"""Modern-mujoco offscreen renderer that mirrors a mujoco_py-based env, but
replaces YCB visual meshes (nontextured.stl) with the textured.obj +
texture_map.png pair so the rendered camera frames carry the real UV-mapped
photo textures.

Used as a side-channel: physics still runs on mujoco_py inside robosuite;
this renderer only produces image observations. State sync is via qpos.
"""

from __future__ import annotations

import os
import re
from xml.etree import ElementTree as ET

# Force modern mujoco's Renderer to use EGL (GPU offscreen, no X server).
# Without this, the default GLFW backend tries to open an X11 connection per
# process; AsyncVectorEnv workers then dogpile the X server and it crashes
# (BrokenPipeError + "X connection to :N broken"). EGL is contention-free
# across processes and doesn't need a display.
# Must be set before mujoco is first imported in this process; setdefault
# respects an explicit user override (e.g. MUJOCO_GL=osmesa for CPU-only).
os.environ.setdefault("MUJOCO_GL", "egl")

# IMPORTANT: do NOT import mujoco at module load. mujoco.egl initializes
# EGL_DISPLAY (a module-level handle) at first import, and if this happens
# in the parent of an AsyncVectorEnv fork, the workers inherit that stale
# handle and eglCreateContext fails with EGL_BAD_ALLOC. We import mujoco
# lazily inside methods so it only happens in the process that actually
# renders (i.e., workers, after fork — never the parent).
import numpy as np


def _mj():
    """Lazy mujoco import. Each process imports mujoco for the first time
    on its own (workers after fork) so EGL_DISPLAY is created fresh per
    process."""
    import mujoco
    return mujoco


# Matches the raw YCB visual STL path emitted for YCBObject (see
# robosuite/models/objects/ycb_objects.py + utils/ycb_download.py).
# Captures: (full_path, ycb_id, base_dir)
_YCB_STL_RE = re.compile(
    r"^(?P<base>.*?/raw/(?P<ycb>[^/]+))/google_16k/nontextured\.stl$"
)


def _swap_ycb_visuals_to_textured(scene_xml: str) -> str:
    """Take a robosuite-assembled scene XML that uses nontextured.stl meshes
    for YCB objects, return an equivalent XML where each such mesh is replaced
    with textured.obj and a per-object texture/material pair is added to the
    asset block; the corresponding visual geom is updated to use the material
    (and any existing rgba is dropped)."""
    root = ET.fromstring(scene_xml)
    asset = root.find("asset")
    if asset is None:
        return scene_xml

    # First pass: find YCB visual meshes, swap their file paths, plan
    # texture/material additions.
    pending_assets = []  # (texture_elem_attribs, material_elem_attribs)
    geom_material_updates = {}  # {mesh_name: material_name}

    for mesh_elem in list(asset.findall("mesh")):
        file_attr = mesh_elem.get("file", "")
        m = _YCB_STL_RE.match(file_attr)
        if m is None:
            continue
        base = m.group("base")
        textured_obj = os.path.join(base, "google_16k", "textured.obj")
        texture_png = os.path.join(base, "google_16k", "texture_map.png")
        if not (os.path.isfile(textured_obj) and os.path.isfile(texture_png)):
            continue

        mesh_elem.set("file", textured_obj)
        mesh_name = mesh_elem.get("name")
        tex_name = f"_ycbtex_{mesh_name}"
        mat_name = f"_ycbmat_{mesh_name}"

        pending_assets.append((
            {"name": tex_name, "type": "2d", "file": texture_png},
            # Explicit rgba=1 so the texture is shown at full brightness;
            # modern mujoco multiplies texture by material rgba, which defaults
            # to a dark gray (would make textured surfaces look black).
            {"name": mat_name, "texture": tex_name, "rgba": "1 1 1 1",
             "specular": "0.2", "shininess": "0.1"},
        ))
        geom_material_updates[mesh_name] = mat_name

    if not pending_assets:
        return scene_xml

    for tex_attribs, mat_attribs in pending_assets:
        ET.SubElement(asset, "texture", attrib=tex_attribs)
        ET.SubElement(asset, "material", attrib=mat_attribs)

    # Second pass: update geoms that reference the swapped meshes.
    for geom in root.iter("geom"):
        mesh_name = geom.get("mesh")
        if mesh_name in geom_material_updates:
            if "rgba" in geom.attrib:
                del geom.attrib["rgba"]
            geom.set("material", geom_material_updates[mesh_name])

    return ET.tostring(root, encoding="unicode")


