"""<film_speaks> selection: let the film talk, 2-3 times, on purpose.

WHY THIS IS A PIPELINE STAGE AND NOT A TASTE DECISION
-----------------------------------------------------
A film_speaks unit is the one place a recap hands the moment to the film: the
narration stops and a character's own line plays at full level. Since the film
audio under narration now comes from the no-vocals stem, it is also the ONLY
original dialogue in the finished video.

The Tokyo Drift draft shipped with ZERO of them. Nothing was broken - no gate
asked for any, so none were written. That is the failure this module fixes: a
device that only happens when somebody remembers is a device that stops
happening. Selection is now a stage with an input, a gate and a cost for
skipping it.

WHAT IS MECHANISED AND WHAT IS NOT
----------------------------------
This module computes the things that are measurable, and refuses to guess at
the things that are not:

  MEASURED here
    * duration (3-15s), and where the quote sits relative to every reveal
      landing, the climax and the film's final line
    * AUDIO CLEANLINESS - the vocals stem's level against the no-vocals stem
      over the quote's own span, in dB. Not a guess about whether music is
      playing: a measurement of it.
    * word overlap against the surrounding narration, which is what
      "already paraphrased" means operationally
    * the transcript's language against the narration's
    * which act the quote falls in, and the gap to every other candidate

  JUDGED by a fresh-context subagent (prompts/film_speaks_select.md)
    * whether the quote really states the reveal or the angle's thesis in the
      character's own words
    * whether it is self-contained given only what the recap has already said
    * which 2-3 of the eligible candidates are the right ones

Mechanising the second group would mean inventing a score for "is this line
good", which is exactly the judgement that should not be faked.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()

# A quote shorter than this does not register as an exchange; longer than this
# and the recap has stopped being a recap. Mirrors config.FILM_SPEAKS_MIN/MAX.
# Transcript segments closer than this join into one quote. MEASURED on
# tokyodrift2006's 559 segments: median segment 1.80s, median inter-segment gap
# 1.37s. The first value here was 1.2s - BELOW the median gap - so it merged
# only 43% of adjacent pairs and mostly failed to assemble an exchange at all.
# At 2.5s it merges 66%, and the pauses inside an exchange are part of the
# exchange: a film_speaks unit plays continuous film audio, so a two-second
# beat between two lines is something to keep, not a seam to avoid.
MERGE_GAP_SEC = 2.5
CLIMAX_TAIL_FRAC = 0.88  # the last 12% of the film is climax territory
REVEAL_WINDOW_SEC = 90.0  # "at or after the land" tolerance, forward only
# Audio: the vocals stem must beat the no-vocals stem by this much over the
# span for the dialogue to be called clean. Measured in dB of mean volume.
AUDIO_CLEAN_MIN_DB = 3.0
# Word overlap above this against a neighbouring narration line means the
# narration has already said it, so the quote would be a repeat.
PARAPHRASE_MAX_OVERLAP = 0.45

_STOP = {
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "of", "to",
    "in", "on", "at", "for", "with", "from", "by", "is", "are", "was",
    "were", "be", "been", "it", "its", "this", "that", "these", "those",
    "he", "she", "they", "him", "her", "them", "his", "their", "you",
    "your", "i", "me", "my", "we", "us", "our", "as", "not", "no", "do",
    "does", "did", "have", "has", "had", "will", "would", "can", "could",
    "just", "all", "out", "up", "down", "what", "who", "when", "where",
}


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z']+", str(text).lower())
            if len(w) > 2 and w not in _STOP}


def overlap(a: str, b: str) -> float:
    """Jaccard-ish overlap of content words: |A&B| / |A|. 0..1.

    Asymmetric on purpose: the question is "how much of the QUOTE has the
    narration already said", so it is normalised by the quote.
    """
    wa, wb = _words(a), _words(b)
    if not wa:
        return 0.0
    return len(wa & wb) / len(wa)


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
def _transcript(pdir: Path) -> tuple[list, str]:
    try:
        t = json.loads((pdir / "transcript.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return [], ""
    segs = t.get("segments") if isinstance(t, dict) else t
    lang = str((t.get("language") if isinstance(t, dict) else "") or "")
    out = []
    for s in segs or []:
        try:
            a, b = float(s["start"]), float(s["end"])
        except (KeyError, TypeError, ValueError):
            continue
        txt = str(s.get("text") or "").strip()
        if txt and b > a:
            out.append({"a": a, "b": b, "text": txt})
    out.sort(key=lambda s: s["a"])
    return out, lang


def _angle_terms(pdir: Path) -> set:
    """Content words from angle.md's thesis, for a cheap thesis signal."""
    p = pdir / "angle.md"
    if not p.exists():
        return set()
    txt = p.read_text(encoding="utf-8-sig")
    # Prefer an explicit thesis/angle heading; fall back to the whole file.
    m = re.search(r"(?is)^#+\s*(thesis|angle|the angle)\b(.{0,1200})", txt,
                  re.M)
    return _words(m.group(2) if m else txt[:1500])


