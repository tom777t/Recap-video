# Lessons

A running log of hard-won lessons from building recaps. Append new lessons
under a dated heading; do not silently rewrite old entries (no git history).


## 2026-06-13 - IT 2017 cleanup session

### Bugs discovered and fixed
- **Family-union false-pass** in binding_audit: audit aggregated chars/depicts
  across all family members instead of checking the specific bound clip. Fixed
  by per-placement check in binding_audit.py. The class of bug, not just IT.
- **Tag-loose mask**: depicts with too many tags or temporally-distinct pairs
  silently passes any matching narration claim. Fixed by adding tag_audit.py +
  TAGGING_GUIDE.md.
- **Content-vs-claim semantic gap**: audit checks type/subject match but not
  semantic content. L44 (Bowers murders father) bound to rock-fight clip - both
  tag "action" so audit passes. Not fixable in rule-based audit; Phase 2 vision
  tagging would help.

### Discipline lessons
- **Tagging discipline is the foundation.** Audit can only be as honest as the
  tags. Tags must describe what is visible in THE clip's window, not the
  surrounding scene or what the script claims.
- **One clip = one primary moment.** Max 1-2 depicts tags. >2 = clip should
  be split.
- **Footage-first workflow.** Catalogue clips before writing skeleton; write
  skeleton bound to cataloged clips; write draft bound to skeleton. NEVER write
  narration referencing un-cataloged footage.
- **Audit + frames + manual QA = three independent verification layers.** Each
  catches different bug classes. Need all three.

### Infrastructure gaps to close
- **No git.** OneDrive incident lost code; manual re-apply introduced bugs.
  Add git ASAP (5-minute task, lifelong value).
- **No lessons doc.** Insights die between sessions. This file is the start.
- **8-pillar consolidation** still pending (currently A-W).
- **Vision Phase 2** waiting until: 2-3 films manually tagged with discipline,
  vision accuracy experiment done (30-min Gemini Flash test on cataloged clips).

### Outstanding for IT
- L44 content bug (Bowers father vs rock fight) - audit-unfixable, accepted.
- Coverage warnings U08, U13 - skeleton calibration issue, not draft defect.

### Process gold standard going forward
1. Frames overview -> identify story beats
2. Frames zoom -> exact timestamps
3. Catalogue (shots.json + broll.json) with tight tags per TAGGING_GUIDE.md
4. Skeleton based on cataloged moments only
5. Draft bound to cataloged clips - if a needed moment isn't cataloged,
   STOP and catalogue first
6. Validate (binding + tags + coverage + continuity all clean)
7. Render
8. Manual QA watch at 1.5x with notepad


## 2026-06-14 - IT 2017 audit/render session

Context: we built a tag-quality audit layer, tightened 27 over-broad tags to
single moments, re-pointed 6 binding mismatches (cataloguing 3 new clips from
source), got the phase-1 audit fully clean (binding 0 / tags 0 / continuity 0),
and re-rendered. Watching the rendered video then revealed 14 viewer-visible
mismatches (see projects/it2017/regression_cases.md). The gap between
"audit-clean" and "video-clean" is the central lesson of the day.

### 1. Audit-clean does NOT equal video-clean
The rule-based audit verifies tag-level claims only. It checks that a line's
claim.type is present in the bound clip's depicts list, and that claim.subject
is present in the bound clip's chars list. It does NOT verify:
- semantic content (does the clip actually depict THIS specific moment, or just
  something of the same type?),
- narrative order (do the clips play in the story's order?),
- render-time sub-window selection (which seeded sub-segment of a clip is
  actually on screen for this line?).
A draft can pass every audit check and still be full of visible mismatches.

### 2. Tagging discipline is necessary but not sufficient
Tight, honest, one-moment tags are required for the audit to mean anything -
loose tags silently mask mismatches (proven today: honest tightening exposed 3
hidden binding errors, raising the count from 3 to 6). But even perfect tags
only let the audit verify TYPE and SUBJECT. They do not make the audit
understand content, order, or render behavior. Discipline raises the floor; it
does not reach the ceiling.

### 3. The audit catches roughly 30-40% of human-visible mismatches
Empirical, based on this session: of the 14 viewer-observed mismatches, only the
subset with a provably-wrong tag (wrong chars on screen, or an
untagged/UNVERIFIED line) is detectable by the rule-based audit. The rest -
render sub-window jitter, order inversion, audio-without-scene, repeat fatigue,
and "right type / wrong content" scene-disconnects - pass the audit cleanly.
Treat a clean audit as "no tag-level errors," not "the video is correct."

### 4. The IT script foundation is out-of-order
The IT 2017 draft jumps around the film's timeline well beyond a single intro
hook. Many lines pull footage from far-apart parts of the movie in an order that
does not track the story. Tagging and re-pointing cannot repair this: even with
perfect one-moment tags and correct bindings, footage that is sequenced
out-of-order still confuses the viewer. The disorder is baked into the script
structure, not the tags.

### 5. Chronological discipline rule for recap scripts
Review-phim (film-recap) style legitimately rearranges scene order ONLY for the
intro hook - at most 1-2 scenes pulled forward to grab attention. After the
hook, the BODY of the recap should follow the source film's chronological
order. Multiple out-of-order jumps throughout the recap create viewer
confusion, and that disorder was a major contributor to IT's quality problems
this session. Rule of thumb: one hook exception, then stay chronological.

### 6. Future films require a footage-first workflow
The order of operations that prevents today's failure mode:
1. Catalogue clips FIRST - watch the source, log real moments with tight
   one-moment tags (depicts + chars verified from frames), with timestamps.
2. Write the skeleton FROM the catalogued moments only - do not invent beats
   that have no footage. If a beat has no clip, either find/cut one or drop the
   beat.
3. Write the draft BOUND to catalogued clips, in chronological order (except the
   hook). Every line points at a real, verified clip from step 1.
This inverts the failure-prone path (write script first, then scramble to find
footage and over-tag clips to make the audit pass). Footage-first makes
missing-footage and scene-disconnect impossible by construction, and makes
chronological order the default.

### Corollaries / open items
- render.py sub-window jitter (seeded sub-segment per line) means even a
  correctly-tagged multi-second clip can show the wrong instant. One-moment,
  tightly-trimmed clips are the only structural fix.
- The audit has no order check. A chronology/continuity check that compares clip
  source-timestamps against narrative order would catch ORDER_INVERSION - worth
  building.
- "Right type, wrong content" (SCENE_DISCONNECT) is the audit's core blind spot.
  No rule-based fix; mitigated only by footage-first cataloguing and human
  review of the rendered cut.
- Always watch the rendered video. The audit is a pre-filter, not a
  certification.


## Failure modes to avoid

These are the canonical "do NOT do this" patterns, drawn from the 14 IT 2017
mismatches in projects/it2017/regression_cases.md. Each maps to a mandatory
scripting rule (S1-S5 in docs/TAGGING_GUIDE.md) and a checklist item (C1-C7 in
docs/SCRIPTING_CHECKLIST.md). Treat the regression_cases.md list as the
authoritative example set of what NOT to do; this section is the index into it.

- **Render sub-window jitter** (regression case 01): a multi-moment clip plays a
  different seeded sub-window per line, so the visible instant does not match the
  line. The IT Georgie meet-vs-bite swap is the canonical example. Avoid via
  one-moment clips and checklist item C6. Rule: tagging discipline (one clip =
  one primary moment).

- **Replay / repeat fatigue** (regression case 02): the Pennywise-as-Georgie
  clip was used ~5 times. Avoid via the no-replay caps (MAX_REUSE = 2,
  MAX_REUSE_HERO = 2, MAX_FAMILY_USES = 2). Rule S3, checklist C3.

- **Wrong character on screen** (regression cases 03, 04): Stanley's intro showed
  someone else; Mike's nightmare showed Bill/Stanley. Avoid via subject-on-screen
  (named character must be visible in the bound clip). Rule S5, checklist C5.

- **Audio without scene** (regression cases 05, 06): the hammer/iron-rod attack
  and Georgie's body were narrated with no matching visual. Avoid via
  audio-must-have-video (rewrite the line to what footage shows, or remove it).
  Rule S4, checklist C4.

- **Order inversion** (regression cases 07, 08): hunt-the-clown and the Beverly
  attack played out of story order. Avoid via the chronological-order rule (body
  follows source-film time order; only the hook and explicit narrative_jump
  lines may break order). Rule S2, checklist C2.

- **Missing footage** (regression cases 09, 10): Beverly's father abuse and Henry
  killing his father had no catalogued footage; lines were written anyway. Avoid
  via footage-first (never write a line for un-catalogued footage; catalogue
  first or drop the beat). Rule S1, checklist C1.

- **Scene disconnect / walk-away** (regression cases 11, 12, 13, 14): the
  walk-away/scatter beat, the compare-notes group discovery, Mike's "ancient
  thing" exposition, and the Bowers intro were bound to clips whose TYPE matched
  but whose CONTENT did not depict the narrated moment. This is the audit's core
  blind spot (type-level pass, content-level miss). Avoid via footage-first
  cataloguing, the audio-must-have-video and no-orphan-transition checks, and
  human review of the rendered cut. Rules S1/S4, checklist C4/C7.

Bottom line: the rule-based audit caught roughly 30-40% of these. The remaining
60-70% are prevented only by the mandatory scripting rules and the pre-flight
checklist - which is why those are MANDATORY, not advisory.


## 2026-06-15 - Prisoners 2013 render + QA session

Context: completed Prisoners 2013 catalogue (51 shots strict discipline) +
skeleton (19 units, chronological) + draft (60 lines, 1359 words) + validation
(all C1-C7 PASS) + render (6:21 with Andrew TTS + ducked music + transition
SFX). Viewer + secondary viewer (friend) QA watch surfaced 6 distinct issues
that workflow had not anticipated. This session's lesson: render-stage
defaults significantly affect output quality even when draft is perfect.

### 1. TTS rate calibration is critical and currently uncalibrated
> SUPERSEDED by Lesson 7 (2026-06-15 final calibration data). Default rate is correct for movie-recap genre; -25% over-corrects.

Andrew voice at Edge-TTS default rate produces ~210-220 wpm narration -
significantly faster than industry standard (150-165 wpm for documentary).
A 1359-word draft projected at 10 min @ 145 wpm rendered at 6:21 instead.
This is ~30-40% under target length. Future films require: (a) explicit
TTS rate parameter, (b) sample test before commit render, (c) per-voice
calibration table built over multiple renders.
Recommended default for English thriller/documentary: rate=-25% (Andrew)
producing ~160 wpm.

### 2. SFX defaults need explicit review per project
Pipeline default added 59 transition whoosh sounds during render - viewer
flagged as distracting for psychological thriller tone. Default-on assumption
violates "minimum required to convey" principle. Future renders should use
--no-sfx flag by default for thriller/drama. SFX appropriate for action/
comedy genres requires conscious opt-in.

### 3. Action sequence coverage is a distinct workflow gap
Stage 5 QA identified 3 action moments where single-line narration over
single shot felt "narrated rather than shown":
- Bob suicide (1 line / 1 shot for 4-stage action: grab + raise + fire +
  aftermath)
- Loki vs Holly gunfight (1 line / 1 shot for full shootout sequence)
- Loki at vigil seeing grieving mothers (passing moment, no dwell)
Workflow now requires S6 (action coverage rule) in TAGGING_GUIDE: action
sequences need 3-4+ catalogued shots minimum, with single discrete moment
per shot.

### 4. Intro/outro are structural, not optional
Original draft used cold-open film-essay structure (no greeting, no channel
intro, no outro CTA). Viewer feedback: hook lacked engagement, ending stopped
abruptly, no channel branding visible. Future films require explicit U01
hook unit (60-80 words) + U_outro CTA unit (40-60 words) as structural
elements, not "if we have words left over."
Skeleton template now mandates these units; SCRIPTING_CHECKLIST C8/C9
enforce them.

### 5. Secondary viewer adds verification value
Self watched + friend watched = independent confirmation of "no scene
mismatches." Single viewer fatigued late in session is prone to satisfaction
bias. Future QA: aim for 2+ independent viewers, or watch self at 2 different
times (initial + fresh next day) before declaring ship-ready.

### 6. Polish surfaces gaps that catalogue/draft cannot anticipate
Render is the first stage where actual viewer experience becomes visible.
Audit clean + draft clean + validation clean does NOT guarantee shippable
output. Render-stage decisions (TTS, SFX, music, hold timing) materially
affect quality. Stage 5 QA is non-skippable and frequently surfaces 4-6
issues requiring re-render. Build re-render time into every project plan.

### 7. TTS rate empirical calibration (Edge-TTS Andrew, en-US)

Today's render experiments produced concrete pacing data (1512-word draft,
SFX off, music 0.16, no captions):

