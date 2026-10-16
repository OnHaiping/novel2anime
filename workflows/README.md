# Workflows

`api/` contains ComfyUI API-format workflows used by the backend. Node ids are part of the application contract and must be updated together with `backend/app/services/workflow.py`.

- `02_environment_api.json`: environment shots or shots without a persistent character.
- `03_character_free_motion_api.json`: IPAdapter character consistency plus AnimateDiff free motion.
- `04_character_openpose_api.json`: IPAdapter plus OpenPose ControlNet plus AnimateDiff.

Before production use, import each corresponding UI workflow into the exact server installation, confirm it runs, export it with **Save (API Format)**, and compare its node inputs with these files. Custom node interfaces can change between commits.

