"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (s) => { s = Math.max(0, Math.round(s || 0)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const ICON = {
  play: '<path d="M7 4l13 8-13 8z"/>',
  pause: '<path d="M7 4h3v16H7zM14 4h3v16h-3z"/>',
};

/* ---------- static config ---------- */

const SECTIONS = ["Intro", "Verse", "Pre-Chorus", "Chorus", "Bridge", "Outro"];
const DEFAULT_LYRICS = $("lyrics").value;
const CHIPS = {
  Genre: ["pop", "indie pop", "rock", "hip hop", "r&b", "electronic", "melodic techno", "progressive house", "EDM", "trance", "techno", "synthwave", "lo-fi", "jazz", "funk", "folk", "country", "metal", "soul", "house", "reggae", "cinematic"],
  Mood: ["uplifting", "melancholic", "dreamy", "energetic", "romantic", "dark", "chill", "epic", "hypnotic", "euphoric", "nostalgic"],
  Instr: ["acoustic guitar", "electric guitar", "piano", "warm Rhodes", "synth pads", "808 bass", "strings", "brass", "soft drums", "punchy drums"],
  Vocal: ["female vocal", "male vocal", "airy vocal", "raspy vocal", "choir harmonies"],
  Mix: ["polished demo mix", "lo-fi tape", "wide stereo", "live band feel", "radio ready"],
};
const SLIDERS = [
  { id: "num_inference_steps", label: "Steps", min: 2, max: 32, step: 1, def: 8 },
  { id: "guidance_scale", label: "Guidance", min: 0.8, max: 3, step: 0.01, def: null, defLabel: "auto" },
  { id: "semantic_temperature", label: "Temperature", min: 0.5, max: 1.5, step: 0.05, def: 1.0 },
  { id: "semantic_top_p", label: "Top-p", min: 0.5, max: 1, step: 0.01, def: 0.95 },
  { id: "semantic_top_k", label: "Top-k", min: 10, max: 300, step: 5, def: 100 },
  { id: "semantic_repetition_penalty", label: "Repetition", min: 1, max: 1.6, step: 0.01, def: 1.2 },
];

/* ---------- demo templates ---------- */

const GENRE_TEMPLATES = [
  {
    id: "progressive-metal", name: "Progressive Metal", hint: "Layered riffs · polyrhythms · clean vocal",
    style: "English, progressive metal, 128 BPM, syncopated seven-string guitar riffs, tight palm-muted rhythm guitars, polyrhythmic drums, melodic lead guitar, atmospheric keyboards, expressive clean male vocal, dynamic verse-chorus development, compact instrumental bridge, resolved outro, powerful balanced mix, wide stereo",
  },
  {
    id: "indie-pop", name: "Indie Pop", hint: "Bright guitars · warm vocal · catchy hooks",
    style: "English, indie pop, 110 BPM, bright acoustic guitar, jangly electric guitar, warm bass, soft punchy drums, intimate lead vocal, layered chorus harmonies, catchy melodic hook, gentle build-up, concise intro, resolved outro, warm polished mix",
  },
  {
    id: "cinematic-synthwave", name: "Cinematic Synthwave", hint: "Analog synths · retro drums · airy vocal",
    style: "English, cinematic synthwave, 100 BPM, analog synth arpeggios, warm pulsing bass, retro drum machine, spacious pads, soaring synth lead, airy female vocal, nostalgic night-drive mood, expansive melodic chorus, concise instrumental transitions, resolved outro, wide stereo",
  },
  {
    id: "soul-rnb", name: "Soul & R&B", hint: "Rhodes · laid-back groove · soulful vocal",
    style: "English, contemporary soul, R&B, 85 BPM, warm Rhodes piano, deep rounded bass, laid-back drums, subtle electric guitar, expressive soulful lead vocal, rich backing harmonies, intimate verses, uplifting chorus, restrained vocal runs, gentle resolved outro, warm clean mix",
  },
  {
    id: "jazz-fusion", name: "Jazz Fusion", hint: "Electric piano · intricate groove · smooth vocal",
    style: "English, jazz fusion, 115 BPM, electric piano, articulate electric bass, intricate syncopated drums, clean melodic guitar, colorful extended harmony, smooth lead vocal, memorable chorus, compact instrumental interplay, dynamic arrangement, resolved outro, detailed live-band mix",
  },
];

const DEMOS = [
  {
    id: "lux-tenebris",
    label: "Demo · Melodic Techno",
    hint: "4 min cinematic melodic techno: dark synths, arpeggios, ethereal vocal, festival drops",
    params: {
      title: "Lux In Tenebris",
      lyrics: `[Intro]
Can you feel it in the dark
Can you feel it in the dark

[Verse]
Neon veins across a midnight sky
Silent engines learning how to fly
I follow the pulse through the static and the rain
Every heartbeat whispers out your name

[Pre-Chorus]
Hold on, the light is breaking through
Hold on, I'm falling into you

[Chorus]
We are the light in the dark
Burning like a thousand stars
Lux in tenebris, we never fall apart
We are the light, we are the light in the dark

[Verse]
Cities sleeping under frozen glass
Shadows dancing, memories that pass
You turned the silence into something I could hear
A single spark and all the night is clear

[Pre-Chorus]
Hold on, the sky is opening wide
Hold on, there's fire on the other side

[Chorus]
We are the light in the dark
Burning like a thousand stars
Lux in tenebris, we never fall apart
We are the light, we are the light in the dark

[Bridge]
When the world goes quiet
And the stars go cold
I will be your signal
I will bring you home

[Chorus]
We are the light in the dark
Burning like a thousand stars
Lux in tenebris, we never fall apart
We are the light, we are the light in the dark

[Outro]
Can you feel it in the dark
We are the light in the dark`,
      style: "English, melodic techno, dark progressive house, cinematic, 124 BPM, four-on-the-floor kick, pulsing rolling bassline, hypnotic synth arpeggios, huge analog lead, epic supersaw chords, atmospheric pads, ethereal female vocal, airy reverb, emotional build-up, massive festival drop, wide stereo, polished club master",
      cot: "full",
    },
  },
];

