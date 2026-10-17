# Automatic clip windows - failure criterion

**Written 2026-09-07, BEFORE any machine windows were generated or scored.**
Pinned so that I cannot quietly become right. If the rule fails this bar I
report the failure; I do not lower the bar.

---

## What is being built

`tools/make_windows.py <project>` - groups consecutive cuts from `_cuts.json`
into catalogue *moments*, writes `projects/<p>/windows.json`.

**Permitted inputs: `_cuts.json`, `transcript.json`. Nothing else.**
Specifically forbidden: `shots.json` (the answer key), `beats_proposal.md`
(written after the catalogue in the real flow), `draft.json`, `timeline.json`.
Enforced in code, and tested in `gate_selftest.py`.

## Why grouping and not detection

Detection is solved - `_cuts.json` already has every camera cut. The gap is
that a catalogue window is a *moment made of several cuts*:

| film | median camera shot | median human window | interior cuts / window |
|---|---|---|---|
| badgenius2017 | 3.00s | 10.0s | median 2 |
| howtomakemillions2024 | 8.04s | 22.2s | median 2 |

## Disclosed prior

I looked at human window statistics (above) **before** designing the rule.
I am not going to pretend otherwise. Two things follow:

1. The figure "a moment is about 3 camera shots" is now known to me. It is
   also what conventional coverage predicts (action / reaction / re-establish),
   so it is not purely answer-key knowledge - but I saw it in the answer key
   first, and that is disclosed.
2. Therefore the rule **must not hardcode a target window duration or a target
   shot count.** Every parameter must be derived from that film's own cut and
   speech distributions. If the output lands near 3 shots per moment without
   being told to, that is a result. If I have to tell it to, it is fitting.

## Signal reality check (machine inputs only)

| film | speech % of runtime | silences > 1s | human windows |
|---|---|---|---|
| badgenius2017 | 77% | 192 | 231 |
| howtomakemillions2024 | 94% | **39** | 280 |

The brief suggests silence marks where a moment ends. That holds on badgenius
(192 silences, 231 windows) and **collapses on howtomakemillions** (39
silences, 280 windows). A silence-threshold rule would pass one film and fail
the other by construction. Noted before building, not after.

## The measurement

For each **human** window, take the best-overlapping machine window:

```
IoU = |H n M| / |H u M|
```

Reported per film, **never averaged across films**:

1. share of human windows with best IoU >= 0.5
2. median |start distance| and median |end distance|
3. human windows with **zero** overlapping machine window, listed by id -
   these are the moments a draft could not bind to

## Pass / fail - fixed now

| | bar |
|---|---|
| **PASS** | IoU >= 0.5 share **>= 0.60 on BOTH films** |
| **HARD FAIL** | any film with **> 5%** of human windows uncovered |
| **STYLE-TUNING FAIL** | `|share_A - share_B| > 0.15` |

Reasoning for 0.60, set from the downstream requirement and not from a pilot
run: a draft line is written for a window and must land on that footage. At
IoU 0.5 the machine window is substantially the same moment. Below a 0.60
share, more than one human moment in three is grouped differently and the
result is a *different catalogue*, not a reconstruction of this one.

The style-tuning clause exists because averaging two films would let a 0.85 /
0.35 split read as 0.60. A rule that only works on one cutting style has not
solved grouping, it has memorised a rhythm. **Report both, average neither.**

## What is deliberately NOT scored

**Precision against the human catalogue.** The human windows are a *selection*
as well as a grouping:

| film | share of runtime inside a human window |
|---|---|
| badgenius2017 | **33.1%** |
| howtomakemillions2024 | 92.3% |

Two thirds of badgenius is deliberately not catalogued. A machine window there
is unselected film, not an error. Scoring precision would be measuring
**selection**, which this piece does not attempt and which piece 3 owns.

This also means the N1a/N1b/N1d finding applies with full force: the human
catalogue is not ground truth. **Before calling any machine-only window wrong,
open its frames - all of them in the window, not one** (single-frame lesson,
2026-09-05). A window the human skipped is unmarked, not refuted.

## Failure modes this bar can still miss

- IoU >= 0.5 can be reached by a window with the right duration in the wrong
  place only if it overlaps heavily, so position is partly covered - but a
  systematic constant offset would show in the median start/end distance and
  not in the IoU share. Both are reported for that reason.
- A rule that emits one window per camera shot scores IoU ~0.30 on badgenius
  (3.0s inside 10.0s) and fails. Confirmed as the degenerate baseline to beat.
- A rule that emits one window for the whole film scores ~0 and fails.

---

# RESULT - 2026-09-07. FAILS. Not wired in.

Everything above is the text as pinned before measuring. Nothing in it was
edited afterwards. This section is the outcome.

## The headline is not that the rule failed

**A metronome passes the criterion I pinned.** "Break every 6 seconds at the
nearest cut" - no signal of any kind - scores 63.2% and 63.9%, clearing the
0.60 bar on *both* films, including the style-tuning clause.

| film | rule | IoU>=0.5 | median IoU | N | boundary-F1 |
|---|---|---|---|---|---|
| badgenius2017 | v1 `make_windows.py` (speech) | **26.0%** | 0.403 | 526 | 25.9 |
| badgenius2017 | baseline: 1 window = 1 camera shot | 46.3% | 0.485 | 1813 | **44.0** |
| badgenius2017 | **METRONOME every 6s** | **63.2% "PASS"** | 0.549 | 798 | 34.9 |
| howtomakemillions2024 | v1 `make_windows.py` (speech) | **24.6%** | 0.352 | 187 | 22.8 |
| howtomakemillions2024 | baseline: 1 window = 1 camera shot | 62.1% | 0.573 | 615 | **38.6** |
| howtomakemillions2024 | **METRONOME every 6s** | **63.9% "PASS"** | 0.573 | 435 | 37.2 |

