"""Where the film's own track plays, measured on the MIX.

THE DEFECT
----------
`has_film_audio` was ONE boolean for the whole render: if the source had an
audio stream, the separated no-vocals stem played under all 111 lines. Stem
separation is not transparent, and spread across the whole film its artefacts
are a constant processed-sounding bed. Under a race those artefacts sit beneath
engines that are the point of the shot; under a dialogue scene they buy nothing
at all, because the dialogue is exactly what was removed - what is left is
smeared room tone under the narrator.

Rule: the stem plays ONLY inside a run of action/tense lines. Everywhere else
the mix is narration plus music. A <film_speaks> unit is the deliberate
exception and uses the ORIGINAL mix.

Cases
-----
  RUN-RULE             only action/tense lines in a run of MIN_RUN+ qualify;
                       isolated singles and every other tag do not.
  FILM-SPEAKS-EXEMPT   a film_speaks unit is not a stem line and does not
                       break the run it sits inside.
  SPANS-SHRINK         separation covers only those windows, so nothing is
                       separated that will never be heard.
  CORRELATION-DETECTS  the measurement works: a stem mixed in at -17 dB is
                       found, and its absence is found, on real audio - while
                       the RMS barely moves, which is why level cannot be used.
  PLACEMENT-GATE       the verdict catches a stem that leaks where it should
                       not be, one that is missing where it should be, and a
                       render where placement is simply not happening.
  SIGNATURE-PER-LINE   the clip cache key carries the per-line decision, so
                       turning the rule on cannot serve old clips that still
                       have the film audio in them.

Run:  python tools/test_film_audio.py
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
from pipeline import audio_check as ac  # noqa: E402
from pipeline import stems  # noqa: E402


def _ff(*a) -> None:
    subprocess.run([config.ffmpeg(), "-y", "-hide_banner", "-loglevel",
                    "error", *a], check=True, capture_output=True)


def _line(i, tag, a, b, **kw):
    d = {"id": i, "delivery": tag,
         "clip_start": f"00:00:{a:06.3f}".replace("00:00:", "00:00:"),
         "clip_end": f"00:00:{b:06.3f}"}
    d["clip_start"] = "00:%02d:%06.3f" % (int(a) // 60, a % 60)
    d["clip_end"] = "00:%02d:%06.3f" % (int(b) // 60, b % 60)
    d.update(kw)
    return d


def test_run_rule() -> tuple[bool, str]:
    draft = {"lines": [
        _line(1, "normal", 10, 14),
        _line(2, "action", 20, 24),            # isolated single -> NO
        _line(3, "normal", 30, 34),
        _line(4, "action", 40, 44),            # run of 3 -> YES
        _line(5, "tense", 44, 48),
        _line(6, "action", 48, 52),
        _line(7, "sad", 60, 64),
        _line(8, "tense", 70, 74),             # run of 2 -> YES at MIN_RUN=2
        _line(9, "tense", 74, 78),
        _line(10, "reveal", 80, 84),
    ]}
    got = stems.film_audio_lines(draft)
    want = {4, 5, 6, 8, 9}
    if int(config.FILM_AUDIO_MIN_RUN) != 2:
        return False, (f"this case is written for FILM_AUDIO_MIN_RUN=2, "
                       f"config says {config.FILM_AUDIO_MIN_RUN}")
    if got != want:
        return False, f"expected {sorted(want)}, got {sorted(got)}"
    if 2 in got:
        return False, "an isolated action line was given the film's track"
    if got & {1, 3, 7, 10}:
        return False, "a non-action/tense line was given the film's track"
    return True, (f"only action/tense lines in runs of "
                  f"{config.FILM_AUDIO_MIN_RUN}+ qualify "
                  f"({sorted(want)}); the isolated single and every other tag "
                  f"are off")


def test_film_speaks_exempt() -> tuple[bool, str]:
    # a film_speaks unit sits INSIDE an action run: it must not be a stem
    # line, and must not split the run either.
    draft = {"lines": [
        _line(1, "action", 10, 14),
        _line(2, "tense", 14, 18, film_speaks_seconds=4.0),
        _line(3, "action", 18, 22),
    ]}
    got = stems.film_audio_lines(draft)
    if 2 in got:
        return False, ("the film_speaks unit was treated as a stem line - it "
                       "uses the ORIGINAL mix, which is the one place "
                       "un-separated audio belongs")
    if got != {1, 3}:
        return False, (f"the film_speaks unit broke the run around it: "
                       f"expected lines 1 and 3 to qualify, got {sorted(got)}")
    return True, ("a film_speaks unit is not a stem line and does not break "
                  "the run it sits inside")


def test_spans_shrink() -> tuple[bool, str]:
    draft = {"lines": [
        _line(1, "normal", 100, 140),
        _line(2, "normal", 200, 240),
        _line(3, "action", 300, 340),
        _line(4, "action", 340, 380),
    ]}
    sp = stems.needed_spans(draft, src_dur=1000.0)
    total = sum(b - a for a, b in sp)
    if total > 120:
        return False, (f"separation still covers {total:.0f}s - the "
                       f"non-action windows are being separated for nothing")
    if not sp:
        return False, "no spans at all; the action run must be separated"
    lo = min(a for a, b in sp)
    hi = max(b for a, b in sp)
    if lo < 290 or hi > 390:
        return False, (f"spans {lo:.0f}-{hi:.0f}s reach outside the action "
                       f"run (300-380s)")
    return True, (f"separation covers {total:.0f}s around the action run "
                  f"only, not the {80:.0f}s of narration windows as well")


def test_correlation_detects() -> tuple[bool, str]:
    """On real audio: a stem at -17 dB is detectable, and level is not enough."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _ff("-f", "lavfi", "-i", "anoisesrc=d=14:c=pink:r=8000", "-ac", "1",
            str(d / "stem.wav"))
        _ff("-f", "lavfi", "-i", "sine=frequency=330:duration=14", "-ac", "1",
            str(d / "music.wav"))
        _ff("-i", str(d / "music.wav"), "-i", str(d / "stem.wav"),
            "-filter_complex",
            "[1:a]volume=-17dB[s];[0:a][s]amix=inputs=2:duration=shortest:"
            "normalize=0[a]", "-map", "[a]", str(d / "with.wav"))
        s = ac._pcm(d / "stem.wav", 2.0, 4.0)
        cw = ac.correlation(ac._pcm(d / "with.wav", 2.0, 4.0), s)
        cn = ac.correlation(ac._pcm(d / "music.wav", 2.0, 4.0), s)
        if cw < ac.STEM_PRESENT_MIN:
            return False, (f"a stem mixed in at -17 dB measured {cw:.4f}, "
                           f"below the {ac.STEM_PRESENT_MIN} present-bar")
        if cn > ac.STEM_ABSENT_MAX:
            return False, (f"music with NO stem measured {cn:.4f}, above the "
                           f"{ac.STEM_ABSENT_MAX} absent-bar")
        if cw < cn * 4:
            return False, (f"present {cw:.4f} vs absent {cn:.4f} is not a "
                           f"clear enough separation to judge on")
        rw = ac.rms_db(d / "with.wav", 2.0, 4.0)
        rn = ac.rms_db(d / "music.wav", 2.0, 4.0)
        if abs(rw - rn) > 3.0:
            return False, (f"the control is wrong: adding the stem changed "
                           f"RMS by {abs(rw-rn):.1f} dB, so this would not "
                           f"demonstrate why level is insufficient")
        return True, (f"stem present {cw:.3f} vs absent {cn:.3f} "
                      f"({cw/max(cn,1e-6):.0f}x apart) while RMS moves only "
                      f"{abs(rw-rn):.1f} dB - level could not decide this")


