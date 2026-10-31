"""Blind A/B material for clause-level picture: strips, not single frames.

blind_prep.py writes ONE frame per side, which cannot show the thing under
test. The claim here is that the picture CHANGES as the sentence moves
through its events, so a judge needs to see the progression: a single frame
from a clause-cut clip looks exactly like a single frame from a continuous
one.

So each side becomes a 5-frame strip across the clip, and the two sides are
stacked into ONE image per line - top and bottom, in RANDOM order, with no
hint of which is which. The answer key is written separately and is not
readable from the question material.

Why blind and why a fresh judge: every other number in this work comes from
the same scorer that chose the shots, so it cannot be evidence that the
choice was good - that is the objective function talking about itself.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

import config                                                 # noqa: E402

PROJ = Path(ROOT) / "projects" / "tokyodrift2006"
AB = PROJ / "_ab"


def strip(ff: str, clip: Path, out: Path, n: int = 5) -> bool:
    """n frames evenly spaced across the clip, tiled left to right."""
    from pipeline.probe import streams
    try:
        dur = float(streams(clip)["video"]["duration"])
    except Exception:
        return False
    if dur <= 0:
        return False
    # sample inside the clip, avoiding the first/last 5% so a fade does not
    # become the sample
    times = [dur * (0.05 + 0.90 * i / (n - 1)) for i in range(n)]
    parts = []
    for i, t in enumerate(times):
        p = out.parent / f"_f{i}_{out.stem}.png"
        r = subprocess.run(
            [ff, "-y", "-hide_banner", "-loglevel", "error", "-ss",
             f"{t:.3f}", "-i", str(clip), "-frames:v", "1",
             "-vf", "scale=384:-2", str(p)],
            capture_output=True, text=True, errors="replace")
        if r.returncode == 0 and p.exists():
            parts.append(p)
    if len(parts) < 2:
        return False
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error"]
    for p in parts:
        cmd += ["-i", str(p)]
    cmd += ["-filter_complex",
            "".join(f"[{i}:v]" for i in range(len(parts)))
            + f"hstack=inputs={len(parts)}[v]", "-map", "[v]", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    for p in parts:
        p.unlink(missing_ok=True)
    return r.returncode == 0 and out.exists()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["A", "B"])
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()

    ff = config.ffmpeg()
    outdir = PROJ / f"_blind_{a.arm}"
    outdir.mkdir(exist_ok=True)
    d = json.load(io.open(PROJ / "draft.json", encoding="utf-8-sig"))
    by = {l["id"]: l for l in d["lines"]}

    ids = sorted(int(p.stem.split("_")[0][4:]) for p in AB.glob(f"*_{a.arm}.mp4"))
    rnd = random.Random(a.seed)
    rnd.shuffle(ids)
    ids = sorted(ids[:a.n])

    key, qs = {}, []
    for lid in ids:
        cur = AB / f"line{lid:03d}_cur.mp4"
        new = AB / f"line{lid:03d}_{a.arm}.mp4"
        if not (cur.exists() and new.exists()):
            continue
        top_is_new = rnd.random() < 0.5
        top, bot = (new, cur) if top_is_new else (cur, new)
        st, sb = outdir / f"_top{lid}.png", outdir / f"_bot{lid}.png"
        if not (strip(ff, top, st) and strip(ff, bot, sb)):
            continue
        comp = outdir / f"line{lid:03d}.png"
        r = subprocess.run(
            [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(st),
             "-i", str(sb), "-filter_complex",
             "[0:v][1:v]vstack=inputs=2[v]", "-map", "[v]", str(comp)],
            capture_output=True, text=True, errors="replace")
        st.unlink(missing_ok=True)
        sb.unlink(missing_ok=True)
        if r.returncode != 0:
            continue
        key[str(lid)] = "TOP" if top_is_new else "BOTTOM"
        qs.append({"line": lid, "image": comp.name,
                   "narration": str(by[lid]["narration"])})

    (outdir / "questions.json").write_text(
        json.dumps(qs, ensure_ascii=False, indent=1), encoding="utf-8")
    (PROJ / f"_blind_{a.arm}_key.json").write_text(
        json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"arm {a.arm}: {len(qs)} comparison image(s) in {outdir}")
    print(f"answer key written OUTSIDE that folder: "
          f"_blind_{a.arm}_key.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
