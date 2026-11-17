# -*- coding: utf-8 -*-
"""test_story_points.py - the story spine and the holders, built in.

Furious 7, 17 Nov: the trial skipped a three-minute battle on footage and
went on with "Afterwards, Dom watches the plant burn". God's Eye had been
stolen inside that silence. The plan now names the chain of causes
(spine) and what passes from hand to hand (holders). Code makes every such
point land on a narrated line and tells that line what it is for.

  SCHEMA            the plan's JSON schema requires spine and holders
  POINTS            a spine step and a holder change become story points on
                    their beats, with the names a line must contain
  REPAIR            a point on a beat the plan gave 0 lines (or footage)
                    gets 1 line; a beat without a point is untouched
  VALIDATE          story mode: no spine, or a spine/holder beat not in the
                    plan, is a violation; legacy mode asks for neither
  SLOTS-MUST-SAY    the first story slot of that beat carries must_say; the
                    writer sees "MUST SAY" in its slots and "STORY POINTS"
                    in its plan
  LINE-NAMES-WHO    on a must-say slot, a line that names none of the
                    point's people deviates (one fix round); a line that
                    names one does not
  PLOT-IN-PLAN      plot.md, when present, is part of the plan request

Run:  python tools/test_story_points.py      (exit 0 = all pass)
"""
from __future__ import annotations

import copy
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import test_write_plan as TWP  # noqa: E402   (sets the legacy flag on import)
import write_plan as WP  # noqa: E402
import write_slots as WS  # noqa: E402

config.STYLE_QUOTA_FLOORS = False
PROJ, PDIR = TWP.PROJ, TWP.PDIR
_C: dict = {}


def _plan():
    if "plan" not in _C:
        TWP._setup()
        p = TWP._plan("good")
        beats = p["beats"]
        said = next(b for b in beats if int(b.get("lines") or 0) >= 1
                    and not b.get("film_speaks"))
        silent = next(b for b in beats if int(b.get("lines") or 0) == 0)
        p["spine"] = [{"step": "Sean races Kamata's nephew for the money",
                       "because": "he owes Han for the wrecked car",
                       "beats": [said["beat"]]}]
        p["holders"] = [{"what": "the Mustang", "changes": [
            {"beat": silent["beat"], "to": "Twinkie's garage"}]}]
        _C.update(plan=p, said=said["beat"], silent=silent["beat"])
    return copy.deepcopy(_C["plan"]), _C["said"], _C["silent"]


def t_schema():
    sch = WP.PLAN_SCHEMA
    ok = ({"spine", "holders"} <= set(sch["required"])
          and "step" in sch["properties"]["spine"]["items"]["properties"])
    return ok, ("spine + holders required by the plan schema" if ok
                else str(sch["required"]))


def t_points():
    p, said, silent = _plan()
    pts = WP.story_points(p)
    a, b = pts.get(said, [{}])[0], pts.get(silent, [{}])[0]
    ok = (a.get("keys") == ["Sean", "Kamata"] and "because he owes Han" in
          a.get("say", "") and b.get("keys") == ["Twinkie"]
          and "the Mustang is now with Twinkie's garage" == b.get("say"))
    return ok, (f"spine -> {a['keys']}, holder -> {b['keys']}" if ok
                else f"{pts}")


def t_repair():
    p, said, silent = _plan()
    before = {x["beat"]: (x["lines"], x.get("footage")) for x in p["beats"]}
    ch = WP.repair_story_points(p)
    after = {x["beat"]: (x["lines"], x.get("footage")) for x in p["beats"]}
    moved = [k for k in before if before[k] != after[k]]
    ok = (moved == [silent] and after[silent] == (1, False) and len(ch) == 1
          and "[code: story point" in next(
              x["why"] for x in p["beats"] if x["beat"] == silent))
    return ok, (f"{silent}: 0 -> 1 line; nothing else moved" if ok
                else f"moved {moved}, {ch}")


