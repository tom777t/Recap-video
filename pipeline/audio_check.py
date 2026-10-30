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


# FILM-AUDIO thresholds. RE-CALIBRATED on real material - the first set came
# from a synthetic control and could not survive contact with the film.
#
# The synthetic control (pink noise as the "stem", a 330 Hz tone as the
# "music") gave present 0.270 / absent 0.006, a 45x separation, and bars of
# 0.040 / 0.025. A tone is trivially separable from noise; real film audio sits
# under real narration and real music, all of it broadband. On the real render
# those bars produced 0.048 on / 0.029 off - a 1.65x separation with six false
# findings.
#
# Three real defects were behind the compression, all now fixed:
#
#  1. ALIGNMENT. The check sampled the finished file at the NARRATION start
#     but the stem at the CLIP start - an offset of the lead-in (0.5s, or 1.1s
#     on a reveal) that the +-50ms lag search cannot bridge. Corrected, the
#     same windows move: line 8 0.033 -> 0.215, line 9 0.043 -> 0.254,
#     line 11 0.085 -> 0.794. And line 7, reported as a leak at 0.033, falls
#     to 0.020 - it was never a leak.
#  2. WINDOW OVERRUN. A fixed 4-6s window runs past a short clip into the next
#     one, where it is compared against the wrong source span. Line 96's
#     narration is 1.70s. The window is now bounded to the clip.
#  3. SILENT STEM. Since separation covers only action/tense runs, the stem
#     file is SILENT outside them (-75 dB). A window where the stem has no
#     signal cannot tell "not mixed" from "nothing to mix", so it is not
#     informative and must be excluded rather than reported.
#
# What is left, measured over 100 lines of the real render: the medians
# separate cleanly but the per-line tails overlap -
#     informative on : min 0.022  median 0.106
#     informative off: p90 0.033  max 0.050
# so a PER-LINE pass/fail bar is not supportable on this measurement and
# claiming one produced six false findings. The verdict is therefore on the
# DISTRIBUTIONS, which do separate: 3.2x measured at this floor.
STEM_INFORMATIVE_DB = -45.0     # below this the stem has nothing to detect
STEM_MIN_WINDOW_SEC = 2.0       # shorter than this, a clip cannot be judged
STEM_MAX_WINDOW_SEC = 6.0
STEM_SEPARATION_MIN = 2.0       # median(on) / p90(off); measured 3.2x
STEM_MIN_SAMPLES = 6            # per group, or the verdict is a coin toss


