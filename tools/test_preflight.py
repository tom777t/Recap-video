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
        # The REAL measured values for Warren at the flat delivery mapping
        # (87 clean readings): sad 109.7 WPM, tense 143.8 WPM. Using the old
        # pre-flattening numbers here made the fixture incoherent with
        # config.TTS_WORDS_PER_MINUTE once that was corrected to 141, and the
        # test then failed on its own stale assumption rather than on the code.
        "by_tag": {
            "sad":   {"words_per_sec": 1.828,
                      "words_per_sec_conservative": 1.747, "samples": 3},
            "tense": {"words_per_sec": 2.397,
                      "words_per_sec_conservative": 1.847, "samples": 24},
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


def test_writer_budget_matches_render() -> tuple[bool, str]:
    """THE WRITER'S WORD BUDGET MUST SATISFY THE RENDER'S CONTRACT.

    This is the regression for 42 capacity overruns in one draft. The writer
    sized every line with a different contract from the one the render
    enforces, in three separate ways:

      * RATE - config.TTS_WORDS_PER_MINUTE was 185 while Warren, measured on
        87 clean readings at the flat delivery mapping, runs 140.6 WPM. A 32%
        over-budget on every single line.
      * MARGIN - the fitter demanded headroom the writer's budget did not
        leave, so a line written exactly at the ceiling was refused the moment
        it was spoken.
      * WINDOW - the budget came from the shot's own duration, ignoring the
        free footage either side that the fitter will happily extend into.

    The check: take the writer's budget for a window, spend it entirely, and
    assert the render's own contract accepts the result.
    """
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from pipeline import preflight as pf
    from pipeline.calibration import production_profile
    from pipeline.render import GAP, _lead_for
    from pipeline.schemas import BINDING_SLOWDOWN_MAX as SM

    prof = production_profile()
    if not prof.is_measured:
        return False, ("the production voice has no calibrated profile, so the "
                       "writer is budgeting from a config constant - run "
                       "pipeline/calibration.py on real narration")

    bad = []
    for window in (3.0, 4.5, 6.0, 9.0, 12.0, 20.0):
        for tag in (None, "sad", "tense", "reveal"):
            words = pf.budget_words(window, tag)
            if words <= 0:
                continue
            # spend the whole budget, at the rate that tag really reads at
            wps = prof.rate_for(tag, conservative=True) if tag else \
                (prof.words_per_sec_conservative or prof.words_per_sec)
            narr = words / max(0.1, wps)
            need = _lead_for(narr, window) + narr + GAP
            cap = window * SM
            if need > cap + 1e-6:
                bad.append(f"{window:.1f}s/{tag}: budget {words} words = "
                           f"{narr:.2f}s, needs {need:.2f}s > capacity "
                           f"{cap:.2f}s")
    if bad:
        return False, ("the writer's budget does not fit the render's "
                       "contract: " + "; ".join(bad[:4]))

    # the budget must also be STRICTLY inside capacity, not exactly on it -
    # re-synthesized audio lands a percent either side of the prediction
    w = pf.budget_words(9.0)
    wps = prof.words_per_sec_conservative or prof.words_per_sec
    slack = 9.0 * SM - (w / wps + GAP)
    want = max(float(config.CAPACITY_MARGIN_MIN_SEC),
               float(config.CAPACITY_MARGIN_FRACTION) * 9.0 * SM)
    if slack < want - 1e-6:
        return False, (f"a fully spent budget leaves only {slack:.2f}s of "
                       f"headroom, under the {want:.2f}s the fitter demands")

    # The rate must come from a MEASUREMENT OF THE CURRENT MAPPING. This check
    # used to assert the rate was NOT ~185, which was right while 185 was a
    # stale figure inherited from the old per-tag mapping - and became wrong
    # the moment the voice was corrected to actually deliver 185. The value is
    # not the issue; its PROVENANCE is. A number that happens to equal the
    # target is fine if it was measured under the mapping in force.
    from pipeline.calibration import mapping_signature, production_voice_key
    import json as _json
    prof_path = Path(ROOT) / "config" / "voice_profiles.json"
    if not prof_path.exists():
        return False, "no voice_profiles.json - the writer has no measurement"
    meta = (_json.loads(prof_path.read_text(encoding="utf-8-sig"))
            .get("profiles", {}).get(production_voice_key(), {}))
    if meta.get("mapping_signature") != mapping_signature():
        return False, ("the writer's rate was measured under a DIFFERENT "
                       "delivery mapping - that is how 185 WPM survived a "
                       "change that made the voice read 134.6")
    # and the measured rate must sit on the target, or the budget is fiction
    tgt = float(config.TARGET_WPM)
    if abs(prof.words_per_sec * 60.0 / tgt - 1.0) > \
            float(config.VOICE_RATE_DRIFT_MAX):
        return False, (f"the writer budgets at {prof.words_per_sec*60:.0f} WPM "
                       f"against a {tgt:.0f} target - fix the voice, not the "
                       f"budget")
    if abs(float(config.TTS_WORDS_PER_MINUTE) / tgt - 1.0) > \
            float(config.VOICE_RATE_DRIFT_MAX):
        return False, (f"config.TTS_WORDS_PER_MINUTE is "
                       f"{config.TTS_WORDS_PER_MINUTE} against a {tgt:.0f} "
                       f"target - the fallback has drifted from the decision")

    # available_window must count free adjacent footage, not the shot
    draft = {"lines": [
        {"id": 1, "clip_start": "00:00:10.000", "clip_end": "00:00:13.000"},
        {"id": 2, "clip_start": "00:01:00.000", "clip_end": "00:01:05.000"},
    ]}
    avail = pf.available_window(draft, 1, src_dur=600.0)
    if avail < 50.0:
        return False, (f"available_window gave line 1 only {avail:.1f}s - it "
                       f"has 3s of its own plus ~47s free before the next "
                       f"line, and budgeting from the shot alone is what sent "
                       f"resolvable lines to the trim worklist")
    # A line BOXED IN on both sides has only its own window. Note the fixture
    # needs a line before it too: free footage before the FIRST line is
    # genuinely free, so counting it there is correct, not a bug.
    tight = {"lines": [
        {"id": 1, "clip_start": "00:00:00.000", "clip_end": "00:00:10.000"},
        {"id": 2, "clip_start": "00:00:10.000", "clip_end": "00:00:13.000"},
        {"id": 3, "clip_start": "00:00:13.000", "clip_end": "00:00:20.000"},
    ]}
    if pf.available_window(tight, 2, src_dur=600.0) > 3.5:
        return False, ("available_window ignored abutting neighbours - it "
                       "would budget footage another line already uses")
    # and a HOLD's real footprint must bound it, not the hold's declared end
    # Line 2 must be bounded on BOTH sides for this to test the hold: a last
    # line can legitimately reach the end of the film, so leaving it unbounded
    # forward tested nothing.
    held = {"lines": [
        {"id": 1, "clip_start": "00:00:00.000", "clip_end": "00:00:02.000",
         "narration": "", "narration_silence_seconds": 12.0},
        {"id": 2, "clip_start": "00:00:20.000", "clip_end": "00:00:23.000"},
        {"id": 3, "clip_start": "00:00:25.000", "clip_end": "00:00:30.000"},
    ]}
    got = pf.available_window(held, 2, src_dur=600.0)
    if got > 14.0:
        return False, (f"available_window gave line 2 {got:.1f}s - it reached "
                       f"back into footage a HOLD actually plays (the hold "
                       f"runs to 12s, not to its declared 2s end)")
    return True, (f"the writer budgets at the measured "
                  f"{prof.words_per_sec*60:.0f} WPM with the fitter's own "
                  f"margin, over the footage actually available, and a fully "
                  f"spent budget satisfies window x {SM:.2f} on every tag")


TESTS = {
    "WRITER-BUDGET-MATCHES-RENDER": test_writer_budget_matches_render,
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
