"use strict";
/* Studio Mode: stem separation + multitrack mixer (Web Audio). Uses helpers from app.js. */

const STEM_COLORS = {   // watercolour pigments, after the Lux In Tenebris illustrations
  vocals: "#f0a23c", drums: "#d9653b", bass: "#6b8fc4", other: "#a888b8", guitar: "#93b47f",
  piano: "#6fb0ac", instrumental: "#caa26a", target: "#f0a23c", residual: "#8a8174",
};
const STEM_ICONS = {
  vocals: '<path d="M12 3a3 3 0 013 3v6a3 3 0 01-6 0V6a3 3 0 013-3z"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>',
  drums: '<ellipse cx="12" cy="8" rx="8" ry="3"/><path d="M4 8v8c0 1.7 3.6 3 8 3s8-1.3 8-3V8"/>',
  bass: '<path d="M14 4l6 6M17 7l-9 9a3 3 0 11-4-4l9-9"/>',
  guitar: '<path d="M14 4l6 6M17 7l-6 6"/><circle cx="8" cy="16" r="4"/>',
  piano: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 5v8M12 5v8M16 5v8"/>',
  other: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  instrumental: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  target: '<path d="M12 3l1.9 5.8L20 10l-5 3.9L16.5 20 12 16.6 7.5 20 9 13.9 4 10l6.1-1.2z"/>',
  residual: '<circle cx="12" cy="12" r="8"/><path d="M8 12h8"/>',
};
const MODE_INFO = {
  vocals: { title: "Vocals & Instrumental", desc: "Clean a cappella and karaoke backing track.", model: "BS-RoFormer · Apache-2.0", stems: ["vocals", "instrumental"] },
  "4stems": { title: "4 Stems", desc: "The classic split for remixing.", model: "HTDemucs · MIT", stems: ["vocals", "drums", "bass", "other"] },
  "6stems": { title: "6 Stems", desc: "Adds dedicated guitar and piano tracks.", model: "HTDemucs 6s · MIT", stems: ["vocals", "drums", "bass", "guitar", "piano", "other"] },
  // Retain labels for previously saved stem sets; no longer offered for new work.
  anything: { title: "Anything", desc: "Describe a sound and pull it out.", model: "SAM Audio · Meta SAM License", stems: ["target", "residual"], retired: true },
};
const PROMPT_IDEAS = ["lead vocal", "backing vocals", "acoustic guitar", "kick drum", "snare", "hi-hat", "piano", "synth lead", "bass guitar", "hand claps", "strings", "reverb tail"];

