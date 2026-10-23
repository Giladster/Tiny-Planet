// Tiny Planet game server.
// Serves the game page, keeps the shared world (planets, players, chat, notes) and passes live
// updates between players over a WebSocket. Run: npm install && npm start  (then open http://localhost:3000)
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { WebSocketServer } from "ws";
import { createStore } from "./store.js";
import { askBolt, boltReady } from "./bolt.js";
import { speak, voiceReady, voiceStatus } from "./voice.js";

const PORT = process.env.PORT || 3000;
const GAME_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "game");
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml", ".json": "application/json", ".glb": "model/gltf-binary", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".md": "text/plain; charset=utf-8" };

// Same numbers as the game, so everyone agrees on how much a hit hurts.
const DAMAGE = { laser: { hp: .5, pop: .004 }, missile: { hp: 5, pop: .045 }, bomb: { hp: 14, pop: .14 } };
const KINDS = ["laser", "missile", "bomb", "atom"];
const MAX_STAMPS = 600, MAX_MAIL = 60, MAX_CHAT = 120;
const PRANK_TYPES = ["sign", "photo", "graffiti", "tp", "ducks", "statue"], MAX_PRANKS = 30;
const PLANET_KEYS = ["name", "design", "decor", "sculpt", "paint", "R"]; // what an owner may change

const id = (p) => p + "_" + crypto.randomBytes(6).toString("hex");
const text = (s, n) => String(s ?? "").replace(/[\u0000-\u001f]/g, "").slice(0, n);
const clockStr = () => new Date().toISOString().slice(11, 16);

// ---------------- world ----------------
const store = await createStore();
const world = { planets: {}, players: {}, chat: [], claims: {} }; // claims: planets someone planted their flag on, by planet name
const dirty = new Set();
{
  const raw = await store.load();
  for (const [k, v] of Object.entries(raw)) {
    if (k.startsWith("planet:")) world.planets[v.id] = v;
    else if (k.startsWith("player:")) world.players[v.id] = v;
    else if (k === "chat") world.chat = v;
    else if (k === "claims") world.claims = v || {};
  }
  console.log(`World loaded from ${store.kind}: ${Object.keys(world.planets).length} planets, ${Object.keys(world.players).length} players`);
}
const markPlanet = (p) => dirty.add("planet:" + p.id);
const markPlayer = (p) => dirty.add("player:" + p.id);
async function flush() {
  if (!dirty.size) return;
  const keys = [...dirty]; dirty.clear();
  const entries = keys.map((k) => {
    const [kind, kid] = k.split(":");
    if (kind === "planet") return [k, world.planets[kid] ?? null];
    if (kind === "player") { const p = world.players[kid]; return [k, p ?? null]; }
    if (k === "claims") return [k, world.claims];
    return [k, world.chat];
  });
  try { await store.save(entries); } catch (e) { console.error("save failed, will retry", e.message); keys.forEach((k) => dirty.add(k)); }
}
setInterval(flush, 8000);
for (const sig of ["SIGTERM", "SIGINT"]) process.on(sig, async () => { await flush(); process.exit(0); });

