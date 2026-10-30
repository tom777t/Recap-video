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
        # No absolute bars any more: the per-line tails of this measurement
        # overlap on real material, so the verdict is on the distributions.
        # What this case still establishes is that adding the stem MOVES the
        # correlation far more than it moves the level.
        if cw < cn * ac.STEM_SEPARATION_MIN:
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
    """The verdict is on the DISTRIBUTIONS, and it catches a real misplacement.

    The shipped render emitted six PER-LINE findings, every one of them an
    artifact of the alignment defect - line 7 was reported as a leak at 0.033
    and measures 0.020 once aligned. So per-line findings are gone, and this
    case checks the three things that remain: a silent stem is not
    informative, too few informative windows is a SKIP rather than a pass,
    and a genuinely mixed-up placement FAILS.
    """
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _ff("-f", "lavfi", "-i", "anoisesrc=d=40:c=pink:r=8000", "-ac", "1",
            str(d / "stem.wav"))
        _ff("-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono", "-t", "40",
            str(d / "silent.wav"))

        def rows(n, want, src0=0.0):
            return [{"line_id": i, "final_at": src0 + i * 3.0,
                     "source_at": src0 + i * 3.0, "window": 3.0,
                     "want": want} for i in range(1, n + 1)]

        # 1. a SILENT stem is not informative - and must not read as a pass
        ok, find, got, info = ac.check_film_audio_placement(
            d / "stem.wav", d / "silent.wav", rows(8, True) + rows(8, False))
        if info.get("uninformative", 0) < 16:
            return False, (f"a silent stem was treated as informative "
                           f"({info}) - it cannot tell 'not mixed' from "
                           f"'nothing to mix'")
        if "skipped" not in info:
            return False, ("with no informative window the verdict should be "
                           "SKIPPED, not a pass")

        # 2. a real misplacement: the file IS the stem, but every window is
        #    labelled 'off' and none 'on' -> too few samples to judge, SKIP;
        #    with the labels INVERTED on real content it must FAIL.
        on_rows = [{"line_id": i, "final_at": i * 3.0, "source_at": i * 3.0,
                    "window": 3.0, "want": False} for i in range(1, 9)]
        off_rows = [{"line_id": 100 + i, "final_at": i * 3.0,
                     "source_at": i * 3.0 + 15.0, "window": 3.0,
                     "want": True} for i in range(1, 9)]
        ok2, find2, got2, info2 = ac.check_film_audio_placement(
            d / "stem.wav", d / "stem.wav", on_rows + off_rows)
        if ok2:
            return False, (f"a render where the 'off' windows carry the stem "
                           f"and the 'on' windows do not was passed: {info2}")
        if "not placed by the rule" not in " ".join(find2):
            return False, f"reported as something else: {find2}"

        # 3. correct placement passes
        good_on = [{"line_id": i, "final_at": i * 3.0, "source_at": i * 3.0,
                    "window": 3.0, "want": True} for i in range(1, 9)]
        good_off = [{"line_id": 100 + i, "final_at": i * 3.0,
                     "source_at": i * 3.0 + 15.0, "window": 3.0,
                     "want": False} for i in range(1, 9)]
        ok3, find3, got3, info3 = ac.check_film_audio_placement(
            d / "stem.wav", d / "stem.wav", good_on + good_off)
        if not ok3:
            return False, (f"correct placement was rejected: {find3} {info3}")
        return True, (f"a silent stem is uninformative and reads SKIPPED, an "
                      f"inverted placement FAILS ({info2.get('separation')}x), "
                      f"and a correct one passes "
                      f"({info3.get('separation')}x)")


def test_bars_from_real_control() -> tuple[bool, str]:
    """The thresholds must be backed by the real-material control on disk."""
    cp = Path(ROOT) / "config" / "film_audio_control.json"
    if not cp.exists():
        return False, ("config/film_audio_control.json is missing - the "
                       "thresholds have no measured evidence behind them")
    c = json.loads(cp.read_text(encoding="utf-8"))
    w = c.get("whole_draft_corrected") or {}
    if float(c.get("separation_required", 0)) != float(
            ac.STEM_SEPARATION_MIN):
        return False, (f"the control records a required separation of "
                       f"{c.get('separation_required')} but the code uses "
                       f"{ac.STEM_SEPARATION_MIN}")
    if float(c.get("informative_floor_db", 0)) != float(
            ac.STEM_INFORMATIVE_DB):
        return False, "the informative floor disagrees with the control"
    meas = float(w.get("separation", 0))
    if meas <= float(ac.STEM_SEPARATION_MIN):
        return False, (f"the control measured {meas}x on the real render, "
                       f"which does not clear the {ac.STEM_SEPARATION_MIN}x "
                       f"bar it is supposed to justify")
    # the control must record the overlap that rules out a per-line bar
    on_min = float((w.get("on") or {}).get("min", 0))
    off_max = float((w.get("off") or {}).get("max", 0))
    if on_min >= off_max:
        return False, ("the control no longer shows the per-line populations "
                       "overlapping, so the distribution-only verdict would "
                       "need revisiting")
    return True, (f"bars backed by the real control: {meas}x measured against "
                  f"a {ac.STEM_SEPARATION_MIN}x bar, with per-line tails "
                  f"overlapping ({on_min} on-min vs {off_max} off-max)")


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
    "BARS-FROM-REAL-CONTROL": test_bars_from_real_control,
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