| Rate flag | TTS-rate WPM (estimated) | Final.mp4 WPM (measured) | Length | Subjective feel |
|-----------|--------------------------|--------------------------|--------|-----------------|
| default   | ~214                     | 214                      | 7:04   | Engaging, fast - genre fit |
| -15%      | ~180                     | 149                      | 10:10  | Slow for YouTube recap genre |
| -25%      | ~138                     | 131                      | 11:33  | Sluggish, lost engagement |

(The -10% row was dropped: it was theorized but never actually rendered, so
only measured data is recorded here.)

Note: TTS-rate WPM (narration speed in isolation) differs from
final.mp4 WPM (1512 words / full duration including crossfades/holds).
Both metrics useful for different purposes: rate WPM predicts, final WPM
measures actual viewer experience.

Recommendation: Default rate (no --rate flag) for movie-recap pace.
Andrew's default ~214 wpm matches YouTube high-energy recap genre.
Slowdowns (--rate=-X%) feel unnaturally slow for this format and
should NOT be applied unless specifically testing documentary tone.

Avoid premature rate adjustment based on draft word count theory.
Calibrate by actual viewer perception, not target length math.

This lesson supersedes the earlier Lesson 1 recommendation of
rate=-25%, which over-corrected based on an incorrect "default too
fast" assumption that today's iteration disproved.

### Failure modes added to regression-style awareness:

- **TTS_RATE_DEFAULT_TOO_FAST**: render produces shorter recap than draft
  projected, scenes flash by, viewer feels rushed.
- **TRANSITION_SFX_INTRUSION**: pipeline default SFX feel cheap or distracting
  for non-action genres.
- **ACTION_COMPRESSION**: multi-stage action sequence rendered as single line
  over single shot, viewer hears event without seeing it unfold.
- **MISSING_INTRO_HOOK**: cold-open recap lacks channel branding + viewer
  engagement structure.
- **MISSING_OUTRO_CTA**: recap ends abruptly without thematic closure +
  subscribe/like prompt.

### Updated workflow gold standard:

1. Frames overview -> identify story beats
2. Frames zoom -> exact timestamps
3. Catalogue (shots.json + broll.json) with S1-S6 rules
   **Including S6: action sequences need 3-4+ shots minimum**
4. Skeleton based on cataloged moments only
   **Including mandatory U01 hook + U_outro CTA units (C8/C9)**
5. Draft bound to cataloged clips, chronological + intro/outro frame
6. Validate (binding + tags + coverage + continuity + C1-C9 checklist)
7. Render with explicit TTS rate + SFX flag (calibrate per voice)
8. Manual QA watch at 1x speed with notepad, ideally with secondary viewer
9. Polish re-render if Stage 5 QA surfaces issues (expected, not failure)


## 2026-06-15 (continued) - Workflow gaps surfaced during Prisoners polish

Three additional gaps identified after Stage 5 QA, deferred to next-film
implementation (not retrofit to Prisoners). Recording here for systematic
attention before Film 2 catalogue begins.

### Gap 1: Commercial narration style (craft expansion)

Current workflow produces honest restrained narration (footage-first,
descriptive, no narrator interpretation). This serves the audit's
zero-mismatch goal but produces "documentary recap" tone rather than
"engaging recap" tone. For commercial viability (retention, watch time,
subscriber growth), narration needs:

- Moderate interpretive layer (narrator extracts insight, not just describes)
- Stronger emotional hooks at scene transitions
- Theme statements at key beats (lessons distilled in-line)
- Mid-recap retention prompts ("but what happened next...")
- Rhetorical engagement (occasional direct viewer address)

Target style: moderate (mix descriptive + interpretive). NOT heavy
provocative manipulation (feels cheap), NOT pure restraint (no engagement).

Implementation requirement before Film 2:
- Expand TAGGING_GUIDE or create new STYLE_GUIDE.md with:
  - Narration voice register specifications per genre
  - Allowed interpretive language patterns (with discipline guardrails)
  - Hook construction templates per genre
  - Theme extraction patterns (how to distill lesson from beat)
- Audit must remain compatible: interpretive lines still bind to visible
  content, just with more narrative voice layered on top

### Gap 2: Censor capability for explicit content

Current pipeline has no censor mode. For films with explicit violence,
nudity, or graphic content, current workflow either skips those scenes
(loses film character) or shows uncensored (YouTube monetization risk +
audience inappropriate).

Required feature: per-shot censor flag with render-time blur/mosaic
application.

Implementation requirement before Film 2 (if relevant genre):
- Schema change: shots.json accept censor field (none / blur / mosaic /
  black)
- Render pipeline: apply ffmpeg filter to flagged clips at render time
- Default policy: violence with blood, nudity, drug use specifics get
  flagged at catalogue stage
- TAGGING_GUIDE addition: when to censor (genre + audience considerations)

Priority: deferred until first explicit-content film attempted
(Wolf of Wall Street, Goodfellas, etc.). Prisoners did not need it.

## Update 2026-06-16: Gap 2 IMPLEMENTED

Censor capability implemented before Gone Girl 2014 (Film 2) ingest.
Reasoning: Gone Girl contains Desi throat slash (iconic beat, cannot skip)
and tasteful nudity. Without censor, would have forced uncensored render
(YouTube risk) or beat skip (lose film signature).

Implementation specs:
- Method: Gaussian blur (whole frame, render-time)
- Schema: shots.json "censor" enum (none/blur_light/blur/blur_heavy)
- Filter: ffmpeg boxblur with enable=between(t,X,Y)
- Tagging: catalogue stage per S7 rules
- Audit: C10 verifies coverage

No Prisoners regression test run (user choice, blur is standard ffmpeg
filter, low implementation risk). First validation will be Gone Girl
render with actual censor flags applied.

Gap 2 now closed.

### Gap 3: Action breathing rooms (narration silence)

Current pipeline requires every shot bound to narration line. No support
for narration silent shots where visual + music carry without voiceover.
This is standard cinematic recap technique: at peak action or emotional
moments, narration pauses 15-25 seconds, letting visuals breathe.

Without this, recap feels wall-to-wall narration - viewer cannot absorb
emotional weight, action sequences feel narrated rather than experienced.

Examples where breathing rooms add craft:
- Suicide peak moments
- Gunfight peaks
- Major reveals (after spoken setup, silence during visual reveal)
- Death scenes
- Iconic cinematic shots (Roger Deakins compositions, etc.)

Required feature: silent shot type in schema, music continues during
silence (often swells), no narration generated.

Implementation requirement before Film 2:
- Schema change: shots.json or draft.json accept narration_silence_seconds
  field on specific lines
- Render pipeline: respect silence duration, suspend TTS, continue music +
  visual
- Music ducking adjusts: during silence, music can rise to 30-40% volume
  (vs ducked 16% under narration)
- TAGGING_GUIDE addition: when to plan silence (peak action, peak emotion)
- SCRIPTING_CHECKLIST: C10 check that major beats have silence consideration

Target: 15-25 second silences at 2-4 major moments per recap (not more,
or viewer scrubs forward).

Priority: high. Apply before Film 2 if possible. Cinematic feel benefit
significant.

### Summary of deferred work before Film 2:

1. Style guide for commercial narration register (no pipeline code, doc only)
2. Censor schema + render filter (pipeline code, defer until genre demands)
3. Silence shot support (pipeline schema + render code, high priority)
4. SCRIPTING_CHECKLIST update with C10 silence consideration

Order of implementation:
- Style guide (easiest, fastest impact)
- Silence support (medium effort, high quality impact)
- Censor support (defer until needed)


## Update 2026-06-16: Phase C COMPLETE - partial blur (region censor)

Extends Gap 2 / S7 whole-frame censor with an OPTIONAL per-shot blur region so
only the explicit rectangle is blurred and the rest of the shot stays watchable.

What shipped (commit 899d820):
- schemas.py: new `CensorRegion(x, y, width, height)` dataclass (int coercion +
  validation: width/height > 0, x/y >= 0). `Shot.censor_region: Optional` =
  None. Dict from JSON is coerced like Claim; absent -> None (backward compat).
- render.py: `_build_clip` now has three branches - none / whole-frame inline
  boxblur (Phase A/B) / partial-region graph
  `[v0]split[base][region];[region]crop=W:H:X:Y,boxblur=N[blurred];`
  `[base][blurred]overlay=X:Y[v]`. Region clamped to the output canvas.
