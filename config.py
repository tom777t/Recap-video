"""
Central configuration + tool discovery for the recap pipeline.

Nothing here needs an internet connection except the actual TTS/download steps.
Edit the CAPTION_* and DEFAULT_* values to tune look & feel without touching the
pipeline code.
"""
from __future__ import annotations

import os
import shutil
import glob
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent
PROJECTS_DIR = ROOT / "projects"
BIN_DIR = ROOT / "bin"
PROMPTS_DIR = ROOT / "prompts"

# --------------------------------------------------------------------------- #
# Defaults (override most of these with CLI flags)
# --------------------------------------------------------------------------- #
DEFAULT_WHISPER_MODEL = "small"      # tiny | base | small | medium | large-v3
DEFAULT_TARGET_MINUTES = 20          # target final recap length
DEFAULT_TTS_VOICE = "en-US-AndrewMultilingualNeural"  # natural male US voice
DEFAULT_TTS_RATE = "+22%"            # brisk "review phim" delivery = hooks the viewer

# Words-per-minute estimate for English neural TTS at the rate above.
# Used to estimate narration duration when planning the draft.
# Lowered from 185 after the pacing slow-down (normal/tense rates reduced).
TTS_WORDS_PER_MINUTE = 170

# --------------------------------------------------------------------------- #
# Stage 2 depth targets (2026-06-22 depth-target enhancement).
# A "tier" maps a film's intended runtime to how full the shot catalogue should
# be FROM THE START, so Stage 2 aims for the film's natural shot capacity rather
# than under-cataloguing and expanding reactively. Each tier carries:
#   shots      = (min, max) total catalogued shots to aim for
#   per_beat   = (min, max) default shots PER BEAT (was implicitly 1-2)
# These are FLOORS TO CONSIDER, not quotas to pad to. The coverage audit warns
# (soft) when a catalogue falls short; it never pads. Override per-project via
# the beats_proposal.md "depth_target:" header line.
DEPTH_TIERS = {
    "recap":        {"runtime": "9-13 min",  "shots": (60, 80),   "per_beat": (2, 3), "runtime_floor_min": 9.0},
    "fuller_recap": {"runtime": "14-17 min", "shots": (90, 110),  "per_beat": (3, 3), "runtime_floor_min": 13.5},
    "video_essay":  {"runtime": "18+ min",   "shots": (110, 130), "per_beat": (3, 4), "runtime_floor_min": 17.0},
}
# DRAFT-TARGET gate (2026-06-30, Stage 3 depth enforcement). The Stage 2
# depth-target enhancement filled the SHOT catalogue; this fills the NARRATION.
# A draft can bind 100 shots and still be under-authored - short lines leave most
# of each shot's capacity unused, so the recap runs short of its declared tier.
# The gate estimates runtime at the CALIBRATED real rate (not the conservative
# 170-WPM heuristic) and reports capacity fill. Soft (advisory) only.
# Fill = draft words / sum(shot word ceilings). Target band 70-85%.
DRAFT_FILL_TARGET = (0.70, 0.85)
DRAFT_FILL_UNDER_WARN = 0.65     # warn below this (clearly under-authored)
DRAFT_FILL_OVER_WARN = 0.90      # warn above this (over-stuffed -> slow-mo everywhere)
# When the conservative and real-rate runtime estimates diverge by more than
# this fraction, print a one-line note that the conservative estimate overshoots.
DRAFT_ESTIMATE_DIVERGENCE_NOTE = 0.15
# When a proposal declares no explicit depth_target, infer the tier from the
# midpoint of its "Target: N-M min" runtime line against these upper bounds.
DEPTH_TIER_RUNTIME_CEIL = [(13, "recap"), (17, "fuller_recap"), (9999, "video_essay")]
# A beat catalogued with fewer than this many shots is flagged for review.
DEPTH_MIN_SHOTS_PER_BEAT = 2
# SET-PIECE COVERAGE gate (linear, SCRIPT stage). Within each human-confirmed,
# dense-verified set-piece range, no gap between consecutive narration lines (or
# from a range edge) may exceed this tier-relative max-gap. The failure mode is
# an unnarrated stretch a viewer can't follow - not a raw coverage %.
# Threshold = max(FLOOR, MULT x the recap's own median line gap): a gap fails
# only if it is both absolutely long AND several times this recap's own cadence
# (tier follows the film; the gate follows the tier). v1 PROVISIONAL - the
# median term is self-referential (a lazily-sparse recap raises its own median
# and loosens the gate); calibrated on Spider-Man only, revisit after film #2.
SETPIECE_MAXGAP_FLOOR = 240.0    # seconds; absolute lower bound on the max-gap
SETPIECE_MAXGAP_MULT = 3.0       # x the film's median consecutive-line gap

