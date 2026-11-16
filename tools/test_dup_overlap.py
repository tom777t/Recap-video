# -*- coding: utf-8 -*-
"""test_dup_overlap.py - positive AND negative controls, per the repo rule that a
new checker runs first on a known-good and a known-bad example.

Known-bad (from the checkpoint-1 review, lines 65/66): the same
"not angry about the shoes" content in two lines -> must FAIL.
Known-good: an audit inventory line followed by its verbatim exhibit quote
-> must PASS (list then quote is the designed anchor shape).

Run:  python tools/test_dup_overlap.py   (exit non-zero on failure)
"""
from __future__ import annotations
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.dup_overlap import check_pairs

BAD = [
    {"id": 1, "note": "B41", "narration": "he is not angry about the shoes; he is angry she never came to him"},
    {"id": 2, "note": "B41", "narration": "His first instinct is not anger about the shoes - it is that she could have been hurt, and never thought to tell him"},
]
GOOD = [
    {"id": 1, "note": "B99", "narration": "Her audit opens: the paid bills, the sudden hire, Daniel's office, a house in his name."},
    {"id": 2, "note": "B99", "narration": "Her own exhibit, verbatim: \"Why I suddenly got accepted to be an enterprise?\""},
    {"id": 3, "note": "B99", "narration": "Nobody showed her. She followed the money herself - the best auditor in the entire cast."},
]

TESTS = {
    "bad-pair flagged": lambda: len(check_pairs(BAD)) >= 1,
    "good triple clean": lambda: len(check_pairs(GOOD)) == 0,
}

fails = 0
for name, fn in TESTS.items():
    try:
        ok = fn()
    except Exception as e:
        print("FAIL %s (exception: %s)" % (name, e))
        fails += 1
        continue
    print(("PASS" if ok else "FAIL"), name)
    fails += 0 if ok else 1
raise SystemExit(1 if fails else 0)
