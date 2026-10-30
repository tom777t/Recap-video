"""A gate must not be green because its input was deleted.

THE DEFECT
----------
The shipped report said:

    MUSIC-CUE    SKIPPED   no prebuilt music track (no music/bed.* +
                           music/cues/*), so there are no cues to measure
    FILM-SPEAKS  SKIPPED   no prebuilt music track, so the film-vs-music
                           margin could not be measured

...while the same render's log showed cues being placed from action1.mp3, and
`music/bed.mp3` and five cue files were sitting in the project all along.

Cause: `build_music_track` wrote music_plan.json next to its output in
projects/<name>/_work/, and render.py rmtree's that directory ~260 lines
BEFORE the post-render checks read it. So both checks could only ever run with
--keep-temp, and on every normal render they reported SKIPPED.

Two compounding mistakes, both worth naming:

  1. The gate's input lived in a directory something else owns and deletes.
  2. The skip message ASSERTED a cause it had never checked. "No prebuilt
     music track" was a guess, and it sent the reader looking for a missing bed
     file instead of at the deletion. A skip reason that guesses is worse than
     one that says "I do not know".

FILM-SPEAKS did not need the file at all: the render has the unit windows in
memory. Routing a measurement that does not depend on music through a music
file is what made it deletable.

Cases
-----
  PLAN-SURVIVES-CLEANUP   the plan is written where the render does not delete
                          it, and is still readable after rmtree(_work).
  NO-GATE-INPUT-IN-WORK   no post-render check reads anything out of _work.
  FILM-SPEAKS-NEEDS-NO-PLAN  it uses the in-memory windows.
  SKIP-REASONS-DISTINCT   "no music", "no cue track", "planner placed none"
                          and "the file is missing although a track was
                          built" are four different reports, and the last is a
                          FAILURE, not a skip.
  REAL-RENDER-MEASURES    on a real render with the temp dir cleaned as normal,
                          FILM-SPEAKS produces a number instead of SKIPPED.

Run:  python tools/test_gate_reachable.py
"""
from __future__ import annotations

import io
import json
import os
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

RENDER_SRC = io.open(os.path.join(ROOT, "pipeline", "render.py"),
                     encoding="utf-8").read()
MUSIC_SRC = io.open(os.path.join(ROOT, "pipeline", "music.py"),
                    encoding="utf-8").read()
PROJ = Path(config.project_dir("tokyodrift2006"))


def test_plan_survives_cleanup() -> tuple[bool, str]:
    if not (PROJ / "music" / "bed.mp3").exists():
        return False, "the project's music files are missing"
    from pipeline import music as mus
    cues = sorted((PROJ / "music" / "cues").glob("*.mp3"))
    pick = {p.stem.rstrip("0123456789"): p for p in cues}
    if "tense" not in pick:
        return False, f"need a tense cue, have {list(pick)}"
    plan_path = PROJ / "music_plan.json"
    backup = plan_path.read_bytes() if plan_path.exists() else None
    work = Path(tempfile.mkdtemp(prefix="planwork_"))
    try:
        if plan_path.exists():
            plan_path.unlink()
        ok = mus.build_music_track(
            config.ffmpeg(), PROJ, work / "music_track.wav", 40.0,
            PROJ / "music" / "bed.mp3",
            [{"start": 10.0, "end": 22.0, "mood": "tense",
              "file": str(pick["tense"])}],
            reveal_positions=[], hold_windows=[],
            film_speaks_windows=[(30.0, 36.0)])
        if not ok:
            return False, "the music track failed to build"
        if (work / "music_plan.json").exists():
            return False, ("the plan is still written into the work dir, "
                           "which the render deletes before reading it")
        if not plan_path.exists():
            return False, "the plan was not written to the project dir"
        # exactly what the render does
        shutil.rmtree(work, ignore_errors=True)
        if not plan_path.exists():
            return False, "the plan did not survive rmtree(_work)"
        d = json.loads(plan_path.read_text(encoding="utf-8"))
        if len(d.get("cues") or []) != 1:
            return False, f"the surviving plan records {d.get('cues')}"
        return True, (f"written to {plan_path.name} in the project dir and "
                      f"still readable after rmtree(_work), with "
                      f"{len(d['cues'])} cue(s) and "
                      f"{len(d.get('film_speaks') or [])} unit(s)")
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if backup is not None:
            plan_path.write_bytes(backup)