function setupDemos() {
  $("demo-row").innerHTML = DEMOS.map((d) => `
    <button type="button" class="demo-btn" data-demo="${d.id}" title="${esc(d.hint)}">
      <svg viewBox="0 0 24 24"><path d="M12 3l1.9 5.8L20 10l-5 3.9L16.5 20 12 16.6 7.5 20 9 13.9 4 10l6.1-1.2z"/></svg>
      <span><b>${esc(d.label)}</b><small>${esc(d.hint)}</small></span>
    </button>`).join("");
  $("demo-row").onclick = (e) => {
    const b = e.target.closest("[data-demo]"); if (!b) return;
    const d = DEMOS.find((x) => x.id === b.dataset.demo);
    loadIntoForm(d.params);
    $("seed-random").checked = true; $("seed").disabled = true;   // every press of Create is a new take
    b.classList.add("loaded"); setTimeout(() => b.classList.remove("loaded"), 900);
  };
}

function setupGenreTemplates() {
  $("template-grid").innerHTML = GENRE_TEMPLATES.map((template) => `
    <button type="button" class="template-btn" data-template="${template.id}" aria-pressed="false">
      <b>${esc(template.name)}</b><small>${esc(template.hint)}</small>
    </button>`).join("");
  $("template-grid").onclick = (event) => {
    const button = event.target.closest("[data-template]"); if (!button) return;
    const template = GENRE_TEMPLATES.find((item) => item.id === button.dataset.template);
    window.Vibe?.clearCreateReference();
    $("lyrics").value = DEMOS.find((demo) => demo.id === "lux-tenebris").params.lyrics;
    updateLyricsCount();
    $("style").value = template.style;
    syncChips();
    $("template-status").textContent = `${template.name} template applied.`;
  };
  syncChips();
}

/* ---------- state ---------- */

const state = { library: [], jobs: [], current: null, adv: {}, cot: "off", variations: 1, jobsAt: 0, submitting: false };
const audio = $("audio");

/* ---------- generative covers ---------- */

