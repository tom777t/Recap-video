

"""
catalogue.py — Mức 3 capacity-aware shot catalogue helpers.

A "capacity-aware" catalogue carries, for every shot, how much narration it can
support BEFORE authoring even begins:

  raw_duration_sec        = clip_end - clip_start (the real footage window)
  max_play_duration_sec   = raw * stretch_tolerance (extendable) or raw (not)
  max_narration_words_en  = max English words that fit within the Mức 1 cap
  extendable              = may the footage be slowed/held? (static yes, motion no)
  stretch_tolerance       = how far an extendable shot may be slowed (default 1.1)

These let a draft writer (human or LLM) size each line to its shot up front,
instead of discovering an overrun at render time.

Backward compatible: shots without these fields get them COMPUTED on demand
(enrich_shots / capacity_map). Nothing on disk has to change for old projects.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import config
from pipeline import calibration as _cal


def parse_ts(ts: str) -> float:
    parts = [float(p) for p in str(ts).split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts[-3], parts[-2], parts[-1]
    return h * 3600 + m * 60 + s


def _raw_window(shot: dict) -> Optional[float]:
    """Footage length from clip_start/clip_end (shots.json shape) or
    time_start/time_end (broll shape). None if not a timed shot."""
    if shot.get("clip_start") and shot.get("clip_end"):
        try:
            return parse_ts(shot["clip_end"]) - parse_ts(shot["clip_start"])
        except Exception:
            return None
    if shot.get("time_start") is not None and shot.get("time_end") is not None:
        try:
            return float(shot["time_end"]) - float(shot["time_start"])
        except Exception:
            return None
    return None


def _is_extendable_default(depicts: list) -> bool:
    static_kinds = {"establishing", "setup", "aftermath", "emotion", "transition"}
    motion_kinds = {"action", "dialogue", "reveal", "discovery", "reaction", "montage"}
    dep = set(depicts or [])
    if dep & motion_kinds:
        return False
    if dep & static_kinds:
        return True
    return False


def compute_fields(shot: dict, profile=None, force: bool = False) -> dict:
    """Return the Mức 3 fields for a single raw shot dict. Existing values are
    preserved unless force=True. Returns a dict of the 5 fields (or {} if the
    shot is not a timed shot / is a silence shot)."""
    if shot.get("narration_silence_seconds"):
        return {}
    raw = _raw_window(shot)
    if raw is None or raw <= 0:
        return {}
    profile = profile or _cal.get_profile(
        getattr(config, "DEFAULT_TTS_VOICE", None),
        getattr(config, "DEFAULT_TTS_RATE", "+22%"))

    tol = float(shot.get("stretch_tolerance", 1.1))
    extendable = shot.get("extendable")
    if extendable is None or force:
        extendable = _is_extendable_default(shot.get("depicts", []))
    eff_tol = tol if extendable else 1.0

    raw_d = round(raw, 3)
    max_play = shot.get("max_play_duration_sec")
    if max_play is None or force:
        max_play = round(raw_d * eff_tol, 3)
    max_words = shot.get("max_narration_words_en")
    if max_words is None or force:
        slowdown = float(getattr(config, "BINDING_SLOWDOWN_MAX", 1.4)) \
            if hasattr(config, "BINDING_SLOWDOWN_MAX") else 1.4
        # use schema's constant if present
        try:
            from pipeline.schemas import BINDING_SLOWDOWN_MAX as _SD
            slowdown = _SD
        except Exception:
            pass
        max_words = profile.max_words_for_capacity(raw_d * slowdown)

    return {
        "raw_duration_sec": raw_d,
        "max_play_duration_sec": max_play,
        "max_narration_words_en": int(max_words),
        "extendable": bool(extendable),
        "stretch_tolerance": tol,
    }


def enrich_shots(project: str, force: bool = False, write: bool = True) -> dict:
    """Populate Mức 3 fields on every timed shot in a project's shots.json.
    Returns {n_shots, n_enriched}. Idempotent (skips shots already populated
    unless force=True). Silence shots are left untouched."""
    pdir = config.project_dir(project)
    sp = pdir / "shots.json"
    if not sp.exists():
        return {"n_shots": 0, "n_enriched": 0}
    data = json.loads(sp.read_text(encoding="utf-8-sig"))
    shots = data.get("shots", [])
    profile = _cal.get_profile(
        getattr(config, "DEFAULT_TTS_VOICE", None),
        getattr(config, "DEFAULT_TTS_RATE", "+22%"))
    n_enriched = 0
    for s in shots:
        fields = compute_fields(s, profile, force=force)
        if not fields:
            continue
        before = {k: s.get(k) for k in fields}
        s.update(fields)
        if before != fields:
            n_enriched += 1
    if write and n_enriched:
        sp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"n_shots": len(shots), "n_enriched": n_enriched}


def capacity_map(project: str) -> dict:
    """Return {clip_start: max_narration_words_en} for every timed shot, computing
    defaults on the fly (does NOT modify disk). Used by the draft validator to
    surface per-shot word ceilings even for un-enriched (old) catalogues."""
    pdir = config.project_dir(project)
    sp = pdir / "shots.json"
    if not sp.exists():
        return {}
    data = json.loads(sp.read_text(encoding="utf-8-sig"))
    profile = _cal.get_profile(
        getattr(config, "DEFAULT_TTS_VOICE", None),
        getattr(config, "DEFAULT_TTS_RATE", "+22%"))
    out = {}
    for s in data.get("shots", []):
        f = compute_fields(s, profile)
        if f and s.get("clip_start"):
            out[s["clip_start"]] = f["max_narration_words_en"]
    return out


# =========================================================================== #
# Stage 2 depth-target enhancement (2026-06-22)
#
# Goal: catch UNDER-CATALOGUE at Stage 2 (before authoring), so the catalogue
# aims for the film's natural shot capacity from the start instead of being
# grown reactively (Parasite went 48 -> 61 -> 87 -> 110, all frame-verified -
# proof the capacity was always there; only the initial target was too low).
#
# Everything here is READ-ONLY analysis. It never edits shots.json or the
# proposal. The audit emits soft warnings by default; --strict makes a
# missed per-beat floor a hard failure for projects that want to enforce it.
# =========================================================================== #

import re as _re


def infer_tier_from_runtime(target_line: str) -> Optional[str]:
    """Infer a depth tier from a proposal 'Target: 11-13 min ...' line by taking
    the midpoint of the runtime range against config.DEPTH_TIER_RUNTIME_CEIL."""
    # Only trust an explicit minute figure. A range like '11-13 min' yields
    # [11, 13]; a single '18+ min' yields [18]. Do NOT grab bare numbers like
    # '36 beats' - that is not a runtime.
    rng = _re.search(r"(\d+)\s*(?:-|to|–)\s*(\d+)\s*min", target_line)
    if rng:
        nums = [int(rng.group(1)), int(rng.group(2))]
    else:
        nums = [int(n) for n in _re.findall(r"(\d+)\s*\+?\s*min", target_line)]
    if not nums:
        return None
    mid = sum(nums) / len(nums)
    ceil = getattr(config, "DEPTH_TIER_RUNTIME_CEIL",
                   [(13, "recap"), (17, "fuller_recap"), (9999, "video_essay")])
    for hi, tier in ceil:
        if mid <= hi:
            return tier
    return ceil[-1][1]


def parse_beats(project: str) -> dict:
    """Parse a project's beats_proposal.md into structured data.

    Handles BOTH proposal formats seen in the repo:
      Parasite: 'B01  ~0:01  description ... chars: X, Y [S6]'
      Joker:    'B01 | 00:00:08 | description | chars | depicts [S6]'

    Returns:
      {
        "tier": "video_essay" | None,            # explicit depth_target: header
        "tier_inferred": "recap" | None,         # inferred from Target: line
        "target_runtime": "11-13 min" | None,
        "beats": [ {id, ts, text, chars:[...], tags:set(), is_s6, is_s9,
                    motifs_hint:[...]} , ... ],
        "declared_motifs": [...],                 # KEY: / motif lines if any
      }
    Never raises on a malformed proposal; returns what it can parse.
    """
    pdir = config.project_dir(project)
    bp = pdir / "beats_proposal.md"
    out = {"tier": None, "tier_inferred": None, "target_runtime": None,
           "beats": [], "declared_motifs": [], "style": "review",
           "ts_format": None}
    if not bp.exists():
        return out
    text = bp.read_text(encoding="utf-8-sig")

    # --- header fields ----------------------------------------------------- #
    # style: which narration style guide this project follows. "linear" ->
    # prompts/style_linear_vn.md (chronological walk-through); anything else or
    # absent -> "review" (prompts/recap_style.md), so existing projects are
    # unchanged. Only the SCRIPT STRUCTURE differs; the engine is shared.
    ms = _re.search(r"^\s*style\s*:\s*([a-z_]+)", text, _re.IGNORECASE | _re.MULTILINE)
    if ms:
        cand = ms.group(1).strip().lower()
        out["style"] = "linear" if cand in ("linear", "linear_vn") else "review"

    # ts_format: how to read a 2-part beat timestamp 'A:B' ("HH:MM" or "MM:SS").
    # Absent -> draft.beat_times falls back to HH:MM, the convention of every
    # linear proposal written so far. Declaring it removes the guess entirely.
    mf = _re.search(r"^\s*ts_format\s*:\s*([A-Za-z:]+)", text,
                    _re.IGNORECASE | _re.MULTILINE)
    if mf:
        cand = mf.group(1).strip().upper()
        if cand in ("HH:MM", "MM:SS"):
            out["ts_format"] = cand

    m = _re.search(r"^\s*depth_target\s*:\s*([a-z_]+)", text, _re.IGNORECASE | _re.MULTILINE)
    if m:
        cand = m.group(1).strip().lower()
        if cand in getattr(config, "DEPTH_TIERS", {}):
            out["tier"] = cand
    mt = _re.search(r"^\s*Target\s*:\s*(.+)$", text, _re.IGNORECASE | _re.MULTILINE)
    if mt:
        out["target_runtime"] = mt.group(1).strip()
        out["tier_inferred"] = infer_tier_from_runtime(mt.group(1))

    # --- beat blocks ------------------------------------------------------- #
    # A genuine beat ENTRY line is one of:
    #   'B01  ~0:01  ...'          (whitespace format: ID then a timestamp)
    #   'B01 | 00:00:08 | ...'     (pipe format: ID then '|')
    # Lines that merely start with a beat reference in prose (e.g.
    # 'B22 is the explicit reveal ...') are NOT entries - they lack the
    # timestamp/pipe right after the ID, so the stricter pattern skips them.
    #
    # A beat's BLOCK is its entry line plus every following line up to (but not
    # including) the next beat entry or a section divider ('====' / '----').
    # We scan chars/tags across the WHOLE block so proposals that wrap the
    # description or carry a 'chars:' / sub-moment block on continuation lines
    # (the fuller_recap enumeration format) still parse correctly.
    entry_re = _re.compile(r"^\s*(B_?\w+?)\s*(?:\|\s*|[~]?\d{1,2}:\d{2})")
    lines = text.splitlines()
    seen_ids = set()
    # find the entry-line indices first
    entries = []
    for i, raw in enumerate(lines):
        m = entry_re.match(raw.rstrip())
        if not m:
            continue
        bid_raw = m.group(1)
        cid = _norm_beat_id(bid_raw)
        bid = cid if cid else bid_raw
        if bid in seen_ids:
            continue
        seen_ids.add(bid)
        entries.append((i, bid, bid_raw, m))

    for idx, (i, bid, bid_raw, m) in enumerate(entries):
        entry_line = lines[i].rstrip()
        rest = entry_line[m.start(1) + len(bid_raw):]
        # gather the block: entry line + continuation lines until next entry /
        # section divider.
        end = entries[idx + 1][0] if idx + 1 < len(entries) else len(lines)
        block_lines = [rest]
        for j in range(i + 1, end):
            lj = lines[j].rstrip()
            if _re.match(r"^\s*(={3,}|-{3,})", lj):
                break
            block_lines.append(lj)
        block = "\n".join(block_lines)

        tags = set(_re.findall(r"\[([A-Z0-9/\-]+)\]", block))  # [S6] [S7] [TWIST-HOLD]
        # Also detect Sn markers inside descriptive brackets like
        # '[S9 - iconic]', '[S6 launch]', '[S7/S8 blood]' - proposals often
        # annotate the tag, not just bare-token it. Pull any S-code seen in a
        # bracket into the tag set so is_s6/is_s9 fire.
        for stag in _re.findall(r"\[[^\]]*?(S\d(?:/S\d)?)[^\]]*?\]", block):
            for part in stag.split("/"):
                tags.add(part)
        # chars: explicit "chars: a, b" (entry line preferred, else anywhere in
        # block) wins; else pull from pipe-format column on the entry line.
        chars = []
        cm = _re.search(r"chars?\s*:\s*([^\[\n]+)", block, _re.IGNORECASE)
        if cm:
            chars = [c.strip() for c in _re.split(r"[,;]", cm.group(1)) if c.strip()]
        elif "|" in rest:
            cols = [c.strip() for c in rest.split("|")]
            if len(cols) >= 4:
                chars = [c.strip() for c in _re.split(r"[,/]", cols[3]) if c.strip()]
        # drop parenthetical / none markers + sub-moment keys from chars
        _skip = ("none", "establishing", "tv", "crowd", "tv/crowd", "",
                 "main_action", "reactions", "motifs", "setting")
        chars = [c for c in chars
                 if c.lower().strip("()") not in _skip and not c.startswith("(")]
        # timestamp hint (first HH:MM or ~M:SS token on the entry line)
        tsm = _re.search(r"(\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)", rest)
        ts = tsm.group(1) if tsm else None
        s6 = bool(tags & {"S6"})
        s9 = bool(tags & {"S9"})
        out["beats"].append({
            "id": bid, "ts": ts, "text": rest.strip(),
            "chars": chars, "tags": tags, "is_s6": s6, "is_s9": s9,
        })

    # --- declared motifs -------------------------------------------------- #
    # DEPTH-MOTIF checks the film's CANONICAL motif set, declared ONCE in a
    # dedicated 'MOTIF TRACKING:' line, e.g.
    #   MOTIF TRACKING (...): DUST, GRAVITY, the WATCH, the CORNFIELD, LOVE...
    # We deliberately do NOT harvest the per-beat 'motifs:' enumeration lines -
    # those are authoring notes (often parenthetical phrases) and would produce
    # dozens of false 'not catalogued' warnings. We extract short motif KEYWORDS
    # (prefer the ALL-CAPS token in each item) so matching is keyword-based, not
    # whole-phrase.
    mtrack = _re.search(r"^\s*MOTIF[ _]?TRACKING[^:]*:\s*(.+)$",
                        text, _re.IGNORECASE | _re.MULTILINE)
    if mtrack:
        for item in _re.split(r"[,;]", mtrack.group(1)):
            item = item.strip()
            if not item:
                continue
            # prefer an ALL-CAPS keyword (DUST, GRAVITY, WATCH); else the first
            # significant word, stripped of articles.
            caps = _re.findall(r"\b([A-Z]{3,})\b", item)
            if caps:
                out["declared_motifs"].append(caps[0])
            else:
                w = _re.sub(r"^(the|a|an)\s+", "", item, flags=_re.IGNORECASE)
                w = _re.split(r"[\s(]", w.strip())[0]
                if len(w) >= 3:
                    out["declared_motifs"].append(w)
    return out


def _norm_beat_id(val) -> Optional[str]:
    """Normalize any beat reference to canonical 'B<NN>' form. Accepts an int
    (1 -> 'B01'), a bare number string ('1' -> 'B01'), 'B1'/'b01' -> 'B01',
    or a non-numbered id like 'B_outro' (returned upper-cased as-is). Returns
    None if it cannot be interpreted."""
    if val is None:
        return None
    if isinstance(val, int):
        return f"B{val:02d}"
    s = str(val).strip()
    if not s:
        return None
    m = _re.match(r"^[Bb]?_?(\d+)$", s)
    if m:
        return f"B{int(m.group(1)):02d}"
    # non-numbered (B_outro etc.)
    return s if s.upper().startswith("B") else None


def _shots_by_beat(shots: list, beats: list) -> tuple:
    """Map canonical beat_id -> [shots]. Uses an explicit shot['beat'] field
    (normalized; accepts int or string) when present; otherwise infers by
    nearest-preceding beat timestamp (fallback for old catalogues with no beat
    field). Returns (by_beat, unassigned)."""
    by_beat = {b["id"]: [] for b in beats}
    # build a timeline of (seconds, beat_id) for inference fallback
    timeline = []
    for b in beats:
        if b["ts"]:
            try:
                timeline.append((parse_ts(b["ts"]), b["id"]))
            except Exception:
                pass
    timeline.sort()

    def infer(shot):
        cs = shot.get("clip_start")
        if not cs or not timeline:
            return None
        try:
            t = parse_ts(cs)
        except Exception:
            return None
        chosen = timeline[0][1]
        for sec, bid in timeline:
            if sec <= t:
                chosen = bid
            else:
                break
        return chosen

    unassigned = []
    for s in shots:
        if s.get("narration_silence_seconds") and not s.get("clip_start"):
            continue
        bid = _norm_beat_id(s.get("beat"))
        if bid is None:
            bid = infer(s)
        if bid in by_beat:
            by_beat[bid].append(s)
        elif bid is not None:
            by_beat.setdefault(bid, []).append(s)
        else:
            unassigned.append(s)
    return by_beat, unassigned


def coverage_report(project: str, strict: bool = False) -> dict:
    """Stage 2 depth audit. Reads beats_proposal.md + shots.json (no writes).

    Returns a dict with the metric block and a list of warnings. Each warning is
    {code, msg}. Severity: all soft unless strict=True, in which case any
    DEPTH-UNDER (per-beat floor miss) is escalated to 'hard'.
    """
    pdir = config.project_dir(project)
    sp = pdir / "shots.json"
    beatinfo = parse_beats(project)
    beats = [b for b in beatinfo["beats"] if _re.match(r"^B\d+$", b["id"])]  # numbered only
    tier = beatinfo["tier"] or beatinfo["tier_inferred"]
    tiers = getattr(config, "DEPTH_TIERS", {})
    tcfg = tiers.get(tier, {})
    shot_lo, shot_hi = tcfg.get("shots", (0, 0))
    pb_lo, pb_hi = tcfg.get("per_beat", (2, 4))
    min_pb = getattr(config, "DEPTH_MIN_SHOTS_PER_BEAT", 2)

    shots = []
    if sp.exists():
        data = json.loads(sp.read_text(encoding="utf-8-sig"))
        shots = data.get("shots", [])
    timed = [s for s in shots if not (s.get("narration_silence_seconds") and not s.get("clip_start"))]

    by_beat, unassigned = _shots_by_beat(shots, beatinfo["beats"])

    warnings = []
    severity = "clean"

    def warn(code, msg, hard=False):
        nonlocal severity
        warnings.append({"code": code, "msg": msg, "hard": hard})
        if hard:
            severity = "hard"
        elif severity != "hard":
            severity = "soft"

    # --- per-beat floor + climax/action + reaction gaps -------------------- #
    for b in beats:
        n = len(by_beat.get(b["id"], []))
        if n < min_pb:
            warn("DEPTH-UNDER",
                 f"Beat {b['id']} has {n} shot(s), expected {pb_lo}-{pb_hi} "
                 f"(tier '{tier}'). {b['text'][:60]}",
                 hard=strict)
        if b["is_s6"] and n < 3:
            warn("DEPTH-CLIMAX",
                 f"Beat {b['id']} is [S6] action/climax but has only {n} shot(s); "
                 f"action sequences need rapid coverage (>=3-4 distinct moments).")
        # reaction-shot heuristic: a beat naming >=2 chars and tagged action but
        # whose shots carry no 'reaction' depicts is missing the reaction beat.
        if n >= 1 and len(b["chars"]) >= 2:
            deps = set()
            for s in by_beat.get(b["id"], []):
                deps |= set(s.get("depicts", []))
            if "action" in deps and "reaction" not in deps and "emotion" not in deps:
                warn("DEPTH-REACTION",
                     f"Beat {b['id']} has action coverage but no reaction/emotion "
                     f"shot catalogued ({len(b['chars'])} chars present).")

    # --- declared-but-uncatalogued motifs --------------------------------- #
    if beatinfo["declared_motifs"]:
        all_actions = " ".join(str(s.get("action", "")).lower() for s in timed)
        for motif in beatinfo["declared_motifs"]:
            if motif.lower() not in all_actions:
                warn("DEPTH-MOTIF",
                     f"Motif '{motif}' declared in proposal but not found in any "
                     f"catalogued shot's action text.")

    # --- total vs tier target --------------------------------------------- #
    total = len(timed)
    if shot_hi and total < shot_lo:
        warn("DEPTH-TOTAL",
             f"{total} shots vs target {shot_lo}-{shot_hi} (tier '{tier}') - "
             f"{shot_lo - total} under target.")

    # --- est word ceiling vs runtime -------------------------------------- #
    ceil_words = 0
    profile = _cal.get_profile(
        getattr(config, "DEFAULT_TTS_VOICE", None),
        getattr(config, "DEFAULT_TTS_RATE", "+22%"))
    for s in timed:
        f = compute_fields(s, profile)
        ceil_words += f.get("max_narration_words_en", 0) if f else 0

    n_beats = len(beats)
    avg_pb = round(total / n_beats, 1) if n_beats else 0.0
    under2 = sum(1 for b in beats if len(by_beat.get(b["id"], [])) < min_pb)

    return {
        "tier": tier,
        "tier_explicit": beatinfo["tier"] is not None,
        "target_runtime": beatinfo["target_runtime"],
        "shot_target": (shot_lo, shot_hi),
        "per_beat_target": (pb_lo, pb_hi),
        "total_shots": total,
        "n_beats": n_beats,
        "avg_shots_per_beat": avg_pb,
        "beats_under_floor": under2,
        "unassigned_shots": len(unassigned),
        "est_word_ceiling": ceil_words,
        "warnings": warnings,
        "severity": severity,
    }


def print_coverage_report(project: str, strict: bool = False) -> int:
    """Human-readable Stage 2 coverage report. Returns an exit code:
    0 clean, 2 soft warnings, 1 hard (only possible with strict=True)."""
    r = coverage_report(project, strict=strict)
    lo, hi = r["shot_target"]
    plo, phi = r["per_beat_target"]
    tier = r["tier"] or "unknown"
    in_band = (lo <= r["total_shots"] <= hi) if hi else False
    band_note = "within target" if in_band else (
        "UNDER target" if (hi and r["total_shots"] < lo) else
        "over target" if (hi and r["total_shots"] > hi) else "no tier")

    print("=== STAGE 2 COVERAGE REPORT ===")
    src = "declared" if r["tier_explicit"] else "inferred from runtime"
    print(f"  Tier:                {tier} ({src})  target {lo}-{hi} shots, "
          f"{plo}-{phi} shots/beat")
    if r["target_runtime"]:
        print(f"  Target runtime:      {r['target_runtime']}")
    print(f"  Total shots:         {r['total_shots']}   [{band_note}]")
    print(f"  Beats (numbered):    {r['n_beats']}  | avg {r['avg_shots_per_beat']} shots/beat")
    print(f"  Beats with <{getattr(config,'DEPTH_MIN_SHOTS_PER_BEAT',2)} shots:  {r['beats_under_floor']}")
    if r["unassigned_shots"]:
        print(f"  Unassigned shots:    {r['unassigned_shots']} (no beat field / not inferable)")
    print(f"  Est. word ceiling:   {r['est_word_ceiling']}w")

    if r["warnings"]:
        print(f"\n  {len(r['warnings'])} depth warning(s):")
        for w in r["warnings"]:
            mark = "HARD" if w["hard"] else "soft"
            print(f"    [{w['code']}/{mark}] {w['msg']}")
    else:
        print("\n  Depth gates clean - catalogue meets the tier's coverage floors.")

    sev = r["severity"]
    if sev == "hard":
        print("\n  Depth audit: HARD failures (strict mode). Catalogue more shots "
              "for the flagged beats before authoring. (exit 1)")
        return 1
    if sev == "soft":
        print("\n  Depth audit: soft warnings. Review each - add coverage where a "
              "real sub-moment is missing; ignore where 1 shot is genuinely right. "
              "(exit 2)")
        return 2
    return 0


if __name__ == "__main__":
    import argparse
    import sys as _sys
    ap = argparse.ArgumentParser(description="Mức 3 catalogue enrichment + Stage 2 depth audit")
    ap.add_argument("--project", required=True)
    ap.add_argument("--force", action="store_true", help="recompute existing fields")
    ap.add_argument("--dry-run", action="store_true", help="don't write")
    ap.add_argument("--coverage", action="store_true",
                    help="run the Stage 2 depth-target coverage report (read-only)")
    ap.add_argument("--strict", action="store_true",
                    help="with --coverage: a per-beat floor miss (DEPTH-UNDER) is a hard fail")
    args = ap.parse_args()
    if args.coverage:
        _sys.exit(print_coverage_report(args.project, strict=args.strict))
    r = enrich_shots(args.project, force=args.force, write=not args.dry_run)
    print(f"shots: {r['n_shots']}  enriched: {r['n_enriched']}")



