"""Isolated browser fixture: tiny files and a fake provider, never real weights."""

import argparse
import time
import copy
import base64
import json
import threading
from unittest.mock import patch

from tests.test_models import ModelFixtures, tiny_audio


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    fixture = ModelFixtures(); fixture.setUp()
    from studio.hook import MANIFEST, REVIEW_ID
    from studio.adapters.yue2_hook import HookMelody, reference_score
    class FakeHookManager:
        def __init__(self):
            self.analysis_lock = threading.Lock(); self.job = None; self.installed = False
        def status(self):
            return {"id": "sheetsage2", "name": "SheetSage2", "revision": MANIFEST["components"][0]["revision"],
                "model_url": "https://huggingface.co/m-a-p/SheetSage2", "licenses": [
                    {"component": c["repo"] + " weights", "id": c["license"], "url": c["license_url"],
                     "summary": "Noncommercial use only. Review the full terms."} for c in MANIFEST["components"]],
                "license_review_id": REVIEW_ID, "license_accepted": self.installed,
                "files_verified": self.installed, "installed": self.installed, "runtime_ready": self.installed,
                "busy": self.analysis_lock.locked(), "total_bytes": 2_760_000_000, "job": self.job}
        def start_install(self, review_id, accepted):
            self.installed = bool(accepted and review_id == REVIEW_ID)
            self.job = {"status": "done", "stage": "done", "completed_bytes": 1, "total_bytes": 1}
            return self.job
        def analyze(self, data, start_s=0, end_s=None, bpm=0):
            melody = HookMelody(bpm=120, beats=8, model_id="sheetsage2", model_revision=MANIFEST["components"][0]["revision"],
                notes=[{"pitch": pitch, "start": start, "end": start + .75}
                       for pitch, start in ((60, 0), (64, 1), (67, 2), (72, 3))],
                score_abc="X:1\\nT:\\nM:4/4\\nL:1/16\\nQ:1/4=120\\nV: Vocal clef=treble name=\\\"Vocal\\\"\\nV: Ins clef=treble name=\\\"Inst.\\\"\\nK:C\\nV: Vocal\\nz16|z16|\\nV: Ins\\nC4 D4 E4 G4|G4 E4 D4 C4|\\n")
            return {"melody": melody.model_dump(), "abc": melody.score_abc,
                "notes": [{"pitch": n.pitch, "start_s": n.start / 2, "end_s": n.end / 2} for n in melody.notes],
                "warnings": [], "bpm": 120, "tempo_estimated": not bool(bpm), "duration_s": 4,
                "model_id": "sheetsage2", "revision": melody.model_revision, "elapsed_s": .1,
                "message": "SheetSage2 analyzed the recording locally."}
        def release(self): pass
    hook_patch = patch("studio.hook._manager", FakeHookManager())
    hook_patch.start(); fixture.addCleanup(hook_patch.stop)
    from studio.vibe import VibeManager
    vibe = VibeManager(fixture.root / "vibe-models")
    vibe.state_path = fixture.root / "vibe-state.json"
    vibe_patch = patch("studio.vibe._manager", vibe)
    vibe_patch.start(); fixture.addCleanup(vibe_patch.stop)
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
        result.capabilities = {**result.capabilities, "semantic_edit": True, "hook": True,
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
