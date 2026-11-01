# -*- coding: utf-8 -*-
"""picture_check.py - does final.mp4 show what each narrated line says?

    python tools/picture_check.py --project P            # submit, wait, report
    python tools/picture_check.py --project P --submit   # submit only, return
    python tools/picture_check.py --project P --collect  # collect if finished

One Message Batch (half price) of vision requests, one per narrated line:
the narration text + config.PICTURE_CHECK_FRAMES frames from the line's real
span in final.mp4, on config.PICTURE_CHECK_MODEL. See pipeline/picture_check.py
for what each request sees and how causes are assigned. The result is a
PICTURE-CHECK row (WARN, never blocking) and the worst
config.PICTURE_CHECK_WORST_N lines in final_report.md, and the token cost.

Reuses tools/tag_batch.py's client (ANTHROPIC_API_KEY from the environment
only), reply parsing, usage and PRICES. State (batch id, line ids) is kept in
projects/<p>/picture_check.json so a submitted batch is never paid for twice.

Exit: 0 report written | 1 hard error | 3 batch still running.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import tag_batch as TB  # noqa: E402
from pipeline import picture_check as PC  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _state_path(project: str) -> Path:
    return config.project_dir(project) / PC.STATE_FILE


def _final_sig(project: str) -> list:
    st = (config.project_dir(project) / "final.mp4").stat()
    return [st.st_size, st.st_mtime_ns]


def submit(project: str, client=None) -> dict:
    """Submit the batch and record it. Returns the state."""
    reqs, notes, skipped = PC.requests_for(project)
    if not reqs:
        raise TB.TagBatchError("no narrated line has a span in timeline.json")
    client = client or TB.CLIENT_FACTORY()
    batch = client.messages.batches.create(
        requests=[{"custom_id": cid, "params": p} for cid, _l, _s, p in reqs])
    st = {"batch_id": TB._get(batch, "id"), "model": config.PICTURE_CHECK_MODEL,
          "submitted_at": _now(), "final": _final_sig(project),
          "lines": {cid: {"id": lid, "at": sp["a"], "end": sp["b"]}
                    for cid, lid, sp, _p in reqs},
          "skipped": skipped, "notes": notes, "status": "submitted"}
    _state_path(project).write_text(json.dumps(st, indent=1), encoding="utf-8")
    print(f"picture check: submitted batch {st['batch_id']} - {len(reqs)} "
          f"line(s), {config.PICTURE_CHECK_FRAMES} frames each, "
          f"{st['model']}" + (f"; {len(skipped)} line(s) had no frame"
                               if skipped else ""))
    return st


def collect(project: str, client=None, wait: bool = False,
            poll: float = 30.0) -> int:
    sp = _state_path(project)
    st = json.loads(sp.read_text(encoding="utf-8"))
    client = client or TB.CLIENT_FACTORY()
    while True:
        b = client.messages.batches.retrieve(st["batch_id"])
        if TB._get(b, "processing_status") == "ended":
            break
        if not wait:
            print(f"picture check: batch {st['batch_id']} still "
                  f"{TB._get(b, 'processing_status')} - collect later:\n"
                  f"  python tools/picture_check.py --project {project} "
                  f"--collect")
            return 3
        time.sleep(poll)
    pdir = config.project_dir(project)
    results, failed = [], []
    tok = {"in": 0, "out": 0}
    cost, known = 0.0, True
    for item in client.messages.batches.results(st["batch_id"]):
        cid = TB._get(item, "custom_id")
        line = st["lines"].get(cid)
        if line is None:
            continue
        res = TB._get(item, "result")
        if TB._get(res, "type") != "succeeded":
            failed.append(line["id"])
            continue
        msg = TB._get(res, "message")
        u = TB.usage_of(msg)
        tok["in"] += u["in"] + u["cw"] + u["cr"]
        tok["out"] += u["out"]
        c = TB.cost_usd(st["model"], u, batch=True)
        known = known and c is not None
        cost += c or 0.0
        obj = TB.parse_reply(TB.reply_text(msg))
        if (not isinstance(obj, dict) or obj.get("verdict") not in PC.VERDICTS):
            failed.append(line["id"])
            continue
        results.append({"id": line["id"], "at": line["at"],
                        "verdict": obj["verdict"],
                        "reason": str(obj.get("reason") or "")[:200],
                        "frames": list(obj.get("frames") or []),
                        "abstract": bool(obj.get("abstract"))})
    stale = _final_sig(project) != st.get("final")
    spans, _off, _n = PC.load_spans(pdir)
    summ = PC.summarise(results, spans, int(config.PICTURE_CHECK_WORST_N))
    info = {"model": st["model"], "tokens_in": tok["in"],
            "tokens_out": tok["out"],
            "cost": round(cost, 4) if known else None,
            "skipped": len(st.get("skipped") or []) + len(failed),
            "why": "the batch returned no usable result"}
    if stale:
        # The frames were taken from a final.mp4 that has since been
        # re-rendered: the answers describe another file. Not a pass.
        summ["ok"] = None
        info["why"] = ("final.mp4 changed after the frames were taken - "
                       "re-run the picture check")
    path = PC.write_report(pdir, summ, info)
    PC.print_summary(summ, info)
    print(f"picture check: tokens in {tok['in']} out {tok['out']} | cost "
          + (f"~${cost:.4f} (batch price, verify tag_batch.PRICES)"
             if known else "n/a (no listed price)"))
    print(f"picture check: report -> {path}")
    st["status"] = "collected"
    st["collected_at"] = _now()
    sp.write_text(json.dumps(st, indent=1), encoding="utf-8")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--project", required=True)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--submit", action="store_true", help="submit and return")
    g.add_argument("--collect", action="store_true",
                   help="collect a submitted batch if it has finished")
    ap.add_argument("--poll", type=float, default=30.0)
    a = ap.parse_args(argv)
    try:
        sp = _state_path(a.project)
        st = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
        pending = st.get("status") == "submitted"
        if pending and not a.collect and st.get("final") != _final_sig(a.project):
            print("picture check: the pending batch was taken from an earlier "
                  "final.mp4 - submitting a new one")
            pending = False
        client = TB.CLIENT_FACTORY()
        if a.collect:
            if not pending:
                print("picture check: no submitted batch to collect")
                return 1
            return collect(a.project, client)
        if not pending:
            submit(a.project, client)
        if a.submit:
            return 0
        return collect(a.project, client, wait=True, poll=a.poll)
    except TB.TagBatchError as e:
        print(str(e))
        return 1
    except (FileNotFoundError, ValueError, KeyError) as e:
        print(f"picture check: cannot run - {e}")
        return 1
    except Exception as e:
        print(f"picture check: API error {type(e).__name__}: {str(e)[:200]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
