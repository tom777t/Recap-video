# -*- coding: utf-8 -*-
"""audit_punchup.py - FACT AUDIT + SPOILER AUDIT for a punch-up pass.

    python tools/audit_punchup.py <project> --before draft_prepunch.json
    python tools/audit_punchup.py <project> --score payload/punchup_audit.json

WHY THIS EXISTS. A punch-up pass rewrites flat lines "in voice", and voice is
exactly where invention gets in. Measured on ten hand-written sample pairs,
6 of 10 carried an error that no existing gate could see:

  - a character named who is not in the shot (named a man "Kamata" 28 minutes
    before Kamata first appears)
  - invented durations - "for months", "all night" - in no tag or transcript
  - a reveal foreshadowed before its land ("that is the part that costs Han his
    life", 7.6 minutes before the death lands)
  - a mechanical detail half-right: the engine swap is tagged, whose car it
    came from is not

[REVEAL-TIMING] cannot catch the third class at all. It is a literal keyword
scan, and foreshadowing contains no keywords - "costs him his life" shares no
term with R2's hold list. A human reader catches it instantly. So the auditor
is a reader, with the evidence in front of it, and it runs on EVERY changed
line rather than a sample: a punch-up pass that invents one fact in forty is
still a draft that says something untrue.

Two verdicts per changed line:
  fact    - every claim traceable to tags / transcript / beat map, or reject
  spoiler - states, implies or FORESHADOWS no reveal before its land, or reject

Either rejection reverts that line to its pre-punch text. The round is not
failed wholesale, because one bad line out of forty should cost one line.
"""
from __future__ import annotations
import argparse, io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

MAX_SEG = 30.0        # transcript segments longer than this are untrustworthy


def pt(ts) -> float:
    p = [float(x) for x in str(ts).split(":")]
    while len(p) < 3:
        p.insert(0, 0.0)
    return p[0] * 3600 + p[1] * 60 + p[2]


def _load(p):
    return json.load(io.open(p, encoding="utf-8-sig"))


def emit(project: str, before_path: str, limit: int) -> int:
    pdir = config.project_dir(project)
    after = _load(pdir / "draft.json")
    before = _load(before_path)
    bmap = {l.get("id"): l for l in before.get("lines", [])}

    try:
        shots = _load(pdir / "shots.json")["shots"]
    except Exception:
        shots = _load(pdir / "shots_machine.json")["shots"]
    by_cs = {s["clip_start"]: s for s in shots}
    try:
        segs = [s for s in _load(pdir / "transcript.json").get("segments", [])
                if isinstance(s.get("start"), (int, float))
                and float(s["end"]) - float(s["start"]) <= MAX_SEG]
    except Exception:
        segs = []

    from pipeline.draft import parse_reveal_map
    reveals = parse_reveal_map(project)

    changed = []
    for ln in after.get("lines", []):
        old = bmap.get(ln.get("id"))
        if old is None:
            continue
        a, b = str(old.get("narration", "")), str(ln.get("narration", ""))
        if a.strip() != b.strip():
            changed.append((ln, old))
    if limit:
        changed = changed[:limit]

    print("# PUNCH-UP AUDIT - fact and spoiler")
    print()
    print("You are auditing lines that another writer rewrote to make them more")
    print("engaging. You have not seen their instructions. Your job is to find")
    print("anything they made up and anything they gave away early.")
    print()
    print("Judge ONLY against the evidence printed under each line. If a claim")
    print("is not in the tag, the transcript or the beat, it is NOT supported -")
    print("however plausible it sounds, and however much it improves the line.")
    print()
    print("## The two tests")
    print()
    print("FACT. Reject if the new line asserts anything the evidence does not")
    print("carry. The classes that actually went wrong on real samples:")
    print("  - a NAME for someone the shot's `chars` does not name")
    print("  - a DURATION or frequency: 'for months', 'all night', 'every week'")
    print("  - a CAUSE presented as fact when the evidence shows only sequence")
    print("  - a mechanical/physical detail not in the tag")
    print("  - numbers, amounts, relationships nobody stated")
    print("Narrator OPINION is not a fact claim and must NOT be rejected as one")
    print("('it is the best idea the film has' is a view; 'the engine came from")
    print("Han's car' is a claim).")
    print()
    print("SPOILER. Each reveal below has a LAND time. Reject the line if it")
    print("states, implies or FORESHADOWS that reveal and the line sits before")
    print("that land. Indirect phrasing counts - this is the whole point of")
    print("asking a reader instead of a keyword scan. Examples of indirect")
    print("foreshadowing that must be rejected:")
    print("  - 'that is the part that costs him his life' before a death lands")
    print("  - 'he has been doing it for months' before a theft is revealed")
    print("  - 'the last time anyone sees him happy' before a death")
    print("  - 'he would regret that' pointing at an unrevealed consequence")
    print("A line may freely state anything whose reveal has ALREADY landed.")
    print()
    print("## REVEAL MAP")
    if not reveals:
        print("  (no reveal map on this project - SPOILER test cannot run, and")
        print("   you must say so in the `note` field rather than passing it)")
    for r in reveals:
        print("  %-4s lands at %-11s (%.0fs). Protected: %s"
              % (r["id"], r["land_ref"], r["land_sec"], ", ".join(r["holds"][:8])
                 + (" ..." if len(r["holds"]) > 8 else "")))
    print()
    print("## %d CHANGED LINE(S)" % len(changed))
    print()
    for ln, old in changed:
        cs = ln.get("clip_start")
        t = pt(cs) if cs else -1
        print("-" * 68)
        print("LINE %s   at %s (%.0fs)" % (ln.get("id"), cs, t))
        pend = [r["id"] for r in reveals if t < r["land_sec"]]
        if pend:
            print("  NOT YET LANDED at this point: %s" % ", ".join(pend))
        else:
            print("  every reveal has already landed here")
        print("  BEFORE: %s" % str(old.get("narration", "")).strip())
        print("  AFTER : %s" % str(ln.get("narration", "")).strip())
        s = by_cs.get(cs)
        if s:
            print("  EVIDENCE chars : %s"
                  % (", ".join(s.get("chars") or []) or "(none named)"))
            print("  EVIDENCE action: %s" % str(s.get("action", "")).strip())
        else:
            print("  EVIDENCE: no catalogued shot for this window")
        if cs and ln.get("clip_end"):
            a, b = pt(cs), pt(ln["clip_end"])
            sp = [x for x in segs if x["end"] > a and x["start"] < b]
            if sp:
                for x in sp:
                    print("  EVIDENCE speech %.1f: %s"
                          % (x["start"], str(x.get("text", "")).strip()[:160]))
            else:
                print("  EVIDENCE speech: none in this window")
        print("  beat: %s" % ln.get("note"))
        print()

    out = pdir / "punchup_audit.json"
    print("## OUTPUT - write ONLY this JSON to %s" % out)
    print()
    print(json.dumps({
        "verdicts": [
            {"id": (changed[0][0].get("id") if changed else 1),
             "fact_ok": True, "spoiler_ok": True, "why": ""},
            "... one entry per changed line, all %d of them ..." % len(changed),
        ],
        "note": "",
    }, indent=2, ensure_ascii=False))
    return 0


