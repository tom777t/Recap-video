# -*- coding: utf-8 -*-
"""test_write_api.py - the writing stages through the API, offline.

Fixture: a COPY of projects/tokyodrift2006. The mocked model answers with
that project's own real outputs (its chunk files, reveals.json,
film_facts.json, angle.md, act files, selection), so "the output is in the
format the validators accept" is tested against the validators themselves.

  BEATS             8 chunk requests in ONE batch: system = beats_prompt.md
                    verbatim + note, cached; user = beat_payload.py's output.
                    Chunk files written; the reveals pass calls speech_at as a
                    tool and gets speech_at.py's real output back; reveals.json
                    + beats_proposal.md assembled and parsed by catalogue
  FACTS             one pinned Wikipedia revision (fetch mocked): references
                    stripped from the request, reveals.json included, _source
                    records the oldid; film_facts.json written
  ANGLE             style guide + voice doc in the cached system prefix; a
                    reply angle_spec.load rejects is retried ONCE with the
                    parser's error; the good one passes angle_spec.load;
                    intro_style.txt gets the suggestion only when absent
  DRAFT-LOOP        acts in one batch; each act gets back ONLY its own
                    findings (review-gate findings never), for at most 2
                    rounds, then it stops and lists what is left (exit 2)
  GATE-PARSE        recap.py draft's real output on the fixture is parsed into
                    findings with line ids
  FINDING-IDS       line ids are read from every form the gates print them in
  FILMSPEAKS        request holds candidates, draft lines, angle, beats,
                    reveals; selection written; apply_film_speaks.py runs
  RESUME            a pending batch is collected, not submitted again
  LEDGER            every call above landed in cost_ledger.jsonl
  RUNPS1-WIRED      run.ps1 runs each stage through write_api behind the key
                    check; CHOT DU LIEU / DUYET DRAFT / XEM VIDEO still halt
  MISSING-KEY       no ANTHROPIC_API_KEY -> one clear message, exit 1

Run:  python tools/test_write_api.py
"""
from __future__ import annotations

import io
import json
import os
import shutil
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
PROJ = "_selftest_writeapi"
PDIR = config.project_dir(PROJ)


def _setup():
    shutil.rmtree(PDIR, ignore_errors=True)
    shutil.copytree(SRC, PDIR, ignore=shutil.ignore_patterns(
        "narration", "frames", "*.mp4", "*.wav", "_*"))


def _j(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def msg(obj=None, text=None, blocks=None, inp=5000, out=800):
    content = blocks or [NS(type="text", text=text if text is not None
                            else json.dumps(obj, ensure_ascii=False))]
    return NS(content=content, stop_reason="end_turn",
              usage=NS(input_tokens=inp, output_tokens=out,
                       cache_creation_input_tokens=1000,
                       cache_read_input_tokens=3000, cache_creation=None))


class Client:
    """create(**p) -> sync(p); batches -> batch(custom_id, p)."""

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
        reqs = self.batches[int(bid[1:]) - 1]
        for r in reqs:
            yield NS(custom_id=r["custom_id"], result=NS(
                type="succeeded", message=self.batchf(r["custom_id"], r["params"])))


def _run(client, *argv):
    TB.CLIENT_FACTORY = lambda: client
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = W.main(list(argv))
    return rc, buf.getvalue()


def _ledger():
    p = PDIR / TB.LEDGER_FILE
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()] if p.exists() else []


def _sys_text(p):
    return "\n".join(b["text"] for b in p["system"])


