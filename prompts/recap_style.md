# Recap Narration Style Guide (v3 — built for views)

> **THE FULL QUALITY BAR IS IN `SHIP_CHECKLIST.md` (criteria A-V).** A recap is
> not done until every item passes. The validator + linter enforce the objective
> ones (reuse/family/visual-repeat caps, length, names, clarity/read-aloud/
> freshness/action-setup flags); the rest are judged in the self-review loop, the
> first-time viewer audit (7A), and render QA (8) before any ship.
>
> New capabilities: `"family"` tags on B-roll shots AND `"visual"` action-tags on
> explicit-timestamp lines (BOTH cap 2 per visual family - same character+action+
> purpose = same family, judged by viewer memory not file identity);
> `"montage": ["A4","A7","A8"]` = a silent action montage; `"setup_ok": true` to
> exempt an intentional context-free cold-open action; per-film `names.json`.



This is the brain of the tool. The script is THE product. Follow this exactly.

The model is the Vietnamese "review phim" recap channel — but delivered in
natural, idiomatic ENGLISH. Channel identity: **Serabudabu**.

---

## PILLAR ZERO: THE VIEWER MUST UNDERSTAND THE MOVIE

The whole job of a retell is that someone who never saw the film can follow the
plot. Hooks keep them watching; CLARITY makes it worth it. Keep the fast, punchy,
show-don't-tell style EXACTLY — clarity comes from better word CHOICE, not from
slowing down or padding.

- **Establish the spine fast.** In the first ~30-45 seconds after the cold-open
  hook, make these crystal clear: WHO the hero is, WHAT they want, and WHAT stands
  in their way. Plain words.
- **Name + role every key character on first appearance** — one or two words.
  "Spencer, the disgraced game warden." "The mercenary leader hunting them for
  revenge." Never leave the audience guessing who someone is.
- **Every beat answers who / why / what's at stake** — not just what's on screen.
  Bad (vague): "And then it gets personal." Good (clear, still punchy): "Then the
  villain recognizes him — this is the man who killed his brother."
- **Prefer names and motives over vague pronouns.** Swap "the leader / the enemy /
  one of them / it gets personal" for a name or a reason. Same syllables, more story.
- **Keep cause -> effect intact when trimming.** Don't cut the connective tissue:
  "Because X, he has to Y, which leads to Z." A highlight reel isn't a story.
- **Complex plots earn more lines.** Length is flexible. If a film is hard to
  follow, ADD the connecting beats needed to understand it. Comprehension beats a
  length cap, every time.
- **Comprehension re-read.** After drafting, read it as someone who's never seen
  the film. Can they explain the plot back? If not, add a clarifying line.
- **Foreign / dialogue-heavy films:** transcribe with `--translate` (and a `small`
  or `medium` model) so you actually KNOW the plot before scripting. You cannot
  make a clear recap from a garbled transcript.

## STAGE 2: CATALOGUE TO DEPTH (catalogue BEFORE you author — full from the start)

The catalogue is the visual vocabulary the whole script binds to. If it is thin,
the script is forced thin. Across four films the FIRST catalogue pass
systematically under-shot the film's real capacity (Parasite grew 48 -> 61 -> 87
-> 110 shots, all frame-verified, no padding). The fix: catalogue to the film's
NATURAL depth from the start, not 1-2 shots per beat with reactive expansion.

**1. Declare the depth tier in `beats_proposal.md`:**

    depth_target: video_essay      # recap | fuller_recap | video_essay

| Tier           | Runtime    | Total shots | Shots/beat |
|----------------|------------|-------------|------------|
| `recap`        | 9-13 min   | 60-80       | 2-3        |
| `fuller_recap` | 14-17 min  | 90-110      | 3          |
| `video_essay`  | 18+ min    | 110-130     | 3-4        |

**2. Multi-shot per beat is the DEFAULT.** Each beat aims for 2-4 shots covering
its distinct sub-moments, not one compressed shot. Before picking shots, write a
sub-moment enumeration per beat:

    B07 sub-moments:
      main_action:  Moon-gwang ousted (fake-TB / peach-allergy scheme)
      reactions:    Yeon-kyo recoil; Chung-sook feigned concern
      motifs:       the peach; the spotless kitchen (class line)
      setting:      the Parks' immaculate kitchen

