# -*- coding: utf-8 -*-
"""test_stale_once.py - the STALE voice-profile warning is said once a run.

production_profile() is asked for every line the budget checks; with a
stale profile the Lost in the Stars draft log printed the same four-line
warning ~190 times and buried the gate report.

    python tools/test_stale_once.py
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline import calibration as C  # noqa: E402


def test_once() -> tuple[bool, str]:
    key = C.production_voice_key()
    saved = (C._load_all, C.mapping_signature)
    C._STALE_SAID.clear()
    try:
        C._load_all = lambda: {key: {"mapping_signature": "old"}}
        C.mapping_signature = lambda: "new"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            profs = [C.production_profile() for _ in range(50)]
        n = buf.getvalue().count("STALE")
        base = C.default_profile()
        if any(p.words_per_sec != base.words_per_sec for p in profs):
            return False, "a later call did not fall back to the baseline"
        if n != 1:
            return False, f"warning printed {n} times over 50 calls"
        return True, "50 calls: 1 warning, every call on the baseline"
    finally:
        C._load_all, C.mapping_signature = saved
        C._STALE_SAID.clear()


if __name__ == "__main__":
    ok, msg = test_once()
    print(f'{"PASS" if ok else "FAIL"}  STALE-ONCE  {msg}')
    print("-" * 60)
    print("test_stale_once: all pass" if ok else "test_stale_once: 1 FAILURE(S)")
    sys.exit(0 if ok else 1)
