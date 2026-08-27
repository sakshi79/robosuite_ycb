"""On-demand fetcher for YCB Google-16k raw meshes.

robosuite ships pre-generated XML wrappers and pre-decomposed collision
meshes for YCB objects (models/assets/objects/ycb/{xml,processed}/), but not
the raw Google-16k downloads themselves (~800MB across all objects) -- those
are fetched here, once per object, the first time that object is requested.
"""

import os
import tarfile
import urllib.request
from urllib.error import HTTPError, URLError

REGISTRY_URL = "https://ycb-benchmarks.s3.amazonaws.com/data/objects.json"
TGZ_URL_TEMPLATE = (
    "http://ycb-benchmarks.s3-website-us-east-1.amazonaws.com/"
    "data/google/{name}_google_16k.tgz"
)
# This file lives at <robosuite_pkg>/utils/ycb_download.py; the raw cache is
# a sibling of the pre-shipped xml/processed dirs under models/assets/.
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(_PKG_ROOT, "models", "assets", "objects", "ycb", "raw")


def raw_mesh_path(ycb_id):
    return os.path.join(RAW_DIR, ycb_id, "google_16k", "nontextured.stl")


def is_downloaded(ycb_id):
    return os.path.isfile(raw_mesh_path(ycb_id))


def download(ycb_id):
    """Download and extract the raw Google-16k mesh for a single YCB object
    into RAW_DIR. No-op if already present. Raises on network failure."""
    if is_downloaded(ycb_id):
        return

    obj_dir = os.path.join(RAW_DIR, ycb_id)
    os.makedirs(obj_dir, exist_ok=True)
    tgz_path = os.path.join(obj_dir, f"{ycb_id}_google_16k.tgz")
    url = TGZ_URL_TEMPLATE.format(name=ycb_id)

    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            with open(tgz_path, "wb") as f:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
    except (HTTPError, URLError) as e:
        raise RuntimeError(f"Failed to download YCB object '{ycb_id}' from {url}: {e}") from e

    with tarfile.open(tgz_path) as tar:
        tar.extractall(path=RAW_DIR)
    os.remove(tgz_path)

    if not is_downloaded(ycb_id):
        raise RuntimeError(f"Downloaded '{ycb_id}' but {raw_mesh_path(ycb_id)} is still missing")
