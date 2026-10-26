"""YuE2 generation parameters.

Mirrors the request options documented in vendor/audio.cpp/docs/models/yue2.md.
Only options the user actually sets are forwarded, so audio.cpp defaults apply
for everything else.
"""

from typing import Literal
import base64
import copy
import json
import math

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .yue2_hook import HookMelody, apply_hook, reference_score

SEMANTIC_FPS = 25  # semantic codec frames per second of audio


class YuE2Params(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # --- core ---
    title: str | None = Field(None, max_length=80, description="Song title (UI only, not sent to the model)")
    lyrics: str = Field("", description="Lyrics with [Verse]/[Chorus]/... section tags; may be empty")
    instrumental: bool = Field(False, description="No vocals: replaces the lyrics with the [instrumental] tag")
    style: str = Field(..., min_length=1, description="Style prompt: language, genre, instruments, vocal, mix")
    cot: Literal["off", "melody", "full"] = Field("off", description="Symbolic planning route")
    seed: int = Field(1234, ge=0, lt=2**63)
    num_inference_steps: int | None = Field(None, gt=0, description="NAR ODE steps (default 8)")
    guidance_scale: float | None = Field(None, ge=0, le=20)

    # --- ABC conditioning (cot=melody|full) ---
    abc: str | None = Field(None, description="Inline ABC score")
    hook_melody: HookMelody | None = None

    # --- semantic sampling (controls the song itself, incl. length) ---
    semantic_temperature: float | None = Field(None, ge=0, le=5)
    semantic_top_p: float | None = Field(None, ge=0, le=1)
    semantic_top_k: int | None = Field(None, ge=1)
    semantic_repetition_penalty: float | None = Field(None, gt=0)
    semantic_min_tokens: int | None = Field(None, ge=0)
    semantic_max_tokens: int | None = Field(None, ge=1)

    # --- ABC planner sampling ---
    abc_temperature: float | None = Field(None, ge=0, le=5)
    abc_top_p: float | None = Field(None, ge=0, le=1)
    abc_top_k: int | None = Field(None, ge=1)

    # --- convenience: max length in seconds -> semantic_max_tokens ---
    max_duration_s: float | None = Field(None, gt=0, le=360)
    target_duration_s: float | None = Field(None, ge=30, le=330)

    @model_validator(mode="after")
    def _check(self):
        if self.hook_melody:
            if self.abc:
                raise ValueError("Remove the supplied ABC score before using a Hook melody.")
            if self.cot == "off":
                self.cot = "melody"
        if self.instrumental:
            # Upstream's instrumental guidance; normalizing here keeps edits and token recovery identical.
            # The vocal line is muted in the planned score, so planning is required.
            self.lyrics = "[instrumental]"
            if self.cot == "off":
                self.cot = "full"
        if self.abc and self.cot == "off":
            raise ValueError("abc requires cot=melody or cot=full")
        if self.target_duration_s:
            if self.cot == "off":
                self.cot = "full"
            # A transcribed recording is an approximate timing reference. Its
            # new performance may need more release time than a native plan.
            reference_timing = self.hook_melody and self.hook_melody.mode == "arrange"
            allowance = (max(30, self.target_duration_s * .25) if reference_timing
                         else max(15, self.target_duration_s * .125))
            cap = min(360, self.target_duration_s + allowance)
            if self.max_duration_s is None:
                self.max_duration_s = cap
            if self.max_duration_s < self.target_duration_s:
                raise ValueError("The hard limit must be at least the target duration")
        if self.max_duration_s and self.semantic_max_tokens is None:
            self.semantic_max_tokens = int(self.max_duration_s * SEMANTIC_FPS)
        if self.target_duration_s and self.semantic_max_tokens < int(self.target_duration_s * SEMANTIC_FPS):
            raise ValueError("The semantic token cap must allow the target duration")
        if self.target_duration_s and self.semantic_max_tokens > int(self.max_duration_s * SEMANTIC_FPS):
            raise ValueError("The semantic token cap must not exceed the hard duration limit")
        lo, hi = self.semantic_min_tokens, self.semantic_max_tokens
        if hi is not None and lo is None and hi < 200:
            # audio.cpp default min is 200 tokens (8s); keep the pair valid
            self.semantic_min_tokens = hi
        if lo is not None and hi is not None and hi < lo:
            raise ValueError("semantic_max_tokens must be >= semantic_min_tokens")
        return self

    def to_request(self) -> dict:
        """Build the body for audio.cpp POST /v1/tasks/run (`request` field)."""
        skip = {"title", "lyrics", "instrumental", "seed", "max_duration_s", "target_duration_s", "hook_melody"}
        options = {
            k: str(v).lower() if isinstance(v, bool) else str(v)
            for k, v in self.model_dump(exclude_none=True).items()
            if k not in skip
        }
        return {"lyrics": self.lyrics, "seed": self.seed, "options": options}


class YuE2Adapter:
    """Translate shared inputs into the native YuE2 request."""
    capabilities = {"planning": ["off", "melody", "full"], "abc": True, "instrumental": True,
                    "duration_analysis": True, "hook": True,
                    "semantic_edit": True, "max_duration_s": 360,
                    "target_duration_s": 330, "min_target_duration_s": 30,
                    "options": ["num_inference_steps", "guidance_scale", "semantic_temperature",
                                "semantic_top_p", "semantic_top_k", "semantic_repetition_penalty"]}

    @staticmethod
    def vibe_options(diversity):
        """Conservative creative presets, not a measured audio-quality claim."""
        if not math.isfinite(diversity) or not 0 <= diversity <= 1:
            raise ValueError("Invalid image diversity")
        if diversity < 0.08:
            label, temperature, top_p, top_k = "Cohesive palette", 0.9, 0.9, 80
        elif diversity < 0.18:
            label, temperature, top_p, top_k = "Balanced blend", 1.0, 0.95, 100
        else:
            label, temperature, top_p, top_k = "Contrasting textures", 1.1, 0.97, 140
        return {"label": label,
                "explanation": "A creative preset based on how similar the image atmospheres are. Sampling balances consistency and variation. Rendering uses 8 steps to keep generation lighter. You can edit these values in Advanced.",
                "options": {"semantic_temperature": temperature, "semantic_top_p": top_p,
                            "semantic_top_k": top_k, "num_inference_steps": 8}}

    def normalize(self, params):
        data = params.model_dump(exclude_none=True)
        options = data.pop("model_options", {})
        for key, value in options.items():
            if key in data and data[key] != value:
                raise ValueError(f"Conflicting model option: {key}")
            data[key] = value
        return YuE2Params(**data)

    @staticmethod
    def _requested_bpm(style):
        """Return one explicit style BPM target, ignoring ranges and conflicts."""
        import re
        if re.search(r"\b\d{2,3}\s*(?:[-–—]|to)\s*\d{2,3}\s*BPM\b", style, re.IGNORECASE):
            return None
        values = {int(value) for value in re.findall(r"\b(\d{2,3})\s*BPM\b", style, re.IGNORECASE)}
        if len(values) != 1:
            return None
        bpm = values.pop()
        return bpm if 30 <= bpm <= 300 else None

    def request(self, params):
        request = self.normalize(params).to_request()
        request["options"]["export_semantic"] = "true"
        return request

    def smoke_request(self):
        return {"lyrics": "[Verse]\nA quiet light", "seed": 1234,
                "options": {"style": "English, soft piano", "cot": "off",
                            "semantic_min_tokens": "8", "semantic_max_tokens": "16",
                            "num_inference_steps": "1"}}

    @staticmethod
    def _plan(request, p, run, progress, report, artifacts, accept, failure):
        """Plan up to three scores; accept(text) returns (score, info) or raises ScoreError."""
        from .yue2_score import ScoreError
        for attempt in range(3):
            if progress:
                progress(f"Planning arrangement ({attempt + 1}/3)")
            planning = copy.deepcopy(request)
            planning["seed"] = (p.seed + attempt) % (2**63)
            planning["options"]["stop_after"] = "abc"
            result = run(planning)
            art = next((a for a in result.get("artifacts", []) if a["id"] == "score"), None)
            entry = {"seed": planning["seed"]}
            if art:
                artifacts.append({**art, "id": f"plan-{attempt + 1}"})
            try:
                if not art or str(art.get("meta", {}).get("truncated")).lower() != "false":
                    raise ScoreError("The planner did not return a complete score")
                chosen, info = accept(base64.b64decode(art["payload"]).decode("utf-8"))
                entry.update(info)
                report["planning"] = {**info, "source": "generated", "seed": planning["seed"]}
                report["planning_attempts"].append(entry)
                return chosen
            except (ValueError, UnicodeError) as error:
                entry["error"] = str(error)
                entry.update(getattr(error, "diagnostics", {}))
                report["planning_attempts"].append(entry)
        attempts = report["planning_attempts"]
        length_attempts = [item for item in attempts if "minimum_duration_s" in item]
        best_attempt = min(length_attempts, key=lambda item: item["minimum_duration_s"]) if length_attempts else attempts[-1]
        error = ScoreError(failure + " " + best_attempt["error"])
        error.diagnostics = {"generation": report, "artifacts": artifacts}
        raise error

    def _score_for_analysis(self, text, p):
        from .yue2_score import inspect, retime, mute_vocals
        score = inspect(text)
        info = {"planner_bpm": score.bpm, "planner_duration_s": round(score.duration_s, 2)}
        bpm = self._requested_bpm(p.style)
        if bpm is not None:
            text, _ = retime(text, bpm)
            info.update(requested_bpm=bpm, tempo_adjusted_to_match_style=score.bpm != bpm)
        if p.hook_melody:
            text, hook = apply_hook(text, p.hook_melody, p.instrumental)
            info["hook"] = hook
        if p.instrumental:
            text = mute_vocals(text)
        return text, info

    def analyze_duration(self, params, run, progress=None):
        """Prepare a reusable local plan and public duration advice, without audio."""
        from .yue2_score import inspect, fit, ScoreError
        p = self.normalize(params)
        if p.cot == "off":
            p.cot = "full"
        limit = self.capabilities["target_duration_s"]
        target = p.target_duration_s or limit
        report, artifacts, source = {"planning_attempts": []}, [], {}

        def accept(text):
            source["score"], tempo = self._score_for_analysis(text, p)
            chosen, info = fit(source["score"], target)
            return chosen, {**tempo, **info}

        if p.abc or p.hook_melody and p.hook_melody.mode == "arrange":
            source["score"] = p.abc or reference_score(p.hook_melody, p.instrumental)
            if p.instrumental:
                from .yue2_score import mute_vocals
                source["score"] = mute_vocals(source["score"])
            score = inspect(source["score"])
            minimum = score.duration_s
            report["planning"] = {"source": "supplied", "planned_duration_s": minimum, "bpm": score.bpm}
            too_short = minimum > target
        else:
            try:
                self._plan(self.request(p), p, run, progress, report, artifacts, accept,
                           "The model could not prepare a complete arrangement.")
                minimum = report["planning"]["planned_duration_s"]
                too_short = False
            except ScoreError:
                candidates = [(i, a) for i, a in enumerate(report["planning_attempts"])
                              if "minimum_duration_s" in a]
                if not candidates:
                    raise
                index, best = min(candidates, key=lambda pair: pair[1]["minimum_duration_s"])
                art = next(a for a in artifacts if a["id"] == f"plan-{index + 1}")
                source["score"], tempo = self._score_for_analysis(base64.b64decode(art["payload"]).decode(), p)
                minimum = best["minimum_duration_s"]
                report["planning"] = {**tempo, "source": "generated", "seed": best["seed"], "bpm": best["bpm"]}
                too_short = True
        recommendation = min(limit, max(30, math.ceil(minimum / 5) * 5)) if minimum <= limit else None
        status = "too_long" if recommendation is None else "too_short" if too_short else "ready"
        planned = minimum
        supplied = bool(p.abc or p.hook_melody and p.hook_melody.mode == "arrange")
        if recommendation is not None and not supplied:
            _, info = fit(source["score"], recommendation if too_short or not p.target_duration_s else target)
            report["planning"].update(info)
            planned = info["planned_duration_s"]
        summary = {"status": status, "planned_duration_s": round(planned, 2),
                   "original_duration_s": round(inspect(source["score"]).duration_s, 2),
                   "recommended_target_s": recommendation, "selected_target_s": p.target_duration_s,
                   "bpm": inspect(source["score"]).bpm, "max_target_s": limit,
                   "removed_instrumental_bars": report["planning"].get("removed_instrumental_bars", 0),
                   "supplied_score": supplied, "instrumental": p.instrumental}
        return {"analysis": summary, "prepared": {"score": source["score"], "report": report, "artifacts": artifacts},
                "params": p.model_dump(exclude_none=True)}

    def reuse_plan(self, params, prepared):
        from .yue2_score import inspect, fit, ScoreError
        p = self.normalize(params)
        if not p.target_duration_s:
            raise ScoreError("Choose a complete-song duration to use the analyzed arrangement.")
        planning = prepared["report"]["planning"]
        if planning["source"] == "supplied":
            score = inspect(prepared["score"])
            if score.duration_s > p.target_duration_s:
                raise ScoreError(f"This score needs about {math.ceil(score.duration_s)}s. Choose a longer duration.")
            return prepared["score"], {**planning, "analysis_reused": True}
        chosen, info = fit(prepared["score"], p.target_duration_s)
        return chosen, {**planning, **info, "analysis_reused": True}

    def generate(self, params, run, progress=None, prepared=None):
        from .yue2_score import inspect, fit, mute_vocals, ScoreError
        p = self.normalize(params)
        request = self.request(p)
        report = {"target_duration_s": p.target_duration_s,
                  "hard_limit_s": p.semantic_max_tokens / SEMANTIC_FPS if p.semantic_max_tokens else 360,
                  "planning_attempts": [], "listening_verified": False}
        artifacts = []
        if p.target_duration_s:
            if prepared is not None:
                chosen, info = self.reuse_plan(p, prepared)
                report.update(copy.deepcopy(prepared["report"]))
                report["planning"] = info
                artifacts = copy.deepcopy(prepared["artifacts"])
            elif p.abc or p.hook_melody and p.hook_melody.mode == "arrange":
                supplied_score = p.abc or reference_score(p.hook_melody, p.instrumental)
                score = inspect(supplied_score)
                if score.duration_s > p.target_duration_s:
                    raise ScoreError(f"Your score lasts about {score.duration_s:.0f}s. Choose a longer target or edit the score; supplied scores are never shortened automatically.")
                report["planning"] = {"planned_duration_s": round(score.duration_s, 2), "source": "supplied"}
                chosen = supplied_score
            else:
                requested_bpm = self._requested_bpm(p.style)

                def accept_generated_score(text):
                    text, tempo = self._score_for_analysis(text, p)
                    fitted, info = fit(text, p.target_duration_s)
                    if requested_bpm is not None:
                        info.update(tempo)
                    return fitted, info

                chosen = self._plan(request, p, run, progress, report, artifacts, accept_generated_score,
                                    "No complete arrangement fits the requested duration after three plans.")
            if p.instrumental:
                chosen = mute_vocals(chosen)
            request["options"]["abc"] = chosen
            artifacts.append({"id": "score", "payload": base64.b64encode(chosen.encode()).decode(),
                              "meta": {"truncated": "false", "source": "duration-checked", "format": "abc"}})
            # Compose before acoustic decoding. Never render tokens already
            # known to have hit the cap; retries are deliberately bounded.
            report["semantic_attempts"] = []
            accepted = None
            planned = report["planning"]["planned_duration_s"]
            reference_timing = bool(p.hook_melody and p.hook_melody.mode == "arrange")
            tolerance = lambda seconds: max(15, seconds * .125)
            finishing_tolerance = (lambda seconds: max(30, seconds * .25)) if reference_timing else tolerance
            if reference_timing:
                report["recording_timing"] = {"policy": "approximate", "planned_duration_s": planned,
                                               "finishing_allowance_s": p.max_duration_s - p.target_duration_s}
            for attempt in range(2):
                if progress:
                    progress(f"Composing and checking the ending ({attempt + 1}/2)")
                semantic_request = copy.deepcopy(request)
                semantic_request["seed"] = (p.seed + attempt) % (2**63)
                semantic_request["options"]["stop_after"] = "semantic"
                result = run(semantic_request)
                semantic = next((a for a in result.get("artifacts", []) if a["id"] == "semantic"), None)
                ending = self.ending(result)
                entry = {"seed": semantic_request["seed"], **ending}
                if semantic:
                    artifacts.append({**semantic, "id": f"semantic-attempt-{attempt + 1}"})
                    codes = json.loads(base64.b64decode(semantic["payload"]))
                    entry["duration_s"] = len(codes) / SEMANTIC_FPS
                    drift = entry["duration_s"] - p.target_duration_s
                    entry["target_match"] = -tolerance(p.target_duration_s) <= drift <= finishing_tolerance(p.target_duration_s)
                    # Planning only shortens, so short lyrics give a short plan. Accept a complete
                    # song that follows its plan; an ending far before the plan dropped sections.
                    entry["shorter_than_target"] = (entry["duration_s"] < p.target_duration_s and not entry["target_match"]
                                                    and abs(entry["duration_s"] - planned) <= tolerance(planned))
                    if ending["status"] == "model_end" and (entry["target_match"] or entry["shorter_than_target"]):
                        accepted = (semantic, codes, entry)
                report["semantic_attempts"].append(entry)
                if accepted:
                    break
            if not accepted:
                report.update(report["semantic_attempts"][-1])
                advice = ("Try a shorter, clearer recording phrase, review the detected tempo, or choose Develop into a song. "
                          if p.hook_melody else "Try fewer repeated sections, a shorter score, or a more compact style. ")
                error = ScoreError("The model did not finish near the expected duration after two attempts. "
                                   + advice + "No unfinished audio was rendered. Planning and semantic diagnostics were saved.")
                error.diagnostics = {"generation": report, "artifacts": artifacts}
                raise error
            semantic, codes, entry = accepted
            report.update(entry)
            if reference_timing:
                report["recording_timing"].update(actual_duration_s=entry["duration_s"],
                                                   drift_s=round(entry["duration_s"] - planned, 2))
            report["semantic_seed"] = entry["seed"]
            render = copy.deepcopy(request)
            render["options"].update(semantic_prefix=json.dumps(codes),
                                      semantic_min_tokens=str(len(codes)), semantic_max_tokens=str(len(codes)))
            if progress:
                progress("Rendering the finished composition")
            data = run(render)
            report["render_artifact_meta"] = {a["id"]: a.get("meta", {}) for a in data.get("artifacts", [])}
            # A forced render reports a full window by construction. Preserve
            # this separately from EOS observed at the composing stage.
            data["artifacts"] = [a for a in data.get("artifacts", []) if a["id"] != "semantic"]
            data["artifacts"].append(semantic)
        elif p.instrumental:
            chosen = mute_vocals(p.abc) if p.abc else self._plan(
                request, p, run, progress, report, artifacts,
                lambda text: (mute_vocals(text), {"planned_duration_s": round(inspect(text).duration_s, 2)}),
                "No complete instrumental arrangement after three plans.")
            request["options"]["abc"] = chosen
            artifacts.append({"id": "score", "payload": base64.b64encode(chosen.encode()).decode(),
                              "meta": {"truncated": "false", "source": "vocals-muted", "format": "abc"}})
            if progress:
                progress("Rendering the instrumental arrangement")
            data = run(request)
            data["artifacts"] = [a for a in data.get("artifacts", []) if a["id"] != "score"]
        else:
            data = run(request)
        # Supplied ABC is not exported by the native runtime, so retain our plan.
        data["artifacts"] = artifacts + data.get("artifacts", [])
        report.update(self.ending(data))
        if report.get("recording_timing"):
            timing = report["recording_timing"]
            report["message"] += (f" The recording score is about {timing['planned_duration_s']:.0f}s; "
                                  f"the new performance lasts about {timing['actual_duration_s']:.0f}s. Reference timing is approximate.")
        if report.get("shorter_than_target"):
            report["message"] += (f" It is shorter than the {p.target_duration_s:.0f}s target: the arrangement for these"
                                  f" lyrics lasts about {planned:.0f}s. Add sections for a longer song.")
        data["generation"] = report
        return data

    @staticmethod
    def ending(data):
        meta = {a["id"]: a.get("meta", {}) for a in data.get("artifacts", [])}
        semantic = str(meta.get("semantic", {}).get("truncated", "")).lower()
        score = str(meta.get("score", {}).get("truncated", "")).lower()
        status = "truncated" if "true" in (semantic, score) else "model_end" if semantic == "false" else "unknown"
        return {"status": status, "semantic_truncated": {"true": True, "false": False}.get(semantic),
                "score_truncated": {"true": True, "false": False}.get(score),
                "eos_observed": semantic == "false",
                "message": {"truncated": "Stopped at the hard limit. The song may be unfinished. Try a longer duration or shorter lyrics.",
                            "model_end": "The model emitted its end token. Listen to check the musical ending.",
                            "unknown": "The runtime did not report an ending signal."}[status]}

    def runtime_config(self, profile):
        return {"path": profile["root"], "session_options": {
            "yue2.model_gguf": profile["main_file"], "yue2.vae_gguf": profile["vae_file"]}}

    def render_section(self, *args, **kwargs):
        from .yue2_edit import render_section
        return render_section(*args, **kwargs)
