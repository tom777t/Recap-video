"""ONE NARRATOR - voice-consistency regression tests.

THE DEFECT
----------
The first Warren render sounded like two or three different readers. Measured
on its 102 measurable lines: line 99 at 126 WPM against line 32 at 329 WPM, a
2.62x spread; `sad` and `reveal` ran 25% under the mean and `tense` 32% over.

The cause was the tag -> controls mapping varying three things at once:
  * deliveryMode (BALANCED / CREATIVE / STABLE) - CREATIVE changes the timbre
  * steering cues instructing TEMPO and CHARACTER ("say fast and driving",
    "whisper in a hushed style", "say with force")
  * speaking_rate from 1.02 to 1.42, added to compensate for the ~23% of pace a
    cue costs - which traded a pace problem for a consistency problem

These tests lock the fix in both directions: the shipped mapping passes, and
the EXACT historical mapping fails with the reasons named.

Cases
-----
  CUES-CLEAN            the shipped mapping satisfies the contract
  CUES-CATCH-OLD        the real historical mapping is rejected, naming tempo
                        words, character words, the uncued tag, the varying
                        rate and the varying mode
  ONE-RATE-ONE-MODE     every tag has the same speaking_rate and deliveryMode
  CUE-WORD-BOUNDARIES   "phrasing" and "closing" are not read as "sing" - a
                        substring test condemned three legitimate cues
  BUMP-IN-BAND          a rate_bump answers to the voice band, and
                        fit_narration's ceiling is derived from it
  RATIO-GATE            a 1.77x spread fails, a 1.15x spread passes
  ADJACENT-JUMP         a step change between neighbours fails, a ramp passes
  SHORT-LINES-EXCLUDED  a 4-word line cannot poison the statistics
  WORD-LENGTH-NEUTRAL   identical speaking rate with different word lengths is
                        NOT flagged - the gate must measure the narrator, not
                        the vocabulary

Run:  python tools/test_voice_consistency.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402
from pipeline import voice_check as vc  # noqa: E402


# The mapping as it actually shipped and failed, kept verbatim as the fixture.
OLD_MAPPING = {
    "normal":  dict(cue="", delivery_mode="BALANCED", speaking_rate=1.02),
    "tense":   dict(cue="[say with urgency, clipped and controlled]",
                    delivery_mode="BALANCED", speaking_rate=1.32),
    "sad":     dict(cue="[say quietly in a low, subdued tone]",
                    delivery_mode="CREATIVE", speaking_rate=1.12),
    "reveal":  dict(cue="[say with weight, letting it land]",
                    delivery_mode="BALANCED", speaking_rate=1.18),
    "mystery": dict(cue="[whisper in a hushed style]",
                    delivery_mode="CREATIVE", speaking_rate=1.15),
    "hook":    dict(cue="[say with force]",
                    delivery_mode="BALANCED", speaking_rate=1.30),
    "intro":   dict(cue="[articulate clearly]",
                    delivery_mode="STABLE", speaking_rate=1.28),
    "outro":   dict(cue="[say with a falling pitch]",
                    delivery_mode="STABLE", speaking_rate=1.20),
    "action":  dict(cue="[say fast and driving]",
                    delivery_mode="BALANCED", speaking_rate=1.42),
}


class _FakeProvider:
    def __init__(self, mapping):
        self.delivery = mapping

    def controls_for(self, tag, speed_mult=1.0):
        return dict(self.delivery[tag])


def _production_provider():
    from pipeline.tts import DEFAULT_PROVIDER
    from pipeline.tts_providers import all_providers
    return all_providers().get(DEFAULT_PROVIDER)


def _rows(spec):
    """spec: [(line_id, tag, words, syls, dur, bump)] -> measure()-shaped rows."""
    return [{"line_id": i, "tag": t, "words": w, "syls": s, "dur": d,
             "wps": w / d, "sps": s / d, "rate_bump": b}
            for i, t, w, s, d, b in spec]


def test_cues_clean() -> tuple[bool, str]:
    p = _production_provider()
    if p is None:
        return False, "no production provider registered"
    bad = vc.audit_cues(p) + vc.rate_band_violations(p)
    ok = not bad
    return ok, (f"the shipped mapping ({len(p.delivery)} tags) satisfies the "
                f"one-narrator contract" if ok else "; ".join(bad))


def test_cues_catch_old() -> tuple[bool, str]:
    bad = (vc.audit_cues(_FakeProvider(OLD_MAPPING))
           + vc.rate_band_violations(_FakeProvider(OLD_MAPPING)))
    blob = " | ".join(bad).lower()
    need = {
        "a tempo word":          "fast",
        "a character word":      "subdued",
        "the uncued tag":        "carry no cue",
        "the varying rate":      "speaking_rate differs",
        "the varying mode":      "delivery_mode differs",
        "an out-of-band rate":   "outside the +-10% band",
    }
    missing = [label for label, probe in need.items() if probe not in blob]
    ok = not missing and len(bad) >= 10
    return ok, (f"the historical mapping is rejected with {len(bad)} findings, "
                f"naming every cause" if ok else
                f"did not report: {missing} (got {len(bad)} findings)")


def test_one_rate_one_mode() -> tuple[bool, str]:
    p = _production_provider()
    if p is None:
        return False, "no production provider registered"
    rates = {round(float(p.controls_for(t)["speaking_rate"]), 4)
             for t in p.delivery}
    modes = {str(p.controls_for(t)["delivery_mode"]) for t in p.delivery}
    uncued = [t for t in p.delivery if not str(p.controls_for(t)["cue"]).strip()]
    ok = (len(rates) == 1 and len(modes) == 1 and not uncued
          and rates == {round(float(config.VOICE_BASE_SPEAKING_RATE), 4)})
    return ok, (f"all {len(p.delivery)} tags share rate {rates.pop():.3f} and "
                f"mode {modes.pop()}, and every tag is cued" if ok else
                f"rates={sorted(rates)} modes={sorted(modes)} uncued={uncued}")


def test_cue_word_boundaries() -> tuple[bool, str]:
    """A substring test for banned words condemned "phrasing" and "closing"."""
    fine = _FakeProvider({
        "a": dict(cue="[even phrasing]", delivery_mode="BALANCED",
                  speaking_rate=1.02),
        "b": dict(cue="[pause before the closing phrase]",
                  delivery_mode="BALANCED", speaking_rate=1.02),
    })
    if vc.audit_cues(fine):
        return False, (f"legitimate cues rejected: {vc.audit_cues(fine)} - "
                       f"'sing' is matching inside 'phrasing'/'closing'")
    caught = _FakeProvider({
        "a": dict(cue="[sing the line]", delivery_mode="BALANCED",
                  speaking_rate=1.02),
        "b": dict(cue="[pause, then whispers]", delivery_mode="BALANCED",
                  speaking_rate=1.02),
    })
    bad = " ".join(vc.audit_cues(caught)).lower()
    if "sing" not in bad or "whisper" not in bad:
        return False, f"real banned words not caught: {vc.audit_cues(caught)}"
    return True, ("'phrasing' and 'closing' pass; a real 'sing' and "
                  "'whispers' are still caught")


def test_bump_in_band() -> tuple[bool, str]:
    band = float(config.VOICE_RATE_BAND)
    checks = [(1.0, True), (1.0 + band, True), (1.0 + band + 0.01, False),
              (1.0 - band, True), (1.0 - band - 0.01, False), (1.4, False)]
    bad = [b for b, want in checks if vc.bump_in_band(b) != want]
    if bad:
        return False, f"bump_in_band wrong for {bad}"
    # fit_narration must derive its ceiling from the band, not hold its own
    src = open(os.path.join(ROOT, "tools", "fit_narration.py"),
               encoding="utf-8").read()
    if "VOICE_RATE_BAND" not in src:
        return False, ("tools/fit_narration.py does not derive --max-bump from "
                       "config.VOICE_RATE_BAND - a bump could sit outside the "
                       "band every tag respects")
    return True, (f"a rate_bump answers to the +-{band:.0%} voice band, and "
                  f"fit_narration derives its ceiling from it")


def test_ratio_gate() -> tuple[bool, str]:
    # the real shape of the failure: sad ~151 WPM vs tense ~267 WPM
    slow = 151.0 / 60.0
    fast = 267.0 / 60.0
    bad_rows = _rows([(1, "sad", 20, 30, 20 / slow, 1.0),
                      (2, "tense", 20, 30, 20 / fast, 1.0)])
    r = vc.analyse(bad_rows)
    if r["ok"]:
        return False, (f"a {r['ratio_wps']:.2f}x spread passed the "
                       f"{config.VOICE_WPM_RATIO_MAX:.2f}x ceiling")
    # and a tight spread must pass
    a, b = 190.0 / 60.0, 205.0 / 60.0
    good = _rows([(1, "sad", 20, 30, 20 / a, 1.0),
                  (2, "normal", 20, 30, 20 / b, 1.0)])
    r2 = vc.analyse(good)
    if not r2["ok"]:
        return False, (f"a {r2['ratio_wps']:.2f}x spread was rejected: "
                       f"{r2['problems']}")
    return True, (f"{r['ratio_wps']:.2f}x fails, {r2['ratio_wps']:.2f}x passes "
                  f"(ceiling {config.VOICE_WPM_RATIO_MAX:.2f}x)")


def test_adjacent_jump() -> tuple[bool, str]:
    jump = float(config.VOICE_ADJACENT_MAX_JUMP)
    base = 200.0 / 60.0
    # a hard step between neighbours
    step = _rows([(1, "sad", 20, 30, 20 / base, 1.0),
                  (2, "tense", 20, 30, 20 / (base * (1 + jump * 3)), 1.0)])
    r = vc.analyse(step)
    if not any("adjacent" in p for p in r["problems"]):
        return False, f"a {jump*3:.0%} step between neighbours was not flagged"
    # a ramp of the same total change, spread over intervening lines
    ramp = _rows([(i + 1, "normal", 20, 30,
                   20 / (base * (1 + jump * 0.8 * i)), 1.0)
                  for i in range(4)])
    r2 = vc.analyse(ramp)
    if any("adjacent" in p for p in r2["problems"]):
        return False, (f"a ramp inside {jump:.0%} per step was flagged: "
                       f"{[p for p in r2['problems'] if 'adjacent' in p]}")
    return True, (f"a {jump*3:.0%} step fails; the same total change ramped at "
                  f"{jump*0.8:.0%} per line passes")


def test_short_lines_excluded() -> tuple[bool, str]:
    """A 4-word line is lead-in and trailing silence, not a rate measurement."""
    import io
    import json
    import shutil
    from pathlib import Path
    floor = int(config.VOICE_RATE_MIN_WORDS)
    pdir = Path(ROOT) / "_vctest"
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True, exist_ok=True)
    try:
        draft = {"lines": [
            {"id": 1, "narration": " ".join(["word"] * (floor + 4)),
             "delivery": "normal"},
            {"id": 2, "narration": " ".join(["word"] * (floor - 2)),
             "delivery": "normal"},
        ]}
        # durations passed in directly; no audio needed
        rows = vc.measure(draft, [(1, pdir / "a.mp3", 4.0),
                                  (2, pdir / "b.mp3", 4.0)])
        ids = sorted(r["line_id"] for r in rows)
        ok = ids == [1]
        return ok, (f"lines under {floor} words are excluded from the rate "
                    f"statistics" if ok else
                    f"expected only line 1 measured, got {ids}")
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_word_length_neutral() -> tuple[bool, str]:
    """Same speaking rate, different word lengths, must NOT be flagged.

    Words/sec conflates reading speed with word length: at an identical rate, a
    line of long words has far fewer words per second. Gating on words/sec
    alone would fail a render for the writing rather than the reading, so the
    gate requires the SYLLABLE rate to be an outlier too.
    """
    # both lines read at 4.0 syllables/sec - the same speaking rate
    sps = 4.0
    short_words = _rows([(1, "normal", 20, 20, 20 / sps, 1.0)])   # 1 syl/word
    long_words = _rows([(2, "normal", 10, 40, 40 / sps, 1.0)])    # 4 syl/word
    rows = short_words + long_words
    r = vc.analyse(rows)
    ratio_w = r["ratio_wps"]
    if ratio_w < 1.5:
        return False, (f"fixture is wrong: words/sec ratio is only "
                       f"{ratio_w:.2f}x, so it does not test the conflation")
    if not r["ok"]:
        return False, (f"identical speaking rate ({sps} syl/s) was flagged "
                       f"because words/sec differed {ratio_w:.2f}x: "
                       f"{r['problems']}")
    return True, (f"a {ratio_w:.2f}x words/sec difference at an identical "
                  f"{sps:.1f} syl/s speaking rate is not flagged")


def test_profile_stale_on_mapping_change() -> tuple[bool, str]:
    """A measured voice profile is void if the delivery mapping changed.

    The profile measured under the old mapping recorded `sad` at 151 WPM. The
    new mapping does not produce that rate, so carrying the profile across the
    change would budget capacity against a narrator that no longer exists -
    silently, because the file still looks like a measurement.
    """
    from pipeline import calibration as cal
    sig = cal.mapping_signature()
    if not sig:
        return False, "mapping_signature() returned nothing"

    saved = cal._load_all
    try:
        # a profile stamped with a DIFFERENT mapping must be refused
        cal._load_all = lambda: {cal.production_voice_key(): {
            "voice_id": "x", "rate_adjustment": "", "words_per_sec": 2.5,
            "words_per_sec_conservative": 2.4,
            "by_tag": {"sad": {"words_per_sec": 2.5,
                               "words_per_sec_conservative": 2.4,
                               "samples": 9}},
            "mapping_signature": "deadbeefdeadbeef"}}
        if cal.production_profile().is_measured:
            return False, ("a profile measured under a different mapping was "
                           "accepted")
        # an UNSIGNED profile is unknown provenance -> also refused
        cal._load_all = lambda: {cal.production_voice_key(): {
            "voice_id": "x", "rate_adjustment": "", "words_per_sec": 2.5,
            "words_per_sec_conservative": 2.4, "by_tag": {}}}
        if cal.production_profile().is_measured:
            return False, "an unsigned profile was accepted"
        # a profile stamped with the CURRENT mapping is used
        cal._load_all = lambda: {cal.production_voice_key(): {
            "voice_id": "x", "rate_adjustment": "", "words_per_sec": 2.5,
            "words_per_sec_conservative": 2.4,
            "by_tag": {"sad": {"words_per_sec": 2.5,
                               "words_per_sec_conservative": 2.4,
                               "samples": 9}},
            "mapping_signature": sig}}
        if not cal.production_profile().is_measured:
            return False, "a profile matching the current mapping was refused"
    finally:
        cal._load_all = saved
    return True, ("a profile is used only when its mapping_signature matches; "
                  "a mismatched or unsigned one falls back to the baseline")


TESTS = {
    "CUES-CLEAN":           test_cues_clean,
    "PROFILE-STALE":        test_profile_stale_on_mapping_change,
    "CUES-CATCH-OLD":       test_cues_catch_old,
    "ONE-RATE-ONE-MODE":    test_one_rate_one_mode,
    "CUE-WORD-BOUNDARIES":  test_cue_word_boundaries,
    "BUMP-IN-BAND":         test_bump_in_band,
    "RATIO-GATE":           test_ratio_gate,
    "ADJACENT-JUMP":        test_adjacent_jump,
    "SHORT-LINES-EXCLUDED": test_short_lines_excluded,
    "WORD-LENGTH-NEUTRAL":  test_word_length_neutral,
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
    print("test_voice_consistency: all pass" if not bad else
          f"test_voice_consistency: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
