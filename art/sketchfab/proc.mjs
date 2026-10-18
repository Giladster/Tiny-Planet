// shrink a Sketchfab .glb for the browser: optional keep one ship from a pack, bake an animation pose, simplify, small webp textures
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, prune, join, weld, simplify, textureCompress, flatten, metalRough, quantize, resample } from '@gltf-transform/functions';
import { MeshoptSimplifier } from 'meshoptimizer';
import sharp from 'sharp';
const [,, inp, out, optsJson] = process.argv;
const o = { ratio: 1, tex: 1024, keep: null, bake: false, quant: true, ...JSON.parse(optsJson || '{}') };
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(inp), root = doc.getRoot();
if (o.keep) { // keep one subtree by node name, drop the rest of the pack
  const keep = root.listNodes().find((n) => n.getName() === o.keep); if (!keep) throw new Error('no node ' + o.keep);
  const inKeep = new Set(); const walk = (n) => { inKeep.add(n); n.listChildren().forEach(walk); }; walk(keep);
  for (const n of root.listNodes()) if (n.getMesh() && !inKeep.has(n)) n.setMesh(null);
}
if (o.bake) { // put every part where the animation ends, then drop the animation
  for (const a of root.listAnimations()) {
    for (const ch of a.listChannels()) {
      const s = ch.getSampler(), out = s.getOutput().getArray(), n = ch.getTargetNode(), path = ch.getTargetPath(), k = path === 'rotation' ? 4 : 3;
      const last = Array.from(out.slice(out.length - k));
      if (path === 'translation') n.setTranslation(last); else if (path === 'rotation') n.setRotation(last); else if (path === 'scale') n.setScale(last);
    }
    a.dispose();
  }
  for (const n of root.listNodes()) { const w = n.getWorldMatrix(); if (n.getMesh() && Math.hypot(w[0], w[1], w[2]) < 1e-6) n.setMesh(null); } // parts the pose hides
}
if (o.noanim) for (const a of root.listAnimations()) a.dispose();
for (const m of root.listMeshes()) for (const p of m.listPrimitives()) for (const s of ['TEXCOORD_2', 'TEXCOORD_3', 'TANGENT', 'COLOR_1']) if (p.getAttribute(s)) p.setAttribute(s, null);
for (const m of root.listMeshes()) for (const p of m.listPrimitives()) if (p.getAttribute('TEXCOORD_1') && !root.listTextures().length) p.setAttribute('TEXCOORD_1', null);
await MeshoptSimplifier.ready;
const steps = [metalRough(), dedup(), flatten(), join(), weld()];
if (o.ratio < 1) steps.push(simplify({ simplifier: MeshoptSimplifier, ratio: o.ratio, error: o.error ?? 0.001 }));
steps.push(prune());
if (o.quant) steps.push(quantize());
steps.push(textureCompress({ encoder: sharp, targetFormat: 'webp', resize: [o.tex, o.tex], quality: 85 }));
await doc.transform(...steps);
let tris = 0; for (const m of root.listMeshes()) for (const p of m.listPrimitives()) tris += (p.getIndices() ? p.getIndices().getCount() : p.getAttribute('POSITION').getCount()) / 3;
await io.write(out, doc);
console.log(out, 'tris', tris);
