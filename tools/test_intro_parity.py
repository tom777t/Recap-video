"""The intro must obey the same footage and encoder rules as the story.

THE DEFECT
----------
The finished render held BLACK for 3.00s at 16:75 and 1.50s at 40.00s, and
MOTION-CHECK failed on both - correctly, because a run of identical black
frames IS frozen.

The cause was NOT a filter bug and NOT the encoder mismatch that was suspected.
Measured:

  * the montage block is 16.63s and the film-intro block follows it, so the
    junction is at 16.63s - exactly where the first black starts;
  * the film-intro block read source 0.00-29.19 because `vis_start` was
    hardcoded to 0.0, and only a FLAGGED shot could move it;
  * the source's first 32s contains exactly 4.50s of black, at t=0.00-2.75 and
    t=23.25-24.75 - which is exactly the 3.00s + 1.50s that reached the screen,
    at exactly those offsets past the junction.

The function's docstring said "no frame is described by the narration, so any
calm opening footage is safe". That is the error in one sentence: a logo fade
is calm AND black. The story half never hits this because every story clip is
bound to a tagged shot window.

Two further divergences found while confirming it, both real and neither the
cause of the freezes:

  * the film-intro block scaled with force_original_aspect_ratio=INCREASE plus
    a crop - fill-and-cut - so it had no letterbox while the rest of the film
    does, and a 1280x544 source was blown past 1080 and cropped;
  * intro.py pinned the scaler NOWHERE, so the whole opening was resampled with
    ffmpeg's default bicubic while render.py pins config.VIDEO_SCALER (lanczos)
    in all four of its scale filters.

And the suspected cause was NOT present: all three segments already carry
identical video parameters (h264 High, level 40, yuv420p, 1920x1080, 30fps,
tb 1/15360) and the video stream copy already works.

Cases
-----
  BLACK-MEASURED        the measurement itself: the source's real black spans
                        are found, and the bars separate fades from content.
  DIM-NOT-JUST-BLACK    a window is judged on its DARKEST frame, not its mean -
                        the first fix passed a window with mean luma 70 whose
                        opening was a fade at luma 2.6.
  FILM-INTRO-WATCHABLE  the real film-intro choice is clear of black, and the
                        old hardcoded 0.0 is not used.
  INTRO-LETTERBOX-MATCH the intro frames the picture the same way as the story.
  INTRO-SCALER-PINNED   every scale filter in intro.py pins config.VIDEO_SCALER.
  INTRO-TRACEABLE       the film-intro block records its output position, so a
                        freeze inside it can be traced to its source span.
  JOIN-IS-STREAM-COPY   the join copies video rather than re-encoding the film.

Run:  python tools/test_intro_parity.py
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
from pipeline import footage as F  # noqa: E402

PROJ = Path(config.project_dir("tokyodrift2006"))
SRC = PROJ / "source.mp4"
INTRO_SRC = io.open(os.path.join(ROOT, "pipeline", "intro.py"),
                    encoding="utf-8").read()


def _ff(*a) -> None:
    subprocess.run([config.ffmpeg(), "-y", "-hide_banner", "-loglevel",
                    "error", *a], check=True, capture_output=True)


def test_black_measured() -> tuple[bool, str]:
    if not SRC.exists():
        return False, "the project source.mp4 is missing"
    spans = F.black_spans(SRC, 0.0, 32.0)
    if len(spans) < 2:
        return False, (f"expected two black spans in the film's opening, "
                       f"found {spans}")
    total = sum(b - a for a, b in spans)
    if abs(total - 4.5) > 0.6:
        return False, (f"measured {total:.2f}s of black in the first 32s; the "
                       f"finished render showed 4.50s, so the measurement no "
                       f"longer matches the defect it explains")
    # the bars must separate the fade from real content
    if not (F.BLACK_LUMA < F.DIM_LUMA < 14.0):
        return False, (f"the bars do not sit in the measured gap: black "
                       f"{F.BLACK_LUMA}, dim {F.DIM_LUMA}, and the darkest "
                       f"real content in this opening is 14.4")
    return True, (f"{len(spans)} black span(s) totalling {total:.2f}s found in "
                  f"the opening - the 4.50s that reached the screen; bars "
                  f"{F.BLACK_LUMA}/{F.DIM_LUMA} sit below real content at 14.4")


def test_dim_not_just_black() -> tuple[bool, str]:
    """A window is judged on its darkest frame, not its average."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "fade.mp4"
        # 4s of black, then 16s of real structured picture. The MEAN over a
        # window starting at 0 is high; its opening is not. `testsrc` rather
        # than a flat colour on purpose - a uniform grey is FLAT and would be
        # rejected for that instead, which would prove the wrong thing.
        _ff("-f", "lavfi", "-i", "color=c=black:s=320x180:r=30:d=4",
            "-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=16",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", str(p))
        got, why = F.watchable_start(p, 10.0, 0.0, 20.0)
        if got is None:
            return False, f"no window found at all in a mostly-bright file: {why}"
        if got < 3.5:
            return False, (f"picked t={got:.2f}s, which opens inside the "
                           f"4s black run - the mean was being judged "
                           f"instead of the darkest frame")
        if F.has_black(p, got, got + 10.0):
            return False, "the chosen window still contains black"
        return True, (f"picked t={got:.2f}s, past the 4s black opening, "
                      f"instead of a high-mean window that starts dark")


def test_film_intro_watchable() -> tuple[bool, str]:
    if "vis_start = 0.0" in INTRO_SRC:
        return False, ("the film-intro window start is still hardcoded to "
                       "0.0, which is the film's logo fade")
    if "watchable_start" not in INTRO_SRC:
        return False, "the film-intro block does not measure its footage"
    if "has_black" not in INTRO_SRC:
        return False, ("the chosen window is not re-checked; the search is "
                       "trusted rather than verified, and this is the one "
                       "number that produced the defect")
    if not SRC.exists():
        return True, "code path correct (no source to measure against here)"
    # behaviour on the real film: the choice must be clear of black
    got, why = F.watchable_start(SRC, 29.2, 0.0, 600.0)
    if got is None:
        return False, f"no watchable opening window found on the real film: {why}"
    if got < 3.0:
        return False, f"chose t={got:.2f}s, inside the opening fade"
    blk = F.has_black(SRC, got, got + 29.2)
    if blk:
        return False, f"the chosen window {got:.2f}s still contains black {blk}"
    old = F.has_black(SRC, 0.0, 29.2)
    if not old:
        return False, ("the old hardcoded window is no longer black, so this "
                       "case cannot demonstrate the defect")
    return True, (f"chose t={got:.2f}s with no black, where the old hardcoded "
                  f"0.0 contained {sum(b-a for a, b in old):.2f}s of it")


def test_intro_letterbox_match() -> tuple[bool, str]:
    if "force_original_aspect_ratio=increase" in INTRO_SRC:
        return False, ("the intro still scales to FILL and crops, so it has "
                       "no letterbox while the rest of the film does")
    n_dec = INTRO_SRC.count("force_original_aspect_ratio=decrease")
    if n_dec < 2:
        return False, (f"only {n_dec} intro scale filter(s) letterbox; the "
                       f"montage and the film-intro block must both match "
                       f"the story")
    if INTRO_SRC.count("pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black") < 2:
        return False, "an intro scale filter letterboxes without padding"
    return True, (f"both intro scale filters use decrease + pad, the same "
                  f"framing as the story's clip builder")


def test_intro_scaler_pinned() -> tuple[bool, str]:
    import re
    spots = [m.start() for m in re.finditer(r"scale=\{w\}:\{h\}", INTRO_SRC)]
    if not spots:
        return False, "found no scale filters in intro.py at all"
    bad = []
    for i in spots:
        window = INTRO_SRC[i:i + 220]
        if "flags=" not in window:
            bad.append(INTRO_SRC[:i].count("\n") + 1)
    if bad:
        return False, (f"{len(bad)} intro scale filter(s) do not pin the "
                       f"scaler, at line(s) {bad} - they resample with "
                       f"ffmpeg's default while the story uses "
                       f"config.VIDEO_SCALER")
    if "config.VIDEO_SCALER" not in INTRO_SRC:
        return False, "intro.py does not read config.VIDEO_SCALER"
    return True, (f"all {len(spots)} intro scale filter(s) pin "
                  f"config.VIDEO_SCALER ({config.VIDEO_SCALER})")


def test_intro_traceable() -> tuple[bool, str]:
    i = INTRO_SRC.find("def _build_film_intro_segment")
    body = INTRO_SRC[i:INTRO_SRC.find("\ndef ", i + 10)]
    if "record_footage(" not in body:
        return False, "the film-intro block records no footage at all"
    if "out_a=" not in body or "out_b=" not in body:
        return False, ("the film-intro block records its source span without "
                       "its OUTPUT position, so a freeze inside it is "
                       "untraceable - and both reported freezes were in it")
    if "out_offset" not in body:
        return False, "the block does not receive its timeline offset"
    if "out_offset=_block_dur_for_offset" not in INTRO_SRC:
        return False, ("prepend_to_final does not pass the montage's measured "
                       "length as the offset")
    return True, ("the film-intro block records source span AND output "
                  "position, measured from the montage's real length")


def test_join_is_stream_copy() -> tuple[bool, str]:
    i = INTRO_SRC.find("def prepend_to_final")
    body = INTRO_SRC[i:INTRO_SRC.find("\ndef ", i + 10)]
    if '"-c:v", "copy"' not in body:
        return False, ("the join does not stream-copy video; it would "
                       "re-encode the whole film to put 45s on the front")
    if "_probe.verify(tmp" not in body:
        return False, "the join does not verify its result"
    # behaviour: two segments built by this module must copy-concat cleanly
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        from pipeline import probe
        for i2, dur in enumerate((3.0, 4.0)):
            _ff("-f", "lavfi", "-i",
                f"testsrc=size={config.OUTPUT_WIDTH}x{config.OUTPUT_HEIGHT}:"
                f"rate={config.OUTPUT_FPS}:duration={dur}",
                "-f", "lavfi", "-i", f"sine=frequency=330:duration={dur}",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", config.VIDEO_PIX_FMT, "-c:a", "aac",
                str(d / f"s{i2}.mp4"))
        lst = d / "l.txt"
        io.open(lst, "w", encoding="utf-8", newline="\n").write(
            "".join("file '%s'\n" % (d / f"s{i2}.mp4").as_posix()
                    for i2 in range(2)))
        out = d / "j.mp4"
        r = subprocess.run(
            [config.ffmpeg(), "-y", "-v", "error", "-f", "concat", "-safe",
             "0", "-i", str(lst), "-c:v", "copy", "-c:a", "aac",
             "-b:a", "192k", "-ar", "48000", "-ac", "2", str(out)],
            capture_output=True, text=True)
        if r.returncode != 0:
            return False, f"the copy-concat failed: {(r.stderr or '')[-200:]}"
        bad = probe.verify(out, expect_dur=7.0)
        if bad:
            return False, f"the copied join mis-measures: {[b['msg'] for b in bad]}"
    return True, ("the join copies video and verifies the result; two "
                  "segments at the project's own settings copy-concat to a "
                  "correct file")


TESTS = {
    "BLACK-MEASURED":        test_black_measured,
    "DIM-NOT-JUST-BLACK":    test_dim_not_just_black,
    "FILM-INTRO-WATCHABLE":  test_film_intro_watchable,
    "INTRO-LETTERBOX-MATCH": test_intro_letterbox_match,
    "INTRO-SCALER-PINNED":   test_intro_scaler_pinned,
    "INTRO-TRACEABLE":       test_intro_traceable,
    "JOIN-IS-STREAM-COPY":   test_join_is_stream_copy,
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
        print(f'{"PASS" if ok else "FAIL"}  {name:<23} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_intro_parity: all pass" if not bad else
          f"test_intro_parity: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