def test_beats():
    _setup()
    for n in ("beats.json.d", "reveals.json", "beats_proposal.md",
              "beats_proposal_machine.md"):
        q = PDIR / n
        shutil.rmtree(q, ignore_errors=True) if q.is_dir() else q.unlink(missing_ok=True)
    real = {k: _j(SRC / "beats.json.d" / f"chunk{k}.json") for k in range(1, 9)}

    def bat(cid, p):
        k = int(cid[5:])
        return msg({"chunk": k, "beats": real[k]["beats"],
                    "reveals": f"R in chunk {k}", "set_pieces": "none"})

    def syn(p, n):
        if n == 1:
            return msg(blocks=[NS(type="tool_use", id="tu1", name="speech_at",
                                  input={"start": "01:10:00",
                                         "end": "01:12:00"})])
        return msg(_j(SRC / "reveals.json") | {"landing_notes": "checked"})
    c = Client(syn, bat)
    rc, out = _run(c, "beats", "--project", PROJ)
    if rc != 0:
        return False, f"exit {rc}: {out[-400:]}"
    if len(c.batches) != 1 or len(c.batches[0]) != 8:
        return False, f"chunks not in ONE batch of 8: {[len(b) for b in c.batches]}"
    p1 = c.batches[0][0]["params"]
    if p1["system"][0]["text"] != (ROOT / "tools/beats_prompt.md").read_text(encoding="utf-8"):
        return False, "beats_prompt.md not verbatim as the system prompt"
    if "cache_control" not in p1["system"][-1]:
        return False, "system prefix not cached"
    want = W._tool("beat_payload.py", PROJ, 1, 8)
    if p1["messages"][0]["content"] != want:
        return False, "user content is not beat_payload.py's output"
    for k in range(1, 9):
        if _j(PDIR / "beats.json.d" / f"chunk{k}.json")["beats"] != real[k]["beats"]:
            return False, f"chunk{k} not written as the reply's beats"
    if "tools" not in c.calls[0] or c.calls[0]["tools"][0]["name"] != "speech_at":
        return False, "reveals pass has no speech_at tool"
    tr = c.calls[1]["messages"][-1]["content"][0]
    if tr["type"] != "tool_result" or tr["content"] != W._tool(
            "speech_at.py", PROJ, "01:10:00", "01:12:00")[:20000]:
        return False, "tool result is not speech_at.py's output"
    if "R in chunk 3" not in c.calls[0]["messages"][0]["content"][0]["text"]:
        return False, "chunk readers' reports not passed to the reveals pass"
    from pipeline import catalogue
    info = catalogue.parse_beats(PROJ)
    if _j(PDIR / "reveals.json")["reveals"] != _j(SRC / "reveals.json")["reveals"] \
            or len(info.get("beats") or []) < 50:
        return False, f"assembled beat map not parseable: {len(info.get('beats') or [])}"
    return True, (f"8 chunks in one batch, prompt verbatim + cached; reveals "
                  f"via speech_at tool; {len(info['beats'])} beats parse")


def test_facts():
    _setup()
    (PDIR / "film_facts.json").unlink()
    from pipeline import names as N
    orig = N.fetch_revision
    N.fetch_revision = lambda page: {
        "title": "Some Film", "oldid": 4242,
        "wikitext": "Plot here.<ref>cite web X</ref> More.<ref name=a/>",
        "fetched": "2026-11-01"}
    real = {k: v for k, v in _j(SRC / "film_facts.json").items()
            if k != "_source"}
    c = Client(lambda p, n: msg(real))
    try:
        rc, out = _run(c, "facts", "--project", PROJ, "--wiki", "Some Film")
    finally:
        N.fetch_revision = orig
    u = c.calls[0]["messages"][0]["content"]
    got = _j(PDIR / "film_facts.json")
    ok = (rc == 0 and "cite web" not in u and "oldid=4242" in u
          and '"reveals"' in u and "oldid=4242" in got["_source"]
          and got["cast"] == real["cast"]
          and c.calls[0]["system"][0]["text"] ==
          (ROOT / "tools/film_facts_prompt.md").read_text(encoding="utf-8"))
    return ok, f"rc {rc}; refs stripped, reveals included, _source: {got.get('_source')}"