def test_no_gate_input_in_work() -> tuple[bool, str]:
    """No post-render check may read out of the directory the render deletes."""
    i = RENDER_SRC.find("rmtree(work)")
    if i < 0:
        return False, "the render no longer deletes the work dir; re-check this"
    after = RENDER_SRC[i:]
    bad = []
    for probe in ('work / "music_plan.json"', 'work / "music_track.wav"',
                  'work /"music_plan.json"'):
        if probe in after:
            bad.append(probe)
    if bad:
        return False, (f"these are read AFTER rmtree(work): {bad} - the gate "
                       f"can only be green because the file is gone")
    return True, ("nothing after the temp cleanup reads out of the deleted "
                  "directory")


def test_film_speaks_needs_no_plan() -> tuple[bool, str]:
    if "_fsw = list(film_speaks_windows)" not in RENDER_SRC:
        return False, ("FILM-SPEAKS still reads its windows out of the music "
                       "plan file; it has them in memory and does not depend "
                       "on music at all")
    if '_fsw = _mp.get("film_speaks")' in RENDER_SRC:
        return False, "the old plan-file path is still present"
    return True, ("FILM-SPEAKS measures the render's own in-memory unit "
                  "windows, so it cannot be skipped by a missing music file")


def test_skip_reasons_distinct() -> tuple[bool, str]:
    i = RENDER_SRC.find('_mplan = pdir / "music_plan.json"')
    if i < 0:
        return False, "the plan is not read from the project dir"
    seg = RENDER_SRC[i:i + 2600]
    if "no prebuilt music track (no music/bed" in RENDER_SRC:
        return False, ("the old message is still there: it asserts a cause it "
                       "never checked")
    for probe, why in (
            ("no music at all", "the genuinely-no-music case"),
            ("_mnote", "the bed-only case, quoting resolve_music's own note"),
            ("pipeline bug", "the missing-file case"),
            ("planner placed", "the no-cues-planned case")):
        if probe not in seg:
            return False, f"the skip reasons do not distinguish {why}"
    # the missing-file case must be a FAILURE, not a skip
    j = seg.find("pipeline bug")
    around = seg[max(0, j - 600):j + 400]
    if '_rep.add("MUSIC-CUE", False' not in around:
        return False, ("a built track with a missing plan file is reported as "
                       "a SKIP; it is a defect in this pipeline and must read "
                       "as one")
    if "problems.append" not in around:
        return False, "the missing-file case is not recorded as a problem"
    return True, ("four causes, four different reports, and the "
                  "missing-file case is a FAILURE rather than a skip")


def test_real_render_measures() -> tuple[bool, str]:
    """End-to-end, temp dir cleaned as normal: FILM-SPEAKS must produce a number."""
    try:
        import test_render_smoke as smoke
    except Exception as e:
        return False, f"could not import the smoke harness: {e}"
    pdir = None
    try:
        pdir, draft = smoke._setup()
        narr = smoke._narration_for(pdir, draft["lines"])
        from pipeline import render as R
        restore = smoke._no_stems()
        try:
            R.render(smoke.PROJ, draft, narr, captions=False, music=None)
        finally:
            restore()
        txt = (Path(pdir) / "final_report.md").read_text(encoding="utf-8")
        row = [ln for ln in txt.splitlines()
               if ln.startswith("| `FILM-SPEAKS`")]
        if not row:
            return False, "FILM-SPEAKS is absent from the report"
        if "SKIPPED" in row[0]:
            return False, (f"FILM-SPEAKS is still SKIPPED on a normal render: "
                           f"{row[0][:140]}")
        if "dB" not in row[0]:
            return False, f"FILM-SPEAKS reported no measurement: {row[0][:140]}"
        if "_work" in txt and "deleted" in txt:
            pass
        return True, (f"on a real render with the temp dir cleaned: "
                      f"{row[0].strip()[:110]}")
    finally:
        if pdir:
            shutil.rmtree(Path(pdir), ignore_errors=True)


TESTS = {
    "PLAN-SURVIVES-CLEANUP":    test_plan_survives_cleanup,
    "NO-GATE-INPUT-IN-WORK":    test_no_gate_input_in_work,
    "FILM-SPEAKS-NEEDS-NO-PLAN": test_film_speaks_needs_no_plan,
    "SKIP-REASONS-DISTINCT":    test_skip_reasons_distinct,
    "REAL-RENDER-MEASURES":     test_real_render_measures,
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
        print(f'{"PASS" if ok else "FAIL"}  {name:<26} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_gate_reachable: all pass" if not bad else
          f"test_gate_reachable: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
