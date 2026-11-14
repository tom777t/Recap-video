# -*- coding: utf-8 -*-
"""test_rate_ceiling.py - no rate_bump may ask Inworld for more than it allows.

doublelife2023: fit_narration set rate_bump 1.10 on `normal` lines whose tag
already runs at speakingRate 1.46. 1.46 x 1.10 = 1.61; the provider's clamp
was 1.60 and Inworld refuses anything above 1.5, so the render stopped with an
HTTP 400 after 43 lines had been synthesized.

  CLAMP-AT-ENGINE   controls_for(tag, 1.10) never resolves above the ceiling
  HEADROOM          max_speed_mult = ceiling / tag rate (mystery at 1.5 -> 1.0)
  FIT-CAP           fit_narration.line_bump_cap never exceeds the headroom, and
                    is 1.0 (no bump, trim only) for a tag on the ceiling
  GUARD-BEFORE-CALL a mapping above the ceiling raises before any HTTP request
  REAL-TAGS         every mapped tag x the voice-band bump stays legal

Run:  python tools/test_rate_ceiling.py      (exit 0 = all pass)
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import tts_providers as TP  # noqa: E402
import fit_narration as FN  # noqa: E402

CEIL = float(config.VOICE_SPEAKING_RATE_MAX)
BAND = round(1.0 + float(config.VOICE_RATE_BAND), 4)


def _inworld():
    return TP.all_providers()["inworld"]


def t_clamp():
    p = _inworld()
    bad = [(t, p.controls_for(t, BAND)["speaking_rate"]) for t in p.delivery
           if p.controls_for(t, BAND)["speaking_rate"] > CEIL + 1e-9]
    return (not bad, f"bumped by {BAND}x every tag resolves <= {CEIL}"
            if not bad else f"above the ceiling: {bad}")


def t_headroom():
    p = _inworld()
    m = p.max_speed_mult("mystery")
    n = p.max_speed_mult("normal")
    want_n = CEIL / float(p.controls_for("normal")["speaking_rate"])
    ok = abs(m - max(1.0, CEIL / float(p.controls_for("mystery")
                                        ["speaking_rate"]))) < 1e-6 \
        and abs(n - want_n) < 1e-6
    return ok, f"mystery {m:.3f}, normal {n:.3f} (want {want_n:.3f})"


def t_fit_cap():
    p = _inworld()
    probs = []
    for t in p.delivery:
        cap = FN.line_bump_cap(t, BAND)
        rate = float(p.controls_for(t)["speaking_rate"])
        if rate * cap * 1.0 > CEIL + 1e-9:
            probs.append(f"{t}: {rate} x {cap} > {CEIL}")
        if cap > BAND + 1e-9:
            probs.append(f"{t}: cap {cap} above the voice band {BAND}")
    on_ceiling = [t for t in p.delivery
                  if float(p.controls_for(t)["speaking_rate"]) >= CEIL - 1e-9]
    for t in on_ceiling:
        if FN.line_bump_cap(t, BAND) != 1.0:
            probs.append(f"{t} sits on the ceiling but may still be bumped")
    return (not probs, f"{len(p.delivery)} tags capped; on the ceiling (trim "
            f"only): {on_ceiling or 'none'}" if not probs else "; ".join(probs))


def t_guard():
    p = _inworld()
    saved_d, saved_post = dict(p.delivery), p._post
    calls = []
    os.environ.setdefault(p.env_var, "dGVzdDp0ZXN0")
    try:
        p.delivery = {**saved_d, "normal": {**saved_d["normal"],
                                            "speaking_rate": CEIL + 0.1}}
        p._post = lambda *a, **k: calls.append(1) or b"{}"
        try:
            p.synthesize("hello", "normal",
                         Path(tempfile.gettempdir()) / "_rate_guard.mp3")
            return False, "a 1.6 speakingRate was sent without an error"
        except TP.SynthesisFailed as e:
            return (not calls, f"refused before any request: {str(e)[:70]}")
    finally:
        p.delivery, p._post = saved_d, saved_post


def t_real_tags():
    p = _inworld()
    worst = max((float(p.controls_for(t, FN.line_bump_cap(t, BAND))
                       ["speaking_rate"]), t) for t in p.delivery)
    return worst[0] <= CEIL + 1e-9, f"highest bumped rate {worst[0]} ({worst[1]})"


TESTS = [("CLAMP-AT-ENGINE", t_clamp), ("HEADROOM", t_headroom),
         ("FIT-CAP", t_fit_cap), ("GUARD-BEFORE-CALL", t_guard),
         ("REAL-TAGS", t_real_tags)]

if __name__ == "__main__":
    fails = 0
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:  # a crash is a failure, not a skip
            ok, msg = False, f"{type(e).__name__}: {e}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:18s} {msg}")
    print("-" * 60)
    print("test_rate_ceiling: all pass" if not fails
          else f"test_rate_ceiling: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
