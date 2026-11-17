# -*- coding: utf-8 -*-
"""flow_stats.py - how a script SOUNDS, measured. Report only, never a gate.

Owner, 17 Nov 2026: "the content can be complete, but how it is told matters
just as much - like in literature". Nine binge-watched recap channels were
measured (references/voice). Next to them, our drafts:
- almost never fold the last event into the next sentence ("Hearing this,
  ...");
- rarely give an action its goal and its obstacle ("to ...", "but", "only
  to");
- chop chains into two-word facts;
- leave feeling out of the story lines.

These numbers let a reader of the run see that at a glance. They are NOT
targets. A quota on them would rebuild the machine-made style that story
mode removed. Hence no gate, no feedback round, no rewrite.

REFERENCE: Movie Recaps, 4 videos, 12,782 words, measured with THIS module
(17 Nov). On the same scale, Furious 7 acts 3-4 scored: the old pipeline 15
words/sentence, 3% folded, 2.3 but, 1.5 goals, 2.3 feeling; the story-mode
trial 12 / 5% / 1.4 / 5.1 / 1.4; the hand sample 11 / 7% / 0.9 / 5.6 / 0.9. The 'hand sample'
is the owner-approved act 3 of Furious 7.
"""
from __future__ import annotations

import re

FOLDED = re.compile(
    r"^(As|When|After|Once|While|Before|Upon|Having|With|Without|Despite|"
    r"Now that|By the time|Back (?:at|in|with)|Determined|Desperate|Unable|"
    r"Unaware|Realizing|Realising|Seeing|Hearing|Knowing|Hoping|Feeling|"
    r"Noticing|Thinking|Furious|Shocked|Worried|Terrified|Left|Fearing|"
    r"Believing|Wanting|Following|Inspired|Within)\b")
FOLDED_ING = re.compile(r"^[A-Z][a-z]+ing\b[^.]{0,60},")
BUT = re.compile(r",? (but|however|yet) |^(But|However|Yet|Unfortunately|"
                 r"Luckily|Fortunately|Still|Instead)\b|\bonly to\b", re.M)
PURPOSE = re.compile(
    r"\b(in order )?to (get|find|stop|save|help|make|keep|take|escape|avoid|"
    r"protect|prove|win|see|learn|pay|kill|reach|catch|warn|buy|show|"
    r"convince|lure|free|track|steal|cover|hide|distract|retrieve|rescue|"
    r"figure|ask|bring|break|clear|finish|start|restart|lock)\b", re.I)
FEELING = re.compile(
    r"\b(desperately|immediately|quickly|finally|suddenly|calmly|"
    r"mercilessly|nervously|secretly|barely|easily|slowly|angrily|happily|"
    r"eagerly|frantically|reluctantly|carefully|silently|unfortunately|"
    r"luckily|fortunately|sadly|thankfully|realizes?|realises?|realizing|"
    r"realising|decides?|fears?|is terrified|is afraid|can't believe|"
    r"begs?|wonders?|suspects?|hopes?)\b", re.I)

REFERENCE = {"words_per_sentence": 16.2, "folded_share": 0.18,
             "but_per_k": 8.9, "purpose_per_k": 9.3, "feeling_per_k": 9.2}


def _sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?])[\"']?\s+", text)
            if len(s.split()) > 2]


def flow_stats(lines: list) -> dict:
    """Narrated lines in -> the five numbers. Holds, film-speaks and blank
    lines are skipped. Quotes are stripped so dialogue does not count."""
    text = " ".join(str(l.get("narration") or "").strip() for l in lines
                    if isinstance(l, dict) and str(l.get("narration") or
                                                   "").strip())
    text = re.sub(r"[\"“”]", "", text)
    sents = _sentences(text)
    words = len(text.split())
    if not sents or not words:
        return {"sentences": 0, "words": 0}
    folded = sum(1 for s in sents if FOLDED.match(s) or FOLDED_ING.match(s))
    k = 1000.0 / words
    return {"sentences": len(sents), "words": words,
            "words_per_sentence": round(words / len(sents), 1),
            "folded_share": round(folded / len(sents), 2),
            "but_per_k": round(len(BUT.findall(text)) * k, 1),
            "purpose_per_k": round(len(PURPOSE.findall(text)) * k, 1),
            "feeling_per_k": round(len(FEELING.findall(text)) * k, 1)}


def flow_line(st: dict) -> str:
    """One printable line, each number next to the reference channel's."""
    if not st.get("sentences"):
        return "[FLOW] no narrated sentences"
    r = REFERENCE
    return (f"[FLOW] (report only - not a gate; reference = Movie Recaps) "
            f"words/sentence {st['words_per_sentence']} (ref {r['words_per_sentence']}), "
            f"folded openers {st['folded_share']:.0%} (ref {r['folded_share']:.0%}), "
            f"but/only-to {st['but_per_k']} per 1k words (ref {r['but_per_k']}), "
            f"goals 'to ...' {st['purpose_per_k']} (ref {r['purpose_per_k']}), "
            f"feeling words {st['feeling_per_k']} (ref {r['feeling_per_k']})")
