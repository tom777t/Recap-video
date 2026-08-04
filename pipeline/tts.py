"""
Produce per-line narration audio.

--voice tts  : Edge-TTS neural voice (free, needs internet) -> narration/line_XXX.mp3
--voice mine : you record your own audio; we just locate your files.

Returns an ordered list of (line_id, audio_path, duration_seconds).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from rich.console import Console

import config

console = Console()


def _audio_duration(path: Path) -> float:
    fp = config.ffprobe()
    out = subprocess.run(
        [fp, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


# --------------------------------------------------------------------------- #
# Edge-TTS with per-line delivery (rate / pitch / volume)
# --------------------------------------------------------------------------- #
async def _edge_one(text: str, out: Path, voice: str,
                    rate: str, pitch: str, volume: str,
                    attempts: int = 4):
    """Synthesize one line, retrying transient Edge-TTS drops.

    The public Edge-TTS endpoint intermittently returns "No audio was
    received" for a valid request. A single drop must NOT abort a long
    render, so retry with backoff and verify a non-empty file was written.
    """
    import asyncio as _asyncio
    import edge_tts
    last_err = None
    for i in range(attempts):
        try:
            communicate = edge_tts.Communicate(
                text, voice=voice, rate=rate, pitch=pitch, volume=volume)
            await communicate.save(str(out))
            if out.exists() and out.stat().st_size > 0:
                return
            last_err = RuntimeError("empty audio file written")
        except Exception as e:  # noqa: BLE001 - transient network/service errors
            last_err = e
        # clean any zero-byte partial before retrying
        try:
            if out.exists() and out.stat().st_size == 0:
                out.unlink()
        except OSError:
            pass
        if i < attempts - 1:
            await _asyncio.sleep(2.0 * (i + 1))  # 2s, 4s, 6s backoff
    raise last_err if last_err else RuntimeError("TTS failed")


def _delivery_for(ln: dict, base_rate: str) -> dict:
    """
    Resolve the per-line delivery. Priority:
      explicit rate/pitch/volume on the line  >  named 'delivery' preset  >
      default preset (with base_rate substituted for the global default).
    """
    preset_name = ln.get("delivery", config.DEFAULT_DELIVERY)
    preset = dict(config.TTS_DELIVERY.get(preset_name, config.TTS_DELIVERY["normal"]))
    # if the line uses the plain default preset, honour the CLI/base rate
    if preset_name == "normal":
        preset["rate"] = base_rate
    # explicit per-line overrides win
    for k in ("rate", "pitch", "volume"):
        if k in ln:
            preset[k] = ln[k]
    return preset


def generate_tts(project: str, draft: dict,
                 voice: str = config.DEFAULT_TTS_VOICE,
                 rate: str = config.DEFAULT_TTS_RATE) -> list[tuple[int, Path, float]]:
    pdir = config.ensure_project(project)
    ndir = pdir / "narration"
    ndir.mkdir(exist_ok=True)

    try:
        import edge_tts  # noqa: F401
    except ImportError:
        console.print("[red]edge-tts not installed.[/] Run: pip install -r requirements.txt")
        sys.exit(1)

    # cache manifest: line_id -> signature. Regenerate only when text/delivery
    # for that line changes.
    manifest_path = ndir / "_cache.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        manifest = {}

    results: list[tuple[int, Path, float]] = []
    console.print(f"[cyan]Generating voiceover[/] with Edge-TTS '{voice}' (per-line delivery)")

    for ln in draft["lines"]:
        # Gap 3 / S9 silence line: no narration -> no TTS. The render builds a
        # silent held clip for it (matched by clip_start/clip_end, not by_id).
        if ln.get("narration_silence_seconds") is not None or not ln.get("narration", "").strip():
            sec = ln.get("narration_silence_seconds")
            console.print(f"  line {ln['id']:>3}: [dim]silence ({float(sec):.0f}s)[/]"
                          if sec else f"  line {ln['id']:>3}: [dim]skipped (empty)[/]")
            continue

        out = ndir / f"line_{ln['id']:03d}.mp3"
        d = _delivery_for(ln, rate)
        sig_src = json.dumps({
            "text": ln["narration"], "voice": voice,
            "rate": d["rate"], "pitch": d["pitch"], "volume": d["volume"],
        }, sort_keys=True, ensure_ascii=False)
        sig = hashlib.sha1(sig_src.encode("utf-8")).hexdigest()

        stale = (not out.exists()) or manifest.get(str(ln["id"])) != sig
        if stale:
            try:
                asyncio.run(_edge_one(ln["narration"], out, voice,
                                      d["rate"], d["pitch"], d["volume"]))
                manifest[str(ln["id"])] = sig
            except Exception as e:
                console.print(f"[red]TTS failed on line {ln['id']}:[/] {e}")
                console.print("  (Edge-TTS needs internet. Check your connection.)")
                sys.exit(1)

        dur = _audio_duration(out)
        results.append((ln["id"], out, dur))
        tag = ln.get("delivery", "normal")
        flag = "[yellow]new[/]" if stale else "cached"
        console.print(f"  line {ln['id']:>3}: {dur:5.2f}s  ({tag:<7}) {flag}")

    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return results


# --------------------------------------------------------------------------- #
# Your own recordings
# --------------------------------------------------------------------------- #
def collect_mine(project: str, draft: dict) -> list[tuple[int, Path, float]]:
    """
    Expect one audio file per line in narration/, named line_001.* (mp3/wav/m4a).
    Tells you exactly which files are missing.
    """
    pdir = config.ensure_project(project)
    ndir = pdir / "narration"
    ndir.mkdir(exist_ok=True)

    results: list[tuple[int, Path, float]] = []
    missing: list[int] = []
    for ln in draft["lines"]:
        hits = sorted(ndir.glob(f"line_{ln['id']:03d}.*"))
        hits = [h for h in hits if h.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac", ".flac")]
        if not hits:
            missing.append(ln["id"])
            continue
        dur = _audio_duration(hits[0])
        results.append((ln["id"], hits[0], dur))

    if missing:
        console.print("[red]Missing your recordings for these lines:[/]")
        for mid in missing:
            console.print(f"  - drop a file named line_{mid:03d}.wav (or .mp3) in:")
        console.print(f"      {ndir}")
        console.print("\nSee script.txt for the text of each line. Then re-run render.")
        sys.exit(1)

    console.print(f"[green]Found all {len(results)} recordings.[/]")
    return results
