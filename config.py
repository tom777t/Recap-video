

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
# THE WRITER'S FALLBACK RATE. Used only when the production voice has never
# been calibrated - a measured profile (config/voice_profiles.json) always wins.
# It must track TARGET_WPM, because TARGET_WPM is what the writing is built for.
#
# MEASURED 186.3 WPM on 23 real draft lines with the live per-tag mapping
# (+0.7% of the 185 target), every tag inside +-4.7%, tag spread 1.10x.
#
# THE HISTORY MATTERS, because the mistake was mine and it was a direction, not
# a number. Flattening the delivery mapping for voice consistency gave every
# tag a steering cue; a cue costs ~20-27% of pace; Warren fell to 134.6 WPM.
# I then re-calibrated this constant DOWN to 141 to match - which "fixed" the
# overruns by shrinking every line's word budget by a third to accommodate a
# regression in the voice. The target is a decision about the writing; the
# VOICE is what gets adjusted to meet it. [VOICE-RATE-DRIFT] now fails if this
# relationship inverts again.
# Tracks TARGET_WPM (210). Re-measured aggregate at the live mapping below.
TTS_WORDS_PER_MINUTE = 210

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
# THE PACE THE WRITING IS BUILT FOR. Not a measurement - a decision, taken
# against a reference channel's delivery. Every word budget in the pipeline
# assumes it, so the VOICE has to be made to hit it rather than the budget
# being re-cut to match whatever the voice happens to do.
#
# That inversion already happened once: flattening the delivery mapping for
# voice consistency gave every tag a steering cue, a cue costs ~20% of pace,
# Warren fell to 140.6 WPM, and the budget was re-calibrated DOWN to 141 -
# shrinking every line's word allowance by a third to accommodate a regression.
# [VOICE-RATE-DRIFT] now fails on exactly that.
#
# 210, raised from 185 after watching a finished recap. The 185 was taken from
# a VIETNAMESE reference channel, and Vietnamese carries more meaning per
# syllable than English does at the same tempo - so the number was transplanted
# across a language boundary where it does not hold, and the English result
# sounds slow. Measured English recap channels run 205-245 WPM. 210 sits at the
# bottom of that band, which is the right end to pick: it is the smallest
# change that leaves the reference range, so it does not trade one guess for a
# larger one.
TARGET_WPM = 210.0
# How far the MEASURED base rate may sit from TARGET_WPM before the gate fails.
VOICE_RATE_DRIFT_MAX = 0.10

