"""
Score the blind A/B test against the key.

    python tools/blind_score.py --project tokyodrift2006

Reports the win rate for the PROPOSED binding, and - because a win rate on 40
items is a small sample - a two-sided binomial p-value against the null that
the judge is choosing at random. A 55% win rate on 40 items is not evidence of
anything, and saying so is part of the measurement.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402


def binom_two_sided(k: int, n: int, p: float = 0.5) -> float:
    if n == 0:
        return 1.0

    def pmf(i):
        return math.comb(n, i) * p ** i * (1 - p) ** (n - i)

    obs = pmf(k)
    return min(1.0, sum(pmf(i) for i in range(n + 1)
                        if pmf(i) <= obs + 1e-15))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    a = ap.parse_args()
    fdir = config.project_dir(a.project) / "_fingerprints"
    key = {k["line_id"]: k for k in
           json.loads((fdir / "blind_key.json").read_text(encoding="utf-8"))}

    answers = []
    for p in sorted(glob.glob(str(fdir / "blind" / "answers_*.json"))):
        answers.extend(json.loads(
            Path(p).read_bytes().decode("utf-8-sig")))
    print(f"answers collected: {len(answers)} (key has {len(key)})")

    new_win = old_win = tie = unknown = 0
    rows = []
    pos_a = 0
    for ans in answers:
        lid = ans.get("line_id")
        k = key.get(lid)
        if k is None:
            unknown += 1
            continue
        ch = str(ans.get("choice", "")).strip().upper()
        if ch == "TIE":
            tie += 1
            verdict = "tie"
        elif ch in ("A", "B"):
            if ch == "A":
                pos_a += 1
            side = k["A"] if ch == "A" else k["B"]
            verdict = side
            if side == "new":
                new_win += 1
            else:
                old_win += 1
        else:
            unknown += 1
            continue
        rows.append({"line_id": lid, "choice": ch, "picked": verdict,
                     "why": ans.get("why", "")})

    decided = new_win + old_win
    print(f"\n  proposed (new) preferred : {new_win}")
    print(f"  current  (old) preferred : {old_win}")
    print(f"  tie                      : {tie}")
    print(f"  unusable                 : {unknown}")
    if decided:
        wr = new_win / decided
        p = binom_two_sided(new_win, decided)
        print(f"\n  WIN RATE for the proposed binding: {wr*100:.1f}% "
              f"({new_win}/{decided} decided)")
        print(f"  two-sided binomial p = {p:.3f} against a coin flip")
        if p >= 0.05:
            print("  -> NOT distinguishable from random choice at this "
                  "sample size. This is not evidence the new binding is "
                  "better, and it is not evidence it is worse.")
        else:
            better = "BETTER" if wr > 0.5 else "WORSE"
            print(f"  -> significantly {better} than the current binding.")
    # position-bias sanity check on the judges themselves
    if decided:
        print(f"\n  judges picked position A in {pos_a}/{decided} decided "
              f"items; the key put old in A for "
              f"{sum(1 for k in key.values() if k['A']=='old')}/{len(key)}. "
              f"A strong lean to one position would mean the judges were "
              f"answering the layout, not the question.")
    (fdir / "blind_result.json").write_text(json.dumps(
        {"new_preferred": new_win, "old_preferred": old_win, "tie": tie,
         "unusable": unknown, "decided": decided,
         "win_rate_new": (new_win / decided if decided else None),
         "p_value": (binom_two_sided(new_win, decided) if decided else None),
         "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
