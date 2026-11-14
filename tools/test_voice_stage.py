# -*- coding: utf-8 -*-
"""test_voice_stage.py - the VOICE stage judges capacity before any clip work.

`recap.py voice` exists so a narration overrun is found right after draft
approval, not after the render has run stems, probes and the censor policy.
These tests drive cmd_voice in-process on a scratch copy of the real project
with the TTS call replaced by a stub that returns chosen durations, so no
network and no API key are needed.

  FITS-EXITS-CLEAN      short narration -> no findings, returns normally
  OVERRUN-STOPS         narration longer than its window -> exit 1 without
                        --fit, and the pre-flight lists the line
  UNRUN-REFUSES         a check that did not run refuses before any TTS
  ESTIMATE-NOT-BLOCKING a word-count BINDING-VIOLATION does not stop the stage
                        (the real audio is what it measures)
  VOICE-ALL-AT-ONCE     cue, rate-drift and consistency problems are ALL listed
                        by this stage and stop it, even when every line fits -
                        they used to surface one per render (doublelife2023)

Run:  python tools/test_voice_stage.py      (exit 0 = all pass)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import recap  # noqa: E402
import pipeline.tts as tts  # noqa: E402

REAL = "tokyodrift2006"
SCRATCH = "_selftest_voice"
TITLE = "Exiled Teen Bets His Last Chance on One Deadly Downhill Race Against a Yakuza Heir"


def _scratch(corrupt_policy=False) -> Path:
    src, dst = Path(config.project_dir(REAL)), Path(config.project_dir(SCRATCH))
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    for p in src.iterdir():
        if p.is_file() and p.suffix in (".json", ".md", ".txt"):
            shutil.copy2(p, dst / p.name)
        elif p.is_dir() and p.name.endswith(".d"):
            shutil.copytree(p, dst / p.name)
    d = json.loads((dst / "draft.json").read_text(encoding="utf-8-sig"))
    d["title"] = TITLE
    (dst / "draft.json").write_text(json.dumps(d, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    if corrupt_policy:
        (dst / "coverage_policy.json").write_text("{ nope", encoding="utf-8")
    return dst


def _stub(seconds):
    """generate_tts stand-in: every narrated line lasts `seconds`."""
    calls = []

    def fake(project, draft, voice=None, rate=None, allow_edge=False):
        calls.append(1)
        nd = Path(config.project_dir(project)) / "narration"
        nd.mkdir(exist_ok=True)
        out = []
        for ln in draft["lines"]:
            if (ln.get("narration") or "").strip():
                out.append((ln["id"], nd / f"line_{int(ln['id']):03d}.mp3",
                            float(seconds)))
        return out
    fake.calls = calls
    return fake


import pipeline.voice_check as VC  # noqa: E402
_VC_REAL = {k: getattr(VC, k) for k in ("audit_cues", "rate_band_violations",
                                         "rate_drift", "measure", "analyse",
                                         "report")}


def _voice(ok=True):
    """The ONE-NARRATOR checks, stubbed: the capacity tests drive fake
    durations with no mp3 behind them, which no voice check can measure."""
    for k, v in _VC_REAL.items():
        setattr(VC, k, v)
    if ok:
        VC.audit_cues = lambda p: []
        VC.rate_band_violations = lambda p: []
        VC.rate_drift = lambda: (True, "stub")
        VC.measure = lambda *a, **k: []
        VC.analyse = lambda rows: {}
        VC.report = lambda res, project="": True
    else:
        VC.audit_cues = lambda p: ["cue STUB-CUE asks for tempo"]
        VC.rate_band_violations = lambda p: []
        VC.rate_drift = lambda: (False, "profile STUB-STALE")
        VC.measure = lambda *a, **k: []
        VC.analyse = lambda rows: {}
        VC.report = lambda res, project="": (print("STUB-CONSISTENCY failed"),
                                             False)[1]


def _drive(**kw) -> tuple[int, str, list]:
    args = argparse.Namespace(project=SCRATCH, fit=False, allow_edge=False,
                              ignore_audit=False, **kw)
    buf = io.StringIO()
    code = 0
    try:
        with redirect_stdout(buf):
            recap.cmd_voice(args)
    except SystemExit as e:
        code = int(e.code or 0)
    return code, buf.getvalue(), getattr(tts.generate_tts, "calls", [])


def test_fits_exits_clean():
    _scratch()
    _voice(ok=True)
    tts.generate_tts = _stub(0.4)
    code, out, calls = _drive()
    if code != 0 or "every narrated line fits" not in out:
        return False, f"exit {code}; tail: {out[-600:]}"
    return True, f"{len(calls)} TTS pass, no findings, exit 0"


def test_overrun_stops():
    _scratch()
    _voice(ok=True)
    tts.generate_tts = _stub(90.0)
    code, out, _ = _drive()
    if code != 1 or "CAPACITY" not in out.upper():
        return False, f"exit {code}; tail: {out[-600:]}"
    return True, "90 s narration on every line -> pre-flight list, exit 1, no fit"


def test_unrun_refuses():
    _scratch(corrupt_policy=True)
    _voice(ok=True)
    tts.generate_tts = _stub(0.4)
    code, out, calls = _drive()
    if code != 1 or "Refusing to voice" not in out or calls:
        return False, f"exit {code}, TTS calls {len(calls)}; tail: {out[-600:]}"
    return True, "corrupt policy -> 'Refusing to voice' before any TTS call"


def test_estimate_not_blocking():
    _scratch()
    _voice(ok=True)
    tts.generate_tts = _stub(0.4)
    code, out, calls = _drive()
    est = "BINDING-VIOLATION" in out
    if code != 0 or not calls:
        return False, f"exit {code}, TTS calls {len(calls)}"
    return True, ("the draft audit's estimate-based BINDING-VIOLATION "
                  + ("was present and " if est else "(absent on this machine) ")
                  + "did not stop the stage")


def test_voice_all_at_once():
    _scratch()
    _voice(ok=False)
    tts.generate_tts = _stub(0.4)          # every line FITS its window
    try:
        code, out, calls = _drive()
    finally:
        _voice(ok=True)
    want = ("STUB-CUE", "STUB-STALE", "STUB-CONSISTENCY")
    miss = [w for w in want if w not in out]
    if code != 1 or miss or "every narrated line fits" in out:
        return False, f"exit {code}, missing {miss}; tail: {out[-400:]}"
    return True, "3 voice problems listed together, stage stops before render"


TESTS = {
    "FITS-EXITS-CLEAN":      test_fits_exits_clean,
    "OVERRUN-STOPS":         test_overrun_stops,
    "UNRUN-REFUSES":         test_unrun_refuses,
    "ESTIMATE-NOT-BLOCKING": test_estimate_not_blocking,
    "VOICE-ALL-AT-ONCE":     test_voice_all_at_once,
}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    real_gen = tts.generate_tts
    bad = 0
    try:
        for name in want:
            try:
                ok, msg = TESTS[name]()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, msg = False, f"raised {type(e).__name__}: {e}"
            finally:
                tts.generate_tts = real_gen
            print(f"{'PASS' if ok else 'FAIL'}  {name:<22} {msg}")
            bad += 0 if ok else 1
    finally:
        shutil.rmtree(config.project_dir(SCRATCH), ignore_errors=True)
    print("-" * 60)
    print(f"test_voice_stage: {bad} FAILURE(S)" if bad
          else "test_voice_stage: all pass")
    sys.exit(1 if bad else 0)
