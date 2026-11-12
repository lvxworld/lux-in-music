"use strict";

const Settings = (() => {
  let catalog = [], status = { active: null, profiles: [], separators: {}, jobs: [] };
  const choices = new Map(), accepted = new Set(), declined = new Set();
  let error = "", lastCompleted = "", loading = false;
  const sizes = (bytes) => `${(bytes / 1e9).toFixed(2)} GB`;
  const visible = () => location.hash === "#/settings";
  const capability = () => status.active?.capabilities || {};
  const running = (job) => job && ["queued", "running"].includes(job.status);
  const busy = (model) => running(latestJob(model));
  const latestJob = (model) => status.jobs.slice().reverse().find((job) => model.choices.some((c) => c.id === job.profile_id));
  const stageLabel = (job) => ({ queued: "Waiting…", downloading: "Downloading…", verifying: "Checking files…", testing: "Testing on this computer…" }[job.stage] || "Preparing…");

  async function request(path, body) {
    const response = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
    return data;
  }

  function selection(model) {
    const selected = status.active?.model_id === model.id ? status.active.id : Object.values(status.separators).find((id) => model.choices.some((c) => c.id === id));
    return model.choices.find((c) => c.id === choices.get(model.id)) || model.choices.find((c) => c.id === selected) || model.choices.find((c) => c.precision === model.default_precision && c.vae_precision === model.default_vae) || model.choices[0];
  }

  function applyCapabilities() {
    const cap = capability();
    $("go").disabled = !status.active || state.submitting;
    $("model-license").textContent = status.active ? `Model: ${[...new Set(status.active.licenses.map((l) => l.id))].join(" + ")}` : "No generation model selected";
    $("cot").closest(".field").hidden = !cap.planning?.length;
    for (const button of $("cot").children) button.hidden = !cap.planning?.includes(button.dataset.v);
    if (cap.planning?.length && !cap.planning.includes(state.cot)) { state.cot = cap.planning[0]; setSegmented("cot", state.cot); }
    $("abc").closest(".field").hidden = !cap.abc;
    $("instrumental-toggle").hidden = !cap.instrumental;
    if (!cap.instrumental && $("instrumental").checked) { $("instrumental").checked = false; updateLyricsCount(); }
    updateSongLengthUI();
    for (const slider of SLIDERS) $(slider.id).closest(".slider").hidden = !cap.options?.includes(slider.id);
    const setupHint = "Choose and activate a model in Settings to create music.";
    if (!status.active) $("form-error").textContent = setupHint;
    else if ($("form-error").textContent === setupHint) $("form-error").textContent = "";
  }

  function options() {
    const cap = capability(), result = {};
    for (const [key, value] of Object.entries(state.adv)) if (cap.options?.includes(key)) result[key] = value;
    if (cap.planning?.length) result.cot = state.cot;
    if (cap.abc && $("abc").value.trim()) result.abc = $("abc").value;
    return { ...result, ...window.Hook?.options() };
  }

  function route() {
    const on = visible();
    document.body.classList.toggle("settings-mode", on);
    $("nav-settings").classList.toggle("active", on);
    if (on) { $("nav-create").classList.remove("active"); $("nav-vibe").classList.remove("active"); $("nav-lux").classList.remove("active"); render(); }
  }

  function progress() {
    const focused = document.activeElement?.id;
    for (const model of catalog) {
      const container = document.getElementById(`progress-${model.id}`);
      if (!container) continue;
      const job = latestJob(model);
      if (!job || job.status === "done" || !running(job) && job.profile_id !== selection(model).id) { container.innerHTML = ""; container.hidden = true; continue; }
      const transferred = job.completed_bytes + (job.stage === "downloading" ? job.file_bytes || 0 : 0);
      const percent = Math.min(100, Math.round(100 * transferred / (job.total_bytes || 1)));
      container.hidden = false;
      container.innerHTML = `${running(job) ? `<progress aria-label="${esc(stageLabel(job))}" ${job.stage === "downloading" ? `value="${percent}"` : ""} max="100"></progress>` : ""}
        ${job.file ? `<small>${esc(job.file)}${job.stage === "downloading" ? ` · ${percent}% · ${sizes(transferred)} / ${sizes(job.total_bytes)}` : ""}</small>` : ""}
        ${job.error ? `<p class="error" role="alert">Setup failed: ${esc(job.error)} Retry verification or repair the files.</p>` : ""}
        ${job.status === "cancelled" ? '<p class="hint">Setup cancelled. You can retry when ready.</p>' : ""}
        ${running(job) ? `<button id="cancel-${job.id}" type="button" class="btn" data-cancel="${esc(job.id)}">Cancel setup</button>` : ""}`;
      if (running(job)) $(`setup-${model.id}`).textContent = stageLabel(job);
    }
    if (focused) document.getElementById(focused)?.focus({ preventScroll: true });
  }

  function render() {
    if (!$("model-cards")) return;
    const focused = document.activeElement?.id;
    $("settings-message").textContent = error || status.state_error || (status.active ? `Active: ${status.active.name}${status.active.precision ? ` · ${status.active.precision.toUpperCase()}` : ""}${status.active.vae_precision ? ` · VAE ${status.active.vae_precision.toUpperCase()}` : ""}` : "Choose a model to get started. Existing downloads can be verified and reused.");
    $("model-cards").innerHTML = catalog.map((model) => {
      const choice = selection(model), vaes = [...new Set(model.choices.map((c) => c.vae_precision).filter(Boolean))];
      const precisions = [...new Set(model.choices.map((c) => c.precision).filter(Boolean))];
      const checked = accepted.has(choice.license_review_id);
      const active = status.active?.id === choice.id || Object.values(status.separators).includes(choice.id);
      const savedReview = status.accepted_license_reviews?.includes(choice.license_review_id);
      const readyActive = active && choice.ready && savedReview;
      const action = model.delivery === "external" || choice.installed ? "activate" : "download";
      const label = readyActive ? "Active · Verified" : active && choice.ready ? "Confirm license review" : choice.ready ? "Activate verified model" : model.delivery === "external" ? "Connect / verify" : choice.installed ? "Verify and activate" : "Download and activate";
      const licensed = model.licenses.length && model.licenses.every((l) => l.verified && l.id && l.url);
      return `<article class="model-card" id="model-${model.id}"><div class="label-row"><h3>${esc(model.name)}</h3><span class="badge">${model.task === "gen" ? "Generation" : "Optional separation"}</span></div>
        <p>${esc(model.description)}</p><div class="row2">${precisions.length ? `<div><label for="precision-${model.id}">Main model precision</label><select id="precision-${model.id}" data-precision="${model.id}">${precisions.map((p) => `<option value="${p}" ${p === choice.precision ? "selected" : ""}>${p.toUpperCase()}</option>`).join("")}</select></div>` : ""}
        ${vaes.length ? `<div><label for="vae-${model.id}">VAE precision</label><select id="vae-${model.id}" data-vae="${model.id}">${vaes.map((v) => `<option value="${v}" ${v === choice.vae_precision ? "selected" : ""}>${v.toUpperCase()}${v === model.default_vae ? " (default)" : ""}</option>`).join("")}</select></div>` : ""}</div>
        <p class="hint">${model.delivery === "external" ? "This provider needs no local model download. Precision is managed by the provider." : `Files: ${sizes(choice.bytes)} · Missing files: ${sizes(choice.missing_bytes)}. Runtime memory also needs cache and buffers; peak memory has not been measured here.`}</p>
        ${vaes.length ? '<p class="hint">BF16 is a 16-bit format distinct from FP16. Main and VAE precision are independent. Higher precision uses more memory; an audible improvement is not guaranteed.</p>' : ""}
        <div class="model-licenses"><h4>Licenses — review before downloading</h4>${model.licenses.map((l) => `<p><b>${esc(l.component)}: <a href="${esc(l.url)}" target="_blank" rel="noopener noreferrer">${esc(l.id)}</a></b><br>${esc(l.summary)}</p>`).join("")}
        ${licensed ? "" : '<p class="error">License information is incomplete. Downloads are unavailable until this release is reviewed.</p>'}
        <label class="license-accept"><input type="checkbox" id="license-${model.id}" data-license="${choice.license_review_id}" ${checked ? "checked" : ""} ${licensed ? "" : "disabled"}> I have reviewed and accept these component license terms.</label></div>
        <p class="hint model-verification">${choice.ready ? active ? `Verified · Active ${model.task === "gen" ? "generation" : "separation"} model` : "Verified on this computer" : choice.installed ? "Files found — verification required" : "Not installed"} · Release ${esc(model.revision.slice(0, 12))}</p>
        <div class="model-actions"><button type="button" class="btn primary" id="setup-${model.id}" data-setup="${model.id}" data-action="${action}" ${busy(model) || !checked || !licensed || readyActive ? "disabled" : ""}>${label}</button></div>
        <div id="progress-${model.id}" class="model-progress" role="status" aria-live="polite" hidden></div>
        ${model.delivery !== "external" && choice.installed ? `<details class="model-maintenance"><summary>Maintenance</summary><button type="button" class="btn" id="repair-${model.id}" data-setup="${model.id}" data-action="download" ${busy(model) || !checked || !licensed ? "disabled" : ""}>Repair / recheck files</button></details>` : ""}</article>`;
    }).join("");
    progress();
    if (focused) document.getElementById(focused)?.focus({ preventScroll: true });
  }

  async function refresh(reloadCatalog = false) {
    if (loading) return;
    loading = true;
    try {
      const next = await request("/api/settings/status");
      const completed = next.jobs.filter((j) => !["queued", "running"].includes(j.status)).map((j) => `${j.id}:${j.status}`).join(",");
      const changed = completed !== lastCompleted || next.active?.id !== status.active?.id;
      status = next;
      for (const review of status.accepted_license_reviews || []) if (!declined.has(review)) accepted.add(review);
      if (reloadCatalog || changed || !catalog.length) catalog = (await request("/api/settings/catalog")).models;
      if (changed) { lastCompleted = completed; loadLibrary(); }
      applyCapabilities();
      if (visible()) { if (changed || reloadCatalog) render(); else progress(); }
    } catch (failure) { error = failure.message; if (visible()) render(); }
    finally { loading = false; }
  }

  async function setup() {
    $("settings").onchange = (event) => {
      const target = event.target;
      if (target.dataset.license) {
        if (target.checked) { accepted.add(target.dataset.license); declined.delete(target.dataset.license); }
        else { accepted.delete(target.dataset.license); declined.add(target.dataset.license); }
      } else {
        const id = target.dataset.precision || target.dataset.vae, model = catalog.find((m) => m.id === id);
        if (!model) return;
        const current = selection(model);
        const choice = model.choices.find((c) => c.precision === (target.dataset.precision ? target.value : current.precision) && c.vae_precision === (target.dataset.vae ? target.value : current.vae_precision));
        choices.set(id, choice.id);
      }
      render();
    };
    $("settings").onclick = async (event) => {
      const button = event.target.closest("button");
      if (!button) return;
      error = "";
      try {
        if (button.dataset.cancel) {
          await request(`/api/settings/jobs/${button.dataset.cancel}/cancel`, {});
          error = "Cancellation requested. The current file check or runtime test may need to finish.";
        } else if (button.dataset.setup) {
          const model = catalog.find((m) => m.id === button.dataset.setup), choice = selection(model);
          await request(`/api/settings/${button.dataset.action}`, { model_id: model.id, precision: choice.precision, vae_precision: choice.vae_precision, license_review_id: choice.license_review_id, accept_licenses: accepted.has(choice.license_review_id) });
        }
      } catch (failure) { error = failure.message; }
      await refresh(true); render();
    };
    window.addEventListener("hashchange", route);
    await refresh(true);
    if (!status.active && !location.hash) location.hash = "#/settings";
    route();
    setInterval(() => refresh(), 1500);
  }

  return { setup, route, options, capability, ready: () => Boolean(status.active),
    profileKey: () => JSON.stringify(status.active),
    canEdit: (song) => Boolean(song?.can_edit),
    modeReady: (mode) => status.profiles.some((p) => p.id === status.separators[mode] && p.ready), refresh };
})();
window.Settings = Settings;
