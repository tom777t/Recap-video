# -*- coding: utf-8 -*-
"""dup_overlap.py - neighbour-overlap check: the P2 blind spot, as a draft-time gate.

The checkpoint-1 review found 8 near-duplicate line pairs (same content, different
words) that every existing gate passed. Identical-text dedupe caught exact copies;
this catches CONTENT overlap between lines within +/- 5 positions of each other.

Known-bad (review, lines 65/66): the "not angry about the shoes" pair, overlap .75.
Known-good: an inventory line followed by its verbatim exhibit quote.

Usage:
    python tools/dup_overlap.py <project>          # check draft.json, exit 1 on hit
"""
from __future__ import annotations
import io, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

WINDOW = 5          # positions either side
FLOOR = 0.50        # content-word overlap ratio that fails
MIN_WORDS = 3       # pairs shorter than this are not meaningful
_QUOTE = re.compile(r'"[^"]*"')
_STOP = set("a an the and or but of to in on at for with her his their its it she he "
            "they them is are was were be been being that this these those there here "
            "as by from into out up down over then so not no yes i you we me my your "
            "our who what which when where how why all any some none one two has have "
            "had do does did will would can could shall should may might must s t "
            "don doesn didn won can just now about after before again very more most "
            "much many few own same too only".split())


def content_words(text: str) -> set:
    t = _QUOTE.sub(" ", str(text or "").lower())
    return {w for w in re.findall(r"[a-z']+", t) if w not in _STOP and len(w) > 1}


def overlap(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def check_pairs(lines: list, window: int = WINDOW, floor: float = FLOOR):
    """[(pos, id, text)] -> list of (id_a, id_b, ratio, shared)."""
    narr = [(i, l.get("id"), str(l.get("narration") or ""))
            for i, l in enumerate(lines) if str(l.get("narration") or "").strip()]
    words = {p: content_words(t) for p, _, t in narr}
    hits = []
    for x in range(len(narr)):
        for y in range(x + 1, min(x + 1 + window, len(narr))):
            pa, ia, _ = narr[x]
            pb, ib, _ = narr[y]
            wa, wb = words[pa], words[pb]
            if min(len(wa), len(wb)) < MIN_WORDS:
                continue
            r = overlap(wa, wb)
            if r >= floor:
                hits.append((ia, ib, round(r, 2), sorted(wa & wb)[:8]))
    return hits


def main(project: str) -> int:
    pdir = config.project_dir(project)
    f = pdir / "draft.json"
    if not f.exists():
        print("no draft.json")
        return 0
    d = json.load(io.open(f, encoding="utf-8"))
    hits = check_pairs(d.get("lines") or [])
    if hits:
        print("[NEIGHBOUR-OVERLAP] %d pair(s) share >= %d%% content words within %d lines:" % (
            len(hits), FLOOR * 100, WINDOW))
        for ia, ib, r, shared in hits:
            print("  lines %s+%s (%.0f%%): %s" % (ia, ib, r * 100, " ".join(shared)))
        return 1
    print("[NEIGHBOUR-OVERLAP] clean: no pair >= %d%% within %d lines" % (FLOOR * 100, WINDOW))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
