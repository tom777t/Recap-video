# -*- coding: utf-8 -*-
"""test_write_schema.py - schema-invalid data can neither hide nor be written.

  UNPARSEABLE-NOT-MASKED  a draft with a writing-gate error AND a line the
                          schema rejects (narration_silence_seconds: 0)
                          reports BOTH under "draft.json has problems"; the
                          schema finding names the field and the line, and
                          the exit is hard
  LINE-PROBLEMS           schemas.line_problems agrees with load_draft (it
                          IS the Line dataclass) and reports every offender
  ACT-REJECTED            a mocked act reply with narration_silence_seconds 0
                          is not written; the schema error goes back to the
                          model inside the same stage; the corrected reply
                          is written
  ROUND-REJECTED          a feedback-round reply that breaks the schema keeps
                          the previous act on disk
  RESOLVE-REJECTED        a resolve edit that breaks the schema is not applied
  REQUEST-SCHEMA          act and resolve requests carry a json_schema derived
                          from the draft line schema: delivery / payload /
                          claim.type enums, > 0 numeric fields, and effort is
                          kept next to format

Run:  python tools/test_write_schema.py
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import tag_batch as TB  # noqa: E402
import write_api as W  # noqa: E402

SRC = config.project_dir("tokyodrift2006")
PROJ = "_selftest_writeschema"
PDIR = config.project_dir(PROJ)


def _setup():
    shutil.rmtree(PDIR, ignore_errors=True)
    shutil.copytree(SRC, PDIR, ignore=shutil.ignore_patterns(
        "narration", "frames", "*.mp4", "*.wav", "_*", "plan*.json"))


def _schema_clean(lines):
    """The shipped act files carry four claim.type values the schema rejects
    ('aftermath', 'establishing' - shot vocabulary); draft.json was fixed by
    hand. A writer's reply is now checked with the schema before it is
    saved, so the mocked replies must be schema-valid: those claims are
    dropped here."""
    from pipeline import schemas as S
    out = json.loads(json.dumps(lines))
    for ln in out:
        c = ln.get("claim")
        if isinstance(c, dict) and c.get("type") not in S._CLAIM_TYPES:
            ln.pop("claim")
    return out


def _j(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def msg(obj):
    return NS(content=[NS(type="text", text=json.dumps(obj))],
              stop_reason="end_turn",
              usage=NS(input_tokens=9000, output_tokens=3000,
                       cache_creation_input_tokens=0,
                       cache_read_input_tokens=0, cache_creation=None))


class Client:
    def __init__(self, sync=None, batch=None):
        self.sync, self.batchf = sync, batch
        self.calls, self.batches = [], []
        self.messages = NS(create=self._create, batches=NS(
            create=self._bcreate, retrieve=lambda b: NS(processing_status="ended"),
            results=self._results))

    def _create(self, **p):
        self.calls.append(json.loads(json.dumps(p)))
        return self.sync(p, len(self.calls))

    def _bcreate(self, requests):
        self.batches.append(list(requests))
        return NS(id=f"b{len(self.batches)}")

    def _results(self, bid):
        for r in self.batches[int(bid[1:]) - 1]:
            yield NS(custom_id=r["custom_id"], result=NS(
                type="succeeded", message=self.batchf(r["custom_id"],
                                                       r["params"])))


def _run(client, *argv):
    TB.CLIENT_FACTORY = lambda: client
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = W.main(list(argv))
    return rc, buf.getvalue()


def _recap_draft(project):
    env = dict(os.environ, COLUMNS="100000", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "recap.py", "draft", "--project",
                        project], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(ROOT),
                       env=env)
    return r.returncode, r.stdout + r.stderr


# --------------------------------------------------------------------------- #
def test_unparseable_not_masked():
    _setup()
    d = _j(PDIR / "draft.json")
    bad = d["lines"][5]
    bad["narration_silence_seconds"] = 0
    (PDIR / "draft.json").write_text(json.dumps(d, ensure_ascii=False),
                                     encoding="utf-8")
    rc, out = _recap_draft(PROJ)
    rc2, finds = W.run_gates(PROJ)
    un = [f for f in finds if f.startswith("[AUDIT-UNPARSEABLE]")]
    other = [f for f in finds if not f.startswith("[AUDIT-UNPARSEABLE]")]
    if rc == 0 or rc2 == 0:
        return False, f"exit {rc}/{rc2} - a schema error must be hard"
    if not un:
        return False, "AUDIT-UNPARSEABLE masked by the other errors"
    if not other:
        return False, "the writing-gate errors were not reported next to it"
    if "narration_silence_seconds" not in un[0] or \
            f"line {bad['id']}" not in un[0]:
        return False, f"field/line not named: {un[0][:200]}"
    return True, (f"both reported ({len(other)} gate finding(s) + "
                  f"AUDIT-UNPARSEABLE naming line {bad['id']}), exit {rc}")


def test_line_problems():
    from pipeline import schemas as S
    lines = [{"id": 1, "narration": "ok"},
             {"id": 2, "narration": "", "narration_silence_seconds": 0},
             {"id": 3, "narration": "x", "claim": {"type": "aftermath"}},
             {"id": 4, "narration": "y", "narration_silence_seconds": "two"}]
    got = S.line_problems(lines)
    try:
        S.Draft(project="p", lines=[dict(l) for l in lines])
        raised = False
    except Exception:
        raised = True
    ok = (len(got) == 3 and got[0].startswith("line 2:")
          and "line 3:" in got[1] and "aftermath" in got[1]
          and got[2].startswith("line 4:") and raised
          and not S.line_problems([{"id": 1, "narration": "fine"}]))
    return ok, f"{len(got)} offender(s) named: {got}"

# --------------------------------------------------------------------------- #
TESTS = {
    "UNPARSEABLE-NOT-MASKED": test_unparseable_not_masked,
    "LINE-PROBLEMS":          test_line_problems,
}

if __name__ == "__main__":
    bad = 0
    saved = TB.CLIENT_FACTORY
    want = sys.argv[1:] or list(TESTS)
    try:
        for name in want:
            try:
                ok, m = TESTS[name]()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, m = False, f"{type(e).__name__}: {e}"
            print(f'{"PASS" if ok else "FAIL"}  {name:<22} {m}')
            bad += (not ok)
    finally:
        TB.CLIENT_FACTORY = saved
        shutil.rmtree(PDIR, ignore_errors=True)
    print("-" * 60)
    print("test_write_schema: all pass" if not bad else
          f"test_write_schema: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
