# Scripting pre-flight checklist

MANDATORY. The agent MUST complete this checklist before declaring any
draft.json ready for render. A passing rule-based audit (binding / tags /
coverage / continuity) is NECESSARY but NOT SUFFICIENT - the IT 2017 recap
passed every audit check and still shipped 14 viewer-visible mismatches (see
projects/it2017/regression_cases.md). This checklist closes the gap the audit
cannot see.

## How to use it

1. Do NOT declare draft.json "ready" or run render until every item below is
   answered YES.
2. Record the answers explicitly. Write them to a file named
   `projects/<project>/scripting_checklist.md` (copy this template, fill in
   YES/NO + evidence per item). If any item is NO, the draft is NOT ready -
   fix it and re-check.
3. "YES" requires EVIDENCE, not assertion. For each item, note how you verified
   (e.g. "compared clip_start times across lines 4-62, all increasing except
   narrative_jump lines 24, 47"). An unevidenced YES counts as NO.
4. These items map to the mandatory scripting rules S1-S5 in
   docs/TAGGING_GUIDE.md. Read that section first.

## The checklist

Answer YES / NO with evidence for each:

- [ ] **C1 (Rule S1 - footage-first):** Every line's clip is ALREADY in
  broll.json or shots.json, with both `depicts` and `chars` populated per
  TAGGING_GUIDE.md. No line references an un-catalogued clip.
  EXCEPTION (Gap 3 / S9): a SILENCE beat carries no spoken narration. It is
  exempt from the CLAIM/binding-audit requirement (narration=""). BUT it MUST
  still be a DRAFT LINE with `narration_silence_seconds` set and empty
  narration - the renderer iterates draft lines, so a silence tagged only on a
  shots.json shot (with no draft line) is silently DROPPED at render (visual
  hold missing, music never swells - the 2026-07-01 Interstellar bug). See
  TAGGING_GUIDE S9 for the exact draft-line shape. Every NON-silence shot still
  binds a normal narrated line.
  Evidence: ____________________

- [ ] **C2 (Rule S2 - chronology):** The body of the recap is in chronological
  source-time order. Only the intro hook (first 1-2 lines, max 3) is exempt.
  After the hook, clip source-times increase monotonically EXCEPT on lines
  marked `narrative_jump: true`.
  Evidence: ____________________

- [ ] **C3 (Rule S3 - no replay):** No clip is used more than its reuse cap
  (MAX_REUSE = 2, MAX_REUSE_HERO = 2), and no family is used more than
  MAX_FAMILY_USES = 2. Checked against the validator's reuse histogram.
  Evidence: ____________________

- [ ] **C4 (Rule S4 - audio-must-have-video):** Every narration claim describes
  what the footage SHOWS, not what is implied, off-screen, or merely nearby in
  the scene. No line asserts an event whose visual is absent.
  Evidence: ____________________

- [ ] **C5 (Rule S5 - subject-on-screen):** Every named character is VISIBLE in
  the bound clip during their mention (the clip's `chars` contains them and is
  accurate to who is actually on screen).
  Evidence: ____________________

- [ ] **C6 (sub-window concern):** For pool clips with span > 5s that contain
  multi-stage content, the bound line claims ONLY what is visible across the
  ENTIRE window - not just one stage. (Render plays a seeded sub-window; a line
  claiming a single stage of a multi-stage clip may not see that stage.)
  Evidence: ____________________

- [ ] **C7 (no orphan transition):** No "walk-away," "transition," or bridging
  line is bound to a clip that is unrelated to the surrounding lines. Bridge
  lines must connect the actual scenes before and after them.
  Evidence: ____________________

- [ ] **C8 (Intro hook unit):** Skeleton includes U01 hook unit with
  narrative_jump=true. Unit covers 60-80 word hook over atmospheric setup
  footage. Format includes: (a) atmospheric setup statement, (b) tension or
  mystery line, (c) channel branding + film title introduction, (d) thematic
  teaser line. No spoiler content. Bound to early-film atmospheric footage,
  not climax/reveal shots.
  Evidence: ____________________

- [ ] **C9 (Outro CTA unit):** Skeleton includes final unit (U_outro) covering
  40-60 word closure. Format includes: (a) thematic takeaway line synthesizing
  film's central question, (b) thanks-for-watching statement, (c) like +
  subscribe call-to-action. Bound to closing or post-climax footage (ambiguous
  ending shots, aftermath shots, or final atmospheric beats).
  Evidence: ____________________

- [ ] **C10 (Censor coverage):** All catalogued shots reviewed for explicit
  content. Each clip with blood/gore/nudity/explicit drug use tagged with
  appropriate censor level (blur_light/blur/blur_heavy) per S7 rules.
  Unflagged explicit content = audit failure.
  For any shot using a PARTIAL blur (S8 censor_region): the rectangle was
  verified against zoom frames to COVER the explicit content across the entire
  4-6s clip (no exposure on any frame), coordinates are in output-canvas pixels
  (top-left origin), and width/height > 0. If no single stable rectangle covers
  it, the shot uses whole-frame blur instead (region absent). Region present
  but mis-covering = audit failure.
  Evidence: ____________________

- [ ] **C11 (Rule S9 - silence usage):** Any silence shots
  (narration_silence_seconds) are EARNED - each lands on a peak emotional beat,
  iconic shot, or action payoff, not on a plot-carrying moment the viewer needs
  explained. Duration within 3-30s (schema caps at 30). No two silence shots
  back to back. Count is restrained (about 2-4 per recap). None placed before
  the audience is invested (not in the first ~minute after the hook). If there
  are zero silence shots, this check is trivially satisfied (silence is
  optional).
  Evidence: ____________________

- [ ] **C16 (DRAFT-TARGET - real-rate depth):** The finished draft's REAL-RATE
  runtime estimate meets the declared tier's floor, and its capacity fill is in
  the healthy band. Read the `[DRAFT-TARGET]` block from `recap.py draft`:
  - No `[DRAFT-UNDER-TARGET]` warning (real-rate estimate >= tier floor:
    recap 9 min / fuller_recap 13.5 min / video_essay 17 min), OR an explicit
    note explaining why a shorter runtime is right for this film.
  - No `[DRAFT-UNDERFILL]` warning (capacity fill >= 65%; target band 70-85%).
    If fill is low, enrich the surfaced units (the gate lists which beats have
    the most unused shot capacity).
  - If `[DRAFT-OVERFILL]` fires (fill > 90%) AND the real-rate estimate is under
    the tier floor, DO NOT just pad existing lines - they are already near
    capacity. Gain runtime by binding more catalogued shots or adding earned
    silence, not by pushing every shot into slow-motion.
  IMPORTANT: trust the REAL-RATE figure, not the conservative 170-WPM estimate.
  The calibrated Andrew +22% voice speaks at ~3.5 w/s (~211 WPM), so the
  conservative estimate overshoots real runtime by ~24%. A draft that reads
  "15 min conservative" may only run ~12 min for real.
  Evidence: ____________________

## Stage 2 depth gates (catalogue-stage, run BEFORE authoring)

C12-C15 are checked at the END of Stage 2 (catalogue), not at draft time. They
ensure the catalogue is full enough to author against before any line is
written. Run `python -m pipeline.catalogue --project NAME --coverage` and
record the report. These map to TAGGING_GUIDE rule S10.

- [ ] **C12 (S10 - depth floor met):** The catalogue's total shot count is AT OR
  ABOVE the declared tier's floor (recap 60+ / fuller_recap 90+ /
  video_essay 110+). **There is no ceiling.** The catalogue is a MENU the draft
  selects from, and LINE count - not shot count - determines runtime; every line
  still has to bind to a catalogued shot (BINDING-INTEGRITY), so more shots is
  more choice, not more obligation. A catalogue cannot be "too full". The tier is
  declared via `depth_target:` in beats_proposal.md (or correctly inferred from
  the Target runtime). No `DEPTH-TOTAL` warning, OR an explicit note explaining
  why fewer shots is right for this film.
  (Ceiling removed 2026-08-31: it contradicted the C13 per-beat floor - N beats x
  per_beat[0] exceeded the ceiling above ~43 beats - and had already been broken
  in the other direction by two shipped films, Superbad 183 and Gia Tai Cua Ngoai
  280. See docs/GATE_CANDIDATES.md "DEPTH-TOTAL ceiling".)
  Evidence: ____________________

