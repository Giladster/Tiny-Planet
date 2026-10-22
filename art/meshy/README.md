# Realistic aliens from Meshy AI

Gilad makes a model in Meshy (free plan, Meshy 6 Lite, static textured .glb, CC BY 4.0, credit "Meshy AI").
We rig and animate it here with the Quaternius Universal Animation Library (CC0): skeleton + Walk_Loop, Idle_Loop, Celebration, Jog_Fwd_Loop, renamed walk/idle/cheer/run.

1. Write `<kind>.json`: joint spots on the model (Blender coords: Z up, feet at 0, model scaled to 1.829 tall, facing -Y). Read them off a width profile of the mesh (see zorg.json).
2. `python3.13 rig.py -- meshy.glb UAL1.glb rigged.glb <kind>.json 8000` (pip install bpy). It fits the skeleton, auto-skins, turns the arms to T-pose, keeps 4 clips, cuts the mesh to 8000 faces.
3. `node slim.mjs rigged.glb game/models/creatures/<kind>.glb` (1024 color map, 512 normal map).
4. In game/index.html add the kind to PEOPLE_KINDS, REAL_KINDS, SPECIES_VOICE, SPECIES_HINT, SPECIES_LINES and PLANET_KINDS. Add it to game/models/CREDITS.md.

UAL1.glb: Quaternius Universal Animation Library, Unreal-Godot folder (from the tilakpatell.com assets-quaternius release).
