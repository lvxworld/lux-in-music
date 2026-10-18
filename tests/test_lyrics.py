import asyncio
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from studio import lyrics
from studio.lyrics import MOOD_IDS, LyricsNotConfigured, LyricsUpstreamError, LyricsWriter, clean_lyrics
from studio.vibe import load_catalog

PNG = "data:image/png;base64,iVBORw0KGgo="
REPLY = "[Verse]\nSynthetic line one\nSynthetic line two\n\n[Chorus]\nSynthetic chorus line"


class Endpoint:
    """Fake OpenAI-compatible server that records each request."""

    def __init__(self, reply=REPLY, status=200, models=("model-a", "model-b")):
        self.reply, self.status, self.models, self.requests = reply, status, models, []

    def __call__(self, request):
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"error": "synthetic failure"})
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": name} for name in self.models]})
        return httpx.Response(200, json={"choices": [{"message": {"content": self.reply}}]})

    def body(self, index=-1):
        return json.loads(self.requests[index].content)


class WriterFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.endpoint = Endpoint()
        self.writer = self.make_writer()
        env = patch.dict(os.environ, {}, clear=False); env.start(); self.addCleanup(env.stop)
        os.environ.pop("LUX_LYRICS_API_KEY", None)

    def make_writer(self):
        transport = httpx.MockTransport(lambda request: self.endpoint(request))
        return LyricsWriter(self.root, client=lambda: httpx.Client(transport=transport))

    def configure(self, **update):
        return self.writer.save({"base_url": "http://llm.test/v1/", "model": "model-a", **update})


class LyricsSettingsTests(WriterFixture):
    def test_fresh_install_is_not_configured_and_makes_no_requests(self):
        status = self.writer.status()
        self.assertFalse(status["configured"])
        self.assertFalse(status["api_key_set"])
        self.assertFalse((self.root / "lyrics.json").exists())
        with self.assertRaises(LyricsNotConfigured):
            self.writer.generate(concept="Synthetic concept")
        self.assertEqual(self.endpoint.requests, [])

    def test_key_is_saved_privately_and_never_returned(self):
        status = self.configure(api_key="sk-synthetic")
        self.assertTrue(status["api_key_set"])
        self.assertNotIn("sk-synthetic", json.dumps(status))
        self.assertEqual(status["base_url"], "http://llm.test/v1")
        path = self.root / "lyrics.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertFalse(path.with_suffix(".json.tmp").exists())
        self.assertTrue(self.make_writer().status()["api_key_set"])

    def test_omitted_key_is_kept_and_empty_key_clears_it(self):
        self.configure(api_key="sk-synthetic")
        self.assertTrue(self.writer.save({"model": "model-b", "api_key": None})["api_key_set"])
        self.assertEqual(self.writer.status()["model"], "model-b")
        self.assertFalse(self.writer.save({"api_key": ""})["api_key_set"])

    def test_moving_to_another_server_drops_the_saved_key(self):
        self.configure(api_key="sk-synthetic")
        self.assertTrue(self.writer.save({"base_url": "http://LLM.test/v1/"})["api_key_set"])
        self.assertTrue(self.writer.save({"base_url": "http://llm.test/v2"})["api_key_set"])
        self.assertFalse(self.writer.save({"base_url": "http://other.test/v1"})["api_key_set"])
        self.writer.generate(concept="Synthetic concept")
        self.assertNotIn("authorization", self.endpoint.requests[-1].headers)
        self.assertTrue(self.writer.save({"base_url": "http://llm.test/v1", "api_key": "sk-new"})["api_key_set"])

    def test_environment_key_overrides_the_saved_key(self):
        self.configure(api_key="sk-saved")
        with patch.dict(os.environ, {"LUX_LYRICS_API_KEY": "sk-env"}):
            self.assertTrue(self.writer.status()["api_key_from_env"])
            self.writer.generate(concept="Synthetic concept")
        self.assertEqual(self.endpoint.requests[-1].headers["authorization"], "Bearer sk-env")

    def test_invalid_settings_are_rejected(self):
        for update in ({"base_url": "ftp://llm.test"}, {"base_url": "localhost:1234"}, {"temperature": 3}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                self.writer.save(update)
        self.assertFalse((self.root / "lyrics.json").exists())

    def test_unreadable_settings_are_reported(self):
        (self.root / "lyrics.json").write_text("[]")
        status = self.make_writer().status()
        self.assertFalse(status["configured"])
        self.assertIn("could not be read", status["state_error"])

    def test_connection_test_lists_models(self):
        self.configure()
        self.assertEqual(self.writer.test(), {"ok": True, "models": ["model-a", "model-b"], "base_url": "http://llm.test/v1"})
        self.assertEqual(str(self.endpoint.requests[-1].url), "http://llm.test/v1/models")


class ModelDiscoveryTests(WriterFixture):
    def test_typed_url_lists_models_without_leaking_the_saved_key(self):
        self.configure(api_key="sk-saved")
        self.assertEqual(self.writer.list_models("http://llm.test/v1/")["models"], ["model-a", "model-b"])
        self.assertEqual(self.endpoint.requests[-1].headers["authorization"], "Bearer sk-saved")
        self.writer.list_models("http://other.test/v1")
        self.assertNotIn("authorization", self.endpoint.requests[-1].headers)
        self.writer.list_models("http://other.test/v1", "sk-typed")
        self.assertEqual(self.endpoint.requests[-1].headers["authorization"], "Bearer sk-typed")
        for url in ("", "ftp://llm.test"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.writer.list_models(url)

    def test_redirects_are_resolved_for_listing_and_explained_for_writing(self):
        def respond(request):
            if request.url.scheme == "http":
                return httpx.Response(301, headers={"location": str(request.url.copy_with(scheme="https"))})
            if request.method == "GET" and request.url.path.endswith("/chat/completions"):
                return httpx.Response(405)
            return self.endpoint(request)
        writer = LyricsWriter(self.root, client=lambda: httpx.Client(transport=httpx.MockTransport(respond),
                                                                     follow_redirects=True))
        self.assertEqual(writer.list_models("http://llm.test/v1")["base_url"], "https://llm.test/v1")
        writer.save({"base_url": "http://llm.test/v1", "model": "model-a"})
        self.assertEqual(writer.test()["base_url"], "https://llm.test/v1")
        with self.assertRaises(LyricsUpstreamError) as caught:
            writer.generate(concept="Synthetic concept")
        self.assertIn("redirects to https://llm.test/v1", str(caught.exception))

    def test_non_openai_model_lists_are_rejected(self):
        writer = LyricsWriter(self.root, client=lambda: httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"models": ["x"]}))))
        with self.assertRaises(LyricsUpstreamError):
            writer.list_models("http://llm.test/v1")

    def test_discovery_reports_only_servers_with_models_and_sends_no_key(self):
        def respond(request):
            if request.url.port == 1234:
                return httpx.Response(200, json={"data": [{"id": "model-b"}, {"id": "model-a"}]})
            if request.url.port == 11434:
                return httpx.Response(200, json={"data": []})
            raise httpx.ConnectError("synthetic closed port")
        requests = []
        def record(request):
            requests.append(request); return respond(request)
        writer = LyricsWriter(self.root, client=lambda: httpx.Client(transport=httpx.MockTransport(record)))
        writer.save({"base_url": "http://llm.test/v1", "model": "model-a", "api_key": "sk-saved"})
        self.assertEqual(writer.discover(), {"servers": [
            {"name": "LM Studio", "base_url": "http://localhost:1234/v1", "models": ["model-a", "model-b"]}]})
        self.assertEqual({request.url.host for request in requests}, {"localhost"})
        self.assertTrue(all("authorization" not in request.headers for request in requests))


