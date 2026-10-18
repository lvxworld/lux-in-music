"use strict";

/* Optional lyrics writer: Settings card, Create concept field and a shared client for Vibe. */
const Lyrics = (() => {
  const $ = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let status = null, models = [], message = "", messageError = false, saving = false;
  let writing = false, undoText = null, undoStyle = null, wroteFromConcept = false, writeToken = 0;
  const listeners = new Set();

  async function request(url, body) {
    const response = await fetch(url, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "The lyrics request failed.");
    return data;
  }

  async function refresh() {
    const previous = JSON.stringify(status);
    try { status = await request("/api/lyrics/status"); } catch { status = null; }
    // Re-render only on change so typing in the Settings card is never wiped.
    if (JSON.stringify(status) !== previous || !$("lyrics-model-card")) renderSettings();
    renderCreate();
    listeners.forEach((listener) => listener(status));
    return status;
  }

  function generate(body) { return request("/api/lyrics/generate", body); }

  // Unsaved Settings input survives re-renders; null means "show the saved value".
  let draft = { base_url: null, model: null, other: false }, servers = [], discovering = false, discovered = false;
  let loadingModels = false, modelsFor = "", modelsToken = 0;
  const draftUrl = () => draft.base_url ?? status?.base_url ?? "";
  const draftModel = () => draft.model ?? status?.model ?? "";

  function renderSettings() {
    const mount = $("lyrics-settings");
    if (!mount) return;
    const s = status || {}, model = draftModel();
    const listed = models.length && modelsFor === draftUrl();
    const other = draft.other || (listed && model && !models.includes(model));
    const choices = listed ? models : [];
    mount.innerHTML = `<article class="model-card" id="lyrics-model-card"><div class="label-row"><h3>Lyrics writer</h3><span class="badge">Optional · OpenAI-compatible</span></div>
      <p>Writes lyrics from a song concept in Create and from your images in Vibe. Use a local server such as LM Studio, Ollama or mlx-lm, or any hosted OpenAI-compatible API.</p>
      <form class="lyrics-form" id="lyrics-form" autocomplete="off">
        <div class="label-row"><label for="lyrics-base-url">Base URL</label><button type="button" class="link" id="lyrics-discover" ${discovering ? "disabled" : ""}>${discovering ? "Looking for local servers…" : "Find local servers"}</button></div>
        <input id="lyrics-base-url" type="url" placeholder="http://localhost:1234/v1" value="${esc(draftUrl())}">
        ${servers.length ? `<div class="lyrics-servers" role="group" aria-label="Local servers found">${servers.map((server, i) => `<button type="button" class="btn ${server.base_url === draftUrl() ? "on" : ""}" data-lyrics-server="${i}">${esc(server.name)} · ${server.models.length} model${server.models.length === 1 ? "" : "s"}</button>`).join("")}</div>` : discovered && !discovering ? '<p class="hint">No local server found on the usual ports. Start one, or enter its base URL.</p>' : ""}
        <div class="label-row"><label for="lyrics-model">Model</label><button type="button" class="link" id="lyrics-load-models" ${loadingModels || !draftUrl() ? "disabled" : ""}>${loadingModels ? "Loading models…" : "Refresh models"}</button></div>
        ${choices.length ? `<select id="lyrics-model">${model ? "" : '<option value="" selected disabled>Choose a model</option>'}${choices.map((id) => `<option value="${esc(id)}" ${id === model && !other ? "selected" : ""}>${esc(id)}</option>`).join("")}<option value="__other__" ${other ? "selected" : ""}>Other…</option></select>` : ""}
        ${!choices.length || other ? `<input id="lyrics-model-name" placeholder="Model name" value="${esc(model)}">` : ""}
        <label for="lyrics-api-key">API key <span class="meta">(optional for local servers)</span></label>
        <input id="lyrics-api-key" type="password" autocomplete="new-password" placeholder="${s.api_key_from_env ? "Using LUX_LYRICS_API_KEY" : s.api_key_set ? "Saved · leave blank to keep" : "Not set"}">
        ${s.api_key_set && !s.api_key_from_env ? '<button type="button" class="link" id="lyrics-clear-key">Clear saved key</button>' : ""}
        <label class="license-accept"><input type="checkbox" id="lyrics-images" ${s.supports_images ? "checked" : ""}> Model can read images (send Vibe images with the request)</label>
      </form>
      <p class="hint">When you write lyrics, your concept, style and mood are sent to this endpoint. Vibe images are sent only when the image option is on. The API key stays on this computer and is never shown again. Finding local servers checks only common ports on this computer.</p>
      ${s.state_error ? `<p class="error">${esc(s.state_error)}</p>` : ""}
      <p class="${messageError ? "error" : "hint"}" id="lyrics-settings-message" role="status" aria-live="polite">${esc(message || (s.configured ? `Ready · ${s.model}` : "Not set up."))}</p>
      <div class="model-actions"><button class="btn primary" type="button" id="lyrics-save" ${saving ? "disabled" : ""}>Save</button><button class="btn" type="button" id="lyrics-test" ${saving ? "disabled" : ""}>Save and test</button></div></article>`;
    $("lyrics-form").onsubmit = (event) => { event.preventDefault(); save(false); };
    $("lyrics-save").onclick = () => save(false);
    $("lyrics-test").onclick = () => save(true);
    $("lyrics-clear-key")?.addEventListener("click", () => save(false, ""));
    $("lyrics-discover").onclick = discover;
    $("lyrics-load-models").onclick = () => loadModels(true);
    $("lyrics-base-url").oninput = (event) => { draft.base_url = event.target.value; };
    $("lyrics-base-url").onchange = () => loadModels(false);
    if ($("lyrics-model")) $("lyrics-model").onchange = (event) => {
      draft.other = event.target.value === "__other__";
      if (!draft.other) draft.model = event.target.value;
      renderSettings();
      if (draft.other) $("lyrics-model-name").focus();
    };
    if ($("lyrics-model-name")) $("lyrics-model-name").oninput = (event) => { draft.model = event.target.value; };
    mount.querySelectorAll("[data-lyrics-server]").forEach((button) => button.onclick = () => {
      const server = servers[Number(button.dataset.lyricsServer)];
      draft.base_url = server.base_url; models = server.models; modelsFor = server.base_url; draft.other = false;
      if (!server.models.includes(draftModel())) draft.model = server.models[0];
      message = `${server.name}: ${server.models.length} model${server.models.length === 1 ? "" : "s"} found. Choose one and save.`; messageError = false;
      renderSettings();
    });
  }

  async function discover() {
    discovering = true; renderSettings();
    try { servers = (await request("/api/lyrics/discover", {})).servers || []; }
    catch (error) { servers = []; message = error.message; messageError = true; }
    finally { discovering = false; discovered = true; }
    // Pick the first server when nothing has been chosen yet.
    if (servers.length && !draftUrl()) { draft.base_url = servers[0].base_url; models = servers[0].models; modelsFor = servers[0].base_url; if (!draftModel()) draft.model = models[0]; }
    renderSettings();
  }

  async function loadModels(report) {
    const baseUrl = draftUrl().trim();
    if (!baseUrl) return;
    const token = ++modelsToken, typed = $("lyrics-api-key")?.value.trim();
    loadingModels = true; renderSettings();
    try {
      const result = await request("/api/lyrics/models", { base_url: baseUrl, api_key: typed || null });
      if (token !== modelsToken) return;
      models = result.models; modelsFor = result.base_url; draft.base_url = result.base_url;
      if (models.length && !draftModel()) draft.model = models[0];
      message = models.length ? `${models.length} model${models.length === 1 ? "" : "s"} found.` : "The server lists no models. Enter the model name.";
      messageError = false;
    } catch (error) {
      if (token !== modelsToken) return;
      models = []; modelsFor = "";
      if (report || draft.base_url !== null) { message = error.message; messageError = true; }
    } finally {
      if (token === modelsToken) { loadingModels = false; renderSettings(); }
    }
  }

  async function save(test, apiKey) {
    const body = { base_url: draftUrl(), model: draftModel(), supports_images: $("lyrics-images").checked };
    const typed = $("lyrics-api-key").value.trim();
    if (apiKey !== undefined) body.api_key = apiKey; else if (typed) body.api_key = typed;
    saving = true; message = test ? "Saving and testing…" : "Saving…"; messageError = false; renderSettings();
    try {
      status = await request("/api/lyrics/settings", body);
      draft = { base_url: null, model: null, other: false };
      message = "Saved.";
      if (test) {
        let result = await request("/api/lyrics/test", {});
        if (result.base_url && result.base_url !== status.base_url) {
          // The server redirected (for example http → https); keep the final address so writing works.
          status = await request("/api/lyrics/settings", { base_url: result.base_url });
          result = await request("/api/lyrics/test", {});
        }
        models = result.models || []; modelsFor = status.base_url;
        message = `Connected. ${models.length} model${models.length === 1 ? "" : "s"} available${models.length && !models.includes(status.model) ? "; the selected model is not listed" : ""}.`;
      }
    } catch (error) { message = error.message; messageError = true; }
    finally { saving = false; }
    renderSettings(); renderCreate();
    listeners.forEach((listener) => listener(status));
  }

  // Opening Settings lists the saved server's models, or looks for local servers on first setup.
  function autoDiscover() {
    if (status?.base_url) { if (modelsFor !== status.base_url && !loadingModels) loadModels(false); }
    else if (!discovered && !discovering) discover();
  }

  function renderCreate() {
    if (!$("lyrics-write")) return;
    const ready = Boolean(status?.configured);
    $("lyrics-setup-link").hidden = ready;
    $("lyrics-write").disabled = !ready || writing;
    $("lyrics-write").textContent = writing ? "Writing…" : wroteFromConcept ? "Regenerate" : "Write style and lyrics";
    $("lyrics-undo").hidden = undoText === null || writing;
  }

  function setLyrics(text) {
    const field = $("lyrics");
    field.value = text;
    field.dispatchEvent(new Event("input", { bubbles: true }));
  }

  async function writeFromConcept() {
    const concept = $("concept").value.trim();
    if (!concept) { $("lyrics-write-status").textContent = "Describe the song first."; $("concept").focus(); return; }
    const token = ++writeToken;
    writing = true; $("form-error").textContent = ""; renderCreate();
    try {
      const previousStyle = $("style").value, styleNote = await writeStyle(concept, token);
      if (token !== writeToken) return;
      $("lyrics-write-status").textContent = "Writing lyrics…";
      const result = await generate({ concept, style: $("style").value, title: $("title").value });
      if (token !== writeToken) return;
      undoText = $("lyrics").value; undoStyle = $("style").value !== previousStyle ? previousStyle : null; wroteFromConcept = true;
      setLyrics(result.lyrics);
      $("lyrics-write-status").textContent = styleNote || "Style and lyrics written. Edit them freely.";
    } catch (error) {
      if (token === writeToken) { $("form-error").textContent = error.message; $("lyrics-write-status").textContent = ""; }
    } finally {
      if (token === writeToken) { writing = false; renderCreate(); }
    }
  }

  // Write Style of music from the request; if it fails, the lyrics still use the current style.
  async function writeStyle(concept, token) {
    $("lyrics-write-status").textContent = "Writing the style…";
    const vocabulary = typeof CHIPS === "undefined" ? [] : Object.values(CHIPS).flat();
    try {
      const { style } = await request("/api/lyrics/style", { concept, title: $("title").value,
        instrumental: $("instrumental").checked, vocabulary });
      if (token !== writeToken) return "";
      $("style").value = style; syncChips();
      return "";
    } catch (error) { return `Lyrics written; the style was kept (${error.message})`; }
  }

  function setupCreate() {
    if (!$("lyrics-write")) return;
    $("lyrics-write").onclick = writeFromConcept;
    $("lyrics-undo").onclick = () => {
      if (undoText === null) return;
      setLyrics(undoText); undoText = null;
      const restoredStyle = undoStyle !== null;
      if (restoredStyle) { $("style").value = undoStyle; syncChips(); undoStyle = null; }
      $("lyrics-write-status").textContent = restoredStyle ? "Previous lyrics and style restored." : "Previous lyrics restored.";
      renderCreate();
    };
    $("concept").oninput = () => { wroteFromConcept = false; renderCreate(); };
  }

  function setup() {
    setupCreate();
    const onSettings = async () => { if (location.hash === "#/settings") { await refresh(); autoDiscover(); } };
    window.addEventListener("hashchange", onSettings);
    refresh().then(() => { if (location.hash === "#/settings") autoDiscover(); });
  }

  return { setup, refresh, generate, status: () => status, moods: () => status?.moods || [],
    configured: () => Boolean(status?.configured), onChange: (listener) => listeners.add(listener) };
})();
window.Lyrics = Lyrics;
document.addEventListener("DOMContentLoaded", () => Lyrics.setup());
