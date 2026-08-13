# Gone Girl (2014) - Stage 5 Validation Report

Date: 2026-06-16. Draft: 55 lines, 1413 words, est. ~8.3 min at 170 WPM
(projects to ~6:30-7:00 at default Andrew TTS ~214 WPM, matching Prisoners scope).
Pipeline: `recap.py draft --project gonegirl2014`. Exit code 2 (warnings-only,
no hard failures).

## Pipeline validation results

### Binding audit ([VOICE-VISUAL])
- 52 visual lines checked: **52 verified matches, 0 mismatches, 0 unverified**.
- Every line's claim.type is present in its bound shot's depicts; every named
  claim.subject is present in the bound shot's chars. Footage matches narration.

### Tag-quality audit ([TAG-QUALITY])
- **clean** - 0 TAG_TOO_GENEROUS, 0 TAG_TEMPORALLY_AMBIGUOUS.
- All 58 catalogued shots within discipline (single primary depict each).

### Coverage audit
- **0 gaps** - all units within word budget, all must_cover satisfied.
- All 36 catalogued beats covered; every skeleton unit (U01-U18, U_outro)
  addressed by line.covers.

### Continuity audit
- **2 soft warnings** (LARGE_JUMP), both forward source-time act-boundary
  ellipses, accepted by design (see below).

### Audit coverage
- Shots tagged with depicts: 58/58 (100%).
- Draft lines with claim: 55/55 (100%).

## SCRIPTING_CHECKLIST C1-C10

All PASS:
- **C1 footage-first:** every line binds to an exact shots.json clip.
- **C2 chronological:** non-hook lines L04-L55 strictly forward in source time;
  only U01 hook (L01-L03) has narrative_jump=true.
- **C3 no-replay:** no clip used >2x; U18 (02:23:34) and U_outro (02:24:18) bind
  to different shots within beat 36 (no consecutive same-clip body replay).
- **C4 audio-has-video:** every visual line's claim.type is in its bound shot's
  depicts; no off-screen content invented.
- **C5 subject-on-screen / face honesty:** every named subject is in the bound
  shot's chars. The 3 dark/aftermath shots carry NO character claim
  (requires_visual=false, subject=None): L36 (01:38:42 robbery aftermath),
  L47 (02:05:05 Desi murder aftermath), L48 (02:05:27 bloodied drive).
  These render under censor and/or show no verifiable face.
- **C6 sub-window:** all bound shots are single-depict (no multi-stage ambiguity).
- **C7 no orphan:** every line maps to a known skeleton unit; coverage 0.
- **C8 intro hook:** U01 (3 lines, narrative_jump=true, ~80w) - atmospheric
  setup + mystery + Serabudabu branding + title + thematic teaser. No twist leak.
- **C9 outro CTA:** U_outro (1 line, ~55w) - thematic closure (marriage as
  performance) + thanks + like/subscribe, bound to the closing bookend shot.
- **C10 censor coverage:** all explicit content flagged at the catalogue (S7):
  7 censor clips (B28 blur, B29 x3 blur/blur_heavy, B30 blur_light, B34
  blur_light). Murder narration is tag-honest with no lurid detail; blur applies
  at render. No unflagged explicit content.

## Twist discipline verification
- **L01-L21 (beats 1-15):** Amy framed purely as victim/missing. Diary beats
  hedged: "Amy's diary fills in the years... It tells us" (L14), "according to
  her account the marriage slowly curdles" (L15). No orchestrator leak.
- **L22 (beat 16):** explicit pivot - "everything we thought we understood falls
  apart. Because Amy is alive... The grieving wife was a performance."
- **L23-L55 (beats 16-36):** Amy framed as architect throughout.
- Cool Girl (L28): faithful paraphrase, zero verbatim, profanity avoided.
- Pregnancy thread: claimed L18 -> paid off L53 (stored-sperm, used as leverage).

## Accepted-by-design: 2 LARGE_JUMP soft warnings

