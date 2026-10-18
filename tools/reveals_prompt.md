# Consolidate the film-wide REVEAL-MAP and SET-PIECES

You are given a finished machine beat list for one film. Produce two things:
the **reveal-map** (spoiler protection) and the **set-pieces** list.

Inputs you may use:

- `projects/<p>/beats_proposal_machine.md` — the beat list.
- `python tools/speech_at.py <p> <start> <end>` — the transcript and the
  moment descriptions in a time range. **Use this.** It is how you find where
  a fact is actually said.

Do **not** read `beats_proposal.md`, `draft.json`, or any human beat map.

---

## What counts as a reveal

Two kinds. Both are things a recap must not state early.

### Type A — a concealed fact

The film knows something, shows its effects, and withholds it until a
disclosure. *Who paid. Who informed. Who the body was.*

### Type B — a character-arc inversion

**Someone becomes the thing they opposed, exposed, or were the victim of.**

This type was missed on the first film and it matters as much as Type A. The
test is not "is there a single hidden fact" — an inversion is usually disclosed
gradually, in behaviour, and still lands at one identifiable moment: the first
point where the character's new position is unmistakable.

Examples of the shape:
- the whistle-blower starts running the scheme he reported
- the investigator takes the bribe he was investigating
- the one who refused the money is the one demanding it

If you catch yourself writing *"progressively disclosed, not concealed, so not
a reveal"* — that is exactly the reasoning that missed one last time. Gradual
disclosure does not disqualify an inversion. Ask instead: **does the recap
spoil the film by naming this in its first half?** If yes, it is a reveal.

---

## Where a reveal LANDS — the rule that was wrong before

> **`land` is the first moment the hidden fact is SPOKEN or SHOWN. It is NOT
> the moment the characters react to it.**

On the first film this was got wrong by 3 minutes 10 seconds: the land was put
at the fist-fight that followed the admission instead of the admission itself.
That over-protects — the correct payoff line then reads as an early leak, and
the three minutes in between are falsely guarded.

So, for every candidate:

1. Find the moment you think it lands.
2. Run `speech_at.py` over a window **starting at least 4 minutes earlier**.
3. Read backwards for the earliest line where the fact becomes knowable, or
   the earliest shot whose `action` shows it plainly.
4. `land` is **that** timestamp, not the shouting, crying, punching or
   realisation that follows it.

A reaction is evidence a reveal already happened. It is never the reveal.

### A slip counts. An explicit admission is usually too late.

The moment a fact becomes **knowable to the audience** is the land — not the
moment someone finally says it in plain words. Films disclose by accident
first: a character knows a detail they could only know if guilty, and the
admission comes minutes later under pressure.

Worked example from the first film. The fact is *Pat paid the men who beat
Bank*. Three candidate timestamps:

| | |
|---|---|
| `01:11:26` | Pat, rehearsing a cover story, says Bank *"was abandoned by a bunch of people in the trash can"* — a detail only an attacker could know. **This is the land.** |
| `01:12:25` | Bank: *"I've never told anyone that I woke up in the trash can."* The character naming the slip. Reaction. |
| `01:14:07` | Pat finally says it outright. **Three minutes too late** — the audience has known since the slip. |

Landing on the admission over-protects by minutes and makes the gate flag the
correct payoff line. Read for the **first leak**, not the confession.

### Snap `land` to the start of its moment

Once you have the timestamp of the disclosure, set `land` to the
**`clip_start` of the moment that contains it** (the `SHOT` line at or before
it in `speech_at.py` output).

Reason: a draft line covering this reveal will be bound to that moment and
therefore starts at its `clip_start`. If `land` sits a few seconds later, the
line that *delivers* the reveal is flagged as leaking it. Snapping removes a
whole class of false positive by construction.

In the worked example the slip at `01:11:26` sits in the moment beginning
`01:11:19`, so `land: 01:11:19`.

---

## How strict to be

A typical film has **2-5** reveals. Twenty makes the map useless; zero makes it
a no-op. Reject anything the audience learns at the same instant it becomes
true — plot mechanics, prices, a character's live discovery of a timetable.
Those are information, not withholding.

For each kept reveal give 8-12 `hold` phrases: literal strings a writer might
use to state the fact early, including paraphrases. The gate does a text scan
for them in lines placed before `land`.

## Set-pieces

An extended procedure the viewer must be able to follow: a heist, an exam, a
chase. Merge anything split across chunk boundaries into one entry. Mark
`verified: unverified` unless the span was frame-checked start to finish.

## Output

Write `projects/<p>/reveals.json`:

```json
{
  "reveals": [
    {"land": "01:10:40", "type": "A", "fact": "one clause",
     "hold": ["phrase", "phrase"]}
  ],
  "set_pieces": [
    {"name": "...", "start": "01:20:53", "end": "01:33:38",
     "verified": "unverified", "keep": true}
  ]
}
```

In your reply, for **each kept reveal**, state the timestamp you first
considered and the timestamp you settled on after reading backwards, so the
landing rule can be checked.
