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
    if len(seen_rates) > 1:
        bad.append(f"speaking_rate differs across tags ({sorted(seen_rates)}). "
                   f"Emotion is carried by pauses and emphasis, not tempo - "
                   f"one rate for every tag.")
    if len(seen_modes) > 1:
        bad.append(f"delivery_mode differs across tags ({sorted(seen_modes)}). "
                   f"Mode changes timbre; use one for every tag.")
    return bad


def rate_band_violations(provider) -> list[str]:
    """Tag rate x the allowed rate_bump must stay inside the band."""
    import config
    base = float(config.VOICE_BASE_SPEAKING_RATE)
    band = float(config.VOICE_RATE_BAND)
    lo, hi = base * (1 - band), base * (1 + band)
    bad = []
    for tag in sorted(provider.delivery):
        try:
            r = float(provider.controls_for(tag).get("speaking_rate", base))
        except Exception:
            continue
        if not (lo - 1e-9 <= r <= hi + 1e-9):
            bad.append(f"{tag}: speaking_rate {r:.3f} is outside the "
                       f"+-{band*100:.0f}% band [{lo:.3f}, {hi:.3f}]")
    return bad


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
