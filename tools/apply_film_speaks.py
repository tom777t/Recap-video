# -*- coding: utf-8 -*-
"""apply_film_speaks.py - put projects/<p>/film_speaks_selection.json into draft.json.

    python tools/apply_film_speaks.py --project <p>
    python tools/apply_film_speaks.py --project <p> --dry-run
    python tools/apply_film_speaks.py --project <p> --by-position

The FILM_SPEAKS stage (.opencode/command/film.md, prompts/film_speaks_select.md)
ends with a selection file: 2-3 spans where the film's own dialogue plays, each
with replacement narration for the line BEFORE (sets it up) and the line AFTER
(reacts). This applies it:

  1. One wordless unit per pick: clip window = the quote's span,
     `film_speaks_seconds` = its length, plus criterion / reason / quote /
     measured margin. A unit already in the draft for the same span is updated,
     never duplicated, so re-running is safe.
  2. The HOST line's window must END where the quote begins. The quote
     usually sits inside the host's window, and leaving both on the same
     footage trips [FOOTAGE-REUSE]. If trimming leaves the host too short for
     its narration (the render's own capacity contract, preflight.budget_words)
     its window is extended BACKWARDS, never into another line's footage. A
     line that starts inside the quote is moved to start where it ends, and
     extended forwards the same way.
  1b. Lines strictly between the named before and after lines are the ones
     the quote REPLACES (they paraphrase it, or sit on its footage): they are
     cut, and the unit carries their slots (`film_speaks_covers`) so the
     draft still conserves every planned line.
  3. The before/after replacement texts are applied to the unit's actual
     neighbours. The selection names them by line id; when that id is NOT the
     neighbour (the draft was rewritten after the selection was made) the text
     is NOT applied - pasting it onto whichever line now sits there would put
     a sentence written for another line into the film. --by-position applies
     it to the neighbour anyway, and says so.

Nothing film-specific lives here. Exit 0 = every pick applied in full; 1 = a
finding (printed) that needs a human; 2 = bad input.
Validate afterwards with `python recap.py draft --project <p>`.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SPAN_TOL = 0.05          # seconds: same span
MAX_EXTEND = 120.0       # never search further than this for room
MAX_CUT = 6              # lines a quote may replace between its neighbours


def _cut_between(lines: list, unit: dict, pk: dict) -> tuple:
    """The lines the quote REPLACES: those strictly between the selection's
    named before and after lines (Lost in the Stars: "the quote also
    replaces lines 167-171, which paraphrase it ... so those lines must be
    cut" - the applier had no way to cut, shrank lines 168-171 to negative
    windows over the quote, and refused both texts because the unit's
    neighbours were not the named ones). Only when both named lines exist,
    the before line comes first, at most MAX_CUT lie between, none of them is
    another unit, and every one starts inside the before line .. the end of
    the after line. Returns (cut lines, why-not or "")."""
    ids = {str(ln.get("id")): i for i, ln in enumerate(lines)}
    b = str(((pk.get("before") or {}).get("line_id")))
    a = str(((pk.get("after") or {}).get("line_id")))
    if b not in ids or a not in ids:
        return [], ""
    bi, ai = ids[b], ids[a]
    if ai <= bi + 1:
        return [], ""
    mid = [ln for ln in lines[bi + 1:ai] if ln is not unit]
    if not mid:
        return [], ""
    if len(mid) > MAX_CUT:
        return [], (f"{len(mid)} lines lie between the named before ({b}) and "
                    f"after ({a}) lines - more than {MAX_CUT}, not cut")
    wb, wa, wu = _win(lines[bi]), _win(lines[ai]), _win(unit)
    if not (wb and wa and wu):
        return [], ""
    # the named pair must frame THIS quote in the film, closely: a stale
    # selection naming lines from an older draft cuts nothing
    if not (wb[0] - 1e-6 <= wu[0] and wu[1] <= wa[1] + 1e-6) or \
            (wa[0] - wb[1]) > (wu[1] - wu[0]) + 30.0:
        return [], ""
    for ln in mid:
        if ln.get("film_speaks_seconds") is not None:
            return [], f"line {ln.get('id')} between them is another unit"
        w = _win(ln)
        if w and not (wb[1] - 1e-3 <= w[0] and w[1] <= wa[0] + 1e-3):
            return [], (f"line {ln.get('id')} between them is not between "
                        f"them in the film")
    return mid, ""


def _ts(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    return f"{h:02d}:{m:02d}:{sec % 60:06.3f}"


def _win(ln: dict):
    from pipeline.draft import parse_ts
    cs, ce = ln.get("clip_start"), ln.get("clip_end")
    if not cs or not ce:
        return None
    try:
        return parse_ts(cs), parse_ts(ce)
    except Exception:
        return None


def _words(ln: dict) -> int:
    return len(str(ln.get("narration") or "").split())


def _fits(ln: dict, a: float, b: float) -> bool:
    """Does the line's narration fit [a, b) under the render's contract?"""
    from pipeline.preflight import budget_words
    if ln.get("film_speaks_seconds") is not None:
        return b - a + 1e-6 >= float(ln["film_speaks_seconds"])
    if ln.get("narration_silence_seconds") is not None:
        return b - a + 1e-6 >= float(ln["narration_silence_seconds"])
    n = _words(ln)
    if n == 0:
        return b > a
    return budget_words(b - a, str(ln.get("delivery") or "normal")) >= n


def _need(ln: dict, a_fixed: float | None, b_fixed: float | None,
          a: float, b: float) -> float | None:
    """Smallest window length that fits, growing away from the fixed edge."""
    w = b - a
    step = 0.05
    while w <= MAX_EXTEND:
        if _fits(ln, b - w, b) if a_fixed is None else _fits(ln, a, a + w):
            return w
        w += step
    return None


def _others(lines, skip_ids):
    out = []
    for ln in lines:
        if ln.get("id") in skip_ids:
            continue
        w = _win(ln)
        if w:
            out.append((w[0], w[1], ln.get("id")))
    for ln in lines:
        if ln.get("id") in skip_ids:
            continue
        for seg in ln.get("montage") or []:
            if isinstance(seg, dict):
                w = _win(seg)
                if w:
                    out.append((w[0], w[1], ln.get("id")))
    return out


def apply(draft: dict, selection: dict, by_position: bool = False) -> tuple:
    """Apply in place. Returns (actions, findings) as lists of strings."""
    lines = draft.get("lines")
    if not isinstance(lines, list):
        raise ValueError("draft.json has no 'lines' list")
    picks = selection.get("selected")
    if not isinstance(picks, list):
        raise ValueError("film_speaks_selection.json has no 'selected' list")
    actions, findings = [], []
    next_id = max([int(ln["id"]) for ln in lines
                   if isinstance(ln.get("id"), int)] or [0]) + 1

    for k, pk in enumerate(picks, 1):
        try:
            start, end = float(pk["start"]), float(pk["end"])
            secs = float(pk.get("seconds") or (end - start))
        except (KeyError, TypeError, ValueError) as e:
            findings.append(f"pick {k}: no usable start/end ({e}) - skipped")
            continue
        if end <= start:
            findings.append(f"pick {k}: end {end} <= start {start} - skipped")
            continue
        tag = f"pick {k} ({_ts(start)})"

        # ---- 1. the unit -------------------------------------------------
        unit = None
        for ln in lines:
            w = _win(ln)
            if (ln.get("film_speaks_seconds") is not None and w
                    and abs(w[0] - start) <= SPAN_TOL):
                unit = ln
                break
        if unit is None:
            # place it after the line whose footage it was cut from (the host),
            # else after the last line that starts before it in the film
            host_i, best = None, None
            for i, ln in enumerate(lines):
                w = _win(ln)
                if not w or ln.get("film_speaks_seconds") is not None:
                    continue
                if w[0] < start - 1e-6 and (best is None or w[0] > best):
                    best, host_i = w[0], i
            src = lines[host_i] if host_i is not None else {}
            unit = {"id": next_id, "note": src.get("note"),
                    "clip_start": _ts(start), "clip_end": _ts(end),
                    "narration": "",
                    "delivery": src.get("delivery") or "normal",
                    "payload": src.get("payload") or "stake"}
            next_id += 1
            pos = (host_i + 1) if host_i is not None else len(lines)
            lines.insert(pos, unit)
            actions.append(f"{tag}: added unit line {unit['id']} "
                           f"{_ts(start)}-{_ts(end)} ({secs:.2f}s)")
        else:
            uw = _win(unit)
            unit["clip_start"] = _ts(start)
            if uw[1] < end - 1e-6:
                unit["clip_end"] = _ts(end)
            actions.append(f"{tag}: unit line {unit['id']} already in the "
                           f"draft - updated, not duplicated")
        unit["narration"] = ""
        unit["film_speaks_seconds"] = round(secs, 2)
        for src_k, dst_k in (("criterion", "film_speaks_criterion"),
                             ("justification", "film_speaks_reason"),
                             ("quote", "film_speaks_quote"),
                             ("audio_margin_db", "film_speaks_audio_margin_db")):
            if pk.get(src_k) is not None:
                unit[dst_k] = pk[src_k]
        u_a, u_b = _win(unit)

        # ---- 1b. the lines the quote replaces -----------------------------
        cut, why_not = _cut_between(lines, unit, pk)
        if why_not:
            findings.append(f"{tag}: {why_not}")
        if cut:
            covers = list(unit.get("film_speaks_covers") or [])
            for ln in cut:
                for sl in [ln.get("slot")] + [
                        x.get("slot") for x in (ln.get("parts") or [])[1:]
                        if isinstance(x, dict)]:
                    if sl and sl not in covers:
                        covers.append(sl)
                lines.remove(ln)
            if covers:
                unit["film_speaks_covers"] = covers
            ui0 = next(i for i, ln in enumerate(lines) if ln is unit)
            bi = next(i for i, ln in enumerate(lines) if str(ln.get("id"))
                      == str(pk["before"]["line_id"]))
            if ui0 != bi + 1:                    # sit between the named pair
                lines.remove(unit)
                lines.insert(bi + 1, unit)
            actions.append(
                f"{tag}: line(s) {', '.join(str(ln.get('id')) for ln in cut)}"
                f" cut - the quote replaces them (the selection named "
                f"{pk['before']['line_id']} before, {pk['after']['line_id']} "
                f"after); their slot(s) {covers} are said by the unit")

        # ---- 3. neighbour texts (before windows: capacity uses new text) --
        ui = next(i for i, ln in enumerate(lines) if ln is unit)
        retexted: set = set()
        for side, j in (("before", ui - 1), ("after", ui + 1)):
            spec = pk.get(side)
            if not isinstance(spec, dict) or not spec.get("new_narration"):
                continue
            nb = lines[j] if 0 <= j < len(lines) else None
            want = spec.get("line_id")
            if nb is None:
                findings.append(f"{tag}: there is no line {side} the unit; "
                                f"the {side} text was not applied")
                continue
            if nb.get("id") != want and not by_position:
                findings.append(
                    f"{tag}: the selection's {side} line is {want}, but the "
                    f"line {side} the unit is {nb.get('id')} - the draft "
                    f"changed after the selection was written. Text NOT "
                    f"applied; re-run the selection, or pass --by-position")
                continue
            old = nb.get("narration")
            nb["narration"] = str(spec["new_narration"]).strip()
            retexted.add(id(nb))
            note = ("" if nb.get("id") == want else
                    f" (selection named line {want}; applied by position)")
            actions.append(f"{tag}: line {nb.get('id')} ({side}) narration "
                           f"replaced, {len(str(old or '').split())} -> "
                           f"{_words(nb)} words{note}")

        # ---- 2. clear the quote's footage --------------------------------
        for ln in lines:
            if ln is unit:
                continue
            w = _win(ln)
            if not w:
                continue
            a, b = w
            overlaps = b > u_a + 1e-6 and a < u_b - 1e-6
            if not overlaps and id(ln) not in retexted:
                continue
            if overlaps and a >= u_a - 1e-6 and b <= u_b + 1e-6:
                findings.append(
                    f"{tag}: line {ln.get('id')} lies wholly inside the "
                    f"quote's footage ({_ts(a)}-{_ts(b)}) - name it between "
                    f"the before and after lines so it is cut, or drop the "
                    f"pick")
                continue
            if overlaps and a < u_a - 1e-6:
                b, side = u_a, "back"                    # host: end at quote
            elif overlaps:
                a, side = u_b, "fwd"                     # starts inside quote
            else:
                side = "back" if b <= u_a + 1e-6 else "fwd"
            occupied = _others(lines, {ln.get("id"), unit.get("id")})
            if not _fits(ln, a, b):
                if side == "back":
                    floor = max([ob for oa, ob, _i in occupied
                                 if ob <= a + 1e-6] or [0.0])
                    need = _need(ln, None, b, a, b)
                    a = max(floor, b - need) if need else floor
                else:
                    ceil = min([oa for oa, ob, _i in occupied
                                if oa >= b - 1e-6] or [b + MAX_EXTEND])
                    need = _need(ln, a, None, a, b)
                    b = min(ceil, a + need) if need else ceil
            if (a, b) != w:
                ln["clip_start"], ln["clip_end"] = _ts(a), _ts(b)
                actions.append(f"{tag}: line {ln.get('id')} window "
                               f"{_ts(w[0])}-{_ts(w[1])} -> {_ts(a)}-{_ts(b)}")
            if not _fits(ln, a, b):
                findings.append(
                    f"{tag}: line {ln.get('id')} ({_words(ln)} words) does "
                    f"not fit {_ts(a)}-{_ts(b)} ({b - a:.2f}s) even after "
                    f"extending to its neighbours - trim the text or re-bind")
    return actions, findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--project", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would change, write nothing")
    ap.add_argument("--by-position", action="store_true",
                    help="apply before/after texts to the unit's neighbours "
                         "even when the selection names other line ids")
    a = ap.parse_args(argv)
    import config
    pdir = Path(config.project_dir(a.project))
    sp, dp = pdir / "film_speaks_selection.json", pdir / "draft.json"
    try:
        sel = json.loads(sp.read_text(encoding="utf-8-sig"))
        draft = json.loads(dp.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        print(f"apply_film_speaks: cannot read input: {e}")
        return 2
    try:
        actions, findings = apply(draft, sel, by_position=a.by_position)
    except ValueError as e:
        print(f"apply_film_speaks: {e}")
        return 2
    for x in actions:
        print(f"  {x}")
    for x in findings:
        print(f"  FINDING: {x}")
    if not a.dry_run:
        bak = pdir / "draft.pre_film_speaks.json"
        shutil.copy2(dp, bak)
        tmp = pdir / "draft.json.tmp"
        tmp.write_text(json.dumps(draft, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, dp)
        print(f"wrote {dp} (previous version: {bak.name})")
    print(f"apply_film_speaks: {len(actions)} change(s), "
          f"{len(findings)} finding(s)"
          + (" - dry run, nothing written" if a.dry_run else "")
          + ". Validate: python recap.py draft --project " + a.project)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
