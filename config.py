

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
# PROMPTS_DIR removed 2026-10-21: nothing read it. The two places that mention
# the prompts folder print a literal path as guidance text, they do not open a
# file through a constant. Caught by tools/check_config_usage.py.

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
# output names which basis it used. 185 = measured on the Tokyo Drift draft
# through the production voice (Inworld "Warren"), calibrated per tag to land on
# this target - see pipeline/tts_providers._inworld for the rate tuning.
TTS_WORDS_PER_MINUTE = 185

# --------------------------------------------------------------------------- #
# ONE NARRATOR - the voice-consistency contract
# --------------------------------------------------------------------------- #
# The first Warren render sounded like two or three different readers. Measured
# over 106 real lines: sad 151 WPM, tense 267 WPM - a 1.77x spread. Three
# separate causes, all in the tag -> controls mapping:
#   1. deliveryMode varied (BALANCED / CREATIVE / STABLE). CREATIVE alone cost
#      9% of pace AND changed the timbre.
#   2. the steering cues instructed TEMPO and CHARACTER - "say fast and
#      driving", "whisper in a hushed style", "say with force".
#   3. speaking_rate ran 1.02 to 1.42 - a 1.39x spread on its own - added to
#      compensate for the pace a cue costs (~23%). The compensation was per-tag
#      and imperfect, so it traded a pace problem for a consistency problem.
#
# The contract now: ONE delivery mode, ONE speaking rate, and cues that may ask
# only for PAUSES and EMPHASIS. Emotion is carried by where the reader breathes
# and what they lean on, not by how fast they talk.
#
# Note the non-obvious part: EVERY tag carries a cue, including `normal`. A cue
# costs pace whatever it says, so a tag with no cue reads ~23% faster than the
# rest - leaving `normal` uncued would have been a new 1.2x spread. Uniform cue
# presence buys uniform pace.
VOICE_BASE_SPEAKING_RATE = 1.02
VOICE_DELIVERY_MODE = "BALANCED"     # one mode for every tag; never CREATIVE
# Tag rate x rate_bump must stay inside +-this fraction of the base rate. A
# per-line rate_bump from tools/fit_narration.py counts against the SAME band -
# fitting a line to its window may not be an exemption from sounding like the
# same person.
VOICE_RATE_BAND = 0.10
# Measured on the real audio, neighbour to neighbour. A mood change ramps
# across intervening lines rather than stepping.
VOICE_ADJACENT_MAX_JUMP = 0.08
# The ship gate: slowest to fastest line, measured. 1.25 is audibly "one
# narrator with range"; 1.77 was audibly three people.
VOICE_WPM_RATIO_MAX = 1.25
# Lines shorter than this are excluded from the rate statistics. Words/sec on a
# 4-word line is dominated by its lead-in and trailing silence, not by how fast
# it was read, so including them measures noise and fails the gate for nothing.
VOICE_RATE_MIN_WORDS = 6

# --------------------------------------------------------------------------- #
# [RUNTIME-BAND] soft band: a recap should run roughly this fraction of the
# film's own runtime. The human reference (Bad Genius) sits near 15%. This is a
# SOFT warning band only - outside it prints a note, never blocks. A recap that
# tells everything is not a recap, but a film can honestly want more or less,
# and hard-failing on runtime is how a draft drifts into padding to hit a number.
# --------------------------------------------------------------------------- #
RECAP_RUNTIME_PCT_LO = 15.0
RECAP_RUNTIME_PCT_HI = 20.0

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
# DRAFT_ESTIMATE_DIVERGENCE_NOTE removed 2026-10-21: nothing read it. It
# described a divergence note that no longer exists - the draft now reports a
# single runtime basis and names it, so there are no two estimates to compare.
# Caught by tools/check_config_usage.py.
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
# SHOWCASE_HOLD_MAX removed 2026-10-21. It said "never silent-hold longer than
# this" and nothing enforced it - a stated ceiling that does not hold is worse
# than no ceiling, because it reads as a guarantee. It was NOT moved to the
# allowed list: that list is for keys deliberately unread, and an unenforced
# promise is a bug, not a decision. If a hold ceiling is wanted, it should be
# implemented on purpose. Caught by tools/check_config_usage.py.
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

