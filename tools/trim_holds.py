# -*- coding: utf-8 -*-
"""trim_holds.py - turn a written draft's extra holds into short breaths.

    python tools/trim_holds.py --project P            # show what would change
    python tools/trim_holds.py --project P --apply    # change it

A draft laid out before SLOTS_VERSION 21 can carry many 5 s holds (Lost in
the Stars: 32, 2.6 min of silence, rendered at 21.7 min). The layout now
keeps only RECAP_HOLDS_MAX full silences - the ones after a reveal lands,
then on an anchor / peak - and makes the rest RECAP_BREATH_SEC breaths that
still show their footage (write_slots.breath_holds). This applies the SAME
choice to a written draft, whose slots cannot be re-derived without moving
its lines: each breath's line and slot get the short length, in draft.json,
the act file and plan.json together (so resolve's hold sync keeps them).
No narration changes, no audio is re-made.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402


def plan_breaths(project: str, pdir: Path) -> list:
    """[(line id, slot, old seconds, new seconds)] for the holds that become
    breaths."""
    import write_api as W
    import write_slots as WS
    plan = json.loads((pdir / "plan.json").read_text(encoding="utf-8-sig"))
    slots = plan.get("slots") or []
    work = []
    for x in slots:
        y = dict(x)
        y.pop("breath", None)
        try:
            y["a"] = WS._pt(x["clip_start"]) if x.get("clip_start") else None
        except Exception:
            y["a"] = None
        work.append(y)
    WS.breath_holds(work, WS._landings(project))
    owner = W.act_of_lines(pdir)
    line_of = {sl["slot"]: lid for lid, sl in
               W.slots_of_lines(pdir, owner).items()}
    draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    by_id = {str(l["id"]): l for l in draft["lines"]}
    out = []
    for x in work:
        if not x.get("breath"):
            continue
        lid = line_of.get(x["slot"])
        ln = by_id.get(lid) if lid else None
        if ln is None or str(ln.get("narration") or "").strip():
            continue
        old = float(ln.get("narration_silence_seconds") or 0)
        if old > WS.BREATH_SEC + 0.01:
            out.append((lid, x["slot"], old, WS.BREATH_SEC))
    return out


def apply(project: str, pdir: Path, todo: list) -> None:
    import write_api as W
    import write_slots as WS
    plan = json.loads((pdir / "plan.json").read_text(encoding="utf-8-sig"))
    draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    by_id = {str(l["id"]): l for l in draft["lines"]}
    owner = W.act_of_lines(pdir)
    edits = {}
    by_slot = {x["slot"]: x for x in plan.get("slots") or []}
    for lid, slot, _old, new in todo:
        a = WS._pt(by_id[lid]["clip_start"])
        end = WS._ts(a + new)
        edits[lid] = {"narration_silence_seconds": new, "clip_end": end}
        sl = by_slot.get(slot)
        if sl is not None:
            sl["hold"] = new
            sl["clip_end"] = WS._ts(WS._pt(sl["clip_start"]) + new)
            sl["breath"] = True
    (pdir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False,
                                               indent=1), encoding="utf-8")
    W.write_back(pdir, draft, by_id, owner, edits, {}, {})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    pdir = Path(config.project_dir(a.project))
    todo = plan_breaths(a.project, pdir)
    saved = sum(o - n for _l, _s, o, n in todo)
    for lid, slot, o, n in todo:
        print(f"  line {lid} ({slot}): hold {o:.1f}s -> breath {n:.1f}s")
    print(f"trim_holds: {len(todo)} hold(s) -> breaths, {saved:.0f}s "
          f"({saved / 60:.1f} min) shorter")
    if a.apply and todo:
        apply(a.project, pdir, todo)
        print("trim_holds: written to draft.json, the act files and plan.json")
    elif todo:
        print("trim_holds: nothing written - add --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
