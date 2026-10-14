

"""
validator_report.py - format Phase 1 audit results for the agent.

Honesty rules (Step 1 fix for the false-pass bug):
  - An AUDIT COVERAGE block at the very top shows how much data was actually
    tagged, so an audit can never silently pass on untagged data.
  - Binding never prints "0 mismatches" alone: if any line is UNVERIFIED it says
    "0 verified mismatches - but Z lines unverified".
  - Severity is "warn" whenever AUDIT_COVERAGE < 90% OR any UNVERIFIED exists,
    even with 0 verified mismatches (cannot claim clean unless the audit ran).
  - Tag-quality warnings (TAG_TOO_GENEROUS / TAG_TEMPORALLY_AMBIGUOUS) elevate
    severity to "warn" because over-broad tagging silently weakens binding.
ASCII-only output (console is cp1252).
"""
from __future__ import annotations

import config


def _runtime_min(total_words: int) -> float:
    wpm = getattr(config, "TTS_WORDS_PER_MINUTE", 170)
    return total_words / max(1, wpm)


def _pct(a, b):
    return (100.0 * a / b) if b else 0.0


def format_validator_report(coverage_gaps, binding_result, continuity_issues,
                            skeleton, draft, tag_stats, tag_issues=None):
    """
    tag_stats keys: broll_total, broll_tagged, shots_total, shots_tagged,
                    lines_total, lines_with_claim.
    tag_issues: optional list of TagIssue from tag_audit (default []).
    Returns (lines, severity) where severity in {clean, soft, hard}.
    """
    lines: list = []
    hard = False
    warn = False
    tag_issues = tag_issues or []

    br_t = tag_stats.get("broll_tagged", 0); br_y = tag_stats.get("broll_total", 0)
    sh_t = tag_stats.get("shots_tagged", 0); sh_y = tag_stats.get("shots_total", 0)
    cl_a = tag_stats.get("lines_with_claim", 0); cl_b = tag_stats.get("lines_total", 0)

    bres = binding_result
    vmatch = getattr(bres, "verified_match", 0)
    vmis = getattr(bres, "verified_mismatch", 0)
    unver = getattr(bres, "unverified", 0)
    bissues = getattr(bres, "issues", [])

    # overall audit-coverage % = how much footage is tagged (the binding gate's input)
    audit_cov = _pct(br_t, br_y) if br_y else 0.0

    # ---- AUDIT COVERAGE (top, before summary) -------------------------------
    lines.append("[bold cyan]== AUDIT COVERAGE ==[/]")
    lines.append(f"  Broll entries tagged with depicts: {br_t}/{br_y} ({audit_cov:.0f}%)")
    if sh_y:
        lines.append(f"  Shots tagged with depicts:         {sh_t}/{sh_y} ({_pct(sh_t,sh_y):.0f}%)")
    lines.append(f"  Draft lines with claim:            {cl_a}/{cl_b} ({_pct(cl_a,cl_b):.0f}%)")
    if audit_cov < 90 or unver > 0:
        lines.append("  [yellow]! Binding ran against TAGGED data only. "
                     "Untagged data is invisible to the audit.[/]")
        warn = True

    lines.append("[bold cyan]-- Phase 1 audit --[/]")
    lines.append(f"[bold]Summary:[/] coverage {len(coverage_gaps)} | "
                 f"binding {vmis} mismatch / {unver} unverified | "
                 f"tags {len(tag_issues)} | continuity {len(continuity_issues)}")

    # ---- COVERAGE -----------------------------------------------------------
    if skeleton is not None:
        lines.append("[bold]Coverage audit:[/]")
        if not coverage_gaps:
            lines.append("  [green]all units within budget + must_cover satisfied[/]")
        else:
            by_unit: dict = {}
            for g in coverage_gaps:
                by_unit.setdefault(g.unit_id, []).append(g)
            for uid, gs in by_unit.items():
                label = gs[0].unit_label
                lines.append(f"  [yellow]x {uid}[/] \"{label}\"")
                for g in gs:
                    if g.hard:
                        hard = True
                    tag = "[red]" if g.hard else "[yellow]"
                    lines.append(f"      {tag}[{g.issue}][/] {g.detail}")
                    if g.suggestions:
                        lines.append(f"        did you mean: {', '.join(g.suggestions)}")
    else:
        lines.append("[yellow]Coverage audit skipped - no skeleton.json.[/]")

    # ---- BINDING ------------------------------------------------------------
    lines.append("[bold]Binding audit ([VOICE-VISUAL]):[/]")
    lines.append("[bold]  BINDING AUDIT COVERAGE[/]")
    lines.append(f"    Verified matches:    {vmatch} lines")
    lines.append(f"    Verified mismatches: {vmis} lines (real issues)")
    lines.append(f"    Unverified:          {unver} lines (footage untagged - cannot audit)")
    # RULES Part J. Printed as its own row, never folded into "verified
    # matches", and always followed by its own limitation. A speech line that
    # passes has had its SPEAKER confirmed and its CONTENT confirmed by nothing;
    # an audit that does not say so out loud is reporting clean on an input it
    # never had (D-GREEN).
    _spk = getattr(bres, "speaker_verified", 0)
    if _spk:
        lines.append(f"    Speaker verified:    {_spk} speech line(s) - "
                     f"speaker present in the bound shot")
        lines.append("  [yellow]LIMIT: a `speech` claim is checked for SPEAKER "
                     "PRESENCE ONLY. Nothing here confirms WHAT was said - no "
                     "gate in this pipeline reads dialogue. These lines need the "
                     "Stage-7 watch.[/]")
        warn = True
    if vmis == 0 and unver > 0:
        lines.append(f"  [yellow]0 verified mismatches - but {unver} lines unverified. "
                     f"Tag remaining footage to complete the audit.[/]")
        warn = True
    elif vmis == 0 and unver == 0 and vmatch == 0:
        # Nothing was checked. Saying "all verified" here is the worst output
        # this report can produce: it is read as a pass. binding_audit only
        # examines lines carrying a `claim`, and across every project so far
        # that count is zero, so this branch fired on every film while the
        # audit had looked at nothing.
        lines.append("  [yellow]NOTHING VERIFIED - 0 lines carry a `claim`, so the "
                     "binding audit checked nothing. This is not a pass.[/]")
        warn = True
    elif vmis == 0 and unver == 0:
        lines.append(f"  [green]all {vmatch} visual line(s) verified - "
                     f"footage matches the narration[/]")
    # list the real mismatches (not the unverified noise)
    for b in bissues:
        if b.issue == "UNVERIFIED":
            continue
        hard = True
        lines.append(f"  [red]x line {b.line_id}[/] [{b.issue}] claim={b.claim_type}"
                     + (f"(subject {b.claim_subject})" if b.claim_subject else ""))
        lines.append(f"      \"{b.line_text[:70]}\"")
        lines.append(f"      footage: {b.footage}"
                     + (f"  depicts={b.footage_depicts}" if b.footage_depicts else "")
                     + (f"  chars={b.footage_chars}" if b.footage_chars else ""))
        if b.suggested:
            lines.append(f"      try: {', '.join(b.suggested)}")

    # ---- TAG QUALITY --------------------------------------------------------
    # Surfaces clips whose depicts tags will silently weaken binding (too many
    # tags / temporally-distinct stages on one clip). Warning-only.
    lines.append("[bold]Tag-quality audit ([TAG-QUALITY]):[/]")
    if not tag_issues:
        if (br_y + sh_y) > 0:
            lines.append("  [green]clean - all tagged clips within discipline[/]")
        else:
            lines.append("  [dim]no footage tagged yet - nothing to audit[/]")
    else:
        warn = True
        # group by issue type for readability
        by_type: dict = {}
        for ti in tag_issues:
            by_type.setdefault(ti.issue, []).append(ti)
        for itype in ("TAG_TOO_GENEROUS", "TAG_TEMPORALLY_AMBIGUOUS"):
            ilist = by_type.get(itype, [])
            if not ilist:
                continue
            lines.append(f"  [yellow]{itype}[/] ({len(ilist)} clip(s)):")
            for ti in ilist:
                lines.append(f"    [yellow]! {ti.shot_id}[/] tags={ti.actual_tags}")
                lines.append(f"        {ti.detail}")
        lines.append("  [dim]See docs/TAGGING_GUIDE.md for when to use each depicts value.[/]")

    # ---- CONTINUITY ---------------------------------------------------------
    if continuity_issues:
        lines.append("[bold]Continuity audit:[/]")
        for c in continuity_issues:
            warn = True
            lines.append(f"  [yellow]! line {c.prev_line_id}->{c.line_id}[/] "
                         f"[{c.issue}] {c.detail}")

    if coverage_gaps:
        warn = True

    # ---- RUNTIME ------------------------------------------------------------
    if skeleton is not None:
        tgt = sum(u.target_words for u in skeleton.units)
        wpm = getattr(config, "TTS_WORDS_PER_MINUTE", 170)
        lines.append(f"[bold]Coverage target:[/] {tgt}w (~{_runtime_min(tgt):.1f} min at {wpm} WPM)")

    # ---- NEXT + severity ----------------------------------------------------
    if hard:
        lines.append("[bold red]Next:[/] fix the [..] items above, then re-run.")
        sev = "hard"
    elif warn:
        lines.append("[bold yellow]Next:[/] tag remaining footage / tighten over-broad "
                     "tags / expand under-covered units. NOTE: cannot certify 'clean' "
                     "until all warnings are resolved.")
        sev = "soft"
    else:
        sev = "clean"

    return lines, sev



