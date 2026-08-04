# STYLE_GUIDE.md

Voice register and interpretive narration patterns for commercial recap output.
Complements TAGGING_GUIDE.md (footage discipline) and SCRIPTING_CHECKLIST.md
(audit rules) by specifying HOW narration sounds, not just what it claims.

This guide applies when commercial appeal is the target (vs pure documentary
restraint). Use selectively based on channel positioning.

## 1. Voice Register Specifications

Two registers supported:

### Register A: Restrained Documentary
- Descriptive, footage-first
- Minimal narrator interpretation
- Audit-strictest mode
- Use for: archival, educational, prestige channel positioning
- Example: original Prisoners draft tone

### Register B: Engaged Commercial (default for film recap channels)
- Mix descriptive + interpretive
- Narrator extracts meaning, builds context
- Emotional engagement at key beats
- Theme statements distill story lessons in-line
- Audit-compatible (interpretive lines still bind to visible content)
- Use for: YouTube/TikTok film recap channels, Sakura/Quin style
- Example: target style for Gone Girl restart

## 2. Interpretive Language Patterns

Allowed interpretive constructions in Register B:

### Context Establishment
Pattern: After introducing a character or element, add ONE interpretive line
explaining significance.

Example:
- Description: "Amy is a kind of celebrity. Her parents wrote a beloved
  children's series, Amazing Amy, modeled on their daughter."
- Add interpretive: "And from the start, the fictional Amazing Amy was always
  one polished step better than the real girl - the version Amy could never
  live up to, even in her own family's eyes."

This pattern moves beyond pure plot retelling to character psychology grounded
in visible content (the books exist on screen).

### Marriage/Relationship Tension
Pattern: Show visible deterioration THEN add interpretive insight about why
it matters.

Example:
- Description: "the recession takes their jobs, the money runs thin"
- Add interpretive: "But for Amy, this is more than financial strain. The
  Cool Girl performance was sustainable when Nick was the version of himself
  she had fallen in love with. Without the money, the apartment, the New York
  life - Nick becomes someone else, and the marriage she had built her
  identity around starts to disappear."

This pattern names the emotional stakes the footage implies but doesn't
state explicitly.

### Stakes Articulation
Pattern: At pivot moments, state what's at stake for protagonists.

Example:
- Description: "Nick struggles with the simplest questions about his wife."
- Add interpretive: "What looks like distance to the detectives is actually
  guilt - not the guilt of a killer, but the guilt of a husband who realized
  too late that he had stopped paying attention to the woman he married."

This pattern guides viewer interpretation of ambiguous behavior.

### Theme Distillation
Pattern: At act boundaries or major beats, ONE sentence distilling thematic
significance.

Example:
- After establishing Amazing Amy backstory: "Amy has been measured against
  a fictional version of herself her entire life - and she has been losing."
- After Cool Girl reveal: "What Amy reveals is something far more uncomfortable
  than a kidnapping: that the woman Nick loved was a performance, and the
  resentment beneath it has been building for years."

Use sparingly - 1 theme line per major beat maximum.

## 3. Engagement Patterns

### Opening Hooks (See template variants in templates/intro_hook.md)

For Register B, hook MUST include:
- Visual intrigue moment (not slow atmospheric build)
- Question/tension that the recap promises to answer
- Channel branding integrated naturally

### Mid-Recap Retention Prompts
At Act boundaries OR before major reveals, ONE line that creates curiosity gap.

Examples:
- "But Amy's plan has a weakness she did not see coming."
- "What Nick is about to discover will change everything he thought he knew
  about his wife."
- "And the woman Nick is about to meet will not be the woman he married."

Use sparingly - 2-3 per recap maximum. Overuse feels manipulative.

### Rhetorical Engagement
Direct viewer address allowed in Register B for hooks/outros only.

Allowed:
- "What would you do if your wife disappeared on your anniversary?"
- "How well do you really know the person beside you?"
- "If you enjoyed this dive, you'll like what's coming next."

Avoided:
- Mid-recap viewer questions (breaks immersion)
- "Stick around to find out..." patronizing prompts
- "Make sure to like and subscribe" mid-narration

## 4. Discipline Guardrails (Audit Compatible)

Interpretive layer MUST follow these rules to remain audit-compatible:

### Rule G1: Interpretive content must connect to visible content
Lines extracting psychology/theme must bind to a shot that establishes the
basis. Cannot fabricate motivation from off-screen.

GOOD: Over Amazing Amy book launch shot, "she has been measured against a
fictional version of herself her entire life" - book launch shot visibly
establishes Amazing Amy character.

BAD: Over Amy driving shot, "she was abused as a child" - no visible basis
for claim in footage.

### Rule G2: Interpretive content stays within film's text
Use only psychology/themes the FILM establishes. Don't import outside
interpretations.

GOOD: Gone Girl's text supports "Amy's identity built on performance" reading.
BAD: Importing fan-theory interpretations not grounded in film's content.

### Rule G3: Maintain twist/spoiler discipline
Interpretive lines pre-twist CANNOT leak post-twist information.

GOOD pre-twist L15: "according to her account the marriage slowly curdles"
BAD pre-twist: "Amy is planning her revenge" (post-twist info leaked)

### Rule G4: Restraint at climaxes
At major emotional moments (deaths, reveals, iconic shots), narration goes
QUIETER not louder. Let footage carry the weight.