### 1. L11 -> L12 (+710s, ~11.8 min forward)
- Gap: L11 (first police interview, 00:15:18, beat 7) -> L12 (Desi Collings
  raised as a suspect, 00:27:08, beat 8).
- Classification: chronological recap ELLIPSIS. The recap skips ~12 min of
  procedural runtime (early search logistics) that has no catalogued footage to
  bridge without fabricating a clip.
- Decision: NOT setting narrative_jump=true. The jump is forward/chronological;
  narrative_jump is reserved for true flashback/parallel-action semantics.
  Mislabeling a standard time-skip would corrupt the flag for future films.

### 2. L16 -> L17 (+1131s, ~18.9 min forward)
- Gap: L16 (search HQ / pressure on Nick, 00:35:09, beat 11) -> L17 (vigil and
  press conference, 00:54:00, beat 12).
- Classification: chronological recap ELLIPSIS across the Act 1 -> Act 2
  boundary. The recap compresses ~19 min of mounting-investigation runtime; no
  catalogued footage bridges the window.
- Decision: same as above - forward/chronological, NOT a flashback, so
  narrative_jump is NOT set. Footage is real, chars correct, soft warning only.

Both mirror the Prisoners pattern (forward act-boundary ellipses shipped as soft
warnings to a successful render). Neither is a C2 violation: source time is
strictly non-decreasing across both.

## Non-blocking linter notes (expected, no fix)
- [NAME] false positives: multi-word proper nouns/title tokens split by the
  per-token check (Dunne, Gone, Girl, David, Fincher, New, York, Officer,
  Amazing, Collings, Cool, Bolt, Schieber). All are real names/title words, not
  invented. Same class of notes Prisoners shipped with.
- [VISUAL-MEMORY] lines 40-42 (~110 min) and 46-48 (~124 min): the S6 multi-shot
  sequences (Sharon-interview cluster; Desi murder cluster). These are DISTINCT
  stages by design (S6 action coverage), not the same remembered action.

## Status (Register A): ACCEPTABLE FOR RENDER
binding 0 / tags 0 / coverage 0 / continuity 2 soft (both by design). C1-C10 all
PASS. Twist discipline verified. Rendered to final_registerA.mp4 (6:38, 1080p).


## Register B re-work (2026-06-16) - Light Register B per docs/STYLE_GUIDE.md

Driver: STYLE_GUIDE.md introduced; channel positioned for engaged-commercial
(Register B) recaps. User chose Light Register B for the Gone Girl restart.
Register A artifacts preserved: draft.registerA.json, script.registerA.txt,
final_registerA.mp4.

### Draft changes (Register A -> Light Register B)
- 55 lines / 1413 words  ->  60 lines / 1532 words. Runtime ~6:38 -> est ~7:00-7:30.
- Interpretive layer added (Light tier: 2-3 context lines per major character,
  2 earned theme lines, 3 retention prompts, Register B hook). New lines bind to
  existing catalogued shots (max clip reuse held at 2).
