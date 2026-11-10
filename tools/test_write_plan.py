# -*- coding: utf-8 -*-
"""test_write_plan.py - the plan before the acts, the resolve loop, and the
mechanical UNWATCHABLE-FOOTAGE fix. Offline, mocked client.

  PLAN-VALIDATES       a one-line-per-beat plan (furious72015's shape) fails
                       with the contour gate's own messages, a thin anchor,
                       a '<film> (<year>)' title and a long hook opener; a
                       planned contour passes
  CONTOUR-REPAIR       code makes a plan's line counts pass [PACING-CONTOUR]:
                       a one-line-per-beat plan comes out with no contour
                       violation, mandatory beats keep a line, anchors keep
                       their dwell, nothing over LINES_MAX; a planned contour
                       is not touched
  PLAN-REVISION        a failing plan gets ONE revision request carrying the
                       violations code could NOT fix (title, hook) and none it
                       did (contour); the fixed plan is written; two failures
                       stop with exit PLAN_STOPPED, plan_rejected.json and no
                       plan.json
  ACT-FOLLOWS-PLAN     each act request carries its slice of the plan; the
                       plan's hook is act 1's first line (over_montage, no
                       window); the plan's title is the draft's title; an act
                       that did not follow the plan gets the mismatches as
                       round-1 feedback
  RESOLVE-CLOSES       RESOLVED / ANSWERED entries are written in the format
                       review_artifacts parses and close their findings; a
                       short ANSWERED, a RESOLVED with no change, and a change
                       to a line no finding names are rejected; only changed
                       lines are re-signed; the act files carry the change
  RESOLVE-SAMEPOINT    an open SAME-POINT pair is answered in review.md with
                       both ids, which is what closes it
  RESOLVE-STOPS        at most 2 rounds, then it lists what is left
  RUNPS1-HALT          with the key, the draft halt runs resolve and prints
                       what is left + the command, not the subagent loop
  UNWATCHABLE-FIX      a window on black is moved inside its beat, never onto
                       another line, never across a reveal; an unfixable one
                       is left for the writer

Run:  python tools/test_write_plan.py
"""
from __future__ import annotations

import io
import json
import shutil
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import tag_batch as TB  # noqa: E402
import write_api as W  # noqa: E402
import write_plan as WP  # noqa: E402
from pipeline import review_artifacts as RA  # noqa: E402

SRC = config.project_dir("tokyodrift2006")
PROJ = "_selftest_writeplan"
PDIR = config.project_dir(PROJ)


def _setup():
    shutil.rmtree(PDIR, ignore_errors=True)
    shutil.copytree(SRC, PDIR, ignore=shutil.ignore_patterns(
        "narration", "frames", "*.mp4", "*.wav", "_*", "plan*.json"))


