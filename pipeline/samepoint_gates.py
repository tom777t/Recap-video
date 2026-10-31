"""[SAME-POINT]: adjacent lines that make the same point, and motif uses.

THE DEFECT. Two adjacent lines said the same thing in different words - one
paid for tyres by hawking a friend's stock, the next worked the shopping
crowds flogging goods to pay for tyres - and they share exactly one content
word. In the same draft a running bit the viewer counted on FIVE lines
registered as ONE, because the budget counter matched the bit's literal
phrase and a callback that works is a callback reworded.

Both are the same failure: meaning repeating where the words do not.

WHY THIS GATE WARNS AND DOES NOT BLOCK, which is the honest part.

An embedding is the right instrument and could not be obtained. Model
downloads here are intercepted by a proxy that returns a ~46 KB page in place
of a 349-byte file, with the size varying per request, so every checksum
fails; and a locally-trained embedding is not an option either - the whole
available corpus is about 487,000 words, where usable synonymy needs tens of
millions.

Four instruments were then measured against a labelled control (one pair a
human reported, and the 103 other adjacent pairs of a draft the viewer
approved, which are therefore labelled negatives). All four were rejected ON
THE EVIDENCE:

  whole-line content overlap   control 0.21 against a 0.50 bar - misses it
  best clause pair, min-norm   control outside the top twelve; a two-word
                               clause sharing one stem scores 1.00
  TF-IDF cosine on stems       control 0.037 with THIRTY-THREE approved pairs
                               scoring higher
  field + shared argument      catches the control, but with 8 false
                               positives on 104 approved pairs

The fourth is this module's detector, and 8 false positives in 104 is not an
error gate - it would block prose the viewer signed off. Worse, the false
positives have no clean discriminator: one of them asserts the same field
about the same argument in the same clause as its neighbour ("his dad says"
twice) and is perfectly legitimate, because what differs is the CONTENT of
what was said, which is exactly the part a lexicon cannot read.

So the division of labour is: this gate NARROWS 104 pairs to a handful, and
the semantic verdict is recorded by the one semantic reader available - the
review agent - in review.md. The gate then enforces that every candidate it
raised was actually adjudicated. That is not a weaker check than a blocking
bar; it is a check whose instrument can actually see the thing. What it is
NOT is automatic, and pretending otherwise would be the failure this file
exists to document.

WHEN AN EMBEDDING BECOMES AVAILABLE: the control set is already in
config/semantic_dup_control.json with one positive, 103 negatives and five
paraphrase probes. Swap the instrument, re-run
tools/calibrate_semantic_dup.py, and if it separates the control from the
negatives the gate can become blocking. Until it separates, it does not.
"""
from __future__ import annotations

from pathlib import Path

import config
from pipeline import semantic_dup as sd


def _narr(ln) -> str:
    if not isinstance(ln, dict):
        return ""
    return str(ln.get("narration") or "").strip()


_SPEECH_VERB = __import__("re").compile(
    r"\b(say|says|said|tell|tells|told|ask|asks|asked|answer|answers|"
    r"answered|reply|replies|replied|explain|explains|explained|admit|"
    r"admits|admitted|reckon|reckons|call|calls|called|give|gives|gave|"
    r"read|reads|put|puts)\b", __import__("re").IGNORECASE)


def narrator_text(text: str) -> str:
    """The text with character speech removed.

    THE REASON: the motif budget is a budget on the NARRATOR's callbacks -
    angle.md asks for "the running bits as callbacks, in the narrator's own
    words". Counting the film's own dialogue against it is wrong twice over:
    the writer did not choose those words, and two characters describing the
    same history to each other is the scene, not a repetition.

    Found by using the gate. A bit measured five uses, two of which were a
    character reading the protagonist's history back to him and him giving
    his own version back - a deliberate parallel, and the film's material,
    not the narrator's habit. Stripping them leaves the three real narrator
    uses, inside budget.

    Two general forms are removed: double-quoted spans, and the span after a
    colon when the clause before it carries a speech verb. The tic detector
    already excludes quoted speech for the same reason, so this is the
    existing rule applied to a counter that was missing it.
    """
    import re as _re
    t = _re.sub(r"[\"\u201c][^\"\u201d]*[\"\u201d]", " ", str(text or ""))
    parts = _re.split(r"(?<=[.!?])\s+", t)
    keep = []
    for p in parts:
        if ":" in p:
            head, tail = p.split(":", 1)
            if _SPEECH_VERB.search(head):
                keep.append(head)
                continue
        keep.append(p)
    return " ".join(keep)


