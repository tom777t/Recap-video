"""ONE NARRATOR - the voice-consistency gate, measured on the real audio.

WHY
---
The first Warren render sounded like two or three different readers. The cause
was the tag -> controls mapping varying three things at once (deliveryMode,
steering cue, speaking_rate), measured at sad 151 WPM vs tense 267 WPM - a
1.77x spread.

Settings alone cannot prove the fix: steering is a request to a model, not a
knob on a waveform, so the only honest check is to measure the audio that came
back. This module does that and fails the render if the narrator is not one
person.

WHAT IT MEASURES
----------------
Three things, on every narrated line that is long enough to measure:

  RATIO      slowest to fastest line. config.VOICE_WPM_RATIO_MAX (1.25).
  TAG BAND   each tag's mean rate within config.VOICE_RATE_BAND (+-10%) of the
             overall mean. A tag may not be a different speed.
  ADJACENT   neighbour-to-neighbour change within
             config.VOICE_ADJACENT_MAX_JUMP (8%), so a mood change ramps
             instead of stepping.

A NOTE ON THE METRIC, because it matters
----------------------------------------
Words per second conflates two different things: how fast the reader talks, and
how long the words are. "He went to the car" and "Characteristically,
Dominic hesitated" at an identical speaking rate differ by about 2x in words/
second. So WPM alone will fail a gate for writing, not for reading.

This module therefore computes BOTH and gates on the stricter reading of the
pair:
  * words/sec  - what was asked for, reported first
  * syllables/sec - the honest proxy for speaking rate
A line is only reported as an outlier when it is an outlier on SYLLABLE rate
too. That keeps the gate pointed at the narrator rather than the vocabulary.
Lines under config.VOICE_RATE_MIN_WORDS words are excluded entirely: on a
4-word line the lead-in and trailing silence dominate the measurement.
"""
from __future__ import annotations

import re
from pathlib import Path

from rich.console import Console

console = Console()

# Words a steering cue may not contain. The old cues instructed tempo and
# character, which is what made the narrator inconsistent; this list is what
# stops them returning one tag at a time.
BANNED_CUE_WORDS = (
    # tempo
    "fast", "faster", "slow", "slower", "quick", "quickly", "rapid",
    "clipped", "driving", "rushed", "hurried", "drag", "pace", "speed",
    "brisk", "urgen",          # urgent / urgency
    # voice character / timbre
    "whisper", "whispers", "hushed", "shout", "shouting", "scream", "growl",
    "breathy", "nasal", "gravel", "falsetto", "pitch", "deeper", "higher",
    "low tone", "subdued", "with force", "forceful", "accent", "lisp",
    "childlike", "robotic", "sing",
)

# What a cue IS allowed to be about.
ALLOWED_CUE_HINTS = ("pause", "pauses", "emphasis", "emphasise", "emphasize",
                     "phrasing", "consonant", "stress", "even", "gentle",
                     "clear", "land", "beat")


# --------------------------------------------------------------------------- #
# ARTICULATION RATE - the rate the voice actually talks at
# --------------------------------------------------------------------------- #
# Raw words-per-second over a file's whole duration is SPEECH RATE: it counts
# every pause as if the narrator were talking through it. That is the wrong
# measurement for voice consistency, and it fails in a specific, systematic
# direction - SHORT LINES ARE PENALISED, because a fixed lead-in and trailing
# breath are a much larger fraction of a 3-second line than of a 12-second one.
#
# MEASURED on this draft: line 55 is 7 words in 3.06s with 1.00s of silence -
# 33% of the file. Raw 137 WPM, ARTICULATION 204 WPM. It was the slowest line
# in the gate's report and the single reason the spread read 1.95x. Line 63 is
# the same story (32% silence, 162 raw vs 237 articulated).
#
# So the rate is computed over SPEECH TIME: duration minus every detected
# silence. That also removes deliberate pauses - the emphasis cues ask for
# them, and a pause the direction asked for is not the narrator changing pace.
SILENCE_THRESHOLD_DB = -35.0
SILENCE_MIN_SEC = 0.12
_ARTIC_CACHE = "_articulation.json"


