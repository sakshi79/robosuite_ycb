# robosuite (local fork)

## Setup

```bash
pip install -e .
```

No separate step for YCB objects (`robosuite.models.objects.YCBObject`): the
raw mesh for a given `ycb_id` downloads automatically (needs internet) the
first time that object is constructed, into `models/assets/objects/ycb/raw/`.
