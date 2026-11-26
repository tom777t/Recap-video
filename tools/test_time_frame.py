# -*- coding: utf-8 -*-
"""test_time_frame.py - the listener is told when the picture leaves the
present and when it comes back (owner, 26 Nov, Lost in the Stars: "người xem
dễ lộn ... quá khứ hiện tại").

  LOST-IN-THE-STARS  the shipped lines: the dream under a 70 s hold (13-15),
                     the crash flashback under a 47 s hold (57-59) are
                     flagged on the line before the hold and on the way
                     back; "The flashback shows the dive" (245) and "Back in
                     the cell" (252) pass
  SAID-PASSES        the same switches, told ("Years earlier", "In his
                     dream", "Back in", "He wakes") -> nothing
  SILENT-OPENING     a frame that opens on a long hold: a marker only in the
                     first narrated line after it is too late
  FLASH-CUT          a 2 s breath of another frame with no line -> nothing
  NO-COLUMN          a beat map without frames: the check is not made
  COLUMN-ROUNDTRIP   frame_beats writes the column; load_beats reads it;
                     assemble_beats keeps it from beat_frames.json
  REPLY-PARSE        the model's reply maps to timestamps; junk is refused
  RESOLVE-ROUTES     gate_findings carries [TIME-FRAME] to resolve

    python tools/test_time_frame.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import beats_spec as BS  # noqa: E402
from pipeline import time_frame as TF  # noqa: E402
import frame_beats as FB  # noqa: E402


def L(i, note, text="", hold=0.0):
    d = {"id": i, "note": note, "narration": text}
    if hold:
        d["narration_silence_seconds"] = hold
    return d


BEATS = {"B04": {"frame": "now"}, "B05": {"frame": "imagined"},
         "B06": {"frame": "now"}, "B29": {"frame": "now"},
         "B30": {"frame": "past"}, "B31": {"frame": "now"},
         "B127": {"frame": "now"}, "B128": {"frame": "past"},
         "B129": {"frame": "past"}, "B130": {"frame": "now"}}

SHIPPED = [
    L(13, "B04", "Staring at a Polaroid of someone on a shore, he lets it "
      "fall to the floor."),
    L(14, "B05", hold=70.0),
    L(15, "B06", "A woman claiming to be his wife apologises, and Zheng "
      "backs her: passport, photos and staff agree."),
    L(57, "B29", "In the apartment, the impostor calls Man Man Muzi's best "
      "friend; He Fei says he never met her."),
    L(58, "B30", hold=47.0),
    L(59, "B31", "Chen Mai sets terms: absolute trust, no secrets, "
      "unconditional obedience."),
    L(243, "B127", "His face turns tense as she tightens her grip on the "
      "bars."),
    L(244, "B127", hold=2.0),
    L(245, "B128", "The flashback shows the dive. Two divers with torches "
      "swim toward the cage, where a diver looks out through the bars."),
    L(248, "B129", "Then He Fei fastens a small bag to the cage bars."),
    L(252, "B130", "Back in the cell, a woman stands at the bars as Muzi's "
      "call plays."),
]


def t_lits():
    got = {(p["id"], p["to"], p["announce"])
           for p in TF.switch_problems(SHIPPED, BEATS)}
    want = {(13, "imagined", True), (15, "now", False),
            (57, "past", True), (59, "now", False)}
    ok = got == want
    return ok, (f"flagged 13 (dream ahead), 15 (back), 57 (flashback "
                f"ahead), 59 (back); 245 and 252 pass" if ok
                else f"got {sorted(got)}")


def t_said():
    told = [dict(x) for x in SHIPPED]
    by = {x["id"]: x for x in told}
    by[13]["narration"] = ("He drops the Polaroid, and in his dream she "
                           "walks into the sea.")
    by[15]["narration"] = ("He wakes to a woman claiming to be his wife, "
                           "and Zheng backs her.")
    by[57]["narration"] = ("He says he never met Man Man; years earlier, a "
                           "car went off a bridge.")
    by[59]["narration"] = ("Back in the apartment, Chen Mai sets her "
                           "terms.")
    got = TF.switch_problems(told, BEATS)
    return not got, ("told switches pass" if not got else
                     f"still flagged: {[p['id'] for p in got]}")


def t_silent_opening():
    lines = [L(1, "B29", "He says he never met her."),
             L(2, "B30", hold=30.0),
             L(3, "B30", "Years earlier, a car crashes through a barrier."),
             L(4, "B31", "Back in the flat, she sets her terms.")]
    got = TF.switch_problems(lines, BEATS)
    ok = [(p["id"], p["announce"]) for p in got] == [(1, True)]
    return ok, ("the line before a 30 s silent flashback must announce it"
                if ok else f"got {got}")


def t_flash_cut():
    lines = [L(1, "B29", "He says he never met her."),
             L(2, "B30", hold=2.0),
             L(3, "B31", "She sets her terms.")]
    got = TF.switch_problems(lines, BEATS)
    # neither the 2 s insert nor the way back from it is a switch to tell
    ok = not got
    return ok, ("a 2 s breath of another frame: nothing to announce, "
                "nothing to come back from" if ok else f"got {got}")


def _proj(name: str) -> Path:
    pd = config.project_dir(name)
    shutil.rmtree(pd, ignore_errors=True)
    pd.mkdir(parents=True)
    return pd


MAP = """# x - Beat List Proposal (MACHINE)

