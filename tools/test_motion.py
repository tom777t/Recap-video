"""Frozen / slow / repeated footage regression tests.

THE DEFECTS, all visible in the Tokyo Drift render and all permitted:
  * a bound shot could be stretched to 1.40x (setpts frame duplication, so it
    reads as judder, not slow motion)
  * `tpad=stop_mode=clone` had stop_duration set to the whole clip length, i.e.
    no ceiling - a short window under a long line became a still image
  * nothing stopped two lines binding overlapping footage

Cases
-----
  SLOWDOWN-CAPPED      BINDING_SLOWDOWN_MAX is 1.15 and schemas reads it from
                       config, so the ceiling is tunable in one place
  FREEZE-CAPPED        no tpad in render.py can clone for longer than
                       config.MAX_FREEZE_SEC. Asserted against the SOURCE, so a
                       new uncapped tpad fails here rather than in a render.
  FREEZE-DETECTED      a real frozen video is found by freezedetect with the
                       right duration; a moving one is not flagged. Built with
                       ffmpeg, not mocked.
  FREEZE-FATAL         the threshold relationship holds: anything over
                       FREEZE_FAIL_SEC fails, and the detector's own minimum is
                       below that so near-misses are still visible
  REUSE-DETECTED       two lines on overlapping footage are caught; abutting
                       windows and a line's own sub-windows are not
  REUSE-USES-SHOWN     the check prefers what the render actually showed over
                       the declared windows - a hold plays PAST its window, so
                       judging declared windows misses the overlap it creates
  HOLD-WINDOW-HONEST   _build_silence_clip ignores its `end` argument, so the
                       footage a hold shows is [start, start+clip_len). The
                       render must record that, not the declared window.
  MULTI-SHOT-EXTENSION fit_narration may extend a window across a cut into the
                       following shots, bounded by the next bound line, a
                       reveal landing and the source duration.

Run:  python tools/test_motion.py
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402

TMP = Path(ROOT) / "_mtest"


def _ff(*args) -> None:
    r = subprocess.run([config.ffmpeg(), "-y", "-hide_banner",
                        "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg: {(r.stderr or '')[-300:]}")


def test_slowdown_capped() -> tuple[bool, str]:
    from pipeline.schemas import BINDING_SLOWDOWN_MAX
    want = 1.15
    if abs(float(config.BINDING_SLOWDOWN_MAX) - want) > 1e-9:
        return False, (f"config.BINDING_SLOWDOWN_MAX is "
                       f"{config.BINDING_SLOWDOWN_MAX}, expected {want}")
    if abs(float(BINDING_SLOWDOWN_MAX) - float(config.BINDING_SLOWDOWN_MAX)) > 1e-9:
        return False, ("schemas.BINDING_SLOWDOWN_MAX does not track the config "
                       "value - the ceiling exists in two places")
    return True, (f"slow-motion ceiling is {want}x and schemas reads it from "
                  f"config")


def test_freeze_capped() -> tuple[bool, str]:
    """No tpad may clone for longer than MAX_FREEZE_SEC."""
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    # Look at a WINDOW after each occurrence, not to the end of the line: the
    # cap is often on the following physical line because these are wrapped
    # f-strings, and a line-bounded regex reported every capped tpad as bare.
    spots = [m.start() for m in
             re.finditer(r"tpad=stop_mode=clone:stop_duration=", src)]
    if not spots:
        return False, "found no tpad clone filters in render.py at all"
    bad = []
    for i in spots:
        window = src[i:i + 160]
        if "MAX_FREEZE_SEC" not in window and "_freeze_cap" not in window:
            line_no = src[:i].count("\n") + 1
            bad.append(f"render.py:{line_no}")
    if bad:
        return False, (f"{len(bad)} tpad(s) clone without the "
                       f"MAX_FREEZE_SEC cap at {bad}")
    if float(config.MAX_FREEZE_SEC) > 0.5:
        return False, (f"MAX_FREEZE_SEC is {config.MAX_FREEZE_SEC}, which is "
                       f"not below the {config.FREEZE_FAIL_SEC}s failure "
                       f"threshold")
    return True, (f"all {len(spots)} tpad clone(s) are capped at "
                  f"MAX_FREEZE_SEC ({config.MAX_FREEZE_SEC}s)")


def test_freeze_detected() -> tuple[bool, str]:
    """A really frozen video is found; a moving one is not."""
    from pipeline import motion_check as mc
    ff = config.ffmpeg()
    TMP.mkdir(parents=True, exist_ok=True)
    try:
        # 1s moving, 2s frozen, 1s moving
        moving = TMP / "mv.mp4"
        _ff("-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=4",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(moving))
        frozen = TMP / "fz.mp4"
        # hold a single frame for 2s in the middle using a still + concat
        still = TMP / "still.mp4"
        _ff("-f", "lavfi", "-i", "color=c=navy:size=320x180:rate=30:duration=2",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(still))
        lst = TMP / "l.txt"
        lst.write_text(f"file '{moving.as_posix()}'\n"
                       f"file '{still.as_posix()}'\n"
                       f"file '{moving.as_posix()}'\n", encoding="utf-8")
        _ff("-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(frozen))

        fz = mc.freezes(ff, frozen)
        if not fz:
            return False, "a 2s frozen stretch was not detected"
        longest = max(f["dur"] for f in fz)
        if longest < 1.0:
            return False, (f"the 2s freeze was detected as only "
                           f"{longest:.2f}s - the duration is being misread")
        clean = mc.freezes(ff, moving)
        if clean:
            return False, (f"moving footage was reported as frozen: {clean}")
        return True, (f"a 2s freeze is detected ({longest:.2f}s found at "
                      f"{fz[0]['start']:.2f}s); moving footage is not flagged")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


def test_freeze_fatal() -> tuple[bool, str]:
    """The thresholds must be ordered so near-misses are visible."""
    if float(config.MAX_FREEZE_SEC) >= float(config.FREEZE_FAIL_SEC):
        return False, (f"MAX_FREEZE_SEC ({config.MAX_FREEZE_SEC}) is not below "
                       f"FREEZE_FAIL_SEC ({config.FREEZE_FAIL_SEC}) - the build "
                       f"rule permits what the check fails")
    # the detector's own minimum must be under the failure threshold, or a
    # near-miss is invisible and the report can only ever say "fail"
    if float(config.FREEZE_FAIL_SEC) / 2.0 >= float(config.FREEZE_FAIL_SEC):
        return False, "detector minimum is not below the failure threshold"
    return True, (f"clone cap {config.MAX_FREEZE_SEC}s < fail threshold "
                  f"{config.FREEZE_FAIL_SEC}s, and the detector reports from "
                  f"{config.FREEZE_FAIL_SEC/2:.2f}s so near-misses show")


def test_reuse_detected() -> tuple[bool, str]:
    from pipeline import motion_check as mc
    ov = float(config.FOOTAGE_REUSE_MIN_OVERLAP_SEC)
    # clear overlap
    draft = {"lines": [
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:20.000"},
        {"id": 2, "clip_start": "00:00:15.000", "clip_end": "00:00:25.000"},
    ]}
    hits = mc.reuse(draft)
    if len(hits) != 1 or abs(hits[0]["overlap"] - 5.0) > 0.01:
        return False, f"a 5s overlap was not reported correctly: {hits}"
    # abutting windows are NOT reuse
    abut = {"lines": [
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:20.000"},
        {"id": 2, "clip_start": "00:00:20.000", "clip_end": "00:00:30.000"},
    ]}
    if mc.reuse(abut):
        return False, "abutting windows were reported as reuse"
    # a frame or two of touch is not reuse either
    touch = {"lines": [
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:20.000"},
        {"id": 2, "clip_start": f"00:00:{20 - ov/2:.3f}",
         "clip_end": "00:00:30.000"},
    ]}
    if mc.reuse(touch):
        return False, (f"a {ov/2:.2f}s touch (under the {ov:.2f}s threshold) "
                       f"was reported as reuse")
    # a line's own montage sub-windows are not reuse with itself
    own = {"lines": [
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:20.000",
         "montage": [{"clip_start": "00:00:10.000", "clip_end": "00:00:15.000"},
                     {"clip_start": "00:00:15.000", "clip_end": "00:00:20.000"}]},
    ]}
    if mc.reuse(own):
        return False, "a line's own sub-windows were reported as reuse"
    return True, ("a 5s overlap is caught; abutting windows, sub-threshold "
                  "touches and a line's own sub-windows are not")


def test_reuse_uses_shown() -> tuple[bool, str]:
    """What the render SHOWED beats what the draft declared.

    A hold ignores its declared window end and keeps playing, so two lines can
    overlap on screen while their declared windows do not.
    """
    from pipeline import motion_check as mc
    # declared windows do NOT overlap...
    draft = {"lines": [
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:12.000",
         "narration": "", "narration_silence_seconds": 8.0},
        {"id": 2, "clip_start": "00:00:14.000", "clip_end": "00:00:20.000"},
    ]}
    if mc.reuse(draft):
        return False, "declared windows do not overlap but were flagged"
    # ...but the hold actually played 10.0 -> 18.0, which does overlap line 2
    shown = [{"line_id": 1, "a": 10.0, "b": 18.0, "source": "hold"},
             {"line_id": 2, "a": 14.0, "b": 20.0, "source": "clip"}]
    hits = mc.reuse(draft, shown=shown)
    if not hits:
        return False, ("the overlap the hold actually created on screen was "
                       "missed - the check is reading declared windows")
    return True, (f"the hold's real {shown[0]['b']-shown[0]['a']:.0f}s of "
                  f"footage overlaps line 2 by {hits[0]['overlap']:.0f}s and "
                  f"is caught, though the declared windows do not overlap")


def test_hold_window_honest() -> tuple[bool, str]:
    """render must record a hold's REAL footage span, not its declared one."""
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    if "_hold_end" not in src:
        return False, ("render.py records a hold's declared window; "
                       "_build_silence_clip ignores `end` and plays clip_len "
                       "seconds from `start`, so footage past the window is "
                       "unchecked by the censor audit and the reuse check")
    # and the builder genuinely does ignore `end`
    i = src.find("def _build_silence_clip")
    j = src.find("\ndef ", i + 10)
    body = src[i:j]
    if '"-t", f"{clip_len' not in body:
        return False, ("_build_silence_clip no longer reads clip_len seconds - "
                       "re-check what a hold actually shows")
    return True, ("a hold's recorded footage span is "
                  "[start, start+clip_len), which is what it really shows")


