# Runtime, judgment and the review artifacts: what was measured

Measured 2026-10-30 with `tools/calibrate_runtime.py` and
`tools/calibrate_judgment.py`. Raw numbers in `config/runtime_control.json`
and `config/judgment_control.json`. Bars in `config.py`; severities in
`docs/WRITING_CRAFT_CRITERION.md`.

This file is the companion to `PACING_CALIBRATION.md` and follows its rule:
every bar states the population it was measured on, the statistic that was
**rejected**, and the basis conversion that made the comparison legal. A bar
whose basis is undeclared is the mistake this repo keeps paying for.

---

# PART 1 — RUNTIME

## The complaint this exists to answer

The old band was `RECAP_RUNTIME_PCT_LO = 15.0` / `PCT_HI = 20.0`, a share of
film runtime, derived from **one** film ("the human reference sits near 15%")
with ±5 points drawn around it by hand. It was also a bare `console.print`
with no severity, so it could not stop anything. Two consequences, both
observed:

1. 15% was the band's **floor** while being the shipped population's
   **ceiling**. No render ever reached the middle of the band; seven of nine
   sat below the floor.
2. A rewrite brief to *pay for dwell by cutting connective tissue* came back
   **1,200 words longer** and the runtime check printed a note nobody had to
   act on.

So the question is measurable: across the renders that actually shipped, which
holds still — the absolute runtime, or the share of the film?

## The nine shipped renders

`final_min` is measured from `final.mp4`. `draft_est_min` is `words / 210.0`
WPM — the only runtime number the *draft* stage can see.

| project | film_min | final_min | words | draft_est_min | render_share | final/est |
|---|---|---|---|---|---|---|
| `shutterisland2010_linear` | 132.08 | **9.12** | 1882 | 8.96 | 6.9% | 1.018 |
| `interstellar2014_linear` | 169.07 | 16.17 | 3158 | 15.04 | 9.6% | 1.075 |
| `spidermannowayhome2021_linear` | 156.93 | 17.22 | 3457 | 16.46 | 11.0% | 1.046 |
| `badgenius2017` | 129.88 | 16.37 | 3464 | 16.50 | 12.6% | 0.993 |
| `badgenius2017_machine` | 129.88 | 18.54 | 3428 | 16.32 | 14.3% | 1.136 |
| `superbad2007` | 118.67 | 17.18 | 3743 | 17.82 | 14.5% | 0.964 |
| `howtomakemillions2024` | 126.79 | 18.81 | 3511 | 16.72 | 14.8% | 1.125 |
| `johnwick2014_linear` | 101.22 | 15.04 | 3106 | 14.79 | 14.9% | 1.017 |
| `tokyodrift2006` | 104.24 | 15.67 | 4266 | 20.31 | 15.0% | — |

**min / median / max, all nine**

| metric | min | median | max | spread (max/min) |
|---|---|---|---|---|
| finished minutes | 9.12 | 16.37 | 18.81 | **2.062x** |
| render share of film | 6.9% | 14.28% | 15.04% | **2.18x** |
| film length | 101.22 | 129.88 | 169.07 | **1.670x** |

### The one excluded render, and the rule that excluded it

`shutterisland2010_linear` at **9.12 min / 6.9%** is excluded from both
spreads. It is not excluded for being inconvenient; it is an outlier by the
**1.5xIQR rule** on the nine finished runtimes:

```
sorted   9.12  15.04  15.67  16.17  16.37  17.18  17.22  18.54  18.81
Q1 = 15.355   median = 16.37   Q3 = 17.88   IQR = 2.525
fences = 15.355 - 3.788 = 11.57   and   17.88 + 3.788 = 21.67
9.12 < 11.57  ->  low outlier.  Nothing is above the high fence.
```

It is roughly half the length of every other render and it is the **only**
reason the raw spreads above read 2.06x and 2.18x. With it excluded:

| metric | min | max | spread |
|---|---|---|---|
| finished minutes | 15.04 | 18.81 | **1.251x** |
| render share of film | 9.56% | 15.04% | **2.180 (see the note on the exclusion rule); 1.573x** |
| film length | 101.22 | 169.07 | 1.670x |

## Which statistic is usable, and which is NOT

- **Absolute finished minutes is the robust one: 15.0–18.8 min while film
  length varies 1.670x.** A quantity that holds to 1.25x while its supposed
  driver moves 1.67x is not driven by it. The format's real constraint is the
  **viewer's attention**, not the film's length.
