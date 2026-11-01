"""Word timings for the cached narration, and the cut moments they imply.

The picture should change when the VOICE reaches the event, not at a shot
boundary that happens to be nearby. Step 2 could only cut at shot edges
because it had no idea when each clause is spoken; this supplies that.

HOW. faster-whisper with word_timestamps on the cached narration mp3 for each
line. We already know the text, so this is forced alignment rather than
recognition: the recognised words are matched to the known words in order and
the known text wins every disagreement. That matters - ASR on a 17-word line
will mishear a name, and a misheard name must not move a cut.

Inworld was checked first, as instructed, and returns no per-word timings
through the provider interface in this repo (pipeline/tts_providers.py has no
timestamp field), so alignment is the path.

CUT PLACEMENT, in this order:
  1. the moment the first word of a clause is spoken;
  2. SNAPPED to the nearest real cut in the film within
     config.CLAUSE_CUT_SNAP_SEC, so the edit lands on the film's own rhythm
     rather than mid-gesture. The cut list is the project's own _cuts.json -
     2088 detected cuts - not a fresh detection that could disagree with the
     catalogue built from it;
  3. refused if it would make a sub-clip shorter than
     config.CLAUSE_MIN_SUBCLIP_SEC, in which case the clause MERGES into its
     predecessor. A flash too brief to read is worse than a held shot.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import config

_WORD = re.compile(r"[a-z0-9']+")
_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel(
            str(getattr(config, "WORD_TIMES_MODEL", "base")),
            device="cpu", compute_type="int8")
    return _MODEL


def norm(w: str) -> str:
    return "".join(_WORD.findall(str(w or "").lower()))


def align(mp3: Path, text: str) -> list:
    """[(word, start, end)] for the KNOWN text, in order.

    The known words are the output; ASR only supplies times. A known word the
    ASR missed inherits a time interpolated between its neighbours, so the
    sequence is always complete and always in the draft's own wording.
    """
    segs, _ = _model().transcribe(str(mp3), word_timestamps=True,
                                  language="en")
    heard = [(norm(w.word), float(w.start), float(w.end))
             for s in segs for w in (s.words or []) if norm(w.word)]
    known = [w for w in str(text or "").split() if norm(w)]
    out: list = []
    i = 0
    for kw in known:
        k = norm(kw)
        hit = None
        for j in range(i, min(i + 4, len(heard))):
            if heard[j][0] == k or heard[j][0].startswith(k[:4]) and len(k) > 3:
                hit = j
                break
        if hit is None:
            out.append([kw, None, None])
        else:
            out.append([kw, heard[hit][1], heard[hit][2]])
            i = hit + 1
    # interpolate the unmatched
    last = 0.0
    nxt = None
    for idx, row in enumerate(out):
        if row[1] is None:
            fwd = next((out[j][1] for j in range(idx + 1, len(out))
                        if out[j][1] is not None), None)
            row[1] = last if fwd is None else (last + fwd) / 2.0
            row[2] = row[1]
        last = row[2] or last
    return [(a, round(float(b or 0), 3), round(float(c or 0), 3))
            for a, b, c in out]


def clause_offsets(words: list, clauses: list) -> list:
    """Seconds into the line at which each clause's first word is spoken."""
    out = []
    wi = 0
    for c in clauses:
        cw = [w for w in str(c.get("text") or "").split() if norm(w)]
        if not cw:
            out.append(None)
            continue
        target = norm(cw[0])
        found = None
        for j in range(wi, len(words)):
            if norm(words[j][0]) == target:
                found = j
                break
        if found is None:
            found = min(wi, max(0, len(words) - 1))
        out.append(words[found][1] if words else None)
        wi = found + len(cw)
    return out


def load_film_cuts(pdir: Path) -> list:
    try:
        c = json.loads((Path(pdir) / "_cuts.json").read_text(encoding="utf-8"))
        return sorted(float(x) for x in (c.get("cuts") or []))
    except Exception:
        return []


def snap(t: float, cuts: list, window: float) -> tuple:
    """(snapped, delta) - move t onto the nearest film cut within window."""
    if not cuts:
        return t, None
    import bisect
    i = bisect.bisect_left(cuts, t)
    best, bd = t, None
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(cuts):
            d = cuts[j] - t
            if abs(d) <= window and (bd is None or abs(d) < abs(bd)):
                best, bd = cuts[j], d
    return best, (round(bd, 3) if bd is not None else None)


def place_cuts(line_start: float, line_dur: float, offsets: list,
               cuts: list) -> dict:
    """Where the picture changes inside one line.

    Returns {"edges": [...], "merged": n, "snapped": n}. `edges` are absolute
    FILM seconds at which the next sub-clip begins, excluding the line's own
    start.
    """
    floor = float(getattr(config, "CLAUSE_MIN_SUBCLIP_SEC", 1.23))
    win = float(getattr(config, "CLAUSE_CUT_SNAP_SEC", 0.5))
    edges, merged, snapped = [], 0, 0
    prev = 0.0
    for off in offsets[1:]:
        if off is None:
            merged += 1
            continue
        if off - prev < floor:
            merged += 1
            continue
        if line_dur - off < floor:
            merged += 1
            continue
        s, d = snap(line_start + off, cuts, win)
        # a snap must not push the sub-clip under the floor either
        rel = s - line_start
        if rel - prev < floor or line_dur - rel < floor:
            s, rel, d = line_start + off, off, None
        if d is not None:
            snapped += 1
        edges.append(round(s, 3))
        prev = rel
    return {"edges": edges, "merged": merged, "snapped": snapped}
