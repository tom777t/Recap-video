# -*- coding: utf-8 -*-
"""test_censor_span.py - a clip is censored by every flagged shot it shows.

Lost in the Stars: hold 220 (5930.3-5932.8 s) is hosted by an unflagged
shot but plays 0.4 s of the flagged bullying shot (01:38:52.375); the clip
took its host's "none" and the render's audit stopped on footage that would
have been published unblurred. censor.span_censor raises a clip to the
strongest flagged shot its span reaches.

    python tools/test_censor_span.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline import censor as C  # noqa: E402
from pipeline.schemas import CensorRegion as R  # noqa: E402

BULLY = ("01:38:52.375", "01:39:01.458")
LEV = {BULLY: "blur_light", ("01:40:00.000", "01:40:05.000"): "blur_heavy"}
REG = {BULLY: R(x=740, y=380, width=300, height=436),
       ("01:40:00.000", "01:40:05.000"): R(x=100, y=100, width=200, height=200)}
HOST = ("01:38:44.000", "01:38:52.375")


def main() -> int:
    res = []
    lv, rg = C.span_censor(5930.3, 5932.8, HOST, LEV, REG, R)
    res.append(("RUNS-INTO-FLAG", lv == "blur_light" and rg == REG[BULLY],
                f"hold 220 -> {lv} {rg}"))
    lv, rg = C.span_censor(5920.0, 5932.4, HOST, LEV, REG, R)
    res.append(("TOUCH-IGNORED", lv == "none",
                f"0.025 s into the flagged shot -> {lv}"))
    lv, rg = C.span_censor(5935.0, 6002.0, BULLY, LEV, REG, R)
    res.append(("STRONGEST-AND-JOINED", lv == "blur_heavy" and rg is not None
                and (rg.x, rg.y, rg.x + rg.width, rg.y + rg.height)
                == (100, 100, 1040, 816),
                f"two flagged shots -> {lv}, box {rg}"))
    lv, rg = C.span_censor(5935.0, 5940.0, BULLY, LEV, REG, R)
    res.append(("HOST-ONLY", lv == "blur_light" and rg == REG[BULLY],
                f"inside its own flagged shot -> {lv}"))
    bad = 0
    for name, ok, msg in res:
        print(f'{"PASS" if ok else "FAIL"}  {name:<20} {msg}')
        bad += not ok
    print("-" * 60)
    print("test_censor_span: all pass" if not bad else
          f"test_censor_span: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
