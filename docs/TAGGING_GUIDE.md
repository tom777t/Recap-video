# TAGGING GUIDE

This is the discipline doc for tagging clips in `broll.json` and `shots.json`.
Every clip you tag here becomes input to the binding audit. If your tags are
loose, the audit's verification becomes loose. The audit is only as honest as
the tags.


## Why this exists

The audit catches narration-vs-footage mismatches by comparing each line's
`claim` against the bound clip's `depicts` and `chars`. This works only if
those tags describe what is **actually visible** in the clip, not what is
nearby or what the scene is about in a broader sense.

A clip tagged loosely (e.g. `depicts: ["reveal", "action"]` when only one of
those is the dominant moment) silently weakens the audit: any narration
claiming either tag will pass, even when the visible moment is just one of
them. The IT 2017 meet-vs-bite swap was exactly this failure mode.

The rule below is the one that prevents it.


## The single rule

**One clip = one primary moment.**

Tag what the viewer SEES in this clip's window, not the surrounding scene.
If you cannot describe the clip in one short sentence, the clip is too long
and should be split into separate entries (one per moment).

Concrete consequences:

- A single clip should carry **1 or 2** `depicts` tags. Three or more is a
  signal to split the clip.
- Tags should describe the moment that is **consistently visible across the
  whole window** of the clip, not just at the start or just at the end.
- If a 10-second clip transitions through stages (reveal -> action), split it
  into two entries (one for the reveal portion, one for the action portion)
  rather than tagging the single clip with both stages.


## Why "one moment" matters technically

`render.py` calls `broll.resolve(label, need_dur, seed=lid)` which picks a
sub-window of the labelled clip with deterministic seeded jitter. Different
lines using the same pool label get different sub-windows. If the clip's
content varies across its full window, two lines hitting different sub-windows
will see different content. The narration may match one sub-window but not
the other. The audit cannot tell which sub-window each line will hit.

Single-moment tagging defeats this: when content is consistent across the
window, jitter doesn't change what's visible, so audit predictions stay
correct.


## The `depicts` vocabulary

Use exactly these eleven values. The `tag_audit` module enforces them; the
schema rejects unknown values.

### `setup`

A moment that establishes context BEFORE an event happens. Character
introduction, place introduction, before-state. The setup itself is not the
event.

- **Use when:** the clip shows who/where/what before the consequential thing
  takes place.
- **Don't use when:** the consequential thing already happened in this clip.
- **Examples:** Georgie in raincoat walking toward storm drain (before the
  bite). Eddie introducing himself. Camera moving down the empty corridor
  before Pennywise appears.

### `reveal`

The moment a previously-hidden identity, character, or threat first becomes
visible. The reveal is the appearance itself, not what happens next.

- **Use when:** the audience first sees the threat / new presence / hidden
  truth in this clip.
- **Don't use when:** the threat is already established and is now acting.
- **Examples:** Pennywise's face emerging from the dark drain. The deadlights
  glowing for the first time. A body floating into view.

### `discovery`

A character finds out NEW INFORMATION (records, clues, evidence, a memory
returning). This is about information, not physical confrontation.

- **Use when:** the character learns something they did not know.
- **Don't use when:** the character physically encounters a threat (that is
  `reveal` or `action`).
- **Examples:** Ben in the library reading old newspapers. Mike piecing
  together that the parents-fire was Pennywise. The Losers comparing notes
  about their visions.

### `dialogue`

Two or more characters exchanging spoken words, where the talking is the
primary moment.

- **Use when:** the clip's content IS the conversation.
- **Don't use when:** characters happen to be talking during an action scene
  (that is `action`, possibly with `dialogue` as a second tag only if the
  conversation is essential to the moment, not background).
- **Examples:** Bill and Beverly's intimate conversation. The Losers arguing
  about going to Neibolt. Pennywise's "we all float down here" speech.

### `reaction`

A character's response (emotional or physical) to a preceding event. The
event itself is not in frame in this clip; the response is.

- **Use when:** the clip is the response shot.
- **Don't use when:** the event and the response are both in frame (then
  `action` covers both, or split into two clips).
- **Examples:** Bill grieving for Georgie. Beverly's face after seeing the
  blood. Ben after Bowers's attack.

### `action`

A physical event with motion and consequence. Fight, attack, chase, bite,
kiss, escape, breach, gunshot.

- **Use when:** the clip IS the physical event.
- **Don't use when:** the clip is showing the build-up (`setup`) or the
  result-state (`aftermath`).
- **Examples:** Pennywise biting Georgie. The Losers beating Pennywise down.
  Ben kissing Beverly to wake her. Bowers carving Ben's stomach.

### `emotion`

A held emotional beat between characters without active dialogue or physical
action. Closer to "the feeling" than to "the moment."

- **Use when:** the clip is a quiet emotional moment that carries meaning by
  presence rather than by what is said or done.
- **Don't use when:** there is active dialogue (use `dialogue`) or action.
- **Examples:** The Losers at the quarry, summer light. Bill and Beverly's
  goodbye look. The group together after the climax.

### `transition`

A bridge moment - characters moving between places, time passing, scene
changing.

- **Use when:** the clip's job in the recap is to move from one scene to
  another, not to convey content of its own.
- **Don't use when:** the clip has its own content.
- **Examples:** The Losers biking through Derry. Pan across the town.
  Time-lapse of the storm.

### `establishing`

A wide shot of a place, location, or world. No specific character focus.

- **Use when:** the clip shows the WHERE, not the WHO or WHAT.
- **Don't use when:** a character is the focus (even if the shot is wide).
- **Examples:** Derry main street. The Neibolt house exterior. The well from
  above.

### `montage`

A compressed-time sequence within a single clip - multiple quick shots
collapsed into one window.

