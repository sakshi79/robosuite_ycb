# robosuite YCB

## This repo adds the YCB asset suite to robosuite. This is useful for testing your manipulation algorithms for their ability to generalize across various objects.

## Setup

```bash
pip install -e .
```

Ships YCB assets with scripts to generate the required raw files. 

The raw mesh for a given `ycb_id` downloads automatically (needs internet) into `models/assets/objects/ycb/raw/`.
