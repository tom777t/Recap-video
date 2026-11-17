# -*- coding: utf-8 -*-
"""trial_act.py - write ONE act through the real pipeline, in isolation, and
record what it cost. The project is left as it was.

Why a separate command: `write_api.py draft` writes every missing act, then
assembles the whole draft and runs feedback rounds on every act with a
finding. Deleting one act and re-running it would mix a new act with old
ones written to a different plan, and the rounds would rewrite the old acts
too: more money, and a damaged draft.

    python tools/trial_act.py --project furious72015 --act 3 4
    python tools/trial_act.py --project furious72015 --act 3 --keep-plan
        (--keep-plan: reuse the project's angle.md and plan.json; only the
         act is written)
    python tools/trial_act.py --project furious72015 --act 3 4 \
        --resume projects/furious72015/trial/act34-20261117-120501
        (--resume: an earlier trial stopped part-way; its angle - and its
         plan, if it got that far - are reused, not paid for again)

Each stage's output is copied into the trial folder THE MOMENT it is
written, so a crash later (a dropped connection, 17 Nov) never loses what
was already paid for.

What it does, with the SAME code the pipeline runs:
  1. backs up angle.md, coverage_policy.json, plan.json (+ plan_rejected*),
     intro_style.txt into projects/<p>/trial/<time>/backup/
  2. angle (--force) and plan (--force): write_api.cmd_angle / cmd_plan
  3. the act(s): draft_system + act_request, ONE batch for all of them (half
     price, as in the pipeline), the same schema check and the same ONE fix
     round for schema errors or slot deviations that the draft stage allows
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
    from pipeline import flow_stats as FS
    out.append(FS.flow_line(FS.flow_stats(lines)))
    return "\n".join(out) + "\n"


def main(argv=None, client=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--act", type=int, nargs="+", required=True)
    ap.add_argument("--keep-plan", action="store_true")
    ap.add_argument("--resume", help="an earlier trial folder to continue")
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
    acts = list(dict.fromkeys(a.act))
    tdir = pdir / "trial" / f"act{''.join(map(str, acts))}-{stamp}"
    n_ = 2
    while tdir.exists():          # two trials in the same second
        tdir = tdir.with_name(f"act{''.join(map(str, acts))}-{stamp}-{n_}")
        n_ += 1
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
    def keep(*names):
        for n in names:
            if (pdir / n).exists():
                shutil.copy2(pdir / n, tdir / n)

    res_dir = Path(a.resume) if a.resume else None
    if res_dir is not None and not res_dir.is_absolute():
        res_dir = Path(ROOT) / res_dir
    if res_dir is not None and not (res_dir / "angle.md").exists():
        print(f"trial_act: --resume {res_dir} has no angle.md - nothing to "
              f"reuse")
        return 1
    try:
        if res_dir is not None:
            for n in ("angle.md", "coverage_policy.json", "plan.json"):
                if (res_dir / n).exists():
                    shutil.copy2(res_dir / n, pdir / n)
                    shutil.copy2(res_dir / n, tdir / n)
            print(f"trial_act: reusing {res_dir.name}'s angle"
                  + (" and plan" if (res_dir / "plan.json").exists() else ""))
        if not a.keep_plan and res_dir is None:
            rc = W.cmd_angle(ns, client)
            keep("angle.md", "coverage_policy.json")
            if rc:
                print("trial_act: angle failed - stopping")
                return rc
        if not a.keep_plan and not (res_dir is not None
                                    and (res_dir / "plan.json").exists()):
            rc = W.cmd_plan(ns, client)
            keep("plan.json", "plan_rejected.json")
            if rc:
                print("trial_act: plan failed - stopping")
                return rc
        plan = json.loads(W._read(pdir / "plan.json"))
        ab = WP.act_beats(a.project, W._tool)
        if not plan.get("slots"):
            W.save_slots(a.project, pdir, plan, ab)
            plan = json.loads(W._read(pdir / "plan.json"))
        slots = plan.get("slots") or None
        sysb = W.draft_system(pdir)
        reqs = {f"act{k}": W.act_request(
            a.project, pdir, k, sysb,
            plan_text=WP.plan_for_act(plan, ab.get(k, []), k),
            slots=slots, plan=plan) for k in acts}
        tag = "trial-act" + "".join(map(str, acts))
        got = W.batch(client, pdir, tag, reqs, wait=True, poll=a.poll)
        res, fixes = {}, {}
        for k in acts:
            msg = got.get(f"act{k}")
            obj, why = W._json_reply(msg, "draft")
            probs = [why] if obj is None else W.check_act(obj, k, slots, plan)
            lines = [] if probs else W.act_lines(obj, k, slots, plan)
            devs = [] if probs else W.slot_deviations({"lines": lines}, k,
                                                      slots, pdir)
            res[k] = {"lines": lines, "probs": probs, "devs": devs, "fix": ""}
            if (probs and obj is not None) or devs:
                # the draft stage's own single fix round
                fb = None if probs else W.slot_feedback(devs)
                fixes[f"act{k}"] = W.retry_params(reqs[f"act{k}"], msg,
                                                  probs or devs, fb)
        if fixes:
            got2 = W.batch(client, pdir, f"{tag}-fix", fixes, wait=True,
                           poll=a.poll)
            for cid in fixes:
                k = int(cid[3:])
                r = res[k]
                obj2, why2 = W._json_reply(got2.get(cid), "draft")
                p2 = [why2] if obj2 is None else W.check_act(obj2, k, slots,
                                                             plan)
                if p2:
                    r["fix"] = f"fix round reply rejected: {'; '.join(p2[:2])}"
                    continue
                if r["devs"] and r["lines"]:
                    import write_slots as WS
                    r["lines"], _n = WS.merge_revision(
                        r["lines"], [l for l in obj2.get("lines") or []
                                     if isinstance(l, dict)],
                        WS.slots_for_act(slots, k), k)
                else:
                    r["lines"] = W.act_lines(obj2, k, slots, plan)
                r["devs"] = W.slot_deviations({"lines": r["lines"]}, k,
                                              slots, pdir)
                r["probs"], r["fix"] = [], "one fix round used"
        md = []
        for k in acts:
            r = res[k]
            if r["probs"]:
                print(f"trial_act: act {k} reply not usable: "
                      f"{'; '.join(r['probs'][:3])}")
                rc = 2
                continue
            (tdir / f"act{k}.json").write_text(json.dumps(
                {"act": k, "lines": r["lines"]}, ensure_ascii=False,
                indent=2), encoding="utf-8")
            md.append(script_md(r["lines"], k, plan.get("title") or a.project))
            from pipeline import flow_stats as FS
            print(f"  act {k} " + FS.flow_line(FS.flow_stats(r["lines"])))
            print(f"trial_act: act {k}: {len(r['lines'])} line(s)"
                  + (f" ({r['fix']})" if r["fix"] else "")
                  + (f"; {len(r['devs'])} slot deviation(s) left: "
                     + "; ".join(r["devs"][:3]) if r["devs"] else ""))
        if md:
            out = tdir / ("script_act" + "".join(map(str, acts)) + ".md")
            out.write_text("\n\n".join(md), encoding="utf-8")
            print(f"trial_act: readable script -> {out}")
        for n in ("angle.md", "coverage_policy.json", "plan.json"):
            if (pdir / n).exists():
                shutil.copy2(pdir / n, tdir / n)
    except Exception as e:
        print(f"trial_act: STOPPED ({type(e).__name__}: {str(e)[:160]}). "
              f"What was already written is kept in {tdir} - continue with "
              f"--resume {tdir.relative_to(Path(ROOT)) if str(tdir).startswith(ROOT) else tdir}")
        rc = 1
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
