"""Phase 0 wiring defects: each found by reading code, each confirmed by running it.

  D  run.ps1's draft checkpoint told the user to resume with `-From render`,
     but the `filmspeaks` stage is defined AFTER that checkpoint - so resuming
     as instructed skipped it entirely. A 17-minute film shipped with ZERO
     film_speaks units, and this is how.

  E  tools/act_payload.py showed the writing agent a word budget of
     `raw_duration_sec * 1.4 * 3.5`: a hardcoded 1.4x slow-motion ceiling when
     the real one has been 1.15x for some time, and no allowance for GAP, the
     fitter's capacity margin or the per-tag measured rate. Measured, it was
     34-41% too generous - the agent was told it had room it did not have, and
     then the render rejected the lines.

  F  the zoom direction was `idx % 2` where idx came from
     enumerate(draft['lines']), and that parity is part of the clip cache key.
     Inserting or deleting ONE line flipped every later line's zoom and so
     invalidated every later clip: editing near the front meant re-encoding
     the whole film. The same `idx` was also passed as `line_id` into
     BindingViolation, so a violation named the wrong line.

  G  stems.py separated the WHOLE FILM when needed_spans() came back empty.
     Since film audio was restricted to action/tense runs, empty is an
     ordinary answer meaning "nothing needs separating" - and the fallback
     then spent ~1.6s per second of audio on a stem nothing would read, about
     2.7 hours on a 104-minute film.

  H  freezedetect ran TWICE over the finished film: once inside
     motion_check.check() and once in render.py to fill the report table.
     2-5 minutes of decode per render for a list check() already had.

Run:  python tools/test_phase0_wiring.py
"""
from __future__ import annotations

import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config  # noqa: E402

RUNPS1 = io.open(os.path.join(ROOT, "run.ps1"), encoding="utf-8",
                 errors="replace").read()
RENDER = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                 encoding="utf-8").read()
STEMS = io.open(os.path.join(ROOT, "pipeline", "stems.py"),
                encoding="utf-8").read()
MC = io.open(os.path.join(ROOT, "pipeline", "motion_check.py"),
             encoding="utf-8").read()


def test_resume_runs_filmspeaks() -> tuple[bool, str]:
    # the stage order the script itself declares
    m = re.search(r"'draft',\s*'filmspeaks',\s*'render'", RUNPS1)
    if not m:
        return False, ("run.ps1 no longer declares filmspeaks between draft "
                       "and render; re-check this case")
    # every resume hint AFTER the draft checkpoint must not skip filmspeaks
    lines = RUNPS1.splitlines()
    chk = next((i for i, l in enumerate(lines)
                if "DUYET DRAFT" in l), None)
    if chk is None:
        return False, "could not find the draft-review checkpoint"
    bad = []
    for i in range(chk, len(lines)):
        mm = re.search(r"-From (\w+)", lines[i])
        if mm and "run.ps1 -Project" in lines[i]:
            if mm.group(1) == "render":
                bad.append(i + 1)
            break      # only the checkpoint's own hint matters here
    if bad:
        return False, (f"the draft checkpoint at line {bad} still resumes with "
                       f"-From render, which skips the filmspeaks stage "
                       f"defined below it")
    if "-From filmspeaks" not in RUNPS1:
        return False, "nothing tells the user to resume at filmspeaks"
    return True, ("the draft checkpoint resumes at filmspeaks, so the stage "
                  "between draft and render cannot be skipped")


def test_writer_budget_shared() -> tuple[bool, str]:
    src = io.open(os.path.join(ROOT, "tools", "act_payload.py"),
                  encoding="utf-8").read()
    import ast
    tree = ast.parse(src)
    code = "\n".join(ast.unparse(n) for n in tree.body)
    if re.search(r"\*\s*1\.4\s*\*\s*3\.5", code):
        return False, ("act_payload still computes its own budget from a 1.4x "
                       "slowdown and 3.5 words/sec")
    if "budget_words" not in code:
        return False, "act_payload does not use preflight.budget_words()"
    # and the numbers must actually differ, or this changed nothing
    from pipeline.preflight import budget_words
    worst = 0.0
    for w in (3.0, 5.0, 8.0, 12.0, 20.0):
        old = int(w * 1.4 * 3.5)
        new = budget_words(w)
        if new <= 0:
            return False, f"budget_words({w}) returned {new}"
        worst = max(worst, (old - new) / new)
    if worst < 0.15:
        return False, (f"the old formula was only {worst:.0%} more generous; "
                       f"this case no longer demonstrates the defect")
    return True, (f"the writer's budget comes from preflight.budget_words(); "
                  f"the old formula was up to {worst:.0%} more generous")