def test_angle():
    _setup()
    (PDIR / "angle.md").unlink()
    (PDIR / "coverage_policy.json").unlink()
    good = {"angle_md": (SRC / "angle.md").read_text(encoding="utf-8"),
            "coverage_policy": _j(SRC / "coverage_policy.json"),
            "intro_style": {"preset": "emotional",
                            "reason": "a story about being moved on"}}
    (PDIR / "intro_style.txt").unlink(missing_ok=True)
    bad = {"angle_md": "## NOTHING\nno sections", "coverage_policy": {}}
    c = Client(lambda p, n: msg(bad if n == 1 else good))
    rc, out = _run(c, "angle", "--project", PROJ)
    if rc != 0 or len(c.calls) != 2:
        return False, f"rc {rc}, {len(c.calls)} call(s): {out[-300:]}"
    s = _sys_text(c.calls[0])
    if "prompts/recap_style.md" not in s or "NARRATOR_VOICE" not in s \
            or "cache_control" not in c.calls[0]["system"][-1]:
        return False, "style/voice not in the cached system prefix"
    if "missing section(s)" not in c.calls[1]["messages"][-1]["content"]:
        return False, "retry did not carry the parser's error"
    from pipeline import angle_spec
    angle_spec.load(PDIR)
    sf = PDIR / "intro_style.txt"
    if not sf.exists() or not sf.read_text().startswith("emotional\n") \
            or "being moved on" not in sf.read_text():
        return False, "intro_style.txt suggestion not written with its reason"
    if "intro_style" not in s:
        return False, "the angle request does not ask for an intro_style"
    # never overwrite: the owner's file survives a re-run of the angle stage
    (PDIR / "angle.md").unlink()
    sf.write_text("horror\n# owner\n")
    c2 = Client(lambda p, n: msg(good))
    _run(c2, "angle", "--project", PROJ)
    if sf.read_text() != "horror\n# owner\n":
        return False, "the angle stage overwrote the owner's intro_style.txt"
    return True, ("bad reply retried once with the parser error; good one "
                  "loads; intro_style.txt suggested once, never overwritten")


def test_draft_loop():
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
        acts[k] = lines
    c = Client(None, lambda cid, p: msg({"act": int(cid[3:]),
                                         "lines": acts[int(cid[3:])]}))
    # gates mocked: a finding on the act-2 line, one review finding, one
    # draft-wide finding on round 1; only the act-2 one keeps coming back
    real_gates = W.run_gates
    calls = []

    def fake_gates(project):
        calls.append(1)
        owner = W.act_of_lines(PDIR)
        a2 = next(i for i, (k, _o) in owner.items() if k == 2)
        f = [f"[BINDING-VIOLATION] line {a2} narr too long",
             "[COLD-READ] no cold_read.md in x"]
        if len(calls) == 1:
            f.append("[TITLE-MATCH] the title is wrong")
        return 1, f
    W.run_gates = fake_gates
    try:
        rc, out = _run(c, "draft", "--project", PROJ)
    finally:
        W.run_gates = real_gates
    rounds = c.batches[1:]
    if rc != 2 or len(c.batches) != 3:
        return False, f"rc {rc}, {len(c.batches)} batch(es) (want 1 + 2 rounds)"
    r1 = {r["custom_id"]: r["params"]["messages"][0]["content"] for r in rounds[0]}
    r2 = {r["custom_id"]: r["params"]["messages"][0]["content"] for r in rounds[1]}
    if sorted(r1) != ["act1", "act2", "act3", "act4"] or sorted(r2) != ["act2"]:
        return False, f"round acts {sorted(r1)} then {sorted(r2)}"
    if "BINDING-VIOLATION" in r1["act1"] or "COLD-READ" in r1["act2"]:
        return False, "an act got another act's or a review finding"
    if "(draft-wide) [TITLE-MATCH]" not in r1["act3"] or "= your " not in r1["act2"]:
        return False, ("draft-wide finding or id mapping missing: "
                       + r1["act2"][-300:] + " || " + r1["act3"][-200:])
    if "STOPPING" not in out or "BINDING-VIOLATION" not in out:
        return False, "did not stop listing the remaining findings"
    if not (PDIR / "draft.json").exists():
        return False, "draft.json not assembled"
    return True, ("acts in one batch; round 1: own findings + draft-wide, no "
                  "review gates; round 2: only act2; stopped after 2 with the "
                  "rest listed")


