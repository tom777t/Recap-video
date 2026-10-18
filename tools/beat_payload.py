# -*- coding: utf-8 -*-
"""
beat_payload.py - in payload cho MOT KHUC phim de mot subagent de xuat beat.

Beat map la buoc duy nhat con lai van do nguoi viet. No can hai thu, va ca hai
deu da co o dang may:
  - CAI GI TREN MAN HINH : `action` cua tung moment trong shots_machine.json
  - AI NOI GI            : transcript.json

Chia theo thoi gian chu khong theo so moment, de ranh gioi khuc la mot moc
thoi gian on dinh - chay lai van ra dung khuc do.

Dung:
    python tools/beat_payload.py <project> <chunk_index> <n_chunks>
"""
from __future__ import annotations
import io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def pt(ts) -> float:
    p = [float(x) for x in str(ts).split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def hms(s: float) -> str:
    s = max(0.0, float(s))
    return f"{int(s)//3600:02d}:{(int(s)%3600)//60:02d}:{int(s)%60:02d}"


def main() -> int:
    proj, k, n = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    pdir = config.project_dir(proj)
    # Trong luong that catalogue may ten la shots_machine.json; trong project
    # may dung de chay gate thi no da duoc dat ten shots.json. Chap nhan ca hai
    # thay vi bat nguoi goi phai nho dang o buoc nao.
    cp = next((p for p in (pdir / "shots_machine.json", pdir / "shots.json")
               if p.exists()), None)
    if cp is None:
        print(f"khong co shots_machine.json hay shots.json trong {pdir}")
        return 1
    S = json.load(io.open(cp, encoding="utf-8-sig"))["shots"]
    lo, hi = pt(S[0]["clip_start"]), pt(S[-1]["clip_end"])
    span = (hi - lo) / n
    a, b = lo + span * (k - 1), lo + span * k
    if k == n:
        b = hi

    segs = []
    tp = pdir / "transcript.json"
    if tp.exists():
        segs = json.load(io.open(tp, encoding="utf-8-sig")).get("segments") or []

    M = [s for s in S if pt(s["clip_end"]) > a and pt(s["clip_start"]) < b]
    print(f"### CHUNK {k} of {n}   {hms(a)} - {hms(b)}   ({len(M)} moments)")
    print(f"### film runs {hms(lo)} - {hms(hi)}")
    print("")
    print("Each moment: TIME | chars | depicts | action")
    print("SPEECH lines under a moment are the transcript inside that window.")
    print("")
    for s in M:
        x0, x1 = pt(s["clip_start"]), pt(s["clip_end"])
        print(f"{s['clip_start'][:8]} | {','.join(s['chars']) or '-'} | "
              f"{','.join(s['depicts'])} | {s['action']}")
        for sp in segs:
            if sp["end"] > x0 and sp["start"] < x1:
                print(f"    SPEECH: {str(sp.get('text','')).strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