Then catalogue shots that cover those moments. Tag each shot with its beat
(`"beat": "B07"`). One shot for a beat is allowed but must be a deliberate
choice (a pure establishing wide, a single held reaction) — never an oversight.

**3. Audit the catalogue BEFORE authoring** (read-only, never edits shots.json):

    python -m pipeline.catalogue --project NAME --coverage
    python -m pipeline.catalogue --project NAME --coverage --strict   # hard-fail floor

Resolve (or consciously justify) every `DEPTH-UNDER` / `DEPTH-CLIMAX` /
`DEPTH-REACTION` / `DEPTH-MOTIF` / `DEPTH-TOTAL` warning, then complete
SCRIPTING_CHECKLIST C12-C15. Only author once the catalogue meets its tier.

**Principle: "đầy đủ rõ ràng chi tiết" — quality fullness, not length for its
own sake.** Depth means showing MORE of the film's real sub-moments (reactions,
motifs, detail), NOT slower pacing or padded narration. See TAGGING_GUIDE S10 +
STYLE_GUIDE section 7.

## STAGE 6A: STORY SKELETON AUDIT (do this BEFORE writing prose)

Before spending 1500-2500 words, write a **beats-only skeleton** and audit the
STRUCTURE first. Example shape:

    Hook -> Inciting incident -> Investigation -> Escalation -> Reveal ->
    Climax -> Resolution

Audit the skeleton:
1. Does every major beat naturally CAUSE the next beat?
2. Is any beat present ONLY because it happened in the movie (cut or re-anchor it)?
3. Is there a MISSING transition between two major beats?
4. Would a first-time viewer understand why we move from beat A to beat B?
5. Does each beat ANSWER a previous question and CREATE a new one?

Fix structural problems here. Save the skeleton to `projects/NAME/skeleton.txt`.
Only start full script writing once the skeleton flows.

## SCRIPT GENERATION PHILOSOPHY (read this before writing a single line)

Write the recap as BOTH:
1. A **cause -> consequence chain** (what happened / why / what changed).
2. A **question -> answer -> new-question chain.**

Every major section should ANSWER the previous question while OPENING the next one.
The audience should be pulled forward by CURIOSITY, not pushed forward by
information. Example chain:

    Bomb explodes.            -> Who did it?
    Quan wants names.         -> Can Hennessy give them?
    Hennessy refuses.         -> How far will Quan go?
    Quan bombs Hennessy.      -> Who is Quan really?
    Quan's file is opened.    -> Can anyone stop him?

A setup, reaction, consequence, realization, or transition is **not filler** if it
helps the audience understand why the NEXT event occurs. Prioritize narrative flow
over maximum compression. The viewer should feel **"Of course this happened next,"**
never **"Wait, where did this come from?"**

**NATURAL PROGRESSION test (criterion W).** After each beat, predict: "if the
recap stopped HERE, what would a first-time viewer naturally expect next?" Then
check the actual next beat against that prediction. If the gap is too large, the
viewer thinks "wait, how did we get here?" - so insert a bridge (a clue,
consequence, discovery, decision, or new objective) that makes the next beat feel
inevitable. Do this forward-check at the skeleton stage AND on the finished draft.

**Setup must occur BEFORE confusion, not after it.** Before every action sequence
establish WHO is involved, WHY it is happening, WHAT triggered it, and WHAT is at
stake. Action must never be the first explanation of itself. If a first-time viewer
would need the NEXT sentence to understand the CURRENT scene, the transition has
failed — move the explanation earlier. (See SHIP_CHECKLIST A, S, U, H, V.)

## THE FOUR PILLARS (non-negotiable — this is what makes people not scroll)

### 0. THE HOOK must score 9-10 (see SHIP_CHECKLIST "R. THE HOOK")
The first line is make-or-break. Lead WITH the shock (not the setup), open a
curiosity gap the viewer needs closed, tease the movie's biggest reversal without
spoiling it, keep it specific and front-loaded. Self-grade 1-10; under 9 = rewrite
before anything else.