- **`render_share` is NOT usable as the primary bar.** It is the *looser*
  statistic — 1.251x against 2.180x — and a share band wide enough to contain
  every shipped render (9.6%–15.0%) rejects nothing a writer would ever
  produce. This is the same test `PACING_CALIBRATION.md` used to throw out
  `lines_per_scene_mean`: the number that moves is measuring something else.
- **`draft_share` is NOT usable either**, for the same reason one basis down
  (0.068–0.150, median 0.127). It is the share statistic computed on the
  draft estimate; being the same statistic, it inherits the same looseness.

## The bars, and why each number

Gate: `[RUNTIME-BAND]` (`pipeline/draft.py`, the block headed
"`[RUNTIME-BAND]`: BLOCKS above the band").

| bar | value | derivation |
|---|---|---|
| `RECAP_RUNTIME_MAX_MINUTES` | **19.0** | Just above the longest render that shipped (18.81). **ERROR — blocks the render.** Above is the direction the draft actually drifts and the direction the viewer complained about. |
| `RECAP_RUNTIME_MIN_MINUTES` | **14.0** | Just below the shortest non-outlier render (15.04). **WARNING only** — a film can honestly have less to say, and the excluded 9.12-min render shipped. |
| `RECAP_RUNTIME_PCT_HI` | **20.0** | ERROR. The **out-of-domain guard**, not a calibrated bar. The population covers 101–169-min films; on a 60-min film 19 minutes is a third of the picture, which the absolute ceiling alone would pass. Deliberately loose (shipped renders reach 15.0% at most) because its only job is to catch a film far shorter than anything measured. |
| `RECAP_RUNTIME_PCT_LO` | **9.0** | WARNING. Lowered from the old 15.0, which declared **seven of the nine shipped renders** out of band. 9.0 sits just below the lowest non-outlier share (9.56%). |
| `RECAP_RUNTIME_RENDER_OVER_DRAFT` | **1.046** | The measured draft→render conversion. See below. |

Whichever of the two ERROR bars is exceeded blocks.

## The basis conversion, and why it exists

Two different numbers are both called "the recap's runtime":

- what the **draft gate** can see: `words / TTS_WORDS_PER_MINUTE` (210.0),
- what the **viewer** gets: `final.mp4`, which also carries holds, the intro,
  music tails, SFX and the gaps between lines.

The bars above describe the second. So the draft estimate is multiplied by the
**measured** factor before comparison, rather than compared raw — otherwise
the two stages enforce one number on two bases, which is the error this repo
has already shipped twice (`185` vs `140.6` WPM in the word budget; 170 WPM in
`script.txt` against a different rate in `DRAFT-TARGET`).

Measured `final_min / draft_est_min` on the **eight** renders whose draft still
matches their render:

```
0.964  0.993  1.017  1.018  1.046  1.075  1.125  1.136      median 1.046
```

`[RUNTIME-BAND]` computes `predicted_finished = (words / 210.0) x 1.046` and
compares *that*. Worked example from `tools/test_runtime_band.py`: 3,885 words
= **18.5 min raw**, which is UNDER the 19.0 ceiling, and predicts **19.35 min
finished**, which is over it and blocks. Without the conversion that draft
ships.

### One render is excluded from the conversion, and why

`tokyodrift2006` is **unpaired**: `103 of 111 lines have audio that does not
match their text — draft.json is not the draft this render was made from`.
Its `final_min` (15.67) still counts toward the absolute band, because the
finished file is real; its `draft_est_min` (20.31) does not, because it is the
estimate of a *different* draft. Pairing it would have produced a conversion
factor of 0.772, outside every other render's range — the signal that said the
inputs were mismatched. `stale_audio` answers that question from the TTS
manifest's recorded signatures rather than from eyeballing the outlier.

### Basis warning: the conversion is only as tight as its own spread

The factor's own range is 0.964–1.136, i.e. **−8% / +9%** around the median. At
the ceiling that is worth about ±1.6 finished minutes:

```
19.0 / 1.046 = 18.17 raw min
18.17 x 0.964 = 17.5 min      18.17 x 1.136 = 20.6 min
```

So a draft predicting 18.5–19.5 min is **inside the conversion's own error** —
the gate's verdict there is a coin toss dressed as a measurement. This is
accepted deliberately: the bar blocks in the direction the drafts drift, and
the cost of a false block is one compress pass, while the cost of a false pass
is a shipped 25-minute recap. It is recorded here so nobody later reads 19.35
as a precision figure.