- **Use when:** the source clip itself contains multiple intercut moments.
- **Don't use when:** you are using montage at the recap level (multiple
  clips assembled together); for that, use the draft's `montage: [labels]`
  list, not the depicts tag.
- **Examples:** A research montage in a single take. A training-style cut.

### `aftermath`

The result-state AFTER an event. The event is not in frame; the
consequence-state is.

- **Use when:** the clip is post-event, showing what's left.
- **Don't use when:** the clip is the response shot (use `reaction`) or the
  event itself (use `action`).
- **Examples:** Empty street after Bowers gang attack. Eddie with his cast.
  The lair after Pennywise retreats.


## `chars` rules

The `chars` field lists characters **visible on screen** in this clip's
window. Not characters being talked about. Not characters in the surrounding
scene.

- Use canonical names from `names.json` only. No diminutives ("Bev" -> use
  "Beverly"). No role descriptions ("the bully" -> use "Bowers").
- If two characters are visible, list both. Order does not matter.
- If no recognizable character is visible (wide establishing shot, montage
  of objects, etc.), use an empty list `[]`.
- If you cannot tell who is visible because the framing is unclear, look at
  the frames via `recap.py frames --project NAME --zoom HH:MM:SS` before
  guessing.

The binding audit uses `chars` to verify `claim.subject`. If a line claims
"Bill discovers X" but the bound clip's `chars` does not include Bill, the
audit flags SUBJECT_MISMATCH. This only works if `chars` is accurate to who
is actually on screen.


### What names.json actually covers (and what it does not)

Two known gaps. Both are recorded here because a field that looks live, or a
guard that looks total, is worse than an absent one.

**`actor_alias` is LIVE.** `recap.py names` writes it when a credit carries an
inline nickname - Thai credits do this routinely, as in
`Putthipong "Billkin" Assaratanakul` -> `actor_alias: "Billkin"`. The nickname
is kept because it is what audiences and narration actually call the person,
and since 2026-08-19 the `[NAME]` guard reads it: `schemas.load_name_tokens`
folds characters, actors and aliases into one token set, so narration may write
"Billkin" without being flagged. Narration may also name actors ("Jonah Hill"),
which previously flagged 12 of Superbad's 13 `[NAME]` warnings.

**One-letter names are NOT checked by the `[NAME]` guard, and cannot be.**
The scanner is `[A-Z][a-z]{2,}` - it requires three characters, so a character
called `M` (the lead of howtomakemillions2024) is never read: not validated,
not flagged, invisible. Widening the pattern to catch single capitals inverts
the guard rather than fixing it. Measured: with `m` in names.json, a stray
mid-sentence capital - "the sign above the door read M" - passes silently,
because the lead's own name makes every single letter acceptable. The guard
would launder exactly what it exists to catch.

So one-letter names stay excluded. `recap.py draft` now says so out loud: if
names.json holds any, the run prints an explicit `[NAME] ... are NOT checked`
warning naming them. Those lines need a human eye; nothing is checking them.

**A `[NAME]` flag is now worth reading (fixed 2026-08-19).** The guard used to
test whole-string membership, so a bare surname drawn from a multi-word entry
failed: `Cawley` was flagged because names.json held `Dr. John Cawley`. On the
two finished films, 11 of 14 and 12 of 13 flags were real names. That is why
RULES B8 told authors to ignore `[NAME]` output - a rule written around a
defect rather than a fact.

Tokenising the name set and adding class-based exclusions took the residual to
**0 flags on Shutter Island and 1 on Superbad**, while injected misspellings
are still caught **10/10**. The one survivor is `Goldberg` - Evan Goldberg,
real crew, genuinely not in the cast list, so arguably a correct flag.

Exclusions are named classes, not hand-added entries: `_RANKS` (marshal,
deputy, warden...), `_PLACES` (US states, countries, cities) and the film's own
title, read from `draft.json` `title` / `shots.json` `film_title`. `_stop`
stays for genuine one-offs only. **Do not add nouns to names.json to quiet a
flag** - that half of B8 stands permanently. If a new film produces recurring
false flags, they belong in a class, not in the name list.

Known cost of the fix: recombination is no longer detected. Once `Rachel` and
`Daniels` are each legal tokens, `Rachel Daniels` passes. The old guard caught
1 of 5 such cases and buried it under 11 false flags, so nothing usable was
given up - but a swapped first name is now the guard's blind spot.


## `family` rules

The `family` field on a `broll.json` entry groups visually-similar clips
into a category for **reuse counting only**. It is NOT used for tagging or
matching.

- A family name is for the `[VISUAL-REPEAT]` linter, which caps how many
  times any one family appears across the whole recap (default
  `MAX_FAMILY_USES`).
- Two clips with different content but similar enough that a viewer might
  feel "I just saw this" should share a family name.
- Two clips that depict genuinely different moments should have different
  family names even if they involve the same characters or location.
- The binding audit does NOT use family for matching. It checks the
  specific labelled clip's own `chars` and `depicts`. (This was the
  family-union bug, fixed in `binding_audit.py`.)

Rule of thumb: if you ask "would showing both of these in the recap make a
viewer feel like a repeat?", they belong in the same family. Otherwise, split.


## Worked examples from IT 2017

### Good tagging

**P1 (georgie_drain family):** `chars=["Georgie", "Pennywise"]`,
`depicts=["setup", "reveal"]`. Two tags but they are concurrent in this
window: Georgie is being introduced (setup) AND Pennywise emerges (reveal)
in the same continuous shot. Acceptable when the moments are coincident in
the same window.

**P8 (losers_fight family):** `chars=[all 7 Losers]`, `depicts=["action"]`.
Single tag. The clip's content is one consistent thing across its window:
the kids fighting. Tight, unambiguous.

