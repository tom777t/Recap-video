"""Before/after table for a draft rewrite: contour, anchors, persona.

Usage:
    python tools/compare_drafts.py --project tokyodrift2006 \
        --before projects/tokyodrift2006/draft_prerewrite.json \
        --after  projects/tokyodrift2006/draft.json

Every number here is the one a gate acts on, so the table and the gate cannot
drift apart: both read pipeline.pacing_gates.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from pipeline import angle_spec  # noqa: E402
from pipeline import continuity_gates as cg  # noqa: E402
from pipeline import pacing_gates as pg  # noqa: E402


def load(p):
    return json.loads(io.open(p, encoding="utf-8-sig").read())


def summarise(draft, pdir):
    rep = pg.pacing_report(draft, pdir)
    con = cg.continuity_report(draft, pdir)
    s = dict(rep.get("stats") or {})
    lines = [ln for ln in (draft.get("lines") or [])
             if str(ln.get("narration") or "").strip()]
    silent = [ln for ln in (draft.get("lines") or [])
              if not str(ln.get("narration") or "").strip()]
    s["narrated_lines"] = len(lines)
    s["silent_units"] = len(silent)
    s["words"] = sum(len(str(ln.get("narration") or "").split())
                     for ln in lines)
    s["errors"] = len(rep["errors"]) + len(con["errors"])
    s["warns"] = len(rep["warns"]) + len(con["warns"])
    return s, rep, con


def anchor_lines(draft, spec):
    tbl = {r["beat"]: r for r in pg.beat_table(draft)}
    out = []
    for a in spec["anchors"]:
        n = sum(tbl.get(b, {}).get("narrated", 0) for b in a["beats"])
        out.append(("/".join(a["beats"]), a["kind"], n))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    a = ap.parse_args()
    pdir = Path(config.project_dir(a.project))
    spec = angle_spec.require(pdir)

    b, brep, bcon = summarise(load(a.before), pdir)
    f, frep, fcon = summarise(load(a.after), pdir)

    def row(label, key, fmt="{}", bar=""):
        bv = b.get(key)
        fv = f.get(key)
        bs = fmt.format(bv) if bv is not None else "-"
        fs = fmt.format(fv) if fv is not None else "-"
        return f"| {label} | {bs} | {fs} | {bar} |"

    print(f"## {a.project}: before / after")
    print()
    print("| measure | before | after | bar |")
    print("|---|---|---|---|")
    print(row("narrated lines", "narrated_lines"))
    print(row("silent units (footage/hold)", "silent_units"))
    print(row("words", "words"))
    print(row("beats covered", "beats"))
    print(row("one-line beats", "one_line_beats"))
    print(row("longest one-line run", "longest_one_line_run", "{}",
              f"<= {config.PACING_ONE_LINE_RUN_MAX}"))
    print(row("top-20% line share", "top20_line_share", "{:.3f}",
              f">= {config.PACING_TOP20_LINE_SHARE_MIN}"))
    print(row("judgment share", "judgment_share", "{:.3f}",
              f">= {config.PERSONA_JUDGMENT_SHARE_MIN}"))
    print(row("frame-only share", "frame_only_share", "{:.3f}",
              f"<= {config.PERSONA_FRAME_ONLY_SHARE_MAX}"))
    print(row("voiced share", "voiced_share", "{:.3f}"))
    print(row("mean compression (s/word)", "mean_compression_sec_per_word",
              "{:.3f}"))
    print(row("gate errors", "errors", "{}", "0"))
    print(row("gate warnings", "warns"))
    print()
    print("### lines per anchor")
    print()
    print("| anchor | kind | before | after | bar |")
    print("|---|---|---|---|---|")
    ab = {k: n for k, _kd, n in anchor_lines(load(a.before), spec)}
    af = {k: n for k, _kd, n in anchor_lines(load(a.after), spec)}
    for k, kd, _n in anchor_lines(load(a.after), spec):
        print(f"| {k} | {kd} | {ab.get(k, 0)} | {af.get(k, 0)} | "
              f">= {config.PACING_ANCHOR_MIN_LINES} |")
    print()
    if frep["errors"] or fcon["errors"]:
        print("### gates still failing on the AFTER draft")
        print()
        for e in frep["errors"] + fcon["errors"]:
            print(f"- {e}")
    else:
        print("### all contour / persona / continuity gates pass on the "
              "AFTER draft")
    return 0


if __name__ == "__main__":
    sys.exit(main())