class LyricsRequestTests(WriterFixture):
    def test_text_request_shape(self):
        self.configure(api_key="sk-synthetic", temperature=0.5)
        result = self.writer.generate(concept="Synthetic concept", style="Synthetic piano", title="Synthetic",
                                      mood="hopeful")
        self.assertEqual(result, {"lyrics": REPLY, "used_images": 0})
        request = self.endpoint.requests[-1]
        self.assertEqual(str(request.url), "http://llm.test/v1/chat/completions")
        self.assertEqual(request.headers["authorization"], "Bearer sk-synthetic")
        body = self.endpoint.body()
        self.assertEqual(body["model"], "model-a")
        self.assertEqual(body["temperature"], 0.5)
        self.assertEqual(body["messages"][0]["role"], "system")
        user = body["messages"][1]["content"]
        self.assertIsInstance(user, str)
        for text in ("Synthetic concept", "Synthetic piano", "Hopeful"):
            self.assertIn(text, user)

    def test_no_authorization_header_without_a_key(self):
        self.configure()
        self.writer.generate(concept="Synthetic concept")
        self.assertNotIn("authorization", self.endpoint.requests[-1].headers)

    def test_custom_theme_replaces_the_mood(self):
        self.configure()
        self.writer.generate(visual="Synthetic harbor", mood="dark", custom="Synthetic custom theme")
        user = self.endpoint.body()["messages"][1]["content"]
        self.assertIn("Synthetic custom theme", user)
        self.assertNotIn("Dark", user)

    def test_images_are_sent_only_when_the_model_reads_images(self):
        self.configure(supports_images=False)
        result = self.writer.generate(visual="Synthetic harbor", images=[PNG])
        self.assertEqual(result["used_images"], 0)
        self.assertIsInstance(self.endpoint.body()["messages"][1]["content"], str)
        self.configure(supports_images=True)
        result = self.writer.generate(visual="Synthetic harbor", images=[PNG, PNG])
        self.assertEqual(result["used_images"], 2)
        parts = self.endpoint.body()["messages"][1]["content"]
        self.assertEqual(parts[0]["type"], "text")
        self.assertEqual([part["image_url"]["url"] for part in parts[1:]], [PNG, PNG])

    def test_upstream_failures_are_short_and_private(self):
        self.configure(api_key="sk-synthetic")
        for status, expected in ((401, "API key"), (500, "HTTP 500")):
            self.endpoint.status = status
            with self.subTest(status=status), self.assertRaises(LyricsUpstreamError) as caught:
                self.writer.generate(concept="Synthetic private concept")
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn("Synthetic private concept", str(caught.exception))
            self.assertNotIn("sk-synthetic", str(caught.exception))
        self.endpoint.status, self.endpoint.reply = 200, "I cannot help with that."
        with self.assertRaises(LyricsUpstreamError):
            self.writer.generate(concept="Synthetic concept")

    def test_unreachable_endpoint_is_explained(self):
        def fail(request): raise httpx.ConnectError("synthetic")
        writer = LyricsWriter(self.root, client=lambda: httpx.Client(transport=httpx.MockTransport(fail)))
        writer.save({"base_url": "http://llm.test/v1", "model": "model-a"})
        with self.assertRaises(LyricsUpstreamError) as caught:
            writer.generate(concept="Synthetic concept")
        self.assertIn("could not be reached", str(caught.exception))


