# -*- coding: utf-8 -*-
"""test_bed_silence.py - the looped bed is music, never its silence.

Lost in the Stars' bed.mp3 ran 16:00 but held music only for 5:35; the rest
was digital silence. Looped under a 20-minute video it left the middle ten
minutes with no bed. music.playable_bed cuts every silence longer than
MUSIC_BED_MAX_SILENCE_SEC before the loop.

  CUTS-SILENCE     6s music + 20s silence + 4s music + 10s silence -> ~11s
  KEEPS-PAUSES     a 1s pause inside the music is the music's: file untouched
  ALL-SILENT       a silent bed gives no bed (None), not a silent loop
  LOOP-HAS-MUSIC   built 40s track: no 3s silence with the cut bed; the raw
                   bed (control) leaves one
  RESOLVE-USES-IT  resolve_music takes the bed through playable_bed

    python tools/test_bed_silence.py
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import music as M  # noqa: E402


def _mk(ff, out: Path, parts: list) -> None:
    """parts: [(kind, seconds)] kind 'tone' or 'sil' -> one wav."""
    ins, n = [], 0
    for kind, sec in parts:
        src = (f"sine=frequency=330:sample_rate=48000:duration={sec}"
               if kind == "tone" else
               f"anullsrc=r=48000:cl=mono:d={sec}")
        ins += ["-f", "lavfi", "-i", src]
        n += 1
    graph = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    subprocess.run([ff, "-y", "-v", "error", *ins, "-filter_complex", graph,
                    "-map", "[a]", "-ac", "2", str(out)], check=True)


def _dur(p: Path) -> float:
    r = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def _long_silence(ff, p: Path) -> bool:
    r = subprocess.run([ff, "-hide_banner", "-nostats", "-i", str(p), "-af",
                        "silencedetect=n=-60dB:d=3", "-f", "null", "-"],
                       capture_output=True, text=True)
    return "silence_start" in (r.stderr or "")


def main() -> int:
    ff = config.ffmpeg()
    tmp = Path(tempfile.mkdtemp(prefix="bedsil_"))
    pdir = tmp / "proj"
    (pdir / "music").mkdir(parents=True)
    res = []
    try:
        bed = pdir / "music" / "bed.wav"
        _mk(ff, bed, [("tone", 6), ("sil", 20), ("tone", 4), ("sil", 10)])
        pb = M.playable_bed(ff, pdir, bed)
        d = _dur(pb) if pb else 0
        res.append(("CUTS-SILENCE", pb is not None and pb != bed
                    and 10.5 <= d <= 11.6,
                    f"40s file -> {d:.1f}s of bed (music 10s + short tails)"))

        p2 = tmp / "paused.wav"
        _mk(ff, p2, [("tone", 5), ("sil", 1), ("tone", 5)])
        res.append(("KEEPS-PAUSES", M.playable_bed(ff, pdir, p2) == p2,
                    "a 1s pause is left alone"))

        p3 = tmp / "silent.wav"
        _mk(ff, p3, [("sil", 12)])
        res.append(("ALL-SILENT", M.playable_bed(ff, pdir, p3) is None,
                    "a silent bed is no bed"))

        out_cut = tmp / "track_cut.wav"
        out_raw = tmp / "track_raw.wav"
        ok_cut = M.build_music_track(ff, pdir, out_cut, 40.0, pb, [])
        ok_raw = M.build_music_track(ff, pdir, out_raw, 40.0, bed, [])
        cut_sil = _long_silence(ff, out_cut) if ok_cut else True
        raw_sil = _long_silence(ff, out_raw) if ok_raw else False
        res.append(("LOOP-HAS-MUSIC", ok_cut and not cut_sil and raw_sil,
                    f"cut bed loop: {'silence' if cut_sil else 'music'} "
                    f"throughout; raw bed (control): "
                    f"{'goes silent' if raw_sil else 'no silence?'}"))

        src = (ROOT / "pipeline" / "music.py").read_text(encoding="utf-8")
        res.append(("RESOLVE-USES-IT",
                    "bed = playable_bed(ff, pdir, bed_file(pdir))" in src,
                    "resolve_music loops the cut bed"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = 0
    for name, ok, msg in res:
        print(f'{"PASS" if ok else "FAIL"}  {name:<16} {msg}')
        bad += not ok
    print("-" * 60)
    print("test_bed_silence: all pass" if not bad else
          f"test_bed_silence: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
