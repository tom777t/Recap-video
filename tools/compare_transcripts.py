# -*- coding: utf-8 -*-
"""
compare_transcripts.py - doi chieu hai ban transcript cua cung mot phim.

Bon con so, va hai canh in ra nguyen van de nguoi doc tu phan xu. Khong cham
diem: mot transcript "tot hon" o ba con so van co the te hon o canh ma phim
can nhat, nen canh phai duoc nhin bang mat.

Dung:
    python tools/compare_transcripts.py <project> --old transcript.json
                                        --new transcript_vad.json
                                        --scene 1082-1109 --scene 4890-5015
"""
from __future__ import annotations
import argparse, io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

MAX_SEG = 30.0
REPEAT = 3


def load(p):
    d = json.load(io.open(p, encoding="utf-8-sig"))
    S = [s for s in (d.get("segments") or [])
         if isinstance(s.get("start"), (int, float))]
    S.sort(key=lambda s: s["start"])
    return d, S


def usable_cov(S, dur):
    good = sorted((float(s["start"]), float(s["end"])) for s in S
                  if float(s["end"]) - float(s["start"]) <= MAX_SEG)
    merged = []
    for x, y in good:
        if merged and x <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], y)
        else:
            merged.append([x, y])
    return sum(y - x for x, y in merged) / dur if dur else 0


def loops(S):
    out, run, prev = [], 1, None
    for s in S:
        t = str(s.get("text", "")).strip().lower()
        if t and t == prev:
            run += 1
        else:
            if prev and run >= REPEAT:
                out.append((prev, run))
            prev, run = t, 1
    if prev and run >= REPEAT:
        out.append((prev, run))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--old", default="transcript.json")
    ap.add_argument("--new", default="transcript_vad.json")
    ap.add_argument("--scene", action="append", default=[])
    a = ap.parse_args()
    pdir = config.project_dir(a.project)

    do, So = load(pdir / a.old)
    dn, Sn = load(pdir / a.new)
    dur = float(do.get("duration") or 0) or max(s["end"] for s in So)

    rows = []
    for name, d, S in (("OLD " + a.old, do, So), ("NEW " + a.new, dn, Sn)):
        longs = [s for s in S if float(s["end"]) - float(s["start"]) > MAX_SEG]
        lt = sum(float(s["end"]) - float(s["start"]) for s in longs)
        rows.append((name, len(S),
                     100 * sum(float(s["end"]) - float(s["start"]) for s in S) / dur,
                     100 * usable_cov(S, dur),
                     len(longs), 100 * lt / dur, len(loops(S))))

    print(f"{'':<34}{'segs':>6}{'raw%':>7}{'usable%':>9}"
          f"{'>30s':>6}{'their%':>8}{'loops':>7}")
    for n, ns, raw, us, nl, lp, lo in rows:
        print(f"{n:<34}{ns:>6}{raw:>7.0f}{us:>9.0f}{nl:>6}{lp:>8.0f}{lo:>7}")

    for name, S in (("OLD", So), ("NEW", Sn)):
        L = loops(S)
        if L:
            print(f"\n{name} repetition loops:")
            for t, n in sorted(L, key=lambda x: -x[1])[:6]:
                print(f"   {n}x  {t[:60]}")

    for sc in a.scene:
        lo, hi = [float(x) for x in sc.split("-")]
        print(f"\n{'='*70}\nSCENE {lo:.0f}-{hi:.0f}s\n{'='*70}")
        for name, S in (("OLD", So), ("NEW", Sn)):
            hit = [s for s in S if float(s["end"]) > lo and float(s["start"]) < hi]
            cov = sum(min(float(s["end"]), hi) - max(float(s["start"]), lo)
                      for s in hit
                      if float(s["end"]) - float(s["start"]) <= MAX_SEG)
            print(f"\n--- {name}: {len(hit)} segment, "
                  f"{100*cov/(hi-lo):.0f}% covered by usable segments")
            for s in hit:
                g = float(s["end"]) - float(s["start"])
                flag = "  <<< GIANT" if g > MAX_SEG else ""
                print(f"   {float(s['start']):7.1f} +{g:5.1f}s  "
                      f"{str(s.get('text','')).strip()[:62]}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