const coverCache = new Map();
function songCover(song, size = 256) {
  return song?.vibe && song.artifacts?.vibe_image ? `/outputs/${encodeURIComponent(song.artifacts.vibe_image)}` : cover(song.name, size);
}
function vibeImageCount(song) { return song.vibe?.image_count || song.vibe?.images?.length || 1; }
function hash(str) { let h = 2166136261; for (const c of str) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
function rng(seed) { return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const PIGMENTS = ["#d9a441", "#3f5f8a", "#7f9f72", "#8e6a8f", "#b5552e", "#4f8a8b", "#c98a3a", "#5a6f9e"];
function cover(key, size = 256) {
  // Watercolour on aged parchment, after the Lux In Tenebris illustrations.
  const k = key + size;
  if (coverCache.has(k)) return coverCache.get(k);
  const r = rng(hash(key)), c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d"), S = size, u = S / 256;
  const pick = () => PIGMENTS[Math.floor(r() * PIGMENTS.length)];
  const rgba = (hex, a) => `rgba(${parseInt(hex.slice(1, 3), 16)},${parseInt(hex.slice(3, 5), 16)},${parseInt(hex.slice(5, 7), 16)},${a})`;

  // parchment
  const base = g.createLinearGradient(0, 0, S, S);
  base.addColorStop(0, "#efe3c8"); base.addColorStop(1, "#dcc8a2");
  g.fillStyle = base; g.fillRect(0, 0, S, S);
  for (let i = 0; i < 7; i++) {           // mottling
    const x = r() * S, y = r() * S, rad = S * (0.15 + r() * 0.35), m = g.createRadialGradient(x, y, 0, x, y, rad);
    m.addColorStop(0, `rgba(120,85,45,${0.05 + r() * 0.07})`); m.addColorStop(1, "rgba(120,85,45,0)");
    g.fillStyle = m; g.fillRect(0, 0, S, S);
  }
  const night = r() < 0.32;               // "in tenebris": darkness above, a candle's light
  if (night) {
    const d = g.createLinearGradient(0, 0, 0, S);
    d.addColorStop(0, "rgba(22,16,12,.97)"); d.addColorStop(0.55, "rgba(30,22,16,.85)"); d.addColorStop(0.85, "rgba(60,42,25,.25)"); d.addColorStop(1, "rgba(60,42,25,0)");
    g.fillStyle = d; g.fillRect(0, 0, S, S);
  }

  // watercolour blots: many translucent, jittered layers bleed like wet pigment
  const blots = 3 + Math.floor(r() * 3);
  for (let b = 0; b < blots; b++) {
    const col = pick(), cx = S * (0.15 + r() * 0.7), cy = S * (night ? 0.45 + r() * 0.4 : 0.2 + r() * 0.6), R = S * (0.16 + r() * 0.22);
    // smooth organic outline: a few low-frequency sines, no spikes
    const harm = Array.from({ length: 4 }, (_, h) => ({ a: (0.05 + r() * 0.12) / (h + 1), f: h + 2, p: r() * 6 }));
    const radius = (t) => 1 + harm.reduce((acc, h) => acc + h.a * Math.sin(h.f * t + h.p), 0);
    const blob = (scale, dx, dy) => {
      const P = 36, pts = [];
      for (let i = 0; i < P; i++) { const t = (i / P) * Math.PI * 2, rr = R * scale * radius(t); pts.push([cx + dx + Math.cos(t) * rr * 1.25, cy + dy + Math.sin(t) * rr * 0.85]); }
      g.beginPath();
      const mid = (p, q) => [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
      let m0 = mid(pts[P - 1], pts[0]); g.moveTo(m0[0], m0[1]);
      for (let i = 0; i < P; i++) { const m = mid(pts[i], pts[(i + 1) % P]); g.quadraticCurveTo(pts[i][0], pts[i][1], m[0], m[1]); }
      g.closePath();
    };
    for (let layer = 0; layer < 16; layer++) {          // wet layers drifting slightly, like bleeding pigment
      blob(1.05 - layer * 0.035, (r() - 0.5) * R * 0.12, (r() - 0.5) * R * 0.1);
      g.fillStyle = rgba(col, 0.068); g.fill();
    }
    const bloom = g.createRadialGradient(cx, cy, 0, cx, cy, R);  // lighter centre, darker rim
    bloom.addColorStop(0, "rgba(245,235,215,.18)"); bloom.addColorStop(1, "rgba(245,235,215,0)");
    blob(0.9, 0, 0); g.fillStyle = bloom; g.fill();
    blob(1.05, 0, 0);
    g.strokeStyle = rgba(col, 0.22); g.lineWidth = 1.2 * u; g.stroke();     // pigment edge
    for (let d = 0; d < 1 + Math.floor(r() * 3); d++) {                   // drips
      const x = cx + (r() - 0.5) * R * 1.4, y0 = cy + R * 0.55, len = S * (0.08 + r() * 0.22);
      g.strokeStyle = rgba(col, 0.35); g.lineWidth = (0.8 + r() * 1.4) * u;
      g.beginPath(); g.moveTo(x, y0); g.lineTo(x + (r() - 0.5) * 2 * u, y0 + len); g.stroke();
      g.fillStyle = rgba(col, 0.4); g.beginPath(); g.arc(x, y0 + len, 1.6 * u, 0, 7); g.fill();
    }
  }

  // candle glow for night covers
  if (night) {
    const x = S * (0.3 + r() * 0.4), y = S * (0.3 + r() * 0.15);
    const glow = g.createRadialGradient(x, y, 0, x, y, S * 0.42);
    glow.addColorStop(0, "rgba(255,214,140,.75)"); glow.addColorStop(0.18, "rgba(240,162,60,.35)"); glow.addColorStop(1, "rgba(240,162,60,0)");
    g.globalCompositeOperation = "screen"; g.fillStyle = glow; g.fillRect(0, 0, S, S); g.globalCompositeOperation = "source-over";
    g.fillStyle = "rgba(255,240,200,.95)"; g.beginPath(); g.ellipse(x, y, 2.6 * u, 6 * u, 0, 0, 7); g.fill();
    for (let i = 0; i < 26; i++) { g.fillStyle = `rgba(255,${190 + r() * 50},120,${0.3 + r() * 0.6})`; g.beginPath(); g.arc(x + (r() - 0.5) * S * 0.6, y - r() * S * 0.3, r() * 1.4 * u, 0, 7); g.fill(); }
  }

  // sepia ink: a flowing music staff with a few notes
  const ink = night ? "rgba(236,214,170," : "rgba(74,52,36,";
  const amp = S * (0.04 + r() * 0.07), f = 0.6 + r() * 1.4, ph = r() * 6, y0 = S * (0.35 + r() * 0.35), tilt = (r() - 0.5) * 0.35;
  const staffY = (x, line) => y0 + line * 4.2 * u + Math.sin((x / S) * Math.PI * 2 * f + ph) * amp + (x - S / 2) * tilt;
  g.lineWidth = 0.7 * u;
  for (let line = 0; line < 5; line++) {
    g.strokeStyle = ink + "0.55)"; g.beginPath();
    for (let x = -4; x <= S + 4; x += 3) { const y = staffY(x, line) + (r() - 0.5) * 0.5 * u; x < 0 ? g.moveTo(x, y) : g.lineTo(x, y); }
    g.stroke();
  }
  const notes = 3 + Math.floor(r() * 5);
  for (let i = 0; i < notes; i++) {
    const x = S * (0.1 + r() * 0.8), y = staffY(x, Math.floor(r() * 5)) - 2 * u;
    g.fillStyle = ink + "0.75)"; g.beginPath(); g.ellipse(x, y, 2.6 * u, 1.8 * u, -0.4, 0, 7); g.fill();
    g.strokeStyle = ink + "0.7)"; g.lineWidth = 0.8 * u; g.beginPath(); g.moveTo(x + 2.3 * u, y); g.lineTo(x + 2.3 * u, y - 12 * u); g.stroke();
  }
  for (let i = 0; i < 2; i++) {          // loose ink flourishes
    g.strokeStyle = ink + "0.35)"; g.lineWidth = 0.6 * u; g.beginPath();
    let x = r() * S, y = r() * S; g.moveTo(x, y);
    for (let k2 = 0; k2 < 3; k2++) { const nx = r() * S, ny = r() * S; g.bezierCurveTo(r() * S, r() * S, r() * S, r() * S, nx, ny); }
    g.stroke();
  }

  // coffee ring + splatter
  if (r() < 0.6) {
    const x = S * (0.15 + r() * 0.7), y = S * (0.55 + r() * 0.35), rad = S * (0.06 + r() * 0.06);
    g.strokeStyle = "rgba(120,80,40,.22)"; g.lineWidth = 1.6 * u; g.beginPath(); g.arc(x, y, rad, r() * 6, r() * 6 + 5.2); g.stroke();
    const st = g.createRadialGradient(x, y, rad * 0.2, x, y, rad); st.addColorStop(0, "rgba(140,95,50,.0)"); st.addColorStop(1, "rgba(140,95,50,.08)");
    g.fillStyle = st; g.beginPath(); g.arc(x, y, rad, 0, 7); g.fill();
  }
  for (let i = 0; i < 40; i++) { g.fillStyle = rgba(pick(), 0.25 + r() * 0.4); g.beginPath(); g.arc(r() * S, r() * S, r() * 1.8 * u, 0, 7); g.fill(); }

  // burnt edges + grain
  const v = g.createRadialGradient(S / 2, S / 2, S * 0.38, S / 2, S / 2, S * 0.75);
  v.addColorStop(0, "rgba(70,45,20,0)"); v.addColorStop(1, "rgba(70,45,20,.38)");
  g.fillStyle = v; g.fillRect(0, 0, S, S);
  const img = g.getImageData(0, 0, S, S), d = img.data;
  for (let i = 0; i < d.length; i += 4) { const n = (r() - 0.5) * 14; d[i] += n; d[i + 1] += n; d[i + 2] += n; }
  g.putImageData(img, 0, 0);

  const url = c.toDataURL("image/jpeg", 0.9);
  coverCache.set(k, url);
  return url;
}

/* ---------- waveform ---------- */

function drawWave(canvas, peaks, progress = 0, opts = {}) {
  if (!canvas || !peaks || !peaks.length) return;
  const dpr = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w) return;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const g = canvas.getContext("2d"); g.scale(dpr, dpr);
  const gap = opts.gap ?? 2, bar = opts.bar ?? 2, n = Math.max(1, Math.floor(w / (bar + gap)));
  const grad = g.createLinearGradient(0, 0, w, 0);
  grad.addColorStop(0, "#caa26a"); grad.addColorStop(0.55, "#f0a23c"); grad.addColorStop(1, "#ff6b35");
  for (let i = 0; i < n; i++) {
    const p = peaks[Math.floor((i / n) * peaks.length)] || 0;
    const bh = Math.max(2, p * h * 0.95), x = i * (bar + gap), y = (h - bh) / 2;
    g.fillStyle = i / n < progress ? grad : (opts.dim || "rgba(236,230,220,.2)");
    g.beginPath(); g.roundRect ? g.roundRect(x, y, bar, bh, bar / 2) : g.rect(x, y, bar, bh); g.fill();
  }
}

/* ---------- create form ---------- */

function setupForm() {
  $("section-tags").innerHTML = SECTIONS.map((s) => `<button type="button" data-s="${s}">[${s}]</button>`).join("");
  $("section-tags").onclick = (e) => {
    const s = e.target.dataset.s; if (!s) return;
    const ta = $("lyrics"), pos = ta.selectionStart, before = ta.value.slice(0, pos);
    const ins = (before && !before.endsWith("\n\n") ? (before.endsWith("\n") ? "\n" : "\n\n") : "") + `[${s}]\n`;
    ta.setRangeText(ins, pos, ta.selectionEnd, "end"); ta.focus(); updateLyricsCount();
  };
  $("lyrics").oninput = updateLyricsCount; updateLyricsCount();
  $("instrumental").onchange = () => {
    // YuE2 mutes the vocal line of a planned score; Direct has no score to mute.
    if ($("instrumental").checked && state.cot === "off") { state.cot = "full"; setSegmented("cot", "full"); }
    updateLyricsCount();
  };

  $("chips").innerHTML = Object.entries(CHIPS).map(([g, list]) =>
    `<div class="chip-group"><span class="gname">${g}</span>${list.map((c) => `<button type="button" class="chip" data-c="${esc(c)}">${esc(c)}</button>`).join("")}</div>`).join("");
  $("chips").onclick = (e) => { const c = e.target.dataset.c; if (c) toggleStyleTag(c); };
  $("style").oninput = syncChips; syncChips();
  $("style-clear").onclick = () => { window.Vibe?.clearCreateReference(); $("style").value = "English, "; syncChips(); $("style").focus(); };

  segmented("cot", (v) => {
    state.cot = v;
    updateSongLengthUI();
  });
  segmented("variations", (v) => { state.variations = Number(v); updateGoLabel(); });

  $("seed-random").onchange = () => { $("seed").disabled = $("seed-random").checked; };
  $("dice").onclick = () => { $("seed").value = Math.floor(Math.random() * 2 ** 31); };

  $("sliders").innerHTML = SLIDERS.map((s) => `
    <div class="slider"><div class="label-row"><label for="${s.id}">${s.label}</label><span class="value default" id="${s.id}-v">${s.defLabel || s.def}</span></div>
    <input type="range" id="${s.id}" min="${s.min}" max="${s.max}" step="${s.step}" value="${s.def ?? s.min}"></div>`).join("");
  for (const s of SLIDERS) {
    const el = $(s.id); paintRange(el);
    el.oninput = () => { state.adv[s.id] = Number(el.value); $(`${s.id}-v`).textContent = el.value; $(`${s.id}-v`).classList.remove("default"); paintRange(el); };
  }
  $("adv-reset").onclick = (e) => { e.preventDefault(); resetAdvanced(); };

  $("form").onsubmit = submit;
  updateGoLabel();
}

function segmented(id, onChange) {
  $(id).onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    for (const x of $(id).children) x.classList.toggle("on", x === b);
    onChange(b.dataset.v);
  };
}
function setSegmented(id, v) { for (const x of $(id).children) x.classList.toggle("on", x.dataset.v === String(v)); }
function paintRange(el) { el.style.setProperty("--p", `${((el.value - el.min) / (el.max - el.min)) * 100}%`); }
function updateLyricsCount() {
  const instrumental = $("instrumental").checked;
  $("lyrics").hidden = $("section-tags").hidden = $("lyrics-count").hidden = $("lyrics-writer").hidden = instrumental;
  if (instrumental) { $("lyrics-advice").textContent = "No vocals: the lyrics are not used and the planned score's vocal line is muted. Describe instruments in the style and leave out vocal tags."; return; }
  const v = $("lyrics").value, lines = v.split("\n").filter((l) => l.trim() && !/^\[.*\]$/.test(l.trim())).length;
  $("lyrics-count").textContent = `${lines} lines · ${v.length} chars`;
  const words = v.replace(/^\[.*\]$/gm, "").trim().split(/\s+/).filter(Boolean).length;
  $("lyrics-advice").textContent = words ? `${words} words. ${/\[outro(?:\s*\||\])/i.test(v) ? "" : "For a clear ending, add a final section and a closing lyric phrase."}` : "";
}
function updateSongLengthUI() {
  const cap = Settings.capability(), supported = Boolean(cap.duration_analysis);
  $("duration-hint").closest(".field").hidden = !supported;
  if (supported) {
    $("duration-hint").textContent = "Lux analyzes your lyrics, style and tempo when you click Create, then chooses a song length and prepares the arrangement before generating audio. Planning takes extra model processing time. The final performance may be shorter or vary from the plan. If the model cannot fit a complete arrangement, Lux explains what to shorten.";
  }
}
function styleTags() { return $("style").value.split(",").map((t) => t.trim()).filter(Boolean); }
function toggleStyleTag(tag) {
  const tags = styleTags(), i = tags.findIndex((t) => t.toLowerCase() === tag.toLowerCase());
  if (i >= 0) tags.splice(i, 1); else tags.push(tag);
  $("style").value = tags.join(", "); syncChips();
}
function syncChips() {
  const set = new Set(styleTags().map((t) => t.toLowerCase()));
  for (const c of document.querySelectorAll(".chip")) c.classList.toggle("on", set.has(c.dataset.c.toLowerCase()));
  for (const button of document.querySelectorAll("[data-template]")) {
    const selected = GENRE_TEMPLATES.find((template) => template.id === button.dataset.template)?.style === $("style").value;
    button.setAttribute("aria-pressed", String(selected));
  }
  $("template-status").textContent = "";
}
function resetSlider(s) {
  delete state.adv[s.id];
  const el = $(s.id); el.value = s.def ?? s.min; paintRange(el); const v = $(`${s.id}-v`); v.textContent = s.defLabel || s.def; v.classList.add("default");
}
function resetAdvanced() {
  state.adv = {};
  for (const s of SLIDERS) resetSlider(s);
  $("abc").value = "";
}
function updateGoLabel() { $("go-label").textContent = state.variations > 1 ? `Create ${state.variations} variations` : "Create"; }

function songInputs() {
  return {
    title: $("title").value.trim() || undefined, lyrics: $("lyrics").value, style: $("style").value,
    instrumental: Settings.capability().instrumental && $("instrumental").checked || undefined,
    model_options: Settings.options(),
  };
}

async function submit(e) {
  e.preventDefault();
  if (!Settings.ready()) { location.hash = "#/settings"; return; }
  $("form-error").textContent = "";
  const base = songInputs();
  const random = $("seed-random").checked, seed0 = Number($("seed").value);
  state.submitting = true;
  $("go").disabled = true;
  try {
    const vibeReference = await window.Vibe?.generationReference() || {};
    const seed = random ? Math.floor(Math.random() * 2 ** 31) : seed0;
    const r = await fetch("/api/generate", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...base, ...vibeReference, seed, variations: state.variations }) });
    if (!r.ok) {
      const d = (await r.json()).detail;
      $("form-error").textContent = Array.isArray(d) ? d.map((x) => `${x.loc.slice(1).join(".") || "request"}: ${x.msg}`).join("\n") : String(d);
    } else if (vibeReference.vibe_images) window.Vibe?.consumeCreateReference();
  } catch (error) { $("form-error").textContent = "The studio could not be reached. Check that it is running and try again."; }
  finally { state.submitting = false; }
  pollJobs();
}

