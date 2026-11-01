# -*- coding: utf-8 -*-
"""test_picture_check.py - [PICTURE-CHECK] offline, on a real smoke render.

The fixture is tools/test_render_smoke.py's synthetic film, rendered for real
(own project dir), with the Anthropic client mocked.

  RENDER-NEVER-BLOCKS  with the key set and a client that raises, the render
                       still completes and says the check was not submitted
  REQUEST-SEES-ONLY    one request per narrated line in timeline.json; each
                       holds the narration text and 3 frames <= 512 px and
                       nothing else (no clip window, beat note, shot label)
  SPANS-IN-FINAL       frames are taken inside each line's out_start..out_end,
                       which sit after the prepended intro
  ALL-MATCH-PASSES     all "fits" -> PICTURE-CHECK PASS added to
                       final_report.md, every earlier check kept
  CAUSES               wrong shot / runs into a neighbouring scene / repeated
                       footage / contradicts / unwatchable assigned from the
                       clip plan; WARN, worst rows with output timestamps;
                       the token cost is printed
  DEFECT-RULE          only wrong-scene / contradicts / unwatchable are
                       defects: 90 "unclear" lines are 0 defects
  FINAL-OVERRIDE       --final/--timeline measure another render, leave
                       final_report.md alone; one without the other refused
  CALIBRATE            BAD + GOOD render -> defects per render and cause,
                       picture_calibration.json; project state untouched
  STALE-FINAL          final.mp4 re-written after submit -> SKIPPED, not PASS
  HOOK-SUBMITS         render's hook submits the batch when the key is set

Run:  python tools/test_picture_check.py
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
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
import picture_check as PCT  # noqa: E402
import test_render_smoke as T  # noqa: E402
from pipeline import picture_check as PC  # noqa: E402

PROJ = "_selftest_picchk"
PDIR = config.project_dir(PROJ)
KEY = "fake-test-key-123"


def _msg(obj):
    return NS(content=[NS(type="text", text=json.dumps(obj))],
              stop_reason="end_turn",
              usage=NS(input_tokens=1500, output_tokens=60,
                       cache_creation_input_tokens=0,
                       cache_read_input_tokens=0, cache_creation=None))


class Client:
    """Mock batches API. `reply(cid, params, batch_no)` -> the JSON answer."""

    def __init__(self, reply=None):
        self.reply = reply or (lambda cid, p, n: {
            "verdict": "fits", "reason": "the right scene",
            "frames": [True] * 5})
        self.requests = []
        self.batches = {}
        self.messages = NS(batches=NS(create=self._create,
                                      retrieve=self._retrieve,
                                      results=self._results))

    def _create(self, requests):
        self.requests = list(requests)
        bid = f"msgbatch_test{len(self.batches)}"
        self.batches[bid] = (len(self.batches), list(requests))
        return NS(id=bid)

    def _retrieve(self, bid):
        return NS(processing_status="ended")

    def _results(self, bid):
        n, reqs = self.batches[bid]
        for r in reqs:
            yield NS(custom_id=r["custom_id"], result=NS(
                type="succeeded",
                message=_msg(self.reply(r["custom_id"], r["params"], n))))


def _render():
    """Render the smoke fixture once, with the key set and a client that
    raises - which is also the never-blocks case."""
    from pipeline import intro as _intro
    from pipeline.render import render
    proj0, T.PROJ = T.PROJ, PROJ
    orig = T._stub_intro_tts()
    restore = T._no_stems()
    old_f, old_k = TB.CLIENT_FACTORY, os.environ.get(TB.KEY_ENV)

    def boom():
        raise RuntimeError("api down (simulated)")
    TB.CLIENT_FACTORY = boom
    os.environ[TB.KEY_ENV] = KEY
    flag0, config.PICTURE_CHECK_AT_RENDER = config.PICTURE_CHECK_AT_RENDER, True
    from pipeline import render as R
    buf_console = R.console
    from rich.console import Console
    R.console = Console(record=True, width=300)
    try:
        pdir, draft = T._setup()
        narration = T._narration_for(pdir, draft["lines"])
        final = render(PROJ, draft, narration, music=None, captions=False,
                       keep_temp=False, force_clips=True)
        log = R.console.export_text()
        return Path(final), log
    finally:
        R.console = buf_console
        config.PICTURE_CHECK_AT_RENDER = flag0
        TB.CLIENT_FACTORY = old_f
        if old_k is None:
            os.environ.pop(TB.KEY_ENV, None)
        else:
            os.environ[TB.KEY_ENV] = old_k
        _intro._tts_line = orig
        restore()
        T.PROJ = proj0


STATE = {}


def _run(client, *argv):
    TB.CLIENT_FACTORY = lambda: client
    (PDIR / PC.STATE_FILE).unlink(missing_ok=True)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = PCT.main(["--project", PROJ, *argv])
    return rc, buf.getvalue()


def _row(name="PICTURE-CHECK"):
    md = (PDIR / "final_report.md").read_text(encoding="utf-8")
    m = re.search(rf"^\| `{name}` \| \*\*(\w+)\*\* \| (.*) \|$", md, re.M)
    return (m.group(1), m.group(2)) if m else (None, None), md


def test_render_never_blocks():
    final, log = _render()
    STATE["final"] = final
    tl = json.loads((PDIR / "timeline.json").read_text(encoding="utf-8"))
    STATE["timeline"] = tl
    STATE["checks_before"] = len(json.loads(
        (PDIR / "final_report.json").read_text(encoding="utf-8"))["checks"])
    ok = final.exists() and "could not be submitted" in log
    return ok, ("render completed with a failing API client; the check was "
                "reported as not submitted" if ok else log[-300:])


def test_request_sees_only():
    c = Client()
    rc, out = _run(c)
    draft = json.loads((PDIR / "draft.json").read_text(encoding="utf-8"))
    narrated = {ln["id"] for ln in draft["lines"]
                if str(ln.get("narration") or "").strip()}
    want = [t["id"] for t in STATE["timeline"]["lines"] if t["id"] in narrated]
    got = [int(r["custom_id"].split("-")[1]) for r in c.requests]
    if rc != 0 or got != want:
        return False, f"rc {rc}, requests for {got}, want {want}"
    by = {ln["id"]: ln for ln in draft["lines"]}
    for r in c.requests:
        lid = int(r["custom_id"].split("-")[1])
        content = r["params"]["messages"][0]["content"]
        texts = [b["text"] for b in content if b["type"] == "text"]
        imgs = [b for b in content if b["type"] == "image"]
        if (texts[0] != f"Narration: {by[lid]['narration']}"
                or len(imgs) != config.PICTURE_CHECK_FRAMES):
            return False, f"line {lid}: {texts[:2]}, {len(imgs)} image(s)"
        # text the model reads (base64 image data can contain any substring)
        blob = "\n".join(texts) + r["params"]["system"][0]["text"]
        if set(r["params"]) - {"model", "max_tokens", "system", "messages",
                               "output_config"}:
            return False, f"unexpected request fields {sorted(r['params'])}"
        for leak in (by[lid].get("clip_start"), by[lid].get("note"),
                     "test pattern", "delivery"):
            if leak and leak in blob:
                return False, f"line {lid} request contains {leak!r}"
        tmp = PDIR / "_f.jpg"
        import base64
        tmp.write_bytes(base64.b64decode(imgs[0]["source"]["data"]))
        wh = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries",
                             "stream=width,height", "-of", "csv=p=0",
                             str(tmp)], capture_output=True, text=True).stdout
        w, h = (int(x) for x in wh.strip().split(",")[:2])
        if max(w, h) != config.PICTURE_CHECK_FRAME_SIDE:
            return False, f"frame is {w}x{h}"
    return True, (f"{len(c.requests)} request(s) = narrated timeline lines; "
                  f"narration + {len(imgs)} frames ({w}x{h}) only")


def test_spans_in_final():
    tl = STATE["timeline"]
    off = float(tl["intro_offset"])
    spans, _o, notes = PC.load_spans(PDIR)
    for s in spans:
        ts = PC.frame_times(s["a"], s["b"], config.PICTURE_CHECK_FRAMES)
        if not all(s["a"] <= t <= s["b"] for t in ts) or s["a"] < off:
            return False, f"line {s['id']} frames {ts} outside {s}"
    if notes:
        return False, f"a correctly shifted timeline was re-shifted: {notes}"
    return True, (f"frames inside each line's span, all after the "
                  f"{off:.1f}s intro")


def test_all_match_passes():
    rc, out = _run(Client())
    (v, summ), md = _row()
    n = len(json.loads((PDIR / "final_report.json").read_text(
        encoding="utf-8"))["checks"])
    if rc != 0 or v != "PASS":
        return False, f"rc {rc}, verdict {v}: {summ}"
    if n != STATE["checks_before"] + 1 or "`MOTION-CHECK`" not in md:
        return False, f"earlier checks lost: {n} vs {STATE['checks_before']}"
    rc, out = _run(Client())                  # re-run replaces, not appends
    n2 = len(json.loads((PDIR / "final_report.json").read_text(
        encoding="utf-8"))["checks"])
    return n2 == n, f"PASS row added, {n - 1} earlier check(s) kept, re-run replaces"


def test_causes():
    tlp = PDIR / "timeline.json"
    orig = tlp.read_text(encoding="utf-8")
    tl = json.loads(orig)
    ids = [t["id"] for t in tl["lines"]]
    a, b, c = ids[:3]
    # line b and c share source footage in the clip plan
    tl["lines"][2]["clip_start"] = tl["lines"][1]["clip_start"]
    tl["lines"][2]["clip_end"] = tl["lines"][1]["clip_end"]
    tlp.write_text(json.dumps(tl), encoding="utf-8")

    def reply(cid, p, n):
        lid = int(cid.split("-")[1])
        if lid == a:
            return {"verdict": "wrong-scene", "reason": "another street",
                    "frames": [True, True, False, False, False]}
        if lid == b:
            return {"verdict": "unclear", "reason": "a face, can't tell",
                    "frames": [False] * 5}
        return {"verdict": "wrong-scene", "reason": "a test card",
                "frames": [False] * 5}
    try:
        rc, out = _run(Client(reply))
    finally:
        tlp.write_text(orig, encoding="utf-8")
    (v, summ), md = _row()
    want = {"runs into a neighbouring scene", "repeated footage"}
    missing = [w for w in want if w not in md]
    if rc != 0 or v != "WARN" or missing:
        return False, f"rc {rc}, verdict {v}, causes missing {missing}"
    if "2 defect(s)" not in summ:
        return False, f"unclear counted as a defect? {summ}"
    if not re.search(r"`PICTURE-CHECK` \*\*\[\d+:\d\d\.\d\d\]\*\*", md):
        return False, "findings carry no output timestamp"
    if f"line {b} " in "".join(l for l in md.splitlines()
                              if l.startswith("- `PICTURE-CHECK`")):
        return False, "an unclear line was listed as a finding"
    if "cost ~$" not in out:
        return False, "token cost not printed"
    sp = PC.load_spans(PDIR)[0]
    got = {v: PC.classify({"id": a, "verdict": v, "frames": [False] * 5}, sp)
           for v in PC.VERDICTS}
    want = {"fits": None, "unclear": None, "wrong-scene": "wrong shot",
            "contradicts": "contradicts the line",
            "unwatchable": "unwatchable footage"}
    if got != want:
        return False, f"classification {got}"
    return True, ("WARN; wrong shot / neighbour / repeated / contradicts / "
                  "unwatchable assigned; unclear is not a defect; findings "
                  "timestamped; cost printed")


def test_defect_rule():
    """The regression that started this: a recap's lines describe far more
    than any picture shows. 89 lines the picture cannot fully show must be
    0 defects; only wrong-scene / contradicts / unwatchable count."""
    res = ([{"id": i, "at": float(i), "verdict": "unclear", "frames": []}
            for i in range(89)]
           + [{"id": 100 + i, "at": 100.0 + i, "verdict": v, "frames": []}
              for i, v in enumerate(PC.VERDICTS)])
    s = PC.summarise(res, [], 15)
    if s["defects"] != 3 or set(PC.DEFECTS) != {"wrong-scene", "contradicts",
                                                "unwatchable"}:
        return False, f"defects {s['defects']} from {s['counts']}"
    if [r["verdict"] for r in s["worst"]] != ["unwatchable", "contradicts",
                                              "wrong-scene"]:
        return False, f"worst order {[r['verdict'] for r in s['worst']]}"
    if PC.SCHEMA["properties"]["verdict"]["enum"] != list(PC.VERDICTS):
        return False, "schema enum is not the answer set"
    for need in ("CONTRADICT", "unwatchable", "NORMAL"):
        if need not in PC.SYSTEM:
            return False, f"prompt lacks {need!r}"
    return True, ("90 lines unclear -> 0 defects; one each of wrong-scene, "
                  "contradicts, unwatchable -> 3, worst first")


def test_final_override():
    """--final/--timeline measure another render and leave final_report.md
    alone; one without the other is refused."""
    import shutil as _sh
    _sh.copy2(PDIR / "final.mp4", PDIR / "final_old.mp4")
    _sh.copy2(PDIR / "timeline.json", PDIR / "timeline_old.json")
    before = (PDIR / "final_report.md").read_text(encoding="utf-8")
    c = Client()
    TB.CLIENT_FACTORY = lambda: c
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = PCT.main(["--project", PROJ, "--final", "final_old.mp4",
                       "--timeline", "timeline_old.json"])
        rc2 = PCT.main(["--project", PROJ, "--final", "final_old.mp4"])
    after = (PDIR / "final_report.md").read_text(encoding="utf-8")
    ok = (rc == 0 and rc2 == 1 and before == after
          and (PDIR / "picture_check_final_old.json").exists()
          and "NOT written into final_report.md" in buf.getvalue())
    return ok, (f"other render measured (rc {rc}), report untouched, own "
                f"state file; --final alone refused (rc {rc2})")


def test_calibrate():
    """BAD and GOOD renders in one command: defects per render and cause."""
    c = Client(lambda cid, p, n: (
        {"verdict": "wrong-scene", "reason": "x", "frames": [False] * 5}
        if n == 0 else
        {"verdict": "fits", "reason": "y", "frames": [True] * 5}))
    TB.CLIENT_FACTORY = lambda: c
    own = (PDIR / PC.STATE_FILE)
    own.write_text('{"status": "submitted", "batch_id": "keepme"}')
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = PCT.main(["calibrate", "--project", PROJ,
                       "--bad-final", "final_old.mp4",
                       "--bad-timeline", "timeline_old.json"])
    out = buf.getvalue()
    rec = json.loads((PDIR / "picture_calibration.json").read_text())
    nb = rec["renders"]["BAD"]["defects"]
    ng = rec["renders"]["GOOD"]["defects"]
    if rc != 0 or not (nb > 0 and ng == 0):
        return False, f"rc {rc}, BAD {nb} GOOD {ng}: {out[-300:]}"
    if "defects by cause" not in out or "wrong shot" not in out:
        return False, "no per-cause breakdown printed"
    if json.loads(own.read_text()).get("batch_id") != "keepme":
        return False, "calibration touched the project's own pending state"
    return True, (f"BAD {nb} defects vs GOOD {ng}, per cause printed, "
                  f"picture_calibration.json written, project state kept")


def test_stale_final():
    c = Client()
    TB.CLIENT_FACTORY = lambda: c
    (PDIR / PC.STATE_FILE).unlink(missing_ok=True)
    buf = io.StringIO()
    with redirect_stdout(buf):
        PCT.main(["--project", PROJ, "--submit"])
        f = PDIR / "final.mp4"
        os.utime(f, ns=(f.stat().st_atime_ns, f.stat().st_mtime_ns + 10**9))
        rc = PCT.main(["--project", PROJ, "--collect"])
    (v, summ), _md = _row()
    return v == "SKIPPED", f"final changed after submit -> {v}: {summ[:80]}"


def test_hook_submits():
    from pipeline import render as R
    c = Client()
    TB.CLIENT_FACTORY = lambda: c
    (PDIR / PC.STATE_FILE).unlink(missing_ok=True)
    old = os.environ.get(TB.KEY_ENV)
    os.environ[TB.KEY_ENV] = KEY
    flag0, config.PICTURE_CHECK_AT_RENDER = config.PICTURE_CHECK_AT_RENDER, True
    try:
        with redirect_stdout(io.StringIO()):
            R._submit_picture_check(PROJ)
        config.PICTURE_CHECK_AT_RENDER = False
        n0 = len(c.requests)
        c.requests = []
        (PDIR / PC.STATE_FILE).unlink(missing_ok=True)
        with redirect_stdout(io.StringIO()):
            R._submit_picture_check(PROJ)
        if c.requests or (PDIR / PC.STATE_FILE).exists():
            return False, "the hook submitted with PICTURE_CHECK_AT_RENDER off"
        config.PICTURE_CHECK_AT_RENDER = True
        with redirect_stdout(io.StringIO()):
            R._submit_picture_check(PROJ)
    finally:
        config.PICTURE_CHECK_AT_RENDER = flag0
        if old is None:
            os.environ.pop(TB.KEY_ENV, None)
        else:
            os.environ[TB.KEY_ENV] = old
    st = json.loads((PDIR / PC.STATE_FILE).read_text(encoding="utf-8"))
    ok = st.get("status") == "submitted" and len(c.requests) > 0
    return ok, f"hook submitted {len(c.requests)} request(s), state recorded"


TESTS = {
    "RENDER-NEVER-BLOCKS": test_render_never_blocks,
    "REQUEST-SEES-ONLY":   test_request_sees_only,
    "SPANS-IN-FINAL":      test_spans_in_final,
    "ALL-MATCH-PASSES":    test_all_match_passes,
    "CAUSES":              test_causes,
    "DEFECT-RULE":         test_defect_rule,
    "FINAL-OVERRIDE":      test_final_override,
    "CALIBRATE":           test_calibrate,
    "STALE-FINAL":         test_stale_final,
    "HOOK-SUBMITS":        test_hook_submits,
}

if __name__ == "__main__":
    bad = 0
    try:
        for name, fn in TESTS.items():      # in order: the render comes first
            try:
                ok, msg = fn()
            except Exception as e:
                import traceback
                traceback.print_exc()
                ok, msg = False, f"{type(e).__name__}: {e}"
            print(f'{"PASS" if ok else "FAIL"}  {name:<20} {msg}')
            bad += (not ok)
            if name == "RENDER-NEVER-BLOCKS" and not ok:
                break
    finally:
        shutil.rmtree(PDIR, ignore_errors=True)
    print("-" * 60)
    print("test_picture_check: all pass" if not bad else
          f"test_picture_check: {bad} FAILURE(S)")
    sys.exit(1 if bad else 0)