**clip:01:53:16.0 (cistern):** `chars=["Pennywise", "Bill"]`,
`depicts=["action", "reveal", "discovery"]`. THREE tags - this trips
TAG_TOO_GENEROUS. Even if all three are happening in the scene, the clip
should be split into separate entries (one per moment) so the audit can
verify each precisely.

### Bad tagging (and how to fix)

**P3 (georgie_drain family) was:** `depicts=["reveal", "action"]`.
- Problem: these are temporally distinct stages. The reveal is the appearance
  moment; the action is the bite moment. Render sub-windowing means only one
  is visible at any given line.
- Fix: split P3 into P3a (`depicts=["reveal"]`, just the appearance window)
  and P3b (`depicts=["action"]`, just the bite/grab window).
- Or, if the clip really shows only one of those moments (need to check the
  frames), keep the single accurate tag and drop the other.

**clip:00:08:09.0 was:** `depicts=["dialogue", "action", "reveal"]`.
- Problem: three temporally distinct stages on one clip. The dialogue (Penny
  talking to Georgie), the reveal (the clown's face), and the action (the
  bite) are all separate moments in the source film. They cannot all be
  consistently visible in any sub-window.
- Fix: split into three entries, each covering one moment with a precise
  start/end and a single primary tag.

**clip:00:11:14.0 was:** `depicts=["reaction", "dialogue", "setup"]`.
- Problem: three tags. The note says "Losers talking, garage/bikes" - this
  is actually a single moment of conversation that introduces characters.
- Fix: pick the one strongest tag. If it's primarily characters talking,
  use `["dialogue"]`. If it's primarily character introduction with
  conversation as background, use `["setup"]`. Don't claim all three.


## Checklist before saving a tag

Before committing a new clip's tags to `broll.json` or `shots.json`, ask:

1. Have I watched the actual frames of this clip (not just remembered the
   surrounding scene)?
2. Is the moment I'm tagging visible across the whole window of this clip,
   or only at one end?
3. Can I describe what's visible in one short sentence?
4. Are my `chars` characters that I would point at on the screen if the
   clip was paused?
5. Am I using exactly 1 or 2 `depicts` tags? If 3+, can I split the clip?
6. If 2 tags, do they describe the SAME moment (e.g. `setup + reveal` in
   one continuous shot) or DIFFERENT moments (e.g. `reveal + action` across
   the window)? Only the first is OK.

If any answer is "no" or "I'm not sure," the tag is not ready. Re-check the
frames or split the clip.


## Quick reference: when the audit will flag your tags

| Audit warning | Triggers when | Fix |
|---|---|---|
| `TAG_TOO_GENEROUS` | depicts has >2 tags | Pick the dominant moment, drop the rest, or split the clip into multiple entries |
| `TAG_TEMPORALLY_AMBIGUOUS` | depicts contains a temporally-distinct pair (setup+action, reveal+action, etc.) | Split the clip - one entry per stage with a single tag each |
| `UNVERIFIED` (binding) | depicts and chars are both empty | Tag the clip, or accept that this line is not auditable |
| `SUBJECT_MISMATCH` (binding) | line's claim.subject not in clip's chars | Either add the character to chars (if they ARE visible) or re-point the line to a clip where they are visible |
| `CLAIM_MISMATCH` (binding) | line's claim.type not in clip's depicts | Either fix the tag (if the clip really depicts this) or re-point the line to a clip that does |


## Scripting discipline (script writer side, not tagger side)

Everything above governs how to TAG clips. This section governs how to WRITE
draft.json lines that reference those clips. These are MANDATORY rules. An agent
writing or editing draft.json MUST follow them - they are not suggestions, and
"audit passes" does not excuse breaking them. They exist because the IT 2017
recap passed every rule-based audit and still shipped 14 viewer-visible
mismatches (see projects/it2017/regression_cases.md). The audit checks tags;
these rules close the gap the audit cannot see.

Before declaring draft.json ready, the agent MUST also complete
docs/SCRIPTING_CHECKLIST.md (YES/NO on every item). A draft is not "ready" until
both this section and that checklist are satisfied.

### Rule S1 - Footage-first rule (MANDATORY)
NO line in draft.json may reference a clip that is not ALREADY catalogued in
broll.json or shots.json with tight tags (depicts + chars populated per this
guide). If a needed moment is not catalogued, STOP and catalogue it first - do
NOT write the line yet.
- Forbidden: writing a narration line and then hunting for / inventing footage
  to back it.
- Required order: catalogue the clip (verified from frames) -> then write the
  line that binds to it.
- Violation example (IT): lines were written for "Beverly's father abuse" and
  "Henry kills his father" with no such footage catalogued (regression cases
  09, 10).

### Rule S2 - Chronological order rule (MANDATORY)
The BODY of the recap must follow source-film time order. Only the intro hook
(first 1-2 lines, hard max 3) may use out-of-order scenes.
- After the hook, draft lines must reference clips in MONOTONICALLY INCREASING
  source-time order (clip_start / pool clip start time goes up, not down).
- The ONLY permitted exceptions after the hook are lines explicitly marked
  `narrative_jump: true` (flashbacks, parallel action, deliberate callbacks).
  Use this flag sparingly and only when the jump is intentional storytelling.
- Violation example (IT): the recap jumped across the timeline repeatedly
  (regression cases 07, 08 - order inversion), a major cause of viewer
  confusion.

### Rule S3 - No-replay rule (MANDATORY)
No single clip - and no family - may be used more than its reuse cap. The caps
are defined in config.py and are NOT optional:
- MAX_REUSE = 2 (any normal pool/explicit clip: at most 2 uses total)
- MAX_REUSE_HERO = 2 (hero clips also capped at 2)
- MAX_FAMILY_USES = 2 (each visual family at most 2 uses total)
Replaying a clip beyond these caps is a QUALITY FAILURE, not a stylistic choice.
- Violation example (IT): the Pennywise-as-Georgie clip was replayed ~5 times
  (regression case 02). That is 2.5x the cap.

