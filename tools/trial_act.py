# -*- coding: utf-8 -*-
"""trial_act.py - write ONE act through the real pipeline, in isolation, and
record what it cost. The project is left as it was.

Why a separate command: `write_api.py draft` writes every missing act, then
assembles the whole draft and runs feedback rounds on every act with a
finding. Deleting one act and re-running it would mix a new act with old
ones written to a different plan, and the rounds would rewrite the old acts
too: more money, and a damaged draft.

    python tools/trial_act.py --project furious72015 --act 3
    python tools/trial_act.py --project furious72015 --act 3 --keep-plan
        (--keep-plan: reuse the project's angle.md and plan.json; only the
         act is written)

What it does, with the SAME code the pipeline runs:
  1. backs up angle.md, coverage_policy.json, plan.json (+ plan_rejected*),
     intro_style.txt into projects/<p>/trial/<time>/backup/
  2. angle (--force) and plan (--force): write_api.cmd_angle / cmd_plan
  3. the act: draft_system + act_request, one batch (half price, as in the
     pipeline), the same schema check and the same ONE fix round for schema
     errors or slot deviations that the draft stage allows
  4. saves to projects/<p>/trial/<time>/: angle.md, coverage_policy.json,
     plan.json, act<N>.json, act<N>_script.md (readable: time, line, a star
     on the narrator's own reactions) and cost.json
  5. RESTORES the backed-up files, so draft.json.d, draft.json and the
     render are untouched. Files the trial created that did not exist before
     are moved into the trial folder.

Cost: every call goes into cost_ledger.jsonl as usual (stages angle, plan,
trial-act<N>...); this command sums the rows it added, per stage.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402

BACKUP = ("angle.md", "coverage_policy.json", "plan.json",
          "plan_rejected.json", "plan_rejected.repaired.json",
          "intro_style.txt")


def _ledger_rows(pdir: Path) -> list:
    p = pdir / "cost_ledger.jsonl"
    if not p.exists():
        return []
    rows = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(ln))
        except ValueError:
            pass
    return rows


def cost_summary(rows: list) -> dict:
    by: dict = {}
    for r in rows:
        s = by.setdefault(r.get("stage", "?"), {"calls": 0, "usd": 0.0,
                                                 "input": 0, "output": 0,
                                                 "cache_read": 0,
                                                 "cache_write": 0,
                                                 "unpriced": 0})
        s["calls"] += 1
        for k in ("input", "output", "cache_read", "cache_write"):
            s[k] += int(r.get(k) or 0)
        if r.get("usd") is None:
            s["unpriced"] += 1
        else:
            s["usd"] += float(r["usd"])
    total = round(sum(s["usd"] for s in by.values()), 4)
    for s in by.values():
        s["usd"] = round(s["usd"], 4)
    return {"by_stage": by, "total_usd": total,
            "unpriced_calls": sum(s["unpriced"] for s in by.values())}


def script_md(lines: list, k: int, title: str) -> str:
    out = [f"# {title} - act {k}, written by the pipeline (trial)", "",
           "`[time]` = where the line's footage starts. ★ = the narrator's "
           "own reaction (payload judgment). Holds and film-speaks are shown "
           "in brackets.", ""]
    n = j = 0
    for ln in lines:
        t = str(ln.get("clip_start") or "")[:8]
        txt = str(ln.get("narration") or "").strip()
        if not txt:
            if ln.get("film_speaks"):
                out.append(f"[{t}] (the film speaks)")
            elif ln.get("narration_silence_seconds") or ln.get("hold"):
                out.append(f"[{t}] (hold on footage)")
            continue
        n += 1
        star = ""
        if ln.get("payload") == "judgment":
            j += 1
            star = "★ "
        out.append(f"[{t}] {star}{txt}")
        out.append("")
    out += ["---", f"{n} narrated lines, {j} reactions "
            f"({(j / n * 100 if n else 0):.0f}%), "
            f"{sum(len(str(l.get('narration') or '').split()) for l in lines)}"
            f" words."]
    return "\n".join(out) + "\n"


def main(argv=None, client=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--act", type=int, required=True)
    ap.add_argument("--keep-plan", action="store_true")
    ap.add_argument("--poll", type=float, default=20.0)
    a = ap.parse_args(argv)

    import tag_batch as TB
    import write_api as W
    import write_plan as WP

    pdir = Path(config.project_dir(a.project))
    if not (pdir / "beats_proposal.md").exists():
        print(f"trial_act: {pdir} has no beats_proposal.md")
        return 1
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tdir = pdir / "trial" / f"act{a.act}-{stamp}"
    bdir = tdir / "backup"
    bdir.mkdir(parents=True)
    existed = {n for n in BACKUP if (pdir / n).exists()}
    for n in existed:
        shutil.copy2(pdir / n, bdir / n)
    print(f"trial_act: backed up {len(existed)} file(s) to {bdir}")
    before = len(_ledger_rows(pdir))
    client = client or TB.CLIENT_FACTORY()
    ns = SimpleNamespace(project=a.project, force=True, feedback_only=False,
                         no_wait=False, poll=a.poll, wiki=None, by_hand=False)
    rc = 0
    t0 = time.time()
    try:
        if not a.keep_plan:
            rc = W.cmd_angle(ns, client)
            if rc:
                print("trial_act: angle failed - stopping")
                return rc
            rc = W.cmd_plan(ns, client)
            if rc:
                print("trial_act: plan failed - stopping")
                return rc
        plan = json.loads(W._read(pdir / "plan.json"))
        ab = WP.act_beats(a.project, W._tool)
        if not plan.get("slots"):
            W.save_slots(a.project, pdir, plan, ab)
            plan = json.loads(W._read(pdir / "plan.json"))
        slots = plan.get("slots") or None
        k = a.act
        sysb = W.draft_system(pdir)
        req = W.act_request(a.project, pdir, k, sysb,
                            plan_text=WP.plan_for_act(plan, ab.get(k, []), k),
                            slots=slots, plan=plan)
        tag = f"trial-act{k}"
        got = W.batch(client, pdir, tag, {f"act{k}": req}, wait=True,
                      poll=a.poll)
        msg = got.get(f"act{k}")
        obj, why = W._json_reply(msg, "draft")
        probs = [why] if obj is None else W.check_act(obj, k, slots, plan)
        lines = [] if probs else W.act_lines(obj, k, slots, plan)
        devs = [] if probs else W.slot_deviations({"lines": lines}, k,
                                                  slots, pdir)
        fixed = ""
        if (probs and obj is not None) or devs:
            # the draft stage's own single fix round
            fb = None if probs else W.slot_feedback(devs)
            r2 = W.retry_params(req, msg, probs or devs, fb)
            got2 = W.batch(client, pdir, f"{tag}-fix", {f"act{k}": r2},
                           wait=True, poll=a.poll)
            obj2, why2 = W._json_reply(got2.get(f"act{k}"), "draft")
            p2 = [why2] if obj2 is None else W.check_act(obj2, k, slots, plan)
            if not p2:
                if devs and lines:
                    import write_slots as WS
                    lines, _n = WS.merge_revision(
                        lines, [l for l in obj2.get("lines") or []
                                if isinstance(l, dict)],
                        WS.slots_for_act(slots, k), k)
                else:
                    lines = W.act_lines(obj2, k, slots, plan)
                devs = W.slot_deviations({"lines": lines}, k, slots, pdir)
                probs = []
                fixed = "one fix round used"
            else:
                fixed = f"fix round reply rejected: {'; '.join(p2[:2])}"
        if probs:
            print(f"trial_act: act {k} reply not usable: {'; '.join(probs[:3])}")
            rc = 2
        else:
            (tdir / f"act{k}.json").write_text(json.dumps(
                {"act": k, "lines": lines}, ensure_ascii=False, indent=2),
                encoding="utf-8")
            (tdir / f"act{k}_script.md").write_text(
                script_md(lines, k, plan.get("title") or a.project),
                encoding="utf-8")
            print(f"trial_act: act {k}: {len(lines)} line(s) -> "
                  f"{tdir / f'act{k}_script.md'}"
                  + (f" ({fixed})" if fixed else "")
                  + (f"; {len(devs)} slot deviation(s) left: "
                     + "; ".join(devs[:3]) if devs else ""))
        for n in ("angle.md", "coverage_policy.json", "plan.json"):
            if (pdir / n).exists():
                shutil.copy2(pdir / n, tdir / n)
    finally:
        # restore: the project is left exactly as it was
        for n in BACKUP:
            cur = pdir / n
            if n in existed:
                shutil.copy2(bdir / n, cur)
            elif cur.exists():
                shutil.move(str(cur), str(tdir / f"created_{n}"))
        rows = _ledger_rows(pdir)[before:]
        cs = cost_summary(rows)
        cs["minutes"] = round((time.time() - t0) / 60, 1)
        (tdir / "cost.json").write_text(json.dumps(cs, indent=1),
                                        encoding="utf-8")
        print(f"trial_act: restored the project's files; cost "
              f"${cs['total_usd']:.4f} over {len(rows)} call(s) in "
              f"{cs['minutes']} min"
              + (f" ({cs['unpriced_calls']} call(s) at an unlisted price)"
                 if cs["unpriced_calls"] else ""))
        for st, s in cs["by_stage"].items():
            print(f"  {st:18s} {s['calls']} call(s)  ${s['usd']:.4f}  "
                  f"in {s['input']:,} out {s['output']:,} cache-read "
                  f"{s['cache_read']:,}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