## What this bar does NOT measure

It measures **length**, not pacing. A draft can sit at 17.0 min and still be
flat (`PACING-CONTOUR`), or pre-digested (`PERSONA-CEILING`), or repetitive
(`MOTIF-BUDGET`). Runtime was never the complaint; it is the constraint the
*fix* for the complaint kept breaking.

---

# PART 2 — JUDGMENT

## The complaint this exists to answer

`PERSONA_JUDGMENT_SHARE_MIN` was a floor with no ceiling. Told only to clear
it, the rewrite of the *Tokyo Drift* draft came back at **52.3%** judgment on
the gate's own instrument: the narrator talks over the film, every beat
arrives pre-digested, and the peak moments land on commentary instead of on
the moment. A floor with no ceiling is half a bar, and the half that was
missing is the half the viewer noticed.

A second question came with it: was **0.22** ever right? Nothing in the repo
recorded a derivation for it. The comment above the constant explained the
*instrument* in detail and never said where the *number* came from.

## The basis problem, which is the whole difficulty

A reference is a VTT. **A VTT has no line structure** — its only natural unit
is the sentence. Our drafts' unit is the LINE, and a line holds 1–4 sentences;
a line counts as judgment if **any** of its sentences does. Those two shares
are not comparable and must not be compared.

So, exactly as `PACING_CALIBRATION.md` did for the contour bars:
the references are measured **by sentence**, our own drafts are measured **by
sentence AND by line**, and the conversion between the bases is measured on
our own text rather than assumed.

| draft | lines | sentences | share (sentence) | share (line) | line/sentence |
|---|---|---|---|---|---|
| `draft_overcorrected.json` | 111 | 353 | 0.354 | 0.730 | 2.062 |
| `draft_prerewrite.json` | 106 | 258 | 0.213 | 0.434 | 2.038 |

**`line_per_sentence_conversion = 2.05.`** The two drafts agree to within 1%,
which is the only reason the factor is trusted at all. It is measured, not
assumed, and it is measured on *our* text because the references cannot supply
it — they have no lines to convert to.

The instrument is `pipeline.pacing_gates.classify_judgment`, the **same**
function the gate calls. Calibrating with one instrument and judging with
another is how the first frame-only cap came out wrong.

## English references, measured by sentence (5 files)

| file | sentences | judgment | share | longest run |
|---|---|---|---|---|
| `mrecaps_lCD7leAyMYo.en-orig.vtt` | 191 | 9 | 0.047 | 1 |
| `mrecaps_dXSI1hYlXlk.en-orig.vtt` | 251 | 12 | 0.048 | 1 |
| `mrecaps_SnAufo-cIao.en-orig.vtt` | 228 | 17 | 0.075 | 2 |
| `mrecaps_HDI-QESF9GY.en-orig.vtt` | 130 | 14 | 0.108 | 2 |
| `cutframe_fT_pA_sX3VU.en-orig.vtt` | 337 | 141 | **0.418** | **8** |

**min 0.047 / median 0.075 / max 0.418.** Spread **8.9x**, and — the fact that
decides everything below — **there is nothing between 0.108 and 0.418.**

## Which of these is trustworthy

- **`longest_judgment_run` is the robust one: 1, 1, 2, 2, 8 — four of five run
  two or fewer.** It is a shape statistic, not a density statistic, and it
  survives the outlier: dropping the chatty file changes the median not at all.
  This is the one judgment bar that **is** reference-calibrated.
- **`judgment_share` is NOT usable as a ceiling.** The genre does not agree on
  a judgment density. The "upper end" of the references is either 0.108 —
  which **both** of our drafts exceed, including the one nobody complained
  about — or 0.418, which rejects nothing. A distribution with a 3.9x gap in
  the middle of it and n=5 has no upper quantile worth the name.
- `judgment_share` **is** usable as a floor, as an upper bound. See below.

## The floor: 0.22 -> 0.15, because the gold standard failed 0.22

The gate measures the **agreement** of the writer's `payload` label with the
classifier. That set is a strict **subset** of the classifier's set, so

```
agreed_share  <=  classifier_share       always
```

which makes the floor argument sound even though the two quantities differ:
demanding `agreed >= 0.22` *necessarily* demands `classifier >= 0.22`. So a
reference whose classifier share cannot reach 0.22 cannot clear the floor
however its lines were labelled. Converting the reference sentence shares to
our line basis by the measured x2.05:

