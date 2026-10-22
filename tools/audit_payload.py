# -*- coding: utf-8 -*-
"""audit_payload.py - kiem tra NHAN tu khai bang mot subagent ngu canh moi.

`payload` va `hook_question` la truong TU KHAI. Nguoi viet co the gan nhan
`stake` cho mot dong ta canh thuan tuy va [PAYLOAD-MIX] van xanh - dung nhu
B9 (fill mu truoc comprehension). Cong do KHONG tu dung duoc; audit nay LA
mot phan cua cong.

    python tools/audit_payload.py <project>              # in de bai cho auditor
    python tools/audit_payload.py <project> --score f.json  # cham diem

Quy tac: >3 nhan sai tren 20 dong -> vong draft do TRUOT.
"""
from __future__ import annotations
import argparse, io, json, os, random, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

FAIL_AT = 3          # nhieu hon 3 nhan sai -> truot
SAMPLE = 20

DEFS = """\
payload definitions (the ONLY five legal values):

  stake      - the line says what it costs, what is risked, or what cannot be
               undone. A number is the strongest form.
  reasoning  - the line says what a character is thinking and WHY they act.
  judgment   - the narrator's own opinion, an aside, a joke, or a remark about
               what the filmmaking MEANS.
  loop       - the line makes a promise that pulls the viewer to the next line.
               It does NOT need a question mark; a flat promise counts
               ("Now meet the other one.").
  rest       - pure description of what is on screen. A breath. No cost, no
               reason, no opinion, no promise.

The decisive test for `rest`: delete the line. Does anybody in the story lose
anything, or does the viewer lose a reason to keep watching? If neither, it is
`rest`, whatever it is labelled.
"""


def _load(project):
    pdir = config.project_dir(project)
    return pdir, json.load(io.open(pdir / "draft.json", encoding="utf-8-sig"))


def emit(project, n, seed):
    pdir, d = _load(project)
    lines = [l for l in d["lines"] if str(l.get("narration", "")).strip()]
    labelled = [l for l in lines if l.get("payload")]
    if not labelled:
        print("KHONG co dong nao mang `payload` - draft v1, khong audit duoc.")
        return 1
    rnd = random.Random(seed)
    sample = rnd.sample(labelled, min(n, len(labelled)))
    sample.sort(key=lambda l: l.get("id", 0))

    hooks = [l for l in d["lines"] if l.get("delivery") == "hook"]
    first15 = lines[:15]

    print("# AUDIT TASK - payload labels and hook question")
    print()
    print("You are auditing a recap script written by someone else. You have")
    print("not seen their instructions. Judge ONLY what the text says.")
    print()
    print(DEFS)
    print()
    print("## Part 1 - label check")
    print()
    print("For each line below, decide the payload you would assign, then say")
    print("whether the author's label is right or wrong. A label is WRONG when")
    print("the text does not actually do what the label claims - most often a")
    print("plain description labelled `stake` or `reasoning`.")
    print()
    for l in sample:
        print("id %s  [author says: %s]" % (l.get("id"), l.get("payload")))
        print("    %s" % l["narration"])
        print()

    print("## Part 2 - hook question")
    print()
    if not hooks:
        print("(no <hook> line in this draft - skip Part 2)")
    for h in hooks:
        print("HOOK line id %s:" % h.get("id"))
        print("    %s" % h.get("narration"))
        print("author's stated hook_question:")
        print("    %s" % (h.get("hook_question") or "(none)"))
    print()
    print("The first 15 narrated lines, in order, so you can see whether the")
    print("question gets answered too early:")
    print()
    for l in first15:
        print("  %s: %s" % (l.get("id"), l["narration"]))
    print()
    print("Answer two things:")
    print("  raised  - does the hook line genuinely raise that question?")
    print("  held    - is the question still unanswered after these 15 lines?")
    print()
    print("## Part 3 - the title")
    print()
    print("Title as written:")
    print("    %s" % (d.get("title") or "(none)"))
    print()
    print("A good title for this genre follows: [a role or character named by")
    print("a trait] + [an extraordinary premise stated as plain fact] +")
    print("[a consequence that is withheld]. Examples that work:")
    print('    "Students Don\'t Realise Their Teacher Is A Kungfu Legend"')
    print('    "Man Steps On Landmine & Can\'t Move For 52 Hours"')
    print('    "Bad Genius - the exam heist that crossed a time zone"')
    print("A title that is just the film\'s name, or the name plus a year,")
    print("wastes the strongest device the format has.")
    print()
    print("Judge three things, and do NOT be generous - a validator already")
    print("checked that the title contains a verb and is not '<film> (<year>)',")
    print("so those are not what you are being asked:")
    print("  premise  - does it state an extraordinary premise as fact?")
    print("  withheld - does it hold back the consequence rather than telling")
    print("             the ending?")
    print("  spoils   - does it give away a reveal it should not?")
    print()
    print("## Output - write ONLY this JSON to %s"
          % (pdir / "payload_audit.json"))
    print()
    print(json.dumps({
        "verdicts": [{"id": l.get("id"), "author": l.get("payload"),
                      "auditor": "<your label>", "ok": True,
                      "why": "<only if ok is false>"} for l in sample[:2]]
        + ["... one entry per sampled line ..."],
        "hook": {"raised": True, "held": True, "why": ""},
        "title": {"premise": True, "withheld": True, "spoils": False,
                  "why": ""},
    }, indent=2, ensure_ascii=False))
    return 0


