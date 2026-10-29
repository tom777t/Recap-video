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

import json
import os
import sys
from pathlib import Path

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
    # The two probes this list used to carry - "speaking_rate differs" and
    # "outside the +-10% band" - were REMOVED from audit_cues on purpose, not
    # lost. A per-tag speaking_rate is now legitimate: it cancels the pace cost
    # of that tag's cue so the DELIVERED rate is uniform, which is gated
    # separately by measured_uniformity(). The old mapping's rates (1.02-1.42)
    # are all inside the engine's range, so the control value was never what
    # convicted it - the tempo words, the character words, the uncued tag and
    # the varying delivery MODE are, and all four still fire.
    need = {
        "a tempo word":          "fast",
        "a character word":      "subdued",
        "the uncued tag":        "carry no cue",
        "the varying mode":      "delivery_mode differs",
    }
    missing = [label for label, probe in need.items() if probe not in blob]
    ok = not missing and len(bad) >= 10
    return ok, (f"the historical mapping is rejected with {len(bad)} findings, "
                f"naming every cause" if ok else
                f"did not report: {missing} (got {len(bad)} findings)")


def test_one_mode_uniform_delivered_rate() -> tuple[bool, str]:
    """ONE delivery mode, every tag cued, and the DELIVERED rate uniform.

    This test used to require one speaking_rate for every tag. That was right
    while rates were being used to CREATE different tempos - the original
    defect. It is wrong now: a steering cue costs pace (a pause instruction
    costs a measured 27%), different cues cost different amounts, so one
    control value DELIVERS rates 1.53x apart. The per-tag rates now exist only
    to cancel that.

    So the uniformity requirement moved to the OBSERVABLE - which is strictly
    stronger, because a control value cannot satisfy it by failing to take
    effect. The control value is checked against the engine's limits instead.
    """
    p = _production_provider()
    if p is None:
        return False, "no production provider registered"
    modes = {str(p.controls_for(t)["delivery_mode"]) for t in p.delivery}
    uncued = [t for t in p.delivery if not str(p.controls_for(t)["cue"]).strip()]
    if len(modes) != 1:
        return False, f"delivery modes differ: {sorted(modes)}"
    if uncued:
        return False, (f"tag(s) {uncued} carry no cue - an uncued tag reads "
                       f"~20% faster than every cued one")
    cap = float(getattr(config, "VOICE_SPEAKING_RATE_MAX", 1.5))
    out = [(t, float(p.controls_for(t)["speaking_rate"])) for t in p.delivery]
    bad = [(t, r) for t, r in out if not (0.5 <= r <= cap)]
    if bad:
        return False, f"speaking_rate outside the engine's range: {bad}"
    # and the delivered rate must be uniform, per the measurement
    uni = vc.measured_uniformity()
    if uni:
        return False, "; ".join(uni)
    return True, (f"one mode ({modes.pop()}), all {len(p.delivery)} tags cued, "
                  f"control rates {min(r for _t, r in out):.3f}-"
                  f"{max(r for _t, r in out):.3f} inside the engine range, and "
                  f"the DELIVERED rate is uniform within "
                  f"{config.VOICE_RATE_BAND:.0%}")


