# -*- coding: utf-8 -*-
"""time_frame.py - the viewer always knows WHEN and WHETHER what they see is
happening: the film's present, the past, or something imagined.

Owner, 26 Nov, on Lost in the Stars: "chuyển cảnh giữa kiểu ảo và thực chưa
tốt, kiểu người xem dễ lộn hay là quá khứ hiện tại". The film cuts to a
dreamlike beach (B05), a crash years earlier (B30), the nurse's story of the
anniversary dinner (B106-B110), the dive under the lighthouse (B128); the
recap laid a 70 s hold over the dream, a 47 s hold over the crash with no
word before it, and told the past in the present tense - "Then He Fei
fastens a small bag to the cage bars." A recap reader cannot see the film's
own cues (colour grade, a match cut, a dissolve) the way a film viewer can;
the narrator has to say it.

Each beat carries a FRAME (beats_proposal.md, sixth column; tools/
frame_beats.py fills it):

  now       the film's present story
  past      a flashback, a memory shown on screen, a past a character
            recounts while the film shows it, a backstory montage
  imagined  a dream, nightmare, vision, hallucination, fantasy, or a false
            version shown as if it happened

switch_problems() finds every place the footage changes frame between two
lines and asks one line to say so in plain words: the first narrated line of
the new frame, or - when the new frame opens on silent footage longer than a
breath - the last narrated line before it ("...and his mind goes back to the
beach where she vanished"). The way back needs it as much as the way in
("Back in the cell, ...", "He wakes.").
"""
from __future__ import annotations

import re

FRAMES = ("now", "past", "imagined")

# words a narrator uses to tell a listener the picture has changed frame
_MARK = {
    "past": re.compile(
        r"\b(flash(?:es)?[- ]?back|flashes back|years? (?:earlier|ago|before)|"
        r"months? (?:earlier|ago|before)|weeks? (?:earlier|ago|before)|"
        r"days? (?:earlier|ago|before)|a year (?:earlier|ago|before)|"
        r"back then|back when|long before|earlier that|in the past|"
        r"his past|her past|their past|past\b|remember(?:s|ed|ing)?|"
        r"recall(?:s|ed|ing)?|memor(?:y|ies)|"
        r"as a (?:boy|girl|child|kid|teenager|student)|when (?:he|she|they) "
        r"(?:was|were) (?:young|a (?:boy|girl|child|kid|teenager|student))|"
        r"(?:goes|went|cuts?|takes us|takes him|takes her) back|"
        r"(?:he|she|they) (?:had|once)|once,|years before|"
        r"the night (?:she|he|they)|that night|on the day|that day|"
        r"how (?:it|this|they|he|she) (?:all )?(?:began|started|met)|"
        r"tells? (?:him|her|them) (?:how|what happened)|story of)\b", re.I),
    "imagined": re.compile(
        r"\b(dream(?:s|ed|ing|like)?|nightmares?|imagin(?:e|es|ed|ing|ation)|"
        r"pictures? (?:her|him|it|them)|visions?|hallucinat\w*|fantas\w*|"
        r"in (?:his|her|their) (?:head|mind)|half[- ]asleep|"
        r"(?:sees|saw) (?:her|him) again|not real|isn't real|wasn't real|"
        r"memor(?:y|ies)|haunt\w*|ghost\w*)\b", re.I),
    "now": re.compile(
        r"\b(back (?:in|at|to|on|inside|outside|home|now)|now\b|today|"
        r"present|meanwhile|wakes?|woke|awake|jolts?|snaps? (?:back|out)|"
        r"returns? to|comes? to|the next (?:day|morning)|that morning|"
        r"again,? (?:in|at)|still (?:in|at)|in the (?:cell|room|car|"
        r"hospital|station))\b", re.I),
}


def marks(text: str, frame: str) -> bool:
    """Does `text` tell a listener the picture is now in `frame`?"""
    rx = _MARK.get(frame)
    return bool(rx and rx.search(str(text or "")))


