"""Optional lyrics writer through an OpenAI-compatible chat completions endpoint.

Song concepts, lyrics and images are private: never log them or store them here.
"""

import base64
import json
import os
import re
import threading
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .providers import ROOT

SECTIONS = ("Intro", "Verse", "Pre-Chorus", "Chorus", "Bridge", "Outro")
MAX_LYRICS_CHARS = 3000
MAX_LYRICS_IMAGES = 5
MAX_IMAGE_DATA_URL = 4 * 1024 * 1024
IMAGE_DATA_URL = re.compile(r"^data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)$")

# Common default addresses of local OpenAI-compatible servers, probed only on request.
LOCAL_SERVERS = [
    ("LM Studio", "http://localhost:1234/v1"),
    ("Ollama", "http://localhost:11434/v1"),
    ("llama.cpp / mlx-lm", "http://localhost:8080/v1"),
    ("vLLM", "http://localhost:8000/v1"),
    ("LocalAI / Jan", "http://localhost:1337/v1"),
]
DISCOVERY_TIMEOUT = 1.5

MOODS = [
    {"id": "uplifting", "label": "Uplifting", "hint": "bright, rising and encouraging"},
    {"id": "hopeful", "label": "Hopeful", "hint": "a new beginning, quiet confidence about tomorrow"},
    {"id": "joyful", "label": "Joyful", "hint": "playful celebration, friends and shared happiness"},
    {"id": "romantic", "label": "Romantic", "hint": "tender closeness, longing and warmth between two people"},
    {"id": "peaceful", "label": "Peaceful", "hint": "calm, slow and grounded in simple details"},
    {"id": "dreamy", "label": "Dreamy", "hint": "floating, hazy imagery and soft wonder"},
    {"id": "nostalgic", "label": "Nostalgic", "hint": "memories, places from the past and bittersweet warmth"},
    {"id": "melancholic", "label": "Melancholic", "hint": "loneliness, rain-soaked reflection and gentle sadness"},
    {"id": "introspective", "label": "Introspective", "hint": "inner thoughts, self-questioning and honest confession"},
    {"id": "mysterious", "label": "Mysterious", "hint": "hidden paths, secrets and the unknown"},
    {"id": "dark", "label": "Dark", "hint": "tension, shadows and struggle"},
    {"id": "energetic", "label": "Energetic", "hint": "motion, speed and a driving pulse"},
    {"id": "epic", "label": "Epic", "hint": "vast scale, courage and a triumphant climb"},
]
MOOD_IDS = {mood["id"] for mood in MOODS}

SYSTEM_PROMPT = (
    "You are a songwriter. Write original song lyrics only.\n"
    "Rules:\n"
    f"- Mark each section with one of these tags on its own line: {', '.join(f'[{s}]' for s in SECTIONS)}.\n"
    "- Write two verses, a chorus that returns after each verse, and an optional bridge. End with an [Outro] "
    "that closes the song with a short final phrase.\n"
    "- Keep lines short and singable, with natural rhythm and some rhyme. Use 4 lines per section at most.\n"
    "- Do not write a title, explanations, notes, chords, performance directions or any text outside the lyrics.\n"
    "- Write in the language the user asks for, otherwise in English."
)


MAX_STYLE_CHARS = 600
STYLE_PROMPT = (
    "You are a music producer. Write the style prompt for a song generator from the user's request.\n"
    "Rules:\n"
    "- Reply with one line of 10 to 16 short comma-separated tags and nothing else.\n"
    "- Order: the language the lyrics are sung in (English unless the request asks for another), genre and "
    "subgenre, tempo as '<number> BPM', main instruments, vocal type, mood, arrangement, mix.\n"
    "- Follow every explicit wish in the request (genre, tempo, instruments, voice, era, mood).\n"
    "- No artist or song names, no sentences, no quotes.\n"
    "Example: English, indie pop, 110 BPM, bright acoustic guitar, warm bass, soft punchy drums, intimate lead "
    "vocal, layered chorus harmonies, catchy melodic hook, gentle build-up, resolved outro, warm polished mix"
)
VOCAL_TAG = re.compile(r"vocal|voice|singer|sung|choir|rap|harmon", re.I)