### Rule S4 - Audio-must-have-video rule (MANDATORY)
Every narration claim must have visible on-screen footage that depicts what is
being said. If the footage does not exist:
- rewrite the narration to describe what the footage DOES show, OR
- remove the line.
Never let the voiceover assert an event whose visual is not on screen.
- Violation example (IT): the hammer/iron-rod attack and Georgie's body were
  narrated while the matching visual was not shown (regression cases 05, 06 -
  audio without scene).

### Rule S5 - Subject-on-screen rule (MANDATORY)
When narration NAMES a character, that character must be VISIBLE in the bound
clip during their mention. Referring to a character by voice while a different
character (or no one) is on screen is a mismatch.
- The bound clip's `chars` must contain every character the line names as its
  subject, and those chars must be accurate to who is actually visible.
- Violation example (IT): the Stanley introduction showed a different character;
  Mike's nightmare showed Bill/Stanley (regression cases 03, 04 - wrong
  character).


### S6 - Action sequence coverage

For multi-stage action/climactic sequences, catalogue MINIMUM 3-4 distinct
shots per sequence, not 1-2 compressed shots. Each shot represents a single
discrete moment within the sequence: initiation, escalation, peak, aftermath.

Failure to catalogue sufficient action coverage causes render to produce
compressed action that feels "narrative summary" rather than "visual story" -
viewer hears narration about events without seeing them unfold. This is the
"audio-without-visible-action" failure mode (IT regression cases 5, 6;
Prisoners initial L42-L43 Bob suicide single-line, L57 gunfight single-line).

**Sequence types requiring extended coverage:**

- **Suicide moments**: minimum 4 shots (gun grab + raise + shot fired +
  aftermath / body)
- **Gunfights**: minimum 3-4 shots (gun draws + shots fired + impacts +
  aftermath)
- **Chase sequences**: minimum 3 shots (pursuit start + obstacle/turn +
  outcome)
- **Physical confrontations**: minimum 3 shots (setup + conflict peak +
  resolution)
- **Reveal moments** (villain unmask, twist): minimum 3 shots (setup +
  reveal beat + reaction)

**Emotional dwell beats:**

For close-up reaction shots that the recap should let viewer absorb (grief,
realization, dread), catalogue as DEDICATED single-moment shot, not bundled
with surrounding action. Examples:
- Detective seeing grieving mothers - dedicated emotional close-up
- Father realizing child is gone - dedicated reaction shot
- Villain's mask dropping - dedicated reveal close-up

**Catalogue review checkpoint:**

Before declaring catalogue complete, scan beat list for action sequences and
emotional peaks. Verify each has 3+ shots catalogued. If sequence has 1-2
shots, return to catalogue stage and add distinct moments before proceeding
to skeleton planning.


### S7 - Censor decision rules

At catalogue stage, tag explicit content with appropriate censor flag.
Default if absent: "none" (no blur applied at render).

#### S7.0 - Before reaching for a blur at all (DO THIS FIRST)

Blur is the LAST resort, not the first. A blurred patch is a signpost: it tells
the viewer precisely where to look and exactly what is being hidden. It also
damages the shot for everyone, including viewers who did not need protecting.

So the first question is never "how hard do I blur this" but:

> Does this shot carry any story information the narration has not already
> stated in words?

If it does not - and for explicit inserts it usually does not, because the
narration has just said what the thing is - then **re-bind the line to a
different catalogued shot in the same beat**. The beat has 3+ shots by S10's
depth target; use one of them. A clean shot of a reaction, a hand, a doorway,
the listener, is better television than a smeared rectangle, and it costs
nothing at render time.

Order of preference, strongest first:

1. Bind the line to a different shot in the same beat that carries the same
   story information without the explicit content. **Preferred.**
2. Bind to the same shot but a different sub-window that is clean (S10 gives
   you the sub-moment enumeration to find one).
3. Partial-region blur (S8) - the explicit element is small, stationary, and
   the rest of the frame is worth keeping.
4. Whole-frame blur (this rule). **Last resort.**

Only when 1-3 are genuinely unavailable does the intensity question below
apply. If you find yourself tagging several shots in one beat for blur, that
is a signal the beat is bound to the wrong footage, not that the beat needs
more blur.

#### S7.1 - Choosing the level: coverage and legibility, NOT content type

The level is decided by **how much of the frame the content occupies** and
**whether it is legible**, not by what the content is. Content type alone is
not sufficient and has produced wrong tags in practice (see the measurement
note below).

Ask two questions in order:

1. **Coverage** - what fraction of the frame does the explicit content occupy?
2. **Legibility** - after the blur, is it still readable, recognisable, or
   anatomically identifiable? If yes, the level is too low, whatever the
   content type says.

| Frame coverage | Minimum level |
|---|---|
| Small background detail, incidental, not the subject | `blur_light` |
| Roughly a third of the frame or more, or it IS the subject | `blur` minimum |
| Fills the frame, or is the point of the shot | `blur_heavy` |

Legibility overrides coverage in one direction only: it can raise the level,
never lower it. Anything **readable** (text, a magazine cover, a screen) or
**anatomically identifiable** must not be left at `blur_light`.

- `blur_light` (boxblur=15) - incidental background detail only.
  Drug paraphernalia on a table in the background; a distant, non-subject
  injury; a partially visible detail that is not what the shot is about.

- `blur` (boxblur=30) - the content is a significant part of the frame, or is
  the subject of the shot. Blood/gore with visible wounds; nudity that is
  identifiable; a readable explicit image; active drug use specifics.

- `blur_heavy` (boxblur=60) - the content dominates the frame or is the point
  of the shot. Graphic gore; explicit sexual acts; self-harm specifics.

