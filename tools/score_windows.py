# -*- coding: utf-8 -*-
"""
score_windows.py - cham `windows.json` (may) doi chieu `shots.json` (nguoi).

Tieu chi duoc GHIM TRUOC khi do, trong docs/WINDOW_GROUPING_CRITERION.md:

    PASS              ty le IoU>=0.5  >= 0.60 tren CA HAI phim
    HARD FAIL         bat ky phim nao co > 5% cua so nguoi KHONG duoc phu
    STYLE-TUNING FAIL |share_A - share_B| > 0.15

KHONG trung binh hai phim. Mot phim dau mot phim truot nghia la luat da hoc
thuoc mot nhip dung phim, khong phai da giai duoc bai toan gom.

KHONG cham precision: cua so nguoi vua la GOM vua la CHON (badgenius chi phu
33.1% thoi luong). Cua so may nam ngoai vung nguoi chon la phim khong duoc
chon, khong phai loi. Xem N1a/N1b/N1d.

Dung:
    python tools/score_windows.py <project> [--baseline shot|film]
"""
from __future__ import annotations
import argparse, io, json, os, statistics, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

IOU_BAR, UNCOVERED_BAR = 0.5, 0.05
PASS_SHARE, STYLE_DELTA = 0.60, 0.15


def pt(ts) -> float:
    p = [float(x) for x in str(ts).split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def iou(a, b):
    lo, hi = max(a[0], b[0]), min(a[1], b[1])
    inter = max(0.0, hi - lo)
    union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return (inter / union if union > 0 else 0.0), inter


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--baseline", choices=["shot", "film"], default=None,
                    help="thay cua so may bang baseline suy bien de kiem tra "
                         "thuoc do co phan biet duoc khong")
    a = ap.parse_args()
    pdir = config.project_dir(a.project)

    hs = json.load(io.open(pdir / "shots.json", encoding="utf-8-sig"))["shots"]
    H = [(pt(s["clip_start"]), pt(s["clip_end"]), s.get("id", f"#{i}"))
         for i, s in enumerate(hs) if s.get("clip_start") and s.get("clip_end")]

    if a.baseline == "shot":
        c = sorted(json.load(io.open(pdir / "_cuts.json", encoding="utf-8"))["cuts"])
        M = [(x, y, f"b{i}") for i, (x, y) in enumerate(zip(c, c[1:]))]
        label = "BASELINE: mot cua so = mot shot may quay"
    elif a.baseline == "film":
        c = sorted(json.load(io.open(pdir / "_cuts.json", encoding="utf-8"))["cuts"])
        M = [(c[0], c[-1], "b0")]
        label = "BASELINE: ca phim la mot cua so"
    else:
        w = json.load(io.open(pdir / "windows.json", encoding="utf-8"))
        M = [(x["start_sec"], x["end_sec"], x["id"]) for x in w["windows"]]
        label = f"windows.json ({w['stats']['n_windows']} cua so)"

    rows, uncovered = [], []
    for h0, h1, hid in H:
        best, bi, binter = 0.0, None, 0.0
        for m0, m1, mid in M:
            if m1 <= h0 or m0 >= h1:
                continue
            v, it = iou((h0, h1), (m0, m1))
            if v > best:
                best, bi, binter = v, (m0, m1, mid), it
        if bi is None:
            uncovered.append((hid, h0, h1))
            rows.append({"hid": hid, "iou": 0.0, "ds": None, "de": None})
        else:
            rows.append({"hid": hid, "iou": best,
                         "ds": abs(bi[0] - h0), "de": abs(bi[1] - h1),
                         "mid": bi[2]})

    n = len(rows)
    hit = sum(1 for r in rows if r["iou"] >= IOU_BAR)
    share = hit / n
    ds = [r["ds"] for r in rows if r["ds"] is not None]
    de = [r["de"] for r in rows if r["de"] is not None]
    unc = len(uncovered) / n

    print(f"=== {a.project} | {label}")
    print(f"cua so nguoi: {n}")
    print(f"IoU >= {IOU_BAR}: {hit}/{n} = {share*100:.1f}%   (bar {PASS_SHARE*100:.0f}%)"
          f"   {'PASS' if share >= PASS_SHARE else 'FAIL'}")
    print(f"IoU trung vi: {statistics.median(r['iou'] for r in rows):.3f}")
    print(f"lech START trung vi: {statistics.median(ds):.2f}s | "
          f"lech END trung vi: {statistics.median(de):.2f}s")
    print(f"KHONG duoc phu: {len(uncovered)}/{n} = {unc*100:.1f}%   "
          f"(bar {UNCOVERED_BAR*100:.0f}%)   "
          f"{'ok' if unc <= UNCOVERED_BAR else 'HARD FAIL'}")
    if uncovered:
        print("  cac khoanh khac draft KHONG the bind vao:")
        for hid, h0, h1 in uncovered[:40]:
            print(f"    {hid}  {h0:8.1f}..{h1:8.1f}")
    lo = [r for r in rows if r["iou"] < IOU_BAR and r["iou"] > 0]
    print(f"phu nhung IoU thap (<{IOU_BAR}): {len(lo)}")
    for r in sorted(lo, key=lambda x: x["iou"])[:10]:
        print(f"    {r['hid']}  IoU {r['iou']:.2f}  ds {r['ds']:.1f} de {r['de']:.1f}")

    io.open(pdir / "windows_score.json", "w", encoding="utf-8").write(json.dumps({
        "project": a.project, "label": label, "n_human": n,
        "iou_ge_bar": hit, "share": share,
        "median_iou": statistics.median(r["iou"] for r in rows),
        "median_start_dist": statistics.median(ds),
        "median_end_dist": statistics.median(de),
        "uncovered": [{"id": h, "start": s, "end": e} for h, s, e in uncovered],
        "rows": rows,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
