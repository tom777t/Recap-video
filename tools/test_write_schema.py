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
# the writers
# --------------------------------------------------------------------------- #
def _acts_fixture():
    """Fixture acts from the shipped project + a plan.json matching them, so
    the plan-count feedback stays quiet and only the schema is under test."""
    _setup()
    shutil.rmtree(PDIR / "draft.json.d")
    (PDIR / "draft.json").unlink()
    acts = {}
    for k in range(1, 5):
        lines = []
        for part in ("a", "b"):
            f = SRC / "draft.json.d" / f"act{k}{part}.json"
            if f.exists():
                lines += _j(f)["lines"]
        acts[k] = _schema_clean(lines)
    import write_plan as WP
    from pipeline.pacing_gates import _beat_of
    ab = WP.act_beats(PROJ, W._tool)
    cnt = {}
    for ls in acts.values():
        for ln in ls:
            if str(ln.get("narration") or "").strip() and not (
                    ln.get("over_montage") or ln.get("delivery") == "hook"):
                cnt[_beat_of(ln)] = cnt.get(_beat_of(ln), 0) + 1
    (PDIR / "plan.json").write_text(json.dumps({
        "title": "A Kid Learns to Drift", "hook": {
            "narration": "He cannot drive sideways.",
            "hook_question": "Will he learn before it costs him?"},
        "acts": [{"act": k, "word_budget": 800} for k in ab],
        "beats": [{"beat": b, "lines": cnt.get(b, 0), "footage": False,
                   "hold_after": False, "film_speaks": False, "why": "x"}
                  for k in sorted(ab) for b in ab[k]]}))
    return acts


def _poison(lines):
    out = json.loads(json.dumps(lines))
    out[3]["narration_silence_seconds"] = 0
    return out


_SAW = {}


def test_act_rejected():
    acts = _acts_fixture()
    seen = {"retry_saw_file": None}

    def bat(cid, p):
        k = int(cid[3:])
        if k == 2 and len(p["messages"]) == 1:
            return msg({"act": 2, "lines": _poison(acts[2])})
        if k == 2:
            seen["retry_saw_file"] = (PDIR / "draft.json.d/act2.json").exists()
            seen["feedback"] = p["messages"][-1]["content"]
            seen["assistant"] = p["messages"][1]["content"]
        return msg({"act": k, "lines": acts[k]})
    c = Client(None, bat)
    real = W.run_gates
    W.run_gates = lambda project: (0, [])
    try:
        rc, out = _run(c, "draft", "--project", PROJ)
    finally:
        W.run_gates = real
    _SAW["act_params"] = c.batches[0][0]["params"]
    if len(c.batches) < 2 or [r["custom_id"] for r in c.batches[1]] != ["act2"]:
        return False, (f"no in-stage retry for act2 only: "
                       f"{[[r['custom_id'] for r in b] for b in c.batches]}")
    if seen["retry_saw_file"]:
        return False, "the schema-invalid act was saved before the retry"
    fb = seen.get("feedback") or ""
    if "narration_silence_seconds must be > 0" not in fb or \
            '"narration_silence_seconds": 0' not in seen.get("assistant", ""):
        return False, f"the exact schema error / rejected reply not fed back: {fb[:200]}"
    a2 = _j(PDIR / "draft.json.d/act2.json")["lines"]
    if any(l.get("narration_silence_seconds") == 0 for l in a2):
        return False, "a 0-second hold reached act2.json"
    if rc != 0:
        return False, f"exit {rc}: {out[-300:]}"
    return True, ("act2 with narration_silence_seconds 0 not written; error "
                  "fed back in a schema round; the corrected act written")


def test_round_rejected():
    acts = _acts_fixture()
    rounds = []

    def bat(cid, p):
        k = int(cid[3:])
        u = p["messages"][0]["content"]
        if "GATE FINDINGS ON YOUR LINES" in u:
            rounds.append(u)
            return msg({"act": k, "lines": _poison(acts[k])})
        return msg({"act": k, "lines": acts[k]})
    c = Client(None, bat)
    real = W.run_gates

    def fake(project):
        owner = W.act_of_lines(PDIR)
        a2 = next(i for i, (k, _o) in owner.items() if k == 2)
        return 1, [f"[BINDING-VIOLATION] line {a2} narr too long"]
    W.run_gates = fake
    try:
        rc, out = _run(c, "draft", "--project", PROJ)
    finally:
        W.run_gates = real
    a2 = _j(PDIR / "draft.json.d/act2.json")["lines"]
    if any(l.get("narration_silence_seconds") == 0 for l in a2):
        return False, "a schema-invalid round reply was saved"
    if len(rounds) != 2 or "(schema - your last reply was NOT saved)" \
            not in rounds[1] or "must be > 0" not in rounds[1]:
        return False, f"round 2 does not carry the schema error ({len(rounds)} rounds)"
    if "NOT saved" not in out:
        return False, "the rejection was not reported"
    return True, ("round-1 reply with a 0 hold kept out; round 2 got the "
                  "schema error as feedback; previous act kept on disk")