- Cache: `_clip_signature` includes the region (`_region_sig`), so changing or
  adding a region busts only the affected clip; whole-frame clips unaffected.
- render() reads `censor_region` from shots.json into region_by_clip and threads
  it through; console prints "(N partial-region)".

Verification: 14/14 tests PASS - Prisoners (67) + Gone Girl (59) shots.json load
with censor_region=None (backward compat); dict->CensorRegion roundtrip; int
coercion; rejects width<=0; real ffmpeg run of the partial-blur filter_complex.
No regression: recap.py draft still validates clean.

Docs: TAGGING_GUIDE S8 (region selection workflow at catalogue: render zoom
frames, pick a rectangle that covers the content across the WHOLE clip, pad for
motion, output-canvas pixels, clamp-safe). SCRIPTING_CHECKLIST C10 extended with
region verification. Whole-frame remains the default; region is a refinement.

Lessons:
- Coordinates are OUTPUT-canvas pixels (post scale/pad), not source pixels - for
  1080p->1080p they match 1:1, but a downscaled source would not. Document per
  project if source != output resolution.
- Over-cover beats under-cover: clamp makes over-estimates safe; the failure
  mode is content slipping out of a too-tight box on a motion frame. Pad
  generously, or fall back to whole-frame.
- Existing whole-frame censor is byte-unchanged (region=None path is the old
  inline boxblur), so adopting Phase C carries zero risk to prior renders.

Estimated 45-60 min, actual ~30 min (censor plumbing from Gap 2 was reused).

Remaining deferred (tomorrow): partial-blur test on Gone Girl's 7 censor flags
with real region coords + re-render; silence-shot support (still high priority).


## Update 2026-06-18: Gap 3 COMPLETE - narration silence (cinematic holds)

Adds an OPTIONAL per-shot silence: the visual holds with NO voiceover so a
moment can breathe, and the music swells from the ducked narration level up to
a higher level, then fades back when the next narration starts.

What shipped (commit 83ea57f):
- config.py: SILENCE_MUSIC_VOLUME = 0.35, SILENCE_FADE = 0.5.
- schemas.py: Shot.narration_silence_seconds: Optional[float] = None. Validated
  > 0, <= 30 (S9 cap), int/str coerced to float, rejects negative/zero/over-cap
  /non-number. Absent -> None (backward compatible).
- render.py:
  - _build_silence_clip(): visual hold for N seconds (same canvas/motion/censor
    as _build_clip) with a SILENT anullsrc stereo track, so xfade + music mix
    stay uniform. No TTS.
  - _clip_signature(): silence is part of the cache key (silence vs narrated
    build of the same clip cache separately; existing clips unaffected).
  - _music_volume_expr(): static volume when no silence windows, else an
    eval=frame trapezoid that ramps base->SILENCE_MUSIC_VOLUME over SILENCE_FADE
    and back, per window. Composes with the existing sidechain duck (during
    silence the clip audio is silent so the duck naturally releases too).
  - render() loop reads narration_silence_seconds from shots.json into
    silence_by_clip; silence lines skip the TTS/by_id lookup, build a silence
    clip, record absolute (start,end) windows, threaded to _render_with_music.

Verification: 23/23 PASS. Schema (backward compat on Prisoners 67 + Gone Girl
59; roundtrip; int/str coercion; rejects negative/zero/>30/non-number; 30.0
boundary ok; cache sig distinct). Render on real source: 20s silence clip holds
20.00s with a silent (-91 dB) audio track. End-to-end mix: music measured +6.4
dB LOUDER in the declared silence window (matches the 0.16->0.35 ratio ~ +6.8
dB) and the narrated window unchanged. Regression: recap.py draft still clean.

Docs: TAGGING_GUIDE S9 (when/how to use silence at catalogue: peak emotion,
iconic shots, action payoffs; 3-30s, ~2-4 per recap, never back-to-back, never
on plot-carrying moments). SCRIPTING_CHECKLIST C11 (silence usage earned) +
C1 footage-first EXCEPTION (silence shots bind no narration line). Gate now
C1-C11.

Lessons:
- A silence shot is the ONLY shot type exempt from line binding (C1). Encoded
  the exception in C1 itself so it is visible at the point the rule is read.
- The music swell is two mechanisms composing: the sidechain duck releases
  because the clip audio is silent, AND the explicit volume expression raises
  the base. Verified by measurement, not assumption (+6.4 dB).
- Silence must be EARNED. The doc/checklist push back on using it as runtime
  filler - if you cannot name why a shot earns silence, it does not get it.

Estimated ~60 min, actual ~50 min (Phase C censor plumbing pattern reused for
the silence map threading).

Gap status: Gap 1 (style guide, Phase A), Gap 2 (censor, + Phase C partial
blur), Gap 3 (silence) all COMPLETE. Full feature set ready for Film 3 (Joker
2019) which will exercise Phase A + B + C + Gap 3 end to end.


## 2026-06-18 - Joker Stage 7 QA diagnosis findings

Joker (Film 3) first to apply ALL workflow features simultaneously (Medium 
Register B + extensive censor + partial blur + Gap 3 silence). Stage 7 
watch revealed 4 systematic issues OpenCode diagnosed via empirical 
investigation (predicted timeline 446.4s = actual 446.4s confirmed no 
render bug):

1. **Catalogue clip windows 5s vs narration 6-15s = "freeze on moment"**:
   41/55 narrated lines had audio > 5s clip window. Workflow held single 
   frame to fill audio, creating freeze effect.
   
   Lesson: When using Medium Register B, either split long lines into 
   more beats OR extend clip windows during catalogue. Default 5s window 
   assumes Light Register narration.

2. **Catalogue timestamps not frame-verified per shot**:
   Multiple beats catalogued at wrong source moments (B10 hospital at 
   Wall Street establishing, B28 Penny smother all 3 shots at Randall 
   apartment aftermath, B35 Wayne murders at riot footage).
   
   Root cause: Stage 2 trusted transcript timestamps + overview frame 
   pages without rendering zoom frames per shot for verification.
   
   Earlier "frame-verified" claims (e.g., B34/B35 Wayne at 01:48:27) 
   were wrong on re-investigation. 
   
   Lesson: Frame-verify EVERY catalogued shot via extracted zoom frame, 
   not transcript anchor or claimed verification. Especially critical 
   when applying multiple workflow features.

3. **Censor flag accuracy inherits catalogue accuracy**:
   Wrong catalogue timestamps cascade to wrong censor placement. 
   3/13 flags landed on wrong scenes entirely (B28 trio).

4. **Blur approach over-conservative for dark/distant shots**:
   Whole-frame blur on already-dark shots = unreadable mush. 
   Heavy blur on distant wide shots disproportionate. 
   "Over-cover beats under-cover" (S8) needs nuance for dark scenes.

Engineering integrity acknowledgment: OpenCode disproved own audio-cascade 
hypothesis through empirical verification rather than confirming intuition. 
This is the right model for diagnosis.

### Tonight's deeper finding (post-Phase 1 frame verification)

Phase 1 frame-verification of additional reference anchors (B27 detective 
chase 01:27:00, B36 Joker on car 01:49:30) revealed BOTH ALSO mis-
timestamped. This proves catalogue drift extends beyond the originally 
diagnosed 5 beats (B10, B28 trio, B35, B13b).

Current confirmed wrong timestamps (6 beats so far):
- B10 hospital children (off 4 min)
- B27 detective chase (wrong content - actually transformation makeup)
- B28 Penny smother trio (off 8 min)
- B35 Wayne murders (off 1.5 min)  
- B36 Joker on car (wrong content - actually Wayne family at theater)
- B13b subway shooting (off 23 sec)

Implications for workflow going forward:

1. **Stage 2 catalogue MUST frame-verify EVERY shot**, not just per beat 
   sampling. Cannot trust transcript timestamps even when contextually 
   plausible.

2. **Renumbering operations require verified anchors first**. Earlier 
   "swap B27↔B28, B35↔B36" plan failed because the swap targets were 
   themselves wrong-anchored. 

3. **OpenCode engineering integrity caught error before commit**. 
   Diligent verification > assumption proceed. This is the right model.

4. Catalogue accuracy degrades when multiple workflow features 
   (Medium Register B + extensive censor + partial blur + silence) 
   applied simultaneously without per-shot frame verification.

Going forward all films Stage 2 catalogue must include frame-verify 
step per shot, time-budget accordingly (~30s per shot = +30min for 
60-shot catalogue, worth investment).

## 2026-06-25 - Joker v3: Mức 1 pipeline upgrade + B/C/D scope

### Mức 1: BindingViolation hard constraint (Phase A)
The render USED to silently freeze a clip's last frame whenever the
narration ran longer than the bound shot window (clip_len = max(narr+GAP,
hold), tpad clone). That freeze was the Stage-7 "frozen frame" artifact.
New contract: narration_duration <= shot_duration * BINDING_SLOWDOWN_MAX
(1.4). Within that, mild slow-motion (setpts) fills the gap; beyond it,
the render RAISES BindingViolation instead of freezing. Surfaced at
`recap.py draft` time (exit 1) so it is caught at authoring, not render.
Files: pipeline/schemas.py (BindingViolation, binding_capacity_check,
estimate_narration_seconds), pipeline/render.py (_build_clip trim/slowmo/
raise + cache-hit gate), pipeline/draft.py (surface pre-render).

### Root cause of the 40 violations (Phase B)
shots.json had 61/64 windows = an identical 5.0s PLACEHOLDER (clip_start +
5s). clip_end was never used for timing (only cache hash), so the 5s
values were meaningless; the render froze to fill the rest. Fix = set REAL
cut-aware windows: measure each scene's continuous-footage length (ffmpeg
scene-cut detection) and cap clip_end at the first hard cut. 51 shots fit
or needed only mild slow-mo; 13 sat at a cut too close -> 9 re-anchors to
a longer take of the SAME scene (frame-verified) + 4 micro-montages.

### Inline-timestamp montage (new capability)
montage[] entries may now be inline {clip_start, clip_end} dicts (not just
broll pool labels), so projects with no broll.json can cut a rapid-cut
sequence across its hard cuts instead of freezing one short shot. Render +
draft validators made tolerant of dict/list montage entries.

### Expansion lessons (Phase C)
- A capacity-bound recap CANNOT hit an arbitrary word target by lengthening
  lines: each line is capped by its shot window * 1.4. Joker v3 reached
  1779w / ~9:18 (from 1412w); 2500w would have required many more
  catalogued sub-moments, i.e. padding. Word targets must be set against
  the available footage budget, not pulled from the air.
