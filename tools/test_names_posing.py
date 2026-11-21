# -*- coding: utf-8 -*-
"""test_names_posing.py - a quoted cast name is an identity CLAIMED, not the
character's own (Lost in the Stars, 21 Nov).

Wikipedia lists 'Janice Man as "Li Muzi" / Jane' (the woman who turns up
claiming to be the missing wife) and 'Kay Huang as Li Muzi' (the wife). The
parser stripped the quotes, gave Li Muzi to Janice Man, and dropped Kay
Huang's line as a duplicate.

  IMPOSTOR-SPLIT   Jane = Janice Man, poses as Li Muzi; Li Muzi = Kay Huang
  ORDER-FREE       the same when the real Li Muzi's line comes first
  DUAL-KEPT        'Ni Ni as Chen Mai / Shen Man' still gives both names
                   to Ni Ni (a dual identity, not a pose)
  LONE-QUOTED      a line that is ONLY a quoted name keeps it as the
                   character; a nickname inside a name is untouched
  TAGGER-TOLD      names.json written by build() carries poses_as, and the
                   tagger's CAST block tells it to tag the impostor by her
                   own name

Run:  python tools/test_names_posing.py      (exit 0 = all pass)
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pipeline import names as N  # noqa: E402

LINES = ['* [[Zhu Yilong]] as He Fei',
         '* [[Ni Ni]] as Chen Mai / Shen Man',
         '* [[Janice Man]] as "Li Muzi" / Jane',
         '* [[Du Jiang]] as Zheng Chen',
         '* [[Kay Huang]] as Li Muzi']


def _parse(lines):
    wiki = "== Cast ==\n" + "\n".join(lines) + "\n== Production ==\n"
    real = N._fetch_raw
    N._fetch_raw = lambda title: wiki
    try:
        got = N.fetch_cast("Lost_in_the_Stars")[0]
    finally:
        N._fetch_raw = real
    return {c: (a, (r[1] if len(r) > 1 else [])) for a, c, *r in got}


def t_impostor():
    m = _parse(LINES)
    ok = (m.get("Jane") == ("Janice Man", ["Li Muzi"])
          and m.get("Li Muzi", ("",))[0] == "Kay Huang")
    return ok, (f"Jane -> {m.get('Jane')}, Li Muzi -> {m.get('Li Muzi')}"
                if ok else f"{m}")


def t_order_free():
    m = _parse([LINES[4]] + LINES[:4])
    ok = (m.get("Jane") == ("Janice Man", ["Li Muzi"])
          and m.get("Li Muzi", ("",))[0] == "Kay Huang")
    return ok, ("real wife listed first: same mapping" if ok else f"{m}")


def t_dual_kept():
    m = _parse(LINES)
    ok = m.get("Chen Mai", ("",))[0] == "Ni Ni" and \
        m.get("Shen Man", ("",))[0] == "Ni Ni" and not m["Shen Man"][1]
    return ok, ("Chen Mai and Shen Man both Ni Ni, no pose" if ok
                else f"{m}")


def t_lone_quoted():
    m = _parse(['* [[Tony Revolori]] as "Zero"',
                '* [[Leonardo DiCaprio]] as Edward "Teddy" Daniels'])
    ok = ("Zero" in m and not m["Zero"][1]
          and "Teddy Daniels" in m)
    return ok, (f"kept {sorted(m)}" if ok else f"{m}")


def t_tagger_told():
    import json
    import shutil
    import config
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import span_payload as SP
    proj = "_test_names_posing"
    wiki = "== Cast ==\n" + "\n".join(LINES) + "\n== Production ==\n"
    real = N._fetch_raw
    N._fetch_raw = lambda title: wiki
    try:
        config.project_dir(proj).mkdir(parents=True, exist_ok=True)
        entries, err, _r, _m = N.build(proj, "Lost_in_the_Stars")
        pdir = config.project_dir(proj)
        nj = json.loads((pdir / "names.json").read_text(encoding="utf-8"))
        lines = SP.cast_lines(SP.load_cast(pdir))
    finally:
        N._fetch_raw = real
        shutil.rmtree(config.project_dir(proj), ignore_errors=True)
    jane = [e for e in nj["names"] if e["character"] == "Jane"]
    pose = [l for l in lines if l.startswith("POSING: Jane")]
    ok = (not err and jane and jane[0].get("poses_as") == ["Li Muzi"]
          and pose and "Tag this person as Jane" in pose[0])
    return ok, (pose[0][:90] if ok else f"{err} {jane} {lines}")


TESTS = [("IMPOSTOR-SPLIT", t_impostor), ("ORDER-FREE", t_order_free),
         ("DUAL-KEPT", t_dual_kept), ("LONE-QUOTED", t_lone_quoted),
         ("TAGGER-TOLD", t_tagger_told)]

if __name__ == "__main__":
    fails = 0
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:15s} {msg}")
    print("-" * 60)
    print("test_names_posing: all pass" if not fails
          else f"test_names_posing: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
