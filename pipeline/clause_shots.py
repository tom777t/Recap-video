"""Clause-level picture: split a line into visual events, one shot each.

THE DIAGNOSIS, which is the viewer's and not an audit's. The binding problem
was never a wrong shot. A line narrates SEVERAL events while its picture is
one continuous stretch of film, so the picture cannot carry what is said -
and that is why re-binding whole lines failed. Re-pointing a line that
describes three things at one shot just picks which of the three the picture
shows.

So the unit of picture is the CLAUSE, not the line. A line that says "he
hands the money back, then the uncle looks up, then the nephew is told to
leave" needs three shots in film order; a line that says "that is the measure
of the man" needs none of its own.

WHAT DOES NOT GET SPLIT, and this is most of the rule:
  - commentary. A clause with no concrete visible event has no picture to
    find, so it rides on whatever is already on screen.
  - anchors and emotional beats. Dwell is the point there: [PACING-CONTOUR]
    bought those scenes extra lines precisely so the picture could stay put,
    and cutting inside them would spend the dwell it paid for.
  - any line with fewer than two visible events. One event is one shot, which
    is what the draft already does.

CALIBRATED CEILING. Cutting inside lines makes the edit faster, so the rate
has a measured ceiling: two reference recaps the viewer likes run 19.35 and
31.33 cuts per minute (PySceneDetect, config/cut_rate_control.json), ours
runs 22.80, so there is +8.53 cuts/min of headroom. The sub-clip floor is
1.23s - the higher of the two references' p10 shot length. Note that this is
HALF the ~2s the brief expected: these channels routinely hold a shot for
about a second, 38% and 62% of their shots run under two seconds, so a 2s
floor would have been stricter than the references it was meant to match.
"""
from __future__ import annotations

import re

import config

# --------------------------------------------------------------------------- #
# A visible EVENT is something a camera could have been pointed at: an agent
# doing a physical thing. The test is deliberately verb-led rather than
# noun-led, because a noun list is scenery (and [SHOT-LIST] already refuses
# it) while a verb with a subject is a moment.
#
# Written as general English, not from this film's vocabulary: the test for
# that is whether it works on a draft it has not seen.
# --------------------------------------------------------------------------- #
PHYSICAL_VERBS = {
    # motion
    "walk", "walks", "walked", "run", "runs", "ran", "drive", "drives",
    "drove", "arrive", "arrives", "arrived", "leave", "leaves", "left",
    "enter", "enters", "entered", "climb", "climbs", "climbed", "step",
    "steps", "stepped", "turn", "turns", "turned", "stop", "stops",
    "stopped", "sprint", "sprints", "bolt", "bolts", "roll", "rolls",
    "rolled", "slide", "slides", "pull", "pulls", "pulled", "push",
    "pushes", "pushed", "drag", "drags", "dragged", "carry", "carries",
    "lands", "land", "landed", "rises", "rise", "rose", "falls", "fall",
    "fell", "crosses", "cross", "crossed", "follows", "follow", "followed",
    # handling
    "hand", "hands", "handed", "take", "takes", "took", "give", "gives",
    "gave", "throw", "throws", "threw", "drop", "drops", "dropped",
    "pick", "picks", "picked", "open", "opens", "opened", "shut", "shuts",
    "close", "closes", "closed", "hold", "holds", "held", "grab", "grabs",
    "grabbed", "pour", "pours", "poured", "lift", "lifts", "lifted",
    "sign", "signs", "signed", "pay", "pays", "paid", "lend", "lends",
    "lent", "collect", "collects", "collected", "count", "counts",
    # violence / impact
    "hit", "hits", "punch", "punches", "punched", "shoot", "shoots",
    "shot", "crash", "crashes", "crashed", "wreck", "wrecks", "wrecked",
    "slam", "slams", "slammed", "ram", "rams", "rammed", "shove", "shoves",
    "shoved", "detonate", "detonates", "explode", "explodes", "exploded",
    "burn", "burns", "burned", "kill", "kills", "killed", "die", "dies",
    "died", "pin", "pins", "pinned", "scrape", "scrapes", "scraped",
    # speech as a visible act (a mouth moving is a picture)
    "say", "says", "said", "tell", "tells", "told", "ask", "asks", "asked",
    "answer", "answers", "answered", "shout", "shouts", "shouted",
    "call", "calls", "called", "warn", "warns", "warned", "argue",
    "argues", "argued", "refuse", "refuses", "refused", "agree", "agrees",
    "agreed", "explain", "explains", "explained",
    # bodily / reaction
    "look", "looks", "looked", "watch", "watches", "watched", "stare",
    "stares", "nod", "nods", "nodded", "smile", "smiles", "smiled",
    "cry", "cries", "cried", "laugh", "laughs", "laughed", "sit", "sits",
    "sat", "stand", "stands", "stood", "wait", "waits", "waited",
}

