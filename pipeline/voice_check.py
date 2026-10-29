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
    """Is the DELIVERED rate uniform across tags, per the measured profile?

    This replaces the old control-value check. The band applies to what the
    voice actually does, not to the number it was asked for: identical
    speaking_rates delivered rates 1.53x apart on this voice, because each
    steering cue costs a different amount of pace.

    An unmeasured voice returns a finding - rate_drift() says the same thing at
    more length, and both exist because "nobody measured" is the state the
    185 -> 134.6 WPM drift happened in.
    """
    import config
    from pipeline.calibration import production_profile
    band = float(config.VOICE_RATE_BAND)
    prof = production_profile()
    if not prof.is_measured or not prof.by_tag:
        return ["no measured per-tag profile, so delivered-rate uniformity "
                "cannot be checked (see [VOICE-RATE-DRIFT])"]
    agg = prof.words_per_sec or 0.0
    if agg <= 0:
        return ["the measured profile carries no aggregate rate"]
    bad = []
    for tag, row in sorted(prof.by_tag.items()):
        v = float(row.get("words_per_sec") or 0.0)
        if v <= 0:
            continue
        if int(row.get("samples") or 0) < 2:
            continue          # one reading is not a rate
        dev = v / agg - 1.0
        if abs(dev) > band:
            bad.append(f"{tag} DELIVERS {v*60:.0f} WPM, {dev:+.0%} off the "
                       f"{agg*60:.0f} WPM mean - outside +-{band:.0%}. Adjust "
                       f"that tag's speaking_rate to cancel its cue's pace "
                       f"cost (tools/calibrate_rate.py --solve-per-tag).")
    return bad


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

    out = []
    floor = int(config.VOICE_RATE_MIN_WORDS)
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
        out.append({"line_id": lid, "tag": str(ln.get("delivery") or "normal"),
                    "words": len(words), "syls": syls, "dur": round(d, 3),
                    "wps": len(words) / d, "sps": syls / d,
                    "rate_bump": float(ln.get("rate_bump") or 1.0)})
    return out


def analyse(rows: list[dict]) -> dict:
    """Ratio, per-tag means, adjacent jumps and outliers."""
    import config
    import statistics as st
    if len(rows) < 2:
        return {"rows": rows, "ok": True, "problems": [], "n": len(rows)}

    band = float(config.VOICE_RATE_BAND)
    ratio_max = float(config.VOICE_WPM_RATIO_MAX)
    jump_max = float(config.VOICE_ADJACENT_MAX_JUMP)

    wps = [r["wps"] for r in rows]
    sps = [r["sps"] for r in rows]
    problems: list[str] = []

    lo_r, hi_r = min(rows, key=lambda r: r["wps"]), max(rows, key=lambda r: r["wps"])
    ratio_w = hi_r["wps"] / lo_r["wps"] if lo_r["wps"] else 0.0
    ratio_s = (max(sps) / min(sps)) if min(sps) else 0.0
    if ratio_w > ratio_max and ratio_s > ratio_max:
        problems.append(
            f"slowest-to-fastest line is {ratio_w:.2f}x on words/sec and "
            f"{ratio_s:.2f}x on syllables/sec (ceiling {ratio_max:.2f}x): "
            f"line {lo_r['line_id']} ({lo_r['tag']}, {lo_r['wps']*60:.0f} WPM) "
            f"vs line {hi_r['line_id']} ({hi_r['tag']}, "
            f"{hi_r['wps']*60:.0f} WPM)")

    # per-tag means against the overall mean, on syllable rate
    mean_s = st.mean(sps)
    by_tag: dict = {}
    for r in rows:
        by_tag.setdefault(r["tag"], []).append(r)
    tag_means = {}
    for tag, rs in sorted(by_tag.items()):
        m = st.mean(x["sps"] for x in rs)
        tag_means[tag] = {"sps": m, "wpm": st.mean(x["wps"] for x in rs) * 60,
                          "n": len(rs), "dev": (m / mean_s - 1.0) if mean_s else 0.0}
        if mean_s and abs(m / mean_s - 1.0) > band and len(rs) >= 3:
            problems.append(
                f"tag {tag!r} averages {m/mean_s-1.0:+.0%} off the overall "
                f"rate ({st.mean(x['wps'] for x in rs)*60:.0f} WPM vs "
                f"{mean_s*60/1:.0f} syl/min overall) - outside the "
                f"+-{band:.0%} band over {len(rs)} line(s)")

    # adjacent jumps, in draft order
    jumps = []
    ordered = sorted(rows, key=lambda r: r["line_id"])
    for a, b in zip(ordered, ordered[1:]):
        if not a["sps"]:
            continue
        j = abs(b["sps"] / a["sps"] - 1.0)
        if j > jump_max:
            jumps.append((a["line_id"], b["line_id"], j,
                          a["tag"], b["tag"]))
    if jumps:
        worst = sorted(jumps, key=lambda x: -x[2])[:6]
        problems.append(
            f"{len(jumps)} adjacent pair(s) jump more than {jump_max:.0%} in "
            f"measured rate - ramp a mood change across intervening lines: "
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
            "problems": problems, "ratio_wps": ratio_w, "ratio_sps": ratio_s,
            "tag_means": tag_means, "mean_sps": mean_s,
            "mean_wpm": st.mean(wps) * 60, "jumps": jumps}


def report(res: dict, project: str = "") -> bool:
    """Print the verdict. Returns True if the narration may ship."""
    if res.get("n", 0) < 2:
        console.print("[dim]Voice: too few measurable lines to judge.[/]")
        return True
    import config
    console.print(
        f"[cyan]Voice:[/] {res['n']} line(s) measured, mean "
        f"{res['mean_wpm']:.0f} WPM, slowest-to-fastest "
        f"{res['ratio_wps']:.2f}x words/sec / {res['ratio_sps']:.2f}x "
        f"syllables/sec (ceiling {config.VOICE_WPM_RATIO_MAX:.2f}x)")
    for tag, m in sorted(res["tag_means"].items(),
                         key=lambda kv: kv[1]["sps"]):
        console.print(f"[dim]    {tag:<8} {m['wpm']:5.0f} WPM  "
                      f"{m['dev']:+.0%}  n={m['n']}[/]")
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
