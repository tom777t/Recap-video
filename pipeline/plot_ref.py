# -*- coding: utf-8 -*-
"""plot_ref.py - the film's Plot section from Wikipedia, saved as plot.md.

WHY (Furious 7, 17 Nov 2026). The beat map is built from frames and speech.
When a character is not named on screen, the tagger has to guess, and the
guesses were wrong in exactly the places the recap needed:
- the man the crew finds at the factory became "an older man in a grey
  suit", with no name;
- Jakande's helicopter, drone and crew became "Mr. Nobody's" (B192, B196,
  B201, B216).
The writer then repeated every error faithfully. Wikipedia's Plot section,
written by people, says who these people are and why they act. So the beats
stage now reads it next to the frames: the frames say WHAT is on screen, the
Plot says WHO and WHY.

Code only. It is the same page the facts stage reads (the Wikipedia URL in
names.json `_source`), fetched once and pinned to a revision. No model call.
A film with no Wikipedia page (a short drama) simply has no plot.md, and the
beats stage runs as before.
"""
from __future__ import annotations

import re
from pathlib import Path

PLOT_HEADINGS = ("Plot", "Synopsis", "Plot summary", "Story", "Premise")


def extract_plot(wikitext: str) -> str:
    """The Plot section as plain prose ('' if the page has none)."""
    t = wikitext or ""
    heads = "|".join(re.escape(h) for h in PLOT_HEADINGS)
    m = re.search(rf"(?im)^==\s*(?:{heads})\s*==\s*$", t)
    if not m:
        return ""
    rest = t[m.end():]
    nxt = re.search(r"(?m)^==[^=].*==\s*$", rest)
    body = rest[:nxt.start()] if nxt else rest
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"<ref[^>/]*/>", "", body)
    body = re.sub(r"<ref[^>]*>.*?</ref>", "", body, flags=re.S)
    for _ in range(3):                              # nested templates
        body = re.sub(r"\{\{[^{}]*\}\}", "", body)
    body = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", body)
    body = re.sub(r"'{2,}", "", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = re.sub(r"(?m)^===+\s*(.*?)\s*===+\s*$", r"\1:", body)
    # a single newline inside a wikitext paragraph renders as a space
    paras = [" ".join(ln.strip() for ln in blk.splitlines() if ln.strip())
             for blk in re.split(r"\n\s*\n", body)]
    paras = [re.sub(r"[ \t]+", " ", p_) for p_ in paras if p_]
    # a sub-heading line stays its own paragraph
    out = []
    for p_ in paras:
        out += [x.strip() for x in re.split(r"(?<=:)\s(?=[A-Z])", p_)
                if x.strip()] if re.match(r"^[^.]{1,60}:\s", p_) else [p_]
    return "\n\n".join(out).strip()


def ensure_plot(pdir: Path, title: str | None, fetch=None) -> dict:
    """Write pdir/plot.md once. `title` is the Wikipedia page (URL or title)
    the caller resolved; `fetch` replaces the network in tests. Returns
    {"state": "kept" | "wrote" | "none", "why": ..., "words": n}. Never
    raises: a missing plot is not an error, it just means the beats stage
    has no second source."""
    p = Path(pdir) / "plot.md"
    if p.exists() and p.stat().st_size > 0:
        return {"state": "kept", "words": len(p.read_text(
            encoding="utf-8").split())}
    if not title and fetch is None:
        return {"state": "none", "why": "no Wikipedia page for this film",
                "words": 0}
    try:
        if fetch is None:
            from pipeline import names as N
            rev = N.fetch_revision(title)
        else:
            rev = fetch()
    except Exception as e:                      # offline, no page
        return {"state": "none", "why": str(e)[:160], "words": 0}
    plot = extract_plot(rev.get("wikitext") or "")
    if not plot:
        return {"state": "none", "why": f"'{rev.get('title')}' has no Plot "
                f"section", "words": 0}
    p.write_text(f"# {rev.get('title')} - Plot (English Wikipedia, oldid="
                 f"{rev.get('oldid')}, fetched {rev.get('fetched')})\n\n"
                 f"{plot}\n", encoding="utf-8")
    return {"state": "wrote", "words": len(plot.split())}


def missing_names(plot_text: str, beats: list, names: list,
                  min_mentions: int = 2) -> list:
    """Characters the Plot names at least `min_mentions` times who appear in
    no beat's `chars` and in no beat's text: a person the story turns on whom
    the frames never identified. Coarse (film-wide), report only."""
    blob = " ".join(str(b.get("what") or "") + " " +
                    " ".join(map(str, b.get("chars") or [])) for b in beats)
    out = []
    for n in names:
        full = str(n or "").strip()
        if not full:
            continue
        # single-name keys: capitalised, 4+ letters, never a possessive
        # ("Dom's sister" names Dom's sister, not Dom)
        parts = [w for w in re.findall(r"[A-Z][\w.'\u2019-]+", full)
                 if len(w) > 3 and w not in ("The", "Mr.", "Mrs.")
                 and not re.search(r"['\u2019]s$", w)]
        keys = [full] + parts
        cnt = max(len(re.findall(rf"\b{re.escape(k)}\b", plot_text))
                  for k in keys)
        if cnt >= min_mentions and not any(
                re.search(rf"\b{re.escape(k)}\b", blob) for k in keys):
            out.append((full, cnt))
    return out
