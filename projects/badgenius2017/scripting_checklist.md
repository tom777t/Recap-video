# Scripting pre-flight — Bad Genius (2017) — STAGE 3a OUTLINE

Stage 3a. The draft gate at this stage is coverage / binding / continuity only;
DRAFT-TARGET (C16) does not apply and is not claimed. C1–C11 answered below.

- **C1 (S1 footage-first): YES.** `[BINDING-INTEGRITY] all 146 explicit-window
  line(s) land on a catalogued shot`. No line references an un-catalogued clip.
  3 silence lines (ids 50, 84, 111) are real draft lines with
  `narration_silence_seconds` set and `narration: ""`, per the S9 shape.

- **C2 (S2 chronology): YES.** `continuity 0`. clip_start increases
  monotonically from line 1 to line 146. The hook (L1) carries
  `narrative_jump: true` — the interview room is the film's own first image so
  there is no backward jump in source time, but it is a flash-forward in story
  time, which is what the flag records.

- **C3 (S3 no replay): YES.** Every clip window appears exactly once. No clip is
  used twice, so MAX_REUSE (2) and MAX_FAMILY_USES (2) cannot be breached. No
  pool/family lines in this draft.

- **C4 (S4 audio-must-have-video): YES — via `claim.type: "speech"` (RULES J1).**
  Three lines report what a character says rather than what the frame shows, and
  each is bound to a shot in which that speaker is **visible speaking**:
  L79 + L81 (R1, subject Pat, on 01:10:48 and 01:10:58 — both after the 01:10:40
  landing) and L136 (Bank's statement, subject Bank, on 01:50:38). The audit
  confirms speaker presence and states in its own output that it cannot confirm
  content. Every other line describes what its clip shows.
  The earlier break is gone: R1 no longer sits on the reaction shot, and Bank's
  denial is restored rather than dropped. Both had looked impossible because the
  catalogue was missing the speaking shots, not because the film lacked them.

- **C5 (S5 subject-on-screen): YES.** Every named character appears in the bound
  clip's `chars`. Checked line by line. The R1 line names nobody: it uses "he",
  whose antecedent is L77, which is bound to Pat's own footage. The two unnamed
  administrators, the invigilators and Bank's mother are described by role only.

- **C6 (sub-window): YES.** All windows are explicit clip_start/clip_end on
  single catalogued shots; no pool clips. The five windows over 20s
  (L119 28s, L125 32s, L126 34s, L131 28s, L134 38s) each claim only what holds
  across the whole window — a chase, an escalator ride, a held close-up.

- **C7 (no orphan transition): YES.** Bridge lines (L7 "Then the midterm.",
  L32, L62) are bound to footage of the scene they bridge into.

- **C8 (intro hook unit): YES.** L1–L3, 78 words, `narrative_jump` on L1.
  (a) atmospheric: the mirrored wall; (b) tension: the sealed bag and the wait;
  (c) branding + title on L3; (d) thematic teaser: "what his daughter is worth
  on paper". Bound to 00:01:22–00:02:50, the film's opening. No spoiler content.

- **C9 (outro CTA): YES.** L145–L146, 50 words, bound to 02:03:10–02:03:34
  (she leaves the shop; the confession to camera). Thematic takeaway + like/
  subscribe.

- **C10 (censor): YES.** All 226 shots reviewed; every one `censor: "none"`.
  The assault (00:57:47–00:58:05) is frame-checked silhouette against a backlit
  gate with no injury detail, which S7 lists explicitly under when NOT to
  censor. The landfill close-up (00:58:28) is dried blood in daylight, non-
  graphic. The vomiting (01:38:40) is not an S7 category.

- **C11 (S9 silence): YES.** 3 silence lines, all earned, none back to back,
  none in the first minute after the hook:
  L50 00:45:28 (6s) the corridor after the expulsion;
  L84 01:18:32 (10s) the harbour, the last quiet hour;
  L111 01:35:35 (20s) the piano that is not there — the film's signature image.

- **C16 (DRAFT-TARGET): YES — at the tier the film accepted.** 150 lines, 3233
  words, **16.4 min real-rate**, capacity fill 68%. No `[DRAFT-UNDER-TARGET]`,
  no `[DRAFT-UNDERFILL]` (68% is above the 65% warn line).
  The tier was dropped **video_essay -> fuller_recap** under A11 after honest
  act-by-act enrichment measured 16.3 min and stopped. The remaining unused
  capacity is 51% on `action` (A9: honest, the set-piece stages are all
  narrated and followable) and 62% on `emotion` (I2: held faces and authored
  silence want FEWER words, not more). Reaching the 17.0 video_essay floor
  would have meant adding ~150 words to shots two rules say to leave alone.
  The drop was pre-registered in `beats_proposal.md` before the measurement was
  taken; the full reasoning is recorded there.

## Gate state

    [STAGE] OUTLINE -> outline_ready: 76/80 beats bound, no >=2-consecutive gap,
            0 mismatch / 0 unverified, continuity 0, 0 violations,
            4 lone beat(s) tolerated
    Summary: coverage 0 | binding 0 mismatch / 0 unverified | tags 0 | continuity 0

Uncovered beats B02, B05, B12, B73 have no catalogued footage at all; each is a
lone beat between two covered ones.

## Two audit problems found while running this, NOT fixed

1. **The binding audit verified nothing and the stage gate counted that as a
   pass.** `0 lines carry a claim, so the binding audit checked nothing. This is
   not a pass.` — yet `outline_ready` fires on "0 mismatch / 0 unverified",
   which is satisfied vacuously because no line declares a `claim`. An absent
   input is being read as a clean result. This is D-GREEN.

2. **False-alarm exit.** The first run ended `Audit found real [VOICE-VISUAL]
   mismatches above - re-point those lines' footage before rendering. (exit 1)`
   while the same run printed `Verified mismatches: 0 lines (real issues)`. The
   summary fires on not-clean rather than on mismatches > 0.

## Rules

**No rule is broken in this draft.** The C4/S4 break reported in the previous
session was resolved by RULES Part J (`claim.type: "speech"`) plus two catalogue
additions; it is not worked around, it is gone.

**Still needing the Stage-7 watch:** the three `speech` lines. The gate confirms
Pat and Bank are on screen speaking; nothing confirms WHAT they say. That content
comes from A7 (Wikipedia Plot), and I4 forbids relying on the machine transcript
for it. A human has to hear those three moments.
