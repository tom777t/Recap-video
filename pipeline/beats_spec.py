"""Read the beat map, so a claim about a beat can be checked against the beat.

WHY
---
angle.md's anchors and hook-promise mappings were trusted exactly as written,
and one was wrong in a way nothing could catch:

    "before he has learned to turn"  ->  B47/B52/B53

    B47  "the long-haired man explains that DK's uncle takes a cut of
          everyone's action on his turf"          <- Kamata's cut, not teaching
    B52  "he stops at the red Evo, and the long-haired man hands it to him"
                                                  <- handing over a car
    B53  "Drift practice in the dockside lot ... the watching crowd laughs at
          how badly he drifts"                    <- he still cannot drift

while the beat that actually delivers the promise,

    B60  "Training starts: told to drift by feeling, he runs the hairpins
          again and again with the mentor coaching from the passenger seat"

was listed in the angle under "compress to a line or hold on footage".

Two of three mapped beats did not deliver the promise, and the one that did
was marked as texture. No gate could see it, because every gate read the
angle's claim about the beats rather than the beats.
"""
from __future__ import annotations

import re
from pathlib import Path


def load_beats(pdir: Path) -> dict:
    """{beat_id: {"ts", "what", "chars", "kind"}} from beats_proposal.md.

    Format is pipe-delimited:
        B47 | 00:41:27 | <what happens> | <characters> | <kind>
    """
    for name in ("beats_proposal.md", "beats_proposal_machine.md"):
        p = Path(pdir) / name
        if p.exists():
            break
    else:
        return {}
    out: dict = {}
    for raw in p.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip().lstrip("|").strip()
        m = re.match(r"^(B\d{1,3})\s*\|", line)
        if not m:
            continue
        parts = [x.strip() for x in line.split("|")]
        bid = f"B{int(m.group(1)[1:]):02d}"
        out[bid] = {
            "ts": parts[1] if len(parts) > 1 else "",
            "what": parts[2] if len(parts) > 2 else "",
            "chars": parts[3] if len(parts) > 3 else "",
            "kind": parts[4] if len(parts) > 4 else "",
        }
    return out


def _norm(s: str) -> str:
    s = str(s or "").lower()
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_STOP = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "from", "by", "as", "is", "was", "are", "were", "be", "been",
    "he", "she", "it", "they", "him", "her", "them", "his", "their", "its",
    "that", "this", "these", "those", "who", "whom", "which", "what",
    "then", "than", "so", "not", "no", "do", "does", "did", "has", "have",
    "had", "will", "would", "can", "could", "up", "out", "off", "into",
    "over", "about", "again", "one", "two", "all", "own", "very", "just",
    "still", "only", "more", "most", "there", "here", "when", "while",
}


def content_words(s: str) -> set:
    return {w for w in _norm(s).split() if w not in _STOP and len(w) > 2}


def quote_supported(quote: str, beats: list, beatmap: dict) -> tuple:
    """(ok, why) - is `quote` really in the `what` text of one of `beats`?

    DETERMINISTIC, and that is the point: the angle's own description of a
    beat carries no weight here. Either the words are in the beat map or they
    are not. Whitespace and punctuation are normalised; nothing else is.
    """
    q = _norm(quote)
    if len(q) < 12:
        return False, f"the evidence quote {quote!r} is too short to verify"
    missing = [b for b in beats if b not in beatmap]
    if missing:
        return False, (f"beat(s) {', '.join(missing)} are not in the beat map "
                       f"at all")
    for b in beats:
        if q in _norm(beatmap[b]["what"]):
            return True, b
    # near-miss diagnosis: which beat shares most content words
    qw = content_words(quote)
    best, bw = None, 0.0
    for b in beats:
        ov = len(qw & content_words(beatmap[b]["what"])) / max(1, len(qw))
        if ov > bw:
            best, bw = b, ov
    return False, (f"the quote is not in {'/'.join(beats)}; closest is "
                   f"{best} at {bw:.0%} word overlap. Quote the beat's own "
                   f"`what` text verbatim.")


def delivers(claim: str, quote: str, min_overlap: float = 0.34) -> tuple:
    """(ok, why) - do the quoted words actually support the claim?

    Content-word overlap between the claim (a promise clause or an anchor's
    stated kind+reason) and the evidence. A deliberately blunt instrument: it
    cannot judge meaning, so it is a FLOOR that catches a mapping pointed at
    an unrelated beat, which is the defect that occurred. The semantic
    judgement is made by the independent audit in
    docs/stage2/ANGLE_EVIDENCE_AUDIT.md.
    """
    cw = content_words(claim)
    if not cw:
        return True, "claim has no content words to check"
    ov = len(cw & content_words(quote)) / len(cw)
    if ov < min_overlap:
        return False, (f"the evidence shares only {ov:.0%} of the claim's "
                       f"content words (floor {min_overlap:.0%}); the quoted "
                       f"beat may not be the one that delivers it")
    return True, f"{ov:.0%} content-word overlap"