- Changing claims requires re-tagging shots.json depicts to match (a shot
  genuinely depicts multiple things). Multi-line shots with different
  claims trip [TAG-QUALITY] dual-stage -> give each line its own
  single-stage sub-window.
- After expansion, skeleton.json target_words + must_cover must be
  re-synced to the new per-unit actuals or coverage audit fails.

### Music auto-discovery (Phase D) - SILENT FOOTGUN
v2 shipped with NO music because `recap.py render` was called WITHOUT
--music, and music was None -> render did a voice-only encode (the else
branch), never calling _render_with_music. music.mp3 sat right there
unused; the --music-volume config edit was inert. Proof: v2 encode log
said "encoding..." not "mixing music encoding...", and a silence-window
audio probe was near-silent. FIX: cmd_render now AUTO-DISCOVERS
projects/<p>/music.{mp3,m4a,wav,ogg} when --music is omitted and warns
loudly if rendering voice-only. Also MUSIC_VOLUME 0.13->0.18 (0.13 was
~-31dB isolated, perceptually absent under -15 LUFS voice). v3 verified:
silence-swell window measured -13dB (louder than -17dB voice sections),
the unmistakable signature of a mixed+swelling music bed.

### Pipeline-wide
All of the above (Mức 1 raise, cut-aware windows discipline, inline
montage, music auto-discovery) apply to ALL future films, not just Joker.
v3 still had 7 narrative<->visual mismatch issues flagged on watch ->
Day N+1 diagnosis (catalogue/binding accuracy, separate from the freeze
and music classes fixed here).

## 2026-06-19 - Joker v3->v4 mismatch fixes findings

Joker v3 watch revealed 7 mismatch issues despite Muc 1 + Phase B
catalogue restructure. Pattern analysis:

1. Adjacent-line swap (Issues 1+2): Phase 2 restructure swapped
   Sophie/Randall line bindings accidentally during U13<->U14 reorder.
   Lesson: After ANY catalogue renumber or restructure, run binding
   audit explicitly - lines may point to wrong shots after beat
   numbering changes.

2. Wrong scene after renumber (Issue 7): L48 timestamp 01:17:27
   pointed to wrong moment after beat renumber.
   Lesson: Beat renumber requires line binding re-verification
   per line, not just chronology check.

3. Action timing wrong (Issue 3): Micro-montage chose 00:32:18
   (still being beaten) instead of 00:32:32 (hunting moment).
   Lesson: Action sequence micro-montage requires per-shot moment
   verification - which beat moment matches narration claim.

4. Catalogue content error (Issue 5): B18 tagged 'Murray mocking
   tape' but actual content = Arthur's Pogo's stage performance.
   Lesson: Phase 1D front-half verify needed deeper frame check,
   not just adjacent-scene acceptance.

5. Thematic acceptable (Issues 4+6): Smoking shot foreshadows
   Sophie delusion. Fridge desperate = post-reveal mental state.
   Lesson: Some 'mismatches' actually serve narrative purpose.
   Verify thematic intent before forcing rebind.

Critical insight: Mismatch issues are CATALOGUE/BINDING DISCIPLINE
issues, not pipeline architecture issues. Muc 2/3 architecture
upgrades will NOT prevent these errors.

Process improvements needed:
- Stage 2 catalogue: frame-verify EVERY shot timestamp
- Phase 2 restructure: line binding audit AFTER renumber
- Action sequences: per-moment montage verification
- Stage 7 watch: catch what pipeline cannot

## 2026-06-20 - Muc 2 + Muc 3 architecture (multi-shot binding + capacity-aware catalogue)

### Muc 2: multi-shot binding as a BACKWARD-COMPAT SUPERSET
The spec proposed a brand-new binds_to/shot_id schema. Instead of a breaking
rewrite, Muc 2 was built as a strict superset of the existing inline montage:
- BindSpec dataclass {clip_start, clip_end, play_duration?}.
- Line.bind_segments() normalises ANY binding (single clip_start, montage dict,
  montage [start,end]) into list[BindSpec]. A single shot -> 1-element list.
- A montage segment may now carry an optional play_duration so each shot plays
  its OWN length; absent -> the legacy EQUAL-split (unchanged).
- binding_capacity_check is now SUM-based for multi-shot, and crucially uses the
  RAW windows (clip_end-clip_start) for capacity, NOT play_duration (which only
  drives the render split). This prevents a false-flag when play_durations are
  sized to the narration.
Result: Prisoners/Gone Girl (single-shot bindings) validate + render unchanged;
Joker's 5 montages migrated to proportional play_durations with PROVEN identical
total length (built a clip both ways: 5.82s == 5.82s).
Lesson: design new capabilities as supersets with an explicit legacy path, and
keep CAPACITY (real footage) separate from SCHEDULING (how time is split).

### Muc 3: capacity-aware catalogue, grounded in a CALIBRATED voice profile
The single most important number is how fast the voice actually speaks. The spec
GUESSED 4.8 words/sec; measuring Andrew Multilingual Neural +22% across Joker's
75 real TTS lines gave 3.50 words/sec (mean 3.518, std 0.426). The spec's
syllable rate (5.2/s) was close to measured (4.74/s) - the error was the
words<->syllables conversion (~1.35 syll/word). A guessed rate would have
under-estimated narration time by ~37%.
- config/voice_profiles.json stores the calibrated profile (+ words_per_sec_
  conservative = mean - 0.5*std for SAFE word ceilings).
- pipeline/calibration.py: VoiceProfile.estimate_narration_seconds / max_words_
  for_capacity, plus a calibrate() that re-measures from any project's TTS.
- pipeline/catalogue.py: enrich_shots / capacity_map auto-compute the 5 Muc 3
  Shot fields (raw_duration_sec, max_play_duration_sec, max_narration_words_en,
  extendable, stretch_tolerance). extendable defaults FALSE for action/dialogue/
  reveal (motion/lipsync the eye catches if slowed), TRUE for establishing/setup/
  aftermath/emotion/transition.
- draft.py [CAPACITY-WORDS] surfaces lines >= 80% of their shot's word ceiling as
  a soft heads-up; the Muc 1 sum-check stays the hard gate.

### Migration strategy: NONE required
Every Muc 2/3 field is optional and computed-on-demand. Old artifacts
(Prisoners, Gone Girl) keep working untouched; capacity_map computes defaults on
the fly. Joker's shots.json was enriched, but render.py references NONE of the
new fields, so output is provably byte-identical (verified: 0 render-relevant
field changes). No re-render needed to confirm no-regression.

### Side-finding the new tooling surfaced
Running [CAPACITY-WORDS] against the OLD catalogues flagged 18 Prisoners + 40
Gone Girl lines over the calibrated word ceiling - the same uniform-5s-placeholder
window problem Joker had before Phase B. Muc 3 makes this visible BEFORE a watch,
which is exactly its purpose. (Migration deferred per plan.)

### Future-film workflow benefit
Stage 2 catalogue can now hand the draft writer (human or LLM) a per-shot
max_narration_words_en up front, so lines are sized to their footage at
authoring time instead of discovering overruns at render. The freeze class
(Muc 1) and the now capacity-aware authoring (Muc 3) together close the loop:
write-to-fit, then verify-cannot-freeze.

## 2026-06-29 - Parasite 2019 v1 SHIPPED (first clean-watch film)

### Workflow maturity demonstrated
Parasite is the FIRST film to ship with a clean Stage 7 watch outcome - no
narrative<->visual mismatch iteration (Phase E/F) needed. Joker took v1->v4
(4 renders) to get there; Parasite got it on v1. The difference was applying
the Joker lessons UP FRONT instead of discovering them on watch:
- Stage 2: frame-verified EVERY shot timestamp (61 shots), not memory anchors.
  The Stage-1 6-beat check proved memory drifted 5-10 min; the transcript
  re-anchored everything before any binding was written.
- Binding audit run after every catalogue add/restructure, not just at the end.
- Capacity-aware authoring (Muc 3) sized lines to footage during drafting, so
  the only render-time surprise (conservative slowdown flags) evaporated at the
  real TTS rate (50 flagged, 0 actually slowed).
This is the thesis from the Day N+1 lessons proven on a new film: mismatch
issues are DATA/PROCESS DISCIPLINE, not architecture. Muc 1+2+3 + the discipline
were sufficient for a non-mismatch outcome.

### Korean-language film: zero pipeline changes for English narration
Source language is decoupled from recap language. Whisper medium + --translate
gave an English transcript to catalogue against; the recap is English Andrew
narration over Korean footage, exactly like the English films. The calibrated
voice profile + all of Muc 1/2/3 applied unchanged.

### New this film: resumable transcription + DARK-scene exposure-lift
- transcribe.py writes transcript.partial.jsonl per segment and resumes via
  Whisper clip_timestamps. A 2h11m film on CPU-medium took ~7h across multiple
  session boundaries; the checkpoint carried it through with zero lost work.
  Essential for any long/foreign film (the first foreground run lost 25 min
  before this existed).
- render.py exposure-lift: shots flagged DARK (or with exposure_lift set) get an
  eq brightness/gamma/saturation lift applied to the PICTURE (not the letterbox
  bars), cache-keyed. Parasite's bunker/flood/aftermath are very dim on a 534p
  source; without the lift they would render as unreadable mush (Joker B35
  lesson, now fixed in code rather than worked around).

### Catalogue ceiling sets the runtime, not word-padding
Same dynamic as Joker Phase C: a fixed catalogue has a hard word ceiling
(shots x cut-aware-window x slowdown). Parasite's first 48-shot catalogue
capped ~10.3 min; reaching the 11-13 min target needed a targeted Stage-2b
expansion (+13 frame-verified shots -> 2671w ceiling), NOT denser narration.
Lesson: when a draft is too short, add catalogued MOMENTS, do not stuff the
existing shots to their ceiling (that produces relentless slow-mo).

### Source quality note
1280x534 (534p) source: usable but soft; the exposure-lift is more necessary
at low resolution. Frame-verification still reliable. Future: prefer >=720p
sources where available.

### Exploration noted
An "18-minute experiment" direction was raised for future exploration (a longer,
deeper recap format) - parked, not pursued this session.

### Channel status
4 films shipped: Prisoners, Gone Girl, Joker, Parasite. Parasite is the cleanest
process run to date and the validation that the pipeline + discipline have
matured to a repeatable, first-attempt-clean state.

## 2026-06-30 - Stage 2 depth-target workflow enhancement

Pattern surfaced across 4 films (Prisoners, Gone Girl, Joker, Parasite):
Initial Stage 2 catalogue systematically under-catalogues vs film's natural shot capacity.

