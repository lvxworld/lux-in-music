"""Web studio: model Settings, profile-bound jobs and the song library.

    uv run uvicorn studio.app:app --port 8000
"""

import json
import logging
import queue
import re
import shutil
import threading
import time
import uuid
import copy
import itertools
from email import policy
from email.parser import BytesParser
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import Literal

from pydantic import BaseModel, Field

from . import audio, edit, engine, separate
from .params import GenerationParams
from .models import get_manager, SetupRequired
from .providers import get_provider, close_providers
from .vibe import get_vibe_manager, validate_image, MAX_IMAGE_BYTES, MAX_VIBE_IMAGES
from .artwork import prepare_vibe_artwork, attach_vibe_artwork
from .lyrics import (get_lyrics_writer, validate_image_data_url, LyricsNotConfigured,
                     LyricsUpstreamError, MAX_LYRICS_IMAGES)
from starlette.concurrency import run_in_threadpool

log = logging.getLogger("lux_in_music")

STATIC = Path(__file__).parent / "static"

@asynccontextmanager
async def lifespan(app):
    yield
    get_manager().close()
    close_providers()
    get_vibe_manager().release()


app = FastAPI(title="Lux In Music", lifespan=lifespan)


@app.middleware("http")
async def _no_cache_ui(request, call_next):
    # The UI changes often during development: always revalidate HTML/JS/CSS.
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response

jobs: dict[str, dict] = {}
_queue: queue.Queue[str] = queue.Queue()
_jobs_lock = threading.Lock()  # queued -> running/cancelled transitions
_cancels: dict[str, threading.Event] = {}  # running job id -> stop request
# Seconds of compute per second of audio, learned from finished jobs (M4 Max, warm model ~0.45).
_speed = {"ratio": 0.5, "overhead": 8.0}


_sep_speed = {"vocals": 1.1, "4stems": 0.15, "6stems": 0.15, "anything": 1.5}  # seconds per audio second


def _song_duration(song: str) -> float:
    try:
        return json.loads((engine.OUTPUT_DIR / f"{song}.json").read_text())["duration_s"]
    except (OSError, KeyError, json.JSONDecodeError):
        return 60.0


def _estimate(job: dict) -> float:
    params = job["params"]
    if job["kind"] == "separate":
        return 3 + _sep_speed.get(params["mode"], 0.5) * _song_duration(params["song"])
    if job["kind"] == "stemedit":
        dur = _song_duration(params["song"])
        span = params["end_s"] - params["start_s"]
        sep = _sep_speed.get(params.get("mode", "4stems"), 0.5) * (span + 6)
        return 6 + 0.25 * dur + 0.3 * span + sep
    target = params.get("target_duration_s") or params.get("max_duration_s")
    if target is None:
        words = len(params.get("lyrics", "").split())
        target = min(330, max(45, words / 2.2))
    return (_speed["overhead"] + _speed["ratio"] * target) * job.get("variations", 1)


