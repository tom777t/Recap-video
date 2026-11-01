# -*- coding: utf-8 -*-
"""test_review_api.py - the three API review readers, offline (client mocked).

  CLEAN-PASSES        readers with no findings -> cold_read.md, review.md and
                      ending_read.md parse and pass [COLD-READ], [REVIEWER]
                      and [ENDING-READ]
  FINDINGS-FAIL       readers with findings -> the gates FAIL on open findings
  COLD-SEES-PAYLOAD   the cold read's request holds the narration payload and
                      the checklist ONLY: no beats, angle, delivery, payload
                      label, hook question or beat note
  ENDING-SEES-WINDOW  the ending read's request holds only the closing
                      window's lines
  REVIEWER-INPUTS     the reviewer gets the fixed checklist and the cold
                      read's findings, in its own fresh request
  FOREIGN-IDS         a finding citing a line the reader was not shown loses
                      that id and the artifact says so
  EXISTING-KEPT       an existing artifact is not re-read or overwritten
  BAD-REPLY           a non-JSON reply writes nothing, exit 2
  MISSING-KEY         no ANTHROPIC_API_KEY -> one clear message, exit 1

Run:  python tools/test_review_api.py
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
import review_api as RV  # noqa: E402
import tag_batch as TB  # noqa: E402
from pipeline import ending_gates as EG  # noqa: E402
from pipeline import review_artifacts as RA  # noqa: E402

PROJ = "_selftest_reviewapi"
PDIR = config.project_dir(PROJ)
BEAT_SENTINEL = "ZZBEATSECRET"
ANGLE_SENTINEL = "ZZANGLESECRET"


def _draft() -> dict:
    lines = []
    for i in range(1, 11):
        lines.append({"id": i, "note": f"B{i:02d} QQNOTE{i}",
                      "delivery": "QQDELIVERY", "payload": "QQPAYLOAD",
                      "hook_question": "QQHOOK" if i == 1 else None,
                      "clip_start": f"00:0{i // 6}:{(i * 7) % 60:02d}.000",
                      "clip_end": f"00:0{i // 6}:{(i * 7) % 60 + 5:02d}.000",
                      "narration": f"Narration sentence number {i} about Kai."})
    lines.insert(4, {"id": 50, "note": "B05", "narration": "",
                     "narration_silence_seconds": 2.0})
    return {"title": "Selftest Film", "lines": lines}


def _setup() -> dict:
    shutil.rmtree(PDIR, ignore_errors=True)
    PDIR.mkdir(parents=True)
    d = _draft()
    (PDIR / "draft.json").write_text(json.dumps(d), encoding="utf-8")
    (PDIR / "beats_proposal.md").write_text(
        f"B01 | the film | {BEAT_SENTINEL}\n", encoding="utf-8")
    (PDIR / "angle.md").write_text(f"## ANGLE\n{ANGLE_SENTINEL}\n",
                                   encoding="utf-8")
    return d


def _msg(obj, stop="end_turn"):
    text = obj if isinstance(obj, str) else json.dumps(obj)
    return NS(content=[NS(type="text", text=text)], stop_reason=stop,
              usage=NS(input_tokens=1000, output_tokens=200,
                       cache_creation_input_tokens=0,
                       cache_read_input_tokens=0, cache_creation=None))


class Client:
    """Records each request; replies per stage from `replies`."""

    def __init__(self, replies: dict):
        self.replies, self.calls = replies, []
        self.messages = NS(create=self._create)

    def _create(self, **params):
        self.calls.append(params)
        sysx = params["system"][0]["text"]
        stage = ("review" if "INDEPENDENT REVIEWER" in sysx else
                 "ending-read" if "closing lines" in sysx else "cold-read")
        return _msg(self.replies.get(stage, {"checked": "x", "findings": []}))

    def text(self, i):
        p = self.calls[i]
        return p["system"][0]["text"] + "\n" + p["messages"][0]["content"]


def _run(client, *argv) -> tuple:
    TB.CLIENT_FACTORY = lambda: client
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = RV.main(list(argv))
    return rc, buf.getvalue()


def _gate_errors(draft):
    rr = RA.review_report(draft, PDIR)
    er = EG.ending_report(draft, PDIR)
    cold = [e for e in rr["errors"] if e.startswith("[COLD-READ]")]
    rev = [e for e in rr["errors"] if e.startswith("[REVIEWER]")]
    end = [e for e in er["errors"] if e.startswith("[ENDING-READ]")]
    return cold, rev, end


CLEAN = {"checked": "every line, once", "findings": []}


def test_clean_passes():
    d = _setup()
    rc, out = _run(Client({}), "all", "--project", PROJ)
    if rc != 0:
        return False, f"exit {rc}: {out[-300:]}"
    cold, rev, end = _gate_errors(d)
    if cold or rev or end:
        return False, f"gates not clean: {(cold + rev + end)[:2]}"
    return True, "three artifacts written; COLD-READ, REVIEWER, ENDING-READ pass"


def test_findings_fail():
    d = _setup()
    f = {"checked": "x", "findings": [
        {"kind": "Ambiguous Pronoun", "ids": [3], "text": "he | could be two men"}]}
    rc, out = _run(Client({"cold-read": f, "review": f, "ending-read":
                           {"checked": "x", "findings": [
                               {"kind": "ending", "ids": [10],
                                "text": "it trails off"}]}}),
                   "all", "--project", PROJ)
    if rc != 0:
        return False, f"exit {rc}"
    cold, rev, end = _gate_errors(d)
    if not (cold and rev and end):
        return False, f"open findings did not fail: {len(cold)},{len(rev)},{len(end)}"
    if not all("UNRESOLVED" in " ".join(x).upper() for x in (cold, rev, end)):
        return False, f"failed, but not for the open findings: {cold[:1]}"
    art = RA.parse_artifact(PDIR / "cold_read.md")
    if art["errors"] or art["findings"][0]["kind"] != "ambiguous-pronoun":
        return False, f"finding not written cleanly: {art}"
    return True, "open findings fail all three gates; '|' in text is escaped"


def test_cold_sees_payload():
    _setup()
    c = Client({})
    _run(c, "cold-read", "--project", PROJ)
    t = c.text(0)
    leaks = [s for s in (BEAT_SENTINEL, ANGLE_SENTINEL, "QQDELIVERY",
                         "QQPAYLOAD", "QQHOOK", "QQNOTE") if s in t]
    if leaks:
        return False, f"cold read saw {leaks}"
    if "Narration sentence number 7" not in t or "[pause]" not in t:
        return False, "cold read did not get the narration payload"
    if "UNINTRODUCED REFERENT" not in t:
        return False, "cold read did not get the checklist"
    return True, "narration + checklist only; no beats/angle/labels/notes"


def test_ending_sees_window():
    d = _setup()
    c = Client({})
    _run(c, "ending-read", "--project", PROJ)
    t = c.text(0)
    win = RV.window_ids(d)
    shown = [i for i in range(1, 11) if f"number {i} about" in t]
    if shown != win or len(win) != int(config.ENDING_WINDOW_LINES):
        return False, f"ending read saw lines {shown}, window {win}"
    if any(s in t for s in (BEAT_SENTINEL, ANGLE_SENTINEL, "QQNOTE")):
        return False, "ending read saw beats/angle/notes"
    return True, f"ending read saw only the window {win}"


def test_reviewer_inputs():
    _setup()
    cf = {"checked": "x", "findings": [
        {"kind": "dangling-ref", "ids": [4], "text": "ZZCOLDFINDING here"}]}
    c = Client({"cold-read": cf})
    _run(c, "all", "--project", PROJ)
    if len(c.calls) != 3 or any(len(p["messages"]) != 1 for p in c.calls):
        return False, "readers did not each get one fresh single-turn request"
    t = c.text(1)
    if "INDEPENDENT REVIEWER" not in t or "PEAKS TALKED OVER" not in t:
        return False, "reviewer did not get the fixed checklist"
    if "ZZCOLDFINDING" not in t:
        return False, "reviewer did not get the cold read's findings"
    if "ZZCOLDFINDING" in c.text(2):
        return False, "the ending read saw the cold read's findings"
    return True, "fixed checklist + cold findings, in a fresh request"


def test_foreign_ids():
    _setup()
    f = {"checked": "x", "findings": [
        {"kind": "callback", "ids": [2, 10], "text": "points nowhere"}]}
    _run(Client({"ending-read": f}), "ending-read", "--project", PROJ)
    art = RA.parse_artifact(PDIR / "ending_read.md")
    txt = (PDIR / "ending_read.md").read_text(encoding="utf-8")
    if art["findings"][0]["ids"] != ["10"] or "not shown" not in txt:
        return False, f"foreign id not dropped/reported: {art['findings']}"
    return True, "id 2 (not shown to the ending reader) dropped and noted"


def test_existing_kept():
    _setup()
    (PDIR / "cold_read.md").write_text("HAND WRITTEN", encoding="utf-8")
    c = Client({})
    rc, out = _run(c, "cold-read", "--project", PROJ)
    kept = (PDIR / "cold_read.md").read_text(encoding="utf-8") == "HAND WRITTEN"
    return (rc == 0 and kept and not c.calls), "existing artifact kept, no API call"


def test_bad_reply():
    _setup()
    rc, out = _run(Client({"cold-read": "I think the draft is fine."}),
                   "cold-read", "--project", PROJ)
    ok = rc == 2 and not (PDIR / "cold_read.md").exists()
    return ok, f"non-JSON reply -> exit {rc}, nothing written"


def test_missing_key():
    _setup()
    TB.CLIENT_FACTORY = TB.make_client
    old = os.environ.pop(TB.KEY_ENV, None)
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = RV.main(["cold-read", "--project", PROJ])
    finally:
        if old is not None:
            os.environ[TB.KEY_ENV] = old
    ok = rc == 1 and TB.KEY_ENV in buf.getvalue()
    return ok, f"no key -> exit {rc}, message names {TB.KEY_ENV}"


TESTS = {
    "CLEAN-PASSES":       test_clean_passes,
    "FINDINGS-FAIL":      test_findings_fail,
    "COLD-SEES-PAYLOAD":  test_cold_sees_payload,
    "ENDING-SEES-WINDOW": test_ending_sees_window,
    "REVIEWER-INPUTS":    test_reviewer_inputs,
    "FOREIGN-IDS":        test_foreign_ids,
    "EXISTING-KEPT":      test_existing_kept,
    "BAD-REPLY":          test_bad_reply,
    "MISSING-KEY":        test_missing_key,
}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    bad = 0
    try:
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
            print(f'{"PASS" if ok else "FAIL"}  {name:<20} {msg}')
            bad += (not ok)
    finally:
        shutil.rmtree(PDIR, ignore_errors=True)
    print("-" * 60)
    print("test_review_api: all pass" if not bad else
          f"test_review_api: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