def clean_style(text: str, instrumental=False) -> str:
    """Keep a single comma-separated style prompt from a model reply."""
    text = re.sub(r"<think>.*?(</think>|$)", "", text or "", flags=re.S | re.I).replace("```", "")
    lines = [re.sub(r"^\W*(style( of music| prompt)?|tags)\s*:\s*", "", line.strip(), flags=re.I).strip(" *\"'`-")
             for line in text.splitlines()]
    tags = []
    for part in ", ".join(line for line in lines if line).split(","):
        part = part.strip(" .*\"'`")
        if part and len(part) <= 80 and part.casefold() not in {tag.casefold() for tag in tags}:
            if not (instrumental and VOCAL_TAG.search(part)):
                tags.append(part)
    if instrumental and "instrumental" not in {tag.casefold() for tag in tags}:
        tags.append("instrumental")
    if len(tags) < 3:
        raise LyricsUpstreamError("The lyrics model did not return a usable style.")
    style = ", ".join(tags[:20])
    return style[:MAX_STYLE_CHARS].rsplit(",", 1)[0] if len(style) > MAX_STYLE_CHARS else style


class LyricsNotConfigured(ValueError):
    pass


class LyricsUpstreamError(RuntimeError):
    pass


def clean_lyrics(text: str) -> str:
    """Keep the lyric body of a model reply, with only the shared section tags."""
    text = re.sub(r"<think>.*?(</think>|$)", "", text or "", flags=re.S | re.I)
    fenced = re.search(r"```[^\n]*\n(.*?)```", text, flags=re.S)
    text = fenced.group(1) if fenced else text.replace("```", "")
    canonical = {section.casefold(): section for section in SECTIONS}
    canonical.update({"prechorus": "Pre-Chorus", "pre chorus": "Pre-Chorus", "hook": "Chorus"})
    lines, started = [], False
    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.strip().strip("*").strip()
        tag = re.fullmatch(r"\[?\s*([A-Za-z][A-Za-z -]*?)\s*(?:\d+)?\s*:?\s*\]?:?", line) if line else None
        name = tag and canonical.get(tag.group(1).strip().casefold())
        if name and (line.startswith("[") or line.endswith(":") or line.casefold() == name.casefold()):
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(f"[{name}]")
            started = True
        elif re.fullmatch(r"\[[^\]]*\]|\([^)]*\)", line):
            continue  # Performance notes and unknown tags are not sung.
        elif started:
            if line or (lines and lines[-1] != ""):
                lines.append(line)
    result = "\n".join(lines).strip()
    if len(result) > MAX_LYRICS_CHARS:
        result = result[:MAX_LYRICS_CHARS].rsplit("\n", 1)[0].strip()
    if not re.search(r"^[^\[\n].*$", result, flags=re.M):
        raise LyricsUpstreamError("The lyrics model did not return lyrics with section tags. Try again or "
                                  "choose a different model in Settings.")
    return result


def normalize_base_url(value) -> str:
    base_url = str(value or "").strip().rstrip("/")
    parsed = urlparse(base_url)
    if base_url and (parsed.scheme not in {"http", "https"} or not parsed.netloc):
        raise ValueError("Use an http:// or https:// base URL, for example http://localhost:1234/v1")
    return base_url


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}".casefold() if parsed.netloc else ""


def model_ids(data) -> list[str]:
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise LyricsUpstreamError("The endpoint did not return an OpenAI-compatible model list.")
    return sorted({item["id"] for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)})


def validate_image_data_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > MAX_IMAGE_DATA_URL:
        raise ValueError("Each lyrics image must be a JPG, PNG or WebP image under 3 MB")
    match = IMAGE_DATA_URL.match(value)
    if not match:
        raise ValueError("Each lyrics image must be a JPG, PNG or WebP image under 3 MB")
    try:
        base64.b64decode(match.group(2), validate=True)
    except ValueError as error:
        raise ValueError("A lyrics image could not be decoded") from error
    return value


