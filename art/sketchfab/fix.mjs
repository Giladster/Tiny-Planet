import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { transformMesh, getBounds } from '@gltf-transform/functions';
import { mat4 } from 'gl-matrix';
const [,, inp, out, roll, len] = process.argv;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(inp); const sc = doc.getRoot().listScenes()[0];
const M = mat4.create(); mat4.rotateY(M, M, Math.PI); mat4.rotateZ(M, M, +roll * Math.PI / 180);
for (const n of doc.getRoot().listNodes()) { const m = n.getMesh(); if (!m) continue; const W = mat4.multiply(mat4.create(), M, n.getWorldMatrix()); transformMesh(m, W); n.setMatrix(mat4.create()); }
for (const n of doc.getRoot().listNodes()) n.setMatrix(mat4.create());
let b = getBounds(sc); const c = b.min.map((v, i) => (v + b.max[i]) / 2), L = b.max[2] - b.min[2], s = +len / L;
const M2 = mat4.create(); mat4.scale(M2, M2, [s, s, s]); mat4.translate(M2, M2, c.map((v) => -v));
for (const n of doc.getRoot().listNodes()) { const m = n.getMesh(); if (m) transformMesh(m, M2); }
b = getBounds(sc); console.log(JSON.stringify(b));
await io.write(out, doc);
