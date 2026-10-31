# Recap Video Tool

Turns a feature-length film into a short English recap video — voiceover
narration, cuts bound to real footage, optional burned-in captions.

**This is not a one-command tool.** The machine does ingest, transcription, TTS
and rendering; a human writes and approves the narration in between. That split
is deliberate — see [Three human checkpoints](#three-human-checkpoints).

---

## Install (once)

```powershell
python -m pip install -r requirements.txt
```

Python 3.11+, ffmpeg and yt-dlp are auto-detected (ffmpeg is found even when only
the WinGet copy exists and PATH has not refreshed). To override, drop
`ffmpeg.exe` / `ffprobe.exe` into `./bin/`.

For YouTube sources, install a JS runtime once so yt-dlp can reach 1080p:

```powershell
winget install DenoLand.Deno
```

**Keep the source at 1080p.** The recap renders at 1080p, so a 720p source gets
upscaled and looks soft. A longer film does not lower quality — it only makes
`source.mp4` bigger, and that file is deleted at the end anyway.

---

## The pipeline

Nine stages. `SHIP_CHECKLIST.md` is the authoritative version with the full
per-stage criteria; this is the map.

| # | Stage | Command | Produces | Who |
|---|---|---|---|---|
| 1 | Ingest | `recap.py ingest` | `source.mp4`, `transcript.json` | machine |
| — | Pre-catalogue | *(read Wikipedia)* | character names, plot shape | human |
| 2 | Frames | `recap.py frames` | sampled stills | machine |
| 3 | Analyze | `recap.py analyze` | `shots.json` | human / LLM |
| 4 | B-roll | `recap.py broll` | `broll.json` | human / LLM |
| 5 | Names | *(hand-written)* | `names.json` | human |
| 6 | Skeleton | `recap.py skeleton` | `beats_proposal.md`, `skeleton.json` | human / LLM |
| 7 | Script | `recap.py draft` | `draft.json`, `script.txt` | human / LLM |
| 7A | Validate | `recap.py draft` | gate report | machine |
| 8 | Render + QA | `recap.py render` | `final.mp4`, `timeline.json` | machine, then **watch it** |
| 9 | Package | `recap.py package` | thumbnail, title options | machine |

### 1. Ingest

```powershell
python recap.py ingest "<URL or C:\path\to\video.mp4>" --project myfilm --model small
```

`--model`: `tiny` < `base` < `small` (default) < `medium` < `large-v3`. On a CPU
laptop a large model on a 2h film is slow. The temporary `audio16k.wav` is
removed once transcription finishes (`--keep-temp` keeps it).

### Pre-catalogue (RULES A7)

Before cataloguing, read the film's Wikipedia **Plot** and **Cast** sections.
Only those two. Not reviews, not ratings, not critical analysis — those muddy the
channel's own voice.

This exists because Whisper mangles proper nouns, and because tagging a scene
correctly requires knowing who is in it. Wikipedia is a *map*, not ground truth:
**when the summary and the frames disagree, the frames win.**

It has a cost — reading the plot means knowing the ending. RULES A8 (spoiler
discipline) carries that weight: split the summary into a SETUP zone and a REVEAL
zone as you read, and never let the reveal zone leak before its beat lands.

### 2–6. Catalogue, B-roll, names, skeleton

```powershell
python recap.py frames   --project myfilm
python recap.py analyze  --project myfilm
python recap.py broll    --project myfilm
python recap.py skeleton --project myfilm
```

`shots.json` is the catalogue: one entry per visual moment, frame-verified,
tagged with `depicts` and `chars`. **Catalogue density decides everything
downstream** — a beat with no shot catalogued cannot be told, and a thin
catalogue pushes the enrichment pass into inventing clip windows. The
`[CATALOGUE-DENSITY]` gate reports beats with no footage; fix those *before*
writing lines.

`names.json` accepts two forms. Prefer the second — it keeps the actor mapping
that Pre-catalogue already read:

```json
{"names": [{"character": "Teddy Daniels", "actor": "Leonardo DiCaprio"}]}
```

### 7. Script — the checkpoint that cannot be automated

The narration is written by a human or an LLM into `draft.json`, following
`prompts/style_linear_vn.md` (linear style) or `prompts/recap_style.md`.
**`docs/RULES.md` overrides both** where they conflict.

Then validate — and validate again after every edit:

```powershell
python recap.py draft --project myfilm
python recap.py draft --project myfilm --promote   # OUTLINE -> SCRIPT
```

The draft moves through two stages. **OUTLINE** is written once across the whole
film and is *meant* to be thin — it establishes coverage and binding. **SCRIPT**
is the act-by-act enrichment pass. Length and density gates only apply at SCRIPT
stage, because a thin outline is not a fault.

Gates that run here:

| Gate | Checks |
|---|---|
| `[BEAT-COVERAGE]` | every beat has at least one bound line, no two consecutive gaps |
| `[BEAT-MAP]` | beat timestamps parse, increase, and fall inside the film |
| `[REVEAL-TIMING]` | no reveal term appears before its beat lands |
| `[BINDING-INTEGRITY]` | every line lands on a catalogued shot |
| `[CATALOGUE-DENSITY]` | beats with no footage catalogued |
| `[ACTION-SETUP]` | action beats are set up before they land |
| `[SET-PIECE]` | no long unnarrated gap inside a set piece |
| `[DUPLICATE-ID]` | line ids are unique — **hard failure** |
| `[CAPACITY-WORDS]` | narration fits the shot it is bound to |
| `[VISUAL-MEMORY]` | separate lines are not pulling the same-looking footage |
| `[PERSONA-CEILING]` | judgment share is not **above** 35% — the narrator talking over the film |
| `[PERSONA-RUN]` | no more than 2 judgment lines back to back; a hold breaks the run |
| `[PEAK-ORDER]` | a peak's first line is the moment, not the opinion of it, and only one line reacts |
| `[ANCHOR-CLEAN]` | every anchor keeps at least one line that is purely the moment |
| `[CLAIM-SUPPORT]` | a claim about repeated or film-long behaviour cites a beat that exists |
| `[NAME-AT-REVEAL]` | once a reveal lands, the character is named — the spoiler hold applies *before* it |
| `[RUNTIME-BAND]` | predicted finished runtime inside 14–19 min — **hard failure above it**, blocks the render |

A red gate means the numbers below it cannot be trusted. `[FOOTAGE-DROPPED]`
specifically means some of the catalogue failed to load and **the audits below
it are degraded** — a clean report under that line means nothing.

This table's `| Gate | Checks |` format carries no column for *which fixture
proves the gate fires*, so that evidence lives in
`docs/WRITING_CRAFT_CRITERION.md` ("Which fixture proves each of the eight
gates above") and in the per-case docstrings of `tools/test_pacing.py`,
`tools/test_continuity_new.py` and `tools/test_runtime_band.py`.

### 8. Render

```powershell
python recap.py render --project myfilm --voice tts
python recap.py render --project myfilm --voice mine   # your own line_001.wav, ...
```

Run this in PowerShell directly. Do **not** hand it to an agent to run — the mux
step is long, agents time out mid-write, and the result is a corrupt file that
fails with `moov atom not found`.

Output: `final.mp4`, plus `timeline.json` mapping every line id to where it lands
in the finished video — use it during QA so a note can say "line 36" instead of
"somewhere around minute 7". `[RENDER-CHECK]` confirms the render matches the
draft; the draft-stage gates cannot see this far.

Captions are **off** by default (`DEFAULT_CAPTIONS` in `config.py`).

List voices: `python recap.py voices`

### 9. Package

```powershell
python recap.py package --project myfilm
```

---

## Three human checkpoints

These are not missing automation. They are the architecture — machine drafts,
human watches, machine fixes.

1. **Approve the draft** — spoilers and hindsight that a text audit is blind to.
2. **Watch the render** — drift, mismatch, unfollowable action, compressed
   scenes. Four films running, this has caught something every single time that
   every gate passed clean.
3. **Censor review** — which scenes need blurring. Subjective; no data yet.

---

## Disk space

A 2–3h `source.mp4` is several GB. Temp files are cleared automatically; the
source is only deleted when you ask, and you are always prompted.

```powershell
python recap.py clean --project myfilm            # temp only
python recap.py clean --project myfilm --source   # + source.mp4 (asks separately)
python recap.py clean --project myfilm --all      # keep only the deliverables
python recap.py clean --all-projects --source     # sweep every project
```

`source.mp4` is never auto-deleted — delete it only after you have approved the
final video, or you will have to re-download to re-render.

---

## Where things are

| File | What |
|---|---|
| `docs/RULES.md` | the editorial rules. **Read first; overrides the prompts** |
| `docs/GATE_CANDIDATES.md` | proposed gates and known engine bugs. Not yet in force |
| `docs/lessons.md` | engineering diary — why each rule exists |
| `SHIP_CHECKLIST.md` | the full per-stage quality bar |
| `docs/TAGGING_GUIDE.md` | when to use each `depicts` value |
| `prompts/style_linear_vn.md` | narration style, linear mode |
| `config.py` | tiers, TTS delivery, caption and video settings |