function loadIntoForm(p) {
  window.Vibe?.clearCreateReference();
  p = { ...p, ...(p.model_options || {}) };
  $("title").value = p.title || "";
  $("instrumental").checked = Boolean(p.instrumental);
  if (!p.instrumental) $("lyrics").value = p.lyrics || "";
  updateLyricsCount();
  $("style").value = p.style || ""; syncChips();
  state.cot = p.cot || "off"; setSegmented("cot", state.cot);
  updateSongLengthUI();
  $("seed-random").checked = false; $("seed").disabled = false; $("seed").value = p.seed ?? 1234;
  resetAdvanced();
  for (const s of SLIDERS) if (p[s.id] != null) { const el = $(s.id); el.value = p[s.id]; el.oninput(); }
  $("abc").value = p.abc || "";
  document.querySelector(".create").scrollTo({ top: 0, behavior: "smooth" });
  $("title").focus();
}

/* ---------- list rendering ---------- */

function tagsHtml(style) { return style.split(",").map((t) => t.trim()).filter(Boolean).map((t) => `<span>${esc(t)}</span>`).join(""); }
function cotBadge(cot) { return cot === "off" ? "" : `<span class="badge grad">${cot === "full" ? "score" : "melody"}</span>`; }
function endingBadge(song) {
  const status = song.generation?.status || (String(song.artifact_meta?.semantic?.truncated) === "true" ? "truncated" : "unknown");
  const g = song.generation || {};
  const shorter = g.shorter_than_target ? `<span class="badge">Shorter than target · ${fmt(song.duration_s)} of ${fmt(g.target_duration_s)}</span>` : "";
  return shorter + (status === "truncated" ? '<span class="badge">Unfinished · limit reached</span>' : status === "model_end" ? '<span class="badge">Model ended</span>' : "");
}