# The one speaking_rate every tag shares. Raised from 1.02 to compensate for
# the pace a steering cue costs, so the voice MEASURES near TARGET_WPM while
# keeping the uniform mapping that made it one narrator.
# Solved by measurement, not arithmetic - see tools/calibrate_rate.py.
VOICE_BASE_SPEAKING_RATE = 1.393
# Inworld rejects speakingRate outside [0.5, 1.5] with an HTTP 400. Measured,
# not assumed - a code comment claimed 1.5 and that happened to be right, but
# nothing had tested it.
VOICE_SPEAKING_RATE_MAX = 1.5
# PER-TAG COMPENSATION, solved by measurement (tools/calibrate_rate.py
# --solve-per-tag). These differ ONLY to cancel each cue's measured pace cost,
# so the DELIVERED rate is uniform. That is the inverse of the original defect,
# where rates differed in order to make tags sound like different speeds.
# A tag absent here falls back to VOICE_BASE_SPEAKING_RATE.
# SOLVED BY MEASUREMENT against TARGET_WPM = 210 (tools/calibrate_rate.py
# --solve-per-tag, 16 real draft lines across 9 tags, 517 words). Delivered:
#     action 209.7  hook 211.1  intro 211.5  normal 206.5  outro 212.3
#     sad 206.1  tense 207.5      mystery 195.2 (-7.0%)  reveal 196.7 (-6.3%)
# Spread 1.088x, every tag inside VOICE_RATE_DRIFT_MAX.
#
# mystery and reveal sit ON Inworld's hard 1.5 speakingRate ceiling and are the
# only two that miss. Two wrong explanations were tested and killed first:
#
#  1. "their cue is too expensive, shorten it". Measured the opposite -
#     shortening reveal to "[strong emphasis]" and mystery to
#     "[close emphasis]" made them SLOWER (mystery 195.2 -> 178.7, reveal
#     196.7 -> 193.0). A cue's pace cost is about what it ASKS FOR, not how
#     long it is: "close"/"strong" emphasis instructs a more deliberate read.
#  2. "the cue is the cause at all". At a uniform 1.5 with mystery's cue
#     swapped for normal's own "[even phrasing]", mystery still read 184.3 WPM
#     where the SAME cue gives normal 219.0. Same cue, same rate, 35 WPM apart
#     - so the difference is the TEXT of those lines, not the direction.
#     Confirmed on articulation (silence excluded), which shows the same gap:
#     mystery 250.7 and reveal 252.3 against normal 284.2 and action 284.0.
#
# So the shortfall is a property of how those particular lines read, it is
# bounded, measured, and inside the band - not something to fix by pushing a
# rate past an engine limit or by re-cutting the target.
VOICE_TAG_SPEAKING_RATE: dict = {
    "action": 1.447,
    "hook": 1.274,
    "intro": 1.485,
    "mystery": 1.5,
    "normal": 1.46,
    "outro": 1.238,
    "reveal": 1.5,
    "sad": 1.403,
    "tense": 1.478
}
VOICE_DELIVERY_MODE = "BALANCED"     # one mode for every tag; never CREATIVE
# Tag rate x rate_bump must stay inside +-this fraction of the base rate. A
# per-line rate_bump from tools/fit_narration.py counts against the SAME band -
# fitting a line to its window may not be an exemption from sounding like the
# same person.
VOICE_RATE_BAND = 0.10
# Measured on the real audio, neighbour to neighbour. A mood change ramps
# across intervening lines rather than stepping.
# CALIBRATED ON A CONTROL (tools/calibrate_voice_spread.py): varied real draft
# lines synthesized with ONE identical delivery, so the only thing varying is
# the words. Whatever spread the voice produces there is the FLOOR for any
# ceiling - a bar below it fails a narrator behaving perfectly, which is what
# a hand-picked 1.25x did on a render whose base rate was dead on target.
# Measured values and the margin live in config/voice_spread_control.json.
VOICE_LINE_SPREAD_MAX = 1.58
VOICE_ROLL3_SPREAD_MAX = 1.38
VOICE_ADJACENT_MAX_JUMP = 0.35
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
# Crossfade length, expressed in FRAMES and converted, because it has to land
# on a frame boundary.
#
# This was 0.28 seconds. At 30 fps that is 8.4 frames - not a whole number, so
# every crossfade boundary fell in the middle of a frame. Nothing complained,
# because the old pipeline re-encoded the entire timeline through an `xfade`
# filtergraph and the filter simply resampled around it.
#
# It matters now. Phase 1 stream-copies each clip body and a stream copy can
# only cut on a frame, so a boundary at 8.4 frames cannot be hit exactly: the
# first copy-cut came out 0.080s long, and at 110 junctions that is nearly nine
# seconds of accumulated drift between picture and sound. Found by the
# assembler's own duration assertion on the first run, not by reading.
#
# 8 frames is the whole number nearest the original 0.28s (0.267s vs the 0.300s
# of 9 frames).
#
# The 30.0 below is OUTPUT_FPS, which is defined further down this file and so
# cannot be referenced here. Rather than duplicate the number silently - the
# "one job, two places" failure the Stage 2 plan opens with - there is an
# assertion next to OUTPUT_FPS that fails loudly if the two ever disagree.
XFADE_FRAMES = 8
XFADE_DURATION = XFADE_FRAMES / 30.0   # = 0.26667s at 30 fps
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