# Verbs of thought, judgement and state. A clause whose only verb is one of
# these is COMMENTARY: there is nothing to point a camera at.
NON_VISUAL_VERBS = {
    "is", "are", "was", "were", "be", "been", "being", "am",
    "has", "have", "had", "will", "would", "can", "could", "should",
    "think", "thinks", "thought", "know", "knows", "knew", "mean", "means",
    "meant", "believe", "believes", "want", "wants", "wanted", "need",
    "needs", "needed", "seem", "seems", "seemed", "matter", "matters",
    "count", "counts", "deserve", "deserves", "remember", "remembers",
    "forget", "forgets", "understand", "understands", "decide", "decides",
    "decided", "choose", "chooses", "chose", "learn", "learns", "learned",
}

# Abstractions cannot act on camera. A clause whose subject is one of these
# is a verdict however active its verb looks - "pride costs him", "losing
# finally cost him something". General English, not this film's vocabulary.
ABSTRACT_SUBJECTS = {
    "pride", "love", "loyalty", "trust", "debt", "fear", "grief", "hope",
    "luck", "shame", "guilt", "anger", "respect", "honour", "honor",
    "loss", "losing", "winning", "growth", "change", "failure", "success",
    "power", "ambition", "character", "nerve", "courage", "doubt",
    "regret", "revenge", "justice", "freedom", "truth", "point",
    "problem", "answer", "question", "reason", "difference", "idea",
    "rule", "deal", "thing", "everything", "nothing", "something",
    "anything",
}

# Relational and evaluative verbs: they relate ideas rather than depict acts.
NON_VISUAL_VERBS |= {
    "cost", "costs", "mean", "means", "meant", "prove", "proves", "proved",
    "show", "shows", "showed", "make", "makes", "made", "become",
    "becomes", "became", "stay", "stays", "stayed", "remain", "remains",
    "belong", "belongs", "belonged",
}

# Clause joiners that mark a NEW event rather than a continuation. "and then"
# is a new moment; "and" alone very often is not, so it only counts when it
# is followed by a finite verb with its own subject - handled by the splitter.
HARD_JOIN = re.compile(
    r"(?:,\s*(?:then|and then|before|after|until|while|as)\s+)"
    r"|(?:\.\s+)|(?:;\s*)|(?:\s+-\s+(?=\w))|(?:\s+\u2014\s+)",
    re.IGNORECASE)

SOFT_JOIN = re.compile(r",\s*(?:and|then|but|so)\s+", re.IGNORECASE)

_WORD = re.compile(r"[a-z']+")


def _words(s: str) -> list:
    return _WORD.findall(str(s or "").lower())


_SUBJECT = re.compile(
    r"\b(he|she|they|it|him|her|them|his|their|i|you|we|the|a|an|this|that|"
    r"these|those)\b|\b[A-Z][a-z]{2,}\b")

_MODAL = {"will", "would", "can", "could", "shall", "should", "may",
          "might", "must", "do", "does", "did", "not"}


def is_visual(clause: str) -> tuple:
    """(visual, why). Does this clause name something a camera saw?

    THE DEFAULT IS INVERTED, and the reason is a failed measurement. The
    first version required a verb from an enumerated PHYSICAL_VERBS list and
    found a mean of 1.55 visible events per line where the viewer counted
    about three. An enumerated list cannot win: "cartwheels", "grinds",
    "swarms", "parts", "lights up" are all pictures and none of them are
    going to be on anybody's list.

    So a clause with a subject and a finite verb is an EVENT unless it is
    provably commentary - and "provably commentary" uses the judgment
    classifier the persona gates already calibrated, rather than a second
    opinion invented here. Two detectors that disagree about what counts as
    commentary would be worse than either alone.
    """
    ws = _words(clause)
    if not ws:
        return False, "empty"
    if not _SUBJECT.search(clause):
        return False, "no subject - scenery or a fragment"

    # The narrator's evaluation has no picture of its own.
    try:
        from pipeline.pacing_gates import classify_judgment
        if classify_judgment(clause)[0]:
            return False, "narrator judgment - rides the existing shot"
    except Exception:
        pass

    # THE COST OF THE INVERTED DEFAULT, found by its own fixture: an abstract
    # subject with a relational verb reads as an event. "Pride costs him,
    # every time" has a subject and a finite verb and there is nothing to
    # point a camera at. The judgment classifier does not catch it either, so
    # the guard is on the SUBJECT: an abstraction cannot act on camera.
    first = next((w for w in ws if w not in _MODAL), "")
    if first in ABSTRACT_SUBJECTS:
        return False, f"abstract subject ({first}) - nothing to film"

    content = [w for w in ws if w not in _MODAL]
    stative = [w for w in content if w in NON_VISUAL_VERBS]
    phys = [w for w in content if w in PHYSICAL_VERBS]
    if phys:
        return True, f"physical verb ({', '.join(phys[:3])})"
    # No verb we recognise either way. If every verb-shaped token is stative
    # it is a state, not a moment; otherwise assume a picture, because the
    # list of English verbs that depict something is open and the list of
    # stative ones is nearly closed.
    verbish = [w for w in content
               if w.endswith(("s", "ed", "ing")) and len(w) > 3]
    if verbish and not set(verbish) <= set(stative):
        return True, f"unlisted verb ({verbish[0]})"
    if stative and not phys:
        return False, f"stative verb only ({stative[0]})"
    return False, "no finite verb"


