# -*- coding: utf-8 -*-
"""
check_bindable.py - kiem tra HA NGUON, dinh nghia ghim truoc trong
docs/WINDOW_GROUPING_V2_CRITERION.md

Bai hoc v1: su trung khop ranh gioi co the KHONG quan trong o ha nguon, dung
nhu 1% trung khop `depicts` hoa ra khong quan trong. Nen phep thu quyet dinh la:
mot dong draft cua NGUOI co bind duoc vao mot moment MAY khong?

Dong co cua so nguoi [a,b] va narration w tu BIND DUOC vao moment may [m0,m1]
khi va chi khi, TREN CUNG MOT moment:

    overlap([a,b],[m0,m1]) >= 0.70 * (b-a)      moment cho thay dung canh do
    w/3.0 + 0.6 <= (m1-m0) * 1.4                luat capacity san co

Hai dieu kien phai thoa tren CUNG mot moment - khong duoc lay overlap tu
moment nay va capacity tu moment kia.

Dung:
    python tools/check_bindable.py <project> --from A --to B
"""
from __future__ import annotations
import argparse, io, json, os, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

OVERLAP_FRAC = 0.70
WPS, LEAD, TOLER = 3.0, 0.6, 1.4


def pt(ts) -> float:
    p = [float(x) for x in str(ts).split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--from", dest="a", type=float, required=True)
    ap.add_argument("--to", dest="b", type=float, required=True)
    ap.add_argument("--file", default="windows_llm.json")
    ap.add_argument("--baseline", choices=["shot", "metro"], default=None)
    ap.add_argument("--metro-sec", type=float, default=6.0,
                    help="buoc metronome. Dat bang DO DAI TRUNG BINH cua moment "
                         "LLM de so sanh cong bang: neu metronome khop do dai ma "
                         "bam sat duoc LLM thi khau gom khong can LLM.")
    x = ap.parse_args()
    pdir = config.project_dir(x.project)
    A, B = x.a, x.b

    lines = json.load(io.open(pdir / "draft.json", encoding="utf-8"))["lines"]
    L = [l for l in lines if l.get("clip_start")
         and pt(l["clip_start"]) >= A and pt(l["clip_end"]) <= B]

    if x.baseline:
        cuts = sorted(float(v) for v in
                      json.load(io.open(pdir / "_cuts.json", encoding="utf-8"))["cuts"])
        inreg = [c for c in cuts if A <= c <= B]
        if x.baseline == "shot":
            M = list(zip(inreg, inreg[1:]))
            label = "BASELINE 1 shot"
        else:
            br, s = [], inreg[0]
            for c in inreg[1:-1]:
                if c - s >= x.metro_sec:
                    br.append(c)
                    s = c
            pts = sorted({inreg[0]} | set(br) | {inreg[-1]})
            M = list(zip(pts, pts[1:]))
            label = f"BASELINE metronome {x.metro_sec:.1f}s"
    else:
        W = json.load(io.open(pdir / x.file, encoding="utf-8"))["windows"]
        M = [(w["start_sec"], w["end_sec"]) for w in W]
        label = x.file

    ok, fail = [], []
    for l in L:
        a, b = pt(l["clip_start"]), pt(l["clip_end"])
        w = len(str(l.get("narration", "")).split())
        need = w / WPS + LEAD
        best = None
        for m0, m1 in M:
            ov = max(0.0, min(b, m1) - max(a, m0))
            if ov >= OVERLAP_FRAC * (b - a) and need <= (m1 - m0) * TOLER:
                best = (m0, m1, ov)
                break
        if best:
            ok.append(l["id"])
        else:
            # chan doan: dieu kien nao truot
            bo = max((max(0.0, min(b, m1) - max(a, m0)) / (b - a)
                      for m0, m1 in M), default=0.0)
            cap = max(((m1 - m0) * TOLER >= need
                       for m0, m1 in M
                       if max(0.0, min(b, m1) - max(a, m0)) >= OVERLAP_FRAC * (b - a)),
                      default=False)
            fail.append((l["id"], l["clip_start"], l["clip_end"], w, bo, cap))

    n = len(L)
    print(f"=== {x.project}  {label}  vung {A:.0f}-{B:.0f}s")
    print(f"dong draft NGUOI nam tron trong vung: {n}")
    print(f"BIND DUOC: {len(ok)}/{n} = {100*len(ok)/n:.1f}%   "
          f"(moc tham chieu ~90%)")
    if fail:
        print(f"\nKHONG bind duoc: {len(fail)} - goi ten tung dong:")
        print(f"  {'id':<5}{'cua so nguoi':<28}{'tu':>4}{'overlap tot nhat':>18}  vi sao")
        for i, cs, ce, w, bo, cap in fail:
            why = ("khong moment nao phu >=70%" if bo < OVERLAP_FRAC
                   else "phu du nhung KHONG du capacity")
            print(f"  {i:<5}{cs+' -> '+ce:<28}{w:>4}{bo*100:>17.0f}%  {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
