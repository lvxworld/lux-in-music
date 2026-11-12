"""Local SheetSage2 listening trial, isolated from the Lux/Vibe environment.

--prepare --accept-noncommercial-license explicitly downloads pinned artifacts
and installs a separate Python 3.11 runtime. Ordinary analysis is offline and
never installs anything. All transcription artifacts go to ignored outputs.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "config/hook-sheet-model.json"
RUNTIME = ROOT / ".lux/experiments/sheetsage2/.venv"
MODEL_ROOT = ROOT / "models/hook/sheetsage2/b83c3d79a6d98bcffaf8f9ed112c90aa887887bc"
DEFAULT_OUTPUT = ROOT / "outputs/checks/hook-sheet"


@contextmanager
def operation_lock():
    """One preparation/analysis process at a time on the target macOS host."""
    import fcntl
    RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    with (RUNTIME.parent / "operation.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("Another SheetSage2 trial is running. Wait for it to finish.") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def valid_file(path, artifact):
    return (path.is_file() and not path.is_symlink()
            and path.stat().st_size == artifact["size"]
            and sha256(path) == artifact["sha256"])


def verify_models(root, manifest):
    for component in manifest["components"]:
        for artifact in component["files"]:
            if not valid_file(root / component["directory"] / artifact["path"], artifact):
                raise ValueError("SheetSage2 files are missing or changed. Run the explicit preparation command first.")


def prepare(root, manifest, accepted, progress=None):
    if not accepted:
        raise ValueError("Review the SheetSage2 and MERT CC BY-NC 4.0 terms, then pass --accept-noncommercial-license.")
    uv = shutil.which("uv")
    if not uv:
        raise ValueError("Run ./studio.sh once to prepare uv, then retry.")
    completed = 0
    total = sum(f["size"] for c in manifest["components"] for f in c["files"])
    for component in manifest["components"]:
        print(f"{component['repo']} · {component['license']}\n{component['license_url']}", flush=True)
        folder = root / component["directory"]
        folder.mkdir(parents=True, exist_ok=True)
        for artifact in component["files"]:
            path = folder / artifact["path"]
            if valid_file(path, artifact):
                print(f"Verified existing {component['directory']}/{artifact['path']}", flush=True)
                completed += artifact["size"]
                if progress: progress(completed, total)
                continue
            url = f"https://huggingface.co/{component['repo']}/resolve/{component['revision']}/{artifact['path']}"
            partial = path.with_name(path.name + ".part")
            if path.is_symlink() or partial.is_symlink():
                raise ValueError("Model paths must be regular local files.")
            print(f"Downloading {component['directory']}/{artifact['path']}", flush=True)
            try:
                count, last_percent = 0, -1
                with urllib.request.urlopen(url, timeout=90) as response, partial.open("wb") as out:
                    while block := response.read(8 << 20):
                        count += len(block)
                        if count > artifact["size"]:
                            raise ValueError("Downloaded model size differs from the pinned manifest.")
                        out.write(block)
                        percent = min(99, int(count * 100 / artifact["size"]))
                        if percent // 10 > last_percent // 10:
                            print(f"  {percent}%", flush=True)
                            last_percent = percent
                        if progress: progress(completed + count, total)
                if not valid_file(partial, artifact):
                    raise ValueError("Model verification failed; retry preparation.")
                partial.replace(path)
                print("  Verified", flush=True)
                completed += artifact["size"]
                if progress: progress(completed, total)
            finally:
                partial.unlink(missing_ok=True)
    verify_models(root, manifest)
    print("Preparing the isolated SheetSage2 runtime…", flush=True)
    subprocess.run([uv, "venv", "--allow-existing", "--python", "3.11", str(RUNTIME)], check=True)
    subprocess.run([uv, "pip", "sync", "--require-hashes", "--python", str(RUNTIME / "bin/python"),
                    str(ROOT / "config/hook-sheet-runtime.lock")], check=True)
    print("Ready. Analysis now works offline; Lux and Vibe packages were not changed.", flush=True)


def offline_environment():
    env = dict(os.environ)
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
               DO_NOT_TRACK="1", HF_HOME=str(ROOT / ".lux/experiments/sheetsage2/hf-cache"),
               HF_MODULES_CACHE=str(ROOT / ".lux/experiments/sheetsage2/hf-modules"),
               TOKENIZERS_PARALLELISM="false", PYTHONUNBUFFERED="1")
    return env


def render_previews(output, result):
    """Audition predicted MIDI timing, not the original sound or a generated song."""
    import io
    import numpy as np
    import pretty_midi
    import soundfile as sf

    rate = 24000
    parts = dict(result["midis"])
    parts["mix"] = result["midi"]
    counts = {}
    for name in ("mix", "melody_vocal", "melody_instrumental", "chords"):
        if name not in parts:
            continue
        midi = pretty_midi.PrettyMIDI(io.BytesIO(parts[name]))
        count = sum(len(track.notes) for track in midi.instruments)
        counts[name] = count
        if not count:
            continue
        # A simple piano-like harmonic envelope makes notes easier to review
        # than a sustained sine. This is not a sampled-piano quality claim.
        duration = min(95, max(float(result["duration_seconds"]), midi.get_end_time()) + .5)
        wave = np.zeros(round(duration * rate), dtype=np.float32)
        for track in midi.instruments:
            for note in track.notes:
                start, stop = round(note.start * rate), min(len(wave), round((note.end + .12) * rate))
                if stop <= start or start >= len(wave):
                    continue
                t = np.arange(stop - start, dtype=np.float32) / rate
                frequency = 440 * 2 ** ((note.pitch - 69) / 12)
                signal = sum(np.sin(2 * np.pi * frequency * harmonic * t) / harmonic ** 2
                             for harmonic in (1, 2, 3, 4))
                release = np.clip((note.end + .12 - note.start - t) / .12, 0, 1)
                envelope = np.minimum(1, t / .008) * np.exp(-t * 2) * release
                wave[start:stop] += .2 * signal * envelope
        peak = float(np.max(np.abs(wave)))
        if peak:
            wave *= .85 / peak
        sf.write(output / f"{name}-preview.wav", wave, rate)
    return counts


def write_review(output, counts):
    """A local listening page; fixed labels and filenames, no model HTML."""
    tracks = [("reference", "Original excerpt")]
    labels = {"mix": "Transcribed melodies and chords", "melody_vocal": "Vocal melody",
              "melody_instrumental": "Instrumental melody", "chords": "Chords"}
    tracks += [(name + "-preview", labels[name]) for name, count in counts.items() if count]
    cards = "".join(f'<section><h2>{label}</h2><audio controls preload="none" src="{name}.wav"></audio></section>'
                    for name, label in tracks)
    (output / "review.html").write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Lux Hook · SheetSage2 trial</title>
<style>body{background:#10100f;color:#e8e2d7;font:18px system-ui;margin:3rem auto;padding:0 1.5rem;max-width:800px}
h1{font-weight:500}h2{font-size:18px}p{color:#bbb4a8;line-height:1.6}section{border-top:1px solid #34312b;padding:1rem 0}
audio{width:100%}a{color:#deb36f}</style><h1>Hook · SheetSage2 listening trial</h1>
<p>Compare the original with the recognized notes. Previews use a simple synthesized sound; they are not a finished arrangement.
Check the melody and rhythm before using the score in Create.</p>''' + cards + '''
<p>Score: <a href="score.abc">score.abc</a> · Separate MIDI files and timed annotations are in this folder.</p>
<script>document.addEventListener('play',e=>{if(e.target.tagName==='AUDIO')document.querySelectorAll('audio').forEach(a=>{if(a!==e.target)a.pause()})},true)</script></html>''')


def analyze(args, manifest):
    # Offline flags must be set before importing Hugging Face modules.
    os.environ.update(offline_environment())
    import socket
    original_connect = socket.socket.connect

    def local_only(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("Network access is disabled during the SheetSage2 trial.")
        return original_connect(sock, address)

    socket.socket.connect = local_only
    import numpy as np
    import soundfile as sf
    import soxr
    import torch
    from transformers import AutoModel

    if args.audio.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Use a recording no larger than 25 MB.")
    with sf.SoundFile(args.audio) as source:
        if not 8000 <= source.samplerate <= 192000 or not 1 <= source.channels <= 2:
            raise ValueError("Use mono/stereo audio at 8–192 kHz.")
        if not 2 <= source.frames / source.samplerate <= 90:
            raise ValueError("Use a recording between 2 and 90 seconds.")
        end = min(source.frames / source.samplerate, args.start + args.seconds) if args.seconds else source.frames / source.samplerate
        if args.start < 0 or end - args.start < 2:
            raise ValueError("Select at least two seconds inside the recording.")
        source.seek(round(args.start * source.samplerate))
        samples = source.read(round((end - args.start) * source.samplerate), dtype="float32", always_2d=True)
        audio = soxr.resample(samples.mean(axis=1), source.samplerate, 24000).astype(np.float32)
    if not np.isfinite(audio).all() or np.max(np.abs(audio)) < .001:
        raise ValueError("Use finite, audible audio samples.")
    torch.set_num_threads(min(6, os.cpu_count() or 1))
    device = args.device
    if device == "auto":
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Loading verified local SheetSage2 + MERT, FP32, {device}…", flush=True)
    model = AutoModel.from_pretrained(str(args.model_dir / "sheet"), trust_remote_code=True,
                                      base_model_path=str(args.model_dir / "mert"),
                                      local_files_only=True, torch_dtype=torch.float32).eval().to(device)
    args.output.mkdir(parents=True, exist_ok=True)
    sf.write(args.output / "reference.wav", audio, 24000)

    def progress(info):
        text = info["stage"]
        if "tokens" in info:
            text += f" · {info['tokens']} tokens"
        print(text, flush=True)

    try:
        result = model.transcribe(audio, sampling_rate=24000, output_dir=args.output,
                                  dtype="fp32", progress=progress, melody_only=args.melody_only)
    except (RuntimeError, NotImplementedError) as error:
        if args.device != "auto" or device != "mps" or not any(
                term in str(error).lower() for term in ("mps", "metal", "not implemented")):
            raise
        print("Metal could not complete this operation. Retrying on CPU…", flush=True)
        # Release failed inference activations retained by the traceback before
        # allocating the retry, especially after Metal memory pressure.
        import gc
        error.__traceback__ = None
        model.to("cpu")
        gc.collect()
        torch.mps.empty_cache()
        device = "cpu"
        result = model.transcribe(audio, sampling_rate=24000, output_dir=args.output,
                                  dtype="fp32", progress=progress, melody_only=args.melody_only)
    counts = render_previews(args.output, result)
    if not args.melody_only and result.get("abc"):
        # Rebuild the cover score from the same predictions, without a second
        # model pass. Keep the full harmonic transcription available as well.
        import importlib
        notation = importlib.import_module(model.__class__.__module__.rsplit(".", 1)[0] + ".notation_sheetsage2")
        cover, _, _ = notation.generate_abc_from_exports(args.output / "notation/song_melody.mid", melody_only=True)
        (args.output / "melody-only.abc").write_text(cover)
    write_review(args.output, counts)
    score_status = {"compatible": False}
    try:
        sys.path.insert(0, str(ROOT))
        from studio.adapters.yue2_score import inspect
        score = inspect(result.get("abc") or "")
        score_status = {"compatible": True, "bpm": score.bpm, "bars": len(score.bars),
                        "duration_s": round(score.duration_s, 2)}
    except ValueError:
        score_status["reason"] = "The current Lux duration checker does not accept this score. Do not generate from it yet."
    summary = {"model": "m-a-p/SheetSage2", "revision": manifest["components"][0]["revision"],
               "device": device, "precision": "FP32", "duration_s": round(len(audio) / 24000, 2),
               "notes_by_part": counts, "lux_score": score_status,
               "listening_verified": False, "melody_only": args.melody_only}
    (args.output / "lux-review.json").write_text(json.dumps(summary, indent=2) + "\n")
    if args.worker:
        import io
        import pretty_midi
        melody_score = args.output / "melody-only.abc"
        abc = melody_score.read_text() if melody_score.is_file() else result.get("abc")
        melody_midi = result.get("midis", {}).get("melody_instrumental")
        if not melody_midi or not abc:
            raise ValueError("SheetSage2 did not return a compatible instrumental melody score.")
        midi = pretty_midi.PrettyMIDI(io.BytesIO(melody_midi))
        notes = [{"pitch": int(note.pitch), "start_s": float(note.start), "end_s": float(note.end)}
                 for instrument in midi.instruments for note in instrument.notes]
        notes.sort(key=lambda note: (note["start_s"], note["end_s"], note["pitch"]))
        from studio.adapters.yue2_score import inspect
        score = inspect(abc)
        (args.output / "hook-result.json").write_text(json.dumps(
            {"abc": abc, "notes": notes, "bpm": score.bpm}, separators=(",", ":")))
    print(json.dumps(summary, indent=2), flush=True)
    print("Listen to the previews before using the score. No song was generated.", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--accept-noncommercial-license", action="store_true")
    parser.add_argument("--model-dir", type=Path, default=MODEL_ROOT)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start", type=float, default=0)
    parser.add_argument("--seconds", type=float)
    parser.add_argument("--device", choices=("auto", "mps", "cpu"), default="auto")
    parser.add_argument("--melody-only", action="store_true", help="Omit chords from ABC/playback, as recommended for YuE2 covers")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    args.model_dir, args.output = args.model_dir.resolve(), args.output.resolve()
    if args.audio:
        args.audio = args.audio.resolve()
    manifest = json.loads(MANIFEST_PATH.read_text())
    try:
        with nullcontext() if args.worker else operation_lock():
            if args.prepare:
                prepare(args.model_dir, manifest, args.accept_noncommercial_license)
                return 0
            if not args.audio:
                parser.error("Choose --audio for analysis, or --prepare for explicit installation.")
            if not math.isfinite(args.start) or args.seconds is not None and (not math.isfinite(args.seconds) or args.seconds < 2):
                raise ValueError("Use a finite start time and at least two seconds.")
            # Keep score/audio artifacts outside tracked source, including for custom output paths.
            output = args.output.resolve()
            if not args.worker and not output.is_relative_to((ROOT / "outputs").resolve()):
                raise ValueError("Keep trial results inside the ignored outputs directory.")
            verify_models(args.model_dir, manifest)
            if args.worker:
                analyze(args, manifest)
                return 0
            python = RUNTIME / "bin/python"
            if not python.is_file():
                raise ValueError("Prepare the isolated SheetSage2 runtime first. Analysis never installs packages or weights.")
            command = [str(python), str(Path(__file__).resolve()), "--worker", "--audio", str(args.audio),
                       "--model-dir", str(args.model_dir), "--output", str(args.output),
                       "--device", args.device, "--start", str(args.start)]
            if args.seconds is not None:
                command += ["--seconds", str(args.seconds)]
            if args.melody_only:
                command.append("--melody-only")
            return subprocess.run(command, env=offline_environment(), cwd=ROOT, timeout=1800).returncode
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"SheetSage2 trial: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
