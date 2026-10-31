"""
Calibrate the embedding duplicate threshold instead of asserting one.

    python tools/calibrate_dup.py --project tokyodrift2006

WHY
The first run of shot_match used cosine >= 0.92 as "same angle reused" and
reported 105 duplicate pairs among the 108 shots a binding uses. That is not
a finding, it is a broken threshold: every frame in one film shares a colour
grade, a cast and a lens look, so CLIP cosines between unrelated shots of the
same film sit high and in a narrow band. A bar set by intuition lands inside
that band and flags everything.

So the bar is derived from the data, two ways that have to agree:

  NEGATIVES  all shot-shot pairs that are far apart in the film (>120s) AND
             not pHash-similar. Mostly genuinely different pictures.
  POSITIVES  pairs whose pHash hamming distance is <= 5. The plan already
             accepts that as duplicate, and it is computed from pixels with
             no model involved, so it is independent evidence.

A usable threshold has to sit above almost all negatives and below most
positives. If the two distributions overlap so much that no such value
exists, that is the honest answer and the embedding term should not be used
for duplicate detection at all.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402


def hhmmss(s: str) -> float:
    p = str(s).split(":")
    return (int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
            if len(p) == 3 else float(s))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    a = ap.parse_args()
    pdir = config.project_dir(a.project)
    fdir = pdir / "_fingerprints"
    z = np.load(fdir / "embeddings.npz", allow_pickle=False)
    shot_emb, shot_ids = z["shot_emb"], [str(x) for x in z["shot_ids"]]
    frame_shot, phash = [str(x) for x in z["frame_shot"]], z["phash"]

    raw = json.loads((pdir / "shots.json").read_text(encoding="utf-8"))
    raw = raw["shots"] if isinstance(raw, dict) else raw
    by = {s["id"]: s for s in raw}
    mid = np.array([(hhmmss(by[s]["clip_start"]) + hhmmss(by[s]["clip_end"]))
                    / 2.0 for s in shot_ids])

    ph: dict[str, list[int]] = {}
    for i, sid in enumerate(frame_shot):
        ph.setdefault(sid, []).append(int(phash[i]))

    n = len(shot_ids)
    cos = shot_emb @ shot_emb.T
    iu = np.triu_indices(n, k=1)
    allc = cos[iu]
    dt = np.abs(mid[iu[0]] - mid[iu[1]])

    # pHash hamming between shots = best (smallest) across their frame pairs
    ham = np.empty(len(iu[0]), dtype=np.int16)
    for k, (x, y) in enumerate(zip(*iu)):
        ha, hb = ph.get(shot_ids[x], []), ph.get(shot_ids[y], [])
        ham[k] = (min(bin(p ^ q).count("1") for p in ha for q in hb)
                  if ha and hb else 64)

    pos = allc[ham <= 5]
    neg = allc[(ham > 12) & (dt > 120.0)]
    print(f"pairs: {len(allc)} total | positives (pHash<=5): {len(pos)} "
          f"| negatives (pHash>12 and >120s apart): {len(neg)}")
    if len(pos) == 0:
        print("\nNo pHash duplicates at all in this film, so there are no "
              "positives to calibrate against. The embedding threshold "
              "cannot be set from data here - say so rather than pick one.")
        return 0

    print(f"\n{'':14}{'min':>8}{'p5':>8}{'p50':>8}{'p95':>8}{'p99':>8}{'max':>8}")
    for nm, arr in (("negatives", neg), ("positives", pos), ("all", allc)):
        q = np.percentile(arr, [0, 5, 50, 95, 99, 100])
        print(f"  {nm:<12}" + "".join(f"{v:8.4f}" for v in q))

    # candidate thresholds
    print(f"\n{'thresh':>8}{'neg flagged':>14}{'pos caught':>12}"
          f"{'neg rate':>10}")
    best = None
    for t in np.arange(0.80, 1.001, 0.01):
        nf = int((neg >= t).sum())
        pc = int((pos >= t).sum())
        rate = nf / max(1, len(neg))
        print(f"{t:8.2f}{nf:14d}{pc:12d}{rate:10.4f}")
        # want: <1% of negatives flagged, and still catch most positives
        if rate <= 0.01 and best is None and pc > 0:
            best = (float(t), nf, pc, rate)
    print()
    if best:
        t, nf, pc, rate = best
        print(f"CHOSEN embedding_dup_cosine = {t:.2f}: flags {rate*100:.2f}% "
              f"of known-different pairs ({nf}/{len(neg)}) while still "
              f"catching {pc}/{len(pos)} pHash-confirmed duplicates.")
    else:
        print("NO threshold keeps the false-positive rate under 1% while "
              "catching any pHash duplicate. The distributions overlap, so "
              "embedding similarity cannot stand in for duplicate detection "
              "on this film with this encoder. Report pHash alone.")
    (fdir / "dup_calibration.json").write_text(json.dumps({
        "pairs": int(len(allc)), "positives": int(len(pos)),
        "negatives": int(len(neg)),
        "neg_p99": float(np.percentile(neg, 99)),
        "pos_p5": float(np.percentile(pos, 5)),
        "pos_median": float(np.median(pos)),
        "chosen": (best[0] if best else None),
    }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
