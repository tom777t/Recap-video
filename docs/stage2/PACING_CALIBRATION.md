# Pacing contour: what the reference channels actually do

Measured 2026-10-30 with `tools/measure_pacing.py` on `references/voice/*.vtt`.
Raw numbers in `config/pacing_control.json`.

## The complaint this exists to answer

The Tokyo Drift draft reads as rushed outside two or three scenes. Measured on
it: **56 of ~80 beats get exactly one line**, every 10 film-minutes gets
1.0–1.6 narration-minutes, and only 14 of 109 lines are narrator judgment. The
scenes viewers singled out — Han on the footbridge (B57/B58), the Neela beats
(B64–B66) — are exactly the ones given 3–4 lines.

So the question is measurable: do the reference channels hold a flat contour,
or do they dwell?

## What a "scene" is in a transcript, and why the basis matters more than the number

Our drafts bind every line to a shot window, so a scene is a given. A reference
is narration over a film we do not have, so boundaries must be inferred from
two signals in the text: a transition cue opening a sentence ("meanwhile",
"the next morning", "back at the house") and a pause longer than that
channel's own typical between-sentence gap.

This **under-segments** — a recap that cuts without signalling reads as one
long scene — and under-segmentation inflates lines-per-scene and shortens
one-line runs.

**The basis is not a detail. Measured on the SAME Tokyo Drift draft:**

| basis | scenes | top20 runtime share | 1-line share | longest 1-line run |
|---|---|---|---|---|
| real beats (what the writer controls) | 82 | **0.310** | 69.5% | **9** |
| the reference's own cue segmentation | 17 | **0.412** | 23.5% | **2** |

Comparing the beat-basis 0.310 against the reference's 0.480 would have been
comparing different units — the same mistake as judging voice spread by
max/min against a control measured as p95/p5. So the gate measures **beats**,
because that is what the writer controls, and the bars below are derived with
the conversion stated.

## English references (5 files, 8.7–25.4 min)

| file | scenes | lines/scene mean | 1-line share | longest run | top20 runtime | top20 lines |
|---|---|---|---|---|---|---|
| cutframe_fT_pA_sX3VU | 27 | 12.48 | 4% | 1 | 0.419 | 0.430 |
| mrecaps_HDI-QESF9GY | 10 | 13.00 | 0% | 0 | 0.480 | 0.477 |
| mrecaps_SnAufo-cIao | 27 | 8.44 | 11% | 1 | 0.462 | 0.443 |
| mrecaps_dXSI1hYlXlk | 15 | 16.73 | 7% | 1 | 0.502 | 0.506 |
| mrecaps_lCD7leAyMYo | 42 | 4.55 | 21% | 3 | 0.481 | 0.461 |

**min / median / max**

| metric | min | median | max |
|---|---|---|---|
| lines per scene (mean) | 4.55 | 12.48 | 16.73 |
| one-line scene share | 0.000 | 0.067 | 0.214 |
| longest one-line run | 0 | 1 | **3** |
| top20 runtime share | **0.419** | **0.480** | 0.502 |
| top20 line share | 0.430 | 0.461 | 0.506 |

### Which of these is trustworthy

- **`top20_runtime_share` is the robust one: 0.419–0.502 across five files of
  wildly different length and scene count.** A statistic that holds to ±4
  points while `lines_per_scene_mean` swings 4.55→16.73 on the same corpus is
  measuring something real; the other is measuring the segmenter.
- `lines_per_scene_mean` is **not** usable as a bar. It is dominated by how
  many boundaries the cue list happens to find.
- `one_line_scene_share` and `longest_one_line_run` are **lower bounds**,
  because merging scenes destroys one-line scenes. Their true beat-basis values
  are higher than shown.

## Vietnamese reference: weak evidence, deliberately not used for bars

Three of four Vietnamese files produced too few sentences to measure —
Vietnamese auto-captions largely lack sentence-final punctuation, so the
sentence splitter finds nothing. The one file that measured:

| file | scenes | top20 runtime | 1-line share | longest run |
|---|---|---|---|---|
| sakura_9Mkd0KgoWZU | 20 | 0.578 | 20% | 1 |

0.578 is *more* dwell than any English file. That is interesting but it is one
file, and `TARGET_WPM` was once set from a Vietnamese channel and applied to
English narration, where it was wrong by 25 WPM. **The bars come from the
English channels.** The Vietnamese figure is recorded as a cross-check and
points the same direction: dwell harder, not softer.

## The bars, and why each number

Gate: `PACING-CONTOUR` (beat basis).

| bar | value | derivation |
|---|---|---|
| `PACING_TOP20_LINE_SHARE_MIN` | **0.40** | References concentrate 0.430–0.506 of lines in their top 20% of scenes on their own basis; our draft measures 0.431 cue-basis against 0.324 beat-basis, a 0.75 conversion. 0.48 × 0.75 ≈ 0.36 is the reference-equivalent floor, so 0.40 is slightly *stricter* than the references and is reachable: the intended shape (8 anchors × 4 lines, ~20 beats dropped to footage, the rest at 1) computes to 0.465. |
| `PACING_ANCHOR_MIN_LINES` | **3** | The scenes viewers singled out have 3–4 lines. One line is the defect; two is not dwell. |
| `PACING_ONE_LINE_RUN_MAX` | **4** | English references max out at 3 on a basis that *destroys* one-line scenes, so their true value is higher. The current draft runs **9**. 4 permits a short connective stretch and fails monotony. |
| `PACING_ANCHORS_MIN` / `_MAX` | **5 / 8** | From the brief. |

A beat with **no** narration (footage or hold) breaks a one-line run rather
than extending it: a deliberate pause is a change of rhythm, which is the
opposite of the monotony being measured. Consecutive silent beats are capped
separately by the existing hold rules.

## How to re-run

```
python tools/measure_pacing.py --write      # rewrites config/pacing_control.json
python tools/test_pacing.py                 # asserts the bars still sit against the control
```

`test_pacing.py` fails if the control and the constants disagree, if the
English `top20_runtime_share` spread widens beyond ±0.10 (which would mean the
statistic had stopped being robust and the bar needs rethinking), or if the
Vietnamese files start dominating the sample.