const Lux = (() => {
  const el = () => document.getElementById("lux");
  const L = {
    song: null, sets: [], set: null, view: "pick", mode: "4stems", prompt: "",
    ctx: null, buffers: {}, tracks: [], playing: false, startAt: 0, offset: 0, duration: 0,
    loadingSet: null, raf: 0, master: null,
    laneSel: null, mixStopAt: null, stemTakes: 1,
    armed: null,        // index of the track in edit mode (set only by its Edit button)
    beats: null,        // {bpm, offset_s, beat_s, beats_per_bar} of the current song
    snap: true,         // snap edit selections to the beat grid
    variation: "new",   // "new" = write the selection anew, "same" = same notes, new performance
    direction: "",
    listen: "solo",     // Play selection: "solo" = only the armed stem, "mix" = full mix
    audition: null,     // while auditioning solo, index of the only audible track
  };

  /* ---------- routing ---------- */

  function visible() { return document.body.classList.contains("lux-mode"); }
  function show(on) {
    hideTakeHelp();
    document.body.classList.toggle("lux-mode", on);
    document.getElementById("nav-create").classList.toggle("active", !on);
    document.getElementById("nav-lux").classList.toggle("active", on);
    if (["#/settings", "#/vibe", "#/hook"].includes(location.hash)) document.getElementById("nav-create").classList.remove("active");
    if (location.hash === "#/vibe") document.getElementById("nav-lux").classList.remove("active");
    if (!on) pause();
  }
  async function open(name) {
    if (L.song?.name !== name) L.direction = "";
    if (location.hash !== `#/lux/${name}`) {
      history.pushState(null, "", `#/lux/${encodeURIComponent(name)}`);
      // pushState does not emit hashchange; retire the other views explicitly.
      Settings.route(); window.Vibe?.route(); window.Hook?.route();
    }
    await route();
  }
  async function route() {
    const m = location.hash.match(/^#\/lux(?:\/(.+))?$/);
    if (!m) return show(false);
    show(true);
    const name = m[1] ? decodeURIComponent(m[1]) : null;
    if (!name) { L.song = null; stopAudio(); return renderPicker(); }  // re-rendered by onLibrary()
    if (L.song?.name !== name) {
      stopAudio(); L.set = null; L.buffers = {}; L.laneSel = null; L.armed = null; L.audition = null; L.beats = null;
      if (!state.library.length) await loadLibrary();
      L.song = state.library.find((s) => s.name === name) || null;
      if (!L.song) return renderPicker();
      await refreshSets();
      fetch(`/api/beats/${encodeURIComponent(name)}`).then((r) => r.ok ? r.json() : null).then((b) => { L.beats = b; drawLanes(); renderEditBar(); }).catch(() => {});
      L.view = L.sets.length ? "mix" : "pick";
      if (L.sets.length) await selectSet(L.sets[0]);
    }
    render();
  }
  window.addEventListener("popstate", route);
  window.addEventListener("hashchange", route);

  async function refreshSets() {
    L.sets = await (await fetch(`/api/lux/${encodeURIComponent(L.song.name)}`)).json();
  }

  /* ---------- views ---------- */

  function render() {
    hideTakeHelp();
    if (!L.song) return renderPicker();
    const job = activeJob();
    if (job) return renderProcessing(job);
    if (L.view === "pick" || !L.set) return renderModes();
    renderMixer();
  }

  function header(extra = "") {
    const s = L.song;
    return `
      <div class="lx-head">
        <button class="icon-btn" data-lx="back" title="All songs"><svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg></button>
        <img class="lx-cover" src="${songCover(s, 160)}" alt="">
        <div class="lx-title"><div class="lx-kicker">Studio Mode</div><h1>${esc(s.title)}</h1>
          <div class="lx-sub">${esc(s.params.style)}</div></div>
        <div class="lx-head-actions">${extra}</div>
      </div>`;
  }

  function renderPicker() {
    const songs = state.library;
    el().innerHTML = `
      <div class="lx-hero">
        <div class="lx-orb"></div>
        <div class="lx-kicker">Studio Mode</div>
        <h1>Pull any song <span class="lux-word">apart.</span></h1>
        <p>Pick a track from your library, choose what to isolate, then remix it with the multitrack mixer. Everything runs on your Mac.<span class="motto">Divide et canta.</span></p>
      </div>
      <div class="lx-grid">${songs.length ? songs.map((s) => `
        <button class="lx-pick" data-lx="open" data-name="${esc(s.name)}">
          <img src="${songCover(s, 256)}" alt="">
          <div><b>${esc(s.title)}</b><span>${fmt(s.duration_s)} · ${esc(s.params.style.split(",").slice(1, 3).join(","))}</span></div>
        </button>`).join("") : `<div class="empty"><h3>No songs yet</h3>Create one first, then bring it here.</div>`}
      </div>`;
  }

  function renderModes() {
    const has = new Set(L.sets.map((x) => x.mode));
    el().innerHTML = header(L.sets.length ? `<button class="btn" data-lx="tomix">Back to mixer</button>` : "") + `
      <div class="lx-ask">
        <h2>What do you want to separate?</h2>
        <div class="lx-modes">${Object.entries(MODE_INFO).filter(([, m]) => !m.retired).map(([id, m]) => `
          <button class="lx-mode ${L.mode === id ? "on" : ""}" data-lx="mode" data-mode="${id}" ${Settings.modeReady(id) ? "" : "disabled"}>
            <div class="lx-stem-dots">${m.stems.map((st) => `<span style="--c:${STEM_COLORS[st]}" title="${st}"><svg viewBox="0 0 24 24">${STEM_ICONS[st]}</svg></span>`).join("")}</div>
            <div class="lx-mode-title">${m.title}${has.has(id) && id !== "anything" ? '<span class="badge">done</span>' : ""}</div>
            <div class="lx-mode-desc">${m.desc}</div>
            <div class="lx-mode-stems">${id === "anything" ? "your sound + everything else" : m.stems.join(" · ")}</div>
            <div class="lx-mode-model">${m.model}${Settings.modeReady(id) ? "" : " · Set up in Settings"}</div>
          </button>`).join("")}
        </div>
        <div class="lx-prompt ${L.mode === "anything" ? "show" : ""}">
          <div class="lx-prompt-box"><svg viewBox="0 0 24 24"><path d="M12 3l1.9 5.8L20 10l-5 3.9L16.5 20 12 16.6 7.5 20 9 13.9 4 10l6.1-1.2z"/></svg>
            <input id="lx-prompt" placeholder="Describe the sound, e.g. “acoustic guitar”" value="${esc(L.prompt)}" maxlength="120"></div>
          <div class="tagbar">${PROMPT_IDEAS.map((p) => `<button type="button" data-lx="idea" data-p="${esc(p)}">${esc(p)}</button>`).join("")}</div>
          <div class="hint">Mono 48 kHz output. Uses ~3 GB of memory and is the slowest mode.</div>
        </div>
        <button class="create-btn lx-go" data-lx="go" ${Settings.modeReady(L.mode) ? "" : "disabled"}><svg viewBox="0 0 24 24"><path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/></svg>Separate</button>
        <div class="error" id="lx-error"></div>
      </div>`;
    const inp = document.getElementById("lx-prompt");
    if (inp) inp.oninput = () => { L.prompt = inp.value; };
  }

  function renderProcessing(job) {
    const mode = MODE_INFO[job.params.mode];
    const stems = job.params.mode === "anything" ? [job.params.prompt, "everything else"] : mode.stems;
    const colors = job.params.mode === "anything" ? [STEM_COLORS.target, STEM_COLORS.residual] : mode.stems.map((x) => STEM_COLORS[x]);
    const queued = job.status === "queued";
    el().innerHTML = header() + `
      <div class="lx-proc">
        <div class="lx-split">
          <canvas class="lx-split-src" id="lx-src"></canvas>
          <div class="lx-split-lanes">${stems.map((st, i) => `
            <div class="lx-split-lane" style="--c:${colors[i]}; --d:${i * 0.18}s"><span>${esc(st)}</span><i></i></div>`).join("")}</div>
        </div>
        <h2 class="${queued ? "" : "shimmer"}" id="lx-proc-title">${queued ? "Waiting for the engine…" : job.params.mode === "anything" ? `Extracting “${esc(job.params.prompt)}”…` : `Separating ${esc(mode.title.toLowerCase())}…`}</h2>
        <div class="progress lx-progress"><i id="lx-bar" style="width:0"></i></div>
        <div class="lx-sub" id="lx-proc-time">${esc(mode.model)}</div>
      </div>`;
    requestAnimationFrame(() => drawWave(document.getElementById("lx-src"), L.song.peaks, 0, { bar: 3, gap: 2, dim: "rgba(236,230,220,.32)" }));
    tickProcessing();
  }

  function renderMixer() {
    hideTakeHelp();
    const set = L.set;
    const setName = (x) => esc(x.prompt ? `“${x.prompt}”` : MODE_INFO[x.mode].title);
    const activeBaseId = editRoot(set)?.id || set.id;
    const tabs = L.sets.filter((x) => !x.edit).map((x) => `<button class="${x.id === activeBaseId ? "on" : ""}" data-lx="set" data-set-id="${esc(x.id)}" title="Separation">${setName(x)}</button>`).join("");
    el().innerHTML = header(`<a class="btn" href="/outputs/${encodeURIComponent(L.song.name)}.wav" download>Original WAV</a>`) + `
      <div class="lx-mixer">
        <div class="lx-bar">
          <div class="segmented lx-tabs">${tabs}</div>
          <button class="btn" data-lx="new"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>New separation</button>
        </div>
        <div class="lx-transport">
          <button class="play-btn lx-play" data-lx="play" title="Play (space)"><svg viewBox="0 0 24 24" id="lx-play-icon">${ICON.play}</svg></button>
          <div class="lx-time"><b id="lx-cur">0:00</b><span>/ ${fmt(L.duration || L.song.duration_s)}</span></div>
          <div class="lx-presets">
            <button class="chip" data-lx="preset" data-p="all">Full mix</button>
            ${hasStem("vocals") ? `<button class="chip" data-lx="preset" data-p="karaoke">🎤 Karaoke</button><button class="chip" data-lx="preset" data-p="acapella">A cappella</button>` : ""}
            ${hasStem("drums") ? `<button class="chip" data-lx="preset" data-p="nodrums">No drums</button><button class="chip" data-lx="preset" data-p="rhythm">Rhythm section</button>` : ""}
            ${hasStem("target") ? `<button class="chip" data-lx="preset" data-p="solo-target">Only “${esc(set.prompt)}”</button><button class="chip" data-lx="preset" data-p="remove-target">Remove it</button>` : ""}
          </div>
          <button class="btn primary lx-export" data-lx="export"><svg viewBox="0 0 24 24"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>Export mix</button>
        </div>
        <div class="lx-editbar" id="lx-editbar"></div>
        <div class="lx-tracks" id="lx-tracks">${set.stems.map((st, i) => trackRow(st, i, set)).join("")}</div>
        <div class="lx-foot">${set.edit?.direction ? `<b>Direction used:</b> ${esc(set.edit.direction)} · ` : ""}<b class="lx-tip">Tip:</b> press <b>Edit</b> on a track, then drag across its lane to regenerate that part of the stem only. Separated in ${fmt(set.elapsed_s)} with ${esc(MODE_INFO[set.mode].model)}${L.loadingSet ? " · loading audio…" : ""}</div>
      </div>`;
    syncTrackUI(); drawLanes(); updateTransport(); renderEditBar();
  }

  /* ---------- regenerate a piece of one stem ---------- */

  const stemJobs = () => state.jobs.filter((j) => j.kind === "stemedit" && j.params.song === L.song?.name);
  function renderEditBar() {
    const box = document.getElementById("lx-editbar"); if (!box || !L.set) return;
    const running = stemJobs().filter((j) => j.status === "running" || j.status === "queued")
      .sort((x, y) => (x.status === "running" ? -1 : 1) - (y.status === "running" ? -1 : 1) || x.created - y.created);
    const failed = stemJobs().find((j) => j.status === "error" && !j.seen);
    const ls = L.laneSel && L.laneSel.i === L.armed ? L.laneSel : null;
    const st = L.armed != null ? L.set.stems[L.armed] : null;
    if (!st && !running.length && !failed) { box.innerHTML = ""; return; }
    const c = st ? (STEM_COLORS[st.id] || "#f0a23c") : "#f0a23c";
    box.innerHTML = `
      ${st && !ls ? `<div class="lx-eb waiting" style="--c:${c}">
        <div class="lx-eb-row">
          <span class="lx-ticon"><svg viewBox="0 0 24 24">${STEM_ICONS[st.id] || STEM_ICONS.other}</svg></span>
          <div class="lx-eb-title"><b>Editing ${esc(st.label)}</b><span>Drag across the highlighted ${esc(st.label)} lane to choose the part you want a new version of</span></div>
          <button class="icon-btn" data-lx="eb-clear" title="Stop editing"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
        </div></div>` : ""}
      ${ls ? `<div class="lx-eb" style="--c:${c}">
        <div class="lx-eb-row">
          <span class="lx-ticon"><svg viewBox="0 0 24 24">${STEM_ICONS[st.id] || STEM_ICONS.other}</svg></span>
          <div class="lx-eb-title"><b>Regenerate ${esc(st.label)}</b><span>${fmt(ls.a)} – ${fmt(ls.b)} · ${barsLabel(ls)} · a new version of this part, the rest of the song stays as it is</span></div>
          <label class="toggle lx-eb-snap" title="Snap the selection to beats and bars so the new part starts and ends on the beat"><input type="checkbox" data-lx="eb-snap" ${L.snap ? "checked" : ""} ${L.beats ? "" : "disabled"}><span></span>Snap${L.beats ? ` · ${Math.round(L.beats.bpm)} BPM` : ""}</label>
          ${L.song.params.cot !== "off" ? `<div class="lx-eb-listen"><span>Variation</span>
            <div class="segmented small">
              <button type="button" data-lx="eb-var" data-v="new" class="${L.variation === "new" ? "on" : ""}" title="Write this part anew: new melody and phrasing, same tempo and key">New idea</button>
              <button type="button" data-lx="eb-var" data-v="same" class="${L.variation === "same" ? "on" : ""}" title="Keep the song's score: the same notes, performed and rendered again">Same melody</button>
            </div></div>` : ""}
          <div class="lx-eb-listen"><span>Listen</span>
            <div class="segmented small">
              <button type="button" data-lx="eb-listen" data-v="solo" class="${L.listen === "solo" ? "on" : ""}" title="Only the ${esc(st.label)} stem">Solo stem</button>
              <button type="button" data-lx="eb-listen" data-v="mix" class="${L.listen === "mix" ? "on" : ""}" title="All stems, with your mute/solo settings">Full mix</button>
            </div></div>
          <button class="btn" data-lx="eb-play"><svg viewBox="0 0 24 24">${ICON.play}</svg>Play selection</button>
          <div class="segmented small lx-eb-takes">${[1, 2, 3].map((n) => `<button type="button" data-lx="eb-takes" data-n="${n}" class="${L.stemTakes === n ? "on" : ""}" title="${n} take${n > 1 ? "s" : ""}">${n}×</button>`).join("")}</div>
          <button class="icon-btn" data-lx="eb-clear" title="Clear selection"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
        </div>
        <label class="lx-eb-direction">Direction for this part <span>Optional · guides the selected section</span>
          <textarea data-lx="eb-direction" maxlength="500" rows="2" placeholder="e.g. Make the chorus more powerful, with a brighter melody and stronger drums">${esc(L.direction || "")}</textarea>
        </label>
        <div class="lx-eb-actions">
          <button class="create-btn lx-eb-go" data-lx="eb-go"><svg viewBox="0 0 24 24"><path d="M12 3l1.9 5.8L20 10l-5 3.9L16.5 20 12 16.6 7.5 20 9 13.9 4 10l6.1-1.2z"/></svg>Regenerate</button>
        </div>
      </div>` : ""}
      ${running.map((j) => `<div class="ed-job" data-sjob="${j.id}"><span class="spinner-ring"></span>
        <div><b class="${j.status === "running" ? "shimmer" : ""}">${j.status === "running" ? "Regenerating" : "Queued"} ${esc(j.params.stem)} ${fmt(j.params.start_s)}–${fmt(j.params.end_s)}</b>
        <div class="progress"><i data-sbar style="width:0"></i></div><span class="meta" data-stime></span></div></div>`).join("")}
      ${failed ? `<div class="error">${esc(failed.error)}</div>` : ""}`;
  }
  function tickStemJobs() {
    for (const j of stemJobs()) {
      if (j.status !== "running") continue;
      const row = document.querySelector(`[data-sjob="${j.id}"]`); if (!row) continue;
      const elapsed = j.now - j.started + (Date.now() - state.jobsAt) / 1000;
      row.querySelector("[data-sbar]").style.width = `${Math.min(96, (elapsed / j.eta_s) * 100)}%`;
      row.querySelector("[data-stime]").textContent = `${fmt(elapsed)} / ~${fmt(j.eta_s)}`;
    }
  }
  setInterval(tickStemJobs, 250);

  function snapTime(t) {
    const g = L.beats; if (!g || !L.snap) return t;
    return Math.max(0, Math.min(L.duration, g.offset_s + Math.round((t - g.offset_s) / g.beat_s) * g.beat_s));
  }
  function barsLabel(sel) {
    const len = sel.b - sel.a, g = L.beats;
    if (!g || !L.snap) return `${len.toFixed(1)} s`;
    const beats = Math.round(len / g.beat_s), bars = beats / g.beats_per_bar;
    return Number.isInteger(bars) ? `${bars} bar${bars === 1 ? "" : "s"}` : `${beats} beats`;
  }

  async function startStemEdit() {
    const { i, a, b } = L.laneSel, st = L.set.stems[i];
    for (let k = 0; k < L.stemTakes; k++) {
      const body = { song: L.song.name, set_id: L.set.id, stem: st.id, start_s: +a.toFixed(2), end_s: +b.toFixed(2),
                     seed: Math.floor(Math.random() * 2 ** 31), variation: L.variation,
                     direction: (document.querySelector('[data-lx="eb-direction"]')?.value || "").trim() || null };
      const r = await fetch("/api/edit/replace-stem", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!r.ok) { const d = (await r.json()).detail; alert(typeof d === "string" ? d : JSON.stringify(d)); return; }
      const job = await r.json();
      state.jobs = [{ ...job, now: Date.now() / 1000 }, ...state.jobs];
    }
    renderEditBar(); pollJobs();
  }

  function trackRow(st, i, set) {
    const c = STEM_COLORS[st.id] || "#f0a23c";
    const root = editRoot(set);
    const takes = root ? L.sets.filter((x) => x.edit && editRoot(x)?.id === root.id && x.edit.stem === st.id)
      .sort((a, b) => String(a.created || a.id).localeCompare(String(b.created || b.id))) : [];
    const versions = takes.length ? `<div class="lx-track-versions" aria-label="${esc(st.label)} versions">
      <button class="lx-version ${set.id === root.id ? "on" : ""}" data-lx="version" data-set-id="${esc(root.id)}">Original</button>
      ${takes.map((take, index) => `<button class="lx-version ${set.id === take.id ? "on" : ""}" data-lx="version" data-set-id="${esc(take.id)}">Take ${index + 1}</button>`).join("")}
    </div>` : "";
    return `
      <div class="lx-track ${st.silent ? "no-signal" : ""}" data-i="${i}" style="--c:${c}">
        <div class="lx-tctl">
          <div class="lx-tname"><span class="lx-ticon"><svg viewBox="0 0 24 24">${STEM_ICONS[st.id] || STEM_ICONS.other}</svg></span><b>${esc(st.label)}</b>
            ${st.silent ? '<span class="badge" title="This stem is near silent: the model found almost nothing for it">not detected</span>' : ""}</div>
          <div class="lx-tbtns">
            <button class="lx-ms" data-lx="mute" data-i="${i}" title="Mute">M</button>
            <button class="lx-ms" data-lx="solo" data-i="${i}" title="Solo">S</button>
            <input type="range" min="0" max="1.5" step="0.01" value="1" data-lx="vol" data-i="${i}" title="Volume">
            ${Settings.canEdit(L.song) && Settings.modeReady(set.mode) ? `<button class="lx-edit-btn" data-lx="arm" data-i="${i}" title="Edit a part of ${esc(st.label)}"><svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M14 6l4 4"/></svg><span>Edit</span></button>` : ""}
            <a class="icon-btn" href="/outputs/${st.file}" download="${esc(L.song.name)}-${esc(st.id)}.wav" title="Download stem"><svg viewBox="0 0 24 24"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg></a>
          </div>
          ${versions}
        </div>
        <div class="lx-lane"><canvas data-i="${i}"></canvas>
          ${st.silent ? `<div class="lx-empty-note">No ${esc(st.label)} detected in this song · ${st.rms_db} dB</div>` : ""}
          <div class="lx-meter"><i data-meter="${i}"></i></div></div>
      </div>`;
  }

  function editRoot(set) {
    let current = set;
    const seen = new Set();
    while (current?.edit && current.base && !seen.has(current.id)) {
      seen.add(current.id);
      current = L.sets.find((candidate) => candidate.id === current.base);
    }
    return current || null;
  }

  function hasStem(id) { return L.set?.stems.some((s) => s.id === id); }

  let takeHelpOwner = null;
  function hideTakeHelp() {
    takeHelpOwner?.removeAttribute("aria-describedby");
    takeHelpOwner = null;
    document.getElementById("lx-take-help")?.remove();
  }

  function showTakeHelp(button) {
    if (takeHelpOwner === button) return;
    hideTakeHelp();
    const take = L.sets.find((candidate) => candidate.id === button.dataset.setId);
    if (!take?.edit) return;
    const stem = take.stems.find((candidate) => candidate.id === take.edit.stem);
    const duration = L.buffers[stem?.file]?.duration || L.duration || L.song?.duration_s;
    const start = Number(take.edit.start_s), end = Number(take.edit.end_s);
    if (!stem || !Number.isFinite(start) || !Number.isFinite(end) || end <= start || !(duration > 0)) return;
    const left = Math.max(0, Math.min(100, start / duration * 100));
    const right = Math.max(left, Math.min(100, end / duration * 100));
    const help = document.createElement("div");
    help.id = "lx-take-help"; help.className = "lx-take-help"; help.setAttribute("role", "tooltip");
    help.style.setProperty("--c", STEM_COLORS[stem.id] || "#f0a23c");
    help.innerHTML = `<b>${esc(button.textContent)} · ${esc(stem.label)}</b>
      <span>Regenerated ${fmt(start)} – ${fmt(end)}</span>
      <div class="lx-take-wave"><canvas></canvas><i style="left:${left}%;width:${right - left}%"></i></div>
      <div class="lx-take-scale"><span>0:00</span><span>${fmt(duration)}</span></div>`;
    document.body.appendChild(help);
    takeHelpOwner = button; button.setAttribute("aria-describedby", help.id);
    drawWave(help.querySelector("canvas"), stem.peaks, 0, { bar: 2, gap: 2, dim: "rgba(236,230,220,.4)" });
    const anchor = button.getBoundingClientRect(), box = help.getBoundingClientRect();
    help.style.left = `${Math.max(8, Math.min(anchor.left, innerWidth - box.width - 8))}px`;
    help.style.top = `${anchor.bottom + 8}px`;
  }


  /* ---------- jobs ---------- */

  function activeJob() {
    if (!L.song) return null;
    return state.jobs.find((j) => j.kind === "separate" && j.params.song === L.song.name && (j.status === "running" || j.status === "queued"));
  }
  let lastJobKey = "";
  async function onJobs(jobs) {
    if (!L.song) return;
    const mine = jobs.filter((j) => (j.kind === "separate" || j.kind === "stemedit") && j.params.song === L.song.name);
    const key = mine.map((j) => j.id + j.status).join();
    if (key === lastJobKey) return;
    const prev = lastJobKey; lastJobKey = key;
    const finished = mine.find((j) => j.status === "done" && !prev.includes(j.id + "done") && prev.includes(j.id));
    const failed = mine.find((j) => j.status === "error" && prev.includes(j.id) && !prev.includes(j.id + "error"));
    if (finished) {
      await refreshSets();
      const set = L.sets.find((x) => x.id === finished.result.id) || L.sets[0];
      const keepSel = finished.kind === "stemedit" ? L.laneSel : null;
      L.view = "mix"; await selectSet(set);
      L.laneSel = keepSel;
    }
    if (!visible()) return;
    render();
    if (failed && failed.kind === "separate") { L.view = "pick"; render(); const e = document.getElementById("lx-error"); if (e) e.textContent = failed.error; }
  }
  function tickProcessing() {
    const job = activeJob(); if (!job || job.status !== "running" || !visible()) return;
    const elapsed = job.now - job.started + (Date.now() - state.jobsAt) / 1000;
    const bar = document.getElementById("lx-bar"), t = document.getElementById("lx-proc-time");
    if (bar) bar.style.width = `${Math.min(96, (elapsed / job.eta_s) * 100)}%`;
    if (t) t.textContent = `${fmt(elapsed)} / ~${fmt(job.eta_s)} · ${MODE_INFO[job.params.mode].model}`;
  }
  setInterval(tickProcessing, 250);

  async function startSeparation() {
    const err = document.getElementById("lx-error"); err.textContent = "";
    const body = { song: L.song.name, mode: L.mode };
    if (L.mode === "anything") {
      body.prompt = (document.getElementById("lx-prompt").value || "").trim();
      if (!body.prompt) { err.textContent = "Describe the sound you want to pull out."; return; }
    }
    const r = await fetch("/api/lux/separate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) { const d = (await r.json()).detail; err.textContent = typeof d === "string" ? d : JSON.stringify(d); return; }
    const job = await r.json();
    state.jobs = [{ ...job, now: Date.now() / 1000 }, ...state.jobs];
    lastJobKey = state.jobs.filter((j) => j.kind === "separate" && j.params.song === L.song.name).map((j) => j.id + j.status).join();
    render(); pollJobs();
  }

  /* ---------- audio engine ---------- */

  function ensureCtx() {
    if (!L.ctx) {
      L.ctx = new (window.AudioContext || window.webkitAudioContext)();
      L.master = L.ctx.createGain(); L.master.connect(L.ctx.destination);
    }
    return L.ctx;
  }
  async function selectSet(set) {
    stopAudio();
    L.set = set; L.offset = 0; L.mixStopAt = null;
    L.tracks = set.stems.map(() => ({ gain: 1, mute: false, solo: false, node: null, src: null, analyser: null }));
    L.loadingSet = set;
    const ctx = ensureCtx();
    await Promise.all(set.stems.map(async (st) => {
      if (L.buffers[st.file]) return;
      const data = await (await fetch(`/outputs/${st.file}`)).arrayBuffer();
      L.buffers[st.file] = await ctx.decodeAudioData(data);
    }));
    if (L.set !== set) return;
    L.loadingSet = null;
    L.duration = Math.max(...set.stems.map((st) => L.buffers[st.file].duration));
    if (visible() && L.view === "mix" && !activeJob()) renderMixer();
  }
  function effectiveGain(i) {
    const t = L.tracks[i], anySolo = L.tracks.some((x) => x.solo);
    if (L.audition != null) return i === L.audition ? (t.gain || 1) : 0;
    if (t.mute || (anySolo && !t.solo)) return 0;
    return t.gain;
  }
  function applyGains() {
    L.tracks.forEach((t, i) => { if (t.node) t.node.gain.setTargetAtTime(effectiveGain(i), L.ctx.currentTime, 0.015); });
    syncTrackUI();
  }
  function play() {
    if (!L.set || L.loadingSet) return;
    const ctx = ensureCtx(); ctx.resume();
    if (!audio.paused) audio.pause();
    if (L.offset >= L.duration - 0.05) L.offset = 0;
    L.startAt = ctx.currentTime + 0.05;
    L.set.stems.forEach((st, i) => {
      const src = ctx.createBufferSource(); src.buffer = L.buffers[st.file];
      const g = ctx.createGain(); g.gain.value = effectiveGain(i);
      const an = ctx.createAnalyser(); an.fftSize = 512;
      src.connect(g); g.connect(an); g.connect(L.master);
      src.start(L.startAt, L.offset);
      Object.assign(L.tracks[i], { src, node: g, analyser: an });
    });
    L.tracks[0].src.onended = () => { if (L.playing && position() >= L.duration - 0.1) { stopAudio(); L.offset = 0; updateTransport(); drawLanes(); } };
    L.playing = true; loop(); updateTransport();
  }
  function pause() {
    if (L.audition != null) { L.audition = null; applyGains(); }
    if (!L.playing) return; L.offset = position(); stopAudio(); updateTransport();
  }
  function stopAudio() {
    for (const t of L.tracks) { try { t.src?.stop(); } catch { /* not started */ } t.src = t.node = t.analyser = null; }
    L.playing = false; cancelAnimationFrame(L.raf);
    document.querySelectorAll("[data-meter]").forEach((m) => (m.style.height = "0%"));
  }
  function toggle() { L.playing ? pause() : play(); }
  function position() { return L.playing ? Math.min(L.duration, L.offset + Math.max(0, L.ctx.currentTime - L.startAt)) : L.offset; }
  function seek(t) { const was = L.playing; if (was) stopAudio(); L.offset = Math.max(0, Math.min(L.duration, t)); if (was) play(); else { updateTransport(); drawLanes(); } }

  const meterBuf = new Uint8Array(512);
  function loop() {
    if (!L.playing) return;
    if (L.mixStopAt != null && position() >= L.mixStopAt) { L.mixStopAt = null; pause(); drawLanes(); return; }
    drawLanes(); updateTransport();
    L.tracks.forEach((t, i) => {
      const m = document.querySelector(`[data-meter="${i}"]`); if (!m || !t.analyser) return;
      t.analyser.getByteTimeDomainData(meterBuf);
      let peak = 0; for (const v of meterBuf) peak = Math.max(peak, Math.abs(v - 128));
      m.style.height = `${Math.min(100, (peak / 128) * 140)}%`;
    });
    L.raf = requestAnimationFrame(loop);
  }

  /* ---------- drawing ---------- */

  function drawLanes() {
    if (!L.set) return;
    const prog = L.duration ? position() / L.duration : 0;
    document.querySelectorAll(".lx-lane canvas").forEach((cv) => {
      const i = Number(cv.dataset.i), st = L.set.stems[i]; if (!st) return;
      const c = STEM_COLORS[st.id] || "#f0a23c", on = effectiveGain(i) > 0;
      const dpr = devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight; if (!w) return;
      cv.width = w * dpr; cv.height = h * dpr;
      const g = cv.getContext("2d"); g.scale(dpr, dpr);
      const n = Math.floor(w / 3), peaks = st.peaks;
      for (let k = 0; k < n; k++) {
        const p = Math.sqrt(peaks[Math.floor((k / n) * peaks.length)] || 0), bh = Math.max(1.5, p * h * 0.9);
        g.globalAlpha = on ? (k / n < prog ? 1 : 0.38) : 0.12;
        g.fillStyle = c; g.fillRect(k * 3, (h - bh) / 2, 2, bh);
      }
      g.globalAlpha = 1;
      if (L.armed === i && L.beats && L.duration) {
        const bt = L.beats;
        for (let k = 0, t = bt.offset_s; t < L.duration; k++, t = bt.offset_s + k * bt.beat_s) {
          const bar = k % bt.beats_per_bar === 0, x = (t / L.duration) * w;
          g.fillStyle = bar ? "rgba(236,230,220,.22)" : "rgba(236,230,220,.08)";
          g.fillRect(Math.round(x), bar ? 0 : h * 0.72, 1, bar ? h : h * 0.28);
        }
      }
      if (L.laneSel && L.laneSel.i === i && L.duration) {
        const x0 = (L.laneSel.a / L.duration) * w, x1 = (L.laneSel.b / L.duration) * w;
        g.fillStyle = "rgba(240,162,60,.16)"; g.fillRect(x0, 0, x1 - x0, h);
        g.fillStyle = "#f0a23c"; g.fillRect(x0 - 1, 0, 2, h); g.fillRect(x1 - 1, 0, 2, h);
        g.beginPath(); g.arc(x0, 6, 4.5, 0, 7); g.arc(x1, 6, 4.5, 0, 7); g.fill();
      }
      g.fillStyle = "#fff"; g.fillRect(Math.round(prog * w), 0, 1.5, h);
    });
  }
  function updateTransport() {
    const cur = document.getElementById("lx-cur"); if (cur) cur.textContent = fmt(position());
    const ic = document.getElementById("lx-play-icon"); if (ic) ic.innerHTML = L.playing ? ICON.pause : ICON.play;
  }
  function syncTrackUI() {
    L.tracks.forEach((t, i) => {
      const row = document.querySelector(`.lx-track[data-i="${i}"]`); if (!row) return;
      row.querySelector('[data-lx="mute"]').classList.toggle("on", t.mute);
      row.querySelector('[data-lx="solo"]').classList.toggle("on", t.solo);
      row.classList.toggle("silent", effectiveGain(i) === 0);
      row.classList.toggle("armed", L.armed === i);
      const eb = row.querySelector('[data-lx="arm"]');
      if (eb) { eb.classList.toggle("on", L.armed === i); eb.querySelector("span").textContent = L.armed === i ? "Editing" : "Edit"; }
      const v = row.querySelector('[data-lx="vol"]'); v.value = t.gain; paintRange(v);
    });
    drawLanes();
  }
  function preset(p) {
    const ids = L.set.stems.map((s) => s.id);
    L.tracks.forEach((t, i) => {
      const id = ids[i]; t.solo = false; t.gain = 1;
      t.mute = (p === "karaoke" && id === "vocals") || (p === "acapella" && id !== "vocals") ||
        (p === "nodrums" && id === "drums") || (p === "rhythm" && !["drums", "bass"].includes(id)) ||
        (p === "solo-target" && id !== "target") || (p === "remove-target" && id === "target");
    });
    applyGains();
  }

  /* ---------- export ---------- */

  async function exportMix() {
    const btn = document.querySelector('[data-lx="export"]');
    btn.disabled = true; btn.lastChild.textContent = "Rendering…";
    try {
      const sr = Math.max(...L.set.stems.map((st) => L.buffers[st.file].sampleRate));
      const off = new OfflineAudioContext(2, Math.ceil(L.duration * sr), sr);
      L.set.stems.forEach((st, i) => {
        const g = effectiveGain(i); if (!g) return;
        const src = off.createBufferSource(); src.buffer = L.buffers[st.file];
        const gn = off.createGain(); gn.gain.value = g; src.connect(gn); gn.connect(off.destination); src.start();
      });
      const out = await off.startRendering();
      const blob = encodeWav(out);
      const parts = L.set.stems.filter((_, i) => effectiveGain(i) > 0).map((s) => s.id).join("+") || "silence";
      const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `${L.song.name}-${parts}.wav` });
      a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    } finally { btn.disabled = false; btn.lastChild.textContent = "Export mix"; }
  }
  function encodeWav(buf) {
    const ch = buf.numberOfChannels, n = buf.length, data = new DataView(new ArrayBuffer(44 + n * ch * 2));
    const w = (o, s) => [...s].forEach((c, i) => data.setUint8(o + i, c.charCodeAt(0)));
    w(0, "RIFF"); data.setUint32(4, 36 + n * ch * 2, true); w(8, "WAVEfmt "); data.setUint32(16, 16, true);
    data.setUint16(20, 1, true); data.setUint16(22, ch, true); data.setUint32(24, buf.sampleRate, true);
    data.setUint32(28, buf.sampleRate * ch * 2, true); data.setUint16(32, ch * 2, true); data.setUint16(34, 16, true);
    w(36, "data"); data.setUint32(40, n * ch * 2, true);
    const chans = [...Array(ch)].map((_, c) => buf.getChannelData(c));
    let peak = 0; for (const c of chans) for (let i = 0; i < n; i++) peak = Math.max(peak, Math.abs(c[i]));
    const norm = peak > 0.99 ? 0.99 / peak : 1;  // avoid clipping when stems are boosted
    for (let i = 0, o = 44; i < n; i++) for (let c = 0; c < ch; c++, o += 2) data.setInt16(o, Math.max(-1, Math.min(1, chans[c][i] * norm)) * 32767, true);
    return new Blob([data], { type: "audio/wav" });
  }

  /* ---------- events ---------- */

  document.addEventListener("pointerover", (e) => {
    const button = e.target.closest('[data-lx="version"]');
    if (button && visible() && e.pointerType !== "touch") showTakeHelp(button);
  });
  document.addEventListener("pointerout", (e) => {
    if (takeHelpOwner?.contains(e.target) && !takeHelpOwner.contains(e.relatedTarget)) hideTakeHelp();
  });
  document.addEventListener("focusin", (e) => {
    if (e.target.matches('[data-lx="version"]') && visible()) showTakeHelp(e.target);
  });
  document.addEventListener("focusout", (e) => { if (e.target === takeHelpOwner) hideTakeHelp(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideTakeHelp(); });
  document.addEventListener("scroll", hideTakeHelp, true);
  window.addEventListener("resize", hideTakeHelp);

  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-lx]"); if (!t || !el().contains(t)) return;
    const a = t.dataset.lx, i = Number(t.dataset.i);
    if (a === "back") { history.pushState(null, "", "#/lux"); route(); }
    if (a === "open") open(t.dataset.name);
    if (a === "mode") { L.mode = t.dataset.mode; renderModes(); if (L.mode === "anything") document.getElementById("lx-prompt").focus(); }
    if (a === "idea") { L.prompt = t.dataset.p; document.getElementById("lx-prompt").value = L.prompt; }
    if (a === "go") startSeparation();
    if (a === "new") { pause(); L.view = "pick"; render(); }
    if (a === "tomix") { L.view = "mix"; render(); }
    if (a === "set" || a === "version") {
      const target = L.sets.find((candidate) => candidate.id === t.dataset.setId);
      if (target) { const keep = L.laneSel; L.view = "mix"; selectSet(target).then(() => { L.laneSel = keep; render(); }); }
    }
    if (a === "play") { L.mixStopAt = null; if (L.audition != null) { L.audition = null; applyGains(); } toggle(); }
    if (a === "mute") { L.tracks[i].mute = !L.tracks[i].mute; applyGains(); }
    if (a === "solo") { L.tracks[i].solo = !L.tracks[i].solo; applyGains(); }
    if (a === "preset") preset(t.dataset.p);
    if (a === "export") exportMix();
    if (a === "eb-play" && L.laneSel) {
      pause();
      L.audition = L.listen === "solo" ? L.armed : null; applyGains();
      seek(L.laneSel.a); play(); L.mixStopAt = L.laneSel.b;
    }
    if (a === "eb-listen") {
      L.listen = t.dataset.v;
      if (L.playing && L.mixStopAt != null) { L.audition = L.listen === "solo" ? L.armed : null; applyGains(); }
      renderEditBar();
    }
    if (a === "arm") {
      if (L.armed === i) { L.armed = null; L.laneSel = null; }
      else { const sel = L.laneSel; L.armed = i; L.laneSel = sel ? { ...sel, i } : null; }
      if (L.audition != null) pause();
      syncTrackUI(); renderEditBar();
    }
    if (a === "eb-snap") {
      L.snap = t.checked;
      if (L.snap && L.laneSel) L.laneSel = { ...L.laneSel, a: snapTime(L.laneSel.a), b: snapTime(L.laneSel.b) };
      renderEditBar(); drawLanes();
    }
    if (a === "eb-var") { L.variation = t.dataset.v; renderEditBar(); }
    if (a === "eb-takes") { L.stemTakes = Number(t.dataset.n); renderEditBar(); }
    if (a === "eb-go" && L.laneSel) startStemEdit();
    if (a === "eb-clear") { L.laneSel = null; L.armed = null; if (L.audition != null) pause(); syncTrackUI(); renderEditBar(); }
  });
  document.addEventListener("input", (e) => {
    const t = e.target;
    if (t.dataset?.lx === "eb-direction") { L.direction = t.value; return; }
    if (t.dataset?.lx !== "vol") return;
    L.tracks[Number(t.dataset.i)].gain = Number(t.value); paintRange(t); applyGains();
  });
  let laneDrag = null;
  document.addEventListener("pointerdown", (e) => {
    const cv = e.target.closest(".lx-lane canvas"); if (!cv || !L.duration) return;
    const r = cv.getBoundingClientRect();
    laneDrag = { i: Number(cv.dataset.i), r, x0: e.clientX, t0: ((e.clientX - r.left) / r.width) * L.duration,
                 canSelect: Number(cv.dataset.i) === L.armed };
    cv.setPointerCapture(e.pointerId);
  });
  document.addEventListener("pointermove", (e) => {
    if (!laneDrag || !laneDrag.canSelect || Math.abs(e.clientX - laneDrag.x0) < 4) return;
    const t = Math.max(0, Math.min(L.duration, ((e.clientX - laneDrag.r.left) / laneDrag.r.width) * L.duration));
    L.laneSel = { i: laneDrag.i, a: Math.min(laneDrag.t0, t), b: Math.max(laneDrag.t0, t) };
    drawLanes();
  });
  document.addEventListener("pointerup", (e) => {
    if (!laneDrag) return;
    const d = laneDrag; laneDrag = null;
    if (!d.canSelect || Math.abs(e.clientX - d.x0) < 4) { seek(d.t0); return; }     // click (or a lane not in edit mode): jump there
    L.laneSel = { ...L.laneSel, a: snapTime(L.laneSel.a), b: snapTime(L.laneSel.b) };
    while (L.laneSel.b - L.laneSel.a < 1 && L.laneSel.b < L.duration)   // at least 1 s, grown beat by beat
      L.laneSel.b = Math.min(L.duration, L.laneSel.b + (L.beats && L.snap ? L.beats.beat_s : 1 - (L.laneSel.b - L.laneSel.a)));
    renderEditBar(); drawLanes();
  });
  document.addEventListener("keydown", (e) => {
    if (!visible() || e.target.matches("input, textarea")) return;
    if (e.key === "ArrowRight") seek(position() + 5);
    if (e.key === "ArrowLeft") seek(position() - 5);
  });
  window.addEventListener("resize", () => visible() && drawLanes());

  function onLibrary() {
    if (!visible()) return;
    if (!L.song) renderPicker();
  }

  return { open, route, onJobs, onLibrary, pause, toggle, visible };
})();
window.Lux = Lux;
Lux.route();