# WHERE the film's own track is allowed to play at all.
#
# It used to be everywhere: `has_film_audio` was ONE boolean for the whole
# render - if the source had an audio stream, every single clip got the
# no-vocals stem underneath it. Separation is not transparent, and spread
# across all 111 lines its artefacts are audible as a constant bed of
# processed-sounding noise. The engines and impacts are worth that cost; a
# dialogue scene with the voices stripped out is not - it is a smeared room
# tone under the narrator for no benefit.
#
# So the stem plays only where the film's own sound IS the content: races,
# fights, chases. That is what the action and tense tags mark.
FILM_AUDIO_TAGS: tuple = ("action", "tense")
# ...and only in a RUN of them. An isolated action line inside calm narration
# is a single cut, not a sequence; switching the film's track on for one clip
# and off again is more noticeable than leaving it off. On this draft: 48
# action/tense lines in 18 runs, of which 8 are isolated singles, so a minimum
# of 2 admits the 10 real sequences and drops the 8 one-offs.
FILM_AUDIO_MIN_RUN = 2
# A <film_speaks> unit is NOT subject to either rule. It hands the moment to
# the film deliberately and uses the ORIGINAL mix (dialogue included), which is
# the one place un-separated audio is used. See FILM_SPEAKS_DB.

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
# WHAT THE MUSIC DOES while the film is speaking.
#
# THE DEFECT: both units were INAUDIBLE - only music was heard. A film_speaks
# unit carries no narration, so it was recorded as a silence window like any
# other hold, and a hold SWELLS the music: SILENCE_MUSIC_VOLUME raises the bed
# to 0.30 (double the 0.15 it sits at under narration) and MUSIC_CUE_HOLD_DB
# puts any cue in that window at -2 dB, near full level. So the one moment the
# film is deliberately given the floor was also the loudest the music ever
# gets, and FILM_SPEAKS_DB = 0.0 was "full level" against a doubled bed.
#
# A hold and a film_speaks unit want OPPOSITE things from the music, and
# treating them as the same kind of event is the whole bug.
FILM_SPEAKS_MUSIC_DB = -20.0     # bed AND cues duck this far under the film
FILM_SPEAKS_MUSIC_FADE_SEC = 0.75   # ...faded, so the moment is not cut out
# Not muted. A hard zero reads as a dropout - as if the audio broke - and the
# scene stops feeling like part of the film. -20 dB is present but out of the
# way of dialogue.
FILM_SPEAKS_MIN_SEC = 3.0   # under this nobody registers an exchange
FILM_SPEAKS_MAX_SEC = 15.0  # over this it stops being a recap
# 2026-10-27: 5 -> 3. This is now the ONLY place the film's own dialogue is
# heard (everywhere else uses the no-vocals stem), which makes each one a
# deliberate editorial event rather than one of many. Fewer original lines is
# also less copyright exposure. Each surviving unit must earn its place against
# FILM_SPEAKS_MUST_SERVE and carry a one-sentence justification.
FILM_SPEAKS_MAX_PER_FILM = 3
FILM_SPEAKS_MIN_PER_FILM = 2          # zero is an ERROR when candidates exist
FILM_SPEAKS_MIN_SPACING_LINES = 15    # cannot cluster
# Minimum SECONDS between two units. The line-count spacing above is a proxy
# that breaks when lines are short; this is the real constraint - two
# hand-overs inside three minutes read as a compilation, not as two events.
FILM_SPEAKS_MIN_GAP_SEC = 180.0
# At most one per act. Acts are the beat map split into RECAP_ACTS equal
# groups, the same division tools/act_payload.py uses.
FILM_SPEAKS_MAX_PER_ACT = 1
# A film_speaks unit must serve one of these, and say which in
# `film_speaks_criterion`, with a sentence of justification in
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
# Headroom between a line's audio and its capacity ceiling. ONE definition,
# used by BOTH the writer's word budget (calibration.max_words_for_capacity)
# and the fitter (tools/fit_narration.py). They used to carry separate numbers,
# so the writer sized a line to land exactly on the ceiling and the fitter then
# refused it for having no headroom - the writer was being told a number the
# render would not honour.
CAPACITY_MARGIN_MIN_SEC = 0.25
CAPACITY_MARGIN_FRACTION = 0.03
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
# --------------------------------------------------------------------------- #
# TONE TAG BUDGET
# --------------------------------------------------------------------------- #
# A tag drives two things: how the narrator reads the line, and which mood cue
# plays under it. So a wrong tag is heard twice.
#
# The Tokyo Drift draft had 19 of 109 lines tagged `sad` (17.4%) - a car crash,
# a gun standoff, and a character fetching a bag of money among them. Each got
# a mournful read AND sad music, which reads as unintentionally comic. Mean-
# while `action` and `mystery` were completely unused, so kinetics were filed
# under `tense` and withheld information under `sad`.
#
# `sad` means real loss or grief - a death, a bereavement, heartbreak - and
# nothing else. A setback, a defeat, a humiliation or a sombre mood is not sad.
# At 5% of lines it stays an event; at 17% it is the house style.
# --------------------------------------------------------------------------- #
# CENSOR CRITERIA - what gets blurred, and how much of the frame
# --------------------------------------------------------------------------- #
# tokyodrift2006 had 14 shots flagged for blur. A visual re-check of every one
# (frames read, not inferred from the catalogue text) kept FOUR and dropped
# TEN: the drops were a bathhouse with men in towels, a clothed couple kissing,
# party guests in cocktail dresses, women pouring champagne, and a beaten
# driver with no visible blood. Ten of fourteen flags were destroying footage
# for nothing.
#
# Flag a shot ONLY for:
#   * BLOOD or GORE  - visible blood, a wound, a body shown graphically
#   * NUDITY         - exposed genitals, breasts or buttocks
# NOT for: crashes, ordinary violence (punches, beatings, a gun held on
# someone, a bruised face with no blood), clothed kissing, revealing clothing,
# tattoos, bathhouses, or anything merely "adult in tone".
CENSOR_CRITERIA = ("blood/gore", "nudity")
# A censor flag must carry a region. Blurring the whole frame to hide a corner
# of it throws away the shot, and every one of this film's 14 flags had NO
# region - so all 14 would have been full-frame blurs.
CENSOR_REQUIRE_REGION = True
# With no region, prefer SWAPPING to a different shot over blurring everything.
# A full-frame blur is never the right answer: it is indistinguishable from
# losing the shot, while still costing the runtime.
CENSOR_ALLOW_FULL_FRAME = False
# A region bigger than this fraction of the frame is not a region, it is a
# full-frame blur with extra steps - report it as such.
CENSOR_REGION_MAX_FRACTION = 0.40