def test_rate_drift_gate() -> tuple[bool, str]:
    """[VOICE-RATE-DRIFT] - the regression for the whole 185 -> 141 episode.

    The sequence that must never repeat: the mapping was flattened, every tag
    gained a cue, the voice fell to 134.6 WPM, NOTHING MEASURED IT, and the
    word budget was then re-cut down to 141 to match - shrinking every line's
    allowance by a third to accommodate a regression in the voice.

    config.TARGET_WPM is a decision about the writing. The voice is what gets
    adjusted to meet it.
    """
    from pipeline import calibration as cal
    target = float(config.TARGET_WPM)
    tol = float(config.VOICE_RATE_DRIFT_MAX)
    # This case owns the GATE's behaviour, not the target's VALUE. It used to
    # assert `target == 185`, which made a deliberate, measured change of the
    # target look like a regression in the drift gate. The value is checked by
    # TARGET-WPM-ENGLISH-BAND, which knows why 185 was wrong (it came from a
    # Vietnamese channel). Keeping the literal in two places meant moving the
    # target required editing a test that has nothing to do with it.
    if target <= 0:
        return False, f"TARGET_WPM is {target}, which is not a pace"

    # the live voice must currently be on target
    ok, msg = vc.rate_drift()
    if not ok:
        return False, f"the shipped voice fails its own drift gate: {msg}"

    saved = cal._load_all
    try:
        # a voice measured well BELOW target must fail
        cal._load_all = lambda: {cal.production_voice_key(): {
            "voice_id": "x", "rate_adjustment": "",
            "words_per_sec": (target * 0.72) / 60.0,
            "words_per_sec_conservative": (target * 0.70) / 60.0,
            "by_tag": {}, "mapping_signature": cal.mapping_signature()}}
        if vc.rate_drift()[0]:
            return False, (f"a voice measuring {target*0.72:.0f} WPM against a "
                           f"{target:.0f} target passed the drift gate - that "
                           f"is exactly the 134.6 WPM state that went "
                           f"unnoticed")
        # ...and so must one well ABOVE it
        cal._load_all = lambda: {cal.production_voice_key(): {
            "voice_id": "x", "rate_adjustment": "",
            "words_per_sec": (target * 1.3) / 60.0,
            "words_per_sec_conservative": (target * 1.25) / 60.0,
            "by_tag": {}, "mapping_signature": cal.mapping_signature()}}
        if vc.rate_drift()[0]:
            return False, "a voice 30% FASTER than target passed the gate"
        # an UNMEASURED voice must fail, not pass quietly
        cal._load_all = lambda: {}
        ok2, msg2 = vc.rate_drift()
        if ok2:
            return False, ("an unmeasured voice passed - 'nobody measured' is "
                           "the state the drift happened in")
        if "calibrate" not in msg2.lower():
            return False, f"the finding does not say how to re-measure: {msg2}"
    finally:
        cal._load_all = saved

    # and the writer's fallback must track the target, never be cut to match a
    # slow voice
    fb = float(config.TTS_WORDS_PER_MINUTE)
    if abs(fb / target - 1.0) > tol:
        return False, (f"config.TTS_WORDS_PER_MINUTE is {fb:.0f} against a "
                       f"{target:.0f} target ({fb/target-1.0:+.0%}) - the "
                       f"budget has been re-cut to match the voice instead of "
                       f"the voice being fixed")
    return True, (f"on target ({msg}); a voice 28% slow, 30% fast, or "
                  f"unmeasured all fail; the writer's fallback {fb:.0f} WPM "
                  f"tracks the {target:.0f} target")


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


def test_single_line_reported_not_gated() -> tuple[bool, str]:
    """A single wild line is REPORTED; a sustained swing is GATED.

    Replaces an earlier test that failed a 1.77x single-line spread outright.
    That was the wrong unit: a control measured a perfectly consistent narrator
    at 1.38x line-to-line, so single-line spread cannot be a pass/fail. What a
    listener notices is a STRETCH, so the rolling 3-line average is the gate.
    """
    base = 240.0 / 60.0
    # one outlier among thirty: reported, not failed
    rows = _rows_at([base] * 30)
    rows[14]["wps"] = base * 1.8
    rows[14]["speech"] = rows[14]["words"] / rows[14]["wps"]
    res = vc.analyse(rows)
    if not res["ok"]:
        return False, (f"one 1.8x line among thirty failed the gate: "
                       f"{res['problems']}")
    if res["line_spread"] < 1.7:
        return False, "the fixture did not produce the intended spread"
    # a SUSTAINED swing - six consecutive fast lines - must fail
    rows2 = _rows_at([base] * 30)
    for i in range(10, 16):
        rows2[i]["wps"] = base * 1.6
        rows2[i]["speech"] = rows2[i]["words"] / rows2[i]["wps"]
    res2 = vc.analyse(rows2)
    if res2["ok"]:
        return False, ("six consecutive lines 60% fast passed - the rolling "
                       "average is not gating anything")
    if not any("rolling" in p for p in res2["problems"]):
        return False, f"the finding is not the rolling average: {res2['problems']}"
    return True, (f"a single {res['line_spread']:.2f}x outlier is reported but "
                  f"passes; six consecutive fast lines fail on the rolling "
                  f"3-line average")


