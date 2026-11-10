# -*- coding: utf-8 -*-
"""sung.py - which transcript segments are NOT dialogue (a song, mostly).

Whisper writes down whatever is sung over a scene as if a character said it.
Furious 7 quoted "It's been a long without you, my friend" as Dom's line - it
is the chorus of the song over the ending (and Whisper even dropped "day").
A lyric used as a quote is wrong twice: it puts words in a character's mouth,
and it reproduces a song's lyrics in the recap.

A segment is taken as sung when any of these hold - all cheap, all general:

  MARKED    Whisper / a subtitle wrote a music mark: a note sign, or
            "[music]" / "(singing)" / "[song]" ...
  CHORUS    it comes back: another segment within CHORUS_WINDOW seconds
            reads the same (sequence ratio >= CHORUS_SIMILAR, both >= 7
            words).
            Choruses repeat; a character almost never says the same
            seven-plus-word sentence twice in eight minutes - and when one
            does, losing it as a quote costs one candidate, while keeping a
            lyric costs a false line in the recap.
  BY HAND   its text is listed in projects/<p>/not_dialogue.json
            ({"texts": ["It's been a long without you, my friend"]}) -
            written by `tools/fix_line.py --not-dialogue` when a reader
            finds one the rules above missed.

(A beat-level rule - "the beat's description says a song plays" - was tried
and dropped: beats span minutes of dialogue, and "Da-song" is a name.
Parasite lost 227 lines of dialogue to it.)

The quote picker (tools/write_slots.py), the film-speaks candidates
(pipeline/film_speaks.py) and the act payload (tools/act_payload.py) all go
through `sung_flags`, so one rule decides it everywhere.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

CHORUS_WINDOW = 480.0      # seconds: a song's chorus comes back within this
CHORUS_MIN_WORDS = 7       # measured on 17 local transcripts: at 5 words
CHORUS_SIMILAR = 0.85      # and a word-SET overlap, "What are you doing
                           # here?" x2 made 25+ false choruses per film; at 7
                           # words and this character-sequence ratio, ~6 per
                           # film, among them real songs ("And on his farm he
                           # had a chicken", "You don't have to walk in the
                           # sun" x3)

_MARK = re.compile(r"[♪♫♬♭♮♯]|"
                   r"[\[(]\s*(?:music|singing|sings|song|lyrics|"
                   r"music playing|vocalizing)\b[^\])]*[\])]", re.I)



def _norm(t: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9' ]+", " ",
                           str(t).lower().replace("’", "'")).split())


def _words(t: str) -> set:
    return set(_norm(t).split())


def by_hand(pdir) -> list:
    """The texts a person marked as not dialogue (normalised)."""
    p = Path(pdir) / "not_dialogue.json"
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    return [n for n in (_norm(x) for x in d.get("texts") or []) if n]


def add_by_hand(pdir, text: str, why: str = "") -> bool:
    """Record one text as not dialogue; False if it was already there."""
    p = Path(pdir) / "not_dialogue.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
    except ValueError:
        d = {}
    d.setdefault("_what", "transcript lines that are NOT dialogue (a song, "
                          "a PA, a TV) - never quoted; see pipeline/sung.py")
    texts = d.setdefault("texts", [])
    if _norm(text) in {_norm(x) for x in texts}:
        return False
    texts.append(text)
    if why:
        d.setdefault("why", {})[text] = why
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def sung_flags(segs: list, pdir=None) -> list:
    """One reason (str) or "" per segment; segs are (start, end, text)."""
    n = len(segs)
    why = [""] * n
    hand = by_hand(pdir) if pdir is not None else []
    ws = [_words(s[2]) for s in segs]
    nn = [_norm(s[2]) for s in segs]
    order = sorted(range(n), key=lambda i: float(segs[i][0]))
    for i in range(n):
        _a, _b, t = segs[i]
        nt = _norm(t)
        if _MARK.search(str(t)):
            why[i] = "MARKED"
        elif hand and any(h == nt or (len(h) >= 12 and h in nt)
                          or (len(nt) >= 12 and nt in h) for h in hand):
            why[i] = "BY HAND"
    # CHORUS: compare each segment only with those inside the window
    j0 = 0
    for x, i in enumerate(order):
        if len(nn[i].split()) < CHORUS_MIN_WORDS:
            continue
        ti = float(segs[i][0])
        while float(segs[order[j0]][0]) < ti - CHORUS_WINDOW:
            j0 += 1
        for y in range(j0, x):
            k = order[y]
            if len(nn[k].split()) < CHORUS_MIN_WORDS:
                continue
            if len(ws[i] & ws[k]) / min(len(ws[i]), len(ws[k])) < 0.6:
                continue                     # cheap pre-filter
            if difflib.SequenceMatcher(None, nn[i], nn[k]).ratio() \
                    >= CHORUS_SIMILAR:
                why[i] = why[i] or "CHORUS"
                why[k] = why[k] or "CHORUS"
    return why


def dialogue_only(segs: list, pdir=None) -> list:
    """segs without the sung ones."""
    w = sung_flags(segs, pdir)
    return [s for s, r in zip(segs, w) if not r]
