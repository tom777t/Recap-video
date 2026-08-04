"""
coverage_audit.py — Phase 1 coverage check (skeleton.json <-> draft.json).

For each unit: sum word counts of its lines, compare to target_words +/- tolerance,
and verify every must_cover item is addressed by some line's `covers`.
Line-level: unknown unit_id, and covers strings that don't match the parent unit's
must_cover (with a difflib suggestion: n=2, cutoff=0.75).
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Any, Literal

from .schemas import Draft, Skeleton

CoverageIssue = Literal[
    "UNDER_WORDS", "OVER_WORDS", "MISSING_COVER", "UNKNOWN_COVER", "UNKNOWN_UNIT",
]

HARD_COVERAGE = {"UNKNOWN_UNIT", "UNKNOWN_COVER"}


@dataclass
class CoverageGap:
    unit_id: str
    unit_label: str
    issue: CoverageIssue
    expected: Any = None
    actual: Any = None
    detail: str = ""
    suggestions: list = field(default_factory=list)

    @property
    def hard(self) -> bool:
        return self.issue in HARD_COVERAGE


def coverage_audit(draft: Draft, skeleton: Skeleton) -> list[CoverageGap]:
    gaps: list[CoverageGap] = []
    unit_ids = {u.id for u in skeleton.units}

    # ---- line-level: unknown unit_id / unknown covers -----------------------
    for ln in draft.lines:
        uid = ln.unit_id
        if not uid:
            continue  # untagged line — additive schema, not an error
        if uid not in unit_ids:
            gaps.append(CoverageGap(uid, "?", "UNKNOWN_UNIT",
                                    detail=f"line {ln.id}: unit_id '{uid}' not in skeleton"))
            continue
        unit = skeleton.unit_by_id(uid)
        for cov in ln.covers:
            if cov not in unit.must_cover:
                sugg = difflib.get_close_matches(cov, unit.must_cover, n=2, cutoff=0.75)
                gaps.append(CoverageGap(
                    uid, unit.label, "UNKNOWN_COVER",
                    actual=cov,
                    detail=f"line {ln.id}: covers '{cov}' not a must_cover of {uid}",
                    suggestions=sugg))

    # ---- unit-level: word budget + missing must_cover -----------------------
    for unit in skeleton.units:
        unit_lines = [l for l in draft.lines if l.unit_id == unit.id]
        words = sum(l.word_count() for l in unit_lines)
        lo = int(unit.target_words * (1 - unit.tolerance))
        hi = int(unit.target_words * (1 + unit.tolerance))

        if words < lo:
            gaps.append(CoverageGap(
                unit.id, unit.label, "UNDER_WORDS",
                expected=(lo, hi), actual=words,
                detail=f"{words}w (range {lo}-{hi}, UNDER by {lo - words}w)"))
        elif words > hi:
            gaps.append(CoverageGap(
                unit.id, unit.label, "OVER_WORDS",
                expected=(lo, hi), actual=words,
                detail=f"{words}w (range {lo}-{hi}, OVER by {words - hi}w)"))

        covered = set()
        for l in unit_lines:
            covered.update(l.covers)
        missing = [m for m in unit.must_cover if m not in covered]
        if missing:
            gaps.append(CoverageGap(
                unit.id, unit.label, "MISSING_COVER",
                expected=unit.must_cover, actual=sorted(covered),
                detail="; ".join(missing)))

    return gaps
