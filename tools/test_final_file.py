"""Does anything MEASURE the finished file? Until this suite, no.

THE DEFECT
----------
A 148 MB final.mp4 shipped with no picture at all from 4:15.8 to 17:34.5 -
798.7 seconds, 13m18.7s - and every gate passed.

    video stream   255.767s   7673 packets @ 30fps
    audio stream  1054.469s
    container     1054.469s

The picture was not frozen, it was ABSENT. freezedetect reported the film
clean because it scanned the 255s of frames that exist and found nothing wrong
with them. The duration gate compared `sum(clip durations) - XFADE*(n-1)`
against that same expression accumulated in a loop, so it could not disagree
with itself. Every check validated the PLAN.

Cases
-----
  SHORT-VIDEO-CAUGHT     a file whose video stream ends early is caught, with
                         the delta named. Built with ffmpeg, not mocked.
  STREAM-NOT-CONTAINER   the verdict reads the STREAMS, not the container
                         header - the header reports the longest stream, which
                         is exactly why the truncated film looked fine.
  PTS-SORTED-FIRST       packets arrive in DECODE order, so B-frames jump
                         forward and back by design. A real hole is found; a
                         clean B-frame file reports nothing.
  XFADE-MEASURES-INPUTS  a clip that lies about its duration cannot truncate
                         the chain any more: the offsets come from measurement.
  XFADE-RETURNS-MEASURED the chain returns the length of the FILE, not of the
                         arithmetic.
  CLIP-SHORT-FATAL       _build_clip/_build_silence_clip verify their own
                         output, so a short clip never reaches the chain.
  RENDER-PROBES-FINAL    the render actually calls the probe, fatally, BEFORE
                         the checks that assume the file is the right length.
  JOIN-VERIFIED          the intro concat measures its result and falls back
                         rather than shipping a mismatched file.

Run:  python tools/test_final_file.py
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from pipeline import probe  # noqa: E402


def _mk(path: Path, v_sec: float, a_sec: float, fps: int = 30,
        bframes: bool = False) -> None:
    """A file whose video and audio lengths are chosen INDEPENDENTLY."""
    extra = [] if bframes else ["-bf", "0"]
    cmd = [config.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
           "-f", "lavfi", "-i",
           f"testsrc=size=320x180:rate={fps}:duration={v_sec:.3f}",
           "-f", "lavfi", "-i", f"sine=frequency=440:duration={a_sec:.3f}",
           "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
           *extra, "-c:a", "aac", str(path)]
    subprocess.run(cmd, check=True, capture_output=True)


def test_short_video_caught() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "short.mp4"
        # the shipped film's proportions, scaled down 4x
        _mk(p, v_sec=64.0, a_sec=263.6)
        bad = probe.verify(p, expect_dur=263.6)
        kinds = {b["what"] for b in bad}
        if "stream-length-mismatch" not in kinds:
            return False, (f"a file with 64s of video under 263.6s of audio "
                           f"was not reported as mismatched (got {kinds})")
        if "short-video" not in kinds:
            return False, ("the video stream was not reported short against "
                           "the expected duration")
        msg = " ".join(b["msg"] for b in bad)
        if "199" not in msg and "-199" not in msg:
            return False, f"the delta was not reported: {msg}"
        # and a correct file is clean
        q = Path(td) / "ok.mp4"
        _mk(q, v_sec=20.0, a_sec=20.0)
        if probe.verify(q, expect_dur=20.0):
            return False, (f"a correct file was reported broken: "
                           f"{probe.verify(q, expect_dur=20.0)}")
        return True, ("a video stream that ends early is caught with its "
                      "delta; a matched file passes")


def test_stream_not_container() -> tuple[bool, str]:
    """The container header reports the LONGEST stream - never trust it."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "short.mp4"
        _mk(p, v_sec=10.0, a_sec=60.0)
        out = subprocess.run(
            [config.ffprobe(), "-v", "error", "-show_entries",
             "format=duration", "-of", "default=nw=1:nk=1", str(p)],
            capture_output=True, text=True)
        container = float((out.stdout or "0").strip())
        st = probe.streams(p)
        if container < 55.0:
            return False, (f"this ffmpeg reports a container duration of "
                           f"{container:.2f}s, so the premise of the test no "
                           f"longer holds")
        if st["video"]["duration"] > 12.0:
            return False, ("probe.streams read the container duration for the "
                           "video stream instead of the stream's own")
        if probe.verify(p, expect_dur=60.0) == []:
            return False, ("the file passed even though its picture stops at "
                           "10s of a 60s film - the container header was "
                           "believed")
        return True, (f"container says {container:.1f}s, the video STREAM "
                      f"says {st['video']['duration']:.1f}s, and the verdict "
                      f"follows the stream")


