# Creatures

The people on every planet (and the big waving aliens) are Quaternius models, CC0 1.0.
`creatures.json` lists each game name, its source file and which clips become walk / idle / cheer / run.

Sources (all CC0, from the original Quaternius packs):
- Ultimate Space Kit: https://quaternius.com/packs/ultimatespacekit.html (also mirrored as `quaternius-ultimate-space-kit.zip` on https://github.com/tilakpatell/tilakpatell.com/releases/tag/assets-quaternius)
- Ultimate Monsters: https://quaternius.com/packs/ultimatemonsters.html (glTF copies in https://github.com/Han1989/tgt-td-cld/tree/HEAD/tools/blender/assets/quaternius/monsters and https://github.com/Benson-LU77/Claude.guide/tree/HEAD/assets/quaternius)

Put the source files in one folder, then:

    npm i @gltf-transform/core @gltf-transform/extensions @gltf-transform/functions
    node art/creatures/proc.mjs <source folder> game/models/creatures

To add a creature: add a row to `creatures.json`, run the script, add it to `PEOPLE_KINDS` in game/index.html
(and to `FLOATERS` if it flies), and to game/models/CREDITS.md.
In the game, `crowdKit()` bakes each clip into a few still frames once, so a whole crowd is drawn as instanced meshes.