def test_placement_gate() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _ff("-f", "lavfi", "-i", "anoisesrc=d=6:c=pink:r=8000", "-ac", "1",
            str(d / "stem.wav"))
        rows = [{"line_id": 1, "final_at": 1.0, "source_at": 1.0,
                 "want": True}]
        # a stem that leaks where it should NOT be: same file, want=False
        bad = [{"line_id": 9, "final_at": 1.0, "source_at": 1.0,
                "want": False}]
        ok, find, _ = ac.check_film_audio_placement(
            d / "stem.wav", d / "stem.wav", bad)
        if ok:
            return False, ("a window that is fully the stem passed as having "
                           "no film audio")
        if "should have NO film audio" not in " ".join(find):
            return False, f"the leak was reported as something else: {find}"
        # missing where it SHOULD be: silence as the "final"
        _ff("-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono", "-t", "6",
            str(d / "silent.wav"))
        ok2, find2, _ = ac.check_film_audio_placement(
            d / "silent.wav", d / "stem.wav", rows)
        if ok2:
            return False, ("a silent mix passed as carrying the film's track "
                           "under an action run")
        if "do NOT carry" not in " ".join(find2):
            return False, f"the absence was reported as something else: {find2}"
        # and a correct render passes
        ok3, find3, _ = ac.check_film_audio_placement(
            d / "stem.wav", d / "stem.wav", rows)
        if not ok3:
            return False, (f"a window that really carries the stem was "
                           f"reported broken: {find3}")
        return True, ("a leaking stem, a missing stem and a correct placement "
                      "are each judged correctly")


def test_signature_per_line() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                  encoding="utf-8").read()
    if "has_film_audio and lid in _fa_ids" not in src:
        return False, ("the per-line decision is not applied; film audio is "
                       "still a render-wide boolean")
    # BOTH the cache signature and the builder must carry it, or a cache hit
    # serves a clip whose audio was built under the old rule.
    n = src.count("film_audio=(has_film_audio")
    if n < 4:
        return False, (f"only {n} of the 4 call sites (2 signatures + 2 "
                       f"builders) use the per-line value; a cache key that "
                       f"ignores it serves clips that still have the film "
                       f"audio in them")
    i = src.find("_fa_ids: set = set()")
    if i < 0:
        return False, ("_fa_ids is not initialised, so a render with no film "
                       "audio available would raise instead of muting")
    return True, ("the per-line decision reaches both clip signatures and "
                  "both builders, so the cache cannot serve clips built under "
                  "the old rule")


TESTS = {
    "RUN-RULE":            test_run_rule,
    "FILM-SPEAKS-EXEMPT":  test_film_speaks_exempt,
    "SPANS-SHRINK":        test_spans_shrink,
    "CORRELATION-DETECTS": test_correlation_detects,
    "PLACEMENT-GATE":      test_placement_gate,
    "SIGNATURE-PER-LINE":  test_signature_per_line,
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
    print("test_film_audio: all pass" if not bad else
          f"test_film_audio: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
