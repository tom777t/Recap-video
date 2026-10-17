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

## What a line is

```json
{
  "id": 17,
  "narration": "Lynn slides the eraser back over her shoulder without looking.",
  "clip_start": "00:11:41.000",
  "clip_end": "00:11:52.500",
  "note": "B10",
  "delivery": "tense",
  "narrative_jump": false,
  "claim": { "type": "speech", "subject": "Lynn" }
}
```

`claim` is present only on lines whose evidence is speech - see below.

- `note` is the beat id this line serves.
- `delivery` is `hook` for the opening line, otherwise `normal`.
- `narrative_jump` is `true` when the line moves to a new place or time.

## Hard rules

1. **Every line binds to a real moment.** `clip_start`/`clip_end` must come
   from a moment in the payload, copied exactly - unless you use the extension
   rule below.
2. **Capacity.** `words/3.0 + 0.6 <= duration * 1.4`. The payload gives you
   `maxwords` per moment, already computed. Do not exceed it.
3. **Chronological.** Lines run forward in time across the act. Never go back.
4. **One moment, one line.** Do not reuse a moment for two lines.
5. **Write only what the moment's `action` says is on screen.** The `action`
   text is a description of the footage; it is **not** prose to copy. Rewrite
   it as narration. Never assert something the `action` does not support.
6. **Cover the beats.** Each beat in your act should get at least one line
   unless no moment in range can carry it - in which case say so in your reply.

## The window-extension rule

Sometimes a beat has no moment that covers it well enough. You may then
**extend a nearby moment's window outward to the nearest cut timestamps in
`_cuts.json`** so the line has somewhere to sit.

When you do this:

- `clip_start` and `clip_end` must still be **exact values from `_cuts.json`**.
- You must set **`"window_adjusted": true`** on that line.
- Keep the extension as small as will do the job.

`window_adjusted` is not a failure marker - it is how the adjustment becomes
visible at human review instead of disappearing into the draft. A line that
needed an adjustment and does not carry the flag is a silent edit, which is
worse than the adjustment.

## Speech is evidence, and it is the only evidence for some things

Your payload now lists, under each moment, the **transcript lines spoken inside
that window**. Earlier versions of this prompt did not, and the result was a
draft in which nothing said *who informed on whom* - the scholarship was simply
lost, with no cause - and a dozen lines that read "talks", "argues", "pitches"
without saying what was said.

- A causal link that lives in **dialogue** can only come from the transcript.
  **Write it.** It is not optional detail; without it the story has holes.
- The audio is Thai and the transcript is machine translation. Per RULES I4 it
  tells you **what is said and who is speaking**. It is **not** a source for
  what happens on screen. Where transcript and frames disagree, the frames win.
- Never write "X talks to Y", "argues", "pitches", "explains" when the
  transcript tells you *what* was said. Say the content.

### Declaring a speech claim (RULES Part J)

Any line whose evidence is the speech itself must carry:

```json
"claim": { "type": "speech", "subject": "Lynn" }
```

`subject` is the **speaker**, and the speaker must appear in that moment's
`chars`, because the audit checks speaker presence and explicitly cannot check
content. If the speaker is not in `chars`, bind the line to a moment where they
are, or do not make the claim.

## No camera language

You are writing what **happens**, not how it was filmed. The viewer is already
watching the footage.

Banned: *the camera, the cut, cut to, the frame, the shot, close-up, insert,
reverse, shot and reverse, one long take, held take, the wide, racks focus,
intercut, the lens, last shot, first frame, on-screen, in frame, fades out.*

This leaks in because the moment's `action` field was written by a tagger
looking at frames, so it is full of shot language. **`action` is never the prose
source (RULES I1) - rewrite it.** `[CAMERA-LANGUAGE]` in the linter now measures
this; the first machine draft tripped it 32 times.

Wrong: *"The camera pushes down onto the hands alone, working the keys."*
Right: *"She works the same four fingerings until they stop being music."*

## Tone

Every line carries `delivery`. The first machine draft was **186 of 187 lines
`normal`**, which renders as a flat 20-minute read. The human draft on this film
runs 70 tense / 45 normal / 24 sad / 3 reveal / 2 hook.

Use: `hook` (the opening), `tense`, `sad`, `mystery`, `reveal`, `normal`.
Assign from what the moment is doing, not by rotation. `[TONE-FLAT]` fires if
any one tone exceeds 90% of the draft.

## Register

Match the register the beat map asks for in its header. Terse, concrete,
present tense. Describe what is on screen and what it means; do not explain
the plot the audience is about to watch, and do not editorialise.

Do not write a line that merely narrates the image with no information
("A girl sits at a table"). Each line should move the story.

## Output

Write **one JSON file** to `projects/<p>/draft.json.d/act<N>.json`:

```json
{ "act": 1, "lines": [ ... ] }
```

Line ids: start at `<N>00 + 1` (act 1 -> 101, act 2 -> 201 ...) so acts do not
collide. Assembly renumbers them.

No commentary outside the JSON.
