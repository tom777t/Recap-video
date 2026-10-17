# Piece 1, second attempt - LLM grouping inside the tagging loop

**Written 2026-09-08, BEFORE any span was tagged or scored.** Pinned. If it
fails this bar I report the failure; I do not move the bar.

v1 and its pinned criterion stay in the repo with the failure recorded -
`tools/make_windows.py`, `docs/WINDOW_GROUPING_CRITERION.md`. Not deleted.

## What v1 established

97.4% / 88.9% of human windows are reachable from `_cuts.json`, and nothing in
`_cuts.json` + `transcript.json` predicts which grouping. Speech boundaries are
no better than a randomly chosen cut (4.76s vs 4.65s; 2.89s vs 2.52s). The
grouping decision is editorial. So it moves into the LLM.

## Shape

Film is split into spans of ~90s snapped to real cuts. One subagent per span,
fresh context. It receives one frame per cut inside the span and returns
**moments**: consecutive runs of cuts, `clip_start`/`clip_end` on real cut
timestamps, plus `depicts` / `chars` / `action` / `censor`. Moments must tile
the span - no gaps, no overlaps.

**Blindness unchanged:** no `shots.json`, no `beats_proposal.md`. Enforced by
the prompt and grepped in the self-test, as in v1.

### Span edges - where the error will concentrate

A moment that straddles a span edge is the predictable failure: both spans see
half of it and both will close a moment at the edge, producing a false boundary
at every seam. 30 seams on badgenius would inject up to 30 spurious boundaries
into ~95 windows - enough to move F1 on its own.

Handling, declared now:

1. Span `i` **owns** `[S_i, S_i+1)`. Boundaries `S` are snapped to the nearest
   real cut.
2. The subagent is shown cuts over the **extended** range `[S_i, S_i+1 + 20s]`
   and must tile that whole extended range. The extra 20s is context so it can
   see whether the moment continues past the edge.
3. At assembly, a moment is **kept by the span whose owned range contains the
   moment's midpoint**. A moment genuinely crossing a seam is therefore kept
   whole, exactly once, by whichever span holds most of it.
4. Residual conflicts after step 3 are resolved deterministically: for an
   overlap between consecutive kept moments, cut at the real cut nearest the
   middle of the overlap; for a gap, extend the earlier moment to the later
   one's start. Every such adjustment is **counted and reported** - if seams
   need many adjustments, the overlap scheme failed and the number says so.

## The metric - count-controlled, pinned

**Boundary-F1, tolerance +-1.0s, greedy one-to-one matching**, computed over
machine and human boundaries inside the declared region. One-to-one matching
plus precision is what makes it count-controlled: emitting 3x the windows
cannot win, because the extra boundaries land in precision's denominator.

Reported **every time, side by side, on the identical region**:

| | |
|---|---|
| machine | boundary-F1, P, R |
| **baseline A** | one window per camera shot |
| **baseline B** | metronome, break every 6s at nearest cut |
| **count ratio** | machine windows / human windows |

v1's lesson: the metronome passed v1's IoU bar on both films. It is reported
here every time precisely so it cannot happen quietly again.

### PASS

```
boundary-F1 >= (better of baseline A, baseline B) + 8.0 points
        on BOTH films, computed on the identical region
AND count ratio within [0.70, 1.50] on both films
```

If count ratio falls outside that band the F1 result **does not count as a
pass**, whatever its value - a rule that wins F1 by producing 3x the windows
has not won. Reported, not averaged, per film. One film passing and the other
failing is a FAIL and is reported as style-tuning.

Margin reasoning, fixed before any baseline for these regions was computed:
+8 points is roughly the gap between "indistinguishable from doing nothing"
and a real effect given ~90 human windows per region, where the one-to-one
matching makes a single point worth about one boundary. Full-film baselines
from v1 were 44.0 (badgenius) and 38.6 (howtomakemillions); region baselines
are computed after this document is written.

## Declared evaluation regions

Full films would be 172 subagent calls. A contiguous region per film instead,
**with every baseline computed on the identical region**:

| film | region | min | cuts | spans | human windows | human edges |
|---|---|---|---|---|---|---|
| badgenius2017 | 01:00:00-01:45:00 | 45 | 745 | 30 | 95 | 183 |
| howtomakemillions2024 | 01:00:00-01:30:00 | 30 | 155 | 20 | 88 | 90 |

Opposite cutting styles preserved: 24.8 cuts/span vs 7.8 cuts/span.

## Downstream check - badgenius2017 only

v1's lesson was that boundary agreement may not matter downstream, the way 1%
`depicts` agreement did not. So the decisive test is bindability.

Take the **human** `draft.json`. 60 of its 150 lines fall fully inside the
badgenius region. A line with human window `[a,b]` and narration of `w` words
is **bindable** to machine moment `[m0,m1]` if:

```
overlap([a,b],[m0,m1]) >= 0.70 * (b - a)      the moment shows what the line describes
AND  w/3.0 + 0.6 <= (m1 - m0) * 1.4           the existing capacity rule
```

Both conditions on the **same** moment. Reported as a share of the 60 lines,
with every unbindable line named.

**A bindability of ~90% means the windows are good enough to draft from even if
boundary-F1 is mediocre**, and I will say so plainly rather than hiding behind
the F1 verdict. The two results are reported independently; neither is allowed
to overrule the other silently.

## What would make this a non-measurement

Listed now so I can be held to it:

- Scoring only the spans that came back clean. Failed or malformed spans count
  as produced-nothing, and are named.
- Letting the 20s overlap region be scored twice.
- Quietly changing span length, tolerance, or region after seeing a score.
- Reporting F1 without the count ratio.

---

# RESULT - 2026-09-08. FAILS the pinned bar. Passes the downstream test.

Everything above is as pinned. Nothing in it was edited after measuring.

50 spans tagged by subagents (30 badgenius + 20 howtomakemillions), 0 spans
missing, 0 vocabulary/tiling validation problems.

## The pinned metric - FAIL on both films

| film | rule | F1 | P | R | N | ratio |
|---|---|---|---|---|---|---|
| badgenius2017 | **LLM moments** | **30.8** | 28.6 | 33.3 | 213 | **2.24** |
| badgenius2017 | baseline A: 1 shot | 28.7 | 17.9 | 72.7 | 744 | 7.83 |
| badgenius2017 | baseline B: metronome 6s | 24.5 | 19.6 | 32.8 | 305 | 3.21 |
| howtomakemillions2024 | **LLM moments** | **37.9** | 40.5 | 35.6 | 79 | **0.90** |
| howtomakemillions2024 | baseline A: 1 shot | **39.2** | 31.0 | 53.3 | 154 | 1.75 |
| howtomakemillions2024 | baseline B: metronome 6s | 36.0 | 31.4 | 42.2 | 120 | 1.36 |

```
badgenius2017           +2.1 over best baseline (need +8)   ratio 2.24 OUT OF BAND   FAIL
howtomakemillions2024   -1.3 over best baseline (need +8)   ratio 0.90 ok            FAIL
```

On howtomakemillions - the cleaner test, because the human catalogue there
covers 92.3% of runtime so there is almost no selection confound, and the count
ratio came out at 0.90 - **the LLM still loses to one-window-per-camera-shot.**

### The count ratio on badgenius is a confound, and it is disclosed as one

The human badgenius catalogue covers **34.7%** of the region; the LLM tiles
100%. Restricted to the time the human actually catalogued:

```
machine windows with midpoint inside human-selected time   89   vs 95 human -> ratio 0.94
precision on that restricted denominator                   65.1  (vs 27.5 whole-region)
recall                                                     30.6  (UNCHANGED)
```

So the 2.24 ratio is the machine covering film the human deliberately skipped,
not over-segmentation. But **recall does not move** - 2 in 3 human boundaries
are still missed. That is the real weakness and it is not a denominator
artifact. The pinned number stands as FAIL; this paragraph is the diagnosis,
not an appeal.

## The downstream test - PASS, and it inverts the ranking

