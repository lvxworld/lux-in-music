"use strict";

const Vibe = (() => {
  const $ = (id) => document.getElementById(id);
  let files = [], previewUrls = [], result = null, busy = false, accepted = false, acceptanceTouched = false, analysisError = "";
  let status = null, pollTimer = null, wasVisible = false, lastSettingsJson = "";
  let createReference = null, createPreviewUrls = [], replaceNext = false, useAdvanced = true, resultProfileKey = "";
  let lyricsText = "", mood = "", customMood = "", moodTouched = false, lyricsBusy = false, lyricsError = "", lyricsToken = 0;
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const current = () => location.hash === "#/vibe";
  async function request(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "The local request failed.");
    return data;
  }

  function route() {
    const on = current();
    document.body.classList.toggle("vibe-mode", on);
    $("nav-vibe").classList.toggle("active", on);
    document.querySelectorAll(".mobile-nav a").forEach((link) => link.classList.toggle("active",
      link.hash === location.hash || link.hash === "#/lux" && location.hash.startsWith("#/lux/")));
    if (on) {
      $("nav-create").classList.remove("active"); $("nav-lux").classList.remove("active"); $("nav-settings").classList.remove("active");
      if (window.Lux?.visible?.()) window.Lux.pause?.();
      render(); refreshStatus();
    } else if (wasVisible) {
      fetch("/api/vibe/release", { method: "POST" }).catch(() => {});
    }
    wasVisible = on;
  }

  function render() {
    const ready = Boolean(status?.installed), disabled = busy ? "disabled" : "";
    const advanced = result?.advanced;
    $("vibe").innerHTML = `<header class="vibe-head"><p class="lx-kicker">Local creative direction</p><h1 id="vibe-title">Vibe</h1>
      <p class="vibe-subtitle">Turn your images into a musical direction.</p>
      <p>Bring up to five images together. Lux blends their atmospheres into a musical direction, a composite cover and a gentle listening gallery. Everything happens locally on your computer.</p></header>
      ${!ready ? `<section class="vibe-setup"><h2>Prepare Vibe in Settings</h2><p>EmbeddingGemma 2 is an optional local image and text model. Install it from Settings before analyzing images.</p><a class="btn primary" href="#/settings">Open Settings</a></section>` : ""}
      <section class="vibe-card" aria-label="Image upload">
        <input id="vibe-file" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden ${disabled}>
        <div class="vibe-drop ${files.length ? "has-image" : ""}" id="vibe-drop" tabindex="0" role="button" aria-label="Choose up to five JPG, PNG, or WebP images">
          <div class="vibe-placeholder"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>
          <b>${files.length ? `${files.length} of 5 images` : "Drop up to 5 images here"}</b><span>JPG, PNG or WebP · up to 20 MB each</span>
          <div class="vibe-actions">${files.length < 5 ? `<button class="btn" type="button" id="vibe-browse" ${disabled}>${files.length ? "Add images" : "Browse files"}</button>` : ""}${files.length ? `<button class="btn" type="button" id="vibe-replace" ${disabled}>Replace all</button>` : ""}</div></div>
        </div>
        <div class="vibe-image-grid">${files.map((file, i) => `<figure class="vibe-thumb"><img src="${previewUrls[i]}" alt="Selected image ${i + 1}"><figcaption>${esc(file.name)}</figcaption><div class="vibe-thumb-actions">
          <button class="btn" type="button" data-vibe-move="${i}" data-direction="-1" aria-label="Move image ${i + 1} earlier" ${busy || i === 0 ? "disabled" : ""}>←</button>
          <button class="btn" type="button" data-vibe-move="${i}" data-direction="1" aria-label="Move image ${i + 1} later" ${busy || i === files.length - 1 ? "disabled" : ""}>→</button>
          <button class="btn" type="button" data-vibe-remove="${i}" aria-label="Remove image ${i + 1}" ${disabled}>×</button></div></figure>`).join("")}</div>
        <p id="vibe-error" class="error" role="alert">${esc(analysisError)}</p>
        <div class="vibe-actions"><button class="btn primary" type="button" id="vibe-analyze" ${!ready || !files.length || busy ? "disabled" : ""}>${files.length > 1 ? "Analyze Images" : "Analyze Image"}</button>${busy ? '<span class="vibe-wait" role="status" aria-live="polite"><i class="vibe-spinner"></i>Analyzing and blending your images locally…</span>' : ""}</div>
        ${busy ? '<p class="hint">Lux loads the local model and prepares the style catalog when needed. The first analysis after a catalog update takes longer; later analyses reuse the saved catalog.</p>' : ""}
      </section>
      ${result ? `<section class="vibe-card vibe-result"><p class="lx-kicker">Suggested Musical Style</p><label for="vibe-style">Edit this suggestion before using it</label><textarea id="vibe-style" rows="5" maxlength="4000">${esc(result.style)}</textarea>
        ${advanced ? `<div class="vibe-advanced"><label><input type="checkbox" id="vibe-use-advanced" ${useAdvanced ? "checked" : ""}> Use image-guided Advanced settings · ${esc(advanced.label)}</label><p class="hint">${esc(advanced.explanation)}</p><ul>${Object.entries(advanced.options).map(([key, value]) => `<li>${esc(SLIDERS.find(s => s.id === key)?.label || key)}: <b>${esc(value)}</b></li>`).join("")}</ul></div>` : ""}
        ${renderLyrics()}
        <div class="vibe-actions"><button class="btn" type="button" id="vibe-again" ${disabled}>Analyze Again</button><button class="btn primary" type="button" id="vibe-use" ${disabled}>Use in Create</button></div><p class="hint">Creative direction inspired by your images. Edit it freely to match your intent.</p></section>` : ""}`;
    bindPage();
  }

  function renderLyrics() {
    const lyrics = window.Lyrics;
    if (!lyrics?.configured()) return `<div class="vibe-lyrics"><p class="lx-kicker">Lyrics</p><p class="hint">Set up a lyrics writer in <a href="#/settings">Settings</a> to get lyrics that match your images.</p></div>`;
    const moods = lyrics.moods();
    return `<div class="vibe-lyrics"><p class="lx-kicker">Lyrics</p>
      <div class="vibe-mood-row"><label for="vibe-mood">Theme and mood</label>
        <select id="vibe-mood" ${lyricsBusy ? "disabled" : ""}>${moods.map((m) => `<option value="${esc(m.id)}" ${m.id === mood ? "selected" : ""}>${esc(m.label)}${m.id === result?.mood ? " · suggested" : ""}</option>`).join("")}<option value="custom" ${mood === "custom" ? "selected" : ""}>Custom…</option></select>
        <input id="vibe-mood-custom" maxlength="500" placeholder="Describe your own theme, then press Enter" value="${esc(customMood)}" ${mood === "custom" ? "" : "hidden"} ${lyricsBusy ? "disabled" : ""}></div>
      <label for="vibe-lyrics">Edit the lyrics before using them</label><textarea id="vibe-lyrics" rows="12" maxlength="4000" placeholder="${lyricsBusy ? "Writing lyrics…" : "Lyrics appear here."}">${esc(lyricsText)}</textarea>
      <p id="vibe-lyrics-error" class="error" role="alert">${esc(lyricsError)}</p>
      <div class="vibe-actions"><button class="btn" type="button" id="vibe-lyrics-again" ${lyricsBusy || busy ? "disabled" : ""}>${lyricsText ? "Regenerate lyrics" : "Write lyrics"}</button>${lyricsBusy ? '<span class="vibe-wait" role="status" aria-live="polite"><i class="vibe-spinner"></i>Writing lyrics…</span>' : ""}</div></div>`;
  }

  async function writeLyrics() {
    if (!result || !window.Lyrics?.configured()) return;
    if (mood === "custom" && !customMood.trim()) { lyricsError = "Describe your theme first."; render(); $("vibe-mood-custom")?.focus(); return; }
    const token = ++lyricsToken;
    lyricsBusy = true; lyricsError = ""; render();
    try {
      const images = window.Lyrics.status()?.supports_images
        ? await Promise.all(files.map((file) => downscale(file, 1024, .85))) : [];
      const data = await window.Lyrics.generate({ style: result.style, visual: result.visual || "",
        mood: mood === "custom" ? "" : mood, custom: mood === "custom" ? customMood.trim() : "", images });
      if (token === lyricsToken) lyricsText = data.lyrics;
    } catch (error) { if (token === lyricsToken) lyricsError = error.message; }
    finally { if (token === lyricsToken) { lyricsBusy = false; if (current()) render(); } }
  }

  async function downscale(file, size, quality) {
    const bitmap = await createImageBitmap(file);
    try {
      const scale = Math.min(1, size / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(bitmap.width * scale)); canvas.height = Math.max(1, Math.round(bitmap.height * scale));
      const context = canvas.getContext("2d"); context.fillStyle = "#0b0a0d"; context.fillRect(0, 0, canvas.width, canvas.height); context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      return canvas.toDataURL("image/jpeg", quality);
    } finally { bitmap.close(); }
  }

  function updateFiles(next) {
    previewUrls.forEach(url => URL.revokeObjectURL(url));
    files = next; previewUrls = files.map(file => URL.createObjectURL(file));
    result = null; analysisError = ""; lyricsToken++; lyricsText = ""; lyricsError = ""; lyricsBusy = false; moodTouched = false; render();
  }

  function selectFiles(candidates, replace = false) {
    if (!candidates.length || busy) return;
    const next = replace ? [...candidates] : [...files, ...candidates];
    let error = "";
    if (next.length > 5) error = "Choose up to 5 images. Remove an image before adding more.";
    else if (next.some(file => !/^image\/(jpeg|png|webp)$/.test(file.type))) error = "Use JPG, PNG, or WebP images.";
    else if (next.some(file => file.size > 20 * 1024 * 1024)) error = "Each image must be no larger than 20 MB.";
    if (error) { analysisError = error; $("vibe-error").textContent = error; return; }
    updateFiles(next);
  }

  function bindPage() {
    const input = $("vibe-file"), drop = $("vibe-drop");
    input.onchange = () => { selectFiles(Array.from(input.files), replaceNext); replaceNext = false; };
    drop.onclick = (event) => { if (!event.target.closest("button") && !busy) { replaceNext = false; input.click(); } };
    drop.onkeydown = (event) => { if (event.target === drop && ["Enter", " "].includes(event.key)) { event.preventDefault(); if (!busy) input.click(); } };
    for (const name of ["dragenter", "dragover"]) drop.addEventListener(name, (event) => { event.preventDefault(); drop.classList.add("dragging"); });
    for (const name of ["dragleave", "drop"]) drop.addEventListener(name, (event) => { event.preventDefault(); drop.classList.remove("dragging"); });
    drop.ondrop = (event) => selectFiles(Array.from(event.dataTransfer.files));
    $("vibe-browse")?.addEventListener("click", () => { replaceNext = false; input.click(); });
    $("vibe-replace")?.addEventListener("click", () => { replaceNext = true; input.click(); });
    document.querySelectorAll("[data-vibe-remove]").forEach(button => button.onclick = () => updateFiles(files.filter((_, i) => i !== Number(button.dataset.vibeRemove))));
    document.querySelectorAll("[data-vibe-move]").forEach(button => button.onclick = () => {
      const next = [...files], i = Number(button.dataset.vibeMove), j = i + Number(button.dataset.direction);
      [next[i], next[j]] = [next[j], next[i]]; updateFiles(next);
    });
    $("vibe-analyze").onclick = analyze;
    $("vibe-again")?.addEventListener("click", analyze);
    if ($("vibe-style")) $("vibe-style").oninput = event => { result.style = event.target.value; };
    if ($("vibe-use-advanced")) $("vibe-use-advanced").onchange = event => { useAdvanced = event.target.checked; };
    if ($("vibe-lyrics")) $("vibe-lyrics").oninput = event => { lyricsText = event.target.value; };
    if ($("vibe-mood")) $("vibe-mood").onchange = event => {
      mood = event.target.value; moodTouched = true;
      if (mood === "custom") { lyricsError = ""; render(); $("vibe-mood-custom").focus(); } else writeLyrics();
    };
    if ($("vibe-mood-custom")) {
      $("vibe-mood-custom").oninput = event => { customMood = event.target.value; };
      $("vibe-mood-custom").onkeydown = event => { if (event.key === "Enter") { event.preventDefault(); writeLyrics(); } };
    }
    $("vibe-lyrics-again")?.addEventListener("click", writeLyrics);
    $("vibe-use")?.addEventListener("click", () => {
      const style = $("vibe-style").value.trim();
      if (!style) { $("vibe-style").focus(); return; }
      const lyrics = $("lyrics"), written = lyricsText.trim();
      if (written || !lyrics.value.trim()) {
        lyrics.value = written || DEFAULT_LYRICS;
        lyrics.dispatchEvent(new Event("input", { bubbles: true }));
        lyrics.dispatchEvent(new Event("change", { bubbles: true }));
      }
      const field = document.getElementById("style"); field.value = style;
      field.dispatchEvent(new Event("input", { bubbles: true })); field.dispatchEvent(new Event("change", { bubbles: true }));
      let advancedLabel = "";
      const applied = {};
      if (useAdvanced && result.advanced && resultProfileKey === Settings.profileKey()) {
        for (const [key, value] of Object.entries(result.advanced.options)) {
          const slider = SLIDERS.find(s => s.id === key), el = slider && $(key);
          if (el && Settings.capability().options?.includes(key) && Number.isFinite(value) && value >= Number(el.min) && value <= Number(el.max)) { el.value = value; el.oninput(); applied[key] = Number(el.value); }
        }
        advancedLabel = `${result.advanced.label} applied. You can edit Advanced.`;
      } else if (useAdvanced && result.advanced) advancedLabel = "Music model changed. Analyze again to refresh the Advanced suggestions.";
      clearCreateReference();
      createReference = { files: [...files], entry_id: result.entry_id, entry_ids: result.entry_ids || [result.entry_id], advancedLabel, applied };
      createPreviewUrls = files.map(file => URL.createObjectURL(file));
      renderCreateReference();
      location.hash = "#/";
      requestAnimationFrame(() => requestAnimationFrame(() => {
        field.focus({ preventScroll: true }); field.scrollIntoView({ behavior: "smooth", block: "center" });
      }));
    });
  }

  function clearCreateReference() {
    createPreviewUrls.forEach(url => URL.revokeObjectURL(url));
    createReference = null; createPreviewUrls = [];
    renderCreateReference();
  }

  function renderCreateReference() {
    const el = $("create-vibe-reference");
    el.hidden = !createReference;
    el.innerHTML = createReference ? `<div class="create-vibe-thumbs">${createPreviewUrls.map(url => `<img src="${url}" alt="Vibe cover preview">`).join("")}</div><div><b>${createReference.files.length} Vibe image${createReference.files.length > 1 ? "s" : ""}</b><p>Saved locally as your song’s ${createReference.files.length > 1 ? "composite cover and listening gallery" : "cover"}.</p>${createReference.advancedLabel ? `<p>${esc(createReference.advancedLabel)}</p>` : ""}</div><button type="button" class="btn" id="remove-vibe-cover">Remove</button>` : "";
    $("remove-vibe-cover")?.addEventListener("click", clearCreateReference);
  }

  async function generationReference() {
    const selected = createReference;
    if (!selected) return {};
    const images = [];
    for (let i = 0; i < selected.files.length; i++) {
      const image = (await downscale(selected.files[i], 2048, .9)).split(",")[1];
      images.push({ image, entry_id: selected.entry_ids[i] || selected.entry_id });
    }
    return { vibe_images: images, vibe_entry_id: selected.entry_id };
  }

  async function analyze() {
    if (!files.length || busy) return;
    busy = true; analysisError = ""; render();
    const modelKey = Settings.profileKey();
    const body = new FormData(); files.forEach(file => body.append("images", file));
    try {
      result = await request("/api/vibe/analyze", { method: "POST", body });
      resultProfileKey = modelKey; useAdvanced = true;
      if (!moodTouched) { mood = result.mood || "dreamy"; customMood = ""; }
      lyricsToken++; lyricsText = ""; lyricsError = ""; lyricsBusy = false;
    } catch (error) { analysisError = error.message; }
    finally { busy = false; render(); }
    if (result && !analysisError) writeLyrics();
  }

  function renderSettings() {
    if (!$("vibe-settings")) return;
    const job = status?.job, running = job && ["queued", "running"].includes(job.status);
    const percent = job?.total_bytes ? Math.min(job.stage === "downloading" ? 99 : 100, Math.round(100 * job.completed_bytes / job.total_bytes)) : 0;
    const checked = acceptanceTouched ? accepted : Boolean(status?.license_accepted);
    const licenses = status?.licenses || [], licensed = licenses.length && licenses.every((l) => l.verified && l.id && l.url);
    $("vibe-settings").innerHTML = `<article class="model-card" id="vibe-model-card"><div class="label-row"><h3>${esc(status?.name || "Vibe model")}</h3><span class="badge">Optional Vibe model</span></div>
      <p>Local image and text embeddings for Lux Vibe. Optional; installed only when you choose.</p>
      ${status?.revision ? `<p class="hint">Source: <a href="${esc(status.model_url)}" target="_blank" rel="noopener noreferrer">${esc(status.model_id)}</a> · <a href="${esc(status.model_card_url)}" target="_blank" rel="noopener noreferrer">Google model card</a><br>Revision: <code>${esc(status.revision.slice(0, 12))}</code><br>Weights: about ${(status.total_bytes / 1e9).toFixed(2)} GB, plus optional runtime dependencies<br>Text + image inference; audio encoder is not loaded. FP32 on Apple Metal when available, CPU fallback.</p>` : ""}
      <div class="model-licenses"><h4>Licenses — review before downloading</h4>${licenses.map((l) => `<p><b>${esc(l.component)}: <a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.id)}</a></b><br>${esc(l.summary)}</p>`).join("")}
      ${licensed ? "" : '<p class="error">License information is unavailable. Downloads are disabled until it loads.</p>'}
      <label class="license-accept"><input type="checkbox" id="vibe-license" ${checked ? "checked" : ""} ${licensed ? "" : "disabled"}> I have reviewed and accept these model terms.</label></div>
      <p class="hint">${status?.installed && status.runtime_compatible === false ? "Model files are verified. The local image runtime needs an update. Select Update Vibe runtime to prepare the required software and reuse these model files." : status?.installed ? "Model files verified on this computer. They remain local and are never uploaded." : status?.files_present ? "Model files were found but need repair or verification. Lux will reuse valid local files where possible." : "Not installed. Installing the model does not change your active music generation model."}</p>
      ${job?.restart_required && status.auto_restart ? '<p class="hint" role="status">Vibe software updated. Lux restarts automatically when no songs are generating or queued, then Vibe is ready. The model files are already installed.</p>' : ""}
      ${job?.restart_required && !status.auto_restart ? '<p class="hint" role="status">Vibe software updated. In the Terminal window running Lux, press <kbd>Ctrl+C</kbd> and wait for the server to stop, then run <code>./studio.sh</code> again. Refreshing the browser does not restart the runtime. The model files are already installed.</p>' : ""}
      ${job?.status === "error" ? `<p class="error" role="alert">Setup failed: ${esc(job.error)} You can retry the installation.</p>` : ""}
      ${running ? `<progress max="100" ${job.stage === "downloading" ? `value="${percent}"` : ""} aria-label="Preparing EmbeddingGemma"></progress><p class="hint" role="status" aria-live="polite">${["preparing_runtime", "updating_runtime"].includes(job.stage) ? "Preparing the local inference runtime…" : job.stage === "downloading" ? `Downloading model files… ${percent}%` : "Verifying model files…"}</p>` : ""}
      <div class="model-actions"><button class="btn primary" id="vibe-install" type="button" ${!checked || !licensed || running || (status?.installed && status.runtime_compatible !== false) ? "disabled" : ""}>${status?.installed && status.runtime_compatible === false ? "Update Vibe runtime" : status?.installed ? "Installed · Verified" : running ? "Installing…" : status?.files_present ? "Verify / repair Vibe" : "Download and prepare Vibe"}</button></div>
      <div id="vibe-install-error" role="alert" class="error"></div></article>`;
    $("vibe-license").onchange = (event) => { accepted = event.target.checked; acceptanceTouched = true; renderSettings(); };
    $("vibe-install").onclick = async () => {
      try {
        await request("/api/vibe/install", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ license_review_id: status.license_review_id, accept_license: checked }) });
        await refreshStatus();
      } catch (error) { $("vibe-install-error").textContent = error.message; }
    };
  }

  async function refreshStatus() {
    const previous = status;
    try { status = await request("/api/vibe/status"); } catch { status = null; }
    const staleRestartError = Boolean(status && !status?.job?.restart_required && analysisError.includes("Vibe runtime was updated"));
    if (staleRestartError) analysisError = "";
    const key = JSON.stringify(status);
    if (current()) { if (JSON.stringify(previous) !== key || staleRestartError) render(); }
    else if (key !== lastSettingsJson) renderSettings();
    lastSettingsJson = key;
  }

  function setup() {
    window.addEventListener("hashchange", route);
    window.addEventListener("popstate", route);
    refreshStatus();
    window.Lyrics?.onChange(() => { if (current() && result) render(); });
    pollTimer = setInterval(() => {
      if (current() || location.hash === "#/settings") refreshStatus();
    }, 1800);
    route();
  }

  // A Vibe handoff is used by one Create request: afterwards the images detach and the
  // Advanced values Vibe applied (unless the user changed them) return to defaults.
  function consumeCreateReference() {
    for (const [key, value] of Object.entries(createReference?.applied || {})) {
      const slider = SLIDERS.find(s => s.id === key);
      if (slider && state.adv[key] === value) resetSlider(slider);
    }
    clearCreateReference();
  }

  return { setup, route, generationReference, clearCreateReference, consumeCreateReference, installed: () => Boolean(status?.installed) };
})();
window.Vibe = Vibe;
Vibe.setup();