def angle_quotes(pdir: Path) -> list[str]:
    """Phrases angle.md puts in quotation marks.

    If the angle document QUOTES a line, that line states the thesis by
    definition - there is no stronger signal available. Bag-of-words overlap
    against the thesis prose missed exactly such a line on tokyodrift2006:
    angle.md names B17 ("you can't keep running from your trouble") as "the
    exact words the thesis pays off", and the father actually says "you just
    can't keep moving away every time you get into trouble". Different words,
    same line - so the match has to be on the QUOTED PHRASE, normalised by the
    phrase rather than by the whole document, and tolerant of paraphrase.
    """
    p = pdir / "angle.md"
    if not p.exists():
        return []
    txt = p.read_text(encoding="utf-8-sig")
    out = []
    for m in re.finditer(r"[\"\u201c]([^\"\u201c\u201d]{8,160})[\"\u201d]", txt):
        phrase = m.group(1).strip()
        if len(phrase.split()) >= 3:
            out.append(phrase)
    # dedupe, keep order
    seen, uniq = set(), []
    for q in out:
        k = q.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(q)
    return uniq


def angle_beats(pdir: Path) -> list[str]:
    """Beat ids angle.md names as load-bearing (its running bits and payoffs).

    The angle document says which beats carry the thesis - "B13 ... and B17
    ... the exact words the thesis pays off". Dialogue inside a beat the angle
    singles out is thesis dialogue, and this survives any amount of paraphrase
    because it matches on the BEAT, not on the wording.
    """
    p = pdir / "angle.md"
    if not p.exists():
        return []
    txt = p.read_text(encoding="utf-8-sig")
    return sorted(set(re.findall(r"\bB(\d{1,3})\b", txt)),
                  key=lambda s: int(s))


def beat_windows(project: str) -> dict:
    """{beat_id: (start_sec, end_sec)} from the beat map.

    A beat's end is the next beat's start, which is how every other reader of
    this file treats it.
    """
    import config
    from pipeline.draft import parse_ts
    pdir = Path(config.project_dir(project))
    rows = []
    for name in ("beats_proposal.md", "beats_proposal_machine.md"):
        p = pdir / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            m = re.match(r"\s*(B\d+)\s*\|\s*(\d{1,2}:\d{2}:\d{2})", line)
            if m:
                try:
                    rows.append((m.group(1), parse_ts(m.group(2))))
                except Exception:
                    pass
        if rows:
            break
    rows.sort(key=lambda r: r[1])
    out = {}
    for i, (bid, a) in enumerate(rows):
        b = rows[i + 1][1] if i + 1 < len(rows) else a + 60.0
        out[bid] = (a, b)
    return out


