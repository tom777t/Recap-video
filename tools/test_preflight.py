"""Capacity pre-flight regression tests.

THE BUG THESE LOCK DOWN
-----------------------
The binding contract (`narration <= window x BINDING_SLOWDOWN_MAX`) was enforced
INSIDE render.py's clip loop. So the first overrunning line raised
BindingViolation mid-render and every other offender stayed invisible:

    BindingViolation, line 11: narration 13.8s > shot capacity 13.4s

That run had 19 overruns. You fixed one, re-ran, met the next. The draft-time
gate could not have caught them either, because at draft time there is no
audio - it estimated from a single words-per-minute figure, and Warren's rate
varies 1.7x across delivery tags (151 WPM on `sad`, 261 on `tense`), so the
estimate was wrong in both directions at once.

The rule these tests enforce: once narration exists, a line that cannot fit its
window is reported by the PRE-FLIGHT, in a complete list, before any clip is
built - never by the render loop.

Cases
-----
  PREFLIGHT-CATCHES   a deliberately overrun line is caught by the pre-flight,
                      the render exits non-zero, and NO clip was built. The
                      in-loop BindingViolation must not be what stops it.
  PREFLIGHT-LISTS-ALL three overrunning lines are all reported in ONE run. This
                      is the actual regression: reporting one at a time is the
                      defect, not the overrun.
  PREFLIGHT-FORMULA   the pre-flight's capacity formula agrees with the one
                      render.py enforces, at the boundary. If they drift, the
                      pre-flight passes a render that then crashes - so this
                      compares them directly instead of trusting the comment
                      that says they match.
  PREFLIGHT-SCOPE     pool / montage / hold / film_speaks / intro-owned lines
                      are NOT judged, matching the set render enforces. Judging
                      more than render enforces would block working renders.
  PREFLIGHT-STALE     a line whose audio no longer matches its text is skipped,
                      not judged against the wrong audio.
  TAG-RATE-BUDGET     the capacity budget uses the calibrated PER-TAG rate, so
                      the same word count gets a longer estimate on `sad` than
                      on `tense`. This is the recalibration that stops the
                      draft gate being wrong in both directions.

Run:  python tools/test_preflight.py
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402

PROJ = "_preflight_test"


def _ff(*args) -> None:
    cmd = [config.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {(r.stderr or '')[-300:]}")


def _voice_mp3(path: Path, seconds: float) -> None:
    seconds = max(0.4, float(seconds))
    _ff("-f", "lavfi", "-i", f"sine=frequency=330:duration={seconds:.3f}",
        "-c:a", "libmp3lame", "-q:a", "4", str(path))


def _dur(p: Path) -> float:
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def _setup(lines: list[dict], audio: dict) -> tuple[Path, dict, list]:
    """Project with a synthetic source + narration of EXACT chosen lengths."""
    pdir = Path(config.project_dir(PROJ))
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True, exist_ok=True)
    _ff("-f", "lavfi", "-i", "testsrc=size=320x180:rate=30:duration=120",
        "-f", "lavfi", "-i", "sine=frequency=220:duration=120",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(pdir / "source.mp4"))
    draft = {"project": PROJ, "title": "Preflight (2026)",
             "target_minutes": 1, "voice": "tts", "lines": lines}
    io.open(pdir / "draft.json", "w", encoding="utf-8").write(
        json.dumps(draft, indent=2))
    ndir = pdir / "narration"
    ndir.mkdir(exist_ok=True)
    narration = []
    for lid, secs in audio.items():
        p = ndir / f"line_{lid:03d}.mp3"
        _voice_mp3(p, secs)
        narration.append((lid, p, _dur(p)))
    return pdir, draft, narration


def _teardown() -> None:
    shutil.rmtree(Path(config.project_dir(PROJ)), ignore_errors=True)


def _bound(lid: int, a: float, b: float, words: int = 10, **kw) -> dict:
    d = {"id": lid, "narration": " ".join(["word"] * words),
         "clip_start": f"00:00:{a:06.3f}", "clip_end": f"00:00:{b:06.3f}",
         "delivery": "normal", "note": f"B{lid:02d}"}
    d.update(kw)
    return d


# --------------------------------------------------------------------------- #
def test_preflight_catches() -> tuple[bool, str]:
    """An overrun stops the render in the PRE-FLIGHT, before any clip."""
    from pipeline.render import render
    from pipeline import intro as _intro
    # 3s window => capacity 4.2s. 9s of audio cannot fit by any slowdown.
    lines = [_bound(1, 10, 18, words=8), _bound(2, 20, 23, words=30)]
    pdir, draft, narration = _setup(lines, {1: 2.0, 2: 9.0})
    _orig = _intro._tts_line
    try:
        try:
            render(PROJ, draft, narration, music=None, captions=False,
                   keep_temp=True, force_clips=True)
        except SystemExit as e:
            if int(getattr(e, "code", 1) or 0) == 0:
                return False, "render exited 0 despite an impossible line"
            work = pdir / "_work"
            built = sorted(work.glob("clip_*.mp4")) if work.exists() else []
            if built:
                return False, (f"pre-flight stopped the render but "
                               f"{len(built)} clip(s) had already been built - "
                               f"it must run before the clip loop")
            return True, ("overrun caught by the pre-flight, exit non-zero, "
                          "zero clips built")
        except Exception as e:
            return False, (f"stopped with {type(e).__name__} instead of the "
                           f"pre-flight's clean exit: {e}")
        return False, "render COMPLETED with a line that cannot fit its window"
    finally:
        _intro._tts_line = _orig
        _teardown()


def test_preflight_lists_all() -> tuple[bool, str]:
    """THE regression: every overrun in one report, not one per run."""
    from pipeline import preflight as pf
    lines = [_bound(1, 10, 18, words=8),       # fits
             _bound(2, 20, 23, words=30),      # overruns
             _bound(3, 30, 33, words=30),      # overruns
             _bound(4, 40, 43, words=30)]      # overruns
    pdir, draft, narration = _setup(
        lines, {1: 2.0, 2: 9.0, 3: 8.0, 4: 7.0})
    try:
        f = pf.capacity_findings(draft, narration)
        ids = sorted(x["line_id"] for x in f)
        if ids != [2, 3, 4]:
            return False, f"expected overruns [2, 3, 4], got {ids}"
        # worst-first, so the biggest problem is the one you read
        if [x["line_id"] for x in f] != [2, 3, 4]:
            return False, f"not sorted worst-first: {[x['line_id'] for x in f]}"
        return True, ("all 3 overruns reported in one pass, worst first; the "
                      "fitting line is not flagged")
    finally:
        _teardown()


def test_preflight_formula() -> tuple[bool, str]:
    """The pre-flight and render.py must agree at the boundary.

    Built by solving for the window that makes a given audio length land
    EXACTLY on capacity, then probing just inside and just outside it. If the
    two formulas disagree anywhere, they disagree here.
    """
    from pipeline import preflight as pf
    from pipeline.render import _lead_for, GAP
    from pipeline.schemas import BINDING_SLOWDOWN_MAX as SM

    narr = 7.0
    w_exact = (narr + GAP) / SM          # the knife edge

    def render_says(window: float) -> bool:
        """True if render.py's in-loop check would raise for this window."""
        need = _lead_for(narr, window) + narr + GAP
        return window > 0 and need > window * SM

    bad = []
    for delta in (-0.5, -0.2, -0.05, -0.01, 0.01, 0.05, 0.2, 0.5):
        window = w_exact + delta
        lines = [_bound(1, 10, 10 + window, words=20)]
        pdir, draft, narration = _setup(lines, {1: narr})
        try:
            # use the measured duration, so both sides see the same number
            real = narration[0][2]
            need = _lead_for(real, window) + real + GAP
            expect = window > 0 and need > window * SM
            got = bool(pf.capacity_findings(draft, narration))
            if got != expect:
                bad.append(f"window {window:.3f}: preflight={got} "
                           f"render={expect}")
        finally:
            _teardown()
    ok = not bad
    return ok, ("pre-flight and render.py agree on both sides of the capacity "
                "boundary" if ok else "; ".join(bad))


