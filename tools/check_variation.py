# -*- coding: utf-8 -*-
"""check_variation.py - the WATCH VIDEO stop's variation report.

    python tools/check_variation.py <project>

Prints the cross-video findings for one candidate video against
channel/history.json. WARN-ONLY by design (the approved v2 design): the
report prints where run.ps1 pauses for the operator to watch the video;
nothing here blocks a ship. Empty history -> NOT RUN, never a pass.
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
    current = V.snapshot(project)
    findings = V.compare(V.load_history(), current)

    print(f"variation report for {project} "
          f"(history: {len(V.load_history())} shipped)")
    for f in findings:
        print("  " + f)
    if not findings:
        print("  nothing to compare - see [HUMAN-VAR] above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