def check_film_audio_placement(final: Path, stem: Path, rows: list) -> tuple:
    """Is the film's track where the rule says, and nowhere else?

    `rows` = [{line_id, final_at, source_at, window, want}] where `final_at`
    is the CLIP's start on the finished timeline and `source_at` the same
    clip's source start - the two must describe the same instant, which is
    where the first version of this went wrong.

    Returns (ok, findings, measured_rows, info). Judged on the DISTRIBUTIONS,
    not per line: median(informative on) must exceed p90(informative off) by
    STEM_SEPARATION_MIN. Per-line numbers are reported for diagnosis and
    deliberately produce no findings of their own - the per-line tails of this
    measurement overlap, and pretending otherwise produced six false findings
    on the shipped render.
    """
    if not Path(stem).exists():
        return True, [], [], {"skipped": "no stem file"}
    got = []
    for r in rows:
        w = float(r.get("window") or STEM_MAX_WINDOW_SEC)
        w = min(STEM_MAX_WINDOW_SEC, w)
        rec = dict(r, window=round(w, 2))
        if w < STEM_MIN_WINDOW_SEC:
            rec.update(corr=None, stem_db=None,
                       informative=False, why="clip too short to correlate")
            got.append(rec)
            continue
        sdb = rms_db(Path(stem), float(r["source_at"]), w)
        a = _pcm(Path(final), float(r["final_at"]), w)
        b = _pcm(Path(stem), float(r["source_at"]), w)
        c = correlation(a, b)
        inf = sdb >= STEM_INFORMATIVE_DB
        rec.update(corr=round(c, 4), stem_db=round(sdb, 1), informative=inf,
                   why=("" if inf else
                        f"the stem has no signal here ({sdb:.0f} dB), so "
                        f"nothing could be detected either way"))
        got.append(rec)

    on = sorted(r["corr"] for r in got if r.get("want") and r["informative"])
    off = sorted(r["corr"] for r in got
                 if not r.get("want") and r["informative"])
    info = {"informative_on": len(on), "informative_off": len(off),
            "uninformative": sum(1 for r in got if not r["informative"]),
            "informative_floor_db": STEM_INFORMATIVE_DB}
    if len(on) < STEM_MIN_SAMPLES or len(off) < STEM_MIN_SAMPLES:
        info["skipped"] = (
            f"only {len(on)} informative action/tense window(s) and "
            f"{len(off)} elsewhere; {STEM_MIN_SAMPLES} of each are needed "
            f"before the distributions mean anything")
        return True, [], got, info

    med_on = on[len(on) // 2]
    p90_off = off[int(len(off) * 0.9)] if len(off) > 1 else off[0]
    sep = med_on / max(p90_off, 1e-6)
    info.update(median_on=round(med_on, 4), p90_off=round(p90_off, 4),
                separation=round(sep, 2),
                separation_required=STEM_SEPARATION_MIN)
    find = []
    if sep < STEM_SEPARATION_MIN:
        find.append(
            f"the film's track is not placed by the rule: action/tense "
            f"windows have a median correlation of {med_on:.3f} against a p90 "
            f"of {p90_off:.3f} elsewhere - a separation of {sep:.2f}x, under "
            f"the {STEM_SEPARATION_MIN:.1f}x bar. Either the stem is not "
            f"reaching the action/tense clips, or it is leaking into the rest.")
    return (not find), find, got, info


# A <film_speaks> unit must measure clearly above the music around it.
#
# CALIBRATED AGAINST THE DEFECT, which is the only honest way to site this bar.
# Measured on the shipped final.mp4, the render that was described as "I heard
# only music":
#     line 110 at 3:01.2  film -17.5 dB vs music -20.8  margin +3.2 dB
#     line 111 at 12:44.5 film -18.1 dB vs music -19.6  margin +1.5 dB
# So +3.2 dB IS the inaudible case. A first version of this bar was 3.0 dB and
# line 110 would have passed it - a check calibrated to accept the very render
# it was written to catch. Dialogue needs far more headroom over music than the
# ~3 dB "just noticeably louder" figure for a tone.
#
# With the music ducked by FILM_SPEAKS_MUSIC_DB (-20 dB) the achievable margin
# is around +20 dB, so 10 dB is comfortably reachable and still well clear of
# the measured failure.
FILM_SPEAKS_MARGIN_MIN_DB = 10.0
# A cue must rise out of the bed audibly. 3 dB is the usual "just noticeably
# louder" figure; the configured intent is +10 to +14 dB, and a control mix
# measured +15.1 (tense) and +19.3 (action), so this bar fails only a cue that
# has genuinely not been lifted.
CUE_LIFT_MIN_DB = 3.0


def check_film_speaks_audible(final: Path, units: list) -> tuple:
    """(ok, findings, rows) - is the film actually heard in each unit?"""
    rows = film_speaks_margin(Path(final), units)
    find = []
    for r in rows:
        if r["margin_db"] < FILM_SPEAKS_MARGIN_MIN_DB:
            find.append(
                f"film_speaks line {r.get('line_id')} at "
                f"{r['final_at']:.1f}s measures {r['inside_db']:.1f} dB "
                f"against {max(r['before_db'], r['after_db']):.1f} dB of "
                f"music either side - a margin of {r['margin_db']:+.1f} dB, "
                f"under the {FILM_SPEAKS_MARGIN_MIN_DB:.0f} dB bar. The unit "
                f"hands the moment to the film, so the film has to be the "
                f"loudest thing in it.")
    return (not find), find, rows


def check_cues_audible(final: Path, cues: list) -> tuple:
    """(ok, findings, rows) - does every cue rise out of the bed?"""
    rows = cue_vs_bed(Path(final), cues)
    find = []
    for r in rows:
        if r["lift_db"] < CUE_LIFT_MIN_DB:
            find.append(
                f"{r.get('mood')} cue at {r['at']:.1f}s measures "
                f"{r['inside_db']:.1f} dB against a {r['bed_db']:.1f} dB "
                f"bed - a lift of {r['lift_db']:+.1f} dB, under the "
                f"{CUE_LIFT_MIN_DB:.0f} dB bar. A cue at bed level is not a "
                f"cue, it is more bed.")
    return (not find), find, rows


def integrated(path: Path) -> float | None:
    """Integrated loudness of a whole file, in LUFS."""
    cmd = [config.ffmpeg(), "-hide_banner", "-nostats", "-i", str(path),
           "-vn", "-af", "ebur128=framelog=verbose", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    best = None
    for m in re.finditer(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", r.stderr or ""):
        best = float(m.group(1))
    return best