def _worker() -> None:
    # audio.cpp runs one generation at a time per model, so a single worker is enough.
    while True:
        job_id = _queue.get()
        with _jobs_lock:
            job = jobs.get(job_id)
            if job is None or job["status"] != "queued":
                continue
            cancel = _cancels[job_id] = threading.Event()
            job.update(status="running", started=time.time(), eta_s=_estimate(job))
        try:
            if job["kind"] == "stemedit":
                p = job["params"]
                res = separate.replace_stem(p["song"], p["set_id"], p["stem"], p["start_s"], p["end_s"],
                                            p["seed"], p.get("lyrics"), p.get("variation", "new"),
                                            job["profile"], job["separator_profile"])
                job.update(status="done", result=res)
                continue
            if job["kind"] == "separate":
                p = job["params"]
                res = separate.separate(p["song"], p["mode"], p.get("prompt"), job["profile"])
                job.update(status="done", result=res)
                _sep_speed[p["mode"]] = res["elapsed_s"] / max(1.0, _song_duration(p["song"]))
                continue
            count = job.get("variations", 1)
            base = GenerationParams(**job["params"])
            prepared_state = {}
            songs = []
            for index in range(count):
                if cancel.is_set():
                    break
                current = (prepared_state["params"].model_copy(update={"seed": base.seed + index})
                           if index and prepared_state else base.model_copy(update={"seed": base.seed + index}))
                stage = lambda label, i=index: cancel.is_set() or job.update(
                    stage=(f"Variation {i + 1}/{count} · {label}" if count > 1 else label))
                name = None if count == 1 else f"{time.strftime('%Y%m%d-%H%M%S')}-{engine.slugify(current.title or engine.auto_title(current.lyrics))}-{job_id}-{index + 1}"
                res = engine.generate(current, name=name, profile=job["profile"], progress=stage,
                    cancel=cancel, prepared=prepared_state.get("prepared"),
                    on_prepared=lambda selected, plan: prepared_state.update(params=selected, prepared=copy.deepcopy(plan)))
                if job.get("_vibe_artwork"):
                    attach_vibe_artwork(res.meta_path, job["_vibe_artwork"])
                songs.append(json.loads(res.meta_path.read_text()))
                job["completed_variations"] = len(songs)
                if res.duration_s > 5:
                    r = max(0.1, (res.elapsed_s - _speed["overhead"]) / res.duration_s)
                    _speed["ratio"] = 0.7 * _speed["ratio"] + 0.3 * r
            if cancel.is_set():
                job.update(status="cancelled", result={"songs": songs} if songs else None)
            else:
                job.update(status="done", result=songs[0] if len(songs) == 1 else {"songs": songs})
        except Exception as e:
            if cancel.is_set():
                job.update(status="cancelled")
            else:
                job.update(status="error", error=str(e))
        finally:
            job["finished"] = time.time()
            job.pop("_prepared", None)
            job.pop("_vibe_artwork", None)
            with _jobs_lock:
                _cancels.pop(job_id, None)


threading.Thread(target=_worker, daemon=True).start()


@app.get("/api/health")
def api_health():
    try:
        return engine.health()
    except Exception as e:
        return {"engine": "down", "error": str(e)}


@app.get("/api/settings/catalog")
def settings_catalog():
    return {"models": get_manager().options()}


@app.get("/api/settings/status")
def settings_status():
    return get_manager().status()


_restart_server = None  # Set by studio.launch; other hosts keep the manual restart.


def _busy() -> bool:
    active = {"queued", "running"}
    return (any(job["status"] in active for job in list(jobs.values()))
            or any(job.get("status") in active for job in get_manager().status()["jobs"]))


def _restart_after_runtime_update(interval: float = 2.0) -> None:
    # New packages only load in a new process; never interrupt generation or downloads.
    while True:
        time.sleep(interval)
        if (get_vibe_manager().job or {}).get("restart_required") and not _busy():
            log.warning("Restarting Lux to load the updated Vibe runtime…")
            _restart_server()
            return


def enable_auto_restart(restart) -> None:
    global _restart_server
    _restart_server = restart
    threading.Thread(target=_restart_after_runtime_update, daemon=True).start()


@app.get("/api/vibe/status")
def vibe_status():
    return {**get_vibe_manager().status(), "auto_restart": _restart_server is not None}


class VibeInstallRequest(BaseModel):
    license_review_id: str
    accept_license: bool = False


@app.post("/api/vibe/install")
def vibe_install(req: VibeInstallRequest):
    try:
        return get_vibe_manager().start_install(req.license_review_id, req.accept_license)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


async def _vibe_upload_images(request: Request) -> list[bytes]:
    max_request = MAX_IMAGE_BYTES * MAX_VIBE_IMAGES + 256 * 1024
    if request.headers.get("content-length"):
        try:
            if int(request.headers["content-length"]) > max_request:
                raise HTTPException(413, "Choose up to 5 images, no larger than 20 MB each")
        except ValueError:
            raise HTTPException(400, "Invalid request size")
    chunks = bytearray()
    async for chunk in request.stream():
        chunks.extend(chunk)
        if len(chunks) > max_request:
            raise HTTPException(413, "Choose up to 5 images, no larger than 20 MB each")
    content_type = request.headers.get("content-type", "").encode("ascii", "ignore")
    if content_type.lower().startswith(b"multipart/form-data"):
        message = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: " + content_type + b"\r\nMIME-Version: 1.0\r\n\r\n" + bytes(chunks))
        if not message.is_multipart() or message.defects:
            raise HTTPException(400, "Invalid image upload")
        parts = list(message.iter_parts())
        if not 1 <= len(parts) <= MAX_VIBE_IMAGES:
            raise HTTPException(422, "Choose between 1 and 5 images")
        if any(part.get_param("name", header="content-disposition") not in {"image", "images"} for part in parts):
            raise HTTPException(400, "Invalid image upload")
        images = [part.get_payload(decode=True) or b"" for part in parts]
    else:
        images = [bytes(chunks)]
    if any(len(data) > MAX_IMAGE_BYTES for data in images):
        raise HTTPException(413, "Choose an image no larger than 20 MB")
    return images