def test_rolling_jump_gate() -> tuple[bool, str]:
    """Adjacent-jump is measured on the ROLLING average, at a calibrated bar.

    The old threshold was 8% on single pairs. The control measured a consistent
    narrator's p90 single-pair jump at 28% - so 8% flagged 70 pairs in a draft
    that was fine. The bar is now calibrated AND applied to the smoothed
    series, so one line cannot trigger it.
    """
    jump_max = float(config.VOICE_ADJACENT_MAX_JUMP)
    if jump_max < 0.2:
        return False, (f"VOICE_ADJACENT_MAX_JUMP is {jump_max} - below the "
                       f"control's own p90, so it fails a good narrator")
    ctl = json.loads((Path(ROOT) / "config" / "voice_spread_control.json")
                     .read_text(encoding="utf-8"))
    if jump_max < float(ctl["jump_p90"]):
        return False, (f"the jump bar {jump_max:.0%} is below the control's "
                       f"own p90 {float(ctl['jump_p90']):.0%}")

    base = 240.0 / 60.0
    roll_max = float(config.VOICE_ROLL3_SPREAD_MAX)

    # A sustained step big enough to move the smoothed series must fail.
    rates = [base] * 12 + [base * (1 + jump_max * 2.5)] * 12
    res = vc.analyse(_rows_at(rates))
    if res["ok"]:
        return False, (f"a sustained {jump_max*2.5:.0%} step was not flagged: "
                       f"rolling spread {res['roll3_spread']:.2f}x")
    if not any("rolling" in p for p in res["problems"]):
        return False, f"the finding is not the rolling average: {res['problems']}"

    # A gradual change that stays INSIDE the spread ceiling must pass without a
    # jump finding. The total has to be inside the ceiling, not an arbitrary
    # multiple of the jump bar: an 87% ramp legitimately breaks the spread
    # check, and an earlier version of this test asserted otherwise and was
    # wrong about it.
    n = 24
    tot = (roll_max - 1.0) * 0.6
    ramp = [base * (1 + tot * i / (n - 1)) for i in range(n)]
    res2 = vc.analyse(_rows_at(ramp))
    if not res2["ok"]:
        return False, (f"a {tot:.0%} ramp over {n} lines, inside the "
                       f"{roll_max:.2f}x spread ceiling, was flagged: "
                       f"{res2['problems']}")
    return True, (f"the jump bar {jump_max:.0%} sits above the control p90 "
                  f"{float(ctl['jump_p90']):.0%}; a sustained "
                  f"{jump_max*2.5:.0%} step fails on the rolling average, a "
                  f"{tot:.0%} ramp inside the spread ceiling passes")


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


def _rows_at(rates: list, tag: str = "normal", words: int = 20,
             syls: int = 30, silence_frac: float = 0.2) -> list:
    """Rows as measure() produces them, at the given ARTICULATION rates."""
    out = []
    for i, wps in enumerate(rates, 1):
        speech = words / wps
        dur = speech / (1.0 - silence_frac)
        out.append({"line_id": i, "tag": tag, "words": words, "syls": syls,
                    "dur": round(dur, 3), "speech": round(speech, 3),
                    "silence": round(dur - speech, 3),
                    "wps": wps, "sps": syls / speech,
                    "wps_raw": words / dur, "rate_bump": 1.0})
    return out


