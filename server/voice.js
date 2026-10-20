// Bolt's voice: turns his lines into speech with ElevenLabs (set ELEVENLABS_API_KEY in Render). Free plan only:
// it checks the monthly letters left and never goes over (see roomFor).
// Lines are kept in memory, so repeated lines (tutorial, tips) cost nothing after the first time.
// Each player can only ask for a limited number of new lines, so nobody can burn through the credits.
const KEY = process.env.ELEVENLABS_API_KEY;
const VOICE = process.env.ELEVENLABS_VOICE || "nPczCjzI2devNBz1zQrb"; // "Brian": deep, calm and clear
const MODEL = process.env.ELEVENLABS_MODEL || "eleven_flash_v2_5"; // fast and half the price
const API = process.env.ELEVENLABS_URL || "https://api.elevenlabs.io";
export const voiceReady = !!KEY;

const cache = new Map(), MAX_CACHE = 400; // text -> Promise<Buffer>
const asks = new Map(); // ip -> { n, from }
const LIMIT = 40, WINDOW = 10 * 60 * 1000; // 40 new lines per player every 10 minutes

// Never go over the free monthly letters: ask ElevenLabs how many are used before new lines,
// and stop at 90% of the plan (the browser's voice takes over until the month resets).
let quota = { used: 0, limit: 0, at: 0 };
async function roomFor(n) {
  if (Date.now() - quota.at > 60000) {
    try {
      const r = await fetch(`${API}/v1/user/subscription`, { headers: { "xi-api-key": KEY } });
      if (!r.ok) return false;
      const j = await r.json(); quota = { used: j.character_count || 0, limit: j.character_limit || 0, at: Date.now() };
    } catch { return false; }
  }
  if (quota.used + n > quota.limit * .9) return false;
  quota.used += n; return true;
}
function allowed(ip) {
  const now = Date.now(), a = asks.get(ip);
  if (!a || now - a.from > WINDOW) { asks.set(ip, { n: 1, from: now }); return true; }
  return ++a.n <= LIMIT;
}

export function speak(text, ip) {
  text = String(text || "").replace(/\s+/g, " ").trim().slice(0, 400);
  if (!KEY || !text) return Promise.resolve(null);
  if (cache.has(text)) { const p = cache.get(text); cache.delete(text); cache.set(text, p); return p; }
  if (!allowed(ip)) return Promise.resolve(null);
  const p = roomFor(text.length).then((ok) => !ok ? null : fetch(`${API}/v1/text-to-speech/${VOICE}?output_format=mp3_44100_64`, {
    method: "POST",
    headers: { "xi-api-key": KEY, "content-type": "application/json", accept: "audio/mpeg" },
    body: JSON.stringify({ text, model_id: MODEL, voice_settings: { stability: .55, similarity_boost: .75, style: .2, use_speaker_boost: true } }),
  }).then(async (r) => {
    if (!r.ok) { console.warn("ElevenLabs", r.status, (await r.text()).slice(0, 200)); return null; }
    return Buffer.from(await r.arrayBuffer());
  })).catch((e) => { console.warn("ElevenLabs", e.message); return null; });
  cache.set(text, p);
  p.then((b) => { if (!b) cache.delete(text); });
  if (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value);
  return p;
}
