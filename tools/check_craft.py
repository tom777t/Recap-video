# -*- coding: utf-8 -*-
"""check_craft.py - chay rieng cac cong THU VIET (PHASE 1) tren mot draft.

    python tools/check_craft.py <project>            # chay tren projects/<p>/draft.json
    python tools/check_craft.py --file <path>        # chay tren mot file bat ky
    python tools/check_craft.py --selftest           # hai chieu: NGUOI pass, MAY fail

Exit code: 0 neu khong co loi cung, 1 neu co.
"""
from __future__ import annotations
import argparse, io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.craft_gates import craft_report

HUMAN = "projects/badgenius2017/draft.json"
# 2026-10-20: cai nay TUNG tro vao projects/tokyodrift2006/draft.json - file
# SONG. Ngay khi draft do duoc viet lai cho dat, fixture am bien thanh mot
# ban PASS va self-test do sup, bao "SELF-TEST FAILURE" vi mot ly do khong
# lien quan gi den gate. Mot fixture phai la mot ban dong bang, khong phai
# mot file ma pipeline dang ghi vao.
MACHINE = "projects/tokyodrift2006/draft_v1_preCraft.json"


def _load(path):
    return json.load(io.open(path, encoding="utf-8-sig"))


def show(path, draft):
    # facts_for() reads draft["_dir"] to find film_facts.json; set it from the
    # draft's own location so the [FILM-INTRO] gate can run (same wiring the
    # validator does). Without it a draft with a film_intro block always errors
    # "no film_facts.json" even when the file sits right next to it.
    draft.setdefault("_dir", os.path.dirname(os.path.abspath(path)))
    r = craft_report(draft)
    m = r["metrics"]
    print("=" * 70)
    print(path)
    print("  schema=%s  narrated=%s  stats_enforced=%s"
          % (m.get("schema"), m.get("narrated_lines"), m.get("stats_applied")))
    print("  SD=%s  long=%s%%  punch=%s%%  openers=%s%%  judgment=%s  silence=%s"
          % (m.get("sd_words_per_line"),
             round(100 * (m.get("long_sentence_share") or 0), 1),
             round(100 * (m.get("punch_share") or 0), 1),
             round(100 * (m.get("opener_share") or 0), 1),
             m.get("judgment_lines"), m.get("silence_units")))
    print("  words=%s  beats=%s  words/beat=%s  lines/beat=%s"
          % (m.get("words"), m.get("beats_served"),
             m.get("words_per_beat"), m.get("lines_per_beat")))
    if m.get("payload"):
        print("  payload:", m["payload"],
              " rest_share=%.0f%%" % (100 * (m.get("rest_share") or 0)))
    for e in r["errors"]:
        print("  ERROR  ", e)
    for w in r["warns"]:
        print("  warn   ", w)
    for nt in r["notes"]:
        print("  note   ", nt)
    print("  -> %d error(s), %d warning(s)" % (len(r["errors"]), len(r["warns"])))
    return r