def score(project: str, path: str, before_path: str | None) -> int:
    pdir = config.project_dir(project)
    a = _load(path)
    after = _load(pdir / "draft.json")
    v = [x for x in a.get("verdicts", []) if isinstance(x, dict)]
    ids_changed = set()
    if before_path:
        bmap = {l.get("id"): l for l in _load(before_path).get("lines", [])}
        for ln in after.get("lines", []):
            o = bmap.get(ln.get("id"))
            if o is not None and str(o.get("narration", "")).strip() != \
                    str(ln.get("narration", "")).strip():
                ids_changed.add(ln.get("id"))

    bad_fact = [x for x in v if x.get("fact_ok") is False]
    bad_spoil = [x for x in v if x.get("spoiler_ok") is False]
    print("audited        : %d line(s)" % len(v))
    print("fact rejects   : %d" % len(bad_fact))
    for x in bad_fact:
        print("   id %-5s %s" % (x.get("id"), x.get("why", "")[:150]))
    print("spoiler rejects: %d" % len(bad_spoil))
    for x in bad_spoil:
        print("   id %-5s %s" % (x.get("id"), x.get("why", "")[:150]))
    if a.get("note"):
        print("auditor note   : %s" % a["note"])

    failed = False
    if ids_changed and len(v) < len(ids_changed):
        print("INCOMPLETE: %d verdicts for %d changed lines. An audit that did "
              "not cover every edit is not an audit - the uncovered edits must "
              "be reverted." % (len(v), len(ids_changed)))
        failed = True
    revert = sorted({x.get("id") for x in bad_fact + bad_spoil})
    if revert:
        print()
        print("REVERT these line(s) to their pre-punch text: %s"
              % ", ".join(str(r) for r in revert))
        failed = True
    if not failed:
        print("PASS: every edit is supported and no reveal is given away early.")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--before", help="pre-punch draft json")
    ap.add_argument("--score", help="auditor verdict json")
    ap.add_argument("--limit", type=int, default=0)
    # --out writes the task as UTF-8 DIRECTLY. Redirecting stdout with `>` in
    # PowerShell produces UTF-16LE, which the subagent's file reader rejects as
    # binary; the first auditor run had to decode the file itself before it
    # could start. A tool whose output is meant to be read by another process
    # should not depend on the shell's encoding default.
    ap.add_argument("--out", help="write the task to this path as UTF-8")
    a = ap.parse_args()
    if a.score:
        return score(a.project, a.score, a.before)
    if not a.before:
        ap.error("need --before <pre-punch draft> to know what changed")
    if a.out:
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = emit(a.project, a.before, a.limit)
        io.open(a.out, "w", encoding="utf-8").write(buf.getvalue())
        print("wrote %s (%d bytes, utf-8)"
              % (a.out, len(buf.getvalue().encode("utf-8"))))
        return rc
    return emit(a.project, a.before, a.limit)


if __name__ == "__main__":
    sys.exit(main())
