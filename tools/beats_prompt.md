# Propose the BEATS for one chunk of a film

A **beat** is one story event — the unit a recap must cover to stay followable.
Not a shot, not a scene: the thing that *happens*. A whole conversation is
usually one beat. A location change with nothing happening is usually none.

You are given one chunk of the film as:

- **moments** — `TIME | chars | depicts | action`, where `action` describes
  what is on screen in that window;
- **SPEECH** — the transcript lines spoken inside each moment.

## How many beats

There is no target number. The film decides it: **one beat for every time
something changes** - who knows what, who wants what, who holds what, who is
winning, who is alive. A chunk full of schemes and conversations may have 30
beats. A chunk that is one long fight may have 3.

(Owner, 17 Nov 2026. The old reference of "70-90 beats per film, 80/N per
chunk, err high" made 243 beats for Furious 7. Fights were cut into slices
like "armed men trade fire through the warehouse", and every slice later
needed a line or a hold.)

## What makes a beat

Include:
- a decision, a refusal, a threat, an admission
- a plan being formed or a mechanism being shown
- a reversal, a discovery, a consequence landing
- an arrival that changes what is possible

A long fight, chase or montage is **one beat for its outcome**, plus one beat
for each change inside it (someone is shot, the money is taken, the car
goes off the roof). Never a beat for "they keep fighting".

Do **not** make a beat out of:
- pure establishing (a building, a street) with nothing happening in it
- a reaction shot that belongs to the beat before it
- two lines of the same conversation (fold them into one beat)

## The audio is translated

If the film is not in English the transcript is machine translation. It tells
you **what is said and who is speaking**. It is **not** a source for what
happens on screen — that is what `action` is for. Where the two disagree, the
frames (`action`) win.

**Causality usually lives in the speech.** Who informed, who paid, who
threatened: the picture rarely carries it. Read the SPEECH lines.

## Output

Write **one JSON file** to `projects/<p>/beats.json.d/chunk<K>.json`:

```json
{
  "chunk": 3,
  "beats": [
    {
      "ts": "00:11:30",
      "what": "Lynn writes the answers onto an eraser wrapper",
      "chars": ["Lynn"],
      "kind": "action"
    }
  ]
}
```

- `ts` — **HH:MM:SS**, copied from the TIME of the moment where the beat
  starts. Never invent a timestamp.
- `what` — one clause, present tense, concrete. It names the event, not the
  shot. No camera language.
- `chars` — who is involved. `[]` if nobody identifiable.
- `kind` — one of `setup`, `action`, `dialogue`, `discovery`, `reveal`,
  `emotion`, `aftermath`, `transition`, `montage`.

Beats must be **in time order** and must stay inside your chunk's range.

## Also report, in your reply (not in the JSON)

- **REVEALS**: anything in this chunk that is a *payoff* — a fact the film has
  been withholding and now lands (who paid, who informed, who betrayed whom).
  Give the timestamp and the fact in one clause.
- **SET-PIECES**: any extended procedure the viewer must be able to follow
  (a heist, an exam, a chase). Give its start and end timestamps.

These two are assembled film-wide afterwards, so report them even if they feel
obvious.
