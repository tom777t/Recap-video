"""The cold open - picker and [OPEN] gate, both directions.

THE INSTRUMENT, and its controls
--------------------------------
pipeline/opening.py decides what a video's first seconds show; the [OPEN]
and [TRANSITION] gates grade the draft that comes out. AGENTS.md: a new
checker runs first on a known-good and a known-bad example - if it cannot
tell them apart it is not a gate. The known-good is the approved Tokyo
Drift opening zone (the operator's approved draft opens its story there);
the known-bads are the distributor logo at 0:00 and the emptiest quarter
of the catalogue.

Cases - every rule tested in BOTH directions:

  PICKER-CONTROLS       the approved zone outranks both known-bads and the
                        chosen opener is inside it, mode A.
  PICKER-MODE-B         the best candidate beyond the midpoint flips the
                        mode to B (loop-back fragment).
  PICKER-NON-RESOLUTION a candidate sitting on a reveal landing scores
                        -100: the opener spoils nothing.
  PICKER-ANTI           a credits / logo shot is an anti-pick regardless
                        of anything else in its prose.
  OPEN-GOOD             a cold open that follows R0/R3 is silent on [OPEN]
                        and [TRANSITION].
  OPEN-GREETING         a greeting or meta word at 0:00 errors.
  OPEN-NAMES            two named characters in the open error; one does
                        not.
  OPEN-QUESTION         the open's last line must END on the question and
                        carry hook_question - both directions.
  OPEN-ANCHOR-A         OPEN-A's first line without a time-or-place anchor
                        is a hard [TRANSITION]; with one, silent.
  OPEN-ANCHOR-B         OPEN-B's first line WITH an anchor warns, and the
                        story's own first line carries the anchor instead.

Run:  python tools/test_opening.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pipeline import craft_gates as CG          # noqa: E402
from pipeline import opening as OP              # noqa: E402

GOOD_START, GOOD_END = 156.0, 226.0     # the approved Tokyo Drift zone


def _tokyo():
    return OP.read("tokyodrift2006")


def test_picker_controls():
    d = _tokyo()
    pick = OP.choose(d["candidates"], lever=OP.lever_for(d["facts"]),
                     lands=d["lands"], runtime_sec=d["runtime_sec"])

    def _in_zone(cid):
        c = next((x for x in d["candidates"] if x["id"] == cid), None)
        return c and (GOOD_START <= c["start"] < GOOD_END
                      or GOOD_START < c["end"] <= GOOD_END)

    good = [r for r in pick["ranked"] if _in_zone(r["id"])]
    if not good or not pick["opener"]:
        return False, "no ranked candidate in the approved zone"
    logo = min((OP.score(c, lever="THRILL", lands=d["lands"],
                         runtime_sec=d["runtime_sec"])["score"]
                for c in d["candidates"] if c["start"] < 60.0), default=0)
    allc = [OP.score(c, lever=OP.lever_for(d["facts"]), lands=d["lands"],
                     runtime_sec=d["runtime_sec"])["score"]
            for c in d["candidates"]]
    lowq = sorted(s for s in allc if s >= 0)[:max(1, sum(
        1 for s in allc if s >= 0) // 4)]
    in_zone = _in_zone(pick["opener"]["id"])
    ok = (pick["open_mode"] == "A" and in_zone
          and good[0]["score"] > logo
          and good[0]["score"] > (lowq[len(lowq) // 2] if lowq else -1))
    return ok, (f"mode {pick['open_mode']}, opener "
                f"{pick['opener']['id']} (score {pick['opener']['score']}), "
                f"approved-zone best {good[0]['score']}, logo {logo}, "
                f"trivial median {lowq[len(lowq) // 2] if lowq else '-'}")


def _start(d, cid):
    return next((c["start"] for c in d["candidates"] if c["id"] == cid), -1)


def test_picker_mode_b():
    # one late charged DANGER candidate inside the spoiler cap, with a
    # reveal map: mode B. (0.9 with no map is refused - that is
    # SPOILER-CAP-AND-REVEALS' job now.)
    cands = [
        {"id": "late", "start": 3900.0, "end": 3940.0,
         "depicts": ["action"],
         "action": "The house explodes and the wreck burns behind him "
                   "as he drives",
         "chars": ["the driver"], "censor": "none"},
        {"id": "early", "start": 30.0, "end": 60.0, "depicts": ["setup"],
         "action": "A man drives to work and parks", "chars": [],
         "censor": "none"},
    ]
    pick = OP.choose(cands, lever="THRILL", lands=[5700.0],
                     runtime_sec=6000.0)
    return (pick["open_mode"] == "B" and pick["opener"]["id"] == "late"), \
        f"mode {pick['open_mode']}, opener {pick['opener']['id']}"


def test_picker_non_resolution():
    c = {"id": "x", "start": 4000.0, "end": 4040.0, "depicts": ["action"],
         "action": "He kisses her and the room explodes", "chars": [],
         "censor": "none"}
    r = OP.score(c, lever="THRILL", lands=[4010.0], runtime_sec=6000.0)
    return r["score"] == -100.0 and "reveal" in r["why"][0], \
        f"score {r['score']}: {r['why'][0]}"


def test_picker_anti():
    c = {"id": "logo", "start": 0.0, "end": 30.0, "depicts": ["establishing"],
         "action": "Black screen gives way to the studio logo against a "
                   "starfield, and the distributor title fades in",
         "chars": [], "censor": "none"}
    r = OP.score(c, lever="AWE", lands=[], runtime_sec=6000.0)
    return r["score"] == -100.0, f"score {r['score']}: {r['why'][0]}"


def _draft(mode, lines, lever=None):
    return {"title": "t", "lines": lines, "open_mode": mode,
            **({"lever": lever} if lever else {})}


def _open_line(narr, hook=None, cid=1):
    ln = {"id": cid, "note": "OPEN", "narration": narr, "payload": "stake",
          "delivery": "normal", "clip_start": "00:02:19.472",
          "clip_end": "00:02:36.739"}
    if hook is not None:
        ln["hook_question"] = hook
    return ln


GOOD_OPEN = [
    _open_line("Arizona, and a boy who cannot stop racing pins his whole "
               "future on one quarter mile."),
    _open_line("The wreck costs him the car, the race and the last deal "
               "his father will ever cut for him."),
    _open_line("Will one more crash in the one city that runs on sideways "
               "cars put him away for good?", hook="Will one more crash "
               "put him away for good?"),
]
# the same contract, OPEN-B shaped: mid-scene first line, no anchor - the
# anchor belongs to the story's own first line once the pivot lands
GOOD_OPEN_B = [
    _open_line("Sheet metal folds around him at a speed no street should "
               "allow, and one more wreck means jail."),
    _open_line("It costs him the car, the race and the last deal his "
               "father will ever cut for him."),
    _open_line("Will the one city that runs on sideways cars put him away "
               "for good?", hook="Will one more crash put him away for "
               "good?"),
]
_STORY = {"id": 10, "note": "B01", "narration": "Three lads pin a "
          "classmate to a roller door.", "payload": "stake",
          "delivery": "normal", "clip_start": "00:02:36.739",
          "clip_end": "00:02:48.042"}
# OPEN-B's story proper lands with the pivot and must carry the anchor
_STORY_B = dict(_STORY, narration="Arizona, and three lads pin a "
                                "classmate to a roller door.")


def _msgs(d):
    # hard() lands in notes while the draft is under MIN_LINES_FOR_STATS,
    # so a unit-sized fixture has to read all three buckets
    r = CG.craft_report(d)
    return [m for m in r["errors"] + r["warns"] + r["notes"]
            if m.startswith(("[OPEN]", "[TRANSITION]"))]


def test_open_good():
    bad = _msgs(_draft("A", GOOD_OPEN + [_STORY]))
    return bad == [], f"{bad[:2]}"


def test_open_greeting():
    bad = _msgs(_draft("A", [
        _open_line("Welcome back to the channel - this is the recap you "
                   "asked for."),
    ] + GOOD_OPEN[1:]))
    return any("[OPEN]" in m and "welcome" in m for m in bad), f"{bad[:2]}"


def test_open_names():
    two = GOOD_OPEN[:]
    two[1] = _open_line("The wreck costs Dom his car, and Han says "
                        "nothing at all.", cid=2)
    bad = _msgs(_draft("A", two + [_STORY]))
    one = GOOD_OPEN[:]
    one[1] = _open_line("The wreck costs Dom his car and the money he "
                        "owes.", cid=2)
    ok1 = _msgs(_draft("A", one + [_STORY]))
    return (any("[OPEN]" in m and "2" in m and "name" in m for m in bad)
            and not any("[OPEN]" in m and "name" in m for m in ok1)), \
        f"two: {bad[:1]} / one: {ok1[:1]}"


def test_open_question():
    noq = GOOD_OPEN[:]
    noq[2] = _open_line("One more crash in the one city that runs on "
                        "sideways cars will put him away for good.",
                        hook="Will one more crash put him away?", cid=3)
    a = _msgs(_draft("A", noq + [_STORY]))
    nohq = GOOD_OPEN[:]
    nohq[2] = _open_line(nohq[2]["narration"], hook=None, cid=3)
    b = _msgs(_draft("A", nohq + [_STORY]))
    return (any("not END on a question" in m for m in a)
            and any("no hook_question" in m for m in b)), \
        f"question: {a[:1]} / hook: {b[:1]}"


def test_open_anchor_a():
    noanchor = GOOD_OPEN[:]
    noanchor[0] = _open_line("A boy with a fast car and a faster temper "
                             "races the neighbour.")
    a = _msgs(_draft("A", noanchor + [_STORY]))
    ok = _msgs(_draft("A", GOOD_OPEN + [_STORY]))
    return (any("[TRANSITION]" in m and "anchor" in m for m in a)
            and not any("[TRANSITION]" in m for m in ok)), \
        f"no-anchor: {a[:1]} / good: {ok[:1]}"


def test_open_anchor_b():
    # OPEN-B: the fragment must NOT anchor, the story's first line must
    b = _msgs(_draft("B", GOOD_OPEN_B + [_STORY_B]))
    frag_anchored = GOOD_OPEN_B[:]
    frag_anchored[0] = _open_line("Arizona, and a boy races for the last "
                                  "time.")
    warned = _msgs(_draft("B", frag_anchored + [_STORY_B]))
    flat = _msgs(_draft("B", GOOD_OPEN_B + [dict(
        _STORY_B, narration="He pins his whole future on one quarter "
                            "mile.")]))
    return (not any("[TRANSITION]" in m and "anchor" in m for m in b)
            and any("[TRANSITION]" in m and "fragment" in m for m in warned)
            and any("[TRANSITION]" in m and "anchor" in m for m in flat)), \
        f"good: {b[:1]} / frag-anchored: {warned[:1]} / flat-story: {flat[:1]}"


def _cand(cid, start, prose, depicts=("action",), chars=None):
    return {"id": cid, "start": start, "end": start + 30.0,
            "depicts": list(depicts), "action": prose,
            "chars": chars or [], "censor": "none"}


def test_spoiler_outcome():
    # the review's #1 pick on Gone Girl: the ending as the opener
    c = _cand("gg", 5200.0, "Amy sits up drenched in blood in her red "
               "slip beside the body", chars=["amy"])
    r = OP.score(c, lever="THRILL", lands=[100.0], runtime_sec=6000.0)
    before_mid = _cand("gg2", 120.0, "The funeral opens the film and "
                       "nobody names the dead", depicts=("montage",))
    r2 = OP.score(before_mid, lever="THRILL", lands=[3000.0],
                  runtime_sec=6000.0)
    return (r["score"] == -100.0 and "outcome" in r["why"][0]
            and r2["score"] != -100.0), \
        f"late: {r['score']} ({r['why'][0][:60]}) / early setup allowed: {r2['score']}"


def test_spoiler_cap_and_reveals():
    # a charged DANGER beat at 0.90 with a reveal map: refused, OPEN-A
    late = [_cand("early", 60.0, "A boy builds a race car in his garage",
                  depicts=("setup",)),
            _cand("late", 5400.0, "She draws her gun and gives chase "
                  "through the kitchens", chars=["she"])]
    cap = OP.choose(late, lever="THRILL", lands=[3000.0],
                    runtime_sec=6000.0)
    # the same shape inside the cap: OPEN-B, no note
    mid = [_cand("early", 60.0, "A boy builds a race car in his garage",
                 depicts=("setup",)),
           dict(_cand("mid", 3900.0, "She draws her gun and gives chase "
                      "through the kitchens", chars=["she"]),
                start=3900.0, end=3930.0)]
    ok_mid = OP.choose(mid, lever="THRILL", lands=[5700.0],
                       runtime_sec=6000.0)
    # no reveal map at all: never OPEN-B, and the refusal is SAID
    norv = OP.choose(late, lever="THRILL", lands=[],
                     runtime_sec=6000.0)
    return (cap["open_mode"] == "A"
            and any("spoiler cap" in n for n in cap["notes"])
            and ok_mid["open_mode"] == "B"
            and not ok_mid["notes"]
            and norv["open_mode"] == "A"
            and any("no reveal map" in n for n in norv["notes"])), \
        (f"cap: {cap['open_mode']} {cap['notes'][:1]} / "
         f"mid: {ok_mid['open_mode']} / "
         f"no-reveals: {norv['open_mode']} {norv['notes'][:1]}")


_KNOWN_BAD = ("gonegirl2014", "parasite2019", "prisoners2013")


def test_known_bad_real_films():
    # §0's table: these three had the ending as the #1 opener. After the
    # fix none of them may open on an outcome or past the cap. Needs the
    # film data on disk (shots.json at minimum) - without it this is a
    # FAILURE, not a skip: the guard it tests ships cold.
    import json
    rows, bad = [], []
    for name in _KNOWN_BAD:
        try:
            d = OP.read(name)
        except Exception as e:
            return False, f"{name}: cannot read ({type(e).__name__}: {e})"
        if not d["candidates"]:
            return False, f"{name}: no shots.json"
        r = OP.choose(d["candidates"], lever=OP.lever_for(d["facts"]),
                      lands=d["lands"], runtime_sec=d["runtime_sec"])
        o = r["opener"] or {}
        pos = o.get("pos")
        outcome = any("outcome" in w for w in o.get("why", []))
        rows.append(f"{name}={r['open_mode']}@{pos}")
        if r["open_mode"] == "B" and (
                outcome or (pos or 0.0) > OP.B_CAP):
            bad.append(name)
    return not bad, " ".join(rows) + (f" | REFUSED: {bad}" if bad else "")


TESTS = {
    "PICKER-CONTROLS": test_picker_controls,
    "PICKER-MODE-B": test_picker_mode_b,
    "PICKER-NON-RESOLUTION": test_picker_non_resolution,
    "PICKER-ANTI": test_picker_anti,
    "SPOILER-OUTCOME": test_spoiler_outcome,
    "SPOILER-CAP-AND-REVEALS": test_spoiler_cap_and_reveals,
    "KNOWN-BAD-REAL": test_known_bad_real_films,
    "OPEN-GOOD": test_open_good,
    "OPEN-GREETING": test_open_greeting,
    "OPEN-NAMES": test_open_names,
    "OPEN-QUESTION": test_open_question,
    "OPEN-ANCHOR-A": test_open_anchor_a,
    "OPEN-ANCHOR-B": test_open_anchor_b,
}


def main() -> int:
    fails = 0
    for name, fn in TESTS.items():
        try:
            ok, msg = fn()
        except Exception as e:                      # a raise is a failure
            ok, msg = False, f"{type(e).__name__}: {e}"
        print(("PASS  " if ok else "FAIL  ") + f"{name:<22} {msg}")
        fails += 0 if ok else 1
    print("-" * 60)
    print("test_opening: all pass" if not fails
          else f"test_opening: {fails} FAILURE(S)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