def speech_seconds(path, ffmpeg: str | None = None,
                   cache: dict | None = None) -> tuple:
    """(duration, speech_sec, silence_sec) for one audio file.

    ffmpeg's silencedetect is the measurement. Cached by (size, mtime) because
    probing a hundred files takes minutes and the answer never changes for a
    file that has not changed.
    """
    import json
    import re
    import subprocess
    import config
    p = Path(path)
    if not p.exists():
        return 0.0, 0.0, 0.0
    key = f"{p.name}:{p.stat().st_size}:{int(p.stat().st_mtime)}"
    if cache is not None and key in cache:
        d, s = cache[key]
        return float(d), float(s), float(d) - float(s)

    ff = ffmpeg or config.ffmpeg()
    r = subprocess.run(
        [ff, "-hide_banner", "-nostats", "-i", str(p),
         "-af", f"silencedetect=noise={SILENCE_THRESHOLD_DB}dB:"
                f"d={SILENCE_MIN_SEC}",
         "-f", "null", "-"], capture_output=True, text=True)
    log = r.stderr or ""
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", log)
    if not m:
        return 0.0, 0.0, 0.0
    dur = (int(m.group(1)) * 3600 + int(m.group(2)) * 60
           + float(m.group(3)))
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    sil = 0.0
    for i, a in enumerate(starts):
        b = ends[i] if i < len(ends) else dur   # a silence running to the end
        sil += max(0.0, min(b, dur) - a)
    sil = min(sil, dur)
    speech = max(0.05, dur - sil)
    if cache is not None:
        cache[key] = [round(dur, 3), round(speech, 3)]
    return dur, speech, sil


def _load_artic_cache(pdir) -> tuple:
    import json
    p = Path(pdir) / "narration" / _ARTIC_CACHE
    try:
        return json.loads(p.read_text(encoding="utf-8")), p
    except Exception:
        return {}, p


def _save_artic_cache(cache: dict, path) -> None:
    import json
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(cache, indent=0, sort_keys=True),
                              encoding="utf-8")
    except Exception:
        pass


def _pct_spread(values: list, lo: float = 0.05, hi: float = 0.95) -> float:
    """p95/p5 ratio - a spread that does not grow with the sample size.

    max/min does grow with it, so a ceiling calibrated on 20 control readings
    is systematically unfair to a 100-line draft. Small samples fall back to
    max/min because a percentile of six numbers is not a percentile.
    """
    v = sorted(x for x in values if x and x > 0)
    if len(v) < 2:
        return 1.0
    if len(v) < 10:
        return v[-1] / v[0]
    a = v[max(0, min(len(v) - 1, int(len(v) * lo)))]
    b = v[max(0, min(len(v) - 1, int(len(v) * hi)))]
    return (b / a) if a else 1.0


def _syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    n, prev_v = 0, False
    for ch in w:
        v = ch in "aeiouy"
        if v and not prev_v:
            n += 1
        prev_v = v
    if w.endswith("e") and n > 1:
        n -= 1
    return max(1, n)


