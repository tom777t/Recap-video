# -*- coding: utf-8 -*-
"""test_long_cmd.py - an ffmpeg command too long for the OS still runs.

Lost in the Stars' final mix died after the whole video was encoded:
"[WinError 206] The filename or extension is too long" - its filter graph
(a 20-min bed, 11 cues, 26 reveal dips) was past Windows' 32,767-character
command line. ffcmd.short_cmd moves a long -filter_complex into a file.

  RUNS-FROM-FILE   a graph of ~14,000 characters, through short_cmd, runs
                   under the real ffmpeg and gives the same audio length
  SHORT-UNTOUCHED  a short command is passed through as it is
  SYNTAX-BY-VER    ffmpeg 7+ gets -/filter_complex, older -filter_complex_script
  ALL-ROUTED       render, assemble, music and intro all go through fit()

    python tools/test_long_cmd.py
"""
from __future__ import annotations

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
from pipeline import ffcmd as R  # noqa: E402


def main() -> int:
    ff = config.ffmpeg()
    tmp = Path(tempfile.mkdtemp(prefix="longcmd_"))
    res = []
    try:
        out = tmp / "o.wav"
        graph = "[0:a]" + ",".join(["volume=1.0"] * 1400) + "[a]"
        cmd = [ff, "-v", "error", "-y", "-f", "lavfi", "-i",
               "sine=frequency=300:duration=2", "-filter_complex", graph,
               "-map", "[a]", str(out)]
        long_ = sum(len(c) + 1 for c in cmd)
        sc = R.short_cmd(cmd, tmp / "g", R.ff_major(ff))
        r = subprocess.run(sc, capture_output=True, text=True)
        dur = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries",
                              "format=duration", "-of", "csv=p=0", str(out)],
                             capture_output=True, text=True).stdout.strip()
        res.append(("RUNS-FROM-FILE", long_ > R.CMD_MAX and r.returncode == 0
                    and abs(float(dur or 0) - 2.0) < 0.05
                    and sum(len(c) + 1 for c in sc) < 1000,
                    f"{long_} chars -> {sum(len(c) + 1 for c in sc)}; ffmpeg "
                    f"rc {r.returncode}, {dur}s {r.stderr[-200:]}"))
        short = [ff, "-filter_complex", "[0:a]volume=1[a]"]
        res.append(("SHORT-UNTOUCHED", R.short_cmd(short, tmp, 7) == short,
                    "unchanged"))
        a7 = R.short_cmd(cmd, tmp / "g7", 7)
        a6 = R.short_cmd(cmd, tmp / "g6", 6)
        res.append(("SYNTAX-BY-VER", "-/filter_complex" in a7
                    and "-filter_complex_script" in a6,
                    "7+: -/filter_complex; 6: -filter_complex_script"))
        # every module that builds a growing graph routes through fit()
        miss = []
        for mod in ("render", "assemble", "music", "intro"):
            src = (ROOT / "pipeline" / f"{mod}.py").read_text(encoding="utf-8")
            if "ffcmd" not in src:
                miss.append(mod)
        res.append(("ALL-ROUTED", not miss, f"missing: {miss}" if miss
                    else "render, assemble, music, intro use ffcmd.fit"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = 0
    for name, ok, msg in res:
        print(f'{"PASS" if ok else "FAIL"}  {name:<16} {msg}')
        bad += not ok
    print("-" * 60)
    print("test_long_cmd: all pass" if not bad else
          f"test_long_cmd: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
