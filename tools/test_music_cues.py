"""Mood-cue audibility regression tests.

THE DEFECT
----------
The mood cues could not be heard. The numbers said why:

  * a cue was ducked under narration to -22 dB - the SAME depth as the bed. The
    thing meant to mark a mood change sat at the level of the furniture it was
    supposed to rise above.
  * the bed dipped only 6 dB while a cue played, so the cue competed with a bed
    that had barely moved.

And underneath both: MUSIC_CUE_DUCK_DB and MUSIC_CUE_DUCK_ACTION_DB were DEAD
CONFIG. Nothing in the codebase read them. render.py mixes the finished
bed+cues track under the voice with ONE duck (MUSIC_DUCK_DB) applied to the
whole thing, so a cue was ducked identically to the bed no matter what those
constants said.

THE FIX
-------
The mix architecture is fine; the relationship has to be baked into the track
before the global duck. Each cue gets a relative gain of
(cue duck - bed duck) dB in build_music_track, so the single global duck lands
the bed at -22 dB and a cue at -12 dB (-8 for action). It falls out correctly
in holds too: the silence swell raises the whole track, putting a cue near full
level, which is what a hold is for.

Cases
-----
  LEVELS-ORDERED      the constants express the intended hierarchy: a cue above
                      the bed, action above that, and the bed dipping deeper
                      than it used to
  CUE-DUCK-NOT-DEAD   music.py actually READS the cue duck constants. This is
                      the regression for the real bug - the values existed and
                      were ignored.
  RELATIVE-GAIN-MEASURED  build a real track with ffmpeg and MEASURE that a
                      tense cue sits ~10 dB above the bed and an action cue
                      ~14 dB. The only test that proves audibility rather than
                      intent.
  BED-DIPS-UNDER-CUE  the bed's volume expression really dips while a cue
                      plays, measured on the built track
  HOLD-NEAR-FULL      the arithmetic puts a cue near full level inside a hold

Run:  python tools/test_music_cues.py
"""
from __future__ import annotations

import io
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402


def _mk_tone(ff: str, p: Path, freq: int, dur: float) -> None:
    subprocess.run(
        [ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency={freq}:duration={dur}",
         "-c:a", "libmp3lame", str(p)], check=True,
        capture_output=True)


def _mean_db(ff: str, path: Path, a: float, b: float) -> float:
    r = subprocess.run(
        [ff, "-hide_banner", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}",
         "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    for line in (r.stderr or "").splitlines():
        if "mean_volume" in line:
            try:
                return float(line.split("mean_volume:")[1].strip().split()[0])
            except (IndexError, ValueError):
                pass
    return float("nan")


def _build_track(tmp: Path):
    """A real bed+cues track: 40s bed, a tense cue and an action cue."""
    from pipeline import music as M
    ff = config.ffmpeg()
    bed = tmp / "bed.mp3"
    _mk_tone(ff, bed, 110, 40)
    c_tense = tmp / "tense1.mp3"
    _mk_tone(ff, c_tense, 440, 10)
    c_act = tmp / "action1.mp3"
    _mk_tone(ff, c_act, 660, 10)
    plan = [
        {"mood": "tense", "start": 5.0, "end": 13.0, "file": c_tense,
         "why": "run"},
        {"mood": "action", "start": 22.0, "end": 30.0, "file": c_act,
         "why": "run"},
    ]
    out = tmp / "track.wav"
    ok = M.build_music_track(ff, tmp, out, 40.0, bed, plan, [], [])
    return (out if ok and out.exists() else None), ff


def test_levels_ordered() -> tuple[bool, str]:
    bed = float(config.MUSIC_DUCK_DB)
    cue = float(config.MUSIC_CUE_DUCK_DB)
    act = float(config.MUSIC_CUE_DUCK_ACTION_DB)
    dip = float(config.MUSIC_CUE_BED_DIP_DB)
    bad = []
    if cue <= bed:
        bad.append(f"a cue ({cue:+.0f} dB) is not above the bed ({bed:+.0f}) - "
                   f"this is the original defect")
    if act <= cue:
        bad.append(f"an action cue ({act:+.0f}) is not above a normal cue "
                   f"({cue:+.0f})")
    if dip > -10.0:
        bad.append(f"the bed only dips {dip:+.0f} dB under a cue; it has to "
                   f"get out of the way")
    if cue - bed < 8.0:
        bad.append(f"only {cue - bed:.0f} dB between cue and bed - not enough "
                   f"to read as an event")
    ok = not bad
    return ok, (f"bed {bed:+.0f}, cue {cue:+.0f}, action {act:+.0f}, bed dips "
                f"{dip:+.0f} under a cue" if ok else "; ".join(bad))


def test_cue_duck_not_dead() -> tuple[bool, str]:
    """The constants must actually be READ. They were not, which was the bug."""
    src = io.open(os.path.join(ROOT, "pipeline", "music.py"),
                  encoding="utf-8").read()
    missing = [n for n in ("MUSIC_CUE_DUCK_DB", "MUSIC_CUE_DUCK_ACTION_DB")
               if n not in src]
    if missing:
        return False, (f"pipeline/music.py does not read {missing} - they are "
                       f"dead config again, and a cue will be ducked to the "
                       f"same depth as the bed")
    if "volume=" not in src:
        return False, "no per-cue volume is applied in music.py"
    # and the render side must still apply the single global duck it assumes
    rsrc = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                   encoding="utf-8").read()
    if "MUSIC_DUCK_DB" not in rsrc:
        return False, ("render.py no longer applies MUSIC_DUCK_DB, so the "
                       "relative cue gain baked into the track is measured "
                       "against nothing")
    return True, ("music.py reads both cue-duck constants and applies a "
                  "per-cue gain; render.py still applies the global bed duck "
                  "the gain is relative to")