### 1. Open on the most SHOCKING, SPECIFIC moment — never the start of the film
The first line is the single most important sentence. Do NOT open with "this
movie is about a girl who…". Throw the viewer straight into the most jarring,
concrete beat. Specific + weird beats vague + dramatic.
- Bad: "A young woman was afraid of the water."
- Good: "This girl had no idea that the moment she swam out, something would tear
  her apart — and leave only a pink swimsuit floating on the surface."
Use the most violent / mysterious / high-stakes 2–4 beats as a COLD OPEN, with
NO setup. Then hard-pivot: "But to understand how this town got this insane, we
have to rewind."

### 2. Dangle an OPEN LOOP every ~20–30 seconds
The brain hates being left hanging. End beats on a hook that forces the next one:
- "But what was waiting under that boat was so much worse."
- "And that one decision would get someone killed."
- "He didn't know it yet — but he'd have to choose between his friend and the
  whole town."
Open a loop, delay the payoff, open another. Never let the viewer feel "done".

### 3. FAST, relentless pacing — no dead air
Short sentences. The narration never stops. Each line pushes into the next.
Trim ruthlessly (see below). Delivery is brisk (handled by per-line `delivery`).

### 4. EMOTIONAL, intimate voice — like gossiping with a close friend
Rise at the tense bits, drop to a hush for mystery, slip in personal asides:
"honestly, this part gave me chills", "and yeah — it's exactly as insane as it
sounds." Tag each line with a `delivery` preset (below) so the voice actually
rises and hushes.

---

## OTHER RULES

- **Trim filler, KEEP connective tissue.** Cut side gags, repeated radio chatter,
  and beats that reveal nothing new — but NEVER cut the setup, reaction, or
  consequence that explains why the next scene happens. A beat that improves
  understanding of what comes next is not filler (see SHIP_CHECKLIST H). When in
  doubt between a slightly longer recap and a rushed one, choose the longer.
- **Show, don't tell.** Not "she was scared" → "her chest is pounding, the water
  goes dead still, and something brushes her leg." Strong verbs. Concrete images.
- **Simple, visual language.** Easy words. One idea per sentence.
- **Accurate.** Don't invent plot points. Retell, don't transcribe.
- **Match the footage.** Pick clip_start/clip_end using the frame montages
  (`frames/overview/*.jpg` and zoom bursts) so the VISUAL matches the words.
  Never guess timestamps from transcript text alone.

## STRUCTURE (in playback order)

1. **COLD OPEN** (lines tagged `delivery: "hook"` or `"tense"`) — the shocking beats.
2. **CHANNEL INTRO** (one line, `delivery: "intro"`):
   "This is Serabudabu. Today I'm breaking down [film] — and trust me, it goes
   completely off the rails." Tease the central question.
3. **BODY** — setup fast, then rising beats with an open loop every ~20–30s,
   midpoint turn, climax (slow slightly on the biggest moment, `delivery: "tense"`).
4. **OUTRO** (one line, `delivery: "outro"`):
   "If you made it this far — subscribe, smash that like, and tell me in the
   comments what I should recap next." (For multi-part / chaptered films, you may
   add a teaser line for the next part; for standalone films, skip the teaser.)

## STORY UNIT PLANNING (mandatory — plan BEFORE you write, Stage 6B)

Do NOT write a compressed draft and expand it later. Build the runtime from the
beginning by planning per STORY UNIT, then write the draft TO that plan.

A story unit is NOT a scene. It is a meaningful section of the narrative where:
a goal is introduced · a problem appears · a clue is discovered · a relationship
changes · a major decision is made · a conflict escalates · a reveal occurs · or
a consequence reshapes the story. Examples:
- action-adventure: Setup · Treasure Hunt · First Complication · Rival Interference
  · Capture · Escape · Final Confrontation · Resolution
- mystery: Crime · Investigation Begins · First Lead · False Lead · New Discovery
  · Suspect Revealed · Twist · Confrontation · Resolution

**Step 1 — list ALL story units** the audience must experience to understand the
narrative naturally. (Ask that, NOT "how short can this be?")

**Step 2 — score each unit Low / Medium / High** complexity. High units make the
viewer follow reasoning, clues, motivations, or consequences.

**Step 3 — allocate COVERAGE per unit.** High units get more narration; Low units
stay lean. Use **~170 finished words/min** ONLY to convert coverage into an
approximate runtime (rough sanity check by film length: <90min source ~ 10-14 min
recap; ~2h ~ 14-20 min; ~3h ~ 20-30 min — let the units decide, never pad).

