"""
continuity_check.py — Phase 1 timeline-jump check.

Walks consecutive EXPLICIT-timestamp lines (skips pool/montage/broll and any line
flagged narrative_jump or flashback) and flags large forward jumps or backwards
jumps in source time. Complements the existing [FRESHNESS] check in draft.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .schemas import Draft, parse_ts

LARGE_JUMP_THRESHOLD_SEC = 600   # 10 minutes
BACKWARDS_TOLERANCE_SEC = 60     # allow small overlaps for cutting

ContinuityIssueType = Literal["LARGE_JUMP", "BACKWARDS_JUMP"]


@dataclass
class ContinuityIssue:
    line_id: int
    prev_line_id: int
    issue: ContinuityIssueType
    time_delta_sec: float
    detail: str


def _explicit_time(ln):
    """Return source seconds for an explicit-timestamp line, else None."""
    if ln.pool or ln.montage or not ln.clip_start:
        return None
    if ln.narrative_jump or ln.flashback:
        return None
    try:
        return parse_ts(ln.clip_start)
    except Exception:
        return None


def continuity_check(draft: Draft, shots: dict | None = None) -> list[ContinuityIssue]:
    issues: list[ContinuityIssue] = []
    prev = None  # (line_id, seconds)
    for ln in draft.lines:
        t = _explicit_time(ln)
        if t is None:
            # non-explicit / jump line breaks the chain but isn't itself flagged
            if ln.narrative_jump or ln.flashback:
                prev = None
            continue
        if prev is not None:
            delta = t - prev[1]
            if abs(delta) > LARGE_JUMP_THRESHOLD_SEC:
                issues.append(ContinuityIssue(
                    ln.id, prev[0], "LARGE_JUMP", delta,
                    f"time jump {prev[1]:.0f}s -> {t:.0f}s ({delta:+.0f}s). "
                    f"If intentional (flashback/parallel), set narrative_jump=true."))
            elif delta < -BACKWARDS_TOLERANCE_SEC:
                issues.append(ContinuityIssue(
                    ln.id, prev[0], "BACKWARDS_JUMP", delta,
                    f"backwards {prev[1]:.0f}s -> {t:.0f}s ({delta:+.0f}s). "
                    f"If intentional, set narrative_jump=true."))
        prev = (ln.id, t)
    return issues