function render() {
  const q = $("search").value.trim().toLowerCase();
  const rank = { running: 0, queued: 1, error: 2 };
  const active = state.jobs.filter((j) => !["done", "cancelled"].includes(j.status) && (j.kind || "generate") === "generate")
    .sort((a, b) => rank[a.status] - rank[b.status] || a.created - b.created);
  const songs = state.library.filter((s) => !q || [s.title, s.params.style, s.params.lyrics].join(" ").toLowerCase().includes(q));
  $("lib-count").textContent = state.library.length;

  if (!active.length && !songs.length) {
    $("list").innerHTML = q ? `<div class="empty"><h3>No matches</h3>Try another search.</div>` :
      `<div class="empty"><div class="big"><svg viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg></div>
       <h3>Your first song is one click away</h3>Write some lyrics, pick a style, hit Create.</div>`;
    return;
  }
  const jobRows = active.map((j) => {
    const title = esc(j.params.title || "Untitled");
    if (j.status === "error") return `
      <div class="song err" data-job="${j.id}">
        <div class="cover"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h0"/></svg></div>
        <div class="s-main"><div class="s-title">${title}</div><div class="s-sub" title="${esc(j.error)}">Failed: ${esc(j.error)}</div></div>
        <div class="s-actions" style="opacity:1"><button class="icon-btn" data-act="dismiss" title="Dismiss"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
      </div>`;
    const running = j.status === "running";
    return `
      <div class="song gen ${running ? "" : "queued"}" data-job="${j.id}">
        <div class="cover">${running ? '<div class="eq"><i></i><i></i><i></i><i></i></div>' : ""}</div>
        <div class="s-main"><div class="s-title">${title}${cotBadge(j.params.cot)}</div>
          <div class="s-tags">${tagsHtml(j.params.style)}</div>
          <div class="s-sub ${running ? "shimmer" : ""}" data-elapsed>${running ? esc(j.stage || "Generating…") : "Waiting in queue"}</div>
          <div class="progress"><i data-bar style="width:0"></i></div></div>
        <div class="s-actions" style="opacity:1"><button class="icon-btn" data-act="cancel" title="${running ? "Stop generation" : "Remove from queue"}"><svg viewBox="0 0 24 24"><rect x="7" y="7" width="10" height="10" rx="1"/></svg></button></div>
      </div>`;
  }).join("");
  const songRows = songs.map((s) => `
    <div class="song ${state.current?.name === s.name ? "playing" : ""}" data-name="${esc(s.name)}">
      <div class="cover"><img src="${songCover(s, 128)}" alt=""><div class="ov"><svg viewBox="0 0 24 24">${state.current?.name === s.name && !audio.paused ? ICON.pause : ICON.play}</svg></div><span class="dur">${fmt(s.duration_s)}</span></div>
      <div class="s-main"><div class="s-title">${esc(s.title)}${s.vibe ? `<span class="badge">Vibe · ${vibeImageCount(s) > 1 ? `${vibeImageCount(s)} images` : "Image inspired"}</span>` : ""}${cotBadge(s.params.cot)}${endingBadge(s)}${s.edit ? `<span class="badge">edit ${fmt(s.edit.start_s)}–${fmt(s.edit.end_s)}</span>` : ""}</div>
        <div class="s-tags">${tagsHtml(s.params.style)}</div>
        <div class="s-sub">seed ${s.params.seed} · made in ${fmt(s.elapsed_s)} · ${esc((s.created || "").replace("T", " ").slice(0, 16))}</div></div>
      <canvas class="mini-wave"></canvas>
      <div class="s-actions">
        <button class="icon-btn lux-btn" data-act="lux" title="Open in Studio Mode"><svg viewBox="0 0 24 24"><path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/></svg></button>
        <button class="icon-btn" data-act="reuse" title="Reuse settings"><svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 0114-5.3L20 9M20 4v5h-5M20 12a8 8 0 01-14 5.3L4 15M4 20v-5h5"/></svg></button>
        <a class="icon-btn" href="/outputs/${encodeURIComponent(s.name)}.wav" download title="Download WAV"><svg viewBox="0 0 24 24"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg></a>
        <button class="icon-btn" data-act="info" title="Details"><svg viewBox="0 0 24 24"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></svg></button>
      </div>
    </div>`).join("");
  $("list").innerHTML = jobRows + songRows;
  drawMiniWaves();
  tickJobs();
}