**OVER-COMPRESSION warning signs (must avoid):** multiple clues squeezed into one
sentence · travel/investigation/discovery chains skipped · a reveal with no
showing of how it was earned · a character suddenly knowing something · a location
change with no explanation · multiple units collapsed into one paragraph.

Write the unit list + complexity + coverage into skeleton.txt; write each unit to
its planned coverage. The `draft` validator prints a **"Predicted final length"**
from real TTS audio — check it BEFORE rendering and adjust against the plan (add
connective beats if a complex film comes in short; never pad a simple one).

## SOUND DESIGN & CAPTIONS (built-in)

- **SFX** are on by default (config.SFX_ENABLE): a whoosh on transitions, a boom
  on `hold` reveals, a sting on the intro line, a riser on `mystery` beats. They
  sit under the music and below the voice. Tune in config.SFX_*.
- **Captions** are OFF by default (config.DEFAULT_CAPTIONS). Enable per-run with
  `--captions` (animated pop-in, styled in config.CAPTION_*). They also aid
  comprehension, so consider them for hard-to-follow films.

(Runtime-by-source-duration is now a sanity check inside STORY UNIT PLANNING
above — let the story units decide the length, never pad.)

---

## OUTPUT FORMAT (write straight to draft.json)

```json
{
  "title": "Punchy recap title",
  "target_minutes": 14,
  "voice": "tts",
  "lines": [
    {
      "id": 1,
      "narration": "Something tore her apart and left only a pink swimsuit on the water.",
      "clip_start": "00:04:45.0",
      "clip_end": "00:04:55.0",
      "delivery": "hook",
      "note": "cold open - the kill"
    }
  ]
}
```

## MATCH THE FOOTAGE — the most important rule

Don't force an action ratio. Match the footage to the film:
- **Action film** -> lots of action on screen.
- **Dialogue film** (like most cheap shark movies) -> mostly faces; the VOICE
  carries the story. Use action ONLY at the genuine action beats (the kill, the
  dive, the attack, the explosion).
- **Never reuse a shot to fill a quota.** Repetition is what looks awkward. If a
  line has no fitting fresh action shot, use the REAL dialogue footage of that
  scene (different scenes are visually varied on their own).
- The simplest, cleanest approach for a talky film: scene-match almost every line
  to its own moment's footage with explicit clip_start/clip_end. The B-roll pool
  below is mainly for ACTION-heavy films where reuse is unavoidable.

## INTRODUCE THE FAMOUS FACES (briefly)

Right after the cold-open hook and the channel intro, add a short beat that calls
out the genuinely famous actors in the film, on a clip that shows their face:
"And yeah — that's Jackie Chan leading the team. Beside him? John Cena."
Keep it to the few BIG names only (1-3), one or two lines, then move on. It
hooks fans and signals the movie is worth watching. Don't list the whole cast.

## LET ACTION BREATHE — the `hold` field

A clip is normally only as long as its narration line, which cuts away from
action too fast. For a big visual beat, set `"hold": <seconds>` on the line: the
clip plays for at least that long, and the extra time has **NO voiceover** — just
the footage and the music swelling underneath. This lets the audience actually
feel the breach, the attack, the explosion.
- Pick the long-holds yourself: the spectacular payoffs (explosion ~8-9s, a
  breach ~5-6s, a big attack ~6-8s). Don't hold dull footage.
- Make sure a held clip's clip_start/clip_end window is long enough to show real
  motion for the whole hold (don't freeze on a still frame).

## ACTION SCENE CHECK — every fight/chase/explosion is EARNED (criteria S + U)

Before every major fight, chase, explosion, attack, escape, mission, or action
sequence, verify the audience already knows:
- **who** is involved
- **why** it is happening
- **what** triggered it
- **what** is at stake

If any of these are unclear, ADD setup BEFORE the action — do not explain it after.
Every action sequence must read **Setup -> Action -> Consequence**, never
**Action -> Explanation.** The setup can land a few lines earlier (a "meanwhile",
a decision, a threat) as long as it arrives BEFORE the action reaches full
intensity. Never insert an action scene just because it's exciting; if the viewer
thinks "cool scene, but why am I watching it?", the setup is missing.

The validator's **[ACTION-SETUP]** flag scans the lines before each action beat
for a named participant or a causal/transition cue. If it flags a beat, write the
1-2 setup lines it's missing. (You can mark an intentional context-free cold-open
action with `"setup_ok": true`.)

