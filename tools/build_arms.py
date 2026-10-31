"""Build the two arms' sub-clip plans, and per-line clips for the blind A/B.

ARM A  split only clauses with real shot EVIDENCE (score > 0).
ARM B  A, plus sequential placement for the zero-score clauses.

The split is the point of the comparison: 48% of placements in the step-2
measurement scored zero, so arm B is where that half is tested rather than
assumed. If B does not beat A, the sequential half is not earning its cuts.

Per-line clips are built for a sample, not a whole render, because the blind
A/B is per line and a 17-minute render per arm would not fit the budget. The
full-render measurements (final-file picture check, cuts per minute) need a
real render and are reported separately.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

import config                                                 # noqa: E402
from pipeline import angle_spec, clause_shots as cs            # noqa: E402
from pipeline import clause_plan as cp, word_times as wt       # noqa: E402

PROJ = Path(ROOT) / "projects" / "tokyodrift2006"
OUT = Path(ROOT) / "config" / "arms_plan.json"


def sec(v):
    return cp.sec(v)


def plans(arm: str) -> dict:
    """{line_id: {segments, play_durs, clauses, scores, edges}}"""
    d = json.load(io.open(PROJ / "draft.json", encoding="utf-8-sig"))
    shots = cp.load_shots(PROJ)
    speech = cp.load_speech(PROJ)
    cuts = wt.load_film_cuts(PROJ)
    spec = angle_spec.load(PROJ)
    anchors = {b for a in spec["anchors"] for b in a["beats"]}
    protect = tuple(config.CLAUSE_PROTECT_DELIVERIES)

    out = {}
    for ln in d["lines"]:
        ok, _ = cs.splittable(ln, anchors, protect)
        if not ok:
            continue
        p = cp.plan_line(ln, shots, speech)
        if not p["split"]:
            continue
        chosen = p["subclips"]
        if arm == "A":
            # keep only clauses with evidence, but a split needs two of them
            chosen = [c for c in chosen if c["score"] > 0]
            if len(chosen) < 2:
                continue
        mp3 = PROJ / f"narration/line_{ln['id']:03d}.mp3"
        if not mp3.exists():
            continue
        words = wt.align(mp3, str(ln["narration"]))
        offs = wt.clause_offsets(words, [{"text": c["clause"]}
                                         for c in chosen])
        a, b = sec(ln["clip_start"]), sec(ln["clip_end"])
        narr_dur = words[-1][2] if words else 0.0
        pc = wt.place_cuts(a, b - a, offs, cuts)
        # one segment per surviving cut edge, plus the first
        kept = [chosen[0]]
        for i, e in enumerate(pc["edges"], start=1):
            if i < len(chosen):
                kept.append(chosen[i])
        if len(kept) < 2:
            continue
        # on-screen duration per segment, from the spoken offsets
        bounds = [0.0] + [e - a for e in pc["edges"]][:len(kept) - 1]
        bounds.append(max(narr_dur, b - a))
        durs = [round(bounds[i + 1] - bounds[i], 3)
                for i in range(len(kept))]
        if any(x < config.CLAUSE_MIN_SUBCLIP_SEC for x in durs):
            continue
        out[ln["id"]] = {
            "segments": [[c["shot"]["a"], c["shot"]["b"]] for c in kept],
            "play_durs": durs,
            "clauses": [c["clause"] for c in kept],
            "scores": [c["score"] for c in kept],
            "edges": pc["edges"], "snapped": pc["snapped"],
            "merged": pc["merged"], "narr_dur": round(narr_dur, 3),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", type=int, default=0,
                    help="build this many sampled per-line clips per arm")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    res = {}
    for arm in ("A", "B"):
        print(f"planning arm {arm} ...", flush=True)
        res[arm] = plans(arm)
        pl = res[arm]
        subs = sum(len(v["segments"]) for v in pl.values())
        snap = sum(v["snapped"] for v in pl.values())
        zero = sum(1 for v in pl.values() for s in v["scores"] if s == 0)
        print(f"  arm {arm}: {len(pl)} lines, {subs} sub-clips "
              f"(+{subs - len(pl)} cuts), {snap} snapped to film cuts, "
              f"{zero} zero-evidence placements")

    ctrl = json.load(io.open(Path(ROOT) / "config" / "cut_rate_control.json",
                             encoding="utf-8"))
    mins = ctrl["ours"]["final.mp4"]["duration_min"]
    base = ctrl["verdict"]["our_cuts_per_min"]
    ceil = ctrl["verdict"]["ceiling_cuts_per_min"]
    refs = ctrl["verdict"]["reference_cuts_per_min"]
    for arm in ("A", "B"):
        added = sum(len(v["segments"]) - 1 for v in res[arm].values())
        rate = base + added / mins
        res[arm + "_rate"] = round(rate, 2)
        print(f"arm {arm}: +{added} cuts -> {rate:.2f} /min "
              f"(base {base}, ceiling {ceil}, references {refs}) "
              + ("OK" if rate <= ceil else "OVER CEILING"))

    json.dump(res, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)
    print(f"written: {os.path.relpath(OUT, ROOT)}")

    if a.clips:
        from pipeline import clause_clip
        ff = config.ffmpeg()
        src = PROJ / "source.mp4"
        # Sample from ARM B's lines, not the A-and-B intersection: A is a
        # subset of B (16 lines against 43), so intersecting would cap the
        # blind test at 16 and the brief asks for 30. Every A line is in B,
        # so A still gets compared wherever it has an opinion.
        shared = sorted(set(res["B"]))
        random.Random(a.seed).shuffle(shared)
        pick = sorted(shared[:a.clips])
        print(f"\nbuilding {len(pick)} sampled line(s) per arm: {pick}")
        outdir = PROJ / "_ab"
        outdir.mkdir(exist_ok=True)
        d = json.load(io.open(PROJ / "draft.json", encoding="utf-8-sig"))
        by = {l["id"]: l for l in d["lines"]}
        made = 0
        for lid in pick:
            mp3 = PROJ / f"narration/line_{lid:03d}.mp3"
            ln = by[lid]
            for arm in ("A", "B"):
                p = res[arm].get(lid)
                if not p:
                    continue
                o = outdir / f"line{lid:03d}_{arm}.mp4"
                if o.exists():
                    continue
                try:
                    clause_clip.build(
                        ff, src, [tuple(s) for s in p["segments"]],
                        p["play_durs"], mp3, p["narr_dur"], o)
                    made += 1
                except Exception as e:
                    print(f"  !! line {lid} arm {arm}: {str(e)[:120]}")
            # the CURRENT picture: one continuous shot, same slot
            o = outdir / f"line{lid:03d}_cur.mp4"
            if not o.exists():
                a0, b0 = sec(ln["clip_start"]), sec(ln["clip_end"])
                try:
                    clause_clip.build(ff, src, [(a0, b0)],
                                      [res["B"][lid]["narr_dur"]], mp3,
                                      res["B"][lid]["narr_dur"], o)
                    made += 1
                except Exception as e:
                    print(f"  !! line {lid} cur: {str(e)[:120]}")
        print(f"built {made} clip(s) in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