TONE_SAD_MAX_FRACTION = 0.05
# Tags that may appear in a draft at all. An unknown tag used to resolve to
# whatever the provider happened to map, or raise mid-render.
TONE_VALID = ("normal", "tense", "action", "reveal", "sad", "mystery",
              "hook", "intro", "outro")
# Tags that are structural - exactly one or a known few per film - so a drift
# in their count means something is wrong with the draft's shape.
TONE_SINGLETON = ("hook", "outro")

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
# LOUDNESS-NORMALISE EVERY MUSIC FILE BEFORE ANY GAIN IS APPLIED.
#
# THE DEFECT: the cues were not audible, and the gains were not the problem -
# they were real and in the filtergraph. Measured integrated loudness of this
# project's own music:
#     action1  -3.5 LUFS      mystery1  -9.6      tense1  -11.2
#     reveal1 -12.4           sad1     -12.5      bed     -11.1
# a 9.0 dB spread across the cue files alone. A "+10 dB relative to the bed"
# gain therefore means something different for every cue: reveal1 starts 1.3 dB
# QUIETER than the bed, action1 starts 7.6 dB LOUDER. The gain differences the
# mix is built on (-12 vs -8 vs -2) are smaller than the variation in the
# material they are applied to, so the intended relationships never survived.
#
# Normalising to a common loudness first is what makes a gain mean something.
# -23 LUFS is the EBU R128 broadcast reference and leaves plenty of headroom
# before the limiter. Applied as a STATIC gain from a measured integrated
# reading - not two-pass dynamic loudnorm, which would compress the music and
# flatten exactly the dynamics a cue relies on to feel like an event.
# Cached per file (size+mtime+target), because measuring is a second per file
# and the answer never changes for a file that has not changed.
MUSIC_NORMALIZE_LUFS = -23.0
MUSIC_NORMALIZE = True
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

# XFADE_DURATION is computed near the top of this file from XFADE_FRAMES and a
# literal 30.0, because OUTPUT_FPS is not defined yet up there. If the output
# rate changes, the crossfade stops landing on a frame boundary and the
# stream-copy assembly silently drifts - so this is an assertion, not a note.
assert abs(XFADE_DURATION - XFADE_FRAMES / float(OUTPUT_FPS)) < 1e-9, (
    f"XFADE_DURATION ({XFADE_DURATION}) was computed at 30 fps but OUTPUT_FPS "
    f"is {OUTPUT_FPS}. The crossfade must be a whole number of frames or "
    f"pipeline/assemble.py cannot copy-cut exactly. Recompute it as "
    f"XFADE_FRAMES / OUTPUT_FPS.")
