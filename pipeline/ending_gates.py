# -*- coding: utf-8 -*-
"""ending_gates.py - the CLOSING WINDOW, as gates.

THE DEFECT
----------
A finished recap draft garbled its own callbacks in the last four lines it
spoke. Three separate faults, all in the final seconds of the cut:

  1. A closing line introduced a quotation as "the question A asked B ... and
     never got answered" and then quoted a line that was B's STATEMENT, not
     A's question - so the callback handed one character's thesis to the
     character who had asked about it. The same clause also placed the setup
     scene somewhere it never happened: the conversation being called back to
     took place on a rooftop, and the closing line said a garage. One clause,
     two contradictions of the draft's own earlier text.

  2. A closing line framed a character the project's persona card is
     explicitly PROTECTIVE of as the one who "cost him a car he could never
     pay for" - the closing attitude contradicted the declared attitude. The
     card says the narrator defends that character and refuses to reduce him;
     the last thing the viewer heard was the narrator blaming him for a loss.

  3. A third closing line misread which character spoke in a scene.

Why these need their own gates rather than a line in an existing one:

  * They are the LAST thing the viewer hears. A wrong callback in the middle
    of a recap is a wrinkle; a wrong callback in the closer is the sentence
    the viewer leaves with, and it rewrites the meaning of everything that
    came before it.
  * NO COUNTER CAN SEE THEM. Every bar in this repo so far measures a
    distribution - lines per beat, share of judgment, coverage of a review.
    All three faults above are perfectly well-distributed. They are wrong
    about a RELATION (who said it, where, and how the narrator feels about
    them), and a relation is either checked against the draft's own earlier
    text and the persona card, or it is not checked at all.

So this module does two things. It checks the relations it CAN check
mechanically against the draft's own text and against the persona card
(CALLBACK-ATTRIBUTION, ENDING-PERSONA), and it requires a dedicated cold read
of the closing window by an agent that did not write it (ENDING-READ),
because fault 3 - a misread speaker in a scene whose dialogue the draft never
quoted - is not recoverable from the draft's text by any rule. Naming that
limit out loud is the point: the mechanical half is a floor, the required
read is what covers the rest.

NO FILM-SPECIFIC CONTENT LIVES HERE. Not a character name, not a title, not a
line of the film. The lexicons below are general English (place nouns,
attribution verbs, blame idioms); everything particular to a project is read
from that project's own angle.md, beat map and draft at call time, and every
film-specific assertion lives in tools/test_ending_gates.py's fixtures. A gate
that knows the film it was written for passes the next film by accident.

WHAT WAS TRIED AND REJECTED is recorded at each check, in comments, as
evidence rather than as reassurance. Every threshold is read from `config` at
call time via getattr with a stated default, so moving a constant moves the
verdict. Nothing here raises: input this module cannot read degrades to a
stated "CANNOT BE MEASURED" in `errors`, never to a silent pass - an empty
report is read as a pass by every caller in this repo.
"""
from __future__ import annotations

import re
from pathlib import Path

import config

# The artifact this module requires. It sits in the PROJECT dir next to the
# draft, for the reason pipeline/review_artifacts.py gives for cold_read.md:
# the review travels with the project instead of sitting in a docs tree that
# gets copied forward by accident.
ENDING_READ_NAME = "ending_read.md"

# The same `^##\s+TITLE$` section shape pipeline/angle_spec.py `_section` uses.
# WRITTEN OUT rather than imported: `_section` is private to that module, and
# the instruction for ## ATTITUDE TO CHARACTERS is to parse it here because
# angle_spec does not. The regex is deliberately byte-identical in behaviour -
# if the heading convention in angle.md ever changes, both must change, and a
# divergence would mean this gate reads a different document from the one the
# pacing gates read.
_SECTION = r"^##\s+{t}\s*$(.*?)(?=^##\s|\Z)"

# --------------------------------------------------------------------------- #
# Normalisation and content signatures
# --------------------------------------------------------------------------- #
# pipeline/beats_spec.py already has `content_words`, and it is NOT reused
# here: it keeps every word longer than 2 characters, which puts "car", "win",
# "say" and "got" into every signature. On the closing window - five lines,
# matched against a hundred earlier statements - those words match everything,
# and a matcher that matches everything names the wrong setup line with total
# confidence. The >= 4 character floor and the crude stemmer below are this
# module's own, and the cost is stated plainly: a callback whose content words
# are all short ("he has a car now") produces an EMPTY signature and is
# reported as uncheckable rather than as checked.
_STOP = {
    # function words
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "from", "by", "as", "is", "was", "are", "were", "be", "been",
    "being", "he", "she", "it", "they", "him", "her", "them", "his", "their",
    "its", "that", "this", "these", "those", "who", "whom", "whose", "which",
    "what", "then", "than", "so", "not", "no", "do", "does", "did", "done",
    "has", "have", "had", "will", "would", "can", "could", "shall", "should",
    "may", "might", "must", "up", "out", "off", "into", "onto", "over",
    "under", "about", "again", "one", "two", "all", "own", "very", "just",
    "still", "only", "more", "most", "there", "here", "when", "while",
    "because", "since", "until", "after", "before", "where", "how", "why",
    "like", "some", "any", "each", "both", "such", "other", "another",
    "same", "every", "also", "even", "back", "down", "well", "much", "many",
    "them", "yourself", "himself", "herself", "itself", "themselves",
    "you", "your", "yours", "we", "our", "ours", "us", "i", "me", "my",
    "mine", "if", "whether", "else", "ever", "never", "always", "away",
    "really", "quite", "rather", "thing", "things", "something", "anything",
    "nothing", "everything", "someone", "anyone", "nobody", "everybody",
    # contractions, AFTER the apostrophe is stripped by _norm. Without these,
    # "doesn't" becomes "doesnt" (6 characters, not a stopword) and lands in
    # every signature, so two unrelated negated sentences match on it.
    "doesnt", "dont", "didnt", "isnt", "arent", "wasnt", "werent", "hasnt",
    "havent", "hadnt", "wont", "wouldnt", "couldnt", "shouldnt", "cant",
    "cannot", "aint", "theyre", "youre", "thats", "whats", "theres",
    "heres", "lets", "youve", "ive", "weve", "theyve", "youll", "theyll",
    "youd", "theyd", "gonna", "wanna",
}

_CURLY = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
          "\u2013": "-", "\u2014": "-"}


def _flat(s) -> str:
    """Curly punctuation folded to ASCII. Nothing else touched."""
    t = str(s or "")
    for a, b in _CURLY.items():
        t = t.replace(a, b)
    return t


