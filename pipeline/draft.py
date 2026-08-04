"""
The semi-auto checkpoint.

`prepare_scripting`  -> writes transcript_for_script.txt (a clean, timestamped
                        transcript) so you can hand it to OpenCode to write the
                        recap narration into draft.json.

`validate_draft`     -> reads your (hand-or-LLM-edited) draft.json, checks every
                        field, and writes the readable script.txt. The render
                        step refuses to run until this passes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from rich.console import Console

import config

console = Console()


def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def prepare_scripting(project: str) -> Path:
    """Write a clean timestamped transcript for the scripting step."""
    pdir = config.project_dir(project)
    tj = pdir / "transcript.json"
    if not tj.exists():
        console.print(f"[red]No transcript.json. Run ingest first.[/]")
        sys.exit(1)

    data = json.loads(tj.read_text(encoding="utf-8-sig"))
    lines = [
        f"# Transcript for scripting — project: {project}",
        f"# duration: {data.get('duration', 0)/60:.1f} min   language: {data.get('language')}",
        f"# Hand this whole file to OpenCode and ask it to write the recap script.",
        "",
    ]
    for seg in data["segments"]:
        lines.append(f"[{_fmt_ts(seg['start'])} -> {_fmt_ts(seg['end'])}] {seg['text']}")

    out = pdir / "transcript_for_script.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def parse_ts(ts: str) -> float:
    """Accept HH:MM:SS(.mmm) or MM:SS(.mmm) or plain seconds -> float seconds."""
    ts = str(ts).strip()
    if ":" not in ts:
        return float(ts)
    parts = ts.split(":")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts[-3], parts[-2], parts[-1]
    return h * 3600 + m * 60 + s


def validate_draft(project: str, *, write_state: bool = False,
                   promote: bool = False) -> dict:
    """Validate draft.json and (re)write script.txt. Exit non-zero on problems."""
    pdir = config.project_dir(project)
    df = pdir / "draft.json"
    if not df.exists():
        console.print(
            f"[red]No draft.json found in {pdir}[/]\n"
            f"Create it from the transcript first (see the scripting step)."
        )
        sys.exit(1)

    try:
        # utf-8-sig tolerates a BOM (common from Windows editors / PowerShell)
        draft = json.loads(df.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        console.print(f"[red]draft.json is not valid JSON:[/] {e}")
        sys.exit(1)

    if "lines" not in draft or not isinstance(draft["lines"], list) or not draft["lines"]:
        console.print("[red]draft.json must have a non-empty 'lines' array.[/]")
        sys.exit(1)

    # source duration for bounds checking
    tj = pdir / "transcript.json"
    src_dur = 0.0
    if tj.exists():
        src_dur = json.loads(tj.read_text(encoding="utf-8-sig")).get("duration", 0.0)

    # load pool meta (if any) so 'pool' lines validate + reuse can be capped
    pool_meta = {}
    bp = pdir / "broll.json"
    if bp.exists():
        try:
            bd = json.loads(bp.read_text(encoding="utf-8-sig"))
            pool_meta = bd.get("pool", bd)
        except Exception:
            pass
    pool_labels = set(pool_meta.keys())

    errors: list[str] = []
    total_words = 0
    pool_uses: dict = {}              # label -> count
    visual_uses: dict = {}            # explicit 'visual' family -> [line ids]
    explicit_times: list = []         # (line id, source seconds, visual tag)
    for i, ln in enumerate(draft["lines"], 1):
        where = f"line #{ln.get('id', i)}"
        # Gap 3 / S9 silence exception: a silence line (narration_silence_seconds)
        # is a deliberate held visual with NO narration (C1 exception). It is
        # exempt from the empty-narration requirement; every other line must
        # carry narration.
        is_silence = ln.get("narration_silence_seconds") is not None
        if not is_silence and not ln.get("narration", "").strip():
            errors.append(f"{where}: empty 'narration'")
        if ln.get("visual") and not ln.get("pool") and not ln.get("montage"):
            visual_uses.setdefault(ln["visual"], []).append(ln.get("id", i))

        if ln.get("montage"):
            if not isinstance(ln["montage"], list) or len(ln["montage"]) < 2:
                errors.append(f"{where}: 'montage' must list 2+ shots")
            _m2_sum = 0.0          # Mức 2: sum of inline play_durations (if any)
            _m2_has_pd = False
            for lab in ln.get("montage", []):
                # Mức 1: a montage entry may be an INLINE timestamp segment
                # (dict {clip_start, clip_end} or [start, end]) for projects with
                # no broll.json. Validate its timestamps instead of a pool label.
                # Mức 2: a dict entry may carry an optional positive play_duration.
                if isinstance(lab, dict):
                    if not lab.get("clip_start") or not lab.get("clip_end"):
                        errors.append(f"{where}: inline montage segment needs clip_start/clip_end")
                    pd = lab.get("play_duration")
                    if pd is not None:
                        _m2_has_pd = True
                        try:
                            pdf = float(pd)
                            if pdf <= 0:
                                errors.append(f"{where}: montage play_duration must be > 0")
                            else:
                                _m2_sum += pdf
                        except (TypeError, ValueError):
                            errors.append(f"{where}: montage play_duration must be a number")
                elif isinstance(lab, (list, tuple)):
                    if len(lab) != 2:
                        errors.append(f"{where}: inline montage segment must be [start, end]")
                elif lab not in pool_labels:
                    errors.append(f"{where}: montage label '{lab}' unknown")
                else:
                    pool_uses[lab] = pool_uses.get(lab, 0) + 1
            # Mức 2: if total_visual_duration is declared, it must match the sum
            # of the per-shot play_durations (when those are given).
            tvd = ln.get("total_visual_duration")
            if tvd is not None and _m2_has_pd:
                try:
                    if abs(float(tvd) - _m2_sum) > 0.05:
                        errors.append(
                            f"{where}: total_visual_duration {tvd} != sum of "
                            f"play_durations {_m2_sum:.2f}")
                except (TypeError, ValueError):
                    errors.append(f"{where}: total_visual_duration must be a number")
        elif ln.get("pool"):
            # pool-sourced line: label must exist
            if ln["pool"] not in pool_labels:
                errors.append(f"{where}: unknown pool label '{ln['pool']}'")
            else:
                pool_uses[ln["pool"]] = pool_uses.get(ln["pool"], 0) + 1
        else:
            # explicit-timestamp line
            for key in ("clip_start", "clip_end"):
                if key not in ln:
                    errors.append(f"{where}: missing '{key}' (or add a 'pool' label)")
            if "clip_start" in ln and "clip_end" in ln:
                try:
                    a = parse_ts(ln["clip_start"])
                    b = parse_ts(ln["clip_end"])
                except ValueError:
                    errors.append(f"{where}: bad timestamp format")
                    total_words += len(ln.get("narration", "").split())
                    continue
                if b <= a:
                    errors.append(f"{where}: clip_end <= clip_start ({ln['clip_start']} -> {ln['clip_end']})")
                if src_dur and (a > src_dur + 1 or b > src_dur + 1):
                    errors.append(f"{where}: clip beyond source duration ({src_dur:.1f}s)")
                explicit_times.append((ln.get("id", i), a, ln.get("visual")))
        total_words += len(ln.get("narration", "").split())

    # reuse-cap enforcement: per-label (normal/hero) AND per visual family.
    for label, count in pool_uses.items():
        is_hero = bool(pool_meta.get(label, {}).get("hero"))
        cap = config.MAX_REUSE_HERO if is_hero else config.MAX_REUSE
        if count > cap:
            kind = "hero" if is_hero else "normal"
            errors.append(f"shot '{label}' used {count}x exceeds {kind} cap of {cap} "
                          f"(spread these lines to other shots or dialogue)")

    # [VISUAL-REPEAT]: unified family cap across pool 'family' + explicit 'visual'.
    fam_uses: dict = {}
    fam_lines: dict = {}
    for label, count in pool_uses.items():
        fam = pool_meta.get(label, {}).get("family")
        if fam:
            fam_uses[fam] = fam_uses.get(fam, 0) + count
            fam_lines.setdefault(fam, []).append(f"pool:{label}")
    for vfam, ids in visual_uses.items():
        fam_uses[vfam] = fam_uses.get(vfam, 0) + len(ids)
        fam_lines.setdefault(vfam, []).extend(f"line {i}" for i in ids)
    for fam, count in fam_uses.items():
        if count > config.MAX_FAMILY_USES:
            where_list = ", ".join(fam_lines.get(fam, []))
            errors.append(f"[VISUAL-REPEAT] visual family '{fam}' shown {count}x exceeds "
                          f"cap of {config.MAX_FAMILY_USES} ({where_list}) - a viewer feels "
                          f"they just saw this. Re-point extra lines to other footage, or "
                          f"split into distinct stages (setup/reversal/outcome).")

    if errors:
        console.print("[red]draft.json has problems:[/]")
        for e in errors:
            console.print(f"  - {e}")
        sys.exit(1)

    # write readable script.txt
    est_min = total_words / config.TTS_WORDS_PER_MINUTE
    script_lines = [
        f"TITLE: {draft.get('title', '(untitled)')}",
        f"Lines: {len(draft['lines'])}   Words: {total_words}   "
        f"Est. narration: {est_min:.1f} min   Target: {draft.get('target_minutes', '?')} min",
        "=" * 60,
        "",
    ]
    for ln in draft["lines"]:
        if ln.get("pool"):
            src = f"pool {ln['pool']}"
        else:
            src = f"{ln.get('clip_start','?')} -> {ln.get('clip_end','?')}"
        deliv = ln.get("delivery", "normal")
        script_lines.append(f"[{ln['id']:>3}] ({src})  <{deliv}>")
        script_lines.append(f"      {ln['narration']}")
        script_lines.append("")

    (pdir / "script.txt").write_text("\n".join(script_lines), encoding="utf-8")

    # action mix + reuse histogram (visibility before render)
    if pool_uses:
        n_action = sum(pool_uses.values())
        n_total = len(draft["lines"])
        console.print(f"[bold]Action mix:[/] {n_action}/{n_total} pool clips "
                      f"({100*n_action/n_total:.0f}% action, "
                      f"{100*(n_total-n_action)/n_total:.0f}% dialogue)")

    # quality linter (clarity / read-aloud / names / action-setup / visual-memory)
    _lint_script(pdir, draft, src_dur, pool_meta, explicit_times)

    # Phase 1 audits -> returns a metrics dict (or None on swallowed setup failure)
    audit = _run_phase1_audits(project, pdir)
    audit_sev = (audit or {}).get("sev", "clean") if isinstance(audit, dict) else "clean"

    console.print(
        f"[green]draft.json valid.[/]  {len(draft['lines'])} lines, "
        f"{total_words} words, est. {est_min:.1f} min narration."
    )
    console.print(f"Readable script written: {pdir / 'script.txt'}")

    # ---- STAGE MACHINE (Stage 3a/3b), engine-owned, LINEAR only -------------
    # Runs AFTER audits and ONLY when we have real metrics (a dict, not the None
    # returned on a swallowed setup failure) - so a failed audit can never
    # trigger promotion. Promotion is EXPLICIT (--promote) and one-way.
    if isinstance(audit, dict) and audit.get("style") == "linear":
        _stage_machine(project, audit, write_state=write_state, promote=promote)

    # expose the Phase 1 audit severity so the CLI can set an exit code.
    if isinstance(draft, dict):
        draft["_audit_severity"] = audit_sev or "clean"
    return draft


def outline_ready(audit: dict) -> tuple:
    """The honest 'outline done' condition. Returns (ready: bool, reason: str).

    Coverage rule: NOT strict all-beats-bound, but 'no run of >=2 consecutive
    uncovered beats'. A lone uncovered beat between two adjacent lines is a
    coarse-beat (HH:MM) granularity artifact - the neighbouring line covers that
    content. A run of >=2 consecutive uncovered beats is a genuine unnarrated
    stretch of film (the real failure mode: a skipped chunk / under-covered
    close), so that - and only that - blocks the outline.
    """
    bc = audit.get("beat_coverage", {}) or {}
    beats = bc.get("beats", 0)
    max_run = bc.get("max_consecutive_uncovered", 0)
    checks = {
        "beats_present":        beats > 0,
        "no_skipped_chunk":     beats > 0 and max_run < 2,
        "no_binding_mismatch":  audit.get("binding_mismatch", 1) == 0,
        "no_unverified":        audit.get("binding_unverified", 1) == 0,
        "continuity_clean":     audit.get("continuity_issues", 1) == 0,
        "no_binding_violation": audit.get("binding_violations", 1) == 0,
        "not_hard":             audit.get("sev") != "hard",
    }
    ready = all(checks.values())
    if ready:
        lone = len(bc.get("uncovered", []))
        note = (f", {lone} lone beat(s) tolerated (granularity)" if lone else "")
        reason = (f"outline_ready: {bc['covered']}/{beats} beats bound, "
                  f"no >=2-consecutive gap, 0 mismatch / 0 unverified, "
                  f"continuity 0, 0 violations{note}")
    else:
        failed = ", ".join(k for k, v in checks.items() if not v)
        gaps = bc.get("consecutive_gaps", [])
        gap_note = ""
        if gaps:
            gap_note = " | skipped chunks: " + "; ".join(
                "+".join(str(x) for x in g) for g in gaps)
        reason = "not ready: " + failed + gap_note
    return ready, reason


def _stage_machine(project, audit, write_state=False, promote=False):
    from pipeline import state as _state
    if _state.get_stage(project) == "script":
        console.print("[dim][STAGE] already in SCRIPT stage.[/]")
        return
    ready, reason = outline_ready(audit)
    bc = audit.get("beat_coverage", {}) or {}
    metrics = {
        "beats": bc.get("beats", 0), "covered": bc.get("covered", 0),
        "uncovered": bc.get("uncovered", []),
        "binding_mismatch": audit.get("binding_mismatch"),
        "binding_unverified": audit.get("binding_unverified"),
        "continuity_issues": audit.get("continuity_issues"),
        "binding_violations": audit.get("binding_violations"),
    }
    console.print(f"[{'green' if ready else 'yellow'}][STAGE] OUTLINE -> {reason}[/]")

    if not write_state:
        return                       # render re-validates; must never write stage
    if promote:
        if ready:
            _state.promote_to_script(project, reason, metrics)
            console.print("[bold green][STAGE] promoted to SCRIPT. DRAFT-TARGET "
                          "applies from the next draft run.[/]")
        else:
            console.print(f"[red][STAGE] --promote refused: {reason}. "
                          f"Fix the failing checks first.[/]")
    else:
        console.print("[dim][STAGE] run `recap.py draft --promote` to enter "
                      "SCRIPT stage once the checks above are green.[/]")


# --------------------------------------------------------------------------- #
# Quality linter -- 6 unique gates restored after the OneDrive revert:
#   [CLARITY] [READ-ALOUD] [NAME] [ACTION-SETUP] [VISUAL-MEMORY]
#   ([VISUAL-REPEAT] is enforced in the main loop above.)
# [FRESHNESS] is intentionally DROPPED -- continuity_check covers timeline
# position more precisely (avoids double-flagging). Warnings, not blocks.
# --------------------------------------------------------------------------- #
import re as _re

_VAGUE = [
    r"\bit gets personal\b", r"\bthe leader\b", r"\bthe enemy\b",
    r"\bone of them\b", r"\bthe other guy\b", r"\bthis guy\b",
    r"\bthe man\b(?! named)", r"\bthe woman\b(?! named)",
]
_FORMAL = [
    r"\bproceeds to\b", r"\bsubsequently\b", r"\bin order to\b",
    r"\butilize\b", r"\bthereafter\b", r"\bwhom\b", r"\balbeit\b",
    r"\bnevertheless\b", r"\bcommences\b",
]
_ACTION_FAMILIES = {
    "explosion", "forest_fight", "apartment_fight", "gunfight", "bombmaking",
    "chase", "fight", "shootout", "attack", "ambush", "raid", "breach",
    "escape", "battle", "brawl", "jungle_fight", "skydive", "pennywise_attack",
    "pennywise_climax", "losers_fight", "bowers_bully",
}
_SETUP_CUES = [
    r"\bbecause\b", r"\bafter\b", r"\bas a result\b", r"\bin response\b",
    r"\bso (?:he|she|they|now|that)\b", r"\bnow that\b", r"\bonce\b",
    r"\bwhen\b", r"\bfollowing\b", r"\bmeanwhile\b", r"\bhowever\b",
    r"\bunfortunately\b", r"\bin order to\b", r"\btracks?\b", r"\bcorners?\b",
    r"\bwants?\b", r"\bdecides?\b", r"\bhunts?\b", r"\bfinds?\b",
    r"\bdiscovers?\b", r"\bgoes? after\b", r"\bcomes? for\b",
    r"\bthreatens?\b", r"\bdemands?\b", r"\brefuses?\b", r"\bsets? off\b",
    r"\bconfronts?\b", r"\battacks?\b", r"\bso he\b", r"\bso she\b", r"\bso they\b",
]


def _lint_script(pdir, draft, src_dur, pool_meta=None, explicit_times=None):
    pool_meta = pool_meta or {}
    explicit_times = explicit_times or []
    warns: list = []

    # --- [NAME]: invented-name guard via names.json ----------------------
    names_path = pdir / "names.json"
    known = set()
    if names_path.exists():
        try:
            nd = json.loads(names_path.read_text(encoding="utf-8-sig"))
            known = {n.lower() for n in (nd.get("names", nd) if isinstance(nd, dict) else nd)}
        except Exception:
            known = set()
    _stop = {"this", "today", "the", "and", "but", "so", "a", "i", "he", "she",
             "they", "it", "we", "his", "her", "their", "serabudabu", "god",
             "okay", "yeah", "no", "yes", "maine", "black"}
    proper_seen = {}
    for ln in draft["lines"]:
        text = ln.get("narration", "")
        for m in _re.finditer(r"\b([A-Z][a-z]{2,})\b", text):
            w = m.group(1)
            if w.lower() in _stop:
                continue
            idx = m.start()
            prev = text[:idx].rstrip()
            if prev == "" or prev.endswith((".", "!", "?")):
                continue
            proper_seen.setdefault(w, ln["id"])
    if names_path.exists():
        for w, lid in proper_seen.items():
            if w.lower() not in known:
                warns.append(f"[NAME] line {lid}: '{w}' not in names.json - verify it's "
                             f"real or use a generic role (never invent).")

    # --- [CLARITY]: vague references -------------------------------------
    for ln in draft["lines"]:
        t = ln.get("narration", "").lower()
        for pat in _VAGUE:
            if _re.search(pat, t):
                warns.append(f"[CLARITY] line {ln['id']}: vague reference "
                             f"({pat.strip(chr(92)+'b')}) - name the character.")
                break

    # --- [READ-ALOUD]: long/formal sentences -----------------------------
    for ln in draft["lines"]:
        text = ln.get("narration", "")
        for sent in _re.split(r"(?<=[.!?])\s+", text):
            if len(sent.split()) > 28:
                warns.append(f"[READ-ALOUD] line {ln['id']}: a sentence is "
                             f"{len(sent.split())} words - break it up.")
                break
        for pat in _FORMAL:
            if _re.search(pat, text.lower()):
                warns.append(f"[READ-ALOUD] line {ln['id']}: formal phrasing "
                             f"({pat.strip(chr(92)+'b')}) - say it plainly.")
                break

    # --- [ACTION-SETUP]: action beats need setup in the prior 4 lines ----
    lines = draft["lines"]

    def _families_of(ln):
        labs = ln.get("montage") or ([ln["pool"]] if ln.get("pool") else [])
        # inline montage segments (dict/list) have no pool family - skip them.
        return {pool_meta.get(l, {}).get("family")
                for l in labs if l and isinstance(l, str)}

    def _is_action(ln):
        if _families_of(ln) & _ACTION_FAMILIES:
            return True
        try:
            return float(ln.get("hold", 0) or 0) >= 5.0
        except (TypeError, ValueError):
            return False

    def _has_setup(text):
        low = text.lower()
        for pat in _SETUP_CUES:
            if _re.search(pat, low):
                return True
        for nm in known:
            if nm and len(nm) > 2 and _re.search(rf"\b{_re.escape(nm)}\b", low):
                return True
        return False

    for i, ln in enumerate(lines):
        if not _is_action(ln) or ln.get("setup_ok") or ln.get("delivery") in ("hook", "intro"):
            continue
        window = lines[max(0, i - 4):i]
        if any(_has_setup(p.get("narration", "")) for p in window) or _has_setup(ln.get("narration", "")):
            continue
        fams = sorted(f for f in _families_of(ln) if f) or ["hold>=5s"]
        warns.append(f"[ACTION-SETUP] line {ln['id']}: action beat ({', '.join(fams)}) "
                     f"has no setup in the prior 4 lines - establish who/why/trigger/"
                     f"stakes BEFORE it (Setup -> Action -> Consequence).")

    # --- [VISUAL-MEMORY]: proximity hint on untagged explicit clips ------
    untagged = sorted((t, lid) for (lid, t, vis) in explicit_times if not vis)
    clusters: list = []
    for t, lid in untagged:
        if clusters and t - clusters[-1][-1][0] <= 30.0:
            clusters[-1].append((t, lid))
        else:
            clusters.append([(t, lid)])
    for cl in clusters:
        if len(cl) >= 3:
            ids = ", ".join(str(lid) for _, lid in cl)
            mm = int(cl[0][0] // 60)
            warns.append(f"[VISUAL-MEMORY] lines {ids} all pull footage from ~{mm} min "
                         f"of the film - they may read as the SAME action a viewer "
                         f"remembers. Tag repeats with the same 'visual' family, or "
                         f"confirm they are distinct stages / scenes.")

    if warns:
        console.print(f"[yellow]Quality linter: {len(warns)} item(s) to review[/]")
        for w in warns[:40]:
            console.print(f"  {w}")
    else:
        console.print("[green]Quality linter: clean.[/]")


# --------------------------------------------------------------------------- #
# Phase 1 audits (coverage / binding / continuity) -- additive, non-blocking.
# skeleton.json is RECOMMENDED, not required. Never hard-fails. ASCII output.
# --------------------------------------------------------------------------- #
def _beat_ts_seconds(ts):
    """Parse a beats_proposal.md beat timestamp to seconds.

    Beat maps are written in HH:MM (hours:minutes) shorthand - e.g. '00:01' is
    1 minute in, '02:39' is 2h39m - NOT the MM:SS that draft.parse_ts assumes
    for a 2-part string. Verified consistent (no anomalies) across all linear
    proposals: a 2-part 'A:B' = A hours + B minutes; a 3-part 'A:B:C' = the usual
    HH:MM:SS. LINE clip_starts are real HH:MM:SS and still use parse_ts.
    Returns float seconds, or None if unparseable.
    """
    ts = str(ts).strip()
    if ":" not in ts:
        try:
            return float(ts) * 60.0          # bare number = minutes (coarse)
        except Exception:
            return None
    parts = ts.split(":")
    try:
        nums = [float(p) for p in parts]
    except Exception:
        return None
    if len(parts) == 2:
        return nums[0] * 3600 + nums[1] * 60          # HH:MM
    if len(parts) >= 3:
        return nums[-3] * 3600 + nums[-2] * 60 + nums[-1]   # HH:MM:SS
    return None


def beat_coverage(project, d) -> dict:
    """Skeleton-free beat coverage for LINEAR projects.

    Each beat in beats_proposal.md carries a timestamp ('ts'). A beat is
    'covered' when >=1 draft line's clip_start falls in [this beat ts, next
    beat ts). Returns:
        {"beats": N, "covered": M, "uncovered": [beat_id, ...],
         "counts": {beat_id: n_lines}}
    Gate report AND stage machine both read these numbers (single source).
    Returns {"beats": 0, ...} when no beats have parseable timestamps.
    """
    from pipeline import catalogue as _cat
    binfo = _cat.parse_beats(project)
    beats = binfo.get("beats", [])
    result = {"beats": 0, "covered": 0, "uncovered": [], "counts": {}}
    if not beats:
        return result

    # beat boundaries from their 'ts' strings (HH:MM beat-map shorthand)
    bounds = []
    for b in beats:
        ts = b.get("ts")
        if not ts:
            continue
        secs = _beat_ts_seconds(ts)
        if secs is not None:
            bounds.append((b.get("id"), secs))
    bounds.sort(key=lambda x: x[1])
    if not bounds:
        return result

    # explicit-timestamp line starts (montage/pool lines have no clip_start)
    line_secs = []
    for ln in d.lines:
        cs = getattr(ln, "clip_start", None)
        if not cs:
            continue
        try:
            line_secs.append(parse_ts(cs))
        except Exception:
            continue

    counts = {bid: 0 for bid, _ in bounds}
    for i, (bid, start) in enumerate(bounds):
        end = bounds[i + 1][1] if i + 1 < len(bounds) else float("inf")
        counts[bid] = sum(1 for s in line_secs if start <= s < end)

    covered = sum(1 for c in counts.values() if c > 0)

    # Longest RUN of consecutive uncovered beats (in film time order). A lone
    # uncovered beat between two adjacent lines is a coarse-beat granularity
    # artifact (a neighbouring line covers that content); a run of >=2 is a real
    # unnarrated stretch of film - the actual failure mode. We also record the
    # first such run so the report can name the skipped chunk.
    max_run = 0
    run = 0
    worst_run = []
    cur_run = []
    for bid, _ in bounds:
        if counts[bid] == 0:
            run += 1
            cur_run.append(bid)
            if run > max_run:
                max_run = run
                worst_run = list(cur_run)
        else:
            run = 0
            cur_run = []
    # collect every run of >=2 (all the genuine holes), for reporting
    consecutive_gaps = []
    cur = []
    for bid, _ in bounds:
        if counts[bid] == 0:
            cur.append(bid)
        else:
            if len(cur) >= 2:
                consecutive_gaps.append(list(cur))
            cur = []
    if len(cur) >= 2:
        consecutive_gaps.append(list(cur))

    result.update(
        beats=len(bounds),
        covered=covered,
        uncovered=[bid for bid, c in counts.items() if c == 0],
        counts=counts,
        max_consecutive_uncovered=max_run,
        consecutive_gaps=consecutive_gaps,
    )
    return result


def parse_reveal_map(project) -> list:
    """Parse the machine-readable ```reveal-map``` fenced block from
    beats_proposal.md into structured reveals. Returns [] when the block is
    absent (the gate is then a no-op).

    Block format (one reveal per line inside a ```reveal-map fence):
        R1 | land: B08 | hold: Doc Ock, Doctor Octopus, Otto Octavius
    - land:  a beat id (B08, resolved via parse_beats' HH:MM beat time) OR a raw
             HH:MM:SS timestamp OR 'mid-credits'/'stinger'/'none' (= protect
             always: land time +inf so ANY earlier mention flags).
    - hold:  comma-separated protected terms/aliases (word-boundary matched).
    Returns: [{"id": str, "land_ref": str, "land_sec": float, "holds": [str]}].
    """
    import re as _re
    from pipeline import catalogue as _cat
    pdir = config.project_dir(project)
    bp = pdir / "beats_proposal.md"
    if not bp.exists():
        return []
    text = bp.read_text(encoding="utf-8-sig")
    m = _re.search(r"```reveal-map\s*\n(.*?)```", text, _re.DOTALL | _re.IGNORECASE)
    if not m:
        return []
    block = m.group(1)

    # beat-id -> seconds, from the same beat list beat_coverage uses (HH:MM)
    beat_sec = {}
    for b in _cat.parse_beats(project).get("beats", []):
        ts = b.get("ts")
        if b.get("id") and ts:
            s = _beat_ts_seconds(ts)
            if s is not None:
                beat_sec[str(b["id"]).upper()] = s

    INF = float("inf")
    always = {"mid-credits", "midcredits", "stinger", "none", "credits"}
    reveals = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        rid = parts[0]
        land_ref, holds = None, []
        for seg in parts[1:]:
            low = seg.lower()
            if low.startswith("land:"):
                land_ref = seg.split(":", 1)[1].strip()
            elif low.startswith("hold:"):
                holds = [h.strip() for h in seg.split(":", 1)[1].split(",") if h.strip()]
        if not land_ref or not holds:
            continue
        # resolve landing time
        lr = land_ref.strip()
        if lr.lower() in always:
            land_sec = INF
        elif lr.upper() in beat_sec:
            land_sec = beat_sec[lr.upper()]
        else:
            try:
                land_sec = parse_ts(lr)          # raw HH:MM:SS
            except Exception:
                land_sec = INF                   # unresolvable -> protect always
        reveals.append({"id": rid, "land_ref": land_ref,
                        "land_sec": land_sec, "holds": holds})
    return reveals


def reveal_timing_check(project, d) -> list:
    """REVEAL-TIMING: flag any protected reveal term spoken in narration BEFORE
    its landing time. Returns a list of hits:
        {reveal_id, term, line_id, line_sec, land_ref, land_sec}
    LITERAL word-boundary text scan only - see the printed limit note. No-op
    (returns []) when there is no reveal-map block.
    """
    import re as _re
    reveals = parse_reveal_map(project)
    if not reveals:
        return []
    # precompile a word-boundary, case-insensitive matcher per term
    compiled = []
    for rv in reveals:
        for term in rv["holds"]:
            pat = _re.compile(r"\b" + _re.escape(term) + r"\b", _re.IGNORECASE)
            compiled.append((rv, term, pat))

    hits = []
    for ln in d.lines:
        narr = getattr(ln, "narration", "") or ""
        if not narr.strip():
            continue
        cs = getattr(ln, "clip_start", None)
        if not cs:                       # montage/pool: no film-time -> skip
            continue
        try:
            line_sec = parse_ts(cs)
        except Exception:
            continue
        for rv, term, pat in compiled:
            if line_sec < rv["land_sec"] and pat.search(narr):
                hits.append({
                    "reveal_id": rv["id"], "term": term,
                    "line_id": getattr(ln, "id", "?"), "line_sec": line_sec,
                    "land_ref": rv["land_ref"], "land_sec": rv["land_sec"],
                })
    return hits


def parse_set_pieces(project) -> list:
    """Parse the machine-readable ```set-pieces``` fenced block from
    beats_proposal.md into structured set-pieces. Returns [] when the block is
    absent (the gate is then a no-op).

    Block format (one set-piece per line inside a ```set-pieces fence):
        SP3 | Statue of Liberty | 01:53:44 - 02:03:20 | verified: dense | keep
    - name:     free-text label (report readability).
    - start-end: film-time range. Each side is a beat id (B21, resolved via the
                HH:MM beat time) OR a raw HH:MM:SS timestamp.
    - verified: dense | sampled | unverified. 'dense' = frame-verified
                start-to-finish (trusted). Anything else on a KEPT row warns -
                a boundary you sampled is a boundary you cannot trust.
    - keep/drop: only 'keep' rows are measured; 'drop' rows are recorded so the
                human decision stays visible and is never silently re-proposed.
    Returns: [{"id","name","start_sec","end_sec","verified","keep","start_ref",
               "end_ref"}], drop rows included (keep=False) for reporting.
    """
    import re as _re
    from pipeline import catalogue as _cat
    pdir = config.project_dir(project)
    bp = pdir / "beats_proposal.md"
    if not bp.exists():
        return []
    text = bp.read_text(encoding="utf-8-sig")
    m = _re.search(r"```set-pieces\s*\n(.*?)```", text, _re.DOTALL | _re.IGNORECASE)
    if not m:
        return []
    block = m.group(1)

    # beat-id -> seconds, from the same beat list beat_coverage uses (HH:MM)
    beat_sec = {}
    for b in _cat.parse_beats(project).get("beats", []):
        ts = b.get("ts")
        if b.get("id") and ts:
            s = _beat_ts_seconds(ts)
            if s is not None:
                beat_sec[str(b["id"]).upper()] = s

    def _resolve(ref):
        ref = ref.strip()
        if ref.upper() in beat_sec:
            return beat_sec[ref.upper()]
        try:
            return parse_ts(ref)                 # raw HH:MM:SS
        except Exception:
            return None

    out = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        sp_id = parts[0]
        name, rng, verified, keep = "", None, "unverified", True
        # parts[1] is the name; the remaining segments are range / verified /
        # keep-drop in any order (range is the one containing a '-').
        name = parts[1]
        for seg in parts[2:]:
            low = seg.lower()
            if low.startswith("verified:"):
                verified = seg.split(":", 1)[1].strip().lower()
            elif low in ("keep", "drop"):
                keep = (low == "keep")
            elif "-" in seg and rng is None:
                rng = seg
        if rng is None:
            continue
        # split the range on the first ' - ' (times themselves have no bare ' - ')
        rparts = _re.split(r"\s-\s", rng, maxsplit=1)
        if len(rparts) != 2:
            continue
        start_sec = _resolve(rparts[0])
        end_sec = _resolve(rparts[1])
        if start_sec is None or end_sec is None or end_sec <= start_sec:
            continue
        out.append({
            "id": sp_id, "name": name,
            "start_sec": start_sec, "end_sec": end_sec,
            "start_ref": rparts[0].strip(), "end_ref": rparts[1].strip(),
            "verified": verified, "keep": keep,
        })
    return out


def _film_median_line_gap(d) -> float:
    """Median gap (seconds) between consecutive explicit-timestamp draft lines
    across the WHOLE film. This is the recap's own cadence - the reference the
    set-piece max-gap scales from. Returns 0.0 if <2 timed lines."""
    import statistics as _stats
    secs = []
    for ln in d.lines:
        cs = getattr(ln, "clip_start", None)
        if not cs:
            continue
        try:
            secs.append(parse_ts(cs))
        except Exception:
            continue
    secs.sort()
    gaps = [secs[i + 1] - secs[i] for i in range(len(secs) - 1)]
    return _stats.median(gaps) if gaps else 0.0


def set_piece_coverage(project, d) -> dict:
    """SET-PIECE COVERAGE: within each kept, dense-verified set-piece, no gap
    between consecutive narration lines (or from a range edge) may exceed the
    tier-relative max-gap. Returns:
        {"present": bool, "threshold": float, "median_gap": float,
         "results": [{id,name,worst_gap,worst_from,coverage,n_lines,
                      over,start_sec,end_sec}],
         "over": [id,...], "untrusted": [id,...]}
    No-op ({"present": False}) when there is no set-pieces block.

    Threshold (v1, provisional - calibrated on one film, revisit after the next):
        max(SETPIECE_MAXGAP_FLOOR, SETPIECE_MAXGAP_MULT x film median line gap)
    The failure mode is an unnarrated stretch a viewer can't follow, not a raw
    coverage %, so the largest gap decides. Non-combat stretches are unmarked
    (never measured) - the gate cannot fire on a quiet/dialogue scene.
    """
    sps = parse_set_pieces(project)
    if not sps:
        return {"present": False}

    floor = float(getattr(config, "SETPIECE_MAXGAP_FLOOR", 240.0))
    mult = float(getattr(config, "SETPIECE_MAXGAP_MULT", 3.0))
    median = _film_median_line_gap(d)
    threshold = max(floor, mult * median) if median > 0 else floor

    # explicit-timestamp line starts (montage/pool lines have no film time)
    line_secs = []
    for ln in d.lines:
        cs = getattr(ln, "clip_start", None)
        if not cs:
            continue
        try:
            line_secs.append(parse_ts(cs))
        except Exception:
            continue
    line_secs.sort()

    results, over, untrusted = [], [], []
    for sp in sps:
        if not sp["keep"]:
            continue                          # drop rows are recorded, not measured
        a, b = sp["start_sec"], sp["end_sec"]
        inr = [s for s in line_secs if a <= s < b]
        # gaps: from range start -> first line, between lines, last line -> end.
        pts = [a] + inr + [b]
        gaps = [(pts[i + 1] - pts[i], pts[i]) for i in range(len(pts) - 1)]
        if gaps:
            worst_gap, worst_at = max(gaps, key=lambda g: g[0])
        else:
            worst_gap, worst_at = (b - a), a
        span = b - a
        # coverage %: fraction of the span within ~half-threshold of a line
        # (context only; the gap decides). Reported, never gates.
        coverage = (len(inr) / max(1.0, span / max(1.0, median or 60.0))) if span else 0.0
        coverage = min(1.0, coverage)
        is_over = worst_gap > threshold
        res = {
            "id": sp["id"], "name": sp["name"],
            "worst_gap": worst_gap, "worst_from": worst_at,
            "n_lines": len(inr), "coverage": coverage,
            "over": is_over, "start_sec": a, "end_sec": b,
            "verified": sp["verified"],
        }
        results.append(res)
        if is_over:
            over.append(sp["id"])
        if sp["verified"] != "dense":
            untrusted.append(sp["id"])

    return {
        "present": True, "threshold": threshold, "median_gap": median,
        "floor": floor, "mult": mult,
        "results": results, "over": over, "untrusted": untrusted,
    }


def _run_phase1_audits(project, pdir):
    try:
        from pipeline import schemas
        from pipeline.coverage_audit import coverage_audit
        from pipeline.binding_audit import binding_audit
        from pipeline.continuity_check import continuity_check
        from pipeline.tag_audit import tag_audit
        from pipeline.validator_report import format_validator_report
    except Exception as e:
        console.print(f"[dim]Phase 1 audits unavailable: {e}[/]")
        return
    try:
        d = schemas.load_draft(project)
    except Exception as e:
        console.print(f"[dim]Phase 1 audits skipped (draft parse): {e}[/]")
        return
    skel = None
    try:
        skel = schemas.load_skeleton(project)
    except FileNotFoundError:
        skel = None
    except Exception as e:
        console.print(f"[yellow]skeleton.json present but invalid: {e}[/]")
        skel = None
    try:
        shots_by_id, pool_families = schemas.load_shots(project)
    except Exception as e:
        console.print(f"[yellow]footage parse issue: {e}[/]")
        shots_by_id, pool_families = {}, {}
    names = schemas.load_names(project)
    cov = coverage_audit(d, skel) if skel is not None else []
    bind = binding_audit(d, shots_by_id, pool_families, names)
    cont = continuity_check(d, shots_by_id)
    tag_issues = tag_audit(shots_by_id)

    # ---- tag-coverage stats (so the audit can never silently no-op) ---------
    raw_pool = {}
    try:
        bp = pdir / "broll.json"
        if bp.exists():
            bd = json.loads(bp.read_text(encoding="utf-8-sig"))
            raw_pool = bd.get("pool", bd)
    except Exception:
        raw_pool = {}
    broll_total = len(raw_pool)
    broll_tagged = sum(1 for v in raw_pool.values()
                       if isinstance(v, dict) and (v.get("depicts") or v.get("chars")))
    untagged_broll = [k for k, v in raw_pool.items()
                      if isinstance(v, dict) and not (v.get("depicts") or v.get("chars"))]

    raw_shots = []
    sp = pdir / "shots.json"
    if sp.exists():
        try:
            raw_shots = json.loads(sp.read_text(encoding="utf-8-sig")).get("shots", [])
        except Exception:
            raw_shots = []
    shots_total = len(raw_shots)
    shots_tagged = sum(1 for s in raw_shots if s.get("depicts") or s.get("chars"))
    untagged_shots = [s.get("id", "?") for s in raw_shots
                      if not (s.get("depicts") or s.get("chars"))]

    lines_total = len(d.lines)
    lines_with_claim = sum(1 for l in d.lines if l.claim is not None)

    tag_stats = {
        "broll_total": broll_total, "broll_tagged": broll_tagged,
        "shots_total": shots_total, "shots_tagged": shots_tagged,
        "lines_total": lines_total, "lines_with_claim": lines_with_claim,
    }

    # explicit untagged-data warnings (visible, never silent)
    if untagged_broll:
        console.print(f"[yellow][UNTAGGED_BROLL][/] {len(untagged_broll)}/{broll_total} "
                      f"broll entries missing depicts/chars: "
                      f"{', '.join(untagged_broll[:8])}"
                      + (" ..." if len(untagged_broll) > 8 else ""))
    if untagged_shots:
        console.print(f"[yellow][UNTAGGED_SHOT][/] {len(untagged_shots)}/{shots_total} "
                      f"shots.json entries missing depicts/chars: "
                      f"{', '.join(str(x) for x in untagged_shots[:8])}")
    if lines_with_claim < lines_total:
        console.print(f"[yellow][LINE_NO_CLAIM][/] Lines with claim: "
                      f"{lines_with_claim}/{lines_total} "
                      f"({100*lines_with_claim/max(1,lines_total):.0f}%)")

    report_lines, sev = format_validator_report(cov, bind, cont, skel, d, tag_stats,
                                                tag_issues)
    for line in report_lines:
        console.print(line)

    # ---- Mức 1 binding-capacity check (surface BindingViolations PRE-render) -
    # The render no longer silently freezes a clip when narration overruns the
    # shot window; it raises BindingViolation. We surface those here, before any
    # render attempt, so the fix (split / multi-shot) happens at authoring time.
    try:
        from pipeline.schemas import binding_capacity_check, BINDING_SLOWDOWN_MAX
        cap = binding_capacity_check(d, shots_by_id)
    except Exception as e:
        console.print(f"[dim]binding-capacity check unavailable: {e}[/]")
        cap = []
    violations = [c for c in cap if c["severity"] == "violation"]
    slowdowns = [c for c in cap if c["severity"] == "slowdown"]
    if slowdowns:
        console.print(
            f"[yellow][BINDING-SLOWDOWN][/] {len(slowdowns)} line(s) need mild "
            f"slow-motion (<= {BINDING_SLOWDOWN_MAX:.1f}x) to fill their shot - OK, no freeze:")
        for c in slowdowns:
            console.print(
                f"    line {c['line_id']}: narr ~{c['narr_est']:.1f}s vs "
                f"shot {c['shot_dur']:.1f}s (cap {c['capacity']:.1f}s)")
    if violations:
        console.print(
            f"[red][BINDING-VIOLATION][/] {len(violations)} line(s) exceed shot "
            f"capacity ({BINDING_SLOWDOWN_MAX:.1f}x) - would freeze. Split further "
            f"or bind a multi-shot sequence:")
        for c in violations:
            console.print(
                f"    line {c['line_id']}: narr ~{c['narr_est']:.1f}s "
                f"> capacity {c['capacity']:.1f}s "
                f"(shot window {c['shot_dur']:.1f}s, {c['words']} words)")
        sev = "hard"   # block render until resolved

    # ---- Mức 3 capacity-aware narration check (per-shot word ceiling) --------
    # Using the calibrated voice profile, every shot has a max_narration_words_en.
    # Surface lines APPROACHING that ceiling (>= 80%) as a soft heads-up so the
    # writer knows they are near the limit, BEFORE they push a shot into a
    # render-time slowdown/violation. Information only; never hard-fails here
    # (the Mức 1 sum-based check above is the actual gate).
    try:
        from pipeline.catalogue import capacity_map
        cmap = capacity_map(project)
    except Exception as e:
        console.print(f"[dim]Mức 3 capacity map unavailable: {e}[/]")
        cmap = {}
    if cmap:
        near = []
        over = []
        for ln in d.lines:
            if ln.montage or ln.pool or ln.word_count() == 0:
                continue
            cs = ln.clip_start
            if not cs or cs not in cmap:
                continue
            ceiling = cmap[cs]
            if ceiling <= 0:
                continue
            w = ln.word_count()
            ratio = w / ceiling
            if ratio > 1.0:
                over.append((ln.id, w, ceiling))
            elif ratio >= 0.8:
                near.append((ln.id, w, ceiling))
        if over:
            console.print(
                f"[yellow][CAPACITY-WORDS][/] {len(over)} line(s) exceed the "
                f"calibrated word ceiling for their shot (will need slow-mo):")
            for lid, w, ce in over[:20]:
                console.print(f"    line {lid}: {w} words > shot max {ce}")
        if near:
            console.print(
                f"[dim][CAPACITY-WORDS] {len(near)} line(s) within 80-100% of "
                f"their shot word ceiling (approaching limit): "
                f"{', '.join('L%d %d/%d' % (lid, w, ce) for lid, w, ce in near[:12])}[/]")
        if not over and not near:
            console.print("[dim][CAPACITY-WORDS] all lines comfortably within "
                          "calibrated shot word ceilings.[/]")

    # ---- stage-aware gating (Stage 3a OUTLINE / 3b SCRIPT) -------------------
    # DRAFT-TARGET (real-rate / fill / tier-floor) is meaningless for a thin
    # OUTLINE pass whose job is coverage+binding. Run it ONLY in SCRIPT stage,
    # and ONLY for linear projects (review flow unchanged: always "script").
    from pipeline import state as _state
    from pipeline import catalogue as _cat2
    style = _cat2.parse_beats(project).get("style", "review")
    stage = _state.get_stage(project) if style == "linear" else "script"
    if stage == "script":
        _draft_target_report(project, d, cmap)
    else:
        console.print("[dim][STAGE] outline stage - DRAFT-TARGET skipped "
                      "(coverage/binding gate only).[/]")

    # ---- beat-coverage (skeleton-free; linear) - same numbers the stage
    # machine uses; surfaced here for visibility.
    bc = beat_coverage(project, d) if style == "linear" else {"beats": 0}
    if bc.get("beats"):
        msg = (f"[bold][BEAT-COVERAGE][/] {bc['covered']}/{bc['beats']} "
               f"beats have >=1 bound line")
        if bc["uncovered"]:
            msg += f"; uncovered: {', '.join(map(str, bc['uncovered'][:10]))}"
        console.print(msg)

    # ---- SET-PIECE COVERAGE (linear, SCRIPT stage ONLY) ----------------------
    # A followability-critical fight needs no long unnarrated stretch. Measures
    # ONLY human-confirmed, dense-verified set-piece ranges (never a quiet scene
    # - non-combat is deliberately unmarked). Script-only, because an OUTLINE is
    # thin everywhere by design (mirrors DRAFT-TARGET's stage gating). Soft-only:
    # escalate sev, never downgrade hard. No-op without a set-pieces block.
    sp_cov = {"present": False}
    if style == "linear" and stage == "script":
        sp_cov = set_piece_coverage(project, d)
    if sp_cov.get("present"):
        thr = sp_cov["threshold"]
        console.print(
            f"[bold][SET-PIECE][/] max-gap threshold [bold]{thr:.0f}s[/] "
            f"= max({sp_cov['floor']:.0f}, {sp_cov['mult']:.0f}x median "
            f"{sp_cov['median_gap']:.0f}s) | measuring "
            f"{len(sp_cov['results'])} kept set-piece(s)")
        for r in sp_cov["results"]:
            tag = "[yellow]OVER[/]" if r["over"] else "[green]ok[/]"
            console.print(
                f"    {tag} {r['id']} {r['name']}: worst gap "
                f"{r['worst_gap']:.0f}s @ ~{r['worst_from']/60:.1f} min "
                f"({r['n_lines']} line(s) in range)")
        if sp_cov["over"]:
            console.print(
                f"[yellow][SET-PIECE-UNDER][/] {len(sp_cov['over'])} set-piece(s) "
                f"have an unnarrated stretch over {thr:.0f}s "
                f"({', '.join(sp_cov['over'])}) - the fight may lose its thread. "
                f"Add a stage-line inside the gap (Setup -> Action -> Consequence).")
            sev = "hard" if sev == "hard" else "soft"
        if sp_cov["untrusted"]:
            # method-honesty: a KEPT range not dense-verified cannot be trusted.
            console.print(
                f"[yellow][SET-PIECE-UNVERIFIED][/] {len(sp_cov['untrusted'])} "
                f"kept set-piece(s) not marked 'verified: dense' "
                f"({', '.join(sp_cov['untrusted'])}) - the RANGE itself is "
                f"untrusted (a sampled boundary drifts). Dense-verify start/end "
                f"before relying on this gate for them.")
            sev = "hard" if sev == "hard" else "soft"
        console.print("[dim][SET-PIECE] measures ONLY human-confirmed combat "
                      "ranges; quiet/dialogue scenes are unmarked by design and "
                      "never flagged. Threshold is v1 (provisional).[/]")
    elif style == "linear" and stage != "script":
        console.print("[dim][SET-PIECE] outline stage - skipped "
                      "(density is only expected once enriching).[/]")

    # ---- REVEAL-TIMING (linear, ALWAYS-ON regardless of stage) ---------------
    # A spoiler can enter at outline OR during enrichment, and even a thin
    # outline can spoil, so this is not stage-gated. Soft-only: escalate sev to
    # "soft" if any hit, but NEVER downgrade an existing "hard". No-op when the
    # project has no reveal-map block.
    reveal_hits = reveal_timing_check(project, d) if style == "linear" else []
    if reveal_hits:
        console.print(f"[yellow][REVEAL-TIMING][/] {len(reveal_hits)} "
                      f"possible early reveal(s) - a protected term appears "
                      f"BEFORE its landing beat:")
        for h in reveal_hits[:20]:
            land = "always" if h["land_sec"] == float("inf") else h["land_ref"]
            console.print(
                f"    {h['reveal_id']}: \"{h['term']}\" in line {h['line_id']} "
                f"(~{h['line_sec']/60:.1f} min) lands before {land}")
        # escalate to soft, never downgrade hard
        sev = "hard" if sev == "hard" else "soft"
    # Honest-limit note prints whenever a reveal-map exists (hits or not), so no
    # one mistakes a clean pass for spoiler-proof.
    if style == "linear" and parse_reveal_map(project):
        console.print("[dim][REVEAL-TIMING] literal-term text scan; it cannot "
                      "catch paraphrase or implied foreshadowing - the Stage-7 "
                      "watch remains the spoiler backstop.[/]")

    # Return everything the stage machine needs (sev + honest metrics).
    # bind.verified_mismatch / bind.unverified are the SAME ints the Summary
    # line prints (BindingResult fields), so numbers cannot diverge.
    return {
        "sev": sev,
        "style": style,
        "stage": stage,
        "beat_coverage": bc,
        "binding_mismatch": bind.verified_mismatch,
        "binding_unverified": bind.unverified,
        "continuity_issues": len(cont),
        "binding_violations": len(violations),
        "reveal_hits": len(reveal_hits),
        "set_piece_over": len(sp_cov.get("over", [])) if sp_cov.get("present") else 0,
    }


def _draft_target_report(project, d, cmap):
    """DRAFT-TARGET: real-rate runtime + tier-floor + capacity-fill (all soft)."""
    from pipeline import calibration as _cal
    from pipeline import catalogue as _cat

    profile = _cal.get_profile(
        getattr(config, "DEFAULT_TTS_VOICE", None),
        getattr(config, "DEFAULT_TTS_RATE", "+22%"))

    # --- real-rate runtime: sum per-line spoken seconds + silence seconds ----
    # Narrated seconds come from the draft lines (at the calibrated rate).
    real_sec = 0.0
    total_words = 0
    for ln in d.lines:
        w = ln.word_count() if hasattr(ln, "word_count") else len(str(getattr(ln, "narration", "")).split())
        if w == 0:
            continue
        total_words += w
        real_sec += profile.estimate_narration_seconds(getattr(ln, "narration", "") or "")
    # Silence seconds live on SHOTS (a silence shot binds no draft line, per C1),
    # so add them from shots.json so the runtime estimate is complete.
    sil_sec = 0.0
    try:
        import json as _json
        sp = config.project_dir(project) / "shots.json"
        if sp.exists():
            sdata = _json.loads(sp.read_text(encoding="utf-8-sig"))
            for s in sdata.get("shots", []):
                v = s.get("narration_silence_seconds")
                if v:
                    sil_sec += float(v)
    except Exception:
        pass
    real_sec += sil_sec
    real_min = real_sec / 60.0
    cons_min = total_words / float(getattr(config, "TTS_WORDS_PER_MINUTE", 170))

    console.print(f"[bold cyan][DRAFT-TARGET][/] real-rate est: "
                  f"[bold]{real_min:.1f} min[/] "
                  f"(calibrated {profile.words_per_sec:.2f} w/s) | "
                  f"conservative est: {cons_min:.1f} min")

    # divergence note (conservative overshoots when real rate is faster)
    div_thr = float(getattr(config, "DRAFT_ESTIMATE_DIVERGENCE_NOTE", 0.15))
    if cons_min > 0 and (cons_min - real_min) / cons_min > div_thr:
        pct = 100.0 * (cons_min - real_min) / cons_min
        console.print(f"    [dim]note: the conservative estimate overshoots real "
                      f"runtime by ~{pct:.0f}% (voice speaks faster than 170 WPM); "
                      f"trust the real-rate figure for tier targeting.[/]")

    # --- tier floor check ----------------------------------------------------
    tiers = getattr(config, "DEPTH_TIERS", {})
    try:
        binfo = _cat.parse_beats(project)
        tier = binfo.get("tier") or binfo.get("tier_inferred")
        style = binfo.get("style", "review")
    except Exception:
        tier = None
        style = "review"
    _guide = "prompts/style_linear_vn.md" if style == "linear" else "prompts/recap_style.md"
    console.print(f"    [dim]narration style: [bold]{style}[/] ({_guide})[/]")
    if tier and tier in tiers:
        floor = float(tiers[tier].get("runtime_floor_min", 0))
        band = tiers[tier].get("runtime", "?")
        if floor and real_min < floor:
            console.print(f"    [yellow][DRAFT-UNDER-TARGET][/] real-rate "
                          f"{real_min:.1f} min is under the '{tier}' floor of "
                          f"{floor:.1f} min (tier band {band}). Enrich the "
                          f"narration before render.")
        else:
            console.print(f"    [green]tier '{tier}' ({band}): real-rate "
                          f"{real_min:.1f} min meets the {floor:.1f} min floor.[/]")
    else:
        console.print("    [dim]no depth_target tier declared in beats_proposal.md "
                      "- skipping tier-floor check (real-rate + fill still shown).[/]")

    # --- capacity fill -------------------------------------------------------
    if cmap:
        used = 0
        ceil_sum = 0
        per_unit_head: dict = {}   # unit_id -> (words, ceiling)
        for ln in d.lines:
            if getattr(ln, "montage", None) or getattr(ln, "pool", None):
                continue
            cs = getattr(ln, "clip_start", None)
            if not cs or cs not in cmap:
                continue
            ceiling = cmap[cs]
            if ceiling <= 0:
                continue
            w = ln.word_count() if hasattr(ln, "word_count") else len(str(getattr(ln, "narration", "")).split())
            used += w
            ceil_sum += ceiling
            uid = getattr(ln, "unit_id", None) or "?"
            pw, pc = per_unit_head.get(uid, (0, 0))
            per_unit_head[uid] = (pw + w, pc + ceiling)
        if ceil_sum > 0:
            fill = used / ceil_sum
            lo, hi = getattr(config, "DRAFT_FILL_TARGET", (0.70, 0.85))
            under = float(getattr(config, "DRAFT_FILL_UNDER_WARN", 0.65))
            over = float(getattr(config, "DRAFT_FILL_OVER_WARN", 0.90))
            band_note = ("within target" if lo <= fill <= hi else
                         "UNDER target" if fill < lo else "over target")
            console.print(f"    capacity fill: [bold]{fill*100:.0f}%[/] "
                          f"({used}/{ceil_sum} words; target {int(lo*100)}-{int(hi*100)}%) "
                          f"[{band_note}]")
            if fill < under:
                # surface the units with the most unused capacity headroom
                room = sorted(
                    ((uid, pc - pw, pw, pc) for uid, (pw, pc) in per_unit_head.items() if pc > pw),
                    key=lambda x: -x[1])[:6]
                room_str = ", ".join(f"{uid} ({pw}/{pc}w)" for uid, _, pw, pc in room)
                console.print(f"    [yellow][DRAFT-UNDERFILL][/] fill {fill*100:.0f}% "
                              f"is below {int(under*100)}% - the draft leaves shot "
                              f"capacity unused. Most room to enrich: {room_str}.")
            elif fill > over:
                console.print(f"    [yellow][DRAFT-OVERFILL][/] fill {fill*100:.0f}% "
                              f"exceeds {int(over*100)}% - lines are near capacity; "
                              f"expect slow-motion across many shots.")