def audit_cues(provider) -> list[str]:
    """Problems with a provider's steering cues. Empty list = clean.

    Checked as a RULE rather than reviewed by eye, because the failure mode is
    one tag quietly regaining a tempo instruction.
    """
    bad = []
    seen_rates, seen_modes, uncued = set(), set(), []
    for tag in sorted(provider.delivery):
        try:
            c = provider.controls_for(tag)
        except Exception as e:
            bad.append(f"{tag}: controls could not be resolved ({e})")
            continue
        cue = str(c.get("cue") or "")
        low = cue.lower()
        for w in BANNED_CUE_WORDS:
            # WORD BOUNDARIES, not substrings: a plain `in` test matched "sing"
            # inside "phrasing" and "closing" and condemned three legitimate
            # cues. Prefix entries (urgen, whisper) are matched at the start of
            # a word so "urgency"/"urgent" and "whispers" are still caught.
            if re.search(r"\b" + re.escape(w), low):
                bad.append(f"{tag}: cue {cue!r} contains {w!r} - cues may ask "
                           f"for pauses and emphasis only, not tempo or voice "
                           f"character")
        if not cue.strip():
            uncued.append(tag)
        elif not any(h in low for h in ALLOWED_CUE_HINTS):
            bad.append(f"{tag}: cue {cue!r} does not ask for a pause or an "
                       f"emphasis - say what it should do, not how to sound")
        if "speaking_rate" in c:
            seen_rates.add(round(float(c["speaking_rate"]), 4))
        if "delivery_mode" in c:
            seen_modes.add(str(c["delivery_mode"]))

    if uncued:
        bad.append(f"tag(s) {uncued} carry no cue at all. A cue costs ~23% of "
                   f"pace whatever it says, so an uncued tag reads that much "
                   f"faster than every cued one - give it a mild cue.")
    # NOTE ON WHAT IS AND IS NOT CHECKED HERE.
    # This used to require ONE speaking_rate for every tag, and that was the
    # right rule while rates were being used to CREATE different tempos - the
    # original defect, where `tense` ran at 1.32 and `sad` at 1.12 and the
    # narrator sounded like three people.
    #
    # It is the wrong rule now. A steering cue costs pace (measured: a pause
    # instruction costs 27%), and different cues cost different amounts, so an
    # identical control value DELIVERS different rates - 1.53x apart on this
    # voice. The per-tag rates now exist only to CANCEL that, and the thing
    # that must be uniform is the DELIVERED rate.
    #
    # So the control value is checked only against the ENGINE's limits, and
    # uniformity is gated on the measurement instead - measured_uniformity()
    # below, plus rate_drift() for the base pace. Gating the observable rather
    # than the knob is strictly stronger: it cannot be satisfied by a setting
    # that fails to take effect.
    _cap = float(getattr(config_mod(), "VOICE_SPEAKING_RATE_MAX", 1.5))
    for tag in sorted(provider.delivery):
        try:
            r = float(provider.controls_for(tag).get("speaking_rate", 1.0))
        except Exception:
            continue
        if not (0.5 - 1e-9 <= r <= _cap + 1e-9):
            bad.append(f"{tag}: speaking_rate {r:.3f} is outside the engine's "
                       f"[0.50, {_cap:.2f}] range - Inworld rejects it with an "
                       f"HTTP 400.")
    if len(seen_modes) > 1:
        bad.append(f"delivery_mode differs across tags ({sorted(seen_modes)}). "
                   f"Mode changes timbre; use one for every tag.")
    return bad


def config_mod():
    import config
    return config


def measured_uniformity() -> list[str]:
    """Does a measured profile exist at all? That is ALL this checks now.

    It used to compare each tag's rate from the voice profile against the
    aggregate - but the profile stores RAW rate (duration-based), because that
    is what the word BUDGET needs to predict how long a line will run. Judging
    voice consistency on raw rate counts deliberate pauses as slow talking, and
    it produced exactly the false finding this gate was fixed for: `sad` reads
    -11% on raw rate and -0.1% on ARTICULATION. It is the same person talking
    at the same speed with more pauses in it, which is the point of the tag.

    Two measurements, two purposes:
      raw rate         -> the word budget (how long will this line run)
      articulation     -> voice consistency (does it sound like one narrator)

    So the per-tag band is checked on ARTICULATION, in analyse(), against real
    audio. Nothing here duplicates it, because the duplicate disagreed.
    """
    from pipeline.calibration import production_profile
    prof = production_profile()
    if not prof.is_measured:
        return ["no measured voice profile, so the word budget has no basis "
                "(see [VOICE-RATE-DRIFT])"]
    return []


def rate_band_violations(provider) -> list[str]:
    """Kept for callers; the band now applies to the MEASURED rate.

    See measured_uniformity(). The control value is validated against the
    engine's limits inside audit_cues().
    """
    return measured_uniformity()


