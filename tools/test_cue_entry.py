# -*- coding: utf-8 -*-
"""test_cue_entry.py - a cue is heard: it plays its track's BEST stretch,
and enters in a hold the story already has (owner, 18 Nov: "phải ở khúc mà
nhạc hay ... lúc nào cũng bắt đầu từ khúc đầu thì hên xui").

Measured on Furious 7's cue files: the first 4 s sit 2.3-5.6 dB under the
track as a whole, and every cue played from 0 s, so a 13-24 s cue was mostly
the soft opening, under the narrator.

  BEST-STRETCH      soft 10 s, medium 20 s, FULL 15 s, soft 10 s: a 12 s
                    cue starts on the full section, not at 0 and not on the
                    medium one that comes first
  ON-A-NOTE         ...and exactly where that section begins (within 0.1 s),
                    so it starts on a note, not inside one
  SHORT-TRACK       a track no longer than the cue starts at 0
  NEED-RESPECTED    the start never leaves less than the cue's length
  CHOSEN-WINS       music/cue_starts.json (a start chosen by ear) wins
  REAL-BUILD        a REAL bed+cue track: the cue's window is as loud as the
                    file's body, not its opening (it was ~17 dB quieter
                    playing from 0)
  ENTERS-IN-HOLD    a cue run with a hold right before it starts in the
                    hold; one with no hold near starts with its first line;
                    a hold far away is not borrowed
  SWITCH-OFF        MUSIC_CUE_FROM_ARRIVAL False -> 0 s (the old behaviour)

Run:  python tools/test_cue_entry.py      (exit 0 = all pass)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import music as M  # noqa: E402


def _ff(*a):
    subprocess.run([config.ffmpeg(), "-v", "error", "-y", *a], check=True)


def _opening_file(p: Path, soft: float = 8.0, body: float = 30.0):
    """`soft` seconds of quiet pad (-20 dB), then a loud body."""
    _sections(p, [(soft, 0.1), (body, 1.0)])


def _pdir(tmp: Path) -> Path:
    pd = tmp / "proj"
    (pd / "music").mkdir(parents=True)
    return pd


def _sections(p: Path, parts: list):
    """Consecutive (seconds, amplitude) sections of one tone."""
    ins, lab = [], []
    for i, (d, amp) in enumerate(parts):
        ins += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={d}"]
        lab.append(f"[{i}:a]volume={amp}[s{i}]")
    g = ";".join(lab) + ";" + "".join(f"[s{i}]" for i in range(len(parts))) \
        + f"concat=n={len(parts)}:v=0:a=1"
    _ff(*ins, "-filter_complex", g, "-ac", "2", "-ar", "44100", str(p))


def t_best_stretch():
    tmp = Path(tempfile.mkdtemp(prefix="ce_"))
    try:
        f = tmp / "tense1.wav"
        _sections(f, [(10, 0.05), (20, 0.3), (15, 1.0), (10, 0.05)])
        t = M.cue_entry(config.ffmpeg(), _pdir(tmp), f, need=12.0)
        ok = 29.9 <= t <= 30.05
        return ok, (f"a 12 s cue starts at {t:.2f}s - the full section "
                    f"(30.0 s), not 0 s or the medium one at 10 s" if ok
                    else f"starts at {t}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_on_a_note():
    tmp = Path(tempfile.mkdtemp(prefix="ce_"))
    try:
        f = tmp / "action1.wav"
        _sections(f, [(7.3, 0.1), (25, 1.0)])
        t = M.cue_entry(config.ffmpeg(), _pdir(tmp), f, need=10.0)
        ok = abs(t - 7.3) <= 0.1
        return ok, (f"starts at {t:.2f}s on the 7.30 s entrance" if ok
                    else f"starts at {t}, the entrance is 7.30 s")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_short_track():
    tmp = Path(tempfile.mkdtemp(prefix="ce_"))
    try:
        f = tmp / "reveal1.wav"
        _sections(f, [(3, 0.1), (9, 1.0)])
        t = M.cue_entry(config.ffmpeg(), _pdir(tmp), f, need=12.0)
        return t == 0.0, f"a 12 s track for a 12 s cue starts at {t}s"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_need_respected():
    tmp = Path(tempfile.mkdtemp(prefix="ce_"))
    try:
        f = tmp / "sad1.wav"
        _sections(f, [(20, 0.1), (6, 1.0)])         # loud only at the end
        t = M.cue_entry(config.ffmpeg(), _pdir(tmp), f, need=15.0)
        ok = t + 15.0 <= 26.0 + 1e-6
        return ok, (f"a 15 s cue in a 26 s file starts at {t}s and ends "
                    f"inside it" if ok else f"starts at {t}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def t_chosen_wins():
    tmp = Path(tempfile.mkdtemp(prefix="ce_"))
    try:
        pd = _pdir(tmp)
        f = tmp / "mystery1.wav"
        _sections(f, [(10, 0.1), (30, 1.0)])
        (pd / "music" / "cue_starts.json").write_text(
            json.dumps({"mystery1.wav": 21.5}), encoding="utf-8")
        t = M.cue_entry(config.ffmpeg(), pd, f, need=10.0)
        return t == 21.5, f"chosen 21.5 s -> {t}s"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _mean_db(path: Path, a: float, b: float) -> float:
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-ss", f"{a:.3f}",
                        "-t", f"{b - a:.3f}", "-i", str(path), "-af",
                        "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    for line in (r.stderr or "").splitlines():
        if "mean_volume" in line:
            return float(line.split("mean_volume:")[1].split()[0])
    return float("nan")


def t_real_build():
    tmp = Path(tempfile.mkdtemp(prefix="ce_"))
    try:
        pd = _pdir(tmp)
        bed = tmp / "bed.wav"
        _ff("-f", "lavfi", "-i", "sine=frequency=110:duration=40", str(bed))
        cue = tmp / "tense1.wav"
        _opening_file(cue)
        plan = [{"mood": "tense", "start": 10.0, "end": 20.0, "file": cue,
                 "why": "run"}]
        levels = {}
        for flag in (False, True):
            saved = config.MUSIC_CUE_FROM_ARRIVAL
            config.MUSIC_CUE_FROM_ARRIVAL = flag
            try:
                out = tmp / f"track_{flag}.wav"
                ok = M.build_music_track(config.ffmpeg(), pd, out, 40.0, bed,
                                         [dict(p) for p in plan], [], [])
            finally:
                config.MUSIC_CUE_FROM_ARRIVAL = saved
            if not ok:
                return False, "build failed"
            # the cue's first 6 s, after its fade-in
            levels[flag] = _mean_db(out, 12.0, 16.0)
        lift = levels[True] - levels[False]
        ok = lift > 8.0
        return ok, (f"cue window {levels[False]:.1f} dB from 0 s -> "
                    f"{levels[True]:.1f} dB from the arrival ({lift:+.1f} dB)"
                    if ok else f"{levels}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _plan(holds):
    draft = {"lines": [{"id": i, "delivery": "tense" if 3 <= i <= 6
                        else "normal"} for i in range(1, 10)]}
    tl = [{"id": i, "start": (i - 1) * 6.0, "end": (i - 1) * 6.0 + 5.5}
          for i in range(1, 10)]
    cues = {"tense": [Path("tense1.mp3")]}
    return M.plan_cues(draft, tl, cues, [], holds)


def t_enters_in_hold():
    # the tense run is L3-L6: 12.0 s .. 35.5 s
    near = _plan([(9.0, 11.6)])          # a hold just before L3
    inside = _plan([(17.6, 20.0)])       # a hold after L3, inside reach
    none = _plan([])
    far = _plan([(1.0, 4.0)])            # 8 s before the run - not adjacent
    got = [p[0]["start"] if p else None for p in (near, inside, none, far)]
    ok = got == [9.0, 17.6, 12.0, 12.0] and "enters in the hold" in \
        near[0]["why"]
    return ok, (f"hold before -> {got[0]}s, hold early in the run -> "
                f"{got[1]}s, no hold -> {got[2]}s, far hold ignored -> "
                f"{got[3]}s" if ok else f"{got}")


def t_switch_off():
    tmp = Path(tempfile.mkdtemp(prefix="ce_"))
    saved = config.MUSIC_CUE_FROM_ARRIVAL
    try:
        f = tmp / "tense1.wav"
        _opening_file(f)
        config.MUSIC_CUE_FROM_ARRIVAL = False
        t = M.cue_entry(config.ffmpeg(), _pdir(tmp), f)
        return t == 0.0, f"switched off -> {t}s"
    finally:
        config.MUSIC_CUE_FROM_ARRIVAL = saved
        shutil.rmtree(tmp, ignore_errors=True)


TESTS = [("BEST-STRETCH", t_best_stretch), ("ON-A-NOTE", t_on_a_note),
         ("SHORT-TRACK", t_short_track),
         ("NEED-RESPECTED", t_need_respected),
         ("CHOSEN-WINS", t_chosen_wins), ("REAL-BUILD", t_real_build),
         ("ENTERS-IN-HOLD", t_enters_in_hold), ("SWITCH-OFF", t_switch_off)]

if __name__ == "__main__":
    fails = 0
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:15s} {msg}")
    print("-" * 60)
    print("test_cue_entry: all pass" if not fails
          else f"test_cue_entry: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