VIDEO_CRF = 20                  # lower = better quality / bigger file
VIDEO_PRESET = "medium"         # FINAL encode only

# HISTORICAL, and now almost unused. A frame used to be encoded THREE times on
# its way to final.mp4 (clip -> xfade concat -> music mix) - and in fact FOUR,
# because _xfade_chain batches at 12 and then joins the batches, which this
# comment never accounted for. Measured on tokyodrift2006: 115 min for a first
# render, 56 min to re-render after editing three lines, with every clip
# already cached.
#
# Phase 1 removes those passes. Each clip is now encoded ONCE at delivery
# quality, only the 0.28s crossfades are encoded separately, and the pieces are
# joined by stream copy. These two settings therefore no longer describe the
# main path; they remain for the few places that still build a throwaway
# intermediate (the intro-join fallback, calibration scratch files).
VIDEO_CRF_INTERMEDIATE = 16
VIDEO_PRESET_INTERMEDIATE = "veryfast"

# 540p draft mode was specified for Phase 1 and has been DROPPED. It only paid
# off if someone reviewed a cheap preview before the real render, and nobody
# does - the viewer watches the final render and nothing else, so a second
# render at lower quality is pure added cost and a second timing path to keep
# in step. See docs/stage2/STAGE2_PLAN.md.

# FALLBACK TO THE OLD RENDER PATH.
# Phase 1 replaced four full-length re-encodes with a stream-copy assembly.
# Its correctness is established by frame counts, duration assertions and the
# ten final-file checks - but NOBODY HAS WATCHED A RENDER FROM IT YET. If the
# first viewing shows something the numbers could not see (a dissolve that
# looks wrong, a stutter at a junction), set this to True to get the previous
# behaviour back in one edit, without reverting a merge.
#
# True  = _xfade_chain: re-encode the whole timeline through an xfade
#         filtergraph, then re-encode again in the music mix. Slow and proven.
# False = pipeline.assemble: encode each clip once, copy the bodies, encode
#         only the crossfades. Fast and newer.
RENDER_LEGACY_XFADE = False

# Parallel clip builds and parallel TTS are the next Phase 1 item and are NOT
# implemented. CLIP_WORKERS and TTS_WORKERS used to sit here unused, and
# tools/check_config_usage.py was right to fail on them: a config key that
# nothing reads is a claim the code does not honour, and the next person
# cannot tell "tunable" from "dead". They go back in with the code that
# reads them, not before.

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


# --------------------------------------------------------------------------- #
# PACING CONTOUR (dwell). Calibrated on references/voice/*.vtt - the full
# derivation, including why each bar is this number and which of the measured
# statistics are NOT usable, is in docs/stage2/PACING_CALIBRATION.md and the
# raw measurements are in config/pacing_control.json.
#
# THE DEFECT: the Tokyo Drift draft gave 56 of ~80 beats exactly one line and
# spent 1.0-1.6 narration-minutes on every 10 film-minutes throughout - a flat
# contour. The scenes viewers singled out are exactly the ones that got 3-4
# lines. The references do not do this: they concentrate 42-50% of their
# runtime in their top 20% of scenes.
#
# BASIS WARNING, because it changes the numbers more than anything else does.
# Measured on the SAME draft: top-20% runtime share is 0.310 by real beats and
# 0.412 by the reference's own cue-segmentation. The gate measures BEATS,
# because that is what the writer controls, and the bars below are converted
# from the reference basis by the 0.75 factor measured on our own draft. Do not
# compare a beat-basis number to a reference-basis one.
# --------------------------------------------------------------------------- #
PACING_ANCHORS_MIN = 5
PACING_ANCHORS_MAX = 8
# An anchor that gets one line is not an anchor. The scenes viewers singled out
# (Han on the footbridge, the Neela beats) carry 3-4 lines.
PACING_ANCHOR_MIN_LINES = 3
# Share of narration lines that must sit in the top 20% of beats. References
# score 0.430-0.506 on their own basis; x0.75 gives a reference-equivalent
# floor near 0.36, so 0.40 is slightly stricter than the references and is
# reachable - the intended shape computes to 0.465. The shipped draft: 0.324.
PACING_TOP20_LINE_SHARE_MIN = 0.40
# Longest run of consecutive beats that each get exactly ONE narration line.
# English references max at 3 on a basis that destroys one-line scenes, so
# their true figure is higher. The shipped draft runs 9.
PACING_ONE_LINE_RUN_MAX = 4
# A beat with no narration (footage or hold) BREAKS a one-line run rather than
# extending it: a deliberate pause is a change of rhythm, which is the opposite
# of the monotony being measured.
#
# An anchor must also be slower than the film average: compression is
# film-seconds covered per narration-second, and an anchor should dwell.
PACING_ANCHOR_MAX_COMPRESSION_RATIO = 0.70   # of the draft's own mean