def test_pts_sorted_first() -> tuple[bool, str]:
    """B-frame reorder is not a defect; a real hole is."""
    with tempfile.TemporaryDirectory() as td:
        # B-frames on: decode order != presentation order
        p = Path(td) / "bf.mp4"
        _mk(p, v_sec=12.0, a_sec=12.0, bframes=True)
        gaps = probe.pts_gaps(p, "v")
        if gaps:
            return False, (f"normal B-frame reordering was reported as "
                           f"{len(gaps)} timestamp defect(s) - the packets "
                           f"are not being sorted before comparison")
        # A REAL hole: drop the frames between 2s and 4s while KEEPING the
        # original timestamps, so the picture genuinely stops advancing for 2s
        # in the middle of the stream. `fps_mode passthrough` is what preserves
        # the PTS; re-timestamping would close the hole and the test would
        # prove nothing.
        hole = Path(td) / "hole.mp4"
        src = Path(td) / "src.mp4"
        _mk(src, 8.0, 8.0)
        r = subprocess.run(
            [config.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(src), "-vf", "select='not(between(t,2,4))'",
             "-fps_mode", "passthrough", "-an",
             "-c:v", "libx264", "-preset", "ultrafast", "-bf", "0",
             "-pix_fmt", "yuv420p", str(hole)], capture_output=True, text=True)
        if r.returncode != 0 or not hole.exists():
            return False, (f"could not build the synthetic hole, so the "
                           f"detection half is unproven: "
                           f"{(r.stderr or '')[-200:]}")
        got = probe.pts_gaps(hole, "v")
        if not got:
            return False, ("a real 2s hole in the middle of the picture was "
                           "NOT detected")
        worst = max(g["gap"] for g in got)
        if worst < 1.5:
            return False, (f"the hole was detected as only {worst:.3f}s, not "
                           f"the ~2s that was cut out")
        return True, (f"B-frame reordering is ignored; a real 2s hole is "
                      f"found ({worst:.2f}s at {got[0]['at']:.2f}s)")


def test_xfade_measures_inputs() -> tuple[bool, str]:
    """A clip that lies about its length cannot truncate the film.

    This is the exact reproduction of the shipped defect: six 5.0s clips
    declared as 6.0s used to return 34.600s and write a file with 5.03s of
    video under 34.600s of audio.
    """
    from pipeline.render import _xfade_single
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        for i in range(4):
            _mk(d / f"c{i}.mp4", 5.0, 5.0)
        clips = [(d / f"c{i}.mp4", 6.0) for i in range(4)]   # all lying
        ret = _xfade_single(config.ffmpeg(), clips, d / "out.mp4")
        st = probe.streams(d / "out.mp4")
        v, a = st["video"], st["audio"]
        if v["duration"] < 15.0:
            return False, (f"the picture was still truncated: {v['duration']:.2f}s "
                           f"of video under {a['duration']:.2f}s of audio")
        if abs(v["duration"] - a["duration"]) > 0.25:
            return False, (f"video {v['duration']:.2f}s vs audio "
                           f"{a['duration']:.2f}s - the streams still diverge")
        if abs(ret - v["duration"]) > 0.25:
            return False, (f"returned {ret:.3f}s but the file is "
                           f"{v['duration']:.3f}s")
        return True, (f"four clips declared 1.0s too long produced a correct "
                      f"{v['duration']:.2f}s file with matching streams")


