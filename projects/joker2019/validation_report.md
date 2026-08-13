# Joker (2019) - Stage 5 Validation Report

Date: 2026-06-18. Draft: 58 lines, 1386 words, est. ~8.2 min at 170 WPM
(projects to ~6:30-7:00 at default Andrew TTS ~213 WPM). Register B (Medium).
Pipeline: `recap.py draft --project joker2019`. Exit code 2 (warnings-only, no
hard failures).

## Pipeline validation results

### Binding audit ([VOICE-VISUAL])
- 52 visual lines checked: **52 verified matches, 0 mismatches, 0 unverified**.
- Every visual line's claim.type is in its bound shot's depicts; every named
  claim.subject is present in the bound shot's chars.
- Non-visual lines (6 establishing/aftermath + 3 silence) carry
  requires_visual=false / subject=None and are correctly outside the binding set.

### Tag-quality audit ([TAG-QUALITY])
- **clean** - 0 TAG_TOO_GENEROUS, 0 TAG_TEMPORALLY_AMBIGUOUS across 62 shots.

### Coverage audit
- **0 gaps** - all 20 units within word budget, all must_cover satisfied.
- All 37 catalogued beats covered; every unit (U01-U19, U_outro) addressed.

### Continuity audit
- **1 soft warning** (LARGE_JUMP), a forward source-time act-internal ellipsis,
  accepted by design (see below).

### Schema validation
- draft.json valid; skeleton.json + shots.json load clean (62 shots incl.
  6 partial-blur regions + 3 narration_silence_seconds; all enums valid).
- names.json: 12 characters; 0 chars in draft missing from names.json.

### Audit coverage
- Shots tagged with depicts: 62/62 (100%). Draft lines with claim: 58/58 (100%).

## SCRIPTING_CHECKLIST C1-C11

All PASS:
- **C1 footage-first:** every line binds to a catalogued shot. SILENCE EXCEPTION
  (S9): L24 (B14), L42 (B26), L56 (B36) carry narration_silence_seconds and bind
  no narration line - exempt from line-binding. Every NON-silence line binds.
- **C2 chronological:** non-hook lines L04-L58 strictly non-decreasing source
  time; only U01 hook (L01-L03) has narrative_jump=true.
- **C3 no-replay:** no clip used >2x; U19 (01:52:40) and U_outro (01:53:40) bind
  different shots within beat 37.
- **C4 audio-has-video:** every visual line's claim.type is in its bound shot's
  depicts; no off-screen invention.
- **C5 subject-on-screen / face honesty:** every named subject is in the bound
  shot's chars. Face-unverifiable / no-character shots carry subject=None:
  L04 (Gotham establishing), L24/L42/L56 (silence holds), L25 (city reacts, TV/
  crowd), L39 (Randall aftermath), L52/L53 (riot crowd + masked-gunman setup -
  the gunman is masked, S5).
- **C6 sub-window:** all bound shots single/double-depict (no multi-stage
  ambiguity); tag-quality clean.
