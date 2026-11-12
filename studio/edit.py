"""Dispatch song edits using the original model profile."""

import json

from . import engine
from .models import get_manager
from .providers import get_provider
# Audio utilities retained for existing stem mixing and beat-grid consumers.
from .audio import pcm as _pcm, wave_bytes as _wav, crossfade_region, beat_grid, XFADE_S


def render_section(song, start_s, end_s, seed, lyrics=None, variation="new", profile=None, direction=None):
    meta = json.loads((engine.OUTPUT_DIR / f"{song}.json").read_text())
    profile = get_manager().snapshot(profile) if profile else get_manager().song_profile(meta)
    adapter = get_provider(profile).adapter(profile)
    if not adapter.capabilities.get("semantic_edit"):
        raise ValueError("The model used for this song does not support section editing")
    return adapter.render_section(song, start_s, end_s, seed, lyrics, variation,
                                  profile=profile, direction=direction)
