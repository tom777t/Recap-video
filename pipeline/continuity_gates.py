"""Continuity and mismatch gates: things a flat draft tends to hide.

Each of these is a defect found in the shipped Tokyo Drift draft, named with
the line that produced it:

  BACKWARD-CLIP    line 101 goes 01:33:57 -> 01:33:51, so the picture jumps
                   BACKWARD inside one sequence and the viewer sees the same
                   footage twice.
  FACT-CONSISTENCY line 5 puts him in Arizona; line 58 says he was "shipped
                   out of Alabama".
  CHEKHOV          line 53 introduces Reiko's "visitor" and nothing ever
                   explains it.
  REPEATED-EVENT   lines 16 and 17 both land him in Tokyo.
  NO-JARGON        editing language in the narration (handled in
                   pacing_gates, listed here for the record).
  VISUAL-CLAIM     an interim rule until Phase 4's shot matching: a line that
                   makes a concrete visual claim must have that detail in the
                   TAGS of a shot inside its own window, or it is asserting
                   something the picture may not show.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def _narr(ln: dict) -> str:
    return str(ln.get("narration") or "").strip()


def _ts(v):
    from pipeline.draft import parse_ts
    try:
        return parse_ts(v)
    except Exception:
        return None


def backward_clips(draft: dict, max_back_sec: float = 0.0) -> list:
    """Lines whose window starts BEFORE the previous line's window.

    A recap moves forward through the film. Going back inside a sequence
    replays footage the viewer has just seen - which is what line 101 did,
    stepping from 01:33:57 to 01:33:51.

    A deliberate jump back is legitimate when the draft says so (a callback
    marked with `callback_beat`), so that is the one exemption.
    """
    out = []
    prev = None
    for ln in draft.get("lines") or []:
        if ln.get("pool") or ln.get("montage"):
            continue
        a = _ts(ln.get("clip_start"))
        if a is None:
            continue
        if prev is not None and a < prev[1] - float(max_back_sec):
            if not ln.get("callback_beat"):
                out.append({"line_id": ln.get("id"), "at": a,
                            "prev_line": prev[0], "prev_at": prev[1],
                            "back_sec": round(prev[1] - a, 2)})
        prev = (ln.get("id"), a)
    return out


def repeated_events(draft: dict) -> list:
    """Consecutive-ish lines that narrate the SAME event.

    Surface test: two lines within a short span of each other sharing a rare
    content signature (a place or an arrival verb plus the same proper noun).
    Lines 16 and 17 both landed Sean in Tokyo.
    """
    lines = [ln for ln in (draft.get("lines") or []) if _narr(ln)]
    # An arrival AT A NAMED PLACE. Requiring the place is what separates
    # "Sean lands alone in Tokyo" from "the car lands upside down against a
    # kerb" - the first version matched the second and reported lines 74/76
    # while missing the real pair, 16 and 17, which both land him in Tokyo.
    ARRIVE = re.compile(
        r"\b(?:arriv\w+|lands?|landed|touch(?:es|ed)? down|gets? off|"
        r"steps? off|moves? to|shipped (?:off|out)(?: to)?|flown? to|"
        r"sent to|now in|is in|ends? up in|wakes up in)\b", re.I)
    PLACE = re.compile(r"\b(?:in|to|into|at)\s+(?P<p>[A-Z][a-z]{2,})\b")
    out = []
    def places(t):
        return {m.group("p") for m in PLACE.finditer(t)}

    for i, a in enumerate(lines):
        ta = _narr(a)
        if not ARRIVE.search(ta):
            continue
        pa = places(ta)
        if not pa:
            continue
        for b in lines[i + 1:i + 4]:
            tb = _narr(b)
            if not ARRIVE.search(tb):
                continue
            shared = pa & places(tb)
            if shared:
                out.append({"a": a.get("id"), "b": b.get("id"),
                            "shared": sorted(shared)})
    return out


def fact_conflicts(draft: dict, pdir: Path) -> list:
    """Places and names that contradict each other or film_facts.json.

    Deliberately narrow: it compares PLACE words the draft uses for the same
    role, and checks every place/name against film_facts when that file lists
    them. A broad semantic check is not possible here and pretending otherwise
    would produce noise.
    """
    out = []
    facts = {}
    fp = Path(pdir) / "film_facts.json"
    if fp.exists():
        try:
            facts = json.loads(fp.read_text(encoding="utf-8-sig"))
        except Exception:
            facts = {}
    blob = json.dumps(facts, ensure_ascii=False).lower() if facts else ""

    US_STATES = (
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
        "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
        "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
        "maine", "maryland", "massachusetts", "michigan", "minnesota",
        "mississippi", "missouri", "montana", "nebraska", "nevada",
        "new hampshire", "new jersey", "new mexico", "new york",
        "north carolina", "ohio", "oklahoma", "oregon", "pennsylvania",
        "tennessee", "texas", "utah", "vermont", "virginia", "washington",
        "wisconsin", "wyoming")
    seen: dict = {}
    for ln in draft.get("lines") or []:
        t = _narr(ln).lower()
        for st in US_STATES:
            if re.search(rf"\b{re.escape(st)}\b", t):
                seen.setdefault(st, []).append(ln.get("id"))
    if len(seen) > 1:
        out.append({
            "kind": "place",
            "msg": (f"the draft names {len(seen)} different US states for the "
                    f"same back-story: "
                    + ", ".join(f"{k.title()} (line(s) "
                                f"{', '.join(str(i) for i in v)})"
                                for k, v in sorted(seen.items())))})
    if blob:
        for st, ids in seen.items():
            if st not in blob:
                out.append({
                    "kind": "place-vs-facts",
                    "msg": (f"\"{st.title()}\" (line(s) "
                            f"{', '.join(str(i) for i in ids)}) does not "
                            f"appear anywhere in film_facts.json")})
    return out


def chekhov(draft: dict) -> list:
    """A noun introduced with a setup marker and never mentioned again.

    Line 53 introduced Reiko's "visitor" and nothing explained it. The test
    looks for an INDEFINITE reference to a person or object - "a visitor",
    "some guy", "a package" - and checks whether any later line refers to it
    again.
    """
    lines = [ln for ln in (draft.get("lines") or []) if _narr(ln)]
    # A CURATED list of nouns that genuinely promise something. The first
    # version matched any "a <noun>" with a short stop-list and produced 46
    # findings on one draft - "roller", "drawer", "half-built", "shortcut",
    # "cramped" - which buries the one real finding (line 53's "visitor") in
    # noise. For a warning, precision beats recall: a list of 46 is read as
    # zero.
    SETUP_NOUNS = (
        "visitor", "stranger", "message", "letter", "envelope", "package",
        "parcel", "photograph", "photo", "warning", "threat", "secret",
        "debt", "favour", "favor", "promise", "scar", "tattoo", "key",
        "address", "phone call", "voicemail", "rumour", "rumor", "deadline",
        "ultimatum", "offer", "name on", "list", "file", "recording",
        "witness", "informant", "buyer", "dealer", "lawyer", "cousin",
        "uncle", "brother", "sister", "partner", "bodyguard",
    )
    SETUP = re.compile(
        r"\b(?:a|an|some|another)\s+(?P<n>"
        + "|".join(re.escape(n) for n in SETUP_NOUNS) + r")\b", re.I)
    out = []
    for i, ln in enumerate(lines):
        for m in SETUP.finditer(_narr(ln)):
            noun = m.group("n").lower()
            later = " ".join(_narr(x) for x in lines[i + 1:])
            if not re.search(rf"\b{re.escape(noun)}s?\b", later, re.I):
                out.append({"line_id": ln.get("id"), "noun": noun})
    # one finding per noun, worst first
    best: dict = {}
    for r in out:
        best.setdefault(r["noun"], r)
    return list(best.values())


def visual_claims(draft: dict, pdir: Path) -> list:
    """A concrete visual claim must be backed by a TAG inside its own window.

    INTERIM RULE until Phase 4's shot matching. It is narrow on purpose: only
    claims about things the tagger records - a named colour, a vehicle, a
    number of people, an object - and only when shots.json actually covers the
    line's window, so a project without tags is not failed for lacking them.
    """
    from pipeline.draft import parse_ts
    sp = Path(pdir) / "shots.json"
    if not sp.exists():
        return []
    try:
        shots = json.loads(sp.read_text(encoding="utf-8-sig")).get("shots", [])
    except Exception:
        return []
    idx = []
    for s in shots:
        a, b = _ts(s.get("clip_start")), _ts(s.get("clip_end"))
        if a is None or b is None:
            continue
        blob = " ".join(str(s.get(k, "")) for k in
                        ("depicts", "action", "chars", "objects", "note",
                         "tags", "setting")).lower()
        idx.append((a, b, blob))
    if not idx:
        return []

    CLAIM = re.compile(
        r"\b(?P<w>red|blue|green|yellow|orange|purple|pink|white|black|"
        r"silver|gold|neon|"
        r"mustang|evo|evolution|viper|rx-7|rx7|silvia|skyline|nissan|"
        r"minivan|motorbike|scooter|helicopter|"
        r"umbrella|cigarette|suitcase|briefcase|envelope|phone|camera|"
        r"knife|gun|pistol)\b", re.I)
    out = []
    for ln in draft.get("lines") or []:
        t = _narr(ln)
        if not t:
            continue
        a, b = _ts(ln.get("clip_start")), _ts(ln.get("clip_end"))
        if a is None or b is None:
            continue
        cover = [x for x in idx if x[1] > a and x[0] < b]
        if not cover:
            continue       # no tags for this window: cannot judge, do not fail
        blob = " ".join(x[2] for x in cover)
        for m in CLAIM.finditer(t):
            w = m.group("w").lower()
            if w not in blob:
                out.append({"line_id": ln.get("id"), "claim": w})
    best: dict = {}
    for r in out:
        best.setdefault((r["line_id"], r["claim"]), r)
    return list(best.values())


def continuity_report(draft: dict, pdir: Path) -> dict:
    errors: list = []
    warns: list = []

    bc = backward_clips(draft)
    if bc:
        errors.append(
            f"[BACKWARD-CLIP] {len(bc)} line(s) start BEFORE the previous "
            f"line's window, so the picture replays footage the viewer has "
            f"just seen: "
            + "; ".join(f"line {r['line_id']} goes back {r['back_sec']:.1f}s "
                        f"(after line {r['prev_line']})" for r in bc[:6])
            + ". Mark a deliberate return with `callback_beat`.")

    re_ev = repeated_events(draft)
    if re_ev:
        errors.append(
            f"[REPEATED-EVENT] {len(re_ev)} pair(s) of lines narrate the same "
            f"event twice: "
            + "; ".join(f"lines {r['a']} and {r['b']} "
                        f"({', '.join(r['shared'])})" for r in re_ev[:6]))

    fc = fact_conflicts(draft, pdir)
    if fc:
        for r in fc:
            errors.append(f"[FACT-CONSISTENCY] {r['msg']}")

    ck = chekhov(draft)
    if ck:
        warns.append(
            f"[CHEKHOV] {len(ck)} setup(s) are introduced and never paid off: "
            + "; ".join(f"line {r['line_id']} \"{r['noun']}\"" for r in ck[:8])
            + ". Either explain it or cut the mention.")

    vc = visual_claims(draft, pdir)
    if vc:
        warns.append(
            f"[VISUAL-CLAIM] {len(vc)} concrete visual claim(s) are not in the "
            f"tags of any shot inside their own window: "
            + "; ".join(f"line {r['line_id']} \"{r['claim']}\""
                        for r in vc[:8])
            + ". Rewrite as non-visual, or re-point the line. (Interim rule "
              "until Phase 4 shot matching.)")

    return {"errors": errors, "warns": warns, "notes": []}