Each film required iteration:
- Joker: 37 beats initial -> ship 9:17 (capped, possibly under-catalogued)
- Parasite: 28 beats -> 48 shots -> 61 -> 87 -> 110 shots (all expansions frame-verified, no padding)

Root cause analysis:
1. Initial beats_proposal.md too conservative (scene-group level abstraction)
2. Stage 2 default 1-2 shots per beat (speed-optimized, khong depth-optimized)
3. No depth target in workflow specification

Enhancement implemented:

1. DEPTH_TIERS config:
   - recap (9-13 min): 60-80 shots
   - fuller_recap (14-17 min): 90-110 shots
   - video_essay (18+ min): 110-130 shots
   Drive from beats_proposal.md target length declaration.

2. Multi-shot per beat default: 2-4 shots per beat (NOT 1-2). Beats with only 1 shot flagged for review.

3. Sub-moment enumeration protocol: per beat, list main action + character reactions + motif appearances + setting details. Pick shots covering enumerated moments.

4. Quality gates audit (C12-C15):
   - DEPTH-TOTAL: total shot count vs tier band
   - DEPTH-UNDER: beats with <2 shots flagged
   - DEPTH-CLIMAX: action sequences need rapid coverage (>=3 shots per [S6] beat)
   - DEPTH-REACTION: 2+ char action beats missing a reaction/emotion shot
   - DEPTH-MOTIF: declared motif moments not catalogued flagged

5. Beat-linking: explicit `beat` field per shot (B07 format; also accepts int 7 / "B7"). Backward compat via timestamp-inference fallback.

6. Strictness: soft default + --strict opt-in. Soft warnings exit 2, --strict makes DEPTH-UNDER hard fail (exit 1).

Files touched: config.py (DEPTH_TIERS), pipeline/catalogue.py (parse_beats /
coverage_report / print_coverage_report / --coverage --strict CLI),
docs/TAGGING_GUIDE.md (S10), docs/SCRIPTING_CHECKLIST.md (C12-C15 + Stage 2 / draft
gate split), docs/STYLE_GUIDE.md (section 7), prompts/recap_style.md (STAGE 2:
CATALOGUE TO DEPTH).

Two bugs caught + fixed mid-build (real-artifact testing, not assumed-correct):
- Beat-id type mismatch: Parasite shots carry integer `beat: 1`; the audit keyed
  on string "B01" and saw 0 shots/beat. FIX: _norm_beat_id normalizes int/"B7"/
  "B07" -> "B07".
- Runtime-inference false positive: Joker's "Target: 36 beats, 3 acts" line had
  no minutes; the digit-grab read "36" as a runtime and mis-inferred video_essay.
  FIX: only trust an explicit "N-M min" / "N+ min" figure, else tier = None.
  Also tightened the beat-line detector so prose lines beginning "B22 is the..."
  are not counted as beats (Joker went 47 -> correct 37 numbered beats).

Real artifact validation:
- Parasite 18-exp branch (110 shots, 28 beats, 3.9 shots/beat avg): 2 beats under
  floor (B08, B11 genuine single-shot). Soft exit 2; --strict -> hard exit 1.
- Joker (37 beats, pipe format): parses correctly, no false tier inference.

Implications:
- Future films (Film 5+) benefit from first attempt with depth target
- Shipped films stay as-is (re-catalogue work prohibitive)
- Channel quality long-term improves

User engineering insight critical: pattern observation across films caught
structural workflow bias not earlier surfaced.

Critical insight: this is a workflow DESIGN issue, not an OpenCode session error.
Architecture-level fix needed, not a patch per session. The audit is the new
floor every future Stage 2 is measured against; "đầy đủ rõ ràng chi tiết"
(quality fullness) is encoded as tooling, not left to per-session memory.

Quality discipline preserved: the audit reports, never pads. Depth means showing
MORE real sub-moments (reactions, motifs, detail), not slower pacing or padded
narration. Single-shot beats are allowed when genuinely right - the gate asks for
a conscious decision, not a quota.

## 2026-06-30 - Stage 3 draft-target depth enforcement (the twin of Stage 2)

Pattern surfaced across 3 films (Joker v1, Parasite v1, Interstellar v1): the
FIRST draft consistently under-authors the declared tier's REAL runtime, even
when the shot catalogue is deep. This is the narration-level twin of the Stage 2
under-catalogue bias fixed earlier the same week.

Root cause analysis:
1. The draft validator's "Est. narration" used the CONSERVATIVE 170-WPM heuristic
   (config.TTS_WORDS_PER_MINUTE), while the calibrated Andrew +22% voice actually
   speaks at ~3.5 w/s (~211 WPM, measured from 75 Joker samples in
   config/voice_profiles.json). The conservative estimate OVERSHOOTS real runtime
   by ~24%, so a draft reading "15 min" runs only ~12 min - and nobody caught it
   until render/watch.
2. No gate compared draft runtime against the declared tier's runtime floor.
3. No capacity-fill metric, so an under-filled draft (short lines leaving shot
   capacity unused) looked "valid" and shipped short.

Enhancement implemented (DRAFT-TARGET gate, soft/advisory, exit 2 never hard):

1. Real-rate runtime estimate using the calibrated VoiceProfile
   (calibration.get_profile -> estimate_narration_seconds), summing per-line
   spoken seconds PLUS silence-shot seconds (silence lives on shots, not lines).
   Shown ALONGSIDE the conservative estimate; when they diverge >15%, a note
   explains the conservative one overshoots.
2. Tier-floor check: warn [DRAFT-UNDER-TARGET] if the real-rate estimate is under
   the tier floor (recap 9.0 / fuller_recap 13.5 / video_essay 17.0 min), read
   from beats_proposal.md depth_target via catalogue.parse_beats (Day N+4 reuse).
3. Capacity fill = draft words / sum(shot word ceilings). Target 70-85%. Warn
   [DRAFT-UNDERFILL] below 65% and surface the units with the most unused
   capacity headroom (actionable: "enrich U03, U13, U23"). Warn [DRAFT-OVERFILL]
   above 90%.

Files: config.py (DEPTH_TIERS runtime_floor_min + DRAFT_FILL_* thresholds),
pipeline/draft.py (_draft_target_report appended to _run_phase1_audits),
docs/SCRIPTING_CHECKLIST.md (C16), docs/STYLE_GUIDE.md (section 7b).

Key diagnostic value proven on Interstellar v2 draft: the gate flagged it as
real-rate 13.1 min (UNDER the 13.5 fuller_recap floor) AND 94% capacity fill
(OVER-filled). That combination is the important one: the lines are already near
capacity, so the fix is NOT to pad them - it is to bind more catalogued shots or
add earned silence. Without this gate, that draft would have rendered ~13 min and
the shortfall would only have been noticed on watch.

Backward compatible: the gate is additive and soft. No depth_target tier -> it
still prints the real-rate estimate and fill, just skips the tier-floor check.

Insight: same as Stage 2 - this is a WORKFLOW DESIGN fix, not a per-session
discipline reminder. The conservative-estimate overshoot was a silent, structural
mislead baked into the validator; encoding the real rate as tooling means every
future draft is measured honestly, not by a number that flatters short scripts.

## 2026-07-04 - Interstellar linear: don't compress the film's causal setup chain

