# -*- coding: utf-8 -*-
"""opening.py - pick the cold-open scene and the opening mechanism.

WHY. The hook used to be a montage: styled clips under music with a
trailer-voice premise line over them ("over_montage"). Every measured
top recap channel in the 2026 opening study starts the film's own
picture at frame one with narration on it, and the premise sentence
lives in the TITLE, not the voice. The design that replaces the
montage hook is docs/DESIGN_human_variation.md's sibling report
(reports/Mo dau video recap cuon hut.md, rules R0-R6); this module is
R1 + R2 + R4:

    R1  score every candidate scene on CHARGE x LOOP-BACK x
        NON-RESOLUTION x GENRE-CANON x HOOK-IMAGE and take the best;
    R2  best score in the film's opening zone -> OPEN-A (chronological
        "anchor + disruption"); best score beyond the midpoint ->
        OPEN-B (loop-back fragment, Warner Bros / Star Trek pattern);
    R4  the genre lever (FEAR / DESIRE / THRILL / AWE) is chosen from
        the film's metadata and recorded, so the anti-sameness gate can
        force a different mechanism when the last videos repeat.

NO FILM-SPECIFIC CONTENT LIVES HERE. Lexicons are generic English
charge words; the candidates come from shots.json / plan.json beats.

CALIBRATE BEFORE TRUSTING (AGENTS.md). tools/calibrate_opener.py runs
this picker on a known-good opening (the approved Tokyo Drift opener
zone) and a known-bad one (the distributor-logo establishing shot). If
it cannot separate the two it is not an instrument and must not gate
anything; the commit that lands this module states both control
results.

PURE: every function takes parsed data and returns data. The loader
(read) is the only thing that touches disk.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import config

LEVERS = ("FEAR", "DESIRE", "THRILL", "AWE")

# OPEN-A accepts a candidate this deep into the film's opening zone
# (a fraction of runtime; Tokyo Drift's bully scene sits at ~3%).
OPEN_ZONE = 0.12
# OPEN-B is required when the best candidate lands after this fraction.
MIDPOINT = 0.50
# A reveal landing protects this many seconds either side of it: a beat
# overlapping a landing answers a question the film spends Acts 2-3
# asking, and the opener must not spoil it (NON-RESOLUTION).
REVEAL_GUARD_SEC = 45.0

# ---- R1 CHARGE: extremity of the moment -------------------------------
# Word-boundary matched (substring matching scored "race" inside
# "braces" and the camera word "shot" as violence - both real false
# positives on the Tokyo Drift calibration). Distinct markers count,
# not repeats: "crash ... crash" is one crash.
_CHARGE = {
    "kill": 2, "kills": 2, "killed": 2, "murder": 2, "murders": 2,
    "murdered": 2, "death": 2, "dies": 2, "died": 2, "dead": 2,
    "corpse": 2, "blood": 2, "bloody": 2, "gore": 2, "wound": 1,
    "stab": 2, "stabbed": 2, "shoots": 2, "shooting": 2, "gunshot": 2,
    "gunshots": 2, "gun": 1, "fires": 1, "strangles": 2,
    "buried": 1, "grave": 2, "funeral": 2, "coffin": 2,
    "crash": 2, "crashes": 2, "crashed": 2, "collides": 2,
    "collision": 2, "explosion": 2, "explodes": 2, "detonates": 2,
    "burns": 1, "burning": 1, "fire": 1, "smash": 1, "smashes": 1,
    "falls": 1, "plunge": 2, "plunges": 2, "wreck": 1, "wrecks": 1,
    "wrecked": 1, "destroyed": 1, "thrown": 1, "rolls": 1,
    "kiss": 2, "kisses": 2, "kissing": 2, "bed": 1, "sex": 2,
    "naked": 2, "undresses": 2, "affair": 1, "lover": 1, "seduces": 2,
    "unmasks": 2, "betrays": 2, "betrayal": 2, "arrest": 1,
    "arrested": 1, "escape": 1, "escapes": 1, "fight": 1, "fights": 1,
    "brawl": 1, "punch": 1, "punches": 1, "beats": 1, "chase": 1,
    "chases": 1, "hunted": 1, "knife": 1, "blade": 1, "scream": 1,
    "screams": 1, "screaming": 1, "panic": 1, "scuffle": 1,
    "scuffles": 1, "humiliation": 1,
}
# Depicts tags that carry charge without prose (catalogue vocabulary).
_CHARGE_TAGS = {"reveal", "aftermath", "discovery"}

# ---- R1 GENRE-CANON: the lever's own markers --------------------------
_CANON = {
    "FEAR": ("dread", "terror", "haunted", "nightmare", "monster",
             "shadow", "dark", "darkness", "silence", "silent",
             "whisper", "lurks", "stalks", "stalking", "creature",
             "ghost", "demon", "curse", "vanishes", "missing"),
    "DESIRE": ("kiss", "kisses", "love", "lover", "romance", "wedding",
               "marries", "affair", "embrace", "holds her", "holds him",
               "together", "date", "flirts", "longing", "touch"),
    "THRILL": ("race", "races", "racing", "speed", "chase", "chases",
               "countdown", "deadline", "streak", "record", "odds",
               "bet", "wager", "heist", "pursuit", "wins", "risk"),
    "AWE": ("kingdom", "empire", "army", "mountain", "sky", "sea",
            "dragon", "sword", "immortal", "god", "temple", "palace",
            "realm", "ancient", "legion", "horizon", "storm", "giant"),
}
# Genre keywords in film_facts / the film's own metadata pick the lever.
_GENRE = {
    "FEAR": ("horror", "supernatural", "ghost", "haunt", "slasher",
             "monster", "creepy", "dread"),
    "DESIRE": ("romance", "romantic", "erotic", "love", "melodrama",
               "dating", "passion"),
    "THRILL": ("thriller", "action", "crime", "heist", "racing", "car",
               "chase", "spy", "war", "martial", "revenge"),
    "AWE": ("fantasy", "xianxia", "wuxia", "epic", "adventure", "myth",
            "cultivation", "sword", "sorcery", "sci-fi", "science fiction",
            "space"),
}
# HOOK-IMAGE: concrete objects an Epstein-style one-line hook can be
# built around ("There's a bomb on a crowded city bus...").
_OBJECTS = ("bomb", "bus", "car", "truck", "train", "plane", "house",
            "knife", "gun", "letter", "phone", "photo", "ring", "door",
            "key", "coffin", "grave", "cage", "chain", "fire", "bridge",
            "wedding", "money", "diamond", "mask", "body")

_ANCHOR_NUM = re.compile(r"\b\d[\d,.]*\b")
_WORD = re.compile(r"[a-z']+")

# The anti-picks: a candidate that is one of these is not an opener no
# matter its score (credits, pure worldbuilding, or needs names).
_ANTI = ("logo", "credits", "title card", "studio", "distribution",
         "distributor", "black screen")


def _words(text: str) -> list:
    return _WORD.findall(str(text or "").lower())


def _ts(sec: float) -> float:
    try:
        return float(sec)
    except (TypeError, ValueError):
        return 0.0


def _land_sec(land) -> float:
    """'01:07:29' -> seconds. Reveal landings are HH:MM:SS strings."""
    if isinstance(land, (int, float)):
        return float(land)
    parts = str(land or "").split(":")
    try:
        return sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts)))
    except ValueError:
        return -1.0


# --------------------------------------------------------------------------
# R4 - the lever
# --------------------------------------------------------------------------

def lever_for(facts: dict) -> str:
    """Pick the genre lever from film_facts metadata. Ties break toward
    THRILL (the recap median; FEAR/DESIRE/AWE need clearer signals)."""
    blob = " ".join(str(facts.get(k, "")) for k in
                    ("genre", "keywords", "title", "plot", "tagline")).lower()
    best, hits = "THRILL", 0
    for lever, keys in _GENRE.items():
        n = sum(blob.count(k) for k in keys)
        if n > hits:
            best, hits = lever, n
    return best


# --------------------------------------------------------------------------
# R1 - the score
# --------------------------------------------------------------------------

def _present(markers, words: set, prose: str) -> list:
    """Markers present as whole words (single words via the token set,
    phrases via boundary regex on the prose)."""
    out = []
    for m in markers:
        if " " in m:
            if re.search(r"(?<![a-z'])" + re.escape(m) + r"(?![a-z'])",
                         prose):
                out.append(m)
        elif m in words:
            out.append(m)
    return out


def score(cand: dict, *, lever: str, lands: list,
          runtime_sec: float) -> dict:
    """One candidate -> {"id", "score", "why": [str]}.

    `cand` = {"id", "start", "end", "depicts": [str], "action": str,
              "chars": [str], "censor": str} - produced by read().
    `lands` = reveal landing seconds (NON-RESOLUTION input).
    """
    prose = str(cand.get("action") or "").lower()
    tags = {str(t).lower() for t in (cand.get("depicts") or [])}
    why: list = []

    # ANTI first: credits / logos / pure establishing are not openers.
    if any(a in prose for a in _ANTI) or tags == {"establishing"}:
        return {"id": cand.get("id"), "score": -100.0,
                "why": ["anti-pick: credits / logo / pure establishing"]}

    # CHARGE - distinct markers, weight by extremity.
    words = set(_words(prose))
    hits = _present(sorted(_CHARGE), words, prose) \
        + [t for t in sorted(tags) if t in _CHARGE_TAGS]
    charge = sum(_CHARGE.get(w, 1) for w in hits)
    if charge:
        why.append(f"charge {charge} ({', '.join(hits[:5])})")

    # NON-RESOLUTION - overlapping a reveal landing is disqualifying,
    # not a dock: the opener spoils nothing.
    c0, c1 = _ts(cand.get("start")), _ts(cand.get("end"))
    near = [l for l in lands if c0 - REVEAL_GUARD_SEC < l < c1 + REVEAL_GUARD_SEC]
    if near:
        return {"id": cand.get("id"), "score": -100.0,
                "why": [f"anti-pick: sits on a reveal landing "
                        f"(t={min(near):.0f}s)"]}

    # GENRE-CANON - the film's own lever visible in the candidate.
    canon = _present(_CANON.get(lever, ()), words, prose)
    canon_pts = 2 * len(canon)
    if canon:
        why.append(f"{lever.lower()}-canon +{canon_pts} "
                   f"({', '.join(canon[:4])})")

    # HOOK-IMAGE - a concrete object the hook line can point at.
    obj = _present(_OBJECTS, words, prose)
    img_pts = 2 if obj else 0
    if obj:
        why.append(f"hook-image ({', '.join(obj[:3])})")

    # Cast present: an opener with a face the story follows beats an
    # empty one, but two-plus names is a listings entry (R3: max one
    # proper name in the opener) - cap the bonus at one lead.
    chars = cand.get("chars") or []
    face_pts = 1 if 1 <= len(chars) <= 2 else 0
    if face_pts:
        why.append("lead present")

    # LOOP-BACK has two shapes and both are positional: early beats the
    # chronological body returns to naturally; a late beat forces the
    # OPEN-B fragment. Mid-band beats earn nothing here - opening on the
    # middle of a film is neither.
    pos = c0 / runtime_sec if runtime_sec else 0.0
    if pos <= OPEN_ZONE:
        loop_pts, shape = 4, "zone-A"
    elif pos >= MIDPOINT:
        loop_pts, shape = 4, "loop-back-B"
    else:
        loop_pts, shape = 0, "mid-band"
    if loop_pts:
        why.append(f"{shape} +{loop_pts}")

    return {"id": cand.get("id"), "score": float(charge + canon_pts
                                                 + img_pts + face_pts
                                                 + loop_pts),
            "why": why, "pos": round(pos, 3), "censor": cand.get("censor")}


# --------------------------------------------------------------------------
# R2 - the choice
# --------------------------------------------------------------------------

def choose(candidates: list, *, lever: str, lands: list,
           runtime_sec: float) -> dict:
    """Candidates -> {"opener", "open_mode", "lever", "ranked": [...]}.

    OPEN-A: the best candidate inside the opening zone (the film's own
    first scene, told chronologically - even a calm one; R2's
    disruption is narrated, not chosen). OPEN-B: only when the best
    candidate overall lies beyond the midpoint, as a loop-back fragment
    the body must earn its way back to.
    """
    ranked = sorted((score(c, lever=lever, lands=lands,
                           runtime_sec=runtime_sec)
                     for c in candidates),
                    key=lambda r: -r["score"])
    zone = [r for r in ranked
            if r["score"] > 0 and 0.0 <= (r.get("pos") or 1.0) <= OPEN_ZONE]
    best = ranked[0] if ranked else None

    if best and best["score"] > 0 and (best.get("pos") or 0.0) >= MIDPOINT:
        opener, mode = best, "B"
    elif zone:
        opener, mode = zone[0], "A"
    elif best and best["score"] > 0:
        # Charged beat in the mid band: OPEN-A on the best zone-less
        # early candidate beats manufacturing a shock-first open.
        opener, mode = best, "A"
    else:
        opener, mode = None, "A"

    return {"opener": opener, "open_mode": mode, "lever": lever,
            "ranked": ranked[:10]}


# --------------------------------------------------------------------------
# the loader (the only disk-touching part)
# --------------------------------------------------------------------------

def _shot_cands(shots: list) -> list:
    from pipeline.draft import parse_ts
    out = []
    for s in shots:
        if not s.get("action"):
            continue
        out.append({"id": s.get("id"),
                    "start": parse_ts(s.get("clip_start", "0:0:0")),
                    "end": parse_ts(s.get("clip_end", "0:0:0")),
                    "depicts": s.get("depicts") or [],
                    "action": s.get("action"),
                    "chars": s.get("chars") or [],
                    "censor": s.get("censor")})
    return out


def read(project: str) -> dict:
    """shots.json + reveals.json + film_facts.json -> the chooser input.
    Works on both pipeline generations: plan-slot projects and the older
    draft-only ones (the catalogue is the candidate list in both)."""
    pdir = Path(config.project_dir(project))
    shots = json.loads((pdir / "shots.json").read_text(encoding="utf-8-sig"))
    shots = shots if isinstance(shots, list) else shots.get("shots", [])
    cands = _shot_cands(shots)

    lands = []
    rp = pdir / "reveals.json"
    if rp.exists():
        rv = json.loads(rp.read_text(encoding="utf-8-sig"))
        for r in (rv.get("reveals") if isinstance(rv, dict) else rv) or []:
            s = _land_sec(r.get("land"))
            if s >= 0:
                lands.append(s)

    facts = {}
    fp = pdir / "film_facts.json"
    if fp.exists():
        facts = json.loads(fp.read_text(encoding="utf-8-sig"))

    runtime = max((c["end"] for c in cands), default=0.0)
    return {"candidates": cands, "lands": lands, "facts": facts,
            "runtime_sec": runtime}
