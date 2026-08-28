"""YCB object wrappers: loads Google-16k textured meshes with coacd
convex-decomposition collision pieces. XML wrappers and decomposed collision
meshes ship with robosuite (models/assets/objects/ycb/{xml,processed}/); the
raw Google-16k mesh + texture for a given object is fetched on first use via
robosuite.utils.ycb_download (see that module for why it isn't shipped too).
"""

import os

from robosuite.models.objects import MujocoXMLObject
from robosuite.utils import ycb_download

# This file lives at <robosuite_pkg>/models/objects/ycb_objects.py; the
# pre-shipped XML wrappers live under models/assets/objects/ycb/xml/.
_MODELS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_XML_DIR = os.path.join(_MODELS_DIR, "assets", "objects", "ycb", "xml")


def list_ycb_objects():
    """Return a sorted list of YCB object IDs that have generated XML files."""
    if not os.path.isdir(_XML_DIR):
        return []
    return sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(_XML_DIR)
        if f.endswith(".xml")
    )


class YCBObject(MujocoXMLObject):
    """Load a YCB object by its dataset ID (e.g. '003_cracker_box').

    Args:
        name (str): The name this object will have in the env's scope
            (matches the `name=` arg passed to BoxObject etc.).
        ycb_id (str): YCB dataset object ID, e.g. '003_cracker_box'.
            Must have a corresponding `<_XML_DIR>/<ycb_id>.xml`.
    """

    def __init__(self, name, ycb_id):
        xml_path = os.path.join(_XML_DIR, f"{ycb_id}.xml")
        if not os.path.isfile(xml_path):
            available = list_ycb_objects()
            raise FileNotFoundError(
                f"No YCB XML for '{ycb_id}' at {xml_path}. "
                f"Available ({len(available)}): {available[:5]}..."
            )
        if not ycb_download.is_downloaded(ycb_id):
            ycb_download.download(ycb_id)
        super().__init__(
            xml_path,
            name=name,
            joints=[dict(type="free", damping="0.0005")],
            obj_type="all",
            # Visual mesh (nontextured.stl) already represents the shape; we
            # don't want robosuite's auto-duplicated collision-pieces-as-visuals
            # to render on top (they have no rgba and appear gray).
            duplicate_collision_geoms=False,
        )
        self._ycb_id = ycb_id

    @property
    def ycb_id(self):
        return self._ycb_id
