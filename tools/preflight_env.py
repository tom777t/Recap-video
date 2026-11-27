# -*- coding: utf-8 -*-
"""preflight_env.py - check the machine before a film run starts, so a
missing tool stops the run in the first minute and not three hours in.

run.ps1 calls it first. Exit 1 = a FAIL that would break the run later;
exit 0 = OK or warnings only.

  python    3.10 or newer
  ffmpeg    found, and 5.0 or newer: on 4.4.2 the stream-copy join loses
            frames ("the mux changed the frame count: 505 in, 492 out" -
            measured 27 Nov on the desktop VM's ffmpeg; 6.1 and the owner's
            build join the same clips cleanly)
  packages  rich, numpy (always); scenedetect + opencv (the cut scan);
            faster-whisper (transcription, before transcript.json exists);
            anthropic (when ANTHROPIC_API_KEY is set)
  API key   ANTHROPIC_API_KEY set - without it the LLM stages stop for a
            subagent at every step. The key is never printed.
  disk      free space on the projects drive (a 2 h film needs ~15 GB:
            stems, clips, intermediates)

    python tools/preflight_env.py [--project P]
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FFMPEG_MIN = 5
DISK_WARN_GB = 20.0


def ff_version(exe: str) -> tuple:
    """(major, full version text) of an ffmpeg/ffprobe binary; (0, why)."""
    try:
        r = subprocess.run([exe, "-version"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"
    first = ((r.stdout or "").splitlines() or ["no version line"])[0]
    return parse_version(first), first


def parse_version(line: str) -> int:
    """Major version from ffmpeg's first -version line; 99 for a git build
    (recent by construction), 0 when it cannot be read."""
    m = re.search(r"version n?(\d+)\.(\d+)", line or "")
    if m:
        return int(m.group(1))
    if re.search(r"version (N-|git-|\d{4}-\d{2}-\d{2})", line or ""):
        return 99
    return 0


def has(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def checks(project: str | None) -> list:
    """[(level, name, message)] with level PASS / WARN / FAIL."""
    import config
    out = []
    v = sys.version_info
    out.append(("PASS" if v >= (3, 10) else "FAIL", "python",
                f"{v.major}.{v.minor}.{v.micro}"
                + ("" if v >= (3, 10) else " - needs 3.10 or newer")))
    for tool in ("ffmpeg", "ffprobe"):
        try:
            exe = getattr(config, tool)()
        except Exception as e:
            out.append(("FAIL", tool, f"not found ({e})"))
            continue
        major, line = ff_version(exe)
        if major == 0:
            out.append(("WARN", tool, f"version unknown ({line[:80]})"))
        elif major < FFMPEG_MIN:
            out.append(("FAIL", tool,
                        f"{line[:60]} - needs {FFMPEG_MIN}.0 or newer: on "
                        f"4.4 the stream-copy join loses frames. Install a "
                        f"current build (gyan.dev / BtbN) and put it first "
                        f"on PATH"))
        else:
            out.append(("PASS", tool, line[:70]))
    for mod, why, level in (("rich", "console output", "FAIL"),
                            ("numpy", "render checks", "FAIL")):
        out.append(("PASS" if has(mod) else level, mod,
                    "installed" if has(mod) else
                    f"missing - pip install {mod} ({why})"))
    pdir = config.project_dir(project) if project else None
    cut_needed = not (pdir and (pdir / "_cuts.json").exists())
    for mod, pipname in (("scenedetect", "scenedetect"),
                         ("cv2", "opencv-python")):
        ok = has(mod)
        out.append(("PASS" if ok else ("WARN" if cut_needed else "PASS"),
                    pipname, "installed" if ok else
                    (f"missing - pip install {pipname} (the cut scan is "
                     f"skipped without it)" if cut_needed else
                     "missing, not needed: _cuts.json exists")))
    tr_needed = not (pdir and (pdir / "transcript.json").exists())
    ok = has("faster_whisper")
    out.append(("PASS" if ok or not tr_needed else "FAIL", "faster-whisper",
                "installed" if ok else (
                    "missing - pip install faster-whisper (ingest needs it)"
                    if tr_needed else "missing, not needed: transcript.json "
                                      "exists")))
    key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    out.append(("PASS" if key else "WARN", "ANTHROPIC_API_KEY",
                "set" if key else
                "not set - every LLM stage will stop and ask for a subagent. "
                "Load it into this window first: $env:ANTHROPIC_API_KEY = "
                "[Environment]::GetEnvironmentVariable(\"ANTHROPIC_API_KEY\","
                "\"User\")"))
    if key:
        ok = has("anthropic")
        out.append(("PASS" if ok else "FAIL", "anthropic",
                    "installed" if ok else
                    "missing - pip install anthropic (the key is set)"))
    try:
        base = pdir if pdir and pdir.exists() else Path(config.project_dir(
            "_x")).parent
        base.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(str(base)).free / 1e9
        out.append(("PASS" if free >= DISK_WARN_GB else "WARN", "disk",
                    f"{free:.0f} GB free on the projects drive"
                    + ("" if free >= DISK_WARN_GB else
                       f" - a 2 h film needs ~15 GB; free some space")))
    except Exception as e:
        out.append(("WARN", "disk", f"could not measure ({e})"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    a = ap.parse_args()
    rows = checks(a.project)
    for lvl, name, msg in rows:
        print(f"  {lvl:<4}  {name:<18} {msg}")
    fails = [r for r in rows if r[0] == "FAIL"]
    if fails:
        print(f"preflight: {len(fails)} problem(s) would break this run - "
              f"fix them first")
        return 1
    warns = sum(r[0] == "WARN" for r in rows)
    print("preflight: ready" + (f" ({warns} warning(s))" if warns else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
