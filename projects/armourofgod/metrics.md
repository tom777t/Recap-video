# POST-SHIP METRICS — Chinese Zodiac (armourofgod)

First project run end-to-end under the A-V standard + the new staged process
(6A skeleton -> question-chain script -> [VISUAL-REPEAT] gate -> 7A viewer audit
-> render -> 8 render QA).

| Metric | Value |
|---|---|
| Final runtime | 6:38 (398s) after pacing slow-down (was 6:19) |
| Predicted runtime (validator) | ~7.9 min at new WPM 170 (TTS holds shorten vs estimate) |
| Measured loudness | -15.1 LUFS / -1.5 dBTP (was -14.0; user wanted slightly quieter) |
| Pacing change | normal +24->+16%, tense +34->+26%, line gap 0.05->0.18s |
| Music | Murad - Run (NCN release), user-chosen (2nd pick) |
| Lines / words | 50 lines / 1331 words |
| Action mix | 22% action / 78% dialogue (matches the film) |
| Confusion moments found in QA | 0 |
| Transition fixes applied | 0 at 7A (skeleton 6A pre-fixed structure) |
| Visual-repetition fixes applied | 2 (skydive 3->2, volcano_lava 3->2) caught by [VISUAL-REPEAT] at Stage 7, fixed before render |
| Read-aloud / clarity fixes | 3 (two 30-word sentences split, one vague "one of them") |
| Name flags | resolved by expanding names.json (all real proper nouns; 0 invented) |
| Final self-grade | 8.5 / 10 |

## What the new system caught (proof it works)
- The [VISUAL-REPEAT] gate flagged MY OWN over-use of the skydive and volcano-lava
  families (3x each) at validation — the exact "repeated scene" failure the user
  reported on Punisher. Fixed BEFORE rendering, not after.
- 6A skeleton audit pre-validated the cause->consequence + question chain, so the
  7A first-time viewer audit found 0 confusion moments (structure was sound going
  in). This is the intended order: fix structure first, write second.

## Recurring failure modes to watch (cross-project)
- Predicted length over-estimates vs final by ~0.7-0.9 min (TTS holds). Budget a
  bit more script if a hard 10-min floor is ever required.
- Foreign-language uploads mislabeled "English" need --translate (caught here via
  the audio/transcript check; cost one wasted transcribe pass).
- [VISUAL-MEMORY] proximity hints fire on legitimate distinct-stage clusters
  (conversations, news montages) — they are hints, resolved by judgment, not blocks.

## Self-grade rationale (8.5)
Strong: zero perceived repetition, clean hook, earned action, clear moral spine,
real names only, full audit trail (skeleton.txt + qa.md). Held back from 9+ by:
TTS voice ceiling, and a 6:19 runtime that's tight for a plot this eventful (could
support 2-3 more genuine beats without padding on a revisit).
