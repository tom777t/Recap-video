# -*- coding: utf-8 -*-
"""test_trial_act.py - one act written in isolation, against a stub API.

  WRITES-THE-ACT     the act comes back through the real request path (the
                     story guide in its system prompt, its slots in the user
                     message) and is saved as act<N>.json + a readable script
  PROJECT-RESTORED   plan.json and angle.md are byte-identical afterwards;
                     draft.json.d is untouched; a file the trial created is
                     moved into the trial folder, not left behind
  COST-RECORDED      cost.json sums exactly the ledger rows the trial added,
                     per stage
  CRASH-KEEPS-ANGLE  the connection drops in the plan stage (17 Nov): the
                     angle already paid for is in the trial folder, the
                     project is restored, and the message names --resume
  RESUME-REUSES      --resume with that folder makes NO angle call; the plan
                     and the acts are written

Run:  python tools/test_trial_act.py      (exit 0 = all pass)
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import test_write_plan as TWP  # noqa: E402
import test_story_mode as TSM  # noqa: E402
import test_write_api as TWA  # noqa: E402
import trial_act as T  # noqa: E402
import write_slots as WS  # noqa: E402

config.STYLE_QUOTA_FLOORS = False
PROJ, PDIR = TWP.PROJ, Path(TWP.PDIR)
_R: dict = {}


def _go():
    if _R:
        return _R
    TWP._setup()
    plan = TWP._plan("good")
    plan.pop("slots", None)
    (PDIR / "plan.json").write_text(json.dumps(plan, indent=1),
                                    encoding="utf-8")
    (PDIR / "draft.json.d").mkdir(exist_ok=True)
    (PDIR / "draft.json.d" / "act1.json").write_text('{"act": 1}',
                                                     encoding="utf-8")
    snap = {n: (PDIR / n).read_bytes() for n in ("plan.json", "angle.md")}
    k = 2
    seen = {}

    def reply(cid, params):
        seen["system"] = "\n".join(b["text"] for b in params["system"])
        seen["user"] = params["messages"][0]["content"]
        cur = json.loads((PDIR / "plan.json").read_text(encoding="utf-8"))
        mine = WS.slots_for_act(cur["slots"], k)
        rep = [TSM._fill(s, i) for i, s in enumerate(mine)
               if s["role"] not in ("hold", "film_speaks")]
        return TWA.msg({"act": k, "lines": rep})
    c = TWA.Client(batch=reply)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = T.main(["--project", PROJ, "--act", str(k), "--keep-plan",
                     "--poll", "0"], client=c)
    tdirs = sorted((PDIR / "trial").glob(f"act{k}-*"))
    _R.update(rc=rc, out=buf.getvalue(), snap=snap, k=k, seen=seen,
              tdir=tdirs[-1] if tdirs else None, batches=len(c.batches))
    return _R


def t_writes_the_act():
    r = _go()
    td, k = r["tdir"], r["k"]
    bad = []
    if r["rc"] != 0 or td is None:
        return False, f"rc {r['rc']}: {r['out'][-300:]}"
    if "# Story guide: how this channel tells a film" not in r["seen"].get(
            "system", ""):
        bad.append("the story guide is not in the act's system prompt")
    if "YOUR SLOTS" not in r["seen"].get("user", ""):
        bad.append("the act was not given its slots")
    for n in (f"act{k}.json", f"script_act{k}.md"):
        if not (td / n).exists():
            bad.append(f"{n} missing")
    md = (td / f"script_act{k}.md").read_text(encoding="utf-8") \
        if (td / f"script_act{k}.md").exists() else ""
    if "narrated lines" not in md or "[" not in md:
        bad.append("the script has no timed lines")
    return not bad, (f"act {k} written via {r['batches']} batch(es), "
                     f"script saved" if not bad else "; ".join(bad))


def t_project_restored():
    r = _go()
    bad = [n for n, b in r["snap"].items() if (PDIR / n).read_bytes() != b]
    a1 = (PDIR / "draft.json.d" / "act1.json").read_text(encoding="utf-8")
    if a1 != '{"act": 1}':
        bad.append("draft.json.d/act1.json changed")
    left = [n for n in T.BACKUP if (PDIR / n).exists()
            and n not in r["snap"] and n not in ("coverage_policy.json",
                                                 "intro_style.txt")]
    if left:
        bad.append(f"left behind: {left}")
    return not bad, ("plan.json and angle.md byte-identical; draft.json.d "
                     "untouched" if not bad else "; ".join(bad))


def t_cost_recorded():
    r = _go()
    td = r["tdir"]
    cs = json.loads((td / "cost.json").read_text(encoding="utf-8"))
    st = cs["by_stage"]
    ok = (f"trial-act{r['k']}" in st and st[f"trial-act{r['k']}"]["calls"] == 1
          and cs["total_usd"] > 0 and "trial_act: restored" in r["out"]
          and "$" in r["out"])
    return ok, (f"cost.json: {cs['total_usd']} USD over "
                f"{sum(s['calls'] for s in st.values())} call(s), by stage "
                f"{sorted(st)}" if ok else f"{cs}; {r['out'][-200:]}")


def _staged(drop_in_plan: bool, resume=None, calls=None):
    """trial_act with the angle / plan stages replaced: the angle writes a
    marked angle.md and one ledger row; the plan raises a dropped-connection
    error, or writes the good plan."""
    import tag_batch as TB
    import write_api as W
    plan = TWP._plan("good")
    plan.pop("slots", None)
    calls = calls if calls is not None else []

    def fake_angle(ns, client):
        calls.append("angle")
        (PDIR / "angle.md").write_text(
            (PDIR / "angle.md").read_text(encoding="utf-8")
            + "\n<!-- NEW ANGLE -->\n", encoding="utf-8")
        TB.ledger_append(PDIR, "angle", "claude-sonnet-5-5",
                         {"in": 22000, "out": 4400, "cw": 0, "cr": 0,
                          "cw1h": 0}, batch=False)
        return 0

    class RemoteProtocolError(Exception):
        pass

    def fake_plan(ns, client):
        calls.append("plan")
        if drop_in_plan:
            raise RemoteProtocolError("peer closed connection without "
                                      "sending complete message body")
        (PDIR / "plan.json").write_text(json.dumps(plan, indent=1),
                                        encoding="utf-8")
        return 0

    k = 2

    def reply(cid, params):
        cur = json.loads((PDIR / "plan.json").read_text(encoding="utf-8"))
        mine = WS.slots_for_act(cur["slots"], k)
        return TWA.msg({"act": k, "lines": [
            TSM._fill(x, i) for i, x in enumerate(mine)
            if x["role"] not in ("hold", "film_speaks")]})
    sa, sp = W.cmd_angle, W.cmd_plan
    W.cmd_angle, W.cmd_plan = fake_angle, fake_plan
    buf = io.StringIO()
    try:
        argv = ["--project", PROJ, "--act", str(k), "--poll", "0"]
        if resume:
            argv += ["--resume", str(resume)]
        with contextlib.redirect_stdout(buf):
            rc = T.main(argv, client=TWA.Client(batch=reply))
    finally:
        W.cmd_angle, W.cmd_plan = sa, sp
    return rc, buf.getvalue(), calls


def t_crash_keeps_angle():
    _go()
    snap = {n: (PDIR / n).read_bytes() for n in ("plan.json", "angle.md")}
    rc, out, _c = _staged(drop_in_plan=True)
    td = sorted((PDIR / "trial").glob("act2-*"), key=lambda p: p.stat().st_mtime)[-1]
    _R["crash_dir"] = td
    bad = []
    if rc == 0:
        bad.append("rc 0 on a crash")
    if "<!-- NEW ANGLE -->" not in (td / "angle.md").read_text(encoding="utf-8") \
            if (td / "angle.md").exists() else True:
        bad.append("the paid-for angle is not in the trial folder")
    if any((PDIR / n).read_bytes() != b for n, b in snap.items()):
        bad.append("the project was not restored")
    if "--resume" not in out:
        bad.append("the message does not say how to continue")
    cs = json.loads((td / "cost.json").read_text(encoding="utf-8"))
    if "angle" not in cs["by_stage"]:
        bad.append("the angle's cost is not in cost.json")
    return not bad, ("dropped in plan: angle kept, project restored, "
                     "'--resume' named, angle cost recorded" if not bad
                     else "; ".join(bad))


def t_resume_reuses():
    if "crash_dir" not in _R:
        t_crash_keeps_angle()
    calls: list = []
    rc, out, calls = _staged(drop_in_plan=False, resume=_R["crash_dir"],
                             calls=calls)
    td = sorted((PDIR / "trial").glob("act2-*"), key=lambda p: p.stat().st_mtime)[-1]
    ok = (rc == 0 and calls == ["plan"] and (td / "act2.json").exists()
          and "<!-- NEW ANGLE -->" in (td / "angle.md").read_text(
              encoding="utf-8") and "reusing" in out)
    return ok, ("--resume: no angle call, plan + act written on the kept "
                "angle" if ok else f"rc {rc}, calls {calls}: {out[-300:]}")


TESTS = [("WRITES-THE-ACT", t_writes_the_act),
         ("PROJECT-RESTORED", t_project_restored),
         ("COST-RECORDED", t_cost_recorded),
         ("CRASH-KEEPS-ANGLE", t_crash_keeps_angle),
         ("RESUME-REUSES", t_resume_reuses)]

if __name__ == "__main__":
    fails = 0
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:18s} {msg}")
    print("-" * 60)
    print("test_trial_act: all pass" if not fails
          else f"test_trial_act: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
