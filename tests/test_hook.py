"""Hook boundary checks with synthetic audio and a fake transcription worker."""

import io
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf

from studio import hook
from studio.adapters.yue2_hook import HookMelody, _bars, reference_score
from studio.adapters.yue2_score import ScoreError


def tone(format="WAV", seconds=3, rate=16000):
    out = io.BytesIO()
    wave = (.3 * np.sin(2 * np.pi * 440 * np.arange(seconds * rate) / rate)).astype("float32")
    sf.write(out, wave, rate, format=format)
    return out.getvalue()


def melody(notes, beats):
    return HookMelody(bpm=120, beats=beats, notes=notes)


class ValidateAudioTests(unittest.TestCase):
    def test_accepts_each_listed_format(self):
        for name in ("WAV", "FLAC", "OGG", "MP3"):
            if name not in sf.available_formats():
                continue
            with self.subTest(name):
                audio, rate = hook.validate_audio(tone(name))
                self.assertEqual(rate, 16000)
                self.assertGreater(len(audio), 0)


class BarsTests(unittest.TestCase):
    def test_short_final_note_is_kept_not_rejected(self):
        # 19.2 beats squeezed into 2 bars of 16 units: the last note starts at the grid end.
        notes = [{"pitch": 60, "start": i * .96, "end": i * .96 + .96} for i in range(19)]
        notes.append({"pitch": 62, "start": 19.0, "end": 19.2})
        bars = _bars(melody(notes, 19.2), 2, 16, 4)
        self.assertIn(" ", bars[1])
        self.assertTrue(bars[1].rstrip("-").split()[-1].startswith("=D"))

    def test_no_room_left_still_fails_in_plain_english(self):
        notes = [{"pitch": 60 + i, "start": i / 100, "end": (i + 1) / 100} for i in range(40)]
        with self.assertRaisesRegex(ScoreError, "too many notes"):
            _bars(melody(notes, .4), 1, 16, 4)

    def test_reference_score_is_valid_for_a_single_note(self):
        reference_score(melody([{"pitch": 60, "start": 0, "end": 1}], 1))


class AnalyzeTests(unittest.TestCase):
    def analyze(self, result, bpm=0):
        manager = hook.HookManager()

        def fake_run(command, **kwargs):
            (Path(command[command.index("--output") + 1]) / "hook-result.json").write_text(json.dumps(result))
            return types.SimpleNamespace(returncode=0)

        with patch.object(hook.HookManager, "status", return_value={"installed": True}), \
                patch.object(hook, "runtime_ready", return_value=True), \
                patch("subprocess.run", side_effect=fake_run):
            return manager.analyze(tone(), bpm=bpm)

    def test_no_detected_notes_is_a_plain_error(self):
        with self.assertRaisesRegex(ValueError, "No melody"):
            self.analyze({"abc": "", "notes": [], "bpm": 120})

    def test_too_many_notes_is_a_plain_error(self):
        notes = [{"pitch": 60, "start_s": i * .01, "end_s": i * .01 + .005} for i in range(513)]
        with self.assertRaisesRegex(ValueError, "too many notes"):
            self.analyze({"abc": "", "notes": notes, "bpm": 120})

    def test_tempo_override_drops_the_score_quantised_at_the_detected_tempo(self):
        score = reference_score(melody([{"pitch": 60, "start": 0, "end": 2}], 2))
        notes = [{"pitch": 60, "start_s": 0, "end_s": 1}]
        kept = self.analyze({"abc": score, "notes": notes, "bpm": 120}, bpm=0)
        self.assertEqual(kept["melody"]["score_abc"], score)
        changed = self.analyze({"abc": score, "notes": notes, "bpm": 120}, bpm=60)
        self.assertIsNone(changed["melody"]["score_abc"])
        self.assertEqual(changed["melody"]["beats"], 1)


class JobPayloadTests(unittest.TestCase):
    def test_cancelled_queued_job_releases_the_reference_audio(self):
        import asyncio
        import httpx
        from studio import app as studio_app

        studio_app.jobs["hooktest"] = {"id": "hooktest", "kind": "generate", "status": "queued",
                                      "created": 0, "_hook_reference": {"audio": b"x"}}

        async def cancel():
            transport = httpx.ASGITransport(app=studio_app.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://studio.test") as client:
                return await client.post("/api/jobs/hooktest/cancel")

        try:
            self.assertEqual(asyncio.run(cancel()).status_code, 200)
            self.assertNotIn("_hook_reference", studio_app.jobs["hooktest"])
        finally:
            studio_app.jobs.pop("hooktest", None)


if __name__ == "__main__":
    unittest.main()