def test_articulation_excludes_pauses() -> tuple[bool, str]:
    """Rate must be words per SPEAKING second, not per elapsed second.

    Raw WPM penalises short lines systematically: a fixed lead-in and trailing
    breath are a third of a 3-second line and a tenth of a 12-second one.
    MEASURED on the real draft, line 55 is 7 words in 3.06s with 1.00s of
    silence - 137 raw WPM, 204 articulated. It was the slowest line in the
    report and the whole reason the spread read 1.95x.
    """
    import subprocess
    import tempfile
    ff = config.ffmpeg()
    tmp = Path(tempfile.mkdtemp(prefix="artic_"))
    try:
        # 1s tone, 1s silence, 1s tone -> 3s long, 2s of speech
        p = tmp / "a.wav"
        subprocess.run(
            [ff, "-y", "-hide_banner", "-loglevel", "error",
             "-f", "lavfi", "-i", "sine=frequency=330:duration=1",
             "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-f", "lavfi", "-i", "sine=frequency=330:duration=1",
             "-filter_complex",
             "[1]atrim=duration=1[s];[0][s][2]concat=n=3:v=0:a=1[a]",
             "-map", "[a]", str(p)], check=True, capture_output=True)
        dur, speech, sil = vc.speech_seconds(p, ff)
        if abs(dur - 3.0) > 0.25:
            return False, f"duration read {dur:.2f}s, expected ~3.0s"
        if abs(sil - 1.0) > 0.35:
            return False, (f"detected {sil:.2f}s of silence, expected ~1.0s - "
                           f"the pause is not being excluded")
        if abs(speech - 2.0) > 0.35:
            return False, f"speech read {speech:.2f}s, expected ~2.0s"
        # and a short, pause-heavy line must not read as slow
        rows = _rows_at([3.5], words=7, silence_frac=0.33)
        r = rows[0]
        if r["wps_raw"] >= r["wps"]:
            return False, "the raw rate is not lower than the articulated rate"
        if abs(r["wps"] - 3.5) > 1e-6:
            return False, "articulated rate is not words/speech-time"
        return True, (f"a 3.0s file with a 1.0s pause measures {speech:.2f}s "
                      f"of speech; the rate is words per SPEAKING second, so a "
                      f"33%-silence line is not reported as slow")
    finally:
        shutil_rmtree(tmp)


def shutil_rmtree(p):
    import shutil as _sh
    _sh.rmtree(p, ignore_errors=True)