def test_relative_gain_measured() -> tuple[bool, str]:
    tmp = Path(tempfile.mkdtemp(prefix="cuetest_"))
    try:
        out, ff = _build_track(tmp)
        if out is None:
            return False, "the bed+cues track failed to build"
        bed_db = _mean_db(ff, out, 0.5, 4.0)
        tense_db = _mean_db(ff, out, 7.0, 12.0)
        act_db = _mean_db(ff, out, 24.0, 29.0)
        if any(math.isnan(x) for x in (bed_db, tense_db, act_db)):
            return False, "could not measure the track levels"
        want_t = float(config.MUSIC_CUE_DUCK_DB) - float(config.MUSIC_DUCK_DB)
        want_a = (float(config.MUSIC_CUE_DUCK_ACTION_DB)
                  - float(config.MUSIC_DUCK_DB))
        got_t = tense_db - bed_db
        got_a = act_db - bed_db
        # 4 dB tolerance: these are mean levels of real encoded audio through a
        # limiter, not filter-graph arithmetic
        if abs(got_t - want_t) > 4.0:
            return False, (f"a tense cue measured {got_t:+.1f} dB above the "
                           f"bed, expected about {want_t:+.1f}")
        if got_a <= got_t:
            return False, (f"an action cue ({got_a:+.1f} dB) is not above a "
                           f"tense cue ({got_t:+.1f} dB)")
        return True, (f"measured on a real track: bed {bed_db:.1f} dB, tense "
                      f"cue {got_t:+.1f} dB above it, action cue "
                      f"{got_a:+.1f} dB above it")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_bed_dips_under_cue() -> tuple[bool, str]:
    """The bed must really get out of the way, not just be told to."""
    tmp = Path(tempfile.mkdtemp(prefix="cuedip_"))
    try:
        from pipeline import music as M
        ff = config.ffmpeg()
        bed = tmp / "bed.mp3"
        _mk_tone(ff, bed, 110, 40)
        cue = tmp / "tense1.mp3"
        # a near-silent "cue" so what we measure during it is the BED alone
        subprocess.run(
            [ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
             "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
             "-t", "10", "-c:a", "libmp3lame", str(cue)],
            check=True, capture_output=True)
        plan = [{"mood": "tense", "start": 15.0, "end": 25.0, "file": cue,
                 "why": "run"}]
        out = tmp / "t.wav"
        if not M.build_music_track(ff, tmp, out, 40.0, bed, plan, [], []):
            return False, "track build failed"
        before = _mean_db(ff, out, 2.0, 10.0)
        during = _mean_db(ff, out, 18.0, 23.0)
        if math.isnan(before) or math.isnan(during):
            return False, "could not measure the bed level"
        drop = before - during
        want = abs(float(config.MUSIC_CUE_BED_DIP_DB))
        if drop < want - 4.0:
            return False, (f"the bed only dropped {drop:.1f} dB while a cue "
                           f"played, expected about {want:.0f} dB")
        return True, (f"the bed drops {drop:.1f} dB while a cue plays "
                      f"(configured {want:.0f} dB)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_hold_near_full() -> tuple[bool, str]:
    """Inside a hold a cue should land near full level."""
    bed = float(config.MUSIC_DUCK_DB)
    cue = float(config.MUSIC_CUE_DUCK_DB)
    swell = 20.0 * math.log10(max(1e-6, float(config.SILENCE_MUSIC_VOLUME)))
    cue_in_hold = swell + (cue - bed)
    target = float(getattr(config, "MUSIC_CUE_HOLD_DB", -2.0))
    if cue_in_hold < target - 4.0:
        return False, (f"a cue lands at {cue_in_hold:+.1f} dB inside a hold, "
                       f"well under the {target:+.1f} dB intent - a hold is "
                       f"the one moment a cue can carry the beat alone")
    if cue_in_hold > 0.5:
        return False, (f"a cue lands at {cue_in_hold:+.1f} dB inside a hold, "
                       f"which risks clipping the mix")
    return True, (f"inside a hold the track swells to {swell:+.1f} dB, putting "
                  f"a cue at {cue_in_hold:+.1f} dB - near full, intent "
                  f"{target:+.1f} dB")


TESTS = {
    "LEVELS-ORDERED":         test_levels_ordered,
    "CUE-DUCK-NOT-DEAD":      test_cue_duck_not_dead,
    "RELATIVE-GAIN-MEASURED": test_relative_gain_measured,
    "BED-DIPS-UNDER-CUE":     test_bed_dips_under_cue,
    "HOLD-NEAR-FULL":         test_hold_near_full,
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
    print("test_music_cues: all pass" if not bad else
          f"test_music_cues: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