def vibe_advanced_options(result):
    try:
        profile = get_manager().snapshot()
        adapter = get_provider(profile).adapter(profile)
    except (SetupRequired, ValueError):
        return None
    suggest = getattr(adapter, "vibe_options", None)
    if not suggest:
        return None
    suggested = suggest(result.get("diversity", 0.0))
    options = {key: value for key, value in suggested["options"].items()
               if key in adapter.capabilities.get("options", [])}
    return {**suggested, "options": options, "model_id": profile["model_id"]} if options else None


@app.post("/api/vibe/analyze")
async def vibe_analyze(request: Request):
    manager = get_vibe_manager()
    vibe_status = manager.status()
    if not vibe_status["installed"]:
        raise HTTPException(409, "EmbeddingGemma is not installed. Open Settings to install it.")
    if (vibe_status.get("job") or {}).get("restart_required"):
        if _restart_server:
            raise HTTPException(503, "The Vibe runtime was updated. Lux restarts automatically when no songs "
                                "are generating or queued. Try again in a moment.")
        raise HTTPException(503, "The Vibe runtime was updated. In the Terminal window running Lux, press Ctrl+C and wait for the server to stop; then run ./studio.sh again. Refreshing the browser does not restart the runtime.")
    if not vibe_status.get("runtime_compatible", True):
        if vibe_status.get("runtime_missing"):
            raise HTTPException(503, "The Vibe image runtime is incomplete. Open Settings and select "
                                "Update Vibe runtime. Your verified model files will be reused.")
        version = vibe_status["runtime_version"] or "not installed"
        raise HTTPException(503, f"Vibe needs Sentence Transformers 6.1.0 or newer; {version} is installed. "
                            "Open Settings and select Update Vibe runtime. Your verified model files will be reused.")
    uploads = await _vibe_upload_images(request)
    def perform_analysis():
        def decoded_images():
            for data in uploads:
                try:
                    yield validate_image(data)
                except ValueError as error:
                    raise HTTPException(422, str(error)) from error
        images = iter(decoded_images())
        first = next(images)
        return (manager.analyze(first) if len(uploads) == 1
                else manager.analyze_many(itertools.chain([first], images)))
    started = time.monotonic()
    try:
        result = await run_in_threadpool(perform_analysis)
    except HTTPException:
        raise
    except Exception as error:
        log.exception("Vibe image analysis failed")
        raise HTTPException(503, "Local image analysis failed. Check the Vibe model installation in Settings.") from error
    return {"entry_id": result["id"], "style": result["style"],
            "entry_ids": result.get("entry_ids", [result["id"]]), "image_count": len(uploads),
            "mood": result.get("mood"), "visual": result.get("visual"),
            "advanced": vibe_advanced_options(result),
            "elapsed_s": round(time.monotonic() - started, 2)}


@app.post("/api/vibe/release")
def vibe_release():
    get_vibe_manager().release()
    return {"ok": True}


@app.get("/api/lyrics/status")
def lyrics_status():
    return get_lyrics_writer().status()


class LyricsSettings(BaseModel):
    base_url: str | None = Field(None, max_length=500)
    model: str | None = Field(None, max_length=200)
    api_key: str | None = Field(None, max_length=500)  # None keeps the saved key; "" clears it.
    supports_images: bool | None = None
    temperature: float | None = None


@app.post("/api/lyrics/settings")
def lyrics_settings(req: LyricsSettings):
    try:
        return get_lyrics_writer().save(req.model_dump(exclude_unset=True))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def _lyrics_call(action):
    try:
        return action()
    except LyricsNotConfigured as error:
        raise HTTPException(409, str(error)) from error
    except LyricsUpstreamError as error:
        raise HTTPException(502, str(error)) from error