**Measured limit of blur_light (2026-08-19, superbad2007 line 8).** A
pornographic magazine cover occupying roughly a third of the frame was tagged
`blur_light`, which the old wording permitted as "light nudity (partial,
non-sexual context)". Checked frame-by-frame in the rendered file, the cover
was still plainly legible after the blur. boxblur=15 does not obscure anything
readable or anatomically identifiable at any meaningful frame coverage. Treat
`blur_light` as usable ONLY for incidental background detail; if the thing
matters enough to tag, it almost certainly needs `blur` or higher.

When NOT to censor:
- Implied violence (off-screen)
- Action scenes without graphic injury detail
- Dark/silhouette violence (already obscured by lighting)
- Stylized violence (clearly cinematic, no gore detail)

Catalogue review checkpoint: scan beat list before declaring catalogue
complete, verify all explicit moments tagged with correct censor level.
Verify the S7.0 question was asked before any blur was tagged. Flag
uncertainty cases for human review.

**Verify the outcome, not the intent.** `recap.py render` reports how many
LINES will render censored, not how many shots carry a flag - those are
different numbers, and for a long stretch they silently differed (see
docs/lessons.md, exact-key vs A3). Read that line. If a shot is flagged and no
line resolves to it, nothing blurs.


### S8 - Partial-blur region selection (Phase C)

S7 blurs the WHOLE frame. S8 is an OPTIONAL refinement: blur only the
explicit rectangle and leave the rest of the shot watchable. Use it when the
explicit content occupies a small, stable part of the frame and blurring the
whole frame would needlessly hide the scene (a face, a reaction, the staging).

When to use a region (vs whole-frame S7):
- The explicit element is localized AND roughly stationary across the 4-6s clip
  (a wound on a body, a screen, a sign, genital nudity in an otherwise clothed
  two-shot).
- Keeping the rest of the frame visible adds real value (the actor's face, the
  geography of the scene).

When to STAY whole-frame (region = absent/None):
- The explicit content moves a lot or fills most of the frame.
- Fast cuts / handheld where a fixed rectangle would not track the content.
- When in doubt, whole-frame is safer (over-blur beats under-blur).

How to choose coordinates (catalogue stage):
1. Render zoom frames across the clip's window:
   `recap.py frames --project NAME --zoom HH:MM:SS`
2. Identify the rectangle that covers the explicit element across the WHOLE
   clip (account for motion: pad generously - it is better to blur a little
   extra margin than to let the content slip out of the box on a frame).
3. Coordinates are in OUTPUT-CANVAS pixels (the 1920x1080 render frame), with
   origin at the TOP-LEFT. They are NOT source-resolution pixels if the source
   differs - but for a 1080p source rendered to 1080p they match 1:1.
4. The render clamps the rectangle to the canvas, so slight over-estimates are
   safe; under-coverage is the real risk.

Schema shape (shots.json), added alongside the existing "censor" flag:

    {
      "id": "clip:02:04:47.0",
      "censor": "blur_heavy",
      "censor_region": { "x": 760, "y": 420, "width": 520, "height": 360 }
    }

- "censor_region" is OPTIONAL. Absent/null = whole-frame blur (S7 behaviour).
- "censor" still selects the blur INTENSITY (blur_light/blur/blur_heavy);
  censor_region only changes WHERE the blur is applied.
- width/height must be > 0; x/y >= 0. Out-of-canvas values are clamped.

Discipline: a region must COVER the explicit content across the entire clip.
If you cannot find one stable rectangle that does, drop the region and use
whole-frame S7 instead. Never ship a region that exposes the content on any
frame of the clip.


### S9 - Narration silence (cinematic holds)

Most shots carry narration. A SILENCE shot is the deliberate exception: the
visual holds with NO voiceover so a moment can breathe. The music swells from
the ducked narration level (16%) up to 35% during the silence, then fades back
when the next narration starts. Implemented via the optional Shot field
"narration_silence_seconds" (Gap 3).

When to use silence (plan at catalogue stage):
- Peak emotional beats - a held reaction, a face, a final look, grief.
- Iconic / signature shots - a famous composition the audience came to see.
- Peak ACTION payoff - the breach, the kill, the reveal landing - where words
  would step on the image.
- A deliberate breath after a heavy plot turn, before the recap moves on.

When NOT to use silence:
- Plot-carrying moments the viewer needs explained (silence loses them).
- Back to back (two silences in a row reads as dead air / a glitch).
- Early in the recap before the audience is invested (they will scrub).
- As filler to pad runtime - silence must be EARNED by the image.

How long:
- 3-8s for a held reaction or breath.
- 8-15s for an iconic shot or major action payoff.
- HARD CAP 30s (schema rejects more). Beyond ~15s most viewers scrub; reserve
  the long end for a truly singular image.
- Budget: about 2-4 silence shots per recap, not more.

How to tag (shots.json), alongside the normal shot fields:

    {
      "id": "clip:01:22:14.0",
      "clip_start": "01:22:14.0",
      "clip_end": "01:22:20.0",
      "chars": ["Arthur"],
      "depicts": ["emotion"],
      "action": "Arthur dances alone on the stairs, fully transformed",
      "narration_silence_seconds": 10.0
    }

- "narration_silence_seconds" is OPTIONAL; absent = a normal narrated shot.
- A silence shot still picks a real footage window (clip_start/clip_end) so the
  visual is sourced and styled like any other clip; the duration of the HOLD is
  the silence value, independent of the window length.
- A silence shot generates NO TTS: it carries no spoken narration.

**CRITICAL - how the RENDER actually finds a silence beat (2026-07-01 fix):**
The renderer builds the timeline by iterating `draft.json` LINES, not shots.json
shots. So a silence beat MUST be represented as a DRAFT LINE, or the render will
never see it - it will silently drop the held visual AND never swell the music.
Tagging `narration_silence_seconds` on a shots.json shot ALONE is NOT enough.

