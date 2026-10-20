// turn Quaternius creature models (CC0) into small .glb files for the planet people: only the clips the game uses, renamed walk/idle/cheer/run
// usage: node proc.mjs <folder with the source .gltf/.glb files> <out folder>   (list of creatures: creatures.json)
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, prune, resample } from '@gltf-transform/functions';
import fs from 'fs';
const [,, src, out] = process.argv;
const list = JSON.parse(fs.readFileSync(new URL('./creatures.json', import.meta.url)));
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
for (const [key, c] of Object.entries(list)) {
  const doc = await io.read(`${src}/${c.src}`), root = doc.getRoot();
  for (const n of root.listNodes()) if (n.getMesh() && (c.drop || []).includes(n.getMesh().getName())) n.setMesh(null); // guns, tridents
  const want = Object.fromEntries(Object.entries(c.clips).map(([k, v]) => [v, k]));
  for (const a of root.listAnimations()) { const k = want[a.getName()]; if (k && !root.listAnimations().some((b) => b.getName() === k)) a.setName(k); else a.dispose(); }
  await doc.transform(resample(), dedup(), prune()); // textures stay PNG: they are tiny color palettes, and lossy formats smear the colors
  await io.write(`${out}/${key}.glb`, doc);
  console.log(key, fs.statSync(`${out}/${key}.glb`).size, root.listAnimations().map((a) => a.getName()).join(' '));
}
