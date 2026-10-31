"""Both directions for clause splitting, planning and [VISUAL-CAPACITY]."""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8")

import config                                                 # noqa: E402
from pipeline import clause_shots as cs                        # noqa: E402
from pipeline import clause_plan as cp                         # noqa: E402

PROJ = Path(ROOT) / "projects" / "tokyodrift2006"


def test_commentary_has_no_picture() -> tuple:
    """A verdict is not an event; an action is."""
    com = ["That is the measure of the man.",
           "He is the only one who had worked it out.",
           "Pride costs him, every time."]
    act = ["He hands the money back.",
           "The car detonates and the crowd scatters.",
           "Twinkie collects fistfuls of cash from the crowd."]
    bad = [c for c in com if cs.is_visual(c)[0]]
    miss = [c for c in act if not cs.is_visual(c)[0]]
    if bad:
        return False, f"commentary counted as a picture: {bad[0]!r}"
    if miss:
        return False, f"an action was not counted: {miss[0]!r}"
    return True, (f"{len(com)} commentary clause(s) carry no picture, "
                  f"{len(act)} action clause(s) do")


def test_unlisted_verbs_still_count() -> tuple:
    """The inverted default is the whole fix - an enumerated list cannot win.

    The first version required a verb from a closed PHYSICAL_VERBS list and
    measured 1.55 events per line where the viewer counted three. These verbs
    are all pictures and none of them are on the list.
    """
    probes = ["The orange car cartwheels down the avenue.",
              "The doors grind and throw sparks down the tarmac.",
              "The crowd swarms his window.",
              "Tyres light up and the smoke swallows the road."]
    missed = [p for p in probes if not cs.is_visual(p)[0]]
    if missed:
        return False, (f"{len(missed)} unlisted-verb picture(s) missed, e.g. "
                       f"{missed[0]!r}")
    return True, f"all {len(probes)} unlisted-verb pictures counted"


def test_split_only_multi_event() -> tuple:
    """One event keeps one shot; two or more may be cut."""
    one = {"id": 1, "narration": "He hands the money back.",
           "clip_start": "00:01:00.000", "clip_end": "00:01:10.000"}
    two = {"id": 2, "clip_start": "00:01:00.000", "clip_end": "00:01:10.000",
           "narration": ("He hands the money back, then the uncle looks up "
                         "and the nephew is told to leave.")}
    if cs.splittable(one)[0]:
        return False, "a single-event line was marked splittable"
    if not cs.splittable(two)[0]:
        return False, f"a three-event line was not: {cs.splittable(two)[1]}"
    return True, (f"1 event -> kept continuous; "
                  f"{cs.visual_events(two['narration'])} events -> splittable")


def test_exclusions_hold_the_frame() -> tuple:
    """Anchors and emotional lines keep continuous footage whatever they say."""
    text = ("He hands the money back, then the uncle looks up and the "
            "nephew is told to leave.")
    base = {"id": 3, "narration": text, "clip_start": "00:01:00.000",
            "clip_end": "00:01:10.000"}
    anchored = dict(base, note="B79")
    emotional = dict(base, delivery="sad")
    if cs.splittable(anchored, {"B79"})[0]:
        return False, "an anchor beat was split"
    if cs.splittable(emotional, set(), ("sad",))[0]:
        return False, "a sad line was split"
    if not cs.splittable(base, {"B01"}, ("tense",))[0]:
        return False, "an ordinary multi-event line was wrongly excluded"
    return True, ("anchor and emotional lines hold the frame; an ordinary "
                  "multi-event line is still splittable")


def test_plan_is_film_order_and_unique() -> tuple:
    """Shots advance with the sentence and are never reused inside a line."""
    if not (PROJ / "shots.json").exists():
        return False, "shots.json missing"
    shots = cp.load_shots(PROJ)
    speech = cp.load_speech(PROJ)
    d = json.load(io.open(PROJ / "draft.json", encoding="utf-8-sig"))
    planned = back = dupe = 0
    for ln in d["lines"]:
        if not cs.splittable(ln)[0]:
            continue
        p = cp.plan_line(ln, shots, speech)
        if not p["split"]:
            continue
        planned += 1
        starts = [s["shot"]["a"] for s in p["subclips"]]
        if starts != sorted(starts):
            back += 1
        if len(set(starts)) != len(starts):
            dupe += 1
    if planned == 0:
        return False, "nothing planned - cannot assert the invariants"
    if back:
        return False, f"{back} line(s) place shots out of film order"
    if dupe:
        return False, f"{dupe} line(s) reuse a shot inside one line"
    return True, (f"{planned} planned line(s): every shot in film order, "
                  f"none reused inside a line")


