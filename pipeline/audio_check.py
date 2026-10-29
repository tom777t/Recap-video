"""Measure the FINISHED MIX. Nothing in here reads the plan.

Companion to pipeline/probe.py, which measures the finished picture. Three
audible defects were reported after watching a whole render, and not one of
them could have been caught by the checks that existed, because every audio
check validated the PLAN - it confirmed that a gain had been written into a
filtergraph, never that the result was audible:

  * the film's separated stem played under ALL 111 lines, so its artefacts
    were a constant processed-sounding bed;
  * both <film_speaks> units were INAUDIBLE - the moment the film is handed
    the floor, only music was heard;
  * the music CUES were not audible against the bed they are supposed to lift
    out of.

So this module opens final.mp4 and measures it. Everything it returns is a
number in dB or LUFS that can be put next to a claim.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import config

# Integrated loudness needs 3s of signal to mean anything (the gating block is
# 400ms with a 3s window); below that, report RMS instead of pretending.
LUFS_MIN_WINDOW_SEC = 3.0


def _pcm(path: Path, start: float, dur: float, sr: int = 8000):
    """Mono float32 samples for one window, decoded by ffmpeg."""
    import numpy as np
    cmd = [config.ffmpeg(), "-v", "error", "-ss", f"{max(0.0, start):.3f}",
           "-t", f"{max(0.01, dur):.3f}", "-i", str(path),
           "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return np.zeros(0, dtype="float32")
    return np.frombuffer(r.stdout, dtype="<f4")


def rms_db(path: Path, start: float, dur: float) -> float:
    """RMS level of one window, in dBFS. -120.0 for silence."""
    import numpy as np
    x = _pcm(Path(path), start, dur)
    if x.size == 0:
        return -120.0
    v = float(np.sqrt(np.mean(np.square(x.astype("float64")))))
    return 20.0 * np.log10(v) if v > 1e-9 else -120.0


def lufs(path: Path, start: float, dur: float) -> float | None:
    """Integrated LUFS of one window, or None if the window is too short.

    Returning None rather than a number is deliberate: an integrated reading
    over 0.8s of audio is not a quiet measurement, it is a meaningless one,
    and a meaningless number next to a threshold is how a check comes to look
    rigorous while deciding nothing.
    """
    if float(dur) < LUFS_MIN_WINDOW_SEC:
        return None
    cmd = [config.ffmpeg(), "-hide_banner", "-nostats",
           "-ss", f"{max(0.0, start):.3f}", "-t", f"{dur:.3f}",
           "-i", str(path), "-vn", "-af", "ebur128=framelog=verbose",
           "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    best = None
    for m in re.finditer(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", r.stderr or ""):
        best = float(m.group(1))
    return best


def correlation(a, b, max_lag: int = 400) -> float:
    """Peak normalised cross-correlation between two windows, 0.0 .. 1.0.

    This is how "is the film's stem actually in this part of the mix?" gets
    answered without reading the filtergraph. The stem is mixed in at -17 dB
    under narration and music, so its LEVEL tells you nothing - but its
    waveform is still in there, and it correlates with the stem file it came
    from. Narration and music do not.

    `max_lag` allows for the clip's lead-in and any resampling offset.
    """
    import numpy as np
    if a.size < 64 or b.size < 64:
        return 0.0
    n = min(a.size, b.size)
    a = a[:n].astype("float64")
    b = b[:n].astype("float64")
    a -= a.mean()
    b -= b.mean()
    da, db = np.std(a), np.std(b)
    if da < 1e-9 or db < 1e-9:
        return 0.0
    a /= da
    b /= db
    best = 0.0
    lags = range(-int(max_lag), int(max_lag) + 1, 4)
    for lag in lags:
        if lag < 0:
            x, y = a[-lag:], b[:lag]
        elif lag > 0:
            x, y = a[:-lag], b[lag:]
        else:
            x, y = a, b
        if x.size < 64:
            continue
        c = abs(float(np.dot(x, y)) / x.size)
        if c > best:
            best = c
    return min(1.0, best)


def stem_presence(final: Path, stem: Path, rows: list,
                  sample_sec: float = 4.0) -> list:
    """Is the film's stem really in the mix where it is supposed to be?

    `rows` = [{"line_id", "final_at", "source_at", "want"}] - where the line
    sits in the FINISHED file, where its footage came from in the source, and
    whether film audio was supposed to be on.

    Returns the same rows with a measured `corr`. The verdict is comparative,
    not absolute: what matters is that windows which should carry the stem
    correlate clearly more than windows which should not.
    """
    out = []
    for r in rows:
        a = _pcm(Path(final), float(r["final_at"]), sample_sec)
        b = _pcm(Path(stem), float(r["source_at"]), sample_sec)
        out.append(dict(r, corr=round(correlation(a, b), 4)))
    return out


def film_speaks_margin(final: Path, units: list,
                       ref_gap: float = 2.5) -> list:
    """How much louder is a <film_speaks> unit than the music around it?

    `units` = [{"line_id", "final_at", "dur"}].

    THE DEFECT: in both units only the music was heard. The unit is the one
    moment the film is deliberately given the floor, so it has to be the
    loudest thing there - and "the gain is in the graph" was not evidence,
    because the bed and the cues were still running underneath at full level.

    Measures the unit's own window against the music-only windows immediately
    before and after it, and reports the difference in dB. A positive margin
    means the film is on top, which is the whole point of the unit.
    """
    out = []
    for u in units:
        at, dur = float(u["final_at"]), float(u["dur"])
        inside = rms_db(final, at + 0.15, max(0.3, dur - 0.3))
        before = rms_db(final, max(0.0, at - ref_gap - 0.2), ref_gap)
        after = rms_db(final, at + dur + 0.2, ref_gap)
        ref = max(before, after)      # the louder neighbour is the fair test
        out.append(dict(u,
                        inside_db=round(inside, 2),
                        before_db=round(before, 2),
                        after_db=round(after, 2),
                        margin_db=round(inside - ref, 2),
                        inside_lufs=lufs(final, at + 0.15,
                                         max(0.3, dur - 0.3))))
    return out


def cue_vs_bed(final: Path, cues: list, pad: float = 1.0) -> list:
    """Does each music cue measure louder than the bed around it?

    `cues` = [{"at", "dur", "mood"}] on the FINISHED timeline.

    THE DEFECT: the cues were inaudible. The gains were real and in the
    filtergraph - they were applied to source files whose own loudness varied
    by more than the gain did, so a "+10 dB" cue built from a quiet file still
    sat under the bed. Normalising every music file to a known loudness BEFORE
    the gains is what makes the gain mean something, and this is the check
    that it worked.
    """
    out = []
    for c in cues:
        at, dur = float(c["at"]), float(c["dur"])
        inside = rms_db(final, at + 0.2, max(0.4, dur - 0.4))
        before = rms_db(final, max(0.0, at - pad - 0.3), pad)
        after = rms_db(final, at + dur + 0.3, pad)
        neigh = [x for x in (before, after) if x > -119.0]
        ref = (sum(neigh) / len(neigh)) if neigh else -120.0
        out.append(dict(c,
                        inside_db=round(inside, 2),
                        bed_db=round(ref, 2),
                        lift_db=round(inside - ref, 2),
                        inside_lufs=lufs(final, at + 0.2,
                                         max(0.4, dur - 0.4))))
    return out


# Correlation thresholds, calibrated on a control mix rather than picked.
# pink noise as the "stem", a 330 Hz tone as the "music":
#     stem mixed in at -17 dB -> corr 0.293
#     stem absent             -> corr 0.006
# a 49x separation, while the two mixes differ in RMS by only 0.4 dB - which
# is the whole reason this is measured by correlation and not by level.
# The bars sit well inside that gap, with room for narration and music in the
# real mix pushing the "present" figure down.
STEM_PRESENT_MIN = 0.040
STEM_ABSENT_MAX = 0.025


def check_film_audio_placement(final: Path, stem: Path, rows: list) -> tuple:
    """Is the film's track where the rule says, and nowhere else?

    `rows` as for stem_presence, each with `want` True/False.

    Returns (ok, findings, measured_rows). Judged comparatively AND absolutely:
    an ON window must correlate above STEM_PRESENT_MIN, an OFF window must
    stay below STEM_ABSENT_MAX, and the ON mean must exceed the OFF mean.
    Comparative alone would pass a render with the stem missing everywhere;
    absolute alone would be a bar picked by feel.
    """
    if not Path(stem).exists():
        return True, [], []
    got = stem_presence(Path(final), Path(stem), rows)
    on = [r for r in got if r.get("want")]
    off = [r for r in got if not r.get("want")]
    find = []
    for r in off:
        if r["corr"] > STEM_ABSENT_MAX:
            find.append(
                f"line {r['line_id']} at {r['final_at']:.1f}s should have NO "
                f"film audio but correlates {r['corr']:.3f} with the stem "
                f"(bar {STEM_ABSENT_MAX})")
    weak = [r for r in on if r["corr"] < STEM_PRESENT_MIN]
    if on and len(weak) > len(on) // 2:
        find.append(
            f"{len(weak)} of {len(on)} action/tense window(s) do NOT carry "
            f"the film's track: "
            + ", ".join(f"line {r['line_id']} {r['corr']:.3f}"
                        for r in weak[:6]))
    if on and off:
        mon = sum(r["corr"] for r in on) / len(on)
        moff = sum(r["corr"] for r in off) / len(off)
        if mon <= moff:
            find.append(
                f"the film's track is not placed by the rule at all: "
                f"action/tense windows average {mon:.3f} and the rest "
                f"average {moff:.3f}")
    return (not find), find, got


def integrated(path: Path) -> float | None:
    """Integrated loudness of a whole file, in LUFS."""
    cmd = [config.ffmpeg(), "-hide_banner", "-nostats", "-i", str(path),
           "-vn", "-af", "ebur128=framelog=verbose", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    best = None
    for m in re.finditer(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", r.stderr or ""):
        best = float(m.group(1))
    return best