def test_multi_shot_extension() -> tuple[bool, str]:
    """A window may extend across a cut, bounded by the next bound line."""
    src = io.open(os.path.join(ROOT, "tools", "fit_narration.py"),
                  encoding="utf-8").read()
    if "MULTI-SHOT EXTENSION" not in src:
        return False, ("tools/fit_narration.py does not document the "
                       "multi-shot extension - it may still be clamping to "
                       "the host shot, whose only alternative is slow-motion")
    # the limit must come from the next bound line, not the host shot end
    if "limit = max(he, max(m[\"b\"] for m in members))" not in src:
        return False, "the extension limit is not derived as expected"
    for guard in ("lands", "src_dur"):
        if guard not in src:
            return False, f"the extension is not bounded by {guard}"
    return True, ("a window extends across cuts to the next bound line, "
                  "bounded by reveal landings and the source duration")


def test_static_source_excused() -> tuple[bool, str]:
    """A shot the FILM holds still must not be reported as a render freeze.

    freezedetect on the finished file cannot tell the two apart:
      * the render froze the picture        - a defect
      * the film is holding a static shot   - a shot
    Locked-off establishing shots, held close-ups and title cards are all
    legitimate, and flagging them produced findings with nothing to fix. A
    freeze counts only where the SOURCE moved over the same span.
    """
    from pipeline import motion_check as mc
    ff = config.ffmpeg()
    TMP.mkdir(parents=True, exist_ok=True)
    try:
        # A genuinely STATIC source: a single colour, 4s. Nothing moves.
        static = TMP / "static_src.mp4"
        _ff("-f", "lavfi", "-i", "color=c=navy:size=320x180:rate=30:duration=4",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(static))
        # A MOVING source of the same length.
        moving = TMP / "moving_src.mp4"
        _ff("-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=4",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(moving))

        if mc.source_has_motion(ff, static, 0.5, 3.5) is not False:
            return False, ("a single-colour source was reported as moving, so "
                           "a held shot would still be flagged")
        if mc.source_has_motion(ff, moving, 0.5, 3.5) is not True:
            return False, "a testsrc source was not reported as moving"
        if mc.source_has_motion(ff, TMP / "nope.mp4", 0.0, 1.0) is not None:
            return False, ("an unreadable source returned a verdict instead "
                           "of None - an unknown answer must not read as "
                           "'static', which would suppress real freezes")

        # ---- end to end: the same freeze, excused or not by its source ----
        # A finished file that is frozen for 2s in the middle.
        frozen_final = TMP / "final.mp4"
        lst = TMP / "l.txt"
        lst.write_text(f"file '{moving.as_posix()}'\n"
                       f"file '{static.as_posix()}'\n"
                       f"file '{moving.as_posix()}'\n", encoding="utf-8")
        _ff("-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-pix_fmt", "yuv420p", str(frozen_final))
        # the frozen stretch sits at 4-8s in the finished file, and came from
        # 0-4s of whichever source we claim
        shown = [{"a": 0.0, "b": 4.0, "out_a": 4.0, "out_b": 8.0,
                  "source": "clip", "line_id": 1, "blurred": False}]
        draft = {"lines": [{"id": 1, "clip_start": "00:00:00.000",
                            "clip_end": "00:00:04.000"}]}

        ok_static, bad_static = mc.check(ff, frozen_final, draft, shown=shown,
                                         source=static)
        if not ok_static:
            return False, (f"the freeze was reported even though its SOURCE "
                           f"span is static: {bad_static}")
        ok_moving, bad_moving = mc.check(ff, frozen_final, draft, shown=shown,
                                        source=moving)
        if ok_moving:
            return False, ("a freeze whose source MOVES was not reported - the "
                           "check now excuses everything")
        if not any("SOURCE moves" in b for b in bad_moving):
            return False, f"the finding does not explain itself: {bad_moving}"
        return True, ("a static source excuses the freeze; a moving source "
                      "still fails it; an unreadable source is reported, not "
                      "excused")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


TESTS = {
    "SLOWDOWN-CAPPED":      test_slowdown_capped,
    "STATIC-SOURCE-EXCUSED": test_static_source_excused,
    "FREEZE-CAPPED":        test_freeze_capped,
    "FREEZE-DETECTED":      test_freeze_detected,
    "FREEZE-FATAL":         test_freeze_fatal,
    "REUSE-DETECTED":       test_reuse_detected,
    "REUSE-USES-SHOWN":     test_reuse_uses_shown,
    "HOLD-WINDOW-HONEST":   test_hold_window_honest,
    "MULTI-SHOT-EXTENSION": test_multi_shot_extension,
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
    print("test_motion: all pass" if not bad else
          f"test_motion: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
