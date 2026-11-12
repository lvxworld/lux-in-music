import asyncio
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from studio.adapters.yue2 import YuE2Params as GenerationParams

ROOT = Path(__file__).resolve().parents[1]


class ProductIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from studio.app import app
        cls.app = app

    def get(self, path):
        async def request():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://studio.test") as client:
                return await client.get(path)
        return asyncio.run(request())

    def test_browser_and_api_names_match_the_product(self):
        page = self.get("/")
        schema = self.get("/openapi.json")
        self.assertEqual(page.status_code, 200)
        self.assertIn("<title>Lux In Music</title>", page.text)
        self.assertEqual(schema.json()["info"]["title"], "Lux In Music")

    def test_project_and_lock_package_identity_match(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        lock = tomllib.loads((ROOT / "uv.lock").read_text())
        editable = next(p for p in lock["package"] if p.get("source") == {"editable": "."})
        self.assertEqual(project["name"], "lux-in-music")
        self.assertEqual(editable["name"], project["name"])
        self.assertEqual(editable["version"], project["version"])

    def test_generation_cli_help_needs_no_engine(self):
        result = subprocess.run([sys.executable, "-m", "studio.cli", "--help"], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--lyrics", result.stdout)
        self.assertNotIn("--max-duration", result.stdout)
        self.assertNotIn("--target-duration", result.stdout)

    def test_create_page_has_no_manual_duration_or_separate_check(self):
        page = self.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn('id="duration-hint"', page.text)
        self.assertNotIn('id="duration-mode"', page.text)
        self.assertNotIn('id="len"', page.text)
        self.assertNotIn("Analyze duration", page.text)
        self.assertNotIn("duration.js", page.text)
        script = self.get("/static/app.js")
        self.assertEqual(script.status_code, 200)
        self.assertNotIn("/api/duration-analysis", script.text)
        self.assertIn("variations: state.variations", script.text)

    def test_create_reference_cards_follow_song_title(self):
        page = self.get("/")
        self.assertEqual(page.status_code, 200)
        title = page.text.index('id="title"')
        vibe_reference = page.text.index('id="create-vibe-reference"')
        hook_reference = page.text.index('id="create-hook-reference"')
        self.assertLess(title, vibe_reference)
        self.assertLess(title, hook_reference)
        self.assertLess(vibe_reference, hook_reference)

    def test_style_has_an_accessible_randomizer(self):
        page = self.get("/")
        script = self.get("/static/app.js")
        styles = self.get("/static/app.css")
        self.assertIn('class="icon-btn style-random" id="style-random" aria-label="Suggest a random music style"', page.text)
        self.assertIn("🎲</button>", page.text)
        self.assertIn('$("style-random").onclick', script.text)
        self.assertIn("sample(CHIPS.Instr", script.text)
        self.assertIn(".style-random { width: 28px; height: 28px", styles.text)
        self.assertIn(".icon-btn:hover", styles.text)

    def test_advanced_controls_have_plain_language_help(self):
        page = self.get("/")
        script = self.get("/static/app.js")
        styles = self.get("/static/app.css")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(script.status_code, 200)
        self.assertEqual(styles.status_code, 200)
        self.assertIn('class="advanced-help" aria-label="Help for ${s.label}"', script.text)
        self.assertIn("How many passes YuE2 uses to turn the music tokens into sound", script.text)
        self.assertIn("Auto uses 1.01 for Direct and 1.0 for Melody or Full score", script.text)
        self.assertEqual(page.text.count('class="advanced-help"'), 1)  # ABC score; sliders are model-driven
        self.assertIn('aria-label="Help for ABC score"', page.text)
        self.assertIn(".slider:nth-child(even) .advanced-help [role=tooltip]", styles.text)
        self.assertIn("left: 0; bottom: calc(100% + 9px)", styles.text)

    def test_hook_explains_why_lyrics_are_disabled(self):
        script = self.get("/static/hook.js")
        self.assertEqual(script.status_code, 200)
        self.assertIn("does not yet combine its recorded melody reference with sung lyrics", script.text)
        self.assertIn("cannot yet combine the recorded melody reference with sung lyrics", script.text)
        self.assertNotIn("Use lyrics that fit this short arrangement", script.text)

    def test_create_and_library_have_an_accessible_resizable_split(self):
        page = self.get("/")
        script = self.get("/static/app.js")
        styles = self.get("/static/app.css")
        self.assertIn('id="panel-resizer" role="separator" tabindex="0"', page.text)
        self.assertIn('aria-label="Resize Create and Library panels"', page.text)
        self.assertIn("grid-template-columns: 220px minmax(400px, var(--create-width, 580px)) 12px", styles.text)
        self.assertIn('localStorage.setItem("lux.createWidth"', script.text)
        self.assertIn("Math.floor(trackWidth() * 0.48)", script.text)
        self.assertIn("Library ${Math.round(trackWidth() - width)} pixels", script.text)
        self.assertIn("narrow() ? 320 : 360", script.text)
        self.assertIn('event.key === "ArrowLeft"', script.text)
        self.assertIn('event.key === "ArrowRight"', script.text)

    def test_song_details_group_audio_exports_together(self):
        script = self.get("/static/app.js")
        styles = self.get("/static/app.css")
        self.assertIn('<section class="d-export-group" aria-labelledby="d-export-title">', script.text)
        self.assertIn('<h4 id="d-export-title">Export</h4>', script.text)
        self.assertIn("class=\"d-export-actions\"", script.text)
        self.assertIn(".d-export-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr))", styles.text)

    def test_hook_reference_player_fills_its_detail_section(self):
        script = self.get("/static/app.js")
        styles = self.get("/static/app.css")
        self.assertIn('class="d-sec d-hook-audio"', script.text)
        self.assertIn('controls preload="metadata"', script.text)
        self.assertIn("The original recording was not saved with this song", script.text)
        self.assertIn("#drawer .d-hook-audio { align-self: stretch; width: 100%", styles.text)
        self.assertIn("#drawer audio.hook-reference-player { display: block; width: 100% !important", styles.text)

    def test_generation_api_schema_does_not_advertise_duration_controls(self):
        schema = self.get("/openapi.json").json()
        ref = schema["paths"]["/api/generate"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        fields = schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]["properties"]
        self.assertIn("variations", fields)
        self.assertNotIn("target_duration_s", fields)
        self.assertNotIn("max_duration_s", fields)
        self.assertNotIn("semantic_max_tokens", fields)

    def test_cli_rejects_duration_fields_in_generic_model_options(self):
        result = subprocess.run([sys.executable, "-m", "studio.cli", "--style", "Piano",
            "--model-options", '{"target_duration_s":120}'], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Song length is inferred", result.stderr)

    def test_engine_offline_health_remains_a_valid_ui_response(self):
        with patch("studio.engine.health", side_effect=RuntimeError("engine unavailable")):
            response = self.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["engine"], "down")


class RequestBoundaryTests(unittest.TestCase):
    def params(self, **changes):
        return GenerationParams(lyrics="[Verse]\nA song", style="English, pop", **changes)

    def test_duration_cap_maps_to_codec_budget_not_a_false_completion_flag(self):
        request = self.params(max_duration_s=180).to_request()
        self.assertEqual(request["options"]["semantic_max_tokens"], "4500")
        self.assertNotIn("max_duration_s", request["options"])
        self.assertNotIn("completed", request)

    def test_short_cap_does_not_conflict_with_engine_default_minimum(self):
        request = self.params(max_duration_s=4).to_request()
        self.assertEqual(request["options"]["semantic_min_tokens"], "100")
        self.assertEqual(request["options"]["semantic_max_tokens"], "100")

    def test_lyrics_are_optional_and_instrumental_sends_the_upstream_tag(self):
        self.assertEqual(GenerationParams(style="Piano").to_request()["lyrics"], "")
        request = self.params(instrumental=True).to_request()
        self.assertEqual(request["lyrics"], "[instrumental]")
        self.assertNotIn("instrumental", request["options"])

    def test_conflicting_token_limits_and_unsupported_score_route_fail(self):
        with self.assertRaises(ValidationError):
            self.params(semantic_min_tokens=201, semantic_max_tokens=200)
        with self.assertRaises(ValidationError):
            self.params(abc="X:1\nK:C\nC4|", cot="off")


class LaunchHostTests(unittest.TestCase):
    def launch(self, *argv):
        import contextlib, io
        from studio import launch
        out = io.StringIO()
        with patch.object(sys, "argv", ["launch", "--no-open", *argv]), patch("uvicorn.Config") as config, \
                patch("uvicorn.Server"), patch("studio.app.enable_auto_restart"), \
                contextlib.redirect_stdout(out):
            launch.main()
        return config.call_args.kwargs["host"], out.getvalue()

    def test_requested_restart_stops_the_server_and_reexecs_without_opening_a_tab(self):
        import contextlib, io
        from studio import launch
        class Server:
            def __init__(self, config): self.should_exit = False
            def run(self): restart_hooks[0]()
        restart_hooks = []
        with patch.object(sys, "argv", ["launch", "--port", "18001"]), patch("uvicorn.Config"), \
                patch("uvicorn.Server", Server), patch("studio.launch.threading.Thread"), \
                patch("studio.app.enable_auto_restart", restart_hooks.append), \
                patch("studio.launch.os.execv") as execv, contextlib.redirect_stdout(io.StringIO()):
            launch.main()
        execv.assert_called_once_with(sys.executable, [sys.executable, "-m", "studio.launch",
                                                       "--port", "18001", "--no-open"])

    def test_local_by_default_and_warns_when_listening_elsewhere(self):
        host, out = self.launch()
        self.assertEqual(host, "127.0.0.1")
        self.assertIn("http://127.0.0.1:8000", out)
        self.assertNotIn("WARNING", out)
        host, out = self.launch("--host", "0.0.0.0")
        self.assertEqual(host, "0.0.0.0")
        self.assertIn("every network interface", out)
        self.assertIn("http://127.0.0.1:8000", out)
        self.assertIn("no login", out)
        for given, shown in [("192.168.1.20", "http://192.168.1.20:8000"),
                             ("fd7a::1", "http://[fd7a::1]:8000")]:
            with self.subTest(host=given):
                host, out = self.launch("--host", given)
                self.assertEqual(host, given)
                self.assertIn(shown, out)
                self.assertIn("no login", out)

    def test_ready_line_mentions_other_devices_only_when_shared(self):
        import contextlib, io, json, threading
        from studio import launch
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps({"setup_required": False}).encode()
        for shared in (True, False):
            with self.subTest(shared=shared):
                out = io.StringIO()
                with patch("studio.launch.urllib.request.urlopen", return_value=Response()), \
                        patch("studio.launch.webbrowser.open") as opened, \
                        contextlib.redirect_stdout(out):
                    launch.open_when_ready("http://127.0.0.1:8000", threading.Event(), shared)
                opened.assert_called_once_with("http://127.0.0.1:8000/")
                self.assertEqual("reachable from other devices" in out.getvalue(), shared)