@app.post("/api/lyrics/test")
def lyrics_test():
    return _lyrics_call(get_lyrics_writer().test)


class LyricsModelsRequest(BaseModel):
    base_url: str = Field(..., max_length=500)
    api_key: str | None = Field(None, max_length=500)


@app.post("/api/lyrics/models")
def lyrics_models(req: LyricsModelsRequest):
    try:
        return _lyrics_call(lambda: get_lyrics_writer().list_models(req.base_url, req.api_key))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/api/lyrics/discover")
def lyrics_discover():
    return get_lyrics_writer().discover()


class StyleRequest(BaseModel):
    concept: str = Field(..., min_length=1, max_length=2000)
    title: str = Field("", max_length=200)
    instrumental: bool = False
    vocabulary: list[str] = Field(default_factory=list, max_length=200)


@app.post("/api/lyrics/style")
def lyrics_style(req: StyleRequest):
    if any(len(term) > 60 for term in req.vocabulary):
        raise HTTPException(422, "Style terms must be short")
    concept = req.concept.strip()
    if not concept:
        raise HTTPException(422, "Describe a song concept first")
    return _lyrics_call(lambda: get_lyrics_writer().write_style(
        concept, req.title.strip(), req.instrumental, req.vocabulary))


class LyricsRequest(BaseModel):
    concept: str = Field("", max_length=2000)
    style: str = Field("", max_length=4000)
    title: str = Field("", max_length=200)
    mood: str = Field("", max_length=40)
    custom: str = Field("", max_length=500)
    visual: str = Field("", max_length=2000)
    language: str = Field("", max_length=60)
    images: list[str] = Field(default_factory=list)


@app.post("/api/lyrics/generate")
def lyrics_generate(req: LyricsRequest):
    if len(req.images) > MAX_LYRICS_IMAGES:
        raise HTTPException(422, "Choose up to 5 images")
    try:
        images = [validate_image_data_url(image) for image in req.images]
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    if not any(value.strip() for value in (req.concept, req.visual, req.custom)) and not images:
        raise HTTPException(422, "Describe a song concept first")
    fields = req.model_dump(exclude={"images"})
    return _lyrics_call(lambda: get_lyrics_writer().generate(**{k: v.strip() for k, v in fields.items()},
                                                              images=images))


class ModelSetup(BaseModel):
    model_id: str
    precision: str | None = None
    vae_precision: str | None = None
    license_review_id: str
    accept_licenses: bool = False


def start_model_setup(req, download):
    try:
        return get_manager().start(req.model_id, req.precision, req.vae_precision,
                                   req.license_review_id, req.accept_licenses, download)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@app.post("/api/settings/download")
def download_model(req: ModelSetup):
    return start_model_setup(req, True)


@app.post("/api/settings/activate")
def activate_model(req: ModelSetup):
    return start_model_setup(req, False)


@app.post("/api/settings/jobs/{job_id}/cancel")
def cancel_model_setup(job_id: str):
    try:
        get_manager().cancel(job_id)
        return {"ok": True}
    except ValueError as error:
        raise HTTPException(404, str(error)) from error


def _public_job(job):
    return {key: value for key, value in job.items() if not key.startswith("_")}


class VibeImageRequest(BaseModel):
    image: str = Field(..., min_length=1, max_length=14 * 1024 * 1024)
    entry_id: str = Field(..., min_length=1, max_length=80)


class GenerateRequest(GenerationParams):
    variations: int = Field(1, ge=1, le=4)
    vibe_image: str | None = Field(None, max_length=14 * 1024 * 1024)
    vibe_entry_id: str | None = Field(None, max_length=80)
    vibe_images: list[VibeImageRequest] | None = Field(None, min_length=1, max_length=MAX_VIBE_IMAGES)


