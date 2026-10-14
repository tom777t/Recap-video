# Project status

Why this project has no `beats_proposal.md`, and therefore why
`SET-PIECE-DECLARE`, `RATCHET` and the whole `DEPTH-*` family are no-ops here.

Recorded 2026-09-05 following the G2 precedent: an absence that a gate reads as
"nothing to check" must be a decision on the record, not a default.

**Evidence common to all six:** each arrived in a single bulk commit on
2026-08-13 with exactly one commit since, and **none has a source video**.
They cannot be catalogued or re-rendered as they stand.

**Not a mode question.** A beat map is not linear-only - the review-mode
projects carry them too (gonegirl2014 has 36 beats, joker2019 38,
parasite2019 28). `style:` itself is declared on only 6 of 17 projects; the
rest default to `review` by absence, which is the same silent-default pattern
one level further up and is NOT addressed here.

```project-status
status: legacy
mode: undetermined
reason: Imported 2026-08-13, no source video, no beat map. Mode cannot be determined from the artefacts - see the correction below.
```

## What is actually here

shots.json (67), skeleton.json, draft.json (69 lines, 0 pool / 69 explicit). 69 claims.

## Correction, 2026-09-05

An earlier version of this file said the behavioural signature was "linear",
citing 69 lines that are all explicit windows with zero pool use. **That
inference was wrong and is withdrawn.**

The 0-pool / all-explicit shape does not separate the two modes. Every mature
project has it, on both sides: gonegirl2014 0/67, interstellar2014 0/91,
parasite2019 0/114, howtomakemillions2024 0/129 - all `review` - against
badgenius2017 0/150 and superbad2007 0/144 - both `linear`. Pool use survives
only in the four legacy no-source imports (armourofgod 11, it2017 10,
punisher 9, rushhour5 27). **Pool use is a legacy signature, not a review
signature**, and it says nothing about mode.

What a dry run on a scratch copy actually shows for declaring this project
`style: linear` (measured, original untouched):

- **gains** `BINDING-INTEGRITY` - which really does verify all 69
  explicit-window lines land on a catalogued shot. Real coverage, lost today.
- gains `CATALOGUE-DENSITY` and `SNAP-GRID` **in name only** - both print
  "not measured" (no beat map, no `_cuts.json`).
- gains `SET-PIECE` in name only - skipped at outline stage.
- **loses** `DRAFT-TARGET`, which is skipped while at outline stage.
- **degrades** `ACTION-SETUP` from 11 per-line findings to a single summary
  line, because review gets the *stricter* variant of that gate.
- `BEAT-COVERAGE`, `BEAT-MAP` and `REVEAL-TIMING` stay dark either way - they
  need the beat map this project does not have.

So the flip is worth exactly one real gate here, not twelve cells. The mode
remains undetermined and is not being guessed. Note also that `style:` lives in
`beats_proposal.md`, so it cannot be declared at all until a beat map exists -
which requires a source video this project does not have.