// The galaxies (same as the game). New players start out in open space, between the galaxies, so the busy
// Main Galaxy never fills up with homes. The Main Galaxy is the city: planets there can be conquered, never destroyed.
const GALAXIES = [{ c: [0, 0, 0], r: 2250 }, { c: [3200, 0, 900], r: 700 }, { c: [-2400, 0, -3000], r: 800 }, { c: [8000, 2600, -12500], r: 1500 }];
const MAIN_R = 2250, SAFE_R = 350; // pirates leave you alone this close to any home
const dist3 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
const inMainGalaxy = (pos) => Array.isArray(pos) && Math.hypot(pos[0], pos[1], pos[2]) < MAIN_R;
const isHome = (p) => !!p.ownerId;
const indestructible = (p) => isHome(p) || inMainGalaxy(p.pos);
function placeNewPlanet() { // a free spot in open space, out of every galaxy and away from other homes
  const homes = Object.values(world.planets).filter((p) => p.ownerId).map((p) => p.pos);
  let best = null;
  for (let i = 0; i < 60; i++) {
    const a = Math.random() * Math.PI * 2, r = MAIN_R + 250 + Math.random() * (500 + i * 20), pos = [Math.round(Math.cos(a) * r), Math.round((Math.random() - .5) * 200), Math.round(Math.sin(a) * r)];
    if (GALAXIES.some((g) => dist3(pos, g.c) < g.r + 150)) continue;
    const gap = Math.min(Infinity, ...homes.map((h) => dist3(pos, h)));
    if (gap > 220) return pos;
    if (!best || gap > best.gap) best = { pos, gap };
  }
  return best ? best.pos : [MAIN_R + 400, 0, 0];
}
function uniqueName(name) {
  const taken = new Set(Object.values(world.planets).map((p) => p.name.toLowerCase()));
  let out = name, i = 2;
  while (taken.has(out.toLowerCase())) out = `${name} ${i++}`;
  return out;
}
const levelOf = (xp) => { let lv = 1; while (xp >= 100 * (lv + 1) * lv) lv++; return lv; };
const publicPlayer = (p) => ({ id: p.id, name: p.name, planetId: p.planetId, ship: p.ship, flag: p.flag || null, empire: p.empire || null });
const snapshot = () => ({ planets: Object.values(world.planets), players: Object.values(world.players).map(publicPlayer), chat: world.chat, claims: world.claims });
function tellVictim(victimId, msg) { // you were attacked: tell you now, or when you come back
  const v = world.players[victimId]; if (!v) return;
  const s = socketOf(v.id); if (s) return send(s, { t: "attacked", ...msg });
  (v.attacks ||= []).push(msg); if (v.attacks.length > 10) v.attacks.shift(); markPlayer(v);
}
function stat(p) { return { t: "stat", id: p.id, hp: p.hp, pop: p.pop, dead: !!p.dead, troops: p.troops || 0 }; }
function applyHit(p, kind) {
  if (p.dead) return;
  if (kind === "atom") p.hp = 0;
  else { const d = DAMAGE[kind]; if (!d) return; p.hp = Math.max(0, p.hp - d.hp); p.pop = Math.max(0, p.pop - p.maxPop * d.pop); }
  if (indestructible(p)) { p.hp = Math.max(1, p.hp); p.pop = Math.max(p.maxPop * .05, p.pop); } // homes and Main Galaxy planets can be beaten down, never destroyed
  if (p.hp <= 0 || p.pop <= 0) { p.dead = true; p.hp = 0; p.pop = 0; p.troops = 0; p.diedAt = Date.now(); }
}

// ---------------- web server ----------------
const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://x");
  if (url.pathname === "/health") { res.writeHead(200, { "content-type": "text/plain", "access-control-allow-origin": "*" }); return res.end("ok"); }
  if (url.pathname === "/status") {
    res.writeHead(200, { "content-type": "application/json", "access-control-allow-origin": "*" });
    return res.end(JSON.stringify({ online: clients.size, planets: Object.keys(world.planets).length, players: Object.keys(world.players).length, storage: store.kind }));
  }
  if (url.pathname === "/voice") { // Bolt's spoken lines (POST {text}); 204 means "no voice here, use the browser's"
    if (req.method === "GET") { res.writeHead(200, { "content-type": "application/json" }); return res.end(JSON.stringify(voiceStatus(), null, 1)); } // a quick health check, no secrets
    if (!voiceReady || req.method !== "POST") { res.writeHead(204, { "x-voice": "off" }); return res.end(); }
    let body = ""; req.on("data", (c) => { body += c; if (body.length > 4000) req.destroy(); });
    req.on("end", async () => {
      let text = "", voice = ""; try { ({ text, voice } = JSON.parse(body)); } catch {}
      const ip = String(req.headers["x-forwarded-for"] || req.socket.remoteAddress || "").split(",")[0].trim();
      const mp3 = await speak(text, ip, voice);
      if (!mp3) { res.writeHead(204); return res.end(); }
      res.writeHead(200, { "content-type": "audio/mpeg", "cache-control": "no-store" }); res.end(mp3);
    });
    return;
  }
  let file = path.normalize(path.join(GAME_DIR, url.pathname === "/" ? "index.html" : decodeURIComponent(url.pathname)));
  if (!file.startsWith(GAME_DIR)) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); return res.end("not found"); }
    res.writeHead(200, { "content-type": MIME[path.extname(file)] || "application/octet-stream", "cache-control": "no-cache" });
    res.end(data);
  });
});

