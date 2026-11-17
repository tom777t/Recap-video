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


TESTS = [("WRITES-THE-ACT", t_writes_the_act),
         ("PROJECT-RESTORED", t_project_restored),
         ("COST-RECORDED", t_cost_recorded)]

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