def selftest() -> int:
    """Hai chieu. Mot cong chi duoc tin khi no PASS cai dung VA FAIL cai sai."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ok = True
    print("### POSITIVE: the human reference draft, with ONE declared exception")
    # 2026-10-21: the invariant used to be "no hard gate may fire on the human
    # draft". It now has exactly one documented exception, because the VOICE
    # MODEL CHANGED. The narrator-presence bar is calibrated on SAKURA REVIEW
    # (1.82-2.35 markers/min), and measured against that model the Bad Genius
    # draft is under-voiced at 0.79/min - roughly a third of it. That is a real
    # finding about the draft, not a broken gate: the draft was written before
    # there was a voice model at all.
    # The exception is pinned to ONE gate by name. If any OTHER hard gate ever
    # fires on the human draft, that is still a broken gate and this still
    # fails - which is the part that keeps the invariant useful.
    HUMAN_EXPECTED = {"[VOICE-PRESENCE]"}
    h = show(os.path.join(root, HUMAN), _load(os.path.join(root, HUMAN)))
    _unexpected = [e for e in h["errors"]
                   if not any(e.startswith(g) for g in HUMAN_EXPECTED)]
    _missing = [g for g in HUMAN_EXPECTED
                if not any(e.startswith(g) for e in h["errors"])]
    if _unexpected:
        print("  FAIL: the gold standard tripped a hard gate that is NOT the "
              "declared exception. The GATE is wrong, not the draft:")
        for e in _unexpected:
            print("     ", e[:150])
        ok = False
    elif _missing:
        print("  FAIL: %s was declared as an expected failure on the human "
              "draft but did not fire. Either the bar moved or the draft "
              "changed - re-derive it, do not delete this check."
              % ", ".join(_missing))
        ok = False
    else:
        print("  PASS: the only hard gate firing on the human draft is "
              "[VOICE-PRESENCE], which is expected - the voice model is now "
              "SAKURA (1.82-2.35 markers/min) and this draft measures 0.79.")

    print()
    print("### NEGATIVE: the rejected machine draft must fail")
    mr = show(os.path.join(root, MACHINE), _load(os.path.join(root, MACHINE)))
    want = ["[RHYTHM]", "[SPEECH-BLIND]", "[INTRO-OUTRO]", "[NARRATOR-VOICE]",
            "[HOOK]"]
    got = {w for w in want if any(e.startswith(w) for e in mr["errors"])}
    for w in want:
        print("  %-18s %s" % (w, "FAILS as predicted" if w in got
                              else "DID NOT FIRE  <-- unexpected"))
    if set(want) != got:
        ok = False

    print()
    print("### SYNTHETIC: payload gates, both directions")
    # Mot "positive control" chi co gia tri khi no SACH va khi ty le cua no
    # giong ban nguoi. Phien ban dau cua fixture nay gom phan lon la dong DAI,
    # nen khi TRAN duoc them vao thi chinh no truot - mot fixture "tot" ma
    # khong the pass la mot fixture sai, khong phai mot cong sai.
    good = {"title": "A thief who robbed the same bank twice", "lines": []}
    bad = {"title": "Some Film (2011)", "lines": []}

    LONG = ("He counts the money twice and finds the second bag lighter than "
            "the first one was, which is the exact moment the whole plan stops "
            "being about money and starts being about which of them lied. "
            "He stops.")                      # cau dai + cau punch <=5 tu
    MED = ("The guard signs the log without looking up, and that signature is "
           "the only thing standing between them and twenty years.")
    SHORT = "Nobody moves."
    # Fixture nay phai mang ca GIONG KE: [VOICE-PRESENCE] doi 1.2-3.0
    # markers/min, va mot "positive control" khong sach thi khong chung minh
    # duoc gi. Dong OPIN xuat hien 6 lan va mang 2 marker ("I", "your"), cong
    # voi outro -> khoang 2.1/min, dung giua dai cua Sakura.
    OPIN = ("He is the kind of careful that only ever protects himself, and I "
            "would not trust him with your coat.")

    for i in range(1, 61):
        # 5 dong dai tren 60 -> ~7% cau >=30 tu (nguoi 4.3%, tran 12%)
        if i % 12 == 0:
            text, pay = LONG, "stake"
        elif i % 10 == 0:
            text, pay = MED, "loop"
        elif i % 9 == 0:
            text, pay = OPIN, "judgment"       # 6/60 = 10% (nguoi 7.5%, tran 15%)
        elif i % 5 == 0:
            text, pay = SHORT, "rest"          # 12/60 = 20% (tran 25%)
        elif i % 3 == 0:
            text, pay = MED, "reasoning"
        else:
            text, pay = SHORT if i % 7 == 0 else MED, "stake"
        good["lines"].append({
            "id": i, "clip_start": "00:00:01.0", "clip_end": "00:00:05.0",
            "delivery": "normal", "payload": pay, "narration": text,
            "note": "B%02d" % (((i - 1) // 2) + 1)})   # 30 beat -> 2.0 dong/beat
        bad["lines"].append({
            "id": i, "clip_start": "00:00:01.0", "clip_end": "00:00:05.0",
            "delivery": "normal", "payload": "rest",
            "narration": "He walks across the room and opens the door slowly."})

    good["lines"][0].update(delivery="hook", payload="loop",
                            hook_question="Why does the same bank let him in twice?")
    good["lines"][1].update(delivery="intro", payload="rest")
    good["lines"][-1].update(
        delivery="outro", payload="judgment",
        narration=("The man never wanted the money, he wanted one person to "
                   "admit they had seen him, and that is the only debt the "
                   "film lets anybody pay. If you made it this far, subscribe "
                   "and tell me what to recap next."))
    for _i in (14, 28, 42):
        good["lines"][_i].update(narration_silence_seconds=6.0, narration="",
                                 delivery=None)
        good["lines"][_i - 1]["delivery"] = "reveal"
    gr = craft_report(good)
    br = craft_report(bad)
    print("  good fixture : %d error(s)" % len(gr["errors"]))
    for e in gr["errors"]:
        print("     ", e)
    if gr["errors"]:
        print("     FAIL: a deliberately well-formed draft tripped a hard gate.")
        ok = False
    else:
        print("     PASS: a well-formed v2 draft clears every hard gate")
    pm = [e for e in br["errors"] if e.startswith("[PAYLOAD-MIX]")]
    print("  bad fixture  : %d error(s), %d of them [PAYLOAD-MIX]"
          % (len(br["errors"]), len(pm)))
    if not pm:
        print("     FAIL: a 100%-rest draft did not trip [PAYLOAD-MIX]")
        ok = False
    else:
        print("     PASS: 100%-rest draft rejected")

    print()
    print("### TITLE: premise title vs film name, both directions")
    # Item 4 co hai nua. Nua am ("khong duoc la '<phim> (<nam>)'") da co tu
    # truoc. Nua duong ("phai LA mot tien de") duoc them 2026-10-20 bang mot
    # proxy: mot tien de la mot MENH DE, mot ten phim la mot CUM DANH TU, nen
    # dau hieu may doc duoc la co dong tu hay khong.
    _tbase = _load(os.path.join(root, HUMAN))
    TITLES = [
        ("human badgenius", "Bad Genius - the exam heist that crossed a time zone", True),
        ("tokyodrift premise", "Shipped to Tokyo to Avoid Jail, He Owes the Yakuza a Debt Only a Race Can Pay", True),
        ("MysteryRecapped A", "Students Don't Realise Their Teacher Is A Kungfu Legend", True),
        ("MysteryRecapped B", "Man Steps On Landmine & Can't Move For 52 Hours", True),
        ("film + year", "The Fast and the Furious: Tokyo Drift (2006)", False),
        ("bare film name", "Tokyo Drift", False),
        ("name + year short", "Bad Genius (2017)", False),
        ("name, no verb", "The Fast and the Furious: Tokyo Drift", False),
    ]
    for nm, t, should_pass in TITLES:
        dd = dict(_tbase)
        dd["title"] = t
        hits = [e for e in craft_report(dd)["errors"]
                if e.startswith("[HOOK] title")]
        passed = not hits
        good = (passed == should_pass)
        print("  %-20s %-8s -> %-8s %s"
              % (nm, "pass" if should_pass else "reject",
                 "passed" if passed else "rejected", "OK" if good else "WRONG"))
        if not good:
            ok = False

    print()
    print("### DENSITY: words-per-beat ceiling, both directions")
    # Chieu DUONG: hai ban da duoc nguoi duyet phai pass.
    for nm, rel in (("human badgenius", HUMAN),
                    ("rendered machine bg", "projects/badgenius2017_machine/draft.json")):
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            print("  %-20s (missing - NOT counted as a pass)" % nm)
            continue
        mm = craft_report(_load(p))
        dens = [e for e in mm["errors"] if e.startswith("[DENSITY]")]
        print("  %-20s %5.1f w/beat  %s"
              % (nm, mm["metrics"].get("words_per_beat") or -1,
                 "FAILS <-- unexpected" if dens else "passes"))
        if dens:
            print("     ", dens[0])
            ok = False
    # Chieu AM: dung chinh ban 58 phut da bi tu choi, dung lai tu cac shard
    # KHONG con ton tai -> tai tao bang cach nhan doi do dai moi dong cua ban
    # cuoi. Mot fixture tong hop, nhung ty le dung voi cai da do: 105.7 w/beat.
    infl = _load(os.path.join(root, MACHINE))
    for i, l in enumerate(infl["lines"]):
        t = str(l.get("narration", "")).strip()
        if t:
            l["narration"] = (t + " ") * 4          # phinh x4, beat khong doi
            l["payload"] = ("loop" if i % 9 == 0 else
                            "judgment" if i % 17 == 0 else
                            "rest" if i % 11 == 0 else "stake")
    ir = craft_report(infl)
    idens = [e for e in ir["errors"] if e.startswith("[DENSITY]")]
    print("  %-20s %5.1f w/beat  %s"
          % ("inflated x4", ir["metrics"].get("words_per_beat") or -1,
             "REJECTED as it should be" if idens else "PASSED <-- gate is blind"))
    if not idens:
        ok = False

    print()
    print("### GUARD: a short fixture must NOT be hard-failed")
    tiny = {"title": "x", "lines": [
        {"id": 1, "clip_start": "00:00:01.0", "clip_end": "00:00:04.0",
         "narration": "A short fixture.", "delivery": "normal"}]}
    tr = craft_report(tiny)
    print("  tiny fixture : %d error(s)" % len(tr["errors"]))
    if tr["errors"]:
        print("     FAIL: craft gates would kill small fixtures, which is how "
              "a new gate takes out the gates under test.")
        ok = False
    else:
        print("     PASS: statistics reported, not enforced, below "
              "MIN_LINES_FOR_STATS")

    print()
    print("RESULT:", "ALL SELF-TESTS PASS" if ok else "SELF-TEST FAILURE")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?")
    ap.add_argument("--file")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    path = a.file or (str(config.project_dir(a.project) / "draft.json")
                      if a.project else None)
    if not path:
        ap.error("give a project, --file, or --selftest")
    r = show(path, _load(path))
    return 1 if r["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
