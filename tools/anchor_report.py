# -*- coding: utf-8 -*-
"""anchor_report.py - which lines show the moment they narrate, before render.

Runs the same logic the render uses (pipeline/anchor.py) on a project's draft
and transcript and prints, for every line that quotes or paraphrases
dialogue, whether that moment is on screen while the line is spoken:

    ON        already on screen from clip_start
    MOVED     the render will start the shown part later, inside the window
    OFF       the moment is outside what the window can show - rebind the
              line at the write stage (fix_line / the writer)

Narration lengths come from timeline.json (a finished render) when present,
else from the draft at config.WORDS_PER_SECOND. No API, no render.

    python tools/anchor_report.py --project doublelife2023
    python tools/anchor_report.py --project furious72015 --before
        (--before ignores the fix: counts what the old render showed)
    python tools/anchor_report.py --project doublelife2023 --apply
        (REBINDS each OFF line's window onto its moment when that moment is
         within REBIND_REACH seconds and the new window overlaps neither
         neighbour's shown footage; draft_preanchor.json is the backup)

Rebinding is done HERE, on the draft, not in the render: a new clip_start /
clip_end moves the line to the shot that really holds the moment, so censor,
exposure and silence flags resolve through that shot. A render-time jump
outside the window would play a neighbouring shot under the old shot's flags.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import anchor as A  # noqa: E402


def _ts(s):
    h, m, x = str(s).split(":")
    return int(h) * 3600 + int(m) * 60 + float(x)


REBIND_REACH = 25.0     # seconds outside the window a rebind may go


def _hms(t: float) -> str:
    h = int(t // 3600); m = int(t % 3600 // 60)
    return f"{h:02d}:{m:02d}:{t - h * 3600 - m * 60:06.3f}"


def analyse(pdir: Path, before: bool = False, rebind: bool = False) -> dict:
    draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    segs = A.load_segments(pdir)
    durs = {}
    tlp = pdir / "timeline.json"
    if tlp.exists():
        for t in json.loads(tlp.read_text(encoding="utf-8-sig"))["lines"]:
            durs[t["id"]] = float(t["out_end"]) - float(t["out_start"])
    wps = float(getattr(config, "WORDS_PER_SECOND", 3.5))
    lead_in = float(getattr(config, "NARRATION_LEAD_IN", 0.5))
    gap = float(getattr(config, "GAP_BETWEEN_LINES", 0.18))
    lines = [ln for ln in draft["lines"] if ln.get("clip_start")
             and not ln.get("pool") and ln.get("narration")]
    rows, prev_end = [], None
    for k, ln in enumerate(lines):
        cs, ce = _ts(ln["clip_start"]), _ts(ln["clip_end"])
        nd = durs.get(ln["id"]) or len(ln["narration"].split()) / wps
        need = max(lead_in + nd + gap, float(ln.get("hold", 0.0)))
        nxt = _ts(lines[k + 1]["clip_start"]) if k + 1 < len(lines) else None
        start = cs
        a = A.find_anchor(ln["narration"], segs, cs, ce)
        if a is not None:
            if A.visible(cs, need, a[0]):
                state = "ON"
            elif before:
                state = "OFF"
            else:
                ns = A.place(cs, ce, a[0], need, lead_in, nd,
                             lo=prev_end, hi=nxt)
                if ns is not None:
                    state, start = "MOVED", ns
                else:
                    state = "OFF"
                    if rebind and abs(a[0] - (cs + ce) / 2) <= \
                            REBIND_REACH + (ce - cs) / 2:
                        # a new window around the moment, as long as the
                        # old one (but at least `need`), between neighbours
                        lo = max(prev_end or 0.0, a[0] - REBIND_REACH)
                        hi = min(nxt if nxt is not None else 1e9,
                                 a[0] + REBIND_REACH)
                        L = max(need, min(ce - cs, hi - lo))
                        ns2 = A.place(lo, min(hi, lo + 10 * L), a[0], need,
                                      lead_in, nd, lo=lo, hi=hi)
                        if ns2 is not None:
                            ncs = ns2
                            nce = min(hi, max(ns2 + need, ns2 + min(L, ce - cs)))
                            ln["clip_start"], ln["clip_end"] = _hms(ncs), _hms(nce)
                            ln.setdefault("anchor_rebound", {
                                "from": [_hms(cs), _hms(ce)],
                                "moment": round(a[0], 2), "kind": a[1]})
                            state, start = "REBOUND", ncs
            rows.append({"id": ln["id"], "kind": a[1], "state": state,
                         "at": round(a[0] - cs, 1), "window": round(ce - cs, 1),
                         "shown": round(need, 1),
                         "moved_by": round(start - cs, 1),
                         "said": a[2][:50]})
        prev_end = start + need
    return {"segments": len(segs), "rows": rows, "draft": draft}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--before", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    pdir = Path(ROOT) / "projects" / a.project
    r = analyse(pdir, before=a.before, rebind=a.apply)
    if not r["segments"]:
        print("no transcript.json - nothing to anchor (NOT RUN, not clean)")
        sys.exit(2)
    rows = r["rows"]
    n = {s: sum(1 for x in rows if x["state"] == s)
         for s in ("ON", "MOVED", "REBOUND", "OFF")}
    print(f"{a.project}: {len(rows)} line(s) narrate a quoted/paraphrased "
          f"moment - ON {n['ON']}, MOVED {n['MOVED']}, REBOUND "
          f"{n['REBOUND']}, OFF {n['OFF']}"
          + ("  (old render)" if a.before else ""))
    if a.apply and n["REBOUND"]:
        import shutil
        dp = pdir / "draft.json"
        shutil.copy2(dp, pdir / "draft_preanchor.json")
        dp.write_text(json.dumps(r["draft"], ensure_ascii=False, indent=2),
                      encoding="utf-8")
        print(f"Rebound {n['REBOUND']} window(s); backup in "
              f"draft_preanchor.json. The voice stage re-checks capacity.")
    for x in rows:
        if x["state"] != "ON":
            print(f"  line {x['id']:>3} {x['state']:5s} {x['kind']:5s} moment "
                  f"{x['at']:+6.1f}s in a {x['window']:4.1f}s window "
                  f"(shown {x['shown']:.1f}s, start {x['moved_by']:+.1f}s)  "
                  f"\"{x['said']}\"")
    sys.exit(1 if n["OFF"] else 0)


if __name__ == "__main__":
    main()
