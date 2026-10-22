# Render-craft changes (PHASE 2) - criterion and results

Scope: items 10-13 of `docs/RECAP_CRAFT_RESEARCH.md`, as amended by the user.
**Captions stay off** and **no runtime target** is introduced (both amendments).

Status at time of writing: **2a-2e built and validated. 2f and 2g NOT built.**
See "What is not done" at the bottom - it is not a to-do list for later, it is
the honest boundary of what has been tested.

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

## What is not done

Stated plainly rather than left to be discovered:

- **2f - splitting narration lines longer than ~8s across 2-3 clips.** Not
  built. This is a structural change to the clip loop, not a parameter.
- **2g - the music intro edit** (beat-cut montage from `intro_music.mp3`, using
  only moments before the first reveal's land, with a gate for that). Not
  built. It has never existed.
- **`PRE_REVEAL_PAUSE`** is defined in config and read by nothing.
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
