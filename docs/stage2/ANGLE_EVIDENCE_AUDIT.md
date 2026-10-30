# Angle evidence audit — Tokyo Drift (2006)

Derived 2026-10-30 by an auditor given **only** the beat map
(`beats_proposal.md`, 109 beats) and the angle's one-sentence thesis. It was
not shown the previous mapping and was not told which beats were assumed to
deliver which slot.

Every quote below was then verified **deterministically** as a verbatim
contiguous substring of the named beat's own `what` text by
`pipeline.beats_spec.quote_supported`. 12 of 12 verified. The previous
mapping fails the same check.

## Why this document exists

The angle's anchors and hook-promise mappings were trusted exactly as
written, and one was wrong:

```
"before he has learned to turn"  ->  B47 / B52 / B53
```

| beat | what the beat map actually says | delivers "learned to turn"? |
|---|---|---|
| B47 | "the long-haired man explains that DK's uncle takes a cut of everyone's action on his turf" | no — territory and money |
| B52 | "he stops at the red Evo, and the long-haired man hands it to him because he represents him now" | no — a car handover |
| B53 | "Drift practice in the dockside lot … the watching crowd laughs at how badly he drifts" | no — he still cannot drift |
| **B60** | **"Training starts: told to drift by feeling, he runs the hairpins again and again with the mentor coaching from the passenger seat"** | **yes** |

and B60 was listed in the angle under *"compress to a line or hold on
footage"*. Two of three mapped beats did not deliver the promise, the beat
that did was filed as texture, and no gate could see any of it, because every
gate read the angle's **claim** about the beats rather than the beats.

## PROMISES (re-derived)

| promise | beats | strongest | evidence (verbatim) |
|---|---|---|---|
| "before he has learned to turn" | B35, B53, B60 | **B60** | "told to drift by feeling, he runs the hairpins again and again with the mentor coaching from the passenger seat" |
| "one city, one man, and one girl worth losing in front of" | B57, B65, B66 | **B57** | "calls Tokyo his Mexico and admits he lent out the car on purpose" |
| "stops running" | B17, B83, B86 | **B83** | "he caused this and cannot run from it" |
| "only then does he win" | B91, B101, B102 | **B101** | "shoves the rival wide instead, putting him off the shoulder into the brush" |

## ANCHORS (re-derived)

| slot | beats | strongest | evidence (verbatim) |
|---|---|---|---|
| emotional peak — being moved on | B11, B13, B46 | **B13** | "his mother tells him they are not moving this time, and he takes the sentence in silence" |
| thesis setup — stop running | B17, B18 | **B17** | "he cannot keep moving away from his own trouble" |
| hook payoff — he cannot drift | B35, B37, B53 | **B35** | "He loses the borrowed car's line mid-drift and grinds it along the concrete" |
| hook payoff — he is taught to drift | B32, B60, B93 | **B60** | "told to drift by feeling, he runs the hairpins again and again with the mentor coaching from the passenger seat" |
| thesis — what he drifts for | B48, B58, B59 | **B58** | "life is choices you never look back on, and that he doesn't drift to win" |
| emotional peak — the girl | B65, B66 | **B65** | "her mother came from Australia to work a hostess bar and died when she was ten, and that DK's grandmother took her in" |
| reveal — the mentor's death | B79, B80 | **B79** | "lands upside down with the mechanic trapped inside and detonates" |
| reveal — the final race | B91, B101, B105 | **B101** | "shoves the rival wide instead, putting him off the shoulder into the brush" |

## Beats commonly assumed to deliver, that do not

The auditor volunteered these without being asked about any of them:

- **B52** — "the long-haired man hands it to him because he represents him
  now" is a car handover, not teaching. Use B60.
- **B42** — "he stays on call whenever he is phoned, in exchange for being
  taught to drift" is a *deal about future teaching*, not the teaching.
- **B47 / B48** — territory, cuts and debt. B48's "what a race is for" edges
  toward thesis and is outclassed by B58.
- **B84** — pressed to get out of Tokyo, walks off without answering. A
  non-answer is not commitment; B83 is where he says it back.
- **B102 / B103** — the celebration, not the win. B101 decides the race.

## What changed in the angle

- "before he has learned to turn": B30/B37 + B47/B52/B53 → **B35, B53, B60**.
- The public-failure anchor moved from B30/B37 to **B35** (failure at the
  wheel with stakes, rather than the crowd mocking him for having no car).
- The thesis-setup anchor narrowed from B17/B18 to **B17** (B18 is house
  rules).
- The Neela anchor narrowed from B64/B65/B66 to **B65** (her own reason).
- The final-race anchor moved from B99/B101 to **B101**.
- "stops running" gained **B83**, which the previous mapping did not contain
  at all.
- **B60 was removed from the footage-only list.**

## How the gate uses this

`[ANCHOR-EVIDENCE]` in `pipeline/pacing_gates.py`:

1. every anchor and promise must carry an `evidence:` quote — **error** if
   absent;
2. the quote must be a verbatim substring of one of the named beats' `what`
   text — **error** if not, with the closest beat and its word overlap named;
3. no beat may be both load-bearing and listed as secondary/footage-only —
   **error**;
4. this document must exist and must cover every promise clause and every
   anchor beat — **error** if a mapping is not audited.

Rule 4 is what makes the semantic judgement a required artifact rather than a
guess. A first version of the gate tried to check "does this beat deliver this
promise" by content-word overlap between the clause and the evidence, and
reported 0% for all four promises — because "before he has learned to turn"
shares no literal words with "told to drift by feeling". A poetic four-word
clause cannot be matched lexically against prose. The overlap check is kept
only as a warning on anchors, whose `kind | why` text is long enough for it to
mean something.
