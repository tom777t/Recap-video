> **Read `docs/RULES.md` before writing anything.** It holds the editorial rules derived from previous films. Where it conflicts with the general guidance below, RULES.md wins. Candidate rules not yet confirmed live in `docs/GATE_CANDIDATES.md` — do not apply those unless told to.
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

### 1. Open on the image that raises a QUESTION
The first line is the single most important sentence. Do NOT open with "this
movie is about a girl who…". Throw the viewer straight into the most jarring,
concrete beat. Specific + weird beats vague + dramatic.
- Bad: "A young woman was afraid of the water."
- Good: "This girl had no idea that the moment she swam out, something would tear
  her apart — and leave only a pink swimsuit floating on the surface."

The test is not *where in the film the shot comes from* — it is **whether you
can name the question it raises.** If you cannot name it, you have written a
statement, not a hook. Declare it in `hook_question` on the line.

MEASURED CORRECTION (2026-10-20): this section used to say "never the start of
the film". That turned out to be wrong, and it was wrong in a way that would
have scored our own best draft badly. The human Bad Genius draft opens on a
clip from **00:01:22 of a 2h10m film** — 1.05% of the runtime, *earlier* than
the Tokyo Drift draft we rejected (2.23%). It works because the film's own
opening is a flash-forward that poses a question, not because it is late.
A timestamp rule was proposed for the validator and **dropped** for this
reason. What is gated is `hook_question`.

Then hard-pivot: "But to understand how this town got this insane, we have to
rewind."

### 2. Dangle an OPEN LOOP every ~20–30 seconds
The brain hates being left hanging. End beats on a hook that forces the next one:
- "But what was waiting under that boat was so much worse."
- "And that one decision would get someone killed."

A loop **does not need a question mark.** The human reference draft contains
**zero** question marks and still opens loops constantly, with flat promises:
- "Now meet the other one."
- "Then she sits down at the piano, and this is where the whole idea comes from."
- "That should be the end of it. Then Bank walks onto a footbridge…"

Mark these lines `"payload": "loop"`. The validator fails any draft with a
stretch longer than **12 lines** carrying no loop.

### 3. VARY THE RHYTHM — this is a measured gate, not a feeling
This section used to read *"Short sentences. The narration never stops."* That
instruction produced a draft with a words-per-line standard deviation of
**3.9** — a metronome in prose, monotonous before TTS ever read it. The human
draft scores **13.7**.

The validator now **rejects any draft below SD 9.0.** To clear it:

- Let a loaded line run **30, 40, even 70 words** when it carries a mechanism
  or a piece of reasoning. At least one sentence in fifty must be 30+ words.
- **Then hit it with a short one.** A ≤5-word sentence straight after a ≥20-word
  sentence is the device that most separates the two drafts (5.9% vs 1.3%).
  "The bars are the answers." "She is googling the essay." "He stops."
- Short sentences **on their own are not the goal.** The rejected draft had
  *more* of them than the human draft — all the same stunted shape, with
  nothing long for them to land against.
- Vary how lines **open.** Six consecutive lines beginning with a place or a
  time ("Night, steam venting…" / "At the guarded door…") is a pattern the
  ear hears even when the words are good.

"No dead air" is also retired: see LET ACTION BREATHE below. Deliberate
silence is a tool, and the human draft uses three of them.

### 4. EMOTIONAL, intimate voice — HAVE AN OPINION
Rise at the tense bits, drop to a hush for mystery, slip in personal asides:
"honestly, this part gave me chills", "and yeah — it's exactly as insane as it
sounds." Tag each line with a `delivery` preset (below) so the voice actually
rises and hushes.

This pillar was in the guide all along and the machine ignored it, because
nothing measured it: the Tokyo Drift draft contained **zero** lines where the
narrator had a view. It is now gated — **at least one judgment or aside every
30 lines, minimum 4 per draft.**

What counts:
- An opinion about a person: *"He is rich in the way that never has to be
  explained to anyone, least of all to him."*
- An opinion about a choice: *"Her father takes it sitting down without
  raising his voice, which is worse than if he had."*
- A remark about the filmmaking **as meaning**: *"the camera stays on her face
  for all of it rather than his, because the answer was never going to come
  from him."*
- A joke **played**, not reported. Understatement wins.

Address the viewer as **you**. Speak as **I**. The audiences who praise this
genre never praise completeness — they praise the voice.

### 5. EVERY LINE CARRIES A PAYLOAD
Each line declares `"payload"`: one of `stake`, `reasoning`, `judgment`,
`loop`, `rest`.

- `stake` — what it costs, what cannot be undone. Numbers are best.
- `reasoning` — what a character thinks and **why** they act.
- `judgment` — your opinion, an aside, a joke.
- `loop` — a promise that pulls the viewer forward.
- `rest` — pure description, a breath between loaded lines.

`rest` is capped at **25%** of lines, and **three `rest` lines in a row is a
hard failure**. Description is not banned — the human draft has plenty. It
works because it sits between loaded lines. The rejected draft's problem was
that *every* line was a rest line.

Label honestly: a fresh auditor samples 20 lines and checks the labels against
the text. **More than 3 wrong labels fails the round.**

---

## OTHER RULES

- **Trim filler, KEEP connective tissue.** Cut side gags, repeated radio chatter,
  and beats that reveal nothing new — but NEVER cut the setup, reaction, or
  consequence that explains why the next scene happens. A beat that improves
  understanding of what comes next is not filler (see SHIP_CHECKLIST H). When in
  doubt between a slightly longer recap and a rushed one, choose the longer.
