# Scripting pre-flight checklist - howtomakemillions2024

Draft: 223 lines (219 narrated + 4 silence), 3,632 words, 222 of 280 shots bound,
all 57 beats represented. Stage: OUTLINE.

Evidence commands: `python recap.py draft --project howtomakemillions2024` and
the per-item checks recorded below.

---

- [x] **C1 (S1 - footage-first): YES.**
  Evidence: every line's `clip_start` is an exact `shots.json` key - checked
  programmatically, 223/223 resolve, 0 synthesized timestamps. Binding audit
  reports `Unverified: 0 lines`, which is only possible if every bound clip
  carries both `depicts` and `chars`. The 4 silence lines are real DRAFT LINES
  with `narration_silence_seconds` set and `narration: ""` (the 2026-07-01
  Interstellar bug), not shots-only tags.

- [x] **C2 (S2 - chronology): YES.**
  Evidence: walked `clip_start` across all 223 lines in written order - zero
  backward jumps. `narrative_jump` is used on zero lines because none is needed:
  the hook (lines 1-3) is bound to 00:00:52.8 / 00:01:10.0 / 00:02:00.4, i.e. the
  film's own opening, so it is in order rather than exempt from it. The one
  flashback (B55, lines 209-211) plays at its true source position 01:53:28,
  which is where the film puts it, so it is also not a jump.

- [x] **C3 (S3 - no replay): YES.**
  Evidence: reuse histogram - 222 distinct shots across 223 lines. Exactly one
  clip is used twice (`clip:01:58:52.0`, the silence hold and then the outro over
  the same final image), which is at MAX_REUSE=2, not over. No family exceeds
  MAX_FAMILY_USES=2; max family count is 2.

- [x] **C4 (S4 - audio-must-have-video): YES, with three declared exceptions.**
  Evidence: binding audit 189/189 verified, 0 mismatches. Claim type is a member
  of the bound shot's `depicts` on every visual-required line (checked
  programmatically, 0 violations). Shots tagged `establishing` / `aftermath` have
  no matching ClaimType, so those 30 lines carry
  `{"type":"narration","requires_visual":false}` rather than a false claim.
  Three lines report information the film carries in DIALOGUE, not in the image.
  Each is bound to the conversation itself and worded as speech being made, not
  as an event being shown:
  - line 9 (00:05:45.0) the diagnosis - bound to the family conversing at the kerb
  - line 110 (01:14:20.0) the property listing - the listing card and the building
    photo ARE visible (verified `frames/zoom/01-14-26`); the name on the advert
    and Amah's denial are reported as things said
  - line 152 (01:20:42.2) R2 - bound to the refusal being spoken
  **The R1 trap was avoided:** no line describes a phone call. See "R1" below.

- [x] **C5 (S5 - subject-on-screen): YES.**
  Evidence: for every line carrying `claim.subject`, the subject is a member of
  the bound shot's `chars` - checked programmatically, 0 violations. Four people
  are never named anywhere in the draft (the elderly man at the big house, the
  bedridden man at the care home, the bearded man with the shoulder bag, the
  young woman in the car); they appear only as roles. `[CLARITY]` flags lines 110
  and 182 for "the man" / "one of them" and is correctly describing a real
  limitation - those two are unnameable, not sloppy.

- [x] **C6 (sub-window concern): YES.**
  Evidence: each line's declared window is trimmed to its own narration duration
  (real-rate x1.25, floor 4.5s) and clamped to the catalogued shot's end, so no
  line claims footage beyond what it describes. Because the claim type is drawn
  from the shot's own `depicts` and this film's shots are single-moment by
  construction (tag audit clean, 0 TAG_TOO_GENEROUS / TAG_TEMPORALLY_AMBIGUOUS
  across all 280), the claim holds across the whole window, not just one stage.