// ---------------- live connections ----------------
const wss = new WebSocketServer({ server, path: "/ws", maxPayload: 3 * 1024 * 1024 });
const clients = new Map(); // socket -> { player, ship }
const send = (ws, msg) => { if (ws.readyState === 1) ws.send(JSON.stringify(msg)); };
const broadcast = (msg, except) => { const s = JSON.stringify(msg); for (const ws of clients.keys()) if (ws !== except && ws.readyState === 1) ws.send(s); };
const socketOf = (playerId) => { for (const [ws, c] of clients) if (c.player && c.player.id === playerId) return ws; return null; };

wss.on("connection", (ws) => {
  clients.set(ws, { player: null, ship: null, rate: 0 });
  ws.on("message", (buf) => {
    let m; try { m = JSON.parse(buf); } catch { return; }
    const c = clients.get(ws); if (!c) return;
    try { handle(ws, c, m); } catch (e) { console.error("bad message", m && m.t, e.message); }
  });
  ws.on("close", () => {
    const c = clients.get(ws); clients.delete(ws);
    if (c && c.player) { c.player.lastSeen = Date.now(); markPlayer(c.player); if (!socketOf(c.player.id) && !flyHomeAlone(c.player, c.ship)) broadcast({ t: "left", pid: c.player.id }); }
  });
});

