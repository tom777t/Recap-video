# -*- coding: utf-8 -*-
"""name_spelling.py - [NAME-SPELLING]: a known name, spelled wrong.

Furious 7's draft wrote "Mosé Jaconde" for Mose Jakande. names.json had the
right spelling and the writer had names.json; the spelling came from the
transcript (Whisper hears a name, it does not know how it is written). The
[NAME] / [NAME-LEAK] lint saw it - as a yellow WARNING among dozens, so the
draft passed with it.

This gate is the narrow, high-precision half of that lint, and it is HARD:
a capitalised word that is NOT a known name token but is one or two letters
away from one (or the same letters with other accents / case) is the known
name misspelled. Unknown names stay with [NAME-LEAK] (a warning: a place or
a sign can be real and unlisted). A misspelling of a listed name is never
right, so it is an error, routed to resolve by line.

Known tokens: names.json (characters, actors, aliases) and film_facts.json's
cast. Words inside double quotation marks are the film's own words (a quote
must match the transcript) and are not checked. A word the film's transcript
or the beat map uses in lower case is an ordinary word ("Show" at the start
of a sentence is not a misspelled "Shaw").
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

_TOKEN = re.compile(r"[^\W\d_][\w'’-]*", re.UNICODE)
_QUOTED = re.compile(r"[\"“][^\"”]*[\"”]")


def _fold(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t))
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _lev(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _base(tok: str) -> str:
    return re.split(r"['’]", tok)[0]


def known_names(pdir: Path) -> set:
    """Every listed name token, spelled as listed (case kept)."""
    out = set()

    def add(v):
        for t in _TOKEN.findall(str(v or "")):
            t = _base(t)
            if len(t) >= 3 and t[:1].isupper():
                out.add(t)
    try:
        nd = json.loads((pdir / "names.json").read_text(encoding="utf-8-sig"))
        for n in (nd.get("names", nd) if isinstance(nd, dict) else nd) or []:
            if isinstance(n, dict):
                for f in ("character", "name", "actor", "actor_alias"):
                    add(n.get(f))
            else:
                add(n)
    except (OSError, ValueError, AttributeError):
        pass
    try:
        ff = json.loads((pdir / "film_facts.json").read_text(
            encoding="utf-8-sig"))
        for c in ff.get("cast") or []:
            add(c.get("actor"))
            add(c.get("role"))
        add(ff.get("director"))
    except (OSError, ValueError, AttributeError):
        pass
    return out


def _lowercase_words(pdir: Path) -> set:
    words = set()
    srcs = []
    try:
        srcs += [str(s.get("text") or "") for s in json.loads(
            (pdir / "transcript.json").read_text(encoding="utf-8-sig"))
            .get("segments") or []]
    except (OSError, ValueError, AttributeError):
        pass
    try:
        srcs.append((pdir / "beats_proposal.md").read_text(encoding="utf-8-sig"))
    except OSError:
        pass
    for t in srcs:
        for w in re.findall(r"\b[a-z][a-z'’-]*\b", t):
            words.add(_base(w))
    return words


def misspelled(pdir: Path, lines: list) -> list:
    """[(line id, word as written, the listed spelling)]."""
    pdir = Path(pdir)
    known = known_names(pdir)
    if not known:
        return []
    folded = {}
    for k in known:
        folded.setdefault(_fold(k), k)
    lower = None
    out = []
    for ln in lines:
        text = _QUOTED.sub(" ", str(ln.get("narration") or ""))
        seen = set()
        for tok in _TOKEN.findall(text):
            w = _base(tok)
            if len(w) < 3 or not w[:1].isupper() or w in known or w in seen:
                continue
            if (w.endswith("s") and w[:-1] in known) or (
                    w.endswith("es") and w[:-2] in known):
                continue                         # "the Tarasovs"
            if w.isupper() and len(w) > 1:
                continue                         # an acronym, not a name
            seen.add(w)
            f = _fold(w)
            hit = folded.get(f)                  # same letters, other accents
            # a near-spelling only from five letters up: at four, a word
            # and a name one letter apart are common ("Kong" / Sung Kang)
            if hit is None and len(f) >= 5:
                near = [k for fk, k in folded.items()
                        if fk[:1] == f[:1] and len(fk) >= 5
                        and abs(len(fk) - len(f)) <= 1
                        and _lev(f, fk) <= (2 if len(f) >= 6 else 1)]
                if near:
                    if lower is None:
                        lower = _lowercase_words(pdir)
                    if f not in lower:
                        hit = min(near, key=lambda k: _lev(f, _fold(k)))
            if hit is not None and hit != w:
                out.append((ln.get("id"), w, hit))
    return out


def report(pdir: Path, lines: list) -> list:
    """The gate's error strings, one per line and word."""
    return [f"[NAME-SPELLING] line {i}: '{w}' is a misspelling of '{k}' "
            f"(names.json / film_facts.json spell it '{k}') - a transcript "
            f"hears a name, it does not spell it; use the listed spelling"
            for i, w, k in misspelled(pdir, lines)]
