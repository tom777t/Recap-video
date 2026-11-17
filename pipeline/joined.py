# -*- coding: utf-8 -*-
"""joined.py - a joined line's picture switches when the VOICE reaches each
piece (owner, 17 Nov).

A joined line (tools/write_slots.apply_join) is one sentence across 2-3
adjacent slots:
    "So they turn her into the ball in a game of keep-away, | passing her
     from car to car while Dom goes after Shaw."
The voice reads it in one breath. The picture must show slot 1's footage
while piece 1 is spoken and change to slot 2's footage the moment the voice
reaches piece 2. The render's 2f split gives every sub-shot an EQUAL share
and does not know where the voice is. That is why a joined line without this
module could show a clause's event before or after it is said.

  piece_offsets()  seconds into the narration audio at which each piece
                   starts: forced alignment (pipeline/word_times.py, faster-
                   whisper on the machine, no API) when it can run, else
                   each piece's share of the words. Cached per audio file.
  shares()         seconds of screen time per piece, from the line's lead-in
                   and the offsets, or None when a piece would need more
                   screen time than its own footage holds (the render then
                   falls back to the even split and says so).

The render uses this only while the narration still IS its pieces
(intact()): a later rewrite without '|' leaves them stale.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_W = re.compile(r"[\w']+")
MIN_SHARE = 1.0          # seconds: a sub-shot shorter than this does not read


def _norm(s: str) -> str:
    s = str(s or "").replace("’", "'").replace("‘", "'")
    return " ".join(re.sub(r"[^\w' ]+", " ", s.lower()).split())


def intact(ln: dict) -> bool:
    ps = ln.get("parts") or []
    return len(ps) > 1 and _norm(" ".join(str(p.get("text") or "")
                                          for p in ps)) == _norm(
        ln.get("narration"))


def word_share_offsets(ln: dict, narr_dur: float) -> list:
    """Piece i starts at narr_dur x (words before it / all words)."""
    counts = [len(_W.findall(str(p.get("text") or ""))) for p in ln["parts"]]
    tot = max(1, sum(counts))
    out, acc = [], 0
    for c in counts:
        out.append(round(narr_dur * acc / tot, 3))
        acc += c
    return out


def _key(audio: Path, text: str) -> str:
    st = audio.stat()
    return hashlib.sha1(f"{audio.name}|{st.st_size}|{int(st.st_mtime)}|"
                        f"{text}".encode("utf-8")).hexdigest()[:16]


def piece_offsets(ln: dict, audio: Path, narr_dur: float,
                  cache: Path | None = None, aligner=None) -> tuple:
    """(offsets, how): how is "aligned", "cached" or "word-share (<why>)".
    `aligner(audio, text) -> [(word, start, end)]` replaces word_times.align
    in tests."""
    text = str(ln.get("narration") or "")
    store: dict = {}
    key = None
    if cache is not None and audio.exists():
        try:
            store = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            store = {}
        key = _key(audio, text)
        hit = store.get(key)
        if isinstance(hit, list) and len(hit) == len(ln["parts"]):
            return hit, "cached"
    try:
        from pipeline import word_times as WT
        words = (aligner or WT.align)(audio, text)
        offs = WT.clause_offsets(words, [{"text": p.get("text")}
                                         for p in ln["parts"]])
        if not offs or any(o is None for o in offs):
            raise ValueError("a piece was not found in the audio")
        offs = [0.0] + [round(float(o), 3) for o in offs[1:]]
        if any(b <= a for a, b in zip(offs, offs[1:])) or offs[-1] >= narr_dur:
            raise ValueError("the aligned offsets are out of order")
        how = "aligned"
    except Exception as e:                       # no model, no audio, bad fit
        offs = word_share_offsets(ln, narr_dur)
        how = f"word-share ({str(e)[:60]})"
    if key is not None and how == "aligned":
        store[key] = offs
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(store), encoding="utf-8")
        except OSError:
            pass
    return offs, how


def shares(lead: float, offsets: list, clip_len: float,
           windows: list) -> tuple:
    """(shares, why_not). Piece 0 is on screen through the lead-in and until
    the voice reaches piece 1; the last piece fills the rest of the clip.
    None when a piece would need more screen time than its own footage holds,
    or less than MIN_SHARE."""
    cuts = [lead + o for o in offsets[1:]]
    edges = [0.0] + cuts + [clip_len]
    sh = [round(b - a, 3) for a, b in zip(edges, edges[1:])]
    for i, (s, (a, b)) in enumerate(zip(sh, windows)):
        if s < MIN_SHARE:
            return None, (f"piece {i + 1} is on screen {s:.1f}s, under "
                          f"{MIN_SHARE:.1f}s")
        if s > (b - a) + 1e-3:
            return None, (f"piece {i + 1} is spoken over {s:.1f}s but its "
                          f"footage is {b - a:.1f}s")
    return sh, ""