# --------------------------------------------------------------------------- #
# Transitions + audio feel (review-phim style)
# --------------------------------------------------------------------------- #
XFADE_DURATION = 0.28      # crossfade/dissolve length between clips (seconds)
GAP_BETWEEN_LINES = 0.18   # a real micro-breath between lines (was 0.05; too fast)
NARRATION_FADE = 0.04      # micro fade in/out on each line to kill pops

# Motion energy (Ken Burns) - subtle constant zoom/pan so nothing sits still.
MOTION_ENABLE = True
MOTION_ZOOM = 0.08         # max extra zoom over a clip (0.08 = up to +8%)
# direction alternates per clip automatically (in/out)

# Silent action beats (no-voiceover holds that let action breathe).
SHOWCASE_HOLD = 8.0        # default seconds for a big "showcase" action beat
SHOWCASE_HOLD_MAX = 10.0   # never silent-hold longer than this
# A line can set "hold": 8 for a single held shot, or "montage": ["A4","A7",..]
# to cut through several action shots during the (mostly silent) hold.

# Background music
MUSIC_VOLUME = 0.18        # music level under the voice (0..1); ~0.12-0.18 is good. Joker v3: 0.18 (v2 had NO music - render was called without --music; auto-discovery now fixes that, and 0.13 was too subtle so raised to 0.18 for a clearly-audible bed).
MUSIC_DUCK = True          # duck music slightly whenever narration plays
MUSIC_FADEOUT = 3.0        # fade music out over N seconds at the very end
# Gap 3 silence shots: during a narration-free "silence" shot the music swells
# from the ducked narration level up to this level, then fades back when the
# next narration starts. SILENCE_FADE = the rise/fall transition (seconds).
SILENCE_MUSIC_VOLUME = 0.35
SILENCE_FADE = 0.5

# DARK-scene exposure lift (render): default brightness lift applied to shots a
# catalogue marks DARK (or sets exposure_lift on). Brightens shadows so very dim
# footage (bunkers, night floods) stays readable - never darkens (Joker B35
# lesson: do not blur/darken already-dark footage into unreadable mush).
# Disabled by default on the linear/recap side: dark space scenes (e.g.
# Interstellar's black-hole/space shots) were getting washed out by the auto
# lift. Set to 0.0 so DARK-tagged shots are NOT auto-brightened. A project can
# still opt in per-shot via an explicit `exposure_lift` field in its shots.json.
# Re-enable globally by restoring a positive value (e.g. 0.18).
DARK_EXPOSURE_LIFT = 0.0

# Loudness mastering (YouTube standard ~ -14 LUFS)
LOUDNORM_ENABLE = True
LOUDNORM_I = -15.0         # integrated loudness target (LUFS); nudged down from -14 (felt a touch loud)
LOUDNORM_TP = -1.5         # true peak ceiling (dBTP)
LOUDNORM_LRA = 11.0        # loudness range

# --------------------------------------------------------------------------- #
# Sound design (synthesized SFX, mixed under music, below the voice)
# --------------------------------------------------------------------------- #
SFX_ENABLE = False         # master switch for sound design (Joker v2 render: --no-sfx)
SFX_WHOOSH = True          # transition whooshes between clips
SFX_BOOM = True            # low boom on hold/reveal action beats
SFX_STING = True           # bright sting on the channel-intro line
SFX_RISER = True           # rising tension on mystery beats
# gains in dB (negative = quieter); kept subtle so they sit under the mix
SFX_WHOOSH_DB = -16.0
SFX_BOOM_DB = -12.0        # nudged down from -10 (booms were the loudest hits)
SFX_STING_DB = -14.0
SFX_RISER_DB = -18.0

# --------------------------------------------------------------------------- #
# Channel branding (used by the script style guide; not enforced in code)
# --------------------------------------------------------------------------- #
CHANNEL_NAME = "Serabudabu"

# --------------------------------------------------------------------------- #
# B-roll reuse caps (avoid awkward repetition).
# A normal pool shot may appear at most MAX_REUSE times; a "hero" shot (flagged
# in broll.json) may appear at most MAX_REUSE_HERO times. The draft validator
# enforces these and prints a reuse histogram.
# --------------------------------------------------------------------------- #
MAX_REUSE = 2          # any normal shot: at most 2 uses in the whole video
MAX_REUSE_HERO = 2     # hero shots also capped at 2 (tightened per standard)
MAX_FAMILY_USES = 2    # each VISUAL FAMILY (fin/explosion/chase...) at most 2x
                       # -> catches look-alike shots even across different labels

