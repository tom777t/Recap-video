# -*- coding: utf-8 -*-
"""fix_line.py - fix ONE line by hand after the review stage, the safe way.

    python tools/fix_line.py --project P --line 40 --text "New line." [--note "..."]
    python tools/fix_line.py --project P --line 40 --show
    python tools/fix_line.py --project P --line 109 --claim narration
    python tools/fix_line.py --project P --relabel

When resolve stops with a finding it could not close, the fix is often one
line. Editing draft.json by hand leaves the review artifacts' signatures
stale and the act files out of step (the gates then fail again). This goes
through the same write-back as resolve (write_api.write_back):

  * the new text must fit the line's SLOT - the same rules as every other
    write (word band, a reaction heard as the narrator, no commentary on an
    anchor, the verbatim quote, ...); a misfit is refused and explained
  * draft.json AND the act file are updated; the line is re-signed in every
    review artifact
  * every open reader finding naming the line is closed RESOLVED with
    --note (default: "rewritten by hand: <old> -> <new>")
  * the draft gates run once at the end (same as `recap.py draft`)

--claim narration: the line REPORTS what someone said without showing
them (a minor character not in names.json, or a voice over the listener's
face). Its claim becomes a narration claim with no picture requirement, so
[VOICE-VISUAL] no longer asks for the speaker on screen; the text is kept.
Use it only when that is true of the line - you confirm it at the watch.

--relabel: re-derive the slots from plan.json when the code's layout has
moved on (SLOTS_VERSION), and re-apply the labels code owns (delivery for
intro/outro and the `sad` budget, payload for reactions/loops) to every
line of an already-written draft. Text is not touched, so nothing needs
re-reviewing.

--show prints the line, its slot, what is wrong with it now, its
neighbours and the open findings naming it - read that first.
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--line", type=int)
    ap.add_argument("--relabel", action="store_true")
    ap.add_argument("--text")
    ap.add_argument("--note", default="")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--claim", choices=("narration",),
                    help="make the line a narration claim (no speaker on "
                         "screen required); text unchanged unless --text")
    a = ap.parse_args(argv)

    import write_api as W
    import write_plan as WP
    import write_slots as WS
    pdir = Path(config.project_dir(a.project))
    draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    by_id = {str(l["id"]): l for l in draft["lines"]}
    if a.relabel:
        return _relabel(a.project, pdir, draft, by_id)
    if a.line is None:
        ap.error("--line is required (or --relabel)")
    lid = str(a.line)
    if lid not in by_id:
        print(f"fix_line: line {lid} is not in draft.json")
        return 1
    owner = W.act_of_lines(pdir)
    sl = W.slots_of_lines(pdir, owner).get(lid)
    finds = [f for f in WP.open_findings(pdir, draft) if lid in f["ids"]]
    old = by_id[lid]

    if a.claim and not a.text:
        was = dict(old.get("claim") or {})
        claim = dict(was, type="narration", requires_visual=False)
        claim.pop("subject", None)
        W.write_back(pdir, draft, by_id, owner, {lid: {"claim": claim}},
                     {}, {})
        print(f"fix_line: line {lid} is now a narration claim (was "
              f"{was.get('type')} / {was.get('subject')}). Running the draft "
              f"gates ...")
        rc, errs = W.run_gates(a.project)
        if not errs:
            print("fix_line: draft gates clean")
        else:
            print(f"fix_line: {len(errs)} hard error(s) left:")
            for e in errs[:8]:
                print(f"  - {e[:220]}")
        return 0 if not errs else 2

    if a.show or not a.text:
        ids = [str(l["id"]) for l in draft["lines"]]
        i = ids.index(lid)
        for j in range(max(0, i - 3), min(len(ids), i + 3)):
            ln = by_id[ids[j]]
            mark = ">>" if ids[j] == lid else "  "
            print(f"{mark} [{ids[j]}] ({ln.get('note')}) "
                  f"{ln.get('narration') or '(hold)'}")
        if sl is not None:
            print(f"\nslot: {WS.slot_tag(sl)}")
            now = WS.line_deviations(old, sl)
            print("wrong now: " + ("; ".join(now) if now else "nothing"))
        print(f"\nopen findings naming line {lid}: {len(finds)}")
        for f in finds:
            print(f"  - {f['artifact']}: {f['kind']} @ {','.join(f['ids'])} - "
                  f"{f['text'][:160]}")
        return 0

    text = " ".join(a.text.split())
    new = dict(old, narration=text)
    if sl is not None:
        new = WS.code_labels(new, sl)
        broke = WS.new_deviations(old, new, sl) + \
            WS.unfixed_deviations(old, new, sl)
        if broke:
            print("fix_line: NOT saved - the text does not fit the line's slot:")
            for b in broke:
                print(f"  - {b}")
            print(f"slot: {WS.slot_tag(sl)}")
            return 2
    note = a.note.strip() or (f"rewritten by hand: "
                              f"'{old.get('narration')}' -> '{text}'")
    for i, f in enumerate(finds, 1):
        f["key"] = f.get("key") or f"H{i}"
    reply = {"lines": [{"id": int(lid), "narration": text}],
             "responses": [{"key": f["key"], "status": "RESOLVED",
                            "text": note} for f in finds
                           if not f.get("gate")]}
    changes, entries, rejects = WP.apply_resolution(finds or [
        {"key": "H0", "ids": [lid], "kind": "hand", "artifact": None,
         "gate": True, "text": ""}], reply, by_id)
    if rejects:
        print("fix_line: " + "; ".join(rejects))
    edits = {lid: {f: new[f] for f in ("payload", "delivery")
                   if new.get(f) != old.get(f)}} if sl is not None else {}
    W.write_back(pdir, draft, by_id, owner, edits, changes, entries)
    print(f"fix_line: line {lid} saved; {len(finds)} finding(s) closed "
          f"RESOLVED. Running the draft gates ...")
    rc, errs = W.run_gates(a.project)
    if not errs:
        print("fix_line: draft gates clean")
    else:
        print(f"fix_line: {len(errs)} hard error(s) left:")
        for e in errs[:8]:
            print(f"  - {e[:220]}")
    return 0 if not errs else 2


def _relabel(project: str, pdir: Path, draft: dict, by_id: dict) -> int:
    import write_api as W
    import write_plan as WP
    import write_slots as WS
    plan = json.loads((pdir / "plan.json").read_text(encoding="utf-8-sig"))
    if plan.get("slots_version") != WS.SLOTS_VERSION:
        ab = WP.act_beats(project, W._tool)
        W.save_slots(project, pdir, plan, ab)
        print(f"fix_line: slots re-derived (version "
              f"{plan.get('slots_version', 1)} -> {WS.SLOTS_VERSION})")
    owner = W.act_of_lines(pdir)
    slot_of = W.slots_of_lines(pdir, owner)
    edits, moved = {}, {}
    for lid, sl in slot_of.items():
        old = by_id[lid]
        new = WS.code_labels(old, sl)
        fe = {f: new[f] for f in ("payload", "delivery", "film_intro")
              if f in new and new.get(f) != old.get(f)}
        if fe:
            edits[lid] = fe
            for f, v in fe.items():
                moved[f"{f} {old.get(f)} -> {v}"] = \
                    moved.get(f"{f} {old.get(f)} -> {v}", 0) + 1
    if not edits:
        print("fix_line: every label already matches its slot")
    else:
        W.write_back(pdir, draft, by_id, owner, edits, {}, {})
        print(f"fix_line: {len(edits)} line(s) relabelled:")
        for k, n in sorted(moved.items(), key=lambda x: -x[1]):
            print(f"  - {n} x {k}")
    print("fix_line: running the draft gates ...")
    rc, errs = W.run_gates(project)
    if not errs:
        print("fix_line: draft gates clean")
    else:
        print(f"fix_line: {len(errs)} hard error(s) left:")
        for e in errs[:8]:
            print(f"  - {e[:220]}")
    return 0 if not errs else 2


if __name__ == "__main__":
    sys.exit(main())
