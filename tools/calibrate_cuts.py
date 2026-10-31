"""Cut-rate calibration: how fast may the picture change?

THE DEFECT this serves. A line narrates several events while its picture is
one continuous stretch of film, so the picture cannot carry what is said.
Clause-level binding fixes that by cutting inside a line - which means the
edit gets faster, and "faster" needs a ceiling that is measured rather than
guessed. The references are the ceiling: our edit must not cut faster than
recaps the viewer actually likes.

BASIS, because it decides the number. PySceneDetect on a finished recap
counts EVERY cut in the picture - the ones the recapper chose AND the ones
already in the film footage they are showing. Ours is the same mixture, so
the totals are comparable. What is NOT comparable is our clip-join rate
(units per minute of draft), which counts only our own decisions and is
roughly half the total. Both are reported; the bar goes on the total,
because that is what a viewer's eye actually receives.

A second statistic matters as much as the rate: the SHORT TAIL. A sub-clip
too brief to read as a shot is the failure mode of cutting inside a line, so
the floor for a generated sub-clip is taken from how short the references
actually let a shot run - measured at the low percentiles, not the minimum,
since a single frame-accurate flash is noise rather than an edit.
"""
from __future__ import annotations

import io
import json
import os
import statistics as st
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

import config  # noqa: E402

OUT = os.path.join(ROOT, "config", "cut_rate_control.json")


def detect(path: str, threshold: float = 27.0) -> tuple:
    """(cut times, duration) via PySceneDetect's ContentDetector."""
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import ContentDetector
    v = open_video(path)
    sm = SceneManager()
    sm.add_detector(ContentDetector(threshold=threshold))
    sm.detect_scenes(v, show_progress=False)
    scenes = sm.get_scene_list()
    if not scenes:
        return [], 0.0
    cuts = [s[0].get_seconds() for s in scenes][1:]
    dur = scenes[-1][1].get_seconds()
    return cuts, dur


def stats(cuts: list, dur: float) -> dict:
    if len(cuts) < 3 or dur <= 0:
        return {"cuts": len(cuts), "duration_min": round(dur / 60, 2),
                "note": "too few cuts to characterise"}
    bounds = [0.0] + cuts + [dur]
    lens = sorted(b - a for a, b in zip(bounds, bounds[1:]) if b > a)
    n = len(lens)

    def p(q):
        return round(lens[min(n - 1, int(q * n))], 2)
    return {
        "cuts": len(cuts),
        "duration_min": round(dur / 60, 2),
        "cuts_per_min": round(len(cuts) / (dur / 60), 2),
        "shots": n,
        "shot_len_min": round(lens[0], 2),
        "shot_len_p05": p(0.05), "shot_len_p10": p(0.10),
        "shot_len_p25": p(0.25),
        "shot_len_median": round(st.median(lens), 2),
        "shot_len_p75": p(0.75), "shot_len_p90": p(0.90),
        "shot_len_max": round(lens[-1], 2),
        "share_under_1s": round(sum(1 for x in lens if x < 1.0) / n, 3),
        "share_under_2s": round(sum(1 for x in lens if x < 2.0) / n, 3),
        "share_under_3s": round(sum(1 for x in lens if x < 3.0) / n, 3),
    }


