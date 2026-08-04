# Recap Narration Style Guide — LINEAR mode (kể tuyến tính)

> **SIBLING FILE.** This is the "linear" counterpart to `recap_style.md` (the
> "review" style). The two share the SAME engine, voice, footage-matching,
> validators, and draft.json format — they differ ONLY in how the SCRIPT is
> STRUCTURED. A project chooses its style with `style: linear` in
> `beats_proposal.md`. **Absent = `review`**, so every existing project is
> untouched and keeps behaving exactly as before.
>
> **THE FULL QUALITY BAR IS STILL IN `SHIP_CHECKLIST.md` (criteria A-V).** Linear
> mode does not lower any bar. The same validator + linter run (reuse/family/
> visual-repeat caps, length, names, clarity/read-aloud/action-setup); the same
> Stage 2 catalogue-to-depth and Stage 3 DRAFT-TARGET gates apply.
>
> New capabilities available (identical to review mode): `"family"` tags on
> B-roll shots AND `"visual"` action-tags on explicit-timestamp lines (BOTH cap 2
> per visual family); `"montage": ["A4","A7","A8"]` = a silent action montage;
> `"setup_ok": true` to exempt an intentional context-free cold-open action;
> per-film `names.json`.

This is the brain of the tool in LINEAR mode. The script is THE product.

The model is the Vietnamese "review phim" recap channel — the kind that walks the
viewer **through the film beat by beat, in order**, so they feel they have
experienced the whole movie — but delivered in natural, idiomatic ENGLISH.
Channel identity: **Serabudabu**.

**The core difference from review mode:** review mode *re-sequences* the film into
a curiosity-driven argument (question -> answer -> new question). Linear mode
*follows the film's own timeline*, walking the viewer through each successive
development. Fullness comes from **covering MORE of the film's real developments**,
not from padding any single one. A longer video is the RESULT of dense coverage —
it is never a goal you pad toward.

---

## VALIDATION IS ONLY AS GOOD AS YOUR TAGS — RENDER QA IS MANDATORY

The audits (binding, continuity, capacity) compare your line's *claim* against the
*text tags* in shots.json — they do NOT watch the video. A mis-tagged shot passes
the audit while still mismatching the footage. So a clean validator is necessary,
NOT sufficient. **Stage 8 RENDER QA — watching the real final.mp4 — is required,
not optional.** This is true in both modes; it matters even more here because
linear mode binds many more shots, so there is more footage to actually verify.

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
- **Don't compress a causal setup chain into a single line.** When a film
  establishes its premise through a chain of cause -> effect (A leads to B leads
  to C — a dying world, an escalating threat, a ticking countdown), walk the
  viewer through the chain; don't state only its conclusion. A first-time viewer
  needs the MECHANISM, not just the result. BUT: only narrate links the film
  actually shows. If the film deliberately leaves something unexplained (an
  unexplained cause, an ambiguous origin), do NOT invent a reason to fill the gap
  — present exactly what the film presents, no more. The failure mode is
  two-sided: under-covering a chain the film gave you, OR inventing a link the
  film withheld.
- **Complex plots earn more lines.** Length is flexible. If a film is hard to
  follow, ADD the connecting beats needed to understand it. Comprehension beats a
  length cap, every time.
- **Comprehension re-read.** After drafting, read it as someone who's never seen
  the film. Can they explain the plot back? If not, add a clarifying line.
- **Foreign / dialogue-heavy films:** transcribe with `--translate` (and a `small`
  or `medium` model) so you actually KNOW the plot before scripting. You cannot
  make a clear recap from a garbled transcript.

## PRE-CATALOGUE: READ A PLOT REFERENCE FIRST (before Stage 2)

Before cataloguing, read the film's **Wikipedia page — the Plot and Cast sections**
— and, if character names are still missing, **IMDb for a fuller cast list**. A
transcript alone is noisy: Whisper mangles proper names and you can miss who's who.
Reading a plot reference first lets you catalogue with context instead of blind.

