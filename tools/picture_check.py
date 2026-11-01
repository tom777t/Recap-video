# -*- coding: utf-8 -*-
"""picture_check.py - is each narrated line's picture from the right scene?

    python tools/picture_check.py --project P            # submit, wait, report
    python tools/picture_check.py --project P --submit   # submit only, return
    python tools/picture_check.py --project P --collect  # collect if finished
    python tools/picture_check.py --project P --final X.mp4 --timeline X.json
    python tools/picture_check.py calibrate --project P \\
        --bad-final F1.mp4 --bad-timeline T1.json \\
        [--good-final final.mp4 --good-timeline timeline.json]

One Message Batch (half price) of vision requests, one per narrated line:
the narration text + config.PICTURE_CHECK_FRAMES frames from the line's real
span in the render, on config.PICTURE_CHECK_MODEL. See pipeline/picture_check.py
for the question, the answers and how causes are assigned. Only wrong-scene,
contradicts and unwatchable count as defects.

The project's own final.mp4 gets a PICTURE-CHECK row (WARN, never blocking)
and its worst lines in final_report.md. A render named with --final is
measured and printed but NOT written into final_report.md, which describes
final.mp4. --final and --timeline go together: a timeline describes one cut.

`calibrate` runs the check on two renders a viewer already judged - a BAD one
and a GOOD one of the same film - and prints defects per render and per
cause, so the check's defect rate can be compared with the viewer's verdict.

Reuses tools/tag_batch.py's client (ANTHROPIC_API_KEY from the environment
only), reply parsing, usage and PRICES. State per render in
projects/<p>/picture_check[_<file>].json, so a batch is never paid for twice.

Exit: 0 done | 1 hard error | 3 batch still running.
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


class Running(Exception):
    """The batch has not finished yet."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def target(project: str, final=None, timeline=None) -> dict:
    """The render to check: its file, its timeline, where its state lives."""
    pdir = config.project_dir(project)
    if (final is None) != (timeline is None):
        raise ValueError("--final and --timeline go together: a timeline "
                         "describes the positions of ONE render")
    if final is None:
        return {"final": pdir / "final.mp4", "timeline": pdir / "timeline.json",
                "state": pdir / PC.STATE_FILE, "default": True}
    f, t = Path(final), Path(timeline)
    if not f.is_absolute() and not f.exists():
        f = pdir / f
    if not t.is_absolute() and not t.exists():
        t = pdir / t
    default = f.resolve() == (pdir / "final.mp4").resolve()
    st = (pdir / PC.STATE_FILE if default
          else pdir / f"picture_check_{f.stem}.json")
    return {"final": f, "timeline": t, "state": st, "default": default}


def _sig(path: Path) -> list:
    st = Path(path).stat()
    return [st.st_size, st.st_mtime_ns]


def submit(project: str, client=None, final=None, timeline=None,
           state: Path | None = None) -> dict:
    """Submit the batch for one render and record it. Returns the state.
    `state` overrides where it is recorded (calibration keeps its own)."""
    tg = target(project, final, timeline)
    if state is not None:
        tg["state"] = Path(state)
    reqs, notes, skipped = PC.requests_for(project, tg["final"], tg["timeline"])
    if not reqs:
        raise TB.TagBatchError(f"no narrated line has a span in "
                               f"{tg['timeline'].name}")
    client = client or TB.CLIENT_FACTORY()
    batch = client.messages.batches.create(
        requests=[{"custom_id": cid, "params": p} for cid, _l, _s, p in reqs])
    st = {"batch_id": TB._get(batch, "id"), "model": config.PICTURE_CHECK_MODEL,
          "submitted_at": _now(), "final_path": str(tg["final"]),
          "timeline_path": str(tg["timeline"]), "final": _sig(tg["final"]),
          "lines": {cid: {"id": lid, "at": sp["a"], "end": sp["b"]}
                    for cid, lid, sp, _p in reqs},
          "skipped": skipped, "notes": notes, "status": "submitted"}
    tg["state"].write_text(json.dumps(st, indent=1), encoding="utf-8")
    print(f"picture check: submitted batch {st['batch_id']} for "
          f"{tg['final'].name} - {len(reqs)} line(s), "
          f"{config.PICTURE_CHECK_FRAMES} frames each, {st['model']}"
          + (f"; {len(skipped)} line(s) had no frame" if skipped else ""))
    return st


