# -*- coding: utf-8 -*-
"""test_model_compare.py - the comparison sends the REAL requests and writes
nothing into the draft (offline, a fake client).

  SAME-REQUEST    each variant gets the draft stage's own act request and
                  the cold-read's own request, only model / effort changed
  DRAFT-UNTOUCHED draft.json, plan.json and the act files are byte-identical
                  after the run; the replies are under model_compare/
  MEASURED        a reply that fits its slots shows 0 deviations; one that
                  misses a quote and runs long shows them; the report names
                  every variant and lists the lines slot by slot

Run:  python tools/test_model_compare.py      (exit 0 = all pass)
"""
from __future__ import annotations

import io
import json
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402


def main() -> int:
    import tag_batch as TB
    import test_write_slots as TWS
    import write_api as W
    import write_slots as WS
    import model_compare as MC
    TWS.test_draft_slots()
    pdir, proj = TWS.PDIR, TWS.PROJ
    plan = json.loads((pdir / "plan.json").read_text(encoding="utf-8"))
    mine = WS.slots_for_act(plan["slots"], 1)
    good = {"act": 1, "lines": [TWS._fill(s, i) for i, s in enumerate(mine)
                                if s["role"] != "hold"]}
    bad = json.loads(json.dumps(good))
    q = next(l for l in bad["lines"] if any(
        s["slot"] == l["slot"] and s.get("quote") for s in mine))
    q["narration"] = " ".join(["word"] * 60) + "."
    sent = []

    class Msgs:
        def stream(self, **p):
            sent.append(p)
            sys_ = json.dumps(p.get("system"))
            if "cold" in sys_.lower() and "act<N>.json" not in sys_:
                body = {"checked": "x", "findings": [
                    {"kind": "clarity", "ids": [3], "text": "unclear"}]}
            else:
                body = good if "haiku" not in p["model"] else bad
            m = {"content": [{"type": "text", "text": json.dumps(body)}],
                 "stop_reason": "end_turn",
                 "usage": {"input_tokens": 1000, "output_tokens": 500}}

            class S:
                def __enter__(s):
                    return s

                def __exit__(s, *a):
                    return False

                def get_final_message(s):
                    return m
            return S()

    class Client:
        messages = Msgs()
    files = [pdir / "draft.json", pdir / "plan.json"] + sorted(
        (pdir / "draft.json.d").glob("act*.json"))
    before = {f: f.read_bytes() for f in files}
    saved = TB.CLIENT_FACTORY
    TB.CLIENT_FACTORY = lambda: Client()
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = MC.main(["--project", proj, "--act", "1", "--variants",
                          "sonnet,sonnet@low,haiku"])
    finally:
        TB.CLIENT_FACTORY = saved
    want = W.act_request(proj, pdir, 1, W.draft_system(pdir),
                         slots=plan["slots"], plan=plan)
    drafts = [p for p in sent if "act<N>.json" in json.dumps(p["system"])]
    same = (len(drafts) == 3 and all(
        p["messages"] == want["messages"] and p["system"] == want["system"]
        for p in drafts) and [p["model"] for p in drafts] ==
        ["claude-sonnet-5-5"] * 2 + ["claude-haiku-5-5"]
        and drafts[1].get("output_config", {}).get("effort") == "low")
    untouched = all(f.read_bytes() == b for f, b in before.items())
    rep = (pdir / "model_compare" / "act1.compare.md")
    text = rep.read_text(encoding="utf-8") if rep.exists() else ""
    dsec = text.split("## Cold-read")[0]
    rows = {ln.split("|")[1].strip(): ln for ln in dsec.splitlines()
            if ln.startswith("| sonnet") or ln.startswith("| haiku")}
    dev = lambda r: int(r.split("|")[9].strip()) if r else -1  # noqa: E731
    gr = lambda r: int(r.split("|")[10].strip()) if r else -1  # noqa: E731
    measured = (rc == 0 and dev(rows.get("sonnet-5-5")) == 0
                and dev(rows.get("haiku-5-5")) > 0
                and "## The lines, slot by slot" in text
                and "*haiku-5-5*" in text and "Cold-read" in text)
    cases = [("SAME-REQUEST", same, "3 variants, the stage's own request, "
              "model / effort only"),
             ("DRAFT-UNTOUCHED", untouched, "draft, plan, act files "
              "byte-identical"),
             ("MEASURED", measured, f"good reply 0 deviations, bad one "
              f"{dev(rows.get('haiku-5-5'))}; report lists lines by slot; "
              f"gate-rule column {gr(rows.get('sonnet-5-5'))} / "
              f"{gr(rows.get('haiku-5-5'))}")]
    shutil.rmtree(config.project_dir("_selftest_writeplan"), ignore_errors=True)
    bad_n = 0
    for name, ok, msg in cases:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<16} {msg}")
        bad_n += not ok
    if bad_n:
        print(buf.getvalue()[-1500:])
    print("-" * 60)
    print(f"test_model_compare: {bad_n} FAILURE(S)" if bad_n
          else "test_model_compare: all pass")
    return 1 if bad_n else 0


if __name__ == "__main__":
    sys.exit(main())
