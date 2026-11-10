"""
Packaging: thumbnail image + clickable title options.

Thumbnail: grab a strong frame from the source, darken + boost contrast/saturation
so text pops, then burn a big bold outlined headline. 1280x720.

Titles: write a handful of clickbait-but-honest options to titles.txt for you to
choose from.

No extra Python deps - all done with ffmpeg.
"""
from __future__ import annotations

import json
import re
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


# Titles are written PER FILM from the draft's own premise (R0/the
# variation design): the draft's `title` is the premise the plan already
# wrote, and `hook_question` (the open's last line, the question the
# video answers) is reshaped into a second option. There is NO bank: a
# shared bank is exactly the "template content with minimal variation"
# the 2026 inauthentic-content policy names, and TITLE-FORMULA gates
# titles.txt against ever being byte-identical between two videos.
def _title_options(draft: dict) -> list:
    import json
    title = str(draft.get("title") or "").strip()
    if not title:
        return []
    out = [title]
    q = ""
    for ln in draft.get("lines") or []:
        hq = str(ln.get("hook_question") or "").strip()
        if hq:
            q = hq
    if q:
        # "Will X?" -> the question AS a title, then its subject as a
        # consequence title. Both stay honest: the video answers exactly
        # this.
        q0 = q.rstrip("?").strip()
        out.append(q0 if q0.endswith(("...", "!", ".")) else q0 + "?")
        m = re.search(r"^(?:Will|Can|Does|Is|Are|Do|Did)\s+(.+)$", q0,
                      re.I)
        if m:
            out.append("What Happens When " + m.group(1))
    # one stakes restatement from the hook line's own words
    for ln in draft.get("lines") or []:
        if ln.get("delivery") == "hook" or str(
                ln.get("note") or "").upper() == "OPEN":
            n = str(ln.get("narration") or "").strip().rstrip(".")
            if len(n.split()) >= 6:
                out.append(n)
            break
    seen, uniq = set(), []
    for t in out:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(t)
    return uniq


def write_titles(project: str, channel: str = config.CHANNEL_NAME) -> Path:
    pdir = config.project_dir(project)
    out = pdir / "titles.txt"
    dp = pdir / "draft.json"
    draft = {}
    if dp.exists():
        try:
            draft = json.loads(dp.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            draft = {}
    opts = _title_options(draft)
    if not opts:
        console.print("[yellow]Titles:[/] no draft title found - pass "
                      "--title or write draft.json first; no bank to "
                      "fall back on (a shared bank is the formula the "
                      "policy names).")
        return out
    lines = [f"# Title options for {channel}", ""]
    lines += [f"{i+1}. {t}" for i, t in enumerate(opts)]
    out.write_text("\n".join(lines), encoding="utf-8-sig")
    console.print(f"[green]Titles:[/] {out} ({len(opts)} option(s), "
                  f"written from this film's premise)")
    return out