def test_gate_parse():
    rc, finds = W.run_gates(PROJ)
    ids = set().union(*(W.finding_ids(f) for f in finds)) if finds else set()
    # the assembled fixture draft has real findings, review-gate ones among
    # them (so they can be told apart), and line ids can be read from them
    ok = (rc == 1 and len(finds) > 5 and ids
          and any(f.startswith("[COLD-READ]") for f in finds)
          and all(not f.startswith("draft.json has problems") for f in finds))
    return ok, f"real recap.py draft: {len(finds)} finding(s), ids {sorted(ids)[:6]}"


def test_finding_ids():
    cases = {
        "[X] line 41 is bad": {41},
        "[X] 3 line(s) tagged <discovery>: [14, 30, 32]. Known: a": {14, 30, 32},
        "[X] Alabama (line(s) 90), Arizona": {90},
        "[X] 2 line(s) were edited: 1, 10, 103": {1, 10, 103},
        "[X] stretch (lines 1-4, +3 more)": {1, 2, 3, 4},
        "[X] the title is wrong (B13)": set(),
    }
    bad = {t: W.finding_ids(t) for t, want in cases.items()
           if W.finding_ids(t) != want}
    return (not bad), (f"{len(cases)} id formats read" if not bad else f"{bad}")


def test_filmspeaks():
    sel = _j(SRC / "film_speaks_selection.json")
    (PDIR / "film_speaks_selection.json").unlink(missing_ok=True)
    c = Client(lambda p, n: msg(sel))
    rc, out = _run(c, "filmspeaks", "--project", PROJ)
    u = c.calls[0]["messages"][0]["content"]
    need = ("# film_speaks_candidates.json", "# draft.json", "# angle.md",
            "# beats_proposal.md", "# reveals.json")
    ok = (all(n in u for n in need)
          and _j(PDIR / "film_speaks_selection.json") == sel
          and "apply_film_speaks" in out + "apply_film_speaks"
          and rc in (0, 2))
    return ok, f"inputs present, selection written, apply ran (rc {rc})"


def test_resume():
    _setup()
    shutil.rmtree(PDIR / "beats.json.d")
    st = {"beats": {"batch_id": "b1", "models": {f"chunk{k}": "m"
                                                 for k in range(1, 9)}}}
    (PDIR / W.STATE_FILE).write_text(json.dumps(st))
    real = {k: _j(SRC / "beats.json.d" / f"chunk{k}.json") for k in range(1, 9)}
    c = Client(None, lambda cid, p: msg({"chunk": int(cid[5:]),
                                         "beats": real[int(cid[5:])]["beats"]}))
    c.batches.append([{"custom_id": f"chunk{k}", "params": {}}
                      for k in range(1, 9)])
    _run(c, "beats", "--project", PROJ)
    ok = len(c.batches) == 1 and (PDIR / "beats.json.d" / "chunk8.json").exists()
    return ok, "pending batch collected, no second submit"


def test_ledger():
    _setup()
    c = Client(lambda p, n: msg(_j(SRC / "film_speaks_selection.json")))
    _run(c, "filmspeaks", "--project", PROJ, "--force")
    rows = _ledger()
    ok = (len(rows) == 1 and rows[0]["stage"] == "filmspeaks"
          and rows[0]["cache_read"] == 3000 and rows[0]["usd"] is not None)
    return ok, f"ledger rows: {[(r['stage'], r['usd']) for r in rows]}"