def score(project, path):
    pdir, d = _load(project)
    a = json.load(io.open(path, encoding="utf-8-sig"))
    v = [x for x in a.get("verdicts", []) if isinstance(x, dict)]
    wrong = [x for x in v if not x.get("ok")]
    print("sampled      : %d" % len(v))
    print("mislabelled  : %d" % len(wrong))
    for x in wrong:
        print("   id %-5s author=%-10s auditor=%-10s %s"
              % (x.get("id"), x.get("author"), x.get("auditor"),
                 x.get("why", "")))
    hk = a.get("hook") or {}
    print("hook raised  : %s" % hk.get("raised"))
    print("hook held    : %s" % hk.get("held"))
    if hk.get("why"):
        print("   %s" % hk["why"])

    failed = False
    if len(v) < SAMPLE:
        print("INCOMPLETE: %d verdicts, expected %d. An audit that did not "
              "cover the sample is not an audit." % (len(v), SAMPLE))
        failed = True
    if len(wrong) > FAIL_AT:
        print("FAIL: %d mislabels > %d allowed. The payload gate did not "
              "really pass - the labels do not match the text." % (len(wrong), FAIL_AT))
        failed = True
    if hk and (hk.get("raised") is False or hk.get("held") is False):
        print("FAIL: the hook's stated question is not raised by the hook "
              "line, or is already answered early.")
        failed = True
    ti = a.get("title") or {}
    if ti:
        print("title premise : %s" % ti.get("premise"))
        print("title withheld: %s" % ti.get("withheld"))
        print("title spoils  : %s" % ti.get("spoils"))
        if ti.get("why"):
            print("   %s" % ti["why"])
        if ti.get("premise") is False or ti.get("withheld") is False:
            print("FAIL: the title is not a premise title, or it gives the "
                  "consequence away instead of withholding it.")
            failed = True
        if ti.get("spoils") is True:
            print("FAIL: the title spoils a reveal.")
            failed = True
    else:
        print("title        : NOT AUDITED - the verdict file has no `title` "
              "block. The verb-presence check in [HOOK] is a proxy only, so "
              "with no audit the premise-title rule is unverified.")
    if not failed:
        print("PASS: labels hold up (%d/%d wrong, limit %d)."
              % (len(wrong), len(v), FAIL_AT))
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--n", type=int, default=SAMPLE)
    ap.add_argument("--seed", type=int, default=20261020)
    ap.add_argument("--score")
    a = ap.parse_args()
    if a.score:
        return score(a.project, a.score)
    return emit(a.project, a.n, a.seed)


if __name__ == "__main__":
    sys.exit(main())