KEY: id | ts | what happens | chars | kind

B01 | 00:04:16 | He watches the news | He Fei | setup
B02 | 00:05:17 | Dreamlike memory of a beach | He Fei | emotion
B03 | 00:06:26 | A woman claims to be his wife | He Fei | action
"""


def t_no_column():
    import write_api as WA
    pd = _proj("_selftest_timeframe")
    try:
        (pd / "beats_proposal.md").write_text(MAP, encoding="utf-8")
        (pd / "draft.json").write_text(json.dumps({"lines": [
            L(1, "B01", "He watches."), L(2, "B02", hold=40.0),
            L(3, "B03", "A woman arrives.")]}), encoding="utf-8")
        b = BS.load_beats(pd)
        got = WA.time_frame_findings("_selftest_timeframe")
    finally:
        shutil.rmtree(pd, ignore_errors=True)
    ok = all(x["frame"] is None for x in b.values()) and got == []
    return ok, ("no frame column -> not checked (a note says how to mark "
                "the frames)" if ok else f"{b} {got}")


def t_roundtrip():
    import write_api as WA
    pd = _proj("_selftest_timeframe")
    try:
        (pd / "beats_proposal.md").write_text(MAP, encoding="utf-8")
        rows = FB.beat_rows(MAP)
        frames, _ = FB.frames_from_reply(
            {"frames": [{"beat": "B02", "frame": "imagined", "why": "x"}]},
            rows)
        (pd / "beat_frames.json").write_text(json.dumps(frames),
                                             encoding="utf-8")
        FB.apply(pd, frames)
        b = BS.load_beats(pd)
        again = FB.with_column((pd / "beats_proposal.md").read_text(
            encoding="utf-8"), frames)
        (pd / "draft.json").write_text(json.dumps({"lines": [
            L(1, "B01", "He watches the news."), L(2, "B02", hold=40.0),
            L(3, "B03", "A woman arrives.")]}), encoding="utf-8")
        fnd = WA.time_frame_findings("_selftest_timeframe")
        # assemble_beats keeps the frames when it rebuilds the map
        d = pd / "beats.json.d"
        d.mkdir()
        (d / "chunk1.json").write_text(json.dumps({"chunk": 1, "beats": [
            {"ts": "00:04:16", "what": "He watches the news",
             "chars": ["He Fei"], "kind": "setup"},
            {"ts": "00:05:17", "what": "Dreamlike memory of a beach",
             "chars": ["He Fei"], "kind": "emotion"}]}), encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "tools" /
                            "assemble_beats.py"), "_selftest_timeframe",
                            "--out", "rebuilt.md"], capture_output=True,
                           text=True)
        rebuilt = (pd / "rebuilt.md").read_text(encoding="utf-8") \
            if (pd / "rebuilt.md").exists() else r.stderr
    finally:
        shutil.rmtree(pd, ignore_errors=True)
    ok = (b["B02"]["frame"] == "imagined" and b["B01"]["frame"] == "now"
          and again.count("| imagined") == 1
          and [f["ids"] for f in fnd] == [["1"], ["3"]]
          and "| emotion | imagined" in rebuilt
          and "| setup | now" in rebuilt)
    return ok, ("column written, read, idempotent, kept by assemble_beats; "
                "the check fires on the marked map" if ok else
                f"{b} | {fnd} | {rebuilt[-300:]}")


def t_reply_parse():
    rows = FB.beat_rows(MAP)
    frames, probs = FB.frames_from_reply({"frames": [
        {"beat": "B2", "frame": "imagined", "why": "dream"},
        {"beat": "B09", "frame": "past", "why": "x"},
        {"beat": "B01", "frame": "now", "why": "x"},
        {"beat": "hello", "frame": "past", "why": "x"}]}, rows)
    ok = frames == {"00:05:17": "imagined"} and len(probs) == 3
    return ok, ("B2 -> 00:05:17 imagined; an unknown beat, a 'now' and a "
                "non-id are refused" if ok else f"{frames} {probs}")


def t_routes():
    src = (ROOT / "tools" / "write_api.py").read_text(encoding="utf-8")
    ok = "+ time_frame_findings(project))" in src
    return ok, "gate_findings -> resolve" if ok else "not routed"


TESTS = [("LOST-IN-THE-STARS", t_lits), ("SAID-PASSES", t_said),
         ("SILENT-OPENING", t_silent_opening), ("FLASH-CUT", t_flash_cut),
         ("NO-COLUMN", t_no_column), ("COLUMN-ROUNDTRIP", t_roundtrip),
         ("REPLY-PARSE", t_reply_parse), ("RESOLVE-ROUTES", t_routes)]


def main() -> int:
    bad = 0
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:<18} {msg}")
    print("-" * 60)
    print("test_time_frame: all pass" if not bad else
          f"test_time_frame: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