def test_ceilings_calibrated_on_control() -> tuple[bool, str]:
    """The ceilings must come from a CONTROL, not from taste.

    The old bars were 1.25x line spread and 8% adjacent jump, both picked by
    ear. A control - varied real lines, ONE identical delivery, only the words
    changing - measured a single consistent narrator at 1.38x (p95/p5) line
    spread, 1.20x rolling-3 spread and a 28% p90 adjacent jump. So the old bars
    were BELOW what a perfect narrator produces: the gate was unpassable, and
    it blocked a render whose base rate was dead on target.
    """
    p = Path(ROOT) / "config" / "voice_spread_control.json"
    if not p.exists():
        return False, ("no config/voice_spread_control.json - the ceilings are "
                       "not traceable to a measurement. Run "
                       "tools/calibrate_voice_spread.py --write")
    ctl = json.loads(p.read_text(encoding="utf-8"))
    line_c = float(getattr(config, "VOICE_LINE_SPREAD_MAX", 0))
    roll_c = float(getattr(config, "VOICE_ROLL3_SPREAD_MAX", 0))
    jump_c = float(getattr(config, "VOICE_ADJACENT_MAX_JUMP", 0))
    obs_line = float(ctl.get("line_spread_pct") or 0)
    obs_roll = float(ctl.get("roll3_spread_pct") or 0)
    obs_jump = float(ctl.get("jump_p90") or 0)
    if not (obs_line and obs_roll and obs_jump):
        return False, f"the control file is missing measurements: {ctl}"
    if int(ctl.get("n") or 0) < 15:
        return False, (f"the control used only {ctl.get('n')} lines - too few "
                       f"to set a gate threshold")
    # every ceiling must sit ABOVE what a consistent narrator produces
    for name, ceil, obs in (("line spread", line_c, obs_line),
                            ("rolling-3 spread", roll_c, obs_roll),
                            ("adjacent jump", jump_c, obs_jump)):
        if ceil < obs:
            return False, (f"the {name} ceiling ({ceil}) is BELOW the control "
                           f"({obs:.2f}) - it fails a narrator doing nothing "
                           f"wrong, which is what 1.25x did")
    # ...and not absurdly above it either, or it is not a gate
    if roll_c > obs_roll * 2.0:
        return False, (f"the rolling-3 ceiling ({roll_c}) is more than double "
                       f"the control ({obs_roll:.2f}) - that is not a gate")
    return True, (f"ceilings sit above the control: line {line_c} > "
                  f"{obs_line:.2f}, rolling-3 {roll_c} > {obs_roll:.2f}, jump "
                  f"{jump_c} > {obs_jump:.2f}, from {ctl['n']} control lines")


def test_consistent_narrator_passes() -> tuple[bool, str]:
    """POSITIVE fixture: control-like variation must PASS.

    Built from the control's own numbers - a 1.38x spread of single-line rates
    around the mean. A gate that fails this fails a narrator behaving perfectly.
    """
    import random
    rnd = random.Random(7)
    base = 240.0 / 60.0
    # a 1.38x spread, scattered so no three consecutive lines cluster
    rates = [base * rnd.uniform(1 / 1.175, 1.175) for _ in range(40)]
    res = vc.analyse(_rows_at(rates))
    if not res["ok"]:
        return False, (f"a control-like narrator was rejected: "
                       f"{res['problems']}")
    if res["line_spread"] < 1.25:
        return False, (f"the fixture's own spread is only "
                       f"{res['line_spread']:.2f}x, so it does not exercise "
                       f"the old 1.25x bar")
    return True, (f"single-line spread {res['line_spread']:.2f}x with a "
                  f"rolling-3 of {res['roll3_spread']:.2f}x passes - the old "
                  f"1.25x bar would have failed it")


def test_old_mapping_still_fails() -> tuple[bool, str]:
    """NEGATIVE fixture: the 1.53x per-tag mapping must still FAIL.

    This is the regression that matters. Relaxing the single-line bar must not
    make a genuinely inconsistent narrator acceptable - and what made the old
    mapping unacceptable was that whole TAGS ran at different speeds, which the
    tag-mean band and the rolling-3 average both catch.
    """
    # the real measured per-tag rates of the old mapping, WPM
    old = {"sad": 151.4, "reveal": 153.3, "normal": 188.3, "tense": 266.9}
    rows = []
    lid = 1
    # interleave tags the way a draft does, so the rolling average sees them
    for _ in range(8):
        for tag, wpm in old.items():
            r = _rows_at([wpm / 60.0], tag=tag)[0]
            r["line_id"] = lid
            lid += 1
            rows.append(r)
    res = vc.analyse(rows)
    if res["ok"]:
        return False, ("the old 1.53x mapping PASSED the recalibrated gate - "
                       "the relaxation went too far")
    blob = " ".join(res["problems"])
    if "tense" not in blob and "sad" not in blob:
        return False, (f"the finding does not name the offending tags: "
                       f"{res['problems']}")
    # and a single wild line must NOT fail on its own
    ok_rows = _rows_at([240.0 / 60.0] * 30)
    ok_rows[15]["wps"] = (240.0 * 1.6) / 60.0     # one outlier
    ok_rows[15]["speech"] = ok_rows[15]["words"] / ok_rows[15]["wps"]
    res2 = vc.analyse(ok_rows)
    if not res2["ok"]:
        return False, (f"ONE fast line among thirty failed the gate: "
                       f"{res2['problems']} - consistency is judged on tag "
                       f"means and a rolling average, not single lines")
    return True, (f"the old per-tag mapping fails on {len(res['problems'])} "
                  f"finding(s) naming the tags; one outlier line among thirty "
                  f"does not fail")