The correct representation is a silence DRAFT LINE (this is how Parasite's
working silence beats are authored):

    {
      "id": 75, "line_id": "L75", "unit_id": "U14", "covers": ["19"],
      "clip_start": "01:33:18.0", "clip_end": "01:33:36.0",
      "narration": "",
      "narration_silence_seconds": 18.0
    }

Key points for the draft line:
- `narration`: "" (empty - no spoken words)
- `narration_silence_seconds`: the HOLD length (mirrors the shot's value)
- NO `claim` block (a silence line is claim-exempt; the binding audit skips it)
- placed in its correct chronological POSITION in the lines list (the line order
  is what puts the held beat in the right spot on the timeline)
- NEVER inside the intro hook (S9: not before the audience is invested)
The matching shots.json shot may also carry `narration_silence_seconds` (for the
catalogue/audit), but the DRAFT LINE is what makes the render honour it.

Verify after render: the log must print a `line NNN: [silen] -> Ns (no
narration, music swell)` for EACH silence beat, and the final audio must show a
music swell at each silence timestamp. If you don't see the `[silen]` log line,
the silence beat was dropped (it was a shots-only silence with no draft line).

Discipline: silence is a spotlight. Point it at the one image in a sequence
that deserves the audience's full attention with no narrator talking over it.
If you cannot name WHY a shot earns silence, it does not.


### S10 - Stage 2 depth target + sub-moment enumeration (2026-06-22)

S6 already requires 3-4 shots for ACTION/climax sequences. S10 extends that
discipline to the WHOLE catalogue: catalogue to the film's natural shot
capacity FROM THE START, instead of cataloguing 1-2 shots per beat and growing
reactively when the draft comes up short.

Why this exists: across four films the initial Stage 2 catalogue systematically
under-shot the film's capacity. Parasite went 48 -> 61 -> 87 -> 110 shots, every
expansion frame-verified with no padding - proof the coverage was always
available; only the initial target was too low. Joker's 36 beats catalogued to
~62 shots (~1.7/beat) with multi-shot reserved only for the 4 S6 sequences. The
root cause was a speed-optimized default (1-2 shots/beat), not a depth-optimized
one.

#### Depth target per genre tier

Declare the film's tier in `beats_proposal.md` with a header line:

    depth_target: video_essay        # or: recap | fuller_recap

| Tier           | Runtime    | Total shots | Default shots/beat |
|----------------|------------|-------------|--------------------|
| `recap`        | 9-13 min   | 60-80       | 2-3                |
| `fuller_recap` | 14-17 min  | 90-110      | 3                  |
| `video_essay`  | 18+ min    | 110-130     | 3-4                |

If no `depth_target:` line is present, the audit infers the tier from the
`Target: N-M min` runtime line. Declaring it explicitly is preferred.

These are FLOORS TO CONSIDER, not quotas to pad to. Quality fullness ("đầy đủ
rõ ràng chi tiết") beats length for its own sake. If a beat genuinely warrants
one shot (a pure establishing wide, a single held reaction), keep one shot and
let the soft warning stand reviewed - do NOT invent a second shot to silence it.

#### Multi-shot per beat is the DEFAULT (was 1-2)

Each beat should aim for 2-4 shots covering its distinct sub-moments, not a
single compressed shot. The four coverage roles map to the `depicts` vocabulary:

- **establishing / setup** - the WHERE / the before-state of the beat
- **action / dialogue / reveal / discovery** - the main thing that happens
- **reaction / emotion** - a character's response to it (often the missing one)
- **aftermath / transition** - the result-state or the move to the next beat

A beat catalogued with only ONE shot is FLAGGED FOR REVIEW (DEPTH-UNDER). One
shot is allowed, but it must be a deliberate choice, not an oversight.

#### Sub-moment enumeration protocol (do this BEFORE picking shots)

For each beat, write a short enumeration first, then catalogue shots that cover
the enumerated moments. This makes under-coverage visible at authoring time
instead of at render time:

    B07 sub-moments:
      main_action:  Moon-gwang ousted via the fake-TB / peach-allergy scheme
      reactions:    Yeon-kyo's recoil; Chung-sook's feigned concern
      motifs:       the peach (allergy trigger); the spotless kitchen (class line)
      setting:      the Parks' immaculate kitchen vs the staged "illness"

Then select shots covering those moments (here: a setup shot of the scheme, an
action shot of the cough/peach, a reaction shot of Yeon-kyo). If a listed
sub-moment has no shot, either catalogue one or consciously drop it.

#### The Stage 2 depth audit (read-only)

Run before authoring to catch under-coverage automatically:

    python -m pipeline.catalogue --project NAME --coverage
    python -m pipeline.catalogue --project NAME --coverage --strict   # hard-fail floor

It reads `beats_proposal.md` + `shots.json` and emits:

| Warning        | Triggers when                                                | Fix |
|----------------|--------------------------------------------------------------|-----|
| `DEPTH-UNDER`  | a beat has fewer than 2 shots (per-beat floor)               | Add the missing sub-moment shot, or confirm 1 is right |
| `DEPTH-CLIMAX` | an [S6] action/climax beat has <3 shots                       | Add distinct action moments (S6: 3-4) |
| `DEPTH-REACTION` | a 2+ char beat has action coverage but no reaction/emotion | Catalogue the response shot |
| ~~`DEPTH-MOTIF`~~ | **RETIRED 2026-08-23** - see the dated section at the bottom of this file | - |
| `DEPTH-TOTAL`  | total shots fall below the tier's lower bound                 | Catalogue more, or re-declare the tier |

All warnings are soft (exit 2) by default. `--strict` escalates DEPTH-UNDER to
a hard fail (exit 1) for projects that want to enforce the floor before
authoring. The audit NEVER edits shots.json - it only reports.

#### Linking shots to beats

Tag each shot with its beat so the audit is exact:

    { "id": "clip:00:33:00.0", "beat": "B07", "depicts": ["action"], ... }

The `beat` field accepts `"B07"`, `"B7"`, or the integer `7` (all normalize to
B07). If absent, the audit falls back to inferring the beat from the shot's
`clip_start` timestamp - reliable only when the proposal's beat timestamps are
accurate, so prefer the explicit field.


## Maintenance

When you find a new mistake pattern not covered here, add it. This doc is a
living spec - the goal is to make tagging discipline explicit so it does not
drift between sessions and so future projects start with the lessons of past
ones.

Updates: append at the bottom under a dated heading. Do not silently rewrite
sections (no git history, so changes vanish).


## 2026-08-23 - Beat-map formats in `beats_proposal.md` (MANDATORY)

This section exists because the format was never written down. Three mutually
incompatible shapes got authored across ten films, `parse_beats()` accepted two
of them, and the third parsed to **zero beats for five consecutive passes** on
howtomakemillions2024 - which silently switched off every beat-iterating depth
gate on that project while `--coverage` kept printing "Depth gates clean".

An undocumented format is not a style question. It is a gate that stops running.

### The three accepted shapes

`pipeline/catalogue.py:parse_beats()` accepts exactly these. Pick ONE per file
and use it for every beat in that file.

**1. Whitespace** - id, then a timestamp, then prose (parasite2019):

    B01  ~0:01  Kim family's semi-basement: phone hunting for wifi, folding pizza

**2. Pipe** - id, then `|`-separated columns (joker2019, superbad2007):

    B01 | 00:00:08 | Gotham decays - news, garbage strike | (none) | establishing
    B03 | 00:04:42 | The convenience store ... | Seth, Evan | setup, dialogue [S7]

**3. Markdown table row** - a leading `|` before the id (howtomakemillions2024):

    | Beat | Window | Content | chars | depicts |
    |---|---|---|---|---|
    | B01 | 00:00:52 - 00:04:59 | Qingming grave visit ... | Amah Saejiu, M | setup |

Shapes 2 and 3 share column semantics: the leading `|` of a table row is
consumed together with the id, so the columns land at the same indices in both.
The header row is skipped because a beat id must be `B` + optional `_` + a
**digit** (`Beat` fails at the digit); the `|---|---|` separator never starts
with `B`. A table row's block is the row alone - it does not swallow the prose
that follows the table.

### What the parser needs from you

| You want this gate to run | The beat line must carry |
|---|---|
| `DEPTH-UNDER` (per-beat floor) | the id and a timestamp - nothing else |
| `DEPTH-CLIMAX` (S6 coverage) | a `[S6]` tag on the action/climax beats |
| `DEPTH-REACTION` (missing response shot) | a **chars column** (shape 2/3) or an inline `chars: X, Y` |
| `DEPTH-TOTAL` (total vs tier) | a `depth_target:` or `Target: N-M min` header |

A three-column table (`Beat | Window | Content`) parses fine and satisfies only
the first row of that table. Two of the four gates will report NOT MEASURED, and
that is now printed rather than hidden.

An **empty** chars cell means "not declared" and leaves the beat out of
`DEPTH-REACTION`'s unit count. Do not write `-` or `n/a` in it: those parse as a
character name. Leave the cell blank.

Declaring `chars` per beat is cheap and honest if you derive it from the union of
that beat's shots in `shots.json` rather than from memory - the shots were
frame-verified, so the derived list is too.

### Prose that mentions a beat is not a beat

`B22 is the explicit reveal ...` is NOT an entry - the id is not followed by a
timestamp or a pipe, so the parser skips it. Keep it that way: do not start a
prose paragraph with `B22 | ` or it will be harvested as a beat.

### Rule G1 - zero units is UNMEASURED, never clean (MANDATORY)

Any gate that walks a collection must distinguish "walked N units and found
nothing wrong" from "had nothing to walk". The second is not a pass, and a gate
that prints a pass on an empty collection is worse than no gate: it manufactures
confidence.

`--coverage` now prints a per-gate status block and refuses to say "clean" when
any gate had zero units, exiting 2 (review) instead of 0:

    Gate status:
      DEPTH-UNDER      measured over 51 numbered beats - 1 warning(s)
      DEPTH-CLIMAX     NOT MEASURED: no beat is tagged [S6] in beats_proposal.md
      DEPTH-TOTAL      measured over 1 tier band - pass

`CATALOGUE-DENSITY` and `SNAP-GRID` in `draft.py` already did this
("not measured: no usable beat map"). That idiom is now the house standard - if
you add a gate that iterates anything, it reports its unit count and says NOT
MEASURED at zero. Do not let a new gate certify an empty set.


## 2026-08-23 - DEPTH-MOTIF RETIRED (do not rebuild it)

`DEPTH-MOTIF` and the `MOTIF TRACKING:` harvest that fed it are **removed** from
`pipeline/catalogue.py`. The Stage 2 depth audit now has four gates, not five.
This is recorded at length because the obvious instinct on reading "motifs are
not checked" is to build it again.

The choice was required-or-retired: a gate that exists and does not run is the
state this codebase spent two weeks removing. It was retired on four measurements.

**1. It ran on 1 film in 10.** Nine of the ten proposals in `projects/` carried
no `MOTIF TRACKING:` line, so the gate had zero units and reported nothing.

**2. Where it did run, it silently measured 60% of what was declared.**
interstellar2014 declares five motifs across a **wrapped** line:

    MOTIF TRACKING (weave systematically, Register B): DUST, GRAVITY, the WATCH,
    the CORNFIELD, and LOVE-transcends-time.

The harvest regex was `^\s*MOTIF[ _]?TRACKING[^:]*:\s*(.+)$` under `MULTILINE`.
`.` does not cross a newline, so it read the first line only and extracted
`['DUST', 'GRAVITY', 'WATCH']`. CORNFIELD and LOVE were dropped without a word,
and the gate printed **pass**. That is the same defect class as the zero-unit
false pass, one level down: a pass over a silently truncated unit set.

**3. It cannot catch the failure it is imagined to catch.** The gate asks *"does
this motif keyword appear in ANY shot's `action` text?"* That is presence, not
placement. Measured on howtomakemillions2024: `pomegranate` appears in the action
text of **four** shots, so the gate passes - while the actual defect, flagged by
hand in pass 4 and still unresolved in pass 6, is that the motif's **plant is
missing** and only its payoff is catalogued. A motif audit that cannot tell a
plant from a payoff is not auditing motifs.

**4. It greps `action` text, so it is blind to anything planted in dialogue.**
This is the documented blind spot, and it is not hypothetical. On the same film,
the house-sale plant lives entirely in what the buyer at the gate *says*
(01:14:10, "I saw someone selling this house ... someone named M. Thanapat").
`action` correctly described only what was visible - a man holding up a phone -
so every text search over the catalogue returned nothing and a hand audit
declared the plant absent. It was not absent. It was inaudible to the method.

**What replaces it: nothing new, because the real check already exists.**
S4 and the binding audit test **each narration claim against the clip it is
actually bound to**, per line, at draft time. That is strictly stronger than a
keyword sweep: it is per-line, it knows which shot the claim is attached to, and
it fails on the specific line rather than on a global word count.

**If you want motif checking back, these are the requirements it must meet**,
and none of them are satisfied by grepping `action`:

- it must distinguish a PLANT from a PAYOFF (order matters, presence does not);
- it must read dialogue as well as visuals, i.e. the transcript, not just the
  catalogue's own prose;
- it must not depend on an author-written declaration that the same author then
  marks their own homework against.

Until something meets those three, motif discipline is a human review item and
is written up per film in `beats_proposal.md` under a plant audit - which is
where the pomegranate and the house-sale findings actually came from.

### The general lesson, which outlives this gate

**A text search over `action` text can only find things that are pictorial.**
`action` is required by this guide to describe what is *visible* and nothing
else, which is correct - but it means the catalogue is a deliberately incomplete
record of the film. Any audit that greps it will return confident false
negatives for everything the film carries in speech.

When auditing a film for a missing plant, grep the **transcript** as well as the
catalogue. Two of the three plant findings on howtomakemillions2024 were only
reachable that way.


## 2026-08-29 - Rule P1: a parser must name the shape it matched (MANDATORY)

This is the **third** time an unstated input format has cost a working day, so it
stops being three anecdotes and becomes a rule.

| When | Parser | The shape it did not expect | What it did |
|---|---|---|---|
| 2026-08-23 | `catalogue.py:parse_beats()` | markdown table rows, after id-prefixed lines | returned **0 beats** for five passes; every depth gate silently stopped running while `--coverage` printed "clean" |
| 2026-08-29 | `names.py:fetch_cast()` | Bad Genius (2017) writes its cast as **prose**, not a list | returned **0 names**; the file was hand-typed instead, and nobody knew whether the film had no cast or the parser had no eyes |
| 2026-08-29 | `names.py:fetch_cast()` | John Wick writes its cast as a **wikitable** | same silent zero; `johnwick2014_linear/names.json` is hand-authored with no actors for exactly this reason |

The common defect is not the missing format. It is that **an empty result and an
unrecognised format were the same output.** A parser that cannot tell those apart
converts a five-minute fix into a search of the wrong half of the codebase.

### The rule

Any parser that reads an external or authored format must:

**1. Report which shape it matched, on success.** Not a debug flag - normal
output. `recap.py names` now prints one of:

    parsed 30 entries from the cast list.
    parsed 5 entries from prose - this article has no cast list, so the
    mapping was inferred from sentences. Word order is a weaker signal
    than a list: check every pairing below.

**2. Fail loudly on zero, and name what it actually saw.** "No entries parsed" is
useless; it describes the parser, not the input. Say what the input was:

    Cast section found but nothing could be read from it - the section is
    a wikitable, which this parser does not read

That message points at the fix. The old one ("no 'Actor as Character' lines
parsed") pointed at nothing, and was read twice as "this film has no cast list"
when it meant "this parser has no wikitable branch".

**3. Rank its own modes by reliability, and say so.** The prose fallback infers
the actor-role pairing from word order, which a list states outright. Both are
"success"; they are not equally trustworthy, and the output says which one ran so
it gets read with the right amount of suspicion. A fallback that is silently as
authoritative as the primary path is how a guess becomes a fact.

This is the same principle as Rule G1 above, one layer down: G1 says a gate must
not certify an empty set, P1 says a parser must not report an empty set without
saying what it failed to read.

### The trap that comes with a prose fallback

A prose parser reads sentences that happen to sit near a cast mention, so its
false positives look plausible. Two guards earned their place on Bad Genius:

- **Image captions are dropped.** A caption is prose *about a person* sitting
  next to their name - the exact shape being matched, and the exact place it is
  wrong.
- **A role must start with a capital.** This single test rejects
  "served **as** acting coach" and "**as** her character is left-handed", both of
  which sit in the same paragraph as the four real cast sentences.

Also: scope the section to the next heading **of the same level or shallower**.
Bad Genius keeps its cast under `===Casting===`, and a boundary of `^==[^=]` ran
past it through Filming and cinematography, handing the prose scanner three
thousand extra characters of camera talk to misread. That boundary was wrong for
every level-3 section in the corpus and harmless for all sixteen level-2 ones,
which is why it survived so long.