# --------------------------------------------------------------------------- #
# Per-line TTS delivery presets. A line in draft.json can set "delivery" to one
# of these keys, or override rate/pitch/volume directly.
# --------------------------------------------------------------------------- #
TTS_DELIVERY = {
    "normal":  {"rate": "+16%", "pitch": "+0Hz",  "volume": "+0%"},  # slowed from +24 (middle felt too fast)
    "hook":    {"rate": "+30%", "pitch": "+2Hz",  "volume": "+8%"},  # energetic open
    "tense":   {"rate": "+26%", "pitch": "+3Hz",  "volume": "+8%"},  # slowed from +34 (action/urgency)
    "mystery": {"rate": "+10%", "pitch": "-3Hz",  "volume": "-2%"},  # hushed, slow
    "sad":     {"rate": "+6%",  "pitch": "-4Hz",  "volume": "-4%"},  # somber beats
    "intro":   {"rate": "+20%", "pitch": "+1Hz",  "volume": "+6%"},  # channel intro
    "outro":   {"rate": "+18%", "pitch": "+0Hz",  "volume": "+4%"},  # sign-off
}
DEFAULT_DELIVERY = "normal"

# --------------------------------------------------------------------------- #
# Caption styling (burned in via ffmpeg subtitles filter, ASS overrides)
# These map to libass style fields. Tweak freely.
# --------------------------------------------------------------------------- #
CAPTION_FONT = "Arial"
CAPTION_FONT_SIZE = 22          # relative to a 384px PlayResY (see srt.py)
CAPTION_PRIMARY_COLOUR = "&H00FFFFFF"   # white  (AABBGGRR hex, AA=00 opaque)
CAPTION_OUTLINE_COLOUR = "&H00000000"   # black outline
CAPTION_BACK_COLOUR = "&H80000000"      # 50% black shadow box
CAPTION_OUTLINE = 2             # outline thickness
CAPTION_SHADOW = 1              # drop shadow
CAPTION_BOLD = -1               # -1 = true in ASS
CAPTION_MARGIN_V = 40           # vertical margin from bottom
CAPTION_MAX_CHARS_PER_LINE = 38 # wrap captions to keep them readable
CAPTION_MAX_LINES = 2
CAPTION_ANIMATE = True          # subtle pop-in (fade + scale) per caption
CAPTION_FADE_MS = 120           # fade/animation duration in ms
# Captions are OFF by default (user preference); enable per-run with --captions,
# or flip this to True to make them the default.
DEFAULT_CAPTIONS = False

# Output video
OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080
OUTPUT_FPS = 30
VIDEO_CRF = 20                  # lower = better quality / bigger file
VIDEO_PRESET = "medium"


# --------------------------------------------------------------------------- #
# Tool discovery
# --------------------------------------------------------------------------- #
def _find_in_winget(exe: str) -> str | None:
    """Search the per-user WinGet package store for an executable."""
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return None
    patterns = [
        os.path.join(local, "Microsoft", "WinGet", "Packages", "*", "*", "bin", exe),
        os.path.join(local, "Microsoft", "WinGet", "Packages", "*", "*", exe),
        os.path.join(local, "Microsoft", "WinGet", "Links", exe),
    ]
    for pat in patterns:
        hits = glob.glob(pat)
        if hits:
            return hits[0]
    return None


def find_tool(exe_name: str) -> str:
    """
    Locate an executable in this order:
      1. ./bin/<exe>            (manual drop-in, highest priority)
      2. PATH                   (normal install)
      3. WinGet package store   (installed but PATH not refreshed yet)
    Returns the resolved path or raises a clear, actionable error.
    """
    exe = exe_name if exe_name.lower().endswith(".exe") else exe_name + ".exe"

    # 1. local bin
    local = BIN_DIR / exe
    if local.exists():
        return str(local)

    # 2. PATH
    on_path = shutil.which(exe_name) or shutil.which(exe)
    if on_path:
        return on_path

    # 3. winget store
    winget = _find_in_winget(exe)
    if winget:
        return winget

    raise FileNotFoundError(
        f"Could not find '{exe_name}'.\n"
        f"  Fix: drop {exe} into:\n      {BIN_DIR}\n"
        f"  or install it and restart your shell so PATH refreshes."
    )


def ffmpeg() -> str:
    return find_tool("ffmpeg")


def ffprobe() -> str:
    return find_tool("ffprobe")


def yt_dlp() -> str:
    """yt-dlp ships as a python module too; prefer the exe but fall back."""
    try:
        return find_tool("yt-dlp")
    except FileNotFoundError:
        return ""  # caller will use the python module form


# --------------------------------------------------------------------------- #
# Project helpers
# --------------------------------------------------------------------------- #
def project_dir(name: str) -> Path:
    d = PROJECTS_DIR / name
    return d


def ensure_project(name: str) -> Path:
    d = project_dir(name)
    (d / "narration").mkdir(parents=True, exist_ok=True)
    return d
