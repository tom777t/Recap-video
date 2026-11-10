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

--not-dialogue: the line's QUOTE is not something a character says (a
song over the scene, a PA, a TV - Whisper writes them all down as speech).
The quote is recorded in not_dialogue.json (pipeline/sung.py), the slots are
re-derived so that beat's quote slot takes another real line or becomes an
action slot, and the line's NEW slot is printed. The text is not changed -
write the new line with --text next (it is checked against the new slot).

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
    ap.add_argument("--not-dialogue", action="store_true",
                    help="the line's quote is a song / PA / TV, not a "
                         "character: never quote it; re-derive the slots")
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

    if a.not_dialogue:
        if sl is None or not sl.get("quote"):
            print(f"fix_line: line {lid}'s slot carries no quote - nothing "
                  f"to mark (see --show)")
            return 1
        from pipeline import sung
        q = sl["quote"]
        nd = pdir / "not_dialogue.json"
        was = nd.read_bytes() if nd.exists() else None
        added = sung.add_by_hand(pdir, q, a.note.strip() or
                                 f"line {lid}: not dialogue (marked by hand)")
        rc = _rederive(a.project, pdir, force=True, owner=owner)
        sl2 = W.slots_of_lines(pdir, owner).get(lid) if not rc else None
        if rc or sl2 is None or sung._norm(sl2.get("quote") or "") == \
                sung._norm(q):
            # nothing half-done: the record goes back as it was
            if was is None:
                nd.unlink(missing_ok=True)
            else:
                nd.write_bytes(was)
            sung._CACHE.clear()
            if not rc:
                print(f"fix_line: NOT done - after re-deriving, line {lid}'s "
                      f"slot still quotes \"{q}\" (the record did not take)")
            return 1
        print(f"fix_line: \"{q}\" "
              + ("recorded" if added else "was already recorded")
              + " in not_dialogue.json - it is never quoted again")
        now = WS.line_deviations(old, sl2)
        if sung.quoted_not_dialogue(pdir, old.get("narration") or ""):
            now.append("the line still quotes it - rewrite it with --text")
        print(f"line {lid} now: {WS.slot_tag(sl2)}")
        print("wrong now: " + ("; ".join(now) if now else "nothing"))
        print(f"next: python tools/fix_line.py --project {a.project} "
              f"--line {lid} --text \"...\"  (a line for that slot, without "
              f"the old quote)")
        return 0

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
        _speech_around(pdir, old)
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
    # the draft gates that judge one line, BEFORE anything is written
    from pipeline import line_rules as LR
    lr = LR.problems(pdir, draft["lines"], lid, text)
    if lr:
        print("fix_line: NOT saved - the text would fail a draft gate:")
        for b in lr:
            print(f"  - {b}")
        return 2
    print("fix_line: checking the draft gates before saving ...")
    _rc0, before = W.run_gates(a.project)
    snap = _snapshot(pdir)
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
    rc, errs = W.run_gates(a.project)
    broke = _new_errors(before, errs, lid)
    if broke:
        # every gate, not only the per-line ones: the change is undone,
        # byte for byte, and nothing is left half-saved
        _restore(snap)
        print(f"fix_line: NOT saved - with this text the draft gates find "
              f"{len(broke)} new error(s):")
        for e in broke[:6]:
            print(f"  - {e[:220]}")
        print("line, act file and review artifacts are as they were")
        return 2
    print(f"fix_line: line {lid} saved; {len(finds)} finding(s) closed "
          f"RESOLVED.")
    if not errs:
        print("fix_line: draft gates clean")
    else:
        print(f"fix_line: {len(errs)} hard error(s) left:")
        for e in errs[:8]:
            print(f"  - {e[:220]}")
    return 0 if not errs else 2


def _snapshot(pdir: Path) -> dict:
    """The bytes of every file write_api.write_back may change."""
    import write_plan as WP
    files = [pdir / "draft.json"] + sorted((pdir / "draft.json.d").glob(
        "act*.json")) + [pdir / a for a in WP.ARTIFACTS]
    return {f: (f.read_bytes() if f.exists() else None) for f in files}


def _restore(snap: dict) -> None:
    for f, b in snap.items():
        if b is None:
            f.unlink(missing_ok=True)
        else:
            f.write_bytes(b)


def _err_key(e: str) -> str:
    import re
    return re.sub(r"\d+(?:\.\d+)?", "#", e)


