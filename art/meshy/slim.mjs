// shrink a rigged Meshy model for the game: 1024 color map, 512 normal map, no metal/rough map, resampled clips
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, prune, resample, textureCompress } from '@gltf-transform/functions';
import sharp from 'sharp';
const [,, src, out] = process.argv;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(src);
for (const m of doc.getRoot().listMaterials()) { const t = m.getMetallicRoughnessTexture(); if (t) m.setMetallicRoughnessTexture(null); m.setMetallicFactor(0); m.setRoughnessFactor(.75); }
await doc.transform(prune(), resample(), dedup(),
  textureCompress({ encoder: sharp, targetFormat: 'jpeg', quality: 85, resize: [1024, 1024], slots: /baseColor/ }),
  textureCompress({ encoder: sharp, targetFormat: 'jpeg', quality: 85, resize: [512, 512], slots: /normal/ }));
await io.write(out, doc);
console.log(out, (await import('fs')).statSync(out).size);
