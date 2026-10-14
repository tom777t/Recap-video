# -*- coding: utf-8 -*-
"""
reviewed.py - findings a human has looked at and deliberately kept.

Shared by draft.py (VISUAL-REPEAT) and catalogue.py (the DEPTH-* family), so an
exception is declared once, in the project, in one format.

Lives in the PROJECT (`reviewed_exceptions.md`), never in a gate's code, so the
exception is visible to whoever opens that project instead of buried in a
threshold somebody has to go hunting for.

Format - a fenced ```reviewed-exceptions block, one per line, four fields:

    GATE | finding-key | YYYY-MM-DD | why it was kept

The key names the EXACT FINDING, not the gate. `VISUAL-REPEAT | *` is refused:
a blanket per-gate mute is how a gate dies quietly, and the point of this file
is that it cannot happen silently.

An entry missing a date or a reason is REFUSED - "reviewed" has to mean somebody
actually looked, on a day, for a stated reason.
"""
from __future__ import annotations
import re

_BLOCK = re.compile(r"```reviewed-exceptions\s*\n(.*?)```", re.S)
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BLANKET = {"*", "all", "any"}


def load(pdir) -> tuple[dict, list]:
    """Return ({(GATE, key): (date, reason)}, [malformed-entry messages])."""
    out: dict = {}
    bad: list = []
    fp = pdir / "reviewed_exceptions.md"
    if not fp.exists():
        return out, bad
    try:
        txt = fp.read_text(encoding="utf-8-sig")
    except Exception as e:                              # pragma: no cover
        return out, [f"unreadable: {e}"]
    m = _BLOCK.search(txt)
    if not m:
        return out, bad
    for raw in m.group(1).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4 or not all(parts[:4]):
            bad.append(f"needs 'GATE | finding | YYYY-MM-DD | reason': {line[:70]}")
            continue
        gate, key, date = parts[0], parts[1], parts[2]
        reason = " | ".join(parts[3:])
        if key.lower() in _BLANKET:
            bad.append(f"blanket exception refused (name the finding): {line[:70]}")
            continue
        if not _DATE.match(date):
            bad.append(f"bad date, want YYYY-MM-DD: {line[:70]}")
            continue
        out[(gate.upper(), key)] = (date, reason)
    return out, bad


def stale(declared: dict, hit: set, gates: tuple) -> list:
    """Entries for `gates` that were declared but never matched a finding.

    A stale entry is how a gate dies quietly in the other direction: the finding
    goes away, the note stays, and it silently covers the next one.
    """
    return [(g, k, d, r) for (g, k), (d, r) in declared.items()
            if g in gates and (g, k) not in hit]
