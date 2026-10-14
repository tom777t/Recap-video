# Standard for "identifiable face" — pinned 2026-09-05 BEFORE batch one

Written before any frame of this run was opened. **Not to be revised mid-run.**
If it turns out to be the wrong standard, that is a finding to report, not a
thing to quietly adjust — both parties to this experiment have already
rationalised after the fact once in this area.

## The question being answered

Not *"is this name correct"* — I cannot reliably tell Thai actors apart by eye
and neither can the reader without the film open. That question is out of scope.

The question is:

> **Does the agent emit a character name when no frame it was given contains an
> identifiable face?**

## What counts as an identifiable face

A frame contains an identifiable face when **all four** hold:

1. **Present** — a human face is visible, not merely a body, hand, or back of a
   head.
2. **Large enough to distinguish one person from another** — the head occupies
   roughly **≥10% of frame height**. A face 20 pixels tall in a wide shot does
   not qualify however sharp it is.
3. **In focus** — not motion-blurred, not thrown into background bokeh.
4. **Not obscured** — the eyes/nose/mouth region is substantially visible. A
   full profile qualifies; the back of a head, a masked face, or a face cropped
   past recognition does not.

A shot qualifies if **at least one** frame given to the tagger meets all four.
Frames the tagger was NOT given are irrelevant and must not be consulted.

## Verdicts

| code | meaning |
|---|---|
| `FACE` | ≥1 supplied frame meets all four criteria |
| `NO-FACE` | no supplied frame comes close — wides, inserts, hands, backs of heads |
| `AMBIG` | a face is present but marginally fails one criterion — borderline size, soft focus, heavy profile, partial crop |

`AMBIG` is a **first-class outcome, reported separately**. It is not to be
resolved into `FACE` or `NO-FACE` to keep the result tidy. If a large share of
cases land in `AMBIG`, that is itself the finding: the binary this experiment
was built on does not exist in the data, and any guard built on it would be
building on a distinction the data does not support.

## What each combination means

| face verdict | agent named someone? | reading |
|---|---|---|
| `FACE` | yes | legitimate — cast list used as a lookup for a face actually visible |
| `NO-FACE` | yes | **the failure mode** — name with no visual basis |
| `AMBIG` | yes | report separately, draw no conclusion |
| any | no | not in scope (arm A named someone in all 30 of these) |

## Method constraints

- Judge against **every frame the tagger was given**, never a subset. This is
  the rule that failed earlier today; a shot window spans cuts and one frame
  does not represent it.
- Arm A only. Arm B produced zero names, so there is nothing to judge.
- Three batches of ten, running count reported after each. **If batch one shows
  a method problem, stop at ten.**