Use the reference ONLY to:
- **Spell character names correctly** — override Whisper's mangling with the real
  spellings.
- **Understand who's who and the film's structure** — the cast, their relationships,
  and the shape of the story.
- **Avoid comprehension gaps** — know what a scene is actually about before you tag it.

Use ONLY the Wikipedia-style plot summary and cast list. **Do NOT read or absorb
critic reviews, ratings, or analysis** (Rotten Tomatoes, Metacritic, Ebert,
Letterboxd, etc.). Those pollute the channel's own voice and raise copyright issues
— the recap is Serabudabu's read of the film, not a digest of critics.

**Wikipedia is a MAP, not ground truth.** If the plot reference and the actual
frames disagree, the **FRAMES win** — the reference may describe a different cut, or
simply be wrong. Catalogue what is on screen, not what the summary says should be.

### SPOILER DISCIPLINE (absolute — the core risk of reading the plot in advance)

Reading the full plot up front means you now KNOW the ending. That knowledge must
never leak into narration ahead of the film. This is the price of the pre-catalogue
read, and it is non-negotiable.

- **Split the summary into two zones the moment you read it.** (a) The **SETUP
  zone** — characters, premise, structure, first-half developments — which you may
  use freely for names and context. (b) The **REVEAL zone** — every twist, betrayal,
  death, and the ending — which you treat as KNOWLEDGE-TO-PROTECT, not content to
  deliver.
- **Knowing a twist is NOT permission to reveal it.** The narration unfolds at the
  FILM'S pace: a reveal stays hidden until the exact beat the film itself reveals it
  (the same reveal-at-its-own-moment discipline that governs following the film's
  order — a genuine turning point earns its cliffhanger phrasing only WHEN the film
  turns).
- **Name the reveals explicitly before drafting — an explicit per-reveal hold.**
  After reading the plot summary, write down in `beats_proposal.md` each REVEAL-zone
  item and the exact film beat / timestamp where the film FIRST reveals it. Then,
  while drafting, hold each one until its named beat — **regardless of narration
  order.** Following the film's order does NOT guarantee this on its own: a scene
  narrated in correct chronological order can STILL leak a twist if you describe it
  with later knowledge (narrating Interstellar's early "ghost" as "which we later
  learn is Cooper," or calling John "Baba Yaga" before the film does — correct order,
  still spoiled). Narrate every early scene with ONLY what a first-time viewer knows
  AT THAT POINT, never with hindsight from the reveal zone.
- **Reading ahead makes you MORE responsible for not leaking, not less.** If
  anything from the REVEAL zone starts appearing in your narration before its
  film-beat, that is a spoiler failure — stop and hold it.
- **When in doubt whether something is a reveal, treat it as one and hold it.**

### THE REVEAL-MAP (machine-checkable spoiler holds — the REVEAL-TIMING gate)

The per-reveal holds above are enforced by a gate. Alongside the free-text reveal
notes, write a machine-readable `reveal-map` block in `beats_proposal.md`; the
REVEAL-TIMING gate reads THAT block and flags any protected term that appears in a
narration line whose footage sits BEFORE the reveal's landing time.

Format — a fenced block, one reveal per line, three fields separated by `|`:

    ```reveal-map
    R1-ock  | land: B08 | hold: Doc Ock, Doctor Octopus, Otto Octavius
    R1-gob  | land: B08 | hold: Green Goblin, the Goblin
    R4      | land: B19 | hold: Maguire, Garfield, Peter-Two, Peter-Three, other Spider-Men
    R6      | land: B25 | hold: erases himself, world forgets, forget him
    R7      | land: mid-credits | hold: Venom, Eddie Brock, symbiote
    ```