function drawMiniWaves() {
  for (const row of document.querySelectorAll(".song[data-name]")) {
    const s = state.library.find((x) => x.name === row.dataset.name);
    const prog = state.current?.name === s.name && audio.duration ? audio.currentTime / audio.duration : 0;
    drawWave(row.querySelector(".mini-wave"), s.peaks, prog, { bar: 2, gap: 2, dim: "rgba(236,230,220,.14)" });
  }
}

$("list").onclick = async (e) => {
  const row = e.target.closest(".song"); if (!row) return;
  const act = e.target.closest("[data-act]")?.dataset.act;
  if (row.dataset.job) {
    if (act === "dismiss") { await fetch(`/api/jobs/${row.dataset.job}`, { method: "DELETE" }); pollJobs(); }
    if (act === "cancel") { await fetch(`/api/jobs/${row.dataset.job}/cancel`, { method: "POST" }); pollJobs(); }
    return;
  }
  if (e.target.closest("a")) return;
  const s = state.library.find((x) => x.name === row.dataset.name);
  if (act === "reuse") return loadIntoForm(s.params);
  if (act === "lux") return Lux.open(s.name);
  if (act === "info") return openDrawer(s);
  togglePlay(s);
};
$("search").oninput = render;


/* ---------- jobs polling ---------- */

let pollTimer;
async function pollJobs() {
  clearTimeout(pollTimer);
  try {
    const jobs = await (await fetch("/api/jobs")).json();
    const doneBefore = state.jobs.filter((j) => j.status === "done" && j.kind !== "separate").length;
    const songsBefore = state.jobs.reduce((n, j) => n + (j.completed_variations || 0), 0);
    const changed = JSON.stringify(jobs.map((j) => [j.id, j.status])) !== JSON.stringify(state.jobs.map((j) => [j.id, j.status]));
    state.jobs = jobs; state.jobsAt = Date.now();
    if (window.Lux) Lux.onJobs(jobs);
    if (jobs.filter((j) => j.status === "done" && j.kind !== "separate").length !== doneBefore ||
        jobs.reduce((n, j) => n + (j.completed_variations || 0), 0) !== songsBefore) await loadLibrary(true);
    else if (changed) render();
  } catch { /* studio restarting */ }
  const busy = state.jobs.some((j) => j.status === "running" || j.status === "queued");
  pollTimer = setTimeout(pollJobs, busy ? 1000 : 4000);
}
function tickJobs() {
  for (const j of state.jobs) {
    if (j.status !== "running") continue;
    const row = document.querySelector(`.song[data-job="${j.id}"]`); if (!row) continue;
    const elapsed = j.now - j.started + (Date.now() - state.jobsAt) / 1000;
    const pct = Math.min(0.96, elapsed / j.eta_s);
    row.querySelector("[data-bar]").style.width = `${pct * 100}%`;
    row.querySelector("[data-elapsed]").textContent = `${j.stage || "Generating…"} ${fmt(elapsed)} / ~${fmt(j.eta_s)}`;
  }
}
setInterval(tickJobs, 250);

async function loadLibrary(autoplayNewest = false) {
  const before = new Set(state.library.map((s) => s.name));
  state.library = await (await fetch("/api/library")).json();
  render();
  if (window.Lux) Lux.onLibrary();
  const fresh = state.library.find((s) => !before.has(s.name));
  if (autoplayNewest && fresh && before.size && audio.paused) { flash(fresh.name); }
}
function flash(name) {
  const row = document.querySelector(`.song[data-name="${CSS.escape(name)}"]`);
  if (row) { row.animate([{ background: "rgba(240,162,60,.25)" }, { background: "transparent" }], { duration: 1600 }); }
}

/* ---------- player ---------- */

