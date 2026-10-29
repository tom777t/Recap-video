# Selecting the `<film_speaks>` units

You are choosing the 2-3 moments in this recap where **the narration stops and
the film's own dialogue plays at full level**.

This matters more than its size suggests. Everywhere else in the video the film
is heard through the no-vocals stem — engines, tyres, impacts, no voices. So a
`film_speaks` unit is the **only original dialogue in the finished video**. Two
or three times, a character speaks for themselves. That is the whole device.

A recap with **zero** of them is the failure this stage exists to prevent. It
happened: a finished 17-minute film shipped with none, because nothing asked.

## Your input

`projects/<project>/film_speaks_candidates.json`, produced by
`python tools/film_speaks_candidates.py --project <project>`.

Every candidate already carries the facts that can be **measured**. Do not
re-derive them, and do not overrule them:

| field | meaning |
|---|---|
| `start`, `end`, `seconds` | the span of film audio that would play |
| `text` | the transcript of that span |
| `criteria` | which eligibility rules it satisfies (see below) |
| `evidence` | which reveal / how much thesis overlap / where in the film |
| `act` | which act it falls in |
| `audio.margin_db` | **how far the dialogue stands above the music and effects, measured** |
| `narration_overlap.worst` | how much of the quote nearby narration already says |

Candidates overlap each other on purpose — the same moment appears at several
lengths, because choosing the right boundary is your judgement.

## The rules

### a. Eligibility — at least one must hold
The generator has already applied these; `criteria` tells you which fired.
- **`reveal_own_words`** — the quote is at or after a reveal's landing and
  states that reveal in the character's own words.
- **`thesis`** — it states the recap's angle (see `angle.md`) in a character's
  words.
- **`climax_or_final`** — it is the climax line or the film's final line.

Confirm the criterion really holds by reading the quote. The generator matches
on word overlap, which finds candidates but cannot tell whether a line *means*
the thesis. If it does not, discard it and say so.

### b. Quality — all of these must hold
- **3-15 seconds.** Already enforced.
- **Self-contained.** Understandable with only what the recap has told the
  viewer *by that point*. Read the draft lines before it. A quote that needs a
  name, a relationship or a plot fact the recap has not introduced fails.
  **This is the judgement the generator cannot make — it is the main thing you
  are here for.**
- **Clean audio.** `audio.margin_db` must be **>= 3 dB**. Below that the line
  is fighting the music and will not be intelligible at full level. A candidate
  with `audio.measured: false` fails: a quote is not clean because nobody
  checked.
- **In the narration language**, or else it needs a caption — say so if it does.
- **Not already paraphrased.** High `narration_overlap.worst` is not an
  automatic rejection, because you can fix it by rewriting the neighbouring
  line (see step d). But if the beat *cannot* be set up without saying the
  quote, drop the candidate.

### c. Count and spacing
- **2-3 per film.** Zero is an error whenever eligible candidates exist.
- **At most one per act** (`act`, and the act boundaries are in `acts`).
- **Never two within `rules.min_gap_sec`** (3 minutes). Two hand-overs inside
  three minutes read as a compilation, not as two events.

Check the arithmetic before you commit: it is easy to pick two strong
candidates that are 117 seconds apart and fail spacing.

### d. Adjust the neighbouring narration
A hand-over only works if it is framed. For each pick, specify:
- **the line BEFORE** — it sets the moment up *without paraphrasing the quote*.
  Its job is to make the viewer want to hear this, then get out of the way. If
  it currently says what the quote says, rewrite it.
- **the line AFTER** — it reacts. It does not summarise what was just heard; it
  tells the viewer what it meant or what it costs.

Give the exact replacement text for both, with the same word budget as the line
it replaces (capacity is bound to the shot).

## Output

Write `projects/<project>/film_speaks_selection.json`:

```json
{
  "selected": [
    {
      "start": 0.0, "end": 0.0, "seconds": 0.0,
      "quote": "the exact words that will play",
      "criterion": "reveal | climax | thesis",
      "justification": "one sentence: why THIS moment earns the film's own voice",
      "act": 0,
      "audio_margin_db": 0.0,
      "self_contained": "what the viewer already knows that makes this land",
      "before": {"line_id": 0, "new_narration": "...", "why": "..."},
      "after":  {"line_id": 0, "new_narration": "...", "why": "..."}
    }
  ],
  "rejected": [
    {"start": 0.0, "reason": "which rule it failed, with the number"}
  ],
  "spacing_check": "the gaps between picks, in seconds, and the acts they fall in",
  "count_note": "why this many and not more"
}
```

`criterion` must contain one of reveal / climax / thesis.

## Report back

A table of the picks: timestamp, criterion, audio margin, act, and the quote.
Then the rejections with the rule each failed. Then:
- the spacing arithmetic, explicitly
- any candidate you wanted but could not take, and which rule stopped you
- whether you could reach the minimum count, and if not, why — do not pad to
  the minimum with a weak pick, say you could not
- any case where you disagree with a measurement
