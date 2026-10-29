"""<film_speaks> selection + gate regression tests.

THE DEFECT
----------
A finished 17-minute recap shipped with ZERO film_speaks units. Nothing was
broken - no gate asked for any, so none were written. Since the film audio
under narration now comes from the no-vocals stem, that recap contained no
original dialogue at all.

These tests lock the stage that replaces "somebody remembers".

Cases
-----
  ELIGIBILITY-REVEAL      a quote AT/AFTER a reveal landing that states it is
                          eligible; the same words BEFORE the landing are not
                          (that is a spoiler, not a quote)
  ELIGIBILITY-ANGLE-QUOTE a phrase angle.md quotes is found even when the film
                          PARAPHRASES it - the real miss, where bag-of-words
                          against the thesis prose scored too low
  ANGLE-QUOTE-PRECISION   a one-word coincidence against a short quoted phrase
                          does NOT qualify
  QUALITY-DURATION        3-15s enforced at generation
  AUDIO-CLEAN-MEASURED    cleanliness is a measured dB margin; an unmeasured
                          span FAILS rather than passing
  COUNT-ZERO-WITH-CANDS   zero units while candidates exist is an ERROR - the
                          exact failure that shipped
  COUNT-ZERO-LEGITIMATE   zero units with NO candidates is accepted
  JUSTIFIED               criterion + a real justification required
  NO-PARAPHRASE           high word overlap with the PRECEDING line fails
  SPACING                 one per act, and a minimum gap in SECONDS (line-id
                          spacing was meaningless once units carry high ids)
  SPOILER                 a quote may not precede the reveal it reveals
  CANDIDATE-BALANCE       the candidate list spreads across acts and signals,
                          so the selector can see more than one kind of evidence

Run:  python tools/test_film_speaks.py
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from pipeline import film_speaks as fs  # noqa: E402

PROJ = "_fstest"


def _mk(transcript: list, reveals: list | None = None,
        angle: str = "", beats: list | None = None) -> Path:
    pdir = Path(config.project_dir(PROJ))
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True, exist_ok=True)
    io.open(pdir / "transcript.json", "w", encoding="utf-8").write(json.dumps({
        "language": "en",
        "segments": [{"start": a, "end": b, "text": t}
                     for a, b, t in transcript]}))
    io.open(pdir / "reveals.json", "w", encoding="utf-8").write(
        json.dumps({"reveals": reveals or [], "set_pieces": []}))
    if angle:
        io.open(pdir / "angle.md", "w", encoding="utf-8").write(angle)
    rows = beats or [("B01", "00:00:10"), ("B02", "00:05:00"),
                     ("B03", "00:10:00"), ("B04", "00:20:00")]
    io.open(pdir / "beats_proposal.md", "w", encoding="utf-8").write(
        "# beats\n" + "\n".join(f"{b} | {t} | what happens | chars | action"
                                for b, t in rows))
    return pdir


def _teardown():
    shutil.rmtree(Path(config.project_dir(PROJ)), ignore_errors=True)


def _draft(lines: list) -> dict:
    return {"project": PROJ, "lines": lines}


# --------------------------------------------------------------------------- #
def test_eligibility_reveal() -> tuple[bool, str]:
    quote = "I was the one who took the money the whole time"
    rev = [{"land": "00:10:00", "type": "A",
            "fact": "he took the money himself",
            "hold": ["took the money"]}]
    # AFTER the landing (600s) -> eligible
    _mk([(610.0, 616.0, quote)], reveals=rev)
    try:
        after = fs.candidates(PROJ, measure_audio=False)
        if not any("reveal_own_words" in c["criteria"] for c in after):
            return False, (f"a quote after the reveal landing did not qualify: "
                           f"{[c['criteria'] for c in after]}")
    finally:
        _teardown()
    # BEFORE the landing -> must NOT be eligible (it is a spoiler)
    _mk([(300.0, 306.0, quote)], reveals=rev)
    try:
        before = fs.candidates(PROJ, measure_audio=False)
        if any("reveal_own_words" in c["criteria"] for c in before):
            return False, ("the same words BEFORE the landing qualified - that "
                           "is a spoiler, not a quote")
    finally:
        _teardown()
    return True, ("a reveal stated at/after its landing is eligible; the same "
                  "words before it are not")


def test_eligibility_angle_quote() -> tuple[bool, str]:
    """The real miss: angle.md quotes it, the film paraphrases it."""
    angle = ('# Angle\n\nThe spine: he only wins the day he stops running.\n'
             '- B02 ("you can\'t keep running from your trouble") - the exact '
             'words the thesis pays off.\n')
    # the film says it DIFFERENTLY
    said = ("And you know she had no other choice, it was either this or "
            "Juvie Hall. You just can't keep moving away every time you get "
            "into trouble.")
    _mk([(320.0, 329.0, said)], angle=angle)
    try:
        c = fs.candidates(PROJ, measure_audio=False)
        hit = [x for x in c if "angle_quote" in x["evidence"]]
        if not hit:
            return False, ("a line angle.md QUOTES was not found because the "
                           "film paraphrases it - this is the exact gap that "
                           "forced a selector off-list")
        m = hit[0]["evidence"]["angle_quote"]
        return True, (f"matched the quoted phrase at {m['match']:.2f} on "
                      f"{m['matched_words']} despite different wording")
    finally:
        _teardown()


def test_angle_quote_precision() -> tuple[bool, str]:
    """A single-word coincidence must not qualify."""
    angle = '# Angle\n\nB01 ("I\'m his father") carries it.\n'
    _mk([(320.0, 329.0,
          "My father bought me a laptop and I take it everywhere I go now")],
        angle=angle)
    try:
        c = fs.candidates(PROJ, measure_audio=False)
        bad = [x for x in c if "angle_quote" in x["evidence"]]
        if bad:
            return False, (f"a one-word match against a 2-content-word phrase "
                           f"qualified: {bad[0]['evidence']['angle_quote']} - "
                           f"this put a laptop pitch and a line about ketchup "
                           f"in the candidate list")
        return True, ("a single shared word against a short quoted phrase does "
                      "not qualify (>= 2 matched words required)")
    finally:
        _teardown()


def test_quality_duration() -> tuple[bool, str]:
    angle = '# Angle\n\nB01 ("he stops running from trouble") is the spine.\n'
    line = "he finally stops running from his trouble"
    _mk([(320.0, 321.5, line),          # 1.5s - too short
         (400.0, 425.0, line)],         # 25s  - too long
        angle=angle)
    try:
        c = fs.candidates(PROJ, measure_audio=False)
        bad = [x for x in c
               if x["seconds"] < config.FILM_SPEAKS_MIN_SEC - 1e-6
               or x["seconds"] > config.FILM_SPEAKS_MAX_SEC + 1e-6]
        if bad:
            return False, f"out-of-range durations qualified: {bad}"
        return True, (f"only {config.FILM_SPEAKS_MIN_SEC:.0f}-"
                      f"{config.FILM_SPEAKS_MAX_SEC:.0f}s spans are generated")
    finally:
        _teardown()


def test_audio_clean_measured() -> tuple[bool, str]:
    """Cleanliness is a measurement, and an unmeasured span FAILS."""
    pdir = _mk([(10.0, 16.0, "a line")])
    try:
        # no source.mp4 -> cannot measure
        got = fs.audio_cleanliness(PROJ, 10.0, 16.0)
        if got.get("measured"):
            return False, "claimed a measurement with no source to measure"
        if got.get("margin_db") is not None:
            return False, "returned a margin it could not have measured"
        # an unmeasured unit must be REPORTED by the audit, not passed
        d = _draft([
            {"id": 1, "narration": "setup line here", "clip_start":
             "00:00:01.000", "clip_end": "00:00:09.000"},
            {"id": 2, "narration": "", "clip_start": "00:00:10.000",
             "clip_end": "00:00:16.000", "film_speaks_seconds": 6.0,
             "film_speaks_criterion": "thesis",
             "film_speaks_reason": "it states the thesis in his own words",
             "film_speaks_quote": "a line"},
        ])
        probs = fs.audit(PROJ, d)
        if not any("AUDIO-CLEAN" in p for p in probs):
            return False, (f"an unmeasured unit was accepted: {probs} - a "
                           f"quote is not clean because nobody checked")
        # a recorded margin below the floor must also fail
        d["lines"][1]["film_speaks_audio_margin_db"] = 1.0
        if not any("AUDIO-CLEAN" in p for p in fs.audit(PROJ, d)):
            return False, "a +1.0 dB margin passed the 3 dB floor"
        # and at/above the floor it must pass that gate
        d["lines"][1]["film_speaks_audio_margin_db"] = 12.0
        if any("AUDIO-CLEAN" in p for p in fs.audit(PROJ, d)):
            return False, "a +12 dB margin was rejected"
        return True, (f"unmeasured fails; +1.0 dB fails the "
                      f"{fs.AUDIO_CLEAN_MIN_DB:.0f} dB floor; +12 dB passes")
    finally:
        _teardown()


def test_count_zero_with_candidates() -> tuple[bool, str]:
    """THE failure that shipped: zero units while candidates exist."""
    angle = '# Angle\n\nB01 ("he stops running from trouble") is the spine.\n'
    _mk([(320.0, 329.0,
          "he finally stops running from his own trouble for once")],
        angle=angle)
    try:
        if not fs.candidates(PROJ, measure_audio=False):
            return False, "the fixture produces no candidate, so it cannot test"
        probs = fs.audit(PROJ, _draft([
            {"id": 1, "narration": "a line", "clip_start": "00:00:01.000",
             "clip_end": "00:00:05.000"}]))
        hit = [p for p in probs if "FILM-SPEAKS-COUNT" in p]
        if not hit:
            return False, ("zero units with eligible candidates was accepted - "
                           "this is exactly what shipped")
        if "candidate" not in hit[0] or "film_speaks_candidates" not in hit[0]:
            return False, f"the finding does not name the remedy: {hit[0]}"
        return True, "zero units with candidates present is an error that names the fix"
    finally:
        _teardown()


def test_count_zero_legitimate() -> tuple[bool, str]:
    """Zero with NOTHING eligible is fine - the gate must not cry wolf."""
    _mk([(10.0, 16.0, "pass me that wrench would you")])
    try:
        if fs.candidates(PROJ, measure_audio=False):
            return False, "the fixture unexpectedly produced a candidate"
        probs = fs.audit(PROJ, _draft([
            {"id": 1, "narration": "a line", "clip_start": "00:00:01.000",
             "clip_end": "00:00:05.000"}]))
        if any("FILM-SPEAKS-COUNT" in p for p in probs):
            return False, (f"zero units with no eligible candidate was "
                           f"reported: {probs}")
        return True, "zero units with no candidate is accepted"
    finally:
        _teardown()


def test_justified() -> tuple[bool, str]:
    _mk([(10.0, 16.0, "pass me that wrench")])
    try:
        base = {"id": 2, "narration": "", "clip_start": "00:00:10.000",
                "clip_end": "00:00:16.000", "film_speaks_seconds": 6.0,
                "film_speaks_quote": "a line",
                "film_speaks_audio_margin_db": 12.0}
        # no criterion
        d = _draft([{"id": 1, "narration": "setup", "clip_start":
                     "00:00:01.000", "clip_end": "00:00:09.000"}, dict(base)])
        if not any("JUSTIFIED" in p for p in fs.audit(PROJ, d)):
            return False, "a unit with no criterion was accepted"
        # criterion that names nothing valid
        d["lines"][1]["film_speaks_criterion"] = "it is a great line"
        d["lines"][1]["film_speaks_reason"] = "because it is a great line here"
        if not any("JUSTIFIED" in p for p in fs.audit(PROJ, d)):
            return False, "a criterion naming none of reveal/climax/thesis passed"
        # valid criterion but no real reason
        d["lines"][1]["film_speaks_criterion"] = "thesis"
        d["lines"][1]["film_speaks_reason"] = "good"
        if not any("JUSTIFIED" in p for p in fs.audit(PROJ, d)):
            return False, "a two-word justification passed"
        d["lines"][1]["film_speaks_reason"] = \
            "it states the angle's thesis in the character's own words"
        if any("JUSTIFIED" in p for p in fs.audit(PROJ, d)):
            return False, "a properly justified unit was rejected"
        return True, ("a criterion naming reveal/climax/thesis AND a real "
                      "sentence of justification are both required")
    finally:
        _teardown()


def test_no_paraphrase() -> tuple[bool, str]:
    _mk([(10.0, 16.0, "pass me that wrench")])
    try:
        quote = "you cannot keep running away from your own trouble forever"
        unit = {"id": 2, "narration": "", "clip_start": "00:00:10.000",
                "clip_end": "00:00:16.000", "film_speaks_seconds": 6.0,
                "film_speaks_criterion": "thesis",
                "film_speaks_reason": "it states the thesis in his own words",
                "film_speaks_quote": quote,
                "film_speaks_audio_margin_db": 12.0}
        # the PRECEDING line says the same thing
        d = _draft([
            {"id": 1, "narration": "His father tells him he cannot keep "
                                   "running away from his own trouble forever",
             "clip_start": "00:00:01.000", "clip_end": "00:00:09.000"},
            dict(unit)])
        if not any("NO-PARAPHRASE" in p for p in fs.audit(PROJ, d)):
            return False, ("the preceding line paraphrased the quote and it "
                           "was accepted - the viewer hears it twice")
        # a setup that does NOT say it
        d["lines"][0]["narration"] = ("The man has clearly been rehearsing "
                                      "this one. Listen.")
        if any("NO-PARAPHRASE" in p for p in fs.audit(PROJ, d)):
            return False, "a clean setup line was rejected"
        return True, ("a preceding line that paraphrases the quote fails; a "
                      "setup that frames without saying it passes")
    finally:
        _teardown()


def test_spacing() -> tuple[bool, str]:
    _mk([(10.0, 16.0, "pass me that wrench")])
    try:
        def unit(i, cs):
            return {"id": i, "narration": "", "clip_start": cs,
                    "clip_end": cs, "film_speaks_seconds": 6.0,
                    "film_speaks_criterion": "thesis",
                    "film_speaks_reason": "it states the thesis in his words",
                    "film_speaks_quote": "x", "film_speaks_audio_margin_db": 12.0}
        # 100s apart - under the 180s floor. Note the IDS are far apart, which
        # the old line-id spacing proxy would have called fine.
        d = _draft([{"id": 1, "narration": "setup", "clip_start":
                     "00:00:01.000", "clip_end": "00:00:09.000"},
                    unit(50, "00:05:00.000"), unit(90, "00:06:40.000")])
        probs = fs.audit(PROJ, d)
        if not any("SPACING" in p for p in probs):
            return False, (f"two units 100s apart were accepted: {probs}")
        # far apart in time AND in different acts -> fine
        d["lines"][2]["clip_start"] = "00:21:00.000"
        d["lines"][2]["clip_end"] = "00:21:00.000"
        if any("SPACING" in p for p in fs.audit(PROJ, d)):
            return False, (f"units 16 minutes apart in different acts were "
                           f"rejected: {fs.audit(PROJ, d)}")
        return True, (f"two units under {config.FILM_SPEAKS_MIN_GAP_SEC:.0f}s "
                      f"apart fail even with distant ids; well-spaced units in "
                      f"different acts pass")
    finally:
        _teardown()


def test_spoiler() -> tuple[bool, str]:
    rev = [{"land": "00:10:00", "type": "A", "fact": "he took the money",
            "hold": ["took the money"]}]
    _mk([(10.0, 16.0, "pass me that wrench")], reveals=rev)
    try:
        d = _draft([
            {"id": 1, "narration": "setup", "clip_start": "00:00:01.000",
             "clip_end": "00:00:09.000"},
            {"id": 2, "narration": "", "clip_start": "00:05:00.000",
             "clip_end": "00:05:06.000", "film_speaks_seconds": 6.0,
             "film_speaks_criterion": "thesis",
             "film_speaks_reason": "it states the thesis in his own words",
             "film_speaks_quote": "I took the money and nobody noticed",
             "film_speaks_audio_margin_db": 12.0}])
        if not any("SPOILER" in p for p in fs.audit(PROJ, d)):
            return False, ("a quote using a held term 5 minutes before its "
                           "reveal lands was accepted")
        # after the landing it is fine
        d["lines"][1]["clip_start"] = "00:11:00.000"
        d["lines"][1]["clip_end"] = "00:11:06.000"
        if any("SPOILER" in p for p in fs.audit(PROJ, d)):
            return False, "the same quote after the landing was rejected"
        return True, ("a quote cannot precede the reveal it reveals; after the "
                      "landing it is allowed")
    finally:
        _teardown()


def test_candidate_balance() -> tuple[bool, str]:
    """The list must spread across acts and signals, or the selector is blind.

    A rank-ordered head() gave one act ten candidates of a single signal type
    and hid the strongest line in the film behind a signal that fires 173
    times. A selector cannot choose what it cannot see.
    """
    p = Path(config.project_dir("tokyodrift2006"))
    if not (p / "film_speaks_candidates.json").exists():
        return False, "SKIPPED - tokyodrift2006 candidates not generated"
    doc = json.loads((p / "film_speaks_candidates.json")
                     .read_text(encoding="utf-8"))
    cands = doc.get("candidates") or []
    if not cands:
        return False, "the candidate file is empty"
    acts = {c["act"] for c in cands}
    if len(acts) < 3:
        return False, (f"candidates cover only acts {sorted(acts)} - the "
                       f"selector cannot honour one-per-act from that")

    def sig(c):
        ev = c["evidence"]
        if "reveal" in ev:
            return "reveal"
        if "climax_or_final" in c["criteria"]:
            return "climax"
        if "angle_quote" in ev:
            return "angle_quote"
        if ev.get("in_angle_beat"):
            return "angle_beat"
        return "thesis_overlap"

    sigs = {sig(c) for c in cands}
    if len(sigs) < 2:
        return False, (f"every candidate came from one signal ({sigs}) - one "
                       f"kind of evidence has crowded out the rest")
    measured = [c for c in cands if (c.get("audio") or {}).get("measured")]
    if not measured:
        return False, "no candidate carries a measured audio margin"
    return True, (f"{len(cands)} candidates across acts {sorted(acts)} and "
                  f"{len(sigs)} signal types, {len(measured)} with measured "
                  f"audio")


TESTS = {
    "ELIGIBILITY-REVEAL":       test_eligibility_reveal,
    "ELIGIBILITY-ANGLE-QUOTE":  test_eligibility_angle_quote,
    "ANGLE-QUOTE-PRECISION":    test_angle_quote_precision,
    "QUALITY-DURATION":         test_quality_duration,
    "AUDIO-CLEAN-MEASURED":     test_audio_clean_measured,
    "COUNT-ZERO-WITH-CANDS":    test_count_zero_with_candidates,
    "COUNT-ZERO-LEGITIMATE":    test_count_zero_legitimate,
    "JUSTIFIED":                test_justified,
    "NO-PARAPHRASE":            test_no_paraphrase,
    "SPACING":                  test_spacing,
    "SPOILER":                  test_spoiler,
    "CANDIDATE-BALANCE":        test_candidate_balance,
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
        print(f'{"PASS" if ok else "FAIL"}  {name:<26} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_film_speaks: all pass" if not bad else
          f"test_film_speaks: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