def rate_drift() -> tuple[bool, str]:
    """[VOICE-RATE-DRIFT] - has the voice's MEASURED pace left the target?

    Returns (ok, message).

    THE FAILURE THIS EXISTS FOR, in order:
      1. the delivery mapping was flattened for voice consistency
      2. that gave every tag a steering cue, and a cue costs ~20-27% of pace
      3. the voice fell from ~185 WPM to 134.6 WPM
      4. nothing noticed, because nothing was measuring
      5. the word budget was re-calibrated DOWN to 141 to match, shrinking
         every line's allowance by a third to accommodate the regression
      6. the draft then "fit" - at 21.7 minutes instead of 16.5

    Step 4 is the one to kill. config.TARGET_WPM is a DECISION about the
    writing; the voice is what gets adjusted to meet it. So this fails when the
    measured rate drifts, and it fails when there is NO measurement at all -
    because "unmeasured" is exactly the state in which the drift happened.

    A mapping change invalidates the measured profile automatically
    (calibration.mapping_signature), so changing a cue puts this gate into its
    unmeasured state, which is the re-measurement trigger.
    """
    import config
    from pipeline.calibration import production_profile, production_voice_key
    target = float(getattr(config, "TARGET_WPM", 185.0))
    tol = float(getattr(config, "VOICE_RATE_DRIFT_MAX", 0.10))
    prof = production_profile()
    if not prof.is_measured:
        return False, (
            f"the production voice has NO valid measurement, so its pace is "
            f"unknown. That is the state the 185 -> 134.6 WPM drift happened "
            f"in. Re-measure on real audio:\n"
            f"    python tools/calibrate_rate.py --project <p>        "
            f"(check the live mapping)\n"
            f"    python -m pipeline.calibration --project <p> "
            f"--voice-key {production_voice_key()}\n"
            f"  A delivery-mapping change voids the profile on purpose - that "
            f"is the trigger, not a bug.")
    got = prof.words_per_sec * 60.0
    dev = got / target - 1.0
    if abs(dev) > tol:
        return False, (
            f"measured {got:.1f} WPM against a {target:.0f} WPM target "
            f"({dev:+.1%}, tolerance +-{tol:.0%}). Fix the VOICE, not the "
            f"budget: raise or lower the speaking rate until it measures on "
            f"target -\n"
            f"    python tools/calibrate_rate.py --project <p> "
            f"--solve-per-tag --write\n"
            f"  Re-cutting the word budget to match a slower voice is how a "
            f"17-minute recap silently became a 22-minute one.")
    return True, f"measured {got:.1f} WPM, {dev:+.1%} of the {target:.0f} target"


def bump_in_band(rate_bump: float) -> bool:
    """Is a per-line rate_bump inside the same band as the tags?

    Fitting a line to its window is not an exemption from sounding like the
    same person, so a bump counts against the voice band too.
    """
    import config
    band = float(config.VOICE_RATE_BAND)
    b = float(rate_bump or 1.0)
    return (1.0 - band) - 1e-9 <= b <= (1.0 + band) + 1e-9


def measure(draft: dict, narration: list, ffprobe: str | None = None,
            skip_ids: set | None = None) -> list[dict]:
    """Per-line measured rate. [{line_id, tag, words, syls, dur, wps, sps}]."""
    import config
    from pipeline.preflight import _audio_dur
    if ffprobe is None:
        ffprobe = config.ffprobe()
    skip = set(skip_ids or ())
    dur_by_id = {}
    for item in narration or []:
        try:
            lid, path = item[0], Path(item[1])
            d = float(item[2]) if len(item) > 2 and item[2] else 0.0
        except (TypeError, ValueError, IndexError):
            continue
        if d <= 0 and path.exists():
            d = _audio_dur(ffprobe, path)
        dur_by_id[lid] = d

    # ARTICULATION, not speech rate: the pauses come out before the division.
    pdir = None
    for item in narration or []:
        try:
            pdir = Path(item[1]).parent.parent
            break
        except Exception:
            pass
    cache, cache_path = _load_artic_cache(pdir) if pdir else ({}, None)
    ff = config.ffmpeg()

    out = []
    floor = int(config.VOICE_RATE_MIN_WORDS)
    path_by_id = {}
    for item in narration or []:
        try:
            path_by_id[item[0]] = Path(item[1])
        except Exception:
            pass

    for ln in draft.get("lines", []):
        lid = ln.get("id")
        if lid in skip:
            continue
        text = str(ln.get("narration") or "").strip()
        if not text:
            continue
        d = float(dur_by_id.get(lid) or 0.0)
        if d <= 0.2:
            continue
        words = text.split()
        if len(words) < floor:
            continue
        syls = sum(_syllables(w) for w in words)
        p = path_by_id.get(lid)
        speech, sil = d, 0.0
        if p is not None:
            _d, _speech, _sil = speech_seconds(p, ff, cache)
            if _d > 0:
                d, speech, sil = _d, _speech, _sil
            # If the file cannot be probed we still know the duration the
            # caller handed us, so the line is measured as if it were all
            # speech rather than DROPPED. Silently discarding lines would
            # shrink the sample the gate judges on, which is the opposite of
            # what a consistency check needs.
        if speech <= 0.05:
            continue
        out.append({"line_id": lid, "tag": str(ln.get("delivery") or "normal"),
                    "words": len(words), "syls": syls, "dur": round(d, 3),
                    "speech": round(speech, 3), "silence": round(sil, 3),
                    # rates over SPEECH time
                    "wps": len(words) / speech, "sps": syls / speech,
                    # kept for reporting: what the raw figure would have been
                    "wps_raw": len(words) / d,
                    "rate_bump": float(ln.get("rate_bump") or 1.0)})
    if cache_path is not None:
        _save_artic_cache(cache, cache_path)
    return out


