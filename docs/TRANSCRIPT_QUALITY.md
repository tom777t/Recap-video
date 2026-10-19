# Transcript quality — the 89% that was really 34%

**2026-09-11, tokyodrift2006.**

## What happened

The first Whisper pass produced a transcript that looked healthy:

```
577 segments, 89% of runtime covered
```

It was broken. **34 segments were longer than 30s**, the worst being **569.6s
carrying one sentence** — "He's the only one to ever make it to the bottom."
stamped across 9.5 minutes and 261 cuts. Excluding those, real coverage was
**34%**.

The 89% was not a measurement. It was produced *by* the failure: a sentence
stretched over nine minutes contributes nine minutes of "coverage".

Two mechanisms:

1. **`condition_on_previous_text=True`** (the default) makes the model repeat
   itself through audio it cannot parse — the `"Uwabaki." x7` loop, and the
   giant segments.
2. **Language detected once per film.** Tokyo Drift mixes English and
   Japanese. Whisper locked to `en` and then either dropped the Japanese
   scenes or hallucinated through them. Zero CJK characters appeared anywhere,
   and the school scene produced the outright-wrong *"In Japan, you're not
   allowed to wear clothes"* (it is shoes).

## The fix

`tools/retranscribe.py`:

- **VAD first**, then one model pass per speech chunk, capped at 25s. No
  segment can exceed the cap by construction.
- **`condition_on_previous_text=False`** — the model cannot repeat itself
  across chunk boundaries.
- **Language detected per chunk**, and non-English chunks are decoded with
  `task="translate"`, keeping the speaker's timing.

`tools/fix_chunk_languages.py`: per-chunk detection has its own failure mode.
On a 0.5–1.7s clip the detector returns nonsense languages with confident
probabilities — `zh`, `hi`, `sv`, `pt`, `ko`, `ru`, `ml`, `ar` on a film that
has none of them — and then *translates from them*, producing fluent English
that reads fine and is invented. The fix computes the film's top-2 languages
**weighted by duration** and re-decodes anything outside it.

## Result

| | OLD | NEW |
|---|---|---|
| segments | 577 | 558 |
| raw coverage | 89% | 17% |
| **usable coverage** | **34%** | **17%** |
| segments > 30s | 34 (55% of runtime) | **0** |
| longest segment | **570s** | **9s** |
| repetition loops | 2 | 1 |
| total words | 3065 | **3292** |
| Japanese chunks translated | 0 | **27** |

Two things that look like regressions and are not:

- **17% < 34%.** VAD measures only **932s of actual speech = 15% of runtime**.
  The new figure is honest coverage of the speech that exists; the old 34%
  still included text hallucinated over engine noise. `raw% == usable%` is the
  tell: nothing is inflated.
- **More words in less time** (3292 vs 3065) — because the old giant segments
  spent minutes carrying a single sentence.

Japanese now comes through. Lines entirely absent before:

```
1075.3  Ah, a transfer student.                 (school)
4914.6  Your friend, huh?                       (Kamata)
4918.1  It's nothing. Don't worry.              (Kamata)
4973.9  Are you going to do this to me?         (Kamata)
```

## The gate

`tools/check_transcript.py`, wired into `run.ps1` **immediately after
whisper** — not after 70 spans have been tagged against a broken transcript.

Three checks, because the damage has three shapes:

1. >10% of runtime inside segments over 30s
2. any line repeating 3+ times in a row
3. long blind stretches **where VAD says people are speaking** — the only one
   that needs the audio, and the only way to tell a silent stretch from a lost
   one

Positive-tested both ways (`gate_selftest.py: TRANSCRIPT-QUALITY`), and
against the real broken transcript, where it fires on all three.

## Known limits

- **The loop check cannot tell a Whisper loop from real repeated dialogue.**
  The new transcript still flags `"uwabaki." x3`, which is a character
  genuinely repeating the word. A false positive, left visible rather than
  tuned away.
- **One segment is still untranslated Japanese** (`2365.7`,
  `今までのディテールについて…`). `task="translate"` returned source text for
  that chunk. 1 of 558.
- One hallucination artefact survives: `"Thank you for watching."` at 1101.8.

## PENDING — Bad Genius re-run

**`badgenius2017` has the same defect and has NOT been re-transcribed.**

```
[TRANSCRIPT-QUALITY] badgenius2017: 1472 segments, 77% raw, 51% usable
  ! 28 segments longer than 30s cover 26% of runtime
  ! 4 repetition loops
```

Milder than Tokyo Drift (26% vs 55%) but the same class. The shipped Bad
Genius draft was checked and **all 54 of its speech claims rest on normal
segments**, so that draft is not invalidated — but the catalogue and beat map
were built against a transcript with 26% of its runtime mis-timestamped.

Deferred deliberately, not forgotten. Re-run with:

```
python tools/retranscribe.py badgenius2017 --model medium
python tools/fix_chunk_languages.py badgenius2017
```
