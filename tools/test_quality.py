"""Picture-quality contract regression tests.

These lock the settings that decide how the render looks. The failure they
prevent is silent: quality is spread over ~6 constants and 4 ffmpeg
invocations, so one changed character degrades every future render and nothing
reports it. Each test here names the setting and why it is what it is.

Cases
-----
  CONTRACT-MATCHES-CONFIG  config.RENDER_QUALITY_CONTRACT agrees with the
                           OUTPUT_* / pix_fmt constants. Changing the output
                           format must be a deliberate two-place edit.
  SETTINGS-LOCKED          the exact values: 1920x1080p30, CRF 20 / medium
                           final, CRF 16 / veryfast intermediates, lanczos,
                           yuv420p. A change fails here with the reason.
  NO-HARDCODED-ENCODES     render.py routes every encode through config - no
                           stray "veryfast" or "yuv420p" literals, which is how
                           a locked setting gets bypassed.
  SCALER-APPLIED           every scale= filter carries flags=<scaler>. A
                           missing one silently falls back to bicubic.
  INTERMEDIATES-BETTER     the intermediate CRF is strictly better than the
                           final CRF. A frame is encoded 3x; if the
                           intermediates are not near-transparent they throw
                           away detail the final encode cannot recover.
  CONTRACT-CATCHES         a file that violates the contract is detected
                           (wrong resolution / wrong fps / missing), built for
                           real with ffmpeg rather than mocked. Bitrate is NOT
                           a criterion: under CRF it tracks scene complexity,
                           and a floor false-fired on a flat test pattern at
                           281 kbit/s - it conflated a simple picture with a
                           broken encode.
  SOURCE-HEADROOM          an upscaled source is reported as upscaled, so
                           "1920x1080" is never read as "a 1080p picture".

Run:  python tools/test_quality.py
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

TMP = Path(ROOT) / "_qtest"

# The locked values, written out so a diff of this file shows what changed.
EXPECT = {
    "OUTPUT_WIDTH": 1920,
    "OUTPUT_HEIGHT": 1080,
    "OUTPUT_FPS": 30,
    "VIDEO_CRF": 20,
    "VIDEO_PRESET": "medium",
    "VIDEO_CRF_INTERMEDIATE": 16,
    "VIDEO_PRESET_INTERMEDIATE": "veryfast",
    "VIDEO_SCALER": "lanczos",
    "VIDEO_PIX_FMT": "yuv420p",
}


def _ff(*args) -> None:
    r = subprocess.run([config.ffmpeg(), "-y", "-hide_banner",
                        "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg: {(r.stderr or '')[-300:]}")


def test_contract_matches_config() -> tuple[bool, str]:
    c = config.RENDER_QUALITY_CONTRACT
    bad = []
    if int(c["width"]) != int(config.OUTPUT_WIDTH):
        bad.append("width")
    if int(c["height"]) != int(config.OUTPUT_HEIGHT):
        bad.append("height")
    if float(c["fps"]) != float(config.OUTPUT_FPS):
        bad.append("fps")
    if c["pix_fmt"] != config.VIDEO_PIX_FMT:
        bad.append("pix_fmt")
    ok = not bad
    return ok, ("the contract tracks the OUTPUT_* constants" if ok else
                f"contract disagrees with config on: {bad}")


def test_settings_locked() -> tuple[bool, str]:
    bad = []
    for k, want in EXPECT.items():
        got = getattr(config, k, None)
        if got != want:
            bad.append(f"{k}={got!r} (locked at {want!r})")
    ok = not bad
    return ok, ("1920x1080p30, CRF 20/medium final, CRF 16/veryfast "
                "intermediates, lanczos, yuv420p" if ok else
                "; ".join(bad) + " - if deliberate, update EXPECT and say why")


def test_no_hardcoded_encodes() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    bad = []
    if '"yuv420p"' in src:
        bad.append('a literal "yuv420p" (use config.VIDEO_PIX_FMT)')
    if '"veryfast"' in src:
        bad.append('a literal "veryfast" (use '
                   'config.VIDEO_PRESET_INTERMEDIATE)')
    if re.search(r'"-crf",\s*"\d', src):
        bad.append("a literal -crf value")
    ok = not bad
    return ok, ("every encode setting comes from config" if ok else
                "render.py contains " + "; ".join(bad))


def test_scaler_applied() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    scales = re.findall(r"scale=\{w\}:\{h\}[^\"']*", src)
    if not scales:
        return False, "found no scale= filters in render.py at all"
    missing = [s for s in scales if "flags=" not in s]
    ok = not missing
    return ok, (f"all {len(scales)} scale= filter(s) pin the scaler" if ok else
                f"{len(missing)} scale= filter(s) have no flags= and would "
                f"fall back to bicubic: {missing[:2]}")


def test_intermediates_better() -> tuple[bool, str]:
    i = int(config.VIDEO_CRF_INTERMEDIATE)
    f = int(config.VIDEO_CRF)
    ok = i < f
    return ok, (f"intermediates at CRF {i} are better than the final CRF {f}, "
                f"so the 3 encode generations do not compound loss" if ok else
                f"intermediate CRF {i} is not better than final CRF {f} - the "
                f"two intermediate encodes discard detail the final cannot "
                f"recover")


def test_contract_catches() -> tuple[bool, str]:
    """Build files that really violate the contract and confirm detection."""
    from pipeline import quality as q
    ffp = config.ffprobe()
    TMP.mkdir(parents=True, exist_ok=True)
    try:
        good = TMP / "good.mp4"
        _ff("-f", "lavfi", "-i",
            f"testsrc=size={config.OUTPUT_WIDTH}x{config.OUTPUT_HEIGHT}"
            f":rate={config.OUTPUT_FPS}:duration=2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", config.VIDEO_PIX_FMT, str(good))
        ok_good, bad_good = q.check_output(ffp, good)
        if not ok_good:
            return False, f"a conforming file was rejected: {bad_good}"

        small = TMP / "small.mp4"
        _ff("-f", "lavfi", "-i",
            f"testsrc=size=1280x720:rate={config.OUTPUT_FPS}:duration=2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", config.VIDEO_PIX_FMT, str(small))
        ok_small, bad_small = q.check_output(ffp, small)
        if ok_small:
            return False, "a 1280x720 file passed the 1920x1080 contract"

        wrong_fps = TMP / "fps.mp4"
        _ff("-f", "lavfi", "-i",
            f"testsrc=size={config.OUTPUT_WIDTH}x{config.OUTPUT_HEIGHT}"
            f":rate=15:duration=2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", config.VIDEO_PIX_FMT, str(wrong_fps))
        ok_fps, _ = q.check_output(ffp, wrong_fps)
        if ok_fps:
            return False, "a 15fps file passed the 30fps contract"

        ok_missing, _ = q.check_output(ffp, TMP / "nope.mp4")
        if ok_missing:
            return False, "a missing file passed the contract"
        return True, ("conforming file passes; wrong resolution, wrong frame "
                      "rate and a missing file are all caught")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


def test_source_headroom() -> tuple[bool, str]:
    """An upscaled source must be reported as upscaled, with the real numbers."""
    from pipeline import quality as q
    ffp = config.ffprobe()
    TMP.mkdir(parents=True, exist_ok=True)
    try:
        # the same shape as tokyodrift2006's real source: 1280x544 scope
        src = TMP / "src.mp4"
        _ff("-f", "lavfi", "-i", "testsrc=size=1280x544:rate=24:duration=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", config.VIDEO_PIX_FMT, str(src))
        hd = q.source_headroom(ffp, src)
        if not hd:
            return False, "could not measure source headroom"
        if abs(hd["scale"] - 1.5) > 0.01:
            return False, f"expected a 1.50x upscale, got {hd['scale']:.3f}"
        if (hd["fit_w"], hd["fit_h"]) != (1920, 816):
            return False, (f"expected a 1920x816 picture area, got "
                           f"{hd['fit_w']}x{hd['fit_h']}")
        if hd["bars_px"] != 132:
            return False, f"expected 132px bars, got {hd['bars_px']}"

        native = TMP / "native.mp4"
        _ff("-f", "lavfi", "-i",
            f"testsrc=size={config.OUTPUT_WIDTH}x{config.OUTPUT_HEIGHT}"
            f":rate=24:duration=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", config.VIDEO_PIX_FMT, str(native))
        hn = q.source_headroom(ffp, native)
        if hn["scale"] > 1.01:
            return False, "a native-resolution source was reported as upscaled"
        return True, ("1280x544 is reported as a 1.50x upscale to 1920x816 "
                      "with 132px bars; a native source is not")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


TESTS = {
    "CONTRACT-MATCHES-CONFIG": test_contract_matches_config,
    "SETTINGS-LOCKED":         test_settings_locked,
    "NO-HARDCODED-ENCODES":    test_no_hardcoded_encodes,
    "SCALER-APPLIED":          test_scaler_applied,
    "INTERMEDIATES-BETTER":    test_intermediates_better,
    "CONTRACT-CATCHES":        test_contract_catches,
    "SOURCE-HEADROOM":         test_source_headroom,
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
    print("test_quality: all pass" if not bad else
          f"test_quality: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