def test_preflight_scope() -> tuple[bool, str]:
    """Judge exactly the set render enforces - no more, no less."""
    from pipeline import preflight as pf
    lines = [
        # pool: window resolved at render time from broll.json
        {"id": 1, "narration": " ".join(["w"] * 40), "pool": "A1",
         "delivery": "normal"},
        # montage: segments are scaled to the narration by construction
        {"id": 2, "narration": " ".join(["w"] * 40), "delivery": "normal",
         "montage": [{"clip_start": "00:00:10.0", "clip_end": "00:00:11.0"},
                     {"clip_start": "00:00:12.0", "clip_end": "00:00:13.0"}]},
        # hold and film_speaks carry no narration
        _bound(3, 30, 31, words=0, narration="",
               narration_silence_seconds=3.0),
        _bound(4, 40, 41, words=0, narration="", film_speaks_seconds=3.0),
        # intro-owned: no clip window at all
        {"id": 5, "narration": " ".join(["w"] * 40), "over_montage": True,
         "delivery": "hook"},
        {"id": 6, "narration": " ".join(["w"] * 40), "film_intro": True,
         "delivery": "intro"},
        # a real bound line that DOES overrun, to prove the test can see one
        _bound(7, 50, 53, words=30),
    ]
    pdir, draft, narration = _setup(
        lines, {1: 12.0, 2: 12.0, 3: 0.5, 4: 0.5, 5: 12.0, 6: 12.0, 7: 9.0})
    try:
        ids = sorted(x["line_id"] for x in pf.capacity_findings(draft,
                                                                narration))
        if ids != [7]:
            return False, (f"expected only line 7 judged, got {ids} - "
                           f"pool/montage/hold/film_speaks/intro-owned lines "
                           f"must be out of scope")
        return True, ("pool, montage, hold, film_speaks and intro-owned lines "
                      "are out of scope; the bound overrun is caught")
    finally:
        _teardown()