# --------------------------------------------------------------------------- #
# NARRATOR PERSONA. angle.md's ATTITUDE section says what the narrator thinks;
# it never said how the narrator SOUNDS, so the draft came back with 14 of 109
# lines carrying any judgment at all and no recognisable voice.
#
# Reference aside-rates, measured in references/voice/_measured.json: the
# English channels average 177 "asides" (first/second person, stance adverbs,
# questions to the viewer) over 25.8 minutes on cutframe - about 7 per minute
# of narration. We are not chasing that density; we are refusing zero.
# --------------------------------------------------------------------------- #
# Share of narrated lines carrying payload == "judgment". Measured on the
# draft's OWN label, which is where the 14/109 figure in the brief comes from
# (14 of 106 narrated = 13.2%). A first version of this gate scored judgment
# with a text detector and reported 42.5% on the same draft - it matched
# "only", "still", "never" and any "you", which appear throughout ordinary
# descriptive prose. It PASSED a draft the viewer said had no voice, which is
# the worst kind of gate. Use the label the writer commits to.
# Measured on the shipped draft: the writer labelled 14 lines judgment, the
# independent classifier found 44, and the two AGREED on 11 (10.4% of 106).
# The gate counts the agreement, which is conservative because the two signals
# fail in opposite directions - the label can be asserted, the classifier
# over-fires on unquoted reported speech.
PERSONA_JUDGMENT_SHARE_MIN = 0.22
# ...and the agreement RATE among labelled lines is what collapses if the
# label is inflated. Shipped draft: 11/14 = 78.6%, so an honest-but-thin draft
# fails on the SHARE above and not on this. A writer who tags 40 lines
# judgment to clear the share would drop this to ~30% and fail here instead.
PERSONA_JUDGMENT_AGREEMENT_MIN = 0.60
#
# A DECISION, NOT A MEASUREMENT - and the references say so. Persona-move rate
# (direct address, first person, questions to the viewer, stance adverbs)
# measured across the five English reference files: 0.4%, 1.2%, 2.1%, 3.1%,
# 37.1%. A 90x spread means the genre has no shared persona rate: Movie Recaps
# is almost impersonal, cutframe is chatty. So this floor is the style asked
# for in the brief, grounded in angle.md's persona card, and it is NOT claimed
# to be calibrated. Recorded honestly because the alternative is dressing a
# preference up as evidence.
PERSONA_WINDOW_SEC = 120.0            # the persona must be audible every 2 min
PERSONA_MIN_PER_WINDOW = 1
# Lines that only report what is already on screen. RE-CALIBRATED after the
# judgment classifier was corrected, because the same correction changes this
# measure: a line the classifier now recognises as evaluation is no longer
# frame-only. Measured with the corrected classifier, the English references
# run 5.9%, 7.0%, 8.4%, 11.5%, 11.5% (median 8.4%, max 11.5%); the shipped
# draft is 14.2%, still above every reference. The cap sits just above the
# reference maximum.
#
# The earlier figures (7.1-13.1%, cap 0.15) were taken with the broken
# classifier and are superseded - a bar calibrated with a faulty instrument is
# not a calibration.
PERSONA_FRAME_ONLY_SHARE_MAX = 0.13



