// keep 1 of every N little debris quads in a mesh (the black hole's dust ring), so the file gets smaller
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { compactPrimitive, prune } from '@gltf-transform/functions';
const [,, inp, out, meshName, keepEvery] = process.argv;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS), doc = await io.read(inp), N = +keepEvery;
for (const m of doc.getRoot().listMeshes()) if (m.getName() === meshName) for (const p of m.listPrimitives()) {
  const ix = p.getIndices(), a = ix.getArray(), kept = [];
  for (let q = 0; q < a.length / 6; q++) if (q % N === 0) for (let k = 0; k < 6; k++) kept.push(a[q * 6 + k]);
  ix.setArray(new Uint32Array(kept)); compactPrimitive(p);
}
await doc.transform(prune()); await io.write(out, doc);
