"""
binding_audit.py - Phase 1 claim-vs-footage check ([VOICE-VISUAL]).

For each line that carries a claim with requires_visual=True, resolve its footage
and verify the footage can actually depict the claim:
  - pool reference (e.g. "pool: P3"): check ONLY that specific pool entry's
    chars/depicts. The family is NOT used for matching - render plays the
    specific labelled clip (see broll.resolve), so the audit must check the
    same specific clip. Family-union here was a silent false-pass: it accepted
    any family member's tags as covering the claim, hiding mismatches whenever
    one family member happened to depict what another member did not.
  - explicit clip_start: a single synthesized shot; check against it as usual.

Family info is still passed in (API compatibility) and remains available to the
suggestion helper so the report can recommend other family members as
repointing candidates when a line fails to match its bound clip.

Lines without a claim, or with requires_visual=False, are skipped (additive schema).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from .schemas import Draft, Shot, parse_ts

BindingIssueType = Literal[
    "NO_SHOT", "UNKNOWN_SHOT", "SUBJECT_MISMATCH", "CLAIM_MISMATCH", "UNVERIFIED",
]


@dataclass
class BindingIssue:
    line_id: int
    issue: BindingIssueType
    line_text: str
    claim_type: str
    claim_subject: Optional[str]
    footage: str                       # e.g. "pool:P3" or "clip 00:42:00"
    footage_chars: list = field(default_factory=list)
    footage_depicts: list = field(default_factory=list)
    suggested: list = field(default_factory=list)   # pool labels / shot ids

    @property
    def hard(self) -> bool:
        # UNVERIFIED is a coverage gap (warning), not a real mismatch (hard issue).
        return self.issue != "UNVERIFIED"


@dataclass
class BindingResult:
    issues: list                       # all flags incl. UNVERIFIED
    verified_match: int = 0            # lines whose footage genuinely depicts the claim
    verified_mismatch: int = 0         # real problems (NO_SHOT/UNKNOWN_SHOT/CLAIM/SUBJECT)
    unverified: int = 0                # footage untagged -> could not audit
    checked: int = 0                   # visual-required lines considered

    @property
    def mismatches(self) -> list:
        return [i for i in self.issues if i.issue != "UNVERIFIED"]


def _norm(s: str) -> str:
    return str(s).strip().lower()


def binding_audit(draft: Draft, shots: dict, pool_families: dict, names: set) -> "BindingResult":
    issues: list[BindingIssue] = []
    verified_match = 0
    verified_mismatch = 0
    unverified = 0
    checked = 0

    # Suggestions: walk all known shots and surface ones whose depicts cover the
    # claim, preferring those whose chars include the subject. pool_families is
    # accepted for future family-aware ranking but not required for correctness.
    def _suggest(claim_type: str, subject: Optional[str]) -> list:
        out = []
        subj = _norm(subject) if subject else None
        for sid, sh in shots.items():
            if claim_type in sh.depicts:
                if subj and subj in {_norm(c) for c in sh.chars}:
                    out.insert(0, sid)          # subject match first
                elif not subj:
                    out.append(sid)
                else:
                    out.append(sid)
            if len(out) >= 5:
                break
        return out[:5]

    for ln in draft.lines:
        claim = ln.claim
        if claim is None or not claim.requires_visual:
            continue
        if ln.montage:
            continue  # montage handled by reuse/visual-repeat caps, not binding

        checked += 1
        ctype = claim.type
        subj = claim.subject
        subj_is_char = bool(subj) and _norm(subj) in names

        # ---- resolve footage: SPECIFIC pool entry, or explicit single shot --
        # When a line uses "pool: <label>", we check ONLY that label's own
        # chars/depicts. Render plays the specific labelled clip; the audit
        # must mirror that. Aggregating across the label's family would re-
        # introduce the silent false-pass bug.
        if ln.pool:
            sh = shots.get(ln.pool)
            if sh is None:
                issues.append(BindingIssue(ln.id, "UNKNOWN_SHOT", ln.narration,
                                           ctype, subj, f"pool:{ln.pool}",
                                           suggested=_suggest(ctype, subj)))
                verified_mismatch += 1
                continue
            agg_chars = {_norm(c) for c in sh.chars}
            agg_depicts = set(sh.depicts)
            footage = f"pool:{ln.pool}"
        elif ln.clip_start:
            sid = f"clip:{ln.clip_start}"
            try:
                t = parse_ts(ln.clip_start)
            except Exception:
                t = None
            sh = shots.get(sid)  # may exist if a shots.json described it
            if sh is not None:
                agg_chars = {_norm(c) for c in sh.chars}
                agg_depicts = set(sh.depicts)
            else:
                # synthesized shot from a raw timestamp has NO tags -> we cannot
                # confirm depiction. Recorded below as UNVERIFIED (never silently pass).
                agg_chars = set()
                agg_depicts = set()
            footage = f"clip {ln.clip_start}"
        else:
            issues.append(BindingIssue(ln.id, "NO_SHOT", ln.narration,
                                       ctype, subj, "(none)",
                                       suggested=_suggest(ctype, subj)))
            verified_mismatch += 1
            continue

        # If footage has NO tags at all (untagged broll or raw clip), we CANNOT
        # audit it -> record UNVERIFIED (never silently pass). This is the fix
        # for the false-pass bug: untagged data is now VISIBLE, not invisible.
        if not agg_depicts and not agg_chars:
            issues.append(BindingIssue(
                ln.id, "UNVERIFIED", ln.narration, ctype, subj, footage,
                suggested=[]))
            unverified += 1
            continue

        # ---- check claim.type is depicted -----------------------------------
        if agg_depicts and ctype not in agg_depicts:
            issues.append(BindingIssue(
                ln.id, "CLAIM_MISMATCH", ln.narration, ctype, subj, footage,
                footage_chars=sorted(agg_chars), footage_depicts=sorted(agg_depicts),
                suggested=_suggest(ctype, subj)))
            verified_mismatch += 1
            continue

        # ---- check subject (only if it's a known character) -----------------
        if subj_is_char and agg_chars and _norm(subj) not in agg_chars:
            issues.append(BindingIssue(
                ln.id, "SUBJECT_MISMATCH", ln.narration, ctype, subj, footage,
                footage_chars=sorted(agg_chars), footage_depicts=sorted(agg_depicts),
                suggested=_suggest(ctype, subj)))
            verified_mismatch += 1
            continue

        # ---- passed all checks: genuinely verified ------------------------
        verified_match += 1

    return BindingResult(issues=issues, verified_match=verified_match,
                         verified_mismatch=verified_mismatch, unverified=unverified,
                         checked=checked)