function handle(ws, c, m) {
  const me = c.player, mine = me && world.planets[me.planetId];
  switch (m.t) {
    case "hello": { // returning players send their secret token
      const p = Object.values(world.players).find((x) => x.token && x.token === m.token);
      if (p && world.planets[p.planetId]) { c.player = p; p.lastSeen = Date.now(); delete p.away; markPlayer(p); } // you are back: you start on your planet again
      if (process.env.ADMIN_KEY && typeof m.god === "string" && m.god === process.env.ADMIN_KEY) { c.god = true; send(ws, { t: "god" }); } // only the game owner knows this key
      if (c.player && c.player.pending) { send(ws, { t: "paid", amount: c.player.pending, from: "Ransoms" }); c.player.pending = 0; markPlayer(c.player); }
      const lost = c.player && c.player.lost; if (lost) { delete c.player.lost; markPlayer(c.player); }
      if (c.player && c.player.attacks && c.player.attacks.length) { const list = c.player.attacks; delete c.player.attacks; markPlayer(c.player); setTimeout(() => list.forEach((a) => send(ws, { t: "attacked", ...a, late: true })), 4000); }
      send(ws, { t: "welcome", you: c.player ? { ...publicPlayer(c.player), wallet: c.player.wallet || null, lost: lost || null } : null, world: snapshot(), needsSeed: !Object.values(world.planets).some((p) => !p.ownerId), boltAi: boltReady });
      break;
    }
    case "seed": { // the very first visitor fills the empty galaxy with the starting planets
      if (Object.values(world.planets).some((p) => !p.ownerId) || !Array.isArray(m.planets)) return;
      for (const raw of m.planets.slice(0, 20)) {
        const p = { ...raw, id: id("p"), ownerId: null, stamps: [], mail: Array.isArray(raw.mail) ? raw.mail.slice(0, MAX_MAIL) : [] };
        delete p.dmg; world.planets[p.id] = p; markPlanet(p);
      }
      broadcast({ t: "world", world: snapshot() });
      break;
    }
    case "join": { // a new player creates their planet
      if (me) return;
      const name = text(m.name, 20).trim() || "Space Cadet", planetName = uniqueName(text(m.planetName, 20).trim() || name + "'s Planet");
      const src = m.planet || {};
      const planet = {
        id: id("p"), ownerId: null, name: planetName, owner: name, R: 1.6, pos: placeNewPlanet(), hp: 100, pop: 8000, maxPop: 8000, dead: false, troops: 0,
        design: src.design || {}, decor: Array.isArray(src.decor) ? src.decor.slice(0, 200) : [], sculpt: null, paint: null, mail: [], stamps: [],
      };
      const player = { id: id("u"), token: crypto.randomBytes(18).toString("hex"), name, planetId: planet.id, ship: m.ship || null, created: Date.now(), lastSeen: Date.now() };
      planet.ownerId = player.id;
      world.planets[planet.id] = planet; world.players[player.id] = player; c.player = player;
      markPlanet(planet); markPlayer(player);
      send(ws, { t: "joined", you: publicPlayer(player), token: player.token, world: snapshot() });
      broadcast({ t: "planetAdd", planet, player: publicPlayer(player) }, ws);
      broadcast({ t: "chat", msg: { who: "📡", text: `${name} joined the galaxy with ${planetName}!`, t: clockStr() } });
      break;
    }
    case "planet": { // the owner changed their planet
      if (!mine || !m.patch) return;
      const patch = {};
      for (const k of PLANET_KEYS) if (k in m.patch) patch[k] = k === "name" ? uniqueNameFor(mine, text(m.patch.name, 20)) : m.patch[k];
      Object.assign(mine, patch); markPlanet(mine);
      broadcast({ t: "planetPatch", id: mine.id, patch }, ws);
      break;
    }
    case "ship": { if (!me) return; me.ship = m.ship; markPlayer(me); broadcast({ t: "shipCfg", pid: me.id, ship: m.ship }, ws); break; }
    case "pos": { if (!me) return; c.ship = { pid: me.id, name: me.name, p: m.p, q: m.q, f: !!m.f, hp: m.hp, lv: Math.min(999, m.lv | 0) || 1 }; break; }
    case "hit": { // someone hit a planet: everyone sees the crater and the new health
      const p = world.planets[m.id]; if (!p || p.dead || !KINDS.includes(m.kind) || !Array.isArray(m.n)) return;
      if (p.shield) return; // god mode shield
      if (m.kind !== "laser" || Math.random() < .4) { p.stamps.push([...m.n.map((x) => +(+x).toFixed(3)), KINDS.indexOf(m.kind)]); if (p.stamps.length > MAX_STAMPS) p.stamps.splice(0, p.stamps.length - MAX_STAMPS); }
      applyHit(p, m.kind); p.lastAttack = Date.now(); markPlanet(p);
      broadcast({ t: "hit", id: p.id, n: m.n, kind: m.kind, by: me ? me.id : null }, ws);
      broadcast(stat(p));
      if (p.dead) broadcast({ t: "chat", msg: { who: "💥", text: `${p.name} was destroyed${me ? " by " + me.name : ""}!`, t: clockStr() } });
      break;
    }
    case "troops": {
      const p = world.planets[m.id]; if (!p || p.dead) return; const count = Math.max(0, Math.min(10, m.count | 0));
      if (p.conqueredBy && me && me.id !== p.conqueredBy.id) { // troops free a conquered planet
        p.freeing = (p.freeing || 0) + count; markPlanet(p);
        if (p.freeing >= 10) { const was = p.conqueredBy; p.conqueredBy = null; p.freeing = 0; p.troops = 0; broadcast({ t: "conquer", id: p.id, by: null }); broadcast({ t: "chat", msg: { who: "🕊", text: `${me.name} freed ${p.name} from ${was.name}!`, t: clockStr() } }); }
        return;
      }
      if (me && p.ownerId === me.id) return; // not on your own people
      p.troops = (p.troops || 0) + count; if (me) p.troopsBy = { id: me.id, name: me.name }; markPlanet(p);
      broadcast({ t: "troops", id: p.id, n: m.n, count }, ws); broadcast(stat(p)); break;
    }
    case "mail": { const p = world.planets[m.id]; if (!p || !me) return; const note = { who: me.name, text: text(m.text, 160), t: clockStr() }; p.mail.push(note); if (p.mail.length > MAX_MAIL) p.mail.shift(); markPlanet(p); broadcast({ t: "mail", id: p.id, note }); break; }
    case "chat": { if (!me) return; const msg = { who: me.name, text: text(m.text, 200), t: clockStr() }; world.chat.push(msg); if (world.chat.length > MAX_CHAT) world.chat.shift(); dirty.add("chat"); broadcast({ t: "chat", msg }); break; }
    case "rebuild": { if (!mine) return; Object.assign(mine, { dead: false, hp: 100, pop: mine.maxPop, troops: 0, stamps: [] }); markPlanet(mine); broadcast({ t: "planetFull", planet: mine }); break; }
    case "resetPlanet": { if (!mine || !m.planet) return; Object.assign(mine, { design: m.planet.design, decor: m.planet.decor, sculpt: null, paint: null, dead: false, hp: 100, pop: mine.maxPop, troops: 0, stamps: [] }); if (c.god) Object.assign(mine, { pranks: [], conqueredBy: null, freeing: 0 }); markPlanet(mine); broadcast({ t: "planetFull", planet: mine }); break; }
    case "shot": { if (!me) return; broadcast({ t: "shot", pid: me.id, kind: m.kind, from: m.from, to: m.to }, ws); break; }
    case "prank": { // leave a prank on someone's planet; it fades after 2 to 4 days
      const p = world.planets[m.id], r = m.prank; if (!p || !me || p.dead || !r || !PRANK_TYPES.includes(r.type)) return;
      if (p.id === me.planetId && !c.god) return;
      const hours = [48, 72, 96].includes(+r.hours) ? +r.hours : 48, vec = (a) => (Array.isArray(a) ? a.slice(0, 3).map((x) => +(+x || 0).toFixed(3)) : null);
      const img = typeof r.img === "string" && r.img.length < 400000 && /^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(r.img) ? r.img : ""; // pictures only, nothing else
      const prank = { id: id("k"), type: r.type, n: vec(r.n) || [0, 1, 0], face: vec(r.face), text: text(r.text || "", 24), img, by: me.name, byId: me.id, at: Date.now(), until: Date.now() + hours * 3600e3 };
      (p.pranks ||= []).push(prank); if (p.pranks.length > MAX_PRANKS) p.pranks.shift(); markPlanet(p);
      broadcast({ t: "prank", id: p.id, prank });
      break;
    }
    case "clean": { // the owner pays to clean a prank off their planet
      if (!mine || !Array.isArray(mine.pranks)) return;
      const before = mine.pranks.length; mine.pranks = mine.pranks.filter((k) => k.id !== m.pid);
      if (mine.pranks.length !== before) { markPlanet(mine); broadcast({ t: "unprank", id: mine.id, pid: m.pid }); }
      break;
    }
    case "godKey": { // the owner types their key in the game
      if (!process.env.ADMIN_KEY) return send(ws, { t: "godNo", why: "nokey" });
      if (typeof m.key === "string" && m.key === process.env.ADMIN_KEY) { c.god = true; send(ws, { t: "god" }); } else send(ws, { t: "godNo", why: "wrong" });
      break;
    }
    case "godConquer": { if (!c.god || !mine) return; mine.conqueredBy = { id: "bot", name: "Test Bot" }; markPlanet(mine); broadcast({ t: "conquer", id: mine.id, by: mine.conqueredBy }); break; }
    case "wallet": { // your credits, level and progress, so they follow you to any browser
      if (!me || !m.wallet || typeof m.wallet !== "object") return;
      if (JSON.stringify(m.wallet).length > 30000) return;
      me.wallet = m.wallet; markPlayer(me); break;
    }
    case "askBolt": { // the player asks their robot a question
      if (!me) return;
      askBolt(me.id, text(m.q, 400), text(m.status || "", 600), m.history).then((r) => send(ws, { t: "boltSays", id: m.id, text: r.text, reason: r.reason }));
      break;
    }
    case "top": { // the Galaxy Top 100, ranked by fame
      const list = Object.values(world.players).filter((p) => p.wallet && p.wallet.fame > 0).sort((a, b) => b.wallet.fame - a.wallet.fame).slice(0, 100)
        .map((p) => ({ id: p.id, name: p.name, planet: world.planets[p.planetId]?.name || "", lv: levelOf(p.wallet.xp | 0), fame: Math.round(p.wallet.fame) }));
      send(ws, { t: "top", list }); break;
    }
    case "wave": { if (!me) return; const to = socketOf(m.to); if (to) send(to, { t: "wave", from: me.name, fromId: me.id, kind: ["wave", "duel", "msg", "invite"].includes(m.kind) ? m.kind : "wave", text: text(m.text || "", 120) }); break; }
    case "ransom": { // the owner pays to get their planet back
      if (!mine || !mine.conqueredBy) return;
      const by = mine.conqueredBy, amount = Math.max(0, Math.min(5000, +m.amount || 0)), boss = world.players[by.id];
      mine.conqueredBy = null; mine.freeing = 0; markPlanet(mine); broadcast({ t: "conquer", id: mine.id, by: null });
      if (boss) { const s2 = socketOf(boss.id); if (s2) send(s2, { t: "paid", amount, from: me.name }); else { boss.pending = (boss.pending || 0) + amount; markPlayer(boss); } }
      broadcast({ t: "chat", msg: { who: "💰", text: `${me.name} paid a ransom to ${by.name} and ${mine.name} is free!`, t: clockStr() } });
      break;
    }
    case "newPlanet": { // your planet was destroyed or taken: start a fresh one somewhere new
      if (!me || !mine || (!mine.dead && !mine.conqueredBy)) return;
      mine.ownerId = null; mine.owner = "ruins of " + me.name; markPlanet(mine); broadcast({ t: "planetPatch", id: mine.id, patch: { owner: mine.owner } });
      const src = m.planet || {};
      const planet = { id: id("p"), ownerId: me.id, name: uniqueName(me.name + "'s New World"), owner: me.name, R: 1.6, pos: placeNewPlanet(), hp: 100, pop: 8000, maxPop: 8000, dead: false, troops: 0,
        design: src.design || {}, decor: Array.isArray(src.decor) ? src.decor.slice(0, 200) : [], sculpt: null, paint: null, mail: [], stamps: [], pranks: [] };
      world.planets[planet.id] = planet; me.planetId = planet.id; markPlanet(planet); markPlayer(me);
      broadcast({ t: "planetAdd", planet, player: publicPlayer(me) }, ws); send(ws, { t: "newHome" });
      break;
    }
    case "godResetWorld": { // the owner wipes the whole galaxy (every planet, player and chat) to test from zero
      if (!c.god) return;
      for (const k of Object.keys(world.planets)) dirty.add("planet:" + k);
      for (const k of Object.keys(world.players)) dirty.add("player:" + k);
      world.planets = {}; world.players = {}; world.chat = []; world.claims = {}; dirty.add("chat"); dirty.add("claims");
      for (const cl of clients.values()) { cl.player = null; cl.ship = null; }
      flush(); console.log("World reset by the owner");
      broadcast({ t: "worldReset" });
      break;
    }
    case "flag": { // your flag: colors, a symbol, maybe your photo; it flies on your planets and maybe your ship
      if (!me || !m.flag || typeof m.flag !== "object") return;
      const f = m.flag, col = (x, d) => (typeof x === "string" && /^#[0-9a-f]{6}$/i.test(x) ? x : d);
      const img = typeof f.img === "string" && f.img.length < 60000 && /^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(f.img) ? f.img : "";
      me.flag = { bg: col(f.bg, "#2a6bff"), fg: col(f.fg, "#ffffff"), pattern: ["plain", "stripe", "cross", "split", "star"].includes(f.pattern) ? f.pattern : "plain", icon: text(f.icon, 4), img };
      markPlayer(me); broadcast({ t: "flag", pid: me.id, flag: me.flag }); break;
    }
    case "claim": { // you planted your flag on a planet: it is yours now
      if (!me || typeof m.name !== "string") return;
      const name = text(m.name, 40), old = world.claims[name];
      if (Object.values(world.planets).some((p) => p.ownerId && p.name === name)) return; // someone's home: only troops can take it
      const n = Array.isArray(m.n) ? m.n.slice(0, 3).map((x) => +(+x || 0).toFixed(3)) : [0, 1, 0];
      world.claims[name] = { by: me.id, byName: me.name, at: Date.now(), n, kind: m.kind === "town" ? "town" : "wild", pos: Array.isArray(m.pos) ? m.pos.slice(0, 3).map((x) => Math.round(+x || 0)) : null };
      dirty.add("claims"); broadcast({ t: "claim", name, claim: world.claims[name] });
      if (old && old.by !== me.id) tellVictim(old.by, { by: { id: me.id, name: me.name }, what: "took", planet: name, at: Date.now() });
      broadcast({ t: "chat", msg: { who: "🚩", text: `${me.name} planted their flag on ${name}!`, t: clockStr() } });
      break;
    }
    case "destroyed": { // you destroyed a planet out in open space: whatever was on it is gone, and so is its flag
      if (!me || typeof m.name !== "string") return;
      const name = text(m.name, 40), old = world.claims[name];
      if (old) { delete world.claims[name]; dirty.add("claims"); broadcast({ t: "claim", name, claim: null }); if (old.by !== me.id) tellVictim(old.by, { by: { id: me.id, name: me.name }, what: "destroyed", planet: name, at: Date.now() }); }
      broadcast({ t: "chat", msg: { who: "💥", text: `${me.name} blew up ${name}! 💥`, t: clockStr() } });
      break;
    }
    case "empire": { // 5 planets close together: you are an Emperor and you name your galaxy
      if (!me) return;
      const mine = Object.values(world.claims).filter((k) => k.by === me.id).length; if (mine < 5) return;
      me.empire = { name: text(m.name, 30).trim() || me.name + "'s Empire", color: typeof m.color === "string" && /^#[0-9a-f]{6}$/i.test(m.color) ? m.color : "#ffd23f" };
      markPlayer(me); broadcast({ t: "empire", pid: me.id, empire: me.empire }); break;
    }
    case "trade": { // offer a trade to another player
      if (!me || !m.offer) return; const to = socketOf(m.to); if (!to) return send(ws, { t: "tradeNo", why: "offline" });
      const n = (x) => Math.max(0, Math.min(100000, Math.floor(+x || 0))), o = m.offer;
      send(to, { t: "trade", from: me.name, fromId: me.id, id: text(m.id, 20), offer: { metal: n(o.metal), crystal: n(o.crystal), fuel: n(o.fuel), credits: n(o.credits) } }); break;
    }
    case "tradeReply": { // yes or no to a trade offer
      if (!me) return; const to = socketOf(m.to); if (to) send(to, { t: "tradeReply", from: me.name, id: text(m.id, 20), ok: !!m.ok }); break;
    }
    case "godShield": { if (!c.god || !mine) return; mine.shield = !!m.on; markPlanet(mine); break; }
    case "pvp": { if (!me) return; const target = socketOf(m.target); if (target) send(target, { t: "hurt", dmg: Math.min(60, +m.dmg || 0), by: me.name }); else hitAway(world.players[m.target], Math.min(60, +m.dmg || 0), me); break; }
  }
}
function uniqueNameFor(planet, name) { const n = name.trim() || planet.name; return n.toLowerCase() === planet.name.toLowerCase() ? n : uniqueName(n); }

// old pranks fade away
setInterval(() => {
  const now = Date.now();
  for (const p of Object.values(world.planets)) {
    if (!Array.isArray(p.pranks) || !p.pranks.length) continue;
    const gone = p.pranks.filter((k) => k.until <= now); if (!gone.length) continue;
    p.pranks = p.pranks.filter((k) => k.until > now); markPlanet(p);
    for (const k of gone) broadcast({ t: "unprank", id: p.id, pid: k.id });
  }
}, 60000);
// ---------------- ships flying home on their own ----------------
// When you log off out in space, your ship flies itself home. Others still see it and can shoot it down.
const FLY_HOME_SPEED = 30, FLY_HOME_MAX_S = 180; // it gets home in 3 minutes at most, even from far away
function flyHomeAlone(p, s) {
  const home = world.planets[p.planetId]; if (!home || !s || !Array.isArray(s.p) || !(s.hp > 0)) return false;
  const d = Math.hypot(s.p[0] - home.pos[0], s.p[1] - home.pos[1], s.p[2] - home.pos[2]);
  if (!(d > 12)) return false; // already home
  p.away = { p: s.p.map(Number), q: s.q, hp: s.hp, lv: s.lv || 1, speed: Math.max(FLY_HOME_SPEED, d / FLY_HOME_MAX_S) };
  markPlayer(p); return true;
}
function hitAway(p, dmg, by) {
  const a = p && p.away; if (!a || socketOf(p.id)) return;
  a.hp -= dmg; markPlayer(p); if (a.hp > 0) return;
  delete p.away; p.lost = { by: by.name, at: Date.now() };
  broadcast({ t: "shipBoom", pid: p.id, by: by.name });
  broadcast({ t: "chat", msg: { who: "💥", text: `${by.name} shot down ${p.name}'s ship while it was flying home!`, t: clockStr() } });
}
function awayStep(dt) {
  const out = [];
  for (const p of Object.values(world.players)) {
    const a = p.away; if (!a) continue;
    const home = world.planets[p.planetId]; if (!home) { delete p.away; continue; }
    const dx = home.pos[0] - a.p[0], dy = home.pos[1] - a.p[1], dz = home.pos[2] - a.p[2], d = Math.hypot(dx, dy, dz);
    if (d < 6) { delete p.away; markPlayer(p); broadcast({ t: "left", pid: p.id }); continue; } // home: it lands and waits for you
    const k = Math.min(1, a.speed * dt / d); a.p = [a.p[0] + dx * k, a.p[1] + dy * k, a.p[2] + dz * k].map((x) => +x.toFixed(2));
    const w = 1 + dz / d; a.q = w < 1e-4 ? [0, 1, 0, 0] : (() => { const x = -dy / d, y = dx / d, n = Math.hypot(x, y, w); return [x / n, y / n, 0, w / n].map((v) => +v.toFixed(3)); })(); // nose toward home
    markPlayer(p);
    out.push({ pid: p.id, name: p.name, p: a.p, q: a.q, f: true, hp: Math.max(0, Math.round(a.hp)), lv: a.lv, away: true });
  }
  return out;
}
// ships of everyone online (and the ones flying home), 10 times a second
setInterval(() => {
  const ships = [...clients.values()].map((c) => c.ship).filter(Boolean).concat(awayStep(.1));
  if (ships.length) broadcast({ t: "ships", ships });
}, 100);
// troops slowly take over planets, even when nobody is looking
setInterval(() => {
  for (const p of Object.values(world.planets)) {
    if (p.dead || !p.troops) continue;
    p.pop = Math.max(0, p.pop - p.maxPop * .0012 * p.troops * 2);
    if (p.pop <= 0) {
      if (p.troopsBy && p.troopsBy.id !== p.ownerId && !p.conqueredBy) { // the troops win: the planet is conquered, not destroyed
        p.conqueredBy = p.troopsBy; p.pop = p.maxPop * .3; p.troops = 0;
        if (p.ownerId) tellVictim(p.ownerId, { by: p.conqueredBy, what: "conquered", planet: p.name, at: Date.now() });
        broadcast({ t: "conquer", id: p.id, by: p.conqueredBy, pop: p.pop });
        broadcast({ t: "chat", msg: { who: "🏴", text: `${p.conqueredBy.name} conquered ${p.name}!`, t: clockStr() } });
      } else applyHit(p, "atom");
    }
    markPlanet(p); broadcast(stat(p));
  }
}, 2000);

server.listen(PORT, () => console.log(`Tiny Planet is running on http://localhost:${PORT}`));
