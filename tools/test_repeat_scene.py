"""Does the finished film show the same picture twice? Judged on the frames.

WHY SOURCE BOOKKEEPING IS NOT ENOUGH
------------------------------------
motion_check.reuse compares the SOURCE windows two lines were cut from. That
catches literal reuse of the same footage and it cannot catch what a viewer
notices, because this film is built out of shot/reverse-shot: two DIFFERENT
source windows, minutes apart, can hold a nearly identical frame - the same
character at the same angle in the same room. The bookkeeping says "different
footage" and is correct. The screen says "I have seen this already" and is
also correct.

Cases
-----
  CROP-MEASURED        the letterbox is found by row brightness across the
                       whole file. ffmpeg's own cropdetect got this WRONG here
                       (it was pointed at a window inside the intro, whose
                       frames are black, and reported no bars), and the bars
                       are 24% of every frame - leaving them in drags every
                       hash towards every other hash.
  DETECTS-REAL-REPEAT  a shot really repeated 90s later is found at hamming 0,
                       with the right OUTPUT timestamps. Built by concatenating
                       real footage, not mocked.
  NO-FALSE-POSITIVE    the same footage with nothing repeated reports nothing.
  THRESHOLD-CALIBRATED the bar sits between the measured cross-shot minimum
                       and an exact match, with the evidence on disk.
  FLAT-FRAMES-SKIPPED  fades, flashes and black are near-uniform, all hash
                       alike, and none of them is a repeated scene. They are
                       skipped AND counted, not silently treated as clean.
  ADJACENT-NOT-FLAGGED two samples inside the same shot should match; only
                       pairs more than MIN_GAP_SEC apart are compared.
  CLUSTERS-COLLAPSED   a repeated 4s shot reports once, not sixteen times.
  RENDER-REPORTS       the render runs it and lists output timestamps.

Run:  python tools/test_repeat_scene.py
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from pipeline import dupe_check as dc  # noqa: E402

REAL = Path(config.project_dir("tokyodrift2006")) / "final.mp4"


def _ff(*a) -> None:
    subprocess.run([config.ffmpeg(), "-y", "-hide_banner", "-loglevel",
                    "error", *a], check=True, capture_output=True)


def _letterboxed(path: Path, seconds: float = 30.0,
                 bar: int = 132) -> None:
    """Moving content inside black bars, like the real output."""
    _ff("-f", "lavfi", "-i",
        f"testsrc=size=640x272:rate=30:duration={seconds:.1f}",
        "-vf", f"pad=640:{272 + 2 * bar}:0:{bar}:black",
        "-an", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", str(path))


def test_crop_measured() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "lb.mp4"
        _letterboxed(p, 20.0, bar=100)
        got = dc.content_crop(p)
        if not got:
            return False, "no crop measured on an obviously letterboxed file"
        # expect roughly crop=640:272:0:100
        try:
            body = got.split("=", 1)[1]
            w, h, x, y = (int(v) for v in body.split(":"))
        except (ValueError, IndexError):
            return False, f"unparseable crop: {got}"
        if abs(y - 100) > 6 or abs(h - 272) > 12:
            return False, (f"measured {got}, expected about "
                           f"crop=640:272:0:100")
        return True, f"letterbox measured as {got} on a 100px-bar file"


def test_detects_real_repeat() -> tuple[bool, str]:
    if not REAL.exists():
        return False, "the project's final.mp4 is missing; cannot use real footage"
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        ff = config.ffmpeg()
        _ff("-ss", "60", "-t", "100", "-i", str(REAL), "-an",
            "-c:v", "libx264", "-preset", "ultrafast", str(d / "p1.mp4"))
        _ff("-ss", "70", "-t", "8", "-i", str(REAL), "-an",
            "-c:v", "libx264", "-preset", "ultrafast", str(d / "p2.mp4"))
        lst = d / "l.txt"
        lst.write_text("file '%s'\nfile '%s'\n"
                       % (d.joinpath("p1.mp4").as_posix(),
                          d.joinpath("p2.mp4").as_posix()), encoding="utf-8")
        _ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
            str(d / "dupe.mp4"))
        ok, find, info = dc.check(d / "dupe.mp4")
        if ok:
            return False, ("a shot repeated 90s later was NOT detected "
                           f"(sampled {info.get('sampled')} frames)")
        pairs = info.get("pairs") or []
        if not pairs:
            return False, "reported a finding with no pair behind it"
        best = min(p["distance"] for p in pairs)
        if best > 2:
            return False, (f"the exact repeat measured {best}/64; an identical "
                           f"picture should be near 0")
        if not any(abs(p["gap"] - 90.0) < 12.0 for p in pairs):
            return False, (f"the gap was reported as "
                           f"{[p['gap'] for p in pairs]}, not about 90s")
        if "near-identical" not in find[0] or ":" not in find[0]:
            return False, f"the finding does not give output times: {find[0]}"
        return True, (f"a real shot repeated 90s later is found at "
                      f"hamming {best}/64 with its output timestamps")


def test_no_false_positive() -> tuple[bool, str]:
    if not REAL.exists():
        return False, "the project's final.mp4 is missing"
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _ff("-ss", "60", "-t", "100", "-i", str(REAL), "-an",
            "-c:v", "libx264", "-preset", "ultrafast", str(d / "p1.mp4"))
        ok, find, info = dc.check(d / "p1.mp4")
        if not ok:
            return False, (f"100s of real footage with nothing repeated was "
                           f"flagged: {find[:3]}")
        return True, (f"100s of real footage, {info.get('sampled')} frames "
                      f"sampled, nothing flagged")


def test_threshold_calibrated() -> tuple[bool, str]:
    p = Path(ROOT) / "config" / "dupe_hash_control.json"
    if not p.exists():
        return False, ("config/dupe_hash_control.json is missing - the "
                       "threshold has no measured evidence behind it")
    c = json.loads(p.read_text(encoding="utf-8"))
    for k in ("pairs", "min", "p01", "max_distance"):
        if k not in c:
            return False, f"the control does not record {k}"
    if int(c["pairs"]) < 1000:
        return False, (f"only {c['pairs']} pairs measured; too few to site a "
                       f"threshold on")
    if int(dc.MAX_DISTANCE) != int(c["max_distance"]):
        return False, (f"MAX_DISTANCE is {dc.MAX_DISTANCE} but the control "
                       f"was recorded for {c['max_distance']}")
    if dc.MAX_DISTANCE >= int(c["min"]):
        return False, (f"MAX_DISTANCE {dc.MAX_DISTANCE} is not below the "
                       f"closest measured different-shot pair ({c['min']}), "
                       f"so ordinary cuts would be reported as repeats")
    if dc.MAX_DISTANCE <= 2:
        return False, (f"MAX_DISTANCE {dc.MAX_DISTANCE} only catches an exact "
                       f"match; near-identical shot/reverse-shot is the "
                       f"whole point")
    return True, (f"bar {dc.MAX_DISTANCE} sits between an exact match (0) and "
                  f"the closest of {c['pairs']} measured different-shot pairs "
                  f"({c['min']}); p01 {c['p01']:.0f}")


def test_flat_frames_skipped() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        # 30s of pure black: every frame hashes alike and none is a repeat
        _ff("-f", "lavfi", "-i", "color=c=black:s=320x180:r=30:d=30",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(d / "black.mp4"))
        hs = dc.frame_hashes(d / "black.mp4", 1.0, None)
        if not hs:
            return False, "no frames sampled at all"
        flat = [h for h in hs if h[2] < dc.MIN_VARIANCE]
        if len(flat) < len(hs) - 1:
            return False, (f"only {len(flat)} of {len(hs)} black frames were "
                           f"below the variance floor")
        dupes = dc.near_duplicates(hs)
        if dupes:
            return False, (f"{len(dupes)} pair(s) of BLACK frames reported as "
                           f"repeated scenes - a fade is not a repeat")
        return True, (f"{len(flat)} of {len(hs)} flat frames skipped and "
                      f"counted; no fade reported as a repeat")


def test_adjacent_not_flagged() -> tuple[bool, str]:
    # two samples 1s apart inside one shot are identical BY DESIGN
    hs = [(0.0, 0b1010, 50.0), (1.0, 0b1010, 50.0), (2.0, 0b1010, 50.0)]
    if dc.near_duplicates(hs):
        return False, ("frames one second apart inside the same shot were "
                       "reported as a repeated scene")
    far = [(0.0, 0b1010, 50.0), (dc.MIN_GAP_SEC + 5.0, 0b1010, 50.0)]
    if not dc.near_duplicates(far):
        return False, (f"identical frames {dc.MIN_GAP_SEC + 5:.0f}s apart were "
                       f"NOT reported")
    return True, (f"pairs under {dc.MIN_GAP_SEC:.0f}s apart are the same shot "
                  f"and ignored; beyond it they are reported")


def test_clusters_collapsed() -> tuple[bool, str]:
    # a 5s shot repeated 60s later, sampled every second: 25 frame pairs match
    hs = []
    for i in range(5):
        hs.append((float(i), 0b1111000011110000, 50.0))
    for i in range(5):
        hs.append((60.0 + i, 0b1111000011110000, 50.0))
    for i in range(10):
        hs.append((20.0 + i, 0b0000111100001111 ^ (1 << i), 50.0))
    got = dc.near_duplicates(hs)
    if not got:
        return False, "the repeated 5s shot was not reported at all"
    if len(got) > 2:
        return False, (f"the same repeated shot was reported {len(got)} "
                       f"times; one finding per repeat, or the real ones are "
                       f"buried")
    return True, (f"a 5s shot repeated 60s later reports {len(got)} "
                  f"finding(s), not 25")


def test_render_reports() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    if "[REPEAT-SCENE]" not in src:
        return False, "the render never runs the repeated-scene check"
    if "_dup.check(final)" not in src:
        return False, "the check is not pointed at final.mp4"
    i = src.find("_dup.check(final)")
    # To the end of the block, not a fixed byte count: a `i + 900` window
    # broke as soon as the check also started writing its measurements into
    # final_report.md, failing correct code because lines were added nearby.
    _end = src.find("\n    # ----", i)
    seg = src[i:_end if _end > i else len(src)]
    if "problems.append" not in seg:
        return False, "a finding is printed but not recorded as a problem"
    if "_rep.add(\"REPEAT-SCENE\"" not in seg:
        return False, ("the measurements are not written to the report, so "
                       "the timestamps only exist in the console log")
    if "sys.exit" in seg:
        return False, ("a perceptual-hash finding is fatal; it is a fuzzy "
                       "measure and a false positive must not block a "
                       "publish - it must be visible, not lethal")
    return True, ("the render measures final.mp4, lists output timestamps, "
                  "and records a finding without blocking the publish")


TESTS = {
    "CROP-MEASURED":        test_crop_measured,
    "DETECTS-REAL-REPEAT":  test_detects_real_repeat,
    "NO-FALSE-POSITIVE":    test_no_false_positive,
    "THRESHOLD-CALIBRATED": test_threshold_calibrated,
    "FLAT-FRAMES-SKIPPED":  test_flat_frames_skipped,
    "ADJACENT-NOT-FLAGGED": test_adjacent_not_flagged,
    "CLUSTERS-COLLAPSED":   test_clusters_collapsed,
    "RENDER-REPORTS":       test_render_reports,
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
    print("test_repeat_scene: all pass" if not bad else
          f"test_repeat_scene: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