- [x] **C7 (no orphan transition): YES.**
  Evidence: every `transition`-claim line names the places it moves between and
  sits between lines in those places - e.g. line 22 (00:13:29.4, "across town,
  down along the railway, into the old lanes") sits between the Bangkok
  establishing and the arrival at the gate. No bridging line is bound to footage
  from an unrelated scene.

- [x] **C8 (Intro hook unit): YES.**
  Evidence: lines 1-3, 79 words. (a) atmospheric setup - the hillside and the
  yearly grave-sweeping; (b) tension - the grandson three feet away on his phone;
  (c) branding + title - "This is Serabudabu... How to Make Millions Before
  Grandma Dies"; (d) thematic teaser - "how much of love is arithmetic". Bound to
  early-film footage (00:00:52-00:02:35), no reveal or climax shot, no spoiler.
  Per RULES H2 the hook states the premise flatly instead of manufacturing a
  thriller shape - this film's pull is moral, not informational, and the title
  already discloses the ending.
  Deviation recorded: no `skeleton.json` exists for this project, so there is no
  U01 unit object; the hook is the first three draft lines. `narrative_jump` is
  false because the hook is in chronological order (see C2).

- [x] **C9 (Outro CTA unit): YES.**
  Evidence: line 223, 41 words, bound to `clip:01:58:52.0` - the film's final
  image, post-climax. (a) thematic takeaway synthesising the central question -
  "He wanted a house. What he got was a year, and a receipt for it in her
  handwriting"; (b) thanks-for-watching; (c) subscribe CTA.

- [x] **C10 (Censor coverage): YES.**
  Evidence: all 280 catalogued shots carry `censor: "none"`; no other value
  appears in the file. Two judgement calls were reviewed at catalogue stage and
  recorded in `shots.json._censor_note`: the care-home ward (01:41:33-01:43:13)
  and the deathbed (01:49:30-01:51:20) show feeding/oxygen tubes and terminal
  illness, shot without graphic detail - S7 does not censor implied or
  non-graphic medical content. No body is visible at the funeral; the coffin is
  closed throughout. No partial-blur regions used, so the S8 sub-checks are
  vacuous rather than passed.

- [x] **C11 (S9 - silence usage): YES.**
  Evidence: 4 silence lines, within the 2-4 budget. Durations 12s / 6s / 12s /
  12s, all inside the 3-30s range. Line ids 69, 94, 201, 222 - no two adjacent
  (checked programmatically), and the earliest sits at line 69 of 223, far past
  the hook. Each lands on a held image the film itself holds: the 56-second
  empty room, the shoe-shop close, the 57-second deathbed hold, the final shot.
  None sits on a plot-carrying moment. Full decision record including the three
  rejected claimants is in `draft.json._decisions._2_silence_budget`.

- [ ] **C16 (DRAFT-TARGET): PARTIAL - runtime YES, fill NO and deliberately so.**
  Evidence: `[DRAFT-TARGET] real-rate est: 18.4 min` against the `video_essay`
  floor of 17.0 and band of 18-22. No `[DRAFT-UNDER-TARGET]`.
  `[DRAFT-UNDERFILL] fill 13%` DOES fire and is **not** actioned. This is the
  explicit note the checklist allows, and it is measured rather than asserted:
  fill is words / (bound seconds x 3.5 w/s), so it falls as the source holds its
  shots. Across finished drafts, mean bound-shot duration vs fill scored -
  gonegirl 5.5s -> 109%, interstellar 9.7s -> 71%, shutterisland 17.4s -> 73%,
  superbad 21.7s -> 27%, this film 27.1s -> 13%. Reaching 65% here needs ~66
  narrated words per shot, i.e. ~14,700 words / ~70 minutes of continuous
  talking, or binding ~45 shots instead of 222. Declined under RULES B9 (fill is
  a blind metric for comprehension, never a target) and B12 (do not polish a
  metric already concluded untrustworthy). Full record in
  `draft.json._decisions._1_shot_selection`.

---

## Stage 2 depth gates (re-run after the parser fix)

- [x] **C12 (depth target): reviewed, over band by choice.** 280 shots vs
  110-130. `DEPTH-TOTAL` does not warn (it only fires UNDER). Justification in
  `draft.json._decisions._1_shot_selection`.
- [x] **C13 (per-beat floor): YES.** 57 beats, one below floor - B26 at 1 shot,
  the deliberate single-shot train-home beat argued for in pass 2 and now found
  unaided by `DEPTH-UNDER`.
- [x] **C14 (climax/action coverage): reviewed.** `DEPTH-CLIMAX` fires once, on
  B54 (2 shots). Reviewed and left standing: the passbook beat holds setup and
  reveal, and the film puts the reaction in B55 - read as one sequence the reveal
  carries 7 shots. Not split to clear the flag. `DEPTH-REACTION` passes over 16
  beats.
- [n/a] **C15 (motif coverage): gate RETIRED 2026-08-23.** `DEPTH-MOTIF` was
  removed estate-wide - it greps `action` prose, so it measures presence rather
  than placement and is blind to anything planted in dialogue. Motif discipline
  for this film is the hand-written plant audit in `beats_proposal.md`.

---

## R1 - the trap that was avoided

The reveal-map originally called R1 "the bank call". There is no bank call on
screen. Lines 206-210 narrate what the film shows: he goes through her things
(line 206), finds a savings book with his own name in it (207), the flashback of
a small boy walking home from school with his grandmother (209-210). The two
phone shots are bound (208, 211) and describe only a man standing outside on a
phone. No line asserts a conversation, a clerk, or a disclosure by a third party.

## Gate

C1-C11 YES with evidence. C16 runtime YES, fill declined with a recorded and
measured justification. **Draft is ready for human review, not for unattended
render** - RULES Part F: draft approval and RENDER QA are the two checkpoints a
person cannot skip, and this film's whole last act is exactly the kind of held,
near-wordless material that gates read as fine and eyes do not.