def split_clauses(text: str) -> list:
    """[{text, visual, why}] in reading order.

    Splits on hard joiners first, then on soft joiners only where the
    resulting halves BOTH carry a verb - otherwise ", and the dust settles"
    becomes a clause of its own and the count inflates.
    """
    t = " ".join(str(text or "").split())
    if not t:
        return []
    parts = [p.strip(" ,;-\u2014") for p in HARD_JOIN.split(t) if p
             and p.strip(" ,;-\u2014")]
    out = []
    for p in parts:
        halves = [h.strip(" ,;-\u2014") for h in SOFT_JOIN.split(p)]
        halves = [h for h in halves if h]
        if len(halves) > 1 and all(
                any(w in PHYSICAL_VERBS or w in NON_VISUAL_VERBS
                    for w in _words(h)) for h in halves):
            out.extend(halves)
        else:
            out.append(p)
    res = []
    for c in out:
        v, why = is_visual(c)
        res.append({"text": c, "visual": v, "why": why})
    return res


def visual_events(text: str) -> int:
    """How many distinct visible events this line narrates."""
    return sum(1 for c in split_clauses(text) if c["visual"])


def splittable(line: dict, anchor_beats: set = frozenset(),
               protect_deliveries: tuple = ()) -> tuple:
    """(ok, why) - may this line's picture be cut inside?

    The exclusions are the point: everything that earns continuous footage
    keeps it, and only a line that genuinely narrates past its picture is
    touched.
    """
    text = str(line.get("narration") or "").strip()
    if not text:
        return False, "no narration - a hold keeps its footage"
    beat = str(line.get("note") or "").split()[0] if line.get("note") else ""
    if beat in anchor_beats:
        return False, f"anchor beat {beat} - dwell was bought for this scene"
    deliv = str(line.get("delivery") or "")
    if deliv in protect_deliveries:
        return False, f"delivery '{deliv}' - emotional lines hold the frame"
    n = visual_events(text)
    mn = int(getattr(config, "CLAUSE_MIN_EVENTS_TO_SPLIT", 2))
    if n < mn:
        return False, f"{n} visible event(s) - fewer than {mn}"
    return True, f"{n} visible events"


def _sec(v):
    try:
        p = [float(x) for x in str(v).split(":")]
        return p[0] * 3600 + p[1] * 60 + p[2]
    except Exception:
        return None


def visual_capacity(draft: dict, pdir,
                    tolerance: int | None = None) -> list:
    """[VISUAL-CAPACITY] findings: more events than shots to show them in.

    The writer's rule. A line may narrate as many events as there are
    distinct shots available for it in film order; commentary is free. When a
    line exceeds that, no editor can fix it - the picture simply does not
    exist - so it is the WRITER who must split the line or cut an event.

    Calibrated on this draft: excess events per line run median 1, p75 2,
    p90 2, max 3 (config/visual_capacity_control.json). A tolerance of 2
    therefore flags the top of the distribution rather than a tenth of the
    draft - the lines that are genuinely over-stuffed.
    """
    if tolerance is None:
        tolerance = int(getattr(config, "VISUAL_CAPACITY_TOLERANCE", 2))
    shots = _load_shots(pdir)
    out = []
    for ln in draft.get("lines") or []:
        text = str(ln.get("narration") or "").strip()
        if not text:
            continue
        a, b = _sec(ln.get("clip_start")), _sec(ln.get("clip_end"))
        if a is None or b is None:
            continue
        ev = visual_events(text)
        avail = max(1, len([s for s in shots
                            if s["a"] >= a - 0.05 and s["b"] <= b + 0.05]))
        if ev - avail > tolerance:
            out.append({"line_id": ln.get("id"), "events": ev,
                        "shots": avail, "excess": ev - avail})
    return out


def _load_shots(pdir) -> list:
    """Catalogued shots as {a, b} seconds. A local reader so the gate does
    not drag in the clause-cut planner."""
    import json
    from pathlib import Path as _P
    try:
        raw = json.loads((_P(pdir) / "shots.json")
                         .read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    out = []
    for x in raw.get("shots") or []:
        a, b = _sec(x.get("clip_start")), _sec(x.get("clip_end"))
        if a is not None and b is not None and b > a:
            out.append({"a": a, "b": b})
    out.sort(key=lambda s: s["a"])
    return out
