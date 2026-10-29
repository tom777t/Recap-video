"""Every final-file measurement ends up in projects/<name>/final_report.md.

WHY
---
Seven defects got through because every gate validated the PLAN. The gates now
measure the finished file - but their output was a few hundred lines of dim
console log interleaved with the build, and a number that scrolled past at
02:14 of a render is not evidence anybody can check.

Cases
-----
  ALL-CHECKS-REGISTERED  every final-file check writes into the report. If a
                         new one is added without registering, this fails.
  SURVIVES-FATAL         the report is written BEFORE every fatal exit. A
                         report emitted only on the happy path tells you
                         nothing about the run you need to understand, and
                         that is the easy thing to get wrong.
  PATH-PRINTED           the render prints where it put the file.
  SKIPPED-IS-NOT-PASS    a check that could not run reads SKIPPED, never PASS.
                         "Unknown" masquerading as "clean" is the exact shape
                         of the original defect: a freeze check that scanned
                         255s of a 1054s film reported no freezes.
  FINDINGS-HAVE-TIMES    a finding with a position renders an OUTPUT timestamp
                         in m:ss.cc, which is what you type into a player.
  NUMBERS-AND-ROWS       every measured number and per-item row reaches the
                         file, not just the verdict.
  REAL-RENDER-WRITES-IT  a real end-to-end render produces the file, with the
                         checks in it. Runs the actual renderer.

Run:  python tools/test_final_report.py
"""
from __future__ import annotations

import io
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if os.path.join(ROOT, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools"))

import config  # noqa: E402
from pipeline import final_report as fr  # noqa: E402

RENDER_SRC = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                     encoding="utf-8").read()

# Every check that measures the FINISHED file (or the audio that went into it).
EXPECTED = [
    "FILE-CHECK",        # streams, frames, pts
    "MOTION-CHECK",      # freezes + source reuse
    "REPEAT-SCENE",      # perceptual hash
    "FILM-AUDIO",        # stem placement by correlation
    "MUSIC-CUE",         # cue lift over the bed
    "FILM-SPEAKS",       # film over the music
    "VOICE-RATE",        # measured WPM vs TARGET_WPM
    "RUNTIME-BAND",      # length vs the film it recaps
    "QUALITY-CONTRACT",  # format contract
    "RENDER-CHECK",      # position drift + draft consistency
]


def test_all_checks_registered() -> tuple[bool, str]:
    got = set(re.findall(r'_rep\.add\(\s*"([A-Z][A-Z0-9-]+)"', RENDER_SRC))
    missing = [n for n in EXPECTED if n not in got]
    if missing:
        return False, (f"these final-file checks do not write into the "
                       f"report: {missing}")
    extra = sorted(got - set(EXPECTED))
    return True, (f"all {len(EXPECTED)} checks register"
                  + (f" (plus {extra})" if extra else ""))


def test_survives_fatal() -> tuple[bool, str]:
    lines = RENDER_SRC.splitlines()
    try:
        start = next(i for i, l in enumerate(lines)
                     if "_rep = _fr.Report" in l)
    except StopIteration:
        return False, "the render never builds a report"
    bad = []
    n = 0
    for i in range(start, len(lines)):
        if "sys.exit" not in lines[i]:
            continue
        n += 1
        window = "\n".join(lines[max(0, i - 8):i])
        if "_write_report()" not in window:
            bad.append(i + 1)
    if bad:
        return False, (f"{len(bad)} fatal exit(s) after the report is built "
                       f"do not write it first, at line(s) {bad} - the run "
                       f"that most needs a report would produce none")
    if n == 0:
        return False, ("no fatal exits found after the report is built; this "
                       "case is no longer checking anything")
    if "_write_report()" not in RENDER_SRC.split("Done!")[-1]:
        return False, "the report is not written on the success path"
    return True, (f"all {n} fatal exit(s) write the report first, and the "
                  f"success path writes it too")


def test_path_printed() -> tuple[bool, str]:
    i = RENDER_SRC.find("def _write_report")
    body = RENDER_SRC[i:i + 700]
    if "console.print" not in body:
        return False, "the report's path is never printed"
    if "Full measurements" not in body:
        return False, "the printed line does not label itself"
    if "_rep.write()" not in body:
        return False, "_write_report does not call Report.write()"
    return True, "the render prints the report's path when it writes it"


def test_skipped_is_not_pass() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        r = fr.Report("t", Path(td) / "final.mp4")
        r.add("A", None, "could not run")
        r.add("B", True, "fine")
        r.add("C", False, "broken", fatal=True)
        r.add("D", False, "iffy", fatal=False)
        p = r.write(Path(td) / "r.md")
        txt = p.read_text(encoding="utf-8")
        if "**SKIPPED**" not in txt:
            return False, "a check that could not run is not marked SKIPPED"
        if "**FAIL**" not in txt or "**WARN**" not in txt:
            return False, ("a fatal failure and a non-fatal one are not "
                           "distinguished")
        if "1 pass, 1 fail, 1 warn, 1 skipped" not in txt:
            return False, f"the counts are wrong: {txt[:400]}"
        # the skipped one must NOT be counted as a pass anywhere
        if "2 pass" in txt:
            return False, "a skipped check was counted as a pass"
        return True, ("SKIPPED, PASS, WARN and FAIL are four distinct "
                      "verdicts and the counts keep them apart")


