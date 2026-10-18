"""Browser acceptance test using an isolated app and fake model downloads.

Requires Playwright and an installed Chrome. No model or browser download occurs.
"""

import argparse
import json
import io
import math
import os
import re
import shutil
import socket
import subprocess
import struct
import tempfile
import time
import urllib.request
import zlib
import wave
from urllib.parse import urljoin
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def synthetic_png(color=(40, 80, 120)):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 32, 24, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\0" + bytes(color) * 32) * 24)) + chunk(b"IEND", b""))


def reactive_wav():
    """A synthetic bass/mid tone with a silent interval; no song audio."""
    frames = bytearray()
    for n in range(20 * 8000):
        t = n / 8000
        sample = 0 if 2 <= t < 8 else .22 * math.sin(2 * math.pi * 90 * t) + .08 * math.sin(2 * math.pi * 850 * t)
        frames.extend(struct.pack("<h", round(sample * 32767)))
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(8000); audio.writeframes(frames)
    return output.getvalue()


def check_reactive_effects(page, expect, artifacts):
    effects = page.locator("#vibe-effects")
    toggle = page.locator("#vibe-effects-toggle")
    expect(toggle).to_have_attribute("aria-pressed", "true")
    page.evaluate("audio.currentTime = 10")
    page.wait_for_function("parseFloat($('vibe-effects').style.getPropertyValue('--vibe-energy')) > .15")
    assert page.evaluate("$('vibe-effects').width <= 960 && $('vibe-effects').height <= 720")
    page.evaluate("audio.currentTime = 3")
    page.wait_for_function("parseFloat($('vibe-effects').style.getPropertyValue('--vibe-energy')) < .025", timeout=4500)
    page.evaluate("audio.currentTime = 10")
    page.wait_for_function("parseFloat($('vibe-effects').style.getPropertyValue('--vibe-energy')) > .15")
    page.screenshot(path=str(artifacts / "vibe-effects-desktop.png"))
    page.locator("#p-play").click()
    frozen = effects.evaluate("canvas => canvas.toDataURL()")
    page.wait_for_timeout(250)
    assert effects.evaluate("canvas => canvas.toDataURL()") == frozen
    page.locator("#p-play").click()
    page.evaluate("Object.defineProperty(document, 'hidden', {configurable:true, value:true}); document.dispatchEvent(new Event('visibilitychange'))")
    frozen = effects.evaluate("canvas => canvas.toDataURL()")
    page.wait_for_timeout(250)
    assert effects.evaluate("canvas => canvas.toDataURL()") == frozen
    page.evaluate("delete document.hidden; document.dispatchEvent(new Event('visibilitychange'))")
    toggle.click()
    expect(toggle).to_have_text("Effects Off")
    expect(effects).to_have_css("opacity", "0")
    before = page.evaluate("audio.currentTime")
    page.wait_for_timeout(250)
    assert page.evaluate("!audio.paused && audio.currentTime") > before
    assert page.evaluate("localStorage.getItem('lux.vibe.effects')") == "off"
    toggle.click()
    expect(toggle).to_have_text("Effects On")
    assert page.evaluate("window.__luxMediaSourceCount") == 1
    page.wait_for_function("parseFloat(getComputedStyle($('vibe-effects')).opacity) > .4")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=ROOT / "outputs/checks/ui")
    parser.add_argument("--readme-screenshots", action="store_true", help="Capture synthetic example screens for the README")
    args = parser.parse_args(); args.artifacts.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright, expect
    chrome = os.environ.get("LUX_TEST_BROWSER") or shutil.which("google-chrome") or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not Path(chrome).is_file(): raise SystemExit("Install Chrome or set LUX_TEST_BROWSER to its executable")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="lux-browser-") as temp:
        with (Path(temp) / "server.log").open("w+") as log:
            server = subprocess.Popen([str(ROOT / ".venv/bin/python"), "-m", "tests.ui_server", "--port", str(port)], cwd=ROOT,
                                      stdout=log, stderr=subprocess.STDOUT)
            try:
                for _ in range(100):
                    try:
                        urllib.request.urlopen(url + "/api/settings/status", timeout=1).close(); break
                    except OSError:
                        if server.poll() is not None:
                            log.seek(0); raise RuntimeError(log.read())
                        time.sleep(0.1)
                else: raise RuntimeError("Fixture server did not start")
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=chrome, headless=True)
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.add_init_script("""window.__luxMediaSourceCount = 0;
                        const original = AudioContext.prototype.createMediaElementSource;
                        AudioContext.prototype.createMediaElementSource = function(...args) {
                            window.__luxMediaSourceCount++; return original.apply(this, args);
                        };""")
                    errors = []; page.on("pageerror", lambda error: errors.append(str(error)))
                    page.route("https://**/*", lambda route: route.abort())  # external fonts are optional
                    page.goto(url); page.wait_for_url("**/#/settings")
                    default_lyrics = page.locator("#lyrics").input_value()
                    assert default_lyrics.startswith("[Verse]\n") and "[Outro]\n" in default_lyrics
                    expect(page.locator("#nav-vibe .new-badge")).to_have_text("NEW")
                    expect(page.locator("#nav-lux .new-badge")).to_have_count(0)
                    expect(page.locator("#vibe-model-card")).to_be_visible()
                    assert abs(page.locator("#vibe-model-card").bounding_box()["width"] - page.locator("#model-test-model").bounding_box()["width"]) < 1
                    expect(page.locator("#vae-test-model")).to_have_value("f16")
                    expect(page.locator("#setup-test-model")).to_be_disabled()
                    expect(page.locator("#model-test-model .model-licenses")).to_contain_text("MIT")
                    expect(page.locator("#model-test-model .model-licenses")).to_contain_text("monetize outputs")
                    expect(page.locator("#model-test-model .model-licenses")).to_contain_text("company use")
                    assert page.locator("#model-progress").count() == 0
                    assert page.locator("#precision-test-external").count() == 0
                    assert page.locator("#vae-test-external").count() == 0
                    page.locator("#precision-test-model").select_option("bf16")
                    page.locator("#vae-test-model").select_option("f32")
                    expect(page.locator("#setup-test-model")).to_be_disabled()
                    page.locator("#license-test-model").check()
                    page.locator("#setup-test-model").click()
                    expect(page.locator("#model-test-model progress")).to_be_visible()
                    expect(page.locator("#settings-message")).to_contain_text("Active: Test model · BF16 · VAE F32", timeout=15000)
                    expect(page.locator("#setup-test-model")).to_have_text("Active · Verified")
                    expect(page.locator("#setup-test-model")).to_be_disabled()
                    page.reload()
                    expect(page.locator("#precision-test-model")).to_have_value("bf16")
                    expect(page.locator("#vae-test-model")).to_have_value("f32")
                    expect(page.locator("#license-test-model")).to_be_checked()
                    expect(page.locator("#setup-test-model")).to_have_text("Active · Verified")
                    page.locator("#precision-test-model").select_option("q8_0")
                    expect(page.locator("#license-test-model")).to_be_checked()
                    expect(page.locator("#setup-test-model")).to_have_text("Download and activate")
                    page.locator("#precision-test-model").select_option("bf16")
                    expect(page.locator(".model-verification").first).to_contain_text("Verified")
                    expect(page.locator("#setup-test-model")).to_have_text("Active · Verified")
                    expect(page.locator("#progress-test-model")).to_be_hidden()
                    page.locator("#license-test-separator").check()
                    page.locator("#setup-test-separator").click()
                    expect(page.locator("#model-test-separator progress")).to_be_visible()
                    expect(page.locator("#setup-test-separator")).to_have_text("Active · Verified", timeout=15000)
                    expect(page.locator("#setup-test-separator")).to_be_disabled()
                    expect(page.locator("#progress-test-separator")).to_be_hidden()
                    expect(page.locator("#repair-test-separator")).to_be_hidden()
                    page.locator("#precision-test-separator").select_option("bf16")
                    page.locator("#setup-test-separator").click()
                    expect(page.locator("#progress-test-separator")).to_contain_text("Test device does not support this precision", timeout=15000)
                    expect(page.locator("#progress-test-model")).to_be_hidden()
                    page.locator("#precision-test-separator").select_option("q8_0")
                    expect(page.locator("#setup-test-separator")).to_be_disabled()
                    page.locator("#model-test-separator summary").click()
                    page.locator("#repair-test-separator").click()
                    expect(page.locator("#model-test-separator progress")).to_be_visible()
                    expect(page.locator("#setup-test-separator")).to_have_text("Active · Verified", timeout=15000)
                    expect(page.locator("#progress-test-separator")).to_be_hidden()
                    assert page.locator(".model-job").count() == 0
                    page.screenshot(path=str(args.artifacts / "settings-desktop.png"))
                    page.locator("#nav-create").click()
                    expect(page.locator("#go")).to_be_enabled()
                    expect(page.locator("#cot")).to_be_hidden()  # the fake provider offers no planning
                    expect(page.locator("#abc")).to_be_hidden()
                    expect(page.locator("#demo-row [data-demo='lux-tenebris']")).to_have_count(1)
                    expect(page.locator(".template-btn")).to_have_count(5)
                    page.locator("#genre-templates summary").click()
                    page.locator("#demo-row [data-demo='lux-tenebris']").click()
                    demo_lyrics = page.locator("#lyrics").input_value()
                    page.locator("#title").fill("My working title")
                    before_template = page.evaluate("({title: $('title').value, seed: $('seed').value, cot: state.cot})")
                    generation_posts = []
                    page.on("request", lambda request: generation_posts.append(request.url) if request.method == "POST" and request.url.endswith("/api/generate") else None)
                    for template in ["progressive-metal", "indie-pop", "cinematic-synthwave", "soul-rnb", "jazz-fusion"]:
                        page.locator("#lyrics").fill("Custom lyrics before choosing " + template)
                        page.locator(f"[data-template='{template}']").click()
                        expect(page.locator(f"[data-template='{template}']")).to_have_attribute("aria-pressed", "true")
                        expect(page.locator("#lyrics")).to_have_value(demo_lyrics)
                        assert page.evaluate("({title: $('title').value, seed: $('seed').value, cot: state.cot})") == before_template
                    assert not generation_posts, generation_posts
                    page.locator("[data-template='progressive-metal']").click()
                    assert "progressive metal" in page.locator("#style").input_value()
                    expect(page.locator("#template-status")).to_contain_text("Progressive Metal template applied")
                    page.locator("#style").fill("My custom sound")
                    expect(page.locator("[data-template='progressive-metal']")).to_have_attribute("aria-pressed", "false")
                    page.locator("[data-template='progressive-metal']").click()
                    assert page.locator(".create").bounding_box()["width"] == 520
                    page.locator(".create").evaluate("panel => panel.scrollTop = 0")
                    page.screenshot(path=str(args.artifacts / "templates-desktop.png"))
                    for width in [1280, 1024, 900, 390]:
                        page.set_viewport_size({"width": width, "height": 844})
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Overflow at {width}px"
                    page.locator("#genre-templates").scroll_into_view_if_needed()
                    expect(page.locator("[data-template='progressive-metal']")).to_be_visible()
                    page.screenshot(path=str(args.artifacts / "templates-mobile.png"))
                    page.set_viewport_size({"width": 1440, "height": 1000})
                    page.locator("#go").click()
                    expect(page.locator(".song")).to_have_count(2, timeout=15000)
                    # Vibe uses fake embeddings and a real synthetic image; no weights are loaded.
                    entry = json.loads((ROOT / "studio/data/vibe-style-catalog.json").read_text())["entries"][0]
                    page.route("**/api/vibe/status", lambda route: route.fulfill(json={"installed": True, "runtime_compatible": True, "job": None}))
                    page.route("**/api/vibe/analyze", lambda route: route.fulfill(json={"entry_id": entry["id"], "style": "Synthetic piano and soft strings"}))
                    before_vibe = page.evaluate("({lyrics: $('lyrics').value, title: $('title').value, seed: $('seed').value, cot: state.cot})")
                    posts_before_vibe = len(generation_posts)
                    page.locator("#nav-vibe").click()
                    expect(page.locator("#vibe")).to_be_visible()
                    expect(page.locator(".workspace")).to_be_hidden()
                    expect(page.locator(".create")).to_be_hidden()
                    page.locator("#vibe-file").set_input_files({"name": "synthetic.png", "mimeType": "image/png", "buffer": synthetic_png()})
                    page.locator("#vibe-analyze").click()
                    expect(page.locator("#vibe-style")).to_have_value("Synthetic piano and soft strings")
                    page.locator("#vibe-style").fill("Synthetic edited piano direction")
                    page.locator("#vibe-use").click()
                    expect(page.locator("#style")).to_have_value("Synthetic edited piano direction")
                    assert page.evaluate("({lyrics: $('lyrics').value, title: $('title').value, seed: $('seed').value, cot: state.cot})") == before_vibe
                    assert len(generation_posts) == posts_before_vibe
                    expect(page.locator("#create-vibe-reference")).to_be_visible()
                    page.locator("#title").fill("Synthetic Vibe cover")
                    page.locator("#go").click()
                    vibe_row = page.locator(".song[data-name]").filter(has_text="Synthetic Vibe cover")
                    expect(vibe_row).to_have_count(1, timeout=15000)
                    expect(vibe_row).to_contain_text("Vibe · Image inspired")
                    image_src = vibe_row.locator(".cover img").get_attribute("src")
                    saved_image = page.request.get(urljoin(page.url, image_src))
                    assert saved_image.ok and saved_image.headers["content-type"] == "image/jpeg"
                    # The handoff is single-use: the next song from Create has no Vibe images.
                    expect(page.locator("#create-vibe-reference")).to_be_hidden()
                    assert page.evaluate("Vibe.generationReference()") == {}
                    page.reload()
                    expect(vibe_row.locator(".cover img")).to_have_attribute("src", image_src)
                    page.evaluate("audio.loop = true")
                    vibe_row.locator(".cover").click()
                    expect(page.locator("#vibe-listening")).to_have_class(re.compile("open"))
                    expect(page.locator("#vibe-listening")).to_have_css("opacity", "1")
                    assert page.locator("#vibe-listening-image").bounding_box()["width"] > 300
                    expect(page.locator("#p-cover")).to_have_attribute("src", image_src)
                    expect(page.locator("#p-play")).to_be_visible()
                    page.screenshot(path=str(args.artifacts / "vibe-listening-desktop.png"))
                    page.locator("#vibe-listening-close").click()
                    expect(page.locator("#vibe-listening")).to_be_hidden()
                    assert page.evaluate("!audio.paused")
                    page.locator("#p-play").click(); page.locator("#p-play").click()
                    expect(page.locator("#vibe-listening")).to_be_hidden()
                    page.locator("#p-artwork").click()
                    expect(page.locator("#vibe-listening")).to_have_class(re.compile("open"))
                    page.keyboard.press("Escape")
                    expect(page.locator("#vibe-listening")).to_be_hidden()
                    vibe_row.locator("[data-act='info']").click()
                    expect(page.locator("#drawer")).to_contain_text("Image inspiration · Lux Vibe")
                    expect(page.locator("#drawer .d-hero img")).to_have_attribute("src", image_src)
                    page.locator("#drawer [data-act='dimage']").click()
                    page.set_viewport_size({"width": 390, "height": 844})
                    expect(page.locator("#vibe-listening")).to_have_class(re.compile("open"))
                    expect(page.locator("#vibe-listening")).to_have_css("opacity", "1")
                    expect(page.locator("#vibe-listening-close")).to_be_visible()
                    expect(page.locator("#p-play")).to_be_in_viewport()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    page.screenshot(path=str(args.artifacts / "vibe-listening-mobile.png"))
                    page.emulate_media(reduced_motion="reduce")
                    expect(page.locator("#vibe-listening")).to_have_css("transition-duration", "0s")
                    page.keyboard.press("Escape")
                    expect(page.locator("#vibe-listening")).to_be_hidden()
                    page.emulate_media(reduced_motion="no-preference")
                    page.evaluate("audio.pause(); audio.loop = false; closeDrawer(); setTrack(state.library.find(s => s.name === 'legacy-song')); audio.dispatchEvent(new Event('play'))")
                    expect(page.locator("#vibe-listening")).to_be_hidden()
                    page.set_viewport_size({"width": 1440, "height": 1000})
                    # Five-image blending, Advanced opt-out, composite colors and carousel.
                    entries = json.loads((ROOT / "studio/data/vibe-style-catalog.json").read_text())["entries"][:5]
                    advanced = {"label": "Contrasting textures", "explanation": "Synthetic creative preset; edit in Advanced.",
                                "model_id": "test-model", "options": {"semantic_temperature": 1.1, "semantic_top_p": .97, "semantic_top_k": 140, "num_inference_steps": 8}}
                    page.unroute("**/api/vibe/analyze")
                    page.route("**/api/vibe/analyze", lambda route: route.fulfill(json={"entry_id": entries[0]["id"], "entry_ids": [entry["id"] for entry in entries], "image_count": 5,
                        "style": "Synthetic multi-image direction", "advanced": advanced}))
                    page.evaluate("$('semantic_temperature').value = .85; $('semantic_temperature').oninput()")
                    page.locator("#lyrics").fill("   ")
                    page.locator("#nav-vibe").click()
                    colors = [(40, 80, 120), (180, 50, 60), (45, 150, 80), (220, 150, 40), (125, 65, 165)]
                    files = [{"name": f"synthetic-{i}.png", "mimeType": "image/png", "buffer": synthetic_png(color)} for i, color in enumerate(colors)]
                    page.locator("#vibe-file").set_input_files(files + [files[0]])
                    expect(page.locator("#vibe-error")).to_contain_text("up to 5 images")
                    expect(page.locator(".vibe-thumb")).to_have_count(0)
                    page.locator("#vibe-file").set_input_files(files)
                    expect(page.locator(".vibe-thumb")).to_have_count(5)
                    page.locator("[data-vibe-remove='4']").click()
                    expect(page.locator(".vibe-thumb")).to_have_count(4)
                    page.locator("#vibe-file").set_input_files(files[4])
                    page.locator("[data-vibe-move='0'][data-direction='1']").click()
                    expect(page.locator(".vibe-thumb figcaption").first).to_have_text("synthetic-1.png")
                    page.locator("[data-vibe-move='1'][data-direction='-1']").click()
                    page.locator("#vibe-analyze").click()
                    expect(page.locator("#vibe-use-advanced")).to_be_checked()
                    page.locator("#vibe-use-advanced").uncheck()
                    page.locator("#vibe-use").click()
                    expect(page.locator("#lyrics")).to_have_value(default_lyrics)
                    expect(page.locator("#lyrics-count")).to_contain_text("5 lines")
                    expect(page.locator("#semantic_temperature")).to_have_value("0.85")
                    page.locator("#nav-vibe").click()
                    page.locator("#vibe-use-advanced").check()
                    page.locator("#vibe-use").click()
                    expect(page.locator("#semantic_temperature")).to_have_value("1.1")
                    expect(page.locator("#num_inference_steps")).to_have_value("8")
                    expect(page.locator("#create-vibe-reference img")).to_have_count(5)
                    page.locator("#title").fill("Five-image Vibe song")
                    with page.expect_request("**/api/generate") as multi_generation:
                        page.locator("#go").click()
                    body = multi_generation.value.post_data_json
                    assert len(body["vibe_images"]) == 5 and body["model_options"]["semantic_temperature"] == 1.1
                    expect(page.locator("#create-vibe-reference")).to_be_hidden()
                    expect(page.locator("#semantic_temperature")).to_have_value("1")
                    expect(page.locator("#num_inference_steps")).to_have_value("8")
                    assert "semantic_temperature" not in page.evaluate("Settings.options()")
                    multi_row = page.locator(".song[data-name]").filter(has_text="Five-image Vibe song")
                    expect(multi_row).to_have_count(1, timeout=15000)
                    expect(multi_row).to_contain_text("Vibe · 5 images")
                    multi_cover = multi_row.locator(".cover img").get_attribute("src")
                    pixels = page.evaluate("""async src => {
                        const bitmap = await createImageBitmap(await (await fetch(src)).blob());
                        const canvas = document.createElement('canvas'); canvas.width = bitmap.width; canvas.height = bitmap.height;
                        const ctx = canvas.getContext('2d'); ctx.drawImage(bitmap, 0, 0); bitmap.close();
                        return [[300,600],[750,300],[1050,300],[750,900],[1050,900]].map(([x,y]) => Array.from(ctx.getImageData(x,y,1,1).data).slice(0,3));
                    }""", multi_cover)
                    assert all(abs(actual - expected) < 10 for pixel, color in zip(pixels, colors) for actual, expected in zip(pixel, color)), pixels
                    # Lyrics writer: Settings, Create concept and Vibe mood use a fake OpenAI-compatible boundary.
                    lyrics_status = {"configured": False, "base_url": "", "model": "", "api_key_set": False, "api_key_from_env": False,
                                     "supports_images": False, "temperature": .8, "state_error": None,
                                     "moods": [{"id": "dreamy", "label": "Dreamy", "hint": "soft"}, {"id": "hopeful", "label": "Hopeful", "hint": "bright"}]}
                    lyrics_posts = []
                    def lyrics_settings(route):
                        body = route.request.post_data_json
                        assert body["api_key"] == "sk-synthetic" and body["base_url"] == "http://llm.test/v1" and body["model"] == "model-b"
                        lyrics_status.update(configured=True, base_url=body["base_url"], model=body["model"], api_key_set=True)
                        route.fulfill(json=lyrics_status)
                    def lyrics_generate(route):
                        lyrics_posts.append(route.request.post_data_json)
                        route.fulfill(json={"lyrics": f"[Verse]\nSynthetic written line {len(lyrics_posts)}", "used_images": 0})
                    page.route("**/api/lyrics/status", lambda route: route.fulfill(json=lyrics_status))
                    page.route("**/api/lyrics/settings", lyrics_settings)
                    page.route("**/api/lyrics/test", lambda route: route.fulfill(json={"ok": True, "models": ["model-a"]}))
                    page.route("**/api/lyrics/discover", lambda route: route.fulfill(json={"servers": [
                        {"name": "Synthetic server", "base_url": "http://llm.test/v1", "models": ["model-a", "model-b"]}]}))
                    page.route("**/api/lyrics/models", lambda route: route.fulfill(json={"base_url": "http://llm.test/v1", "models": ["model-a", "model-b"]}))
                    page.route("**/api/lyrics/generate", lyrics_generate)
                    style_posts = []
                    def lyrics_style(route):
                        style_posts.append(route.request.post_data_json)
                        route.fulfill(json={"style": f"English, jazz ballad, 80 BPM, piano, strings, dreamy, smooth lead vocal, take {len(style_posts)}"})
                    page.route("**/api/lyrics/style", lyrics_style)
                    page.evaluate("Lyrics.refresh()")
                    expect(page.locator("#lyrics-setup-link")).to_be_visible()
                    expect(page.locator("#lyrics-write")).to_be_disabled()
                    page.locator("#nav-settings").click()
                    expect(page.locator("#lyrics-model-card")).to_be_visible()
                    page.evaluate("Lyrics.refresh()")
                    page.locator("#lyrics-discover").click()
                    page.locator("[data-lyrics-server='0']").click()
                    expect(page.locator("#lyrics-base-url")).to_have_value("http://llm.test/v1")
                    expect(page.locator("#lyrics-model")).to_have_value("model-a")
                    page.locator("#lyrics-model").select_option("model-b")
                    page.locator("#lyrics-api-key").fill("sk-synthetic")
                    page.locator("#lyrics-test").click()
                    expect(page.locator("#lyrics-settings-message")).to_contain_text("Connected")
                    expect(page.locator("#lyrics-api-key")).to_have_value("")
                    expect(page.locator("#lyrics-api-key")).to_have_attribute("placeholder", re.compile("Saved"))
                    page.locator("#nav-create").click()
                    expect(page.locator("#lyrics-setup-link")).to_be_hidden()
                    page.locator("#concept").fill("Synthetic concept")
                    page.locator("#lyrics-write").click()
                    expect(page.locator("#lyrics")).to_have_value("[Verse]\nSynthetic written line 1")
                    assert lyrics_posts[-1]["concept"] == "Synthetic concept"
                    assert style_posts[0]["concept"] == "Synthetic concept" and "jazz" in style_posts[0]["vocabulary"]
                    expect(page.locator("#style")).to_have_value("English, jazz ballad, 80 BPM, piano, strings, dreamy, smooth lead vocal, take 1")
                    assert lyrics_posts[-1]["style"].endswith("take 1")
                    expect(page.locator(".chip[data-c='piano']")).to_have_class(re.compile("on"))
                    expect(page.locator("#lyrics-write")).to_have_text("Regenerate")
                    page.locator("#lyrics-write").click()
                    expect(page.locator("#lyrics")).to_have_value("[Verse]\nSynthetic written line 2")
                    expect(page.locator("#style")).to_have_value(re.compile("take 2$"))
                    page.locator("#lyrics-undo").click()
                    expect(page.locator("#lyrics")).to_have_value("[Verse]\nSynthetic written line 1")
                    expect(page.locator("#style")).to_have_value(re.compile("take 1$"))
                    page.unroute("**/api/vibe/analyze")
                    page.route("**/api/vibe/analyze", lambda route: route.fulfill(json={"entry_id": entries[0]["id"], "entry_ids": [entries[0]["id"]], "image_count": 5,
                        "style": "Synthetic multi-image direction", "mood": "hopeful", "visual": "Synthetic scene"}))
                    page.locator("#nav-vibe").click()
                    page.locator("#vibe-again").click()
                    expect(page.locator("#vibe-lyrics")).to_have_value("[Verse]\nSynthetic written line 3")
                    expect(page.locator("#vibe-mood")).to_have_value("hopeful")
                    assert lyrics_posts[-1]["mood"] == "hopeful" and lyrics_posts[-1]["visual"] == "Synthetic scene" and lyrics_posts[-1]["images"] == []
                    page.locator("#vibe-mood").select_option("custom")
                    page.locator("#vibe-mood-custom").fill("Synthetic theme")
                    page.locator("#vibe-mood-custom").press("Enter")
                    expect(page.locator("#vibe-lyrics")).to_have_value("[Verse]\nSynthetic written line 4")
                    assert lyrics_posts[-1]["custom"] == "Synthetic theme" and lyrics_posts[-1]["mood"] == ""
                    page.screenshot(path=str(args.artifacts / "vibe-lyrics-desktop.png"))
                    page.locator("#vibe-use").click()
                    expect(page.locator("#lyrics")).to_have_value("[Verse]\nSynthetic written line 4")
                    for path in ("status", "settings", "test", "generate", "discover", "models", "style"):
                        page.unroute(f"**/api/lyrics/{path}")
                    page.reload()
                    tone_path = "**/outputs/" + multi_row.get_attribute("data-name") + ".wav"
                    page.route(tone_path, lambda route: route.fulfill(body=reactive_wav(), content_type="audio/wav"))
                    page.evaluate("audio.loop = true")
                    multi_row.locator(".cover").click()
                    expect(page.locator("#vibe-slide-count")).to_have_text("1 / 5")
                    expect(page.locator("#vibe-listening")).to_have_class(re.compile("open"))
                    expect(page.locator("#vibe-slide-count")).to_have_text("2 / 5", timeout=12000)
                    page.locator("#vibe-slide-pause").click()
                    expect(page.locator("#vibe-slide-pause")).to_have_text("Resume slideshow")
                    page.wait_for_timeout(8500)
                    expect(page.locator("#vibe-slide-count")).to_have_text("2 / 5")
                    page.locator("#vibe-slide-next").click()
                    expect(page.locator("#vibe-slide-count")).to_have_text("3 / 5")
                    check_reactive_effects(page, expect, args.artifacts)
                    assert page.evaluate("!audio.paused")
                    page.set_viewport_size({"width": 390, "height": 844})
                    expect(page.locator("#vibe-slide-next")).to_be_in_viewport()
                    expect(page.locator("#p-play")).to_be_in_viewport()
                    expect(page.locator("#vibe-effects-toggle")).to_be_in_viewport()
                    page.screenshot(path=str(args.artifacts / "vibe-effects-mobile.png"))
                    page.emulate_media(reduced_motion="reduce")
                    expect(page.locator("#vibe-effects-toggle")).to_be_disabled()
                    expect(page.locator("#vibe-effects")).to_have_css("opacity", "0")
                    expect(page.locator("#vibe-slide-pause")).to_be_disabled()
                    page.locator("#vibe-slide-prev").click()
                    expect(page.locator("#vibe-slide-count")).to_have_text("2 / 5")
                    page.screenshot(path=str(args.artifacts / "vibe-carousel-mobile.png"))
                    page.keyboard.press("Escape")
                    expect(page.locator("#vibe-listening")).to_be_hidden()
                    page.emulate_media(reduced_motion="no-preference")
                    page.locator("#p-artwork").click()
                    page.locator("#vibe-effects-toggle").click()
                    expect(page.locator("#vibe-effects-toggle")).to_have_text("Effects Off")
                    page.reload()
                    expect(page.locator("#vibe-effects-toggle")).to_have_text("Effects Off")
                    page.evaluate("audio.pause(); audio.loop = false; setTrack(state.library.find(s => s.name === 'legacy-song'))")
                    page.set_viewport_size({"width": 1440, "height": 1000})
                    def stem_set(route):
                        route.fulfill(json=[{"id": "vocals", "mode": "vocals", "mode_label": "Vocals / Instrumental",
                            "prompt": None, "elapsed_s": 0.1, "stems": [{"id": name, "label": name,
                                "file": f"ui-stems/{name}.wav", "peaks": [0.1] * 16, "rms_db": -20, "silent": False}
                                for name in ("vocals", "instrumental")]}])
                    page.route("**/api/lux/*", stem_set)
                    page.route("**/api/beats/*", lambda route: route.fulfill(json={"bpm": 120, "offset_s": 0, "beat_s": 0.5, "beats_per_bar": 4}))
                    page.locator("#nav-vibe").click()
                    page.evaluate("Lux.open('legacy-song')")
                    expect(page.locator("#lux")).to_be_visible()
                    expect(page.locator("#vibe")).to_be_hidden()
                    expect(page.locator(".sidebar nav a.active")).to_have_count(1)
                    expect(page.locator(".lx-track")).to_have_count(2)
                    expect(page.locator(".lx-edit-btn")).to_have_count(0)
                    song = page.evaluate("state.library.find((song) => song.name !== 'legacy-song').name")
                    page.evaluate("name => Lux.open(name)", song)
                    expect(page.locator(".lx-track")).to_have_count(2)
                    expect(page.locator(".lx-edit-btn")).to_have_count(2)
                    page.locator(".lx-edit-btn").first.click()
                    expect(page.locator("#lx-editbar")).to_contain_text("Editing vocals")
                    page.locator("[data-lx='new']").click()
                    expect(page.locator("[data-lx='mode'][data-mode='anything']")).to_have_count(0)
                    expect(page.locator("[data-lx='mode']")).to_have_count(3)
                    # Duration is inferred within the one Generate request.
                    analysis_capable = True
                    def duration_capability(route):
                        data = route.fetch().json()
                        data["active"]["capabilities"].update(target_duration_s=330, min_target_duration_s=30,
                            max_duration_s=360, planning=["off", "melody", "full"], instrumental=True,
                            duration_analysis=analysis_capable)
                        route.fulfill(json=data)
                    expect(page.locator("#instrumental-toggle")).to_be_hidden()  # the fake provider has no instrumental mode
                    page.route("**/api/settings/status", duration_capability)
                    page.locator("#nav-create").click()
                    page.evaluate("Settings.refresh(true)")
                    expect(page.locator("#duration-mode")).to_have_count(0)
                    expect(page.locator("#duration-hint")).to_be_visible()
                    page.locator("#lyrics").fill("[Verse]\n" + "light " * 100)
                    expect(page.locator("#lyrics-advice")).to_contain_text("closing lyric phrase")
                    expect(page.locator("#cot")).to_be_visible()
                    expect(page.locator("#cot [data-v='off']")).to_have_class("on")
                    for mode in ("off", "melody", "full"):
                        button = page.locator(f"#cot [data-v='{mode}']")
                        expect(button.locator("svg")).to_have_count(1)
                        button.hover()
                        expect(button.locator("[role='tooltip']")).to_be_visible()
                        button.focus()
                        page.keyboard.press("Tab")
                        page.keyboard.press("Shift+Tab")
                        page.mouse.move(1000, 200)
                        expect(button.locator("[role='tooltip']")).to_be_visible()
                    page.locator("#cot [data-v='melody']").click()
                    with page.expect_request("**/api/generate") as generation_request:
                        page.locator("#go").click()
                    body = generation_request.value.post_data_json
                    assert "target_duration_s" not in body and "max_duration_s" not in body, body
                    assert body["model_options"]["cot"] == "melody", body
                    assert "instrumental" not in body, body
                    page.locator("#instrumental-toggle").click()
                    expect(page.locator("#lyrics")).to_be_hidden()
                    expect(page.locator("#lyrics-advice")).to_contain_text("No vocals")
                    page.route("**/api/generate", lambda route: route.fulfill(json={}))
                    with page.expect_request("**/api/generate") as instrumental_request:
                        page.locator("#go").click()
                    assert instrumental_request.value.post_data_json["instrumental"] is True
                    page.unroute("**/api/generate")
                    page.locator("#instrumental-toggle").click()
                    expect(page.locator("#lyrics")).to_be_visible()
                    page.evaluate("state.library[0].generation = {status:'truncated', message:'Stopped at the hard limit. The song may be unfinished.'}; render()")
                    expect(page.locator(".badge").filter(has_text="Unfinished · limit reached")).to_be_visible()
                    page.evaluate("state.library[0].generation = {status:'model_end', shorter_than_target:true, target_duration_s:330}; state.library[0].duration_s = 229; render()")
                    expect(page.locator(".badge").filter(has_text="Shorter than target · 3:49 of 5:30")).to_be_visible()
                    page.screenshot(path=str(args.artifacts / "duration-desktop.png"))
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.locator("#duration-hint").scroll_into_view_if_needed()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    page.screenshot(path=str(args.artifacts / "duration-mobile.png"))
                    page.unroute("**/api/generate")
                    page.unroute("**/api/jobs")
                    analysis_capable = False
                    page.evaluate("Settings.refresh(true)")
                    page.locator(".song[data-name='legacy-song'] [data-act='info']").click()
                    for fmt, media in {"flac": "audio/flac", "mp3": "audio/mpeg"}.items():
                        link = page.locator(f"#drawer a[href='/api/export/legacy-song?format={fmt}']")
                        expect(link).to_have_text(fmt.upper())
                        exported = page.request.get(urljoin(page.url, link.get_attribute("href")))
                        assert exported.ok and exported.headers["content-type"] == media and exported.body(), fmt
                    page.once("dialog", lambda dialog: dialog.dismiss())
                    page.locator("#drawer [data-act='ddelete']").click()
                    expect(page.locator("#drawer")).to_have_class(re.compile("open"))
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.locator("#drawer [data-act='ddelete']").click()
                    expect(page.locator(".song[data-name='legacy-song']")).to_have_count(0)
                    expect(page.locator("#drawer")).not_to_have_class(re.compile("open"))
                    page.evaluate("state.jobs = [{id:'held', kind:'generate', status:'running', params:{title:'Held', style:'Piano'}, created:0, started:0, now:0, eta_s:60}]; state.jobsAt = Date.now(); render()")
                    with page.expect_request("**/api/jobs/held/cancel") as stop_request:
                        page.locator(".song[data-job='held'] [data-act='cancel']").click()
                    assert stop_request.value.method == "POST"
                    page.unroute("**/api/settings/status", duration_capability)
                    page.locator(".mobile-nav a[href='#/settings']").click(); page.set_viewport_size({"width": 390, "height": 844})
                    expect(page.locator(".mobile-nav")).to_be_visible()
                    page.locator(".mobile-nav a[href='#/']").click()
                    expect(page.locator(".workspace")).to_be_visible()
                    page.locator(".mobile-nav a[href='#/settings']").click()
                    expect(page.locator("#settings")).to_be_visible()
                    page.screenshot(path=str(args.artifacts / "settings-mobile.png"))
                    page.locator("#license-test-external").check()
                    page.locator("#setup-test-external").click()
                    expect(page.locator("#settings-message")).to_contain_text("Active: Test external", timeout=15000)
                    def unresolved_license(route):
                        data = route.fetch().json()
                        data["models"][0]["licenses"][0]["verified"] = False
                        route.fulfill(json=data)
                    page.route("**/api/settings/catalog", unresolved_license)
                    page.reload()
                    expect(page.locator("#license-test-model")).to_be_disabled()
                    expect(page.locator("#setup-test-model")).to_be_disabled()
                    assert not errors, errors
                    # A failed optional AudioContext must leave the native player usable.
                    fallback = browser.new_context(viewport={"width": 1440, "height": 1000})
                    fallback_page = fallback.new_page()
                    fallback_page.route("https://**/*", lambda route: route.abort())
                    fallback_page.add_init_script("window.AudioContext = class { constructor() { throw new Error('Synthetic unavailable context'); } }")
                    fallback_page.goto(url + "/#/")
                    fallback_page.evaluate("audio.loop = true")
                    fallback_page.locator(".song[data-name]").filter(has_text="Five-image Vibe song").locator(".cover").click()
                    expect(fallback_page.locator("#vibe-effects-toggle")).to_be_disabled()
                    expect(fallback_page.locator("#vibe-effects-message")).to_contain_text("Playback continues")
                    assert fallback_page.evaluate("!audio.paused")
                    fallback.close()
                    if args.readme_screenshots:
                        from readme_screenshots import capture
                        capture(browser, url, ROOT / "docs/images")
                    browser.close()
                print(json.dumps({"vibe_effects_unavailable_preserves_playback": True,
                                  "vibe_effects_follow_live_audio_and_silence": True, "vibe_effects_pause_and_visibility": True,
                                  "vibe_effects_toggle_persists_without_stopping_audio": True, "vibe_effects_single_media_source": True,
                                  "vibe_five_image_validation_and_order": True, "vibe_advanced_opt_out_and_transfer": True,
                                  "vibe_composite_contains_all_images": True, "vibe_carousel_auto_manual_and_pause": True,
                                  "vibe_style_transfer_preserves_form": True, "vibe_cover_survives_reload": True, "lyrics_writer_settings_create_vibe": True,
                                  "vibe_listening_desktop_mobile": True, "vibe_close_reopen_and_resume": True,
                                  "vibe_reduced_motion": True, "settings_first": True, "license_gate": True, "independent_precision": True,
                                  "fake_download_and_activation": True, "capability_controls": True,
                                  "generation_and_library": True, "five_templates_without_generation": True, "templates_share_techno_lyrics": True, "templates_preserve_title_and_settings": True, "wider_create_and_responsive_layout": True, "implicit_duration_analysis_without_manual_control": True, "lyric_advice_and_truncation_badge": True, "instrumental_switch": True, "shorter_than_target_badge": True, "mobile_navigation": True, "external_without_weights": True, "verification_survives_reload_and_dropdown": True, "separator_disabled_when_active": True, "card_progress_and_errors_only": True, "flac_and_mp3_downloads": True, "delete_song_with_confirmation": True, "generation_stop_button": True, "creator_terms_visible": True, "mixer_editable_and_legacy_songs": True, "unresolved_license_blocked": True, "javascript_errors": errors}))
            finally:
                server.terminate()
                try: server.wait(timeout=10)
                except subprocess.TimeoutExpired: server.kill(); server.wait()


if __name__ == "__main__": main()
