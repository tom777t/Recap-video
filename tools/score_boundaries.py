# -*- coding: utf-8 -*-
"""
score_boundaries.py - thuoc do DA GHIM trong docs/WINDOW_GROUPING_V2_CRITERION.md

    boundary-F1, dung sai +-1.0s, ghep MOT-MOT tham lam,
    tinh tren ranh gioi may va nguoi BEN TRONG vung da khai bao.

Vi sao mot-mot + precision: do la phan lam cho thuoc do KIEM SOAT SO LUONG.
v1 dung IoU best-overlap khong chan so cua so, va ket qua la mot cai METRONOME
(ngat moi 6s, khong tin hieu gi) VUOT QUA bar tren ca hai phim. Lan nay
metronome duoc in ra canh ket qua MOI LAN, dung de dieu do khong the lap lai
mot cach im lang.

PASS: F1 >= max(baseline_1shot, baseline_metronome) + 8.0 tren CA HAI phim
      VA ty le so cua so may/nguoi nam trong [0.70, 1.50] tren ca hai.

Dung:
    python tools/score_boundaries.py <project> --from A --to B [--file windows_llm.json]
"""
from __future__ import annotations
import argparse, bisect, io, json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

TOL = 1.0
MARGIN = 8.0
RATIO_LO, RATIO_HI = 0.70, 1.50


def pt(ts) -> float:
    p = [float(x) for x in str(ts).split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def bounds(wins, a, b):
    """Tap ranh gioi (start+end) nam trong vung."""
    s = set()
    for x, y in wins:
        if a - 1e-9 <= x <= b + 1e-9:
            s.add(round(x, 3))
        if a - 1e-9 <= y <= b + 1e-9:
            s.add(round(y, 3))
    return sorted(s)


def f1(machine_b, human_b, tol=TOL):
    used, tp = set(), 0
    for h in human_b:
        i = bisect.bisect_left(machine_b, h)
        cand = [j for j in range(max(0, i - 2), min(len(machine_b), i + 3))
                if abs(machine_b[j] - h) <= tol and j not in used]
        if cand:
            j = min(cand, key=lambda k: abs(machine_b[k] - h))
            used.add(j)
            tp += 1
    P = 100 * tp / len(machine_b) if machine_b else 0.0
    R = 100 * tp / len(human_b) if human_b else 0.0
    return (2 * P * R / (P + R) if P + R else 0.0), P, R, tp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--from", dest="a", type=float, required=True)
    ap.add_argument("--to", dest="b", type=float, required=True)
    ap.add_argument("--file", default="windows_llm.json")
    a = ap.parse_args()
    pdir = config.project_dir(a.project)
    A, B = a.a, a.b

    cuts = sorted(float(x) for x in
                  json.load(io.open(pdir / "_cuts.json", encoding="utf-8"))["cuts"])
    hs = json.load(io.open(pdir / "shots.json", encoding="utf-8-sig"))["shots"]
    H = [(pt(s["clip_start"]), pt(s["clip_end"])) for s in hs
         if s.get("clip_start") and s.get("clip_end")]
    H = [w for w in H if w[0] >= A and w[1] <= B]
    HB = bounds(H, A, B)

    W = json.load(io.open(pdir / a.file, encoding="utf-8"))["windows"]
    M = [(w["start_sec"], w["end_sec"]) for w in W
         if w["end_sec"] > A and w["start_sec"] < B]

    inreg = [x for x in cuts if A <= x <= B]
    base_shot = list(zip(inreg, inreg[1:]))
    br, s = [], inreg[0]
    for x in inreg[1:-1]:
        if x - s >= 6.0:
            br.append(x)
            s = x
    pts = sorted({inreg[0]} | set(br) | {inreg[-1]})
    base_metro = list(zip(pts, pts[1:]))

    rows = [("LLM (" + a.file + ")", M),
            ("baseline A: 1 cua so = 1 shot", base_shot),
            ("baseline B: METRONOME 6s", base_metro)]
    out = {}
    print(f"=== {a.project}   vung {A:.0f}-{B:.0f}s   "
          f"cua so nguoi {len(H)} | ranh gioi nguoi {len(HB)}")
    print(f"{'':<34}{'F1':>7}{'P':>7}{'R':>7}{'N win':>7}{'ratio':>8}")
    for name, wins in rows:
        bb = bounds(wins, A, B)
        F, P, R, tp = f1(bb, HB)
        ratio = len(wins) / len(H) if H else 0
        out[name] = dict(F1=F, P=P, R=R, n=len(wins), ratio=ratio)
        print(f"{name:<34}{F:7.1f}{P:7.1f}{R:7.1f}{len(wins):7d}{ratio:8.2f}")

    llm = out[rows[0][0]]
    best_base = max(out[rows[1][0]]["F1"], out[rows[2][0]]["F1"])
    gain = llm["F1"] - best_base
    ok_f1 = gain >= MARGIN
    ok_ratio = RATIO_LO <= llm["ratio"] <= RATIO_HI
    print(f"\nbaseline tot nhat: {best_base:.1f} | LLM {llm['F1']:.1f} | "
          f"chenh {gain:+.1f} (can >= +{MARGIN:.0f})  -> {'OK' if ok_f1 else 'KHONG DAT'}")
    print(f"ty le so cua so: {llm['ratio']:.2f} "
          f"(can {RATIO_LO}-{RATIO_HI})  -> {'OK' if ok_ratio else 'NGOAI BANG'}")
    print(f"KET QUA PHIM NAY: {'PASS' if (ok_f1 and ok_ratio) else 'FAIL'}")
    io.open(pdir / "windows_llm_score.json", "w", encoding="utf-8").write(
        json.dumps({"project": a.project, "region": [A, B], "tol": TOL,
                    "n_human": len(H), "n_human_bounds": len(HB),
                    "results": out, "best_baseline_f1": best_base,
                    "gain": gain, "pass_f1": ok_f1, "pass_ratio": ok_ratio},
                   ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
