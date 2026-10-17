"""Store the analyzed Hook excerpt as a local song artifact."""

import base64
import binascii
import json
from pathlib import Path

from .hook import validate_audio

MAX_REFERENCE_BYTES = 12 * 1024 * 1024


def prepare_hook_reference(encoded: str | None, melody) -> dict | None:
    if encoded is None:
        return None
    if melody is None:
        raise ValueError("Hook reference audio requires a Hook melody.")
    try:
        audio = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("The Hook reference audio is not valid base64 audio.") from error
    if not audio or len(audio) > MAX_REFERENCE_BYTES:
        raise ValueError("The analyzed Hook excerpt is too large to save with the song.")
    samples, rate = validate_audio(audio)
    melody = melody.model_dump() if hasattr(melody, "model_dump") else melody
    return {
        "audio": audio,
        "info": {
            "source": "recording",
            "mode": melody["mode"],
            "target": melody["target"],
            "bpm": melody["bpm"],
            "duration_s": round(len(samples) / rate, 2),
        },
    }


def attach_hook_reference(meta_path: Path, reference: dict) -> None:
    """Attach the selected analyzed excerpt and Hook choices to a generated song."""
    metadata = json.loads(meta_path.read_text())
    path = meta_path.with_suffix(".hook-reference.wav")
    path.write_bytes(reference["audio"])
    metadata.setdefault("artifacts", {})["hook_reference_audio"] = path.name
    metadata["hook_reference"] = reference["info"]
    meta_path.write_text(json.dumps(metadata, indent=2))
