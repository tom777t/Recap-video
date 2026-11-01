# -*- coding: utf-8 -*-
"""test_silent_failures.py - a check that cannot run must never read as a pass.

The Tokyo Drift rewrite shipped "all gates green" for nine rounds while ten
gates had not run: draft.json failed the schema, the handler printed one dim
line, returned None, and the caller turned None into "clean". A survey of
every broad exception handler on the draft and render paths then found 26 more
places with the same shape - a gate's input could not be read or the gate
itself crashed, and the outcome was indistinguishable from a pass. These tests
pin each fixed path so it cannot drift back.

  CRAFT-CRASH-IS-ERROR      a crashing craft gate adds an error, not a red line
  PHASE1-LEDGER             a gate that cannot run inside the Phase 1 audits
                            makes the audit hard and is named in
                            audit_unavailable (real draft, corrupt policy)
  RENDER-REFUSES-UNRUN      `recap.py render` refuses while checks did not run
  NONE-IS-NOT-CLEAN         a non-dict audit result is "hard", never "clean"
  COVERAGE-POLICY-CORRUPT   absent policy = no policy; present-but-corrupt raises
  CENSOR-UNREADABLE         unreadable shots.json stops the censor path
  NAME-AT-REVEAL-UNREAD     unreadable reveal map -> "cannot verify" error
  FILM-SPEAKS-INPUTS        unreadable transcript/reveals raise; an unparseable
                            landing PROTECTS (inf), never "already landed" (0)
  REPEAT-SCENE-NO-FRAMES    no decodable frames -> None (not run), not True

Run:  python tools/test_silent_failures.py      (exit 0 = all pass)
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402

REAL = "tokyodrift2006"
SCRATCH = "_selftest_unrun"


def _scratch_project(corrupt_policy: bool) -> Path:
    """A copy of the real project's small JSON/MD inputs, nothing heavy."""
    src = Path(config.project_dir(REAL))
    dst = Path(config.project_dir(SCRATCH))
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    for p in src.iterdir():
        if p.is_file() and p.suffix in (".json", ".md", ".txt"):
            shutil.copy2(p, dst / p.name)
        elif p.is_dir() and p.name.endswith(".d"):
            shutil.copytree(p, dst / p.name)
    # A copied project carries the original's title, which [TITLE-MATCH]
    # rightly refuses before the Phase 1 audits are reached.
    dj = dst / "draft.json"
    d = json.loads(dj.read_text(encoding="utf-8-sig"))
    d["title"] = "Exiled Teen Bets His Last Chance on One Deadly Downhill Race Against a Yakuza Heir"
    dj.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    if corrupt_policy:
        (dst / "coverage_policy.json").write_text("{ not json", encoding="utf-8")
    return dst


def _run(*args, timeout=900) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "recap.py", *args], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# --------------------------------------------------------------------------- #
def test_craft_crash_is_error():
    import pipeline.draft as dr
    src = open(dr.__file__, encoding="utf-8").read()
    i = src.index("except Exception as _ce:")
    block = src[i:i + 900]
    if "errors.append(" not in block:
        return False, "the CRAFT handler prints but does not add to errors"
    return True, "a crashing craft gate appends to errors, so validation fails"


def test_phase1_ledger():
    _scratch_project(corrupt_policy=True)
    try:
        code, out = _run("draft", "--project", SCRATCH)
    finally:
        pass
    if "[AUDIT-UNAVAILABLE]" not in out or "BEAT-COVERAGE" not in out:
        return False, ("a corrupt coverage_policy.json did not surface as "
                       "AUDIT-UNAVAILABLE naming BEAT-COVERAGE:\n"
                       + out[-1500:])
    if code == 0:
        return False, "the draft exited 0 with a check that did not run"
    return True, ("corrupt coverage_policy.json -> [AUDIT-UNAVAILABLE] naming "
                  f"BEAT-COVERAGE/BRIDGE, exit {code}")


def test_render_refuses_unrun():
    _scratch_project(corrupt_policy=True)
    try:
        code, out = _run("render", "--project", SCRATCH, "--voice", "tts")
    finally:
        shutil.rmtree(config.project_dir(SCRATCH), ignore_errors=True)
    if code == 0 or "did NOT run" not in out or "Refusing to render" not in out:
        return False, ("render did not refuse on an unrun check:\n"
                       + out[-1500:])
    return True, "render refuses before any TTS: 'checks that did NOT run'"


def test_none_is_not_clean():
    import pipeline.draft as dr
    src = open(dr.__file__, encoding="utf-8").read()
    if 'else "clean"' in src.split("audit = _run_phase1_audits(project, pdir)")[1][:400]:
        return False, "a non-dict audit result still falls back to 'clean'"
    return True, "a non-dict audit result reads as 'hard'"


