# Gates by construction - the slot-based API writer

2026-11-08. Written alongside `tools/write_slots.py` (slots), the schema-first
checks in `tools/write_api.py`, and `[AUDIT-UNPARSEABLE]` running first in
`pipeline/draft.py`. Tests: `tools/test_write_slots.py`,
`tools/test_write_schema.py`.

The API writer used to "write first, judge later": the model chose the
timestamps, the line lengths, where loops open and where the narrator reacts,
and the gates graded each choice afterwards. Now the plan becomes one SLOT per
line (`plan.json` `slots`), derived by code from the model's per-beat counts
and the gates' own constants. The writer fills slots with words; code owns ids,
beats, windows and holds. Every gate still runs as the final check - nothing is
removed in this pass.

## 1. Satisfied by construction

A gate here can still fire, but only if a writer ignores its slot, and
`write_slots.check_slots` reports that deviation inside the stage first.

| Gate | What makes it hold |
|---|---|
| `[AUDIT-UNPARSEABLE]`, claim.type vocabulary | every reply goes through `schemas.line_problems` before it is saved; the request schema enumerates `ClaimType` |
| `[DELIVERY-UNKNOWN]` | the request's `delivery` enum is `config.TTS_DELIVERY` |
| `[PAYLOAD-MIX]` (invalid label part) | `payload` enum is `craft_gates.PAYLOAD_KINDS` |
| `[WINDOW-OVERLAP]` | windows are contiguous splits of disjoint beat ranges, only ever trimmed |
| `[DUPLICATE-ID]` | ids are assigned by code (`act*1000 + n`) |
| `[EMPTY-LINE]`, `[SILENCE-UNIT]` minimum | holds are code lines carrying `narration_silence_seconds` in `HOLD_SEC` (>= `BAR_SILENCE_MIN`) |
| `[PACING-CONTOUR]` (top-20 share, one-line runs, anchor dwell) | the plan is validated with `pacing_report` (existing); one slot per planned line makes the act follow it |
| `[LOOP-CADENCE]` | a slot opens a loop at least every `BAR_LOOP_GAP - 2` lines; `check_slots` requires `payload: loop` there |
| `[PEAK-ORDER]` (structure) | an anchor's slots run action -> quote -> ... -> ONE reaction; a multi-beat anchor reacts once, at its last beat |
| `[PERSONA]` anchor ends on a reaction / 2-minute window | reaction slot last on every dwelt-on beat; the gate's window walk is replayed in `derive_slots` |
| `[RHYTHM]` SD, long-sentence share, punch share | length bands (short / medium / long) with an alternating aim, plus `punch` and `sweep` shapes for long slots |
| `[BINDING-VIOLATION]` / capacity | a slot's `max_words` is `preflight.budget_words` of its own window |
| `[WINDOW-SPAN]` | a window is cut to `WINDOW_SPAN_RATIO` x the band's narration, never below `MIN_WINDOW` |
| `[REVEAL-TIMING]` (window part) | no window straddles a reveal's landing |
| `[UNWATCHABLE-FOOTAGE]` | `write_plan.fix_unwatchable` moves the window in code (needs `source.mp4`) |
| `[TITLE-MATCH]`, `[HOOK]` | the title and the hook come from the validated plan (existing) |
| `[PACING-CONTOUR]` on the plan itself | `write_plan.repair_contour` fixes the counts in code before the plan is validated (Furious 7: two plans each missed one number) |
| `[INTRO-OUTRO]`, `[FILM-INTRO]` | act 1 has two INTRO slots (greeting, facts) with `film_facts.json` in the brief and its required elements / bans checked by `check_slots`; the last narrated slot is the OUTRO (thesis then CTA, checked); code sets `delivery` |
| `[SILENCE-UNIT]` hold after the outro | nothing is held after the OUTRO slot (the film ends on credits) |
| `[PERSONA]` judgment share | reaction slots planned at `PERSONA_JUDGMENT_SHARE_MIN + REACTION_SHARE_MARGIN`; a reaction must pass `classify_judgment` (checked) and code sets its `payload` |
| `[PEAK-ORDER]` / `[ANCHOR-CLEAN]` (wording) | `check_slots` runs `classify_judgment` on every non-reaction anchor slot |
| `[VOICE-PRESENCE]` floor and ceiling | reactions are split VOICE (one marker) / EVAL (none) by `_voice_budget` to land mid-band; action / bridge slots may carry no marker (checked) |
| `[TRANSITION]` | the first story slot opens on a time or place (checked), never a reaction |
| plan follow-through (beat line counts) | one line per slot; `check_plan_counts` still runs after the acts and feeds a mismatch back |

## 2. Still checks (the words decide)

The slot gives the shape. Whether the words meet these bars is still up to the
writer, so the gates stay as they are:

- `[PERSONA]` frame-only share, jargon, judgment share and label agreement;
  `[PERSONA-RUN]`, `[PERSONA-CEILING]`, `[NARRATOR-VOICE]`.
- `[PEAK-ORDER]` and `[ANCHOR-CLEAN]` as text: they classify the wording
  (`classify_judgment`), not the payload label. An ACTION slot written as
  commentary still fails.
- `[PAYLOAD-MIX]` rest share and rest runs (the writer picks `payload` outside
  loop and reaction slots).
- Binding audit (claims vs footage), `[VISUAL-CAPACITY]`, `[SPEECH-BLIND]`,
  the REVEAL-TIMING spoiler terms, `[CALLBACK-CITE]`.
- `RUNTIME-BAND` / `[DENSITY]`: the act's word budget and the bands are given,
  but the total is what the writer actually writes.
- `[FILM-SPEAKS]` (film_speaks slots are only
  reserved; the selection stage still fills them), motif gates, SAME-POINT,
  and the review artifacts (COLD-READ / REVIEWER / ENDING-READ).

## 3. Decorative - candidates to retire (not deleted in this pass)

- `[RHYTHM]` consecutive-"Then" lint (`craft_gates.py`). Its own note says it
  scored 0 on both reference drafts and has never discriminated anything.
- `[RHYTHM]` place/time opener share (warning). Its own message says it flips
  on how the regex is written, the human reference scores worse under a
  broader pattern, and rewording satisfies it. A slot-based writer never
  chooses openers for a reason this gate can see.

## Not done in this pass

- `write_api resolve` still gathers only review findings and SAME-POINT pairs.
  The draft-gate findings (PACING-CONTOUR, PERSONA, RHYTHM, LOOP-CADENCE...)
  are not routed to resolve yet, and resolve does not yet re-run the gates
  with a word-budget guard (item 3 of the brief).
- Slot bands are calibrated by arithmetic (`GATES-BY-CONSTRUCTION` fills the
  slots and the gates stay silent). They have not been measured on a real
  API-written film yet.
