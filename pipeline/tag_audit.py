"""
tag_audit.py - Phase 1 tagging-discipline check ([TAG-QUALITY]).

Inspects every Shot's depicts list and flags entries that are too generous
or temporally ambiguous. These are warnings only - they do not block render,
but they surface clips where the audit cannot reliably verify narration
claims because the tags claim too many simultaneous things.

Root cause this protects against:
  A clip tagged ["reveal", "action"] passes any narration claiming either
  "reveal" or "action," even when only one of them is the dominant moment
  in the actual visible window. Render plays a seeded sub-window of the
  clip; if the sub-window shows the action portion but the narration claims
  the reveal moment, the audit passes (tag includes reveal) but the viewer
  sees a mismatch.

Fix: clips should be tagged with the single primary moment that is
consistently visible across the clip's window. Multi-stage clips should be
split into multiple clip entries, one per stage, each with a tight tag.
See docs/TAGGING_GUIDE.md for the full discipline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TagIssueType = Literal["TAG_TOO_GENEROUS", "TAG_TEMPORALLY_AMBIGUOUS"]

# Heuristic threshold: a clip with more depicts tags than this is flagged.
# Two tags is the realistic maximum for a single coherent moment (e.g.
# "dialogue + emotion" for a tense conversation). Three or more almost
# always means the clip spans multiple distinct stages.
MAX_PRIMARY_DEPICTS = 2

# Pairs that are almost never simultaneously visible in a single coherent
# window. If a clip claims both, it likely spans temporal stages and should
# be split into separate clip entries (one per stage).
TEMPORALLY_AMBIGUOUS_PAIRS = [
    ("setup", "action"),         # before-event vs the event itself
    ("setup", "aftermath"),      # before-event vs after-event
    ("setup", "reaction"),       # before-event vs response-to-event
    ("reveal", "action"),        # the identity moment vs the consequence moment
    ("reveal", "aftermath"),     # reveal vs what comes after
    ("discovery", "action"),     # information moment vs physical event
    ("action", "aftermath"),     # the event vs after the event
    ("action", "reaction"),      # the event vs the response to it
]


@dataclass
class TagIssue:
    shot_id: str
    issue: TagIssueType
    detail: str
    actual_tags: list


def tag_audit(shots: dict) -> list:
    """
    Walk every Shot and flag tagging that will mask mismatches downstream.
    Returns warnings only - never hard-fails.
    """
    issues: list[TagIssue] = []
    for sid, sh in shots.items():
        depicts = list(sh.depicts or [])
        n = len(depicts)

        if n > MAX_PRIMARY_DEPICTS:
            issues.append(TagIssue(
                shot_id=sid,
                issue="TAG_TOO_GENEROUS",
                detail=(f"{n} depicts tags - a single clip should depict 1-2 "
                        f"primary moments. Drop the secondary tags or split this "
                        f"clip into separate entries (one per moment)."),
                actual_tags=sorted(depicts),
            ))

        # Check for temporally-distinct tag pairs (even when n <= 2).
        # Only one ambiguity warning per shot to keep output readable;
        # if the shot triggers MAX_PRIMARY_DEPICTS too, both warnings surface.
        depicts_set = set(depicts)
        for a, b in TEMPORALLY_AMBIGUOUS_PAIRS:
            if a in depicts_set and b in depicts_set:
                issues.append(TagIssue(
                    shot_id=sid,
                    issue="TAG_TEMPORALLY_AMBIGUOUS",
                    detail=(f"depicts both '{a}' and '{b}' - these are temporally "
                            f"distinct stages. Render plays a sub-window of the "
                            f"clip; only one stage will be on screen at any line. "
                            f"Pick the dominant stage, or split the clip."),
                    actual_tags=sorted(depicts),
                ))
                break  # one ambiguity warning per shot

    return issues