```
0.096   0.098   0.154   0.221   0.857
```

**Three of the five English references cannot satisfy a 0.22 floor at all.**
Of the two that can, one sits *exactly* on it (0.221) and the other is the
chatty outlier (0.857). A bar the gold standard fails is a broken bar, not a
broken gold standard — the same finding that moved five of eleven bars in
`docs/WRITING_CRAFT_CRITERION.md`.

`PERSONA_JUDGMENT_SHARE_MIN = 0.15`. It keeps the point of the floor —
refusing a narrator with no view at all — while sitting just **below** the
reference that defines the quiet end of the genre (0.154). And **0.22 had no
derivation recorded anywhere**, which is the other half of why it moved: it
was not a measurement being revised, it was an unsourced number being replaced
by one.

### What the floor does NOT do: cure flatness

The shipped draft measured **0.213 judgment by sentence — above four of the
five references** — and the viewer still called it flat. Flatness was a
**dwell** defect (56 of ~80 beats getting exactly one line) and
`PACING-CONTOUR` is what fixed it. Raising a judgment floor to fix dwell is
precisely how 0.104 became 0.523.

## The ceiling: NOT reference-calibrated, and the references say why

`PERSONA_JUDGMENT_SHARE_MAX = 0.35`.

The references cannot site this bar, for the reason stated above: 9x spread,
nothing between 0.108 and 0.418. So it is calibrated the way
`config/shipped_render_defects.json` sites the render thresholds — **on our own
work, with the viewer's verdict as the label** — and that is a weaker basis
than the run cap has, stated here rather than implied:

| draft | judgment share (gate basis: label ∧ classifier) | verdict |
|---|---|---|
| `draft_prerewrite.json` | **0.104** | called flat; **no complaint about commentary** |
| `draft_overcorrected.json` | **0.523** | called overcorrected — the narrator talks over the film |

The bar sits between them, **nearer the complaint**: 0.35 leaves the known-bad
draft failing by a wide margin and leaves 3.4x headroom above the draft nobody
complained about. n=2, and the label is a human verdict rather than a
measurement. It is a defensible siting, not a calibration, and it should move
the first time a third draft gives it a real distribution.

### Basis warning: two different "judgment shares" appear in this file

`config/judgment_control.json` records the **classifier-only** share (0.730 and
0.434 on the line basis). The GATE measures the **intersection** of the
classifier with the writer's `payload` label (0.523 and 0.104). The second is
always smaller, sometimes much smaller, and the two are **not interchangeable**:

- the floor derivation above uses the classifier numbers *as an upper bound*,
  which is valid because agreement can only reduce them;
- the ceiling siting uses the gate numbers, because the ceiling is the bar the
  gate enforces and nothing else would be comparable to it.

Reading 0.730 from the control file and 0.35 from config as if they were the
same quantity would make the ceiling look violated by every draft ever written.
They are different instruments on the same text.

## The shape bars

| bar | value | basis | derivation |
|---|---|---|---|
| `PERSONA_JUDGMENT_RUN_MAX` | **2** | **reference-calibrated** | Longest consecutive run of judgment *sentences* across the five English references: 1, 1, 2, 2, 8 — four of five at or under 2. The overcorrected draft runs **14 lines** (5 by sentence). |
| `PERSONA_PEAK_REACTION_MAX` | **1** | DECISION, sited on the defect | The overcorrected draft gave one death **seven lines, four of them commentary, two of which made the same point.** A peak narrated before it is shown is a peak the viewer is told about instead of shown, so the moment lands first on action, quotation or a hold, and gets one reaction. |
| `PERSONA_ANCHOR_CLEAN_LINES_MIN` | **1** | DECISION, sited on the defect | Two anchors in the overcorrected fixture had **4 lines each and 0 without commentary**. Dwell was bought to make room for the moment; spending all of it on the narrator's opinion of the moment deletes the thing being dwelt on. |

## The motif and tic bars are DECISIONS, not measurements

`MOTIF_CALLBACKS_MAX = 2`, `MOTIF_LINES_MAX = 4`, `MOTIF_THESIS_MAX = 1`,
`MOTIF_ADJACENT_OVERLAP_MAX = 0.50`, `TIC_NGRAM_N = 3`, `TIC_NGRAM_MAX = 1`,
`TIC_MIN_CONTENT_WORDS = 2`.