def test_zoom_keyed_on_line_id() -> tuple[bool, str]:
    if re.search(r"if idx % 2 == 0:", RENDER):
        return False, ("the zoom phase is still keyed on the draft POSITION, "
                       "so inserting a line re-encodes every clip after it")
    if "str(idx % 2)" in RENDER:
        return False, "the clip cache key still contains the draft position"
    if "str(line_id % 2)" not in RENDER:
        return False, "the cache key no longer carries the zoom phase at all"
    if RENDER.count("if line_id % 2 == 0:") < 2:
        return False, ("only one of the two zoom sites is keyed on the line "
                       "id")
    if "line_id=idx," in RENDER:
        return False, ("BindingViolation is still handed the draft position as "
                       "its line_id, so it names the wrong line")
    # the call sites must pass the real id
    for probe in ("end, 0.0, lid, crop_top,", "end, hold, lid, crop_top,",
                  "cout, lid, crop_top, hold,", "sil_secs, lid, crop_top,"):
        if probe not in RENDER:
            return False, f"a builder/signature call still passes idx: {probe}"
    return True, ("zoom phase and the clip cache key are keyed on the line's "
                  "own id, so editing one line does not invalidate the rest")


def test_stems_skip_when_unused() -> tuple[bool, str]:
    i = STEMS.find("spans = needed_spans(draft, src_dur=total)")
    if i < 0:
        return False, "could not find the span decision in stems.py"
    seg = STEMS[i:i + 1800]
    if "if draft and not spans" not in seg:
        return False, ("an empty span list still falls through to separating "
                       "the whole film, which is what 'nothing is needed' now "
                       "means")
    if "return None" not in seg:
        return False, "the no-work case does not return without separating"
    if "UNKNOWN" not in seg:
        return False, ("the no-draft case is not distinguished from the "
                       "nothing-needed case; only the first justifies doing "
                       "all of it")
    # the render must not STOP for a stem nothing needs
    if "_needs_stem" not in RENDER:
        return False, ("the render still treats a missing stem as fatal "
                       "regardless of whether any line reads it")
    j = RENDER.find("_needs_stem = bool")
    if "FILM_AUDIO_REQUIRE_STEMS" not in RENDER[j:j + 600]:
        return False, "the requirement check is no longer reached"
    return True, ("nothing needed means nothing separated, 'no draft' is "
                  "treated differently, and the render does not stop for a "
                  "stem no line reads")


def test_freezedetect_runs_once() -> tuple[bool, str]:
    if "freezes(ff, final)" not in MC:
        return False, "motion_check.check no longer measures freezes"
    if not re.search(r"return \(not problems\), problems, fz", MC):
        return False, ("check() does not return the freeze list it already "
                       "measured, so a caller that needs it must re-run "
                       "ffmpeg over the whole film")
    # render must take it from the return, not re-run
    if re.search(r"^\s*_frz = _mc\.freezes\(", RENDER, re.M):
        return False, ("render.py still calls _mc.freezes() a second time - "
                       "that is a full decode of the finished film per render")
    if "_mok, _mbad, _frz = _mc.check(" not in RENDER:
        return False, "render.py does not take the freeze list from check()"
    return True, ("check() returns its freeze list and render.py uses it, so "
                  "freezedetect decodes the finished film once per render")


TESTS = {
    "RESUME-RUNS-FILMSPEAKS":  test_resume_runs_filmspeaks,
    "WRITER-BUDGET-SHARED":    test_writer_budget_shared,
    "ZOOM-KEYED-ON-LINE-ID":   test_zoom_keyed_on_line_id,
    "STEMS-SKIP-WHEN-UNUSED":  test_stems_skip_when_unused,
    "FREEZEDETECT-RUNS-ONCE":  test_freezedetect_runs_once,
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
        print(f'{"PASS" if ok else "FAIL"}  {name:<25} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_phase0_wiring: all pass" if not bad else
          f"test_phase0_wiring: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