def _norm(s) -> str:
    """Lowercased, apostrophes removed, punctuation to spaces."""
    t = _flat(s).lower().replace("'", "")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _stem(w: str) -> str:
    """A crude suffix strip, longest suffix first.

    Crude on purpose and never below four characters, so "answered" ->
    "answer" and "rooftops" -> "rooftop" while "asked" stays "asked" rather
    than becoming "ask" and colliding with "ask" in a different sense. A real
    stemmer would be better and is not available in this repo's dependencies.
    """
    for suf in ("ings", "ing", "ers", "er", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def content_sig(text) -> set:
    """The content-word signature of a statement: {stemmed words >= 4 chars}."""
    out = set()
    for w in _norm(text).split():
        if len(w) < 4 or w in _STOP:
            continue
        s = _stem(w)
        if len(s) >= 4 and s not in _STOP:
            out.add(s)
    return out


def sig_overlap(a: set, b: set) -> float:
    """|A and B| / min(|A|,|B|).

    min() rather than union: a closing line paraphrases in five words what an
    earlier line quoted in twenty, so Jaccard on the union scores a correct
    callback at 0.2 and the bar would have to drop so low it matched anything.
    The cost of min() is that a one-word signature matches any statement
    containing that word at 1.0, which is why `_callback_findings` reports the
    signature it matched on and the thin ones are visible in the message.
    """
    if not a or not b:
        return 0.0
    return len(a & b) / float(min(len(a), len(b)))


# --------------------------------------------------------------------------- #
# Sentences, quotes, places
# --------------------------------------------------------------------------- #
_QUOTE = re.compile(r'["\u201c]([^"\u201d]+)["\u201d]')


def _sentences(text: str) -> list:
    """[(offset, sentence)] - split on . ! ? followed by space or end.

    A quotation ending in a question mark inside a sentence splits it, and
    that is accepted: both halves are searched for attributions and places,
    so a split costs nothing except a slightly tighter clause window.
    """
    t = _flat(text)
    out = []
    start = 0
    for m in re.finditer(r"[.!?]+(?=\s|$)", t):
        end = m.end()
        seg = t[start:end].strip()
        if seg:
            out.append((start, seg))
        start = end
    tail = t[start:].strip()
    if tail:
        out.append((start, tail))
    return out


# A GENERAL place lexicon. Nothing here is from any film: these are the nouns
# English uses for "where a scene happened".
#
# "lot" was in the first version and was REMOVED: "the lot" and "a lot of"
# are both common non-place English ("hands over the lot", "a lot of money"),
# and with a locative preposition in front of them ("over the lot") the
# detector read a place that was not there and reported a place contradiction
# against a correct callback. "car park" and "parking lot" survive as
# multi-word entries, which is where the real place sense lives.
_PLACE_WORDS = (
    "car park", "carpark", "parking lot", "petrol station", "gas station",
    "police station", "train station", "bus station", "fire escape",
    "multi storey", "rooftop", "roof", "garage", "street", "road", "avenue",
    "boulevard", "bridge", "footbridge", "overpass", "underpass", "tunnel",
    "kitchen", "bedroom", "bathroom", "living room", "hallway", "corridor",
    "stairwell", "staircase", "basement", "cellar", "attic", "balcony",
    "alley", "alleyway", "dock", "docks", "dockyard", "dockside", "harbour",
    "harbor", "pier", "wharf", "quay", "beach", "school", "classroom",
    "playground", "campus", "office", "boardroom", "warehouse", "factory",
    "workshop", "bar", "pub", "club", "nightclub", "casino", "restaurant",
    "diner", "cafe", "kitchenette", "temple", "shrine", "church", "chapel",
    "mosque", "cemetery", "graveyard", "station", "platform", "airport",
    "runway", "hangar", "track", "racetrack", "circuit", "mountain",
    "hillside", "valley", "forest", "woods", "desert", "field", "farm",
    "hospital", "clinic", "morgue", "prison", "jail", "cell", "courtroom",
    "courthouse", "hotel", "motel", "lobby", "apartment", "flat", "house",
    "mansion", "yard", "garden", "porch", "driveway", "elevator", "lift",
    "carriage", "cockpit", "deck", "bunker", "lighthouse", "market", "shop",
    "store", "mall", "gym", "stadium", "arena", "studio", "library",
    "museum", "theatre", "theater", "cinema", "bank", "barracks", "camp",
    "village", "rooftop bar",
)
# Synonyms folded together, so "roof" and "rooftop" are not a contradiction.
_PLACE_CANON = {
    "rooftop": "roof", "rooftop bar": "roof",
    "docks": "dock", "dockyard": "dock", "dockside": "dock",
    "harbor": "harbour", "quay": "dock", "wharf": "dock",
    "carpark": "car park", "parking lot": "car park", "multi storey":
        "car park",
    "road": "street", "avenue": "street", "boulevard": "street",
    "theater": "theatre", "jail": "prison", "flat": "apartment",
    "pub": "bar", "nightclub": "club", "woods": "forest",
    "racetrack": "track", "circuit": "track",
}
# NAIVE EQUALITY WAS WRONG. A setup line that says "classroom" and a closing
# line that says "school" do not contradict each other; the first version
# reported them as a place error, which teaches writers that the gate does not
# understand English and should be worked around. A place CONTAINS another
# place here, and a containment is agreement.
_PLACE_INSIDE = {
    "classroom": "school", "playground": "school", "campus": "school",
    "platform": "station", "runway": "airport", "hangar": "airport",
    "cell": "prison", "courtroom": "courthouse", "lobby": "hotel",
    "kitchen": "house", "bedroom": "house", "bathroom": "house",
    "hallway": "house", "basement": "house", "attic": "house",
    "balcony": "house", "porch": "house", "driveway": "house",
    "garden": "house", "boardroom": "office", "pier": "dock",
    "deck": "dock", "roof": "building", "stairwell": "building",
    "elevator": "building", "lift": "building", "corridor": "building",
}
_LOC_PREP = (r"(?:in|on|at|inside|outside|above|below|under|underneath|"
             r"beneath|near|by|beside|across|onto|into|through|from|around|"
             r"behind|atop|toward|towards|up|down|over|off|along|past)")
_PLACE_RE = re.compile(
    r"\b" + _LOC_PREP +
    r"\s+(?:the|a|an|his|her|their|its|that|this|some|another|different|"
    r"same|each|every|one|two|both)?\s*(?:[a-z]+\s+)?(" +
    "|".join(sorted((w.replace(" ", r"\s+") for w in _PLACE_WORDS),
                    key=len, reverse=True)) + r")\b")


def places(text) -> set:
    """Canonical place nouns in `text`, each introduced by a locative word.

    THE LOCATIVE PREPOSITION IS REQUIRED, and that was the second attempt. The
    first matched any occurrence of a place noun, which made "a garage band",
    "street smart" and "the school of thought" into scene locations. Demanding
    "in/on/at/outside ... <place>" costs the rare bare locative ("Tokyo,
    rooftop, midnight") and buys a detector whose findings are worth reading.
    """
    out = set()
    for m in _PLACE_RE.finditer(_norm(text)):
        w = re.sub(r"\s+", " ", m.group(1))
        out.add(_PLACE_CANON.get(w, w))
    return out


def places_agree(a: set, b: set) -> bool:
    """Do two place sets name a compatible location?"""
    if not a or not b:
        return True                  # nothing to contradict
    for x in a:
        for y in b:
            if x == y:
                return True
            if _PLACE_INSIDE.get(x) == y or _PLACE_INSIDE.get(y) == x:
                return True
            if (_PLACE_INSIDE.get(x) is not None
                    and _PLACE_INSIDE.get(x) == _PLACE_INSIDE.get(y)):
                return True
    return False


# --------------------------------------------------------------------------- #
# Attributions
# --------------------------------------------------------------------------- #
# A NAME is a capitalised token. Capitalised function words are excluded by
# list rather than by position, because a draft line routinely starts with
# "Then", "Tyres" or "Weeks" and a positional rule ("ignore the first word")
# would also ignore a real name in the first word, which is where names
# usually are.
_NOT_NAME = {
    "the", "then", "and", "but", "so", "now", "here", "there", "that", "this",
    "these", "those", "what", "when", "why", "who", "whom", "whose", "how",
    "where", "it", "he", "she", "they", "we", "you", "i", "a", "an", "after",
    "before", "later", "weeks", "months", "years", "days", "minutes", "once",
    "meanwhile", "inside", "outside", "somewhere", "nobody", "everyone",
    "someone", "another", "both", "neither", "either", "one", "two", "three",
    "from", "with", "without", "across", "above", "below", "beside", "every",
    "his", "her", "their", "our", "my", "your", "its", "not", "no", "yes",
    "cut", "tyres", "tires", "friends", "enter", "still", "even", "just",
    "if", "while", "because", "since", "until", "though", "although",
}
# The exclusion is a LOOKAHEAD inside the pattern, not a filter applied to the
# match afterwards. Filtering afterwards was the first version and it was
# worse than useless: `[A-Z][a-z]+(\s+[A-Z][a-z]+)?` is greedy, so "So Sean
# asks it straight" matched the two-word name "So Sean", the filter threw the
# whole attribution away, and `finditer` resumed AFTER the rejected span - so
# the real name inside it was never seen and the line was indexed as having no
# attribution at all. A lookahead makes the engine retry at the next position.
_NOT_NAME_ALT = "|".join(sorted((w[:1].upper() + w[1:] for w in _NOT_NAME),
                                key=len, reverse=True))
_NAME_WORD = r"(?!(?:" + _NOT_NAME_ALT + r")\b)[A-Z][a-z]+"
_NAME = (r"(?:" + _NAME_WORD + r"(?:\s+" + _NAME_WORD + r")?|[A-Z]{2,4}\b)")
_PRON = r"(?:him|her|them|me|us|you|himself|herself)"
# Nouns that name an UTTERANCE. The presence of one is what makes a closing
# clause a callback to something somebody said, as opposed to narration of
# what is happening on screen now.
_UTTER_NOUN = (r"(?:question|questions|line|lines|words|word|answer|answers|"
               r"advice|warning|warnings|promise|promises|threat|threats|"
               r"joke|jokes|remark|remarks|speech|phrase|lesson|lessons|"
               r"rule|rules|point|claim|claims|boast|boasts|offer|offers|"
               r"complaint|complaints|statement|statements|verdict|sermon)")
_SAY_PAST = (r"(?:said|told|asked|promised|warned|answered|replied|"
             r"insisted|admitted|claimed|swore|added)")
_SAY_PRES = (r"(?:says|tells|asks|promises|warns|answers|replies|"
             r"insists|admits|claims|swears|adds)")
_SAY_PLAIN = r"(?:" + _SAY_PAST[3:-1] + r"|" + _SAY_PRES[3:-1] + r")"
# "gave", "put to" and "offered" only make sense as attributions when an
# utterance NOUN is already present ("the line X gave him"). In the bare
# shape they are ordinary transitive verbs - "DK puts a pistol in his face"
# indexed a pistol as a statement - so they are admitted to the
# noun-anchored patterns only.
_SAY_ANY = (r"(?:" + _SAY_PLAIN[3:-1]
            + r"|gave|gives|put|puts|offered|offers)")

# The four attribution shapes. P1-P3 are CALLBACK-shaped: each one refers to
# an utterance as an object ("the question X asked Y", "what X said", "X's
# line"), which is how a closing line reaches back to an earlier scene. P4 is
# the plain narration shape ("X says ...") and is used when indexing the
# earlier lines; in a CLOSING line only its PAST tense counts, because "X
# says" in the closer is the narrator describing the scene on screen right
# now, not calling anything back.
_P_NOUN = re.compile(
    r"\b(?:the|that|his|her|their)\s+(?P<noun>" + _UTTER_NOUN + r")\s+"
    r"(?P<sp>" + _NAME + r")\s+(?P<vb>" + _SAY_ANY + r")"
    r"(?:\s+to)?(?:\s+(?P<ad>" + _NAME + r"|" + _PRON + r"))?")
_P_WHAT = re.compile(
    r"\bwhat\s+(?P<sp>" + _NAME + r")\s+(?P<vb>" + _SAY_ANY + r")"
    r"(?:\s+to\s+(?P<ad>" + _NAME + r"|" + _PRON + r"))?")
_P_POSS = re.compile(
    r"\b(?P<sp>" + _NAME + r")'s\s+(?P<noun>" + _UTTER_NOUN + r")")
_P_PLAIN = re.compile(
    r"\b(?P<sp>" + _NAME + r")\s+(?P<vb>" + _SAY_PLAIN + r")"
    r"(?:\s+to)?(?:\s+(?P<ad>" + _NAME + r"|" + _PRON + r"))?")

_QUESTION_NOUNS = {"question", "questions"}
_QUESTION_VERBS = {"asked", "asks"}
_Q_OPEN = re.compile(
    r"^(?:so\s+|and\s+|but\s+)?(?:what|why|who|whom|whose|how|when|where|"
    r"which|whether|if)\b", re.I)
_Q_AUX = re.compile(
    r"\b(?:do|does|did|dont|doesnt|didnt|are|is|was|were|can|could|will|"
    r"would|should|have|has|had|am)\s+(?:you|he|she|they|we|i|it)\b", re.I)


def _clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", _flat(s)).strip(" ,.;:'\"")


def _is_name(s: str) -> bool:
    """Belt and braces behind the lookahead in _NAME.

    `.strip("'s")` was used here and is a trap worth recording: str.strip
    takes a SET of characters, so "so".strip("'s") is "o", which is not in the
    exclusion list, and every sentence-initial "So" passed as a surname. Use
    an anchored substitution.
    """
    s = _clean_name(s)
    if not s:
        return False
    first = re.sub(r"'s$", "", s.split()[0].lower())
    return first not in _NOT_NAME


def is_question(text) -> bool:
    """Does this text read as an interrogative?

    Three signals, any of which is enough: a question mark, an interrogative
    opener, or an inverted auxiliary with a pronoun subject. Not a parser -
    deliberately a floor, used only to compare an utterance against the NOUN
    the closing line filed it under.
    """
    t = _flat(text).strip()
    if "?" in t:
        return True
    if _Q_OPEN.match(t):
        return True
    return bool(_Q_AUX.search(_norm(t)))


def attributions(text: str, closing: bool = False) -> list:
    """Every attribution in `text`, as

        {"at", "end", "kind", "noun", "speaker", "addressee", "verb"}

    `at`/`end` are offsets into the (flattened) text. `closing=True` drops the
    plain present-tense shape, which in a closing line is narration of the
    current scene rather than a callback.
    """
    t = _flat(text)
    found: list = []
    for kind, pat in (("noun", _P_NOUN), ("what", _P_WHAT),
                      ("poss", _P_POSS), ("plain", _P_PLAIN)):
        for m in pat.finditer(t):
            sp = _clean_name(m.group("sp") or "")
            if not _is_name(sp):
                continue
            ad = ""
            if "ad" in (m.groupdict() or {}) and m.group("ad"):
                ad = _clean_name(m.group("ad"))
                # "tells it like he was in on it" - an addressee slot filled
                # by a non-person is not an addressee, and taking it as one
                # invented an attribution in a line that had none.
                if (ad.lower() not in ("him", "her", "them", "me", "us",
                                       "you", "himself", "herself")
                        and not _is_name(ad)):
                    ad = ""
            vb = (m.groupdict().get("vb") or "").lower()
            if closing and kind == "plain" and vb and not re.fullmatch(
                    _SAY_PAST, vb):
                continue
            found.append({
                "at": m.start(), "end": m.end(), "kind": kind,
                "noun": (m.groupdict().get("noun") or "").lower(),
                "speaker": sp, "addressee": ad, "verb": vb,
                "raw": m.group(0),
            })
    # De-overlap: keep the most specific match at each position. "the question
    # Sean asked Han" matches both _P_NOUN and _P_PLAIN; keeping both would
    # double-count the same callback and report it twice.
    found.sort(key=lambda f: (f["at"], -(f["end"] - f["at"])))
    out: list = []
    for f in found:
        if any(f["at"] < o["end"] and o["at"] < f["end"] for o in out):
            continue
        out.append(f)
    return out


def _speaker_for_quote(attrs: list, qstart: int) -> str:
    """The speaker of a quote at `qstart`: nearest attribution before it.

    Falls back to the nearest one AFTER the quote, because "'Pick a car,' the
    older man tells him" is as common as the other order. Returns "" when the
    line attributes nothing, and "" is carried through as UNKNOWN rather than
    guessed - an unknown speaker can neither contradict a callback nor
    corroborate one, and the gate says which it is.
    """
    before = [a for a in attrs if a["end"] <= qstart]
    if before:
        return max(before, key=lambda a: a["end"])["speaker"]
    after = [a for a in attrs if a["at"] >= qstart]
    if after:
        return min(after, key=lambda a: a["at"])["speaker"]
    return ""


def _narr(ln) -> str:
    if not isinstance(ln, dict):
        return ""
    return str(ln.get("narration") or "").strip()


def _beat_of(ln) -> str:
    """The beat id a line is filed under, normalised to B<nn>, or ''."""
    m = re.match(r"\s*B(\d{1,3})\b", str((ln or {}).get("note") or ""))
    return f"B{int(m.group(1)):02d}" if m else ""


def statement_index(lines: list) -> list:
    """Every statement the draft attributes to somebody, in draft order.

    One entry per quoted span and one per attribution with an unquoted trailing
    clause:

        {"pos", "id", "beat", "speaker", "content", "sig", "quoted"}

    `pos` is the index in the narrated-line list, so "earlier than the closing
    line" is a comparison rather than a guess about ids (draft ids are not
    contiguous - the live project's 105 narrated lines run to id 114).
    """
    out: list = []
    for pos, ln in enumerate(lines):
        text = _flat(_narr(ln))
        if not text:
            continue
        attrs = attributions(text)
        lid = (ln or {}).get("id")
        beat = _beat_of(ln)
        for qm in _QUOTE.finditer(text):
            inner = qm.group(1).strip()
            out.append({"pos": pos, "id": lid, "beat": beat,
                        "speaker": _speaker_for_quote(attrs, qm.start()),
                        "content": inner, "sig": content_sig(inner),
                        "quoted": True})
        # Unquoted reported speech. The draft narrates most of its dialogue
        # this way ("X says only that ..."), so indexing only quotations would
        # leave the majority of the draft's statements out of the index and
        # every callback to them would come back "uncheckable".
        for a in attrs:
            tail = text[a["end"]:]
            tail = re.split(r"(?<=[.!?])\s", tail, maxsplit=1)[0]
            tail = _QUOTE.sub(" ", tail).strip(" ,;:-")
            if not tail:
                continue
            out.append({"pos": pos, "id": lid, "beat": beat,
                        "speaker": a["speaker"], "content": tail,
                        "sig": content_sig(tail), "quoted": False})
    return out


# --------------------------------------------------------------------------- #
# Message helpers
# --------------------------------------------------------------------------- #
def _cap(items, n: int) -> str:
    """At most `n` ids, then a count of the rest.

    pipeline/review_artifacts.py has the same three lines as a private `_cap`.
    Duplicated here rather than reaching into that module's privates for a
    FORMATTER: nothing about a measurement depends on it, and the two are free
    to diverge. Every helper that affects a verdict is reused, not copied.
    """
    xs = [str(x) for x in items]
    head = ", ".join(xs[:n])
    return head + (f" (+{len(xs) - n} more)" if len(xs) > n else "")


def _snip(s, n: int = 110) -> str:
    t = re.sub(r"\s+", " ", _flat(s)).strip()
    return t if len(t) <= n else t[: n - 3] + "..."


def _ids_in(findings: list) -> list:
    """The line ids named at the head of each per-line finding, de-duplicated.

    Every finding string this module builds opens "line <id> ...". Read back
    rather than carried alongside, with a guard: a finding that somehow does
    not open that way is simply not counted in the id list instead of taking
    the whole report down with an AttributeError.
    """
    out: list = []
    for f in findings:
        m = re.match(r"line (\S+?)[ :,]", str(f))
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


# --------------------------------------------------------------------------- #
# [CALLBACK-ATTRIBUTION]
# --------------------------------------------------------------------------- #
def _callback_findings(window: list, lines: list, beatmap: dict,
                       match_min: float, min_sig: int = 2) -> tuple:
    """(errors_data, warns_data, attributions_found, statements_indexed).

    Three findings, all about a closing line contradicting the draft's own
    earlier text:

      SPEAKER  the content matched an earlier statement and the closing line
               names a different speaker for it.
      PLACE    the closing clause names a scene location and the setup names a
               different one.
      KIND     the closing line files the content under an utterance noun the
               content is not - a statement introduced as "the question X
               asked Y".

    KIND is here because it is the only one of the three that catches the
    original fault from the inside. When a draft quotes one character's thesis
    inside ANOTHER character's question about it - which is exactly how the
    shipped draft recorded the scene - the content words of the two are the
    same, so a content-signature matcher corroborates the wrong speaker and
    stays silent. What does NOT survive is the grammar: a question and a
    statement are different shapes, and "the question A asked B" followed by a
    declarative sentence is wrong on the face of it. Reported under the same
    gate because it is the same defect, and the message says which signal
    fired so the writer is not sent hunting.
    """
    errs: list = []
    warns: list = []
    found: list = []
    index = statement_index(lines)
    stat_count = len(index)
    wpos = {id(ln) for ln in window}
    for ln in window:
        text = _flat(_narr(ln))
        lid = (ln or {}).get("id")
        for off, sent in _sentences(text):
            for a in attributions(sent, closing=True):
                content, cstart = _callback_content(sent, a["end"])
                clause = _clause_of(sent, a["at"], cstart)
                rec = {"line": lid, "speaker": a["speaker"],
                       "addressee": a["addressee"], "noun": a["noun"],
                       "verb": a["verb"], "content": _snip(content, 80),
                       "clause": _snip(clause, 80)}
                found.append(rec)

                # ---- KIND ------------------------------------------------ #
                want_q = (a["noun"] in _QUESTION_NOUNS
                          or (not a["noun"] and a["verb"] in _QUESTION_VERBS))
                is_q = is_question(content)
                if content and want_q and not is_q:
                    errs.append(
                        f"line {lid} introduces the content as "
                        f"{'the ' + a['noun'] if a['noun'] else 'a question'} "
                        f"{a['speaker']} asked"
                        + (f" {a['addressee']}" if a["addressee"] else "")
                        + f", but \"{_snip(content, 70)}\" is a STATEMENT, not "
                          f"a question - so either the speaker is wrong (it is "
                          f"the reply, not the asking) or the noun is")
                elif content and a["noun"] and not want_q and is_q:
                    errs.append(
                        f"line {lid} calls the content "
                        f"{a['speaker']}'s {a['noun']}, but "
                        f"\"{_snip(content, 70)}\" is a QUESTION")

                # ---- SPEAKER and PLACE ----------------------------------- #
                sig = content_sig(content)
                if not sig:
                    warns.append(
                        f"line {lid}: the callback attributed to "
                        f"{a['speaker']} has no content words long enough to "
                        f"match ({_snip(content, 50)!r}), so its attribution "
                        f"CANNOT BE MEASURED")
                    continue
                cands = []
                for st in index:
                    if id(lines[st["pos"]]) in wpos:
                        continue              # don't match the closer itself
                    ov = sig_overlap(sig, st["sig"])
                    if ov >= match_min:
                        cands.append((ov, st))
                if not cands:
                    warns.append(
                        f"line {lid} attributes \"{_snip(content, 50)}\" to "
                        f"{a['speaker']}, and no earlier narrated line says "
                        f"anything matching it - an UNCHECKABLE callback. It "
                        f"may be a callback to something only the footage "
                        f"showed; a reader has to confirm it")
                    continue
                cands.sort(key=lambda c: (-c[0], -c[1]["pos"]))
                best = cands[0][1]
                named = [c for c in cands if c[1]["speaker"]]
                # Corroboration beats contradiction: if ANY matching earlier
                # statement is attributed to the same speaker, the callback is
                # supported and no speaker finding is raised. The first version
                # compared only against the single best match and accused a
                # correct callback whenever a second, closer-scoring line
                # happened to quote a different character saying the same
                # words.
                agree = [c for c in named
                         if c[1]["speaker"].lower() == a["speaker"].lower()]
                # A SIGNATURE THIS THIN CANNOT ESTABLISH WHO SPOKE.
                #
                # Found by running the gate on a corrected draft: the closer
                # called back a mentor's one-line thesis, and an earlier line
                # carried the protagonist's QUESTION about that thesis. Both
                # reduce to one content word, min()-overlap scored them 1.00,
                # and the gate reported a speaker contradiction on a line
                # that was right - a question about a statement is not the
                # statement.
                #
                # The guard is on the SPEAKER verdict only. A first version
                # dropped thin matches entirely and that was wrong: it also
                # silenced the PLACE contradiction on the frozen fixture,
                # where the same thin signature still locates the right
                # scene. Thin words can find the scene; they cannot say whose
                # mouth they came out of. The claim in the first version's
                # own comment - that this "costs nothing real" - was false,
                # and the fixture caught it.
                _thin = min(len(sig), len(best["sig"])) < min_sig
                if _thin and named and not agree:
                    warns.append(
                        f"line {lid} attributes \"{_snip(content, 50)}\" to "
                        f"{a['speaker']} while line {named[0][1]['id']} "
                        f"attributes it to {named[0][1]['speaker']}, but the "
                        f"match rests on only "
                        f"{min(len(sig), len(best['sig']))} content word(s) "
                        f"({sorted(sig & best['sig'])}), which cannot "
                        f"establish a speaker - a question about a statement "
                        f"shares its content words. Reported, not failed")
                if named and not agree and not _thin:
                    ov, st = named[0]
                    errs.append(
                        f"line {lid} attributes \"{_snip(content, 60)}\" to "
                        f"{a['speaker']}, but line {st['id']} attributes the "
                        f"same words to {st['speaker']} "
                        f"({ov:.0%} content-word overlap on "
                        f"{sorted(sig & st['sig'])}). One of the two names the "
                        f"wrong speaker")
                elif not named:
                    warns.append(
                        f"line {lid} attributes \"{_snip(content, 50)}\" to "
                        f"{a['speaker']}; the matching earlier line "
                        f"{best['id']} quotes those words but names no "
                        f"speaker, so the attribution CANNOT BE MEASURED")

                # The setup line for the place check is the best-matching
                # earlier statement's line, PLUS that line's beat text from the
                # beat map when one is available. The draft almost never names
                # a location in the line that carries the dialogue - the live
                # project's setup line does not - while the beat map names one
                # for every beat, because that is what a beat map is for. Using
                # the draft alone made this check structurally unable to fire
                # on the defect it was written for.
                setup = agree[0][1] if agree else best
                sline = lines[setup["pos"]]
                sp_places = places(_narr(sline))
                bsrc = f"line {setup['id']}"
                if setup["beat"] and setup["beat"] in (beatmap or {}):
                    bp = places(beatmap[setup["beat"]].get("what", ""))
                    if bp:
                        sp_places = sp_places | bp
                        bsrc = f"line {setup['id']} / beat {setup['beat']}"
                cl_places = places(clause)
                if cl_places and sp_places and not places_agree(cl_places,
                                                                sp_places):
                    errs.append(
                        f"line {lid} puts the callback "
                        f"{'in/at the ' + sorted(cl_places)[0]} "
                        f"(\"{_snip(clause, 60)}\"), but the setup it matches "
                        f"happens at the "
                        f"{'/'.join(sorted(sp_places))} ({bsrc}). A callback "
                        f"that relocates its own setup scene reads as a "
                        f"different scene")
    return errs, warns, found, stat_count


def _clause_of(sentence: str, at: int, upto: int) -> str:
    """The comma-delimited clause containing offset `at`, up to `upto`.

    "The same clause as the attribution" taken literally. The whole SENTENCE
    was used first and over-reached: a closing sentence routinely opens on an
    unrelated image ("the crowd on the street"), and reading its place noun as
    the callback's location reported a contradiction between two clauses that
    were never about the same scene.
    """
    head = sentence[: max(0, upto)] if upto > at else sentence
    cuts = [0] + [m.end() for m in re.finditer(r",\s*", head)]
    start = max([c for c in cuts if c <= at] or [0])
    return head[start:]


def _callback_content(sentence: str, attr_end: int) -> tuple:
    """(content, start_offset) - what the closing line attributes.

    Order: after a colon, else the first quotation, else the trailing clause.
    The colon comes first because that is the shape the defect used and it is
    the shape a paraphrased callback takes - a quotation would have been
    checkable by the quote index alone.
    """
    tail = sentence[attr_end:]
    ci = tail.find(":")
    if ci >= 0:
        return tail[ci + 1:].strip(), attr_end + ci + 1
    qm = _QUOTE.search(tail)
    if qm:
        return qm.group(1).strip(), attr_end + qm.start(1)
    qm = _QUOTE.search(sentence)
    if qm:
        return qm.group(1).strip(), qm.start(1)
    return tail.strip(" ,;:-"), attr_end


# --------------------------------------------------------------------------- #
# [ENDING-PERSONA]
# --------------------------------------------------------------------------- #
# PROTECTIVE markers: the narrator has declared it is ON this character's side.
# Surface words, and a surface rule is honest about being one - the gate's job
# is to notice a declared attitude, not to interpret the paragraph.
_PROTECT = re.compile(
    r"\b(?:protective|protect|sympathetic|sympathy|defend(?:s|ed|ing)?|"
    r"honour(?:s|ed)?|honor(?:s|ed)?|respect(?:s|ed|ful)?|loyal(?:ty)?|"
    r"kind(?:ly|ness)?|deserve(?:s|d)?|mourn(?:s|ed)?|love(?:s|d)?|"
    r"root(?:s|ing)? for|credit(?:s|ed)?|admire(?:s|d)?|forgiv\w*|"
    r"never mock\w*|not a fool|no fool)\b", re.I)
# "never hated" was in that list and is OUT. The live attitude card opens one
# bullet "wary, never hated" - an attitude that is explicitly NOT protective -
# and with "never hated" as a marker every character on the card came back
# protected, which makes the gate fire on any blame of anybody and tells the
# writer nothing. A marker has to separate the characters the narrator defends
# from the ones it merely refuses to caricature.
# BLAME markers: the closing line is making somebody the cause of a loss.
_BLAME = re.compile(
    r"\b(?:cost (?:him|her|them|he|she)\b|to blame\b|at fault\b|his fault\b|"
    r"her fault\b|their fault\b|the fault of\b|ruin(?:s|ed)?\b|"
    r"wreck(?:s|ed)? (?:his|her|their|him|them)\b|destroy(?:s|ed)?\b|"
    r"let (?:him|her|them) down\b|betray(?:s|ed)? (?:him|her|them)\b|"
    r"got (?:him|her|them) into\b|is why (?:he|she|they) lost\b|"
    r"drag(?:s|ged)? (?:him|her|them)\b|lost (?:him|her|them) (?:his|her|"
    r"their|the)\b)", re.I)


def attitudes(raw: str) -> list:
    """The `## ATTITUDE TO CHARACTERS` bullets.

    [{"name", "aliases", "line", "protective", "marker"}] in document order, or
    [] when the section is absent - which the caller reports as a NOTE rather
    than treating as "no protected characters", because an absent section would
    otherwise make this gate pass on every draft, the exact failure mode
    pipeline/angle_spec.py `require` exists to refuse.
    """
    m = re.search(_SECTION.format(t=re.escape("ATTITUDE TO CHARACTERS")),
                  _flat(raw), re.M | re.S)
    if not m:
        return []
    out: list = []
    for bullet in re.split(r"(?m)^\s*[-*]\s+", m.group(1)):
        t = " ".join(bullet.split()).strip()
        if not t:
            continue
        nm = re.match(r"\*\*(?P<n>[^*]+)\*\*", t)
        if not nm:
            continue
        head = nm.group("n")
        # Drop a parenthetical gloss: a bullet head carries production notes
        # in brackets in the live project, and those are prose, not names.
        head = re.sub(r"\([^)]*\)", " ", head)
        aliases = [a for a in (x.strip(" .;:-*_") for x in
                               re.split(r"/|;|,| or ", head)) if a]
        aliases = [a for a in aliases if len(a) >= 2]
        if not aliases:
            continue
        pm = _PROTECT.search(t)
        out.append({"name": aliases[0], "aliases": aliases, "line": t,
                    "protective": bool(pm),
                    "marker": pm.group(0) if pm else ""})
    return out


def _name_positions(words: list, alias: str) -> list:
    """Word indices where `alias` occurs (whole-word, case-insensitive)."""
    toks = _norm(alias).split()
    if not toks:
        return []
    out = []
    for i in range(len(words) - len(toks) + 1):
        if words[i:i + len(toks)] == toks:
            out.append(i)
    return out


def _persona_findings(window: list, cards: list, blame_window: int) -> list:
    """Closing lines whose blame contradicts a declared protective attitude."""
    errs: list = []
    prot = [c for c in cards if c["protective"]]
    allnames = [a for c in cards for a in c["aliases"]]
    for ln in window:
        text = _flat(_narr(ln))
        lid = (ln or {}).get("id")
        for off, sent in _sentences(text):
            for bm in _BLAME.finditer(sent):
                clause = _snip(sent, 150)
                words = _norm(sent).split()
                # Word index of the marker inside the normalised sentence.
                mpos = len(_norm(sent[: bm.start()]).split())
                hit = None
                for c in prot:
                    for a in c["aliases"]:
                        for i in _name_positions(words, a):
                            if abs(i - mpos) <= blame_window:
                                hit = (c, a, abs(i - mpos))
                                break
                        if hit:
                            break
                    if hit:
                        break
                if hit:
                    c, a, dist = hit
                    errs.append(
                        f"line {lid} blames {a} ({dist} word(s) from "
                        f"\"{bm.group(0)}\"), but angle.md's ATTITUDE TO "
                        f"CHARACTERS says of {c['name']}: \"{_snip(c['line'], 150)}\" "
                        f"(protective marker \"{c['marker']}\"). The offending "
                        f"clause is \"{clause}\". The closing attitude "
                        f"contradicts the declared one")
                    continue
                # NOBODY NAMED. A blame clause whose agent is a definite
                # description ("the last stranger who ...") cannot be checked
                # against the attitude card at all, and in the closing window
                # that is an ERROR rather than a shrug: the house rule is that
                # what cannot be measured is said out loud, never passed
                # silently. It is also the exact shape the original defect
                # took - the protected character was blamed without being
                # named, so a name-proximity rule alone was structurally
                # blind to it. The fix asked for is cheap: name whoever the
                # clause blames, and the proximity check above then verifies
                # the attitude.
                if not any(_name_positions(words, a) for a in allnames):
                    errs.append(
                        f"line {lid} assigns blame - \"{bm.group(0)}\" - to "
                        f"someone the clause never names: \"{clause}\". The "
                        f"attitude card declares an attitude to "
                        f"{_cap([c['name'] for c in cards], 8)}, and which of "
                        f"them this blames CANNOT BE MEASURED, so it is not a "
                        f"pass. Name the character the clause blames (or drop "
                        f"the blame): "
                        + (f"the card is PROTECTIVE of "
                           f"{_cap([c['name'] for c in prot], 8)}"
                           if prot else "no character is marked protective"))
    return errs


# --------------------------------------------------------------------------- #
# [ENDING-READ]
# --------------------------------------------------------------------------- #
def _ending_read(window: list, pdir: Path, cap: int) -> dict:
    """The dedicated cold read of the closing window: exists, current, closed.

    Every measurement here is pipeline/review_artifacts.py's, reused rather
    than reimplemented: `parse_artifact` for the fence format, `line_signature`
    for the staleness rule, `_closes` for finding closure. Two of those are
    PRIVATE (`_closes`, `_norm_id`) and are used as privates on purpose -
    copy-pasting them would create a second copy of the staleness and closure
    rules that could silently disagree with the first, which is the failure
    `line_signature`'s own docstring exists to prevent. They are named in this
    module's report so the coupling is on the record.
    """
    from pipeline import review_artifacts as ra

    E: list = []
    N: list = []
    S: dict = {"exists": False, "required_ids": [], "signed": 0,
               "missing": [], "stale": [], "findings": 0, "unresolved": 0,
               "malformed": 0}
    path = Path(pdir) / ENDING_READ_NAME
    need = {}
    for ln in window:
        t = _narr(ln)
        if t:
            need[ra._norm_id((ln or {}).get("id"))] = ra.line_signature(t)
    S["required_ids"] = sorted(need)

    if not path.exists():
        E.append(
            f"[ENDING-READ] no {ENDING_READ_NAME} in {Path(pdir).name}: "
            f"{len(need)} closing line(s) ({_cap(sorted(need), cap)}) have had "
            f"no dedicated read. Write {path}, by an agent that DID NOT write "
            f"the draft, reading ONLY the closing window - the last lines the "
            f"viewer hears are where a misattributed callback, a contradicted "
            f"attitude and a misread speaker all survived every counter in "
            f"this repo. Format is pipeline/review_artifacts.py's: a "
            f"```review-signatures``` fence of `<id> <sig8>` rows and a "
            f"```review-findings``` fence of `STATUS | kind | ids | text`.")
        return {"errors": E, "notes": N, "stats": S}
    S["exists"] = True

    art = ra.parse_artifact(path)
    if art["errors"]:
        S["malformed"] = len(art["errors"])
        E.append(
            f"[ENDING-READ] {len(art['errors'])} malformed entr(ies) in "
            f"{ENDING_READ_NAME}: " + _cap(art["errors"], cap)
            + ". They were NOT skipped and NOT counted as read; fix the shape "
              "and re-run. Prose belongs outside the fences.")

    sigs = art["signatures"]
    S["signed"] = len(sigs)
    missing = sorted(k for k in need if k not in sigs)
    stale = sorted(k for k in need if k in sigs and sigs[k] != need[k])
    S["missing"], S["stale"] = missing, stale
    if not need:
        N.append(
            f"[ENDING-READ] the draft has no narrated closing line(s), so "
            f"{ENDING_READ_NAME} coverage CANNOT BE MEASURED. This is not a "
            f"pass.")
    # AN EDIT MADE TO CLOSE A FINDING IS NOT AN UNREAD LINE.
    #
    # Found by running the gate: the ending read produced 16 findings, fixing
    # them rewrote all five closing lines, and the 100% bar then reported 0 of
    # 5 signed - so the read went stale precisely because it was acted on, and
    # the only way to pass was to read the ending carefully and change
    # nothing. review_artifacts already had this rule and this gate did not,
    # which made the two inconsistent about the same question.
    #
    # The bar stays 100%. What changes is what counts as covered: a line whose
    # CURRENT text differs from the signature, but which a RESOLVED or
    # ANSWERED finding in this artifact names, is accounted for. A line that
    # changed and is named nowhere is still an error - that is the case that
    # catches an unreviewed edit, and it is unaffected.
    _closed_ids: set = set()
    for _f in (art.get("findings") or []):
        if str(_f.get("status") or "").upper() in ("RESOLVED", "ANSWERED"):
            for _i in (_f.get("ids") or []):
                _closed_ids.add(str(_i))
    _accounted = [k for k in stale if str(k) in _closed_ids]
    stale = [k for k in stale if str(k) not in _closed_ids]
    S["stale"] = stale
    S["accounted_stale"] = _accounted

    if missing or stale:
        bits = []
        if missing:
            bits.append(f"{len(missing)} line(s) are not signed at all "
                        f"({_cap(missing, cap)})")
        if stale:
            bits.append(f"{len(stale)} line(s) were EDITED after the read and "
                        f"are named in no resolved finding "
                        f"({_cap(stale, cap)})")
        E.append(
            f"[ENDING-READ] {ENDING_READ_NAME} signs "
            f"{len(need) - len(missing) - len(stale)} of {len(need)} closing "
            f"line(s) with the current text: " + "; ".join(bits)
            + f". THE BAR HERE IS 100%, NOT A PERCENTAGE: the window is "
              f"{len(need)} line(s) long, so a percentage bar would let the "
              f"closer itself go unread and still round to a pass. Re-read the "
              f"window and re-sign every line in it.")

    # Findings closure - the same rules as review_artifacts: an ANSWERED needs
    # a real argument, and a FINDING is closed only by a LATER RESOLVED or
    # ANSWERED of the same kind with overlapping ids. The LOOP is re-written
    # because review_artifacts keeps it inside `_check_one`, which also does
    # coverage and cannot be called for a 100% window; the PREDICATE (`_closes`)
    # and the word floor (config.REVIEW_ANSWER_MIN_WORDS) are reused.
    minw = int(getattr(config, "REVIEW_ANSWER_MIN_WORDS", 8))
    finds = art["findings"]
    S["findings"] = sum(1 for f in finds if f["status"] == "FINDING")
    thin = [f for f in finds if f["status"] == "ANSWERED"
            and len(f["text"].split()) < minw]
    valid = [f for f in finds
             if f["status"] in ("RESOLVED", "ANSWERED") and f not in thin]
    if thin:
        E.append(
            f"[ENDING-READ] {len(thin)} ANSWERED entr(ies) in "
            f"{ENDING_READ_NAME} carry fewer than {minw} words of reason: "
            + _cap([f"line {t['at']} ({t['kind']})" for t in thin], cap)
            + ". They close nothing. Argue the case or fix the line.")
    unres = [f for f in finds if f["status"] == "FINDING"
             and not any(ra._closes(f, r) for r in valid if r["at"] > f["at"])]
    S["unresolved"] = len(unres)
    if unres:
        E.append(
            f"[ENDING-READ] {len(unres)} of {S['findings']} finding(s) in "
            f"{ENDING_READ_NAME} are UNRESOLVED: "
            + _cap([f"{f['kind']}@" + (",".join(f["ids"]) or "-")
                    for f in unres], cap)
            + f". Each needs a LATER 'RESOLVED | <kind> | <ids> | what "
              f"changed' or 'ANSWERED | <kind> | <ids> | why the reading is "
              f"wrong' (>= {minw} words) with an overlapping id. An open "
              f"finding on the closer is a defect somebody read and nobody "
              f"acted on.")
    if not E:
        N.append(
            f"[ENDING-READ] {ENDING_READ_NAME} is present and current: all "
            f"{len(need)} closing line(s) signed with the current text "
            f"({_cap(sorted(need), cap)}), {S['findings']} finding(s), all "
            f"closed.")
    return {"errors": E, "notes": N, "stats": S}


# --------------------------------------------------------------------------- #
# the gate
# --------------------------------------------------------------------------- #
def ending_report(draft: dict, pdir: Path) -> dict:
    """CALLBACK-ATTRIBUTION, ENDING-PERSONA and ENDING-READ on the closer.

    {"errors", "warns", "notes", "stats"} - pipeline/pacing_gates.py's
    convention. NEVER raises. Anything this function cannot measure becomes a
    stated "CANNOT BE MEASURED" in `errors` or a NOTE saying which check did
    not run, because a gate that dies on malformed input hands the caller an
    empty report and an empty report is read as a pass by every caller here.
    """
    errors: list = []
    warns: list = []
    notes: list = []
    stats: dict = {}

    # Every bar read from config AT CALL TIME, so moving a constant moves the
    # verdict on the same draft (see tools/test_ending_gates.py).
    win_n = int(getattr(config, "ENDING_WINDOW_LINES", 5))
    match_min = float(getattr(config, "ENDING_CALLBACK_MATCH_MIN", 0.5))
    blame_window = int(getattr(config, "ENDING_BLAME_WINDOW_WORDS", 12))
    cap = int(getattr(config, "ENDING_MAX_IDS_IN_MESSAGE",
                      getattr(config, "REVIEW_MAX_IDS_IN_MESSAGE", 8)))

    try:
        pdir = Path(pdir)
    except Exception:
        return {"errors": ["[ENDING-READ] the project directory could not be "
                           "resolved, so the closing-window gates CANNOT BE "
                           "MEASURED. This is not a pass."],
                "warns": [], "notes": [], "stats": {}}

    # ---- the window ------------------------------------------------------ #
    raw_lines = (draft or {}).get("lines") if isinstance(draft, dict) else None
    if not isinstance(raw_lines, list):
        errors.append(
            "[ENDING-WINDOW] the draft has no readable `lines` list, so the "
            "closing window CANNOT BE MEASURED and none of "
            "CALLBACK-ATTRIBUTION, ENDING-PERSONA or ENDING-READ ran. Nothing "
            "here is a pass.")
        return {"errors": errors, "warns": warns, "notes": notes,
                "stats": {"window_ids": []}}
    unusable = sum(1 for ln in raw_lines if not isinstance(ln, dict))
    lines = [ln for ln in raw_lines if isinstance(ln, dict) and _narr(ln)]
    window = lines[-win_n:] if win_n > 0 else []
    stats["narrated_lines"] = len(lines)
    stats["unreadable_lines"] = unusable
    stats["window_size"] = len(window)
    stats["window_ids"] = [ln.get("id") for ln in window]
    if unusable:
        errors.append(
            f"[ENDING-WINDOW] {unusable} line record(s) in the draft are not "
            f"objects, so whether any of them belongs in the closing window "
            f"CANNOT BE MEASURED. The window below is a best effort, not a "
            f"measurement.")
    if not window:
        errors.append(
            f"[ENDING-WINDOW] the draft has no narrated lines, so the last "
            f"{win_n} of them CANNOT BE MEASURED. The closing-window checks "
            f"did not run; this is not a pass.")
    elif len(window) < win_n:
        notes.append(
            f"[ENDING-WINDOW] the draft has only {len(window)} narrated "
            f"line(s), fewer than the {win_n}-line closing window, so the "
            f"whole draft is the window.")

    # ---- the beat map, for scene locations ------------------------------- #
    beatmap: dict = {}
    try:
        from pipeline import beats_spec
        beatmap = beats_spec.load_beats(pdir) or {}
    except Exception as e:
        notes.append(f"[CALLBACK-ATTRIBUTION] the beat map could not be read "
                     f"({type(e).__name__}: {e}), so a callback's setup "
                     f"LOCATION was checked against the draft text only.")
    if not beatmap:
        notes.append(
            "[CALLBACK-ATTRIBUTION] no beat map in this project, so the place "
            "half of this check sees only what the draft's own lines say about "
            "where a scene happened - which is usually nothing. A place "
            "contradiction can be MISSED here; that is not a pass.")

    # ---- CALLBACK-ATTRIBUTION -------------------------------------------- #
    stats["attributions"] = []
    stats["callback_errors"] = 0
    stats["callback_warns"] = 0
    if window:
        try:
            _min_sig = int(getattr(config,
                                   "ENDING_CALLBACK_MIN_CONTENT_WORDS", 2))
            ce, cw, found, nstat = _callback_findings(window, lines, beatmap,
                                                      match_min, _min_sig)
            stats["attributions"] = found
            stats["statements_indexed"] = nstat
            stats["callback_errors"] = len(ce)
            stats["callback_warns"] = len(cw)
            if ce:
                errors.append(
                    f"[CALLBACK-ATTRIBUTION] {len(ce)} closing-line "
                    f"callback(s) contradict the draft's own earlier text "
                    f"(lines " + _cap(_ids_in(ce), cap)
                    + "): " + "; ".join(ce[:cap])
                    + (f" (+{len(ce) - cap} more)" if len(ce) > cap else "")
                    + ". Fix the attribution, the place or the noun so the "
                      "closer agrees with the scene it is calling back to - "
                      "these are the last words the viewer hears, and a "
                      "callback that names the wrong speaker or the wrong "
                      "room rewrites the scene it is quoting.")
            if cw:
                warns.append(
                    f"[CALLBACK-ATTRIBUTION] {len(cw)} closing-line "
                    f"callback(s) could not be checked against any earlier "
                    f"narrated line: " + "; ".join(cw[:cap])
                    + (f" (+{len(cw) - cap} more)" if len(cw) > cap else "")
                    + ". A warning, not an error: the callback may point at "
                      "something only the footage showed. A reader has to "
                      "confirm each one - that is what ENDING-READ is for.")
        except Exception as e:
            errors.append(
                f"[CALLBACK-ATTRIBUTION] CANNOT BE MEASURED: "
                f"{type(e).__name__}: {e}. Treat this as unchecked "
                f"attributions, not as a pass.")

    # ---- ENDING-PERSONA -------------------------------------------------- #
    stats["protected_characters"] = []
    stats["persona_errors"] = 0
    try:
        from pipeline import angle_spec
        if not (pdir / "angle.md").exists():
            # Same reasoning as pipeline/pacing_gates.py: a project that has
            # not reached the angle stage must not have its OTHER gates killed
            # by this one. It is a NOTE, and the note says the check did not
            # run.
            notes.append(
                f"[ENDING-PERSONA] no angle.md in {pdir.name}, so the "
                f"declared attitudes are unknown and the closing lines were "
                f"NOT checked against them. Nothing about the ending's "
                f"attitude was verified by this run.")
        else:
            try:
                spec = angle_spec.load(pdir)
                raw = str(spec.get("raw") or "")
            except Exception as e:
                raw = ""
                errors.append(
                    f"[ENDING-PERSONA] angle.md could not be parsed "
                    f"({type(e).__name__}: {e}), so the declared attitudes "
                    f"CANNOT BE MEASURED. This is not a pass.")
            cards = attitudes(raw) if raw else []
            stats["attitude_characters"] = [c["name"] for c in cards]
            stats["protected_characters"] = [c["name"] for c in cards
                                             if c["protective"]]
            if raw and not cards:
                notes.append(
                    "[ENDING-PERSONA] angle.md has no `## ATTITUDE TO "
                    "CHARACTERS` section (or no parseable `- **Name** - "
                    "attitude` bullets in it), so there are no declared "
                    "attitudes to contradict and THIS CHECK DID NOT RUN. That "
                    "is not a pass: add the section, or the closing lines are "
                    "unchecked against the persona card.")
            elif cards and window:
                pe = _persona_findings(window, cards, blame_window)
                stats["persona_errors"] = len(pe)
                if pe:
                    errors.append(
                        f"[ENDING-PERSONA] {len(pe)} closing line(s) "
                        f"contradict the attitudes angle.md declares (lines "
                        + _cap(_ids_in(pe), cap) + "): "
                        + "; ".join(pe[:cap])
                        + (f" (+{len(pe) - cap} more)" if len(pe) > cap
                           else "")
                        + f". The attitude card is the contract for how the "
                          f"narrator treats each character; the closer is "
                          f"where the viewer finds out whether it was kept. "
                          f"({len(stats['protected_characters'])} of "
                          f"{len(cards)} character(s) are marked protective, "
                          f"within a {blame_window}-word blame window.)")
    except Exception as e:
        errors.append(
            f"[ENDING-PERSONA] CANNOT BE MEASURED: {type(e).__name__}: {e}. "
            f"Treat this as an unchecked ending attitude, not as a pass.")

    # ---- ENDING-READ ----------------------------------------------------- #
    try:
        r = _ending_read(window, pdir, cap)
        errors.extend(r["errors"])
        notes.extend(r["notes"])
        stats["ending_read"] = r["stats"]
        stats["ending_read_errors"] = len(r["errors"])
    except Exception as e:
        errors.append(
            f"[ENDING-READ] {ENDING_READ_NAME} CANNOT BE MEASURED: "
            f"{type(e).__name__}: {e}. Treat this as a missing read, not as a "
            f"pass.")
        stats["ending_read_errors"] = 1

    return {"errors": errors, "warns": warns, "notes": notes, "stats": stats}