def _new_errors(before: list, after: list, lid: str) -> list:
    """Hard errors the change brought: not there before (numbers aside), and
    naming this line - or naming no line at all (a draft-wide one)."""
    import write_api as W
    had = {_err_key(e) for e in before}
    out = []
    for e in after:
        if _err_key(e) in had:
            continue
        ids = {str(i) for i in W.finding_ids(e)}
        if not ids or str(lid) in ids:
            out.append(e)
    return out


SPEECH_AROUND = 90.0        # seconds either side of the line's window


def _speech_around(pdir: Path, ln: dict) -> None:
    """The transcript around the line, with what pipeline/sung.py says of
    each segment - so a reader can see a song the rules did not catch (and
    mark it with --not-dialogue)."""
    import write_slots as WS
    from pipeline import sung
    try:
        a, z = WS._pt(ln.get("clip_start")), WS._pt(ln.get("clip_end"))
    except Exception:
        return
    try:
        segs = json.loads((pdir / "transcript.json").read_text(
            encoding="utf-8-sig")).get("segments") or []
    except (OSError, ValueError):
        return
    near = [x for x in segs if isinstance(x.get("start"), (int, float))
            and a - SPEECH_AROUND <= float(x["start"]) <= z + SPEECH_AROUND]
    print(f"\nspeech around the line ({a - SPEECH_AROUND:.0f}-"
          f"{z + SPEECH_AROUND:.0f}s; >> = inside its window; "
          f"[...] = not dialogue):")
    for x in near[:40]:
        t0 = float(x["start"])
        why = sung.reason(pdir, t0, str(x.get("text") or ""))
        print(f"  {'>>' if a <= t0 < z else '  '} {t0:7.1f}s "
              + (f"[{why}] " if why else "")
              + str(x.get("text") or "").strip()[:100])


def _rederive(project: str, pdir: Path, force: bool = False,
              owner: dict | None = None) -> int:
    """Re-derive plan.json's slots when the code's layout moved on (or when
    forced: an input of the layout changed, e.g. not_dialogue.json). 0 = ok;
    1 = not done (said why; plan.json untouched).

    Conserving: the lines of a written draft are bound to slots by id, so a
    re-derive that would move any slot to another beat, or add / drop one,
    is REFUSED - not warned about (AGENTS.md: a drop or a move at a stage
    boundary is a hard error). A slot whose role or quote changed is listed
    with the line that owns it."""
    import write_api as W
    import write_plan as WP
    import write_slots as WS
    plan = json.loads((pdir / "plan.json").read_text(encoding="utf-8-sig"))
    if not force and plan.get("slots_version") == WS.SLOTS_VERSION:
        return 0
    was = plan.get("slots_version", 1)
    old = {x.get("slot"): x for x in plan.get("slots") or []}
    try:
        ab = WP.act_beats(project, W._tool)
        r = WS.derive_slots(plan, project, pdir, ab)
    except Exception as e:
        print(f"fix_line: slots could NOT be re-derived ({type(e).__name__}: "
              f"{e}); nothing changed")
        return 1
    new = {x.get("slot"): x for x in r["slots"]}
    moved = [k for k in set(old) | set(new)
             if (old.get(k) or {}).get("beat") != (new.get(k) or {}).get("beat")]
    if old and moved:
        print(f"fix_line: NOT re-derived - {len(moved)} slot(s) would move, "
              f"appear or vanish ({sorted(moved, key=str)[:8]}); the written "
              f"lines are bound to the old ones. plan.json is unchanged.")
        return 1
    owner = owner if owner is not None else W.act_of_lines(pdir)
    line_of = {}
    for lid, sl in W.slots_of_lines(pdir, owner).items():
        line_of[sl.get("slot")] = lid
    changed = [k for k in new if k in old and (
        old[k].get("role"), old[k].get("quote")) != (
        new[k].get("role"), new[k].get("quote"))]
    W.save_slots(project, pdir, plan, ab, r)
    print(f"fix_line: slots re-derived (version {was} -> "
          f"{WS.SLOTS_VERSION})")
    for k in changed:
        print(f"  - line {line_of.get(k, '?')} ({k}): "
              f"{old[k].get('role')} -> {new[k].get('role')}"
              + (f", quote now \"{new[k].get('quote')}\""
                 if new[k].get("quote") != old[k].get("quote") else ""))
    return 0


def _relabel(project: str, pdir: Path, draft: dict, by_id: dict) -> int:
    import write_api as W
    import write_slots as WS
    if _rederive(project, pdir):
        return 1
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
