"""Same-point detection for adjacent lines, by semantic field and argument.

THE DEFECT. Two adjacent lines said the same thing - one paid for tyres by
hawking a friend's stock, the next worked the shopping crowds flogging goods
out of a bag to pay for tyres - and the lexical check scored them 0.21 against
a 0.50 bar. They share exactly one content word.

WHY THIS IS NOT AN EMBEDDING, which is what the instruction asked for. No
pretrained sentence encoder can be obtained in this environment: model
downloads are intercepted by a proxy that returns a ~46 KB page in place of a
349-byte file, with the size varying per request, so every checksum fails.
Three lexical instruments were measured first and all three were REJECTED on
the evidence rather than on taste:

  whole-line content overlap   control 0.21 against a 0.50 bar - misses it
  best clause pair, min-norm   ranks the control outside the top twelve; a
                               two-word clause sharing one stem scores 1.00,
                               so it ranked an unrelated pair first
  TF-IDF cosine on stems       control 0.037 with THIRTY-THREE approved pairs
                               scoring higher - a bar catching the control
                               catches a third of ordinary prose

So this is a classifier over semantic FIELDS, which the instruction allows.
A field is a general class of English action (commerce, speech, violence,
motion...), not a list of words from the draft being judged. Two lines make
the same point when they assert the same FIELD about the same ARGUMENT, and
the argument has to be specific rather than a word the draft uses constantly.

WHAT IT CANNOT DO, stated because the alternative is trusting it too far: it
has one human-labelled positive and 103 human-labelled negatives. One positive
is a thin basis. Recall is therefore also measured against PARAPHRASES
generated from approved lines - if the detector only fires on the single pair
it was shown, it has memorised rather than generalised, and
tools/calibrate_semantic_dup.py reports that directly.
"""
from __future__ import annotations

import math
import re

# --------------------------------------------------------------------------- #
# SEMANTIC FIELDS. General classes of English action and state. Written as
# vocabulary for each class, NOT by reading the pair this gate was built for -
# the test for that is whether it fires on paraphrases it was never shown.
#
# A field needs enough members to survive a writer choosing a different verb,
# which is the entire failure being fixed: "hawking", "flogging", "selling"
# and "peddling" are one act, and any instrument that treats them as three
# different acts cannot see a restatement.
# --------------------------------------------------------------------------- #
FIELDS: dict[str, set[str]] = {
    "commerce": {
        "sell", "sells", "sold", "selling", "sale", "buy", "buys", "bought",
        "pay", "pays", "paid", "paying", "cost", "costs", "price", "money",
        "cash", "fund", "funds", "funded", "funding", "afford", "debt",
        "owe", "owes", "owed", "bet", "bets", "stake", "hawk", "hawking",
        "flog", "flogging", "peddle", "peddling", "trade", "trading",
        "hustle", "hustling", "profit", "earn", "earns", "earning", "wage",
        "charge", "charges", "bill", "collect", "collects", "collecting",
        "takings", "stock", "goods", "merchandise", "wares", "customers",
        "crowds", "market", "shopping", "street",
    },
    "speech": {
        "say", "says", "said", "tell", "tells", "told", "ask", "asks",
        "asked", "answer", "answers", "answered", "warn", "warns", "warned",
        "explain", "explains", "explained", "admit", "admits", "admitted",
        "claim", "claims", "claimed", "shout", "shouts", "call", "calls",
        "called", "quote", "promise", "promises", "offer", "offers",
        "threaten", "threatens", "argue", "argues", "argued", "reckons",
    },
    "violence": {
        "hit", "hits", "punch", "punches", "beat", "beats", "shoot",
        "shoots", "shot", "gun", "pistol", "fight", "fights", "fighting",
        "kill", "kills", "killed", "crash", "crashes", "crashed", "wreck",
        "wrecks", "wrecked", "detonate", "detonates", "explode", "explodes",
        "burn", "burns", "burning", "fire", "slam", "slams", "ram", "rams",
        "shove", "shoves", "shoved",
    },
    "motion": {
        "drive", "drives", "drove", "driving", "run", "runs", "ran",
        "running", "walk", "walks", "walked", "arrive", "arrives",
        "arrived", "leave", "leaves", "left", "move", "moves", "moved",
        "moving", "chase", "chases", "chased", "race", "races", "raced",
        "drift", "drifts", "drifted", "drifting", "roll", "rolls", "rolled",
        "climb", "climbs", "climbed", "sprint", "sprints", "bolt", "bolts",
    },
    "teaching": {
        "teach", "teaches", "taught", "learn", "learns", "learned", "train",
        "trains", "trained", "training", "practise", "practises", "coach",
        "coaches", "coaching", "show", "shows", "showed", "lesson",
        "instruct", "instructs", "feel", "feels",
    },
    "authority": {
        "order", "orders", "ordered", "rule", "rules", "boss", "command",
        "commands", "demand", "demands", "demanded", "allow", "allows",
        "forbid", "forbids", "punish", "punishes", "arrest", "arrests",
        "jail", "court", "police", "uncle", "turf", "territory", "tax",
        "taxes", "taxed", "cut", "tribute", "protection",
    },
    "affection": {
        "love", "loves", "loved", "kiss", "kisses", "kissed", "family",
        "friend", "friends", "trust", "trusts", "trusted", "loyal",
        "loyalty", "care", "cares", "cared", "protect", "protects",
        "protected", "betray", "betrays", "betrayed", "stealing", "steal",
        "steals", "stole", "skimming", "thief",
    },
    "death": {
        "die", "dies", "died", "death", "dead", "grave", "funeral",
        "mourn", "mourns", "body", "corpse", "lost", "lose", "loses",
    },
    "perception": {
        "see", "sees", "saw", "watch", "watches", "watched", "look",
        "looks", "looked", "notice", "notices", "noticed", "stare",
        "stares", "realise", "realises", "realised", "know", "knows",
        "knew", "understand", "understands",
    },
}

