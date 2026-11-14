# -*- coding: utf-8 -*-
"""check_variation.py - the WATCH VIDEO stop's variation report.

    python tools/check_variation.py <project>

Exit codes:
    0  nothing to stop for (warnings may have printed)
    3  an [OPEN-ECHO] [STOP] finding - the opening repeats the previous
       video in a way the viewer SEES; run.ps1 halts at the WATCH VIDEO
       step until the operator answers for it (rerun to continue)
    2  usage

The rest of the findings stay warn-only by design (the approved v2
design): they print where run.ps1 pauses for the operator to watch the
video; nothing else blocks a ship. Empty history -> NOT RUN, never a
pass.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pipeline import variation as V  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    project = sys.argv[1]
    hist = V.load_history()
    current = V.snapshot(project)
    findings = V.compare(hist, current)

    print(f"variation report for {project} "
          f"(history: {'MISSING' if hist is None else len(hist)} shipped)")
    stop = False
    for f in findings:
        print("  " + f)
        if "[STOP]" in f:
            stop = True
    if stop:
        print("  -> OPEN-ECHO: answer for the echo, then rerun to "
              "continue (recorded exceptions live in the review).")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