- **`land:`** — WHERE the film first reveals it: a **beat id** (`B08`, resolved to the
  film's beat time) OR a raw **`HH:MM:SS`** timestamp OR **`mid-credits`/`none`**
  (= protect ALWAYS: any mention anywhere flags). Prefer a beat id — it stays stable
  when you re-anchor timestamps at frame-verification (the beat moves, the id doesn't).
- **`hold:`** — the protected term(s), comma-separated. This is an **alias list** and
  it is only as complete as you make it: enumerate every name/phrase that would give
  the reveal away (`Doc Ock, Doctor Octopus, Otto Octavius`). Terms are matched
  case-insensitively on WORD BOUNDARIES (so "May" won't fire inside "maybe").
- **Split monster-vs-man into separate rows** when a civilian name is legitimately
  present before the reveal. Protect the MONSTER (`Green Goblin, the Goblin`) with the
  landing beat; leave the MAN (`Norman Osborn`, an early businessman) unprotected — or
  in its own earlier row. Do NOT protect a term that appears legitimately early, and
  do NOT add a "mention it's fine here" escape hatch — put the legitimate-early term in
  its own row instead. Keep the map dumb and the intent explicit.
- The block is OPTIONAL. With no `reveal-map` block the gate is a no-op (nothing to
  check). Add one for any film whose value depends on protected reveals.

**Severity + timing:** the gate is SOFT (a warning, exit 2 — a possible spoiler, not a
proven one; it must not block a render on a false positive). It runs on EVERY linear
draft regardless of stage (a spoiler can enter at outline OR during enrichment).

**Its limit — read this, it is the whole point.** REVEAL-TIMING is a LITERAL-term text
scan. It catches a listed term spoken early ("Maguire" at minute 22). It does NOT
catch:
- **paraphrase** not in the alias list ("the man with metal arms" for Doc Ock),
- **implied foreshadowing** with no protected term ("and a familiar face steps through
  the portal").
The gate is a FLOOR, not a ceiling: it catches the obvious literal leaks that slip past
a tired eye, and nothing more. **The draft-review watch remains the spoiler backstop.**
A clean REVEAL-TIMING pass means "no listed term leaked early," never "spoiler-proof" —
the gate prints exactly this reminder every run so no one mistakes the two.

## SCRIPT GENERATION PHILOSOPHY (read this before writing a single line)

Write the recap as a **chronological cause -> consequence walk**: this happened,
which led to this, which forced this. Follow the film's own order of events. The
viewer should always feel *"và rồi..."* (and then...) — carried forward by the
film's own momentum, not by an artificial cliffhanger every 20 seconds.

**DEFAULT: follow the film's timeline.** Move through developments in the order the
film presents them. You may **merge two adjacent developments** or **pull a detail
slightly earlier** ONLY when the film's own order actively confuses a recap viewer
(a non-linear film, a deliberately withheld reveal). When you do, it must be a
*conscious* choice for clarity — never to rush or compress. If you find yourself
re-sequencing out of habit, you have drifted into review mode; stop and go back to
the film's order.

**Coverage over selection.** Review mode picks the juiciest beats and drops the
rest. Linear mode's job is the opposite: walk the viewer through the *connected
chain* of what happens, so no development a first-time viewer needs feels skipped.
This is why linear recaps naturally run longer and suit the `fuller_recap` /
`video_essay` tiers — more developments covered = more shots = more narration.
That length is EARNED by coverage, not by padding a beat.

**NATURAL PROGRESSION test.** After each beat, a first-time viewer should feel "of
course, that's what happened next," never "wait, where did this come from?" In
linear mode this is usually automatic (you are following the film's order), but
still forward-check every transition: if two consecutive beats leave a gap, you
have skipped a development — go back and cover it, don't paper over it.

**Setup must occur BEFORE confusion, not after it.** Before every action sequence
establish WHO is involved, WHY it is happening, WHAT triggered it, and WHAT is at
stake. Action must never be the first explanation of itself. (See SHIP_CHECKLIST
A, S, U, H, V.)

## THE HOOK (identical framework to review mode)

Use the SAME hook framework as review mode — see `recap_style.md` PILLAR 0 /
"THE HOOK". In short: judge how much the viewer already knows
(`hook_context: high_fame | mid | low_fame` in beats_proposal.md); open a
curiosity GAP the viewer must close; for famous films use the film's fame as FUEL
for a shock, never as an intro ("this won Oscars" closes the gap and fails);
self-grade 1-10 on gap strength, under 9 = rewrite.

**The ONLY linear-specific difference is the pivot.** After the cold-open hook
(~30-45s) and the channel intro, **hard-pivot to the BEGINNING of the story and
walk forward in order**: "Let me take you back to where it all starts…" From this
point the recap is chronological. The cold-open hook is the ONE deliberate jump
out of sequence — everything after it follows the film's timeline.

## PACING & OPEN LOOPS (looser than review mode)

- **FAST, relentless delivery — no dead air.** Short sentences. The narration
  never stops. Tag each line with a `delivery` preset so the voice rises and
  hushes. (Same as review mode.)
- **Do NOT force an open loop every 20-30s.** The pull in linear mode is the
  film's own forward motion — "and then what happens" — not a manufactured
  cliffhanger. Save cliffhanger phrasing ("but what came next was so much worse")
  for the film's GENUINE turning points: a real twist, a reveal, a betrayal.
  Over-using it on ordinary in-order developments makes the recap feel jerky and
  fake, the opposite of the smooth "và rồi" flow you want.
- **EMOTIONAL, intimate voice — like gossiping with a close friend.** Rise at the
  tense bits, drop to a hush for mystery, slip in personal asides ("honestly, this
  part gave me chills"). (Same as review mode.)

## CONTINUITY IS YOUR SKIP-DETECTOR (linear-specific reading)

The engine's continuity_check flags large forward jumps (>10 min) and backward
jumps in source time. In REVIEW mode these are often noise (you re-sequence on
purpose, so you set `narrative_jump: true` to silence them). In LINEAR mode the
meaning FLIPS: because you walk in order, a continuity warning usually means **you
skipped a chunk of the film** — exactly the "thin / missing developments" problem
to avoid. So when continuity_check fires:
1. FIRST assume you skipped a development the viewer needs, and check whether to
   add a covering beat.
2. ONLY set `narrative_jump: true` when the jump is genuinely intentional (a real
   flashback / parallel timeline the film itself presents out of order).

Do not reflexively silence continuity warnings in linear mode — they are doing
useful work for you.

## OTHER RULES (shared with review mode)

- **Trim filler, KEEP connective tissue.** Cut side gags, repeated radio chatter,
  and beats that reveal nothing new — but NEVER cut the setup, reaction, or
  consequence that explains why the next scene happens. When in doubt between a
  slightly longer recap and a rushed one, choose the longer.
- **Show, don't tell.** Not "she was scared" -> "her chest is pounding, the water
  goes dead still, and something brushes her leg." Strong verbs. Concrete images.
- **Simple, visual language.** Easy words. One idea per sentence.
- **Accurate.** Don't invent plot points. Retell, don't transcribe.
- **Match the footage.** Pick clip_start/clip_end using the frame montages
  (`frames/overview/*.jpg` and zoom bursts) so the VISUAL matches the words.
  Never guess timestamps from transcript text alone.

## STRUCTURE (in playback order)

1. **COLD OPEN** (`delivery: "hook"` / `"tense"`) — the shock, per the hook
   framework above.
2. **CHANNEL INTRO** (one line, `delivery: "intro"`):
   "This is Serabudabu. Today I'm walking you through [film], start to finish."
3. **FAMOUS FACES** (brief, if applicable) — call out the 1-3 genuinely famous
   actors on a clip that shows their face, then move on. (Same as review mode.)
4. **CHRONOLOGICAL BODY** — pivot to the story's start, then walk each development
   IN ORDER: setup -> each successive complication / discovery / decision / reveal
   -> midpoint -> climax (slow slightly on the biggest moment, `delivery: "tense"`,
   `hold`) -> resolution. This is the heart of linear mode: keep the film's own
   sequence, cover the connected chain, don't skip mechanics that make the next
   beat make sense.
5. **OUTRO** (one line, `delivery: "outro"`):
   "If you made it this far — subscribe, smash that like, and tell me what I should
   recap next." (Add a next-part teaser only for multi-part films.)

## DEPTH & LENGTH (how "fuller" is earned, not padded)

Linear mode aims HIGHER on the depth tiers by default, because covering the film's
developments in order naturally needs more shots. In `beats_proposal.md`:

    style: linear
    depth_target: fuller_recap      # or video_essay for long / complex films

- Catalogue to the tier's shot count at Stage 2 (the coverage audit warns if thin).
- Author the draft TO that depth: the Stage 3 DRAFT-TARGET gate estimates the REAL
  runtime (calibrated voice rate) and reports capacity fill (target 70-85%). If it
  reports DRAFT-UNDERFILL / under-target, you have skipped developments or written
  lines too short — ADD covering beats, do not pad existing ones.
- **A longer video is the by-product of covering more of the film — never a target
  in itself.** If fill climbs past ~90% (DRAFT-OVERFILL), you are over-stuffing
  lines toward slow-motion; that is padding, and it is wrong. Cover more DISTINCT
  developments instead of cramming words onto the shots you already have.

- **Under-fill: WHERE the capacity is unused matters, not just how much.** A low
  capacity-fill number is NOT automatically a genre artifact. Before you accept it,
  break the unused capacity down BY SHOT TYPE. Unused capacity on long ACTION shots
  is honest — fights resist words, and padding them with play-by-play makes the recap
  worse; leave those gaps alone. But unused capacity on DIALOGUE, EMOTIONAL, or
  CLOSING shots is a coverage gap: the film is showing something the narration isn't
  carrying, and that scene will play rushed. Fill the dialogue/emotional gaps with
  real narration; leave the action gaps. "Fill is low because it's an action film" is
  valid ONLY for the action shots — never apply it blanket. (A film can ship at, say,
  61% fill on the "action artifact" reading and still have a 3-minute emotional
  closing scene collapsed into one short window — the action logic holds, the ending
  gap does not.)

  **"Don't pad the fights" is NOT "let the fights be unfollowable."** Unused capacity
  on action shots is honest ONLY when the fight is still COMPREHENSIBLE — i.e. its
  STAGES are narrated (breach → clearing the room → hand-to-hand → the finish), even
  if tersely. Blow-by-blow narration of every punch is padding and is wrong; narrating
  a fight's stages so a viewer can follow the escalation is COVERAGE and is required.
  If a long set-piece is collapsed into so few windows that a viewer can't follow how
  the fight unfolds, that IS a coverage gap — exactly like an under-covered emotional
  scene — and you fix it by adding STAGE-LEVEL lines/windows, not by blow-by-blow
  padding. **The test: can a first-time viewer follow what happened in the fight? If
  no, it is under-covered, regardless of the fill number.** (The John Wick house fight
  is the model: 5 windows narrating 5 stages — breach, clearing the main floor,
  room-to-room, hand-to-hand, the finish. Tight, not a play-by-play, but the viewer
  follows the whole escalation.)

  **This test is now backed by a gate: SET-PIECE COVERAGE (linear, SCRIPT stage).**
  You do not have to eyeball every fight by hand. Mark each followability-critical
  set-piece in a machine-readable ```set-pieces``` block in beats_proposal.md, and the
  gate checks that no unnarrated stretch inside it grows long enough to lose the
  viewer. The block is MACHINE-PROPOSED, HUMAN-CONFIRMED:

  1. PROPOSE the content list from Wikipedia + the S6 action beats — WHICH fights
     exist (the highway fight, the Statue battle). Wikipedia knows the content; it
     does NOT know this file's timecodes (extended cuts drift from the theatrical plot).
  2. DENSE frame-verify each [start, end] IN THIS FILE — 1-2s frames start-to-finish
     across every boundary, NEVER sampled. A set-piece boundary off by 2 minutes makes
     the whole coverage measurement wrong (this is exactly where the MJ-catch drifted).
  3. CONFIRM keep/drop (is it followability-critical? an S6 beat like a spell isn't a
     fight — drop it) and eyeball the range. Only `keep` rows are measured.

  Block format (parallel to the reveal-map):
      SP3 | Statue of Liberty combat | 01:53:44 - 02:03:20 | verified: dense | keep
  - start-end: a beat id or raw HH:MM:SS range.
  - verified: MUST be `dense` for a kept row to be trusted; `sampled`/`unverified`
    WARNS (a boundary you sampled can drift — the gate is honest about its own inputs).
  - keep/drop: drop rows are recorded (decision stays visible), never measured.

  **Mark ONLY real combat; leave non-combat UNMARKED.** A "battle" is often interleaved
  with dialogue (the Statue sequence is scaffold-planning talk, then combat, then a
  spell-VFX climax + an emotional fall/catch). Mark the combat ranges only; the quiet
  stretches are deliberately unmarked and NEVER measured — so the gate can never fire on
  a dialogue scene. If you mark one big range spanning the lulls, it will false-fire.

  **Threshold (v1, PROVISIONAL — not settled):** a gap fails only if it exceeds
  max(240s, 3 x the recap's OWN median line gap). It is TIER-RELATIVE on purpose: a
  flat number copied from one film false-fires on another. A 90s max-gap borrowed from
  the dense John Wick house-fight wrongly flagged the viewer-approved, sparser
  Spider-Man draft (its 88s median cadence is honest for a fuller_recap). The gate
  adapts to each recap's cadence — the same truth as "tier follows the film's
  talkiness" (see the tier section): an action recap narrates sparser, so its
  followability bar must loosen WITH it. CAVEAT: the median term is self-referential (a
  uniformly-thin recap raises its own median and loosens its own bar); calibrated on one
  film, to be revisited. Treat a SET-PIECE-UNDER flag as "probably add a stage-line
  here," not a hard failure — it is soft-only.

**Enrich act-by-act when a draft comes in under-target.** If the DRAFT-TARGET gate
reports the draft under the tier floor or under 70% fill after a first full-film
pass, do NOT re-enrich the whole film at once — a single whole-film re-pass tends
to stay thin (the model drifts and thins out over a 2+ hour film) or over-stuff a
few lines. Instead, enrich in segments with a validation checkpoint per segment:

- **Split the film into its natural acts** — typically 2-4 for a feature. Follow
  the beat structure, not a fixed number.
- **Enrich ONE act at a time.** Deepen the EXISTING lines in that act (reaction,
  motive, cause -> effect, sensory detail) so each uses more of its shot capacity.
  Do NOT add new shots just to raise the line count — that lowers fill.
- **Run the validator after EACH act, not just at the end.** Confirm that act
  actually added fill and introduced no freeze (BindingViolation) before moving to
  the next. Per-act validation is the part that matters: it catches thinning and
  freezes locally, where they are cheap to fix.
- **Use the 1.4x time-cap as the true per-line ceiling** (not the raw word
  ceiling), and stay ~85-90% of it, leaving headroom so no line freezes.

The point is measured, incremental enrichment with a checkpoint per act — that is
what reliably lifts a thin draft into the tier band, where one big pass does not.

## TWO-STAGE DRAFT: OUTLINE (3a) → SCRIPT (3b)

The first full-film draft pass is an OUTLINE, and being thin is CORRECT — do not
treat it as a failure. Its job is COVERAGE + BINDING, not density: hit every beat,
bind each line to a frame-verified shot, and see the whole arc end to end. A thin
outline that "fails" DRAFT-TARGET is meaningless — that pass was never meant to hit
target. So the two stages run DIFFERENT gates:

- **Stage 3a (OUTLINE):** the gate checks coverage / binding / continuity only.
  DRAFT-TARGET (real-rate, fill, tier-floor) does NOT run. The engine defaults a
  fresh draft to this stage.
- **Stage 3b (SCRIPT):** act-by-act enrichment (the DEPTH & LENGTH section above).
  DRAFT-TARGET applies here — this is where fill and tier floor matter.

**Promotion 3a → 3b is a measurable condition, not a vibe.** The outline is READY
when:
- every beat is covered — specifically **no run of ≥2 consecutive uncovered beats**
  (a lone uncovered beat between two adjacent lines is a coarse HH:MM beat-map
  granularity artifact and is tolerated; two or more in a row is a genuinely
  unnarrated stretch of film and blocks promotion),
- 0 binding mismatch AND 0 unverified (every line on tagged, frame-verified footage),
- continuity clean,
- 0 freeze-class violations (BINDING-VIOLATION).

When ready, promote with `recap.py draft --promote`. The engine tracks the stage in
`state.json` (engine-owned, NEVER hand-edited); promotion is **one-way** and, for
now, **explicit** — the engine computes readiness and prints its judgment (with the
reason and metrics), and you pull the trigger. (Once the readiness condition is
proven across more films, promotion can become automatic; until then, nhắc-tay →
observe → automate.)

This split ends the false alarm where every film's first pass flagged
DRAFT-UNDER-TARGET and we "fixed" a pass that was an outline by design. It keeps BOTH
benefits: the big-picture outline (coverage + whole-arc) AND the density that
act-by-act enrichment adds on top. It also means the coverage measure runs on every
draft — which is how it earns its keep (it has already surfaced a real
under-covered-ending gap in a film we thought was finished; see docs/lessons.md).

## STORY UNIT PLANNING (mandatory — plan BEFORE you write, Stage 6B)

Same as review mode: list ALL story units the audience must experience to follow
the narrative naturally, score each Low/Medium/High complexity, allocate coverage
per unit, and write each unit to its planned coverage. In linear mode the unit
list should track the FILM'S ORDER (units in playback sequence), and you should
expect MORE units than a review-mode draft of the same film, because you are
covering the connected chain rather than a selection. Write the unit list into
skeleton.txt / skeleton.json. Never pad a simple unit; never skip a complex one.

## OUTPUT FORMAT (write straight to draft.json — identical to review mode)

```json
{
  "title": "Punchy recap title",
  "target_minutes": 16,
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

The `hold` field (let a big visual beat breathe with no voiceover), silence shots
(`narration_silence_seconds`), `delivery` presets, sound design and captions all
work identically to review mode — see `recap_style.md` for those sections. Nothing
about the engine changes; only the shape of the script does.

## MATCH THE FOOTAGE — the most important rule (shared)

Match the footage to the film; don't force an action ratio. Talky films: mostly
faces, the VOICE carries the story, action only at the genuine action beats. Never
reuse a shot to fill a quota — repetition is what looks awkward. For a dialogue
film the cleanest approach is to scene-match almost every line to its own moment's
footage with explicit clip_start/clip_end; the B-roll pool is mainly for
action-heavy films where reuse is unavoidable. (Full detail in `recap_style.md`.)

## CLIP ANCHORING — anchor to the narrated moment, not the shot's start (shared)

Anchor `clip_start` to the narrated MOMENT, not the first frame of the catalogued
shot. The default habit of setting `clip_start` to a shot's opening frame makes the
narration run ahead of the visual whenever that shot opens on lead-in footage — a
wide or establishing frame, an approach, a wind-up, a getting-ready beat, or a
reaction — BEFORE the specific subject or action the line names. This is NOT an
action-only problem: it hits establishing, arrival, transition, and emotional shots
too, any time the opening frames aren't the narrated moment. It's just most obvious
on action, where the payoff — the kill, the fall, the impact — is a sharp, spoiler-y
beat.

- **Anchor to the moment.** Set `clip_start` to the frame where the narrated
  subject/action actually appears — or a beat before it — so the footage leads and
  the narration follows, never the reverse. When a shot genuinely IS the moment (a
  dialogue line held on a face, a static emotional beat), `clip_start` = shot start
  is already correct; leave it.
- **Shift the whole window, never shrink it.** When you move `clip_start` later,
  move `clip_end` forward by the SAME amount. Shrinking the window risks a render
  freeze. If a shot is too short to shift without running past its real cut, accept
  a tighter anchor rather than force it.
- **Verify large shifts.** A correction bigger than ~3-4s usually means the window
  is crossing into a different beat or past a scene cut — frame-check that it lands
  on the narrated moment; don't just push blindly. A too-large shift trades a
  lead-in problem for a scene-mismatch problem.
- **Fast-cut sequences are high drift-risk — anchor to the exact SUB-MOMENT.** A
  single shot in a fast intercut sequence (an action set-piece, a battle, a rapid
  scene) contains MANY sub-moments packed a second or two apart. Anchoring
  `clip_start` to the shot's start — or even a few seconds off — lands on the WRONG
  sub-moment while the narration names the next one, producing a mismatch even though
  the scene is "right." Frame-verify the EXACT sub-moment the line names and anchor to
  it, not to the sequence's start. Most footage-vs-narration mismatches cluster here,
  and it is also why such scenes read as "rushed" — the window is racing past the beat
  the words describe.

## DRIFT TAGGING — when characters look alike, tag the SPECIFIC one (shared)

When a film has characters who are easily confused on screen — variants of the same
character (multiverse doubles, the three Spider-Men), twins, or several people in
similar costume/uniform (guards, soldiers, masked figures) — **NEVER tag a shot with
a generic label** ("Spider-Man," "the villains," "a guard"). Always tag the specific
individual. Binding a narration line to the wrong look-alike is a **DRIFT error**
(the narration names X, the footage shows Y) — the most damaging kind of mismatch,
and one the gates CANNOT catch: they check tag-compatibility, not visual identity.

**Drift is not just about look-alikes — it extends to any GROUP that intercuts.** A
team of villains, a squad, a crew, an ensemble — any set of characters who appear
together and cut between each other is a drift risk EVEN WHEN THEY LOOK DIFFERENT. A
line naming one member can easily land on another member's footage, because the
sequence intercuts them and a `clip_start` a few seconds off jumps to the wrong one.
So frame-verify the specific individual named in EVERY line involving a group, the
same as you would for look-alikes. (On a recent film the three look-alike heroes were
tagged perfectly — because they were flagged up front as the hazard — but two
different-looking villains in the same battle got swapped, and a line about one
villain landed on the heroes' footage. The flagged risk was handled; the unflagged
group was not. Flag the group too.)

- **Cue hierarchy — most to least reliable.** Use these to make a POSITIVE id:
  1. **Unmasked face** — the surest tell.
  2. **Costume / suit design when clearly lit** — distinct patterns, colours, gear.
  3. **A signature dialogue anchor** — a line only that character would say (a name
     they alone use, a loss only they suffered). Dialogue-locks an id when the face
     is turned or masked.
- **When all cues fail, admit it — don't guess.** The failure mode is **fast masked
  action intercut**, where costume-shade is the only cue and motion-blur or darkness
  defeat it. In those shots do NOT force a false-precise single id. Tag ALL
  candidates present and add a `_drift_note` warning not to bind a single-character
  narration line to that shot without re-checking frames. Bind character-specific
  lines to the clearly-identifiable shots on EITHER SIDE instead. Admitting
  uncertainty and flagging beats guessing wrong every time.
- **Intercut scenes are high drift-risk — frame-verify each shot individually.** A
  scene that cuts rapidly between look-alikes — OR between two locations / storylines
  — is where drift creeps in, because a `clip_start` off by only a few seconds can
  land on the wrong character or the wrong side of the cut. Never trust a single
  timestamp to represent a run of an intercut scene; check the actual frame for every
  shot. (This is exactly how a Viggo→Aurelio drift happened on an intercut John Wick
  scene, and why the three-Spider-Man zone needs per-shot verification.)
