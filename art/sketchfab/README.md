# Sketchfab models

Credits and links: game/models/CREDITS.md.

How the downloads became game/models files (originals are not kept in git):

    npm i @gltf-transform/core @gltf-transform/extensions @gltf-transform/functions meshoptimizer sharp gl-matrix
    node proc.mjs in.glb out.glb '{"ratio":0.5}'          # simplify, quantize, 1024 webp textures
    node proc.mjs lowpoly_spaceships.glb ship_lp1.glb '{"keep":"space shi "}'   # one ship from the pack (also "sapceship 3", "drt", "df")
    node proc.mjs star_sparrow_modular_spaceship.glb ship_sparrow.glb '{"bake":true}'  # use the end pose of its build animation
    node proc.mjs black_hole.glb black_hole.glb '{"ratio":0.05,"error":0.01}' && node thin.mjs black_hole.glb black_hole.glb "black hole_ring_ring2_0" 3

Silver Hawk was turned and scaled with fix.mjs before opt.mjs. The game turns the rest itself (MODEL_SHIPS rot in game/index.html).
Sky pictures are the equirect images inside the two skybox files, saved as JPEG.

Removed 2026-10-20 so the game can make money: Light Fighter (rights belong to EVERSPACE), Raven (a Star Conflict ship),
Toy Rocket (copies the Futurama ship), Red Viper (CC BY-NC-ND, no money). Check the model page for other games' or shows' names before adding a ship.
