# -*- coding: utf-8 -*-
"""sung.py - which transcript segments are NOT dialogue (a song, mostly).

Whisper writes down whatever is sung over a scene as if a character said it.
Furious 7 quoted "It's been a long without you, my friend" as Dom's line - it
is the chorus of the song over the ending (and Whisper even dropped "day").
A lyric used as a quote is wrong twice: it puts words in a character's mouth,
and it reproduces a song's lyrics in the recap.

A segment is taken as not dialogue when any of these hold:

  MARKED    Whisper / a subtitle wrote a music mark: a note sign, or a
            bracket naming music ("[music]", "(singing)", "[upbeat music]",
            "[man singing]") ...
  BY HAND   one of its sentences is, or contains, a text listed in
            projects/<p>/not_dialogue.json - written by
            `tools/fix_line.py --not-dialogue` when a reader finds one the
            other rules missed. Matched sentence by sentence and on word
            boundaries ("see you again" does not take "see you against").
  CHORUS    it comes back: another segment within CHORUS_WINDOW seconds
            reads the same (character-sequence ratio >= CHORUS_SIMILAR, both
            >= CHORUS_MIN_WORDS words).
  IN-SONG   it lies between two passes of one chorus, SONG_GAP_MIN to
            SONG_SPAN seconds apart (the verse), or runs straight on (within
            SONG_JOIN s) from the closing pass.

CHORUS is NOT precise, and is used knowing that. Measured on 17 local
transcripts (review of 677fc38): 0-29 segments a film, most of them repeated
dialogue ("I repeat, do not open the hatch") or Whisper writing one line
twice; a few real songs. Requiring 3+ repeats did not separate them (the
repeats are just as often dialogue). What it costs: those lines are not
offered as QUOTE / FILM-SPEAKS candidates and the payloads mark them "may be
a song" - a lost candidate. What missing a lyric costs: a false line in the
recap and a reproduced lyric. So it stays, as a candidate filter only; the
[NOT-DIALOGUE] gate on the draft uses MARKED and BY HAND alone.

(A beat-level rule - "the beat's description says a song plays" - was tried
and dropped: beats span minutes of dialogue, and "Da-song" is a name.
Parasite lost 227 lines of dialogue to it.)

ONE computation per transcript (`transcript_flags`), over every segment of
transcript.json, so the quote picker (tools/write_slots.py), the film-speaks
candidates (pipeline/film_speaks.py) and the payloads (tools/act_payload.py,
tools/beat_payload.py) cannot disagree about a line.
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

CHORUS_WINDOW = 480.0      # seconds: a song's chorus comes back within this
CHORUS_MIN_WORDS = 7       # at 5 words and a word-set overlap, "What are you
CHORUS_SIMILAR = 0.85      # doing here?" x2 made 25+ false choruses a film
# IN-SONG: the verse between two passes of one chorus is the song too.
# Furious 7: the chorus came back 55 s later, and the picker took the rap
# verse in between as Dom's line. A pair closer than SONG_GAP_MIN is a line
# said twice, not a chorus; a song's chorus returns within SONG_SPAN.
# Measured on 17 local transcripts at 30-90 s: 85 segments in 5 films are
# swept in, all of them dialogue between a repeated line (Interstellar's "I
# repeat, do not open the hatch") - lost quote CANDIDATES, never a block.
SONG_GAP_MIN = 30.0
SONG_SPAN = 90.0
SONG_JOIN = 1.0            # s: a segment this close runs on from the chorus

_MUSIC = r"(?:music|singing|sings|sung|song|lyrics|vocali[sz]ing|humming)"
_MARK = re.compile(r"[♪♫♬♭♮♯]|"
                   r"[\[(][^\])]{0,40}\b" + _MUSIC + r"\b[^\])]{0,40}[\])]",
                   re.I)
_SENT = re.compile(r"(?<=[.!?…])\s+")
_CACHE: dict = {}


def _norm(t: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9' ]+", " ",
                           str(t).lower().replace("’", "'")).split())


def _words(t: str) -> set:
    return set(_norm(t).split())


def by_hand(pdir) -> list:
    """The texts a person marked as not dialogue (normalised)."""
    p = Path(pdir) / "not_dialogue.json"
    if not p.exists():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    return [n for n in (_norm(x) for x in d.get("texts") or []) if n]


def hand_listed(text: str, hand: list) -> bool:
    """True if any sentence of `text` is a listed text, or holds one / is
    held by one (when it is most of it) on word boundaries. The quote picker stores ONE sentence of
    a segment, so a short sentence inside a long segment must still match
    ("I love you." in "Oh, baby. I love you.")."""
    if not hand:
        return False
    sents = [_norm(x) for x in _SENT.split(str(text))] + [_norm(text)]
    for s in sents:
        if not s:
            continue
        ps = f" {s} "
        for h in hand:
            ph = f" {h} "
            # a sentence inside a listed text counts only when it is most of
            # it ("It's been a long day." is a line of its own elsewhere)
            if s == h or (len(h) >= 12 and ph in ps) or \
                    (len(s) >= max(12, 0.6 * len(h)) and ps in ph):
                return True
    return False


def add_by_hand(pdir, text: str, why: str = "") -> bool:
    """Record one text as not dialogue; False if it was already there."""
    p = Path(pdir) / "not_dialogue.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
    except ValueError:
        d = {}
    d.setdefault("_what", "transcript lines that are NOT dialogue (a song, "
                          "a PA, a TV) - never quoted; see pipeline/sung.py")
    texts = d.setdefault("texts", [])
    if _norm(text) in {_norm(x) for x in texts}:
        return False
    texts.append(text)
    if why:
        d.setdefault("why", {})[text] = why
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    _CACHE.clear()
    return True


def sung_flags(segs: list, pdir=None) -> list:
    """One reason (str) or "" per segment; segs are (start, end, text)."""
    n = len(segs)
    why = [""] * n
    hand = by_hand(pdir) if pdir is not None else []
    ws = [_words(s[2]) for s in segs]
    nn = [_norm(s[2]) for s in segs]
    order = sorted(range(n), key=lambda i: float(segs[i][0]))
    for i in range(n):
        t = segs[i][2]
        if _MARK.search(str(t)):
            why[i] = "MARKED"
        elif hand_listed(t, hand):
            why[i] = "BY HAND"
    # CHORUS: compare each segment only with those inside the window
    j0 = 0
    pairs = []
    for x, i in enumerate(order):
        if len(nn[i].split()) < CHORUS_MIN_WORDS:
            continue
        ti = float(segs[i][0])
        while float(segs[order[j0]][0]) < ti - CHORUS_WINDOW:
            j0 += 1
        for y in range(j0, x):
            k = order[y]
            if len(nn[k].split()) < CHORUS_MIN_WORDS:
                continue
            if len(ws[i] & ws[k]) / min(len(ws[i]), len(ws[k])) < 0.6:
                continue                     # cheap pre-filter
            if difflib.SequenceMatcher(None, nn[i], nn[k]).ratio() \
                    >= CHORUS_SIMILAR:
                why[i] = why[i] or "CHORUS"
                why[k] = why[k] or "CHORUS"
                lo_, hi_ = sorted((float(segs[k][0]), ti))
                if SONG_GAP_MIN <= hi_ - lo_ <= SONG_SPAN:
                    pairs.append((lo_, hi_))
    pos = {i: x for x, i in enumerate(order)}
    by_start = {}
    for i in range(n):
        by_start.setdefault(round(float(segs[i][0]), 3), i)
    for lo_, hi_ in pairs:
        for j in range(n):
            if not why[j] and lo_ < float(segs[j][0]) < hi_:
                why[j] = "IN-SONG"
        # the chorus line Whisper split in two: the segment running straight
        # on from the closing pass (Furious 7: "And I'll tell you." 0.1 s
        # after it was picked next). Only AFTER: the line just before the
        # opening pass is the scene the song comes in over (Furious 7: Dom's
        # "It's never goodbye." was swept in when both sides were joined)
        z_i = by_start.get(round(hi_, 3))
        for c, step in ((z_i, 1),):
            if c is None:
                continue
            y = pos[c] + step
            if 0 <= y < n:
                j = order[y]
                gap = (float(segs[j][0]) - float(segs[c][1]) if step > 0
                       else float(segs[c][0]) - float(segs[j][1]))
                if not why[j] and gap <= SONG_JOIN:
                    why[j] = "IN-SONG"
    return why


def _key(start, text) -> tuple:
    return (round(float(start), 2), _norm(text))


def transcript_flags(pdir) -> dict:
    """{(start, normalised text): reason} for every flagged segment of the
    project's transcript.json - THE answer every caller looks up."""
    pdir = Path(pdir)
    tp, hp = pdir / "transcript.json", pdir / "not_dialogue.json"
    stamp = tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in (tp, hp))
    hit = _CACHE.get(str(pdir))
    if hit and hit[0] == stamp:
        return hit[1]
    segs = []
    try:
        raw = json.loads(tp.read_text(encoding="utf-8-sig"))
        for s in (raw.get("segments") if isinstance(raw, dict) else raw) or []:
            try:
                segs.append((float(s["start"]), float(s["end"]),
                             str(s.get("text") or "").strip()))
            except (KeyError, TypeError, ValueError):
                continue
    except (OSError, ValueError):
        segs = []
    w = sung_flags(segs, pdir)
    out = {_key(s[0], s[2]): r for s, r in zip(segs, w) if r}
    _CACHE[str(pdir)] = (stamp, out)
    return out


def reason(pdir, start, text) -> str:
    """Why this transcript segment is not dialogue ("" = it is)."""
    return transcript_flags(pdir).get(_key(start, text), "")


def dialogue_only(segs: list, pdir) -> list:
    """segs (start, end, text) without the flagged ones."""
    f = transcript_flags(pdir)
    return [s for s in segs if _key(s[0], s[2]) not in f]


def quoted_not_dialogue(pdir, narration: str) -> list:
    """The quoted spans of a narration line that are a MARKED or BY HAND
    text (CHORUS is too loose to block a written line)."""
    hand = by_hand(pdir)
    marked = [t for (_s, t), r in transcript_flags(pdir).items()
              if r == "MARKED"]
    out = []
    for q in re.findall(r"[\"“]([^\"”]+)[\"”]", str(narration)):
        nq = _norm(q)
        if len(nq) < 6:
            continue
        if hand_listed(q, hand) or any(
                f" {nq} " in f" {m} " for m in marked):
            out.append(q.strip())
    return out