- Hook rewritten to Register B: rhetorical question ("How well do you really
  know the person lying next to you?") + visual-intrigue + branding (L01-L03).
- Character context (G1, all bound to establishing footage):
  L07 (meet-cute -> charm as performance), L12 (Amazing Amy psychology over the
  book-launch shot), L14 (Nick's distance = inattention, not murder),
  L19 (marriage decline = identity loss, diary-hedged), L44 (Desi: one cage to
  another), L47 (Nick learns to perform like Amy, over the watching shot).
- Earned theme lines (G5, after establishing beats): L34 (Cool Girl ->
  "the real horror ... the woman Nick loved was a role"), L60 (closure ->
  "marriage as performance ... the people who know us best can destroy us").
- Retention prompts (sec 3, 3 total, G3-safe): L26 ("the one fact the police do
  not have yet" - teases twist, no leak), L39 ("a weakness she did not see
  coming"), L49 ("she has only one way out").

### G1-G5 self-verification (authoring-time; audit cannot verify interpretation)
- G1 visible-basis: every interpretive line binds to a shot that establishes its
  basis; binding audit verified all 60 lines (0 mismatch / 0 unverified).
- G2 within-text: all readings (performance/identity/control) are the film's own.
- G3 twist discipline: pre-twist interpretive lines (L07/L12/L14/L19) and the
  retention prompt (L26) leak NO post-twist info; diary beats stay hedged
  ("the diary suggests", "according to her account").
- G4 climax restraint: twist (L27-L28) and Desi murder (L51) kept QUIET - no
  "shocking twist" inflation; footage carries the weight.
- G5 earned themes: both theme lines placed AFTER their establishing beats.

### Validation (Register B)
- binding 0 mismatch / 0 unverified (57 visual lines verified).
- tag-quality clean; coverage 0 (skeleton target_words re-planned to the
  Register B distribution, tolerance 0.3); C1-C10 all PASS.
- No READ-ALOUD or CLARITY warnings.
- 2 soft continuity warnings, both accepted by design (same forward act-boundary
  ellipses as Register A, line numbers shifted by the added lines):
  - L14 -> L15 (+710s): first interview (00:15:18, b7) -> Desi raised
    (00:27:08, b8). Forward recap ellipsis, not a flashback.
  - L20 -> L21 (+1131s): search HQ (00:35:09, b11) -> vigil (00:54:00, b12).
    Forward ellipsis across the Act 1 -> Act 2 boundary.
  narrative_jump NOT set (forward/chronological, not flashback).

### Status (Register B): ACCEPTABLE FOR RENDER
binding 0 / tags 0 / coverage 0 / continuity 2 soft (both by design). C1-C10
PASS. G1-G5 self-verified. Light Register B per STYLE_GUIDE.md.


## Viral hook re-work (2026-06-16) - intro_hook.md Variant B

Driver: intro_hook.md updated with a Variant B (Viral) hook pattern. The
template's first Gone Girl example revealed the twist ("Amy is alive..."),
which contradicted the template's own anti-spoiler rules and our twist
discipline; the template example was corrected, and U01 rebuilt to the
corrected, spoiler-preserved version.

### U01 rebuilt (3 lines -> 4 lines, 80 words, narrative_jump=true)
- L01 COLD OPEN: bound to the bloody-return shot (02:06:15, B31) per the
  Variant B binding caution ("can show Amy bloody return but NOT Amy driving
  alive"). Narration: "On the morning of their fifth anniversary, Amy Dunne
  walked out of her house and never came back." Peak-intrigue visual; NO twist.
- L02 STAKES: "The investigation that follows will tear her husband's life
  apart - and the truth ... will be worse than anyone could imagine."
  (00:08:35, ransacked house.)
- L03 QUESTION: "How well do you really know the person sleeping next to you?"
  (00:00:24, opening.)
- L04 BRANDING + TITLE + PROMISE: "I'm Serabudabu, and today we're diving into
  Gone Girl ... where every clue is a lie, and the truth comes at a cost."
  (00:09:32.)

### Twist discipline in the hook (CRITICAL)
- Hook does NOT reveal that Amy is alive or that she planned it. The cold-open
  image is the bloodied RETURN (an ambiguous victim-coded moment to a first-time
  viewer), framed by the disappearance line. Reveal is still reserved for U09.
- The cold-open visual is allowed per Variant B binding rules; the verbal layer
  teases without resolving.

### Coverage note
- U01 must_cover extended to include beat 31 (the cold-open footage). Coverage
  audit clean (the hook's covers=31 now matches the unit's must_cover).
- New line count: 60 -> 61 lines, 1532 -> 1526 words. Runtime est ~7:13.

### Validation (viral hook)
- binding 0 mismatch / 0 unverified; tags 0; coverage 0; C1-C10 PASS.
- 2 soft continuity warnings (now L15->L16 and L21->L22 after the +1 hook line),
  same forward act-boundary ellipses, accepted by design.

### Status (viral hook): ACCEPTABLE FOR RENDER
binding 0 / tags 0 / coverage 0 / continuity 2 soft (by design). C1-C10 PASS.
Variant B viral hook, twist preserved. Hook Quality Checklist (intro_hook.md)
all checked.
