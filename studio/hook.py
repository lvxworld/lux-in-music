"""Explicit local SheetSage2 setup and offline melody transcription for Hook."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time

import numpy as np
import soundfile as sf

from .providers import ROOT

MANIFEST_PATH = ROOT / "config/hook-sheet-model.json"
MANIFEST = json.loads(MANIFEST_PATH.read_text())
MODEL = MANIFEST["components"][0]
MODEL_REVISION = MODEL["revision"]
REVIEW_ID = hashlib.sha256(json.dumps(MANIFEST, sort_keys=True).encode()).hexdigest()
RUNTIME_ID = hashlib.sha256((ROOT / "config/hook-sheet-runtime.lock").read_bytes()).hexdigest()
MODEL_ROOT = ROOT / "models/hook/sheetsage2" / MODEL_REVISION
RUNTIME = ROOT / ".lux/experiments/sheetsage2/.venv"
TRIAL_SCRIPT = ROOT / "scripts/check_hook_sheet.py"
MAX_BYTES = 25 * 1024 * 1024
MAX_SECONDS = 90


class HookUnavailable(RuntimeError):
    pass


class HookBusy(RuntimeError):
    pass


def runtime_ready():
    python = RUNTIME / "bin/python"
    site_dirs = list((RUNTIME / "lib").glob("python*/site-packages"))
    return python.is_file() and bool(site_dirs) and all(
        any((site / package).exists() for site in site_dirs)
        for package in ("torch", "transformers", "pretty_midi"))


def validate_audio(data: bytes):
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Choose an audio file no larger than 25 MB.")
    try:
        with sf.SoundFile(io.BytesIO(data)) as source:
            if source.format not in {"WAV", "WAVEX", "FLAC", "OGG", "AIFF", "MP3"}:
                raise ValueError("Use WAV, FLAC, MP3, OGG or AIFF, or record in Hook.")
            rate, channels, duration = source.samplerate, source.channels, source.frames / source.samplerate
            if not 8000 <= rate <= 192000 or not 1 <= channels <= 2:
                raise ValueError("Use mono or stereo audio with a sample rate from 8 to 192 kHz.")
            if not 2 <= duration <= MAX_SECONDS:
                raise ValueError("Choose a recording between 2 and 90 seconds long.")
            audio = source.read(dtype="float32", always_2d=True)
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("This file could not be read as audio. Try WAV or record directly in Hook.") from error
    if not audio.size or not np.isfinite(audio).all() or float(np.max(np.abs(audio))) < .001:
        raise ValueError("The recording is silent or contains invalid audio samples.")
    return audio, rate


class HookManager:
    def __init__(self, root=None):
        self.model_root = Path(root) if root else MODEL_ROOT
        # The verified marker lives beside, rather than inside, downloaded sources.
        self.state_path = self.model_root.parent / "verified.json"
        self.lock = threading.Lock()
        self.analysis_lock = threading.Lock()
        self.job = None

    def status(self):
        try:
            state = json.loads(self.state_path.read_text())
            accepted = state.get("review_id") == REVIEW_ID
        except (OSError, ValueError):
            state, accepted = {}, False
        files_present = all((self.model_root / c["directory"] / f["path"]).is_file()
                            for c in MANIFEST["components"] for f in c["files"])
        ready_runtime = runtime_ready()
        return {"id": "sheetsage2", "name": "SheetSage2", "revision": MODEL_REVISION,
                "model_url": "https://huggingface.co/m-a-p/SheetSage2/tree/" + MODEL_REVISION,
                "licenses": [{"component": c["repo"] + " weights", "id": c["license"],
                              "url": c["license_url"], "summary": "Noncommercial use only. Review the full terms."}
                             for c in MANIFEST["components"]],
                "license_review_id": REVIEW_ID, "license_accepted": accepted,
                "files_verified": accepted and files_present,
                "installed": accepted and state.get("runtime_id") == RUNTIME_ID and files_present and ready_runtime,
                "runtime_ready": ready_runtime, "busy": self.analysis_lock.locked(),
                "total_bytes": sum(f["size"] for c in MANIFEST["components"] for f in c["files"]),
                "job": dict(self.job) if self.job else None}

    def start_install(self, review_id, accepted):
        if review_id != REVIEW_ID or not accepted:
            raise ValueError("Review and accept the SheetSage2 and MERT CC BY-NC 4.0 terms before setup.")
        with self.lock:
            if self.analysis_lock.locked():
                raise HookBusy("Wait for melody analysis to finish before repairing Hook.")
            if self.job and self.job["status"] in {"queued", "running"}:
                return dict(self.job)
            total = sum(f["size"] for c in MANIFEST["components"] for f in c["files"])
            self.job = {"status": "queued", "stage": "queued", "completed_bytes": 0, "total_bytes": total}
            threading.Thread(target=self._install, args=(self.job,), daemon=True).start()
            return dict(self.job)

    def _install(self, job):
        try:
            from scripts.check_hook_sheet import prepare
            job.update(status="running", stage="downloading")
            def prepared_progress(done, total):
                job.update(completed_bytes=done)
            prepare(self.model_root, MANIFEST, True, progress=prepared_progress)
            job.update(stage="verifying", completed_bytes=job["total_bytes"])
            if not runtime_ready():
                raise HookUnavailable("The isolated SheetSage2 runtime is incomplete. Use Verify / repair Hook to retry.")
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.state_path.with_suffix(".tmp")
            temp.write_text(json.dumps({"review_id": REVIEW_ID, "revision": MODEL_REVISION,
                                        "runtime": str(RUNTIME.relative_to(ROOT)), "runtime_id": RUNTIME_ID}))
            temp.replace(self.state_path)
            job.update(status="done", stage="done")
        except Exception as error:
            job.update(status="error", error=str(error) if isinstance(error, HookUnavailable)
                       else "Hook setup failed. Check network access and disk space, then use Verify / repair Hook.")

    def analyze(self, data, start_s=0., end_s=None, bpm=0):
        if not self.analysis_lock.acquire(blocking=False):
            raise HookBusy("Hook is already analyzing a recording. Wait for it to finish.")
        try:
            if isinstance(bpm, bool) or not isinstance(bpm, int) or bpm != 0 and not 40 <= bpm <= 240:
                raise ValueError("Set the recording tempo from 40 to 240 BPM, or use Auto.")
            if self.job and self.job["status"] in {"queued", "running"}:
                raise HookUnavailable("Hook is still being installed. Wait for Settings to show Installed · Verified.")
            if not self.status()["installed"]:
                raise HookUnavailable("Prepare SheetSage2 in Settings first. Missing or changed files can be repaired there.")
            audio, rate = validate_audio(data)
            duration = len(audio) / rate
            end_s = duration if end_s is None else end_s
            if not all(math.isfinite(v) for v in (start_s, end_s)) or not 0 <= start_s < end_s <= duration + .01 or end_s - start_s < 2:
                raise ValueError("Select at least 2 seconds within the recording.")
            audio = audio[round(start_s * rate):round(end_s * rate)]
            if not runtime_ready():
                raise HookUnavailable("The SheetSage2 runtime needs repair. Use Settings, then restart Lux if requested.")
            started = time.monotonic()
            # Keep the user's recording and all intermediate transcription files transient.
            with tempfile.TemporaryDirectory(prefix="lux-hook-") as folder:
                folder = Path(folder)
                input_path, output_path = folder / "input.wav", folder / "result"
                sf.write(input_path, audio, rate, subtype="PCM_16")
                output_path.mkdir()
                command = [str(RUNTIME / "bin/python"), str(TRIAL_SCRIPT), "--worker", "--audio", str(input_path),
                           "--model-dir", str(self.model_root), "--output", str(output_path),
                           "--device", "auto", "--start", "0"]
                from scripts.check_hook_sheet import offline_environment
                result = subprocess.run(command, cwd=ROOT, env=offline_environment(), capture_output=True,
                                        text=True, timeout=1800)
                if result.returncode:
                    raise HookUnavailable("Local SheetSage2 analysis failed. Verify / repair Hook in Settings, then retry.")
                response = json.loads((output_path / "hook-result.json").read_text())
            from .adapters.yue2_hook import HookMelody
            selected_bpm = bpm or int(response["bpm"])
            abc = response["abc"]
            notes = response["notes"]
            if not notes:
                raise ValueError("No melody was detected. Try a clearer or louder recording, or select another part.")
            if len(notes) > 512:
                raise ValueError("The melody has too many notes. Select a shorter part of the recording.")
            if selected_bpm != int(response["bpm"]):
                # The score rhythm was quantised at the detected tempo; the notes below follow the chosen one.
                abc = None
            # Model note times are seconds. Keep onset/duration while mapping them to the selected musical grid.
            origin = notes[0]["start_s"]
            last = notes[-1]["end_s"]
            beats = max(.25, (last - origin) * selected_bpm / 60)
            try:
                melody = HookMelody(version=1, bpm=selected_bpm, beats=beats, source="recording",
                                    model_id="sheetsage2", model_revision=MODEL_REVISION,
                                    score_abc=abc,
                                    notes=[{"pitch": int(n["pitch"]),
                                            "start": (n["start_s"] - origin) * selected_bpm / 60,
                                            "end": (n["end_s"] - origin) * selected_bpm / 60}
                                           for n in notes])
            except ValueError as error:
                raise ValueError("The detected melody could not be used. Try a clearer single-voice part.") from error
            return {"melody": melody.model_dump(), "abc": abc, "notes": notes,
                    "warnings": [], "bpm": selected_bpm, "tempo_estimated": not bool(bpm),
                    "duration_s": round(end_s - start_s, 2), "model_id": "sheetsage2",
                    "revision": MODEL_REVISION, "elapsed_s": round(time.monotonic() - started, 2),
                    "message": "Review the melody and tempo. SheetSage2 analyzed the recording locally; Create uses its melody-only score to guide a new performance."}
        finally:
            self.analysis_lock.release()

    def release(self):
        # The isolated inference process exits after every analysis and releases its memory.
        return None


_manager = None
_manager_lock = threading.Lock()


def get_hook_manager():
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = HookManager()
    return _manager
