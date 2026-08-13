# IT 2017 - Regression Cases

Fourteen viewer-observed mismatches recorded from watching the rendered video.
These are the ground-truth failures that the rule-based audit did NOT all catch.
Use this list as a regression set: any future audit/render change should be
checked against these cases.

Columns:
- Case: case number
- Narration claim: what the voiceover says is on screen
- Footage observed: what the rendered video actually shows
- Suspected class: the failure category (see legend at bottom)


## Cases

### Case 01
- Narration claim: Georgie meets the clown / Pennywise bites and drags Georgie.
- Footage observed: the same drain clip plays a different sub-segment per line; the "meet" line lands on the bite frames and the "bite" line lands on the meet frames (swap).
- Suspected class: RENDER_SUBWINDOW_JITTER

### Case 02
- Narration claim: the clown wears Georgie's face to torment Bill (a single beat).
- Footage observed: the Pennywise-as-Georgie footage is replayed roughly 5 times across the recap.
- Suspected class: VISUAL_REPEAT

### Case 03
- Narration claim: introducing Stanley (the rabbi's anxious son).
- Footage observed: the shot on screen shows a different character, not Stanley.
- Suspected class: WRONG_CHARACTER

### Case 04
- Narration claim: Mike's nightmare (his parents burning).
- Footage observed: the shot shows Bill and Stanley, not Mike's vision.
- Suspected class: WRONG_CHARACTER

### Case 05
- Narration claim: the hammer / iron-rod attack (a physical action beat).
- Footage observed: the action audio plays but the matching scene is not on screen (audio present, visual absent).
- Suspected class: AUDIO_WITHOUT_SCENE

### Case 06
- Narration claim: Bill finds Georgie's body in the cistern.
- Footage observed: the body-discovery audio/beat plays but the corresponding visual is not shown.
- Suspected class: AUDIO_WITHOUT_SCENE

### Case 07
- Narration claim: the kids decide to hunt the clown / track it to its lair.
- Footage observed: footage order is inverted relative to the narration - the "find where it lives" beat appears before the setup that should precede it.
- Suspected class: ORDER_INVERSION

### Case 08
- Narration claim: Pennywise attacks Beverly / hits her with the deadlights.
- Footage observed: the attack beats play out of order relative to the narration sequence.
- Suspected class: ORDER_INVERSION

### Case 09
- Narration claim: Beverly's father abuses/controls her at home.
- Footage observed: no footage of the father-abuse exists in the cut; the claim has no matching visual.
- Suspected class: MISSING_FOOTAGE

### Case 10
- Narration claim: Henry Bowers murders his own father.
- Footage observed: no footage of the father-killing exists; the line is backed by unrelated Bowers footage (the rock fight), not the murder.
- Suspected class: MISSING_FOOTAGE

### Case 11
- Narration claim: the Losers fall apart and walk away from each other.
- Footage observed: the footage shown does not read as the walk-away/scatter beat; the scene is disconnected from the narration's meaning.
- Suspected class: SCENE_DISCONNECT

### Case 12
- Narration claim: the Losers compare notes and realize the same thing hunts them all (group discovery).
- Footage observed: footage shows a single character / unrelated street moment rather than the group realization (pre-fix state).
- Suspected class: SCENE_DISCONNECT

### Case 13
- Narration claim: Mike adds the last piece - it is an ancient thing, not a clown (Mike's discovery).
- Footage observed: footage shows the Derry-town establishing shot with no Mike on screen (pre-fix state).
- Suspected class: WRONG_CHARACTER / SCENE_DISCONNECT

### Case 14
- Narration claim: introducing Henry Bowers as a looming threat (setup/intro).
- Footage observed: footage is a mid-attack action shot (Mike shoved into meat), not an introduction beat; the intro reads as confusing.
- Suspected class: SCENE_DISCONNECT


## Suspected-class legend

- RENDER_SUBWINDOW_JITTER: render.py picks a seeded sub-window of a multi-moment
  clip; different lines hit different sub-windows, so the visible moment does
  not match the line. Fixed structurally only by one-moment clips.
- VISUAL_REPEAT: the same footage is reused enough times that the viewer feels
  they are seeing a repeat. Caught partially by the [VISUAL-REPEAT] /
  [VISUAL-MEMORY] linters, but only as a proximity heuristic.
- WRONG_CHARACTER: the on-screen character is not the one the narration names.
  Caught by the binding audit ONLY when chars tags are accurate; missed when
  tags are wrong or when the wrong-but-same-type clip is bound.
- AUDIO_WITHOUT_SCENE: narration/SFX implies an event whose visual is not on
  screen. Not caught by the rule-based audit (it checks tag presence, not
  whether the specific event is visible).
- ORDER_INVERSION: footage plays in a different order than the narrated story
  beats. NOT caught by the audit at all (no chronological/order check exists).
- MISSING_FOOTAGE: the claimed event has no footage in the source catalogue.
  Caught only if the line ends up UNVERIFIED; missed if a same-type but
  content-wrong clip is bound (type matches, content does not).
- SCENE_DISCONNECT: the bound clip's type matches the claim type, so the audit
  passes, but the actual content does not depict the narrated moment.
  This is the audit's core blind spot: type-level match, content-level miss.


## Audit coverage against this set

Of these 14 cases, the rule-based phase-1 audit (binding + tag-quality) can
detect only the subset where a tag is provably wrong (wrong chars, or an
untagged/UNVERIFIED line). It cannot detect RENDER_SUBWINDOW_JITTER results,
ORDER_INVERSION, AUDIO_WITHOUT_SCENE, VISUAL_REPEAT semantics, or
SCENE_DISCONNECT where the clip type matches but the content does not. This is
the empirical basis for the "~30-40% caught" lesson recorded in docs/lessons.md.
