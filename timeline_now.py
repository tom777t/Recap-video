"""Reconstruct where each draft line lands in final.mp4.

Uses the real per-line narration audio in narration/line_XXX.* plus the same
clip_len / XFADE arithmetic render.py uses, so the numbers line up with the
rendered video. This is timeline.json (candidate E1) computed after the fact.

    python timeline_now.py <project>
"""
import json, io, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

proj = sys.argv[1]
pdir = config.project_dir(proj)
XF, GAP = config.XFADE_DURATION, config.GAP_BETWEEN_LINES

def pt(t):
    return sum(float(x) * m for x, m in zip(str(t).split(':'), (3600, 60, 1)))

def ms(s):
    return f"{int(s)//60:02d}:{int(s)%60:02d}"

def dur(p):
    r = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries",
                        "format=duration", "-of",
                        "default=noprint_wrappers=1:nokey=1", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0

lines = json.load(io.open(pdir / "draft.json", encoding="utf-8-sig"))["lines"]
shots = json.load(io.open(pdir / "shots.json", encoding="utf-8-sig"))["shots"]
starts = [pt(s["clip_start"]) for s in shots if s.get("clip_start")]

ids = [str(l["id"]) for l in lines]
dupes = sorted({i for i in ids if ids.count(i) > 1})
ndir = pdir / "narration"
files = sorted(ndir.glob("line_*.*")) if ndir.exists() else []
print(f"lines: {len(lines)} | narration files: {len(files)} | duplicate ids: {dupes or 'none'}")
print("-" * 92)
print(f"{'id':<7}{'VIDEO':<8}{'phim':<9}{'bind':<7}narration")
print("-" * 92)

cursor = 0.0
for ln in lines:
    lid = ln["id"]
    f = next((ndir / f"line_{int(lid):03d}{e}" for e in (".mp3", ".wav", ".m4a")
              if (ndir / f"line_{int(lid):03d}{e}").exists()), None)
    nd = max(0.4, dur(f)) if f else 0.0
    clip_len = max(nd + GAP, float(ln.get("hold", 0.0) or 0.0))
    cs = ln.get("clip_start")
    bind = "-"
    if cs:
        t = pt(cs)
        bind = "shot" if any(abs(t - s) < 0.6 for s in starts) else "FREE"
    print(f"{str(lid):<7}{ms(cursor):<8}{ms(pt(cs)) if cs else '-':<9}{bind:<7}"
          f"{(ln.get('narration') or '')[:52]}")
    cursor += clip_len - XF

print("-" * 92)
print(f"tong runtime uoc tinh: {ms(cursor)}")
