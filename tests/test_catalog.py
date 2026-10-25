import json
import tempfile
import unittest
from pathlib import Path

from studio.models import ModelManager
from studio.providers import ROOT, get_provider


class CatalogTests(unittest.TestCase):
    def test_retired_sam_model_cannot_be_selected_or_downloaded(self):
        with tempfile.TemporaryDirectory() as root:
            manager = ModelManager(Path(root) / "state", Path(root) / "models")
            self.assertNotIn("sam-audio", manager.catalog)
            self.assertFalse(any(m.get("mode_id") == "anything" for m in manager.catalog.values()))
            with self.assertRaisesRegex(ValueError, "Unknown model"):
                manager.profile("sam-audio")

    def test_yue2_keeps_base_weight_terms_and_pins_the_creator_permission(self):
        model = next(m for m in json.loads((ROOT / "config/model-catalog.json").read_text())["models"] if m["id"] == "yue2-3b")
        self.assertEqual([l["id"] for l in model["licenses"][:2]], ["CC-BY-NC-4.0", "CC-BY-NC-4.0"])
        permission = model["licenses"][2]
        self.assertIn("monetize generated outputs", permission["summary"])
        self.assertIn("Company commercial use", permission["summary"])
        self.assertRegex(permission["source_revision"], r"^[0-9a-f]{40}$")
        self.assertEqual(permission["url"], "https://github.com/multimodal-art-projection/YuE/blob/" + permission["source_revision"] + "/MODEL_LICENSE")

    def test_real_catalog_uses_pinned_files_with_integrity_and_license_details(self):
        models = json.loads((ROOT / "config/model-catalog.json").read_text())["models"]
        for model in models:
            self.assertRegex(model["revision"], r"^[0-9a-f]{40}$")
            for license in model["licenses"]:
                self.assertTrue(license["verified"])
                self.assertTrue(license["url"].startswith("https://"))
                self.assertEqual(license["release_revision"], model["revision"])
            for file in [*model["precisions"].values(), *model["vaes"].values(), *model["required"]]:
                self.assertIn(f"/resolve/{model['revision']}/", file["url"])
                self.assertGreater(file["size"], 0)
                self.assertRegex(file.get("sha256") or file["git_sha1"], r"^[0-9a-f]{40}([0-9a-f]{24})?$")

    def test_optional_models_pin_every_file_hash_and_license(self):
        for model in json.loads((ROOT / "config/model-catalog.json").read_text())["optional_models"]:
            self.assertRegex(model["revision"], r"^[0-9a-f]{40}$")
            self.assertTrue(model["licenses"])
            for license in model["licenses"]:
                self.assertTrue(license["verified"])
                self.assertTrue(license["url"].startswith("https://"))
                self.assertEqual(license["release_revision"], model["revision"])
            self.assertTrue(any(file["path"].endswith(".safetensors") and file["sha256"] for file in model["files"]))
            for file in model["files"]:
                self.assertIn(f"/resolve/{model['revision']}/", file["url"])
                self.assertGreater(file["size"], 0)
                self.assertRegex(file.get("sha256") or file["git_sha1"], r"^[0-9a-f]{40}([0-9a-f]{24})?$")

    def test_yue2_main_precision_and_default_vae_are_independent(self):
        with tempfile.TemporaryDirectory() as root:
            manager = ModelManager(Path(root) / "state", Path(root) / "models")
            default = manager.profile("yue2-3b")
            self.assertEqual(default["precision"], "q8_0")
            self.assertEqual(default["vae_precision"], "f16")
            profile = manager.profile("yue2-3b", "bf16", "f32")
            self.assertEqual(profile["main_file"], "yue2-3b-bf16.gguf")
            self.assertEqual(profile["vae_file"], "yue2-vae-f32.gguf")
            runtime = get_provider(profile).adapter(profile).runtime_config(profile)
            self.assertEqual(runtime["path"], profile["root"])
            self.assertEqual(runtime["session_options"], {
                "yue2.model_gguf": "yue2-3b-bf16.gguf", "yue2.vae_gguf": "yue2-vae-f32.gguf"})
            self.assertFalse(Path(profile["root"]).exists())
            self.assertTrue(manager.status()["setup_required"])
            with self.assertRaises(ValueError): manager.profile("yue2-3b", "fp16", "f32")
