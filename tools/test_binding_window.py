# -*- coding: utf-8 -*-
"""test_binding_window.py - the speaker check measures what the viewer sees.

Furious 7 stopped on 39 [VOICE-VISUAL] "speaker absent" lines that were, on
inspection, instrument errors: the audit looked only at the shot at
clip_start while the render plays a window ~1.9x the narration (several
shots); the tagger wrote "the bald man in the black tank top" for Dom, or
the ACTOR's name ("paul walker"); and names.json had stored Tej as
'Chris "Ludacris" Bridges) as Tej Parker'. Controls, both directions:

  KNOWN-BAD-STILL-CAUGHT  every person on screen named, the speaker not
                          among them -> SPEAKER_ABSENT (hard), as before
  LATER-SHOT-COUNTS       the speaker is in the window's SECOND shot -> ok
  DESCRIPTION-UNVERIFIED  an unnamed description on screen -> UNVERIFIED
                          (not a pass, not a mismatch)
  ACTOR-NAME-RESOLVES     a tag naming the actor / nickname counts as the
                          character; a junk names.json entry resolves
  CAST-PARSE-CREDITED     the Wikipedia parser no longer writes that junk
                          entry ("(credited as ...)" before the role)

Run:  python tools/test_binding_window.py      (exit 0 = all pass)
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import schemas  # noqa: E402
from pipeline.binding_audit import binding_audit  # noqa: E402
from pipeline.schemas import Claim, Draft, Line, Shot  # noqa: E402

PROJ = "_selftest_binding_window"


def _names():
    pdir = Path(config.project_dir(PROJ))
    shutil.rmtree(pdir, ignore_errors=True)
    pdir.mkdir(parents=True)
    (pdir / "names.json").write_text(json.dumps({"names": [
        {"character": "Dominic Toretto", "actor": "Vin Diesel"},
        {"character": "Brian O'Conner", "actor": "Paul Walker"},
        {"character": 'Chris "Ludacris" Bridges) as Tej Parker',
         "actor": "Ludacris"},
        {"character": "Roman Pearce", "actor": "Tyrese Gibson"},
        {"character": "Letty Ortiz", "actor": "Michelle Rodriguez"},
    ]}), encoding="utf-8")
    return schemas.load_names(PROJ), schemas.load_name_resolver(PROJ)


def _run(chars_by_shot, subject, start="00:00:10.000", end="00:00:20.000"):
    shots = {}
    t = 10.0
    for i, ch in enumerate(chars_by_shot):
        sid = f"clip:00:00:{int(t):02d}.000"
        shots[sid] = Shot(id=sid, source="shots", time_start=t, time_end=t + 5,
                          chars=ch, depicts=["dialogue"])
        t += 5
    ln = Line(id=1, narration="He says it.", clip_start=start, clip_end=end,
              claim=Claim(type="speech", subject=subject))
    names, res = _names()
    r = binding_audit(Draft(project=PROJ, lines=[ln]), shots, {}, names, res)
    return r


def main() -> int:
    cases = []
    r = _run([["dominic toretto"], ["roman pearce"]], "Letty Ortiz")
    cases.append(("KNOWN-BAD-STILL-CAUGHT",
                  [i.issue for i in r.issues] == ["SPEAKER_ABSENT"],
                  f"all named, Letty absent -> {[i.issue for i in r.issues]}"))
    r = _run([["roman pearce"], ["letty ortiz"]], "Letty Ortiz")
    cases.append(("LATER-SHOT-COUNTS", not r.issues and r.speaker_verified == 1,
                  f"Letty in the 2nd shot of the window -> issues "
                  f"{[i.issue for i in r.issues]}"))
    r = _run([["the bald man in the black tank top"]], "Dominic Toretto",
             end="00:00:14.000")
    cases.append(("DESCRIPTION-UNVERIFIED",
                  [i.issue for i in r.issues] == ["UNVERIFIED"]
                  and r.verified_mismatch == 0,
                  f"an unnamed face on screen -> {[i.issue for i in r.issues]}"))
    r1 = _run([["paul walker"]], "Brian O'Conner", end="00:00:14.000")
    r2 = _run([["tej parker"]], 'Chris "Ludacris" Bridges) as Tej Parker',
              end="00:00:14.000")
    r3 = _run([["ludacris"]], "Tej Parker", end="00:00:14.000")
    cases.append(("ACTOR-NAME-RESOLVES",
                  all(not x.issues and x.speaker_verified == 1
                      for x in (r1, r2, r3)),
                  f"actor tag / junk entry / nickname -> "
                  f"{[[i.issue for i in x.issues] for x in (r1, r2, r3)]}"))
    # the parser that wrote the junk entry: a "(credited as ...)" before " as "
    from pipeline import names as N
    wiki = ("== Cast ==\n"
            "* [[Ludacris]] (credited as Chris \"Ludacris\" Bridges) as "
            "Tej Parker, a mechanic\n"
            "* [[Paul Walker]] as Brian O'Conner, a former cop\n"
            "== Production ==\n")
    real = N._fetch_raw
    N._fetch_raw = lambda title: wiki
    try:
        got = N.fetch_cast("Furious_7")[0]
    finally:
        N._fetch_raw = real
    chars = [c for _a, c, *_r in got]
    cases.append(("CAST-PARSE-CREDITED",
                  chars == ["Tej Parker", "Brian O'Conner"],
                  f"'(credited as ...)' line parsed to {chars}"))
    shutil.rmtree(config.project_dir(PROJ), ignore_errors=True)
    bad = 0
    for name, ok, msg in cases:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<24} {msg}")
        bad += 0 if ok else 1
    print("-" * 60)
    print(f"test_binding_window: {bad} FAILURE(S)" if bad
          else "test_binding_window: all pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
