# Silver Hawk

"SpaceShip" by JazOone, CC BY 4.0 (credit required).
Source: https://sketchfab.com/3d-models/spaceship-8dc6c42edd9e4ddeb9283bd5f47701fc
License: http://creativecommons.org/licenses/by/4.0/

Changes for the game (game/models/silver_hawk.glb):
- turned to face +z, rolled 25.7 degrees to sit level, centered, scaled to 0.62 long (fix.mjs)
- 362k to 90k triangles, extra UV sets and tangents removed, quantized, textures 1024 JPEG (opt.mjs)

    npm i @gltf-transform/cli meshoptimizer sharp gl-matrix
    node fix.mjs spaceship.glb fixed.glb 25.7 0.62
    node opt.mjs fixed.glb silver_hawk.glb 0.25
