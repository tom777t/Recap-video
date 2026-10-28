"""Censor-criteria and region-placement regression tests.

TWO DEFECTS, one of them silent and serious.

1. OVER-FLAGGING. tokyodrift2006 had 14 shots flagged for blur. A visual
   re-check of all 14 - frames read, not inferred from the catalogue text -
   kept FOUR and dropped TEN. The drops: a bathhouse with men in towels, a
   clothed couple kissing, party guests in cocktail dresses, women pouring
   champagne, a beaten driver with no visible blood, and an overturned car
   whose "blood-smeared face" turned out to be dust (measured: peak red-excess
   26 with zero pixels over 30, against 68 and 3,546 pixels on a frame with
   real blood). Ten of fourteen flags were destroying footage for nothing.

2. EVERY PARTIAL BLUR WAS PLACED WRONG. CensorRegion is documented as "pixel
   coordinates in the ORIGINAL source frame", but the crop was applied AFTER
   the scale+pad to the output canvas and clamped against OUTPUT_WIDTH/HEIGHT.
   The documented units and the implemented units disagreed. On this film the
   error is gross: the source is 1280x544, scaled 1.5x to 1920x816 and padded
   with 132px bars, so a box authored at source y=25 was applied at output
   y=25 - inside the top black bar, blurring nothing.

Cases
-----
  CRITERIA-CONFIGURED   the criteria and the region rules exist and forbid
                        full-frame blur
  REGION-TRANSFORM      source coordinates map to the right output pixels, and
                        a box in the picture area never lands in a bar
  REGION-REQUIRED       a flag with no region is rejected, naming the swap as
                        the remedy
  REGION-SIZE-CAPPED    a region covering most of the frame is reported as the
                        full-frame blur it is
  NO-SPLIT-WITH-REGION  a region-censored clip is never split across shots,
                        because the box only describes one of them
  REAL-FLAGS-CLEAN      the shipped shots.json passes the policy, keeps only
                        blood/gore, and every kept flag has a region

Run:  python tools/test_censor_policy.py
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402

PROJ = "_censortest"

# The ten shots the re-check dropped, kept as the fixture.
DROPPED = ["clip:00:09:26", "clip:00:35:46", "clip:00:36:08", "clip:00:36:16",
           "clip:00:44:01", "clip:00:44:30", "clip:00:45:15", "clip:00:45:27",
           "clip:00:46:20", "clip:01:35:07"]
KEPT = ["clip:00:09:53", "clip:01:02:31", "clip:01:02:46", "clip:01:02:59"]


def _mk(shots: list) -> Path:
    pdir = Path(config.project_dir(PROJ))
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True, exist_ok=True)
    io.open(pdir / "shots.json", "w", encoding="utf-8").write(
        json.dumps({"shots": shots}, indent=2))
    return pdir


def _teardown():
    shutil.rmtree(Path(config.project_dir(PROJ)), ignore_errors=True)


def test_criteria_configured() -> tuple[bool, str]:
    crit = tuple(getattr(config, "CENSOR_CRITERIA", ()))
    if not {"blood/gore", "nudity"} <= set(crit):
        return False, f"CENSOR_CRITERIA is {crit}"
    if getattr(config, "CENSOR_ALLOW_FULL_FRAME", True):
        return False, ("CENSOR_ALLOW_FULL_FRAME is True - a full-frame blur "
                       "loses the shot while still costing the runtime")
    if not getattr(config, "CENSOR_REQUIRE_REGION", False):
        return False, "CENSOR_REQUIRE_REGION is False"
    cap = float(getattr(config, "CENSOR_REGION_MAX_FRACTION", 1.0))
    if not (0.0 < cap <= 0.5):
        return False, f"CENSOR_REGION_MAX_FRACTION is {cap}"
    return True, (f"criteria {crit}; a region is required, full-frame is "
                  f"forbidden, regions capped at {cap:.0%} of frame")


def test_region_transform() -> tuple[bool, str]:
    from pipeline.render import region_to_output
    from pipeline.schemas import CensorRegion
    sw, sh = 1280, 544          # the real source shape
    W, H = int(config.OUTPUT_WIDTH), int(config.OUTPUT_HEIGHT)
    f = min(W / sw, H / sh)
    bar = (H - sh * f) / 2.0

    r = CensorRegion(x=300, y=25, width=220, height=330)
    x, y, w, h = region_to_output(r, sw, sh)
    if abs(x - 300 * f) > 2:
        return False, f"x mapped to {x}, expected about {300*f:.0f}"
    if abs(y - (25 * f + bar)) > 2:
        return False, (f"y mapped to {y}, expected about {25*f+bar:.0f} - the "
                       f"{bar:.0f}px letterbox bar was not accounted for")
    if y < bar:
        return False, (f"y={y} lands inside the {bar:.0f}px top bar, so the "
                       f"blur would cover black and miss the content - this is "
                       f"the original bug")
    # a box at the very top of the PICTURE must sit exactly at the bar edge
    top = CensorRegion(x=0, y=0, width=100, height=100)
    _, ty, _, _ = region_to_output(top, sw, sh)
    if abs(ty - bar) > 2:
        return False, f"a source-top box mapped to y={ty}, expected {bar:.0f}"
    # nothing may escape the canvas
    big = CensorRegion(x=sw - 10, y=sh - 10, width=999, height=999)
    bx, by, bw, bh = region_to_output(big, sw, sh)
    if bx + bw > W or by + bh > H:
        return False, f"an oversized region escaped the canvas: {bx},{by},{bw},{bh}"
    # unknown source size must not invent a transform
    u = region_to_output(r, 0, 0)
    if u[:2] != (300, 25):
        return False, (f"with an unknown source size the coordinates were "
                       f"transformed anyway: {u}")
    return True, (f"source (300,25) -> output ({x},{y}) on a {sw}x{sh} source "
                  f"with {bar:.0f}px bars; clamped to canvas; no transform "
                  f"invented when the source size is unknown")


def test_region_required() -> tuple[bool, str]:
    from pipeline import censor as c
    pdir = _mk([{"id": "s1", "clip_start": "00:00:10.0",
                 "clip_end": "00:00:14.0", "censor": "blur_light"}])
    try:
        probs = c.criteria_problems(pdir, 1280, 544)
        if not probs:
            return False, "a flag with no region was accepted"
        blob = " ".join(probs).lower()
        if "swap" not in blob:
            return False, (f"the finding does not name swapping the shot as "
                           f"the remedy: {probs}")
        # with a region it must pass
        pdir2 = _mk([{"id": "s1", "clip_start": "00:00:10.0",
                      "clip_end": "00:00:14.0", "censor": "blur_light",
                      "censor_region": {"x": 10, "y": 10, "width": 100,
                                        "height": 100}}])
        if c.criteria_problems(pdir2, 1280, 544):
            return False, "a flag WITH a small region was rejected"
        return True, ("a region-less flag is rejected and the finding names "
                      "the swap; a flag with a region passes")
    finally:
        _teardown()


def test_region_size_capped() -> tuple[bool, str]:
    from pipeline import censor as c
    cap = float(config.CENSOR_REGION_MAX_FRACTION)
    pdir = _mk([{"id": "s1", "clip_start": "00:00:10.0",
                 "clip_end": "00:00:14.0", "censor": "blur_light",
                 "censor_region": {"x": 0, "y": 0, "width": 1280,
                                   "height": 544}}])
    try:
        probs = c.criteria_problems(pdir, 1280, 544)
        if not probs:
            return False, (f"a region covering 100% of the frame passed the "
                           f"{cap:.0%} cap")
        return True, (f"a whole-frame 'region' is reported as the full-frame "
                      f"blur it is (cap {cap:.0%})")
    finally:
        _teardown()


def test_no_split_with_region() -> tuple[bool, str]:
    from pipeline.render import _split_points
    from pipeline.schemas import CensorRegion
    cuts = [2.0, 5.0, 8.0, 11.0]
    plain = _split_points(14.0, 12.0, cuts, 0.0, 14.0)
    if len(plain) < 2:
        return False, ("the fixture does not produce a split at all, so it "
                       "cannot test that a region prevents one")
    withreg = _split_points(14.0, 12.0, cuts, 0.0, 14.0,
                            censor_region=CensorRegion(x=1, y=1, width=10,
                                                       height=10))
    if withreg:
        return False, (f"a region-censored clip was split into {len(withreg)} "
                       f"sub-windows; the box only describes the host shot, so "
                       f"the blur would miss the content in the others")
    return True, (f"an uncensored clip splits into {len(plain)} sub-windows; a "
                  f"region-censored one is never split")


def test_real_flags_clean() -> tuple[bool, str]:
    from pipeline import censor as c
    pdir = Path(config.project_dir("tokyodrift2006"))
    if not (pdir / "shots.json").exists():
        return False, "SKIPPED - tokyodrift2006/shots.json not present"
    probs = c.criteria_problems(pdir, 1280, 544)
    if probs:
        return False, f"the shipped flags break the policy: {probs}"
    flagged = c.flagged_shots(pdir)
    ids = sorted(f["key"][0] for f in flagged)
    noreg = [f["key"][0] for f in flagged if not f.get("region")]
    if noreg:
        return False, f"shipped flags with no region: {noreg}"
    doc = json.loads((pdir / "shots.json").read_text(encoding="utf-8-sig"))
    live = {s.get("id") for s in doc["shots"]
            if str(s.get("censor", "none")) != "none"}
    back = sorted(set(DROPPED) & live)
    if back:
        return False, (f"shot(s) the re-check dropped are flagged again: "
                       f"{back}. Those are a bathhouse, clothed kissing, party "
                       f"guests, a beaten driver with no blood, and dust "
                       f"mistaken for blood.")
    missing = sorted(set(KEPT) - live)
    if missing:
        return False, (f"shot(s) with real blood lost their flag: {missing}")
    return True, (f"{len(flagged)} flag(s), all with a region, all blood/gore; "
                  f"the 10 over-flagged shots stay dropped")


TESTS = {
    "CRITERIA-CONFIGURED":  test_criteria_configured,
    "REGION-TRANSFORM":     test_region_transform,
    "REGION-REQUIRED":      test_region_required,
    "REGION-SIZE-CAPPED":   test_region_size_capped,
    "NO-SPLIT-WITH-REGION": test_no_split_with_region,
    "REAL-FLAGS-CLEAN":     test_real_flags_clean,
}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    bad = 0
    for name in want:
        fn = TESTS.get(name)
        if fn is None:
            print(f"?? no such test: {name}")
            continue
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        print(f'{"PASS" if ok else "FAIL"}  {name:<22} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_censor_policy: all pass" if not bad else
          f"test_censor_policy: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