def t_validate():
    p, said, silent = _plan()
    ab = TWP._ab()
    WP.repair_story_points(p)
    clean = [v for v in WP.validate_plan(p, PROJ, PDIR, ab)
             if "spine" in v or "story point" in v]
    q = copy.deepcopy(p)
    q.pop("spine")
    q["holders"][0]["changes"][0]["beat"] = "B999"
    bad = [v for v in WP.validate_plan(q, PROJ, PDIR, ab)
           if "spine" in v or "story point" in v]
    config.STYLE_QUOTA_FLOORS = True
    try:
        legacy = [v for v in WP.validate_plan(q, PROJ, PDIR, ab)
                  if "no story spine" in v]
    finally:
        config.STYLE_QUOTA_FLOORS = False
    ok = (not clean and any("no story spine" in v for v in bad)
          and any("B999" in v for v in bad) and not legacy)
    return ok, ("repaired plan clean; no spine + unknown beat flagged; "
                "legacy asks for neither" if ok
                else f"clean {clean}; bad {bad}; legacy {legacy}")


def _slots(p):
    WS._prev_open_shapes, saved = (lambda: []), WS._prev_open_shapes
    try:
        return WS.derive_slots(p, PROJ, PDIR, TWP._ab())["slots"]
    finally:
        WS._prev_open_shapes = saved


def t_slots_must_say():
    p, said, silent = _plan()
    WP.repair_story_points(p)
    sl = _slots(p)
    first = {}
    for s in sl:
        if s["role"] not in ("hold", "film_speaks", "open", "intro"):
            first.setdefault(s["beat"], s)
    a, b = first.get(said, {}), first.get(silent, {})
    others = [s["slot"] for s in sl if s.get("must_say")
              and s["beat"] not in (said, silent)]
    txt = WS.slots_text(sl)
    ab = TWP._ab()
    k = next(k for k, v in ab.items() if said in v)
    pf = WP.plan_for_act(p, ab[k], k)
    ok = (a.get("must_keys") == [["Sean", "Kamata"]]
          and b.get("must_keys") == [["Twinkie"]] and not others
          and "MUST SAY (a story point - name who): Sean races" in txt
          and "STORY POINTS" in pf and "Sean races Kamata's nephew" in pf)
    return ok, ("must_say on the first story slot of each point's beat; "
                "MUST SAY in the slots, STORY POINTS in the act plan" if ok
                else f"said {a.get('must_keys')}, silent "
                f"{b.get('must_keys')}, others {others}")


def t_line_names_who():
    p, said, _silent = _plan()
    sl = _slots(p)
    s = next(x for x in sl if x.get("must_say") and x["beat"] == said)
    n = max(s["min_words"], min(s["max_words"], 10))
    nameless = {"slot": s["slot"], "narration": " ".join(
        ("The kid races for the cash he owes, flat out, all "
         "night long and more").split()[:n])}
    named = {"slot": s["slot"], "narration": " ".join(
        ("Sean races Kamata's nephew for the cash he owes, flat out all "
         "night").split()[:n])}
    d0 = [d for d in WS.line_deviations(nameless, s) if "must say" in d]
    d1 = [d for d in WS.line_deviations(named, s) if "must say" in d]
    ok = bool(d0) and not d1
    return ok, ("a line naming nobody deviates; naming Sean passes" if ok
                else f"nameless {d0}, named {d1}")


def t_plot_in_plan():
    import write_api as W
    pp = PDIR / "plot.md"
    had = pp.exists()
    old = pp.read_text(encoding="utf-8") if had else None
    try:
        pp.write_text("# plot\n\nSean owes Han for the Silvia.\n",
                      encoding="utf-8")
        u1 = WP.plan_user(PROJ, PDIR, W._tool, W._read)
        pp.unlink()
        u0 = WP.plan_user(PROJ, PDIR, W._tool, W._read)
    finally:
        if had:
            pp.write_text(old, encoding="utf-8")
        elif pp.exists():
            pp.unlink()
    ok = "Sean owes Han for the Silvia" in u1 and "# plot.md" not in u0
    return ok, ("plot.md joins the plan request when present" if ok
                else "plot.md not in the plan request")


TESTS = [("SCHEMA", t_schema), ("POINTS", t_points), ("REPAIR", t_repair),
         ("VALIDATE", t_validate), ("SLOTS-MUST-SAY", t_slots_must_say),
         ("LINE-NAMES-WHO", t_line_names_who),
         ("PLOT-IN-PLAN", t_plot_in_plan)]

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
    print("test_story_points: all pass" if not fails
          else f"test_story_points: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
