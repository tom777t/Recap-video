# -*- coding: utf-8 -*-
"""diag_picture_sync.py - does the picture stay with the voice, line by line?

    python tools/diag_picture_sync.py

The frame-count checks prove the new assembly (Phase 1) makes a file of the
right LENGTH. They cannot see whether, at the moment a line's narration
starts, the picture shows that line's footage. This renders one synthetic
film twice - new path and legacy path - where every source frame carries its
own frame number in its colour, then for every line:

  1. finds where the narration actually starts in the finished audio
     (the stand-in narration is a tone; silencedetect gives its onset);
  2. reads the picture 0.3 s later and decodes which SOURCE frame is showing;
  3. compares that with the line's own clip window.

Output: per line, the source second on screen at voice onset for each path,
and whether it is inside the line's window. A difference that grows along the
film is assembly drift.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import config  # noqa: E402
import test_render_smoke as smoke  # noqa: E402

FPS = 30
N_LINES = 14


def _coded_source(pdir: Path, seconds: int = 90) -> None:
    """Every frame's colour encodes its frame number in r, g and b (base 32)."""
    smoke._ff("-f", "lavfi", "-i",
              f"color=c=black:s=640x360:r={FPS}:d={seconds},format=rgb24,"
              f"geq=r='mod(N,32)*8+4':g='mod(floor(N/32),32)*8+4':b='floor(N/1024)*8+4'",
              "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
              "-c:v", "libx264", "-preset", "ultrafast", "-crf", "4",
              "-pix_fmt", "yuv444p", "-c:a", "aac", "-shortest",
              str(pdir / "source.mp4"))


def _draft() -> dict:
    lines = []
    t = 4.0
    for i in range(1, N_LINES + 1):
        a, b = t, t + 5.0
        lines.append({"id": i, "clip_start": f"00:00:{a:04.1f}",
                      "clip_end": f"00:00:{b:04.1f}", "delivery": "normal",
                      "note": f"B{i:02d}",
                      "narration": "The coloured frame tells us exactly "
                                   "where in the source we are."})
        t += 5.5
    return {"project": smoke.PROJ, "title": "Sync Probe (2026)",
            "target_minutes": 1, "voice": "tts", "lines": lines}


def _shots(draft) -> dict:
    return {"shots": [{"id": f"s{l['id']:02d}", "clip_start": l["clip_start"],
                       "clip_end": l["clip_end"], "action": "colour field",
                       "chars": []} for l in draft["lines"]]}


def _onsets(final: Path) -> list[float]:
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-i", str(final),
                        "-af", "silencedetect=n=-35dB:d=0.25", "-f", "null", "-"],
                       capture_output=True, text=True)
    return [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]


def _source_frame_at(final: Path, t: float) -> int | None:
    r = subprocess.run([config.ffmpeg(), "-v", "error", "-ss", f"{t:.3f}",
                        "-i", str(final), "-frames:v", "1",
                        "-vf", "crop=8:8:(iw-8)/2:(ih-8)/2,format=rgb24",
                        "-f", "rawvideo", "-"], capture_output=True)
    px = r.stdout
    if len(px) < 3:
        return None
    rr = sum(px[0::3]) / (len(px) / 3)
    gg = sum(px[1::3]) / (len(px) / 3)
    bb = sum(px[2::3]) / (len(px) / 3)
    return (int(round((rr - 4) / 8)) % 32 + 32 * (int(round((gg - 4) / 8)) % 32)
            + 1024 * int(round((bb - 4) / 8)))


def _render(legacy: bool):
    from pipeline.render import render
    orig = smoke._stub_intro_tts()
    restore = smoke._no_stems()
    before = config.RENDER_LEGACY_XFADE
    config.RENDER_LEGACY_XFADE = legacy
    try:
        pdir, _ = smoke._setup()
        _coded_source(pdir)
        draft = _draft()
        smoke._write(pdir, draft, _shots(draft))
        nar = smoke._narration_for(pdir, draft["lines"])
        final = Path(render(smoke.PROJ, draft, nar, music=None, captions=False,
                            keep_temp=False, force_clips=True))
        tl = json.loads((pdir / "timeline.json").read_text(encoding="utf-8"))
        out = final.with_name(f"sync_{'legacy' if legacy else 'new'}.mp4")
        final.replace(out)
        return out, draft, tl
    finally:
        config.RENDER_LEGACY_XFADE = before
        restore()
        from pipeline import intro as _intro
        _intro._tts_line = orig


def _measure(final: Path, draft: dict):
    ons = _onsets(final)
    rows = []
    for ln, on in zip(draft["lines"], ons):
        from pipeline.draft import parse_ts
        a, b = parse_ts(ln["clip_start"]), parse_ts(ln["clip_end"])
        n = _source_frame_at(final, on + 0.3)
        src = None if n is None else n / FPS
        rows.append((ln["id"], on, src, a, b))
    return rows, len(ons)


def main() -> int:
    res = {}
    for legacy in (True, False):
        final, draft, tl = _render(legacy)
        res[legacy] = _measure(final, draft)
    print(f"\n{'line':>4} {'window':>13} | {'legacy: voice@ src@':>22} | "
          f"{'new: voice@ src@':>20} | verdict")
    worst = 0.0
    for (lg, nw) in zip(res[True][0], res[False][0]):
        lid, on_l, src_l, a, b = lg
        _, on_n, src_n, _, _ = nw
        ok_l = src_l is not None and a - 0.1 <= src_l <= b + 0.1
        ok_n = src_n is not None and a - 0.1 <= src_n <= b + 0.1
        d = (src_n - src_l) if (src_n is not None and src_l is not None) else 0
        worst = max(worst, abs(d))
        print(f"{lid:>4} {a:5.1f}-{b:5.1f}s | {on_l:8.2f}s {src_l if src_l is None else round(src_l,2):>8} | "
              f"{on_n:8.2f}s {src_n if src_n is None else round(src_n,2):>8} | "
              f"{'ok' if ok_l else 'OUT'}/{'ok' if ok_n else 'OUT'}  "
              f"new-legacy {d:+.2f}s")
    print(f"\nonsets found: legacy {res[True][1]}, new {res[False][1]} "
          f"(expected {N_LINES}); worst picture difference {worst:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
