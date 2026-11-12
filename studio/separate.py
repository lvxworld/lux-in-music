"""Lux Studio: stem separation through the audio.cpp separator models."""

import base64
import io
import json
import re
import shutil
import time
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soxr

from . import engine
from .models import get_manager
from .providers import get_provider

STEMS_DIR = engine.OUTPUT_DIR / "stems"


@dataclass(frozen=True)
class Mode:
    id: str
    model: str
    sample_rate: int
    label: str
    stems: tuple[str, ...]
    prompt: bool = False


MODES = {
    m.id: m for m in [
        Mode("vocals", "sep-vocals", 44100, "Vocals / Instrumental", ("vocals", "instrumental")),
        Mode("4stems", "sep-4stems", 44100, "4 stems", ("vocals", "drums", "bass", "other")),
        Mode("6stems", "sep-6stems", 44100, "6 stems", ("vocals", "drums", "bass", "guitar", "piano", "other")),
        Mode("anything", "sep-anything", 48000, "Anything you describe", ("target", "residual"), prompt=True),
    ]
}


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    return pcm.reshape(-1, ch).astype(np.float32) / 32768.0, sr


def _wav_bytes(x: np.ndarray, sr: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(x.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


SILENT_DB = -60.0  # below this RMS a stem is treated as "not detected"


def stem_levels(path: Path) -> dict:
    x, _ = _read_wav(path)
    rms = float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))) if x.size else 0.0
    rms_db = round(float(20 * np.log10(max(rms, 1e-9))), 1)
    return {"peaks": engine.compute_peaks(path, 240, normalize=False), "rms_db": rms_db, "silent": bool(rms_db < SILENT_DB)}


def stem_set_dir(song: str, mode: str, prompt: str | None) -> Path:
    suffix = f"-{engine.slugify(prompt)}" if prompt else ""
    return STEMS_DIR / song / f"{mode}{suffix}"


def separate_audio(audio: np.ndarray, sr: int, mode: Mode, prompt: str | None, profile=None) -> tuple[list[dict], float]:
    """Run a separator on an in-memory clip; returns [{id, audio, sr}] in the mode's stem order."""
    profile = get_manager().snapshot(profile) if profile else get_manager().separator(mode.id)
    # Keep the mode rate as a migration fallback for profiles saved before this field.
    audio_format = profile.get("input_audio", {})
    sample_rate = audio_format.get("sample_rate", mode.sample_rate)
    channels = audio_format.get("channels", audio.shape[1])
    if sr != sample_rate:
        audio = soxr.resample(audio, sr, sample_rate, quality="VHQ")
    if channels == 1 and audio.shape[1] != 1:
        audio = audio.mean(axis=1, keepdims=True)
    elif channels == 2 and audio.shape[1] == 1:
        audio = np.repeat(audio, 2, axis=1)
    request: dict = {"audio_base64": base64.b64encode(_wav_bytes(audio, sample_rate)).decode()}
    if mode.prompt:
        request.update(text=prompt.strip(), seed=42)
    t0 = time.time()
    outputs = get_provider(profile).run(profile, request).get("named_audio_outputs") or []
    if not outputs:
        raise RuntimeError("separator returned no stems")
    order = {name: i for i, name in enumerate(mode.stems)}
    stems = []
    for o in sorted(outputs, key=lambda o: order.get(o["id"], 99)):
        x, osr = _read_wav_bytes(base64.b64decode(o["audio"]))
        stems.append({"id": o["id"], "audio": x, "sr": osr})
    return stems, time.time() - t0