- **Show, don't tell — but SHOW SOMETHING THAT COSTS.** Not "she was scared" →
  "her chest is pounding, the water goes dead still, and something brushes her
  leg." Strong verbs. Concrete images.
  **The failure mode to avoid:** the machine read this rule as "describe the
  frame" and produced 182 lines of clean, accurate, stakeless screen
  description — *"Tyres haze and the two cars break away together."* Apply the
  test: **delete the line. Does anybody lose anything?** If not, it is a `rest`
  line, and you are allowed only 25% of those.
- **Simple, visual language.** Easy words. One idea per sentence — but see
  PILLAR 3: "one idea per sentence" governs clarity, **not** sentence length,
  and it never justifies making every line the same size.
- **Accurate.** Don't invent plot points. Retell, don't transcribe.
- **Never narrate around dialogue you did not read.** Banned outright, and
  gated: *"whatever he says…"*, *"says something"*, *"answers loudly"* with no
  content, or introducing *"a visitor"* you never resolve. These are the
  narrator confessing it wrote from frames alone. Read the transcript and say
  what was said.
- **Name people and give them a role on first mention.** *"Kamata, the yakuza
  boss whose turf all of this runs on."* Never "the gangster" / "the man" /
  "one of them" once a name exists. Within 45 seconds of the hook the viewer
  must know who this is about, what they want, and what is in the way.
- **There is no length target.** Nothing in the validator compares your draft
  against a runtime; `target_minutes` is advisory and is only checked for not
  changing silently. Cover the beats and carry the payloads. Do not pad, and —
  more importantly — do not trim every line to a uniform size to hit a number,
  which is how the rejected draft reached SD 3.9.
- **Match the footage.** Pick clip_start/clip_end using the frame montages
  (`frames/overview/*.jpg` and zoom bursts) so the VISUAL matches the words.
  Never guess timestamps from transcript text alone.

## FACTS IN BRIDGE / FOLD / COMPRESSED LINES (hard-won, each a shipped error)

These three rules exist because each error below **shipped** in a compressed
Tokyo Drift draft and was caught only afterwards. Each is now backed by a gate
and a regression fixture, but the gate is a floor — read these.

1. **Take place/time facts from the BEATS you skip, never from memory.** A
   bridge or fold line spans beats you are not narrating in full. Every location,
   time, and who-is-where in that line must come from the beat map's own text for
   those beats (the `what happens` and character columns), not from what you
   remember of the film. *The miss:* a bridge line put the first DK race "on the
   mountain" — it is in a multi-storey car park; the mountain is the final race.
   The beat map said "spiral ramps… out onto the neon street" and the line
   ignored it. **The FACT audit now covers 100% of every line written or edited
   in any compress/punch-up pass** (bridge lines, fold lines, re-anchored lines)
   — sampling is only ever allowed on untouched lines. Newly compressed lines are
   the highest-risk lines in the draft; they get full coverage, not a sample.

2. **Name people; never hide an identity behind a description.** If a person is
   in `names.json` or has a known role, name them or give the role — do not write
   "the greying man", "the long-haired guy", "the old man". *The miss:* "the
   greying man he is shipped to" was Sean's **father, a US Navy officer** — the
   description hid the one fact that made the scene make sense. `[APPEARANCE-ID]`
   flags a looks-descriptor + person when the film has a names.json. A genuine
   one-scene extra with no role may stay unnamed; a named character may not.

3. **Any callback to an earlier event must cite the beat it refers to.** A line
   that says "the same move that got him…", "just like back in…", "what got him
   shipped out" is a claim about the plot's past, and those are easy to invent.
   Add `"callback_beat": "B07"` naming the beat where that event actually
   happens, so the FACT audit can check it. *The miss:* "the same move that got
   him shipped out of Arizona" — what got him shipped out was the **race crash**,
   not the thing he was doing (defending someone); the callback linked to a beat
   that does not say that. `[CALLBACK-CITE]` demands the citation. If a line is
   not really a callback, reword it so it does not read as one.

## STRUCTURE (in playback order)

1. **COLD OPEN** (lines tagged `delivery: "hook"` or `"tense"`) — the shocking beats.
2. **CHANNEL INTRO** (one line, `delivery: "intro"`):
   "This is Serabudabu. Today I'm breaking down [film] — and trust me, it goes
   completely off the rails." Tease the central question.
3. **BODY** — setup fast, then rising beats with an open loop every ~20–30s,
   midpoint turn, climax (slow slightly on the biggest moment, `delivery: "tense"`).
4. **OUTRO** (one line, `delivery: "outro"`) — **thesis first, THEN the CTA.**
   The template that used to sit here was CTA-only ("If you made it this far —
   subscribe, smash that like…") and the validator now **fails** it. An outro
   that only reports the last event, or only asks for a subscribe, is the exact
   thing audiences name when they call a recap shallow: it strips the ending of
   what it meant.

   Say what the ending **means**, then ask:
   "The only one who pays in full is the one who decides to stop. If you made
   it this far, subscribe and tell me what to recap next."

   (For multi-part / chaptered films you may add a teaser line for the next
   part; for standalone films, skip the teaser.)

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

### `hold` vs `narration_silence_seconds` — two different things

| field | the line | what happens |
|---|---|---|
| `hold: 8` | **has** narration | the clip keeps playing after the words stop |
| `narration_silence_seconds: 6` | **has no** narration at all | a wordless held shot; music carries it |

Use `narration_silence_seconds` **after a reveal, a death, or a climax** —
never as filler. 4–10 seconds, and **3 to 6 across the whole film**. The
validator warns outside that range, errors under 2s, and a blank `narration`
*without* the field is a hard failure, not a pause.

This is not a new invention: the human Bad Genius draft already uses three of
them (6s, 10s and 20s). A research pass once read that draft's `script.txt`,
which did not print the field, and concluded those three lines were dead air.
They were deliberate. `script.txt` now prints `[HOLD 6.0s — no narration]` so
nobody makes that mistake again.

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
