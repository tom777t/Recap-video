# -*- coding: utf-8 -*-
"""test_plot_ref.py - Wikipedia's Plot next to the frames in the beats stage.

  EXTRACT-PLOT       the Plot section comes out as plain prose: links keep
                     their label, references, templates, comments and bold
                     go, a sub-heading becomes a line, the next section is
                     not included
  NO-PLOT-SECTION    a page with no Plot / Synopsis section -> state "none",
                     no plot.md
  ENSURE-ONCE        plot.md is written once with its revision, then kept
                     (no second fetch); no title (a short drama) -> "none",
                     no fetch, no error
  BEATS-READ-PLOT    with plot.md, every chunk request carries it in the
                     CACHED system prefix with the who/why-not-what note;
                     without it the request is exactly as before
  PLOT-NAMES         a character the Plot names twice and no beat names is
                     reported; one a beat names, or the Plot names once, is
                     not

Run:  python tools/test_plot_ref.py      (exit 0 = all pass)
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
from pipeline import plot_ref as PR  # noqa: E402

WIKI = """{{Short description|2015 film}}
'''Furious 7''' is a film.<ref>cite</ref>

== Plot ==
<!-- keep under 700 words -->
After [[Deckard Shaw]] visits his comatose brother, he swears revenge.
Shaw allies with the terrorist [[Mose Jakande|Jakande]], who wants the
[[God's Eye]].<ref name="a">x</ref> {{citation needed|date=May 2020}}

=== Abu Dhabi ===
Jakande's men steal God's Eye and Jakande hunts Ramsey with a drone.

== Cast ==
* Vin Diesel as Dominic Toretto
"""


def t_extract():
    p = PR.extract_plot(WIKI)
    bad = []
    for must in ("After Deckard Shaw visits", "terrorist Jakande, who wants "
                 "the God's Eye.", "Abu Dhabi:", "Jakande's men steal"):
        if must not in p:
            bad.append(f"missing {must!r}")
    for never in ("<ref", "{{", "[[", "'''", "Cast", "Vin Diesel", "<!--",
                  "Short description"):
        if never in p:
            bad.append(f"kept {never!r}")
    return not bad, (f"{len(p.split())} words of plain Plot prose" if not bad
                     else "; ".join(bad))


def t_no_plot_section():
    d = Path(tempfile.mkdtemp())
    try:
        r = PR.ensure_plot(d, "X", fetch=lambda: {
            "title": "X", "oldid": 1, "fetched": "2026-11-17",
            "wikitext": "== Cast ==\n* someone\n"})
        ok = r["state"] == "none" and not (d / "plot.md").exists()
        return ok, ("no Plot section: state none, no plot.md" if ok
                    else str(r))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def t_ensure_once():
    d = Path(tempfile.mkdtemp())
    n = {"fetch": 0}

    def fetch():
        n["fetch"] += 1
        return {"title": "Furious 7", "oldid": 123, "fetched": "2026-11-17",
                "wikitext": WIKI}
    try:
        r1 = PR.ensure_plot(d, "Furious 7", fetch=fetch)
        r2 = PR.ensure_plot(d, "Furious 7", fetch=fetch)
        txt = (d / "plot.md").read_text(encoding="utf-8")
        r3 = PR.ensure_plot(Path(tempfile.mkdtemp()), None)
        ok = (r1["state"] == "wrote" and r2["state"] == "kept"
              and n["fetch"] == 1 and "oldid=123" in txt
              and r3["state"] == "none")
        return ok, ("written once with oldid=123, kept on the second call; "
                    "no title -> none, no fetch" if ok
                    else f"{r1} {r2} {r3} fetches {n['fetch']}")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def t_beats_read_plot():
    import write_api as W
    tmp = Path(tempfile.mkdtemp())
    prev = config.project_dir
    config.project_dir = lambda name: tmp / name
    (tmp / "p").mkdir()
    sentinel = "Shaw allies with the terrorist Jakande"
    try:
        W._tool, saved = (lambda *a, **k: "PAYLOAD"), W._tool
        try:
            r0 = W.chunk_request("p", 1, 8)
            (tmp / "p" / "plot.md").write_text("# plot\n\n" + sentinel,
                                               encoding="utf-8")
            r1 = W.chunk_request("p", 1, 8)
        finally:
            W._tool = saved
    finally:
        config.project_dir = prev
        shutil.rmtree(tmp, ignore_errors=True)
    s0 = "\n".join(b["text"] for b in r0["system"])
    s1 = r1["system"]
    last = s1[-1]
    ok = (sentinel not in s0 and sentinel in last["text"]
          and "WHO someone is and WHY" in last["text"]
          and "cache_control" in last and len(s1) == len(r0["system"]) + 1
          and r1["messages"] == r0["messages"])
    return ok, ("plot.md rides in the cached system prefix with the "
                "who/why note; without it the request is unchanged" if ok
                else f"blocks {len(r0['system'])}->{len(s1)}, cached "
                f"{'cache_control' in last}")


def t_plot_names():
    plot = PR.extract_plot(WIKI)
    beats = [{"what": "Shaw visits his brother", "chars": ["Deckard Shaw"]},
             {"what": "a man watches", "chars": []}]
    miss = PR.missing_names(plot, beats, ["Deckard Shaw", "Mose Jakande",
                                         "God's Eye keeper", "Ramsey"])
    names = [n for n, _c in miss]
    ok = names == ["Mose Jakande"]
    return ok, ("Jakande (named 3x in the Plot, in no beat) reported; Shaw "
                "(in a beat) and Ramsey (once) not" if ok else str(miss))


TESTS = [("EXTRACT-PLOT", t_extract), ("NO-PLOT-SECTION", t_no_plot_section),
         ("ENSURE-ONCE", t_ensure_once), ("BEATS-READ-PLOT", t_beats_read_plot),
         ("PLOT-NAMES", t_plot_names)]

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
        print(f"{'PASS' if ok else 'FAIL'}  {name:16s} {msg}")
    print("-" * 60)
    print("test_plot_ref: all pass" if not fails
          else f"test_plot_ref: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
