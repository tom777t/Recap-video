# Render-craft changes (PHASE 2) - criterion and results

Scope: items 10-13 of `docs/RECAP_CRAFT_RESEARCH.md`, as amended by the user.
**Captions stay off** and **no runtime target** is introduced (both amendments).

Status: **2a-2g built and validated.** See "What is not done" at the bottom -
it is not a to-do list for later, it is the honest boundary of what has been
tested.

> **The 2a section below is superseded.** It describes a base rate of `-15%`
> chosen from the research report's unverified 121 WPM figure. That was
> reverted to **`+10%` = 186.1 WPM measured on real draft text** after
> measuring real channels' captions (Movie Recaps 236-245, TheCutFrame 205).
> See `docs/NARRATOR_VOICE.md` conflict C1 and commit `6696aed`. The section
> is kept rather than rewritten because the reasoning error it records -
> calibrating on continuous prose instead of real draft text - is the useful
> part.

## 2a TTS rate and per-tag presets

### The rate was measured, not calculated

The old base was `+22%`, which measured **198 WPM** - 64% faster than the
121 WPM of the largest channel in the genre, and 24% above the 160 WPM that two
independent production guides name as the point where comprehension starts to
suffer.

The rate-to-WPM curve was measured rather than assumed, which mattered: it is
**not linear**, so extrapolating from one data point would have been wrong.
One 87-word passage, same voice, one take per rate:

| rate | WPM | | rate | WPM |
|---|---|---|---|---|
| -30% | 132.9 | | -15% | 158.5 |
| -28% | 136.2 | | -5%  | 178.3 |
| -22% | 148.8 | | +0%  | 189.5 |
| -18% | 156.5 | | +22% | (drop) |

A 22-point rate change moves WPM by only about 5%, so "+22% = brisk" was buying
very little speed for a lot of strain.

**Base rate is now `-15%`.** Continuous prose reads faster than a real draft,
which is full of short punch sentences and the pauses they create, so -15%
(158.5 on this passage) lands mid-band on real text. `TTS_WORDS_PER_MINUTE`
fallback moved 170 -> 150; the measured voice profile remains primary.

### Every tag now has a preset, and an unknown tag is an ERROR

`_delivery_for()` used to fall back to `normal` for any tag with no preset. The
consequence, measured on shipped work: **all ten `<reveal>` lines in
tokyodrift2006 and the `<action>` line in badgenius2017 were read at exactly
the pace of an ordinary sentence.** The writer marked the biggest moments in
each film and the renderer discarded the marks, silently, while every gate
stayed green. `reveal`, `action` and `discovery` simply had no entry.

Two faults, one cause:
- missing presets for three tags
- `tense` at +26% against a +22% base - four points apart, on 52% of the
  tokyodrift lines, so "tense" had no flat ground to rise out of

Now: nine presets, spread across ~133-190 WPM, with `reveal` slower and lower
(-26%, -2Hz) and `tense` a clear 20 WPM clear of `normal`. An unknown **named**
tag raises `UnknownDelivery`; a missing or null tag is still `normal`, because
an absent choice is not a wrong one.

Caught in three places so the author hears about it early:
- `[DELIVERY-UNKNOWN]` in the draft validator (draft time)
- a pre-flight in `generate_tts` that lists every bad tag before synthesizing
  anything (fail on line 1, not on line 97 of 219 after eight minutes)
- `_delivery_for` itself

`PRE_REVEAL_PAUSE = 0.6` is defined (400-800ms band, middle) but is **not yet
wired into the render** - see "What is not done".

## 2b/2d Film audio under the narration, raised in holds and before reveals

`_build_clip` mapped `[0:v]` from the source and `[1:a]` from the narration
mp3, so **the film's own audio was discarded on every clip of every render** -
and `_build_silence_clip` used `anullsrc`, making a deliberate hold a literal
hole in the soundtrack. (The research report named render.py:349-353; that is
the silence path. The ordinary path had the same defect.)

Now the source audio is mixed under the voice:

| where | level |
|---|---|
| under narration | `FILM_AUDIO_DB` -17 dB |
| inside a `narration_silence` hold | `FILM_AUDIO_HOLD_DB` -6 dB |
| ramping over the 1.5s before a `<reveal>` | `FILM_AUDIO_PRE_REVEAL_DB` -8 dB |

