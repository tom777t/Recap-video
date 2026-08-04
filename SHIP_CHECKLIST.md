# RECAP SHIP CHECKLIST (the A-W standard)

A recap is DONE only when every item passes. Checked BEFORE the final render —
never "ship then patch". The validator + linter enforce the objective items;
the rest are judged in the scripting self-review loop.

## CORE PRINCIPLE (read first)
Passing the checklist is not enough. A recap ships ONLY when all four pass:
1. Machine gates pass (validator + linter).
2. Human judgment passes (the self-grade loop).
3. First-time viewer audit passes (Stage 7A — read it as if you never saw the film).
4. Render QA passes (Stage 8 — watch the actual video at 1.5-2x).

**Viewer experience is the final authority.** When two goals conflict:
Story > Compression · Clarity > Runtime · Viewer experience > Checklist compliance.

## A. Comprehension (understanding the STORY)
- [ ] Spine (who/wants/obstacle) established within the first 30-45s after the hook.
- [ ] Every key character named and given a role on first appearance.
- [ ] Every beat communicates WHO is acting, WHAT they want, WHAT is at stake.
- [ ] Parallel threads clearly labeled.
- [ ] A first-time viewer can accurately explain the plot, major characters,
      objectives, and outcomes WITHOUT additional context.

Focus: understanding the story. Questions to test it:
- Who are we following?  - What do they want?  - What is stopping them?
- What happened?  - What was the result?

## B. Accuracy (never invent)
- [ ] All names REAL (verified in names.json) or generic role. NEVER invent a name.
- [ ] No invented plot points; correct roles; consistent names (actor name only in intro).

## C. Visual quality (no repetition / no mismatch)
A VISUAL FAMILY = same character(s) + same action + same narrative purpose
(e.g. wound-cauterization, bomb-assembly, computer-hacking, trap-building,
forest-stalking). Families are judged by VIEWER MEMORY, not by file identity.
- [ ] No visual family appears more than TWICE. Different angle / crop / zoom /
      source clip of the SAME action still counts as the same family.
- [ ] The test is: "Would a viewer feel like they just saw this already?" If yes,
      it is a repeat - replace it or move to the actual narrated scene's footage.
- [ ] Same-scene shots count as DISTINCT only across clearly different narrative
      stages (setup / midpoint reversal / final outcome) or substantially
      different information. Otherwise they are one family.
- [ ] Applies to BOTH explicit-timestamp clips AND pool clips. Source proximity is
      only a hint; the action + purpose define the family.
- [ ] Reuse caps: normal <=2, hero <=2, each visual family <=2.
- [ ] Voice matches the slide (script from frame montages).
- [ ] No credit-text / watermark frames.
- [ ] Action breathes via hold; footage never slowed.
- [ ] Action ratio matches the film (no forced quota).

## D. Engagement
- [ ] Shocking, specific cold open (first 5s stop the scroll). SEE "R. THE HOOK" - this is the make-or-break line.
- [ ] Open loop every ~20-30s.
- [ ] Fast pacing, show-don't-tell, strong verbs.
- [ ] Emotional per-line delivery (rise tense, hush mystery).

## R. THE HOOK (first line = 9-10/10 or rewrite it)
The opening line decides whether anyone watches. It must score 9-10. Test it:
- [ ] **Leads with the shock, not the setup.** Open ON the jarring image/fact, not
      the mundane lead-up. Bad: "A man drops his daughter at a shop, then it
      explodes." Good: "This harmless old man just walked into a politician's
      office and threatened to blow up everything he loves - and he means it."