**None of these is reference-derived, and none can be.** A motif is identified
from the project's own `angle.md` `## RUNNING BITS` section — it is defined by
*this* recap's chosen angle, not by a property of the genre. The reference
channels do not publish their angle, so there is nothing in `references/` to
count. What was measured is the **defect**, on the overcorrected fixture
(111 narrated lines of 114):

```
one running bit's wording                   5 lines   (budget 4)
another running bit, promised in the angle  0 lines   (never run)
explicit "this is the thesis" statements    4         (budget 1 before the outro)
3-word phrases appearing in >1 line        20
highest adjacent content-word overlap   0.222         (cap 0.50)
```

and on the draft **before** that rewrite: 6 repeated phrases, no budget
breach, no thesis statement at all. That second figure is the other half of the
evidence — these bars **separate** the two drafts rather than failing every
draft. `angle.md` has carried a `## RUNNING BITS` section since the angle was
written and **nothing parsed it**, so a callback's budget was whatever the
writer felt like on the day; that is how one bit reached five lines with every
gate green.

### Two limits of the tic instrument, on the record

- `[MOTIF-ADJACENT]` is **lexical**. The overcorrected draft genuinely does
  contain adjacent pairs making the same point twice, and the worst measures
  **0.222** overlap — far under the 0.50 cap — because the second line
  restates the first in different words. The cap is **not** lowered to catch
  it: the top eight pairs measure 0.222, 0.214, 0.200, 0.200, 0.200, 0.188,
  0.182, 0.176, so there is no gap to put a bar in, and any bar that fails the
  worst pair fails a tenth of the draft's ordinary prose with it. Paraphrase is
  a job for the cold read.
- `[TIC-REPETITION]` counts 3-word n-grams carrying ≥2 content words. The two
  loudest real tics in that draft — a two-word stance marker in 5 lines and a
  two-word noun phrase in 5 lines — carry **one** content word each and are
  shorter than the window, so they are outside this instrument **by
  construction**. Lowering either constant to reach them floods the report with
  structural English ("he had to", "one of the"), which is the failure the
  constants exist to prevent. They are reported in `stats` as near-misses so
  the number stays on the record instead of being silently absent.

## A synthetic fixture was changed, and the bars were not

`tools/test_pacing.py::GOOD-SHAPE-PASSES` builds a synthetic draft in the
intended shape (8 anchors x 4 lines, ~20 beats dropped to footage, the rest at
1) to prove the contour bars are **reachable**. When the ceiling, the run cap
and the peak-order rule arrived, it failed all three: every anchor ended on
**two consecutive** judgment lines, and the fixture measured **41.9%** judgment
overall. A fixture built to satisfy a floor with no ceiling had encoded the
exact shape the ceiling exists to stop.

**The fixture was changed; the bars were not.** The distinction is the standing
rule, so it is worth stating plainly:

- a **synthetic shape demonstrator** is our own assertion about what good looks
  like. When it collides with a measured bar, it is the assertion that is
  wrong, and it was rewritten to land the moment first and the narrator last
  and once;
- an **externally validated draft** — a reference, or the human draft — is
  evidence. Had one of those failed, **the bar would have been the thing to
  move.** That is not hypothetical: it is exactly what happened to the 0.22
  floor two sections up, and to five of the eleven bars in
  `docs/WRITING_CRAFT_CRITERION.md`.

Treating the two kinds of fixture the same way in either direction is how a
gate quietly becomes a measurement of its own test suite.

---

# PART 3 — THE REVIEW ARTIFACTS

## The complaint this exists to answer

A human read a finished draft that every automated gate had passed, and found
three defects:

1. a line referring to a confrontation, and to a gun being taken off someone's
   head, as though the viewer had just watched it — **the beat containing it
   had been cut from the draft during trimming.** Against the *film* the line
   was perfectly true. It was false only against the *draft*, read front to
   back, by someone who had not written it;
2. two ambiguous pronouns, one of which made a character's nephew sound dead
   when he was not, and one where either of two men named in the preceding
   sentence could have been meant — **and the two readings said opposite things
   about the film.** Both lines are grammatical and both are inside their
   beat's evidence;
3. a narrator claim about what a character "spent the whole film" saying. That
   sentence appears in no transcript line and in no beat: an **invented
   pattern**, reading as the most authoritative line in the paragraph.

