---
description: Run a film all the way through the recap pipeline, doing the LLM stages with subagents, stopping only at the two human checkpoints.
agent: build
---

Run the recap pipeline on this film, end to end: `$ARGUMENTS`

You are the orchestrator. `run.ps1` does every mechanical stage and **halts**
whenever a stage needs an LLM. Your job is to do that work with subagents and
resume, over and over, until the pipeline reaches one of the two human
checkpoints. **Those two are the only places you stop.**

## The loop

1. Run the pipeline from the shell (workdir `D:\Recap Vid`, PowerShell).
2. Read its output. It either finishes a stage, or prints a `DUNG:` block with
   a worklist and the exact resume command.
3. If it halted on an **LLM stage**, do that stage's work with subagents (below),
   then run the resume command it printed.
4. Repeat from 2.
5. Stop **only** when it halts on `DUYET DRAFT` or `XEM VIDEO`.

Do not stop to report progress between stages. Do not ask whether to continue.

## First invocation

Derive a project name from the filename: lowercase, letters and digits only,
plus the release year if present (`Bad.Genius.2017.1080p.mkv` ->
`badgenius2017`). State the name you chose, then start.

Decide `-Translate` by the audio language: if the film is not in English, pass
it, because Whisper must translate rather than transcribe.

```
.\run.ps1 -Source "<path>" -Project <name> [-Translate]
```

If the source is not 1080p the script asks before spending ~an hour on
Whisper. Report what it said and let the user answer — that one is theirs.

## The three LLM stages

### TAG SPANS

`check_stage.py <p> tags-todo` lists the spans with no tag yet. **One subagent
per span**, run in parallel batches of 8-13.

Each subagent: read `tools/span_prompt.md`, run
`python tools/span_payload.py <p> <span>` to get its shot list, **read every
frame listed**, and write `projects/<p>/spans.json.d/<span>.json`.

Tell each one it must not open `shots.json` or `beats_proposal.md`.

A subagent that returns an empty reply has often still written its file.
**Check the directory, not the replies**, and relaunch only the genuinely
missing ones.

### BEAT MAP

Eight chunks. One subagent per chunk: read `tools/beats_prompt.md`, run
`python tools/beat_payload.py <p> <k> 8`, write
`projects/<p>/beats.json.d/chunk<k>.json`.

Then **one more subagent** for the film-wide pass: read
`tools/reveals_prompt.md`, use `python tools/speech_at.py <p> <start> <end>`
to find where facts are first spoken, and write `projects/<p>/reveals.json`.
This stage carries the reveal-map, which is what protects the recap from
spoiling the film — do not let it be rushed.

### DRAFT

One subagent per act: read `tools/draft_prompt.md`, run
`python tools/act_payload.py <p> <n>`, write
`projects/<p>/draft.json.d/act<n>.json`. An act with ~30+ beats should be
split in half (`act_payload.py <p> <n> 1` and `... 2` -> `act<n>a.json`,
`act<n>b.json`).

Then `python tools/assemble_draft.py <p>` and resume.

When the gates fail, the script bumps the round counter and halts again. Feed
the findings back **per act**, fix only what the gates named, and resume. The
script stops the loop at 3 rounds; do not attempt a fourth.

## Rules that are not negotiable

- **Never edit anything under `projects/badgenius2017/` or any other existing
  human project.** They are reference data.
- Never write narration from a moment's `action` text verbatim — it describes
  footage, not story (RULES I1).
- If a stage's output exists but is invalid, `check_stage.py` says so. Trust
  that over the file existing.
- If something fails twice the same way, **stop and say so**. Do not try a
  third variation silently.

## When you stop

At a checkpoint, report:

- which checkpoint, and the exact command to resume;
- the gate findings still outstanding, named;
- for the draft checkpoint: words, estimated runtime and the basis used, beat
  coverage, tone distribution, and anything you judged but could not verify;
- for the censor checkpoint: the rendered runtime against the estimate, and
  every shot carrying a `censor` value.

Report what you are unsure of. A clean summary of work you did not check is
worse than a short one that names the gap.
