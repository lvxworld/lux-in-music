"""Isolated browser fixture: tiny files and a fake provider, never real weights."""

import argparse
import time
import copy
import base64
import json
from unittest.mock import patch

from tests.test_models import ModelFixtures, tiny_audio


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    fixture = ModelFixtures(); fixture.setUp()
    from studio.vibe import VibeManager
    vibe = VibeManager(fixture.root / "vibe-models")
    vibe.state_path = fixture.root / "vibe-state.json"
    vibe_patch = patch("studio.vibe._manager", vibe)
    vibe_patch.start(); fixture.addCleanup(vibe_patch.stop)
    from studio.lyrics import LyricsWriter
    import httpx
    offline = httpx.MockTransport(lambda request: httpx.Response(404))  # Discovery must not probe real ports.
    lyrics_patch = patch("studio.lyrics._writer", LyricsWriter(fixture.root / "lyrics-state",
                                                               client=lambda: httpx.Client(transport=offline)))
    lyrics_patch.start(); fixture.addCleanup(lyrics_patch.stop)
    fixture.catalog[0]["licenses"].append({"component": "Output permission", "id": "Creator terms",
        "url": "https://licenses.test/creator", "summary": "Individual creators may monetize outputs; company use needs a separate license.", "verified": True})
    external = copy.deepcopy(fixture.catalog[0])
    external.update(id="test-external", name="Test external", delivery="external", precisions={}, vaes={}, required=[], default_precision=None, default_vae=None)
    fixture.manager.catalog[external["id"]] = external
    separator = copy.deepcopy(fixture.catalog[0])
    separator.update(id="test-separator", name="Test separator", task="sep", mode_id="vocals",
                     install_dir="test-separator", vaes={}, default_vae=None)
    fixture.manager.catalog[separator["id"]] = separator
    original_adapter = fixture.provider.adapter
    def adapter(profile):
        result = original_adapter(profile)
        result.capabilities = {**result.capabilities, "semantic_edit": True,
            "options": ["semantic_temperature", "semantic_top_p", "semantic_top_k", "num_inference_steps"]}
        return result
    fixture.provider.adapter = adapter
    from studio import engine
    wav = base64.b64decode(tiny_audio())
    (engine.OUTPUT_DIR / "legacy-song.wav").write_bytes(wav)
    (engine.OUTPUT_DIR / "legacy-song.json").write_text(json.dumps({"name": "legacy-song", "title": "Legacy song",
        "created": "2026-10-01", "params": {"lyrics": "Legacy song", "style": "Piano", "cot": "off"},
        "duration_s": 0.1, "peaks": [0.1] * 16}))
    stems = engine.OUTPUT_DIR / "ui-stems"; stems.mkdir()
    for name in ("vocals", "instrumental"): (stems / f"{name}.wav").write_bytes(wav)
    original_probe = fixture.provider.probe
    def probe(profile, cancel=None):
        time.sleep(1.2)
        if profile["model_id"] == "test-separator" and profile["precision"] == "bf16":
            raise RuntimeError("Test device does not support this precision")
        return original_probe(profile, cancel)
    fixture.provider.probe = probe
    from studio.app import app
    import uvicorn
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        fixture.doCleanups()


if __name__ == "__main__": main()
