

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
# (DEFAULT_TARGET_MINUTES removed 2026-08-09 - it was referenced nowhere and
#  contradicted DEPTH_TIERS, which is the real source of target runtime.)
DEFAULT_TTS_VOICE = "en-US-AndrewMultilingualNeural"  # natural male US voice
# 2026-10-21 REVERTED to +10%. History, because the number moved twice:
#
#   +22%  original. Measured 198 WPM.
#   -15%  set on the research report's claim that the genre's biggest channel
#         runs 121 WPM, making 198 "64% too fast". That figure came from a
#         third-party site's declared word count and the report itself flagged
#         it as unverified. It was wrong to build on.
#   +10%  set from OUR OWN measurement of real recap channels' captions:
#         Movie Recaps 236/239/239/245 WPM across four videos, TheCutFrame 205
#         (de-rolled auto-captions, duration cross-checked against info.json
#         and against an isolated 60-second window). Every English channel
#         sampled is FASTER than our original 198. SAKURA REVIEW, the voice
#         model, runs 257-264 Vietnamese syllables/min, which is roughly
#         175-200 English WPM at 1.3-1.5 syllables per word.
#         See docs/NARRATOR_VOICE.md.
#
# The target is 185 WPM MEASURED ON REAL DRAFT TEXT, and that qualifier is the
# whole lesson. A continuous passage reads faster than a draft: a draft is full
# of short punch sentences, and each line is a separate file with
# GAP_BETWEEN_LINES between them. Measured on 14 real badgenius2017_machine
# lines including the gaps:
#       +10% -> 186.1 WPM      +14% -> 192.3 WPM
# while the same voice on one continuous 87-word passage read +0% as 189.5.
# Calibrating on continuous prose is exactly how -15% ended up 35 WPM low.
DEFAULT_TTS_RATE = "+10%"

# Words-per-minute FALLBACK, used only when the voice has no measured profile
# in config/voice_profiles.json. The measured profile is always primary and the
# output names which basis it used. 186 = measured at the base rate above.
TTS_WORDS_PER_MINUTE = 186

