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
                      and names are not counted; a clean line has none
  FIX-LINE-REFUSES    fix_line: a tic text is refused before writing; a text
                      that breaks a gate the per-line rules do not cover is
                      written, found by the gates, and UNDONE byte for byte
  RESOLVE-REFUSES     resolve: a rewrite that repeats another line's phrase
                      is not saved, and goes back to the reviser with why

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
    return (not bad and n > 0), (f"{n} real drafts: the helper counts the "
                                 f"gate's repeated phrases exactly" if not bad
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
    checks = [
        (any("[TIC-REPETITION]" in x and "line(s) 1" in x for x in tic),
         f"shared phrase named ({tic[:1]})"),
        (not quoted, f"quoted words not counted ({quoted})"),
        (any("[NAME-SPELLING]" in x for x in nmok), f"'{wrong}' named"),
        (not clean and not self_, "a clean line, and a line against its own "
                                  "old text, pass"),
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


def test_resolve_refuses():
    TWP = _fixture()
    TWP._resolve_fixture()
    import write_api as W

    def reply(cid, p):
        body = p["messages"][0]["content"]
        keys = [x.split(" | ")[0] for x in
                body.split("# OPEN FINDINGS")[1].strip().splitlines()
                if x.startswith(("F", "G"))]
        return TWP.msg({"lines": [
            {"id": 4, "narration": "Original sentence number nine, told "
                                     "once more about the cars."}],
            "responses": [{"key": k, "status": "ANSWERED",
                           "text": "kept as written for this test"}
                          for k in keys]})
    c = TWP.Client(None, reply)
    real_gf = W.gate_findings
    W.gate_findings = lambda project, wide=None: []
    try:
        rc, out = TWP._run(c, "resolve", "--project", TWP.PROJ)
    finally:
        W.gate_findings = real_gf
    t = {l["id"]: l["narration"] for l in TWP._j(
        TWP.PDIR / "draft.json")["lines"]}
    again = (c.batches[1][0]["params"]["messages"][0]["content"]
             if len(c.batches) > 1 else "")
    ok = (t[4].startswith("Original sentence number 4")
          and "NOT saved" in out and "[TIC-REPETITION]" in out
          and "[TIC-REPETITION]" in again)
    return ok, ("a rewrite repeating another line's phrase is not saved and "
                "goes back with why" if ok else
                f"line 4 now {t[4]!r}; out {out[-400:]}")


TESTS = {
    "TIC-SAME-AS-GATE": test_tic_same_as_gate,
    "LINE-RULES": test_line_rules,
    "FIX-LINE-REFUSES": test_fix_line_refuses,
    "RESOLVE-REFUSES": test_resolve_refuses,
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