def reveal_rows(project: str) -> list[dict]:
    """[{id, land, fact, hold}] read STRAIGHT from reveals.json.

    reveals.json is the authoritative reveal file and already carries all
    three fields. An earlier version paired pipeline.draft.parse_reveal_map
    (which reads a fenced ```reveal-map block in beats_proposal.md) with
    reveals.json rows BY INDEX - two sources that have to agree on ordering,
    and that silently produced NO reveals at all whenever the fence was
    missing. Both the eligibility test and the spoiler check went quiet
    together, which is the worst way for a gate to fail.
    """
    import config
    from pipeline.draft import parse_ts
    pdir = Path(config.project_dir(project))
    try:
        doc = json.loads((pdir / "reveals.json").read_text(
            encoding="utf-8-sig"))
    except Exception:
        return []
    out = []
    for i, row in enumerate(doc.get("reveals") or [], start=1):
        land = row.get("land") or row.get("land_ref")
        sec = 0.0
        if land:
            try:
                sec = parse_ts(str(land))
            except Exception:
                sec = 0.0
        out.append({"id": row.get("id") or f"R{i}", "land": sec,
                    "land_ref": str(land or ""),
                    "fact": str(row.get("fact") or ""),
                    "hold": [str(h) for h in (row.get("hold") or [])]})
    return out