function setTrack(s) {
  VibePlayer.reset();
  state.current = s;
  audio.src = `/outputs/${encodeURIComponent(s.name)}.wav`;
  $("p-cover").src = songCover(s, 128);
  $("p-artwork").disabled = !s.artifacts?.vibe_image;
  $("p-title").textContent = s.title;
  $("p-style").textContent = s.params.style;
  $("p-dl").href = audio.src;
  $("p-dur").textContent = fmt(s.duration_s);
  document.title = `${s.title} · Lux In Music`;
}
function togglePlay(s) {
  if (s && state.current?.name !== s.name) { setTrack(s); audio.play(); }
  else if (state.current) { audio.paused ? audio.play() : audio.pause(); }
  else if (state.library[0]) { setTrack(state.library[0]); audio.play(); }
}
function step(dir) {
  if (!state.library.length) return;
  const i = state.library.findIndex((x) => x.name === state.current?.name);
  const n = state.library[(i + dir + state.library.length) % state.library.length];
  setTrack(n); audio.play();
}
function syncPlayIcons() {
  $("p-play-icon").innerHTML = audio.paused ? ICON.play : ICON.pause;
  for (const row of document.querySelectorAll(".song[data-name]")) {
    const on = state.current?.name === row.dataset.name;
    row.classList.toggle("playing", on);
    row.querySelector(".ov svg").innerHTML = on && !audio.paused ? ICON.pause : ICON.play;
  }
  const dp = document.querySelector("#drawer [data-act=dplay] svg");
  if (dp) dp.innerHTML = state.drawerSong?.name === state.current?.name && !audio.paused ? ICON.pause : ICON.play;
}
function drawPlayer() {
  const prog = audio.duration ? audio.currentTime / audio.duration : 0;
  drawWave($("p-wave"), state.current?.peaks, prog, { bar: 3, gap: 2 });
  $("p-cur").textContent = fmt(audio.currentTime);
  const row = state.current && document.querySelector(`.song[data-name="${CSS.escape(state.current.name)}"] .mini-wave`);
  if (row) drawWave(row, state.current.peaks, prog, { bar: 2, gap: 2, dim: "rgba(236,230,220,.14)" });
}
audio.addEventListener("play", () => { syncPlayIcons(); if (window.Lux) Lux.pause(); VibePlayer.onPlay(); });
audio.addEventListener("pause", () => { syncPlayIcons(); VibePlayer.onPause(); });
audio.addEventListener("timeupdate", drawPlayer);
audio.addEventListener("loadedmetadata", () => { $("p-dur").textContent = fmt(audio.duration); drawPlayer(); });
audio.addEventListener("ended", () => step(1));
$("p-play").onclick = () => togglePlay();
$("p-prev").onclick = () => step(-1);
$("p-next").onclick = () => step(1);
$("p-vol").oninput = (e) => { audio.volume = e.target.value; paintRange(e.target); };
audio.volume = 0.9; paintRange($("p-vol"));
$("p-wave").onclick = (e) => {
  if (!audio.duration) return;
  const r = e.currentTarget.getBoundingClientRect();
  audio.currentTime = ((e.clientX - r.left) / r.width) * audio.duration;
};
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && VibePlayer.visible()) { e.preventDefault(); VibePlayer.close(); return; }
  if (e.target.matches("input, textarea, select, button, a, [contenteditable]")) return;
  if (e.code === "Space") { e.preventDefault(); if (window.Lux && Lux.visible()) Lux.toggle(); else togglePlay(); }
  if (e.key === "Escape") closeDrawer();
  if (e.key === "ArrowRight" && audio.duration) audio.currentTime += 5;
  if (e.key === "ArrowLeft" && audio.duration) audio.currentTime -= 5;
});
window.addEventListener("resize", () => { drawPlayer(); drawMiniWaves(); });

const VibePlayer = (() => {
  const view = $("vibe-listening"), reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const layers = [$("vibe-listening-image"), $("vibe-listening-image-next")];
  const backdrops = [$("vibe-listening-backdrop"), $("vibe-listening-backdrop-next")];
  let dismissed = null, shown = null, hideTimer = null, slideTimer = null, focusBefore = null;
  let gallery = [], index = 0, activeLayer = 0, sequence = 0, paused = false;
  function controls() {
    $("vibe-carousel-controls").hidden = gallery.length < 2;
    $("vibe-slide-count").textContent = `${index + 1} / ${gallery.length}`;
    $("vibe-slide-count").setAttribute("aria-live", paused || audio.paused ? "polite" : "off");
    $("vibe-slide-pause").textContent = reduced.matches ? "Manual slideshow" : paused ? "Resume slideshow" : "Pause slideshow";
    $("vibe-slide-pause").disabled = reduced.matches;
  }
  function schedule() {
    clearTimeout(slideTimer);
    controls();
    if (shown && shown.name === state.current?.name && gallery.length > 1 && !paused && !audio.paused && !reduced.matches && !document.hidden) {
      slideTimer = setTimeout(() => advance(1), 8000);
    }
  }
  function close(restoreFocus = true, immediate = false) {
    dismissed = shown?.name || dismissed;
    shown = null; sequence++;
    window.VibeEffects?.hide();
    view.classList.remove("open");
    clearTimeout(hideTimer); clearTimeout(slideTimer);
    if (immediate) view.hidden = true;
    else hideTimer = setTimeout(() => { view.hidden = true; }, 500);
    if (restoreFocus && focusBefore?.isConnected) focusBefore.focus({ preventScroll: true });
  }
  async function slide(next, first = false) {
    clearTimeout(slideTimer);
    const request = ++sequence, song = shown, layer = first ? 0 : 1 - activeLayer;
    const image = layers[layer], backdrop = backdrops[layer];
    image.src = gallery[next]; backdrop.src = gallery[next];
    image.alt = `Vibe inspiration image ${next + 1} of ${gallery.length}`;
    try {
      await Promise.all([image.decode(), backdrop.decode()]);
      if (!song || shown !== song || request !== sequence) return;
      index = next; activeLayer = layer;
      layers.forEach((el, i) => { el.classList.toggle("active", i === layer); el.setAttribute("aria-hidden", String(i !== layer)); });
      backdrops.forEach((el, i) => el.classList.toggle("active", i === layer));
      controls();
      if (first) requestAnimationFrame(() => requestAnimationFrame(() => {
        if (shown === song && request === sequence) {
          view.classList.add("open"); $("vibe-listening-close").focus({ preventScroll: true }); schedule();
          window.VibeEffects?.show();
        }
      }));
      else schedule();
    } catch {
      if (shown === song && request === sequence) {
        if (first) close(false, true);
        else $("vibe-slide-count").textContent = "Image unavailable. Try the next image.";
      }
    }
  }
  function advance(direction) {
    if (shown && gallery.length > 1) slide((index + direction + gallery.length) % gallery.length);
  }
  function open(song) {
    if (!song?.vibe || !song.artifacts?.vibe_image) return;
    if (shown?.name === song.name && !view.hidden) { schedule(); window.VibeEffects?.show(); return; }
    clearTimeout(hideTimer); clearTimeout(slideTimer);
    focusBefore = document.activeElement === document.body ? $("p-artwork") : document.activeElement;
    shown = song; paused = false;
    gallery = song.vibe.images?.length ? song.vibe.images.map(image => `/outputs/${encodeURIComponent(image.file)}`) : [songCover(song)];
    $("vibe-listening-title").textContent = song.title;
    $("vibe-listening-subtitle").textContent = gallery.length > 1 ? `Inspired by ${gallery.length} Vibe images` : "Inspired by your Vibe image";
    view.hidden = false;
    layers.forEach(el => el.classList.remove("active"));
    backdrops.forEach(el => el.classList.remove("active"));
    slide(0, true);
  }
  $("vibe-listening-close").onclick = () => close();
  $("p-artwork").onclick = () => open(state.current);
  $("vibe-slide-prev").onclick = () => advance(-1);
  $("vibe-slide-next").onclick = () => advance(1);
  $("vibe-slide-pause").onclick = () => { paused = !paused; schedule(); };
  reduced.addEventListener("change", schedule);
  document.addEventListener("visibilitychange", schedule);
  window.addEventListener("hashchange", () => close(false));
  return { open, close, visible: () => !view.hidden,
    reset: () => { close(false, true); dismissed = null; },
    onPause: () => { clearTimeout(slideTimer); controls(); },
    onPlay: () => { if (state.current?.name !== dismissed) open(state.current); } };
})();