class StyleWritingTests(WriterFixture):
    def test_style_follows_the_request_in_one_clean_line(self):
        self.configure()
        self.endpoint.reply = ('<think>Synthetic</think>**Style:** "Italian, rock ballad, 72 BPM, piano, '
                               'strings, warm female vocal, piano, intimate verses, wide stereo mix."')
        result = self.writer.write_style("Synthetic request", "Synthetic title", vocabulary=["piano", "jazz"])
        self.assertEqual(result, {"style": "Italian, rock ballad, 72 BPM, piano, strings, warm female vocal, "
                                           "intimate verses, wide stereo mix"})
        body = self.endpoint.body()
        self.assertIn("BPM", body["messages"][0]["content"])
        user = body["messages"][1]["content"]
        for text in ("Synthetic request", "Synthetic title", "piano, jazz"):
            self.assertIn(text, user)

    def test_instrumental_style_drops_vocal_tags(self):
        self.configure()
        self.endpoint.reply = "English, lo-fi, 80 BPM, soft piano, airy female vocal, choir harmonies, tape hiss"
        style = self.writer.write_style("Synthetic request", instrumental=True)["style"]
        self.assertEqual(style, "English, lo-fi, 80 BPM, soft piano, tape hiss, instrumental")
        self.assertIn("instrumental", self.endpoint.body()["messages"][1]["content"])

    def test_unusable_or_long_replies(self):
        self.configure()
        for reply in ("", "Synthetic sentence only", "<think>never finished"):
            self.endpoint.reply = reply
            with self.subTest(reply=reply), self.assertRaises(LyricsUpstreamError):
                self.writer.write_style("Synthetic request")
        self.endpoint.reply = ", ".join(f"synthetic tag {i:02d} with extra words" for i in range(30))
        style = self.writer.write_style("Synthetic request")["style"]
        self.assertLessEqual(len(style), lyrics.MAX_STYLE_CHARS)
        self.assertFalse(style.endswith(","))


class CleanLyricsTests(unittest.TestCase):
    def test_reasoning_fences_preamble_and_notes_are_removed(self):
        reply = ("<think>Synthetic plan</think>Here are your lyrics:\n```\n**Verse 1:**\nSynthetic line\n(softly)\n"
                 "[Guitar solo]\n\nchorus\nSynthetic hook\n[pre chorus]\nSynthetic lift\n```\nHope you enjoy!")
        self.assertEqual(clean_lyrics(reply), "[Verse]\nSynthetic line\n\n[Chorus]\nSynthetic hook\n\n"
                                             "[Pre-Chorus]\nSynthetic lift")

    def test_unfinished_reasoning_and_untagged_replies_fail(self):
        for reply in ("<think>Synthetic plan without an end", "Synthetic untagged text", "[Verse]\n[Chorus]", ""):
            with self.subTest(reply=reply), self.assertRaises(LyricsUpstreamError):
                clean_lyrics(reply)

    def test_long_replies_are_capped_on_a_line_boundary(self):
        result = clean_lyrics("[Verse]\n" + "Synthetic line\n" * 400)
        self.assertLessEqual(len(result), lyrics.MAX_LYRICS_CHARS)
        self.assertTrue(result.endswith("Synthetic line"))

    def test_every_vibe_direction_suggests_a_known_mood(self):
        self.assertTrue(all(entry.get("mood") in MOOD_IDS for entry in load_catalog()))


