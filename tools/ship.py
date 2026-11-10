# -*- coding: utf-8 -*-
"""ship.py - record a video as SHIPPED, in one deliberate command.

    python tools/ship.py <project> [--lane dtv-thriller] \
        [--claim none|monetize|block] [--claimant "UMPG"]

Uploading is a deliberate act: this is the moment the channel's history
grows an entry and the claim ledger grows a line (the advisory's
claim-rate-per-lane production metric - claims are private to the
creator, so the channel's own ledger is the only dataset that exists).

What it writes:

    channel/history.json   the project's viewer-visible snapshot
                           (title, intro style, cold-open words, hashes
                           - public-safe), keyed by project, overwrite
                           on re-record
    channel/claims.jsonl   one append-only line: lane, claim status

Run tools/check_variation.py <project> FIRST; it reads the history this
command writes.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pipeline import variation as V  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("project")
    ap.add_argument("--lane", default=None,
                    help="content lane, e.g. dtv-thriller / xianxia")
    ap.add_argument("--claim", default=None,
                    choices=("none", "monetize", "block", "unknown"),
                    help="Content ID claim outcome on this video")
    ap.add_argument("--claimant", default=None,
                    help="who claimed it, when there is a claim")
    a = ap.parse_args()

    findings = V.compare(V.load_history(), V.snapshot(a.project))
    for f in findings:
        print("  " + f)

    snap = V.record(a.project, lane=a.lane, claim_status=a.claim,
                    claimant=a.claimant)
    print(f"shipped: {a.project} at {snap['shipped_at']}")
    print(f"history: {V.HISTORY}")
    print(f"claims : {V.CLAIMS} (lane={a.lane or '-'}, "
          f"claim={a.claim or 'not asked'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