def test_real_draft_passes() -> tuple[bool, str]:
    """The shipped narration must pass, on real audio."""
    from pipeline import preflight as pf
    pdir = Path(config.project_dir("tokyodrift2006"))
    nd = pdir / "narration"
    if not (pdir / "draft.json").exists() or not nd.is_dir():
        return False, "SKIPPED - tokyodrift2006 narration not present"
    d = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    narr = [(l["id"], nd / f"line_{l['id']:03d}.mp3", 0.0)
            for l in d["lines"]
            if (nd / f"line_{l['id']:03d}.mp3").exists()]
    if len(narr) < 50:
        return False, f"only {len(narr)} narration files - nothing to judge"
    stale = set(pf.stale_audio(d, pdir))
    res = vc.analyse(vc.measure(d, narr, skip_ids=stale))
    if not res["ok"]:
        return False, f"the shipped narration fails: {res['problems']}"
    worst = max((abs(m["dev"]), t) for t, m in res["tag_means"].items()
                if m["n"] >= 3)
    return True, (f"{res['n']} lines, mean {res['mean_wpm']:.0f} WPM "
                  f"articulated, rolling-3 {res['roll3_spread']:.2f}x of "
                  f"{res['roll3_max']:.2f}x, worst tag {worst[1]} at "
                  f"{worst[0]:.1%} of the {config.VOICE_RATE_BAND:.0%} band")


def test_target_wpm_english_band() -> tuple[bool, str]:
    """The pace target must sit in the band MEASURED on English recaps.

    THE DEFECT: TARGET_WPM was 185, taken from a VIETNAMESE reference channel
    and transplanted across a language boundary where it does not hold -
    Vietnamese carries more meaning per syllable at the same tempo. The
    finished English recap sounds slow. Measured English recap channels run
    205-245 WPM.

    This also pins the relationship the whole pipeline depends on: the writer's
    fallback rate must TRACK the target, because every word budget is built
    for it. Inverting that is the regression [VOICE-RATE-DRIFT] exists to
    catch, and it has already happened once (the budget was re-cut to 141 to
    accommodate a voice that had slowed down).
    """
    lo, hi = 205.0, 245.0
    t = float(config.TARGET_WPM)
    if not (lo <= t <= hi):
        return False, (f"TARGET_WPM is {t:.0f}, outside the {lo:.0f}-{hi:.0f} "
                       f"WPM band measured on English recap channels")
    w = float(config.TTS_WORDS_PER_MINUTE)
    if abs(w - t) > 0.05 * t:
        return False, (f"TTS_WORDS_PER_MINUTE is {w:.0f} but TARGET_WPM is "
                       f"{t:.0f}; the writer's fallback rate must track the "
                       f"target or the word budgets are built for a pace the "
                       f"voice is not asked to deliver")
    return True, (f"TARGET_WPM {t:.0f} is inside the measured English band "
                  f"{lo:.0f}-{hi:.0f}, and the writer's rate tracks it")


