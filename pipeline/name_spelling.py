# -*- coding: utf-8 -*-
"""name_spelling.py - [NAME-SPELLING]: a known name, spelled wrong.

Furious 7's draft wrote "Mosé Jaconde" for Mose Jakande. names.json had the
right spelling and the writer had names.json; the spelling came from the
transcript (Whisper hears a name, it does not know how it is written). The
[NAME] / [NAME-LEAK] lint saw it - as a yellow WARNING among dozens, so the
draft passed with it.

HARD (an error, by line, so resolve rewrites it) only where the evidence
says misspelling and nothing else:
  ACCENT   the same letters as a listed name, other accents or case
           ("Mosé" / Mose)
  HEARD    one or two letters from a listed CHARACTER token, AND the variant
           is in this film's transcript while the listed spelling never is
           (Whisper wrote "Jaconde" and never "Jakande" - that is where the
           draft got it). A real word that happens to sit near a name -
           "America" / Amelia, "George" / Georgie, "China" / Chiba - fails
           this: the listed name is said in the film, or the word is an
           actor's near-miss, or it is an ordinary lower-case word.
Anything else one or two letters from a name is a WARNING (it may be a
place, a real person, a word) - review of 677fc38 measured nine such
plausible lines across seven films that a hard rule would have blocked.

Known tokens: names.json (names / characters / aliases / roles, flat or
cast form, actors, actor_alias) and film_facts.json (cast actors and roles,
director, writer, composer). Words inside double quotation marks are the
film's own words (a quote must match the transcript) and are not checked.
No known names = the gate did NOT run, and says so.
"""
from __future__ import annotations

import glob
import json
import re
import unicodedata
from pathlib import Path

_TOKEN = re.compile(r"[^\W\d_][\w'’-]*", re.UNICODE)
_QUOTED = re.compile(r"[\"“][^\"”]*[\"”]")
_POSS = re.compile(r"(?:['’]s?|-)+$")
_LOWER_CACHE: dict = {}


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
    """'Brian's' -> Brian, 'Murph-' -> Murph, O'Conner stays O'Conner."""
    return _POSS.sub("", tok)


def known_names(pdir: Path) -> dict:
    """{name token as listed: "character" | "other"}."""
    out: dict = {}

    def add(v, kind):
        for t in _TOKEN.findall(str(v or "")):
            t = _base(t)
            if len(t) >= 3 and t[:1].isupper():
                if out.get(t) != "character":
                    out[t] = kind

    def walk(v, kind):
        if isinstance(v, dict):
            if any(k in v for k in ("character", "name", "actor")):
                add(v.get("character") or v.get("name"), "character")
                add(v.get("actor"), "other")
                add(v.get("actor_alias"), "other")
            else:                       # an alias map: both sides are names
                for k, x in v.items():
                    add(k, kind)
                    walk(x, kind)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x, kind)
        else:
            add(v, kind)
    try:
        nd = json.loads((pdir / "names.json").read_text(encoding="utf-8-sig"))
        if isinstance(nd, dict):
            for key in ("names", "characters", "aliases", "roles"):
                walk(nd.get(key), "character")
        else:
            walk(nd, "character")
    except (OSError, ValueError, AttributeError):
        pass
    try:
        ff = json.loads((pdir / "film_facts.json").read_text(
            encoding="utf-8-sig"))
        for c in ff.get("cast") or []:
            add(c.get("actor"), "other")
            add(c.get("role"), "character")
        for k in ("director", "writer", "composer"):
            walk(ff.get(k), "other")
    except (OSError, ValueError, AttributeError):
        pass
    return out


def _texts(pdir: Path) -> list:
    out = []
    try:
        out += [str(s.get("text") or "") for s in json.loads(
            (pdir / "transcript.json").read_text(encoding="utf-8-sig"))
            .get("segments") or []]
    except (OSError, ValueError, AttributeError):
        pass
    return out


def _lowercase_words(pdir: Path) -> set:
    """Words written in lower case anywhere in the repo's transcripts and
    beat maps (the same corpus [NAME-LEAK] uses): ordinary words."""
    root = str(Path(pdir).parent)
    if root in _LOWER_CACHE:
        return _LOWER_CACHE[root] | _film_lower(pdir)
    words = set()
    for p in glob.glob(str(Path(root) / "*" / "transcript.json")) + \
            glob.glob(str(Path(root) / "*" / "beats_proposal.md")):
        try:
            t = Path(p).read_text(encoding="utf-8-sig")
        except OSError:
            continue
        words.update(_base(w) for w in re.findall(r"\b[a-z][a-z'’-]*\b", t))
    _LOWER_CACHE[root] = words
    return words | _film_lower(pdir)


def _film_lower(pdir: Path) -> set:
    srcs = _texts(pdir)
    try:
        srcs.append((pdir / "beats_proposal.md").read_text(encoding="utf-8-sig"))
    except OSError:
        pass
    return {_base(w) for t in srcs
            for w in re.findall(r"\b[a-z][a-z'’-]*\b", t)}


def misspelled(pdir: Path, lines: list) -> list:
    """[(line id, word as written, the listed spelling, hard: bool)]."""
    pdir = Path(pdir)
    known = known_names(pdir)
    if not known:
        return []
    folded: dict = {}
    for k, kind in known.items():
        if folded.get(_fold(k), (None, ""))[1] != "character":
            folded[_fold(k)] = (k, kind)
    lower = None
    heard = None
    out = []
    for ln in lines:
        text = _QUOTED.sub(" ", unicodedata.normalize(
            "NFC", str(ln.get("narration") or "")))
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
            if f in folded:                      # same letters, other accents
                out.append((ln.get("id"), w, folded[f][0], True))
                continue
            # a near-spelling only from five letters up: at four, a word
            # and a name one letter apart are common ("Kong" / Sung Kang)
            if len(f) < 5:
                continue
            near = [(k, kind) for fk, (k, kind) in folded.items()
                    if fk[:1] == f[:1] and len(fk) >= 5
                    and abs(len(fk) - len(f)) <= 1
                    and _lev(f, fk) <= (2 if len(f) >= 6 else 1)]
            if not near:
                continue
            if lower is None:
                lower = _lowercase_words(pdir)
            if f in lower:
                continue                         # an ordinary word
            k, kind = min(near, key=lambda x: (_lev(f, _fold(x[0])),
                                               x[1] != "character"))
            if heard is None:
                heard = {_fold(_base(t)) for s in _texts(pdir)
                         for t in _TOKEN.findall(s)}
            hard = (kind == "character" and f in heard
                    and _fold(k) not in heard)
            out.append((ln.get("id"), w, k, hard))
    return out


def report(pdir: Path, lines: list) -> dict:
    """{"errors": [...], "warns": [...], "notes": [...]} for the validator."""
    pdir = Path(pdir)
    if not known_names(pdir):
        return {"errors": [], "warns": [],
                "notes": ["[NAME-SPELLING] not run: names.json / "
                          "film_facts.json list no names"]}
    errs, warns = [], []
    for i, w, k, hard in misspelled(pdir, lines):
        if hard:
            errs.append(f"[NAME-SPELLING] line {i}: '{w}' is a misspelling "
                        f"of '{k}' (names.json / film_facts.json spell it "
                        f"'{k}') - a transcript hears a name, it does not "
                        f"spell it; use the listed spelling")
        else:
            warns.append(f"[NAME-SPELLING] line {i}: '{w}' is close to the "
                         f"listed name '{k}' - if it means {k}, spell it so")
    return {"errors": errs, "warns": warns, "notes": []}
