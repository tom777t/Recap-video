# tag_prompt_noname.md — identical to tag_prompt.md EXCEPT no cast list

Control arm for the 2026-09-05 experiment on whether `names.json` access causes
the agent to invent names. **The only difference from `tag_prompt.md` is
section 1.** Everything else must stay identical or the comparison is worthless.

The caller gives you: `PROJECT`, `SHOT`, `FRAMES`, `OUTDIR`.

---

## 1. Blindness — non-negotiable

Do **NOT** read ANY file in the project. Not `shots.json`, not
`_vision_truth.json`, not `VISION_EVAL.md`, and **not `names.json`**.

You have **no cast list**. Name a character only if you can identify them from
the frames alone — for example a name badge, a name written on screen, or a
face you recognise from the film itself. Otherwise write `(khong ro)`.

An honest `(khong ro)` is correct. A guessed name is a false positive.

## 2. Read the frames

Use the `Read` tool on each path in `FRAMES`. JPEGs from one continuous shot,
in time order.

## 3. `depicts` — TWO axes, one label from the visible side minimum

| axis | meaning | labels |
|---|---|---|
| **VISIBLE** | what the camera literally shows | `action`, `dialogue`, `establishing`, `montage`, `reaction`, `transition` |
| **STORY** | what the scene does for the plot | `aftermath`, `discovery`, `emotion`, `reveal`, `setup` |

**You MUST include at least one VISIBLE label.** You MAY add STORY labels.

Pick the VISIBLE label for what dominates the frames:
- people talking to each other → `dialogue`
- physical movement driving the moment → `action`
- a place/scale shot orienting the viewer → `establishing`
- a face absorbing something → `reaction`

Do not pad. Two or three labels total is normal.

## 4. `chars`

Named characters **visible in these frames**. Use `(khong ro)` for anyone you
cannot name from the frames alone. Do not list someone only spoken about.

## 5. `action`

**One sentence** describing what is on screen. Frame-caption register.
Per rule I1 in `docs/RULES.md` this is never the source for narration prose.

## 6. Write the result, then return

Write to `<OUTDIR>/<SHOT>.json`, creating the directory if missing:

```json
{"shot": "shot030", "depicts": ["establishing"], "chars": ["(khong ro)"],
 "action": "One sentence."}
```

Final message must be exactly `ok <SHOT>`, nothing else. On failure return
`FAIL <SHOT> <reason>` and write no file.
