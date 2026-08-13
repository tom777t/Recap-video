"""Measure two premises behind the proposed binding rules, before coding them.

    python diag_catalogue.py <project> [<project> ...]

A. CUT BY AUDIO OR BY PICTURE?
   Compares every shot boundary against the transcript segment boundaries. A
   catalogue cut from the picture lands on visual cuts, which have no reason to
   coincide with where someone started speaking. A high alignment rate means the
   catalogue was cut from the transcript - and then "anchor the clip to the
   moment the narration describes" (RULES A3) has nothing honest to anchor to.

B. HOW MANY LINES COULD ALREADY SATISFY "every line references a shot"?
   Splits lines into: starts exactly at a shot, falls inside a shot, or floats
   free. The free ones are what a shot_id requirement would reject today.

Nothing is written or changed.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

TOL = 0.35          # seconds; "the same instant" for boundary comparison


def pt(t) -> float:
    return sum(float(x) * m for x, m in zip(str(t).split(":"), (3600, 60, 1)))


def load(pdir: Path, name: str):
    p = pdir / name
    if not p.exists():
        return None
    return json.load(io.open(p, encoding="utf-8-sig"))


def report(project: str) -> None:
    pdir = config.project_dir(project)
    shots = (load(pdir, "shots.json") or {}).get("shots", [])
    draft = (load(pdir, "draft.json") or {}).get("lines", [])
    tr = load(pdir, "transcript.json") or {}
    segs = tr.get("segments", []) or []

    print(f"\n=== {project} ===")
    print(f"shots: {len(shots)} | lines: {len(draft)} | transcript segments: {len(segs)}")

    # ---- A. boundary provenance -------------------------------------------
    if segs and shots:
        seg_marks = sorted({float(s.get("start", -1)) for s in segs}
                           | {float(s.get("end", -1)) for s in segs})
        bounds = []
        for s in shots:
            for k in ("clip_start", "clip_end"):
                if s.get(k):
                    bounds.append(pt(s[k]))
        hit = 0
        for b in bounds:
            lo, hi = b - TOL, b + TOL
            if any(lo <= m <= hi for m in seg_marks):
                hit += 1
        pct = 100.0 * hit / len(bounds) if bounds else 0.0
        print(f"A. shot boundaries landing on a transcript segment edge "
              f"(+/-{TOL}s): {hit}/{len(bounds)} ({pct:.0f}%)")
        if pct >= 60:
            print("   -> cut from the AUDIO. Shots follow who is speaking, not what")
            print("      is on screen, so a shot can span two visual moments.")
        elif pct <= 25:
            print("   -> cut from the PICTURE. Boundaries are independent of speech.")
        else:
            print("   -> mixed / inconclusive; look at a few shots by hand.")

    # ---- B. bindability ----------------------------------------------------
    if shots and draft:
        wins = [(pt(s["clip_start"]), pt(s.get("clip_end") or s["clip_start"]), s.get("id"))
                for s in shots if s.get("clip_start")]
        at = inside = free = 0
        free_ids = []
        for ln in draft:
            cs = ln.get("clip_start")
            if not cs:
                continue
            t = pt(cs)
            if any(abs(t - a) < 0.6 for a, _b, _i in wins):
                at += 1
            elif any(a <= t < b for a, b, _i in wins):
                inside += 1
            else:
                free += 1
                free_ids.append(str(ln.get("id")))
        tot = at + inside + free
        print(f"B. lines at a shot start: {at} | inside a shot: {inside} | "
              f"free: {free}  ({100.0*free/tot if tot else 0:.0f}% would be rejected)")
        if free_ids:
            print("   free ids: " + ", ".join(free_ids[:20])
                  + (" ..." if len(free_ids) > 20 else ""))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    for proj in sys.argv[1:]:
        try:
            report(proj)
        except Exception as e:
            print(f"\n=== {proj} ===\n  could not read: {e}")