Uncovered human windows: **0.0% on both films, every rule.** The hard-fail
clause never fired and never could - any partition of the timeline covers
everything. That clause was free, and I wrote it as though it were a test.

So the pinned criterion:

- **passes a metronome** on both films;
- **fails every rule that uses a signal**;
- is monotone in window count (512 -> 16.9%, 781 -> 27.3%, 1813 -> 46.3%),
  because best-overlap IoU with an unbounded number of machine windows rewards
  cutting the film finer, which is the opposite of grouping.

This is the fifth measurement-shaped-non-measurement on the register, and the
first one I built deliberately, pinned, and then caught with my own baseline.
The baselines were the only reason it was caught. **The pinned bar was the
part that was wrong, and pinning is what made that visible instead of
convenient.**

### The count-controlled metric that should have been pinned

Boundary-F1 inside the human-selected region, tolerance 1.0s, greedy one-to-one
match - over-segmentation costs precision:

```
badgenius2017           best over ALL variants tried   45.1
                        baseline (do nothing)          44.0
howtomakemillions2024   baseline (do nothing)          38.6
```

**Nothing beat the baseline by more than 1.1 points.** Precision never exceeded
44.1% on any rule. Under this metric the metronome is clearly worse than the
baseline (34.9 vs 44.0), which is the correct verdict and the one the pinned
metric inverted.

## v1 is the worst rule tested, and the signal is the reason

Direct test of the brief's hypothesis - are human window edges closer to speech
boundaries than chance?

| distance to nearest **speech** boundary | badgenius | howtomakemillions |
|---|---|---|
| human window edges | 4.76s (29.4% within 1s) | 2.89s (26.4% within 1s) |
| uniformly random time points | 2.67s (34.5%) | 1.85s (36.9%) |
| **randomly chosen cuts** | 4.65s (27.8%) | 2.52s (32.9%) |

Human edges are **not closer to speech boundaries than a randomly chosen cut** -
on howtomakemillions they are slightly *worse* than chance. Speech carries no
usable signal for where a moment ends, on either cutting style. Every speech
variant swept (tol 0.5-3.0, local minima, snap-to-cut, silence-gated) scored
below the baseline.

Cuts, by contrast, are a very strong signal for where a human edge lands:

| distance to nearest **cut** | badgenius | howtomakemillions |
|---|---|---|
| human window edges | 0.71s (66.7% within 1s) | 0.04s (59.8% within 1s) |
| random time points | 1.19s (44.0%) | 3.39s (17.1%) |

So the cuts are right and the grouping signal is absent. Shot-duration rules
(seed-on-long-take, merge-short-runs, 4 quantiles each) also land at F1
38-45 - baseline.

## The data is sufficient; the available signals are not

Ceiling - best IoU any grouping of consecutive cuts could reach, per human
window:

```
badgenius2017          97.4% of human windows reachable at IoU>=0.5  (median 0.841)
howtomakemillions2024  88.9%                                          (median 0.887)
```

Optimal groupings use a **median of 2 camera shots**. So a correct grouping
exists for ~9 in 10 human windows - **nothing in `_cuts.json` + `transcript.json`
predicts which one.** This is a signal problem, not a tuning problem, and no
further parameter sweep will fix it.

## Why the ceiling is not 100% - checked against frames, not assumed

The brief requires opening frames before calling anything wrong. The 6
badgenius windows no grouping can reach were the candidates for human error.
`clip:01:01:44.0` (3704.0-3706.0, 2.0s, ceiling 0.19), all 8 frames of the
containing region read:

- 3695.6 -> 3704.9 wide lecture hall, barcode on the projection screen
- **cut at 3705.08**
- 3705.4 -> 3708.6 close-up insert, bars resolving to A, B, C, D

The human window takes **1.08s of the wide shot plus 0.92s of the insert** - it
deliberately straddles the cut to catalogue the transition itself. Its own note
says so: *"01:44 the screen, 01:46 the letters under the bars"*. The catalogue
is **right** and no cut-aligned grouping can ever express it.

> **A correction I nearly published.** I first read my own bracket output as
> showing no cut between 3695.29 and 3708.92 and was about to report that scene
> detection had *missed a cut* - which would have contradicted "detection is
> solved". The cut was listed at 3705.08, in the output I had already printed.
> Fourth instance in three days of a confident claim about my own setup made
> from a misread rather than the record, again in the direction of the more
> interesting story. Caught by re-reading the line, as with `shot227`.

## Verdict

**FAIL.** v1 fails the pinned bar on both films (26.0% / 24.6% vs 0.60) and
loses to doing nothing on both. Per the brief's condition, `windows.json` is
**not** wired into `extract_shot_frames.py` or the tagging loop, `shots_machine.json`
was not produced, and no draft was written from it.

Both self-tests are in `gate_selftest.py` and pass (`WINDOW-GROUPING`,
`WINDOW-BAD-CUT`), including a negative control proving the forbidden-input
check can fail.

## What piece 1 needs instead

The grouping boundary is semantic - it is where *what is happening* changes,
and cut timings plus speech timings do not encode that. Untested options, in
order of cost:

1. **Visual similarity between adjacent shots** (histogram / embedding distance
   across a cut). Cheap, still no LLM, and the obvious missing signal: a
   shot/reverse/shot pair looks alike, a new location does not.
2. Audio texture change (music bed, room tone) rather than speech *timing*.
3. Transcript **text** rather than transcript timestamps - speaker turns,
   topic shift. This starts to be an LLM, which piece 1 excludes.

Option 1 is the honest next attempt, and it needs a count-controlled metric
pinned **before** it runs, not the one above.
