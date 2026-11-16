# -*- coding: utf-8 -*-
"""model_compare.py - the same request, several models / efforts, side by side.

    python tools/model_compare.py --project P --act 2
    python tools/model_compare.py --project P --act 2 --variants sonnet,sonnet@medium,haiku
    python tools/model_compare.py --project P --act 2 --estimate

Question it answers: can a cheaper model (or less thinking) write / review
this pipeline's output well enough? It sends ONE act's real draft request
(tools/write_api.act_request - the same slots, brief and payload the draft
stage sends) and the real cold-read review request (tools/review_api) to
each variant, and NOTHING is written into the draft: every reply goes to
projects/<p>/model_compare/. For each variant it measures what code can:

  draft      reply parses / schema problems (check_act) / slot deviations
             (write_slots.check_slots - word bands, quotes, voice, bridges,
             tics inside the act) / per-line draft-gate problems against
             the rest of the draft (pipeline/line_rules) / words / cost
  cold-read  findings filed, by kind / cost

and writes model_compare/act<k>.compare.md: the numbers, then every slot's
line from each variant next to each other, for a person to read. What code
cannot measure - is it good narration - is that reading.

Variants: `sonnet`, `haiku`, or a full model id; `@low|medium|high` sets the
thinking effort (default: the stage's config.WRITE_EFFORT). Each call goes
into cost_ledger.jsonl as stage "compare:<what>:<variant>".
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402

ALIASES = {"sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5",
           "opus": "claude-opus-5-5"}
DEFAULT_VARIANTS = "sonnet,sonnet@medium,haiku"


def parse_variant(v: str) -> tuple:
    m, _, eff = v.strip().partition("@")
    return ALIASES.get(m, m), (eff or None)


def with_variant(p: dict, model: str, eff: str | None) -> dict:
    q = json.loads(json.dumps(p))
    q["model"] = model
    if eff:
        q.setdefault("output_config", {})["effort"] = eff
    return q


def estimate(p: dict, model: str) -> float | None:
    """A rough upper bound: the prompt as input at the uncached rate, the
    whole max_tokens as output."""
    import tag_batch as TB
    chars = len(json.dumps(p.get("system"))) + len(json.dumps(p.get("messages")))
    u = {"in": chars // 4, "out": int(p.get("max_tokens") or 0),
         "cw": 0, "cr": 0}
    return TB.cost_usd(model, u)


def draft_metrics(pdir: Path, project: str, k: int, text: str, plan: dict,
                  draft: dict) -> dict:
    import write_api as W
    import write_slots as WS
    from pipeline import line_rules as LR
    obj, _w = W._json_reply({"content": [{"type": "text", "text": text}]},
                            "draft") if text else (None, None)
    if not isinstance(obj, dict):
        return {"parses": False}
    slots = plan.get("slots") or []
    lines = [l for l in obj.get("lines") or [] if isinstance(l, dict)]
    schema = W.check_act(obj, k, slots, plan)
    devs = W.slot_deviations(obj, k, slots, pdir)
    mine = WS.slots_for_act(slots, k)
    by_slot = {l.get("slot"): l for l in lines}
    # per-line gate rules against the rest of the draft as it stands
    owner = W.act_of_lines(pdir)
    def act_of(lid):
        v = owner.get(lid, owner.get(str(lid)))
        return v[0] if isinstance(v, (tuple, list)) else v
    others = [l for l in draft.get("lines") or []
              if str(act_of(l.get("id"))) != str(k)]
    lr = []
    for s in mine:
        ln = by_slot.get(s["slot"])
        if not ln or not str(ln.get("narration") or "").strip():
            continue
        view = others + [dict(x, id=f"{x.get('slot')}")
                         for x in lines if x is not ln]
        lr += [f"{s['slot']}: {p}" for p in LR.problems(
            pdir, view, s["slot"], ln["narration"])]
    words = sum(len(str(l.get("narration") or "").split()) for l in lines)
    return {"parses": True, "lines": len(lines), "slots": len(mine),
            "missing": [s["slot"] for s in mine if s["slot"] not in by_slot
                        and s["role"] != "hold"],
            "schema": schema, "deviations": devs, "line_rules": lr,
            "words": words, "by_slot": by_slot, "slot_list": mine}


def review_metrics(text: str) -> dict:
    try:
        import review_api as R
        obj = R.parse_reply(text) if hasattr(R, "parse_reply") else None
    except Exception:
        obj = None
    if obj is None:
        try:
            obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        except Exception:
            return {"parses": False}
    fs = obj.get("findings") if isinstance(obj, dict) else obj
    fs = fs if isinstance(fs, list) else []
    kinds: dict = {}
    for f in fs:
        if isinstance(f, dict):
            kinds[str(f.get("kind"))] = kinds.get(str(f.get("kind")), 0) + 1
    return {"parses": True, "findings": len(fs), "kinds": kinds,
            "items": fs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--act", type=int, default=2)
    ap.add_argument("--variants", default=DEFAULT_VARIANTS)
    ap.add_argument("--what", default="draft,cold-read",
                    help="draft, cold-read (comma list)")
    ap.add_argument("--estimate", action="store_true",
                    help="print the rough cost ceiling and stop")
    a = ap.parse_args(argv)

    import tag_batch as TB
    import write_api as W
    pdir = Path(config.project_dir(a.project))
    plan = json.loads((pdir / "plan.json").read_text(encoding="utf-8-sig"))
    draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    variants = [parse_variant(v) for v in a.variants.split(",") if v.strip()]
    whats = [w.strip() for w in a.what.split(",") if w.strip()]

    reqs = {}
    if "draft" in whats:
        reqs["draft"] = W.act_request(a.project, pdir, a.act,
                                      W.draft_system(pdir),
                                      slots=plan.get("slots"), plan=plan)
    if "cold-read" in whats:
        import review_api as R
        reqs["cold-read"] = R.build_request("cold-read", pdir, draft,
                                            variants[0][0])

    total = 0.0
    for what, p in reqs.items():
        for m, eff in variants:
            c = estimate(p, m) or 0.0
            total += c
            print(f"  {what:<9} {m}{'@' + eff if eff else ''}: <= ${c:.3f}")
    print(f"model_compare: at most ~${total:.2f} for "
          f"{len(reqs) * len(variants)} call(s) (the real cost is lower: "
          f"replies rarely use all of max_tokens)")
    if a.estimate:
        return 0

    client = TB.CLIENT_FACTORY()
    out = pdir / "model_compare"
    out.mkdir(exist_ok=True)
    res: dict = {}
    for what, p in reqs.items():
        for m, eff in variants:
            tag = f"{m.replace('claude-', '')}{'@' + eff if eff else ''}"
            q = with_variant(p, m, eff)
            t0 = time.time()
            try:
                msg = TB.create_message(client, **q)
            except Exception as e:
                print(f"  {what} {tag}: API error {type(e).__name__}: "
                      f"{str(e)[:200]}")
                res[(what, tag)] = {"error": str(e)[:300]}
                continue
            u = TB.usage_of(msg)
            TB.ledger_append(pdir, f"compare:{what}:{tag}", m, u,
                             batch=False)
            text = TB.reply_text(msg)
            (out / f"{what}.act{a.act}.{tag}.txt").write_text(
                text, encoding="utf-8")
            r = (draft_metrics(pdir, a.project, a.act, text, plan, draft)
                 if what == "draft" else review_metrics(text))
            r.update(usd=TB.cost_usd(m, u), secs=round(time.time() - t0),
                     out_tokens=u.get("out"),
                     stop=TB._get(msg, "stop_reason"))
            res[(what, tag)] = r
            print(f"  {what} {tag}: ${r['usd'] or 0:.3f}, {r['secs']}s, "
                  f"stop {r['stop']}")
    report = render(a.project, a.act, res)
    (out / f"act{a.act}.compare.md").write_text(report, encoding="utf-8")
    print(f"model_compare: wrote {out / f'act{a.act}.compare.md'}")
    return 0


def render(project: str, k: int, res: dict) -> str:
    L = [f"# Model compare - {project}, act {k}", ""]
    d = {t: r for (w, t), r in res.items() if w == "draft"}
    if d:
        L += ["## Draft (one act, the real request)", "",
              "| variant | USD | s | out tok | stop | lines/slots | missing | "
              "schema | slot deviations | gate rules | words |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for t, r in d.items():
            if "error" in r or not r.get("parses"):
                L.append(f"| {t} | {r.get('usd', '-')} | | | | "
                         f"{'ERROR ' + r.get('error', '') if 'error' in r else 'does not parse'} "
                         f"| | | | | |")
                continue
            L.append(f"| {t} | {r['usd'] or 0:.3f} | {r['secs']} | "
                     f"{r['out_tokens']} | {r['stop']} | {r['lines']}/"
                     f"{r['slots']} | {len(r['missing'])} | "
                     f"{len(r['schema'])} | {len(r['deviations'])} | "
                     f"{len(r['line_rules'])} | {r['words']} |")
        for t, r in d.items():
            if r.get("parses"):
                L += ["", f"### {t}: what code found", ""]
                L += [f"- {x}" for x in (r["schema"] + r["deviations"]
                                         + r["line_rules"])[:25]] or ["- nothing"]
        ok = [t for t, r in d.items() if r.get("parses")]
        if ok:
            L += ["", "## The lines, slot by slot", ""]
            for s in d[ok[0]]["slot_list"]:
                if s["role"] == "hold":
                    continue
                L.append(f"**{s['slot']}** ({s['role']}, {s['min_words']}-"
                         f"{s['max_words']} w)" + (f" - quote: \"{s['quote']}\""
                                                  if s.get("quote") else ""))
                for t in ok:
                    ln = d[t]["by_slot"].get(s["slot"]) or {}
                    L.append(f"- *{t}*: {ln.get('narration') or '(none)'}")
                L.append("")
    c = {t: r for (w, t), r in res.items() if w == "cold-read"}
    if c:
        L += ["## Cold-read review (the whole draft)", "",
              "| variant | USD | s | findings | by kind |", "|---|---|---|---|---|"]
        for t, r in c.items():
            L.append(f"| {t} | {r.get('usd') or 0:.3f} | {r.get('secs')} | "
                     f"{r.get('findings', 'ERROR')} | {r.get('kinds', '')} |")
        for t, r in c.items():
            L += ["", f"### {t}", ""]
            for f in (r.get("items") or [])[:30]:
                if isinstance(f, dict):
                    L.append(f"- {f.get('kind')} @ {f.get('ids') or f.get('lines')}: "
                             f"{str(f.get('text') or f.get('note') or '')[:200]}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main())