## VISUAL-MEMORY REPETITION (criterion C) — the knife-cauterization problem

A VISUAL FAMILY = **same character(s) + same action + same narrative purpose.**
It is judged by VIEWER MEMORY, not by file identity. These are ONE family even
though every clip is technically different:
- wound cauterization (close-up, wide, different angle — still the same memory)
- bomb assembly / a laptop being built
- computer hacking / typing
- trap building / digging
- forest stalking / creeping through trees

The test: **"Would a viewer feel like they just saw this already?"** If yes, it's
a repeat — even if the crop, angle, zoom, or source clip differs. Cap each family
at **2**. Same-scene shots count as DISTINCT only across clearly different stages
(setup / midpoint reversal / outcome). Source proximity is only a hint; the ACTION
defines the family.

**Tag it so the validator can enforce it:** put a `"visual": "knife_cauterize"`
field on every explicit-timestamp action line (the same way pool shots carry
`"family"`). Two lines with the same `visual` count together; a third is BLOCKED
by `[VISUAL-REPEAT]`. When you must show an action more than twice, re-point the
extra lines to the ACTUAL narrated scene's own distinct footage instead.

## RENDER QA (Stage 8) — watch the real video, not the validator

After rendering, WATCH the output at 1.5-2x and log: confusion moments, weak
transitions, repeated visuals, emotional discontinuities. Patch if needed, then
ship. The validator output is necessary but not sufficient — the viewing
experience is the final authority. Record findings to `projects/NAME/qa.md`.

## ADAPTIVE balance: let the FILM decide action vs dialogue

The biggest mistake is forcing a fixed action ratio. A talky film with little
action, padded with the same 8 shark shots on repeat, looks awkward and cheap.
The right approach is adaptive:

1. **Analyze first.** Run `recap.py analyze --project NAME`. Scan the montages
   and estimate the film's ACTION density (shark/water/attack/dive/explosion)
   vs DIALOGUE/character. A cheap shark movie is often only ~20-25% action.
2. **Set the recap's action ratio to MATCH the film.** Dialogue-heavy film ->
   the recap stays mostly on faces; the VOICE carries the story. Action film ->
   lean into action. Don't pad exposition with repeated B-roll.
3. **Cap reuse so it never feels repetitive.** Build the pool with
   `recap.py broll --project NAME --scaffold`, then in draft.json give a line
   `"pool": "A4"` to pull an action shot. Caps (enforced by the validator):
   - normal shot: at most MAX_REUSE (default 2) times in the whole video
   - hero shot (flag `"hero": true` in broll.json): at most MAX_REUSE_HERO
     (default 3) — reserve for the spectacular shots (the explosion, the jaws).
   The renderer jitters the in-point + alternates zoom so even allowed reuses
   don't look identical.
4. Keep explicit clip_start/clip_end for character beats AND for any exposition
   line that has no fitting action shot — staying on dialogue footage is correct
   for a talky film, not a failure.

The validator prints an "Action mix" line and a reuse histogram, and REFUSES to
render if any shot exceeds its cap. Aim the ratio at the film's real density.

Field rules:
- `pool`: a label from broll.json (e.g. "A4"). Use INSTEAD of clip_start/clip_end
  for any line that doesn't need a specific character moment.
- `delivery`: one of `hook | tense | mystery | sad | intro | outro | normal`.
  Drives the voice speed/pitch/volume (see config.TTS_DELIVERY). Default `normal`.
  You may also set explicit `rate` / `pitch` / `volume` to override.
- `clip_start` / `clip_end`: timestamps IN THE SOURCE, `HH:MM:SS.mmm`. Choose
  from the frame montages so the visual matches the line. The renderer NEVER
  slows footage — if narration is longer than the clip, it holds the last frame,
  so prefer clips that contain the action you describe.
- Keep clips ~2–8s. Order `lines` in playback order; `id` ascending & unique.
- `note` is for your reference; ignored at render.
- Output ONLY the JSON object when generating a draft.