60 human `draft.json` lines fall inside the badgenius region.

| windows | lines bindable | |
|---|---|---|
| **LLM moments** | **49/60 = 81.7%** | |
| baseline B: metronome 6s | 33/60 = 55.0% | |
| baseline A: 1 shot | 17/60 = 28.3% | **the F1 winner on hmm** |

**The one-shot baseline wins boundary-F1 and is useless downstream.** It has
many boundaries, so it matches human boundaries often (R 72.7 on badgenius),
but a single camera shot is too short to carry a narration line and rarely
covers 70% of a line's window. Boundary-F1 rewards exactly the thing that makes
it unusable.

The brief predicted this, and it is the same shape as the 1% `depicts`
agreement that turned out not to matter: **the metric and the use disagree,
and the use is what counts.**

81.7% is below the ~90% reference, so this is not "good enough" yet. All 11
failures are the same kind - *no moment covers >=70% of the line's window*, and
**zero** are capacity failures. The moments are the wrong shape, not too short.

## A real bug the self-test caught, after the first scoring run

The pinned seam rule was *"a moment is kept by the span whose owned range
contains the moment's midpoint"*. That rule is **wrong**, and `MOMENT-SEAM`
caught it:

> The overlap only extends **forward** (`ext_end`). A moment crossing a seam
> can therefore only ever be produced by the **earlier** span - the later span
> begins at the seam and never sees the moment's head. Handing ownership to the
> span containing the midpoint hands it to the span that **cannot produce it**,
> so the moment is dropped entirely and the gap-filling step quietly covers the
> hole with a different window.

On badgenius that was **13 gap-fixes and 85.79s of shift** - which I had been
about to report as "model disagreement at seams". It was my own rule deleting
moments.

Fixed to **start-ownership** (keep the moment if the producing span owns its
start; a cross-seam moment is kept whole; overlaps are resolved by trimming the
*later* moment, since the earlier span saw the tail with full context).

Before -> after the fix, both reported because the fix came after a scoring run:

```
                        F1 before   F1 after    gaps before -> after
badgenius2017              28.9       30.8          13 -> 0
howtomakemillions2024      34.5       37.9           3 -> 0
downstream bindable        83.3%      81.7%
```

The verdict does not change: FAIL on the pinned bar, both films, before and
after.

## A second defect, same class

`MAX_FRAMES = 34` in `make_spans.py` truncated the frame list **from the end**.
12 of 30 badgenius spans lost every frame past shot 33 - **77 shots with no
image**, and the blind region was the span *tail*, which is exactly what the
seam logic depends on. Two spans had already been tagged blind and were redone.
The cap now drops only supplementary frames and never a shot.

Both defects are the same shape as the boundary-at-the-wrong-altitude pattern:
a limit placed where it was convenient rather than where the protected thing
actually fails.

## Verdict

**FAIL as pinned**, on both films, and reported as such. Not a style-tuning
failure - it fails on both cutting styles, by +2.1 and -1.3 against a bar of +8.

But the downstream result is the one that matters for the pipeline, and it is
**81.7% vs 28.3% for the metric's own winner**. The honest reading:

> Boundary-F1 against a human catalogue is the wrong instrument for this.
> It cannot distinguish a usable moment from a camera shot, and on badgenius
> its denominator is contaminated by the human catalogue being a *selection*.
> The bindability test separates them cleanly at 81.7 / 55.0 / 28.3.

I am **not** retroactively declaring a pass on the downstream number. The bar
was pinned on boundary-F1, it failed, and the correct conclusion is that the
bar was aimed at the wrong quantity - which is the same error as v1, made a
second time, in a new form. The next criterion should be pinned on bindability
with a count-control, not on boundary agreement.

v1 artifacts retained as instructed: `tools/make_windows.py`,
`docs/WINDOW_GROUPING_CRITERION.md`, `projects/*/windows.json`.

Self-tests: 20/20, including `MOMENT-SEAM` and `MOMENT-BAD-SPAN`
(one corrupt span file is named and costs only that span).