@app.post("/api/generate")
def api_generate(req: GenerateRequest):
    length_controls = {"target_duration_s", "max_duration_s", "semantic_max_tokens", "analysis_id"}
    supplied_options = req.model_options or {}
    if (any(getattr(req, key, None) is not None for key in length_controls)
            or any(key in supplied_options for key in length_controls)):
        raise HTTPException(422, "Lux chooses the song length automatically from the lyrics and style.")
    variations = getattr(req, "variations", 1)
    params = GenerationParams(**req.model_dump(exclude={"variations", "vibe_image", "vibe_entry_id", "vibe_images"}, exclude_none=True))
    try:
        profile = get_manager().snapshot()
        adapter = get_provider(profile).adapter(profile)
        if params.instrumental and not adapter.capabilities.get("instrumental"):
            raise ValueError("The selected model cannot generate instrumental music")
        params = adapter.normalize(params)
        images = getattr(req, "vibe_images", None)
        artwork = prepare_vibe_artwork(getattr(req, "vibe_image", None), getattr(req, "vibe_entry_id", None),
                                      [image.model_dump() for image in images] if images is not None else None)
    except SetupRequired as error:
        raise HTTPException(409, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {"id": job_id, "kind": "generate", "status": "queued", "created": time.time(),
                    "params": params.model_dump(exclude_none=True), "profile": profile,
                    "variations": variations}
    if artwork:
        jobs[job_id]["_vibe_artwork"] = artwork
    _queue.put(job_id)
    return _public_job(jobs[job_id])


@app.get("/api/jobs")
def api_jobs():
    now = time.time()
    out = sorted(jobs.values(), key=lambda j: j["created"], reverse=True)
    return [{**_public_job(j), "now": now} for j in out]


@app.post("/api/jobs/{job_id}/cancel")
def api_cancel_job(job_id: str):
    with _jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404)
        if job["status"] == "queued":
            job.update(status="cancelled", finished=time.time())
            job.pop("_vibe_artwork", None)
        elif job["status"] == "running" and job["kind"] == "generate" and job_id in _cancels:
            # ponytail: generation only; separation/stem edits run several steps that do not check cancel yet.
            _cancels[job_id].set()
            job["stage"] = "Stopping…"
            get_provider(job["profile"]).cancel(job["profile"])
        else:
            raise HTTPException(409, f"job is {job['status']}")
    return _public_job(job)


@app.delete("/api/jobs/{job_id}")
def api_dismiss_job(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404)
    if job["status"] == "running":
        raise HTTPException(409, "job is running")
    del jobs[job_id]
    return {"ok": True}


def _load_meta(meta: Path) -> dict | None:
    try:
        item = json.loads(meta.read_text())
    except json.JSONDecodeError:
        return None
    changed = False
    if "peaks" not in item:  # songs generated before waveforms existed
        wav = meta.with_suffix(".wav")
        if wav.exists():
            item["peaks"] = engine.compute_peaks(wav)
            changed = True
    if "title" not in item or item["title"] == item["name"]:
        item["title"] = item["params"].get("title") or engine.auto_title(item["params"]["lyrics"])
        changed = True
    if changed:
        meta.write_text(json.dumps(item, indent=2))
    try:
        profile = get_manager().song_profile(item)
        item["can_edit"] = bool(get_provider(profile).adapter(profile).capabilities.get("semantic_edit"))
    except ValueError:
        item["can_edit"] = False
    return item


@app.get("/api/library")
def api_library():
    items = [m for p in engine.OUTPUT_DIR.glob("*.json")
             if not p.name.endswith(".semantic.json") and (m := _load_meta(p))]
    return sorted(items, key=lambda m: m.get("created", ""), reverse=True)


@app.delete("/api/songs/{song}")
def api_delete_song(song: str):
    meta = engine.OUTPUT_DIR / f"{song}.json"
    if not re.fullmatch(r"[\w.-]+", song) or song.startswith(".") or not meta.exists():
        raise HTTPException(404)
    with _jobs_lock:
        if any(j["status"] in {"queued", "running"} and j["params"].get("song") == song for j in jobs.values()):
            raise HTTPException(409, "Wait for this song's stem jobs to finish or stop them first.")
    try:
        names = list(json.loads(meta.read_text()).get("artifacts", {}).values())
    except json.JSONDecodeError:
        names = []
    shutil.rmtree(separate.STEMS_DIR / song, ignore_errors=True)
    # Named files only: a glob on the song name could match another song with a longer name.
    # The metadata goes last, so a failed delete still lists the song for another try.
    for name in [f"{song}.wav", f"{song}.semantic.json", *names, meta.name]:
        if Path(name).name == name:
            (engine.OUTPUT_DIR / name).unlink(missing_ok=True)
    return {"ok": True}