None of the three is reachable by a text rule. A dangling referent requires
knowing what was **cut**; an ambiguous pronoun requires **not already knowing**
the answer; an invented film-long claim requires having read the **whole**
film. All three require a fresh reader.

## What was rejected

Three cheaper designs, and why each fails:

- **mtime staleness** ("is `cold_read.md` newer than `draft.json`?"). Rejected:
  it is true for the whole file after any edit anywhere, so it fires on a typo
  fix in line 3 and stays **silent** when line 41 is rewritten and the artifact
  is then touched by an unrelated save. Content signatures answer the question
  actually being asked, which is *was THIS sentence reviewed*.
- **a `#` comment carve-out inside the fences**, as `pipeline/reviewed.py`
  allows. Rejected here: a cold reader writing its prose observations as
  `# the standoff has no beat` would have them silently dropped, which is the
  exact failure the artifact exists to prevent. Blank lines are the only thing
  skipped, and **prose inside a fence is a MALFORMED entry, never a skipped
  one**.
- **text-rule detectors for the three defects themselves** (a pronoun-antecedent
  counter, a "whole film" phrase matcher). Rejected as a **replacement**: they
  are worth having separately — `[CLAIM-SUPPORT]` is one of them — but any one
  of them going green would read as "the draft was reviewed", and none of them
  reads the draft front to back. They are a different claim.

## The mechanism

Two artifacts, in the **project** directory next to the draft they describe, so
the review travels with the project instead of sitting in a docs tree that gets
copied forward by accident. Both must be written by agents that did **not**
write the draft.

| file | gate | what it is |
|---|---|---|
| `cold_read.md` | `[COLD-READ]` | a blind first read, **narration only** |
| `review.md` | `[REVIEWER]` | a second pass, with the draft and the film, against a fixed checklist |

The cold read is produced from `python tools/cold_read_payload.py <project>`,
which prints the narration with line ids and **strips** delivery tags, payload
labels, the hook question and the beat note. Those are the **writer's own
account of what a line does**: an agent handed `script.txt` is told in advance
that line 6 is judgment and line 1 is a loop, and it reads looking for what it
has been told is there. A hold is still printed, as `[pause]` with **no
duration** — whatever the draft carries the reader must see, or the reader is
reviewing a different document from the one that will be rendered.

The gates do **not** judge the prose. They cannot. They enforce that somebody
did: that the review **happened**, that it is **current**, and that every
finding was **resolved or answered** — the same job the angle evidence audit
does for anchor mappings.

## The format

Prose outside the fenced blocks is allowed and ignored; both artifacts are
documents a human reads. Two fenced blocks carry the machine-readable part.

```review-signatures
  12 1a2b3c4d
  13 9f8e7d6c
```

`<line_id> <sig8>`, one entry per reviewed **narrated** line, where sig8 is
`review_artifacts.line_signature()` of the narration text the reviewer actually
read. Lines with no narration (holds, film-speaks units) are not in the
denominator — a reader cannot review them, and including them would put the
coverage bar out of reach of any draft that uses one.

```review-findings
FINDING  | dangling-ref      | 41,42 | "the standoff" has no beat in the draft
RESOLVED | dangling-ref      | 41,42 | the clause was cut in the 2026-06-14 pass
ANSWERED | ambiguous-pronoun | 77    | the antecedent is fixed by the prior clause, which names only one man
FINDING  | invented-claim    | -     | the narrator claims a repetition no line supports
```

`<STATUS> | <kind> | <line ids, comma separated, or -> | <text>`, exactly four
pipe-separated fields. STATUS is `FINDING`, `RESOLVED` or `ANSWERED`; `kind` is
a short slug. A FINDING is closed by a **LATER** RESOLVED or ANSWERED with the
**same `kind`** whose line ids **overlap**. A finding with no ids (`-`) is a
whole-draft observation and is closed by any resolution of its kind, because
requiring an id match would make it unclosable and the reviewer would learn to
stop writing them.

An ANSWERED must carry a real argument — `REVIEW_ANSWER_MIN_WORDS = 8` —
because "answered" with no reason is the same thing as no review at all. A thin
ANSWERED closes nothing; it does not merely warn.

Line ids are normalised: `41`, `L41` and `041` all mean the same line. Refusing
two of the three would train reviewers to fight the parser instead of reading
the draft.

## Staleness, and why a percentage bar alone is insufficient

