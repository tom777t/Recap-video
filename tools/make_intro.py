# -*- coding: utf-8 -*-
"""make_intro.py - build the beat-cut music intro (2g) as a short preview.

    python tools/make_intro.py tokyodrift2006
    python tools/make_intro.py tokyodrift2006 --selftest

Renders ONLY the intro montage plus the hook - about 30 seconds - not the
film. The point is to look at the opening without waiting for a full render.
"""
from __future__ import annotations
import argparse, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline import intro as I


def selftest() -> int:
    """Both directions on the one rule that matters: no spoilers."""
    ok = True
    print("### [INTRO-MONTAGE] must reject anything touching the first land")
    land = 1000.0
    good = [(10.0, 20.0), (500.0, 510.0), (980.0, 999.0)]
    cases = [
        ("clips entirely before the land", good, False),
        ("a clip starting exactly AT the land", good + [(1000.0, 1010.0)], True),
        ("a clip after the land", good + [(1200.0, 1210.0)], True),
        ("a clip STRADDLING the land", good + [(995.0, 1005.0)], True),
        ("a clip ending exactly at the land", good + [(990.0, 1000.0)], False),
    ]
    for name, mom, should_fail in cases:
        try:
            I.gate_moments(mom, land)
            failed = False
        except I.IntroSpoiler:
            failed = True
        mark = "OK" if failed == should_fail else "WRONG"
        print("  %-38s %-8s %s" % (name,
                                   "rejected" if failed else "passed", mark))
        if failed != should_fail:
            ok = False

    print()
    print("### a missing intro_music must SKIP, not fail")
    # pick_moments/first_reveal_land are pure; build_intro's skip path is the
    # one branch worth asserting without ffmpeg.
    import tempfile, pathlib, json as _j
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td) / "projects" / "_introskip"
        p.mkdir(parents=True)
        (p / "draft.json").write_text(_j.dumps({"lines": []}), encoding="utf-8")
        _orig = config.project_dir
        config.project_dir = lambda name: p
        try:
            r = I.build_intro("_introskip")
            print("  returned %r -> %s" % (r, "SKIPPED cleanly" if r is None
                                           else "WRONG, expected None"))
            if r is not None:
                ok = False
        finally:
            config.project_dir = _orig

    print()
    print("RESULT:", "ALL SELF-TESTS PASS" if ok else "SELF-TEST FAILURE")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?")
    ap.add_argument("--seconds", type=float, default=30.0,
                    help="cap on the preview length")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.project:
        ap.error("give a project or --selftest")
    try:
        out = I.build_intro(a.project, max_total=a.seconds)
    except I.IntroSpoiler as e:
        print(str(e))
        return 1
    return 0 if out is not None else 0


if __name__ == "__main__":
    sys.exit(main())
