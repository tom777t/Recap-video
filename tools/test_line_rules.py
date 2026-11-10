# -*- coding: utf-8 -*-
"""test_line_rules.py - a line that would fail a draft gate is refused
BEFORE it is saved, not found by the gate run after.

Furious 7: the hand fix of line 184 fitted its slot, was saved, and only
then did the gates find "dom's voice comes" x2 ([TIC-REPETITION]) - one
more round for the user, as with every misspelt name and lyric before it.

  TIC-SAME-AS-GATE    motif_gates.tic_phrases (what the write-time checks
                      use) finds exactly the repeated phrases the gate
                      reports, on every real draft in projects/
  LINE-RULES          a phrase shared with another line, a misspelt listed
                      name and a quoted song are each named; quoted words
                      and names are not counted; a clean line has none; a
                      repeat the line already had is not refused again
  FIX-LINE-REFUSES    fix_line: a tic text is refused before writing; a text
                      that breaks a gate the per-line rules do not cover is
                      written, found by the gates, and UNDONE byte for byte
  RESOLVE-REFUSES     resolve: a rewrite that repeats another line's phrase
                      is not saved, and goes back to the reviser with why;
                      a rewrite taking a phrase another rewrite of the same
                      round gives up is saved, whatever the order
  GUARD-BY-LINE       fix_line's after-save check is per gate and per line:
                      closing this line's finding inside an aggregate
                      message is not "new"; a gate newly naming this line is,
                      even if another line had it; a fitting fix on a draft
                      with other open findings is SAVED

Run:  python tools/test_line_rules.py      (exit 0 = all pass)
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import line_rules as LR  # noqa: E402
from pipeline import motif_gates as MG  # noqa: E402


def test_tic_same_as_gate():
    bad, n = [], 0
    for d in sorted((ROOT / "projects").iterdir()):
        if d.name.startswith("_") or not (d / "draft.json").exists():
            continue
        try:
            dr = json.loads((d / "draft.json").read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        lines = dr.get("lines") or []
        rep = MG.motif_report(dict(dr, _dir=str(d)), d)["stats"]
        names = MG.tic_names(d, [str(x.get("narration") or "")
                                 for x in lines if str(x.get("narration")
                                                       or "").strip()])
        cnt: dict = {}
        for ln in lines:
            if not str(ln.get("narration") or "").strip():
                continue
            for ph in MG.tic_phrases(ln.get("narration"), names):
                cnt[ph] = cnt.get(ph, 0) + 1
        mine = sum(1 for v in cnt.values()
                   if v > int(getattr(config, "TIC_NGRAM_MAX", 1)))
        n += 1
        if mine != rep.get("repeated_ngrams"):
            bad.append(f"{d.name}: helper {mine}, gate "
                       f"{rep.get('repeated_ngrams')}")
        # and line by line: for each phrase the gate names, line_rules
        # (given every other line) names the same lines
        by_id = {str(x.get("id")): x for x in lines}
        for ph, _k, ids in rep.get("top_repeated") or []:
            for lid in ids[:3]:
                ln = by_id.get(str(lid))
                if ln is None:
                    continue
                probe = [dict(x, narration="") if x is ln else x
                         for x in lines]
                got = LR.problems(d, probe, lid, ln["narration"])
                if not any(f'"{ph}"' in g for g in got):
                    bad.append(f"{d.name} line {lid}: gate names \"{ph}\", "
                               f"line_rules does not ({got[:2]})")
    return (not bad and n > 0), (f"{n} real drafts: the helper counts the "
                                 f"gate's repeated phrases exactly, and "
                                 f"line_rules names them on the gate's "
                                 f"lines" if not bad
                                 else "; ".join(bad[:4]))


def _fixture():
    import test_write_plan as TWP
    TWP._setup()
    return TWP


def test_line_rules():
    TWP = _fixture()
    pdir = TWP.PDIR
    from pipeline import name_spelling as NS
    names = sorted(n for n in NS.known_names(pdir) if len(n) >= 5)
    nm = names[0]
    acc = {"a": "á", "e": "é", "o": "ó", "i": "í"}
    i = next(i for i, c in enumerate(nm) if i and c in acc)
    wrong = nm[:i] + acc[nm[i]] + nm[i + 1:]
    lines = [{"id": 1, "narration": "The garage door slams behind the "
                                    "crew tonight."},
             {"id": 2, "narration": "Placeholder."}]
    tic = LR.problems(pdir, lines, 2, "Later the garage door slams again.")
    quoted = LR.problems(pdir, lines, 2,
                         "He shouts \"the garage door slams\" at them.")
    nmok = LR.problems(pdir, lines, 2, f"{wrong} waits at the track.")
    clean = LR.problems(pdir, lines, 2, "A new car waits at the track.")
    self_ = LR.problems(pdir, lines, 1, lines[0]["narration"])
    # a line that ALREADY shares a phrase keeps it in a rewrite: not new
    lines3 = lines + [{"id": 3, "narration": "Then the garage door slams "
                                            "and nobody moves at all."}]
    keeps = LR.problems(pdir, lines3, 3, "Again the garage door slams; "
                                          "nobody moves.")
    adds = LR.problems(pdir, lines3, 3, "The garage door slams behind the "
                                         "crew once more.")
    checks = [
        (any("[TIC-REPETITION]" in x and "line(s) 1" in x for x in tic),
         f"shared phrase named ({tic[:1]})"),
        (not quoted, f"quoted words not counted ({quoted})"),
        (any("[NAME-SPELLING]" in x for x in nmok), f"'{wrong}' named"),
        (not clean and not self_, "a clean line, and a line against its own "
                                  "old text, pass"),
        (not keeps and any("[TIC-REPETITION]" in x for x in adds),
         f"an old repeat kept is not refused, a new one is ({keeps}, "
         f"{adds[:1]})"),
    ]
    bad = [w for ok, w in checks if not ok]
    return not bad, ("; ".join(w for _, w in checks) if not bad
                     else "FAILED: " + "; ".join(bad))


def _slot_draft():
    import test_write_slots as TWS
    TWS.test_draft_slots()
    return TWS


def test_fix_line_refuses():
    TWS = _slot_draft()
    import fix_line as FL
    import write_api as W
    pdir = TWS.PDIR
    owner = W.act_of_lines(pdir)
    slot_of = W.slots_of_lines(pdir, owner)
    d = json.loads((pdir / "draft.json").read_text(encoding="utf-8"))
    names = MG._load_names(pdir)[0]
    # a line, and another line holding a counted phrase it can borrow
    src = next(l for l in d["lines"] if MG.tic_phrases(l.get("narration"),
                                                      names))
    ph = sorted(MG.tic_phrases(src["narration"], names))[0]
    tgt = next(l for l in d["lines"] if l["id"] != src["id"]
               and str(l["id"]) in slot_of
               and slot_of[str(l["id"])]["role"] in ("action", "bridge")
               and not slot_of[str(l["id"])].get("after_skip")
               and not slot_of[str(l["id"])].get("transition")
               and not slot_of[str(l["id"])].get("anchor")
               and not slot_of[str(l["id"])].get("peak")
               and slot_of[str(l["id"])]["max_words"] >= 9)
    sl = slot_of[str(tgt["id"])]
    words = ("he waits there and " + ph + " and the night goes on").split()
    n = max(sl["min_words"], min(sl["max_words"], len(words)))
    pad = (words + ["on"] * 40)[:n]
    text = " ".join(pad).capitalize() + "."
    snap = FL._snapshot(pdir)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc1 = FL.main(["--project", TWS.PROJ, "--line", str(tgt["id"]),
                       "--text", text])
    same1 = FL._snapshot(pdir) == snap
    ok1 = rc1 == 2 and "[TIC-REPETITION]" in buf.getvalue() and same1
    # the gate guard: with the per-line rules out of the way, the REAL gate
    # run finds the tic after writing, and the change is undone
    real = LR.problems
    LR.problems = lambda *a, **k: []
    buf2 = io.StringIO()
    try:
        with redirect_stdout(buf2):
            rc2 = FL.main(["--project", TWS.PROJ, "--line", str(tgt["id"]),
                           "--text", text])
    finally:
        LR.problems = real
    same2 = FL._snapshot(pdir) == snap
    ok2 = rc2 == 2 and "TIC-REPETITION" in buf2.getvalue() and same2 \
        and "as they were" in buf2.getvalue()
    ok = ok1 and ok2
    return ok, (f"line {tgt['id']} borrowing \"{ph}\": refused before "
                f"writing; past the per-line rules, the gate run finds it and "
                f"every file is restored byte for byte" if ok else
                f"pre-check rc {rc1} same {same1}: {buf.getvalue()[-300:]} | "
                f"guard rc {rc2} same {same2}: {buf2.getvalue()[-400:]}")


def _resolve_with(TWP, W, rewrites: list):
    """The resolve fixture with line 3 holding "garage door slams"; the
    reviser answers every finding and sends `rewrites`."""
    TWP._resolve_fixture()
    act = TWP.PDIR / "draft.json.d" / "act1.json"
    o = json.loads(act.read_text(encoding="utf-8"))
    o["lines"][2]["narration"] = "The garage door slams shut at dawn."
    act.write_text(json.dumps(o), encoding="utf-8")
    W._assemble(TWP.PROJ)
    TWP._resolve_fixture_artifacts()

    def reply(cid, p):
        body = p["messages"][0]["content"]
        keys = [x.split(" | ")[0] for x in
                body.split("# OPEN FINDINGS")[1].strip().splitlines()
                if x.startswith(("F", "G"))]
        return TWP.msg({"lines": rewrites, "responses": [
            {"key": k, "status": "ANSWERED", "text": "kept for this test"}
            for k in keys]})
    c = TWP.Client(None, reply)
    real_gf = W.gate_findings
    W.gate_findings = lambda project, wide=None: []
    try:
        _rc, out = TWP._run(c, "resolve", "--project", TWP.PROJ)
    finally:
        W.gate_findings = real_gf
    t = {l["id"]: l["narration"] for l in TWP._j(
        TWP.PDIR / "draft.json")["lines"]}
    again = (c.batches[1][0]["params"]["messages"][0]["content"]
             if len(c.batches) > 1 else "")
    return t, out, again


def test_resolve_refuses():
    TWP = _fixture()
    import write_api as W
    take = {"id": 4, "narration": "Again the garage door slams on them."}
    give = {"id": 3, "narration": "A quiet dawn settles over the city."}
    t, out, again = _resolve_with(TWP, W, [take])
    ok1 = (t[4].startswith("Original sentence number 4")
           and "NOT saved" in out and "[TIC-REPETITION]" in out
           and "[TIC-REPETITION]" in again)
    # order: line 4 takes the phrase line 3 gives up IN THE SAME ROUND,
    # line 4 listed first - both saved
    t2, out2, _a = _resolve_with(TWP, W, [take, give])
    ok2 = (t2[4] == take["narration"] and t2[3] == give["narration"]
           and "line 4 NOT saved" not in out2)      # in the FIRST round
    ok = ok1 and ok2
    return ok, ("a rewrite repeating another line's phrase is not saved and "
                "goes back with why; one taking a phrase another rewrite "
                "gives up is saved, listed first" if ok else
                f"alone: line 4 {t[4]!r}; with line 3: {t2.get(4)!r} / "
                f"{t2.get(3)!r}; {out[-250:]} || {out2[-250:]}")


def test_guard_by_line():
    import fix_line as FL
    agg_b = "[COLD-READ] 2 of 40 finding(s) UNRESOLVED: clarity@38, clarity@91"
    agg_a = "[COLD-READ] 1 of 40 finding(s) UNRESOLVED: clarity@91"
    sp_b = "[SAME-POINT] 2 of 9 candidate pair(s): 42+43; 56+57"
    tic_b = '[TIC-REPETITION] 1 phrase(s): "a b c" x2 (lines 61, 47)'
    tic_a = '[TIC-REPETITION] 1 phrase(s): "d e f" x2 (lines 61, 14)'
    cases = [
        (FL._new_errors([agg_b, sp_b], [agg_a, sp_b.replace("2 of", "1 of")],
                        "38") == [], "closing this line's finding inside an "
                                     "aggregate is not a new error"),
        (FL._new_errors(["[X] line 12 carries narration"],
                        ["[X] line 12 carries narration",
                         "[X] line 40 carries narration"], "40") ==
         ["[X] line 40 carries narration"],
         "a gate newly naming THIS line is new, though another line had it"),
        (FL._new_errors([tic_b], [tic_a], "61") == [],
         "a gate that already named the line is not new"),
        (FL._new_errors([], ["Audit failed hard: 1 BINDING-VIOLATION(s)"],
                        "5") == [], "an error naming no line is not judged"),
    ]
    bad = [w for ok, w in cases if not ok]
    if bad:
        return False, "FAILED: " + "; ".join(bad)
    # end to end: a fitting fix is SAVED on a draft whose gates already
    # report other findings (aggregate messages that shrink with it)
    TWS = _slot_draft()
    import write_api as W
    pdir = TWS.PDIR
    owner = W.act_of_lines(pdir)
    slot_of = W.slots_of_lines(pdir, owner)
    d = json.loads((pdir / "draft.json").read_text(encoding="utf-8"))
    tgt = next(l for l in d["lines"] if str(l["id"]) in slot_of
               and slot_of[str(l["id"])]["role"] == "action"
               and not any(slot_of[str(l["id"])].get(k) for k in (
                   "transition", "anchor", "peak", "after_skip",
                   "opens_loop")))
    w = tgt["narration"].split()
    w[2] = "quietly"
    text = " ".join(w)
    lid = str(tgt["id"])
    seq = iter([(1, [f"[COLD-READ] 2 of 40 UNRESOLVED: clarity@{lid}, "
                     f"clarity@3", "[SAME-POINT] 1 of 9 pair(s): 5+6"]),
                (1, ["[COLD-READ] 1 of 40 UNRESOLVED: clarity@3",
                     "[SAME-POINT] 1 of 9 pair(s): 5+6"])])
    real = W.run_gates
    W.run_gates = lambda project: next(seq)
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = FL.main(["--project", TWS.PROJ, "--line", lid, "--text",
                          text])
    finally:
        W.run_gates = real
    now = next(l["narration"] for l in json.loads(
        (pdir / "draft.json").read_text(encoding="utf-8"))["lines"]
        if str(l["id"]) == lid)
    ok = now == text and "saved" in buf.getvalue()
    return ok, ("per gate and per line, not by message text; a fix is kept "
                "on a draft that already has other findings" if ok else
                f"rc {rc}: {buf.getvalue()[-400:]}")


TESTS = {
    "TIC-SAME-AS-GATE": test_tic_same_as_gate,
    "LINE-RULES": test_line_rules,
    "FIX-LINE-REFUSES": test_fix_line_refuses,
    "RESOLVE-REFUSES": test_resolve_refuses,
    "GUARD-BY-LINE": test_guard_by_line,
}

if __name__ == "__main__":
    import shutil
    import tag_batch as TB
    saved = TB.CLIENT_FACTORY
    bad = 0
    try:
        for name, fn in TESTS.items():
            try:
                ok, m = fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, m = False, f"{type(e).__name__}: {e}"
            print(f"{'PASS' if ok else 'FAIL'}  {name:<18} {m}")
            bad += not ok
    finally:
        TB.CLIENT_FACTORY = saved
        shutil.rmtree(config.project_dir("_selftest_writeplan"),
                      ignore_errors=True)
    print("-" * 60)
    print(f"test_line_rules: {bad} FAILURE(S)" if bad
          else "test_line_rules: all pass")
    sys.exit(1 if bad else 0)