def test_subclips_respect_the_floor() -> tuple:
    """No planned sub-clip is shorter than the calibrated reference floor."""
    shots = cp.load_shots(PROJ)
    speech = cp.load_speech(PROJ)
    d = json.load(io.open(PROJ / "draft.json", encoding="utf-8-sig"))
    floor = float(config.CLAUSE_MIN_SUBCLIP_SEC)
    short = []
    n = 0
    for ln in d["lines"]:
        if not cs.splittable(ln)[0]:
            continue
        p = cp.plan_line(ln, shots, speech)
        for s in p.get("subclips") or []:
            n += 1
            L = s["shot"]["b"] - s["shot"]["a"]
            if L < floor:
                short.append((ln.get("id"), round(L, 2)))
    if short:
        return False, f"{len(short)} sub-clip(s) under the {floor}s floor: {short[:4]}"
    return True, (f"{n} sub-clip(s), none under the measured {floor}s floor "
                  f"(the floor is not binding here - the catalogue's shots "
                  f"are long, so what needs checking once word timings exist "
                  f"is the ON-SCREEN slice, not the shot)")


def test_visual_capacity_both_ways() -> tuple:
    """The gate fires on an over-stuffed line and not on an ordinary one."""
    d = json.load(io.open(PROJ / "draft.json", encoding="utf-8-sig"))
    hits = cp.visual_capacity(d, PROJ)
    if not hits:
        return False, ("no line exceeds its picture, so this draft cannot "
                       "demonstrate the gate")
    loose = cp.visual_capacity(d, PROJ, tolerance=99)
    if loose:
        return False, "the tolerance is not read - a huge bar still fired"
    tight = cp.visual_capacity(d, PROJ, tolerance=0)
    if len(tight) <= len(hits):
        return False, "a tighter tolerance did not find more lines"
    return True, (f"{len(hits)} line(s) over the calibrated tolerance "
                  f"{config.VISUAL_CAPACITY_TOLERANCE}; 0 at a tolerance of "
                  f"99 and {len(tight)} at 0, so the bar is live")


def test_cut_rate_within_reference_ceiling() -> tuple:
    """The plan must not cut faster than the references the viewer likes."""
    p = Path(ROOT) / "config" / "cut_rate_control.json"
    if not p.exists():
        return False, "config/cut_rate_control.json missing - run calibrate_cuts"
    ctrl = json.loads(p.read_text(encoding="utf-8"))
    v = ctrl.get("verdict") or {}
    mins = ctrl["ours"]["final.mp4"]["duration_min"]
    shots = cp.load_shots(PROJ)
    speech = cp.load_speech(PROJ)
    d = json.load(io.open(PROJ / "draft.json", encoding="utf-8-sig"))
    added = 0
    for ln in d["lines"]:
        if not cs.splittable(ln)[0]:
            continue
        pl = cp.plan_line(ln, shots, speech)
        if pl["split"]:
            added += len(pl["subclips"]) - 1
    new = v["our_cuts_per_min"] + added / mins
    if new > v["ceiling_cuts_per_min"]:
        return False, (f"the plan takes the cut rate to {new:.2f}/min, over "
                       f"the reference ceiling "
                       f"{v['ceiling_cuts_per_min']:.2f}")
    return True, (f"+{added} cuts takes {v['our_cuts_per_min']:.2f} -> "
                  f"{new:.2f} /min, under the reference ceiling "
                  f"{v['ceiling_cuts_per_min']:.2f} "
                  f"(references {v['reference_cuts_per_min']})")


TESTS = {
    "COMMENTARY-NO-PICTURE": test_commentary_has_no_picture,
    "UNLISTED-VERBS":        test_unlisted_verbs_still_count,
    "SPLIT-MULTI-ONLY":      test_split_only_multi_event,
    "EXCLUSIONS-HOLD":       test_exclusions_hold_the_frame,
    "PLAN-FILM-ORDER":       test_plan_is_film_order_and_unique,
    "SUBCLIP-FLOOR":         test_subclips_respect_the_floor,
    "VISUAL-CAPACITY":       test_visual_capacity_both_ways,
    "CUT-RATE-CEILING":      test_cut_rate_within_reference_ceiling,
}


def main() -> int:
    bad = 0
    for name, fn in TESTS.items():
        try:
            ok, msg = fn()
        except Exception as e:                                # pragma: no cover
            ok, msg = False, f"{type(e).__name__}: {e}"
        print(f"{'PASS' if ok else 'FAIL'}  {name:<24} {msg}")
        bad += 0 if ok else 1
    print("-" * 60)
    print(f"test_clause_shots: {'all pass' if not bad else f'{bad} FAILURE(S)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