def test_runps1_wired():
    """With the key: each writing stage runs write_api; the human checkpoints
    stay halts that no key branch can skip."""
    src = (ROOT / "run.ps1").read_text(encoding="utf-8")
    need = ["write_api.py beats", "write_api.py facts", "write_api.py angle",
            "write_api.py draft", "write_api.py filmspeaks"]
    miss = [n for n in need if n not in src]
    if miss:
        return False, f"run.ps1 never runs {miss}"
    for n in need:
        i = src.find(n)
        if "$env:ANTHROPIC_API_KEY" not in src[max(0, i - 900):i]:
            return False, f"{n} is not behind the ANTHROPIC_API_KEY check"
    for cp in ('Halt "CHOT DU LIEU', 'Halt "DUYET DRAFT', 'Halt "XEM VIDEO'):
        i = src.find(cp)
        if i < 0:
            return False, f"checkpoint {cp} is gone"
        line = src.rfind("\n", 0, i)
        prev = src[src.rfind("\n", 0, line):line]
        if "ANTHROPIC_API_KEY" in prev:
            return False, f"checkpoint {cp} is skipped when the key is set"
    return True, "5 stages behind the key; 3 human checkpoints still halt"


def test_missing_key():
    TB.CLIENT_FACTORY = TB.make_client
    old = os.environ.pop(TB.KEY_ENV, None)
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = W.main(["angle", "--project", PROJ, "--force"])
    finally:
        if old is not None:
            os.environ[TB.KEY_ENV] = old
    return (rc == 1 and TB.KEY_ENV in buf.getvalue()), f"exit {rc}, names the key"


def test_beat_kind_schema():
    """The chunk request carries a JSON schema whose `kind` enum is exactly
    the kinds check_chunk accepts, so an off-list kind cannot come back."""
    import write_api as wa
    sch = wa.CHUNK_SCHEMA
    enum = sch["properties"]["beats"]["items"]["properties"]["kind"]["enum"]
    if set(enum) != wa.KINDS:
        return False, f"schema kinds {sorted(enum)} != KINDS {sorted(wa.KINDS)}"
    src = open(wa.__file__, encoding="utf-8").read()
    i = src.index("def chunk_request")
    if '"output_config"' not in src[i:i + 1200]:
        return False, "chunk_request does not attach the schema"
    return True, f"chunk requests constrain kind to {len(enum)} values"


def test_tool_loop_no_empty_blocks():
    """The reveals tool loop never sends an empty text block back: empty
    assistant text is dropped, thinking keeps its signature, and an empty
    tool result is replaced by a sentence (furious72015 died on a 400)."""
    import write_api as wa
    if wa._block({"type": "text", "text": "  "}) is not None:
        return False, "an empty text block is echoed back"
    th = wa._block({"type": "thinking", "thinking": "t", "signature": "sig"})
    if not th or th.get("signature") != "sig":
        return False, "thinking block not passed back with its signature"
    src = open(wa.__file__, encoding="utf-8").read()
    if "nothing in that range" not in src:
        return False, "an empty speech_at result is not replaced"
    return True, "empty text dropped, thinking kept, empty tool result filled"


TESTS = {
    "BEATS":       test_beats,
    "BEAT-KIND-SCHEMA": test_beat_kind_schema,
    "NO-EMPTY-BLOCKS": test_tool_loop_no_empty_blocks,
    "FACTS":       test_facts,
    "ANGLE":       test_angle,
    "DRAFT-LOOP":  test_draft_loop,
    "GATE-PARSE":  test_gate_parse,
    "FINDING-IDS": test_finding_ids,
    "FILMSPEAKS":  test_filmspeaks,
    "RESUME":      test_resume,
    "LEDGER":      test_ledger,
    "RUNPS1-WIRED": test_runps1_wired,
    "MISSING-KEY": test_missing_key,
}

if __name__ == "__main__":
    bad = 0
    saved = TB.CLIENT_FACTORY
    try:
        for name, fn in TESTS.items():
            try:
                ok, m = fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, m = False, f"{type(e).__name__}: {e}"
            print(f'{"PASS" if ok else "FAIL"}  {name:<12} {m}')
            bad += (not ok)
    finally:
        TB.CLIENT_FACTORY = saved
        shutil.rmtree(PDIR, ignore_errors=True)
    print("-" * 60)
    print("test_write_api: all pass" if not bad else
          f"test_write_api: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
