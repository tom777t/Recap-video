# -*- coding: utf-8 -*-
"""test_fix_round.py - the slot-fix round sends only what the fix needs.

Furious 7 trial, 17 Nov: fixing a handful of lines in two acts cost $0.20.
The round resent each whole act (152k input tokens): every beat, every
moment and every transcript line, plus the whole previous reply. The fix
needs only the slots that deviate, what is wrong with them, the act as it
stands for context, and the footage around those slots.

  SLICE-KEEPS-NEAR    payload_slice keeps the header, the target beats'
                      rows, the moments within reach of the target windows
                      with their SPEECH, and the speech rules; it drops far
                      moments, their speech, other beats and the context
                      block
  NARROW-REQUEST      slot_fix_params: only the deviating slots in THE
                      SLOTS TO REWRITE, the deviations verbatim, every line
                      of the act as context, under a quarter of the full
                      act request's size on the same payload
  NO-SLOT-NO-NARROW   deviations that name no slot -> None (the caller
                      resends the whole act, as before)
  PARTIAL-MERGE       a reply for one slot changes that slot only;
                      merge_revision keeps every other line

Run:  python tools/test_fix_round.py      (exit 0 = all pass)
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import test_story_mode as TSM  # noqa: E402
import write_api as W  # noqa: E402
import write_slots as WS  # noqa: E402

config.STYLE_QUOTA_FLOORS = False


def _hms(t: float) -> str:
    return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:06.3f}"


def _payload(n: int = 120) -> str:
    rows = ["### ACT 2: the race", "### time range 600s - 2400s | 3 beats",
            "", "BEATS (id | ts | what happens | chars | kind):"]
    rows += [f"  | B{i:02d} | 00:{10 + i:02d}:00 | beat {i} happens | Sean | "
             f"plot" for i in range(1, 4)]
    rows += ["", f"AVAILABLE MACHINE MOMENTS in range: {n}",
             "Each moment: id | start -> end | dur | maxwords | chars | "
             "depicts | censor | action",
             "SPEECH lines under a moment are the transcript for that window."]
    for i in range(n):
        a = 600 + i * 15
        rows.append(f"  M{i:04d} | {_hms(a)} -> {_hms(a + 15)} | "
                    f"15.0s | 40w | Sean | car | none | moment {i} action")
        rows.append(f"       SPEECH {a + 2:.1f}-{a + 5:.1f}: line {i} said")
    rows += ["", "CONTEXT ONLY - 2 neighbouring moment(s). DO NOT BIND.",
             "  (ctx) M9998 | 00:59:00.000 -> 00:59:10.000 | x",
             "", "HOW TO USE THE SPEECH LINES",
             "- The transcript is machine translation."]
    return "\n".join(rows)


def t_slice():
    pay = _payload()
    # target window 00:20:00-00:20:15 (1200-1215s), beat B02
    out = W.payload_slice(pay, {"B02"}, [(1200.0, 1215.0)], reach=20.0)
    bad = []
    for must in ("### ACT 2", "| B02 |", "M0040 |", "line 40 said",
                 "HOW TO USE THE SPEECH LINES", "machine translation"):
        if must not in out:
            bad.append(f"dropped {must!r}")
    for never in ("| B01 |", "| B03 |", "M0000 |", "line 0 said", "M0100 |",
                  "(ctx) M9998", "CONTEXT ONLY"):
        if never in out:
            bad.append(f"kept {never!r}")
    kept = sum(1 for l in out.splitlines() if l.strip().startswith("M0"))
    return not bad, (f"{kept} of 120 moments kept (within 20s), their "
                     f"speech, B02 only, rules kept, context dropped"
                     if not bad else "; ".join(bad))


def _setup():
    plan, ab, slots = TSM._layout()
    k = 2
    mine = [s for s in WS.slots_for_act(slots, k)
            if s["role"] not in ("hold", "film_speaks")]
    lines = WS.merge([TSM._fill(s, i) for i, s in enumerate(mine)], slots, k)
    return plan, slots, k, mine, lines


def t_narrow():
    plan, slots, k, mine, lines = _setup()
    tgt = mine[1]
    devs = [f"{tgt['slot']} ({tgt['beat']} action): 40 words, the slot is "
            f"3-{tgt['max_words']}"]
    sysb = W.draft_system(TSM.PDIR)
    pay = _payload(400)
    nar = W.slot_fix_params(TSM.PROJ, TSM.PDIR, k, sysb, slots, plan, lines,
                            devs, payload=pay)
    full_user = pay + "\n\n" + WS.writer_brief(TSM.PDIR, plan, k) + \
        "\n\n" + WS.slots_text(WS.slots_for_act(slots, k))
    u = nar["messages"][0]["content"]
    sec = u[u.index("# THE SLOTS TO REWRITE"):u.index("# THE ACT AS IT")]
    others = [s["slot"] for s in mine if s["slot"] != tgt["slot"]
              and f"- {s['slot']} " in sec]
    ctx = u[u.index("# THE ACT AS IT"):u.index("# THE FOOTAGE")]
    missing_ctx = [l["slot"] for l in lines if l.get("slot")
                   and f"- {l['slot']} " not in ctx]
    ratio = len(u) / len(full_user)
    ok = (devs[0] in u and f"- {tgt['slot']} " in sec and not others
          and not missing_ctx and ratio < 0.25
          and nar["system"] == sysb)
    return ok, (f"1 slot to rewrite, {len(lines)} lines as context, "
                f"{ratio:.0%} of the full act request" if ok else
                f"others {others}, missing ctx {missing_ctx}, ratio "
                f"{ratio:.2f}")


def t_no_slot():
    plan, slots, k, _mine, lines = _setup()
    nar = W.slot_fix_params(TSM.PROJ, TSM.PDIR, k, [], slots, plan, lines,
                            ["the act reads flat"], payload=_payload(5))
    return nar is None, ("no slot named -> None (whole-act resend)"
                         if nar is None else "built a narrow request anyway")


def t_partial_merge():
    _plan, slots, k, mine, lines = _setup()
    tgt = mine[1]
    new = {"slot": tgt["slot"], "narration": "Sean takes the corner sideways "
           "because the money is gone.", "payload": "reasoning",
           "delivery": "normal"}
    out, _notes = WS.merge_revision(lines, [new], WS.slots_for_act(slots, k),
                                    k)
    by = {l.get("slot"): l for l in out}
    before = {l.get("slot"): l.get("narration") for l in lines}
    changed = [s for s, t in before.items() if by.get(s, {}).get(
        "narration") != t]
    ok = changed == [tgt["slot"]] and len(out) == len(lines)
    return ok, (f"only {tgt['slot']} changed; {len(out)} lines kept" if ok
                else f"changed {changed}, {len(out)} vs {len(lines)}")


TESTS = [("SLICE-KEEPS-NEAR", t_slice), ("NARROW-REQUEST", t_narrow),
         ("NO-SLOT-NO-NARROW", t_no_slot), ("PARTIAL-MERGE", t_partial_merge)]

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
        print(f"{'PASS' if ok else 'FAIL'}  {name:18s} {msg}")
    print("-" * 60)
    print("test_fix_round: all pass" if not fails
          else f"test_fix_round: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