def _j(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def msg(obj):
    return NS(content=[NS(type="text", text=json.dumps(obj))],
              stop_reason="end_turn",
              usage=NS(input_tokens=9000, output_tokens=3000,
                       cache_creation_input_tokens=0,
                       cache_read_input_tokens=0, cache_creation=None))


class Client:
    def __init__(self, sync=None, batch=None):
        self.sync, self.batchf = sync, batch
        self.calls, self.batches = [], []
        self.messages = NS(create=self._create, batches=NS(
            create=self._bcreate, retrieve=lambda b: NS(processing_status="ended"),
            results=self._results))

    def _create(self, **p):
        self.calls.append(json.loads(json.dumps(p)))
        return self.sync(p, len(self.calls))

    def _bcreate(self, requests):
        self.batches.append(list(requests))
        return NS(id=f"b{len(self.batches)}")

    def _results(self, bid):
        for r in self.batches[int(bid[1:]) - 1]:
            yield NS(custom_id=r["custom_id"], result=NS(
                type="succeeded", message=self.batchf(r["custom_id"],
                                                       r["params"])))


def _run(client, *argv):
    TB.CLIENT_FACTORY = lambda: client
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = W.main(list(argv))
    return rc, buf.getvalue()


_AB = {}


def _ab():
    if not _AB:
        _AB.update(WP.act_beats(PROJ, W._tool))
    return _AB


def _plan(shape="good"):
    """A plan over the fixture's real beats. 'flat' = one line a beat."""
    from pipeline import angle_spec
    ab = _ab()
    anchors = {b for a in angle_spec.load(PDIR)["anchors"] for b in a["beats"]}
    mand = set(_j(PDIR / "coverage_policy.json").get("mandatory") or [])
    beats, run = [], 0
    for k in sorted(ab):
        for bid in ab[k]:
            if shape == "flat":
                n, foot = 1, False
            elif bid in anchors:
                n, foot, run = 5, False, 0
            elif bid in mand:
                run += 1
                n, foot = (2 if run % 3 == 0 else 1), False
            else:
                n, foot, run = 0, True, 0
            beats.append({"beat": bid, "lines": n, "footage": foot,
                          "hold_after": True, "film_speaks": False,
                          "why": "x"})
    lo, hi = WP.word_band(PROJ)
    per = (lo + hi) // 2 // len(ab)
    return {"title": ("The Fast and the Furious (2006)" if shape == "flat"
                      else "Shipped to Tokyo, a Kid Learns to Drift for His Life"),
            "hook": {"narration": ("He had one night left and nobody in that "
                                   "garage told him why it mattered."
                                   if shape == "flat" else
                                   "He cannot drive sideways. Yet."),
                     "hook_question": "Will a kid who crashes everything "
                                      "learn to drift before it costs him?"},
            "acts": [{"act": k, "word_budget": per} for k in sorted(ab)],
            "beats": beats}


def test_plan_validates():
    _setup()
    ab = _ab()
    flat = WP.validate_plan(_plan("flat"), PROJ, PDIR, ab)
    good = WP.validate_plan(_plan("good"), PROJ, PDIR, ab)
    need = ["beats in a row", "anchor(s) are below", "(<year>)",
            "the hook opens with"]
    miss = [n for n in need if not any(n in v for v in flat)]
    if miss:
        return False, f"flat plan not caught on {miss}: {flat}"
    if good:
        return False, f"a planned contour was rejected: {good}"
    return True, (f"flat plan: {len(flat)} violation(s) in the gates' words; "
                  f"planned contour: 0")


def test_contour_repair():
    import copy
    from pipeline import angle_spec
    _setup()
    ab = _ab()
    contour = ("anchor(s) are below", "contour is FLAT", "beats in a row")
    flat = _plan("flat")
    ch = WP.repair_contour(flat, PDIR)
    left = [v for v in WP.validate_plan(flat, PROJ, PDIR, ab)
            if any(c in v for c in contour)]
    if left:
        return False, f"contour still fails after repair: {left}"
    mand = set(_j(PDIR / "coverage_policy.json").get("mandatory") or [])
    by = {b["beat"]: b for b in flat["beats"]}
    lost = [m for m in mand if m in by and by[m]["lines"] < 1]
    if lost:
        return False, f"mandatory beat(s) lost their line: {lost[:6]}"
    for a in angle_spec.load(PDIR)["anchors"]:
        if sum(by[b]["lines"] for b in a["beats"] if b in by) < \
                config.PACING_ANCHOR_MIN_LINES:
            return False, f"anchor {a['beats']} under the minimum"
    if any(b["lines"] > WP.LINES_MAX for b in flat["beats"]):
        return False, "a beat over LINES_MAX"
    good = _plan("good")
    g0 = copy.deepcopy(good)
    if WP.repair_contour(good, PDIR) or good != g0:
        return False, "a plan that already passes was changed"
    return True, (f"flat plan: {len(ch)} count change(s), contour passes, "
                  f"mandatory and anchors intact; planned contour untouched")


def test_plan_revision():
    _setup()
    flat, good = _plan("flat"), _plan("good")
    c = Client(lambda p, n: msg(flat if n == 1 else good))
    rc, out = _run(c, "plan", "--project", PROJ)
    if rc != 0 or len(c.calls) != 2:
        return False, f"rc {rc}, {len(c.calls)} call(s)"
    rev = c.calls[1]["messages"][-1]["content"]
    written = {k: v for k, v in _j(PDIR / "plan.json").items()
               if k not in ("slots", "slot_problems", "slots_version",
                            "open_mode", "lever", "opener")}
    if "(<year>)" not in rev or "beats in a row" in rev or written != good:
        return False, ("revision did not carry the unfixable violations, "
                       "carried a contour one code should have fixed, or the "
                       "plan was not written")
    if "anchor" not in c.calls[0]["messages"][0]["content"].lower() \
            or "WORD BAND" not in c.calls[0]["messages"][0]["content"]:
        return False, "plan request lacks angle / band"
    (PDIR / "plan.json").unlink()
    c2 = Client(lambda p, n: msg(flat))
    rc2, _o = _run(c2, "plan", "--project", PROJ)
    ok = rc2 == W.PLAN_STOPPED and not (PDIR / "plan.json").exists() and \
        (PDIR / "plan_rejected.json").exists() and len(c2.calls) == 2
    if not ok:
        return False, f"two bad plans: rc {rc2}, {len(c2.calls)} call(s)"
    # the rejected plan, re-run: counts repaired by code, NO API call, when
    # the only problems were counts
    rj = _j(PDIR / "plan_rejected.json")
    good_t = _plan("good")
    rj["title"], rj["hook"] = good_t["title"], good_t["hook"]
    (PDIR / "plan_rejected.json").write_text(json.dumps(rj), encoding="utf-8")
    c3 = Client(lambda p, n: msg(flat))
    rc3, out3 = _run(c3, "plan", "--project", PROJ)
    ok = (rc3 == 0 and not c3.calls and (PDIR / "plan.json").exists()
          and "no new API call" in out3)
    if not ok:
        return False, f"rejected plan not reused: rc {rc3}, {len(c3.calls)} call(s)"
    return ok, ("bad plan -> contour fixed by code, one revision with the "
                "rest -> written; two bad -> stop (exit 4), plan_rejected.json; "
                "rerun repairs that file with no API call")


def test_act_follows_plan():
    _setup()
    shutil.rmtree(PDIR / "draft.json.d")
    (PDIR / "draft.json").unlink()
    plan = _plan("good")
    (PDIR / "plan.json").write_text(json.dumps(plan))
    ab = _ab()
    by = {b["beat"]: b["lines"] for b in plan["beats"]}

    def act_reply(cid, p):
        k = int(cid[3:])
        lines, i = [], k * 100
        for bid in ab[k]:
            n = by[bid] if k != 2 else 1          # act 2 ignores the plan
            for _ in range(n):
                i += 1
                lines.append({"id": i, "note": bid, "narration": f"Line {i}.",
                              "delivery": "normal",
                              "clip_start": f"00:{i // 60 % 60:02d}:{i % 60:02d}.000",
                              "clip_end": f"00:{i // 60 % 60:02d}:{i % 60:02d}.500"})
        return msg({"act": k, "lines": lines})
    c = Client(None, act_reply)
    real = W.run_gates
    W.run_gates = lambda project: (1, [])
    try:
        rc, out = _run(c, "draft", "--project", PROJ)
    finally:
        W.run_gates = real
    first = c.batches[0]
    if not all("THE PLAN FOR YOUR BEATS" in r["params"]["messages"][0]["content"]
               for r in first):
        return False, "an act request does not carry its plan slice"
    d = _j(PDIR / "draft.json")
    # R0: the montage hook line is GONE - the cold open is OPEN slots now,
    # and this unslotted fixture carries none; what must never come back
    # is a delivery "hook" line over a montage at 0:00
    if any(ln.get("over_montage") or ln.get("delivery") == "hook"
           for ln in d["lines"]):
        return False, "a montage hook line survived at the front"
    if d["title"] != plan["title"]:
        return False, f"title {d['title']!r}"
    r1 = {r["custom_id"]: r["params"]["messages"][0]["content"]
          for r in c.batches[1]} if len(c.batches) > 1 else {}
    if "act2" not in r1 or "(plan)" not in r1["act2"] or "act1" in r1:
        return False, f"plan mismatch not fed back to act 2 only: {sorted(r1)}"
    return True, ("plan slices in every act request; no montage hook line; "
                  "title from the plan; act 2's ignored plan fed back as "
                  "round-1 findings")


# ---- resolve ----------------------------------------------------------- #
def _resolve_fixture():
    _setup()
    shutil.rmtree(PDIR / "draft.json.d")
    d = PDIR / "draft.json.d"
    d.mkdir()
    lines = [{"id": 100 + i, "note": f"B{i:02d}", "delivery": "normal",
              "clip_start": f"00:01:{i * 5:02d}.000",
              "clip_end": f"00:01:{i * 5 + 4:02d}.000",
              "narration": f"Original sentence number {i} about the race."}
             for i in range(1, 9)]
    (d / "act1.json").write_text(json.dumps({"act": 1, "lines": lines}))
    W._assemble(PROJ)
    return _resolve_fixture_artifacts()


def _resolve_fixture_artifacts():
    dr = _j(PDIR / "draft.json")
    sigs = RA.draft_signatures(dr)
    block = "\n".join(f"  {k} {v}" for k, v in sigs.items())
    finds = {"cold_read.md": ["FINDING | dangling-ref | 2 | the race is unset",
                              "FINDING | ambiguous-pronoun | 3 | who is he"],
             "review.md": ["FINDING | repeated-phrasing | 4 | the race again"],
             "ending_read.md": ["FINDING | ending | 8 | it trails off"]}
    for name, fs in finds.items():
        (PDIR / name).write_text(
            f"# {name}\n\n```review-signatures\n{block}\n```\n\n"
            "```review-findings\n" + "\n".join(fs) + "\n```\n",
            encoding="utf-8")
    return dr


def test_resolve_slot_bound():
    """A rewrite keeps its slot: a REACTION reworded into plain description
    is not saved (and goes back), an echoed payload on a line nobody asked to
    relabel is ignored, a code-owned label is restored."""
    dr = _resolve_fixture()
    d = PDIR / "draft.json.d"
    act = _j(d / "act1.json")
    roles = {2: ("reaction", "eval"), 3: ("action", None), 4: ("bridge", None),
             6: ("hold", None)}       # every real draft has holds (it crashed)
    slots = []
    for i, ln in enumerate(act["lines"], 1):
        role, voice = roles.get(i, ("bridge", None))
        ln["slot"] = f"S{i:03d}"
        ln["payload"] = {"reaction": "judgment"}.get(role, "stake")
        if role == "hold":
            ln["narration"], ln["narration_silence_seconds"] = "", 3.0
            ln["payload"] = "rest"
        if role == "reaction":
            ln["narration"] = "That's the whole price of the race, paid up front."
        if i == 3:      # an anchor ACTION that already reads as commentary
            ln["narration"] = "That's the whole race, and he floors it."
        sl_ = {"slot": ln["slot"], "act": 1, "beat": ln["note"],
               "role": role, "voice": voice, "anchor": i == 3,
               "peak": False, "band": "medium", "min_words": 1,
               "max_words": 30, "target": 8, "opens_loop": False,
               "clip_start": ln["clip_start"], "clip_end": ln["clip_end"]}
        if role == "hold":          # as derive_slots builds a hold: no band
            sl_ = {k_: v for k_, v in sl_.items()
                   if k_ not in ("band", "min_words", "max_words", "target")}
            sl_["hold"] = 3.0
        slots.append(sl_)
    (d / "act1.json").write_text(json.dumps(act))
    W._assemble(PROJ)
    _resolve_fixture_artifacts()
    (PDIR / "plan.json").write_text(json.dumps({"slots": slots}))

    def reply(cid, p):
        body = p["messages"][0]["content"]
        keys = [x.split(" | ")[0] for x in
                body.split("# OPEN FINDINGS")[1].strip().splitlines()
                if x.startswith("F")]
        return msg({"lines": [
            {"id": 2, "narration": "He drives to the garage and parks."},
            {"id": 3, "narration": "That's the whole night, and he floors it."},
            {"id": 4, "narration": "The race is set for midnight now.",
             "payload": "rest"}],
            "responses": [{"key": k, "status": "ANSWERED",
                           "text": "the line already names who and where, "
                                   "so the reading does not hold"}
                          for k in keys]})
    c = Client(None, reply)
    rc, out = _run(c, "resolve", "--project", PROJ)
    t = {str(l["id"]): l for l in _j(PDIR / "draft.json")["lines"]}
    first = (c.batches[0][0]["params"]["messages"][0]["content"]
             if c.batches else "")
    checks = [
        (t["2"]["narration"].startswith("That's the whole price"),
         "the reaction reworded as description was NOT saved"),
        ("breaks its slot" in out, "the rejection says why"),
        (t["4"]["narration"].startswith("The race is set"),
         "a rewrite that fits its slot IS saved"),
        (t["4"].get("payload") == "stake",
         "an echoed payload nobody asked about is ignored"),
        (t["3"]["narration"].startswith("That's the whole race"),
         "a 'fix' that keeps the line's fault (still commentary) is not taken"),
        ("NOW WRONG: reads as commentary" in first,
         "the reviser sees what is wrong with the line now"),
        ("[REACTION EVAL, 1-30 words]" in first
         and "[ACTION on an ANCHOR, 1-30 words" in first,
         "the reviser sees each line's slot"),
        (len(c.batches) > 1 and "| gate |" in
         c.batches[1][0]["params"]["messages"][0]["content"],
         "once the readers are answered, the draft gates' own findings "
         "come back as the next round"),
    ]
    checks.append((rc != 1 and "API error" not in out,
                   f"resolve runs to the end on a draft with a hold (rc {rc})"))
    bad = [w for ok, w in checks if not ok]
    return not bad, ("; ".join(w for _, w in checks) if not bad
                     else "FAILED: " + "; ".join(bad))


def test_fix_line():
    """tools/fix_line.py: a hand fix goes through resolve's write-back - the
    slot still binds it, the finding closes RESOLVED, the line is re-signed
    in the artifact, the act file follows."""
    import fix_line as FL
    test_resolve_slot_bound()          # leaves a slot-written fixture
    dr = _j(PDIR / "draft.json")
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc_bad = FL.main(["--project", PROJ, "--line", "2",
                          "--text", "He drives home to the garage."])
    before = _j(PDIR / "draft.json")
    refused = rc_bad == 2 and "NOT saved" in buf.getvalue() and \
        before["lines"][1]["narration"] == dr["lines"][1]["narration"]
    good = "Nobody gets to race for free tonight."
    with redirect_stdout(io.StringIO()):
        FL.main(["--project", PROJ, "--line", "2", "--text", good])
    after = _j(PDIR / "draft.json")
    act = _j(PDIR / "draft.json.d" / "act1.json")
    cr = RA.parse_artifact(PDIR / "cold_read.md")
    with redirect_stdout(io.StringIO()):
        FL.main(["--project", PROJ, "--line", "4", "--claim", "narration"])
    c4 = next(l for l in _j(PDIR / "draft.json")["lines"] if l["id"] == 4)
    a4 = [l for l in _j(PDIR / "draft.json.d" / "act1.json")["lines"]
          if l.get("narration") == c4.get("narration")]
    claimed = ((c4.get("claim") or {}).get("type") == "narration"
               and (c4.get("claim") or {}).get("requires_visual") is False
               and a4 and (a4[0].get("claim") or {}).get("type") == "narration")
    checks = [
        (claimed, "--claim narration lands in draft.json and the act file"),
        (refused, "a text that breaks the slot is refused, nothing written"),
        (after["lines"][1]["narration"] == good, "draft.json updated"),
        (any(l.get("narration") == good for l in act["lines"]),
         "the act file follows"),
        (cr["signatures"].get("2") == RA.line_signature(good),
         "the line is re-signed in cold_read.md"),
    ]
    bad = [w for ok, w in checks if not ok]
    return not bad, ("; ".join(w for _, w in checks) if not bad
                     else "FAILED: " + "; ".join(bad))


def test_resolve_closes():
    dr = _resolve_fixture()
    before = RA.parse_artifact(PDIR / "cold_read.md")["signatures"]
    real_sp = WP.open_findings

    def reply(cid, p):
        fs = {ln.split(" | ")[0]: ln for ln in
              p["messages"][0]["content"].split("# OPEN FINDINGS")[1]
              .strip().splitlines()}
        key = {v.split(" | ")[2]: k for k, v in fs.items()}
        return msg({
            "lines": [{"id": 2, "narration": "The race he was dared into is "
                                             "set up now."},
                      {"id": 6, "narration": "An unrequested rewrite."}],
            "responses": [
                {"key": key["dangling-ref"], "status": "RESOLVED",
                 "text": "named the race in the line"},
                {"key": key["ambiguous-pronoun"], "status": "ANSWERED",
                 "text": "only one man has been named since line 1, so the "
                         "pronoun has a single antecedent"},
                {"key": key["repeated-phrasing"], "status": "ANSWERED",
                 "text": "fine"},
                {"key": key["ending"], "status": "RESOLVED",
                 "text": "rewrote the ending"}]})
    c = Client(None, reply)
    # this test is about the READERS' findings; the fixture's own gate
    # findings (which now ride in the same round) would legitimately name
    # line 6, so they are held out here - RESOLVE-SLOT-BOUND covers them
    real_gf = W.gate_findings
    W.gate_findings = lambda project, wide=None: []
    try:
        rc, out = _run(c, "resolve", "--project", PROJ)
    finally:
        WP.open_findings = real_sp
        W.gate_findings = real_gf
    dr2 = _j(PDIR / "draft.json")
    t = {str(l["id"]): l["narration"] for l in dr2["lines"]}
    cr = RA.parse_artifact(PDIR / "cold_read.md")
    if cr["errors"]:
        return False, f"cold_read.md does not parse: {cr['errors']}"
    rr = RA.review_report(dr2, PDIR)
    cold = [e for e in rr["errors"] if e.startswith("[COLD-READ]")]
    checks = [
        ("set up now" in t["2"], "line 2 changed"),
        (t["6"] == dr["lines"][5]["narration"], "unnamed line 6 untouched"),
        (cr["signatures"]["2"] == RA.line_signature(t["2"]), "line 2 re-signed"),
        (all(cr["signatures"][k] == before[k] for k in before if k != "2"),
         "other signatures untouched"),
        (not cold, f"COLD-READ closed ({cold[:1]})"),
        (any("RESOLVED | dangling-ref | 2" in x["raw"] for x in cr["findings"]),
         "RESOLVED entry written"),
        ("stays open" in out and "no finding names it" in out,
         "short ANSWERED / RESOLVED-without-change / unnamed change rejected"),
        ("set up now" in json.dumps(_j(PDIR / "draft.json.d/act1.json")),
         "act file carries the change"),
    ]
    bad = [w for ok, w in checks if not ok]
    return (not bad), ("entries close their findings, rejects kept open, only "
                       "changed lines re-signed" if not bad else f"{bad}")


def test_resolve_samepoint():
    dr = _resolve_fixture()
    for n in ("cold_read.md", "ending_read.md"):
        (PDIR / n).unlink()
    from pipeline import semantic_dup as SD
    real = SD.adjacent_duplicates
    SD.adjacent_duplicates = lambda lines, *a, **k: [
        {"a": 4, "b": 5, "why": "both assert motion"}]

    def reply(cid, p):
        body = p["messages"][0]["content"]
        keys = [ln.split(" | ")[0] for ln in
                body.split("# OPEN FINDINGS")[1].strip().splitlines()]
        return msg({"lines": [], "responses": [
            {"key": k, "status": "ANSWERED",
             "text": "line 5 builds on line 4 with a new consequence, "
                     "it does not restate it"} for k in keys]})
    try:
        c = Client(None, reply)
        rc, out = _run(c, "resolve", "--project", PROJ)
        from pipeline import samepoint_gates as SPG
        rep = SPG.samepoint_report(_j(PDIR / "draft.json"), PDIR)
    finally:
        SD.adjacent_duplicates = real
    open_sp = [e for e in rep["errors"] if "not been adjudicated" in e]
    return (not open_sp), ("SAME-POINT pair 4+5 adjudicated in review.md"
                           if not open_sp else open_sp[0])


def test_resolve_stops():
    _resolve_fixture()
    c = Client(None, lambda cid, p: msg({"lines": [], "responses": []}))
    rc, out = _run(c, "resolve", "--project", PROJ)
    ok = rc == 2 and len(c.batches) == int(config.WRITE_RESOLVE_ROUNDS) and "STOPPING" in out \
        and "dangling-ref" in out
    return ok, f"rc {rc}, {len(c.batches)} round(s), remaining findings listed"


def test_unwatchable_fix():
    lines = [
        {"id": 1, "note": "B01", "narration": "two words",
         "clip_start": "00:00:10.000", "clip_end": "00:00:16.000"},
        {"id": 2, "note": "B02", "narration": "next line",
         "clip_start": "00:00:30.000", "clip_end": "00:00:36.000"},
        {"id": 3, "note": "B03", "narration": "stuck",
         "clip_start": "00:00:50.000", "clip_end": "00:00:56.000"},
    ]
    # black at 10-13 (line 1: the part after it fits); line 3 is black
    # end to end and its beat holds nothing else
    def measure(a, b):
        spans = []
        if a < 13 and b > 10:
            spans.append((max(a, 10.0), min(b, 13.0), ["black"]))
        if a < 60 and b > 48:
            spans.append((max(a, 48.0), min(b, 60.0), ["text card"]))
        return spans
    import write_plan as _wp
    from pipeline import draft as D
    real_bt, real_rm = D.beat_times, D.parse_reveal_map
    D.beat_times = lambda p: {"ordered": [("B01", 8.0), ("B02", 28.0),
                                          ("B03", 48.0), ("B04", 60.0)]}
    D.parse_reveal_map = lambda p: [{"id": "R1", "land_sec": 26.0}]
    try:
        acts = _wp.fix_unwatchable(PROJ, lines, measure=measure)
    finally:
        D.beat_times, D.parse_reveal_map = real_bt, real_rm
    a1 = W.parse_ts(lines[0]["clip_start"]) if hasattr(W, "parse_ts") else None
    from pipeline.draft import parse_ts
    s1, e1 = parse_ts(lines[0]["clip_start"]), parse_ts(lines[0]["clip_end"])
    ok = (s1 >= 13.0 and e1 <= 26.0 and e1 <= 28.0
          and lines[1]["clip_start"] == "00:00:30.000"
          and lines[2]["clip_start"] == "00:00:50.000"
          and any("left for the writer" in x for x in acts))
    return ok, (f"line 1 moved to {s1:.1f}-{e1:.1f}s (inside B01, before the "
                f"26s reveal, off line 2); line 3 left for the writer")


def test_runps1_halt():
    src = (ROOT / "run.ps1").read_text(encoding="utf-8")
    i = src.find("write_api.py resolve --project $Project")
    j = src.find('Halt "DRAFT vong $($round+1)/3')
    k = src.rfind("$env:ANTHROPIC_API_KEY", 0, i)
    blk = src[k:j]
    ok = (0 < k < i < j and 'Halt "DRAFT - gate con loi sau vong API"' in blk
          and "exit 0" in blk and "subagent" not in blk.split("Halt")[1])
    return ok, ("with the key: resolve, then a halt listing what is left and "
                "the command - the subagent round text is never reached")


TESTS = {
    "PLAN-VALIDATES":    test_plan_validates,
    "CONTOUR-REPAIR":    test_contour_repair,
    "PLAN-REVISION":     test_plan_revision,
    "ACT-FOLLOWS-PLAN":  test_act_follows_plan,
    "RESOLVE-CLOSES":    test_resolve_closes,
    "RESOLVE-SAMEPOINT": test_resolve_samepoint,
    "RESOLVE-SLOT-BOUND": test_resolve_slot_bound,
    "FIX-LINE":          test_fix_line,
    "RESOLVE-STOPS":     test_resolve_stops,
    "UNWATCHABLE-FIX":   test_unwatchable_fix,
    "RUNPS1-HALT":       test_runps1_halt,
}

if __name__ == "__main__":
    bad = 0
    saved = TB.CLIENT_FACTORY
    want = sys.argv[1:] or list(TESTS)
    try:
        for name in want:
            try:
                ok, m = TESTS[name]()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, m = False, f"{type(e).__name__}: {e}"
            print(f'{"PASS" if ok else "FAIL"}  {name:<18} {m}')
            bad += (not ok)
    finally:
        TB.CLIENT_FACTORY = saved
        shutil.rmtree(PDIR, ignore_errors=True)
    print("-" * 60)
    print("test_write_plan: all pass" if not bad else
          f"test_write_plan: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
