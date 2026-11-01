# -*- coding: utf-8 -*-
"""test_cost_ledger.py - every API call lands in cost_ledger.jsonl; the report.

  LEDGER-ROW        one row per call: stage, model, input/output/cache tokens,
                    batch flag, USD at PRICES (batch half price); an unlisted
                    model gets usd null, never an invented price
  TAG-BATCH-CALLS   tag_batch's synchronous call and its batch collection
                    append rows (stage "tags")
  REVIEW-CALLS      review_api appends one row per reader ("review:<stage>")
  PICTURE-CALLS     picture_check appends one row per result (batch)
  REPORT            cost_report.md: per stage, per model, total, unpriced
                    flagged, an unreadable row counted, Inworld characters
                    from the narration manifest

Run:  python tools/test_cost_ledger.py
"""
from __future__ import annotations

import io
import json
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
import cost_report as CR  # noqa: E402

PROJ = "_selftest_costledger"
PDIR = config.project_dir(PROJ)


def _fresh():
    shutil.rmtree(PDIR, ignore_errors=True)
    PDIR.mkdir(parents=True)


def _rows():
    p = PDIR / TB.LEDGER_FILE
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()] if p.exists() else []


def _msg(obj, inp=1000, out=200, cw=0, cr=0):
    return NS(content=[NS(type="text", text=json.dumps(obj))],
              stop_reason="end_turn",
              usage=NS(input_tokens=inp, output_tokens=out,
                       cache_creation_input_tokens=cw,
                       cache_read_input_tokens=cr, cache_creation=None))


def test_ledger_row():
    _fresh()
    u = {"in": 1_000_000, "out": 100_000, "cw": 0, "cr": 0, "cw1h": 0}
    TB.ledger_append(PDIR, "beats", "claude-haiku-5-5", u, batch=True)
    TB.ledger_append(PDIR, "draft", "claude-unlisted-9", u)
    r = _rows()
    want = TB.cost_usd("claude-haiku-5-5", u, batch=True)
    keys = {"at", "stage", "model", "input", "output", "cache_write",
            "cache_read", "batch", "usd"}
    if len(r) != 2 or not keys <= set(r[0]):
        return False, f"rows {r}"
    if abs(r[0]["usd"] - want) > 1e-9 or r[0]["batch"] is not True:
        return False, f"usd {r[0]['usd']} vs {want}"
    if r[1]["usd"] is not None:
        return False, "an unlisted model got an invented price"
    return True, f"row has every field; batch usd {want:.4f}; unlisted -> null"


def test_tag_batch_calls():
    _fresh()
    real = TB.build_params
    TB.build_params = lambda *a, **k: {}
    try:
        client = NS(messages=NS(create=lambda **p: _msg({"x": 1})))
        TB.tag_sync(client, PDIR, {"id": "sp01", "shots": []}, [],
                    "claude-haiku-5-5")
    finally:
        TB.build_params = real
    r = _rows()
    ok = len(r) == 1 and r[0]["stage"] == "tags" and r[0]["note"] == "sp01"
    return ok, f"tag_sync -> {[(x['stage'], x.get('note')) for x in r]}"


def test_review_calls():
    _fresh()
    import review_api as RV
    d = {"title": "T", "lines": [{"id": i, "narration": f"Line {i} text."}
                                 for i in range(1, 7)]}
    (PDIR / "draft.json").write_text(json.dumps(d), encoding="utf-8")
    client = NS(messages=NS(create=lambda **p: _msg(
        {"checked": "all", "findings": []}, inp=4000, out=300)))
    with redirect_stdout(io.StringIO()):
        RV.run_stage("cold-read", PROJ, client=client)
        RV.run_stage("ending-read", PROJ, client=client)
    st = [x["stage"] for x in _rows()]
    ok = st == ["review:cold-read", "review:ending-read"]
    return ok, f"review_api -> {st}"


