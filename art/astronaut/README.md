# Your astronaut (on foot)

Source: [Space suit](https://sketchfab.com/3d-models/space-suit-bdc42075279746dab4c8b54784276a20) by IgorSholopov, CC BY 4.0 (Sketchfab glb, 9 parts, 1k PBR textures).

1. Pull the suit's color texture out (see `join.py`'s materials, `base_002`) and paint our own patches over the NASA logo and the Apollo 11 patch:
   `python3 patches.py base.png base_new.png`
2. Join the 9 parts into one mesh with the new texture: `python3.13 join.py -- space_suit.glb joined.glb base_002 base_new.png`
3. Rig + animate: `python3.13 ../meshy/rig.py -- joined.glb UAL1.glb rigged.glb astronaut.json 20000`
   (the suit is many open pieces, so rig.py weights a solid voxel copy and copies the weights over).
4. `node ../meshy/slim.mjs rigged.glb ../../game/models/astronaut.glb` (1024 color maps).

The game loads it as AVATAR in game/index.html; the gold visor material (`helm_gold`) is made shiny there.
