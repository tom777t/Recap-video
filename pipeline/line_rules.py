# -*- coding: utf-8 -*-
"""line_rules.py - the draft gates that can judge ONE line, asked BEFORE it
is saved.

Furious 7, after the draft passed: every hand fix (tools/fix_line.py) and
every resolve rewrite was checked against its SLOT (word band, quote,
voice) and then saved - and only the full gate run afterwards found that
the new words repeated a phrase from another line ([TIC-REPETITION]
"dom's voice comes" x2), misspelled a name or quoted a song. Each of those
cost the user another round. These are the gates' own rules, called with
the candidate text and the rest of the draft, so a line that would fail
them is refused with the reason before anything is written:

  [TIC-REPETITION]  a counted phrase (motif_gates.tic_phrases - the gate's
                    own definition) the line would share with another line
  [NAME-SPELLING]   a hard misspelling of a listed name (name_spelling)
  [NOT-DIALOGUE]    a quoted span that is a song / listed line (sung)

The slot's own rules stay in tools/write_slots.line_deviations. Rules that
need the whole draft's shape (shares, contour, cadence) are built by the
slots, not checked here.
"""
from __future__ import annotations

from pathlib import Path


def problems(pdir, lines: list, lid, text: str) -> list:
    """Why `text`, as line `lid` of `lines` (the draft's line dicts: the
    other lines as they will stand, line `lid` as it stands NOW), would
    fail a draft gate in a way it does not already. [] = none."""
    from pipeline import motif_gates as MG
    from pipeline import name_spelling as NS
    from pipeline import sung
    import config
    pdir = Path(pdir)
    out = []
    others = [ln for ln in lines if str(ln.get("id")) != str(lid)]
    was = next((str(ln.get("narration") or "") for ln in lines
                if str(ln.get("id")) == str(lid)), "")
    # the gate's fallback names (no names.json) from the draft as it WILL
    # stand - not from this line's old text
    names = MG.tic_names(pdir, [str(x.get("narration") or "")
                                for x in others] + [text])
    # only a phrase the line did NOT already carry: a rewrite that keeps an
    # old repetition adds nothing, and refusing it would block every other
    # fix to that line (review of 341ffca: badgenius2017 line 61)
    mine = MG.tic_phrases(text, names) - MG.tic_phrases(was, names)
    if mine:
        cap = int(getattr(config, "TIC_NGRAM_MAX", 1))
        where: dict = {}
        for ln in others:
            for ph in MG.tic_phrases(ln.get("narration") or "", names) & mine:
                where.setdefault(ph, []).append(ln.get("id"))
        for ph, ids in sorted(where.items()):
            if len(ids) + 1 > cap:
                out.append(f"[TIC-REPETITION] \"{ph}\" is already in line(s) "
                           f"{', '.join(str(i) for i in ids[:4])} - say it "
                           f"another way")
    for _i, w, k, hard in NS.misspelled(pdir, [{"id": lid, "narration": text}]):
        if hard:
            out.append(f"[NAME-SPELLING] '{w}' - names.json spells it '{k}'")
    for q in sung.quoted_not_dialogue(pdir, text):
        out.append(f"[NOT-DIALOGUE] quotes \"{q[:50]}\" - a song / not "
                   f"dialogue, no character says it")
    return out