Viewer feedback on the Interstellar linear recap: it did not make clear HOW
Earth was dying. The film's slow-apocalypse premise is a chain - blight spreads
-> crops die one by one -> corn is the last crop standing -> starvation and
suffocation - but the recap compressed that whole chain into a single line
stating only the conclusion ("Earth is suffocating; blight has eaten every
crop"). A first-time viewer got the RESULT without the MECHANISM, so the world's
death read as an assertion rather than a process the film actually walks through.

### The fix
Style rule added to prompts/style_linear_vn.md (PILLAR ZERO comprehension list):
"Don't compress a causal setup chain into a single line." When a film establishes
its premise through a chain of cause -> effect (a dying world, an escalating
threat, a ticking countdown), walk the viewer through the chain; state the
mechanism, not just the result.

### The two-sided failure mode (the important part)
This is NOT a blanket "add more explanation" rule - it cuts both ways:
- UNDER-COVER: compressing a causal chain the film DID show into its conclusion
  (the Interstellar blight/last-crop/suffocation miss above).
- INVENT: filling a gap the film DELIBERATELY left open. Interstellar never
  explains the scientific CAUSE of the blight - a recap must not manufacture one
  to sound complete. Present exactly what the film presents, no more.
The discipline is to narrate every link the film actually shows, and stop
precisely where the film stops. Coverage of the shown chain; silence on the
withheld cause. (Mirrors the existing ending-ambiguity discipline: state the
film's choice, don't resolve what it left open.)

## 2026-07-04 - Interstellar linear: enrich act-by-act, validate per act

An under-target draft is lifted into the tier band more reliably by segmented
enrichment than by re-writing the whole film at once.

Interstellar came in thin and TWO whole-film enrichment passes failed to fix it:
the draft stayed under-target at ~11.8 min then ~12.4 min real-rate, ~54% capacity
fill (below the 70% target and the fuller_recap floor). A single full-film re-pass
keeps drifting - the model thins out over a 2+ hour film, or over-stuffs a handful
of lines without lifting overall fill.

Switching to act-by-act enrichment with a validation checkpoint per act reached the
tier band in THREE passes: Act 1, then Act 2, then Act 3, running the DRAFT-TARGET
gate after EACH act. Fill climbed 54% -> 62% -> 67% -> 72% and real-rate reached
16.0 min (inside the 14-17 fuller_recap band), with no freeze (BindingViolation)
introduced. Deepening EXISTING lines (reaction, motive, cause -> effect, sensory
detail) to ~85-90% of each shot's 1.4x time-cap raised fill; crucially, no new
shots were added (adding shots without words LOWERS fill - observed directly).

### Why per-act validation is the load-bearing part
Validating after each act (not just at the end) catches thinning and freezes
LOCALLY, where they are cheap to fix. A per-act pass earlier surfaced 6 freeze
violations the moment they were introduced (lines pushed past the 1.4x cap), and a
later act's silence-shot override produced two zero-duration clips - both caught at
the act checkpoint instead of at render. One big pass would have buried these in a
106-line diff.

### Likely style-agnostic
This is about draft length/fill mechanics, not linear-specific narration. The same
"segment + validate per segment" loop would almost certainly help a review-style
draft that comes in under-target too; the rule is written general in the style
guide (DEPTH & LENGTH section) and worth applying whenever the DRAFT-TARGET gate
reports under-floor or under-70%-fill.

## 2026-07-04 - Tier choice must match a film's TALKINESS, not just its shot count

Action / dialogue-light films need a LOWER depth tier than their shot count
suggests. The DRAFT-TARGET fill metric = draft words / sum(max_narration_words_en),
and max_narration_words_en scales with each shot's playable length. Long action
shots therefore carry a large word-capacity - but a gunfight or a chase 'resists
words': you physically cannot narrate 150+ words over a wordless set-piece without
padding (which the style guide forbids). So a laconic film's capacity denominator
is inflated relative to how much there is honestly to say.

John Wick (2014) is the clean case. ~92 frame-verified shots put it in the
fuller_recap SHOT band (90-110), so it was scoped fuller_recap (14-17 min, capacity
8452 words). But the film is deliberately laconic - long stretches are pure action
and pure silence. Result: a single-pass draft filled only 23%, and enriching all of
Act 1 HONESTLY (dialogue/emotion-heavy, no padding) moved the whole-film fill to
just 30%. Projected honest full-film fill landed ~49% - permanently under the 65%
floor - because the three action-heavy acts resist words. The only way to reach 70%
would be to pad the fights with play-by-play. Dropping to 'recap' tier (9-13 min,
smaller capacity denominator) fits the honest content: the same unpadded narration
yields a healthy fill, and the ~13-15 min honest runtime sits at/near the recap band.

Rule going forward: at Stage 1, pick the tier from BOTH shot count AND talkiness.
A dialogue-driven film (courtroom, drama, ensemble) can sustain a higher tier at a
given shot count; an action/spectacle film should drop a tier, because its shots
carry capacity its script cannot honestly fill. The shot-count band is a soft
guide; the fill/runtime/no-padding constraint is the real one. When in doubt,
enrich ONE act honestly and read the fill - if it's ~65-70%, the tier fits; if the
honest ceiling is well below the floor, drop a tier rather than pad.

## 2026-07-13 - John Wick linear: clip_start was systematically anchored to shot-start, not the narrated moment

Stage-7 watch of the John Wick linear recap surfaced a pervasive
narration-ahead-of-visual problem: the voice named a subject or action a beat or
two BEFORE it appeared on screen. Frame-measuring all 91 lines showed the cause was
structural, not a few stray lines: clip_start had been set to the FIRST frame of the
catalogued shot as a default habit, so whenever a shot opened on lead-in footage -
a wide/establishing frame, an approach, a wind-up, a getting-ready beat, or a
reaction - the narration ran 1-3s ahead of the moment it described.

### Not an action-only problem
The instinct is to treat this as an action-scene issue (the fight/kill/impact
arriving late), and it IS most noticeable there because the payoff is a sharp,
spoiler-y beat. But the measured offenders spanned every shot type - establishing,
arrival, transition, dialogue, and emotional shots all drifted the same way, any
time the opening frames were not yet the narrated moment. 19 of 91 lines needed a
shift; the rest were already anchored correctly (a shot that genuinely IS the
moment - a line held on a face, a static emotional beat - needs no shift).

### The fix: anchor to the moment, shift the whole window
Set clip_start to the frame where the narrated subject/action actually appears (or a
beat before, so footage leads and narration follows). Preserve window size: move
clip_end forward by the SAME offset - shift the whole window, never shrink it
(shrinking risks a render freeze). If a shot is too short to shift without running
past its real cut, accept a tighter anchor rather than force it. Codified as the
CLIP ANCHORING rule in prompts/style_linear_vn.md.

### Large shifts must be beat-verified (the id22 near-miss)
A correction bigger than ~3-4s is a red flag: it usually means the window is
crossing into a different beat or past a scene cut. id22 was first "fixed" at +9s -
which frame-checking revealed had drifted PAST a scene cut onto an aftermath insert
(blood on the floor), trading a lead-in problem for a scene-MISMATCH problem. The
real narrated moment ("he lies motionless in the wreckage") was at +2s. The other
four large shifts (id44 +6 Viggo, id55 +4 into the club fight, id61 +4 Perkins with
pistol, id75 +4 Marcus beaten) each frame-verified onto the correct beat. Lesson:
never push a large shift blindly - verify it lands on the narrated moment.

### Process
All 19 shifts were applied in one pass, then gated: 0 BINDING-VIOLATIONs, 0 new
overlaps, continuity 0, and real-rate/line-count unchanged (windows moved, narration
untouched). Re-render + watch confirmed the narration-ahead-of-visual problem
resolved. Prevention going forward is the CLIP ANCHORING style rule so future films
anchor to the moment from the first draft instead of discovering the drift on watch.

## 2026-07-13 - Pre-catalogue plot reference: fewer name/comprehension errors, at the cost of spoiler risk

Added a PRE-CATALOGUE step to the linear workflow (prompts/style_linear_vn.md):
before Stage 2 cataloguing, read the film's Wikipedia Plot + Cast sections (and IMDb
for a fuller cast list when names are missing). The motivation is recurring across
films: a Whisper transcript is noisy - it mangles proper names (Joker's B-beat
character drift, the John Wick name-linter flags) and leaves the model guessing who's
who and how the film is structured. A plot reference read up front lets the model
catalogue with names, relationships, and structure correct from the start instead of
reverse-engineering them from garbled audio.

### Scope limits baked into the rule
- Read ONLY the Wikipedia-style plot summary + cast list. Explicitly NOT critic
  reviews, ratings, or analysis (Rotten Tomatoes / Metacritic / Ebert / Letterboxd):
  those pollute the channel's own voice and raise copyright issues. The recap must
  stay Serabudabu's own read of the film.
- Wikipedia is a MAP, not ground truth. When the reference and the frames disagree,
  the FRAMES win (different cut, or the summary is simply wrong). This preserves the
  existing footage-first / frame-verify discipline - the reference informs, it does
  not override what is on screen.

### The tradeoff: the model now knows the whole plot (spoiler risk)
This is the real cost and the reason the rule carries a heavy spoiler section. The
manual workflow used to control this implicitly by having a human "cut the ending"
or simply not read ahead. Because this step is aimed at AUTOMATION - the model reads
the source itself - that implicit guard is gone, so the spoiler rule now carries the
full weight the manual cut-the-ending step used to. It is written as absolute:
- On reading the summary, split it into a SETUP zone (names/premise/structure/
  first-half - free to use) and a REVEAL zone (twists, betrayals, deaths, ending -
  knowledge-to-protect).
