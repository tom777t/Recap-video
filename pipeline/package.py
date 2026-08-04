"""
Packaging: thumbnail image + clickable title options.

Thumbnail: grab a strong frame from the source, darken + boost contrast/saturation
so text pops, then burn a big bold outlined headline. 1280x720.

Titles: write a handful of clickbait-but-honest options to titles.txt for you to
choose from.

No extra Python deps - all done with ffmpeg.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rich.console import Console

import config

console = Console()

FONT = "C\\:/Windows/Fonts/arialbd.ttf"  # Arial Bold


def _run(cmd: list[str], desc: str):
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        console.print(f"[red]ffmpeg failed: {desc}[/]")
        console.print(proc.stderr[-1500:])
        sys.exit(1)


def _esc(text: str) -> str:
    """Escape text for ffmpeg drawtext."""
    return (text.replace("\\", "\\\\").replace(":", "\\:")
            .replace("'", "\u2019").replace("%", "\\%"))


def make_thumbnail(project: str, at: str, headline: str,
                   sub: str | None = None, out_name: str = "thumbnail.jpg") -> Path:
    """
    Grab frame at `at` (HH:MM:SS), style it, and draw `headline` (and optional
    `sub`). headline is auto-wrapped onto up to 2 lines.
    """
    from pipeline.draft import parse_ts

    pdir = config.project_dir(project)
    source = pdir / "source.mp4"
    if not source.exists():
        console.print(f"[red]No source.mp4 in '{project}'.[/]")
        sys.exit(1)

    t = parse_ts(at)
    out = pdir / out_name
    ff = config.ffmpeg()

    # wrap headline to ~16 chars/line, max 2 lines
    words = headline.upper().split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= 16:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lines = lines[:2]

    # build drawtext filters: big yellow headline with thick black outline,
    # bottom-left, stacked lines.
    draw = []
    base_y = 720 - 60 - (len(lines) - 1) * 110 - (140 if sub else 0)
    for i, ln in enumerate(lines):
        draw.append(
            f"drawtext=fontfile='{FONT}':text='{_esc(ln)}':"
            f"x=50:y={base_y + i*110}:fontsize=96:fontcolor=yellow:"
            f"borderw=8:bordercolor=black:shadowcolor=black@0.8:shadowx=4:shadowy=4"
        )
    if sub:
        draw.append(
            f"drawtext=fontfile='{FONT}':text='{_esc(sub.upper())}':"
            f"x=50:y={720-110}:fontsize=52:fontcolor=white:"
            f"borderw=6:bordercolor=black:shadowcolor=black@0.8:shadowx=3:shadowy=3"
        )

    vf = (
        "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
        "eq=contrast=1.18:saturation=1.35:brightness=-0.04,"
        "vignette=PI/5,"
        + ",".join(draw)
    )

    _run([
        ff, "-y", "-ss", f"{t:.3f}", "-i", str(source),
        "-vframes", "1", "-vf", vf, "-q:v", "2", str(out),
    ], "thumbnail")

    console.print(f"[green]Thumbnail:[/] {out}")
    return out


# A small bank of title templates. {t} = topic/title of the recap.
TITLE_TEMPLATES = [
    "They Put a BOMB in the Lake to Kill the Sharks",
    "This Town's Insane Plan to Stop the Sharks Could Kill Everyone",
    "He Dove Into Shark-Infested Water to Plant a Bomb by Hand",
    "5 People Were Eaten - So They Rigged the Whole Lake to Explode",
    "The Sharks Came Back... and This Time the Lake Fights Back",
]


def write_titles(project: str, channel: str = config.CHANNEL_NAME) -> Path:
    pdir = config.project_dir(project)
    out = pdir / "titles.txt"
    lines = [f"# Title options for {channel}", ""]
    lines += [f"{i+1}. {t}" for i, t in enumerate(TITLE_TEMPLATES)]
    out.write_text("\n".join(lines), encoding="utf-8-sig")
    console.print(f"[green]Titles:[/] {out}")
    return out