/* ---------- drawer ---------- */

async function openDrawer(s) {
  state.drawerSong = s;
  const p = s.params;
  const lyr = esc(p.lyrics).replace(/^\[(.+?)\]$/gm, "<b>[$1]</b>");
  let abc = "";
  if (s.artifacts?.score) {
    try { abc = await (await fetch(`/outputs/${encodeURIComponent(s.artifacts.score)}`)).text(); } catch { abc = ""; }
  }
  const kv = [["Length", fmt(s.duration_s)], ["Planned length", p.target_duration_s ? fmt(p.target_duration_s) : "—"], ["Model cap", p.max_duration_s ? fmt(p.max_duration_s) : "—"], ["Planning", p.cot], ["Seed", p.seed], ["Made in", fmt(s.elapsed_s)],
    ["Sample rate", `${s.sample_rate / 1000} kHz · ${s.channels === 2 ? "stereo" : "mono"}`], ["Created", (s.created || "").replace("T", " ").slice(0, 16)],
    ...SLIDERS.filter((x) => p[x.id] != null).map((x) => [x.label, p[x.id]])];
  $("drawer").innerHTML = `
    <div class="d-hero"><img src="${songCover(s, 512)}" alt=""><button class="icon-btn d-close" data-act="close"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
    <div class="d-body">
      <div><h2 class="d-title">${esc(s.title)}</h2><div class="d-style">${esc(p.style)}</div></div>
      ${s.generation?.message ? `<p class="hint">${esc(s.generation.message)}</p>` : endingBadge(s)}
      ${s.vibe ? `<div class="d-sec"><h4>Image inspiration · Lux Vibe</h4><p class="hint">${vibeImageCount(s) > 1 ? `${vibeImageCount(s)} images inspired this song’s musical direction. They are saved locally with its composite cover and listening gallery.` : "This song’s musical direction was inspired by an image. The image is saved locally as its cover."}</p><button class="btn" data-act="dimage">${vibeImageCount(s) > 1 ? "View inspiration gallery" : "View inspiration image"}</button></div>` : ""}
      <div class="d-actions">
        <button class="btn primary" data-act="dplay"><svg viewBox="0 0 24 24">${ICON.play}</svg>Play</button>
        <button class="btn lux-cta" data-act="dlux"><svg viewBox="0 0 24 24"><path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/></svg>Open in Studio Mode</button>
        <button class="btn" data-act="dreuse"><svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 0114-5.3L20 9M20 4v5h-5"/></svg>Reuse settings</button>
        <a class="btn" href="/outputs/${encodeURIComponent(s.name)}.wav" download><svg viewBox="0 0 24 24"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>WAV</a>
        ${["flac", "mp3"].map((f) => `<a class="btn" href="/api/export/${encodeURIComponent(s.name)}?format=${f}" download><svg viewBox="0 0 24 24"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>${f.toUpperCase()}</a>`).join("")}
        ${s.artifacts?.score ? `<a class="btn" href="/outputs/${encodeURIComponent(s.artifacts.score)}" download><svg viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/></svg>Score</a>` : ""}
        <button class="btn danger" data-act="ddelete"><svg viewBox="0 0 24 24"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/></svg>Delete</button>
      </div>
      <p class="error" id="d-error" role="alert"></p>
      ${p.instrumental ? '<div class="d-sec"><h4>Lyrics</h4><p class="hint">Instrumental · no vocals requested</p></div>' : p.lyrics?.trim() ? `<div class="d-sec"><h4>Lyrics</h4><div class="d-lyrics">${lyr}</div></div>` : ""}
      <div class="d-sec"><h4>Generation</h4><div class="kv">${kv.map(([k, v]) => `<div><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("")}</div></div>
      ${abc ? `<div class="d-sec"><h4>Generated score (ABC)</h4><pre class="abc">${esc(abc)}</pre></div>` : ""}
    </div>`;
  $("drawer").classList.add("open"); $("drawer-bg").classList.add("open");
  syncPlayIcons();
}
function closeDrawer() { $("drawer").classList.remove("open"); $("drawer-bg").classList.remove("open"); }
$("drawer-bg").onclick = closeDrawer;
$("drawer").onclick = (e) => {
  const act = e.target.closest("[data-act]")?.dataset.act, s = state.drawerSong;
  if (act === "close") closeDrawer();
  if (act === "dplay") togglePlay(s);
  if (act === "dimage") VibePlayer.open(s);
  if (act === "dreuse") { closeDrawer(); loadIntoForm(s.params); }
  if (act === "dlux") { closeDrawer(); Lux.open(s.name); }
  if (act === "ddelete") deleteSong(s);
};
async function deleteSong(s) {
  if (!confirm(`Delete "${s.title}"? This removes its audio, score and stems. It cannot be undone.`)) return;
  const r = await fetch(`/api/songs/${encodeURIComponent(s.name)}`, { method: "DELETE" });
  if (!r.ok) { $("d-error").textContent = (await r.json().catch(() => ({}))).detail || "Could not delete this song."; return; }
  if (state.current?.name === s.name) {
    VibePlayer.reset();
    $("p-artwork").disabled = true;
    $("p-cover").removeAttribute("src");
    audio.pause(); audio.removeAttribute("src"); state.current = null;
    $("p-title").textContent = "Nothing playing"; $("p-style").textContent = ""; $("p-dl").removeAttribute("href");
  }
  closeDrawer(); await loadLibrary();
}

/* ---------- engine health ---------- */

async function health() {
  try {
    const h = await (await fetch("/api/health")).json();
    $("engine").className = `engine ${h.engine === "ok" ? "ok" : "down"}`;
    $("engine-text").textContent = h.engine === "ok" ? `Model ready · ${h.backend}` : "Model setup needed";
    $("engine").title = h.engine === "ok" ? "The selected model is verified; its runtime starts when needed" : "Open Settings to choose a model";
  } catch { $("engine").className = "engine down"; $("engine-text").textContent = "Studio offline"; }
}

/* ---------- boot ---------- */

setupForm();
setupDemos();
setupGenreTemplates();
loadLibrary();
pollJobs();
health(); setInterval(health, 8000);
Settings.setup();
