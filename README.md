# robosuite YCB

## This repo adds the YCB asset suite to robosuite. This is useful for testing your manipulation algorithms for their ability to generalize across various objects.

## Setup

```bash
pip install -e .
```

Ships YCB assets with scripts to generate the required raw files. 

The raw mesh for a given `ycb_id` downloads automatically (needs internet) into `models/assets/objects/ycb/raw/`.

## Choosing the object in Lift

```python
import robosuite as suite
from robosuite.environments.manipulation.lift import YCB_OBJECTS

env = suite.make("Lift", robots="Panda", object_type="011_banana")  # YCB id (or "ycb:011_banana")
env = suite.make("Lift", robots="Panda", object_type="cylinder")    # box | cylinder | capsule | ball
env = suite.make("Lift", robots="Panda", object_type="bottle")      # bottle | can | lemon | milk | bread | cereal

print(YCB_OBJECTS)  # YCB ids that load cleanly
```