def test_profile_measures_on_target() -> tuple[bool, str]:
    """The SIGNED profile must measure on TARGET_WPM, not near the old one.

    The profile is the evidence that the voice was actually made to hit the
    target rather than the target being quietly re-cut to whatever the voice
    does. A stale profile left over from a 185 calibration would keep every
    word budget 12% too generous while reporting success.
    """
    import json
    p = Path(ROOT) / "config" / "voice_profiles.json"
    if not p.exists():
        return False, "config/voice_profiles.json is missing"
    prof = json.loads(p.read_text(encoding="utf-8")).get("profiles") or {}
    live = None
    for k, v in prof.items():
        if str(v.get("voice_id")) == "Warren":
            live = v
            break
    if live is None:
        return False, "no profile for the production voice (Warren)"
    wps = float(live.get("words_per_sec") or 0.0)
    if wps <= 0:
        return False, "the profile records no measured words_per_sec"
    wpm = wps * 60.0
    drift = abs(wpm - float(config.TARGET_WPM)) / float(config.TARGET_WPM)
    if drift > float(config.VOICE_RATE_DRIFT_MAX):
        return False, (f"the signed profile measures {wpm:.1f} WPM against a "
                       f"{config.TARGET_WPM:.0f} target ({drift:+.1%}), "
                       f"outside VOICE_RATE_DRIFT_MAX "
                       f"({config.VOICE_RATE_DRIFT_MAX:.0%}) - re-run "
                       f"calibrate_rate.py --solve-per-tag --write-profile")
    return True, (f"the signed profile measures {wpm:.1f} WPM, "
                  f"{drift:+.1%} of the {config.TARGET_WPM:.0f} target")


def test_engine_cap_respected() -> tuple[bool, str]:
    """No tag may be configured past the engine's hard speakingRate ceiling.

    Inworld returns HTTP 400 above 1.5. Two tags (mystery, reveal) sit exactly
    ON that ceiling at the 210 target and still read ~7% slow. That shortfall
    is measured, bounded and inside the band - and it must not be "fixed" by
    writing 1.6 into the config, which would fail every request for those
    tags at render time rather than sounding slightly slower.
    """
    cap = float(config.VOICE_SPEAKING_RATE_MAX)
    bad = {k: v for k, v in config.VOICE_TAG_SPEAKING_RATE.items()
           if float(v) > cap + 1e-9}
    if bad:
        return False, (f"these tags are configured above the {cap} engine "
                       f"ceiling and would fail at render time: {bad}")
    at_cap = sorted(k for k, v in config.VOICE_TAG_SPEAKING_RATE.items()
                    if abs(float(v) - cap) < 1e-9)
    return True, (f"every tag rate is within the {cap} engine ceiling"
                  + (f"; at the ceiling: {', '.join(at_cap)}" if at_cap
                     else ""))


TESTS = {
    "TARGET-WPM-ENGLISH-BAND":      test_target_wpm_english_band,
    "PROFILE-MEASURES-ON-TARGET":   test_profile_measures_on_target,
    "ENGINE-CAP-RESPECTED":         test_engine_cap_respected,
    "ARTICULATION-EXCLUDES-PAUSES": test_articulation_excludes_pauses,
    "CEILINGS-FROM-CONTROL":        test_ceilings_calibrated_on_control,
    "CONSISTENT-NARRATOR-PASSES":   test_consistent_narrator_passes,
    "OLD-MAPPING-STILL-FAILS":      test_old_mapping_still_fails,
    "REAL-DRAFT-PASSES":            test_real_draft_passes,
    "CUES-CLEAN":           test_cues_clean,
    "PROFILE-STALE":        test_profile_stale_on_mapping_change,
    "CUES-CATCH-OLD":       test_cues_catch_old,
    "ONE-MODE-UNIFORM-RATE": test_one_mode_uniform_delivered_rate,
    "RATE-DRIFT-GATE":      test_rate_drift_gate,
    "CUE-WORD-BOUNDARIES":  test_cue_word_boundaries,
    "BUMP-IN-BAND":         test_bump_in_band,
    "SINGLE-LINE-REPORTED": test_single_line_reported_not_gated,
    "ROLLING-JUMP-GATE":    test_rolling_jump_gate,
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