def test_picture_calls():
    _fresh()
    import picture_check as PCT
    (PDIR / "final.mp4").write_bytes(b"x" * 100)
    (PDIR / "timeline.json").write_text(json.dumps(
        {"intro_offset": 0, "lines": [
            {"id": 1, "out_start": 1.0, "out_end": 3.0,
             "clip_start": "00:00:01.000", "clip_end": "00:00:03.000"},
            {"id": 2, "out_start": 3.0, "out_end": 5.0,
             "clip_start": "00:00:05.000", "clip_end": "00:00:07.000"}]}),
        encoding="utf-8")
    tg = PCT.target(PROJ)
    tg["state"].write_text(json.dumps({
        "batch_id": "b1", "model": "claude-haiku-5-5",
        "final": PCT._sig(tg["final"]), "status": "submitted",
        "lines": {"line-1": {"id": 1, "at": 1.0}, "line-2": {"id": 2, "at": 3.0}}}))
    items = [NS(custom_id=c, result=NS(type="succeeded", message=_msg(
        {"verdict": "fits", "reason": "ok", "frames": [True] * 5})))
        for c in ("line-1", "line-2")]
    client = NS(messages=NS(batches=NS(
        retrieve=lambda b: NS(processing_status="ended"),
        results=lambda b: iter(items))))
    PCT.fetch(PROJ, tg, client, wait=False, poll=1)
    r = _rows()
    ok = len(r) == 2 and all(x["stage"] == "picture_check" and x["batch"]
                             for x in r)
    return ok, f"picture_check -> {len(r)} batch row(s)"


def test_report():
    _fresh()
    for stage, model, n in (("beats", "claude-haiku-5-5", 8),
                            ("draft", "claude-sonnet-5-5", 4),
                            ("draft", "claude-opus-9-9", 1)):
        for _ in range(n):
            TB.ledger_append(PDIR, stage, model,
                             {"in": 10000, "out": 2000, "cw": 0, "cr": 5000},
                             batch=(stage == "beats"))
    with open(PDIR / TB.LEDGER_FILE, "a", encoding="utf-8") as fh:
        fh.write("{not json\n")
    (PDIR / "narration").mkdir()
    (PDIR / "narration" / "_cache.json").write_text(
        json.dumps({"line_001.mp3": "a", "line_002.mp3": "b"}))
    (PDIR / "draft.json").write_text(json.dumps({"lines": [
        {"id": 1, "narration": "abcde"}, {"id": 2, "narration": "fghij"},
        {"id": 3, "narration": "not synthesised"}]}))
    with redirect_stdout(io.StringIO()):
        out, rows, bad = CR.build(PROJ)
    md = out.read_text(encoding="utf-8")
    exp = sum(TB.cost_usd(m, {"in": 10000, "out": 2000, "cw": 0, "cr": 5000},
                          batch=(s == "beats")) or 0.0
              for s, m, n in (("beats", "claude-haiku-5-5", 8),
                              ("draft", "claude-sonnet-5-5", 4))
              for _ in range(n))
    checks = [("| beats | 8 |" in md, "beats row"),
              ("| claude-sonnet-5-5 | 4 |" in md, "model row"),
              (f"${exp:.4f}" in md, f"total ${exp:.4f}"),
              ("INCOMPLETE" in md and "+1 unpriced" in md, "unpriced flagged"),
              ("1 ledger row(s) could not be read" in md, "bad row counted"),
              ("10 characters of narration over 2 line(s)" in md, "TTS chars")]
    miss = [w for ok, w in checks if not ok]
    return (not miss), ("per stage, per model, total, unpriced, bad row, "
                        "TTS characters" if not miss else f"missing {miss}")


TESTS = {
    "LEDGER-ROW":      test_ledger_row,
    "TAG-BATCH-CALLS": test_tag_batch_calls,
    "REVIEW-CALLS":    test_review_calls,
    "PICTURE-CALLS":   test_picture_calls,
    "REPORT":          test_report,
}

if __name__ == "__main__":
    bad = 0
    try:
        for name, fn in TESTS.items():
            try:
                ok, msg = fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, msg = False, f"{type(e).__name__}: {e}"
            print(f'{"PASS" if ok else "FAIL"}  {name:<16} {msg}')
            bad += (not ok)
    finally:
        shutil.rmtree(PDIR, ignore_errors=True)
    print("-" * 60)
    print("test_cost_ledger: all pass" if not bad else
          f"test_cost_ledger: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