def main() -> int:
    refs = {}
    vdir = os.path.join(ROOT, "references", "video")
    if os.path.isdir(vdir):
        for f in sorted(os.listdir(vdir)):
            if f.lower().endswith((".mp4", ".mkv", ".webm")):
                print(f"detecting {f} ...", flush=True)
                c, d = detect(os.path.join(vdir, f))
                refs[f] = stats(c, d)

    ours = {}
    for name, rel in (("final.mp4",
                       "projects/tokyodrift2006/final.mp4"),):
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            print(f"detecting {rel} ...", flush=True)
            c, d = detect(p)
            ours[name] = stats(c, d)

    # Our own edit rate, which is a DIFFERENT quantity from the total cut
    # rate: picture units per narration minute, counting only our decisions.
    own = {}
    dp = os.path.join(ROOT, "projects", "tokyodrift2006", "draft.json")
    if os.path.exists(dp):
        d = json.load(io.open(dp, encoding="utf-8-sig"))
        units = len(d.get("lines") or [])
        o = ours.get("final.mp4") or {}
        mins = o.get("duration_min") or 0
        own = {"picture_units": units,
               "units_per_min": round(units / mins, 2) if mins else None}

    ok = [v for v in refs.values() if v.get("cuts_per_min")]
    rate = sorted(v["cuts_per_min"] for v in ok)
    floors = sorted(v["shot_len_p05"] for v in ok)
    p10s = sorted(v["shot_len_p10"] for v in ok)

    print()
    print(f"{'file':26} {'min':>6} {'cuts':>6} {'c/min':>6} {'p05':>5} "
          f"{'p10':>5} {'med':>6} {'<2s':>6}")
    for k, v in list(refs.items()) + list(ours.items()):
        if not v.get("cuts_per_min"):
            print(f"{k[:26]:26} {v.get('note')}")
            continue
        print(f"{k[:26]:26} {v['duration_min']:6.1f} {v['cuts']:6d} "
              f"{v['cuts_per_min']:6.2f} {v['shot_len_p05']:5.2f} "
              f"{v['shot_len_p10']:5.2f} {v['shot_len_median']:6.2f} "
              f"{100*v['share_under_2s']:5.0f}%")

    verdict = {}
    if rate and ours.get("final.mp4", {}).get("cuts_per_min"):
        ourrate = ours["final.mp4"]["cuts_per_min"]
        # HELD, not auto-maxed. The viewer pinned 31.33 after the first two
        # references; the third (a Vietnamese channel) cuts at 42.95/min with
        # 87% of its shots under two seconds, which would raise an auto-max
        # ceiling by a third. Taking that silently would let the edit chase
        # the fastest channel in the set rather than the band the viewer
        # chose, so the measured max is REPORTED and the ceiling stays where
        # it was put.
        measured_max = rate[-1]
        ceiling = float(getattr(config, "CLAUSE_CUTS_PER_MIN_MAX",
                                measured_max))
        verdict = {
            "reference_cuts_per_min": rate,
            "ceiling_cuts_per_min": ceiling,
            "ceiling_is_held_not_maxed": True,
            "measured_max_cuts_per_min": measured_max,
            "ceiling_note": ("held at the viewer's pinned value; the "
                             "measured max across references is higher and "
                             "is recorded beside it"),
            "our_cuts_per_min": ourrate,
            "headroom_cuts_per_min": round(ceiling - ourrate, 2),
            "sub_clip_floor_sec": max(p10s) if p10s else None,
            "sub_clip_floor_basis": ("the HIGHEST reference p10 shot length - "
                                     "a generated sub-clip should not be "
                                     "shorter than the shortest shots the "
                                     "references routinely use"),
        }
        print()
        print(f"references cut at {rate} /min; ours at {ourrate} /min")
        print(f"CEILING {ceiling} cuts/min, headroom "
              f"{verdict['headroom_cuts_per_min']:+.2f} /min")
        print(f"reference p05 shot lengths {floors}, p10 {p10s}")
        print(f"SUB-CLIP FLOOR {verdict['sub_clip_floor_sec']}s")
        if own:
            print(f"our own edit rate (picture units / min): "
                  f"{own.get('units_per_min')} over {own.get('picture_units')} "
                  f"units - a different quantity from the total cut rate")

    json.dump({
        "instrument": "PySceneDetect ContentDetector(threshold=27.0)",
        "basis_note": ("a finished recap's cut count includes BOTH the "
                       "recapper's cuts and the film's own; ours is the same "
                       "mixture, so the totals compare. Our clip-join rate is "
                       "a different, smaller quantity and is reported "
                       "separately."),
        "references": refs, "ours": ours, "our_edit_rate": own,
        "verdict": verdict,
    }, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"written: {os.path.relpath(OUT, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
