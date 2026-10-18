import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { quantize, dedup, prune, join, weld, simplify, textureCompress, flatten } from '@gltf-transform/functions';
import { MeshoptSimplifier } from 'meshoptimizer';
import sharp from 'sharp';
const [,, inp, out, ratio] = process.argv;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(inp);
for (const m of doc.getRoot().listMeshes()) for (const p of m.listPrimitives()) for (const s of ['TEXCOORD_1','TEXCOORD_2','TEXCOORD_3','TANGENT']) { const a = p.getAttribute(s); if (a) p.setAttribute(s, null); }
const img = doc.getRoot().listTextures(); for (const t of img) console.log('tex', t.getName(), t.getMimeType(), t.getSize());
for (const mat of doc.getRoot().listMaterials()) console.log('mat', mat.getName(), !!mat.getBaseColorTexture(), !!mat.getMetallicRoughnessTexture(), !!mat.getNormalTexture(), !!mat.getEmissiveTexture(), mat.getEmissiveFactor(), mat.getMetallicFactor(), mat.getRoughnessFactor());
await MeshoptSimplifier.ready;
await doc.transform(dedup(), flatten(), join(), weld(), simplify({ simplifier: MeshoptSimplifier, ratio: +ratio, error: 0.0008 }), prune(),
  quantize(), textureCompress({ encoder: sharp, targetFormat: 'jpeg', resize: [1024, 1024], quality: 85 }));
let tris = 0; for (const m of doc.getRoot().listMeshes()) for (const p of m.listPrimitives()) tris += p.getIndices().getCount() / 3;
console.log('tris', tris);
await io.write(out, doc);
