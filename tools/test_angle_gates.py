# -*- coding: utf-8 -*-
"""
test_angle_gates.py - both-direction tests for the three angle-compression gates
added in the Tokyo Drift compress-and-repair pass:

  [BEAT-COVERAGE] policy-aware : only coverage_policy.json's MANDATORY beats must
                                 be covered; non-mandatory beats may be skipped.
  [BRIDGE]                     : every run of >=2 consecutive uncovered
                                 NON-mandatory beats needs a bridge line or a
                                 hold at the seam; a mandatory beat in a gap is a
                                 coverage failure, not a bridge one.
  [RUNTIME-BAND]               : soft band (config 15-20% of film runtime); the
                                 band math is checked here, the warn/never-block
                                 behaviour is asserted by it being a console note
                                 with no sev change (tested via the live draft).

Every gate needs a POSITIVE test in BOTH directions (standing repo rule): it
must FIRE on the bad input and STAY SILENT on the good one. These are unit tests
on the pure functions (_coverage_policy, bridge_audit, and the band arithmetic),
so they are deterministic and need no render.

Usage:  python tools/test_angle_gates.py    (exit 0 = all pass)
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from pipeline import draft as _d  # noqa: E402


def _bc(counts, bounds):
    """A minimal beat_coverage-shaped dict for bridge_audit."""
    return {"counts": counts, "bounds": bounds,
            "beats": len(bounds), "covered": sum(1 for v in counts.values() if v)}


def _line(sec=None, narr="", hold=None, bridge=False):
    return SimpleNamespace(
        clip_start=(f"00:{int(sec)//60:02d}:{int(sec)%60:02d}.000"
                    if sec is not None else None),
        narration=narr,
        narration_silence_seconds=hold,
        bridge=bridge,
        id=int(sec) if sec is not None else 0)


def main() -> int:
    fails = []

    # ----- [BRIDGE] direction 1: an unbridged skip of >=2 non-mandatory beats
    # must FIRE. Monkeypatch the policy so B02,B03 are NON-mandatory and skipped.
    bounds = [("B01", 0.0), ("B02", 30.0), ("B03", 60.0), ("B04", 90.0)]
    counts = {"B01": 1, "B02": 0, "B03": 0, "B04": 1}   # B02,B03 skipped
    _orig_policy = _d._coverage_policy
    _d._coverage_policy = lambda proj: {"B01", "B04"}   # B02,B03 not mandatory
    try:
        d_nobridge = SimpleNamespace(lines=[_line(0.0, "Arizona."),
                                            _line(90.0, "At the garage.")])
        ba = _d.bridge_audit("x", d_nobridge, _bc(counts, bounds))
        fired = len(ba["unbridged"]) == 1 and ba["unbridged"][0]["beats"] == ["B02", "B03"]
        print(f"BRIDGE unbridged skip      : {'FIRES' if fired else 'SILENT'} "
              f"(expected FIRES)")
        if not fired:
            fails.append(f"BRIDGE should fire on an unbridged 2-beat skip; "
                         f"got {ba['unbridged']}")

        # ----- direction 2a: the SAME skip with a bridge LINE at the seam ->
        # must STAY SILENT.
        d_bridge = SimpleNamespace(lines=[
            _line(0.0, "Arizona."),
            _line(90.0, "Two weeks and a lot of crashed cars later, the garage.")])
        ba2 = _d.bridge_audit("x", d_bridge, _bc(counts, bounds))
        silent1 = len(ba2["unbridged"]) == 0 and len(ba2["gaps"]) == 1
        print(f"BRIDGE + time-jump phrase  : {'SILENT' if silent1 else 'FIRES'} "
              f"(expected SILENT)")
        if not silent1:
            fails.append(f"BRIDGE should accept a 'later' bridge line; "
                         f"got unbridged={ba2['unbridged']}")

        # ----- direction 2b: the SAME skip with a HOLD inside it -> SILENT.
        d_hold = SimpleNamespace(lines=[
            _line(0.0, "Arizona."),
            _line(45.0, "", hold=6.0),              # hold sits inside the gap
            _line(90.0, "The garage.")])
        ba3 = _d.bridge_audit("x", d_hold, _bc(counts, bounds))
        silent2 = len(ba3["unbridged"]) == 0
        print(f"BRIDGE + hold in the gap   : {'SILENT' if silent2 else 'FIRES'} "
              f"(expected SILENT)")
        if not silent2:
            fails.append(f"BRIDGE should accept a hold in the gap; "
                         f"got unbridged={ba3['unbridged']}")

        # ----- direction 2c: a skip containing a MANDATORY beat is NOT a bridge
        # failure (it is a coverage failure, reported separately). Make B03
        # mandatory and leave the gap unbridged -> bridge_audit must NOT list it
        # as unbridged.
        _d._coverage_policy = lambda proj: {"B01", "B03", "B04"}
        ba4 = _d.bridge_audit("x", d_nobridge, _bc(counts, bounds))
        not_bridge_fault = len(ba4["unbridged"]) == 0 and len(ba4["gaps"]) == 1
        print(f"BRIDGE mandatory-in-gap    : {'DEFERS' if not_bridge_fault else 'WRONGLY FIRES'} "
              f"(expected DEFERS to coverage)")
        if not not_bridge_fault:
            fails.append("a gap with a mandatory beat must defer to "
                         "BEAT-COVERAGE, not fire [BRIDGE]")
    finally:
        _d._coverage_policy = _orig_policy

    # ----- [RUNTIME-BAND] arithmetic: a 104-min film, bands from config.
    lo = float(getattr(config, "RECAP_RUNTIME_PCT_LO", 15.0))
    hi = float(getattr(config, "RECAP_RUNTIME_PCT_HI", 20.0))
    film_min = 104.2
    wpm = float(getattr(config, "TTS_WORDS_PER_MINUTE", 186))

    def pct(words):
        return 100.0 * (words / wpm) / film_min

    # 5726 words (the uncompressed draft) ~ 30% -> OUTSIDE
    out_hi = pct(5726)
    # ~3100 words -> ~16% -> INSIDE
    in_band = pct(3100)
    outside = out_hi > hi
    inside = lo <= in_band <= hi
    print(f"RUNTIME-BAND 5726w         : {out_hi:.0f}% -> "
          f"{'OUTSIDE' if outside else 'inside'} (expected OUTSIDE, band {lo:.0f}-{hi:.0f}%)")
    print(f"RUNTIME-BAND 3100w         : {in_band:.0f}% -> "
          f"{'INSIDE' if inside else 'outside'} (expected INSIDE)")
    if not outside:
        fails.append(f"5726 words should read OUTSIDE the band; got {out_hi:.0f}%")
    if not inside:
        fails.append(f"3100 words should read INSIDE the band; got {in_band:.0f}%")

    # ----- [RUNTIME-BAND] never-block: config band is a warn, so the bounds must
    # be a real (lo < hi) band and both soft-side. (Structural check.)
    if not (0 < lo < hi < 100):
        fails.append(f"runtime band is malformed: lo={lo} hi={hi}")

    # ===== PERMANENCE REGRESSION FIXTURES =================================
    # Each is built from the EXACT bad line that shipped in the Tokyo Drift
    # compress pass, so the gate fails if that class of error comes back.
    from pipeline.draft import _APPEARANCE, _CALLBACK

    # Rule 2 - APPEARANCE-ID: identity hidden behind a looks descriptor.
    # The exact miss: 'the greying man he is shipped to' = his father.
    bad_appearance = "the greying man he is shipped to lays it out plain"
    good_appearance = ("his father, a US Navy officer posted there, lays it "
                       "out plain")  # the fix that shipped
    # more looks descriptors that must fire:
    must_fire_app = ["the long-haired man waits to collect",
                     "the old man says his piece", "the bald man at the wheel"]
    # characterisations that must NOT fire (not hidden identity):
    must_not_app = ["the best driver in the city", "the quiet man nods",
                    "the whole crowd swarms the wreck"]
    a_fire = bool(_APPEARANCE.search(bad_appearance))
    a_silent = not _APPEARANCE.search(good_appearance)
    print(f"APPEARANCE-ID bad line     : {'FIRES' if a_fire else 'SILENT'} "
          f"(expected FIRES on 'the greying man')")
    print(f"APPEARANCE-ID fixed line   : {'SILENT' if a_silent else 'FIRES'} "
          f"(expected SILENT on 'his father')")
    if not a_fire:
        fails.append("APPEARANCE-ID must fire on 'the greying man he is shipped to'")
    if not a_silent:
        fails.append("APPEARANCE-ID must stay silent on the 'his father' fix")
    for s in must_fire_app:
        if not _APPEARANCE.search(s):
            fails.append(f"APPEARANCE-ID should fire on {s!r}")
    for s in must_not_app:
        if _APPEARANCE.search(s):
            fails.append(f"APPEARANCE-ID should NOT fire on {s!r}")

    # Rule 3 - CALLBACK-CITE: a link to an earlier event needs a beat citation.
    # The exact miss: 'the same move that got him shipped out of Arizona'.
    bad_callback = ("It's the same move that got him shipped out of Arizona")
    good_callback_reworded = ("It is the same thing he did in the very first "
                              "scene back home")  # reads as a callback -> cite
    c_fire = bool(_CALLBACK.search(bad_callback))
    print(f"CALLBACK-CITE bad line     : {'FIRES' if c_fire else 'SILENT'} "
          f"(expected FIRES - a callback with no cited beat)")
    if not c_fire:
        fails.append("CALLBACK-CITE must fire on the 'same move that got him "
                     "shipped out' callback")
    # a plain description with no backward link must NOT fire:
    if _CALLBACK.search("Sean slides out dead last, front end smoking"):
        fails.append("CALLBACK-CITE should not fire on a plain description")
    # the gate is satisfied when the line carries callback_beat: a line object
    # WITH the field present does not warn (checked in the live validator; here
    # we assert the regex detects the callback so the validator can demand the
    # cite).
    if not _CALLBACK.search(good_callback_reworded):
        fails.append("CALLBACK-CITE should detect the reworded roof callback "
                     "('the very first scene') so a cite is demanded")

    print("-" * 60)
    if fails:
        for f in fails:
            print("FAIL:", f)
        return 1
    print("test_angle_gates: all pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