- Knowing a twist is NOT permission to reveal it early; the narration unfolds at the
  FILM'S pace, a reveal held until the film's own beat (same reveal-at-its-moment
  discipline as following the film's order).
- Reading ahead makes the model MORE responsible for not leaking, not less. Anything
  from the REVEAL zone surfacing before its film-beat is a spoiler failure - hold it.
- When in doubt whether something is a reveal, treat it as one and hold.

Key clarification: twist-hold is an EXPLICIT per-reveal beat-map (each reveal written
down with the timestamp where the film first shows it, held until then), NOT a
byproduct of chronological order. A scene told in correct order can still leak a twist
via hindsight narration - e.g. narrating Interstellar's early "ghost" as "which we
later learn is Cooper," or calling John "Baba Yaga" before the film does. So the rule
requires narrating each early scene with only what a first-time viewer knows at that
point, never with later knowledge.

### Why this is worth the risk
Name-drift and comprehension gaps are recurring, expensive-to-fix errors caught late
(usually at Stage 7 watch, per the Joker findings). Catching them at the SOURCE -
before a single shot is tagged - is far cheaper. The spoiler risk is real but fully
controllable by a disciplined rule; name/comprehension errors from working blind are
not controllable, only discoverable after the fact. Net: read the map first, protect
the reveals, let the frames win.

## 2026-07-14 - DRIFT tagging: tag the specific look-alike, admit uncertainty rather than guess

Two films produced the same class of catalogue error - binding narration to the
WRONG look-alike when a scene shows characters that are hard to tell apart. Codified
as the DRIFT TAGGING rule in prompts/style_linear_vn.md. This is the most damaging
mismatch class AND invisible to the gates: the binding/tag audits check that a line's
claimed type/subject is tag-compatible with the bound clip, NOT that the clip visually
shows the RIGHT individual. A shot mis-tagged 'Spider-Man' passes every gate while
showing the wrong Spider-Man.

### The two source cases
- John Wick (intercut drift): an intercut scene cutting between two locations/people
  (e.g. Viggo's side vs Aurelio's chop shop) meant a clip_start off by only a few
  seconds landed on the wrong character / wrong side of the cut. The lesson: a single
  timestamp cannot represent a run of an intercut scene - frame-verify EACH shot.
- Spider-Man: No Way Home (three-Peter zone): once Maguire's and Garfield's Peters
  join Holland's (~B19), many shots show near-identical masked Spider-Men intercut in
  a fight. Tagging any of them a generic 'Spider-Man' would guarantee drift. Every
  shot had to name the specific Peter (Peter-One/Two/Three).

### The cue hierarchy (most to least reliable), validated on SM:NWH
1. Unmasked face - the surest tell (Holland youngest; Maguire older/broader; Garfield
   lean/narrow).
2. Costume/suit design when clearly lit (Holland MCU Integrated red-black; Garfield
   bright red with bold web-lines; Maguire darker muted classic suit; organic vs
   mechanical web-shooters).
3. Signature dialogue anchor - a line only that character would say. The 'I lost Gwen,
   she was my MJ' line dialogue-locked Garfield with certainty even where the suit was
   ambiguous.

### The key discipline: admit uncertainty rather than guess
The failure mode where all cues break is fast MASKED action intercut - costume-shade
is the only cue and motion-blur/darkness defeat it. On SM:NWH exactly two shots (the
Statue battle 1:55:00 and the Goblin finale 2:08:40) were genuinely unresolvable per
micro-cut. The right move proved to be: tag ALL candidates present + add a _drift_note
('do not bind a single-character line here without re-checking frames'), and bind any
character-specific narration to the clearly-identifiable shots on either side instead.
Flagging the ambiguity beats a confident wrong guess every time - and it is honest
about what the frames actually support. An automated per-shot reveal/identity audit
(scriptable) confirmed zero bare 'Spider-Man'/'Peter Parker' tags in the whole
three-Peter zone before we moved on.

### Why gates can't save you here
DRIFT is a content-level (which individual) miss, not a type-level one - the same
blind spot as the IT-2017 'right type, wrong content' scene-disconnects. The only
defenses are catalogue-time per-shot frame verification, specific (never generic)
character tags, and Stage-7 watch. Getting it right at catalogue is far cheaper than
discovering it on watch.

## 2026-07-14 - Spider-Man NWH render QA: four findings that must not repeat

The first NWH render (draft complete, all gates green, drift-tagging on the three
Peters verified) still shipped four distinct problems, all caught by a human watch.
Codified: RULES 1-3 in prompts/style_linear_vn.md; RULE 4 is process, recorded here
only.

### RULE 1 - Under-fill: WHERE the capacity is unused matters, not just how much
A low capacity-fill number is not automatically a genre artifact. Before accepting
it, break the unused capacity down BY SHOT TYPE. Unused capacity on long ACTION shots
is honest (fights resist words; padding them with play-by-play makes the recap
worse - leave it). Unused capacity on DIALOGUE / EMOTIONAL / CLOSING shots is a
coverage gap: the film is showing something the narration isn't carrying, and the
scene plays rushed. Fill the dialogue/emotional gaps; leave the action gaps. "Fill is
low because it's an action film" is valid ONLY for the action shots - never blanket.
Source: NWH shipped at 61% fill on the "action artifact" reading. The action logic
held, but the ~3-minute emotional closing scene (Peter meeting friends who no longer
remember him) was collapsed into ONE 24s window, so the ending played rushed. The
blanket reading hid a real coverage gap in the film's emotional close.

CORRECTION (second watch): the "leave the action gaps" half was ALSO mis-applied.
"Don't pad the fights" is not "let the fights be unfollowable" - those are different
things. Blow-by-blow narration of every punch = padding (wrong). Narrating a fight's
STAGES so a viewer can follow the escalation = coverage (required). NWH's set-pieces
were catalogued as scattered highlight fragments, not staged sequences: the highway/
Doc Ock fight ran 5.8 min under 3 windows (21% covered), the apartment/Goblin fight
4.9 min under 2 windows (16%), and the Statue of Liberty CLIMAX 13.5 min under 5
windows (14%) - multi-minute holes where the viewer sees footage jump with no thread.
Result: the fights were incomprehensible, not just fast. The test that catches this:
can a first-time viewer follow WHAT HAPPENED in the fight? If no, it is under-covered,
regardless of the fill number. The fix is stage-level lines (John Wick house fight =
5 stages: breach -> clear the floor -> room-to-room -> hand-to-hand -> finish), never
blow-by-blow. Unused action capacity is honest ONLY when the fight is still
comprehensible via its narrated stages. This is the SAME meta-pattern as the others:
a correct rule ("don't pad") applied too broadly (into "don't cover") - widen the
scope back to "cover the stages, just don't play-by-play."

### RULE 2 - Fast-cut sequences are high drift-risk; anchor to the exact sub-moment
A single shot in a fast intercut sequence contains multiple sub-moments packed a
second or two apart. Anchoring clip_start to the shot's start (or even a few seconds
off) lands on the WRONG sub-moment while the narration names the next one - a mismatch
even though the scene is "right." Frame-verify the EXACT sub-moment the line names and
anchor to it. Most footage-vs-narration mismatches cluster here, and it is also why
such scenes read as "rushed." Source: NWH - L42 (May's death lead-in) landed on the
explosion instead of the finding-May aftermath; L59 (the catch) landed on the
Peter-One/Goblin brawl; L56 (Electro's lightning) landed on the Peters inside the
statue. All the same class: window off by seconds, wrong sub-moment.

### RULE 3 - DRIFT TAGGING extends to GROUPS, not just look-alikes
The existing drift rule covers look-alikes (variants, twins, same costume). Extend
it: any GROUP that appears together and intercuts - a team of villains, a squad, a
crew - is a drift risk EVEN WHEN THEY LOOK DIFFERENT. A line naming one member can
land on another's footage. Frame-verify the specific individual named in every line
involving a group. Source: NWH - the three Spider-Men were tagged perfectly BECAUSE
they were flagged up front as the hazard. But Sandman and Electro (different-looking
villains in the same woods/battle sequence) got swapped, and an Electro line landed
on the three Peters. The flagged group was handled; the unflagged group was not. The
lesson: flag EVERY intercutting group as a drift hazard, not only the look-alikes.

### RULE 4 (process, lessons-only) - self-verification is a FILTER, not an approval
When instructed to check every line's footage-vs-narration with no sampling, the
model's own frame-check found 14 of the 16 real mismatches - genuine work saved, and
far better than the earlier under-sampling failures. BUT it missed the Sandman/Electro
swap entirely, and under-classified the R5 catch as PARTIAL when it was a full DRIFT
(wrong character AND wrong action). A human watch found both. Conclusion: model
self-check REDUCES the human's search work; it does not REPLACE the watch. Stage-7
RENDER QA stays mandatory - always watch the rendered cut. Treat a clean self-check
as "most mismatches filtered," never as "the video is correct."

### The meta-pattern across all four
Each is a case of a discipline being applied correctly but too NARROWLY: drift-tagging
applied to look-alikes but not groups (R3); the action-underfill logic applied to the
whole draft not just action shots (R1); clip-anchoring applied to shot-start but not
sub-moment (R2); self-verification trusted as approval not filter (R4). The fix in
every case is to widen the scope of an already-correct rule - and to keep the human
watch as the final, non-negotiable gate.

## 2026-07-18 - Spider-Man NWH final act: fill is blind to comprehension; sampling drifts 2 minutes

The NWH linear recap shipped clean after a final-act rework, but only after a
third round of dense frame-verification. Four lessons, all reinforced by the same
film that produced RULES 1-4 (they are the deeper root causes under those rules).

### 1. Capacity fill is BLIND to comprehension - never a quality signal or target
Fill measures words-per-capacity, NOT whether a viewer understands what they are
watching. Hard proof from this film: before adding the 9 action stage-lines, fill
was 62% (2821/4574 words); after adding them, still 62% - identical numbers - yet
one cut had an unfollowable 13.5-min climax and the other did not. Adding
stage-lines opens windows (the denominator) in step with words (the numerator), so
fill does not move. A rushed close, an under-covered emotional scene, and an
incomprehensible fight can all sit at a "healthy" fill. Only a human watch catches
those. Use fill to spot UNUSED capacity to investigate; never as a pass/fail or a
target to hit. (This is the twin of the RULE 1 correction: fill told us nothing
about the 3-min emotional gap OR the unfollowable fights.)

### 2. Frame-verify by SAMPLING fails in fast-cut sequences - dense-scan or drift 2 min
A 20-24s window in an action set-piece spans 8-12 cuts; sampling 2-3 frames sees
~20% of the window. Worse than the coverage gap: a single matching FRAGMENT gets
mistaken for the whole window. On NWH the "MJ!" reunion SHOUT was mistaken for MJ's
FALL, binding the catch ~2 MINUTES off (real fall 02:04:26, catch 02:04:38; the old
window sat at 02:06:40 on the Goblin brawl). This survived TWO prior "frame-verified"
fix rounds because both sampled. When footage REPEATS (MJ on the scaffold, three
Peters swinging, the Goblin attacking all recur dozens of times across a 13.5-min
battle), "found a matching frame" is not enough - you must pin the RIGHT occurrence
with unique anchors: signature dialogue ("chase me!", "you okay"), non-repeatable
state (the scaffold collapsing, the fall itself), or causal order (the catch MUST
follow the fall). Rule: in action / fast-cut sequences, extract frames DENSELY
(every 1-2s) start-to-finish; never sample. And when the assistant reports
"frame-verified," it must state the METHOD (dense vs sample) before the result is
trusted - a sampled verification of a fast-cut window is not a verification.

### 3. Set-piece coverage: ~1 line per major stage is the FLOOR
Under ~25% coverage is unfollowable, measured: Statue 13.5 min / 5 windows = 14%,
Highway 5.8 / 3 = 21%, Apartment 4.9 / 2 = 16% - all read as incomprehensible on
watch. The John Wick house fight (followable) = 5 stages. For NWH's climax, the 9
added stage-lines STILL were not right in one pass - it took a third dense-scan
round to correct the bindings. Budget accordingly: hard action films need ~3
watch-and-fix rounds, not 1. Coverage means stage-level lines (track: what is
happening -> who is winning -> what turns it), never blow-by-blow (which is padding).

### 4. The cue hierarchy distinguishes TIME, not just CHARACTER (widen the drift rule again)
The DRIFT rule uses unique cues (dialogue, costume, face) to tell look-alike
CHARACTERS apart. Extend the same discipline to TIME: when a SCENE repeats - the
same location/action recurring through a long sequence - use those same unique cues
(signature dialogue, non-repeatable state, causal order) to pin the right MOMENT,
not just the right person. Same discipline, wider scope. This is the meta-pattern
one more time: a correct rule (unique cues resolve drift) applied too narrowly (only
to character identity) - widen it to moment identity in any repeating sequence.

### Outcome
Final act re-bound off the dense scan: fall 02:04:15, catch 02:04:31 (split from the
Gwen callback so the emotional beat gets its own calm window), Electro takedown
02:00:18, Strange return 02:01:18, Goblin finale 02:08:50 (collective, no single-Peter
ID on the ambiguous cut). Duplicate/mis-anchored lines removed (id531 never existed on
screen; id591/id60 were one beat; id56/id562 overlapped), so the honest runtime landed
at 16.9 min - reverted the tier video_essay -> fuller_recap rather than pad to 18.
Viewer confirmed the final cut clean: no mismatches, fights followable, emotion holds.

## 2026-07-20 - The always-thin first draft was an OUTLINE, not a failure (Stage 3a/3b split)

Across three linear films the FIRST full-film draft came in thin and flagged
DRAFT-UNDER-TARGET — Interstellar 54% fill, John Wick 23%, Spider-Man 31% — and each
time we treated it as a problem to fix. It was not a problem. The thin pass IS an
outline: its job is coverage + binding + a whole-arc view, not density. Act-by-act
enrichment (the Interstellar 2026-07-04 lesson) IS writing the script on top of that
outline. We had been running the density gate (DRAFT-TARGET) on a pass that was never
meant to hit density, and calling the expected result a failure.

### The fix: make the two stages explicit
Stage 3a (OUTLINE) runs coverage/binding/continuity only — DRAFT-TARGET is SKIPPED,
because "thin outline under target" is meaningless. Stage 3b (SCRIPT) is the
act-by-act enrichment pass, and DRAFT-TARGET applies there. This keeps BOTH benefits
that were previously in tension: the big-picture outline (see the whole film, bind
every beat) AND the per-act density. Nothing about enrichment changed; we just
stopped measuring the outline against a ruler meant for the script.

### Implementation (engine-owned, automation-ready)
- Stage lives in `projects/<name>/state.json` — engine-written, never hand-edited —
  so the transition is driven by project DATA, not a command-line flag a human must
  remember. A fresh draft defaults to `outline`.
- `outline_ready` is an HONEST condition, not a number: no run of ≥2 consecutive
  uncovered beats + 0 binding mismatch + 0 unverified + continuity clean + 0
  freeze-class violations. The coverage rule encodes the actual failure mode (a
  skipped CHUNK of film) rather than a magic percentage — a lone uncovered beat
  between two adjacent lines is a coarse HH:MM beat-map granularity artifact and is
  tolerated; two in a row is a real unnarrated stretch.
- Promotion is ONE-WAY and, for now, EXPLICIT (`recap.py draft --promote`): the
  engine computes readiness and prints its judgment + metrics to state.json so it is
  auditable; the human pulls the trigger. Proven-correct → later automatic
  (nhắc-tay → observe → automate, same path as every other feature).
- Gated on `style == "linear"` (review flow untouched) and `write_state` (only
  `recap.py draft` promotes; render re-validates but never mutates stage). Verified
  zero regression on all three finished films: every pre-existing audit number
  (binding, continuity, freeze, and — once promoted — DRAFT-TARGET) identical to
  baseline.

### The new check earned its place immediately
The beat-coverage measure, the moment it existed, surfaced a REAL gap in a film we
thought was finished: **John Wick has a ~5-minute unnarrated ending tail** — the last
draft line is at 94.4 min, but the climax/ending beats (97-99+ min) have no bound
narration (flagged as the consecutive gap B29+B30). This is the same
under-covered-close class as Spider-Man's 3-minute coffee-shop scene that we had to
fix on watch — except here a tool caught it before a watch, because we finally had a
coverage measure. LOGGED TO FIX LATER (separate content pass: dense-scan JW 94-101
min, add ending-stage lines, re-gate). The lesson within the lesson: a coverage gate
that runs on every draft pays for itself by finding the gaps a human watch would
otherwise have to catch — or miss.

## 2026-07-20 - Reveal-timing formalized into a permanent gate (a floor, never a ceiling)

The ad-hoc "reveal-timing audit" built by hand on Spider-Man (it held all 7 reveals
across 5 acts) is now a first-class linear gate. Design mirrors the Outline/Script
split: reads DATA not memory (a machine-readable `reveal-map` block in
beats_proposal.md), linear-only, additive, zero regression on the three finished films.

### What it does
For each reveal (a set of protected TERMS + a LANDING time - a beat id or timestamp),
the gate flags any narration line, whose footage sits BEFORE the landing, that contains
a protected term. Matching is word-boundary, case-insensitive. Landing by beat id
resolves through the same HH:MM beat-time helper as beat-coverage (NOT parse_ts - the
2-minute-drift trap we fixed). Soft-only severity (escalate sev to soft on a hit, NEVER
downgrade a hard - a possible spoiler must not block a render on a false positive).
ALWAYS-ON regardless of stage: unlike DRAFT-TARGET (meaningless on a thin outline), a
spoiler can enter at outline OR during enrichment, and even a one-line-per-beat outline
can leak - so it is not stage-gated. No-op when a project has no reveal-map block.

### The key design principle: it declares its own limit every run
REVEAL-TIMING is a LITERAL-term text scan. It cannot catch paraphrase ("the man with
metal arms") or implied foreshadowing ("a familiar face steps through the portal"). So
it PRINTS that limitation on every run ("literal-term scan; cannot catch paraphrase or
implication - the Stage-7 watch remains the spoiler backstop"). A gate that quietly let
people believe it was complete spoiler protection would be worse than no gate - it would
falsely reassure. The gate is a FLOOR (catch the obvious literal leaks a tired eye
misses), never a ceiling (the draft-review watch stays the backstop). Same lineage as
"audit-clean is not video-clean" and "a sampled verification is not a verification."

### We deliberately OMITTED an allow-before escape hatch
The tempting feature is a per-reveal "this term is fine before the landing" exception,
for civilian names legitimately present early. We left it out on purpose: silencers are
how gates die. VISUAL-MEMORY drifted into ignorable soft noise precisely because it was
easy to wave off; an allow-before list would train authors to silence REVEAL-TIMING to
get unblocked, hollowing it out. Instead, legitimate-early terms go in a SEPARATE row
(protect "the Goblin" the monster; leave "Norman Osborn" the man unprotected). Dumb gate
+ explicit map beats smart gate + escape hatch - the intent stays visible in the data.

### The acceptance test verified honesty, not just function
Three cases: (a) the shipped Spider-Man draft -> 0 hits (all reveals held); (b) a planted
early "Maguire" -> CAUGHT (R4, before B19); and crucially (c) a planted IMPLIED spoiler
with no protected term ("a familiar face steps through the portal") -> NOT caught. Case
(c) is the important pass: a gate that "caught" the implied spoiler would be over-matching
on meaning it cannot parse, and would falsely reassure. Verifying that it honestly does
NOT catch (c) is how we confirmed it knows its own boundary. A gate must be trusted for
exactly what it checks and no more.

## 2026-07-21 - SET-PIECE COVERAGE gate: a fixed threshold copied from one film false-fires on the next (tier-relative is the honest fix)

The fifth linear gate. A followability-critical fight needs no long unnarrated
stretch: within a human-confirmed, dense-verified set-piece range, no gap between
consecutive narration lines (or from a range edge) may exceed a max-gap. Same
lineage as the others: reads DATA not memory (a machine-readable `set-pieces` block
in beats_proposal.md), linear-only, additive, zero regression on the three finished
films, no-op without a block, declares its own limits every run.

### The valuable lesson: 90s was right for John Wick and WRONG for Spider-Man
The first threshold was a flat 90-second max-gap - calibrated to the John Wick house
fight, which narrates a line every ~30-60s across five stages. Run against the
VIEWER-APPROVED Spider-Man draft, that 90s false-fired: SP1 Highway (worst gap 120s)
and SP3 Statue (198s) both flagged - fights the viewer had already confirmed were
followable. The cause is not a bad draft; it is a bad threshold. Spider-Man is a
sparser recap (fuller_recap, 16.9 min over 148 min; whole-film MEDIAN line gap 88s)
than the denser John Wick cut 90s came from. A gap of 120s is below Spider-Man's own
rhythm-and-a-half; it only looks alarming against a number borrowed from a different
film's cadence.

The rule: **a fixed threshold copied from one film will false-fire on another whose
narration cadence differs.** The fix was NOT a bigger fixed number (240s flat would
"work" for these two but silently mis-scale on film #3). The fix is tier-relative:
threshold = max(240s floor, 3 x the recap's OWN median line gap). The gate adapts to
each recap's cadence, so it flags only a stretch that is both absolutely long AND
several times this recap's own rhythm. This is the same principle as "tier follows
the film, the gate follows the tier" and beat-coverage's "no >=2 consecutive
uncovered" over a raw %: encode the actual failure mode (a hole a viewer can't
follow), not a magic number. See 2026-07-04 (tier choice must match TALKINESS, not
shot count) - the same truth, now enforced in a gate: an action film narrates sparser,
so its followability threshold must loosen WITH its cadence, automatically.

Validated: broken Statue (sparse 3-line binding, ~390s hole) -> FLAGS; fixed/shipped
Statue (worst 198s) -> passes; the tier-relative 264s threshold (= max(240, 3x88))
cleanly separates them where 90s could not.

### v1 PROVISIONAL - the median term is self-referential
Do NOT treat 264s / 3x-median as settled. The threshold scales from the recap's own
median gap, which is self-referential: a UNIFORMLY-lazy recap (thin everywhere) raises
its own median, which raises the threshold, which loosens the gate - a recap could be
sparse enough to be bad yet never trip its own adaptive bar. It works for Spider-Man
because Spider-Man's 88s median is HONEST (a genuine fuller_recap cadence, viewer-
approved), not lazy. But "honest median" is an assumption that holds for one film.
This is calibrated on ONE film; revisit after film #2. Candidate hardening once we
have a second data point: cap the median term (e.g. min(3x median, absolute ceiling)),
or derive the reference from the tier's declared runtime band rather than the draft's
own gaps (breaks the self-reference). Logged as v1; the gate prints "(provisional)"
every run so no one mistakes it for settled.

### Machine-proposed, human-confirmed - and it forced an honest reading of the footage
The `set-pieces` block is authored proposal-then-confirm: Wikipedia + S6 beats name
WHICH fights exist (content), then each [start,end] is DENSE frame-verified (1-2s
frames start-to-finish - the exact Statue scenes that drifted 2 min under sampling
twice), then the human confirms keep/drop and eyeballs the range. Building it surfaced
two truths the tag-only approach would have missed: (1) the Statue "battle" is NOT
continuous combat - it is ~3 min of scaffold planning-dialogue, then combat, then a
Strange-spell VFX climax + the MJ fall/catch (an emotional beat) before the Goblin
rooftop fight. Marking one big range would have measured the dialogue lulls and
false-fired on quiet scenes - the exact thing the gate forbids. The honest fix was to
mark ONLY the real combat ranges (SP3 Statue-combat 01:53:44-02:03:20; SP4 Goblin
rooftop 02:07:00-02:10:00) and leave the non-combat stretches deliberately UNMARKED,
so they are never measured. (2) An S6 beat is a set-piece CANDIDATE, not a confirmed
one: the forget-spell is S6 but not followability-critical -> dropped. Neither the
`action` depicts tag (per-shot, incomplete, no range) nor an S6 beat (a point, over-
broad) reliably bounds a set-piece as a RANGE with an END; only a human dense-verify
does.

### Test (d): the gate enforces dense-verification of its OWN foundation
Acceptance included a case with no analogue in the other gates except REVEAL-TIMING's
"honestly does NOT catch the implied spoiler": a KEPT set-piece row marked
`verified: sampled` must WARN that its range is untrusted. A boundary you sampled is a
boundary that can drift (the 2-min MJ-catch error was born exactly this way), and a
coverage measurement over a wrong range is worse than none - it reassures falsely. So
the gate refuses to silently trust a non-dense range: it flags it. The gate is honest
about the quality of its own inputs, not just its outputs. Stage: SCRIPT only (an
outline is thin everywhere by design; density is a defect only once enriching -
mirrors DRAFT-TARGET). Soft-only (escalate sev, never downgrade a hard). This
completes the clean three-way stage split: beat-coverage + REVEAL-TIMING are always-on
(a hole/spoiler is wrong even in an outline); SET-PIECE + DRAFT-TARGET are script-only
(density is only expected once enriching).