def test_findings_have_times() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        r = fr.Report("t", Path(td) / "final.mp4")
        r.add("X", False, "two problems",
              findings=[{"at": 181.22, "text": "unit too quiet"},
                        {"at": 764.47, "text": "other unit too quiet"},
                        {"text": "no position for this one"}])
        txt = r.write(Path(td) / "r.md").read_text(encoding="utf-8")
        if "[3:01.22]" not in txt:
            return False, (f"181.22s was not rendered as 3:01.22: "
                           f"{txt[txt.find('## Findings'):][:300]}")
        if "[12:44.47]" not in txt:
            return False, "764.47s was not rendered as 12:44.47"
        if "no position for this one" not in txt:
            return False, "a finding without a position was dropped"
        if fr.hms(3725.5) != "1:02:05.50":
            return False, f"an hour-long position formats as {fr.hms(3725.5)}"
        return True, ("findings carry OUTPUT timestamps in m:ss.cc, hours "
                      "roll over, and a finding without a position still "
                      "appears")


def test_numbers_and_rows() -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        r = fr.Report("t", Path(td) / "final.mp4")
        r.add("Y", True, "ok",
              numbers={"video stream (s)": 255.767, "fps": 30.0,
                       "codec": "h264", "nothing": None, "flag": True},
              rows=[{"line": 110, "at": "3:01.22", "margin (dB)": 3.2},
                    {"line": 111, "at": "12:44.47", "margin (dB)": 1.5}])
        txt = r.write(Path(td) / "r.md").read_text(encoding="utf-8")
        for probe in ("255.767", "h264", "| 110 |", "3.2", "12:44.47"):
            if probe not in txt:
                return False, f"{probe!r} did not reach the file"
        if "| nothing | - |" not in txt:
            return False, "a missing value is not rendered as '-'"
        if "| flag | yes |" not in txt:
            return False, "a boolean is not rendered readably"
        return True, ("numbers, per-item rows, missing values and booleans "
                      "all render")


def test_real_render_writes_it() -> tuple[bool, str]:
    """End-to-end: run the real renderer and read the file it leaves."""
    try:
        import test_render_smoke as smoke
    except Exception as e:
        return False, f"could not import the smoke harness: {e}"
    pdir = None
    try:
        pdir, draft = smoke._setup()
        narration = smoke._narration_for(pdir, draft["lines"])
        from pipeline import render as R
        _restore = smoke._no_stems()      # returns a restore callable
        try:
            R.render(smoke.PROJ, draft, narration, captions=False,
                     music=None)
        finally:
            _restore()
        rp = Path(pdir) / "final_report.md"
        if not rp.exists():
            return False, "a real render produced no final_report.md"
        txt = rp.read_text(encoding="utf-8")
        present = [n for n in EXPECTED if f"`{n}`" in txt]
        missing = [n for n in EXPECTED if n not in present]
        if missing:
            return False, (f"a real render left {missing} out of the report "
                           f"entirely. A check with nothing to measure must "
                           f"register as SKIPPED with a reason - omitting it "
                           f"leaves a report that looks complete and is not, "
                           f"which is the same shape as the freeze check that "
                           f"scanned 255s of a 1054s film and passed")
        if "FILE-CHECK" not in " ".join(present):
            return False, "the real report has no FILE-CHECK verdict"
        if "## Verdicts" not in txt or "## Measurements" not in txt:
            return False, "the real report is missing its sections"
        if "video stream (s)" not in txt:
            return False, ("the real report records no stream durations - the "
                           "one number the truncated render turned on")
        return True, (f"a real render wrote {len(txt.splitlines())} lines "
                      f"with {len(present)} of {len(EXPECTED)} checks "
                      f"({', '.join(present[:5])}...)")
    finally:
        if pdir:
            shutil.rmtree(Path(pdir), ignore_errors=True)


TESTS = {
    "ALL-CHECKS-REGISTERED": test_all_checks_registered,
    "SURVIVES-FATAL":        test_survives_fatal,
    "PATH-PRINTED":          test_path_printed,
    "SKIPPED-IS-NOT-PASS":   test_skipped_is_not_pass,
    "FINDINGS-HAVE-TIMES":   test_findings_have_times,
    "NUMBERS-AND-ROWS":      test_numbers_and_rows,
    "REAL-RENDER-WRITES-IT": test_real_render_writes_it,
}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    bad = 0
    for name in want:
        fn = TESTS.get(name)
        if fn is None:
            print(f"?? no such test: {name}")
            continue
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        print(f'{"PASS" if ok else "FAIL"}  {name:<23} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_final_report: all pass" if not bad else
          f"test_final_report: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
