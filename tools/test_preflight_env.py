# -*- coding: utf-8 -*-
"""test_preflight_env.py - the run's first-minute machine check.

  VERSIONS        ffmpeg version lines from the builds people install
                  (Ubuntu 4.4 / 6.1, gyan.dev, BtbN git, n-tags) read right
  OLD-FFMPEG      ffmpeg 4.4 is a FAIL (its stream-copy join loses frames)
  KEY-NEVER-SHOWN the API key's value never appears in the output
  RUNPS1-CALLS    run.ps1 runs it before ingest and stops on exit 1
  RUNPS1-WAITS    run.ps1 waits for API batches (tags, beats, draft) up to
                  -WaitMin instead of stopping; -Wiki runs NAMES unattended

    python tools/test_preflight_env.py
"""
from __future__ import annotations

import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import preflight_env as P  # noqa: E402


def main() -> int:
    res = []
    lines = {"ffmpeg version 4.4.2-0ubuntu0.22.04.1 Copyright (c)": 4,
             "ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023": 6,
             "ffmpeg version 7.1-full_build-www.gyan.dev Copyright": 7,
             "ffmpeg version N-117865-g1f9a7d2e1b-20241125 Copyright": 99,
             "ffmpeg version 2024-11-25-git-1f9a7d2e1b-full_build": 99,
             "ffmpeg version n6.1.1 Copyright": 6,
             "garbage": 0}
    got = {k: P.parse_version(k) for k in lines}
    res.append(("VERSIONS", got == lines,
                "all read" if got == lines else f"{got}"))
    saved = P.ff_version
    P.ff_version = lambda exe: (4, "ffmpeg version 4.4.2-0ubuntu0.22.04.1")
    try:
        rows = P.checks(None)
    finally:
        P.ff_version = saved
    ff = [r for r in rows if r[1] == "ffmpeg"]
    res.append(("OLD-FFMPEG", ff and ff[0][0] == "FAIL",
                ff[0][2][:80] if ff else "no ffmpeg row"))
    marker = "PREFLIGHT-SENTINEL-VALUE-NOT-A-KEY-0042"
    old = os.environ.get("ANTHROPIC_API_KEY")
    os.environ["ANTHROPIC_API_KEY"] = marker
    buf = io.StringIO()
    try:
        sys.argv = ["preflight_env.py"]
        with redirect_stdout(buf):
            P.main()
    finally:
        if old is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = old
    out = buf.getvalue()
    res.append(("KEY-NEVER-SHOWN", marker not in out,
                "the key's value is not printed" if marker not in out
                else "THE KEY WAS PRINTED"))
    ps = (ROOT / "run.ps1").read_text(encoding="utf-8")
    i, j = ps.find("tools\\preflight_env.py"), ps.find("# 1. INGEST")
    res.append(("RUNPS1-CALLS", 0 < i < j and "exit 1" in ps[i:j],
                "called before ingest; exit 1 stops the run"))
    waits = (ps.count("Run-Waiting @('tools\\write_api.py', 'beats'") == 1
             and ps.count("Run-Waiting @('tools\\write_api.py', 'draft'") == 1
             and ps.count("collect --project $Project --wait --max-wait "
                          "$WaitMin") == 2
             and "[int]$WaitMin" in ps
             and "elseif ($Wiki -or (Test-Path" in ps
             and "@('names', '--project', $Project, '--wiki', $Wiki)" in ps)
    res.append(("RUNPS1-WAITS", waits, "beats and draft wait through "
                "Run-Waiting, both tag collects pass --max-wait, -Wiki runs "
                "names" if waits else "a wait or the -Wiki path is missing"))
    bad = 0
    for name, ok, msg in res:
        print(f'{"PASS" if ok else "FAIL"}  {name:<16} {msg}')
        bad += not ok
    print("-" * 60)
    print("test_preflight_env: all pass" if not bad else
          f"test_preflight_env: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
