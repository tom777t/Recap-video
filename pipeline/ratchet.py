# -*- coding: utf-8 -*-
"""
ratchet.py - declared facts may move only TOWARD strictness.

WHY A RATCHET AND NOT A LOCK
----------------------------
The A11 fix pinned `target_minutes` with an equality check, and that worked
because tier is a scalar that should NEVER change after it is declared. Three
other self-certifying inputs were examined on 2026-09-05 and none has that
property - all three should legitimately GROW:

    reveal-map aliases   adding an alias makes the gate stricter
    set-piece ranges     widening a range measures more film
    the beat map         Bad Genius gained a beat and corrected seven
                         timestamps during cataloguing, all toward truth

An equality check would have fired on all eight Bad Genius corrections, which
is the "permanently red project" failure that trains people to ignore the
runner. So the instrument is directional: movement that makes a gate STRICTER
is free and silent; movement that makes it LOOSER is printed and named.

LOUD, NOT FATAL
---------------
A loosening is not proof of gaming - sometimes a range really was too wide, or
an alias really was wrong. Findings print and are named; they do not fail the
project. `reviewed_exceptions.md` is the escape hatch, keyed per finding.

This module is PURE: it takes already-parsed data and returns findings, so it
has no import relationship with the parsers in draft.py.
"""
from __future__ import annotations


def snapshot(beats: int, reveals: list, set_pieces: list) -> dict:
    """Capture the strictness-relevant facts. `reveals` / `set_pieces` are the
    dicts produced by draft.parse_reveal_map / draft.parse_set_pieces."""
    return {
        "beats": int(beats or 0),
        "reveals": {
            r["id"]: {"land_sec": r.get("land_sec"),
                      "holds": sorted({h.strip().lower()
                                       for h in (r.get("holds") or []) if h.strip()})}
            for r in (reveals or []) if r.get("id")
        },
        "set_pieces": {
            s["id"]: {"start": s.get("start_sec"), "end": s.get("end_sec"),
                      "keep": bool(s.get("keep"))}
            for s in (set_pieces or []) if s.get("id")
        },
    }


def compare(pinned: dict, current: dict) -> list:
    """Return [(key, message)] for every LOOSENING. Silent on strictening.

    `key` is the exact finding, for reviewed_exceptions.md - never the gate.
    """
    out = []
    if not pinned:
        return out

    # ---- DEPTH-*: the denominator ---------------------------------------
    # Only SHRINKAGE matters. Merging beats inflates shots-per-beat and
    # shrinks the DEPTH-UNDER denominator. Growth and retiming are free -
    # that is the Bad Genius regression case.
    pb, cb = pinned.get("beats", 0), current.get("beats", 0)
    if pb and cb < pb:
        out.append(("beats", f"beat count fell {pb} -> {cb}. Fewer beats is a "
                             f"smaller DEPTH-* denominator and a higher "
                             f"shots-per-beat average. Growth and retiming are "
                             f"free; shrinkage is not."))

    # ---- reveal-map: aliases and landing --------------------------------
    pr, cr = pinned.get("reveals", {}), current.get("reveals", {})
    for rid, p in pr.items():
        c = cr.get(rid)
        if c is None:
            out.append((f"reveal:{rid}",
                        f"reveal '{rid}' was removed from the reveal-map. "
                        f"It is no longer protected at all."))
            continue
        gone = sorted(set(p.get("holds") or []) - set(c.get("holds") or []))
        if gone:
            out.append((f"reveal:{rid}:holds",
                        f"reveal '{rid}' lost {len(gone)} alias(es): "
                        f"{', '.join(gone[:6])}"
                        + (" ..." if len(gone) > 6 else "")
                        + ". Fewer aliases is a weaker scan."))
        pl, cl = p.get("land_sec"), c.get("land_sec")
        if pl is not None and cl is not None and cl > pl:
            out.append((f"reveal:{rid}:land",
                        f"reveal '{rid}' landing moved LATER "
                        f"({pl:.0f}s -> {cl:.0f}s). More of the film is now "
                        f"outside the protected window. Earlier is free."))

    # ---- set-pieces: ranges and keep/drop -------------------------------
    ps, cs = pinned.get("set_pieces", {}), current.get("set_pieces", {})
    for sid, p in ps.items():
        c = cs.get(sid)
        if c is None:
            out.append((f"setpiece:{sid}",
                        f"set-piece '{sid}' was removed. It is no longer "
                        f"measured."))
            continue
        if p.get("keep") and not c.get("keep"):
            out.append((f"setpiece:{sid}:keep",
                        f"set-piece '{sid}' flipped keep -> drop. Dropped rows "
                        f"are recorded but never measured."))
        a0, b0 = p.get("start"), p.get("end")
        a1, b1 = c.get("start"), c.get("end")
        if None not in (a0, b0, a1, b1) and (a1 > a0 or b1 < b0):
            out.append((f"setpiece:{sid}:range",
                        f"set-piece '{sid}' narrowed "
                        f"({a0:.0f}-{b0:.0f}s -> {a1:.0f}-{b1:.0f}s). "
                        f"A shorter range has fewer gaps to find. Widening "
                        f"is free."))
    return out