class LyricsWriter:
    def __init__(self, state_dir=None, client=None):
        self.state_dir = Path(state_dir or os.environ.get("LUX_STATE_DIR", ROOT / ".lux"))
        self.path = self.state_dir / "lyrics.json"
        self.client = client or (lambda: httpx.Client(follow_redirects=True, timeout=120))
        self.lock = threading.Lock()
        self.state_error = None
        try:
            self.state = self._defaults() | json.loads(self.path.read_text())
            if self.state.get("schema_version") != 1:
                raise ValueError("Unsupported lyrics settings format")
        except FileNotFoundError:
            self.state = self._defaults()
        except (ValueError, OSError, TypeError) as error:
            self.state_error = f"Lyrics settings could not be read: {error}."
            self.state = self._defaults()

    @staticmethod
    def _defaults():
        return {"schema_version": 1, "base_url": "", "model": "", "api_key": "",
                "supports_images": False, "temperature": 0.8}

    def _api_key(self):
        return os.environ.get("LUX_LYRICS_API_KEY") or self.state.get("api_key") or ""

    def configured(self):
        return bool(self.state.get("base_url") and self.state.get("model"))

    def status(self):
        return {"configured": self.configured(), "base_url": self.state["base_url"],
                "model": self.state["model"], "api_key_set": bool(self._api_key()),
                "api_key_from_env": bool(os.environ.get("LUX_LYRICS_API_KEY")),
                "supports_images": bool(self.state["supports_images"]),
                "temperature": self.state["temperature"], "state_error": self.state_error,
                "moods": MOODS}

    def save(self, update: dict):
        state = dict(self.state)
        if update.get("base_url") is not None:
            state["base_url"] = normalize_base_url(update["base_url"])
            if update.get("api_key") is None and _origin(state["base_url"]) != _origin(self.state["base_url"]):
                state["api_key"] = ""  # A saved key only ever goes to the server it was entered for.
        if update.get("model") is not None:
            state["model"] = str(update["model"]).strip()
        if update.get("api_key") is not None:
            state["api_key"] = str(update["api_key"]).strip()
        if update.get("supports_images") is not None:
            state["supports_images"] = bool(update["supports_images"])
        if update.get("temperature") is not None:
            temperature = float(update["temperature"])
            if not 0 <= temperature <= 2:
                raise ValueError("Temperature must be between 0 and 2")
            state["temperature"] = temperature
        with self.lock:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(state, indent=2) + "\n")
            os.chmod(temp, 0o600)
            temp.replace(self.path)
            self.state, self.state_error = state, None
        return self.status()

    def _call(self, method, path, base_url=None, api_key=None, resolved=None, **kwargs):
        if base_url is None:
            if not self.configured():
                raise LyricsNotConfigured("Set up a lyrics writer in Settings first.")
            base_url, api_key = self.state["base_url"], self._api_key()
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            with self.client() as client:
                response = client.request(method, base_url + path, headers=headers, **kwargs)
        except httpx.TimeoutException as error:
            raise LyricsUpstreamError("The lyrics endpoint did not answer in time.") from error
        except httpx.HTTPError as error:
            raise LyricsUpstreamError(f"The lyrics endpoint could not be reached ({type(error).__name__}). "
                                      "Check the base URL in Settings.") from error
        final_base = str(response.url).split("?")[0]
        final_base = final_base[:-len(path)] if final_base.endswith(path) else final_base
        if response.history and method != "GET":
            # A redirected POST turns into a GET (HTTP 405), so ask for the final address instead.
            raise LyricsUpstreamError(f"The endpoint redirects to {final_base}. Use that base URL in Settings.")
        if resolved is not None:
            resolved.append(final_base)
        if response.status_code in {401, 403}:
            raise LyricsUpstreamError("The lyrics endpoint rejected the API key. Check it in Settings.")
        if response.status_code >= 400:
            raise LyricsUpstreamError(f"The lyrics endpoint returned HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError as error:
            raise LyricsUpstreamError("The lyrics endpoint did not return JSON.") from error

    def test(self):
        resolved = []
        models = model_ids(self._call("GET", "/models", resolved=resolved))
        return {"ok": True, "models": models, "base_url": resolved[0]}

    def list_models(self, base_url, api_key=None):
        """List models at a typed URL before it is saved."""
        base_url = normalize_base_url(base_url)
        if not base_url:
            raise ValueError("Enter a base URL first")
        if not api_key and base_url == self.state["base_url"]:
            api_key = self._api_key()  # Never send the saved key to a different host.
        resolved = []
        models = model_ids(self._call("GET", "/models", base_url, api_key, resolved=resolved))
        return {"base_url": resolved[0], "models": models}

    def discover(self):
        """Probe well-known local server addresses; no API key is sent."""
        found = [None] * len(LOCAL_SERVERS)
        def probe(index, name, base_url):
            try:
                models = model_ids(self._call("GET", "/models", base_url, None, timeout=DISCOVERY_TIMEOUT))
            except LyricsUpstreamError:
                return
            if models:
                found[index] = {"name": name, "base_url": base_url, "models": models}
        threads = [threading.Thread(target=probe, args=(i, *server), daemon=True)
                   for i, server in enumerate(LOCAL_SERVERS)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(DISCOVERY_TIMEOUT + 1)
        return {"servers": [server for server in found if server]}

    def prompt(self, concept="", style="", title="", mood="", custom="", visual="", language="",
               image_count=0):
        parts = []
        if image_count:
            parts.append(f"Write song lyrics inspired by the {image_count} attached image"
                         f"{'s' if image_count > 1 else ''}. Use concrete details you see in them.")
        else:
            parts.append("Write song lyrics.")
        if concept:
            parts.append(f"Song concept: {concept}")
        if visual:
            parts.append(f"The images show: {visual}")
        if title:
            parts.append(f"Song title: {title}")
        if style:
            parts.append(f"Musical style (shape the mood and rhythm, do not name it in the lyrics): {style}")
        mood_entry = next((m for m in MOODS if m["id"] == mood), None)
        if custom:
            parts.append(f"Theme and mood: {custom}")
        elif mood_entry:
            parts.append(f"Mood: {mood_entry['label']} — {mood_entry['hint']}.")
        if language:
            parts.append(f"Language: {language}")
        return "\n".join(parts)

    def _chat(self, system, content, temperature) -> str:
        payload = {"model": self.state["model"], "temperature": temperature,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}
        data = self._call("POST", "/chat/completions", json=payload)
        try:
            reply = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LyricsUpstreamError("The lyrics endpoint returned an unexpected reply.") from error
        if isinstance(reply, list):
            reply = "".join(part.get("text", "") for part in reply if isinstance(part, dict))
        return reply if isinstance(reply, str) else ""

    def write_style(self, concept, title="", instrumental=False, vocabulary=()):
        """Write the Style of music prompt that fits the user's song request."""
        lines = [f"Song request: {concept}"]
        if title:
            lines.append(f"Song title: {title}")
        if instrumental:
            lines.append("The song is instrumental: no vocals.")
        if vocabulary:
            lines.append(f"Prefer these terms when they fit: {', '.join(vocabulary)}")
        return {"style": clean_style(self._chat(STYLE_PROMPT, "\n".join(lines), 0.5), instrumental)}

    def generate(self, concept="", style="", title="", mood="", custom="", visual="", language="",
                 images=()):
        images = list(images or ())[:MAX_LYRICS_IMAGES] if self.state["supports_images"] else []
        text = self.prompt(concept, style, title, mood, custom, visual, language, len(images))
        content = ([{"type": "text", "text": text}] +
                   [{"type": "image_url", "image_url": {"url": image}} for image in images]) if images else text
        reply = self._chat(SYSTEM_PROMPT, content, self.state["temperature"])
        return {"lyrics": clean_lyrics(reply), "used_images": len(images)}


_writer = None
_writer_lock = threading.Lock()


def get_lyrics_writer() -> LyricsWriter:
    global _writer
    with _writer_lock:
        if _writer is None:
            _writer = LyricsWriter()
        return _writer