def motif_uses(draft: dict, pdir: Path) -> dict:
    """{motif name: [line ids]} counted by MEANING, not by literal phrase.

    Measured against the five lines the viewer counted by hand for one bit:
      literal phrase (what shipped)        1 of 5, 0 false
      every content stem of the name       3 of 5, 1 false
      the name's field + its argument      0 of 5
      argument + a possession-lack marker  4 of 5, 12 false

    None is both complete and precise, so the counter used here is the
    stem-subset rule - the best precision of the four - and the near misses
    are reported as candidates for adjudication rather than silently counted
    or silently dropped. Reporting 3 of 5 and naming the gap beats reporting
    1 of 5 and calling it a pass.
    """
    from pipeline import angle_spec
    out: dict = {}
    try:
        spec = angle_spec.load(Path(pdir))
    except Exception:
        return out
    lines = [l for l in (draft.get("lines") or []) if _narr(l)]
    for m in (spec.get("motifs") or []):
        name = str(m.get("name") or "")
        if not name:
            continue
        stems = {sd.stem(w) for w in sd._words(name) if w not in sd.STOP}
        if not stems:
            continue
        hits = []
        for l in lines:
            ws = {sd.stem(w) for w in sd._words(narrator_text(_narr(l)))}
            if stems <= ws:
                hits.append(l.get("id"))
        out[name] = hits
    return out


def samepoint_report(draft: dict, pdir: Path) -> dict:
    errors: list = []
    warns: list = []
    notes: list = []
    stats: dict = {}
    try:
        lines = [l for l in (draft.get("lines") or []) if _narr(l)]
        if len(lines) < 3:
            return {"errors": [], "warns": [], "notes": [
                "[SAME-POINT] fewer than three narrated lines, so adjacency "
                "was not measured. This is not a pass."], "stats": {}}

        min_idf = float(getattr(config, "SEMANTIC_DUP_MIN_IDF", 3.0))
        min_args = int(getattr(config, "SEMANTIC_DUP_MIN_ARGS", 1))
        cands = sd.adjacent_duplicates(lines, min_idf, min_args)
        stats["candidates"] = [[c["a"], c["b"]] for c in cands]
        stats["candidate_count"] = len(cands)

        # Which candidates has a review actually adjudicated? A candidate is
        # closed when review.md names BOTH line ids in a resolved or answered
        # finding - naming one of the pair is not a judgement about the pair.
        closed: set = set()
        adjudicated = None
        try:
            from pipeline import review_artifacts as ra
            art = ra.parse_artifact(Path(pdir) / "review.md")
            adjudicated = True
            for f in (art.get("findings") or []):
                if str(f.get("status") or "").upper() not in ("RESOLVED",
                                                              "ANSWERED"):
                    continue
                ids = {str(i) for i in (f.get("ids") or [])}
                for c in cands:
                    if {str(c["a"]), str(c["b"])} <= ids:
                        closed.add((c["a"], c["b"]))
        except Exception:
            adjudicated = False

        open_c = [c for c in cands if (c["a"], c["b"]) not in closed]
        stats["adjudicated"] = len(closed)
        stats["open"] = len(open_c)

        if cands:
            warns.append(
                f"[SAME-POINT] {len(cands)} adjacent pair(s) may make the "
                f"same point in different words: "
                + "; ".join(f"{c['a']}+{c['b']} ({c['why']})"
                            for c in cands[:8])
                + ". This instrument is a candidate filter, not a verdict - "
                  "it has 8 false positives in 104 on an approved draft, so "
                  "a human or an independent review agent decides.")
        if not adjudicated:
            notes.append(
                "[SAME-POINT] review.md could not be read, so no candidate "
                "is recorded as adjudicated. The warning above is unresolved, "
                "not cleared.")
        elif open_c:
            errors.append(
                f"[SAME-POINT] {len(open_c)} of {len(cands)} candidate "
                f"pair(s) have not been adjudicated in review.md: "
                + "; ".join(f"{c['a']}+{c['b']}" for c in open_c[:8])
                + ". The detector cannot decide these - a reviewer must. "
                  "Record a finding naming BOTH line ids and close it "
                  "RESOLVED (you cut or reworded one) or ANSWERED (they are "
                  "a build-up, not a restatement, and here is why).")
        elif cands:
            notes.append(
                f"[SAME-POINT] all {len(cands)} candidate pair(s) were "
                f"adjudicated in review.md.")

        # ---- motif budget, recounted by meaning ------------------------ #
        uses = motif_uses(draft, Path(pdir))
        stats["motif_uses"] = uses
        cap = int(getattr(config, "MOTIF_LINES_MAX", 4))
        over = {k: v for k, v in uses.items() if len(v) > cap}
        if over:
            errors.append(
                f"[SAME-POINT] {len(over)} running bit(s) exceed the "
                f"{cap}-line budget when counted by MEANING rather than by "
                f"the bit's literal phrase: "
                + "; ".join(f"\"{k}\" on {len(v)} lines {v[:6]}"
                            for k, v in list(over.items())[:4])
                + ". Keep the setup and the payoff; reword the middle uses.")
        if uses:
            notes.append(
                "[SAME-POINT] motif uses by meaning: "
                + "; ".join(f"\"{k}\" {len(v)}" for k, v in uses.items())
                + ". This counter catches 3 of 5 hand-counted uses on the "
                  "control bit, so it is a floor: a bit reported inside "
                  "budget may still be over it.")
    except Exception as e:                                   # pragma: no cover
        errors.append(
            f"[SAME-POINT] did not run: {type(e).__name__}: {e}. Treat this "
            f"draft as UNCHECKED for restatement.")
    return {"errors": errors, "warns": warns, "notes": notes, "stats": stats}
