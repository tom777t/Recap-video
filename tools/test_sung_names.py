# -*- coding: utf-8 -*-
"""test_sung_names.py - a song is not dialogue; a listed name is spelled as
listed. Both came out of Furious 7's finished script: the ending song's
chorus quoted as Dom's line, and "Mosé Jaconde" for Mose Jakande.

  SUNG-RULES          flagged: a music mark (also "[upbeat music]"), a chorus
                      that comes back (even with a word dropped, as Whisper
                      did), the verse between two passes of it (not a line
                      between a repeat under 30 s), a hand-listed text - also as ONE sentence of a
                      longer segment. Kept: repeated short dialogue, two long
                      lines that share words but do not read the same, a
                      phrase that only starts like a listed one ("see you
                      against"), a short line inside a long listed lyric
  QUOTE-PICKER        a quote marked not-dialogue is never a quote slot
                      again; the slot count is unchanged; film-speaks runs
                      never contain it and never join across it
  FIX-LINE-NOT-DIALOGUE
                      --not-dialogue records the quote, re-derives, keeps the
                      text and says the line still quotes it; only that
                      line's slot changed; a --text quoting it is refused, a
                      fitting one is taken; a re-derive that would move slots
                      is refused and leaves plan.json and not_dialogue.json
                      as they were
  NOT-DIALOGUE-WIRED  recap.py draft: a line quoting a listed text is a hard
                      [NOT-DIALOGUE] error naming the line, a resolve finding
  NAME-SPELLING       HARD: accents only (Mosé), or the variant heard in the
                      transcript while the listed spelling never is (Jaconde).
                      WARN only: a near-name the transcript does not support,
                      or whose listed name is said ("America" / Amelia). Not
                      at all: listed, plural, quoted, 4-letter ("Kong"),
                      acronym, "Murph-", a lower-case word ("marrow" /
                      Marlow). Names read from characters / aliases too, and
                      O'Conner kept whole. No names -> "not run". On every
                      real draft in projects/: no hard finding
  NAME-SPELLING-WIRED recap.py draft reports the hard one naming the line, and
                      resolve receives it as a finding for that line

Run:  python tools/test_sung_names.py      (exit 0 = all pass)
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
from pipeline import sung  # noqa: E402
from pipeline import name_spelling as NS  # noqa: E402

LYRIC = "It's been a long day without you, my friend"


def test_sung_rules():
    segs = [
        (10.0, 13.0, "What are you doing here?"),
        (40.0, 43.0, "What are you doing here?"),
        (50.0, 53.0, "I told you to stay put!"),
        (55.0, 58.0, "I told you to stay put!"),
        (100.0, 104.0, LYRIC),
        (110.0, 114.0, "And I'll tell you all about it when I see you again"),
        (160.0, 164.0, "It's been a long without you, my friend"),  # Whisper
        (170.0, 172.0, "\u266a Oh, oh \u266a"),
        (200.0, 204.0, "We're going to need a bigger crew for this job."),
        (300.0, 302.0, "my friend"),
        (310.0, 314.0, "Nobody walks away from this family, not tonight."),
        (320.0, 324.0, "We are going to need a bigger boat for that shark."),
        (330.0, 333.0, "[upbeat music]"),
        (340.0, 343.0, "Oh, baby. I love you, Letty."),
        (350.0, 353.0, "I'll see you against the wall, punk."),
        (360.0, 362.0, "It's been a long day."),
    ]
    w = sung.sung_flags(segs)
    want = ["", "", "", "", "CHORUS", "IN-SONG", "CHORUS", "MARKED", "", "",
            "", "", "MARKED", "", "", ""]
    # IN-SONG (Furious 7 line 184: the verse between two passes of the
    # chorus, 55 s apart, was picked as Dom's line). Invented words here.
    ch = "We ride on through the city lights tonight, my brother"
    song = [(100.0, 104.0, ch), (110.0, 113.0, "Built it on our own when the "
             "road was long"), (120.0, 123.0, "And the road is where we "
             "belong"), (155.0, 159.0, ch + "."),
            (165.0, 168.0, "You thought you could leave without a word?"),
            (300.0, 304.0, "Put your keys on the table and step back now."),
            (310.0, 312.0, "Do it now."),
            (318.0, 322.0, "Put your keys on the table and step back now!")]
    ws = sung.sung_flags(song)
    want_s = ["CHORUS", "IN-SONG", "IN-SONG", "CHORUS", "", "CHORUS", "",
              "CHORUS"]
    if ws != want_s:
        return False, (f"IN-SONG: {ws} (want the verse between choruses "
                       f"55 s apart, not the line after, not a line between "
                       f"a repeat 18 s apart)")
    ok1 = w == want
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sung.add_by_hand(td, "Nobody walks away from this family, not tonight.")
        sung.add_by_hand(td, "I love you, Letty.")
        sung.add_by_hand(td, "see you again")
        sung.add_by_hand(td, LYRIC)
        again = sung.add_by_hand(td, "nobody walks away from this family not "
                                     "tonight")
        w2 = sung.sung_flags(segs, td)
    ok2 = (w2[10] == "BY HAND" and w2[13] == "BY HAND" and w2[9] == ""
           and w2[14] == "" and w2[15] == "" and again is False)
    ok = ok1 and ok2
    return ok, (f"flags {w}" if not ok1 else
                "chorus (word dropped) + the verse between two choruses + music marks + by hand (also one "
                "sentence of a segment) flagged; short repeats, look-alike "
                "long lines, 'see you against', a short line inside a lyric "
                "kept; a text recorded once" if ok2 else f"by hand: {w2}")


def _fixture_with_draft():
    import test_write_slots as TWS
    TWS.test_draft_slots()                # leaves a slot-written draft
    return TWS


def test_quote_picker():
    TWS = _fixture_with_draft()
    import write_slots as WS
    pdir = TWS.PDIR
    plan = json.loads((pdir / "plan.json").read_text(encoding="utf-8"))
    ab = TWS._C.get("ab") or TWS._layout()[1]
    before = WS.derive_slots(plan, TWS.PROJ, pdir, ab)["slots"]
    q = [s["quote"] for s in before if s.get("quote")]
    if not q:
        return False, "the fixture has no quote slot"
    sung.add_by_hand(pdir, q[0])
    try:
        after = WS.derive_slots(plan, TWS.PROJ, pdir, ab)["slots"]
        from pipeline import film_speaks as FS
        segs = FS._transcript(pdir)[0]
        fs = [r["text"] for r in FS._runs(segs, 0.5, 60.0)]
        kept = [x for x in segs if sung._norm(q[0]) in sung._norm(x["text"])]
    finally:
        (pdir / "not_dialogue.json").unlink(missing_ok=True)
    # a run may not join the dialogue either side of a song
    hole = FS._runs([{"a": 0.0, "b": 2.0, "text": "Get in.", "sung": ""},
                     {"a": 2.5, "b": 5.0, "text": "la la", "sung": "MARKED"},
                     {"a": 5.5, "b": 8.0, "text": "Drive.", "sung": ""}],
                    1.0, 15.0)
    no_join = all("la la" not in r["text"] and not (r["a"] < 2.5 < r["b"])
                  for r in hole) and len(hole) == 2
    q2 = [s.get("quote") for s in after if s.get("quote")]
    same = [(s["slot"], s["beat"]) for s in before] == \
        [(s["slot"], s["beat"]) for s in after]
    ok = q[0] not in q2 and same and not any(
        sung._norm(q[0]) in sung._norm(t) for t in fs) and no_join and \
        kept and all(x.get("sung") for x in kept)
    return ok, (f"'{q[0][:40]}' marked -> not a quote ({len(q)} -> "
                f"{len(q2)} quote slots), slots line up: {same}, film-speaks "
                f"runs never hold it nor join across a song")


def _line_text(pdir, lid):
    return next(l["narration"] for l in json.loads(
        (pdir / "draft.json").read_text(encoding="utf-8"))["lines"]
        if str(l["id"]) == str(lid))


def test_fix_line_not_dialogue():
    TWS = _fixture_with_draft()
    import fix_line as FL
    import write_api as W
    import write_slots as WS
    pdir = TWS.PDIR
    (pdir / "not_dialogue.json").unlink(missing_ok=True)
    owner = W.act_of_lines(pdir)
    slot_of = W.slots_of_lines(pdir, owner)
    lid = next((k for k, s in slot_of.items() if s.get("quote")), None)
    if lid is None:
        return False, "no quote line in the fixture draft"
    q = slot_of[lid]["quote"]
    text0 = _line_text(pdir, lid)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = FL.main(["--project", TWS.PROJ, "--line", lid, "--not-dialogue"])
    nd = json.loads((pdir / "not_dialogue.json").read_text(encoding="utf-8"))
    after = W.slots_of_lines(pdir, W.act_of_lines(pdir))
    sl2 = after.get(lid)
    others = [k for k in slot_of if k != lid and
              (slot_of[k].get("role"), slot_of[k].get("quote"),
               slot_of[k].get("beat")) !=
              ((after.get(k) or {}).get("role"), (after.get(k) or {}).get(
                  "quote"), (after.get(k) or {}).get("beat"))]
    shown = io.StringIO()
    with redirect_stdout(shown):
        FL.main(["--project", TWS.PROJ, "--line", lid, "--show"])
    # --show lists the transcript around the line, the marked quote flagged
    around = [r for r in shown.getvalue().split("speech around the line")[-1]
              .splitlines() if sung._norm(q) in sung._norm(r)]
    ok1 = ("speech around the line" in shown.getvalue() and around
           and all("[BY HAND]" in r for r in around)) and \
        (rc == 0 and q in nd["texts"] and sl2 is not None
           and sl2.get("quote") != q and _line_text(pdir, lid) == text0
           and "still quotes it" in buf.getvalue() and not others)
    # a --text that still quotes it is refused; a fitting one is taken
    with redirect_stdout(io.StringIO()):
        rc_q = FL.main(["--project", TWS.PROJ, "--line", lid, "--text",
                        f"\"{q}\" he says to his father at the table."])
    refused = rc_q == 2 and _line_text(pdir, lid) == text0
    new = (f"\"{sl2['quote']}\" he tells his father across the "
           f"kitchen table." if sl2.get("quote") else TWS._fill(sl2, 0)
           ["narration"])
    with redirect_stdout(io.StringIO()):
        FL.main(["--project", TWS.PROJ, "--line", lid, "--text", new])
    ok2 = " ".join(new.split()) == _line_text(pdir, lid)
    # a re-derive that would move slots is refused, nothing half-done
    plan_p = pdir / "plan.json"
    plan = json.loads(plan_p.read_text(encoding="utf-8"))
    b0 = next(b for b in plan["beats"] if b.get("lines"))
    b0["lines"] = int(b0["lines"]) + 1           # one more slot -> moves
    plan_p.write_text(json.dumps(plan), encoding="utf-8")
    plan_before = plan_p.read_bytes()
    nd_before = (pdir / "not_dialogue.json").read_bytes()
    lid2 = next((k for k, s in after.items() if s.get("quote")
                 and k != lid), None)
    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        rc_m = FL.main(["--project", TWS.PROJ, "--line", lid2,
                        "--not-dialogue"]) if lid2 else 1
    ok3 = (lid2 is not None and rc_m == 1 and "NOT re-derived" in
           buf2.getvalue() and plan_p.read_bytes() == plan_before
           and (pdir / "not_dialogue.json").read_bytes() == nd_before)
    (pdir / "not_dialogue.json").unlink(missing_ok=True)
    ok = ok1 and refused and ok2 and ok3
    return ok, (f"line {lid}: quote recorded, slot now "
                f"{WS.slot_tag(sl2)[:40]}..., no other slot changed, text "
                f"kept and reported; quoting it again refused; a fitting "
                f"--text taken; a moving re-derive refused, nothing changed"
                if ok else
                f"rc {rc}, other slots changed {others[:3]}, ok1 {ok1}, "
                f"refused {refused}, taken {ok2}, move-refused {ok3}\n"
                f"{buf.getvalue()[-400:]}\n{buf2.getvalue()[-300:]}")


def test_not_dialogue_wired():
    TWS = _fixture_with_draft()
    import write_api as W
    pdir = TWS.PDIR
    dj = pdir / "draft.json"
    d = json.loads(dj.read_text(encoding="utf-8"))
    ln = next(l for l in d["lines"] if l.get("slot") and l.get("narration"))
    ln["narration"] = ln["narration"].rstrip(".") + \
        ", and the radio plays \"see you again, my old friend\"."
    dj.write_text(json.dumps(d), encoding="utf-8")
    sung.add_by_hand(pdir, "See you again, my old friend.")
    try:
        finds = W.gate_findings(TWS.PROJ)
    finally:
        (pdir / "not_dialogue.json").unlink(missing_ok=True)
    hit = [f for f in finds if f["text"].startswith("[NOT-DIALOGUE]")]
    ok = bool(hit) and hit[0]["ids"] == [str(ln["id"])]
    return ok, (f"a listed lyric quoted on line {ln['id']} -> hard error, a "
                f"resolve finding for that line" if ok else
                f"findings: {[f['text'][:90] for f in finds][:6]}")


def _names_dir(td, transcript):
    p = Path(td) / "film"        # its own parent: the repo-wide word list is
    p.mkdir()                    # read from a project's siblings
    (p / "names.json").write_text(json.dumps({
        "names": [{"character": "Mose Jakande", "actor": "Djimon Hounsou"},
                  {"character": "Deckard Shaw", "actor": "Jason Statham"},
                  {"character": "Ivan Tarasov", "actor": "x"},
                  {"character": "Amelia Brand", "actor": "y"},
                  {"character": "Sean Boswell", "actor": "Sung Kang"}],
        "characters": ["Marlow"],
        "aliases": {"Brian O'Conner": "Brian", "Murph": "Murphy"}}),
        encoding="utf-8")
    (p / "transcript.json").write_text(json.dumps({"segments": [
        {"start": i, "end": i + 1, "text": t}
        for i, t in enumerate(transcript)]}), encoding="utf-8")
    return p


def test_name_spelling():
    import tempfile
    lines = [{"id": 1, "narration": "A terrorist named Mosé Jaconde."},
             {"id": 2, "narration": "Deckerd waits."},
             {"id": 3, "narration": "America is starving, and Amelia knows."},
             {"id": 4, "narration": "Brian O'Connor drives."},
             {"id": 5, "narration": "Marrow, he says."}]
    good = [{"id": 6, "narration": "Mose Jakande and Deckard Shaw."},
            {"id": 7, "narration": "Everything the Tarasovs have."},
            {"id": 8, "narration": "He yells \"Jaconde!\" at the car."},
            {"id": 9, "narration": "Donkey Kong, he guesses. The CIA waits."},
            {"id": 10, "narration": "Murph- no, Murph runs."}]
    with tempfile.TemporaryDirectory() as td:
        p = _names_dir(td, ["Jaconde is in the city.", "Amelia, wait.",
                            "Where is the marrow"])
        got = NS.misspelled(p, lines)
        none = NS.misspelled(p, good)
    with tempfile.TemporaryDirectory() as td:
        p2 = _names_dir(td, ["Jaconde is here.", "Jakande, yes."])
        both = NS.misspelled(p2, lines[:1])
        nolow = NS.misspelled(p2, lines[4:5])
    with tempfile.TemporaryDirectory() as td:
        empty = NS.report(Path(td), lines)
    hard = {(i, w) for i, w, _k, h in got if h}
    soft = {(i, w) for i, w, _k, h in got if not h}
    checks = [
        (hard == {(1, "Mosé"), (1, "Jaconde")},
         f"hard: accent + heard-not-listed ({sorted(hard)})"),
        ({(2, "Deckerd"), (3, "America"), (4, "O'Connor")} == soft,
         f"warn only: not heard / listed name said / alias O'Conner "
         f"({sorted(soft)})"),
        (not none, f"listed / plural / quoted / Kong / CIA / Murph- clean "
                   f"({none})"),
        ([h for *_x, h in both] == [True, False],
         "the listed spelling heard too -> the variant is only a warning"),
        (nolow == [(5, "Marrow", "Marlow", False)],
         f"'Marrow' flagged only where 'marrow' is not an ordinary word "
         f"({nolow})"),
        (empty["notes"] and "not run" in empty["notes"][0]
         and not empty["errors"], "no names -> not run, said"),
    ]
    real = []
    for d in sorted((ROOT / "projects").iterdir()):
        if d.name.startswith("_"):
            continue
        for f in d.glob("draft*.json"):
            try:
                ls = json.loads(f.read_text(encoding="utf-8-sig")).get(
                    "lines") or []
            except ValueError:
                continue
            real += [(f"{d.name}/{f.name}",) + x
                     for x in NS.misspelled(d, ls) if x[-1]]
    checks.append((not real, f"real drafts: {len(real)} hard ({real[:3]})"))
    bad = [w for ok, w in checks if not ok]
    return not bad, ("; ".join(w for _, w in checks) if not bad
                     else "FAILED: " + "; ".join(bad))


def test_name_spelling_wired():
    TWS = _fixture_with_draft()
    import write_api as W
    pdir = TWS.PDIR
    dj = pdir / "draft.json"
    d = json.loads(dj.read_text(encoding="utf-8"))
    known = NS.known_names(pdir)
    acc = {"a": "\u00e1", "e": "\u00e9", "o": "\u00f3", "i": "\u00ed"}
    nm = next((n for n in sorted(known) if len(n) >= 4
               and any(c in acc for c in n[1:])), None)
    if nm is None:
        return False, "fixture names.json has no name with a vowel"
    i = next(i for i, c in enumerate(nm) if i and c in acc)
    wrong = nm[:i] + acc[nm[i]] + nm[i + 1:]
    ln = next(l for l in d["lines"] if l.get("slot") and l.get("narration"))
    ln["narration"] = ln["narration"].rstrip(".") + f", and {wrong} knows it."
    dj.write_text(json.dumps(d), encoding="utf-8")
    finds = W.gate_findings(TWS.PROJ)
    hit = [f for f in finds if f["text"].startswith("[NAME-SPELLING]")]
    ok = bool(hit) and hit[0]["ids"] == [str(ln["id"])] and \
        f"'{nm}'" in hit[0]["text"]
    return ok, (f"'{wrong}' -> hard error naming line {ln['id']}, a resolve "
                f"finding for that line" if ok else
                f"'{wrong}' for {nm}: findings "
                f"{[f['text'][:90] for f in finds][:6]}")


TESTS = {
    "SUNG-RULES": test_sung_rules,
    "QUOTE-PICKER": test_quote_picker,
    "FIX-LINE-NOT-DIALOGUE": test_fix_line_not_dialogue,
    "NOT-DIALOGUE-WIRED": test_not_dialogue_wired,
    "NAME-SPELLING": test_name_spelling,
    "NAME-SPELLING-WIRED": test_name_spelling_wired,
}

if __name__ == "__main__":
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
            print(f"{'PASS' if ok else 'FAIL'}  {name:<22} {m}")
            bad += not ok
    finally:
        TB.CLIENT_FACTORY = saved
        import shutil
        shutil.rmtree(config.project_dir("_selftest_writeplan"),
                      ignore_errors=True)
    print("-" * 60)
    print(f"test_sung_names: {bad} FAILURE(S)" if bad
          else "test_sung_names: all pass")
    sys.exit(1 if bad else 0)
