# -*- coding: utf-8 -*-
"""
compare_transcripts.py - doi chieu hai ban transcript cua cung mot phim.

Bon con so, so CHU theo tung 10 phut (de thay doan nao bi mat thoai - do phu
% KHONG noi len dieu do), va hai canh in ra nguyen van de nguoi doc tu phan
xu. Khong cham
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


def words(S, lo=0.0, hi=1e12) -> int:
    import re
    return sum(len(re.findall(r"[A-Za-z0-9']+", str(s.get("text", ""))))
               for s in S if lo <= float(s["start"]) < hi)


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
                     len(longs), 100 * lt / dur, len(loops(S)), words(S)))

    print(f"{'':<34}{'segs':>6}{'words':>7}{'raw%':>7}{'usable%':>9}"
          f"{'>30s':>6}{'their%':>8}{'loops':>7}")
    for n, ns, raw, us, nl, lp, lo, nw in rows:
        print(f"{n:<34}{ns:>6}{nw:>7}{raw:>7.0f}{us:>9.0f}{nl:>6}{lp:>8.0f}"
              f"{lo:>7}")
    # Coverage % is NOT how much dialogue a transcript holds. A VAD transcript
    # fits each segment tight to the speech, so its coverage drops to the
    # share of the film that is speech (25% on Lost in the Stars) while it
    # holds MORE words (7116 against 6799, 20 Nov). Words per 10 minutes is
    # the measure of lost dialogue: a bin where NEW holds much less than OLD
    # is a stretch the new pass dropped.
    print("\nwords per 10 minutes (a drop of a third or more is flagged):")
    lost = 0
    for b in range(0, int(dur) + 1, 600):
        wo, wn = words(So, b, b + 600), words(Sn, b, b + 600)
        if not wo and not wn:
            continue
        flag = "  <<< NEW LOST DIALOGUE" if wo >= 30 and wn < wo * 0.67 \
            else ""
        lost += bool(flag)
        print(f"  {b // 60:>4}m  old {wo:>5}  new {wn:>5}{flag}")
    print(f"  -> {lost} stretch(es) where the new transcript lost dialogue")

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