- [ ] **C13 (S10 - per-beat floor):** Every numbered beat has >= 2 shots, OR
  each single-shot beat carries a one-line justification (a pure establishing
  wide, a single held reaction). No unreviewed `DEPTH-UNDER` warning. Average
  shots/beat is within the tier's per-beat band.
  Evidence: ____________________

- [ ] **C14 (S10 + S6 - climax/action coverage):** Every [S6] action/climax
  beat has >= 3 distinct shots (initiation / escalation / peak / aftermath). No
  `DEPTH-CLIMAX` warning. Every 2+ character action beat has a reaction or
  emotion shot catalogued (no unreviewed `DEPTH-REACTION`).
  Evidence: ____________________

- [ ] **C15 (S10 - sub-moment + motif coverage):** For each beat, the
  sub-moment enumeration (main action / reactions / motifs / setting) was
  written and the catalogued shots cover the enumerated moments. Declared
  motifs appear in at least one catalogued shot (no unreviewed `DEPTH-MOTIF`).
  Evidence: ____________________

## Gate

Stage 2 gate (catalogue): C12-C15 reviewed (warnings resolved or each one
explicitly justified) -> the catalogue is ready to author against.

Draft gate (authoring): if all of C1-C11 AND C16 are YES with evidence -> draft
is ready for render. C1-C11 close the content/binding gaps; C16 (DRAFT-TARGET)
closes the depth/runtime gap so the recap actually hits its declared tier length
at the real voice rate.

If ANY item is NO (or YES without evidence) -> not ready. Fix and re-run the
relevant checklist section from the top. Do not author against an
under-catalogued Stage 2, and do not render a draft that fails the C1-C11 + C16
gate.