def _pending(tg: dict):
    if not tg["state"].exists():
        return None
    st = json.loads(tg["state"].read_text(encoding="utf-8"))
    if st.get("status") != "submitted":
        return None
    return st


def fetch(project: str, tg: dict, client, wait: bool, poll: float) -> tuple:
    """(summary, info) for a submitted render. Raises Running."""
    st = json.loads(tg["state"].read_text(encoding="utf-8"))
    while True:
        b = client.messages.batches.retrieve(st["batch_id"])
        if TB._get(b, "processing_status") == "ended":
            break
        if not wait:
            raise Running(f"batch {st['batch_id']} still "
                          f"{TB._get(b, 'processing_status')}")
        time.sleep(poll)
    results, failed = [], []
    tok = {"in": 0, "out": 0}
    cost, known = 0.0, True
    for item in client.messages.batches.results(st["batch_id"]):
        line = st["lines"].get(TB._get(item, "custom_id"))
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
        if not isinstance(obj, dict) or obj.get("verdict") not in PC.VERDICTS:
            failed.append(line["id"])
            continue
        results.append({"id": line["id"], "at": line["at"],
                        "verdict": obj["verdict"],
                        "reason": str(obj.get("reason") or "")[:200],
                        "frames": list(obj.get("frames") or [])})
    spans, _off, _n = PC.load_spans(config.project_dir(project), tg["timeline"])
    summ = PC.summarise(results, spans, int(config.PICTURE_CHECK_WORST_N))
    info = {"model": st["model"], "tokens_in": tok["in"],
            "tokens_out": tok["out"], "cost": round(cost, 4) if known else None,
            "skipped": len(st.get("skipped") or []) + len(failed),
            "why": "the batch returned no usable result"}
    if _sig(tg["final"]) != st.get("final"):
        # The frames came from a file that has since been re-rendered: the
        # answers describe another cut. Not a pass.
        summ["ok"] = None
        info["why"] = (f"{tg['final'].name} changed after the frames were "
                       f"taken - re-run the picture check")
    st["status"] = "collected"
    st["collected_at"] = _now()
    tg["state"].write_text(json.dumps(st, indent=1), encoding="utf-8")
    return summ, info


def _cost_line(info: dict) -> str:
    c = info.get("cost")
    return (f"tokens in {info['tokens_in']} out {info['tokens_out']} | cost "
            + (f"~${c:.4f} (batch price, verify tag_batch.PRICES)"
               if c is not None else "n/a (no listed price)"))


def collect(project: str, client=None, wait: bool = False, poll: float = 30.0,
            final=None, timeline=None) -> int:
    tg = target(project, final, timeline)
    client = client or TB.CLIENT_FACTORY()
    try:
        summ, info = fetch(project, tg, client, wait, poll)
    except Running as e:
        print(f"picture check: {e} - collect later with --collect")
        return 3
    PC.print_summary(summ, info)
    print("picture check: " + _cost_line(info))
    if tg["default"]:
        path = PC.write_report(config.project_dir(project), summ, info)
        print(f"picture check: report -> {path}")
    else:
        print(f"picture check: {tg['final'].name} is not the project's "
              f"final.mp4 - measured, NOT written into final_report.md")
    return 0


