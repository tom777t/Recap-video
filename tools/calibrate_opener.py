# -*- coding: utf-8 -*-
"""calibrate_opener.py - prove the picker can tell good from bad.

    python tools/calibrate_opener.py <project> [--good-start S] [--good-end S]

WHY. AGENTS.md: calibrate an instrument before trusting it. The opener
picker (pipeline/opening.py) decides what a video's first seconds show;
if it cannot separate a human-approved opening from a trivial one it is
not an instrument and nothing downstream may trust it.

Controls:

  known-good  the approved Tokyo Drift opening zone - the school-bully
              scene the operator's approved draft opens its story on
              (draft lines 4-6, ~02:36-03:46). For another project pass
              --good-start/--good-end in seconds.
  known-bad   (a) the distributor-logo / credits shot at 0:00 - R1's
              anti-pick; (b) the emptiest quarter of the catalogue -
              shots with nothing charged to show.

PASS requires all of: mode A chosen; the chosen opener inside the
known-good window; known-good best strictly above the logo's score; and
known-good best strictly above the median of the emptiest quartile.
Both control results are printed - the commit that lands the picker
states them.
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline import opening  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?", default="tokyodrift2006")
    ap.add_argument("--good-start", type=float, default=156.0)
    ap.add_argument("--good-end", type=float, default=226.0)
    a = ap.parse_args()

    data = opening.read(a.project)
    if not data["candidates"]:
        print("CALIBRATE-OPENER: no candidates - cannot calibrate")
        return 1

    lever = opening.lever_for(data["facts"])
    pick = opening.choose(data["candidates"], lever=lever,
                          lands=data["lands"], runtime_sec=data["runtime_sec"])
    ranked = pick["ranked"]

    # known-good: the approved window's best score
    good = [r for r in ranked if r["id"] in _ids_in(
        data["candidates"], a.good_start, a.good_end)]
    good_best = max((r["score"] for r in good), default=None)
    good_best_id = next((r["id"] for r in good
                         if r["score"] == good_best), None) if good else None

    # known-bad (a): the logo / credits shot at the head of the film
    head = [c for c in data["candidates"] if c["start"] < 60.0]
    bad_logo = [opening.score(c, lever=lever, lands=data["lands"],
                              runtime_sec=data["runtime_sec"])
                for c in head]
    logo_scores = [r["score"] for r in bad_logo if r["score"] < 0]

    # known-bad (b): the emptiest quartile of everything scoreable
    allc = [opening.score(c, lever=lever, lands=data["lands"],
                          runtime_sec=data["runtime_sec"])
            for c in data["candidates"]]
    ok = sorted(r["score"] for r in allc if r["score"] >= 0)
    lowq = ok[:max(1, len(ok) // 4)] if ok else []
    low_med = statistics.median(lowq) if lowq else None

    print(f"project={a.project} lever={lever} mode={pick['open_mode']} "
          f"opener={pick['opener']['id'] if pick['opener'] else None}")
    print(f"known-good window {a.good_start}-{a.good_end}s: "
          f"{len(good)} scored, best {good_best} ({good_best_id})")
    print(f"known-bad logo/credits: {len(logo_scores)} anti-picked, "
          f"scores {logo_scores[:5]}")
    print(f"known-bad emptiest quartile: median {low_med} of {len(lowq)}")
    print("top-5 ranked:")
    for r in ranked[:5]:
        print(f"  {r['id']:>22} {r['score']:>6}  {'; '.join(r['why'])}")

    ok_mode = pick["open_mode"] == "A"
    ok_in = bool(good_best is not None and pick["opener"]
                 and _ids_in(data["candidates"], a.good_start, a.good_end,
                             pick["opener"]["id"]))
    ok_logo = bool(good_best is not None and logo_scores
                   and good_best > max(logo_scores))
    ok_low = bool(good_best is not None and low_med is not None
                  and good_best > low_med)

    print(f"mode-A            : {'PASS' if ok_mode else 'FAIL'}")
    print(f"opener in window  : {'PASS' if ok_in else 'FAIL'}")
    print(f"beats logo        : {'PASS' if ok_logo else 'FAIL'}")
    print(f"beats trivial med : {'PASS' if ok_low else 'FAIL'}")
    if all((ok_mode, ok_in, ok_logo, ok_low)):
        print("CALIBRATE-OPENER: PASS - picker separates the controls")
        return 0
    print("CALIBRATE-OPENER: FAIL - not an instrument; do not gate on it")
    return 1


def _ids_in(cands: list, lo: float, hi: float, only=None) -> set:
    out = {c["id"] for c in cands
           if lo <= c["start"] < hi or lo < c["end"] <= hi}
    return (out & {only}) if only else out


if __name__ == "__main__":
    sys.exit(main())
