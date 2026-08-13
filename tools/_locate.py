"""Tim moc dung cho mot shot bi drift.

    python _locate.py <project>                      # liet ke shot + line bind vao
    python _locate.py <project> --find "tu khoa"     # tim tu khoa trong transcript
    python _locate.py <project> --shot shot13        # xem cua so hien tai + line

Quy trinh sua drift (da chay thanh cong cho Shutter Island line 24 va 31):
  1. _locate --shot   xem cua so hien tai va cau narration
  2. _locate --find   tim doan thoai that trong transcript
  3. _peek            trich frame quanh moc do + liet ke cu cat
  4. mo anh xac nhan bang MAT, roi moi dich cua so
  5. lay clip_start/clip_end tu CU CAT that, dung go so tron

Buoc 4 khong bo duoc: transcript va mat do cat chi la suy luan gian tiep.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def pt(t):
    return sum(float(x) * m for x, m in zip(str(t).split(":"), (3600, 60, 1)))


def hms(s):
    return f"{int(s)//3600:02d}:{int(s)%3600//60:02d}:{int(s)%60:02d}"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    proj = sys.argv[1]
    pdir = config.project_dir(proj)

    if "--find" in sys.argv:
        kw = sys.argv[sys.argv.index("--find") + 1].lower()
        segs = json.load(io.open(pdir / "transcript.json", encoding="utf-8-sig"))["segments"]
        hits = [s for s in segs if kw in (s.get("text") or "").lower()]
        print(f"{len(hits)} doan chua '{kw}':")
        for s in hits:
            print(f"  {hms(float(s['start']))}  {(s.get('text') or '').strip()[:86]}")
        return

    truth_p = pdir / "_vision_truth.json"
    truth = json.load(io.open(truth_p, encoding="utf-8")) if truth_p.exists() else {}
    lines = json.load(io.open(pdir / "draft.json", encoding="utf-8-sig"))["lines"]

    want = None
    if "--shot" in sys.argv:
        want = sys.argv[sys.argv.index("--shot") + 1]

    for key, v in sorted(truth.items()):
        if want and key != want:
            continue
        a, b = pt(v["clip_start"]), pt(v["clip_end"])
        bound = [l for l in lines
                 if l.get("clip_start") and a <= pt(l["clip_start"]) < b]
        print(f"\n{key}  {v['clip_start']} -> {v['clip_end']}  ({b-a:.1f}s)")
        print(f"  shot id : {v.get('id')}")
        print(f"  mo ta   : {(v.get('action') or '')[:88]}")
        for l in bound:
            print(f"  line {l.get('id')} : {(l.get('narration') or '')[:88]}")
        if not bound:
            print("  (khong line nao bind vao)")


if __name__ == "__main__":
    main()
