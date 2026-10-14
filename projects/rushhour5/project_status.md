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
status: abandoned
mode: review
reason: Imported 2026-08-13, no source video, no catalogue, and the draft does not validate - shots B6 and B10 each exceed the hero reuse cap. It has failed every run since it arrived.
```

## What is actually here

broll.json + draft.json (106 lines, 27 pool / 79 explicit), 0 shots. This is the only project in the repo that fails `recap.py draft` outright, and it has done so continuously. Fixing it is not possible without a source.
