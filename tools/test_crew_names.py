# -*- coding: utf-8 -*-
"""test_crew_names.py - [FILM-INTRO] with more than one director.

Lost in the Stars (2023) has two directors. film_facts.json holds
"Cui Rui, Liu Xiang"; the intro said "Directed by Cui Rui and Liu Xiang",
and the gate - which looked for the field's literal text - failed it every
round, at slot level and draft level, and called both names unsourced.

    python tools/test_crew_names.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import craft_gates as cg  # noqa: E402

FACTS = {"title": "Lost in the Stars", "year": 2023,
         "director": "Cui Rui, Liu Xiang",
         "cast": [{"actor": "Zhu Yilong", "role": "He Fei"},
                  {"actor": "Ni Ni", "role": "Chen Mai"},
                  {"actor": "Du Jiang", "role": "Zheng Chen"}]}


def _intro(text):
    return {"id": 4, "narration": text, "delivery": "intro",
            "film_intro": True, "note": "INTRO"}


def test_split() -> tuple[bool, str]:
    cases = {"Cui Rui, Liu Xiang": ["Cui Rui", "Liu Xiang"],
             "Joel and Ethan Coen": ["Joel", "Ethan Coen"],
             "A & B; C": ["A", "B", "C"],
             "Andrew Lau": ["Andrew Lau"],
             ("X Y", "Z W"): ["X Y", "Z W"], None: [], "": []}
    bad = {k: cg.crew_names(k) for k, v in cases.items()
           if cg.crew_names(k) != v}
    if bad:
        return False, f"wrong split: {bad}"
    if not cg.fact_stated("director", "Cui Rui, Liu Xiang",
                          "directed by liu xiang and cui rui."):
        return False, "both names in another order not accepted"
    if cg.fact_stated("director", "Cui Rui, Liu Xiang", "directed by cui rui"):
        return False, "one of two directors accepted as the whole field"
    if not cg.fact_stated("year", 2023, "lost in the stars, from 2023"):
        return False, "plain fields no longer matched literally"
    return True, "comma / and / & / ; / list split; every director required"


def test_gates() -> tuple[bool, str]:
    d = Path(tempfile.mkdtemp(prefix="recap_crew_"))
    try:
        (d / "film_facts.json").write_text(json.dumps(FACTS), "utf-8")
        text = (f"This is {config.CHANNEL_NAME}, and today we're telling "
                f"Lost in the Stars, from 2023. Directed by Cui Rui and Liu "
                f"Xiang. Zhu Yilong plays He Fei, Ni Ni is the lawyer Chen "
                f"Mai, and Du Jiang is Officer Zheng Chen.")
        from tools import write_slots as ws
        slot = [p for p in ws._intro_problems(text, d) if "director" in p]
        if slot:
            return False, f"slot check: {slot}"
        draft = {"_dir": str(d), "lines": [_intro(text)]}
        rep = cg.craft_report(draft)
        msgs = [str(x) for x in (rep.get("errors") or []) +
                (rep.get("warnings") or rep.get("warns") or [])]
        hit = [x for x in msgs if "[FILM-INTRO]" in x and (
            "director" in x or "Cui Rui" in x or "Liu Xiang" in x
            or "Officer Zheng" in x)]
        if hit:
            return False, f"draft check: {hit}"
        one = text.replace(" and Liu Xiang", "")
        if not any("director" in p for p in ws._intro_problems(one, d)):
            return False, "naming only one of two directors passed"
        return True, ("'Cui Rui and Liu Xiang' satisfies 'Cui Rui, Liu Xiang' "
                      "at slot and draft level; no unsourced-name warning "
                      "for either director or 'Officer Zheng'")
    finally:
        shutil.rmtree(d, ignore_errors=True)


TESTS = {"CREW-SPLIT": test_split, "INTRO-TWO-DIRECTORS": test_gates}

if __name__ == "__main__":
    bad = 0
    for name, fn in TESTS.items():
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        print(f'{"PASS" if ok else "FAIL"}  {name:<22} {msg}')
        bad += (not ok)
    print("-" * 60)
    print("test_crew_names: all pass" if not bad else
          f"test_crew_names: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
