# Draft one ACT from the machine catalogue

You write narration for **one act** of a recap video. You are given the beat
map for that act and the machine catalogue of moments that fall inside it.

## Inputs

- The act payload (beats + available moments), printed by `act_payload.py`.
- `projects/<p>/beats_proposal.md` - read the header and the house rules, not
  just your act.
- `projects/<p>/names.json` - spell characters exactly as this file does.
- `projects/<p>/_cuts.json` - **only** for the window-extension rule below.

You may **not** read `draft.json` or any other project's draft. Write the act
from the beats and the moments, not from an existing answer.

## Read this first: what went wrong last time

The previous machine draft of *Tokyo Drift* was causally correct and
completely boring. Every gate was green. Measured against a human-written
draft of the same length:

| | human draft | machine draft |
|---|---|---|
| words-per-line standard deviation | 13.7 | **3.9** |
| sentences of 30+ words | 11 | **0** |
| lines where the narrator has an opinion | 6 | **0** |
| intro / outro | 1 / 1 | **0 / 0** |

Every line was the same length, the same shape, and reported what was on
screen without once saying what it cost anybody. The old version of this
prompt caused that directly: it ended with *"do not editorialise"*. That
instruction is gone. You are now **required** to have a point of view.

## What a line is

```json
{
  "id": 17,
  "narration": "Lynn slides the eraser back over her shoulder without looking.",
  "clip_start": "00:11:41.000",
  "clip_end": "00:11:52.500",
  "note": "B10",
  "delivery": "tense",
  "payload": "stake",
  "narrative_jump": false,
  "claim": { "type": "speech", "subject": "Lynn" }
}
```

- `note` is the beat id this line serves.
- `delivery` is the read: `hook`, `intro`, `tense`, `sad`, `mystery`,
  `reveal`, `action`, `normal`, `outro`.
- `payload` is **required on every line** - see the next section.
- `narrative_jump` is `true` when the line moves to a new place or time.
- `claim` is present only on lines whose evidence is speech.

## `payload`: what this line is FOR

Every line must declare one of five values. This is the single most important
field you write, because a line that carries none of these is a line the
viewer can leave during.

| value | the line gives the viewer | example |
|---|---|---|
| `stake` | what it costs, what is risked, what cannot be undone - best with a number | *"A hundred and twenty thousand baht. The place is free; getting through the door is not."* |
| `reasoning` | what a character is thinking and **why** they act | *"Lynn does not say yes. She also does not say no, and Pat has met enough people to know that is the same thing with a delay on it."* |
| `judgment` | **your** opinion, an aside, a joke, a remark on how the film is made | *"He is rich in the way that never has to be explained to anyone, least of all to him."* |
| `loop` | a promise that pulls the viewer to the next line | *"Then she sits down at the piano, and this is where the whole idea comes from."* |
| `rest` | pure description - a breath between loaded lines | *"She sits with her chin on her hand and looks down the rows."* |

Rules the validator enforces on the assembled draft:

- **`rest` may not exceed 25% of lines.** Rest lines are not banned; the human
  draft has them. They work because they sit *between* loaded lines.
- **Never three `rest` lines in a row.** That is where a viewer leaves.
- **A `loop` at least every 12 lines.** A loop does not need a question mark -
  the human draft contains **zero** question marks and still opens loops, with
  flat promises like *"Now meet the other one."*
- **A `judgment` at least every 25 lines of your act**, and more is better.

Label honestly. A separate auditor who has not seen this prompt will read 20
lines at random and check your labels against the text; **more than 3 wrong
labels fails the whole round and the act is rewritten.** Labelling a screen
description `stake` does not make it one.

## Every requirement here has a CEILING as well as a floor

The first draft written against these rules passed every single one of them
and came out **three times too long** - 353 lines and 58 minutes against a
human reference of 147 lines and 20 minutes. Eight writers each maximised
every floor they were given:

| | human reference | first re-run | allowed band |
|---|---|---|---|
| sentences of 30+ words | 4.3% | **18.9%** | 2% - 12% |
| lines with a judgment/aside | 7.5% | **27.5%** | 3% - 15% |
| lines per beat | 1.93 | **3.24** | up to 2.5 |