class LyricsApiTests(WriterFixture):
    def setUp(self):
        super().setUp()
        writer_patch = patch.object(lyrics, "_writer", self.writer); writer_patch.start(); self.addCleanup(writer_patch.stop)

    def request(self, method, path, body=None):
        from studio.app import app
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://studio.test") as client:
                return await client.request(method, path, json=body)
        return asyncio.run(send())

    def test_settings_round_trip_without_exposing_the_key(self):
        self.assertFalse(self.request("GET", "/api/lyrics/status").json()["configured"])
        response = self.request("POST", "/api/lyrics/settings", {"base_url": "http://llm.test/v1", "model": "model-a",
                                                                 "api_key": "sk-synthetic"})
        self.assertEqual(response.status_code, 200)
        status = self.request("GET", "/api/lyrics/status").json()
        self.assertTrue(status["configured"] and status["api_key_set"])
        self.assertNotIn("sk-synthetic", json.dumps(status))
        self.assertTrue(status["moods"])
        self.assertEqual(self.request("POST", "/api/lyrics/settings", {"base_url": "file:///etc"}).status_code, 422)
        self.assertEqual(self.request("POST", "/api/lyrics/test").json()["models"], ["model-a", "model-b"])
        response = self.request("POST", "/api/lyrics/models", {"base_url": "http://llm.test/v1"})
        self.assertEqual(response.json(), {"base_url": "http://llm.test/v1", "models": ["model-a", "model-b"]})
        self.assertEqual(self.request("POST", "/api/lyrics/models", {"base_url": "llm.test"}).status_code, 422)
        self.endpoint.status = 500
        self.assertEqual(self.request("POST", "/api/lyrics/models", {"base_url": "http://llm.test/v1"}).status_code, 502)
        with patch.object(lyrics, "LOCAL_SERVERS", []):
            self.assertEqual(self.request("POST", "/api/lyrics/discover").json(), {"servers": []})

    def test_generate_maps_errors_to_clear_statuses(self):
        self.assertEqual(self.request("POST", "/api/lyrics/generate", {"concept": "Synthetic"}).status_code, 409)
        self.configure()
        self.assertEqual(self.request("POST", "/api/lyrics/generate", {"style": "Synthetic piano"}).status_code, 422)
        self.assertEqual(self.request("POST", "/api/lyrics/generate", {"visual": "x", "images": ["data:text/plain;base64,eA=="]}).status_code, 422)
        self.assertEqual(self.request("POST", "/api/lyrics/generate", {"visual": "x", "images": [PNG] * 6}).status_code, 422)
        response = self.request("POST", "/api/lyrics/generate", {"concept": "Synthetic concept"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["lyrics"], REPLY)
        self.endpoint.status = 500
        self.assertEqual(self.request("POST", "/api/lyrics/generate", {"concept": "Synthetic concept"}).status_code, 502)

    def test_style_endpoint(self):
        self.configure()
        self.endpoint.reply = "English, jazz, 90 BPM, piano"
        response = self.request("POST", "/api/lyrics/style", {"concept": "Synthetic", "vocabulary": ["jazz"]})
        self.assertEqual(response.json(), {"style": "English, jazz, 90 BPM, piano"})
        self.assertEqual(self.request("POST", "/api/lyrics/style", {"concept": "  "}).status_code, 422)
        self.assertEqual(self.request("POST", "/api/lyrics/style", {"concept": "Synthetic", "vocabulary": ["x" * 61]}).status_code, 422)

    def test_vibe_analysis_suggests_a_mood_and_describes_the_scene(self):
        result = {"id": "synthetic", "style": "Synthetic style", "mood": "dreamy", "visual": "Synthetic scene"}
        class Manager:
            def status(self): return {"installed": True, "job": None}
            def analyze(self, image): return result
        async def send():
            from studio.app import app
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://studio.test") as client:
                return await client.post("/api/vibe/analyze", content=b"synthetic", headers={"content-type": "image/png"})
        with patch("studio.app.get_vibe_manager", return_value=Manager()), \
             patch("studio.app.validate_image", return_value=object()):
            response = asyncio.run(send())
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()["mood"], response.json()["visual"]), ("dreamy", "Synthetic scene"))


if __name__ == "__main__":
    unittest.main()