def test_coverage_policy_corrupt():
    import pipeline.draft as dr
    pdir = _scratch_project(corrupt_policy=False)
    try:
        (pdir / "coverage_policy.json").unlink()
        if dr._coverage_policy(SCRATCH) != set():
            return False, "an absent policy is not 'no policy'"
        (pdir / "coverage_policy.json").write_text("[[", encoding="utf-8")
        try:
            dr._coverage_policy(SCRATCH)
        except ValueError:
            return True, "absent -> set(); present-but-corrupt -> ValueError"
        return False, "a corrupt policy still returns set() (= no policy)"
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_censor_unreadable():
    from pipeline import censor
    d = Path(tempfile.mkdtemp())
    try:
        if censor.flagged_shots(d) != []:
            return False, "no shots.json should mean nothing flagged"
        (d / "shots.json").write_text("{ broken", encoding="utf-8")
        try:
            censor.flagged_shots(d)
        except ValueError:
            pass
        else:
            return False, ("unreadable shots.json returned [] = 'nothing to "
                           "blur', and the film would render uncensored")
        src = open(os.path.join(ROOT, "pipeline", "render.py"),
                   encoding="utf-8").read()
        i = src.index("Could not read shots.json censor/silence flags")
        if "sys.exit(1)" not in src[i - 900:i]:
            return False, "render does not stop on an unreadable shots.json"
        return True, "absent -> []; unreadable -> raise, and render stops"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_name_at_reveal_unread():
    from pipeline import continuity_gates as cg
    d = Path(tempfile.mkdtemp())
    try:
        (d / "reveals.json").write_text("{ nope", encoding="utf-8")
        (d / "names.json").write_text("[]", encoding="utf-8")
        rep = cg.continuity_report({"lines": []}, d)
        hit = [e for e in rep["errors"] if "cannot verify" in e]
        if not hit:
            return False, ("an unreadable reveals.json still reports clean: "
                           f"{rep['errors']}")
        return True, "unreadable reveal map -> [NAME-AT-REVEAL] cannot verify"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_film_speaks_inputs():
    from pipeline import film_speaks as fs
    pdir = _scratch_project(corrupt_policy=False)
    try:
        rv = json.loads((pdir / "reveals.json").read_text(encoding="utf-8-sig"))
        rows = rv.get("reveals") or []
        if not rows:
            return False, "the real reveal map has no rows to test with"
        rows[0]["land"] = "mid-credits"
        (pdir / "reveals.json").write_text(json.dumps(rv), encoding="utf-8")
        got = fs.reveal_rows(SCRATCH)
        if got[0]["land"] != float("inf"):
            return False, (f"an unparseable landing became {got[0]['land']} - "
                           f"0.0 means 'already landed' and unprotects it")
        (pdir / "reveals.json").write_text("{ broken", encoding="utf-8")
        try:
            fs.reveal_rows(SCRATCH)
            return False, "unreadable reveals.json returned [] (spoiler check off)"
        except ValueError:
            pass
        (pdir / "transcript.json").write_text("{ broken", encoding="utf-8")
        try:
            fs._transcript(pdir)
            return False, "unreadable transcript.json returned no candidates"
        except ValueError:
            pass
        return True, ("unparseable landing -> inf (protected); unreadable "
                      "reveals/transcript -> raise")
    finally:
        shutil.rmtree(pdir, ignore_errors=True)


def test_repeat_scene_no_frames():
    from pipeline import dupe_check
    d = Path(tempfile.mkdtemp())
    try:
        bad = d / "not_a_video.mp4"
        bad.write_bytes(b"\x00" * 2048)
        ok, _f, info = dupe_check.check(bad)
        if ok is True:
            return False, "no frames decoded, yet REPEAT-SCENE reported PASS"
        return True, f"no decodable frames -> {ok!r} (not run), sampled {info['sampled']}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


TESTS = {
    "CRAFT-CRASH-IS-ERROR":    test_craft_crash_is_error,
    "PHASE1-LEDGER":           test_phase1_ledger,
    "RENDER-REFUSES-UNRUN":    test_render_refuses_unrun,
    "NONE-IS-NOT-CLEAN":       test_none_is_not_clean,
    "COVERAGE-POLICY-CORRUPT": test_coverage_policy_corrupt,
    "CENSOR-UNREADABLE":       test_censor_unreadable,
    "NAME-AT-REVEAL-UNREAD":   test_name_at_reveal_unread,
    "FILM-SPEAKS-INPUTS":      test_film_speaks_inputs,
    "REPEAT-SCENE-NO-FRAMES":  test_repeat_scene_no_frames,
}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    bad = 0
    try:
        for name in want:
            try:
                ok, msg = TESTS[name]()
            except Exception as e:  # a crashing test is a failing test
                import traceback
                traceback.print_exc()
                ok, msg = False, f"raised {type(e).__name__}: {e}"
            print(f"{'PASS' if ok else 'FAIL'}  {name:<24} {msg}")
            bad += 0 if ok else 1
    finally:
        shutil.rmtree(config.project_dir(SCRATCH), ignore_errors=True)
    print("-" * 60)
    print(f"test_silent_failures: {bad} FAILURE(S)" if bad
          else "test_silent_failures: all pass")
    sys.exit(1 if bad else 0)
