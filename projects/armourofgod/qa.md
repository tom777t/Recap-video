# QA LOG — Chinese Zodiac (armourofgod)

## Stage 7 — Validator (machine gates)
- `[VISUAL-REPEAT]` fired on first pass: `skydive` 3x (P6, P7, line37) and
  `volcano_lava` 3x (P8 used twice + line39). FIXED:
  - Hook line 2 moved off `volcano_lava` (P8) -> `1860_sacking` (P1).
  - Merged the two skydive-chase lines; re-pointed the extra to `crowd_watching`
    (telescopes on the rim) — a genuinely different visual that adds "world is
    watching" stakes.
  - Result: skydive:2, jungle_fight:2, dragon_head_save:2, volcano_lava:1. Clean.
- `[NAME]` false positives (Chinese/Zodiac/Jackie/Chan/Indestructible/Roses/etc.)
  resolved by adding the verified proper nouns to names.json. No invented names.
- `[CLARITY] line 30` "one of them" -> "JC and his whole crew". Fixed.
- `[READ-ALOUD]` 30-word sentences on the maze + landing lines -> split. Fixed.
- `[FRESHNESS] line 50` outro reuses the 1860 image -> tagged `flashback`. Fixed.

## Stage 7 — VISUAL-MEMORY hints (proximity backstop; judged by viewer memory)
The hint flags clips that sit close in SOURCE time. Applied the test "would a
viewer feel they just saw this?" to each cluster:
- lines 3/5/7/50 (~6 min): intro-at-ruins / bronze-heads-on-screen / boardroom /
  1860 flashback. DISTINCT scenes + different info. NOT a repeat. Keep.
- lines 17/21/22/23 (~33 min): the Katherine castle conversation — her intro,
  her offer, JC's dilemma, the island map. Distinct narrative STAGES that each
  advance new info; viewer follows a conversation, not a repeat. Keep.
- lines 32/33/34 (~59 min): gold reveal / team celebrates / JC goes quiet.
  Distinct beats of one sequence (discovery -> reaction -> turn). Keep.
- lines 45/46/47 (~96 min): news of arrests / mailing relics / relic list.
  Different information in the resolution montage. Keep.
Verdict: no action-family repeats; all hints are distinct stages/scenes.

## Stage 7A — First-Time Viewer Audit (read as if never seen the film)
Per-section who/why/here/objective/changed — findings:
- Spine clear by ~0:45: JC = treasure hunter hired by MP to grab looted zodiac
  heads. Every character named on first appearance (JC, Morgan, Coco, Katherine,
  Simon, David/Bonnie). PASS (A).
- Every action beat has setup BEFORE it (S/U): castle target set (L9) before the
  wingsuit dive (L10); pirates established (L27-28) before the jungle fight
  (L29-30); MP's volcano stunt set (L37-39) before JC's jump (L40). PASS.
- Question-chain holds end to end: hook "why jump?" is only paid off at the
  climax (L40) + theme (L49). Curiosity pull intact. PASS.
- Minor: L35 quotes the early "give it back" line, so its footage (27:00) lands
  at the 64% mark — a small visual-freshness jump, but it's the literal line
  being referenced. Acceptable; not worth a fresher mismatch.
- No "where did this come from?" moments found. No info dumps (David/Bonnie is the
  one texture beat and it earns its place). No unexplained investigations.
Verdict: 7A PASS — cleared for render.

## Stage 8 — Render QA (watched the render / contact sheet)
- Runtime: 6:19 (379s), 1080p, 66 SFX hits, music = Murad "Run" (user-chosen).
- VISUAL REPETITION: contact sheet shows every beat is a DISTINCT scene. No
  perceived repeats anywhere — the knife-cauterization failure mode from Punisher
  does NOT recur. The new [VISUAL-REPEAT] gate caught my own skydive/lava over-use
  at validation and I fixed it before render. PASS (criterion C).
- HOOK: opens on the skydive freefall — lands the shock immediately. PASS (R).
- TRANSITIONS: setup-before-action holds on the sheet — castle target before the
  wingsuit dive; pirates established before the jungle fight; MP's volcano stunt
  before JC's jump. No "where did this come from?" moments. PASS (S/U).
- Jackie Chan (famous face) shown early; question-chain structure visible.
- Confusion moments: none. Weak transitions: none. Emotional discontinuities: none.
- Minor: L35 footage (27:00 dialogue) lands at ~64% — small freshness jump, but
  it's the literal "give it back" line being quoted. Acceptable, not patched.
Verdict: Stage 8 PASS — ship.

## W. Natural Progression Audit (added pass; predict next-beat vs actual)
Walked all beats with "if it stopped here, what would a viewer expect next?":
- One [NATURAL-PROGRESSION-FAIL] found: L35 (JC decides to send the heads home)
  -> L36 jumped to global protests, before showing MP's reaction the viewer
  expects. FIXED: reworded L36 so JC's defiance + the protests together corner
  Morgan, leading naturally into L37 (his retaliation). Now reads
  decision -> MP cornered -> MP lashes out.
- All other beats: expectation met or deliberately bridged. PASS (W).

## Re-render pass (pacing + loudness + music)
- Config changed: normal +24->+16%, tense +34->+26%, line gap 0.05->0.18s,
  WPM 185->170, master -14->-15 LUFS, boom -10->-12dB. Goal: fix "middle too fast"
  + "slightly too loud" feedback.
- Music swapped to Murad - Run (NCN release), user-chosen.
- Predicted narration now ~7.9 min (was ~7.2) reflecting the slower pace.
- RE-RENDER RESULT (verified): runtime 6:38 (was 6:19), measured loudness
  -15.1 LUFS / -1.5 dBTP (was -14.0). Middle pace noticeably calmer; mix slightly
  quieter; new music in place. Required clearing narration + _clipcache so TTS
  regenerated at the new rate (the cache keys on text, not delivery rate).
- NOTE for future rate/loudness changes: must clear projects/NAME/narration and
  _clipcache, or the render reuses old-rate audio ("cached" in the log).

