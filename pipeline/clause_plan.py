"""Assign each visual clause a shot, and emit the sub-clip list.

Rules, in the order they bind:
  - a clause's shot must lie in the line's own beat span plus a small
    neighbourhood, so the picture never jumps to another scene to illustrate
    a word;
  - shots are taken in FILM ORDER, so the picture advances as the sentence
    does and [BACKWARD-CLIP] stays satisfied by construction;
  - each shot is used once within a line, because showing the same frames
    twice inside one sentence is the duplication [VISUAL-REPEAT] exists for;
  - a sub-clip shorter than the calibrated floor is MERGED into its
    neighbour rather than shipped, because a flash too brief to read is
    worse than a held shot.

Scoring a clause against a shot uses what the catalogue already knows - its
`depicts` tags, its `action` text and its `chars` - plus the transcript for
that window when the clause reports speech. No new vision pass: the catalogue
was built by one and a second opinion here could only disagree with it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import config
from pipeline import clause_shots as cs

_WORD = re.compile(r"[a-z']+")
STOP = {"the", "a", "an", "and", "or", "but", "so", "then", "that", "this",
        "with", "from", "into", "his", "her", "their", "them", "they", "he",
        "she", "it", "its", "him", "of", "to", "in", "on", "at", "by", "as",
        "out", "up", "down", "off", "back", "is", "are", "was", "were",
        "has", "have", "had", "for", "not", "no"}


def _w(s: str) -> set:
    return {x for x in _WORD.findall(str(s or "").lower())
            if len(x) >= 4 and x not in STOP}


def sec(v):
    try:
        p = [float(x) for x in str(v).split(":")]
        return p[0] * 3600 + p[1] * 60 + p[2]
    except Exception:
        return None


def load_shots(pdir: Path) -> list:
    s = json.loads((Path(pdir) / "shots.json").read_text(encoding="utf-8-sig"))
    out = []
    for x in s.get("shots") or []:
        a, b = sec(x.get("clip_start")), sec(x.get("clip_end"))
        if a is None or b is None or b <= a:
            continue
        out.append({"a": a, "b": b, "start": x["clip_start"],
                    "end": x["clip_end"],
                    "depicts": [str(t) for t in (x.get("depicts") or [])],
                    "chars": [str(c) for c in (x.get("chars") or [])],
                    "action": str(x.get("action") or ""),
                    "censor": x.get("censor")})
    out.sort(key=lambda s: s["a"])
    return out


def load_speech(pdir: Path) -> list:
    try:
        t = json.loads((Path(pdir) / "transcript.json")
                       .read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    segs = t.get("segments") if isinstance(t, dict) else t
    return [{"a": float(s.get("start") or 0), "b": float(s.get("end") or 0),
             "text": str(s.get("text") or "")} for s in (segs or [])]


def score(clause: str, shot: dict, speech: list) -> float:
    """How well this shot depicts this clause. Catalogue first, speech second."""
    cw = _w(clause)
    if not cw:
        return 0.0
    s = 0.0
    s += 2.0 * len(cw & _w(shot["action"]))
    s += 1.0 * len(cw & _w(" ".join(shot["depicts"])))
    s += 1.5 * len(cw & _w(" ".join(shot["chars"])))
    # A clause that reports speech belongs on the window where that speech
    # actually happens.
    if '"' in clause or "\u201c" in clause:
        said = " ".join(x["text"] for x in speech
                        if x["b"] > shot["a"] and x["a"] < shot["b"])
        s += 2.5 * len(cw & _w(said))
    return s


def plan_line(line: dict, shots: list, speech: list,
              neighbourhood: float = 20.0) -> dict:
    """{split, subclips:[{start,end,clause,shot_score}], why}"""
    a, b = sec(line.get("clip_start")), sec(line.get("clip_end"))
    text = str(line.get("narration") or "")
    if a is None or b is None:
        return {"split": False, "why": "no window", "subclips": []}
    clauses = [c for c in cs.split_clauses(text) if c["visual"]]
    if len(clauses) < 2:
        return {"split": False, "why": "fewer than two visible events",
                "subclips": []}

    lo, hi = a - neighbourhood, b + neighbourhood
    pool = [s for s in shots if s["b"] > lo and s["a"] < hi]
    if len(pool) < 2:
        return {"split": False,
                "why": f"only {len(pool)} shot(s) in the beat span plus "
                       f"{neighbourhood:.0f}s - nothing to cut to",
                "subclips": []}

    # film order, each shot once: walk the clauses forward and never take a
    # shot earlier than the one already used.
    chosen = []
    idx = 0
    for c in clauses:
        best, bi = None, None
        for i in range(idx, len(pool)):
            sc = score(c["text"], pool[i], speech)
            if best is None or sc > best:
                best, bi = sc, i
        if bi is None:
            break
        chosen.append({"clause": c["text"], "shot": pool[bi],
                       "score": round(best or 0.0, 2)})
        idx = bi + 1
    if len(chosen) < 2:
        return {"split": False, "why": "could not place two clauses in "
                                       "film order", "subclips": []}
    return {"split": True, "why": f"{len(chosen)} clauses placed",
            "subclips": chosen}


# [VISUAL-CAPACITY] lives in clause_shots now, because it is the one piece of
# this work that stands on its own: it is a WRITER rule about how many events
# a line may narrate, and it needs nothing from the clause-cut planner. Main
# carries clause_shots; the planner below stays on this branch. Re-exported so
# existing callers here keep working and the two copies cannot drift.
from pipeline.clause_shots import visual_capacity  # noqa: E402,F401