def _read_wav_bytes(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    return pcm.reshape(-1, ch).astype(np.float32) / 32768.0, sr


def _stem_label(mode: Mode, stem_id: str, prompt: str | None) -> str:
    if mode.prompt:
        return prompt.strip() if stem_id == "target" else "everything else"
    return stem_id


def separate(song: str, mode_id: str, prompt: str | None = None, profile=None) -> dict:
    mode = MODES[mode_id]
    src = engine.OUTPUT_DIR / f"{song}.wav"
    if not src.exists():
        raise FileNotFoundError(song)
    if mode.prompt and not (prompt and prompt.strip()):
        raise ValueError("describe the sound to extract")

    audio, sr = _read_wav(src)
    profile = get_manager().snapshot(profile) if profile else get_manager().separator(mode_id)
    outputs, elapsed = separate_audio(audio, sr, mode, prompt, profile)

    out_dir = stem_set_dir(song, mode_id, prompt if mode.prompt else None)
    out_dir.mkdir(parents=True, exist_ok=True)
    stems = []
    for o in outputs:
        path = out_dir / f"{re.sub(r'[^a-z0-9_-]', '', o['id'].lower())}.wav"
        path.write_bytes(_wav_bytes(o["audio"], o["sr"]))
        stems.append({"id": o["id"], "label": _stem_label(mode, o["id"], prompt),
                      "file": path.relative_to(engine.OUTPUT_DIR).as_posix(), **stem_levels(path)})

    meta = {
        "song": song, "mode": mode_id, "mode_label": mode.label, "prompt": prompt if mode.prompt else None,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "elapsed_s": round(elapsed, 1), "stems": stems,
        "model_profile": profile,
    }
    (out_dir / "stems.json").write_text(json.dumps(meta, indent=2))
    meta["id"] = out_dir.name
    return meta


MARGIN_S = 3.0  # context around the selection given to the separator


def replace_stem(song: str, set_id: str, stem_id: str, start_s: float, end_s: float, seed: int,
                 lyrics: str | None = None, variation: str = "new", profile=None,
                 separator_profile=None, direction: str | None = None) -> dict:
    """Regenerate [start_s, end_s) of one stem: new take of the song, separated, only that stem swapped in."""
    from . import edit  # local import: edit imports engine only, no cycle at module load

    base_dir = STEMS_DIR / song / set_id
    base = json.loads((base_dir / "stems.json").read_text())
    mode = MODES[base["mode"]]
    target = next((st for st in base["stems"] if st["id"] == stem_id), None)
    if target is None:
        raise ValueError(f"no stem {stem_id} in this set")

    t0 = time.time()
    take, info = edit.render_section(song, start_s, end_s, seed, lyrics, variation, profile,
                                     direction=direction)   # 48 kHz composite
    a_s, b_s = info["start_s"], info["end_s"]
    sample_rate = info["sample_rate"]
    lo = max(0.0, a_s - MARGIN_S)
    hi = min(len(take) / sample_rate, b_s + MARGIN_S)
    clip = take[int(lo * sample_rate):int(hi * sample_rate)]
    separator_profile = separator_profile or (get_manager().snapshot(base["model_profile"]) if base.get("model_profile") else get_manager().separator(mode.id))
    outputs, _ = separate_audio(clip, sample_rate, mode, base.get("prompt"), separator_profile)
    new = next((o for o in outputs if o["id"] == stem_id), None)
    if new is None:
        raise RuntimeError(f"separator did not return {stem_id}")

    orig, sr = _read_wav(engine.OUTPUT_DIR / target["file"])
    if new["sr"] != sr:
        new["audio"] = soxr.resample(new["audio"], new["sr"], sr, quality="VHQ")
    placed = orig.copy()
    off = int(lo * sr)
    seg = new["audio"][:max(0, len(orig) - off)]
    if seg.shape[1] != orig.shape[1]:
        seg = np.repeat(seg[:, :1], orig.shape[1], axis=1)
    placed[off:off + len(seg)] = seg
    edited = edit.crossfade_region(orig, placed, int(a_s * sr), int(b_s * sr), int(edit.XFADE_S * sr))

    out_dir = STEMS_DIR / song / f"{base['mode']}-take-{time.strftime('%Y%m%d-%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    stems = []
    for st in base["stems"]:
        path = out_dir / Path(st["file"]).name
        if st["id"] == stem_id:
            path.write_bytes(_wav_bytes(edited, sr))
            stems.append({**st, "file": path.relative_to(engine.OUTPUT_DIR).as_posix(), **stem_levels(path)})
        else:
            shutil.copyfile(engine.OUTPUT_DIR / st["file"], path)
            stems.append({**st, "file": path.relative_to(engine.OUTPUT_DIR).as_posix()})
    meta = {
        **{k: base[k] for k in ("song", "mode", "mode_label", "prompt")},
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "elapsed_s": round(time.time() - t0, 1), "stems": stems,
        "base": set_id, "model_profile": separator_profile,
        "edit": {"stem": stem_id, "label": target["label"], "start_s": a_s, "end_s": b_s, "seed": info["seed"],
                 "variation": variation,
                 "direction": info["direction"],
                 "new_lyrics": info["lyrics"] != info["meta"]["params"]["lyrics"]},
    }
    (out_dir / "stems.json").write_text(json.dumps(meta, indent=2))
    meta["id"] = out_dir.name
    return meta


def list_stem_sets(song: str) -> list[dict]:
    sets = []
    for meta in (STEMS_DIR / song).glob("*/stems.json"):
        try:
            item = json.loads(meta.read_text())
        except json.JSONDecodeError:
            continue
        if any("rms_db" not in st for st in item["stems"]):  # sets made before absolute levels
            for st in item["stems"]:
                st.update(stem_levels(engine.OUTPUT_DIR / st["file"]))
            meta.write_text(json.dumps(item, indent=2))
        item["id"] = meta.parent.name
        sets.append(item)
    return sorted(sets, key=lambda s: s["created"], reverse=True)
