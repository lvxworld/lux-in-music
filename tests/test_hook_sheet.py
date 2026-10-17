"""Offline checks for the optional SheetSage2 trial; no model or Torch import."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from scripts import check_hook_sheet as trial


class SheetTrialTests(unittest.TestCase):
    def test_manifest_pins_each_executable_and_weight_with_source_and_license(self):
        manifest = json.loads(trial.MANIFEST_PATH.read_text())
        self.assertEqual([part["directory"] for part in manifest["components"]], ["sheet", "mert"])
        for part in manifest["components"]:
            self.assertRegex(part["revision"], r"^[0-9a-f]{40}$")
            self.assertEqual(part["license"], "CC-BY-NC-4.0")
            self.assertIn(part["revision"], part["license_url"])
            self.assertIn("model.safetensors", [file["path"] for file in part["files"]])
            for file in part["files"]:
                self.assertEqual(Path(file["path"]).name, file["path"])
                self.assertGreater(file["size"], 0)
                self.assertRegex(file["sha256"], r"^[0-9a-f]{64}$")

    def test_file_verification_rejects_changed_content_and_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); path = root / "model"
            path.write_bytes(b"synthetic model")
            artifact = {"path": "model", "size": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            self.assertTrue(trial.valid_file(path, artifact))
            path.write_bytes(b"synthetic other")
            self.assertFalse(trial.valid_file(path, artifact))
            link = root / "link"; link.symlink_to(path)
            self.assertFalse(trial.valid_file(link, artifact))
            with self.assertRaises(ValueError):
                trial.verify_models(root, {"components": [{"directory": "missing", "files": [artifact]}]})

    def test_prepare_requires_explicit_noncommercial_review_before_network_or_software(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("No downloads")), patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "CC BY-NC"):
                trial.prepare(Path("unused"), {}, False)
            run.assert_not_called()

    def test_concurrent_trials_cannot_load_two_models(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(trial, "RUNTIME", Path(tmp) / "runtime"):
            with trial.operation_lock():
                with self.assertRaisesRegex(ValueError, "Another SheetSage2"):
                    with trial.operation_lock():
                        self.fail("A second heavy model must not be loaded")

    def test_missing_model_analysis_never_downloads_or_installs(self):
        with tempfile.TemporaryDirectory() as tmp, patch("urllib.request.urlopen", side_effect=AssertionError("No network")), patch("subprocess.run") as run, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(trial.main(["--audio", "synthetic.wav", "--model-dir", tmp]), 1)
            run.assert_not_called()

    def test_launcher_runs_only_isolated_python_with_offline_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp); (runtime / "bin").mkdir(); (runtime / "bin/python").touch()
            with patch.object(trial, "RUNTIME", runtime), patch.object(trial, "verify_models"), patch("subprocess.run", return_value=types.SimpleNamespace(returncode=0)) as run:
                self.assertEqual(trial.main(["--audio", "synthetic.wav", "--device", "cpu"]), 0)
                command = run.call_args.args[0]
                self.assertEqual(command[0], str(runtime / "bin/python"))
                self.assertIn("--worker", command)
                self.assertNotIn("uv", command)
                self.assertEqual(run.call_args.kwargs["env"]["HF_HUB_OFFLINE"], "1")
                self.assertEqual(run.call_args.kwargs["env"]["TRANSFORMERS_OFFLINE"], "1")

    def test_private_trial_artifacts_cannot_be_written_into_source(self):
        with patch.object(trial, "verify_models") as verify, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(trial.main(["--audio", "synthetic.wav", "--output", str(trial.ROOT / "tests")]), 1)
            verify.assert_not_called()

    def test_review_uses_only_local_fixed_media_paths_and_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            trial.write_review(Path(tmp), {"mix": 10, "melody_vocal": 0, "melody_instrumental": 10, "chords": 3})
            html = (Path(tmp) / "review.html").read_text()
            self.assertIn('src="reference.wav"', html)
            self.assertIn('src="melody_instrumental-preview.wav"', html)
            self.assertNotIn('src="melody_vocal-preview.wav"', html)
            self.assertNotIn('https:', html)


if __name__ == "__main__":
    unittest.main()