def analyse(rows: list[dict]) -> dict:
    """Ratio, per-tag means, adjacent jumps and outliers."""
    import config
    import statistics as st
    if len(rows) < 2:
        return {"rows": rows, "ok": True, "problems": [], "n": len(rows)}

    band = float(config.VOICE_RATE_BAND)
    jump_max = float(config.VOICE_ADJACENT_MAX_JUMP)
    line_max = float(getattr(config, "VOICE_LINE_SPREAD_MAX", 1.55))
    roll_max = float(getattr(config, "VOICE_ROLL3_SPREAD_MAX", 1.37))

    wps = [r["wps"] for r in rows]
    problems: list[str] = []
    ordered = sorted(rows, key=lambda r: r["line_id"])

    # ---- SINGLE-LINE SPREAD IS REPORTED, NOT GATED ---------------------- #
    # A control run (varied real lines, ONE identical delivery, only the words
    # changing) measured a 1.35x line-to-line spread. So single-line variation
    # of that order is what a perfectly consistent narrator DOES - gating on it
    # at 1.25x blocked a render whose base rate was dead on target. The ceiling
    # here is calibrated from the control plus a margin and exists only to
    # catch something far outside it; consistency is judged on the aggregates
    # below, which is what a listener actually perceives.
    lo_r = min(rows, key=lambda r: r["wps"])
    hi_r = max(rows, key=lambda r: r["wps"])
    ratio_w = hi_r["wps"] / lo_r["wps"] if lo_r["wps"] else 0.0

    # ---- TAG MEANS ------------------------------------------------------- #
    mean_w = st.mean(wps)
    by_tag: dict = {}
    for r in rows:
        by_tag.setdefault(r["tag"], []).append(r)
    tag_means = {}
    for tag, rs in sorted(by_tag.items()):
        m = st.mean(x["wps"] for x in rs)
        tag_means[tag] = {"wps": m, "wpm": m * 60, "n": len(rs),
                          "dev": (m / mean_w - 1.0) if mean_w else 0.0}
        # A tag needs at least 3 readings to have a mean worth judging. Below
        # that the "mean" is one or two lines and the finding is noise.
        if mean_w and abs(m / mean_w - 1.0) > band and len(rs) >= 3:
            problems.append(
                f"tag {tag!r} averages {m/mean_w-1.0:+.0%} off the overall "
                f"articulation rate ({m*60:.0f} vs {mean_w*60:.0f} WPM) over "
                f"{len(rs)} line(s) - outside +-{band:.0%}. Adjust that tag's "
                f"speaking_rate (tools/calibrate_rate.py --solve-per-tag).")

    # ---- ROLLING 3-LINE AVERAGE ------------------------------------------ #
    # What a viewer hears is a stretch, not a line. A single fast line between
    # two ordinary ones is not a different narrator; three fast lines in a row
    # is. The control measured a 1.19x rolling spread, so the ceiling is set
    # from that.
    roll = [st.mean(r["wps"] for r in ordered[i:i + 3])
            for i in range(max(0, len(ordered) - 2))]
    # PERCENTILE RANGE, not max/min. The ceiling is calibrated on a 20-line
    # control and applied to a 100-line draft, and max/min grows with sample
    # size on its own - so a max/min bar derived from 20 readings is unfair to
    # 100 and the draft passed by 0.00x, which is not a measurement, it is a
    # coincidence. p95/p5 estimates the same thing without that dependence,
    # and the control reports the identical statistic.
    roll_spread = _pct_spread(roll)
    if roll_spread > roll_max:
        iw = max(range(len(roll)), key=lambda i: roll[i])
        ib = min(range(len(roll)), key=lambda i: roll[i])
        problems.append(
            f"the rolling 3-line average swings {roll_spread:.2f}x (ceiling "
            f"{roll_max:.2f}x): lines "
            f"{[r['line_id'] for r in ordered[ib:ib+3]]} average "
            f"{roll[ib]*60:.0f} WPM against "
            f"{[r['line_id'] for r in ordered[iw:iw+3]]} at "
            f"{roll[iw]*60:.0f} WPM")

    # adjacent jumps, measured on the ROLLING average so one line cannot
    # trigger a finding on its own
    jumps = []
    for i in range(len(roll) - 1):
        if not roll[i]:
            continue
        j = abs(roll[i + 1] / roll[i] - 1.0)
        if j > jump_max:
            jumps.append((ordered[i]["line_id"], ordered[i + 1]["line_id"], j,
                          ordered[i]["tag"], ordered[i + 1]["tag"]))
    if jumps:
        worst = sorted(jumps, key=lambda x: -x[2])[:6]
        problems.append(
            f"{len(jumps)} place(s) where the rolling 3-line average jumps "
            f"more than {jump_max:.0%} - ramp a mood change across "
            f"intervening lines: "
            + ", ".join(f"{a}->{b} {j:+.0%} ({ta}->{tb})"
                        for a, b, j, ta, tb in worst))

    # a rate_bump outside the voice band
    for r in rows:
        if not bump_in_band(r["rate_bump"]):
            problems.append(
                f"line {r['line_id']} carries rate_bump "
                f"{r['rate_bump']:.3f}, outside the +-{band:.0%} voice band - "
                f"fitting a line to its window is not an exemption from "
                f"sounding like the same narrator")

    return {"rows": rows, "n": len(rows), "ok": not problems,
            "problems": problems, "ratio_wps": ratio_w,
            "line_spread": ratio_w, "line_spread_max": line_max,
            "roll3_spread": roll_spread, "roll3_max": roll_max,
            "slowest": lo_r, "fastest": hi_r,
            "tag_means": tag_means, "mean_wps": mean_w,
            "mean_wpm": mean_w * 60, "jumps": jumps,
            "mean_silence_pct": (100.0 * st.mean(
                r.get("silence", 0.0) / r["dur"] for r in rows
                if r.get("dur")) if rows else 0.0)}