`REVIEW_SIGNATURE_MIN_COVERAGE = 0.95`. The signature is sha1 of the
whitespace-normalised, lowercased text, 8 hex chars — **byte-for-byte the
normalisation `pipeline/draft.py exception_key` uses**, and for the same
reason: a review must survive a reflow or a capitalisation fix (nothing was
reviewed differently) and must **not** survive a word change (nobody reviewed
the new sentence). Reusing the rule rather than inventing a second one means
the repo's two staleness mechanisms can never disagree about whether a line
changed.

**The arithmetic that says the percentage is not enough.** On the 111-line
draft this was built against:

```
0.05 x 111 = 5.55  ->  five lines can be rewritten after the review
coverage = (111 - 5) / 111 = 0.955  >=  0.95   ->  PASS
```

Five silently rewritten lines, a green gate. And raising the bar to 100% is not
the fix, because an edit made **in response to a finding** is legitimate, and
re-reviewing after every such edit never terminates.

So the two cases are separated, and the second one is absolute:

- a line that changed **and** is named in a finding that was RESOLVED or
  ANSWERED is **accounted for** — that is the review working;
- a line that changed and is named **nowhere** is an unreviewed edit, and
  **one** of those fails the gate regardless of coverage. The review describes
  text that is no longer in the draft.

The percentage bar is kept for the *other* failure — whole blocks of narrated
lines that were never signed at all, which the silent-edit rule cannot see
because those lines never had a signature to differ from.

### Three more "cannot measure" paths that are not passes

Stated because a gate trusted for more than it measures is worse than none:

- a draft with **no narrated lines** makes coverage unmeasurable; the gate says
  so and the count it prints is explicitly **not a pass**;
- **malformed entries** are reported *before* anything derived from the file,
  because a file the parser only half understood makes every count below it a
  floor rather than a measurement;
- an artifact that exists with **no signature block** is treated as **STALE,
  not as missing** — the file is there, and an unknown answer must not
  masquerade as a fresh one.

A `RESOLVED`/`ANSWERED` that closes no earlier FINDING is a **warning**, not an
error: by itself it hides no defect, but it is either a typo in the kind slug
or a note left behind after its finding moved, and in the second case it would
silently cover the next finding of that kind.

## How to re-run

```
python tools/calibrate_runtime.py     # rewrites config/runtime_control.json
python tools/calibrate_judgment.py    # rewrites config/judgment_control.json
python tools/test_runtime_band.py     # the band, the conversion and the wire
python tools/test_motif_gates.py      # motif budget + tics, both directions
python tools/test_review_artifacts.py # format, staleness, silent edits
python tools/test_pacing.py           # the four ceiling gates
python tools/gate_selftest.py         # nothing else broke
```

Both calibrators rewrite their control file on every run — there is no
`--write` flag — so re-run them only when the population changes, and read the
diff.

## Basis warnings, collected

1. **Runtime is measured on renders, judged on drafts.** The x1.046 bridge is
   measured, median of 8, spread −8%/+9%. A verdict within ±1.6 min of the
   ceiling is inside that error.
2. **One render is in the absolute population and out of the conversion
   population**, because its `final.mp4` is real and its paired draft is not
   the draft it was rendered from.
3. **Judgment references are measured by sentence; the gate judges by line.**
   The x2.05 conversion is measured on our own two drafts (2.062 and 2.038),
   never on the references, which have no lines.
4. **Two instruments are both called "judgment share"** — classifier-only in
   `judgment_control.json`, label∧classifier in the gate. The floor derivation
   uses the first as an upper bound; the ceiling siting uses the second. They
   are not interchangeable.
5. **The judgment ceiling, the peak rule, the anchor-clean rule, the motif
   budget and the tic bars are DECISIONS**, sited on observed defects in our
   own work. Only the run cap (≤2) and the judgment floor (0.15) rest on the
   reference corpus.
6. **n=5 references, n=9 renders, n=2 drafts.** Every bar here is a bar on a
   small sample, and the first genuinely new draft that fails one should be
   checked against the bar before it is checked against itself.

> **Exclusion rule, stated once.** Spread by the SAME 1.5xIQR rule on both: absolute minutes 1.251x with one render dropped (9.12 min, below the lower fence 11.57), share 2.180x with NOTHING dropped - 6.9% is not an outlier among shares. An earlier version of this line said 1.573x, which came from removing that render from the share population BY HAND; the rule does not justify it, and the honest comparison is the stronger one.
