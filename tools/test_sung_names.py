# -*- coding: utf-8 -*-
"""test_sung_names.py - a song is not dialogue; a listed name is spelled as
listed. Both came out of Furious 7's finished script: the ending song's
chorus quoted as Dom's line, and "Mosé Jaconde" for Mose Jakande.

  SUNG-RULES          a music mark, a chorus that comes back (even with a
                      word dropped, as Whisper did) and a hand-listed text are
                      flagged; repeated SHORT dialogue ("What are you doing
                      here?" x2, "I told you to stay put!" x2) and ordinary
                      lines are not; a short segment inside a hand-listed text
                      is not swallowed
  QUOTE-PICKER        a quote marked not-dialogue is never a quote slot
                      again; the slot count is unchanged (lines stay bound);
                      film-speaks candidates do not see it either
  FIX-LINE-NOT-DIALOGUE
                      fix_line --not-dialogue records the line's quote,
                      re-derives the slots, keeps the text; the line's new
                      slot no longer carries the lyric, and a --text for that
                      slot is taken
  NAME-SPELLING       an accent / one-letter / two-letter variant of a listed
                      name is caught, the listed spelling is not, nor a plural,
                      a quoted word, a 4-letter near-word ("Kong"), or an
                      acronym; on the real drafts in projects/ it says nothing
  NAME-SPELLING-WIRED recap.py draft reports it as a hard error naming the
                      line, and resolve receives it as a finding for that line

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
        (170.0, 172.0, "♪ Oh, oh ♪"),
        (200.0, 204.0, "We're going to need a bigger crew for this job."),
        (300.0, 302.0, "my friend"),
        (310.0, 314.0, "Nobody walks away from this family, not tonight."),
    ]
    w = sung.sung_flags(segs)
    want = ["", "", "", "", "CHORUS", "", "CHORUS", "MARKED", "", "", ""]
    ok1 = w == want
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sung.add_by_hand(td, "Nobody walks away from this family, not tonight.")
        again = sung.add_by_hand(td, "nobody walks away from this family not "
                                     "tonight")
        w2 = sung.sung_flags(segs, td)
    ok2 = w2[10] == "BY HAND" and w2[9] == "" and again is False
    ok = ok1 and ok2
    return ok, (f"flags {w}" if not ok1 else
                "chorus (with the dropped word) + music mark + by hand "
                "flagged; repeated short dialogue and 'my friend' kept; a "
                "text recorded once" if ok2 else f"by hand: {w2}")


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
        fs = [s["text"] for s in FS._transcript(pdir)[0]]
    finally:
        (pdir / "not_dialogue.json").unlink(missing_ok=True)
    q2 = [s.get("quote") for s in after if s.get("quote")]
    same = [(s["slot"], s["beat"]) for s in before] == \
        [(s["slot"], s["beat"]) for s in after]
    ok = q[0] not in q2 and same and not any(
        sung._norm(q[0]) in sung._norm(t) for t in fs)
    return ok, (f"'{q[0][:40]}' marked -> not a quote ({len(q)} -> "
                f"{len(q2)} quote slots), slots line up: {same}, film-speaks "
                f"never sees it")


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
    text0 = next(l["narration"] for l in json.loads(
        (pdir / "draft.json").read_text(encoding="utf-8"))["lines"]
        if str(l["id"]) == lid)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = FL.main(["--project", TWS.PROJ, "--line", lid, "--not-dialogue"])
    nd = json.loads((pdir / "not_dialogue.json").read_text(encoding="utf-8"))
    owner = W.act_of_lines(pdir)
    sl2 = W.slots_of_lines(pdir, owner).get(lid)
    text1 = next(l["narration"] for l in json.loads(
        (pdir / "draft.json").read_text(encoding="utf-8"))["lines"]
        if str(l["id"]) == lid)
    ok1 = (rc == 0 and q in nd["texts"] and sl2 is not None
           and sl2.get("quote") != q and text1 == text0
           and "now:" in buf.getvalue())
    # a line for the new slot is taken
    new = (f"\"{sl2['quote']}\" he tells his father across the "
           f"kitchen table." if sl2.get("quote") else TWS._fill(sl2, 0)
           ["narration"])
    with redirect_stdout(io.StringIO()):
        FL.main(["--project", TWS.PROJ, "--line", lid, "--text", new])
    text2 = next(l["narration"] for l in json.loads(
        (pdir / "draft.json").read_text(encoding="utf-8"))["lines"]
        if str(l["id"]) == lid)
    (pdir / "not_dialogue.json").unlink(missing_ok=True)
    ok2 = " ".join(new.split()) == text2
    ok = ok1 and ok2
    return ok, (f"line {lid}: quote recorded, slot now "
                f"{WS.slot_tag(sl2)[:60]}..., text kept until --text, which "
                f"is taken" if ok else
                f"rc {rc}, recorded {q in nd['texts']}, new quote "
                f"{(sl2 or {}).get('quote')!r}, kept {text1 == text0}, "
                f"--text taken {ok2}\n{buf.getvalue()[-600:]}")


def test_name_spelling():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "names.json").write_text(json.dumps({"names": [
            {"character": "Mose Jakande", "actor": "Djimon Hounsou"},
            {"character": "Deckard Shaw", "actor": "Jason Statham"},
            {"character": "Ivan Tarasov", "actor": "x"},
            {"character": "Sean Boswell", "actor": "Sung Kang"}]}),
            encoding="utf-8")
        (p / "transcript.json").write_text(json.dumps({"segments": [
            {"start": 1, "end": 2, "text": "the show starts now"}]}),
            encoding="utf-8")
        bad = [{"id": 1, "narration": "A terrorist named Mosé Jaconde."},
               {"id": 2, "narration": "Deckerd waits."},
               {"id": 3, "narration": "Then Statam shrugs."}]
        good = [{"id": 4, "narration": "Mose Jakande and Deckard Shaw."},
                {"id": 5, "narration": "Everything the Tarasovs have."},
                {"id": 6, "narration": "He yells \"Jaconde!\" at the car."},
                {"id": 7, "narration": "Donkey Kong, he guesses."},
                {"id": 8, "narration": "Show me, Shaw says. The CIA waits."}]
        b = NS.misspelled(p, bad)
        g = NS.misspelled(p, good)
    want = [(1, "Mosé", "Mose"), (1, "Jaconde", "Jakande"),
            (2, "Deckerd", "Deckard"), (3, "Statam", "Statham")]
    real = []
    for d in sorted((ROOT / "projects").iterdir()):
        if d.name.startswith("_") or not (d / "draft.json").exists():
            continue
        try:
            lines = json.loads((d / "draft.json").read_text(
                encoding="utf-8-sig")).get("lines") or []
        except ValueError:
            continue
        real += [(d.name,) + x for x in NS.misspelled(d, lines)]
    ok = b == want and not g and not real
    return ok, ("4 misspellings caught; listed / plural / quoted / 'Kong' / "
                "acronym kept; real drafts: none flagged" if ok else
                f"bad -> {b}; good -> {g}; real -> {real[:5]}")


def test_name_spelling_wired():
    TWS = _fixture_with_draft()
    import write_api as W
    pdir = TWS.PDIR
    dj = pdir / "draft.json"
    d = json.loads(dj.read_text(encoding="utf-8"))
    names = NS.known_names(pdir)
    nm = next((n for n in sorted(names) if len(n) >= 6), None)
    if nm is None:
        return False, "fixture names.json has no 6+ letter name"
    wrong = nm[:-1] + ("y" if nm[-1] != "y" else "e")
    ln = next(l for l in d["lines"] if l.get("slot") and l.get("narration"))
    ln["narration"] = ln["narration"].rstrip(".") + f", and {wrong} knows it."
    dj.write_text(json.dumps(d), encoding="utf-8")
    finds = W.gate_findings(TWS.PROJ)
    hit = [f for f in finds if f["text"].startswith("[NAME-SPELLING]")]
    ok = bool(hit) and hit[0]["ids"] == [str(ln["id"])] and \
        f"'{nm}'" in hit[0]["text"]
    return ok, (f"'{wrong}' -> hard error naming line {ln['id']}, a resolve "
                f"finding for that line" if ok else
                f"findings: {[f['text'][:90] for f in finds][:6]}")


TESTS = {
    "SUNG-RULES": test_sung_rules,
    "QUOTE-PICKER": test_quote_picker,
    "FIX-LINE-NOT-DIALOGUE": test_fix_line_not_dialogue,
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
