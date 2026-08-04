"""
Two-pass frame sampling so the script can be written to match the real footage.

Pass 1 (overview):  one frame every N seconds, tiled into labelled montage
                    images. Lets the scripter SEE the whole film cheaply and
                    learn where each beat happens.

Pass 2 (zoom):      a dense burst of frames around a single timestamp, so the
                    scripter can pick the EXACT frame that matches a line.

Frames carry a burned-in timestamp so the scripter can read off clip_start /
clip_end values directly.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rich.console import Console

import config

console = Console()


def _probe_duration(source: Path) -> float:
    fp = config.ffprobe()
    out = subprocess.run(
        [fp, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def _run(cmd: list[str], desc: str):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        console.print(f"[red]ffmpeg failed: {desc}[/]")
        console.print(proc.stderr[-1500:])
        sys.exit(1)


def overview(project: str, every: float = 5.0,
             cols: int = 6, rows: int = 6, thumb_w: int = 320) -> Path:
    """
    Extract 1 frame every `every` seconds with a burned-in timestamp, then tile
    into montage pages of cols x rows. Returns the frames/overview directory.
    """
    pdir = config.project_dir(project)
    source = pdir / "source.mp4"
    if not source.exists():
        console.print(f"[red]No source.mp4 in project '{project}'.[/]")
        sys.exit(1)

    out_dir = pdir / "frames" / "overview"
    out_dir.mkdir(parents=True, exist_ok=True)
    # clear stale frames
    for f in out_dir.glob("*.jpg"):
        f.unlink()

    ff = config.ffmpeg()
    dur = _probe_duration(source)
    fps = 1.0 / every
    thumb_h = int(thumb_w * 9 / 16)
    per_page = cols * rows

    # drawtext showing the source timestamp (pts in seconds * `every` adjusts
    # because we sampled at fps). We compute timestamp from frame number n.
    # n-th sampled frame corresponds to source time n*every.
    # Use a monospace label top-left with black box.
    drawtext = (
        f"drawtext=fontfile='C\\:/Windows/Fonts/consola.ttf':"
        f"text='%{{eif\\:n*{every}/3600\\:d\\:2}}\\:"
        f"%{{eif\\:mod(n*{every}/60\\,60)\\:d\\:2}}\\:"
        f"%{{eif\\:mod(n*{every}\\,60)\\:d\\:2}}':"
        f"x=4:y=4:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=4"
    )
    vf = (
        f"fps={fps},scale={thumb_w}:{thumb_h}:force_original_aspect_ratio=decrease,"
        f"pad={thumb_w}:{thumb_h}:(ow-iw)/2:(oh-ih)/2:black,{drawtext},"
        f"tile={cols}x{rows}"
    )

    console.print(
        f"[cyan]Overview frames[/]: 1 every {every}s "
        f"(~{int(dur/every)} frames -> {cols}x{rows} pages)"
    )
    _run([
        ff, "-y", "-i", str(source),
        "-vf", vf,
        "-q:v", "3",
        str(out_dir / "page_%03d.jpg"),
    ], "overview montage")

    pages = sorted(out_dir.glob("page_*.jpg"))
    console.print(f"[green]Wrote {len(pages)} montage pages[/] to {out_dir}")
    console.print(f"  each page holds {per_page} frames = {per_page*every:.0f}s of film")
    return out_dir


def analyze(project: str, every: float = 5.0) -> Path:
    """
    Step 1 of every film: generate overview montages (if missing) and write an
    analysis worksheet. The scripter (you or the LLM) scans the montages, tags
    each ~`every`s sample as action vs dialogue, and the recap's target action
    ratio is derived from the film's actual action density:

        recap_action_ratio  ~=  film_action_density   (capped by pool + reuse)

    Dialogue-heavy films -> low action ratio (voice carries it).
    Action films         -> high action ratio.
    """
    pdir = config.project_dir(project)
    odir = pdir / "frames" / "overview"
    if not (odir.exists() and any(odir.glob("page_*.jpg"))):
        overview(project, every)
    pages = sorted(odir.glob("page_*.jpg"))

    note = pdir / "analysis.md"
    note.write_text(
        f"# Footage analysis\n\n"
        f"Overview pages: {len(pages)} (1 frame every {every:.0f}s)\n\n"
        f"## How to use\n"
        f"1. Scan the montages in frames/overview/.\n"
        f"2. Estimate the share of ACTION footage (shark/water/attack/dive/\n"
        f"   explosion) vs DIALOGUE/character (people, rooms, faces).\n"
        f"3. Set the recap's target action ratio to match that density, then cap\n"
        f"   it by what the B-roll pool can supply under reuse limits\n"
        f"   (MAX_REUSE={config.MAX_REUSE}, hero={config.MAX_REUSE_HERO}).\n"
        f"4. Talky film -> stay mostly on faces; action film -> lean action.\n\n"
        f"## Estimate (fill in)\n"
        f"- film action density: ____ %\n"
        f"- recommended recap action ratio: ____ %\n",
        encoding="utf-8")
    console.print(f"[green]Analysis worksheet:[/] {note}")
    console.print(f"  Scan {len(pages)} montage pages in {odir}")
    console.print("  Then set the recap's action ratio to match the film's density.")
    return note


def zoom(project: str, at: str, span: float = 6.0, every: float = 0.75,
         cols: int = 4) -> Path:
    """
    Dense burst of frames centred on timestamp `at` (HH:MM:SS[.ms]).
    Covers [at-span/2, at+span/2]. Burned-in absolute timestamps.
    Returns the zoom subdir.
    """
    from pipeline.draft import parse_ts

    pdir = config.project_dir(project)
    source = pdir / "source.mp4"
    if not source.exists():
        console.print(f"[red]No source.mp4 in project '{project}'.[/]")
        sys.exit(1)

    center = parse_ts(at)
    start = max(0.0, center - span / 2)
    rows = max(1, int((span / every + cols - 1) // cols))

    safe = at.replace(":", "-").replace(".", "_")
    out_dir = pdir / "frames" / "zoom" / safe
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("*.jpg"):
        f.unlink()

    ff = config.ffmpeg()
    fps = 1.0 / every
    thumb_w, thumb_h = 400, 225
    # absolute timestamp = start + n*every
    drawtext = (
        f"drawtext=fontfile='C\\:/Windows/Fonts/consola.ttf':"
        f"text='%{{eif\\:({start}+n*{every})/3600\\:d\\:2}}\\:"
        f"%{{eif\\:mod(({start}+n*{every})/60\\,60)\\:d\\:2}}\\:"
        f"%{{eif\\:mod(({start}+n*{every})\\,60)\\:d\\:2}}':"
        f"x=4:y=4:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=4"
    )
    # Scale to fit inside the thumb box (decrease keeps aspect), then pad up to
    # the exact thumb box. force_divisible_by=2 + the increase guard on pad keep
    # this valid for sources at or below the thumb size (e.g. a 720p source),
    # which the plain pad rejected with "Padded dimensions cannot be smaller
    # than input dimensions".
    vf = (
        f"fps={fps},scale={thumb_w}:{thumb_h}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
        f"pad={thumb_w}:{thumb_h}:-1:-1:black:eval=frame,{drawtext},"
        f"tile={cols}x{rows}"
    )

    console.print(f"[cyan]Zoom frames[/] around {at} (+/-{span/2:.1f}s, 1 every {every}s)")
    _run([
        ff, "-y", "-ss", f"{start:.3f}", "-t", f"{span:.3f}", "-i", str(source),
        "-vf", vf, "-q:v", "2",
        str(out_dir / "zoom_%03d.jpg"),
    ], "zoom montage")

    console.print(f"[green]Zoom montage[/] -> {out_dir}")
    return out_dir