# --------------------------------------------------------------------------- #
# STEMS: the film's audio WITHOUT its dialogue
# --------------------------------------------------------------------------- #
# At -17 dB under narration and -6 dB in holds, the film's dialogue was audible
# almost continuously - narrator and characters talking over each other. But
# the non-dialogue audio is the best thing in the mix (engines, tyres, gear
# changes, impacts), so muting the film to fix it would be a worse trade.
#
# pipeline/stems.py separates the audio ONCE per project with Demucs and caches
# it. Everywhere the narrator speaks, and inside every hold, the pipeline uses
# the NO-VOCALS stem. The original mix is used only inside a <film_speaks>
# unit, where hearing a character is the entire point.
#
# There is no ffmpeg filter that does this: centre-channel subtraction needs
# true multichannel audio and wrecks a stereo mix. So separation is a real
# dependency, and if it is missing this is a STOP rather than a silent fallback
# to the un-separated mix - that fallback is the defect being removed.
FILM_AUDIO_USE_STEMS = True
# Separation model. MEASURED warm on a 60s sample with the output files
# verified (12 CPU cores, no CUDA - Intel Iris Xe only):
#   htdemucs     1.57 s/s   <- fastest WORKING model, and the best separator
#   mdx_extra    2.35 s/s   (a bag of 4 models, hence slower)
#   mdx_extra_q  unusable: needs `diffq`, which will not build on this machine.
#
# A correction worth recording: mdx_extra_q was first measured at 0.47 s/s and
# chosen on that basis. That number was a FAST FAILURE being timed - the
# benchmark suppressed output and never checked that any file appeared. Verify
# the artefact, not just the exit of the clock.
#
# 1.57 s/s is 2.7 hours for a 104-minute film, which is why only the spans the
# recap actually plays are separated (~25% of this film, ~41 min). See
# pipeline/stems.needed_spans.
DEMUCS_MODEL = "htdemucs"
# True  -> a missing/failed separation stops the render with install
#          instructions.
# False -> the render continues with the film audio MUTED under narration and
#          in holds. Honest but lossy: no dialogue, and no engines either.
FILM_AUDIO_REQUIRE_STEMS = True

# --------------------------------------------------------------------------- #
# <film_speaks>: narration STOPS and the film's own exchange plays at full
# level (2026-10-21).
# Measured on real channels: both English recap channels studied hand whole
# exchanges to the film - 136 and 99 dialogue markers in their captions - while
# this pipeline narrated over every second of every film. This is the one
# device the "bland" baseline does that we did not.
# A line declares `film_speaks_seconds: 6.0` and carries NO narration.
# Deliberately kept SPARSE: using someone's original audio is a copyright
# exposure, and the device stops working if it is everywhere.
# --------------------------------------------------------------------------- #
FILM_SPEAKS_DB = 0.0        # full level - this is the point of the unit
FILM_SPEAKS_MIN_SEC = 3.0   # under this nobody registers an exchange
FILM_SPEAKS_MAX_SEC = 15.0  # over this it stops being a recap
# 2026-10-27: 5 -> 3. This is now the ONLY place the film's own dialogue is
# heard (everywhere else uses the no-vocals stem), which makes each one a
# deliberate editorial event rather than one of many. Fewer original lines is
# also less copyright exposure. Each surviving unit must earn its place against
# FILM_SPEAKS_MUST_SERVE and carry a one-sentence justification.
FILM_SPEAKS_MAX_PER_FILM = 3
FILM_SPEAKS_MIN_SPACING_LINES = 15    # cannot cluster
# A film_speaks unit must serve one of these, and say which in
# `film_speaks_reason`. "It is a good line" is not one of them.
FILM_SPEAKS_MUST_SERVE = ("reveal", "climax", "thesis")

# A clip that plays longer than this gets its PICTURE split across 2-3
# contiguous sub-windows cut at real shot boundaries (render 2f). The genre's
# own floor is clips under 8 seconds; the Voz practitioners quoted in the
# research report cut at 4. A twelve-second line on one shot is twelve seconds
# of the same frame drifting under a Ken Burns zoom.
SPLIT_CLIP_SEC = 8.0

