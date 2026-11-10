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
| `[BRIDGE]` | the slot after a skipped run is marked AFTER A SKIP and carries the skipped beats' own descriptions and the film time they span (`skip_note`, also in the reviser's `slot_tag`); the writer opens on what changed - a place, the skipped event in a clause, "Meanwhile", or a time phrase the beats support - and `crosses_skip` (the gate's own test) checks it. Until SLOTS_VERSION 9 code handed out a clock phrase by count; 7 of Furious 7's 27 were false |
| quotes are dialogue | the quote picker, the film-speaks candidates and the act payload read the transcript through `pipeline/sung.py`: a music mark, a chorus that comes back, or a text in `not_dialogue.json` (`fix_line --not-dialogue`) is never a quote (Furious 7 quoted the ending song as Dom) |
| plan follow-through (beat line counts) | one line per slot; `check_plan_counts` still runs after the acts and feeds a mismatch back |

`[NAME-SPELLING]` (hard, `pipeline/name_spelling.py`) is the one new
check-after: a capitalised word an accent or one/two letters away from a
names.json / film_facts.json name ("Mosé Jaconde" for Mose Jakande). It is
by line, so resolve rewrites it. On every draft in projects/ it is silent.

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

## Resolve keeps the construction

The first real resolve pass (Furious 7) closed all 122 review findings and
broke the layout doing it: it echoed `payload` back on 68 rewrites (rest
share 25% -> 39%, judgment 15.6% -> 9.8%), set three lines to `<outro>`, and
turned an anchor's action line into commentary. Now:

- every rewrite of a slot-written line goes through `write_slots.code_labels`
  (labels are code's) and `write_slots.new_deviations` (a rewrite that adds a
  deviation from its slot is NOT saved and goes back next round);
- `payload` / `delivery` edits are ignored unless a finding about labels
  names the line;
- the reviser sees each line's slot (`[REACTION EVAL]`, `[ACTION on an
  ANCHOR]`, ...);
- once the readers' findings are closed, the draft gates' own hard errors
  that name lines come back as the next resolve round (`gate_findings`).
- `film_facts.json` withheld entries must carry `ban`, or the facts reply is
  sent back once.
- the draft stage's gate-feedback round is applied SLOT BY SLOT
  (`write_slots.merge_revision`): a slot the reply leaves out keeps its line.
  Furious 7 lost ~60 beats of act 2 when a whole-act rewrite, sent back for
  two draft-wide findings, replaced the act. SAME-POINT is a reviewer's call
  and is no longer sent to the writer.
- quotes are whole sentences (`whole_sentences`) - a Whisper segment cut
  mid-sentence is never a quote slot.
- the reviser's slot tag carries the word band and the verbatim quote.
- gate findings ride in EVERY resolve round, beside the readers' (run 6:
  two reader findings that could not close kept three gate errors from
  ever being sent).
- `[TIC-REPETITION]`: each EVAL reaction is handed its own form in rotation
  (`EVAL_FORMS`) - four parallel acts all reached for "that's the price";
  `check_slots` runs the gate's own n-gram count inside each act.
- `[PEAK-ORDER]` on the last anchor: the outro is that beat's reaction, so
  no other reaction slot sits on the outro's beat.
- `[ACTION-STAKE]`: `check_slots` sends back 4 action/tense lines with no
  stake.

## Not done in this pass

- A draft-wide gate error that names no line (a share across the whole
  draft) is not routed to resolve - it is the layout's to prevent.
- Slot bands are calibrated by arithmetic (`GATES-BY-CONSTRUCTION` fills the
  slots and the gates stay silent). Measured on one real film (Furious 7):
  the first write left only the review stage open.