def test_xfade_returns_measured() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    i = src.find("def _xfade_single")
    j = src.find("def ", i + 10)
    body = src[i:j]
    # Match the STATEMENT, not the prose. A substring search for
    # "return cumulative" hit the comment that explains why it was removed,
    # and failed a correct implementation for documenting itself.
    import re as _re
    if _re.search(r"^\s*return\s+cumulative\s*$", body, _re.M):
        return False, ("_xfade_single still returns the ARITHMETIC total; a "
                       "truncated film is reported at its planned length and "
                       "every downstream clock is wrong")
    if "_probe.streams(out)" not in body:
        return False, "_xfade_single never measures its own output"
    for probe_s in ("using the MEASURED", "real.append"):
        if probe_s not in body:
            return False, ("the offsets are not computed from measured input "
                           "durations")
    return True, ("the chain measures every input, computes its offsets from "
                  "those, and returns the length of the file")


def test_clip_short_fatal() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    if "def _verify_clip" not in src:
        return False, "there is no per-clip verification at all"
    n = src.count("_verify_clip(out, clip_len")
    if n < 2:
        return False, (f"_verify_clip is called {n} time(s); both the narrated "
                       f"clip builder and the hold builder must verify")
    # and the slowed read must be long enough to fill clip_len
    if "_need_src" not in src or "clip_len) / setpts_factor" not in src:
        return False, ("a slowed clip still reads only its window, so a clip "
                       "whose clip_len exceeds its narration need comes out "
                       "short")
    # behaviour: a genuinely short file is rejected
    from pipeline.render import _verify_clip
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "s.mp4"
        _mk(p, 3.0, 9.0)
        try:
            _verify_clip(p, 9.0, "test clip")
        except SystemExit:
            return True, ("both builders verify their output, a slowed read "
                          "is sized to clip_len, and a 3s-video/9s-audio clip "
                          "is rejected")
        return False, ("_verify_clip accepted a clip with 3s of video under "
                       "9s of audio")


def test_render_probes_final() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    i = src.find("[FILE-CHECK]")
    if i < 0:
        return False, "the render never probes final.mp4"
    j = src.find("_probe.verify(final")
    if j < 0:
        return False, "the render describes final.mp4 but never verifies it"
    if "sys.exit(1)" not in src[j:j + 900]:
        return False, "a malformed final.mp4 is reported but not fatal"
    # it must run BEFORE the motion check, which cannot see an absent stream
    m = src.find("from pipeline import motion_check as _mc")
    if m > 0 and j > m:
        return False, ("the file check runs AFTER the motion check; "
                       "freezedetect on a truncated stream reports the film "
                       "clean, so the order matters")
    return True, ("the render measures final.mp4 fatally, before the checks "
                  "that assume it is the right length")


def test_join_verified() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "pipeline", "intro.py"),
                  encoding="utf-8").read()
    i = src.find("def prepend_to_final")
    body = src[i:src.find("def build_intro")]
    if "_probe.verify(tmp" not in body:
        return False, ("the intro join never measures its result, so a "
                       "stream-copy concat that drops the picture is pasted "
                       "straight onto final.mp4")
    if "_join_bad" not in body:
        return False, ("a mis-measured stream-copy does not trigger the "
                       "re-encode fallback")
    if body.count("_probe.verify(tmp") < 2:
        return False, ("the re-encode fallback is not verified, so if both "
                       "paths fail the broken file still ships")
    return True, ("the join verifies the stream-copy, falls back to a "
                  "re-encode when it mis-measures, and refuses to overwrite "
                  "final.mp4 if that is wrong too")


TESTS = {
    "SHORT-VIDEO-CAUGHT":     test_short_video_caught,
    "STREAM-NOT-CONTAINER":   test_stream_not_container,
    "PTS-SORTED-FIRST":       test_pts_sorted_first,
    "XFADE-MEASURES-INPUTS":  test_xfade_measures_inputs,
    "XFADE-RETURNS-MEASURED": test_xfade_returns_measured,
    "CLIP-SHORT-FATAL":       test_clip_short_fatal,
    "RENDER-PROBES-FINAL":    test_render_probes_final,
    "JOIN-VERIFIED":          test_join_verified,
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
        print(f'{"PASS" if ok else "FAIL"}  {name:<24} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_final_file: all pass" if not bad else
          f"test_final_file: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