Two things track the picture: when footage is slowed, the audio is stretched by
the same ratio with `atempo` (bounded by `BINDING_SLOWDOWN_MAX` 1.4, so 0.714 -
inside atempo's legal range); and the pre-reveal raise is a dB ramp over the
clip tail.

A source with no audio stream is detected once with ffprobe and reported, and
the render falls back to narration-only rather than referencing a stream that
does not exist.

### Verified, and the first measurement was invalid

The first A/B compared the finished `final.mp4` with film audio on and off and
found the hold window **louder with film audio OFF** (-17.9 dB vs -22.4 dB).
That comparison is worthless: `loudnorm` normalises the whole file, so adding
film audio makes it attenuate everything else. Absolute dB after loudnorm
cannot isolate this.

The valid measurement is the **hold clip before mixing** - narration-free by
construction, no music, no loudnorm:

| clip | mean dB | max dB | |
|---|---|---|---|
| clip_004 (the hold) | **-34.7** | **-10.9** | was `anullsrc`, i.e. digital silence |

Real content where there was none. That is the claim, and that is the test.

### A clipping defect this found

`amix` with `normalize=0` sums, so voice near full scale plus film audio raised
to -8 dB exceeded 1.0: the pre-reveal clip measured **max_volume 0.0 dB** -
samples pinned at full scale, distortion baked into the clip file where the
later loudnorm cannot undo it. An `alimiter` at -1 dBFS fixed it (max now
-0.8 dB).

## 2c Music by mood

`projects/<name>/music/{tense,neutral,action,sad}.(mp3|m4a|wav|ogg)`. The
timeline is split into stretches by the dominant `delivery` tag
(`MUSIC_MOOD_FOR_TAG`), stretches shorter than `MUSIC_MOOD_MIN_SEC` (25s) are
absorbed into their neighbour, and one continuous bed is built as a **file**
rather than as a branch of the final filter graph - a pre-built bed can be
played and checked on its own.

- duck `MUSIC_DUCK_DB` -22 dB under the voice, `MUSIC_DUCK_ACTION_DB` -10 dB in
  action (baked per-mood into the bed, so the final mix stays one expression)
- the bed dips to `MUSIC_PRE_REVEAL_LEVEL` 0.02 for 1.5s either side of every
  reveal, so the line lands into a hole
- **missing mood files are not an error**: the render falls back to the single
  `music.mp3` and says which moods were missing and where it looked

A half-populated `music/` directory must never produce a render where some
stretches have a bed and others are silent, so the fallback is all-or-nothing.

### Validated, including the path that failed first

The first bed build **failed and left a truncated 2 MB wav**: every segment was
an infinite `-stream_loop -1` input and `concat` sat waiting on the ones it had
not reached. Bounding each input with `-t` before `-i` fixed it.

| case | result |
|---|---|
| no `music/` dir | falls back to `music.mp3`, names the missing moods, exit 0 |
| all four moods present, 1 stretch | bed built, exit 0 |
| all four moods, **5 stretches** (min_sec lowered to force it) | `action 0.3min, neutral 0.5min, tense ...`, exit 0 |

The multi-segment case is the one that had failed, so it is the one that had to
be exercised deliberately.

## 2e SFX on reveals and holds only

`plan_events` used to emit a transition whoosh before **every** clip (~190 on a
190-line draft), a sting on the intro and a riser on every mystery beat - which
is why SFX had been switched off wholesale rather than aimed. "Use these in
moderation" is the one point every sound-design source agrees on, and a whoosh
on every cut is the most recognisable mark of a cheap recap.

Now: a low boom on a `<reveal>` line and a boom on a hold. Nothing else.
`SFX_ENABLE` back to `True`; `SFX_WHOOSH`, `SFX_STING`, `SFX_RISER` retired.

**The restriction lives in `plan_events`, where the events are decided.** The
first version filtered downstream in render.py on `ev["line_id"]` - and these
dicts never carried a line_id, so it silently dropped every event while
printing a confident count. Every event now carries its line id and a `why`.

Measured on the fixture (1 reveal, 1 hold): `1 on holds, 1 on reveals (no
whoosh on ordinary cuts)`.

## How this was tested

A six-line fixture on badgenius2017_machine's source, hardlinked so no 1 GB
copy was made, deliberately containing a normal line, a pre-reveal line, a
`<reveal>`, a `narration_silence` hold, an `<action>` line and an `<outro>`.
Full renders, exit 0, `RENDER-CHECK` position drift <= 0.01s.

Building it exposed an inconsistency worth keeping: `[HOOK]` and
`[LOOP-CADENCE]` were not size-gated like the rhythm statistics, so any small
labelled fixture was hard-failed for having no hook. Both now route through the
same `MIN_LINES_FOR_STATS` guard - otherwise a new gate stops the gates under
test from running, which is the `[TITLE-MATCH]` lesson again.

`gate_selftest.py` 23/23 exit 0. `check_craft.py --selftest` passes.

## 2f Splitting a long line's picture across 2-3 shots

Built, commit `e0ab747`. A clip playing longer than `SPLIT_CLIP_SEC` (8s) shows
its picture across 2-3 contiguous sub-windows of its own window, cut **only at
real cuts from `_cuts.json`**. With no cut list the line stays on one shot and
the render says so - a missing cut is a reason not to split, not a licence to
jump-cut inside a continuous take.

Implemented inside `_build_clip`, not by routing through
`_build_montage_clip`: that builder predates the film-audio work, so reusing
it would have silently dropped the -17 dB film bed.

A defect the verification caught: the first version gave each sub-shot screen
time *proportional to its source length*, to protect audio sync. There was no
sync to protect - the audio is read from `start` for the whole clip - and the
rule handed one sub-shot 1.4s of an 8.8s clip. Equal shares now. Scene
detection: 7.4s clip 0 cuts, 8.8s clip a cut at exactly 4.4s, 5.6s clip 0 cuts.

## PRE_REVEAL_PAUSE

Wired, commit `1fc2ec6`. A `<reveal>` gets 0.6s of extra front silence, added
inside `_lead_for` **before** its clamp so it cannot cause a BindingViolation.
Sweep of 2204 (narration, shot) combinations: the pause newly breaks zero.
End to end, identical narration text: `<normal>` 4.6s clip, `<reveal>` 5.2s.

## 2g Music intro montage

Built and tested on **tokyodrift2006**. `pipeline/intro.py` +
`tools/make_intro.py`, output `intro_preview.mp4` - the intro and hook only,
about 30s, not the film.

- **Beats** from a spectral-flux onset envelope, peak-picked against a *local*
  median rather than a global threshold, because music that gets louder would
  otherwise put every detected beat in its loud half. 59 beats in the first
  40s, median interval 0.65s.
- **The drop** is the largest (mean energy of the next 2s) minus (mean of the
  previous 2s) - sustained level, not a transient, because a drum hit is a
  beat and a drop is where the track changes gear and stays there. Found at
  4.40s, and confirmed against the raw envelope: the track sits at ~0.13 RMS
  for four seconds, jumps to ~0.44 at 4.5s and holds.
- **The hook enters on the drop** with the music ducked to `MUSIC_DUCK_DB`.
  The hook line is read from `draft.json` at build time, never baked in - the
  draft gets rewritten and the montage has to follow it.
- **`[INTRO-MONTAGE]`** fails if any chosen clip touches the first reveal's
  land. A montage is the most spoiler-prone part of a recap: it picks frames
  for being striking, and the most striking frames in any film are after the
  twist. Moments are chosen *spread evenly* across the allowed range rather
  than by any notion of "best", because there is no measure of best here and
  choosing by eye is exactly what puts the twist in the montage.
- **Missing `intro_music.*` prints a notice and skips.** Not an error.

Verified on the real output rather than the log: duration 13.70s, 1920x1080,
**20 picture cuts** landing on the detected beats (0.57 / 1.53 / 2.27 / 2.83 /
3.43 / 4.40 against beats at 0.58 / 1.533 / 2.252 / 2.81 / 3.413 / 4.389),
latest clip used 3956s against a land of 4049s. The duck is confirmed
indirectly but soundly: the raw track *triples* in level at its own drop, so
if the music were still at full the output would be far louder after 4.4s than
before - measured, it is quieter.

Gate self-tested on five boundary cases including a clip starting exactly *at*
the land (rejected) and one ending exactly at it (allowed), plus the skip path.

## What is not done

Stated plainly rather than left to be discovered:

- **Nobody has watched the intro preview.** Beat alignment is asserted from
  scene-change timestamps matching onset timestamps, which is evidence that
  the cuts are *where the beats are*, not that it looks good.
- **No full-length render has been produced or watched.** Everything above is a
  six-line fixture and per-clip measurements. The claim "this sounds better"
  is not supported by anything here; the claims that ARE supported are that
  film audio is present where there was silence, that each tag now gets a
  different rate, that the bed changes with mood, and that SFX fire only on
  reveals and holds.
- **The 140-160 WPM target has not been confirmed on real draft text.** The
  -15% figure rests on one continuous passage. A real draft's short sentences
  add pauses and will read slower; the number to check is the measured WPM of a
  full narration pass.
