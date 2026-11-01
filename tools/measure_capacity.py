"""Reproduce the viewer's diagnosis, then calibrate VISUAL-CAPACITY on it.

The viewer measured roughly: median line ~9s with ~3 event clauses over 1
catalogued shot, and 67 of 107 lines narrating at least 2 more events than
the shots they show. That is the defect clause-level picture exists to fix,
so it has to be reproducible here before anything is built on it - if this
tool cannot see what the viewer saw, the instrument is wrong.

Also reports what the SPLIT would cost: how many sub-clips the plan adds and
what that does to the cut rate, against the measured reference ceiling in
config/cut_rate_control.json.
"""
from __future__ import annotations

import io
import json
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

import config                                                 # noqa: E402
from pipeline import angle_spec, clause_shots as cs            # noqa: E402

PROJ = os.path.join(ROOT, "projects", "tokyodrift2006")
OUT = os.path.join(ROOT, "config", "visual_capacity_control.json")


def _sec(v):
    try:
        p = [float(x) for x in str(v).split(":")]
        return p[0] * 3600 + p[1] * 60 + p[2]
    except Exception:
        return None


def main() -> int:
    d = json.load(io.open(os.path.join(PROJ, "draft.json"),
                          encoding="utf-8-sig"))
    shots = json.load(io.open(os.path.join(PROJ, "shots.json"),
                              encoding="utf-8-sig"))["shots"]
    try:
        spec = angle_spec.load(__import__("pathlib").Path(PROJ))
        anchors = {b for a in spec["anchors"] for b in a["beats"]}
    except Exception:
        anchors = set()
    protect = tuple(getattr(config, "CLAUSE_PROTECT_DELIVERIES",
                            ("sad", "reveal", "outro", "hook", "intro")))

    # catalogued shots fully inside a line's own window
    def shots_in(a, b):
        return [s for s in shots
                if _sec(s["clip_start"]) is not None
                and _sec(s["clip_start"]) >= a - 0.05
                and _sec(s["clip_end"]) <= b + 0.05]

    rows = []
    for ln in d["lines"]:
        text = str(ln.get("narration") or "").strip()
        if not text:
            continue
        a, b = _sec(ln.get("clip_start")), _sec(ln.get("clip_end"))
        dur = (b - a) if (a is not None and b is not None) else None
        ev = cs.visual_events(text)
        cl = cs.split_clauses(text)
        nsh = len(shots_in(a, b)) if dur else 0
        ok, why = cs.splittable(ln, anchors, protect)
        rows.append({
            "id": ln.get("id"), "beat": str(ln.get("note") or ""),
            "dur": round(dur, 2) if dur else None,
            "words": len(text.split()),
            "clauses": len(cl), "events": ev, "shots": max(nsh, 1),
            "excess": ev - max(nsh, 1),
            "splittable": ok, "why": why,
        })

    nar = [r for r in rows if r["dur"]]
    durs = sorted(r["dur"] for r in nar)
    evs = sorted(r["events"] for r in nar)
    over2 = [r for r in nar if r["excess"] >= 2]
    over1 = [r for r in nar if r["excess"] >= 1]
    spl = [r for r in rows if r["splittable"]]

    print(f"narrated lines with a window: {len(nar)}")
    print(f"  median line length   {st.median(durs):.1f}s  "
          f"(p25 {durs[len(durs)//4]:.1f}s  p75 "
          f"{durs[3*len(durs)//4]:.1f}s)")
    cls=sorted(r["clauses"] for r in nar)
    print(f"  median clauses        {st.median(cls):.1f}")
    print(f"  median visible events {st.median(evs):.1f}  "
          f"mean {sum(evs)/len(evs):.2f}")
    print(f"  lines narrating >=2 more events than their shots: "
          f"{len(over2)}/{len(nar)}")
    print(f"  lines narrating >=1 more:                         "
          f"{len(over1)}/{len(nar)}")
    print()
    print(f"SPLITTABLE under the exclusions: {len(spl)}/{len(rows)}")
    from collections import Counter
    skipped = Counter(r["why"].split(" - ")[-1] for r in rows
                      if not r["splittable"])
    for why, n in skipped.most_common(6):
        print(f"    kept continuous: {n:3d}  {why}")

    # what the split costs in cuts
    extra = sum(min(r["events"], r["shots"] + 3) - 1 for r in spl)
    ctrl = {}
    cp = os.path.join(ROOT, "config", "cut_rate_control.json")
    if os.path.exists(cp):
        ctrl = json.load(io.open(cp, encoding="utf-8")).get("verdict") or {}
    mins = (ctrl.get("our_cuts_per_min") and
            json.load(io.open(cp, encoding="utf-8"))["ours"]
            ["final.mp4"]["duration_min"])
    print()
    print(f"sub-clips the plan would ADD: {extra}")
    if ctrl and mins:
        new_rate = ctrl["our_cuts_per_min"] + extra / mins
        print(f"  cut rate {ctrl['our_cuts_per_min']:.2f} -> "
              f"{new_rate:.2f} /min  (reference ceiling "
              f"{ctrl['ceiling_cuts_per_min']:.2f})")
        print("  " + ("WITHIN the ceiling" if new_rate
                      <= ctrl["ceiling_cuts_per_min"]
                      else "OVER the ceiling - the plan must split fewer "
                           "lines or merge more clauses"))

    # the gate bar: how much excess is tolerable before a line is simply
    # over-stuffed and the WRITER must fix it rather than the editor.
    exc = sorted(r["excess"] for r in nar)
    p90 = exc[int(0.90 * len(exc))]
    print()
    print(f"excess events per line: median {st.median(exc):.0f}  "
          f"p75 {exc[int(0.75*len(exc))]}  p90 {p90}  max {exc[-1]}")
    worst = sorted(nar, key=lambda r: -r["excess"])[:8]
    print("  worst lines (events vs shots):")
    for r in worst:
        print(f"    line {r['id']:>3} {r['beat'][:5]:5} {r['dur']:5.1f}s "
              f"{r['events']} events / {r['shots']} shot(s)  "
              f"excess {r['excess']}")

    json.dump({
        "instrument": "pipeline.clause_shots",
        "lines": rows,
        "summary": {
            "narrated": len(nar),
            "median_line_sec": round(st.median(durs), 2),
            "median_events": st.median(evs),
            "lines_excess_ge2": len(over2),
            "lines_excess_ge1": len(over1),
            "splittable": len(spl),
            "subclips_added": extra,
            "excess_p90": p90,
        },
    }, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"written: {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