def acts(project: str, n_acts: int | None = None) -> list:
    """Act boundaries in seconds, from the beat map split into equal groups.

    Matches how tools/act_payload.py divides a film (RECAP_ACTS, default 4), so
    "one per act" means the same thing everywhere.
    """
    import os
    import config
    from pipeline.draft import parse_ts
    if n_acts is None:
        n_acts = int(os.environ.get("RECAP_ACTS", "4"))
    pdir = Path(config.project_dir(project))
    ts = []
    for name in ("beats_proposal.md", "beats_proposal_machine.md"):
        p = pdir / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            m = re.match(r"\s*B\d+\s*\|\s*(\d{1,2}:\d{2}:\d{2})", line)
            if m:
                try:
                    ts.append(parse_ts(m.group(1)))
                except Exception:
                    pass
        if ts:
            break
    if not ts:
        return []
    ts.sort()
    per = max(1, (len(ts) + n_acts - 1) // n_acts)
    bounds = []
    for i in range(0, len(ts), per):
        bounds.append(ts[i])
    return bounds


def act_of(sec: float, bounds: list) -> int:
    if not bounds:
        return 0
    n = 1
    for i, b in enumerate(bounds, start=1):
        if sec >= b:
            n = i
    return n


# --------------------------------------------------------------------------- #
# Audio cleanliness - measured, not assumed
# --------------------------------------------------------------------------- #
def _mean_db(ff: str, path: Path) -> float:
    r = subprocess.run(
        [ff, "-hide_banner", "-i", str(path), "-af", "volumedetect",
         "-f", "null", "-"], capture_output=True, text=True)
    for line in (r.stderr or "").splitlines():
        if "mean_volume" in line:
            try:
                return float(line.split("mean_volume:")[1].strip().split()[0])
            except (IndexError, ValueError):
                pass
    return float("nan")


def audio_cleanliness(project: str, a: float, b: float) -> dict:
    """How far the DIALOGUE stands above the music and effects, in dB.

    {vocals_db, other_db, margin_db, measured: bool, note}

    `measured` False means separation was unavailable - which is reported, not
    silently treated as clean. A quote cannot be called clean on the strength
    of nobody having checked.
    """
    import config
    import math
    from pipeline import stems as _st
    vo, nv = _st.separate_span(project, a, b)
    if vo is None or nv is None:
        ok, why = _st.available()
        return {"vocals_db": None, "other_db": None, "margin_db": None,
                "measured": False,
                "note": f"not measured - {why if not ok else 'separation failed'}"}
    ff = config.ffmpeg()
    v, o = _mean_db(ff, vo), _mean_db(ff, nv)
    if math.isnan(v) or math.isnan(o):
        return {"vocals_db": None, "other_db": None, "margin_db": None,
                "measured": False, "note": "could not measure levels"}
    return {"vocals_db": round(v, 1), "other_db": round(o, 1),
            "margin_db": round(v - o, 1), "measured": True, "note": ""}


# --------------------------------------------------------------------------- #
# Candidate generation
# --------------------------------------------------------------------------- #
def _rank(crits: list, ev: dict) -> float:
    """Signal strength, for ordering only - never for selection.

    Selection is the subagent's job; this just decides what survives a --top
    cut, so the strongest evidence is what reaches them.
    """
    score = 0.0
    if "reveal_own_words" in crits:
        score += 5.0                      # the character says the reveal
    if "angle_quote" in ev:
        score += 4.0 + float(ev["angle_quote"].get("match") or 0)
    if "climax_or_final" in crits:
        score += 3.0
        if "final" in str(ev.get("position", "")):
            score += 1.0
    if "thesis_overlap" in ev:
        score += 1.0 + float(ev.get("thesis_overlap") or 0)
    if ev.get("in_angle_beat"):
        score += 0.75
    return round(score, 3)


def candidates(project: str, measure_audio: bool = True,
               limit: int = 0) -> list[dict]:
    """Eligible film_speaks candidates with every measurable fact attached.

    Eligibility (at least one must hold, per the rules in
    prompts/recap_style.md):
      reveal_own_words - the quote sits AT OR AFTER a reveal's landing and uses
                         one of that reveal's own held terms, i.e. the
                         character says the thing the recap has been holding
      thesis           - the quote's words overlap the angle's thesis
      climax_or_final  - the quote is in the climax stretch or is the film's
                         last line
    """
    import config
    from pipeline.draft import parse_reveal_map
    pdir = Path(config.project_dir(project))
    segs, lang = _transcript(pdir)
    if not segs:
        return []

    lo = float(getattr(config, "FILM_SPEAKS_MIN_SEC", 3.0))
    hi = float(getattr(config, "FILM_SPEAKS_MAX_SEC", 15.0))
    dur = max(s["b"] for s in segs)

    # 1. Build EVERY contiguous run of segments that lands inside [lo, hi],
    #    not one greedy partition of the transcript.
    #
    #    Greedy merging was the first attempt and it was actively harmful: it
    #    swallowed a good 8.8-second quote into a run that then exceeded the
    #    15-second cap and was discarded, so raising the merge gap REDUCED the
    #    candidate count from 3 to 1. Generation should be generous and let
    #    selection narrow; overlapping candidates are a feature, because the
    #    right quote boundary is a judgement the subagent makes.
    quotes = []
    seen = set()
    for i in range(len(segs)):
        a = segs[i]["a"]
        text = segs[i]["text"]
        j = i
        while j < len(segs):
            if j > i:
                gap = segs[j]["a"] - segs[j - 1]["b"]
                if gap > MERGE_GAP_SEC:
                    break
                text = (text + " " + segs[j]["text"]).strip()
            b = segs[j]["b"]
            if b - a > hi:
                break
            if b - a >= lo:
                key = (round(a, 2), round(b, 2))
                if key not in seen:
                    seen.add(key)
                    quotes.append({"a": a, "b": b, "text": text})
            j += 1
            if j - i > 8:        # a quote is an exchange, not a scene
                break

    rv = reveal_rows(project)

    thesis = _angle_terms(pdir)
    a_quotes = angle_quotes(pdir)
    a_beats = angle_beats(pdir)
    bwins = beat_windows(project)
    # the time spans of the beats the angle names as load-bearing
    thesis_spans = [bwins[f"B{b}"] for b in a_beats if f"B{b}" in bwins]
    act_bounds = acts(project)
    final_a = quotes[-1]["a"] if quotes else 0.0

    out = []
    for q in quotes:
        length = q["b"] - q["a"]
        if length < lo or length > hi:
            continue
        low = q["text"].lower()

        crits = []
        ev = {}
        # (a) the reveal in the character's own words
        for r in rv:
            if not r["land"]:
                continue
            if q["a"] + 0.5 < r["land"]:
                continue                      # before the land: a spoiler
            if q["a"] - r["land"] > REVEAL_WINDOW_SEC:
                continue
            hit = [h for h in r["hold"] if h.lower() in low]
            if hit or (r["fact"] and overlap(q["text"], r["fact"]) >= 0.3):
                crits.append("reveal_own_words")
                ev["reveal"] = {"id": r["id"], "land": r["land"],
                                "matched": hit[:3],
                                "fact_overlap": round(
                                    overlap(q["text"], r["fact"]), 2)}
                break
        # (b) the angle's thesis in a character's words. Three signals, from
        #     strongest to weakest - any of them fires `thesis`.
        #
        #     b1. the angle QUOTES this line. Matched on the quoted phrase and
        #         normalised by it, so a paraphrase still matches: the angle
        #         saying "you can't keep running from your trouble" has to find
        #         "you just can't keep moving away every time you get into
        #         trouble". Bag-of-words against the whole document did not.
        for aq in a_quotes:
            # A RATIO alone is not enough. angle.md quotes "I'm his father",
            # whose content words are {i'm, father}, so any line containing one
            # of them scores exactly 0.50 and qualified - which put a laptop
            # pitch, a wrong-train exchange and a line about ketchup in the
            # list. Require at least two MATCHED content words as well, which
            # keeps the real target ("you can't keep running from your
            # trouble", 2 of 4 matched) and drops the single-word coincidences.
            _aw = _words(aq)
            _hit = _aw & _words(q["text"])
            if len(_hit) >= 2 and len(_hit) / max(1, len(_aw)) >= 0.5:
                crits.append("thesis")
                ev["angle_quote"] = {"phrase": aq,
                                     "match": round(len(_hit) / len(_aw), 2),
                                     "matched_words": sorted(_hit)}
                break
        #     b2. sitting inside a beat the angle names is NOT eligibility.
        #         It was, briefly, and it produced 696 candidates out of 559
        #         transcript segments: angle.md names about forty beat ids and
        #         each beat spans 30-60s, so nearly every line in the film
        #         "qualified". The signal says this BEAT matters, not that this
        #         LINE states the thesis - so it is kept as metadata for
        #         ranking and does not make a line eligible on its own.
        in_angle_beat = any(ba - 0.5 <= q["a"] < bb for (ba, bb) in thesis_spans)
        #     b3. plain word overlap with the thesis prose - the weak signal,
        #         kept because it catches lines the angle never thought to name.
        if "thesis" not in crits and thesis:
            ov = overlap(q["text"], " ".join(sorted(thesis)))
            if ov >= 0.35:
                crits.append("thesis")
                ev["thesis_overlap"] = round(ov, 2)
        # (c) the climax, or the film's last line
        if q["a"] >= dur * CLIMAX_TAIL_FRAC:
            crits.append("climax_or_final")
            ev["position"] = ("final line" if q["a"] >= final_a - 0.01
                              else f"last {100*(1-CLIMAX_TAIL_FRAC):.0f}% of the film")
        if not crits:
            continue

        if in_angle_beat:
            ev["in_angle_beat"] = True
        out.append({
            "start": round(q["a"], 2), "end": round(q["b"], 2),
            "seconds": round(length, 2),
            "text": q["text"],
            "criteria": crits,
            "evidence": ev,
            "act": act_of(q["a"], act_bounds),
            "language": lang,
            "words": len(q["text"].split()),
            "rank": _rank(crits, ev),
        })

    # Strongest signal first, so a --top cut keeps the best rather than the
    # earliest. An angle QUOTE outranks a bare thesis word-overlap by a long
    # way: one is the angle naming this line, the other is shared vocabulary.
    out.sort(key=lambda c: (-c["rank"], c["start"]))
    if limit:
        # The budget is spread across ACTS and across distinct MOMENTS, not
        # spent on the top N rows.
        #
        # Two failures got it here. A plain head() returned five boundary
        # variants of one line and nothing else. Then a moment-diversity cut
        # still ordered purely by rank, and dropped the strongest act-3
        # candidate in the film (+27.1 dB, the thesis turn) because one signal
        # - a match against a phrase angle.md quotes - outranked everything
        # else and there are 173 of those. A selector cannot choose what it
        # cannot see, so recall across the film matters more here than ranking
        # precision; the subagent does the choosing.
        MAX_PER_MOMENT = 3
        MOMENT_SEC = 15.0
        by_act: dict = {}
        for c in out:
            by_act.setdefault(c["act"], []).append(c)
        n_acts = max(1, len(by_act))
        share = max(1, limit // n_acts)
        kept: list = []
        per: dict = {}

        def _signal(c) -> str:
            ev = c["evidence"]
            if "reveal" in ev:
                return "reveal"
            if "climax_or_final" in c["criteria"]:
                return "climax"
            if "angle_quote" in ev:
                return "angle_quote"
            if ev.get("in_angle_beat"):
                return "angle_beat"
            return "thesis_overlap"

        def _take(pool, budget):
            """Round-robin by SIGNAL, so one kind of evidence cannot fill the
            act on its own.

            Pure rank order gave an act ten angle_quote candidates and nothing
            else, which hid the strongest line in the film (+27.1 dB, the beat
            angle.md names as paying off the thesis) behind a signal that
            happens to fire 173 times. The selector needs the best of each KIND
            of evidence, not the top of one list.
            """
            groups: dict = {}
            for c in pool:
                groups.setdefault(_signal(c), []).append(c)
            order = sorted(groups, key=lambda k: -max(
                x["rank"] for x in groups[k]))
            n = 0
            while n < budget and len(kept) < limit:
                progressed = False
                for k in order:
                    if not groups[k]:
                        continue
                    c = groups[k].pop(0)
                    key = int(c["start"] // MOMENT_SEC)
                    if sum(per.get(j, 0) for j in (key - 1, key, key + 1)) \
                            >= MAX_PER_MOMENT:
                        progressed = True
                        continue
                    per[key] = per.get(key, 0) + 1
                    kept.append(c)
                    n += 1
                    progressed = True
                    if n >= budget or len(kept) >= limit:
                        break
                if not progressed:
                    break

        for act in sorted(by_act):
            _take(by_act[act], share)
        # spend anything left over on the best remaining, wherever they are
        if len(kept) < limit:
            seen = {(c["start"], c["end"]) for c in kept}
            _take([c for c in out if (c["start"], c["end"]) not in seen],
                  limit - len(kept))
        kept.sort(key=lambda c: (-c["rank"], c["start"]))
        out = kept

    if measure_audio:
        for c in out:
            c["audio"] = audio_cleanliness(project, c["start"], c["end"])
    return out


def audit(project: str, draft: dict) -> list[str]:
    """Every film_speaks gate, as a list of problems. Empty = clean.

    FILM-SPEAKS-COUNT      2-3 per film, and ZERO when eligible candidates
                           exist is an error - that is the failure that shipped
    FILM-SPEAKS-JUSTIFIED  criterion + one-sentence justification per unit
    NO-PARAPHRASE          the preceding narration must not already say it
    AUDIO-CLEAN            the vocals stem must measurably dominate the span
    SPACING                one per act, never two within the minimum gap
    SPOILER                a quote may not precede the reveal it reveals
    """
    import config
    from pipeline.draft import parse_ts
    pdir = Path(config.project_dir(project))
    lines = list(draft.get("lines") or [])
    units = [ln for ln in lines if ln.get("film_speaks_seconds") is not None]
    problems: list[str] = []

    lo_n = 2
    hi_n = int(getattr(config, "FILM_SPEAKS_MAX_PER_FILM", 3))
    must = tuple(getattr(config, "FILM_SPEAKS_MUST_SERVE",
                         ("reveal", "climax", "thesis")))
    min_gap = float(getattr(config, "FILM_SPEAKS_MIN_GAP_SEC", 180.0))
    sec_lo = float(getattr(config, "FILM_SPEAKS_MIN_SEC", 3.0))
    sec_hi = float(getattr(config, "FILM_SPEAKS_MAX_SEC", 15.0))

    # ---- COUNT, including the zero case ---------------------------------- #
    if len(units) > hi_n:
        problems.append(
            f"[FILM-SPEAKS-COUNT] {len(units)} units, cap {hi_n}. This is the "
            f"only original dialogue in the video; past {hi_n} it stops being "
            f"an event and becomes a copyright surface.")
    if len(units) < lo_n:
        # Zero (or one) is only acceptable if NOTHING qualified. Checking that
        # is the whole point: a draft with no units and a transcript full of
        # eligible lines is the failure this gate exists for.
        try:
            cands = candidates(project, measure_audio=False)
        except Exception as e:
            cands = []
            problems.append(f"[FILM-SPEAKS-COUNT] {len(units)} unit(s) and the "
                            f"candidate scan failed ({e}) - cannot confirm "
                            f"that none qualified.")
        if cands:
            problems.append(
                f"[FILM-SPEAKS-COUNT] {len(units)} film_speaks unit(s), but "
                f"{len(cands)} eligible candidate(s) exist. A recap with no "
                f"original dialogue is a choice nobody made - run "
                f"`python tools/film_speaks_candidates.py --project {project}` "
                f"and select {lo_n}-{hi_n}. Best candidates: "
                + "; ".join(f"{c['start']:.0f}s \"{c['text'][:50]}\""
                            for c in cands[:3]))
        elif len(units) == 0:
            console.print("[dim]film_speaks: none, and no candidate qualified "
                          "- that is a legitimate zero.[/]")

    by_id = {ln.get("id"): i for i, ln in enumerate(lines)}
    for ln in units:
        lid = ln.get("id")
        sec = float(ln.get("film_speaks_seconds") or 0.0)
        if not (sec_lo <= sec <= sec_hi):
            problems.append(f"[FILM-SPEAKS-COUNT] line {lid}: {sec:.1f}s is "
                            f"outside {sec_lo:.0f}-{sec_hi:.0f}s")

        # ---- JUSTIFIED ---------------------------------------------------- #
        why = str(ln.get("film_speaks_reason") or "").strip()
        crit = str(ln.get("film_speaks_criterion") or "").strip()
        if not crit:
            problems.append(
                f"[FILM-SPEAKS-JUSTIFIED] line {lid}: no "
                f"`film_speaks_criterion`. Name which of {'/'.join(must)} it "
                f"serves.")
        elif not any(m in crit.lower() for m in must):
            problems.append(
                f"[FILM-SPEAKS-JUSTIFIED] line {lid}: criterion {crit!r} does "
                f"not name a {'/'.join(must)}.")
        if len(why.split()) < 5:
            problems.append(
                f"[FILM-SPEAKS-JUSTIFIED] line {lid}: `film_speaks_reason` is "
                f"missing or too short to be a justification.")

        # ---- NO-PARAPHRASE: the line BEFORE must not already say it ------- #
        quote = str(ln.get("film_speaks_quote") or "").strip()
        idx = by_id.get(lid)
        if quote and idx:
            prev = next((lines[j] for j in range(idx - 1, -1, -1)
                         if str(lines[j].get("narration") or "").strip()), None)
            if prev is not None:
                ov = overlap(quote, str(prev.get("narration")))
                if ov > PARAPHRASE_MAX_OVERLAP:
                    problems.append(
                        f"[NO-PARAPHRASE] line {lid}: the preceding narration "
                        f"(line {prev.get('id')}) already contains "
                        f"{ov:.0%} of the quote's content words. Set the "
                        f"moment up without saying it - the hand-over lands "
                        f"flat if the viewer has just heard it in other words.")

        # ---- AUDIO-CLEAN -------------------------------------------------- #
        cs = ln.get("clip_start")
        if cs:
            try:
                a = parse_ts(cs)
            except Exception:
                a = None
            if a is not None:
                got = ln.get("film_speaks_audio_margin_db")
                if got is None:
                    m = audio_cleanliness(project, a, a + sec)
                    got = m.get("margin_db")
                    if not m.get("measured"):
                        problems.append(
                            f"[AUDIO-CLEAN] line {lid}: dialogue cleanliness "
                            f"was never measured ({m.get('note')}). A quote "
                            f"cannot be called clean because nobody checked - "
                            f"install separation or drop the unit.")
                        got = None
                if got is not None and float(got) < AUDIO_CLEAN_MIN_DB:
                    problems.append(
                        f"[AUDIO-CLEAN] line {lid}: the vocals stem is only "
                        f"{float(got):+.1f} dB over the music and effects "
                        f"(need >= {AUDIO_CLEAN_MIN_DB:.0f} dB). The line will "
                        f"not be intelligible at full level.")

        # ---- SPOILER: a quote may not precede the reveal it reveals ------- #
        if quote and cs:
            try:
                a = parse_ts(cs)
            except Exception:
                a = None
            if a is not None:
                for r in reveal_rows(project):
                    land = float(r.get("land") or 0.0)
                    if not land or a + 0.5 >= land:
                        continue
                    hit = [h for h in r["hold"]
                           if str(h).lower() in quote.lower()]
                    if hit:
                        problems.append(
                            f"[FILM-SPEAKS-SPOILER] line {lid} at {a:.0f}s "
                            f"quotes {hit[:2]}, held by {r['id']} until "
                            f"{land:.0f}s.")

    # ---- SPACING ---------------------------------------------------------- #
    pos = []
    for ln in units:
        cs = ln.get("clip_start")
        if not cs:
            continue
        try:
            pos.append((parse_ts(cs), ln.get("id")))
        except Exception:
            pass
    pos.sort()
    for (p1, i1), (p2, i2) in zip(pos, pos[1:]):
        if p2 - p1 < min_gap:
            problems.append(
                f"[FILM-SPEAKS-SPACING] lines {i1} and {i2} are "
                f"{p2 - p1:.0f}s apart; the minimum is {min_gap:.0f}s so they "
                f"cannot cluster.")
    bounds = acts(project)
    if bounds:
        seen: dict = {}
        for p, i in pos:
            n = act_of(p, bounds)
            if n in seen:
                problems.append(
                    f"[FILM-SPEAKS-SPACING] lines {seen[n]} and {i} are both "
                    f"in act {n}; at most one per act.")
            else:
                seen[n] = i
    return problems


def annotate_paraphrase(project: str, cands: list) -> list:
    """Attach the highest word overlap with any nearby narration line.

    This is what "already paraphrased by nearby narration" means in practice:
    if the line before the quote already says it, the quote is a repeat and the
    hand-over lands flat.
    """
    import config
    from pipeline.draft import parse_ts
    pdir = Path(config.project_dir(project))
    try:
        d = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return cands
    lines = []
    for ln in d.get("lines") or []:
        cs = ln.get("clip_start")
        if not cs:
            continue
        try:
            lines.append((parse_ts(cs), ln.get("id"),
                          str(ln.get("narration") or "")))
        except Exception:
            pass
    lines.sort()
    for c in cands:
        best, best_id = 0.0, None
        for pos, lid, txt in lines:
            if abs(pos - c["start"]) > 60.0:
                continue
            ov = overlap(c["text"], txt)
            if ov > best:
                best, best_id = ov, lid
        c["narration_overlap"] = {"worst": round(best, 2), "line_id": best_id}
    return cands
