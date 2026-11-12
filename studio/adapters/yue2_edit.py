"""Regenerate a section of a song with YuE2 semantic tokens (used to edit a piece of one stem).

How it works (see vendor/audio.cpp/docs/models/yue2.md, "Continuing From Semantic Tokens"):
  1. get the song's semantic tokens S (25 per second): saved at generation time, or
     recovered by re-running the original request with stop_after=semantic (deterministic)
  2. force S[:A] as history and let the model sample frames A..B with a new seed
  3. splice tokens: new[:B] + S[B:], render the whole song once (one coherent acoustic pass)
  4. keep the original audio outside [A, B] and crossfade the new render in at the edges
"""

import base64
import json
import time

import numpy as np

from .. import engine
from ..audio import pcm as _pcm, wave_bytes, crossfade_region
from ..models import get_manager
from ..providers import get_provider
from .yue2 import YuE2Params as GenerationParams

FPS = 25                 # semantic frames per second
SR = 48000               # YuE2 output sample rate
XFADE_S = 0.2            # crossfade at each edge of the replaced region
MAX_SAME_TOKENS = 0.5    # a take sharing more than this share of tokens with the original is re-rolled
MAX_REROLLS = 3


def _run(lyrics: str, seed: int, options: dict, profile: dict) -> dict:
    return get_provider(profile).run(profile, {"lyrics": lyrics, "seed": seed, "options": options})


def _semantic(data: dict) -> list[int]:
    for art in data.get("artifacts", []):
        if art["id"] == "semantic":
            return json.loads(base64.b64decode(art["payload"]))
    raise RuntimeError("engine returned no semantic tokens")






def _base_options(meta: dict) -> dict:
    """Request options of the original generation, plus its score when it was planned."""
    params = GenerationParams(**meta["params"])
    options = params.to_request()["options"]
    options.pop("semantic_min_tokens", None)
    options.pop("semantic_max_tokens", None)
    if params.cot != "off" and (not params.abc or params.instrumental):  # instrumental scores are saved muted
        score = meta.get("artifacts", {}).get("score")
        if not score:
            raise RuntimeError("this song was planned (cot=%s) but its score is missing" % params.cot)
        options["abc"] = (engine.OUTPUT_DIR / score).read_text()
    return options


def song_tokens(song: str, profile: dict | None = None) -> list[int]:
    """Semantic tokens of a song, recovering (and caching) them when they were not exported."""
    cache = engine.OUTPUT_DIR / f"{song}.semantic.json"
    if cache.exists():
        return json.loads(cache.read_text())
    meta = json.loads((engine.OUTPUT_DIR / f"{song}.json").read_text())
    profile = profile or get_manager().song_profile(meta)
    if meta.get("parent"):
        raise RuntimeError("edited song has no saved tokens")
    params = GenerationParams(**meta["params"])
    # Same request as the original, stopped after the semantic stage: same seed, same tokens.
    options = {**params.to_request()["options"], "stop_after": "semantic"}
    if meta.get("generation", {}).get("target_duration_s") or params.instrumental:
        score = meta.get("artifacts", {}).get("score")
        if not score:
            raise RuntimeError("The duration-checked score is missing; semantic recovery is unavailable")
        options["abc"] = (engine.OUTPUT_DIR / score).read_text()
    seed = meta.get("generation", {}).get("semantic_seed", params.seed)
    tokens = _semantic(_run(params.lyrics, seed, options, profile))
    expected = meta["duration_s"] * FPS
    if abs(len(tokens) - expected) > 2:
        raise RuntimeError(f"recovered {len(tokens)} tokens but the song has {expected:.0f} frames")
    cache.write_text(json.dumps(tokens))
    return tokens




def render_section(song: str, start_s: float, end_s: float, seed: int, lyrics: str | None = None,
                   variation: str = "new", profile: dict | None = None,
                   direction: str | None = None) -> tuple[np.ndarray, dict]:
    """New take of [start_s, end_s) of a song; returns the composite audio (48 kHz) and edit info.

    variation="new"   regenerate without the song's score: same history, freshly written notes
                      (measured on the vocal line: melody similarity 0.53-0.63, like two different
                      parts of the same song, vs 0.94 when the score is kept)
    variation="same"  keep the score: the same notes re-sung, only the performance/timbre changes
    """
    meta = json.loads((engine.OUTPUT_DIR / f"{song}.json").read_text())
    profile = profile or get_manager().song_profile(meta)
    tokens = song_tokens(song, profile)
    n = len(tokens)
    a = max(1, int(round(start_s * FPS)))
    b = min(n, int(round(end_s * FPS)))
    if b - a < FPS:
        raise ValueError("select at least 1 second")

    lyrics = lyrics if lyrics and lyrics.strip() else meta["params"]["lyrics"]
    options = _base_options(meta)
    direction = (direction or "").strip()
    if direction:
        base_style = options.get("style", "").strip()
        options["style"] = f"{base_style}. For the selected section only: {direction}" if base_style else direction
    # ponytail: instrumental songs keep their muted score, so "new" only re-performs it; re-plan and mute to vary notes.
    if variation == "new" and "abc" in options and not meta["params"].get("instrumental"):
        # The score fixes melody and rhythm; drop it so the model writes the selection anew.
        options = {k: v for k, v in options.items() if k not in ("abc", "cot")} | {"cot": "off"}
    t0 = time.time()

    # 2. new take of the selection, conditioned on everything before it. A take that repeats the
    #    original (many identical tokens) is re-rolled with another seed so every take is a new version.
    for attempt in range(MAX_REROLLS + 1):
        leg = _semantic(_run(lyrics, seed, {**options, "semantic_prefix": json.dumps(tokens[:a]),
                                            "semantic_min_tokens": str(b), "semantic_max_tokens": str(b),
                                            "stop_after": "semantic"}, profile))
        same = sum(x == y for x, y in zip(leg[a:b], tokens[a:b])) / (b - a)
        if same <= MAX_SAME_TOKENS:
            break
        seed = (seed + 7919) % 2**63
    spliced = leg[:b] + tokens[b:]

    # 3. one acoustic pass over the whole spliced song (original seed keeps the NAR noise)
    data = _run(lyrics, meta["params"]["seed"], {**options, "semantic_prefix": json.dumps(spliced),
                                                  "semantic_min_tokens": str(n), "semantic_max_tokens": str(n)}, profile)
    new = _pcm(base64.b64decode(data["audio"]))

    # 4. original audio outside the region, new render inside
    orig = _pcm((engine.OUTPUT_DIR / f"{song}.wav").read_bytes())
    length = min(len(orig), len(new))
    out = crossfade_region(orig[:length], new[:length], int(a / FPS * SR), int(b / FPS * SR), int(XFADE_S * SR))
    info = {"meta": meta, "lyrics": lyrics, "direction": direction,
            "spliced": spliced, "start_s": round(a / FPS, 2), "end_s": round(b / FPS, 2),
            "sample_rate": SR, "seed": seed, "same_tokens": round(same, 3), "variation": variation, "elapsed_s": round(time.time() - t0, 1)}
    return out, info




def _wav(audio):
    return wave_bytes(audio, SR)
