"""Translate a reviewed Hook melody into YuE2's bounded two-voice ABC.

The model still plans the song. Lux inserts the motif into chorus phrases of
that plan, or builds an explicit score for arranging the recording itself.
"""

from fractions import Fraction
import math
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .yue2_score import Bar, Score, ScoreError, inspect


class HookNote(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    pitch: int = Field(ge=24, le=108)
    start: float = Field(ge=0, le=450)
    end: float = Field(gt=0, le=450)


class HookMelody(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    version: Literal[1] = 1
    bpm: int = Field(ge=40, le=240)
    beats: float = Field(gt=0, le=450)
    notes: list[HookNote] = Field(min_length=1, max_length=512)
    source: Literal["recording"] = "recording"
    octave_shift: int = Field(default=0, ge=-72, le=72)
    model_id: Literal["sheetsage2"] = "sheetsage2"
    model_revision: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}$")
    score_abc: str | None = Field(default=None, max_length=32000)
    mode: Literal["develop", "arrange"] = "develop"
    target: Literal["vocal", "instrumental"] = "vocal"

    @model_validator(mode="after")
    def timing(self):
        end = 0.
        for note in self.notes:
            if note.end <= note.start or note.start < end - .0001 or note.end > self.beats + .001:
                raise ValueError("Hook notes must be ordered, nonoverlapping and inside the melody.")
            end = note.end
        if self.score_abc:
            score = inspect(self.score_abc)
            if score.bpm != self.bpm:
                raise ValueError("The Hook melody tempo must match its SheetSage2 score.")
        return self


def _pitch(midi):
    names = ("=C", "^C", "=D", "^D", "=E", "=F", "^F", "=G", "^G", "=A", "^A", "=B")
    name = names[midi % 12]
    octave = midi // 12 - 5  # MIDI 60 = middle C
    return name + ("'" * octave if octave > 0 else "," * -octave)


def _bars(melody, count, units_per_bar, quarters_per_bar):
    """Fit the complete phrase to a bar grid; never truncate the final note."""
    total = count * units_per_bar
    timeline = [None] * total
    previous = 0
    for note in melody.notes:
        start = min(max(previous, round(note.start / melody.beats * total)), total - 1)
        end = min(total, max(start + 1, round(note.end / melody.beats * total)))
        if start < previous:
            raise ScoreError("The Hook has too many notes for this phrase. Trim it or use Arrange recording.")
        for i in range(start, end):
            timeline[i] = (start, note.pitch)
        previous = end
    bars = []
    for bar in range(count):
        tokens, pos, limit = [], bar * units_per_bar, (bar + 1) * units_per_bar
        while pos < limit:
            end = pos + 1
            while end < limit and timeline[end] == timeline[pos]:
                end += 1
            value = "z" if timeline[pos] is None else _pitch(timeline[pos][1])
            tied = timeline[pos] is not None and end < total and end == limit and timeline[end] == timeline[pos]
            tokens.append(f"{value}{end - pos}{'-' if tied else ''}")
            pos = end
        bars.append(" ".join(tokens))
    return bars


def reference_score(melody: HookMelody, instrumental=False):
    if melody.score_abc and melody.mode == "arrange":
        score = inspect(melody.score_abc)
        if not instrumental and melody.target == "vocal":
            for bar in score.bars:
                bar.vocal, bar.instrumental = bar.instrumental, bar.vocal
        return score.text()
    count = max(1, math.ceil(melody.beats / 4))
    bars = _bars(melody, count, 16, 4)
    voice = instrumental or melody.target == "instrumental"
    score = Score(["X:1", "T:", "M:4/4", "L:1/16", f"Q:1/4={melody.bpm}",
                   'V: Vocal clef=treble name="Vocal Melody" snm="Vocal"',
                   'V: Ins clef=treble name="Ins Melody" snm="Inst."', "K:C"],
                  [Bar("z16" if voice else bar, bar if voice else "z16", "% Hook") for bar in bars]
                  + [Bar("z16", "z16", "% Outro")], melody.bpm, 240 / melody.bpm)
    result = score.text()
    inspect(result)
    return result


def apply_hook(text: str, melody: HookMelody, instrumental=False):
    score = inspect(text)
    meter = re.fullmatch(r"M:(\d+)/(\d+)", score.header[2])
    unit = int(score.header[3].split("/")[1])
    quarters = float(Fraction(int(meter[1]) * 4, int(meter[2])))
    units = int(Fraction(int(meter[1]) * unit, int(meter[2])))
    target = "instrumental" if instrumental or melody.target == "instrumental" else "vocal"
    # Chorus labels are comments in the native score. Preserve intro/outro and
    # all bar lengths. If no chorus exists, use a bounded interior lead phrase.
    groups = []
    for i, bar in enumerate(score.bars):
        if re.search(r"\bchorus\b|\brefrain\b|\bhook\b", bar.section, re.I) and not re.search(r"pre[ -]?chorus", bar.section, re.I):
            if groups and groups[-1][-1] == i - 1:
                groups[-1].append(i)
            else:
                groups.append([i])
    fallback = not bool(groups)
    if fallback:
        def lead_candidates(voice):
            return [i for i, bar in enumerate(score.bars) if 2 <= i < len(score.bars) - 2
                    and not re.search(r"intro|outro|ending", bar.section, re.I)
                    and re.search(r"[A-Ga-g]", re.sub(r'"[^"\n]*"', '', getattr(bar, voice)))]
        candidates = lead_candidates(target)
        if not candidates and target == "instrumental":
            candidates = lead_candidates("vocal")
        if not candidates:
            raise ScoreError("The plan has no clear lead phrase for Hook. Try Melody planning or Arrange recording.")
        start, phrase = candidates[0], [candidates[0]]
        for index in candidates[1:]:
            if index != phrase[-1] + 1 or score.bars[index].section != score.bars[start].section or len(phrase) == 8:
                break
            phrase.append(index)
        groups = [phrase]
    applied = []
    for group in groups:
        # A full copy of the phrase fits inside each chorus. Long recordings
        # compress rhythm to its section; short motifs repeat as whole phrases.
        count = min(len(group), max(1, round(melody.beats / quarters)))
        bars = _bars(melody, count, units, quarters)
        for offset in range(0, len(group) - count + 1, count):
            for j, bar in enumerate(bars):
                index = group[offset + j]
                setattr(score.bars[index], target, bar)
                applied.append(index + 1)
    result = score.text()
    inspect(result)
    return result, {"target": target, "bars": applied, "fallback_phrase": fallback,
                    "source_bpm": melody.bpm, "plan_bpm": score.bpm,
                    "note_count": len(melody.notes), "mode": "develop"}
