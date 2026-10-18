# -*- coding: utf-8 -*-
"""
speech_at.py - in transcript trong mot khoang thoi gian, kem moment bao quanh.

Ton tai vi mot loi cu the: reveal-map may dat R1 (Pat tra tien cho vu danh)
o 01:13:50, la luc Bank PHAN UNG. Su that duoc NOI ra o 01:10:40. Lech 3 phut
10 giay, va cai gate bao ve nham ca doan giua.

Mot "land" phai la lan DAU su that duoc noi hoac duoc cho thay. De tra loi
cau do thi phai doc duoc loi thoai quanh moc nghi ngo - khong doan tu mo ta
hinh anh.

Dung:
    python tools/speech_at.py <project> 01:08:00 01:15:00
"""
from __future__ import annotations
import io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def pt(ts) -> float:
    s = str(ts)
    if s.replace(".", "", 1).isdigit():
        return float(s)
    p = [float(x) for x in s.split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def hms(s: float) -> str:
    return f"{int(s)//3600:02d}:{(int(s)%3600)//60:02d}:{int(s)%60:02d}"


def main() -> int:
    proj, a, b = sys.argv[1], pt(sys.argv[2]), pt(sys.argv[3])
    pdir = config.project_dir(proj)

    segs = []
    tp = pdir / "transcript.json"
    if tp.exists():
        segs = json.load(io.open(tp, encoding="utf-8-sig")).get("segments") or []

    cp = next((p for p in (pdir / "shots_machine.json", pdir / "shots.json")
               if p.exists()), None)
    shots = json.load(io.open(cp, encoding="utf-8-sig"))["shots"] if cp else []

    print(f"=== {hms(a)} - {hms(b)}")
    rows = []
    for s in shots:
        x0, x1 = pt(s["clip_start"]), pt(s["clip_end"])
        if x1 > a and x0 < b:
            rows.append((x0, "SHOT", f"{','.join(s['chars']) or '-'} | "
                                     f"{s['action']}"))
    for sp in segs:
        if sp["end"] > a and sp["start"] < b:
            rows.append((float(sp["start"]), "SAID",
                         str(sp.get("text", "")).strip()))
    if not rows:
        print("  (nothing in range)")
        return 0
    for t, kind, txt in sorted(rows, key=lambda r: (r[0], r[1] != "SHOT")):
        print(f"  {hms(t)} {kind}  {txt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
