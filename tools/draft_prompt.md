# Draft one ACT of a recap

You write the narration for **one act** of a recap video. **How to tell it**
is in the story guide that follows this prompt (`prompts/story_guide.md`), so
read it first. This prompt covers only the mechanics: inputs, the line
format, and the rules the code checks.

The old version of this prompt asked for opinion quotas, an open loop every
12 lines, varied sentence lengths and running bits. Those requirements are
gone (owner, 16-17 Nov 2026): they produced lines that had the shape of a
script without the logic of a story. Do not write to any proportion.

## Inputs

- The act payload: the beats and the moments that fall inside them, with the
  transcript lines spoken in each moment's window.
- When the user message has **YOUR SLOTS** and a **WRITER BRIEF**: one reply
  line per slot. Code owns the id, the beat, the clip window and the holds,
  and each slot says how many words its footage holds. This is the normal
  path. The brief's rules apply on top of this prompt.
- `beats_proposal.md` (header and house rules), `names.json` (spell every
  name exactly as it does), and `_cuts.json` (used only for the
  window-extension rule below).

Do not read `draft.json` or any other project's draft. Write from the beats,
the moments and the transcript.

## A line

```json
{
  "slot": "a3-07",
  "narration": "Jakande's men take the laptop with God's Eye on it.",
  "delivery": "tense",
  "payload": "stake",
  "claim": { "type": "speech", "subject": "Lynn" }
}
```

Without slots, a line also carries `id`, `note` (its beat id), `clip_start`,
`clip_end` and `narrative_jump` (true when it moves to a new place or time).

- `delivery` is how it is read aloud: `tense`, `sad`, `mystery`, `reveal`,
  `action`, `normal` (plus `intro` and `outro` on those slots). Choose it from
  what the moment is doing. If one tone covers more than 90% of the draft,
  `[TONE-FLAT]` fires. `sad` goes only on real loss or grief.
- `payload` is a **label**, not a target. Label each line honestly:
  - `reasoning`: who does what and why.
  - `stake`: what is risked, lost, won, or changes hands.
  - `judgment`: your own reaction.
  - `loop`: a line that points to what comes next.
  - `rest`: pure description of the picture.

  The checks on labels are ceilings:
  - `rest` may be at most a quarter of the lines, and never three in a row.
  - Your reactions may be at most about one line in five.
  - In a long action run, a `stake` or `reasoning` line must appear at least
    every four lines.

  A plain story line (who does what, and why) is `reasoning` or `stake`, and
  it never fails any of these.
- `claim`: a line whose evidence is speech carries
  `{"type": "speech", "subject": "<speaker>"}`. The speaker must be in that
  moment's characters. If they are not, bind the line elsewhere or drop the
  claim.
- `callback_beat`: a line that refers back to an earlier event, or claims a
  habit, names the beat that shows it (story guide, the Facts section).

## Present, past, imagined

A beat line in the beat map can end with its **frame**: `now` (the film's
present), `past` (a flashback, a memory shown on screen, a past someone
recounts while the film shows it) or `imagined` (a dream, a vision, a false
version shown as if it happened). The listener cannot see the film's own
cues - the colour, the younger faces, the dissolve - so **say it when the
picture changes frame, and say it again when it comes back**: "Years
earlier, ...", "In his dream, ...", "He remembers the night ...", "Back in
the cell, ...", "He wakes." Tell the past in the past tense. When a beat in
another frame opens on a hold, the line BEFORE the hold says where we are
going. `[TIME-FRAME]` checks this.

## Hook, intro, outro

- The **hook and the title are written at the plan stage**. Do not write a
  `hook` line.
- **Intro and opening slots**: follow what the brief says for them (cold open,
  genre lever, the intro sentence).
- **Outro**: say what the ending means in one or two plain lines, then the
  sign-off. An outro that only reports the last event is the thing viewers
  name when they call a recap shallow.

## Banned outright

The validator fails the draft on these:

- Narrating around dialogue you did not read: *"whatever he says"*, *"says
  something"*, *"answers loudly"* with no content, or a *"visitor"* you never
  resolve.
- Camera and editing words: *the camera, cut, cut to, the frame, the shot,
  close-up, insert, reverse, take, the wide, racks focus, intercut, the lens,
  on-screen, in frame, fades out*. The moment's `action` text was written by a
  tagger looking at frames and is full of this language. It describes the
  footage; it is never prose to copy.
- A blank `narration` without `"narration_silence_seconds": 4-10`. Silence is
  allowed after a death, a reveal or a climax, at most once in an act.

## Hard rules (when you bind windows yourself, without slots)

1. Every line binds to a real moment: `clip_start` and `clip_end` are copied
   exactly from the payload, or come from the window-extension rule.
2. Capacity: never exceed a moment's `maxwords`. If a line needs more room,
   bind it to a longer moment.
3. Chronological: lines run forward in time, and no moment is used twice.
4. Cover the beats: every beat gets a line unless no moment can carry it. If
   so, say so in your reply.

**Window extension.** If no moment covers a beat well, you may extend a
nearby moment outward to the nearest cut timestamps in `_cuts.json` (exact
values), and set `"window_adjusted": true` on that line. Keep the extension
as small as will do the job.

## Output

One JSON object: `{"act": N, "lines": [...]}`. Without slots, line ids start
at `N00 + 1` (act 1 -> 101). No commentary outside the JSON.
