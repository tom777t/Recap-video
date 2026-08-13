# POST-SHIP METRICS — IT (2017) (it2017)

First ENSEMBLE film run under the A-W standard + Story Unit Planning (6B) +
COVERAGE > DURATION rule.

| Metric | Value |
|---|---|
| Final runtime | 10:56 (656s) — re-rendered 6/13 after Phase 1 tagging + coverage fixes |
| Phase 1 audit | skeleton.json (20 units) + tagged 62 lines; binding 0 mismatches, continuity 0 (intentional jumps marked), coverage 2 soft (~7w under) |
| Runtime progression | 6:12 -> 7:57 -> 9:16 -> 10:51 (coverage-depth expansions) |
| Lines / words | 62 lines / 2197 words |
| Predicted narration | ~12.9 min (holds + xfade shorten to 10:51) |
| Coverage model | LIGHT/STANDARD/DEEP per unit; only DEEP units deepened, STANDARD kept lean |
| Measured loudness | -15.2 LUFS / -1.4 dBTP |
| Music | Murad - Run nhac nen (user track), DOWNLOADED ONLY TO 3:28, looped in-render |
| Story units planned | 27 (skeleton.txt); ~16 High/Med-High |
| Confusion moments in QA | 0 |
| Visual-repetition fixes | spread exposition lines off clustered windows (twice) |
| Read-aloud fixes | 11 long sentences split |
| Final self-grade | 8.5 / 10 |

## What this run proved / corrected
- IT is the ENSEMBLE stress test. First draft (6:12) and second (7:57) were too
  SHORT because the 7 Losers + 6 fear sequences were SUMMARIZED, not dramatized.
- Per the new COVERAGE > DURATION + ensemble rules, I stopped optimizing toward a
  runtime number, rebuilt the story-unit plan (each Loser = own intro + own fear +
  own payoff), and expanded to 55 lines. Coverage now fits the source. Runtime
  (9:16) EMERGED from the units, not a target.
- Music loop verified: downloaded the track trimmed to 3:28 (after that it's ad
  music); the renderer's -stream_loop -1 loops it to cover the 9:16 video. Worked.

## Recurring failure modes to watch
- TTS narration regen requires clearing narration/ + _clipcache/ after any rate or
  text change (cache keys on text, not delivery).
- Predicted length over-estimates the rendered timeline by ~1.5-2 min on long
  recaps (xfade overlap + holds). Budget extra units for ensembles, not extra words.
- Ensemble intros/fears must NOT be merged into shared lines (the over-compression
  warning); give each named co-lead their own beat.

## Self-grade rationale (8.5)
Strong: full ensemble coverage, zero perceived repetition across 55 lines, clean
hook, twist protected, real names only, full audit trail (skeleton/qa/metrics),
runtime emerged from units. Held back by: TTS voice ceiling; the dark Neibolt/lair
footage is dim (source-limited); could push to ~11 min by dramatizing 2-3 more
mid-film fears on a revisit.