def test_preflight_stale() -> tuple[bool, str]:
    """Audio that does not match the current text must not be judged.

    After a trim pass the files on disk still hold the old, longer reading.
    Judging those reports overruns the next render has already fixed.
    """
    from pipeline import preflight as pf
    from pipeline.tts import DEFAULT_PROVIDER
    from pipeline.tts_providers import all_providers
    lines = [_bound(1, 10, 13, words=30)]
    pdir, draft, narration = _setup(lines, {1: 9.0})
    try:
        prov = all_providers().get(DEFAULT_PROVIDER)
        if prov is None:
            return False, "no production provider registered"
        ndir = pdir / "narration"
        # a manifest entry for DIFFERENT text = the file is stale
        sig_other = prov.cache_signature("some other words entirely",
                                         "normal", 1.0)
        io.open(ndir / "_cache.json", "w", encoding="utf-8").write(
            json.dumps({"line_001.mp3": sig_other}))
        stale = pf.stale_audio(draft, pdir)
        if stale != [1]:
            return False, f"stale audio not detected, got {stale}"
        if pf.capacity_findings(draft, narration, skip_ids=stale):
            return False, "a stale line was still judged"
        # and with a MATCHING manifest entry it is judged again
        sig_real = prov.cache_signature(str(lines[0]["narration"]),
                                        "normal", 1.0)
        io.open(ndir / "_cache.json", "w", encoding="utf-8").write(
            json.dumps({"line_001.mp3": sig_real}))
        if pf.stale_audio(draft, pdir) != []:
            return False, "fresh audio was reported stale"
        if not pf.capacity_findings(draft, narration):
            return False, "fresh overrunning line was not judged"
        return True, ("stale audio is skipped; the same line is judged once "
                      "its manifest matches")
    finally:
        _teardown()


def test_tag_rate_budget() -> tuple[bool, str]:
    """The capacity budget must use the calibrated PER-TAG rate.

    A flat words-per-minute treated `sad` and `tense` as the same speed. Warren
    speaks them 110 WPM apart, so the flat figure over-stated capacity on every
    slow line - which is why all the large overruns in the first render were
    `sad` or `reveal`.
    """
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from pipeline import calibration as cal
    from pipeline.schemas import estimate_narration_seconds as est

    # Inject a profile stamped with the CURRENT mapping. The mechanism is what
    # is under test, not whether a valid measurement happens to exist right
    # now: changing the delivery mapping legitimately voids the stored profile
    # (see PROFILE-STALE in tools/test_voice_consistency.py), and this test
    # must not fail just because a re-measurement is pending.
    _saved = cal._load_all
    cal._load_all = lambda: {cal.production_voice_key(): {
        "voice_id": "x", "rate_adjustment": "",
        "words_per_sec": 3.2, "words_per_sec_conservative": 3.0,
        "pause_overhead_sec": 0.18,
        "by_tag": {
            "sad":   {"words_per_sec": 2.52, "words_per_sec_conservative": 2.37,
                      "samples": 13},
            "tense": {"words_per_sec": 4.45, "words_per_sec_conservative": 3.79,
                      "samples": 37},
        },
        "mapping_signature": cal.mapping_signature()}}
    try:
        prof = cal.production_profile()
        if not prof.is_measured or not prof.by_tag:
            return False, "the injected per-tag profile was not picked up"
        sad, tense = est(30, "sad"), est(30, "tense")
        flat = est(30)
        bumped = est(30, "sad", 1.08)
    finally:
        cal._load_all = _saved
    if not sad > tense:
        return False, (f"30 words estimated at {sad:.2f}s on sad vs "
                       f"{tense:.2f}s on tense - the tag is being ignored")
    # the slow tag must also be budgeted SLOWER than the flat figure, or the
    # recalibration has not actually changed the thing that failed
    if not sad > flat:
        return False, (f"sad ({sad:.2f}s) is not budgeted longer than the flat "
                       f"estimate ({flat:.2f}s) - the slow tags are still "
                       f"under-budgeted")
    # a rate_bump must shorten the estimate, or a fitted line stays flagged
    if not bumped < sad:
        return False, "rate_bump does not shorten the estimate"
    return True, (f"30 words: sad {sad:.2f}s > flat {flat:.2f}s > tense "
                  f"{tense:.2f}s; rate_bump 1.08 -> {bumped:.2f}s")


TESTS = {
    "PREFLIGHT-CATCHES":   test_preflight_catches,
    "PREFLIGHT-LISTS-ALL": test_preflight_lists_all,
    "PREFLIGHT-FORMULA":   test_preflight_formula,
    "PREFLIGHT-SCOPE":     test_preflight_scope,
    "PREFLIGHT-STALE":     test_preflight_stale,
    "TAG-RATE-BUDGET":     test_tag_rate_budget,
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
        print(f'{"PASS" if ok else "FAIL"}  {name:<20} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_preflight: all pass" if not bad else
          f"test_preflight: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