# --------------------------------------------------------------------------- #
# FROZEN / SLOW / REPEATED FOOTAGE
# --------------------------------------------------------------------------- #
# Three ways the picture stops being real footage, all previously allowed:
#
# 1. SLOW-MOTION. A bound shot was stretched up to 1.40x to cover long
#    narration. Measured by eye on the Tokyo Drift render, visible slow-mo
#    starts somewhere above ~1.15x - and because the stretch is done with
#    setpts (frame duplication, no interpolation) it reads as judder, not as a
#    slow-motion effect. 1.15 is the ceiling now, and the answer to "the
#    narration needs more picture" is MORE PICTURE: extend the window across
#    the following cuts (multi-shot), which the 2f splitter already renders as
#    real cuts.
# 2. FREEZE. tpad cloned the last frame for however long was needed, with no
#    ceiling at all - a short window under a long line became a still image.
#    A clone this brief reads as a held beat; beyond it, it reads as a bug.
# 3. REUSE. Nothing stopped two lines binding overlapping footage, so the same
#    shot could appear twice in one video.
BINDING_SLOWDOWN_MAX = 1.15
MAX_FREEZE_SEC = 0.30
# Post-render detection thresholds (pipeline/motion_check.py). The render-time
# rules above are the prevention; these measure the FINISHED file, because a
# freeze can also come from the source itself or from a filter-graph mistake.
FREEZE_FAIL_SEC = 0.50          # any frozen stretch longer than this fails
FREEZE_NOISE_DB = -62           # freezedetect sensitivity
# Two windows count as reuse when they overlap by more than this. Shot windows
# are authored by hand and routinely abut by a frame or two.
FOOTAGE_REUSE_MIN_OVERLAP_SEC = 0.40

# Background music
MUSIC_VOLUME = 0.15        # music level under the voice (0..1). History: 0.13 was judged too subtle, 0.18 too present. 0.15 from 2026-08-13.
# --------------------------------------------------------------------------- #
# MOOD BEDS (2026-10-20). One fixed bed for a whole film reads as wallpaper.
# Drop files in projects/<name>/music/{tense,neutral,action,sad}.mp3 and the
# render picks a bed per story stretch from the dominant delivery tag there.
# Missing files are NOT an error: the render falls back to music.mp3 and says
# so out loud.
# --------------------------------------------------------------------------- #
# MUSIC_MOODS removed 2026-10-21: I added it during the mood-bed work and then
# never read it - resolve_mood_beds() derives the moods it needs from the
# segments actually present, which is the better source. The distinct VALUES of
# MUSIC_MOOD_FOR_TAG below are the canonical mood names.
# --------------------------------------------------------------------------- #
# MUSIC DESIGN (2026-11): a single BED under the whole recap + CUES layered on
# top for mood, replacing the per-unit mood-bed switching. See pipeline/music.py.
#   projects/<name>/music/bed.mp3                 - the one bed, looped
#   projects/<name>/music/cues/<mood>*.mp3        - tense|sad|action|mystery
#   projects/<name>/music/cues/reveal*.mp3        - the reveal sting(s)
# --------------------------------------------------------------------------- #
# A cue fires only on a RUN of >=N consecutive lines sharing one mood (or a hold
# after a sad/reveal line), never on a single line.
MUSIC_CUE_MIN_RUN = 3
# Which delivery tags map to a cue mood. Tags not listed here (normal/intro/
# outro) never trigger a cue - they ride the bed alone.
MUSIC_CUE_MOOD_FOR_TAG = {
    "tense": "tense", "mystery": "mystery",
    "sad": "sad", "action": "action", "hook": "action",
}
MUSIC_CUE_FADE_SEC = 1.75        # fade a cue in/out (1.5-2s band, middle)
# 2026-10-27: THE CUES WERE INAUDIBLE, and the numbers say why. A cue was
# ducked to -22 dB under narration - the same depth as the BED - so the thing
# meant to mark a mood change sat at the level of the thing it was supposed to
# rise above. The bed then dipped only 6 dB while a cue played, so the cue had
# to compete with a bed that had barely moved. Net effect: a feature that
# planned, placed, rotated and faded cues, and could not be heard.
#
# A cue is an EVENT; the bed is furniture. The gap between them has to be real:
#   cue under narration   -12 dB  (-8 in action, where it is felt as much as heard)
#   bed while a cue plays -12 dB  (was -6: it has to get out of the way)
# That leaves ~10 dB between cue and bed during a cue, instead of the 16 dB the
# WRONG WAY it had before.
MUSIC_CUE_BED_DIP_DB = -12.0     # the bed dips this much WHILE a cue plays
MUSIC_CUE_DUCK_DB = -12.0        # a cue under narration - clearly above the bed
MUSIC_CUE_DUCK_ACTION_DB = -8.0  # action runs: felt as much as heard
# Inside a hold the narrator has stopped on purpose, so a cue plays at close to
# full level - this is the one moment it can carry the beat by itself.
MUSIC_CUE_HOLD_DB = -2.0
# Cue density caps: at most ~1 per this many seconds on average, and never two
# cues closer than the floor.
MUSIC_CUE_AVG_SPACING_SEC = 90.0
MUSIC_CUE_MIN_GAP_SEC = 20.0
# The bed is raised this much inside a narration-silence hold (felt, not loud).
MUSIC_BED_HOLD_DB = -6.0