GOOD: At Holly reveal, "The quiet aunt was never what she seemed."
BAD: At Holly reveal, "In one of cinema's most shocking twists, Villeneuve
delivers a moment that recontextualizes everything..."

### Rule G5: Theme lines must be earned
Don't insert theme statements before viewer has seen enough content to
understand them. Theme distillation happens AFTER establishing beats, not
before.

## 5. Channel Positioning Calibration

Different audiences prefer different register intensities:

### Light Register B (current Gone Girl style, post-update)
- 2-3 interpretive lines per major character introduction
- 1-2 theme statements per recap
- Restrained climax narration
- Standard hook pattern

### Medium Register B (Sakura Review style approximation)
- 4-5 interpretive lines per major character
- 3-4 theme statements
- Slightly more dramatic climax narration
- Viral hook patterns

### Heavy Register B (high-engagement viral channel style)
- Constant interpretive layer
- Theme statements every 2-3 beats
- Dramatic climax narration
- Aggressive viral hook + retention prompts

Recommendation: Start LIGHT Register B for Film 2 restart. Iterate based on
audience response. Heavy register risks feeling manipulative/cheap.

## 6. Application Checklist

When writing draft in Register B:

- [ ] Each major character introduction has 1-2 context lines
- [ ] Each act boundary has 1 theme distillation line
- [ ] Opening hook follows viral pattern (see template)
- [ ] 2-3 mid-recap retention prompts placed at curiosity peaks
- [ ] Climaxes use restrained narration (Rule G4)
- [ ] All interpretive content binds to visible footage (Rule G1)
- [ ] Twist discipline maintained (Rule G3)

## 7. Depth Expectations Per Genre Tier (2026-06-22)

Register sets HOW narration sounds; depth sets HOW MUCH of the film the visual
catalogue covers. Pick the tier up front from the intended runtime and catalogue
to it from the START (TAGGING_GUIDE S10), rather than under-cataloguing and
expanding reactively.

| Tier           | Runtime    | Total shots | Shots/beat | Feel |
|----------------|------------|-------------|------------|------|
| `recap`        | 9-13 min   | 60-80       | 2-3        | Tight retelling - main beats, key moments |
| `fuller_recap` | 14-17 min  | 90-110      | 3          | Fuller - sub-moments, reactions, more motif weaving |
| `video_essay`  | 18+ min    | 110-130     | 3-4        | Deep - establishing + action + reaction + aftermath per beat, systematic motifs |

Guiding principle (user priority): **"đầy đủ rõ ràng chi tiết"** - quality
fullness over length per se. A deeper tier means more COVERAGE of real
sub-moments (more reactions, more motif appearances, more of the film's own
detail shown), NOT slower pacing or padded narration. The goal is to show more
of what is actually there, not to stretch what little you catalogued.

Tier vs register interact:
- A `video_essay` tier with Medium Register B = the Parasite 18-min experiment
  profile: many shots, interpretive layer, systematic motifs, restrained
  climaxes, ~68-69% capacity fill (room to breathe, not over-stuffed).
- A `recap` tier with Light Register B = a tight 10-min ship: fewer shots, fewer
  interpretive lines, fast pace.

Declare the tier in `beats_proposal.md` (`depth_target: video_essay`) and verify
the catalogue meets it with the Stage 2 depth audit
(`python -m pipeline.catalogue --project NAME --coverage`) before authoring.

### 7b. Draft depth per tier - the DRAFT-TARGET gate (2026-06-30)

Stage 2 depth fills the SHOT catalogue; draft depth fills the NARRATION. A draft
can bind 100 shots and STILL run short of its tier, because short lines leave
most of each shot's capacity unused. Across films (Joker v1, Parasite v1,
Interstellar v1) the FIRST draft consistently under-authored the declared tier's
real runtime - the same under-authoring bias the Stage 2 enhancement fixed at the
catalogue level.

Two numbers matter, and they are different:

- **Conservative estimate** (the old `Est. narration` line): words / 170 WPM.
- **Real-rate estimate** (`[DRAFT-TARGET]`): words / 3.5 words-per-second, the
  EMPIRICALLY calibrated Andrew +22% rate (~211 WPM). This is ~24% faster, so the
  conservative estimate OVERSHOOTS real runtime. Always target the real-rate
  figure. A draft that reads "15 min conservative" may only run ~12 min for real.

Real-rate runtime floors per tier (the gate warns below these):

| Tier           | Runtime band | Real-rate floor | Healthy capacity fill |
|----------------|--------------|-----------------|-----------------------|
| `recap`        | 9-13 min     | 9.0 min         | 70-85% |
| `fuller_recap` | 14-17 min    | 13.5 min        | 70-85% |
| `video_essay`  | 18+ min      | 17.0 min        | 70-85% |

Capacity fill = draft words / sum of the shots' word ceilings. Below ~65% the
draft is under-authored (enrich the surfaced units). Above ~90% it is
over-stuffed and will need slow-motion on many shots.

The tricky case: UNDER runtime AND OVER fill at the same time. That means the
lines are already near capacity, so you cannot simply pad them - you gain runtime
by binding MORE catalogued shots (use the depth you built) or by adding earned
silence, not by pushing every shot into slow-motion.

Run `recap.py draft --project NAME` and read the `[DRAFT-TARGET]` block; satisfy
SCRIPTING_CHECKLIST C16 before render.