def report(res: dict, project: str = "") -> bool:
    """Print the verdict. Returns True if the narration may ship."""
    if res.get("n", 0) < 2:
        console.print("[dim]Voice: too few measurable lines to judge.[/]")
        return True
    import config
    console.print(
        f"[cyan]Voice:[/] {res['n']} line(s), mean "
        f"{res['mean_wpm']:.0f} WPM ARTICULATED "
        f"(pauses excluded; {res['mean_silence_pct']:.0f}% of the audio is "
        f"silence)")
    console.print(
        f"[dim]    rolling 3-line spread {res['roll3_spread']:.2f}x "
        f"(ceiling {res['roll3_max']:.2f}x)   |   single-line spread "
        f"{res['line_spread']:.2f}x, reported not gated (a one-delivery "
        f"control measures 1.35x)[/]")
    for tag, m in sorted(res["tag_means"].items(),
                         key=lambda kv: kv[1]["wps"]):
        _f = "" if abs(m["dev"]) <= float(config.VOICE_RATE_BAND) \
            or m["n"] < 3 else "   <-- outside the band"
        console.print(f"[dim]    {tag:<8} {m['wpm']:5.0f} WPM  "
                      f"{m['dev']:+6.0%}  n={m['n']}{_f}[/]")
    if res["ok"]:
        console.print("[cyan]    one narrator - within the band.[/]")
        return True
    console.print("[red]  VOICE CONSISTENCY failed:[/]")
    for p in res["problems"]:
        console.print(f"[red]    {p}[/]")
    console.print(
        f"[yellow]  The tag mapping is in pipeline/tts_providers.py "
        f"(_inworld). One deliveryMode, one speaking_rate, pause/emphasis "
        f"cues only. After changing it, delete the affected "
        f"projects/{project or '<project>'}/narration/*.mp3 so they "
        f"re-synthesize, then re-measure with "
        f"`python -m pipeline.calibration --project {project or '<project>'} "
        f"--voice-key inworld-Warren_default`.[/]")
    return False
