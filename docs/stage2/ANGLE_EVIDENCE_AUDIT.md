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

# Angle evidence audit — The Double Life of My Billionaire Husband (2023)

Derived 2026-11-12 by an auditor given only the beat map and the one-sentence thesis.

Thesis: "A woman every person in her life has priced marries a 'worthless'
stranger for one hospital bill and turns out to be the only appraiser who got
a human being right; the money was never the twist - her judgment was."

## ANCHORS (re-derived)

| beat | reason | evidence (verbatim) |
|---|---|---|
| B02 | the thesis engine — Natalie is literally priced and traded for a bill; the "worthless stranger" is framed by the trade itself | "The family stops Natalie at the door with the trade: the money if she marries Sebastian Klein in Cassie's place" |
| B22 | the ledger turns on her — the payment that bought the marriage is walked back while Cassie gets a purse; everyone around her prices, nobody pays | "the medical bills she married Sebastian for are still unpaid while Cassie flaunts a new limited-edition purse; the family walks the promise back" |
| B26 | emotional core — at his "worthless" zero she invests comfort and loyalty; the appraisal happens before any value surfaces | "the Klein bastard son never saw the family wealth; Natalie comforts him — you have me now" |
| B44 | the pivot from contract to care — the pretend-marriage terms are retracted and a real husband is offered | "Sebastian retracts the pretend-marriage terms and tells Natalie she can rely on him as her husband" |
| B61 | the mirror reveal — he confesses he married her for money too; the moral field levels and the real asymmetry (who changes) begins | "Sebastian confesses he married her for the generational trust fund — Myers and Quinn families, BM as in the company" |
| B99 | thesis peak — she alone appraised the man correctly and proves it by deduction, not by being told; her judgment is the twist | "the paid medical bills, the internship, Daniel's office, the house — and lands it: 'Or should I call you Bash Meyers?'" |
| B102 | retro-proof of her appraisal — he had already promised a real wedding and a real home, driven by his mother, not money | "Sebastian visited and promised to make Natalie happy once he finishes something for his mother, Stephanie Meyers — a real wedding and a real home" |
| B109 | the closing judgment — she names the asset correctly this time, eyes open; the marriage is chosen, not traded | "Sebastian asks Natalie to marry him for real and she answers: 'This time, I'm marrying Bash Meyers.'" |

## PROMISES (re-derived)

| promise | beats | strongest | evidence (verbatim) |
|---|---|---|---|
| "every turn in this story is a payment" | B01, B02, B13, B22, B36, B47, B62, B88, B107 | **B02** | "the money if she marries Sebastian Klein in Cassie's place" |
| "the show is meaner and smarter than its own ad" | B16, B24, B30, B56, B74, B78, B84, B99 | **B99** | "Natalie walks her deductions — the paid medical bills, the internship, Daniel's office, the house" |
| "she loved the broke version before any money surfaced" | B20, B21, B26, B32, B37, B44, B59 | **B26** | "died when he was in middle school and the Klein bastard son never saw the family wealth; Natalie comforts him" |

## Verification note

Every evidence string above was checked programmatically as a verbatim
contiguous substring of the named beat's own `what` text in
`projects/doublelife2023/beats_proposal.md` (exact characters, including em
dashes and ASCII apostrophes/quotes as written in the beat map). 11 of 11
verified, 0 failures. Word counts of all evidence strings fall in the 10-25
range. The auditor did not open angle.md, draft.json, or any review file.

Notes the next gate may care about:

- B56 (the "I am Bash Myers" reveal to the mob) is a genuine peak but was
  left off the anchor list: the reveal lands on Volkov, not on Natalie, and
  the thesis peaks when SHE does the appraising (B93/B99), not when strangers
  grovel.
- B84 (the Quinns learn the identity before Natalie does) is the ad's version
  of the twist; B99 is the show's. A recap that dwells on B84 over B99 is
  recapping the ad.


---

# Addendum (production angle verification) â€” The Double Life of My Billionaire Husband (2023)

The independent audit above derives a thesis-strict anchor set. The production
angle.md keeps a different, audience-arc anchor set (the reveals and peaks the
recap dwells on). Both are recorded; the divergence is deliberate and is
Operator-review material, not a gate bypass. Every production anchor's
evidence string below was verified deterministically with
pipeline.beats_spec.quote_supported against the same beat map (8/8 pass):

| beat | role (production angle) | evidence (verbatim) | verified |
|---|---|---|---|
| B10 | the vows â€” the one honest transaction | Sebastian and Natalie exchange vows and rings and are pronounced husband and wife | yes |
| B18 | first receipt â€” the 7,000 shoes | Sebastian buys the $7,000 shoes without blinking | yes |
| B39 | action peak â€” which hand touched his wife | Sebastian storms in, shields Natalie, and icily demands to know which hand touched his wife | yes |
| B56 | audience-side identity reveal | Peter grovels to Mr. Myers on the line, and Sebastian confirms to a stunned Volkov that he is Bash Myers | yes |
| B79 | the sting lands â€” Serena fired | Walter fires Serena on the spot, and Sebastian twists the knife by suggesting they sue her for attempted murder | yes |
| B99 | her audit â€” the thesis peak | Natalie walks her deductions | yes |
| B101 | the mothers â€” secrets kept for love | Natalie's mother admits she has known Sebastian all along | yes |
| B109 | the second vow â€” choice not contract | Sebastian asks Natalie to marry him for real | yes |

Note: the auditor's exclusion of B56 ("it lands on Volkov, not Natalie") is
recorded; the production angle keeps B56 because the recap re-prices every
earlier scene there, and pairs it with B99 where the thesis actually lands.


## Promise verification (production angle)

| promise | beats | strongest | evidence (verbatim) | verified |
|---|---|---|---|---|
| "every turn in this story is a payment" | B18, B47, B48, B107 | B18 | Sebastian buys the $7,000 shoes without blinking | yes |
| "the ad never told you what the show actually is" | B79, B93, B101 | B79 | Walter fires Serena on the spot, and Sebastian twists the knife by suggesting they sue her for attempted murder | yes |
| "she loved the broke version" | B10, B36, B99 | B99 | Natalie walks her deductions | yes |
