# Recap / Review Video Tool

Turn a long video (up to ~2h) into a short, punchy English "recap / retelling"
video — voiceover narration, snappy cuts, burned-in captions.

## Install (one time)

```powershell
# from this folder
python -m pip install -r requirements.txt
```

Python 3.11, ffmpeg, and yt-dlp are auto-detected. ffmpeg is found even if it's
only in the WinGet store (PATH not refreshed). To override, drop `ffmpeg.exe` /
`ffprobe.exe` into `./bin/`.

**For YouTube, install a JS runtime once** (yt-dlp needs it for full 1080p):

```powershell
winget install DenoLand.Deno
```

(Or drop `deno.exe` into `./bin/`.) Without it, YouTube ingest falls back to a
lower-quality format and prints a reminder.

## Workflow

### 1. Ingest (download + transcribe)

```powershell
python recap.py ingest "<URL or C:\path\to\video.mp4>" --project myfilm --model small
```

- `--model`: `tiny` < `base` < `small` (default) < `medium` < `large-v3`
  (slower but more accurate). On a CPU laptop, big models on a 2h video are slow.
- Produces `projects/myfilm/transcript.json` and `transcript_for_script.txt`.
- The temporary `audio16k.wav` is removed automatically once transcription
  finishes (pass `--keep-temp` to keep it).

**Quality — keep it 1080p.** `--max-height` defaults to `1080`; leave it there.
The recap is rendered at 1080p, so the source must be 1080p too. Do **not** drop
to 720 — upscaling a 720p source to 1080p output looks blurry. A long film does
not lower quality; it only makes `source.mp4` bigger (which you delete later).

**Pirate / streaming sites** (motphim.net, netprime.to, ...). yt-dlp tries to
auto-detect the embedded HLS (`.m3u8`) stream. If it fails:

```powershell
# 1) send your logged-in browser session
python recap.py ingest "<url>" --project myfilm --cookies-browser chrome
# 2) and/or set a Referer (defaults to the page's origin)
python recap.py ingest "<url>" --project myfilm --referer "https://motphim.net"
```

Still failing? Open the page, press **F12 > Network**, filter `.m3u8`, copy that
stream URL and pass **it** to `ingest` instead of the page URL.

### 2. CHECKPOINT — write the script (required, semi-auto)

Hand `projects/myfilm/transcript_for_script.txt` to OpenCode and ask it to write
the recap narration into `projects/myfilm/draft.json`, following
`prompts/recap_style.md`. Then validate:

```powershell
python recap.py draft --project myfilm
```

This writes a readable `script.txt`. Edit `draft.json` (narration + clip
timestamps) until you're happy; re-run `draft` to re-check.

### 3. Render

```powershell
# automatic English voiceover (Edge-TTS, free, needs internet)
python recap.py render --project myfilm --voice tts
python recap.py render --project myfilm --voice tts --tts-voice en-US-AvaMultilingualNeural

# OR use your own recordings: put line_001.wav, line_002.wav, ... in
# projects/myfilm/narration/  (see script.txt for each line's text)
python recap.py render --project myfilm --voice mine
```

Output: `projects/myfilm/final.mp4`. The intermediate `_work/` clips are removed
automatically once `final.mp4` is done (pass `--keep-temp` to keep them).

List good voices: `python recap.py voices`

## Disk space

A 2-3h `source.mp4` is large (a few GB). Temp junk is cleared for you; the big
source file is only deleted when you ask, and you are **always prompted first**.

```powershell
python recap.py clean --project myfilm            # temp only (audio wav, _work/)
python recap.py clean --project myfilm --source   # + source.mp4  (asks separately!)
python recap.py clean --project myfilm --all      # keep only final.mp4 + transcript/
                                                  # draft/script/thumbnail/titles/narration
python recap.py clean --all-projects --source     # sweep every project
```

- Every `clean` lists exactly what it will delete and the total size, then waits
  for `y/N`. `--yes` skips the prompt for temp, but `source.mp4` is always shown
  loudly.
- **`source.mp4` is never auto-deleted.** Delete it only after you've approved
  the final video — you'd have to re-download to re-render or re-make a thumbnail.

## Tuning

- **Narration style:** `prompts/recap_style.md` (the most important file).
- **Captions / video look:** `config.py` (`CAPTION_*`, `OUTPUT_*`).
- **Target length:** set `target_minutes` in `draft.json`.