- **C7 no orphan:** every line maps to a known skeleton unit; coverage 0.
- **C8 intro hook:** U01 (3 lines, narrative_jump, ~76w region) - viral cold
  open (Arthur's beating + the clown) + "what happens to a person the world
  decides does not matter?" + Serabudabu branding + title + society-theme tease.
  NO twist spoiler (Sophie/reality untouched).
- **C9 outro CTA:** U_outro - thematic closure (society makes its monsters;
  ambiguity left to the viewer) + thanks + like/subscribe, bound to the closing
  Arkham-corridor shot.
- **C10 censor coverage:** all explicit content flagged at the catalogue (S7/S8):
  13 censor flags (7 whole-frame, 6 partial-region). Violence narration is
  G4-restrained, no lurid detail; blur applies at render. Partial-region coords
  are generous estimates - visual spot-check recommended at render for the
  Penny smother (B28) and Murray headshot (B33) rectangles.
- **C11 silence usage:** 3 silence shots, all earned (B14 bathroom dance ~22s,
  B26 stairway dance ~22s, B36 Joker on car ~13s). ~57s total = ~12% of an ~8
  min recap (under 20% cap). None back-to-back; first at U08 (beat 14, after the
  audience is invested). Durations within 3-30s.

## Twist discipline verification (unreliable narrator, alpha)
- **U01-U09 (pre-reveal):** Sophie (L15/L16/L26) narrated as REAL. Leak scan for
  imagined/delusion/not-real/etc found ZERO Sophie leaks before U10. (One
  scanner hit on "fantasy" at L13 is a FALSE POSITIVE - it describes the Murray
  DAYDREAM, B07, correctly framed as Arthur's fantasy, not a Sophie leak.)
- **U10 (the pivot):** explicit - "But Sophie was never real. The entire
  relationship was in his head - he imagined all of it." (+ L34 reinforce).
- **U11-U19 (post-reveal):** narration acknowledges Arthur's unreliable
  perception ("we can no longer trust anything we have been shown").
- **U19 (Arkham ending):** ambiguity PRESERVED - "The film never tells us how
  much of what we saw was real... and it refuses to. That uncertainty is the
  point." Narration does NOT decide delusion-vs-real. Honors the film's intent.

## Accepted-by-design: 1 LARGE_JUMP soft warning

### L31 -> L32 (+710s, ~11.8 min forward)
- Gap: L31 (Wayne Manor gate, 00:53:40, beat 20) -> L32 (Wayne Hall benefit
  confrontation, 01:05:30, beat 21).
- Classification: chronological recap ELLIPSIS within Act 2. The recap skips
  ~12 min of runtime (the Sophie-date / open-mic / Murray-mocks material that
  the draft already covered earlier in U09, plus connective scenes) between the
  manor visit and the benefit confrontation. No catalogued footage bridges the
  01:54-01:05 window without fabricating a clip.
- Decision: NOT setting narrative_jump=true. The jump is forward/chronological;
  narrative_jump is reserved for true flashback/parallel-action semantics.
  Mislabeling a standard recap time-skip would corrupt the flag for future films.
- Status: accepted as a soft warning (exit 2). Same pattern as Prisoners (1 soft
  LARGE_JUMP) and Gone Girl (2 soft LARGE_JUMP), both of which shipped successful
  renders.

## Non-blocking linter notes (expected, no fix)
- [NAME] false positives: multi-word proper nouns / title tokens split by the
  per-token check (Joker, Todd, Phillips, Gotham City, Fleck, Happy, Franklin,
  Wall Street, Thomas Wayne, Manor, Arkham). All are real names/places, not
  invented. Same class of notes Prisoners + Gone Girl shipped with.
- [VISUAL-MEMORY] lines 2/10/11 (~12-16 min cluster): L02 (hook, 00:13:10), L10
  (Penny, 00:12:40), L11 (Murray idol, 00:13:10). These are DISTINCT scenes
  (the hook reuses the couch/Murray shot; L10 is Penny dialogue; L11 the Murray
  show) - the hook's reuse of an early shot is by design (Variant B cold open
  pulls from later/atmospheric footage). Acceptable.

## Pipeline change this stage
- pipeline/draft.py (~line 114): added the Gap 3 / S9 SILENCE EXCEPTION so a
  line with narration_silence_seconds is exempt from the empty-narration check.
  Without it, silence lines fail validation. Completes Gap 3's validator
  integration. To be committed alongside the Joker artifacts.

## Status: ACCEPTABLE FOR RENDER
binding 0 / tags 0 / coverage 0 / continuity 1 soft (by design). C1-C11 all
PASS. Twist discipline verified (no Sophie leak pre-U10; U19 ambiguity
preserved). S9 silence (3 shots) + S8 partial blur (6 regions) tagged. Paused
for approval before Stage 6 render.
