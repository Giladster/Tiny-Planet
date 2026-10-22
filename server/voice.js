// Bolt's voice: turns his lines into speech with ElevenLabs (set ELEVENLABS_API_KEY in Render). Free plan only:
// it checks the monthly letters left and never goes over (see roomFor).
// Lines are kept in memory, so repeated lines (tutorial, tips) cost nothing after the first time.
// Each player can only ask for a limited number of new lines, so nobody can burn through the credits.
const KEY = process.env.ELEVENLABS_API_KEY;
// Free plans can only use ElevenLabs' own "default" voices through the API (library voices need a paid plan).
// If the chosen voice is refused for that reason, Bolt switches to Brian, a default voice, instead of going silent.
const FALLBACK = "nPczCjzI2devNBz1zQrb"; // Brian
let VOICE = process.env.ELEVENLABS_VOICE || FALLBACK;
// Voices players can pick for Bolt (ElevenLabs' free default voices). Add your own designed voice with ELEVENLABS_EXTRA_VOICES="Name:id,Name2:id2".
export const VOICES = {
  nPczCjzI2devNBz1zQrb: "Brian (deep, calm)", JBFqnCBsd6RMkjVDRZzb: "George (warm, British)", onwK4e9ZLuTAKqWW03F9: "Daniel (newsreader, British)",
  TX3LPaxmHKxFdv7VOQHJ: "Liam (young, energetic)", N2lVS1w4EtoT3dr4eOWO: "Callum (gravelly, intense)", IKne3meq5aSn9XLyUdCD: "Charlie (Australian)",
  cjVigY5qzO86Huf0OWal: "Eric (smooth)", iP95p4xoKVk53GoZ742B: "Chris (casual)", pNInz6obpgDQGcFmaJgB: "Adam (deep)", SAz9YHcvj6GT2YYXdXww: "River (calm, neutral)",
  EXAVITQu4vr4xnSDxMlL: "Sarah (soft)", Xb7hH8MSUJpSbSDYk0k2: "Alice (clear, British)", XrExE9yKIg1WjnnlVkGX: "Matilda (friendly)", cgSgspJ2msm6clMCkdW9: "Jessica (bright)",
};
for (const kv of String(process.env.ELEVENLABS_EXTRA_VOICES || "").split(",")) { const [name, id] = kv.split(":").map((x) => x?.trim()); if (name && id) VOICES[id] = name; }
if (process.env.ELEVENLABS_VOICE && !VOICES[VOICE]) VOICES[VOICE] = "Custom";
const MODEL = process.env.ELEVENLABS_MODEL || "eleven_turbo_v2_5"; // smooth and natural, and lets us force English (flash was choppy, multilingual misread words)
const API = process.env.ELEVENLABS_URL || "https://api.elevenlabs.io";
export const voiceReady = !!KEY;

const cache = new Map(), MAX_CACHE = 400; // text -> Promise<Buffer>
const asks = new Map(); // ip -> { n, from }
const LIMIT = 40, WINDOW = 10 * 60 * 1000; // 40 new lines per player every 10 minutes

// Never go over the free monthly letters: ask ElevenLabs how many are used before new lines,
// and stop at 90% of the plan (the browser's voice takes over until the month resets).
let quota = { used: 0, limit: 0, at: 0 }, lastError = "", made = 0;
export const voiceStatus = () => ({ key: voiceReady, voice: VOICE, voices: VOICES, made, cached: cache.size, letters: quota.at ? `${quota.used} of ${quota.limit}` : "not checked yet", lastError: lastError || "none" });
async function roomFor(n) {
  if (Date.now() - quota.at > 60000) {
    try {
      const r = await fetch(`${API}/v1/user/subscription`, { headers: { "xi-api-key": KEY } });
      if (!r.ok) { lastError = `plan check ${r.status}: ${(await r.text()).slice(0, 200)}`; return false; }
      const j = await r.json(); quota = { used: j.character_count || 0, limit: j.character_limit || 0, at: Date.now() };
    } catch (e) { lastError = "plan check: " + e.message; return false; }
  }
  if (quota.used + n > quota.limit * .9) { lastError = "free letters for this month are almost used up"; return false; }
  quota.used += n; return true;
}
function allowed(ip) {
  const now = Date.now(), a = asks.get(ip);
  if (!a || now - a.from > WINDOW) { asks.set(ip, { n: 1, from: now }); return true; }
  return ++a.n <= LIMIT;
}

// The free plan allows only 2 voice requests at the same time; the rest wait their turn instead of failing.
let busy = 0; const waiting = [];
function slot(job) {
  return new Promise((ok) => { const go = () => { busy++; job().then(ok, () => ok(null)).finally(() => { busy--; waiting.shift()?.(); }); }; busy < 2 ? go() : waiting.push(go); });
}
export function speak(text, ip, voice) {
  text = String(text || "").replace(/\s+/g, " ").trim().slice(0, 400);
  if (!KEY || !text) return Promise.resolve(null);
  if (!VOICES[voice]) voice = VOICE;
  const key = voice + "|" + text;
  if (cache.has(key)) { const p = cache.get(key); cache.delete(key); cache.set(key, p); return p; }
  if (!allowed(ip)) return Promise.resolve(null);
  const say = (voice) => slot(() => fetch(`${API}/v1/text-to-speech/${voice}?output_format=mp3_44100_64`, {
    method: "POST",
    headers: { "xi-api-key": KEY, "content-type": "application/json", accept: "audio/mpeg" },
    body: JSON.stringify({ text, model_id: MODEL, language_code: "en", apply_text_normalization: "on", voice_settings: { stability: .3, similarity_boost: .8, style: .45, use_speaker_boost: true } }),
  }).then(async (r) => {
    if (!r.ok) {
      const why = (await r.text()).slice(0, 200); lastError = `speech ${r.status} (${voice}): ${why}`; console.warn("ElevenLabs", lastError);
      if ((r.status === 402 || r.status === 404 || r.status === 400) && voice !== FALLBACK) return { retry: true }; // a paid-only or unknown voice: use the free default one
      return null;
    }
    made++; return Buffer.from(await r.arrayBuffer());
  }));
  const p = roomFor(text.length).then((ok) => !ok ? null : say(voice)).then((b) => b?.retry ? say(FALLBACK) : b).catch((e) => { lastError = "speech: " + e.message; console.warn("ElevenLabs", e.message); return null; });
  cache.set(key, p);
  p.then((b) => { if (!b) cache.delete(key); });
  if (cache.size > MAX_CACHE) cache.delete(cache.keys().next().value);
  return p;
}
