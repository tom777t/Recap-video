# -*- coding: utf-8 -*-
"""anchor.py - show the moment a line talks about, while it talks about it.

THE DEFECT. A line's window (clip_start..clip_end) is the stretch of film it
MAY use. The render plays the window from clip_start for as long as the
narration needs (lead + voice + gap), and the rest of the window never
reaches the screen. The median window is about 1.85x its narration, so the
second half of most windows is cut. RULE A3 asks the writer to put
clip_start ON the narrated moment, and the writer often doesn't.

Measured on the two finished renders (owner's complaint: "the words come
before the action, or the action before the words"):
    doublelife2023  12 of 18 lines that QUOTE dialogue showed footage that
                    does not contain the quoted moment
    furious72015     8 of 16
In each case the quoted line is spoken 5-17 s into the window, after the
part that is shown has ended.

THE FIX. The transcript says exactly when a quoted or paraphrased line is
spoken, so the anchor needs no model and no guess:
  - quote:      the narration quotes a line ("...") and a transcript segment
                in or near the window matches it closely;
  - paraphrase: the narration shares >= PARA_MIN_WORDS content words with
                one segment inside the window ("the street always wins").
The shown part is then placed so that this moment lands in the first third
of the narration. It never moves outside the line's own window, never back
into footage the previous line already showed, and never forward past the
start of the next line's window. A moving start does not change which shot
hosts the line, so censor, exposure and silence flags still resolve the way
they did before.

An anchor that lies OUTSIDE the window is not moved, because reaching it would
cross into other shots. It is reported instead, so the line can be rebound at
the write stage. Silence would hide the mismatch, so this is never silent.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

# A paraphrase anchor needs this many shared content words (len >= 4, not a
# stopword). At 2, a sample of 22 matches on furious72015 was checked by hand:
# 21 were the line the narration described ("That night, Dom says the street
# always wins." -> "Thing about street fights, the street always wins.").
PARA_MIN_WORDS = 2
QUOTE_MIN_RATIO = 0.6       # difflib ratio for a quote match
QUOTE_SEARCH_PAD = 15.0     # look this far outside the window for a quote
SAY_AT = 0.30               # land the moment ~30% into the spoken narration

_STOP = set("""that this with from have they them their what when where which
there then than will would could should into about after before over just
your youre were been being does didnt dont cant wont only also even more most
very much some such each every other here back down still while because says
said tells told asks asked gets goes going""".split())


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def _content(s: str) -> set:
    return {w for w in _norm(s).split() if len(w) >= 4 and w not in _STOP}


def load_segments(pdir: Path) -> list:
    """transcript.json segments as [(start, text)], [] if there is none."""
    p = Path(pdir) / "transcript.json"
    try:
        segs = json.loads(p.read_text(encoding="utf-8-sig")).get("segments", [])
        return [(float(s["start"]), str(s.get("text") or "")) for s in segs
                if s.get("start") is not None]
    except Exception:
        return []


def find_anchor(narration: str, segments: list, cs: float, ce: float):
    """(time, kind, matched_text) for the moment this line describes, or
    None. kind is 'quote' or 'para'. The time may lie outside [cs, ce]; the
    caller decides whether it can be reached."""
    if not segments or not narration:
        return None
    for q in re.findall(r'"([^"]{8,})"', narration):
        nq = _norm(q)
        best, br = None, 0.0
        for t, txt in segments:
            if not (cs - QUOTE_SEARCH_PAD <= t <= ce + QUOTE_SEARCH_PAD):
                continue
            nt = _norm(txt)
            r = difflib.SequenceMatcher(None, nq, nt).ratio()
            if len(nt) > 8 and (nt in nq or nq in nt):
                r = max(r, 0.95)
            if r > br:
                best, br = (t, txt), r
        if best and br >= QUOTE_MIN_RATIO:
            return best[0], "quote", best[1]
    words = _content(re.sub(r'"[^"]*"', " ", narration))
    best, bn = None, 0
    for t, txt in segments:
        if not (cs - 1.0 <= t <= ce):
            continue
        n = len(words & _content(txt))
        if n > bn:
            best, bn = (t, txt), n
    if best and bn >= PARA_MIN_WORDS:
        return best[0], "para", best[1]
    return None


def place(cs: float, ce: float, anchor: float, need: float, lead: float,
          narr_dur: float, lo: float | None = None,
          hi: float | None = None):
    """The start of the shown part so that `anchor` is on screen while the
    line is spoken, or None when it cannot be done inside the window.

    need = lead + narration + gap, the length of footage the clip plays.
    lo / hi are the neighbour bounds: end of the previous line's shown
    footage, start of the next line's window."""
    lower = max(cs, lo if lo is not None else cs)
    upper = min(ce, hi if hi is not None else ce) - need
    if upper < lower - 1e-6:
        return None
    target = anchor - (lead + SAY_AT * max(0.0, narr_dur))
    start = min(max(target, lower), upper)
    # the moment must actually be inside what is shown
    if not (start - 0.5 <= anchor <= start + need):
        return None
    return round(start, 3)


def visible(start: float, need: float, anchor: float) -> bool:
    return start - 0.5 <= anchor <= start + need