All three are now gated in **both** directions. A long sentence is a device,
not a default. An opinion on every line is not a point of view, it is a
running commentary. And three lines on one beat almost always means two of
them say the same thing.

**Aim for roughly two lines per beat.** There is still no runtime target and
nothing is compared against a number of minutes - but a beat that takes four
lines to tell is a beat being re-told.

## Rhythm: vary line length on purpose

The validator measures the standard deviation of words-per-line across the
finished draft and **rejects anything below 9.0**. The rejected draft scored
3.9; the human draft scores 13.7.

You cannot fix this by padding. You fix it by writing some lines long and some
lines very short:

- Let a loaded line run **30, 40, even 70 words** when it is carrying a
  mechanism or a piece of reasoning. At least one sentence in every fifty must
  be 30+ words.
- Then **hit it with a short one.** A sentence of five words or fewer
  immediately after a long one is the single device that most separates the
  human draft from the machine draft (5.9% of sentences vs 1.3%).
- Do not write short sentences on their own as a tic. The rejected draft had
  *more* short sentences than the human one - they were all the same stunted
  shape (*"He keeps working." "They drop."*) with nothing long to land against.
- Vary how lines **open**. Do not start line after line with a place or a
  time (*"Night, steam venting..." / "At the guarded door..." / "At a far
  booth..."*). The rejected draft had six of those in a row.

## Hook, intro, outro

If your act contains the **first** line of the film's recap:

- One line is `"delivery": "hook"` and must carry a **`hook_question`** field
  naming the specific unresolved question it raises:
  `"hook_question": "What is in the sealed bag, and why is she being questioned?"`
  If you cannot name the question, what you have written is a statement, not a
  hook. Do not use the film's first scene just because it is first - use the
  image that raises a question.
- The line after the hook is `"delivery": "intro"`: say who you are, name the
  film, and turn hard into the story.

If your act contains the **last** line:

- One line is `"delivery": "outro"`, and it must state **what the ending
  means before** any call to action. The human draft: *"The only one who pays
  in full is the one who decides to stop. If you made it this far, subscribe
  and tell me what to recap next."* An outro that only reports the last event
  is the single thing audiences name when they call a recap shallow.

## Have a point of view

This is the section that replaces *"do not editorialise"*.

- Say what you think of a character or a choice. *"Her father takes it sitting
  down without raising his voice, which is worse than if he had."*
- You may address the viewer as **you**, and you may speak as **I**.
- You may remark on how the film is made - *"The film keeps them in
  silhouette"*, *"the camera stays on her face for all of it rather than his,
  because the answer was never going to come from him."* This is the one
  exception to the no-camera-language rule below, and it is allowed only when
  the remark is a **judgment about meaning**, not a description of a shot.
- **Play the film's jokes, do not report them.** The rejected draft had a
  character sell a minivan as a Hulk-green family car and narrated it flatly.
- Understatement beats exclamation. The human draft's biggest laugh is four
  words: *"She is googling the essay."*

## Action: an argument with manoeuvres around it, not a list of manoeuvres

The rejected draft's final race ran eleven lines, nine of them pure
mechanics - *"A snap of the shifter brings them level, door to door in orange
sparks."* - and never once restated that the loser leaves Tokyo forever.

Write action in a repeating shape:

1. one wide line: **what is being decided here**,
2. one line of physical detail - one or two specifics, not a blow-by-blow,
3. one line of stake or interior.

Inside any run of four or more `tense`/`action` lines, a `stake` or
`reasoning` payload must appear **at least every four lines**. The validator
enforces this.

## Name people, and give them a role the first time

- First mention of a character carries their role in the same line:
  *"Kamata, the yakuza boss whose turf all of this runs on."*
- After that you may use the role or the name.
- Never *"the gangster"*, *"the man"*, *"one of them"* once a name exists.
- Within the first 45 seconds after the hook, the viewer must know who the
  film is about, what they want, and what is in the way - in plain words.

## Speech is evidence, and it is the only evidence for some things

Your payload lists, under each moment, the **transcript lines spoken inside
that window**.

- A causal link that lives in **dialogue** can only come from the transcript.
  **Write it.** Without it the story has holes.
- The transcript tells you **what is said and who is speaking** (RULES I4). It
  is **not** a source for what happens on screen. Where transcript and frames
  disagree, the frames win.
- Never write *"X talks to Y"*, *"argues"*, *"pitches"*, *"explains"* when the
  transcript tells you *what* was said. Say the content.

**Banned outright** - these are the narrator admitting it did not read the
transcript, and the validator fails the draft on them:

- *"whatever he says..."*, *"whatever she says..."*
- *"says something"*, *"answers loudly"*, *"replies quietly"* with no content
- introducing *"a visitor"* or any similar referent you never resolve

### Declaring a speech claim (RULES Part J)

Any line whose evidence is the speech itself must carry:

```json
"claim": { "type": "speech", "subject": "Lynn" }
```

`subject` is the **speaker**, and the speaker must appear in that moment's
`chars`, because the audit checks speaker presence and explicitly cannot check
content. If the speaker is not in `chars`, bind the line to a moment where they
are, or do not make the claim.

## Silence is a tool

A line may carry **no narration at all** if it declares
`"narration_silence_seconds": 6.0`. The picture holds and the music carries it.

- Use it **after a reveal, a death, or a climax** - never as filler.
- 4 to 10 seconds. The whole film gets **3 to 6** of these, so your act gets
  **at most one**, and only if something in it earns the silence.
- A blank `narration` **without** this field is a hard failure, not a pause.

## No camera language

You are writing what **happens**, not how it was filmed. The viewer is already
watching the footage.

Banned: *the camera, the cut, cut to, the frame, the shot, close-up, insert,
reverse, shot and reverse, one long take, held take, the wide, racks focus,
intercut, the lens, last shot, first frame, on-screen, in frame, fades out.*

This leaks in because the moment's `action` field was written by a tagger
looking at frames, so it is full of shot language. **`action` is never the prose
source (RULES I1) - rewrite it.**

Wrong: *"The camera pushes down onto the hands alone, working the keys."*
Right: *"She works the same four fingerings until they stop being music."*

The one exception is the judgment use described above - *"The film never shows
you what it is"* - where the remark is about meaning, not about a shot.

## Tone

Assign `delivery` from what the moment is doing, not by rotation.
`[TONE-FLAT]` fires if any one tone exceeds 90% of the draft. Note that the
rejected draft was 52% `tense`, which left nothing flat for tension to rise
out of.

## Hard rules

1. **Every line binds to a real moment.** `clip_start`/`clip_end` must come
   from a moment in the payload, copied exactly - unless you use the extension
   rule below.
2. **Capacity.** `words/3.0 + 0.6 <= duration * 1.4`. The payload gives you
   `maxwords` per moment, already computed. Do not exceed it. If a line wants
   to be 40 words and the moment cannot hold it, bind it to a longer moment or
   use the window-extension rule - do not trim every line to a uniform size,
   which is how the last draft reached SD 3.9.
3. **Chronological.** Lines run forward in time across the act. Never go back.
4. **One moment, one line.** Do not reuse a moment for two lines.
5. **Write only what the moment's `action` says is on screen.** The `action`
   text is a description of the footage; it is **not** prose to copy.
6. **Cover the beats.** Each beat in your act should get at least one line
   unless no moment in range can carry it - in which case say so in your reply.
7. **There is no length target.** Nothing compares your act against a runtime.
   Cover the beats and carry the payloads; do not pad and do not trim to hit a
   number.

## The window-extension rule

Sometimes a beat has no moment that covers it well enough. You may then
**extend a nearby moment's window outward to the nearest cut timestamps in
`_cuts.json`** so the line has somewhere to sit.

When you do this:

- `clip_start` and `clip_end` must still be **exact values from `_cuts.json`**.
- You must set **`"window_adjusted": true`** on that line.
- Keep the extension as small as will do the job.

`window_adjusted` is not a failure marker - it is how the adjustment becomes
visible at human review instead of disappearing into the draft.

## Output

Write **one JSON file** to `projects/<p>/draft.json.d/act<N>.json`:

```json
{ "act": 1, "lines": [ ... ] }
```

Line ids: start at `<N>00 + 1` (act 1 -> 101, act 2 -> 201 ...) so acts do not
collide. Assembly renumbers them.

No commentary outside the JSON.