# --- legacy mood-bed switching (2c) - retained for fallback / older projects -
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
# 2026-10-21: the retired switches (SFX_WHOOSH / SFX_STING / SFX_RISER and
# their _DB gains) are DELETED rather than left sitting at False. plan_events()
# no longer has a code path for any of them, so a switch left behind would
# invite someone to set SFX_WHOOSH = True and watch nothing happen - a config
# key that silently does nothing is the exact failure this file's usage check
# was written to catch, and these six were caught by it.
SFX_ENABLE = True          # master switch for sound design
SFX_BOOM = True            # low boom on a reveal line and on a hold
SFX_BOOM_DB = -12.0        # nudged down from -10 (booms were the loudest hits)

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

# --------------------------------------------------------------------------- #
# Output video - THE PICTURE-QUALITY CONTRACT
# --------------------------------------------------------------------------- #
# These are locked by pipeline/quality.py and tools/test_quality.py. Changing a
# value here without changing the expected contract there fails the test, on
# purpose: picture quality regressed silently once and nobody could say which
# setting had moved.
#
# WHAT THESE DO AND DO NOT BUY YOU
# A recap is only ever as sharp as its SOURCE. tokyodrift2006's source.mp4 is
# 1280x544 (a 2.35:1 scope transfer), so the 1080p output is a 1.50x UPSCALE to
# 1920x816 inside a padded 1920x1080 frame. No encoder setting adds detail that
# was never captured. 1080p is still the right container - YouTube gives a
# 1080p upload a better bitrate ladder than a 720p one - but do not read
# "1920x1080" as "this is a 1080p picture".
OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080
OUTPUT_FPS = 30
VIDEO_CRF = 20                  # lower = better quality / bigger file
VIDEO_PRESET = "medium"         # FINAL encode only

# A frame is encoded THREE times on its way to final.mp4: clip -> xfade concat
# -> music mix. All three used to run at CRF 20, so the two intermediates threw
# away detail that the final encode could never recover - generation loss on a
# source that is already being upscaled 1.5x. Intermediates are now near-
# transparent and only the LAST encode is sized for delivery.
VIDEO_CRF_INTERMEDIATE = 16
VIDEO_PRESET_INTERMEDIATE = "veryfast"

# swscale algorithm. ffmpeg's default is bicubic; on a 1.5x upscale lanczos
# holds edges visibly better, which is most of what "looks sharper" means here.
VIDEO_SCALER = "lanczos"
VIDEO_PIX_FMT = "yuv420p"       # 8-bit 4:2:0 - required for broad playback

# The contract pipeline/quality.py asserts on the finished file.
RENDER_QUALITY_CONTRACT = {
    "width": OUTPUT_WIDTH,
    "height": OUTPUT_HEIGHT,
    "fps": OUTPUT_FPS,
    "pix_fmt": VIDEO_PIX_FMT,
    "codec": "h264",
}
# Bitrate is deliberately NOT in the contract. Under CRF the bitrate is an
# OUTPUT that tracks scene complexity - a dark or static stretch legitimately
# encodes small - so a floor conflates "simple picture" with "broken encode".
# It false-fired on a flat test pattern at 281 kbit/s. Reported for information
# only; the format checks above are what actually catch a fallback encode.
# (Measured reference: CRF 20 at 1080p30 on tokyodrift2006 = 2.77 Mbit/s.)
RENDER_BITRATE_REFERENCE_KBPS = 2774


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