- [ ] **Contains a curiosity gap / question the viewer NEEDS answered** ("but what
      nobody knew was..." / "and the reason why is insane").
- [ ] **Teases the biggest reversal/twist of the movie** without spoiling it (the
      harmless man is a trained killer; the victim becomes the hunter).
- [ ] **Specific + concrete + a little bizarre** (real stakes, a vivid detail),
      never generic ("this is a story about revenge").
- [ ] **Front-loaded:** the most gripping word/idea is in the first ~5 words.
- [ ] **Implies a promise** of payoff to come ("how he does it is unbelievable").
- [ ] Self-grade the hook 1-10. If under 9, rewrite before anything else.

## S. Transition Naturalness (scene-to-scene cause -> effect)
The viewer understands WHY a scene happens BEFORE it happens. Scene-to-scene
cause -> effect is clear. Setup arrives before the event, not after it. Every
major scene feels like the natural consequence of the previous scene.
- [ ] Scene-to-scene cause -> effect is explicit (not just plot-level).
- [ ] Setup arrives BEFORE the event, never after.
- [ ] Each major scene feels like the natural consequence of the one before it.
- [ ] A first-time viewer never thinks: "Where did this come from?" / "Why are we
      here?" / "How did we get here?"
- [ ] Action -> Explanation is a FAILURE. Setup -> Action -> Consequence is the default.

## U. Action Context Audit
Before every major action sequence, verify the audience understands:
- [ ] WHO is involved.
- [ ] WHY it is happening.
- [ ] WHAT triggered it.
- [ ] WHAT is at stake.
- [ ] Every major action sequence follows: **Setup -> Action -> Consequence.**
- [ ] Avoid Action -> Explanation.
- [ ] Action scenes feel EARNED, not inserted for excitement alone.

## E. Action Breathing Room (judge per film)
Action should breathe. Narration should RIDE the action, not replace it. Major
action sequences need enough visual space for viewers to EXPERIENCE the action
itself while still understanding objectives, turning points, and consequences.
Neither pure montage nor constant narration is ideal - the balance depends on how
much story the action is carrying. The goal is NOT maximum explanation; it is
maximum understanding while preserving the feeling of watching the film.

**Action Experience Audit** (after the script + footage plan, review every major
action sequence as a viewer):
- [ ] Can I understand what each side is trying to achieve?
- [ ] Can I follow the turning points inside the action?
- [ ] Does the action change the story, or merely interrupt it?
- [ ] Am I experiencing the action itself, or only hearing it described?
- [ ] Am I watching a montage, or a sequence with a beginning, development, and consequence?

- [ ] If it feels like an AUDIOBOOK -> reduce narration. If it feels like RANDOM
      FOOTAGE -> increase narrative guidance. Fix the balance BEFORE render.
- [ ] Tools (serve the principle, don't apply mechanically): ~6-10s silent
      showcase holds (music swells + SFX) on high-motion footage; montage hold
      (2-3 shots) for big set-pieces; holds capped ~10s.

## F. Structure & branding
- [ ] Hook -> "This is Serabudabu..." intro -> body -> outro.
- [ ] Famous-actor intro on the actor's face (1-3 big names).
- [ ] Adaptive ending: standalone = sign-off; chaptered = next-chapter teaser.
- [ ] Ending in correct sequence (climax -> resolution last).

## G. Technical & Runtime
Runtime is an OUTCOME, not a target. (It is set by STORY UNIT PLANNING - see
Stage 6B: list the units, score complexity, allocate coverage; ~170 words/min.)
- [ ] **Runtime is determined by story complexity (typically 10-15 minutes).**
- [ ] Priority order: 1. Comprehension  2. Narrative flow  3. Emotional continuity
      4. Transition quality  5. Engagement  6. Runtime.
- [ ] The goal is NOT compression. The goal is **clarity per minute.**
- [ ] A slightly longer recap is preferable to a rushed one. Never cut necessary
      setup to hit a number; never pad to reach one.
- [ ] **COVERAGE > DURATION.** When a draft comes in SHORTER than the planned
      runtime, do NOT optimize for runtime - check whether all major story units,
      character arcs, conflicts, revelations, and emotional turning points got
      adequate coverage. If it's short because important units were compressed,
      merged, or skipped, EXPAND (don't approve). Expansion must be MEANINGFUL
      coverage only - never filler/repetition/padding. Valid expansion: under-
      developed character arcs · compressed story units · conflicts lacking
      progression · broken cause-effect chains · emotional beats summarized
      instead of dramatized · key discoveries/decisions/reversals jammed into one
      beat. If under-covered, explicitly name the gaps + estimate how many beats
      are needed BEFORE rendering. Approve only when coverage fits the source's
      complexity - even if the runtime target was technically met.
- [ ] Crossfades, ducked music, SFX, loudness ~-15 LUFS, no clipping.
- [ ] Captions per preference. Thumbnail + titles generated.

## H. Narrative Momentum
- [ ] Every beat reveals information, escalates conflict, raises a question,
      answers a question, creates a consequence, or improves understanding.
- [ ] No beat repeats information the viewer already knows.
- [ ] A beat may be removed ONLY if it reduces none of: clarity, narrative flow,
      transition quality, setup, consequences, emotional continuity, or viewer
      understanding.
- [ ] Do not confuse compression with momentum.
- [ ] Setup, reactions, consequences, and transitions COUNT as progress when they
      improve understanding of what happens next.
- [ ] The story should feel CONNECTED, not merely fast.

## I. Narration Value
- [ ] Narration adds value beyond the obvious visual (motivation, consequences, stakes, irony, hidden info, decisions).
- [ ] Tell the story, don't describe the footage.

## J. Twist Protection
- [ ] Never reveal a major twist before the film does.
- [ ] Foreshadow only to raise curiosity without killing suspense.

## K. Emotional Continuity
- [ ] Track the protagonist's emotional arc; narration reflects shifts, not just events.

## L. Visual Freshness
- [ ] Prioritize footage from the current narrative moment.
- [ ] Old footage only for flashback / unavailable / explanation. Visual timeline ~ narrative timeline.

## M. Read-Aloud Test
- [ ] Sounds natural spoken; short sentences, one idea each, conversational.
- [ ] Rewrite anything that reads "written" not "spoken".

## N. Confusion Hotspot Scan
- [ ] No unclear pronouns; no multiple unnamed same-type characters in a scene.
- [ ] No unmarked location/timeline jumps; parallel storylines distinguishable.

## O. Thumbnail Gate
- [ ] One dominant subject, one clear emotion, one source of danger/conflict/mystery.
- [ ] No clutter; readable at mobile size.

## P. Viewer Value
- [ ] Emphasize clever decisions, costly mistakes, irony, shocking consequences, payoffs, reversals.
- [ ] Feels like a story, not a plot summary.

## Q. 7-Second Clarity Rule
- [ ] At any random point, within ~7s a viewer knows who we follow, what they want, what's happening now.

## V. Final Story Audit (after the script, BEFORE render)
Read the entire recap start to finish as a FIRST-TIME viewer. For every section ask:
- [ ] Is this the most natural next thing to happen?
- [ ] Would a viewer understand why we are here?
- [ ] Does this reveal feel earned, or dumped?
- [ ] Is this scene advancing the story, or merely reporting information?
- [ ] Have we repeated a visual or idea recently?

Especially flag: abrupt character switches · abrupt location changes · info dumps ·
unexplained investigations · action without setup · outcomes without process ·
repeated visual concepts · emotional jumps.

Every flagged moment must be rewritten, given more setup, given a smoother
transition, given a stronger consequence, or removed. The goal is NOT checklist
compliance - it is making the viewer feel "Of course this happened next."
**Render only after this audit passes. Fix flagged moments in place; never report
them at the end.** (Recorded to projects/NAME/qa.md.)

## W. Natural Progression Audit (forward-looking; complements S)
S looks BACKWARD ("does this scene have setup before it?"). W looks FORWARD: does
each beat create an EXPECTATION the next beat satisfies? For every major beat ask:
"If the recap stopped here, what would a first-time viewer naturally expect to
happen next?" Then compare that expectation with the actual next beat.
- [ ] Each beat's natural expectation is met by the next beat - OR the gap is
      deliberately bridged.
- [ ] If the gap feels too large, flag **[NATURAL-PROGRESSION-FAIL]** and add a
      bridge, clue, consequence, discovery, decision, or objective that makes the
      transition feel inevitable.
- [ ] Goal: the viewer feels "That makes sense," never "Wait, how did we get here?"

Run this at the SKELETON stage (6A, cheapest) and again beat-by-beat in the
first-time viewer audit (7A). Fix in place; record to projects/NAME/qa.md.

---

## THE VALIDATION OBJECTIVE
The validator must answer TWO questions, not one:
1. "Can the audience understand the plot?"  (comprehension)
2. "Will the audience understand WHY this scene is happening BEFORE it starts?"
   (transition naturalness)
The primary failure mode we are guarding against is NOT plot confusion. It is
scene-to-scene DISCONNECT caused by over-compression and missing connective
tissue -- action that arrives before its setup. Setup before confusion, always.

## AUTOMATION MODEL
- Machine gates / flags: reuse caps (label + family <=2, now covering EXPLICIT
  clips via `visual` tags), predicted length, action ratio, invented names,
  vague-pronoun + confusion flags, read-aloud sentence checks, visual-freshness
  timestamp gap, scrambled-ending order, the ACTION-SETUP check (who/why/trigger/
  stakes before each action beat), and the VISUAL-REPEAT / VISUAL-MEMORY checks
  (action-family >2; source-proximity hint).
- In-loop judgment (me): momentum (H), narration value (I), twist timing (J),
  emotional arc (K), viewer value (P), 7-second clarity (Q), transition
  naturalness (S), action breathing + action experience (E), action context (U),
  final story audit (V), natural progression (W), viewer-memory repetition (C),
  hook, engagement.

## PART 2 - THE PROCESS (original video -> finished recap)
Story > Compression. Clarity > Runtime. Viewer experience > Checklist compliance.

1. **ingest** - download + transcribe (foreign: --model small --translate).
   VERIFY THE AUDIO IS NOT SILENT before anything else.
2. **frames** - sample montages so every clip matches its narration.
3. **analyze** - measure action vs dialogue density; set the recap's ratio to match.
4. **broll** - build the pool with `family` tags AND assign a `visual` action-tag
   to explicit clips (same action = same family; see C).
5. **names -> names.json** - record every verified name; never invent.
6A. **STORY SKELETON AUDIT (before writing prose).** Write a beats-only skeleton
    (Hook -> Inciting incident -> Investigation -> Escalation -> Reveal -> Climax
    -> Resolution). Audit it: (1) does every beat naturally cause the next? (2) is
    any beat present ONLY because it happened in the movie? (3) is a transition
    between beats missing? (4) would a first-timer understand the move from beat A
    to B? (5) does each beat answer a previous question and create a new one?
    (6) NATURAL PROGRESSION (W): for each beat, what would a first-timer expect to
    happen next - and does the next beat deliver or deliberately bridge it? Fix
    STRUCTURE here, before spending 1500-2500 words. Save to projects/NAME/skeleton.txt.
6B. **STORY UNIT PLANNING (mandatory, BEFORE writing).** Plan from the start - do
    NOT write a compressed draft and expand later. Identify the major STORY UNITS
    (a unit is NOT a scene - it's a meaningful section where a goal is introduced,
    a problem appears, a clue is discovered, a relationship changes, a major
    decision is made, a conflict escalates, a reveal occurs, or a consequence
    reshapes the story). Example units (action-adventure): Setup, Treasure Hunt,
    First Complication, Rival Interference, Capture, Escape, Final Confrontation,
    Resolution. (mystery): Crime, Investigation Begins, First Lead, False Lead, New
    Discovery, Suspect Revealed, Twist, Confrontation, Resolution.
    - List ALL story units. For EACH unit identify: (a) the characters introduced,
      (b) the emotional purpose, (c) the narrative QUESTION it answers, (d) the next
      QUESTION it creates. Score each Low / Medium / High complexity.
    - VALIDATE THE PLAN FIRST. Do NOT optimize toward a predicted runtime. If the
      unit plan naturally requires more runtime, ALLOW it. A short runtime is not
      evidence of efficiency. Runtime is TOO SHORT if any major character
      introduction, emotional setup, fear sequence, investigation step, relationship
      change, or payoff has to be compressed into SUMMARY rather than told as STORY.
    - ENSEMBLE FILMS (multiple co-leads, e.g. IT, horror-group, heist-crew): runtime
      emerges from STORY-UNIT COVERAGE, not from film length. Each co-lead needs a
      real introduction + their own arc/fear/payoff - never a shared one-line list.
    - Allocate COVERAGE per unit. High-complexity units get MORE narration (the
      viewer must follow reasoning, clues, motivations, consequences). Use
      ~170 finished words/min only to convert coverage into approximate runtime.
    - OVER-COMPRESSION warning signs (must avoid): multiple clues squeezed into one
      sentence; travel/investigation/discovery chains skipped; a reveal with no
      showing of how it was earned; a character suddenly knowing something; a
      location change with no explanation; multiple units collapsed into one
      paragraph.
    - The question is NOT "how short can this be?" but "what story units must the
      audience EXPERIENCE to understand the narrative naturally?" Runtime is an
      outcome of the units, never a cap; target UNDERSTANDING, not compression.
    Write the unit list + per-unit complexity + coverage plan into skeleton.txt and
    write the draft TO it. (See "STORY UNIT PLANNING" in recap_style.md.)
6.  **SCRIPT WRITING.** Write as BOTH a cause -> consequence chain AND a
    question -> answer -> new-question chain. Every section answers the previous
    question while opening the next; pull the viewer by CURIOSITY, not by info.
    Before every action sequence establish who / why / trigger / stakes - action
    must never be the first explanation of itself.
7.  **validate (gates + linter)** - reuse/family/visual-repeat caps, action-setup,
    names, clarity, read-aloud, freshness, length, ending order. Loop until clean.
7A. **FIRST-TIME VIEWER AUDIT (after validation, before render).** Read the whole
    recap as if the movie was never seen. Per section: (1) why are we here? (2) how
    did we get here? (3) who is this person? (4) what is the current objective? (5)
    what changed since the previous section? Also run the NATURAL PROGRESSION (W)
    pass beat-by-beat: "if it stopped here, what would the viewer expect next?" vs
    the actual next beat - flag [NATURAL-PROGRESSION-FAIL] on big gaps. And run the
    ACTION EXPERIENCE AUDIT (E) on every major action sequence: can the viewer
    follow each side's goal + the turning points; does the action change the story;
    is the viewer experiencing it or only hearing it described; audiobook -> less
    narration, random footage -> more guidance. Flag abrupt transitions, info dumps,
    unexplained investigations, action without setup, outcomes without process,
    emotional jumps, confusing reveals. FIX before rendering; re-audit until clean;
    DO NOT report failures at the end. Save findings + fixes to projects/NAME/qa.md.
8.  **RENDER QA.** Render -> WATCH the actual video at 1.5-2x -> log confusion
    moments, weak transitions, repeated visuals, emotional discontinuities -> patch
    if needed -> final ship. Evaluate the real viewing experience, not just the
    validator output. (Append to qa.md.)
9.  **POST-SHIP METRICS** -> projects/NAME/metrics.md: runtime, predicted runtime,
    confusion moments found in QA, transition fixes applied, visual-repetition
    fixes applied, final self-grade. Tracks recurring failure modes over projects.

A recap ships only when machine gates + human judgment + first-time viewer audit +
render QA all pass. Viewer experience is the final authority.

## HARD CONSTRAINTS
TTS voice kept (main ceiling); source footage quality; foreign needs small+translate;
network blocks fresh model downloads (use hotspot; base + small now cached).
