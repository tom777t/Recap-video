

"""
schemas.py — Phase 1 machine-readable contracts (stdlib dataclasses, no Pydantic).

Adds an OPTIONAL, ADDITIVE layer on top of the existing draft/broll shapes:
  - skeleton.json  : per-unit coverage plan (tier / target_words / must_cover)
  - draft.json     : existing lines (id / narration / pool / clip_start / hold)
                     PLUS optional new fields (unit_id / covers / claim / narrative_jump)
  - footage        : resolved from the EXISTING broll.json "pool" dict + inline
                     clip_start/clip_end (NO new shot_id field), optional shots.json

Validation is done with @dataclass + __post_init__ and typing.Literal enums.
Loaders accept the real on-disk shapes and IGNORE unknown keys (forward-compatible).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional, get_args

import config

# --------------------------------------------------------------------------- #
# Controlled vocabularies (claim.type is a subset of depicts so binding can do
# a direct membership check).
# --------------------------------------------------------------------------- #
TierEnum = Literal["LIGHT", "STANDARD", "DEEP"]

ClaimType = Literal[
    "action", "reveal", "discovery", "dialogue", "reaction",
    "setup", "transition", "narration", "emotion",
    # "speech" (2026-08-31, RULES Part J): the line reports what a character
    # SAYS, and the evidence is the speech itself, not the image. Every other
    # claim type asserts something the frame shows; this one asserts something
    # the frame can only witness being said. It is verifiable ONLY in the strict
    # form: the claimed speaker must be VISIBLE SPEAKING in the bound shot. The
    # audit checks the speaker is present and says, in its own output, that it
    # cannot check the content. Do NOT use it for a speaker established by a
    # neighbouring line - see Part J for why that form was rejected.
    "speech",
]

DepictsType = Literal[
    "action", "reveal", "discovery", "dialogue", "reaction",
    "setup", "transition", "emotion", "establishing", "montage", "aftermath",
]

# Per-shot censor level (optional). Applied at render time as a whole-frame
# Gaussian/box blur over the clip. "none" (or absent) = no blur. See S7 in
# docs/TAGGING_GUIDE.md for when to tag each level.
CensorType = Literal["none", "blur_light", "blur", "blur_heavy"]

_TIERS = set(get_args(TierEnum))
_CLAIM_TYPES = set(get_args(ClaimType))
_DEPICTS_TYPES = set(get_args(DepictsType))
_CENSOR_TYPES = set(get_args(CensorType))

# Map censor level -> ffmpeg boxblur radius (luma). 0 = no blur.
CENSOR_BOXBLUR = {
    "none": 0,
    "blur_light": 15,
    "blur": 30,
    "blur_heavy": 60,
}


# --------------------------------------------------------------------------- #
# DEPICTS vocabulary - single source of truth for what each tag MEANS.
# Tagging is the input layer that drives the binding audit; if a value here
# is used loosely, the audit's verification becomes equally loose. The full
# discipline (when to use which, common mistakes, worked examples) lives in
# docs/TAGGING_GUIDE.md. This dict is the inline quick reference for anyone
# reading the schema directly.
# --------------------------------------------------------------------------- #
DEPICTS_VOCAB: dict = {
    "setup":        "Establishes context BEFORE an event happens - character intro, place introduction, before-state. NOT the event itself.",
    "reveal":       "The moment a previously-hidden identity, character, or threat becomes visible. Pennywise emerging from the drain.",
    "discovery":    "A character finds out NEW INFORMATION (records, clues, evidence). Ben in the library finding old newspapers.",
    "dialogue":     "Two or more characters exchanging spoken words AS the primary moment.",
    "reaction":     "A character's response (emotional or physical) to a preceding event. Bill grieving for Georgie.",
    "action":       "A physical event with motion and consequence - fight, attack, chase, bite, kiss, escape.",
    "emotion":      "A held emotional beat between characters without active dialogue or physical action.",
    "transition":   "Bridge moment - movement between places, time passing, scene change.",
    "establishing": "Wide shot of place, location, or world. No specific character focus.",
    "montage":      "Compressed-time sequence within a single clip - multiple quick shots collapsed.",
    "aftermath":    "The result-state AFTER an event - empty room after fight, injured character, etc.",
}


class SchemaError(ValueError):
    """Raised when an on-disk artifact does not match the Phase 1 schema."""


class BindingViolation(ValueError):
    """Raised (Mức 1 hard constraint) when a line's narration is too long to be
    carried by its bound shot's footage window, even after the mild-slowdown
    allowance.

    Replaces the old SILENT freeze fallback (clip held its last frame for the
    extra narration seconds). The render now refuses to silently freeze: the
    binding contract is `narration_duration <= shot_duration * SLOWDOWN_MAX`.
    Surfaced at `recap.py draft` audit time (before any render attempt) and also
    enforced defensively at render time.

    Attributes mirror the offending line so callers can build a fix plan
    (split the line further, or bind it to a multi-shot / longer window).
    """

    def __init__(self, line_id, narration_dur, shot_dur, capacity,
                 message: str = ""):
        self.line_id = line_id
        self.narration_dur = narration_dur
        self.shot_dur = shot_dur
        self.capacity = capacity
        if not message:
            message = (
                f"Line {line_id}: narration {narration_dur:.1f}s "
                f"> shot capacity {capacity:.1f}s "
                f"(shot window {shot_dur:.1f}s x {BINDING_SLOWDOWN_MAX:.1f}). "
                f"Need multi-shot binding or shorter narration."
            )
        super().__init__(message)


# Mức 1 binding-capacity constants -------------------------------------------
# A bound shot may be stretched at most this factor via mild slow-motion before
# the binding contract is considered violated. 1.0 = no slowdown allowed.
# 2026-10-27: 1.4 -> config (1.15). Sourced from config so the ceiling is a
# tunable in one place rather than a constant buried in a schema module.
# 1.4 was too generous: the stretch is setpts frame-duplication with no
# interpolation, so above roughly 1.15x it reads as judder rather than as
# slow motion. The answer to a line that needs more picture is more picture -
# extend the window across the following cuts - not a slower shot.
BINDING_SLOWDOWN_MAX = float(getattr(config, "BINDING_SLOWDOWN_MAX", 1.15))


def _drop_unknown(cls, data: dict) -> dict:
    """Keep only keys that are declared dataclass fields (forward-compatible)."""
    allowed = {f.name for f in cls.__dataclass_fields__.values()}
    return {k: v for k, v in data.items() if k in allowed}


# --------------------------------------------------------------------------- #
# skeleton.json
# --------------------------------------------------------------------------- #
@dataclass
class Unit:
    id: str
    label: str
    tier: TierEnum
    target_words: int
    why: str = ""
    must_cover: list = field(default_factory=list)
    tolerance: float = 0.25

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id.strip():
            raise SchemaError("unit.id must be a non-empty string")
        if self.tier not in _TIERS:
            raise SchemaError(f"unit {self.id}: tier '{self.tier}' not in {sorted(_TIERS)}")
        if not isinstance(self.target_words, int) or self.target_words <= 0:
            raise SchemaError(f"unit {self.id}: target_words must be a positive int")
        if not (0.0 <= float(self.tolerance) <= 1.0):
            raise SchemaError(f"unit {self.id}: tolerance must be 0.0-1.0")
        if not isinstance(self.must_cover, list) or len(self.must_cover) < 1:
            raise SchemaError(f"unit {self.id}: must_cover must list >=1 item")
        self.must_cover = [str(s) for s in self.must_cover]


@dataclass
class Skeleton:
    project: str
    units: list
    film_title: str = ""
    predicted_runtime_min: int = 0

    def __post_init__(self):
        if not self.units:
            raise SchemaError("skeleton.units must be non-empty")
        self.units = [u if isinstance(u, Unit) else Unit(**_drop_unknown(Unit, u))
                      for u in self.units]
        ids = [u.id for u in self.units]
        if len(ids) != len(set(ids)):
            raise SchemaError("skeleton has duplicate unit ids")

    def unit_by_id(self, uid: str) -> Optional[Unit]:
        for u in self.units:
            if u.id == uid:
                return u
        return None


# --------------------------------------------------------------------------- #
# draft.json (ADDITIVE: existing fields kept, new fields optional)
# --------------------------------------------------------------------------- #
@dataclass
class Claim:
    type: ClaimType
    subject: Optional[str] = None
    requires_visual: bool = True

    def __post_init__(self):
        if self.type not in _CLAIM_TYPES:
            raise SchemaError(f"claim.type '{self.type}' not in {sorted(_CLAIM_TYPES)}")


# --------------------------------------------------------------------------- #
# Mức 2: multi-shot binding. A line may bind to ONE shot (existing clip_start/
# clip_end) or a LIST of shots, each played for an explicit `play_duration`
# (seconds). This generalises the inline `montage` (which split the clip time
# EQUALLY across sub-shots) to per-shot durations. A BindSpec is one shot in the
# sequence. Backward compatible: a montage entry WITHOUT play_duration falls
# back to the equal-split behaviour at render time.
# --------------------------------------------------------------------------- #
@dataclass
class BindSpec:
    clip_start: str
    clip_end: str
    play_duration: Optional[float] = None   # seconds this shot plays; None -> equal split

    def __post_init__(self):
        if not self.clip_start or not self.clip_end:
            raise SchemaError("BindSpec needs clip_start and clip_end")
        if self.play_duration is not None:
            v = self.play_duration
            if isinstance(v, bool):
                raise SchemaError("BindSpec.play_duration must be a number")
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise SchemaError(
                    f"BindSpec.play_duration must be a number, got {self.play_duration!r}")
            if v <= 0:
                raise SchemaError(f"BindSpec.play_duration must be > 0 (got {v})")
            self.play_duration = v


@dataclass
class Line:
    # --- existing fields (unchanged) ---
    id: int
    narration: str = ""
    pool: Optional[str] = None
    montage: Optional[list] = None
    clip_start: Optional[str] = None
    clip_end: Optional[str] = None
    hold: float = 0.0
    delivery: Optional[str] = None
    visual: Optional[str] = None
    flashback: bool = False
    setup_ok: bool = False
    # --- new optional Phase 1 fields ---
    unit_id: Optional[str] = None
    covers: list = field(default_factory=list)
    claim: Optional[Claim] = None
    narrative_jump: bool = False
    # Gap 3 / S9: a SILENCE line - visual holds this long with no voiceover.
    # This lives on the LINE because the renderer iterates draft lines, not
    # shots (TAGGING_GUIDE S9, SCRIPTING_CHECKLIST C1). It was missing from this
    # dataclass until 2026-08-26, so _drop_unknown silently discarded it and
    # every consumer of the typed Draft was blind to authored silence - which is
    # why DRAFT-TARGET was reading silence out of shots.json instead.
    narration_silence_seconds: Optional[float] = None
    # --- Mức 2: declared total visual duration (sum of play_durations).
    # Optional; if set, validated against the bind segments. Informational +
    # lets authors assert intent so a silent drift is caught.
    total_visual_duration: Optional[float] = None
    # --- montage-era opening lines (spoken over the prepended intro, not a shot)
    # These were read off raw draft dicts by the craft gates but never typed, so
    # the typed Draft dropped them and any gate reading d.lines was blind to
    # them. over_montage = spoken over the beat-cut montage; film_intro = the
    # facts block after it. Both windowless, both baked into the intro block.
    over_montage: bool = False
    film_intro: bool = False
    # --- angle-era compression: a BRIDGE line explicitly spans a skipped
    # stretch of film ("Two weeks and a lot of crashed cars later, ..."). The
    # [BRIDGE] gate accepts a flagged bridge OR a time-jump phrase as proof that
    # a skip was declared rather than a teleport.
    bridge: bool = False
    # --- [CALLBACK-CITE] (permanence rule 3): a line asserting a link to an
    # earlier event cites the beat id that event happens in, so the FACT audit
    # can verify the callback is real rather than invented.
    callback_beat: Optional[str] = None
    # --- per-line rate multiplier, written by tools/fit_narration.py when this
    # line's REAL audio overran its footage window by a few percent. Applied on
    # top of the delivery tag's own rate (so a fitted `sad` line is still
    # slower than a `tense` one) and part of the TTS cache key, so it
    # re-synthesizes exactly this line. Stored in the draft deliberately: a
    # bump kept in a side-file would be lost on the next render and the line
    # would overrun again. 1.0 = untouched.
    rate_bump: Optional[float] = None

    def __post_init__(self):
        if isinstance(self.claim, dict):
            self.claim = Claim(**_drop_unknown(Claim, self.claim))
        if self.covers and not isinstance(self.covers, list):
            raise SchemaError(f"line {self.id}: covers must be a list")
        if self.total_visual_duration is not None:
            try:
                self.total_visual_duration = float(self.total_visual_duration)
            except (TypeError, ValueError):
                raise SchemaError(
                    f"line {self.id}: total_visual_duration must be a number")
        # Same rules as Shot.narration_silence_seconds: optional, positive,
        # <= 30s (S9's hard cap). Coerce int/str coming out of JSON.
        if self.narration_silence_seconds is not None:
            v = self.narration_silence_seconds
            if isinstance(v, bool):
                raise SchemaError(
                    f"line {self.id}: narration_silence_seconds must be a number")
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise SchemaError(
                    f"line {self.id}: narration_silence_seconds must be a number, "
                    f"got {self.narration_silence_seconds!r}")
            if v <= 0:
                raise SchemaError(
                    f"line {self.id}: narration_silence_seconds must be > 0 (got {v})")
            if v > 30:
                raise SchemaError(
                    f"line {self.id}: narration_silence_seconds must be <= 30 "
                    f"(S9 long-silence limit; got {v})")
            self.narration_silence_seconds = v

    def word_count(self) -> int:
        return len(self.narration.split())

    def bind_segments(self) -> list:
        """Mức 2: normalise this line's binding into a list of BindSpec.

        - montage list -> one BindSpec per entry (dict {clip_start, clip_end,
          [play_duration]} or [start, end] pair).
        - single clip_start/clip_end -> a one-element list.
        - pool / silence / no binding -> empty list.
        Returns [] when there is nothing timed to bind (caller decides).
        """
        if self.montage:
            out = []
            for m in self.montage:
                if isinstance(m, dict):
                    out.append(BindSpec(
                        clip_start=m.get("clip_start"), clip_end=m.get("clip_end"),
                        play_duration=m.get("play_duration")))
                elif isinstance(m, (list, tuple)) and len(m) == 2:
                    out.append(BindSpec(clip_start=str(m[0]), clip_end=str(m[1])))
                # str labels (broll pool montage) are NOT timed -> skipped here
            return out
        if self.clip_start and self.clip_end:
            return [BindSpec(clip_start=self.clip_start, clip_end=self.clip_end)]
        return []


@dataclass
class Draft:
    project: str
    lines: list

    def __post_init__(self):
        if not self.lines:
            raise SchemaError("draft.lines must be non-empty")
        self.lines = [l if isinstance(l, Line) else Line(**_drop_unknown(Line, l))
                      for l in self.lines]


# --------------------------------------------------------------------------- #
# Footage (resolved from broll pool + inline clip_start; optional shots.json)
# --------------------------------------------------------------------------- #
@dataclass
class CensorRegion:
    """Optional region coordinates for PARTIAL blur (Phase C).

    Pixel coordinates in the ORIGINAL source frame. If a Shot's censor_region
    is None, the entire frame is blurred (backward compatible with Phase A/B
    whole-frame censor). When present, only the [x, y, width, height] rectangle
    is blurred and overlaid back onto an otherwise untouched frame.
    """
    x: int          # Top-left X pixel
    y: int          # Top-left Y pixel
    width: int      # Region width pixels
    height: int     # Region height pixels

    def __post_init__(self):
        for name in ("x", "y", "width", "height"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int):
                # accept ints that arrived as floats/strings from JSON
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    raise SchemaError(
                        f"censor_region.{name} must be an int, got {getattr(self, name)!r}")
                setattr(self, name, v)
        if self.width <= 0 or self.height <= 0:
            raise SchemaError(
                f"censor_region: width/height must be > 0 (got {self.width}x{self.height})")
        if self.x < 0 or self.y < 0:
            raise SchemaError(
                f"censor_region: x/y must be >= 0 (got x={self.x}, y={self.y})")


@dataclass
class Shot:
    id: str                       # pool label (e.g. "P3"), "line:42", or shots.json id
    source: Literal["broll", "explicit", "shots"] = "explicit"
    time_start: Optional[float] = None
    time_end: Optional[float] = None
    chars: list = field(default_factory=list)
    depicts: list = field(default_factory=list)
    action: str = ""
    family: Optional[str] = None
    strength: Optional[str] = None
    censor: str = "none"          # optional; one of CensorType (default "none")
    censor_region: Optional[CensorRegion] = None  # NEW (Phase C): partial blur
    narration_silence_seconds: Optional[float] = None  # NEW (Gap 3): silent shot
    # If set, this shot plays WITHOUT bound narration for the given duration.
    # Music continues and swells from the ducked level to SILENCE_MUSIC_VOLUME.
    # No TTS is generated for this shot. Max 30s (S9 long-silence limit).
    # --- Mức 3: capacity-aware catalogue fields (all OPTIONAL + auto-defaulted) ---
    raw_duration_sec: Optional[float] = None       # clip_end - clip_start (computed)
    max_play_duration_sec: Optional[float] = None  # default raw * stretch_tolerance
    max_narration_words_en: Optional[int] = None   # default from voice profile
    extendable: Optional[bool] = None              # default False (see compute_capacity)
    stretch_tolerance: float = 1.1                 # how far footage may be slowed

    def __post_init__(self):
        self.chars = [str(c) for c in (self.chars or [])]
        self.depicts = [str(d) for d in (self.depicts or [])]
        bad = [d for d in self.depicts if d not in _DEPICTS_TYPES]
        if bad:
            raise SchemaError(f"shot {self.id}: depicts {bad} not in {sorted(_DEPICTS_TYPES)}")
        # censor is optional; absent -> "none". Validate the enum if present.
        self.censor = str(self.censor or "none")
        if self.censor not in _CENSOR_TYPES:
            raise SchemaError(
                f"shot {self.id}: censor '{self.censor}' not in {sorted(_CENSOR_TYPES)}")
        # censor_region is optional; absent -> None (whole-frame blur). Coerce a
        # dict (from JSON) into a CensorRegion; validate (forward-compatible).
        if self.censor_region is not None and not isinstance(self.censor_region, CensorRegion):
            if isinstance(self.censor_region, dict):
                self.censor_region = CensorRegion(**_drop_unknown(CensorRegion, self.censor_region))
            else:
                raise SchemaError(
                    f"shot {self.id}: censor_region must be an object or null")
        # narration_silence_seconds is optional; absent -> None (normal narrated
        # shot). If set: positive float, max 30s (S9). Coerce int/str (JSON).
        if self.narration_silence_seconds is not None:
            v = self.narration_silence_seconds
            if isinstance(v, bool):
                raise SchemaError(
                    f"shot {self.id}: narration_silence_seconds must be a number")
            try:
                v = float(v)
            except (TypeError, ValueError):
                raise SchemaError(
                    f"shot {self.id}: narration_silence_seconds must be a number, "
                    f"got {self.narration_silence_seconds!r}")
            if v <= 0:
                raise SchemaError(
                    f"shot {self.id}: narration_silence_seconds must be > 0 (got {v})")
            if v > 30:
                raise SchemaError(
                    f"shot {self.id}: narration_silence_seconds must be <= 30 "
                    f"(S9 long-silence limit; got {v})")
            self.narration_silence_seconds = v
        # Mức 3 field coercion (all optional). Numeric/bool defensive parsing.
        for fname in ("raw_duration_sec", "max_play_duration_sec"):
            val = getattr(self, fname)
            if val is not None:
                try:
                    setattr(self, fname, float(val))
                except (TypeError, ValueError):
                    raise SchemaError(f"shot {self.id}: {fname} must be a number")
        if self.max_narration_words_en is not None:
            try:
                self.max_narration_words_en = int(self.max_narration_words_en)
            except (TypeError, ValueError):
                raise SchemaError(f"shot {self.id}: max_narration_words_en must be an int")
        if self.extendable is not None and not isinstance(self.extendable, bool):
            raise SchemaError(f"shot {self.id}: extendable must be true/false")
        try:
            self.stretch_tolerance = float(self.stretch_tolerance)
        except (TypeError, ValueError):
            raise SchemaError(f"shot {self.id}: stretch_tolerance must be a number")

    # ---- Mức 3 capacity helpers ----------------------------------------- #
    def is_extendable_default(self) -> bool:
        """Default extendability: a STATIC shot (establishing/setup/aftermath/
        emotion/transition) can be safely held/slowed, so extendable=True. An
        ACTION/DIALOGUE/reveal shot has motion or lip-sync the viewer will catch
        if slowed, so extendable=False unless the author overrides."""
        static_kinds = {"establishing", "setup", "aftermath", "emotion", "transition"}
        motion_kinds = {"action", "dialogue", "reveal", "discovery", "reaction", "montage"}
        dep = set(self.depicts or [])
        if dep & motion_kinds:
            return False
        if dep & static_kinds:
            return True
        return False   # unknown -> conservative (not extendable)

    def compute_capacity(self, raw_sec: float, profile=None) -> dict:
        """Fill any UNSET Mức 3 fields from the raw window length + a voice
        profile. Never overwrites explicit author values. Returns the resolved
        dict (raw_duration_sec, max_play_duration_sec, max_narration_words_en,
        extendable, stretch_tolerance)."""
        if self.raw_duration_sec is None:
            self.raw_duration_sec = round(float(raw_sec), 3)
        if self.extendable is None:
            self.extendable = self.is_extendable_default()
        tol = self.stretch_tolerance if self.extendable else 1.0
        if self.max_play_duration_sec is None:
            self.max_play_duration_sec = round(self.raw_duration_sec * tol, 3)
        if self.max_narration_words_en is None:
            if profile is None:
                from pipeline import calibration as _cal
                profile = _cal.default_profile()
            # Narration capacity = how long the shot may PLAY, which for an
            # extendable shot includes the Mức 1 slowdown headroom on top of the
            # raw window. max_play_duration_sec already folds stretch_tolerance;
            # the Mức 1 render can slow up to BINDING_SLOWDOWN_MAX beyond that, so
            # the true word ceiling uses raw * BINDING_SLOWDOWN_MAX.
            cap = self.raw_duration_sec * BINDING_SLOWDOWN_MAX
            self.max_narration_words_en = profile.max_words_for_capacity(cap)
        return {
            "raw_duration_sec": self.raw_duration_sec,
            "max_play_duration_sec": self.max_play_duration_sec,
            "max_narration_words_en": self.max_narration_words_en,
            "extendable": self.extendable,
            "stretch_tolerance": self.stretch_tolerance,
        }


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #
def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8-sig"))


def load_skeleton(project: str) -> Skeleton:
    p = config.project_dir(project) / "skeleton.json"
    if not p.exists():
        raise FileNotFoundError(str(p))
    data = _read_json(p)
    return Skeleton(**_drop_unknown(Skeleton, data))


def load_draft(project: str) -> Draft:
    p = config.project_dir(project) / "draft.json"
    data = _read_json(p)
    data.setdefault("project", project)
    return Draft(**_drop_unknown(Draft, data))


def load_names(project: str) -> set:
    """Character names, lowercased. Accepts both the flat and the cast form.

    Flat (old, still valid):   {"names": ["Teddy Daniels", "Dr. Cawley"]}
    Cast (new):                {"names": [{"character": "Teddy Daniels",
                                           "actor": "Leonardo DiCaprio"}, ...]}

    The `actor` field exists because PRE-CATALOGUE (RULES A7) already reads the
    Wikipedia *Cast* section, which maps actors to characters - and then names.json
    threw the actor half away. That is the one piece of data that lets anything
    put a name to a face, so it is now kept. Reading it is optional; nothing
    breaks if a project only has the flat form.
    """
    p = config.project_dir(project) / "names.json"
    if not p.exists():
        return set()
    try:
        nd = _read_json(p)
        names = nd.get("names", nd) if isinstance(nd, dict) else nd
        out = set()
        for n in names:
            if isinstance(n, dict):
                c = n.get("character") or n.get("name")
                if c:
                    out.add(str(c).strip().lower())
            elif n:
                out.add(str(n).strip().lower())
        return out
    except Exception:
        return set()


def load_name_tokens(project: str) -> set:
    """Every legal name TOKEN: characters, actors, and actor nicknames.

    Separate from `load_names` on purpose. `load_names` feeds binding_audit,
    which matches a claim's subject against a WHOLE character name and must
    keep doing so. This one exists for the [NAME] invented-name guard, which
    scans single capitalised words out of narration.

    Whole-string membership was the defect: names.json holds "Dr. John Cawley",
    narration says "Cawley", and the guard flagged a real name. Measured on two
    finished films, 11 of 14 and 12 of 13 [NAME] flags were real names it
    should have known - which is why RULES B8 told authors to ignore the gate
    entirely. Tokenising drops those to 4 and 3, with injected misspellings
    still caught 10/10.

    Actors and `actor_alias` are folded in because narration legitimately names
    them ("Jonah Hill", "Billkin"). The known cost is recombination: once
    "Rachel" and "Daniels" are each legal, "Rachel Daniels" passes. The old
    guard caught 1 of 5 such cases and buried it under 11 false flags, so the
    detection being given up was never usable.
    """
    p = config.project_dir(project) / "names.json"
    if not p.exists():
        return set()
    _skip = {"dr", "mr", "mrs", "ms", "the", "of", "and", "a", "an"}
    try:
        nd = _read_json(p)
        names = nd.get("names", nd) if isinstance(nd, dict) else nd
        out = set()

        def _add(value):
            for part in re.split(r"\s*/\s*", str(value)):
                part = part.strip().lower()
                if not part:
                    continue
                out.add(part)                     # whole form
                for tok in part.split():          # and each token
                    tok = tok.strip(".,'\u2019\"")
                    if len(tok) >= 3 and tok not in _skip:
                        out.add(tok)

        for n in names:
            if isinstance(n, dict):
                for field in ("character", "name", "actor", "actor_alias"):
                    if n.get(field):
                        _add(n[field])
            elif n:
                _add(n)
        return out
    except Exception:
        return set()


def load_cast(project: str) -> dict:
    """{character: actor} from names.json, or {} when the file has no actors.

    Consumers: anything that has to identify a face. Empty is a normal answer -
    the flat names.json form carries no actors, and most projects still use it.
    """
    p = config.project_dir(project) / "names.json"
    if not p.exists():
        return {}
    try:
        nd = _read_json(p)
        names = nd.get("names", nd) if isinstance(nd, dict) else nd
        out = {}
        for n in names:
            if isinstance(n, dict):
                c, a = n.get("character") or n.get("name"), n.get("actor")
                if c and a:
                    out[str(c).strip()] = str(a).strip()
        return out
    except Exception:
        return {}


def load_shots(project: str):
    """
    Merge all footage sources into:
      - shots_by_id: dict[str, Shot]   (pool labels, line:<n>, shots.json ids)
      - pool_families: dict[str, list[Shot]]  (broll family -> its shots, for set-union)
    Footage is resolved from the EXISTING broll.json "pool" dict and inline
    clip_start/clip_end on draft lines. shots.json is optional extra detail.

    Returns (shots_by_id, pool_families, problems).

    `problems` is a list of per-entry error strings. It used to be that ONE bad
    entry raised out of this function, the caller swallowed the exception and
    substituted empty dicts, and every downstream footage audit then ran on
    nothing and reported "clean". A single `depicts: ['object']` in Shutter
    Island hid all 31 shots that way for the life of the project. So a bad entry
    is now skipped and recorded; the rest still load, and the caller is expected
    to surface `problems` and refuse to certify the audit clean.
    """
    pdir = config.project_dir(project)
    shots_by_id: dict = {}
    pool_families: dict = {}
    problems: list = []

    # 1) broll.json pool entries
    bp = pdir / "broll.json"
    if bp.exists():
        try:
            bd = _read_json(bp)
            pool = bd.get("pool", bd)
            for label, meta in pool.items():
                if not isinstance(meta, dict):
                    continue
                try:
                    sh = Shot(
                        id=label, source="broll",
                        time_start=meta.get("start"), time_end=meta.get("end"),
                        chars=meta.get("chars", []),
                        depicts=meta.get("depicts", []),
                        action=meta.get("action", meta.get("note", "")),
                        family=meta.get("family"),
                        strength=meta.get("strength", "hero" if meta.get("hero") else None),
                    )
                except Exception as e:
                    problems.append(f"broll pool entry {label!r}: {e}")
                    continue
                shots_by_id[label] = sh
                if sh.family:
                    pool_families.setdefault(sh.family, []).append(sh)
        except Exception as e:
            problems.append(f"broll.json unreadable: {e}")

    # 2) optional shots.json (extra catalogue, e.g. for explicit scenes)
    sp = pdir / "shots.json"
    if sp.exists():
        try:
            sd = _read_json(sp)
            for s in sd.get("shots", []):
                try:
                    # shots.json says clip_start/clip_end; Shot calls the same
                    # thing time_start/time_end, so _drop_unknown was throwing
                    # the window away and every Shot from shots.json arrived
                    # with no timing at all. binding_audit then had nothing to
                    # match a line against except an exact id string.
                    row = {**s, "source": s.get("source", "shots")}
                    for src_k, dst_k in (("clip_start", "time_start"),
                                         ("clip_end", "time_end")):
                        if row.get(src_k) is not None and row.get(dst_k) is None:
                            try:
                                row[dst_k] = parse_ts(row[src_k])
                            except Exception:
                                pass
                    sh = Shot(**_drop_unknown(Shot, row))
                except Exception as e:
                    problems.append(f"shots.json entry {s.get('id', '?')}: {e}")
                    continue
                shots_by_id[sh.id] = sh
        except Exception as e:
            problems.append(f"shots.json unreadable: {e}")

    return shots_by_id, pool_families, problems


def estimate_narration_seconds(words: int, tag: str | None = None,
                               rate_bump: float | None = None) -> float:
    """Conservative draft-time estimate of a line's spoken length (seconds).

    No TTS audio exists at `recap.py draft` time, so we estimate from word count
    plus the inter-line GAP. We deliberately OVER- rather than under-estimate: a
    line that JUST fits the estimate must be guaranteed to fit the real audio.

    When `tag` is given and the production voice has been CALIBRATED, this uses
    that tag's measured conservative rate. That matters more than it looks: a
    flat rate treated `sad` and `tense` as the same speed, and Warren speaks
    them 110 WPM apart (151 vs 261 measured over 109 lines). The flat 185 WPM
    over-stated capacity on every slow line, which is why the first Warren
    render produced 19 capacity overruns and all the large ones were `sad` or
    `reveal`. Falls back to config.TTS_WORDS_PER_MINUTE when the voice has
    never been measured - a single baseline, never an invented second one.
    """
    # A line carrying `rate_bump` WILL be synthesized faster - the bump is part
    # of the TTS cache key, so it is a property of the line, not a one-off. Not
    # applying it here would make this gate permanently flag lines that the
    # render then fits comfortably. Pauses do not scale fully with rate, so
    # only 90% of the bump is credited (the same discount fit_narration uses).
    _bump = 1.0
    if rate_bump:
        try:
            _bump = max(1.0, 1.0 + (float(rate_bump) - 1.0) * 0.90)
        except (TypeError, ValueError):
            _bump = 1.0

    if tag is not None:
        try:
            from pipeline.calibration import production_profile
            prof = production_profile()
            if prof.is_measured:
                wps = prof.rate_for(tag, conservative=True)
                if wps > 0:
                    gap = float(getattr(config, "GAP_BETWEEN_LINES", 0.18))
                    return max(0, int(words)) / (wps * _bump) + gap
        except Exception:
            pass
    wpm = max(1.0, float(config.TTS_WORDS_PER_MINUTE)) * _bump
    gap = float(getattr(config, "GAP_BETWEEN_LINES", 0.18))
    # NARRATION_LEAD_IN is deliberately NOT added here. It looks like it should
    # be - a rendered clip is lead + narration + GAP long - but render.py
    # clamps the lead per line (_lead_for) precisely so it can never push a line
    # past its shot's slow-motion ceiling. Adding it to this estimate instead
    # RE-CREATES the failure the clamp exists to prevent, at draft time:
    # measured at a flat 0.5s, interstellar2014_linear went 0 -> 8 capacity
    # violations, parasite2019 0 -> 12, gonegirl2014 49 -> 52, on drafts that
    # render fine. The lead-in is contract-neutral by construction; keep it out
    # of the contract.
    return (max(0, int(words)) / wpm) * 60.0 + gap


def binding_capacity_check(draft: "Draft", shots: dict,
                           measured: dict | None = None) -> list:
    """Mức 1 capacity audit. For every line bound to an explicit timed shot
    (clip_start/clip_end), check that its estimated narration fits the shot
    window within the BINDING_SLOWDOWN_MAX allowance.

    Returns a list of dicts (NOT raising) so the audit can report ALL offenders
    at once. Each dict: line_id, words, narr_est, shot_dur, capacity, severity
    ('ok' | 'slowdown' | 'violation'). Lines that are pool/montage/silence or
    that lack a usable [clip_start, clip_end] window are skipped (capacity is
    only meaningful for a single explicit window).
    """
    out = []
    for ln in draft.lines:
        if ln.pool:
            continue
        words = ln.word_count()
        if words == 0:
            continue  # silence / visual-only line

        # Mức 2: resolve the line's bound segments (1 shot, or a montage list).
        # The available visual time is the SUM of each segment's play_duration
        # (when given) or its raw window length (clip_end - clip_start). The
        # Mức 1 hard constraint then applies to that SUM:
        #   narration <= total_visual * BINDING_SLOWDOWN_MAX.
        try:
            segs = ln.bind_segments()
        except Exception:
            continue
        if not segs:
            continue
        # Capacity = the REAL footage available = sum of each shot's raw window
        # (clip_end - clip_start). NOTE: play_duration is how long a shot is
        # SCHEDULED to play (the render's proportional split, which sums to the
        # narration length); it is NOT the capacity. Using raw windows here means
        # the Mức 1 constraint asks "is there enough real footage to carry this
        # narration within slowdown?", independent of how the time is split.
        total_dur = 0.0
        bad = False
        for b in segs:
            try:
                s = parse_ts(b.clip_start)
                e = parse_ts(b.clip_end)
            except Exception:
                bad = True
                break
            raw = e - s
            if raw <= 0:
                bad = True
                break
            total_dur += raw
        if bad or total_dur <= 0:
            continue

        # The DELIVERY TAG is part of the capacity question, not a detail: it
        # is what the voice is told to do, and it changes the rate by up to
        # 1.7x. Passing it here is what turns this gate from "a line of about
        # this many words" into "this line, spoken this way".
        _tag = getattr(ln, "delivery", None)
        _bump = getattr(ln, "rate_bump", None)
        # MEASUREMENT BEATS ESTIMATION. This function exists because at draft
        # time there is no audio - but when there IS fresh audio for a line
        # there is no reason to estimate it. Per-line variance inside a tag is
        # about +-25% (line 108 speaks at 2.96 w/s against a `reveal` mean of
        # 2.56), so an estimate is simply weaker evidence, and letting it
        # overrule a measurement produced four false hard failures on lines the
        # real audio fits comfortably.
        _meas = (measured or {}).get(getattr(ln, "id", None))
        narr_est = (float(_meas) + float(getattr(config, "GAP_BETWEEN_LINES",
                                                 0.18))
                    if _meas else estimate_narration_seconds(words, _tag, _bump))
        capacity = total_dur * BINDING_SLOWDOWN_MAX

        # TWO TIERS, because one tier made this gate lie in one direction or
        # the other. The budget rate is deliberately ~1 sigma slower than the
        # measured mean, so a line authored to fit its MEASURED length looks 9%
        # over here. Failing those hard blocks renders that would have
        # succeeded, and a gate that cries wolf gets bypassed - which is worse
        # than no gate. So:
        #   violation ("hard")  - will not fit even at the voice's TYPICAL rate
        #                         for this tag. No take will save it.
        #   at-risk ("warn")    - fits at the typical rate but not at the
        #                         conservative one. The pre-flight decides on
        #                         the real audio, which is the only authority
        #                         once narration exists.
        narr_typical = narr_est
        try:
            from pipeline.calibration import production_profile
            _prof = production_profile()
            if _prof.is_measured and _tag is not None:
                _wps = _prof.rate_for(_tag, conservative=False)
                if _wps > 0:
                    _m = 1.0
                    if _bump:
                        _m = max(1.0, 1.0 + (float(_bump) - 1.0) * 0.90)
                    narr_typical = words / (_wps * _m) + float(
                        getattr(config, "GAP_BETWEEN_LINES", 0.18))
        except Exception:
            pass

        if narr_est <= total_dur:
            sev = "ok"
        elif narr_est <= capacity:
            sev = "slowdown"
        elif _meas:
            # measured and genuinely over: no estimate to argue with
            sev = "violation"
        elif narr_typical > capacity:
            sev = "violation"
        else:
            sev = "at-risk"

        # A line carrying `rate_bump` was fitted by tools/fit_narration.py
        # against its REAL measured audio, with a safety margin. If its audio
        # is now stale (the bump or the text changed, so it re-synthesizes on
        # the next render) a word-count estimate is the weakest of the three
        # kinds of evidence available and must not hard-block a render that the
        # pre-flight will measure exactly. Downgrade to at-risk and let the
        # measurement decide.
        if sev == "violation" and not _meas and _bump:
            sev = "at-risk"

        out.append({
            "line_id": ln.id, "words": words, "narr_est": narr_est,
            "narr_typical": round(narr_typical, 2),
            "shot_dur": total_dur, "capacity": capacity, "severity": sev,
            "n_shots": len(segs), "tag": _tag,
            "measured": bool(_meas),
        })
    return out


def parse_ts(ts: str) -> float:
    """HH:MM:SS.mmm -> seconds. Mirror of draft.parse_ts for standalone use."""
    parts = str(ts).split(":")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts[-3], parts[-2], parts[-1]
    return h * 3600 + m * 60 + s



