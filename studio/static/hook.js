"use strict";

const Hook = (() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const current = () => location.hash === "#/hook";
  let status = null, accepted = null, busy = false, decoding = false, recording = false, recordToken = 0;
  let clip = null, clipUrl = null, result = null, error = "", start = 0, end = 0, bpm = 0;
  let recorder = null, elapsedTimer = null, createReference = null, createReferenceAudio = null, previewUrl = null;
  let instrumentalBeforeHook = false, forcedInstrumental = false;
  let mode = "develop", target = "vocal", requestId = 0, lastStatus = "", wasVisible = false;
  let inputs = [], inputMessage = "", refreshingInputs = false, inputMissing = false;
  let inputId = "";
  try { inputId = localStorage.getItem("lux.hook.audioInput") || ""; } catch { /* Storage can be unavailable. */ }

  async function request(path, options) {
    const response = await fetch(path, options), data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "The local request failed. Please try again.");
    return data;
  }

  function route() {
    const on = current();
    document.body.classList.toggle("hook-mode", on);
    for (const [id, active] of [["nav-create", !location.hash || location.hash === "#/"], ["nav-vibe", location.hash === "#/vibe"],
      ["nav-hook", on], ["nav-lux", /^#\/lux(?:\/|$)/.test(location.hash)], ["nav-settings", location.hash === "#/settings"]]) {
      $(id)?.classList.toggle("active", active);
    }
    document.querySelectorAll(".mobile-nav a").forEach(link => link.classList.toggle("active",
      link.hash === location.hash || link.hash === "#/lux" && location.hash.startsWith("#/lux/")));
    if (on) { render(); refresh(); }
    else if (wasVisible) {
      if (recording) stopRecording();
      $("hook-audio")?.pause(); $("hook-melody-audio")?.pause();
      fetch("/api/hook/release", { method: "POST" }).catch(() => {});
    }
    wasVisible = on;
  }

  function render() {
    const disabled = busy || recording || decoding, ready = status?.installed;
    $("hook").innerHTML = `<header class="hook-head"><p class="lx-kicker">Your melody starts here</p><h1 id="hook-title">Hook</h1>
      <p class="hook-subtitle">Record an idea. Turn it into a song.</p>
      <p>Whistle, hum or play a melody. Record it here or upload an audio file, then let Lux build a new arrangement around it. Everything stays on your computer.</p></header>
      ${!ready ? '<section class="hook-card"><h2>Prepare Hook in Settings</h2><p>Hook uses the optional SheetSage2 transcription model. Install it once in Settings, then analyze offline.</p><a class="btn primary" href="#/settings">Open Settings</a></section>' : ''}
      <section class="hook-card" aria-label="Record or upload a melody">
        <div class="hook-drop" id="hook-drop"><b>${clip ? 'Your recording is ready' : 'Start with a small musical idea'}</b>
          <p>Drop an audio file here, browse files, or record from your microphone.<br>2–90 seconds · up to 25 MB · one recording at a time</p>
          <input id="hook-file" type="file" accept="audio/*,.wav,.flac,.mp3,.m4a,.ogg,.aiff" hidden>
          <div class="hook-actions"><button class="btn" id="hook-browse" type="button" ${disabled ? 'disabled' : ''}>${clip ? 'Replace audio' : 'Browse files'}</button>
            <button class="btn hook-record" id="hook-record" type="button" aria-pressed="${recording}" ${busy || decoding || inputMissing && !recording ? 'disabled' : ''}><i aria-hidden="true"></i>${recording ? 'Stop recording' : 'Record microphone'}</button>
            <span id="hook-record-time" role="status">${recording ? 'Waiting for microphone…' : ''}</span><div class="hook-level" ${recording ? '' : 'hidden'} aria-hidden="true"><span id="hook-level"></span></div></div></div>
        <div class="hook-demo"><div><b>Luke's real performance</b><p>Played and recorded by Luke. Not AI-generated.</p></div>
          <button class="btn" id="hook-demo" type="button" ${disabled ? 'disabled' : ''}>${clip ? "Replace with Luke's demo" : "Load Luke's demo"}</button></div>
        <details class="hook-input-settings"><summary>Audio input settings</summary><div id="hook-input-settings"></div></details>
        ${clip ? `<canvas class="hook-wave" id="hook-wave" width="1000" height="100" aria-label="Recording waveform"></canvas><audio id="hook-audio" src="${clipUrl}" controls preload="metadata" aria-label="Your recording"></audio>
          <div class="hook-fields"><div><label for="hook-start">Start (seconds)</label><input id="hook-start" type="number" min="0" max="${clip.duration}" step="0.1" value="${start}" ${disabled ? 'disabled' : ''}></div>
          <div><label for="hook-end">End (seconds)</label><input id="hook-end" type="number" min="2" max="${clip.duration}" step="0.1" value="${end}" ${disabled ? 'disabled' : ''}></div>
          <div><label for="hook-bpm">Recording tempo · 0 = Auto</label><input id="hook-bpm" type="number" min="0" max="240" step="1" value="${bpm}" ${disabled ? 'disabled' : ''}></div></div>
          <p class="hint">SheetSage2 listens to the full recording and separates the leading melody from accompaniment locally. A clear recording helps; Auto tempo is an estimate, so enter the BPM if you know it.</p>
          <div class="hook-actions"><button class="btn primary" id="hook-analyze" type="button" ${disabled || !ready ? 'disabled' : ''}>${result ? 'Analyze Again' : 'Find my melody'}</button></div>` : ''}
        <p class="hook-status" role="status" aria-live="polite">${busy ? '<i class="vibe-spinner" aria-hidden="true"></i>Analyzing your recording locally with SheetSage2…' : decoding ? 'Opening your audio locally…' : ''}</p>
        <p id="hook-error" class="error" role="alert">${esc(error)}</p>
      </section>
      ${result ? `<section class="hook-card"><p class="lx-kicker">Your melody</p><h2>${result.melody.notes.length} notes · ${result.bpm} BPM${result.tempo_estimated ? ' (estimated)' : ''}</h2>
        <canvas class="hook-roll" id="hook-roll" width="1000" height="145" aria-label="Recognized melody notes"></canvas>
        <audio id="hook-melody-audio" controls src="${previewUrl}" aria-label="Recognized melody preview"></audio>
        ${(result.warnings || []).map(warning => `<p class="hook-warning" role="status">${esc(warning)}</p>`).join('')}
        <p>Listen before continuing. If the melody sounds wrong, trim a clearer phrase, set the recording tempo, or record a solo take.${result.melody.octave_shift ? ' The preview moves the melody by whole octaves into a more usable register.' : ''}</p>
        <div class="hook-actions"><div class="hook-choice"><label for="hook-mode">How should Lux use it?</label><select id="hook-mode"><option value="develop" ${mode === 'develop' ? 'selected' : ''}>Develop into a song</option><option value="arrange" ${mode === 'arrange' ? 'selected' : ''}>Arrange this recording</option></select></div>
        <div class="hook-choice"><label for="hook-target">Use the melody as</label><select id="hook-target"><option value="vocal" ${target === 'vocal' ? 'selected' : ''}>Vocal melody</option><option value="instrumental" ${target === 'instrumental' ? 'selected' : ''}>Instrumental hook</option></select></div></div>
        <p id="hook-mode-help">${modeHelp()}</p><p class="hint">A new performance is generated. Your original voice and guitar sound are not retained. Melody matching is guidance, not a guarantee of identical notes. Hook extracts one melody; it does not identify instruments, chords or a style. Your style comes from Create and stays editable there.</p>
        <div class="hook-actions"><button class="btn primary" id="hook-use" type="button" ${disabled || !Settings.capability().hook ? 'disabled' : ''}>Use in Create</button></div>
        ${!Settings.capability().hook ? '<p class="hint">Select a compatible music model such as YuE2 in Settings to continue.</p>' : ''}</section>` : ''}`;
    bind(); draw(); renderInputs();
  }

  function modeHelp() {
    return mode === "develop" ? "Lux plans a complete song from your lyrics and style, then fits your melody into its chorus sections. Timing adapts to the arrangement. If no chorus is found, it uses an interior lead phrase." :
      "Lux follows the recording’s melody and approximate length, rounded to bars with a short ending. Use lyrics that fit this short arrangement, or choose Instrumental in Create.";
  }

  function bind() {
    $("hook-browse").onclick = () => $("hook-file").click();
    $("hook-demo").onclick = loadDemo;
    $("hook-file").onchange = event => { if (event.target.files[0]) loadFile(event.target.files[0]); };
    const drop = $("hook-drop");
    for (const name of ["dragenter", "dragover"]) drop.addEventListener(name, e => { e.preventDefault(); drop.classList.add("dragging"); });
    for (const name of ["dragleave", "drop"]) drop.addEventListener(name, e => { e.preventDefault(); drop.classList.remove("dragging"); });
    drop.ondrop = e => { if (e.dataTransfer.files.length !== 1) { error = "Choose one audio file at a time."; render(); } else loadFile(e.dataTransfer.files[0]); };
    $("hook-record").onclick = () => recording ? stopRecording() : startRecording();
    for (const id of ["start", "end", "bpm"]) if ($(`hook-${id}`)) $(`hook-${id}`).onchange = () => {
      start = Number($("hook-start").value); end = Number($("hook-end").value); bpm = Number($("hook-bpm").value);
      clearResult(); error = ""; render();
    };
    $("hook-analyze")?.addEventListener("click", analyze);
    const recordingAudio = $("hook-audio");
    if (recordingAudio) {
      recordingAudio.onplay = () => { if (recordingAudio.currentTime < start || recordingAudio.currentTime >= end) recordingAudio.currentTime = start; audio.pause(); window.Lux?.pause?.(); $("hook-melody-audio")?.pause(); };
      recordingAudio.ontimeupdate = () => { if (recordingAudio.currentTime >= end) recordingAudio.pause(); };
    }
    if ($("hook-melody-audio")) $("hook-melody-audio").onplay = () => { recordingAudio?.pause(); audio.pause(); window.Lux?.pause?.(); };
    $("hook-mode")?.addEventListener("change", e => { mode = e.target.value; $("hook-mode-help").textContent = modeHelp(); });
    $("hook-target")?.addEventListener("change", e => { target = e.target.value; });
    $("hook-use")?.addEventListener("click", useInCreate);
  }

  function clearResult() {
    result = null;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }

  function pcmWav(samples, rate) {
    const buffer = new ArrayBuffer(44 + samples.length * 2), view = new DataView(buffer);
    const write = (offset, text) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
    write(0, "RIFF"); view.setUint32(4, buffer.byteLength - 8, true); write(8, "WAVE"); write(12, "fmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true); view.setUint32(24, rate, true);
    view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, samples.length * 2, true);
    samples.forEach((value, i) => view.setInt16(44 + i * 2, Math.round(Math.max(-1, Math.min(1, value)) * 32767), true));
    return new Blob([buffer], { type: "audio/wav" });
  }

  function setClip(samples, rate) {
    if (clipUrl) URL.revokeObjectURL(clipUrl);
    clip = { samples, rate, duration: samples.length / rate };
    clipUrl = URL.createObjectURL(pcmWav(samples, rate));
    start = 0; end = Math.floor(clip.duration * 100) / 100;
    clearResult(); error = ""; render();
  }

  async function loadFile(file) {
    if (busy || recording || decoding) return;
    error = "";
    if (!file.size || file.size > 25 * 1024 * 1024) { error = "Choose an audio file no larger than 25 MB."; render(); return; }
    decoding = true; render();
    let ctx, metadataUrl;
    try {
      metadataUrl = URL.createObjectURL(file);
      const media = new Audio(); media.preload = "metadata";
      const duration = await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => { media.src = ""; reject(new Error("This audio file could not be opened. Try WAV, MP3 or M4A.")); }, 10000);
        media.onloadedmetadata = () => { clearTimeout(timeout); resolve(media.duration); };
        media.onerror = () => { clearTimeout(timeout); reject(new Error("Your browser cannot read this audio file. Try WAV, MP3 or M4A.")); };
        media.src = metadataUrl;
      });
      media.src = "";
      if (!Number.isFinite(duration) || duration < 2 || duration > 90) throw new Error("Choose a recording between 2 and 90 seconds long.");
      ctx = new AudioContext({ sampleRate: 16000 });
      const decoded = await ctx.decodeAudioData(await file.arrayBuffer());
      if (decoded.duration < 2 || decoded.duration > 90 || decoded.numberOfChannels > 2) throw new Error("Use a mono or stereo recording between 2 and 90 seconds.");
      const mono = new Float32Array(decoded.length);
      for (let channel = 0; channel < decoded.numberOfChannels; channel++) {
        const values = decoded.getChannelData(channel);
        for (let i = 0; i < mono.length; i++) mono[i] += values[i] / decoded.numberOfChannels;
      }
      setClip(mono, decoded.sampleRate);
    } catch (e) { error = e.message || "This file could not be opened. Try WAV or record your melody here."; }
    finally { decoding = false; if (ctx) await ctx.close(); if (metadataUrl) URL.revokeObjectURL(metadataUrl); render(); }
  }

  async function loadDemo() {
    if (clip && !window.confirm("Replace your current recording with Luke's demo?")) return;
    try {
      const response = await fetch("/static/audio/luke-real-performance-hook-demo.wav");
      if (!response.ok) throw new Error("Demo audio is unavailable.");
      const audioFile = new File([await response.blob()], "luke-real-performance-hook-demo.wav", { type: "audio/wav" });
      await loadFile(audioFile);
    } catch {
      error = "Luke's demo recording could not be opened. Try again or upload an audio file.";
      render();
    }
  }

  async function startRecording() {
    if (recording || busy || decoding) return;
    const token = ++recordToken;
    recording = true; error = ""; render();
    let stream, ctx;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone recording needs localhost or HTTPS. You can upload a file instead.");
      audio.pause(); window.Lux?.pause?.();
      stream = await navigator.mediaDevices.getUserMedia({ audio: { ...(inputId ? { deviceId: { exact: inputId } } : {}), channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
      refreshInputs();
      if (token !== recordToken || !current()) { stream.getTracks().forEach(track => track.stop()); return; }
      ctx = new AudioContext({ sampleRate: 16000 }); await ctx.resume();
      await ctx.audioWorklet.addModule("/static/hook-recorder.js");
      if (token !== recordToken || !current()) { stream.getTracks().forEach(track => track.stop()); await ctx.close(); return; }
      const input = ctx.createMediaStreamSource(stream), node = new AudioWorkletNode(ctx, "lux-hook-recorder");
      const captured = recorder = { ctx, stream, input, node, chunks: [], frames: 0, started: performance.now(), done: null };
      stream.getAudioTracks().forEach(track => track.addEventListener("ended", async () => {
        if (recording && recorder === captured) {
          await stopRecording();
          error = "The audio input disconnected. Check Audio input settings before recording again."; render();
        }
      }));
      node.port.onmessage = e => {
        if (e.data.done) { captured.done?.(); return; }
        const chunk = e.data.pcm;
        if (!chunk) return;
        const remaining = Math.max(0, Math.floor(ctx.sampleRate * 90) - captured.frames);
        if (remaining) { const kept = chunk.slice(0, remaining); captured.chunks.push(kept); captured.frames += kept.length; }
        let peak = 0; for (const sample of chunk) peak = Math.max(peak, Math.abs(sample));
        if ($("hook-level")) $("hook-level").style.width = `${Math.min(100, peak * 150)}%`;
        if (captured.frames >= ctx.sampleRate * 90 && recording) stopRecording();
      };
      input.connect(node); node.connect(ctx.destination);
      elapsedTimer = setInterval(() => {
        if ($("hook-record-time")) $("hook-record-time").textContent = `${Math.floor((performance.now() - captured.started) / 1000)} / 90 s`;
      }, 200);
    } catch (e) {
      stream?.getTracks().forEach(track => track.stop()); if (ctx && ctx.state !== "closed") await ctx.close();
      recording = false; recorder = null;
      error = e.name === "NotAllowedError" ? "Microphone access was denied. Allow it in your browser, or upload an audio file." :
        ["NotFoundError", "OverconstrainedError"].includes(e.name) ? "The selected audio input is unavailable. Open Audio input settings and choose a connected input." : e.message;
      render();
    }
  }

  async function stopRecording() {
    ++recordToken;
    if (!recording) return;
    recording = false; clearInterval(elapsedTimer);
    const captured = recorder; recorder = null;
    if (!captured) { render(); return; }
    decoding = true; render();
    captured.stream.getTracks().forEach(track => track.stop());
    await new Promise(resolve => { captured.done = resolve; captured.node.port.postMessage("stop"); setTimeout(resolve, 200); });
    captured.input.disconnect(); captured.node.disconnect(); await captured.ctx.close();
    decoding = false;
    if (captured.frames < captured.ctx.sampleRate * 2) { error = "Record at least 2 seconds of melody, then stop."; render(); return; }
    const samples = new Float32Array(captured.frames); let offset = 0;
    for (const chunk of captured.chunks) { samples.set(chunk, offset); offset += chunk.length; }
    setClip(samples, captured.ctx.sampleRate);
  }

  async function analyze() {
    if (busy || recording || decoding || !clip) return;
    if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end > clip.duration || end - start < 2) { error = "Select at least 2 seconds within the recording."; render(); return; }
    if (!Number.isInteger(bpm) || bpm !== 0 && (bpm < 40 || bpm > 240)) { error = "Set a tempo from 40 to 240 BPM, or 0 for Auto."; render(); return; }
    const id = ++requestId;
    busy = true; error = ""; clearResult(); render();
    try {
      const samples = clip.samples.slice(Math.round(start * clip.rate), Math.round(end * clip.rate));
      result = await request(`/api/hook/analyze?bpm=${bpm}`, { method: "POST", headers: { "Content-Type": "audio/wav" }, body: pcmWav(samples, clip.rate) });
      if (id !== requestId) return;
      makePreview();
    } catch (e) { error = e.message; }
    finally { busy = false; render(); }
  }

  function makePreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const melody = result.melody, rate = 16000, secondsPerBeat = 60 / melody.bpm;
    const samples = new Float32Array(Math.ceil((melody.beats * secondsPerBeat + .2) * rate));
    for (const note of melody.notes) {
      const a = Math.round(note.start * secondsPerBeat * rate), b = Math.min(samples.length, Math.round(note.end * secondsPerBeat * rate));
      const frequency = 440 * 2 ** ((note.pitch - 69) / 12);
      for (let i = a; i < b; i++) {
        const t = (i - a) / rate, envelope = Math.min(1, t / .008, (b - i) / rate / .025) * Math.exp(-t * .8);
        samples[i] = .23 * envelope * Math.sin(2 * Math.PI * frequency * t);
      }
    }
    previewUrl = URL.createObjectURL(pcmWav(samples, rate));
  }

  function draw() {
    const canvas = $("hook-wave");
    if (canvas && clip) {
      const ctx = canvas.getContext("2d"), step = Math.max(1, Math.floor(clip.samples.length / canvas.width));
      ctx.fillStyle = "#d8a75f";
      for (let x = 0; x < canvas.width; x += 3) {
        let peak = 0; for (let i = x * step; i < Math.min(clip.samples.length, (x + 3) * step); i += 8) peak = Math.max(peak, Math.abs(clip.samples[i]));
        const h = Math.max(2, peak * 90); ctx.fillRect(x, 50 - h / 2, 1.8, h);
      }
      ctx.fillStyle = "#08080899"; ctx.fillRect(0, 0, start / clip.duration * canvas.width, canvas.height); ctx.fillRect(end / clip.duration * canvas.width, 0, canvas.width, canvas.height);
    }
    const roll = $("hook-roll");
    if (roll && result) {
      const ctx = roll.getContext("2d"), notes = result.melody.notes, low = Math.min(...notes.map(n => n.pitch)) - 2, high = Math.max(...notes.map(n => n.pitch)) + 2;
      ctx.fillStyle = "#e6b46e";
      for (const note of notes) ctx.fillRect(note.start / result.melody.beats * roll.width, (high - note.pitch) / (high - low) * 125 + 5, Math.max(2, (note.end - note.start) / result.melody.beats * roll.width - 1), 6);
    }
  }

  function useInCreate() {
    if (!result || !Settings.capability().hook) return;
    if ($("abc").value.trim()) { error = "Remove the custom ABC score in Create before using a Hook melody."; render(); return; }
    createReferenceAudio = pcmWav(clip.samples.slice(Math.round(start * clip.rate), Math.round(end * clip.rate)), clip.rate);
    createReference = { ...structuredClone(result.melody), mode, target };
    if (!forcedInstrumental) instrumentalBeforeHook = $("instrumental").checked;
    forcedInstrumental = true;
    $("instrumental").checked = true;
    $("instrumental").disabled = true;
    $("instrumental").dispatchEvent(new Event("change", { bubbles: true }));
    state.cot = "melody"; setSegmented("cot", "melody");
    $("cot").dispatchEvent(new Event("change", { bubbles: true }));
    renderReference(); updateSongLengthUI();
    location.hash = "#/";
    requestAnimationFrame(() => $("create-hook-reference").scrollIntoView({ behavior: "smooth", block: "center" }));
  }

  function renderReference() {
    const el = $("create-hook-reference");
    el.hidden = !createReference;
    el.innerHTML = createReference ? `<div><b>Hook · Your recorded melody</b><p>${createReference.notes.length} notes · ${createReference.bpm} BPM · ${createReference.mode === 'develop' ? 'Develop into a song' : 'Arrange recording'} · ${createReference.target === 'vocal' ? 'Vocal melody' : 'Instrumental hook'}. Hook generations are instrumental for now; lyrics are disabled while this reference is active.</p></div><button class="btn" type="button" id="hook-remove-reference">Remove</button>` : '';
    $("hook-remove-reference")?.addEventListener("click", clearReference);
  }
  function clearReference() {
    createReference = null; createReferenceAudio = null;
    if (forcedInstrumental) {
      forcedInstrumental = false;
      $("instrumental").disabled = false;
      $("instrumental").checked = instrumentalBeforeHook;
      $("instrumental").dispatchEvent(new Event("change", { bubbles: true }));
    }
    renderReference(); updateSongLengthUI();
  }
  function restoreReference(params) {
    if (forcedInstrumental) clearReference();
    createReference = params.hook_melody ? structuredClone(params.hook_melody) : null;
    createReferenceAudio = null; renderReference();
  }

  async function generationReference() {
    if (!createReference) return {};
    const reference = { hook_melody: structuredClone(createReference) };
    if (createReferenceAudio) {
      const bytes = new Uint8Array(await createReferenceAudio.arrayBuffer());
      let binary = "";
      for (let offset = 0; offset < bytes.length; offset += 0x8000) {
        binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
      }
      reference.hook_reference_audio = btoa(binary);
    }
    return reference;
  }

  function renderInputs() {
    const el = $("hook-input-settings");
    if (!el) return;
    const disabled = recording || busy || decoding || refreshingInputs;
    el.innerHTML = `<label for="hook-input">Recording input</label><select id="hook-input" ${disabled ? 'disabled' : ''}>
      <option value="">System default</option>${inputs.filter(device => device.deviceId && device.deviceId !== 'default' && device.deviceId !== 'communications').map((device, i) => `<option value="${esc(device.deviceId)}" ${device.deviceId === inputId ? 'selected' : ''}>${esc(device.label || `Audio input ${i + 1}`)}</option>`).join('')}
      ${inputMissing ? `<option value="${esc(inputId)}" selected>Selected input · disconnected or unavailable</option>` : ''}</select>
      <p class="hint">Choose your microphone or audio interface. Your browser may ask for microphone access before it can show device names. This choice is saved in this browser on this device.</p>
      <button type="button" class="btn" id="hook-refresh-inputs" ${disabled ? 'disabled' : ''}>${refreshingInputs ? 'Checking inputs…' : 'Refresh audio inputs'}</button>
      <p id="hook-input-message" ${inputMissing ? 'class="error" role="alert"' : 'class="hint" role="status"'}>${esc(inputMissing ? 'Your selected audio input is unavailable. Reconnect it or choose another input before recording.' : inputMessage)}</p>`;
    $("hook-input").onchange = event => {
      inputId = event.target.value; inputMissing = false; inputMessage = "Audio input selected.";
      try { localStorage.setItem("lux.hook.audioInput", inputId); } catch { /* Keep the in-memory selection. */ }
      renderInputs();
      if ($("hook-record")) $("hook-record").disabled = busy || decoding;
    };
    $("hook-refresh-inputs").onclick = async () => {
      if (refreshingInputs || recording || busy || decoding) return;
      refreshingInputs = true; inputMessage = ""; renderInputs();
      let permissionStream;
      try {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("Audio input selection requires localhost or HTTPS.");
        permissionStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        await refreshInputs();
        inputMessage = inputs.length ? "Available audio inputs updated." : "No audio inputs were found. Connect a microphone and refresh.";
      } catch (error) {
        inputMessage = error.name === "NotAllowedError" ? "Microphone access was denied. Allow access in your browser to show audio inputs." : "Audio inputs could not be listed. Check that your microphone is connected.";
      } finally {
        permissionStream?.getTracks().forEach(track => track.stop());
        refreshingInputs = false; renderInputs();
      }
    };
  }

  async function refreshInputs() {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      inputs = (await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === "audioinput");
      inputMissing = Boolean(inputId && !inputs.some(device => device.deviceId === inputId));
      renderInputs();
      if ($("hook-record")) $("hook-record").disabled = busy || decoding || inputMissing && !recording;
    } catch { inputMessage = "Audio inputs could not be listed. Try Refresh audio inputs."; renderInputs(); }
  }

  function renderSettings() {
    if (!$("hook-settings") || !status) return;
    const job = status.job, installing = job && ["queued", "running"].includes(job.status), checked = accepted ?? status.license_accepted;
    const percent = Math.min(job?.stage === "downloading" ? 99 : 100, Math.round(100 * (job?.completed_bytes || 0) / (job?.total_bytes || 1)));
    $("hook-settings").innerHTML = `<article class="model-card" id="hook-model-card"><div class="label-row"><h3>SheetSage2</h3><span class="badge">Optional Hook model</span></div>
      <p>Local music transcription for Lux Hook. Finds a melody in recordings with voice or instruments.</p>
      <p class="hint">Source: <a href="${esc(status.model_url)}" target="_blank" rel="noopener noreferrer">SheetSage2</a><br>Revision: <code>${esc(status.revision.slice(0, 12))}</code><br>Model files: ${(status.total_bytes / (1024 ** 3)).toFixed(2)} GB, plus an isolated Python runtime. Uses FP32 and Apple Metal when available, with CPU fallback.</p>
      <div class="model-licenses"><h4>License — review before downloading</h4>${status.licenses.map(l => `<p><b>${esc(l.component)}: <a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.id)}</a></b><br>${esc(l.summary)}</p>`).join('')}
      <label class="license-accept"><input type="checkbox" id="hook-license" ${checked ? 'checked' : ''}> I have reviewed and accept these model terms.</label></div>
      <p class="hint">${status.installed ? 'Installed and verified on this computer.' : status.files_verified ? 'Model files verified. Prepare the optional runtime to finish setup.' : 'Not ready. Download or verify Hook to continue.'} Your active music model stays unchanged.</p>
      ${installing ? `<progress max="100" ${job.stage === 'downloading' ? `value="${percent}"` : ''}></progress><p role="status">${job.stage === 'downloading' ? `Downloading model files… ${percent}%` : job.stage === 'verifying' ? 'Verifying model files and local runtime…' : 'Preparing isolated Hook software…'}</p>` : ''}
      ${job?.status === 'error' ? `<p role="alert" class="error">${esc(job.error)}</p>` : ''}
      <div class="model-actions"><button class="btn primary" id="hook-install" type="button" ${!checked || installing || status.installed ? 'disabled' : ''}>${status.installed ? 'Installed · Verified' : installing ? 'Preparing…' : 'Download and prepare Hook'}</button></div>
      ${status.installed ? `<details class="model-maintenance"><summary>Maintenance</summary><button class="btn" id="hook-repair" type="button" ${!checked || installing ? 'disabled' : ''}>Verify / repair Hook</button></details>` : ''}<p id="hook-install-error" class="error" role="alert"></p></article>`;
    $("hook-license").onchange = e => { accepted = e.target.checked; renderSettings(); };
    const install = async () => {
      try { await request("/api/hook/install", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ license_review_id: status.license_review_id, accept_license: Boolean(accepted ?? status.license_accepted) }) }); await refresh(); }
      catch (e) { $("hook-install-error").textContent = e.message; }
    };
    $("hook-install").onclick = install; $("hook-repair")?.addEventListener("click", install);
  }

  async function refresh() {
    try {
      const next = await request("/api/hook/status"), changed = JSON.stringify(next) !== lastStatus;
      status = next; lastStatus = JSON.stringify(next);
      if (changed) { renderSettings(); if (current() && !busy && !recording && !decoding) render(); }
    } catch { /* A launcher restart can briefly interrupt status polling. */ }
  }
  window.addEventListener("hashchange", route); window.addEventListener("popstate", route);
  window.addEventListener("pagehide", () => { if (recording) stopRecording(); });
  navigator.mediaDevices?.addEventListener?.("devicechange", refreshInputs);
  setInterval(() => { if (current() || location.hash === "#/settings") refresh(); }, 1800);
  refresh(); route(); refreshInputs();
  return { route, options: () => createReference ? { hook_melody: structuredClone(createReference) } : {},
    generationReference, clearReference, restoreReference };
})();
window.Hook = Hook;
