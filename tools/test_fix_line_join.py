# -*- coding: utf-8 -*-
"""test_fix_line_join.py - fix_line --join says several short lines as one.

Lost in the Stars' unmasking was four 1.6 s lines ("Shen Man leads." /
"Chen Mai, unmasked." / ...): no sentence fits one of them. --join makes
them one line over their footage.

  JOIN-SAVED     two neighbouring slot lines joined: one line with both
                 slots in `parts`, the second gone from draft.json AND its
                 act file, the draft gates still conserve every slot
  JOIN-TOO-LONG  a piece longer than its footage reads is refused and
                 nothing changes
  NEARBY-POINT   a story point told by a line just before counts as said

Run:  python tools/test_fix_line_join.py      (exit 0 = all pass)
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


def _pair(pdir, lines):
    import write_api as W
    import write_slots as WS
    owner = W.act_of_lines(pdir)
    so = W.slots_of_lines(pdir, owner)
    for x, y in zip(lines, lines[1:]):
        a, b = str(x["id"]), str(y["id"])
        if a not in so or b not in so or x.get("parts") or y.get("parts"):
            continue
        sa, sb = so[a], so[b]
        if sa["act"] != sb["act"] or sa["role"] in WS.NO_JOIN or \
                sb["role"] in WS.NO_JOIN or sb.get("after_skip") or \
                sb.get("transition") or sa.get("quote") or sb.get("quote") \
                or sa.get("must_keys") or sb.get("must_keys"):
            continue
        if abs(WS._pt(sb["clip_start"]) - WS._pt(sa["clip_end"])) > \
                WS.JOIN_GAP:
            continue
        return x, y
    return None, None


def main() -> int:
    import fix_line as FL
    import test_write_slots as TWS
    import write_slots as WS
    from pipeline.preflight import budget_words
    TWS.test_draft_slots()
    pdir, proj = TWS.PDIR, TWS.PROJ
    d = json.loads((pdir / "draft.json").read_text(encoding="utf-8"))
    x, y = _pair(pdir, d["lines"])
    res = []
    if x is None:
        print("FAIL  JOIN-SAVED     no joinable pair in the fixture")
        return 1
    files = [pdir / "draft.json"] + sorted((pdir / "draft.json.d").glob(
        "act*.json"))
    before = {f: f.read_bytes() for f in files}
    long_ = " ".join(["word"] * (budget_words(
        WS._pt(x["clip_end"]) - WS._pt(x["clip_start"])) + 5))
    b0 = io.StringIO()
    with redirect_stdout(b0):
        rc0 = FL.main(["--project", proj, "--line", str(x["id"]), "--join",
                       str(y["id"]), "--text", f"{long_} | He runs."])
    same = all(f.read_bytes() == b for f, b in before.items())
    res.append(("JOIN-TOO-LONG", rc0 == 2 and same and "footage reads"
                in b0.getvalue(), f"rc {rc0}, unchanged {same}"))
    b1 = io.StringIO()
    with redirect_stdout(b1):
        rc = FL.main(["--project", proj, "--line", str(x["id"]), "--join",
                      str(y["id"]), "--text",
                      "He grabs the keys | and runs for the car."])
    d2 = json.loads((pdir / "draft.json").read_text(encoding="utf-8"))
    ids = [str(l["id"]) for l in d2["lines"]]
    j = next((l for l in d2["lines"] if str(l["id"]) == str(x["id"])), {})
    acts_n = [len(json.loads(f.read_text(encoding="utf-8"))["lines"])
              for f in files[1:]]
    acts_b = [len(json.loads(before[f].decode("utf-8"))["lines"])
              for f in files[1:]]
    ok = (rc == 0 and str(y["id"]) not in ids
          and len((j.get("parts") or [])) == 2
          and j.get("narration") == "He grabs the keys and runs for the car."
          and sum(acts_b) - sum(acts_n) == 1
          and "DRAFT-CONSERVATION" not in b1.getvalue())
    res.append(("JOIN-SAVED", ok, f"rc {rc}; line {y['id']} gone: "
                f"{str(y['id']) not in ids}; parts {len(j.get('parts') or [])}"
                f"; act lines {sum(acts_b)} -> {sum(acts_n)}"
                + ("" if ok else "\n" + b1.getvalue()[-800:])))
    ls = [{"id": 1, "narration": "Chen Mai is really Shen Man."},
          {"id": 2, "narration": ""},
          {"id": 3, "narration": "A flashback."}]
    near = WS.said_nearby(ls, 3, [["Shen", "Man"]]) and \
        not WS.said_nearby(ls, 1, [["Shen", "Man"]]) and \
        not WS.said_nearby(ls, 3, [["Muzi"]])
    res.append(("NEARBY-POINT", near, "a point told just before counts"))
    bad = 0
    for name, ok, msg in res:
        print(f'{"PASS" if ok else "FAIL"}  {name:<14} {msg}')
        bad += not ok
    print("-" * 60)
    print("test_fix_line_join: all pass" if not bad else
          f"test_fix_line_join: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