class SeparateRequest(BaseModel):
    song: str = Field(..., pattern=r"^[\w.-]+$")
    mode: str
    prompt: str | None = Field(None, max_length=120)


@app.get("/api/lux/modes")
def lux_modes():
    modes = []
    for mode in separate.MODES.values():
        try:
            get_manager().separator(mode.id)
            ready = True
        except SetupRequired:
            ready = False
        modes.append({"id": mode.id, "label": mode.label, "stems": mode.stems, "prompt": mode.prompt, "ready": ready})
    return modes


@app.post("/api/lux/separate")
def lux_separate(req: SeparateRequest):
    if not (engine.OUTPUT_DIR / f"{req.song}.wav").exists():
        raise HTTPException(404, "song not found")
    mode = separate.MODES.get(req.mode)
    if mode is None:
        raise HTTPException(422, f"unknown mode {req.mode}")
    if mode.prompt and not (req.prompt or "").strip():
        raise HTTPException(422, "describe the sound you want to extract")
    try:
        profile = get_manager().separator(mode.id)
    except SetupRequired as error:
        raise HTTPException(409, str(error)) from error
    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {"id": job_id, "kind": "separate", "status": "queued", "created": time.time(),
                    "params": req.model_dump(exclude_none=True), "profile": profile}
    _queue.put(job_id)
    return jobs[job_id]


class EditRequest(BaseModel):
    song: str = Field(..., pattern=r"^[\w.-]+$")
    start_s: float = Field(..., ge=0)
    end_s: float = Field(..., gt=0)
    seed: int = Field(..., ge=0, lt=2**63)
    lyrics: str | None = None


class StemEditRequest(EditRequest):
    set_id: str = Field(..., pattern=r"^[\w.-]+$")
    stem: str = Field(..., pattern=r"^[\w-]+$")
    variation: Literal["new", "same"] = "new"


@app.post("/api/edit/replace-stem")
def edit_replace_stem(req: StemEditRequest):
    set_meta = separate.STEMS_DIR / req.song / req.set_id / "stems.json"
    if not set_meta.exists():
        raise HTTPException(404, "stem set not found")
    base = json.loads(set_meta.read_text())
    if not any(st["id"] == req.stem for st in base["stems"]):
        raise HTTPException(422, f"no stem {req.stem} in this set")
    duration = _song_duration(req.song)
    if req.end_s - req.start_s < 1 or req.start_s >= duration:
        raise HTTPException(422, "select at least 1 second inside the song")
    try:
        meta = json.loads((engine.OUTPUT_DIR / f"{req.song}.json").read_text())
        profile = get_manager().song_profile(meta)
        if not get_provider(profile).adapter(profile).capabilities.get("semantic_edit"):
            raise ValueError("This song's model does not support section editing")
        sep_profile = get_manager().snapshot(base["model_profile"]) if base.get("model_profile") else get_manager().separator(base["mode"])
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    job_id = uuid.uuid4().hex[:8]
    jobs[job_id] = {"id": job_id, "kind": "stemedit", "status": "queued", "created": time.time(),
                    "params": {**req.model_dump(exclude_none=True), "end_s": min(req.end_s, duration),
                               "mode": base["mode"]}, "profile": profile, "separator_profile": sep_profile}
    _queue.put(job_id)
    return jobs[job_id]


@app.get("/api/export/{song}")
def export_song(song: str, format: Literal["flac", "mp3"]):
    wav = engine.OUTPUT_DIR / f"{song}.wav"
    if "/" in song or song.startswith(".") or not wav.exists():
        raise HTTPException(404)
    return Response(audio.encode(wav, format), media_type=audio.EXPORT_TYPES[format],
                    headers={"Content-Disposition": f'attachment; filename="{song}.{format}"'})


@app.get("/api/beats/{song}")
def song_beats(song: str):
    if "/" in song or song.startswith(".") or not (engine.OUTPUT_DIR / f"{song}.json").exists():
        raise HTTPException(404)
    return edit.beat_grid(song)


@app.get("/api/lux/{song}")
def lux_song(song: str):
    if "/" in song or song.startswith("."):
        raise HTTPException(400)
    return separate.list_stem_sets(song)


engine.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=engine.OUTPUT_DIR), name="outputs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")
