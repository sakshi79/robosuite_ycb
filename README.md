# robosuite YCB

## Setup

```bash
pip install -e .
```

Ships YCB assets with scripts to generate the required raw files. 

The raw mesh for a given `ycb_id` downloads automatically (needs internet) the
first time that object is constructed, into `models/assets/objects/ycb/raw/`.
