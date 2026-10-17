# Span tagging - group cuts into MOMENTS, then tag them

You are tagging **one span** of a film. Fresh context, no memory of other spans.

v1 of this pipeline tried to group cuts into moments mechanically, from cut
timings and speech timings. It failed: it scored **worse than doing nothing**
on both test films, and a direct test showed human window edges are no closer
to speech boundaries than a randomly chosen cut. The grouping decision turned
out to be **editorial** - it depends on what is happening on screen. That is
why it is now yours.

## What you get

- A list of **shots** in this span. Each shot is one camera shot: an index, a
  start timestamp, an end timestamp, a duration.
- **One frame per shot** (long shots get a second frame). The filename tells
  you which shot it belongs to.
- The span's `own_start`, `own_end`, and `ext_end`.

## What you must NOT use

- `shots.json` - that is the human catalogue, the answer key. Do not open it.
- `beats_proposal.md` - in the real flow the beat map is written **after** the
  catalogue. Do not open it.
- `draft.json`, `timeline.json`, `script.txt`.

You may read `names.json` (cast list) if it exists, to get character names right.

If you cannot name a character, use a short stable description
(`the woman in the blue uniform`) rather than inventing a name.

## 1. Group the shots into moments

A **moment** is a run of **consecutive** shots that belong together as one
beat of screen action. It is the unit a narrator would describe in one line.

Reference numbers, from the two films measured:

- a moment is typically **2-4 camera shots**
- it is typically **10-25 seconds**
- a single long held take is often a moment on its own

Group by **what is happening**, not by duration:

- shot / reverse-shot of the same conversation -> **one moment**
- a flurry of fast cuts covering one action -> **one moment**
- the location changes -> **new moment**
- the subject changes, or time has clearly passed -> **new moment**
- an insert or cutaway that serves the surrounding action (a close-up of a
  hand, a screen, a clock) -> **stays inside** that moment
- a long take that is doing its own work -> **its own moment**

### Hard rules on the boundaries

1. Every moment's `clip_start` and `clip_end` must be **exact timestamps from
   the shot list** - a `clip_start` is some shot's `start`, a `clip_end` is
   some shot's `end`. Never invent a timestamp between cuts.
2. `shots` is the list of shot indices in the moment. It must be
   **consecutive** - `[4,5,6]`, never `[4,6]`.
3. The moments must **tile the whole span, from the first shot to the last,
   with no gaps and no overlaps.** Every shot index appears in exactly one
   moment.

## 2. The span edge - read this

You are shown shots up to `ext_end`, which is about 20 seconds past `own_end`.
That tail is **context**, so you can see whether a moment that starts before
`own_end` keeps going afterwards.

**Do not force a moment to end at `own_end`.** If a moment runs across that
boundary, let it run to its natural end in the tail. Assembly keeps each moment
exactly once, assigning it to whichever span contains its midpoint, so a moment
that crosses the edge is kept whole and is not double-counted.

Tile everything you are shown, from the first shot to the last one in the tail.

## 3. `depicts` - TWO axes, and you owe one label from each side

| axis | meaning | labels |
|---|---|---|
| **VISIBLE** | what the camera literally shows | `action`, `dialogue`, `establishing`, `montage`, `reaction`, `transition` |
| **STORY** | what the scene does for the plot | `aftermath`, `discovery`, `emotion`, `reveal`, `setup` |

**You MUST include at least one VISIBLE label.** You MAY add STORY labels.
An answer made only of STORY labels scores zero on the visible axis even when
it is a fair reading of the scene. Pick the VISIBLE label for what **dominates
the frames you were given**.

## 4. `chars`

Named characters **visible in the frames of this moment**. Empty list if none
can be identified. Do not list a character because the plot implies they are
nearby - only if they are on screen.

## 5. `action`

One or two sentences describing what happens across the moment, written from
the frames. Keep it terse and frame-verified - the human catalogue's median is
about 200 characters. Do not write a briefing.

**Describe the change across the moment.** If the last shot shows something
different from the first - someone leaves, a door opens, a face turns away -
**say so**. A caption that averages the moment into one static description is
the known failure mode: it is still true, and it silently loses the only thing
the moment is doing.

Never describe anything you were not shown a frame of.

## 6. `censor`

Return a `censor` value on **every** moment. Default `none`.

| what is in frame | value |
|---|---|
| nothing explicit | `none` |
| incidental background detail, not the subject, not readable | `blur_light` |
| explicit content that fills the frame, or is the point of the shot | `blur_heavy` |

Tag for: nudity, sexual acts, readable explicit images, blood/gore with visible
wounds. Judge by **what is actually in the frames**, not by what the type of
scene usually contains. When it is not `none`, add a `censor_note` naming the
element and roughly how much of the frame it occupies.

## Output

Write **one JSON file** to `projects/<project>/spans.json.d/<span_id>.json`:

```json
{
  "span": "sp07",
  "moments": [
    {
      "shots": [0, 1, 2],
      "clip_start": "01:00:00.042",
      "clip_end": "01:00:14.375",
      "depicts": ["dialogue", "setup"],
      "chars": ["Lynn", "Bank"],
      "action": "Lynn and Bank talk across a library table; she slides a sheet towards him and he does not take it. By the last shot he has sat back, out of her reach.",
      "censor": "none"
    }
  ]
}
```

Rules for the file:
- `shots` consecutive, every shot index used exactly once, in order.
- `clip_start` / `clip_end` copied exactly from the shot list.
- `censor_note` only when `censor` is not `none`.
- No commentary outside the JSON.

If some frames failed to extract and a shot has no image, still include the
shot in a moment, and say in `action` that it was not visually verified.
**Never drop a shot to make the tiling work.**
