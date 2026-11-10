# -*- coding: utf-8 -*-
"""test_music_ending.py - music/ending.* plays from its line to the end.

Synthetic tones (no film media): the bed is a 220 Hz tone, the ending an
880 Hz one, so the built track can be measured band by band.

  START-AFTER-FILM-SPEAKS  with no ending.json the ending starts on the line
                           after the LAST film-speaks unit; ending.json's
                           from_line overrides it; a line not on the timeline
                           places nothing (said, not guessed)
  HANDOVER                 in the built track: before the start the bed is
                           there and the ending is not; after it the ending is
                           there and the bed has faded out
  CUES-STOP                a cue that would start after the ending is dropped,
                           one running into it is cut at the start
  ENDING-ONLY              no bed at all: silence, then the ending

Run:  python tools/test_music_ending.py      (exit 0 = all pass; SKIP without
      ffmpeg / numpy)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _tone(ff, path, hz, secs):
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"sine=frequency={hz}:duration={secs}", "-ac", "2",
                    str(path)], check=True)


def _band(path, a, b, hz):
    import numpy as np
    with wave.open(str(path)) as w:
        sr, n = w.getframerate(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).reshape(-1, 2)[:, 0]
    seg = x[int(a * sr):int(b * sr)].astype(float)
    if not len(seg):
        return 0.0
    f = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    fr = np.fft.rfftfreq(len(seg), 1.0 / sr)
    return float(f[(fr > hz - 20) & (fr < hz + 20)].max() / len(seg))


def main() -> int:
    ff = shutil.which("ffmpeg")
    try:
        import numpy  # noqa: F401
    except ImportError:
        ff = None
    if not ff:
        print("test_music_ending: SKIP (ffmpeg / numpy missing)")
        return 0
    from pipeline import music as M
    cases = []
    with tempfile.TemporaryDirectory() as td:
        pdir = Path(td)
        (pdir / "music").mkdir()
        draft = {"lines": [{"id": 1}, {"id": 2, "film_speaks_seconds": 3.0},
                           {"id": 3}, {"id": 9, "film_speaks_seconds": 4.0},
                           {"id": 4}, {"id": 5}]}
        tl = [{"id": 1, "start": 0.0, "end": 4.0},
              {"id": 2, "start": 4.0, "end": 7.0},
              {"id": 3, "start": 7.0, "end": 9.0},
              {"id": 9, "start": 9.0, "end": 13.0},
              {"id": 4, "start": 13.0, "end": 17.0},
              {"id": 5, "start": 17.0, "end": 24.0}]
        s1 = M.ending_start(pdir, draft, tl)
        (pdir / "music" / "ending.json").write_text('{"from_line": 5}')
        s2 = M.ending_start(pdir, draft, tl)
        (pdir / "music" / "ending.json").write_text('{"from_line": 77}')
        s3 = M.ending_start(pdir, draft, tl)
        (pdir / "music" / "ending.json").unlink()
        cases.append(("START-AFTER-FILM-SPEAKS",
                      s1 and s1[:2] == (13.0, 4) and s2 and s2[:2] == (17.0, 5)
                      and s3 is None,
                      f"after the last unit -> {s1 and s1[:2]}, from_line 5 "
                      f"-> {s2 and s2[:2]}, unknown line -> {s3}"))
        bed, end = pdir / "music" / "bed.wav", pdir / "music" / "ending.wav"
        _tone(ff, bed, 220, 30)
        _tone(ff, end, 880, 30)
        work = pdir / "_work"
        work.mkdir()
        out, pre, note = M.resolve_music(ff, pdir, work, draft, tl, 24.0)
        b_before = _band(out, 5, 10, 220)
        e_before = _band(out, 5, 10, 880)
        b_after = _band(out, 16, 21, 220)
        e_after = _band(out, 16, 21, 880)
        ok = (pre and "ending" in note and b_before > 10 * max(e_before, 1e-9)
              and e_after > 10 * max(b_after, 1e-9))
        cases.append(("HANDOVER", ok,
                      f"5-10 s bed {b_before:.4f} / ending {e_before:.5f}; "
                      f"16-21 s bed {b_after:.5f} / ending {e_after:.4f} "
                      f"({note})"))
        # cues: one before (kept), one running into the start (cut), one after
        cues = pdir / "music" / "cues"
        cues.mkdir()
        _tone(ff, cues / "tense1.wav", 440, 30)
        draft2 = {"lines": [dict(l, delivery="tense") for l in draft["lines"]]}
        plan_full = M.plan_cues(draft2, tl, M.cue_files(pdir))
        out2, _pre2, _n2 = M.resolve_music(ff, pdir, work, draft2, tl, 24.0)
        mp = json.loads((pdir / "music_plan.json").read_text())
        ends = [c["at"] + c["dur"] for c in mp["cues"]]
        ok_c = (plan_full and any(p["end"] > 13.0 for p in plan_full)
                and all(e <= 13.0 + 1e-6 for e in ends)
                and mp.get("ending", {}).get("at") == 13.0)
        cases.append(("CUES-STOP", ok_c,
                      f"cue plan ends {[round(p['end'], 1) for p in plan_full]}"
                      f" -> built {[round(e, 1) for e in ends]}, ending at "
                      f"{mp.get('ending', {}).get('at')}"))
        shutil.rmtree(cues)
        bed.unlink()
        out3, pre3, note3 = M.resolve_music(ff, pdir, work, draft, tl, 24.0)
        ok3 = (pre3 and note3 == "ending only"
               and _band(out3, 3, 8, 880) < 1e-4
               and _band(out3, 16, 21, 880) > 1e-3)
        cases.append(("ENDING-ONLY", ok3, f"silence, then the ending ({note3})"))
    bad = 0
    for n, ok, m in cases:
        print(f"{'PASS' if ok else 'FAIL'}  {n:<24} {m}")
        bad += not ok
    print("-" * 60)
    print(f"test_music_ending: {bad} FAILURE(S)" if bad
          else "test_music_ending: all pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
