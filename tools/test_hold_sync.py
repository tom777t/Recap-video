# -*- coding: utf-8 -*-
"""test_hold_sync.py - resolve puts code's hold lines back on their slot.

Lost in the Stars: hold 220 ran over line 221's footage ([WINDOW-OVERLAP]).
The layout fix (write_slots._size_holds) only changes plan.json's slots; a
draft already written keeps the old window, and no reviser may edit one, so
resolve could never clear the error. write_api.sync_holds copies a hold's
window from its slot into draft.json and the act file.

    python tools/test_hold_sync.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import write_api as W  # noqa: E402
import write_slots as WS  # noqa: E402


def test_sync() -> tuple[bool, str]:
    d = Path(tempfile.mkdtemp(prefix="recap_hold_"))
    try:
        slots = [
            {"slot": "S221", "act": 3, "beat": "B114", "role": "action",
             "clip_start": "01:38:40.000", "clip_end": "01:38:50.400"},
            {"slot": "S222", "act": 3, "beat": "B115", "role": "hold",
             "hold": 2.5, "clip_start": "01:38:50.400",
             "clip_end": "01:38:52.900"},
            {"slot": "S223", "act": 3, "beat": "B116", "role": "action",
             "clip_start": "01:38:52.900", "clip_end": "01:39:01.458"}]
        (d / "plan.json").write_text(json.dumps(
            {"slots": slots, "slots_version": WS.SLOTS_VERSION}), "utf-8")
        act = [{"id": 3001, "slot": "S221", "note": "B114",
                "narration": "He runs.", "clip_start": "01:38:40.000",
                "clip_end": "01:38:50.400"},
               {"id": 3002, "slot": "S222", "note": "B115", "narration": "",
                "narration_silence_seconds": 1.98,
                "clip_start": "01:38:50.400", "clip_end": "01:38:52.375"},
               {"id": 3003, "slot": "S223", "note": "B116",
                "narration": "In a flashback, a girl.",
                "clip_start": "01:38:52.375", "clip_end": "01:39:01.458"}]
        (d / "draft.json.d").mkdir()
        (d / "draft.json.d" / "act3.json").write_text(
            json.dumps({"lines": act}), "utf-8")
        draft = [dict(x, id=219 + i) for i, x in enumerate(act)]
        (d / "draft.json").write_text(json.dumps({"lines": draft}), "utf-8")
        got = W.sync_holds("x", d)
        dr = json.loads((d / "draft.json").read_text("utf-8"))["lines"]
        ac = json.loads((d / "draft.json.d" / "act3.json").read_text(
            "utf-8"))["lines"]
        bad = []
        if got != ["220", "221"]:
            bad.append(f"changed {got}, expected ['220', '221']")
        for name, ls in (("draft", dr), ("act file", ac)):
            h, n = ls[1], ls[2]
            if (h["clip_start"], h["clip_end"],
                    h["narration_silence_seconds"]) != (
                    "01:38:50.400", "01:38:52.900", 2.5):
                bad.append(f"{name} hold not on its slot: {h}")
            if n["clip_start"] != "01:38:52.900":
                bad.append(f"{name} trimmed line not moved: {n}")
        if dr[0] != draft[0]:
            bad.append("an untouched line was changed")
        if W.sync_holds("x", d):
            bad.append("a second run changed something again")
        # a line whose words would NOT fit the trimmed window stays put
        (d / "draft.json").write_text(json.dumps({"lines": draft}), "utf-8")
        (d / "draft.json.d" / "act3.json").write_text(
            json.dumps({"lines": act}), "utf-8")
        long_ = " ".join(["word"] * 40)
        for f in (d / "draft.json", d / "draft.json.d" / "act3.json"):
            o = json.loads(f.read_text("utf-8"))
            o["lines"][2]["narration"] = long_
            f.write_text(json.dumps(o), "utf-8")
        left = W.sync_holds("x", d)
        if "221" in left:
            bad.append("a line was squeezed into a window its words overrun")
        if "220" in left:
            bad.append("the hold grew over a line that could not move")
        return (not bad), ("hold 220 and the line it trimmed back on their "
                           "slots in draft.json and the act file; idempotent; "
                           "a line that would not fit is left, and so is the hold before it"
                           if not bad else "; ".join(bad))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_unwatchable_in_resolve() -> tuple[bool, str]:
    """The outro bound to the end credits (Lost in the Stars line 259) is
    moved by resolve itself, in draft.json and the act file."""
    from pipeline import draft as D
    d = Path(tempfile.mkdtemp(prefix="recap_unw_"))
    real = (D.beat_times, D.parse_reveal_map)
    try:
        outro = ("Muzi gave him chance after chance, and he repaid her with "
                 "a cage. That is not weakness, it is betrayal.")
        act = [{"id": 4001, "note": "B131", "narration": "She walks out.",
                "clip_start": "01:53:49.667", "clip_end": "01:54:09.402"},
               {"id": 4002, "note": "B131", "narration": outro,
                "delivery": "outro", "clip_start": "01:55:08.958",
                "clip_end": "01:57:40.000"}]
        (d / "draft.json.d").mkdir()
        (d / "draft.json.d" / "act4.json").write_text(
            json.dumps({"lines": act}), "utf-8")
        (d / "draft.json").write_text(json.dumps({"lines": [
            dict(act[0], id=258), dict(act[1], id=259)]}), "utf-8")
        D.beat_times = lambda p: {"ordered": [("B130", 6700.0),
                                              ("B131", 6829.0)]}
        D.parse_reveal_map = lambda p: []

        def measure(a, b):
            return ([(max(a, 6908.96), min(b, 7059.96), ["black"])]
                    if a < 7060 and b > 6908.96 else [])
        got = W.fix_windows_in_draft("x", d, measure=measure)
        dr = json.loads((d / "draft.json").read_text("utf-8"))["lines"]
        ac = json.loads((d / "draft.json.d" / "act4.json").read_text(
            "utf-8"))["lines"]
        from pipeline.draft import parse_ts
        ok = (got == ["259"] and dr[1]["clip_end"] == ac[1]["clip_end"]
              and parse_ts(dr[1]["clip_end"]) <= 6908.96 + 1e-3
              and dr[0]["clip_start"] == "01:53:49.667")
        return ok, (f"outro moved off the credits to {dr[1]['clip_start']}-"
                    f"{dr[1]['clip_end']} in both files" if ok else
                    f"got {got}; draft {dr[1]}; act {ac[1]}")
    finally:
        D.beat_times, D.parse_reveal_map = real
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    bad = 0
    for name, fn in (("HOLD-SYNC", test_sync),
                     ("UNWATCHABLE-IN-RESOLVE", test_unwatchable_in_resolve)):
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        print(f'{"PASS" if ok else "FAIL"}  {name:<22} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_hold_sync: all pass" if not bad else
          f"test_hold_sync: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