def _beat_id(ln: dict):
    m = re.match(r"^\s*(B\d{1,3})\b", str(ln.get("note") or ""))
    return f"B{int(m.group(1)[1:]):02d}" if m else None


def _narr(ln: dict) -> str:
    return str(ln.get("narration") or "").strip()


def _quiet(ln: dict) -> float:
    """Seconds a line holds footage with no narrator."""
    return float(ln.get("narration_silence_seconds") or 0) + float(
        ln.get("film_speaks_seconds") or 0)


def switch_problems(lines: list, beats: dict, breath: float = 2.0) -> list:
    """[{"id", "from", "to", "beat", "why"}] - one per frame change that no
    line announces. `beats` is beats_spec.load_beats(); a beat without a
    frame counts as "now". Lines that belong to no beat (intro, outro) do
    not change the frame."""
    out = []
    seq = []                      # (index, frame) for lines on a beat
    for i, ln in enumerate(lines):
        b = _beat_id(ln)
        if b is None or b not in beats:
            continue
        f = beats[b].get("frame") or "now"
        seq.append((i, f if f in FRAMES else "now", b))
    # a flash cut - another frame for no longer than a breath, with no line
    # spoken over it - is not a journey to announce, nor one to come back
    # from: drop it, so the frames either side of it join up
    runs, cur = [], []
    for x in seq:
        if cur and x[1] != cur[-1][1]:
            runs.append(cur)
            cur = []
        cur.append(x)
    if cur:
        runs.append(cur)
    seq = [x for r in runs
           if any(_narr(lines[j]) for j, _f, _b in r)
           or sum(_quiet(lines[j]) for j, _f, _b in r) > breath + 0.01
           for x in r]
    for k in range(1, len(seq)):
        i, f, b = seq[k]
        pf = seq[k - 1][1]
        if f == pf:
            continue
        # the new frame's run of lines
        run = [seq[k]]
        for nxt in seq[k + 1:]:
            if nxt[1] != f:
                break
            run.append(nxt)
        first = None
        quiet = 0.0
        for j, _f, _b in run:
            if _narr(lines[j]):
                first = j
                break
            quiet += _quiet(lines[j])
        prev = None
        for j in range(i - 1, -1, -1):
            if _narr(lines[j]):
                prev = j
                break
        if prev is None:
            continue
        if first is None and quiet <= breath + 0.01:
            continue                    # a flash cut too short to confuse
        said = marks(_narr(lines[prev]), f) or (
            first is not None and quiet <= breath + 0.01
            and marks(_narr(lines[first]), f))
        if said:
            continue
        opens_silent = first is None or quiet > breath + 0.01
        target = lines[prev] if opens_silent else lines[first]
        out.append({"id": target.get("id"), "from": pf, "to": f, "beat": b,
                    "silent": round(quiet, 1), "announce": opens_silent})
    return out


_WORDS = {"now": "the present", "past": "the past (a flashback or a memory)",
          "imagined": "something imagined (a dream, a vision, a false "
                      "version)"}


def finding_text(p: dict) -> str:
    to, fr = _WORDS[p["to"]], _WORDS[p["from"]]
    if p["announce"]:
        where = (f"the footage after this line ({p['beat']}) moves from "
                 f"{fr} to {to} and opens on {p['silent']:.0f}s with no "
                 f"narrator, so THIS line must tell the listener before it "
                 f"happens")
    else:
        where = (f"this line's footage ({p['beat']}) has moved from {fr} to "
                 f"{to} and nothing says so")
    eg = {"past": "\"Years earlier, ...\", \"In a flashback, ...\", "
                  "\"He remembers the night ...\"",
          "imagined": "\"In his dream, ...\", \"He pictures her ...\", "
                      "\"Half asleep, he sees ...\"",
          "now": "\"Back in the cell, ...\", \"He wakes.\", "
                 "\"Now, in the present, ...\""}[p["to"]]
    return (f"[TIME-FRAME] line {p['id']}: {where}. A listener cannot see "
            f"the film's own cues; say it in plain words, e.g. {eg}. Keep "
            f"the line's event and its length")