# --------------------------------------------------------------------------- #
# Stage 2 depth targets (2026-06-22 depth-target enhancement).
# A "tier" maps a film's intended runtime to how full the shot catalogue should
# be FROM THE START, so Stage 2 aims for the film's natural shot capacity rather
# than under-cataloguing and expanding reactively. Each tier carries:
#   shots      = (min, None) total catalogued shots FLOOR. There is no ceiling.
#   per_beat   = (min, max) default shots PER BEAT (was implicitly 1-2)
# These are FLOORS TO CONSIDER, not quotas to pad to. The coverage audit warns
# (soft) when a catalogue falls short; it never pads. Override per-project via
# the beats_proposal.md "depth_target:" header line.
#
# CEILING REMOVED 2026-08-31. It contradicted per_beat: DEPTH-UNDER demands
# per_beat[0] shots on EVERY numbered beat, so a beat map of N beats needs
# N x per_beat[0] shots, while the old ceiling capped the same catalogue. The two
# were satisfiable together only below ~43 beats (video_essay), ~36
# (fuller_recap), ~40 (recap). Bad Genius has 80 beats: DEPTH-UNDER wanted 240,
# the ceiling allowed 130. The ceiling has also been wrong in the other
# direction on shipped films - Superbad 183 (41% over), Gia Tai Cua Ngoai 280.
# Shot count does not set recap length; LINE count does. The catalogue is a menu
# and BINDING-INTEGRITY requires every line to land on a shot, so more shots is
# more choice, not more obligation. See docs/GATE_CANDIDATES.md "DEPTH-TOTAL
# ceiling".
# TIER IS A DESCRIPTIVE LABEL (2026-09-05). It carries NO thresholds.
#   `runtime` and `shots` are RETIRED - kept only so the tier names still read
#   as meaning something to a human ("this film is a video_essay kind of film").
#   Nothing compares against them: DRAFT-UNDER-TARGET and DEPTH-TOTAL were both
#   removed. A threshold whose subject also picks the tier measures the label,
#   not the work - see docs/RULES.md "A11 nghỉ hưu".
#   The author's intended length now lives in draft.json `target_minutes`,
#   pinned in state.json and guarded by [TARGET-LOCK]. It is an INPUT.
#   `per_beat` is still checked - but per BEAT, against the beat map, not
#   against the label.
DEPTH_TIERS = {
    "recap":        {"runtime": "9-13 min  (label only)",  "per_beat": (2, 3)},
    "fuller_recap": {"runtime": "14-17 min (label only)",  "per_beat": (3, 3)},
    "video_essay":  {"runtime": "18+ min   (label only)",  "per_beat": (3, 4)},
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

# Lead-in: how long the PICTURE is on screen before the voice starts, per line.
# --------------------------------------------------------------------------- #
# Until 2026-08-26 narration began on a clip's first frame, so the cut and the
# voice landed together and the voice read as running ahead of the image. On
# eight fast-cut films nobody noticed; on howtomakemillions2024 - shots held for
# 27s on average, each needing a beat to register - it compounded over 114 lines
# and the viewer reported the narration ahead of the picture for the whole film.
#
# This is a GENRE PARAMETER, not a constant. A film that cuts 16 times a minute
# wants a short beat or none at all; a film that holds wants a longer one. Tune
# per project rather than treating 0.5 as correct everywhere.
#   0.0        - previous behaviour, voice on the first frame
#   0.3 - 0.5  - fast-cut / conventional recap
#   0.6 - 1.0  - held, slow, contemplative films
# Cost: each narrated line grows by this much, so a 114-line recap gains ~57s at
# 0.5s. It also raises the footage each line must carry, which tightens the
# binding contract (a line that only just fitted may now need mild slow-motion).
NARRATION_LEAD_IN = 0.5

# Motion energy (Ken Burns) - subtle constant zoom/pan so nothing sits still.
MOTION_ENABLE = True
MOTION_ZOOM = 0.08         # max extra zoom over a clip (0.08 = up to +8%)
# direction alternates per clip automatically (in/out)

# Silent action beats (no-voiceover holds that let action breathe).
SHOWCASE_HOLD = 8.0        # default seconds for a big "showcase" action beat
SHOWCASE_HOLD_MAX = 10.0   # never silent-hold longer than this
# A line can set "hold": 8 for a single held shot, or "montage": ["A4","A7",..]
# to cut through several action shots during the (mostly silent) hold.

# --------------------------------------------------------------------------- #
# FILM AUDIO under the narration (2026-10-20).
# Until now every clip's audio track was the narration ALONE: _build_clip maps
# [0:v] from the source and [1:a] from the narration mp3, so the film's own
# tyres, gunshots, score and dialogue were discarded on every clip in every
# render. Silence clips were worse - literally `anullsrc`.
# Now the source audio is mixed in underneath the voice.
# --------------------------------------------------------------------------- #
FILM_AUDIO_ENABLE = True
FILM_AUDIO_DB = -17.0      # under narration (-15..-20 is the band in the guides)
FILM_AUDIO_HOLD_DB = -6.0  # inside a narration_silence hold: let the film carry it
FILM_AUDIO_PRE_REVEAL_DB = -8.0   # raised in the seconds before a <reveal>
FILM_AUDIO_PRE_REVEAL_SEC = 1.5   # how long before the reveal the raise starts

# Background music
MUSIC_VOLUME = 0.15        # music level under the voice (0..1). History: 0.13 was judged too subtle, 0.18 too present. 0.15 from 2026-08-13.
# --------------------------------------------------------------------------- #
# MOOD BEDS (2026-10-20). One fixed bed for a whole film reads as wallpaper.
# Drop files in projects/<name>/music/{tense,neutral,action,sad}.mp3 and the
# render picks a bed per story stretch from the dominant delivery tag there.
# Missing files are NOT an error: the render falls back to music.mp3 and says
# so out loud.
# --------------------------------------------------------------------------- #
MUSIC_MOODS = ("tense", "neutral", "action", "sad")
MUSIC_MOOD_FOR_TAG = {
    "action": "action", "hook": "action",
    "tense": "tense", "mystery": "tense",
    "sad": "sad",
    "normal": "neutral", "intro": "neutral", "outro": "neutral",
    "reveal": "neutral",       # the music DROPS before a reveal anyway
}
MUSIC_MOOD_MIN_SEC = 25.0   # do not switch beds more often than this
# Ducking depth under the voice. The retention guides give 20-25 dB for
# ordinary narration and 8-12 dB in action, where the bed should be felt.
MUSIC_DUCK_DB = -22.0
MUSIC_DUCK_ACTION_DB = -10.0
# Cut the bed just before a reveal so the line lands into a hole.
MUSIC_PRE_REVEAL_DROP_SEC = 1.5
MUSIC_PRE_REVEAL_LEVEL = 0.02    # near-silence, not a hard zero (avoids a click)
MUSIC_DUCK = True          # duck music slightly whenever narration plays
MUSIC_FADEOUT = 3.0        # fade music out over N seconds at the very end
# Gap 3 silence shots: during a narration-free "silence" shot the music swells
# from the ducked narration level up to this level, then fades back when the
# next narration starts. SILENCE_FADE = the rise/fall transition (seconds).
SILENCE_MUSIC_VOLUME = 0.30
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
# 2026-10-20: SFX back ON, but only on REVEALS and HOLDS - see
# sfx.plan_events(). It used to emit a transition whoosh before every clip
# (~190 of them on a 190-line draft), a sting on the intro and a riser on every
# mystery beat, which is why it was switched off wholesale instead of aimed.
SFX_ENABLE = True          # master switch for sound design
SFX_WHOOSH = False         # retired: a whoosh on every cut is the cheap-recap tell
SFX_BOOM = True            # low boom on a reveal line and on a hold
SFX_STING = False          # retired with the intro sting
SFX_RISER = False          # retired: fired on every mystery beat
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
    # NOTE: "normal" carries no rate. _delivery_for() always overrides it with
    # base_rate (DEFAULT_TTS_RATE), so a rate here would be dead - the "+16%"
    # that used to sit on this line never reached a single rendered word.
    #
    # 2026-10-20 REBUILT. Two faults were fixed at once:
    #
    # 1. `reveal`, `action` and `discovery` had NO preset, and _delivery_for()
    #    silently fell back to "normal" for any unknown tag. So all 10 <reveal>
    #    lines in tokyodrift2006 and the <action> line in badgenius2017 were
    #    read at exactly the pace of an ordinary line: the writer marked the
    #    biggest moments in the film and the renderer ignored the marks. An
    #    unknown tag is now a hard ERROR - see _delivery_for().
    # 2. `tense` was +26% against a +22% base: 4 points apart, and 52% of the
    #    tokyodrift draft carried it. "Tense" had no flat ground to rise from.
    #
    # 2026-10-21: every rate shifted +25 points with the base (-15% -> +10%),
    # so the RELATIVE structure is unchanged - reveal still sits ~11 points
    # below normal, tense ~10 above, action/hook fastest, sad slowest. The
    # presets are deliberately expressed as absolute rates rather than offsets
    # because edge-tts takes an absolute rate; if the base moves again, these
    # must move with it or the spread silently collapses, which is what
    # happened when tense sat 4 points from a +22% base.
    "normal":  {              "pitch": "+0Hz", "volume": "+0%"},  # base +10%, 186 WPM measured
    "hook":    {"rate": "+25%", "pitch": "+2Hz", "volume": "+8%"},  # fastest, energetic open
    "action":  {"rate": "+25%", "pitch": "+1Hz", "volume": "+6%"},  # fastest
    "tense":   {"rate": "+20%", "pitch": "+3Hz", "volume": "+8%"},  # ~10 pts clear of normal
    "intro":   {"rate": "+15%", "pitch": "+1Hz", "volume": "+6%"},  # channel intro
    "outro":   {"rate": "+11%", "pitch": "+0Hz", "volume": "+4%"},  # sign-off, near normal
    "mystery": {"rate": "+3%",  "pitch": "-3Hz", "volume": "-2%"},  # hushed
    "reveal":  {"rate": "-1%",  "pitch": "-2Hz", "volume": "+2%"},  # slower + lower: it lands
    "sad":     {"rate": "-5%",  "pitch": "-4Hz", "volume": "-4%"},  # slowest
}
DEFAULT_DELIVERY = "normal"

# Silence inserted BEFORE a <reveal> line so the reveal arrives out of a gap
# rather than on the heels of the previous sentence. 400-800ms is the range the
# retention guides give; 0.6s is the middle. GAP_BETWEEN_LINES still applies
# everywhere else.
PRE_REVEAL_PAUSE = 0.6

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