def calibrate(project: str, bad: tuple, good: tuple, client=None,
              poll: float = 30.0) -> int:
    """Run both renders, print defects per render and per cause."""
    client = client or TB.CLIENT_FACTORY()
    renders = (("BAD", bad), ("GOOD", good))
    tgs = {}
    for label, (f, t) in renders:
        tg = target(project, f, t)
        if tg["default"]:
            # calibration must not clobber the project's own report state
            tg["state"] = config.project_dir(project) / "picture_check_calibrate_good.json"
        tgs[label] = tg
        st = _pending(tg)
        if st is None or st.get("final") != _sig(tg["final"]):
            submit(project, client, tg["final"], tg["timeline"], tg["state"])
    out = {}
    for label, _r in renders:
        summ, info = fetch(project, tgs[label], client, wait=True, poll=poll)
        out[label] = (summ, info)
    print("\nPICTURE-CHECK calibration - "
          f"{config.PICTURE_CHECK_MODEL}, {config.PICTURE_CHECK_FRAMES} "
          f"frames @ {config.PICTURE_CHECK_FRAME_SIDE}px")
    causes = sorted({k for s, _i in out.values() for k in s["by_cause"]})
    hdr = f"  {'render':<6} {'lines':>5} " + " ".join(
        f"{v:>11}" for v in PC.VERDICTS) + f" {'DEFECTS':>8} {'rate':>6}"
    print(hdr)
    rec = {}
    for label, (s, info) in out.items():
        rate = (s["defects"] / s["lines"]) if s["lines"] else 0.0
        print(f"  {label:<6} {s['lines']:>5} " + " ".join(
            f"{s['counts'][v]:>11}" for v in PC.VERDICTS)
              + f" {s['defects']:>8} {rate:>6.1%}")
        rec[label] = {"final": str(tgs[label]["final"]), "lines": s["lines"],
                      "counts": s["counts"], "defects": s["defects"],
                      "by_cause": s["by_cause"], "cost": info.get("cost"),
                      "worst": [{k: r.get(k) for k in
                                 ("id", "at", "verdict", "cause", "reason")}
                                for r in s["worst"]],
                      "valid": s["ok"] is not None}
    print(f"\n  defects by cause:")
    for k in causes:
        print(f"    {k:<32} BAD {out['BAD'][0]['by_cause'].get(k, 0):>4}   "
              f"GOOD {out['GOOD'][0]['by_cause'].get(k, 0):>4}")
    for label, (s, info) in out.items():
        print(f"  {label}: " + _cost_line(info))
        if s["ok"] is None:
            print(f"  {label}: NOT VALID - {info.get('why')}")
    b, g = out["BAD"][0]["defects"], out["GOOD"][0]["defects"]
    print(f"\n  The viewer judged BAD mismatched and GOOD almost clean. A "
          f"useful check finds clearly more defects in BAD ({b}) than in "
          f"GOOD ({g}), and few in GOOD.")
    p = config.project_dir(project) / "picture_calibration.json"
    p.write_text(json.dumps({"at": _now(), "model": config.PICTURE_CHECK_MODEL,
                             "frames": config.PICTURE_CHECK_FRAMES,
                             "side": config.PICTURE_CHECK_FRAME_SIDE,
                             "renders": rec}, indent=1), encoding="utf-8")
    print(f"  written: {p}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "calibrate"])
    ap.add_argument("--project", required=True)
    ap.add_argument("--final", help="a render other than final.mp4")
    ap.add_argument("--timeline", help="that render's timeline json")
    ap.add_argument("--bad-final")
    ap.add_argument("--bad-timeline")
    ap.add_argument("--good-final")
    ap.add_argument("--good-timeline")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--submit", action="store_true", help="submit and return")
    g.add_argument("--collect", action="store_true",
                   help="collect a submitted batch if it has finished")
    ap.add_argument("--poll", type=float, default=30.0)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "calibrate":
            if not (a.bad_final and a.bad_timeline):
                print("calibrate needs --bad-final and --bad-timeline")
                return 1
            good = ((a.good_final, a.good_timeline)
                    if (a.good_final or a.good_timeline) else
                    ("final.mp4", "timeline.json"))
            return calibrate(a.project, (a.bad_final, a.bad_timeline), good,
                             TB.CLIENT_FACTORY(), a.poll)
        tg = target(a.project, a.final, a.timeline)
        st = _pending(tg)
        client = TB.CLIENT_FACTORY()
        if a.collect:
            if st is None:
                print("picture check: no submitted batch to collect")
                return 1
            return collect(a.project, client, False, a.poll, a.final, a.timeline)
        if st is not None and st.get("final") != _sig(tg["final"]):
            print(f"picture check: the pending batch was taken from an "
                  f"earlier {tg['final'].name} - submitting a new one")
            st = None
        if st is None:
            submit(a.project, client, a.final, a.timeline)
        if a.submit:
            return 0
        return collect(a.project, client, True, a.poll, a.final, a.timeline)
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