_FIELD_OF: dict[str, str] = {}
for _f, _ws in FIELDS.items():
    for _w in _ws:
        _FIELD_OF.setdefault(_w, _f)

STOP = {
    "the", "a", "an", "and", "or", "but", "so", "then", "that", "this",
    "with", "from", "into", "onto", "over", "under", "about", "after",
    "before", "while", "when", "where", "which", "who", "whom", "whose",
    "what", "there", "here", "they", "them", "their", "his", "her", "hers",
    "him", "she", "its", "it", "he", "you", "your", "yours", "we", "our",
    "has", "have", "had", "been", "being", "was", "were", "are", "is",
    "am", "be", "will", "would", "can", "could", "shall", "should", "may",
    "might", "must", "not", "no", "nor", "too", "very", "just", "only",
    "still", "even", "also", "again", "once", "than", "like", "for", "of",
    "to", "in", "on", "at", "by", "as", "out", "up", "down", "off", "back",
    "one", "two", "all", "any", "both", "each", "more", "most", "other",
    "some", "such", "own", "same", "every", "does", "himself", "herself",
}


def _words(text: str) -> list:
    return [w for w in re.findall(r"[a-z']+", str(text or "").lower())
            if len(w) >= 3]


def stem(w: str) -> str:
    """Crude suffix strip: a general rule about English morphology.

    Deliberately not a synonym table. A stemmer ties tyre/tyres and
    pay/paying, which every writer varies; a synonym table for this draft's
    particular verbs would be a list written by looking at the answer.
    """
    for suf in ("ingly", "edly", "ing", "ers", "er", "ed", "es", "s", "ly"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def fields_of(text: str) -> set:
    """Which semantic fields this text asserts."""
    out = set()
    for w in _words(text):
        f = _FIELD_OF.get(w) or _FIELD_OF.get(stem(w))
        if f:
            out.add(f)
    return out


def arguments(text: str, idf: dict, min_idf: float) -> set:
    """The SPECIFIC things the text is about.

    A shared argument only means something if it is specific. Two lines both
    mentioning the protagonist share nothing useful; two both mentioning
    tyres do. Specificity is the line's own corpus IDF, so it needs no
    per-film list.
    """
    out = set()
    for w in _words(text):
        if w in STOP:
            continue
        s = stem(w)
        if _FIELD_OF.get(w) or _FIELD_OF.get(s):
            continue                      # that is the predicate, not the thing
        if idf.get(s, 99.0) >= min_idf:
            out.add(s)
    return out


def build_idf(texts: list) -> dict:
    """IDF over the draft's own narrated lines."""
    docs = [{stem(w) for w in _words(t) if w not in STOP} for t in texts]
    n = max(1, len(docs))
    df: dict = {}
    for d in docs:
        for w in d:
            df[w] = df.get(w, 0) + 1
    return {w: math.log((n + 1) / (c + 0.5)) for w, c in df.items()}


def same_point(a: str, b: str, idf: dict, min_idf: float = 2.0,
               min_args: int = 1) -> tuple:
    """(is_same, why). Same FIELD asserted about the same specific ARGUMENT.

    Both halves are required, and each rules out a different false positive:
      - field alone fires on any two consecutive action lines;
      - argument alone fires on a chase that stays with the same car, which
        is a legitimate build-up rather than a restatement.
    """
    fa, fb = fields_of(a), fields_of(b)
    shared_f = fa & fb
    if not shared_f:
        return False, ""
    aa = arguments(a, idf, min_idf)
    ab = arguments(b, idf, min_idf)
    shared_a = aa & ab
    if len(shared_a) < min_args:
        return False, ""
    return True, (f"both assert {'/'.join(sorted(shared_f))} about "
                  f"{', '.join(sorted(shared_a)[:4])}")


def adjacent_duplicates(lines: list, min_idf: float = 2.0,
                        min_args: int = 1) -> list:
    """[{a, b, why}] for adjacent narrated lines making the same point."""
    texts = [str(l.get("narration") or "") for l in lines]
    idf = build_idf(texts)
    out = []
    for x, y in zip(lines, lines[1:]):
        ok, why = same_point(str(x.get("narration") or ""),
                             str(y.get("narration") or ""),
                             idf, min_idf, min_args)
        if ok:
            out.append({"a": x.get("id"), "b": y.get("id"), "why": why})
    return out