def test_resolve_rejected():
    import test_write_plan as TWP
    TWP._resolve_fixture()
    calls = []

    def reply(cid, p):
        calls.append(p)
        fs = {ln.split(" | ")[0]: ln for ln in
              p["messages"][0]["content"].split("# OPEN FINDINGS")[1]
              .split("\n\n# ")[0].strip().splitlines()}
        key = {v.split(" | ")[2]: k for k, v in fs.items()}
        return msg({"lines": [{"id": 2, "narration": "A rewrite with a bad "
                               "hold.", "narration_silence_seconds": 0}],
                    "responses": [{"key": key["dangling-ref"],
                                   "status": "RESOLVED", "text": "fixed"}]})
    c = Client(None, reply)
    rc, out = _run(c, "resolve", "--project", TWP.PROJ)
    dr = _j(TWP.PDIR / "draft.json")
    l2 = next(l for l in dr["lines"] if str(l["id"]) == "2")
    from pipeline import review_artifacts as RA
    cr = RA.parse_artifact(TWP.PDIR / "cold_read.md")
    _SAW["resolve_params"] = calls[0] if calls else None
    shutil.rmtree(TWP.PDIR, ignore_errors=True)
    if "bad hold" in l2["narration"] or "narration_silence_seconds" in l2:
        return False, f"the invalid edit was applied: {l2}"
    if any("RESOLVED | dangling-ref" in f["raw"] for f in cr["findings"]):
        return False, "a RESOLVED rode on the rejected edit"
    if len(calls) < 2 or "NOT SAVED" not in calls[-1]["messages"][0]["content"]:
        return False, "the schema error did not go back in round 2"
    return True, ("resolve edit with a 0 hold not applied, no RESOLVED "
                  "written, the error fed back next round")


def test_request_schema():
    from pipeline import craft_gates as CG
    from pipeline import schemas as S
    p = _SAW.get("act_params")
    r = _SAW.get("resolve_params")
    if not p or not r:
        return False, "ACT-REJECTED / RESOLVE-REJECTED did not run first"
    bad = []
    for name, q, path in (("act", p, ("lines",)), ("resolve", r, ("lines",))):
        oc = q.get("output_config") or {}
        if oc.get("effort") != config.WRITE_EFFORT[name if name == "resolve"
                                                   else "draft"]:
            bad.append(f"{name}: effort lost ({oc.get('effort')!r})")
        f = oc.get("format") or {}
        if f.get("type") != "json_schema":
            bad.append(f"{name}: no json_schema format")
            continue
        it = f["schema"]["properties"]["lines"]["items"]["properties"]
        if it.get("delivery", {}).get("enum") != sorted(config.TTS_DELIVERY):
            bad.append(f"{name}: delivery enum")
        if it.get("payload", {}).get("enum") != list(CG.PAYLOAD_KINDS):
            bad.append(f"{name}: payload enum")
        if name == "act":
            # a slot-based act reply carries no hold (code writes them); the
            # bounds are checked on the line schema the legacy path sends
            if "slot" not in f["schema"]["properties"]["lines"]["items"][
                    "required"]:
                bad.append("act: slot request does not require `slot`")
            it = W.act_schema()["properties"]["lines"]["items"]["properties"]
        ns = it.get("narration_silence_seconds") or {}
        if ns.get("exclusiveMinimum") != 0 or ns.get("maximum") != 30:
            bad.append(f"{name}: narration_silence_seconds bounds {ns}")
    it = p["output_config"]["format"]["schema"]["properties"]["lines"]["items"]
    ct = it["properties"]["claim"]["properties"]["type"]["enum"]
    if ct != sorted(S._CLAIM_TYPES):
        bad.append("act: claim.type enum")
    if it.get("additionalProperties") is not False:
        bad.append("act: line items accept unknown fields")
    return (not bad), ("act + resolve requests: json_schema with delivery / "
                       "payload / claim.type enums and > 0 bounds, effort kept"
                       if not bad else "; ".join(bad))


# --------------------------------------------------------------------------- #
TESTS = {
    "UNPARSEABLE-NOT-MASKED": test_unparseable_not_masked,
    "LINE-PROBLEMS":          test_line_problems,
    "ACT-REJECTED":           test_act_rejected,
    "ROUND-REJECTED":         test_round_rejected,
    "RESOLVE-REJECTED":       test_resolve_rejected,
    "REQUEST-SCHEMA":         test_request_schema,
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
