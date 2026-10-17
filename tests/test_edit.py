import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from pydantic import ValidationError

from studio.app import StemEditRequest
from studio.adapters import yue2_edit


class EditDirectionTests(unittest.TestCase):
    def test_direction_is_optional_and_bounded_at_the_api_boundary(self):
        base = {"song": "demo", "set_id": "4stems", "stem": "vocals",
                "start_s": 2, "end_s": 8, "seed": 42}
        self.assertIsNone(StemEditRequest(**base).direction)
        self.assertEqual(StemEditRequest(**base, direction="More energy").direction, "More energy")
        with self.assertRaises(ValidationError):
            StemEditRequest(**base, direction="x" * 501)

    def test_direction_conditions_the_edit_render_and_is_returned_for_take_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            song = "synthetic"
            metadata = {"params": {"lyrics": "[Verse]\nSynthetic words", "style": "Indie pop",
                                   "seed": 7, "instrumental": False}, "duration_s": 4}
            (output / f"{song}.json").write_text(json.dumps(metadata))
            (output / f"{song}.wav").write_bytes(b"synthetic wav")
            semantic = {"artifacts": [{"id": "semantic",
                                       "payload": base64.b64encode(json.dumps(list(range(200))).encode()).decode()}]}
            audio = {"audio": base64.b64encode(b"synthetic pcm").decode()}
            with patch.object(yue2_edit.engine, "OUTPUT_DIR", output), \
                 patch.object(yue2_edit, "song_tokens", return_value=[0] * 100), \
                 patch.object(yue2_edit, "_base_options", return_value={"style": "Indie pop"}), \
                 patch.object(yue2_edit, "_pcm", return_value=np.zeros((2000, 2), dtype=np.float32)), \
                 patch.object(yue2_edit, "crossfade_region", side_effect=lambda original, new, *_: new), \
                 patch.object(yue2_edit, "_run", side_effect=[semantic, audio]) as run:
                _, info = yue2_edit.render_section(
                    song, 1, 2, 99, profile={}, direction="Make this part more energetic")

        self.assertEqual(info["direction"], "Make this part more energetic")
        self.assertIn("For the selected section only: Make this part more energetic",
                      run.call_args_list[0].args[2]["style"])
        self.assertEqual(run.call_args_list[1].args[2]["style"], run.call_args_list[0].args[2]["style"])


if __name__ == "__main__":
    unittest.main()