class TexturedRenderer:
    """Render frames of a robosuite env using modern mujoco with real YCB
    textures. Physics state is read from env.sim each frame; only rendering
    happens here.

    Args:
        env: a robosuite env (mujoco_py-backed). We snapshot its assembled XML
            once at construction; if you call env.reset() with hard_reset=True
            the model can change, so reconstruct this renderer.
        height, width: output image dimensions.
    """

    def __init__(self, env, height: int = 480, width: int = 480):
        # Modern mujoco's default offscreen framebuffer is 480x480; anything
        # larger requires <visual><global offheight=.../></visual> in the XML.
        # We inject this so the user can pick any size.
        scene_xml = env.sim.model.get_xml()
        textured_xml = _swap_ycb_visuals_to_textured(scene_xml)
        textured_xml = _ensure_offscreen_buffer(textured_xml, height, width)
        mj = _mj()
        self.model = mj.MjModel.from_xml_string(textured_xml)
        self.data = mj.MjData(self.model)
        # mujoco.Renderer is created LAZILY in render(). Creating it eagerly
        # in __init__ would acquire an EGL/GL context in this process; if this
        # TexturedRenderer is being built in a parent that later fork()s
        # workers (AsyncVectorEnv pattern), the inherited EGL state would be
        # corrupt in the children and produce GL_FRAMEBUFFER_UNSUPPORTED.
        self.renderer = None
        self._h, self._w = height, width

        # Match robosuite/mujoco_py rendering convention:
        #   - geomgroup: only show group=1 visual geoms; hide collision (group=0).
        #   - sitegroup: hide ALL site visualizations (gripper gizmos, ee axes,
        #     etc.); mujoco_py hides them by default in offscreen renders but
        #     modern mujoco shows them, which is visually distracting and
        #     would corrupt image observations used for training.
        self._scene_option = mj.MjvOption()
        for i in range(len(self._scene_option.geomgroup)):
            self._scene_option.geomgroup[i] = 1 if i == 1 else 0
        for i in range(len(self._scene_option.sitegroup)):
            self._scene_option.sitegroup[i] = 0

        # Sanity: state vectors must align so qpos copy is valid.
        assert self.model.nq == env.sim.model.nq, (
            f"qpos size mismatch ({self.model.nq} vs {env.sim.model.nq}); the "
            "textured XML diverged structurally from the physics XML"
        )
        assert self.model.nv == env.sim.model.nv, "nv mismatch"

    def render(self, env, camera_name: str) -> np.ndarray:
        """Sync state from env's mujoco_py sim and render one frame."""
        mj = _mj()
        if self.renderer is None:
            self.renderer = mj.Renderer(
                self.model, height=self._h, width=self._w,
            )
        self.data.qpos[:] = env.sim.data.qpos
        self.data.qvel[:] = env.sim.data.qvel
        mj.mj_forward(self.model, self.data)
        self.renderer.update_scene(
            self.data, camera=camera_name, scene_option=self._scene_option,
        )
        # .copy() detaches the result from mujoco's internal ctypes-backed
        # framebuffer. Without this, the array carries an unpickleable
        # pointer and AsyncVectorEnv workers fail to ship obs back to the
        # parent ("ctypes objects containing pointers cannot be pickled").
        return self.renderer.render().copy()


def _ensure_offscreen_buffer(scene_xml: str, height: int, width: int) -> str:
    """Inject/upsize <visual><global offheight=.. offwidth=.. /></visual> so the
    modern mujoco offscreen renderer can produce frames at the requested size."""
    root = ET.fromstring(scene_xml)
    visual = root.find("visual")
    if visual is None:
        visual = ET.SubElement(root, "visual")
    glob = visual.find("global")
    if glob is None:
        glob = ET.SubElement(visual, "global")
    glob.set("offheight", str(int(height)))
    glob.set("offwidth", str(int(width)))
    return ET.tostring(root, encoding="unicode")
