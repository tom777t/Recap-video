# -*- coding: utf-8 -*-
"""test_tag_batch.py - the API tagging path, offline (SDK client mocked).

  REQUEST-BUILD     one request per span: span_prompt.md verbatim + cast in a
                    cached system prefix, payload text without the CAST lines,
                    every listed frame as an image, the right span ids
  IMAGE-DOWNSCALE   a 1280x720 frame goes up at 768 on the long side; a 640
                    frame goes up byte-for-byte untouched (Pillow and ffmpeg)
  TODO-PARITY       submit selects exactly what check_stage.py tags-todo says
  SUBMIT-STATE      the batch id lands in tag_batch.json with its span ids
  VALIDATE-REJECTS  malformed replies (gap, overlap, invented timestamp, no
                    VISIBLE label, bad censor, censor_note rules, wrong span)
                    are rejected; a good one passes
  COLLECT           a batch with one good, one malformed and one errored
                    result: the good one is written, the others are retried
                    once on the escalate model, what still fails is listed
                    in tag_batch.json and `status` says TRIED
  FORMAT-EXACT      every real tokyodrift2006 span file survives the writer
                    byte-for-byte, and a written file has the same structure
  DOWNSTREAM        assemble_moments.py reads the written files with zero
                    validation problems
  PILOT             tokens and cost per span are printed, results go to
                    tag_pilot/, spans.json.d is untouched, the key never
                    appears in the output
  MISSING-KEY       no ANTHROPIC_API_KEY -> one clear message, exit 1
  DERIVE-CLIPS      a moment's clip_start/clip_end come from its shot ids;
                    a difference is logged, not failed, and not escalated;
                    a real schema failure still is

Run:  python tools/test_tag_batch.py      (exit 0 = all pass)
"""
from __future__ import annotations

import base64
import io
import json
import os
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
import tag_batch as T  # noqa: E402
import make_spans  # noqa: E402

PROJ = "_selftest_tagbatch"
PDIR = config.project_dir(PROJ)
REAL = ROOT / "projects" / "tokyodrift2006" / "spans.json.d"
CUTS = [0.0, 2.5, 6.0, 13.0, 30.0, 31.2, 40.0, 55.5, 70.0, 88.0, 92.0,
        100.0, 115.0, 121.0, 150.0, 170.0, 185.0, 200.0]
CAST = ["Sean Boswell", "Han Lue", "Neela"]
SENTINEL = "fake-test-key-123"     # short on purpose: pre_push_guard pattern


# --------------------------------------------------------------------------- #
# fixture
# --------------------------------------------------------------------------- #
def _pil():
    try:
        from PIL import Image
        return Image
    except ImportError:
        return None


# Pillow is optional for the tool (it falls back to ffmpeg), so the test must
# not need it either: fixtures and size checks fall back to ffmpeg/ffprobe.
def _jpeg(path: Path, w: int, h: int, shade: int) -> None:
    Image = _pil()
    if Image is not None:
        Image.new("RGB", (w, h), (shade, 40, 90)).save(path, "JPEG", quality=80)
        return
    subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"color=c=0x{shade:02x}285a:s={w}x{h}",
                    "-frames:v", "1", str(path)], check=True, capture_output=True)


def _dims(data: bytes) -> tuple:
    Image = _pil()
    if Image is not None:
        return Image.open(io.BytesIO(data)).size
    tmp = PDIR / "_dims.jpg"
    tmp.write_bytes(data)
    out = subprocess.run([config.ffprobe(), "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height", "-of", "csv=p=0",
                          str(tmp)], capture_output=True, text=True).stdout
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def _have_ffmpeg() -> bool:
    try:
        config.ffmpeg()
        return True
    except Exception:
        return False


def _setup() -> dict:
    shutil.rmtree(PDIR, ignore_errors=True)
    (PDIR / "frames" / "spans").mkdir(parents=True)
    spans = make_spans.build_spans(CUTS, 0, CUTS[-1])
    for s in spans:
        s.pop("cuts")
        s["frames"] = [{"file": f"{s['id']}_{k:02d}.jpg", "shot_i": sh["i"],
                        "t": sh["start"]} for k, sh in enumerate(s["shots"])]
    # sp01's first frame is big (must be downscaled); one frame of sp02 is
    # missing on disk (must be reported, not dropped).
    for s in spans:
        for k, f in enumerate(s["frames"]):
            if s["id"] == "sp02" and k == 1:
                continue
            big = s["id"] == "sp01" and k == 0
            _jpeg(PDIR / "frames" / "spans" / f["file"],
                  1280 if big else 640, 720 if big else 360, 10 * k)
    (PDIR / "spans.json").write_text(json.dumps(
        {"project": PROJ, "span_sec": 90.0, "overlap_sec": 20.0,
         "region": [0, CUTS[-1]], "frame_width": 640, "spans": spans}),
        encoding="utf-8")
    (PDIR / "_cuts.json").write_text(json.dumps({"cuts": CUTS}), encoding="utf-8")
    (PDIR / "names.json").write_text(json.dumps(
        {"names": [{"character": c} for c in CAST]}), encoding="utf-8")
    return {s["id"]: s for s in spans}


def _teardown() -> None:
    shutil.rmtree(PDIR, ignore_errors=True)


def good_reply(sp: dict) -> dict:
    """A valid reply: consecutive pairs of shots tiling the whole span."""
    sh, moms = sp["shots"], []
    for a in range(0, len(sh), 2):
        idx = list(range(a, min(a + 2, len(sh))))
        moms.append({"shots": idx,
                     "clip_start": T.hms(sh[idx[0]]["start"]),
                     "clip_end": T.hms(sh[idx[-1]]["end"]),
                     "depicts": ["dialogue", "setup"],
                     "chars": ["Sean Boswell"],
                     "action": "Sean talks across a garage; by the last shot "
                               "he has turned away.",
                     "censor": "none"})
    moms[-1]["censor"] = "blur_light"
    moms[-1]["censor_note"] = "blood on a forehead, a fifth of the frame"
    return {"span": sp["id"], "moments": moms}


def message(obj_or_text, usage=None, stop="end_turn"):
    text = obj_or_text if isinstance(obj_or_text, str) else json.dumps(obj_or_text)
    u = usage or {"input_tokens": 9000, "cache_creation_input_tokens": 0,
                  "cache_read_input_tokens": 2500, "output_tokens": 700}
    return NS(content=[NS(type="text", text=text)], stop_reason=stop,
              usage=NS(cache_creation=None, **u))


class FakeBatches:
    def __init__(self):
        self.created, self.status, self.items = [], "ended", []

    def create(self, requests):
        self.created.append(list(requests))
        return NS(id=f"msgbatch_test{len(self.created)}")

    def retrieve(self, bid):
        return NS(id=bid, processing_status=self.status,
                  request_counts=NS(processing=0, succeeded=1))

    def results(self, bid):
        return iter(self.items)


class FakeMessages:
    def __init__(self, reply):
        self.reply, self.calls = reply, []
        self.batches = FakeBatches()

    def create(self, **params):
        self.calls.append(params)
        return self.reply(params)


class FakeClient:
    def __init__(self, reply=None):
        self.messages = FakeMessages(reply or (lambda p: message("{}")))


def _run(argv) -> tuple:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = T.main(argv)
    return code, buf.getvalue()


def _span_from_params(params, spans) -> dict:
    text = params["messages"][0]["content"][0]["text"]
    sid = text.split()[1]
    return spans[sid]


# --------------------------------------------------------------------------- #
# tests
# --------------------------------------------------------------------------- #
def t_request_build(spans):
    sp = spans["sp01"]
    p = T.build_params(PDIR, sp, CAST, config.TAG_MODEL, ttl="1h")
    sysb = p["system"]
    probs = []
    if sysb[0]["text"] != T.PROMPT_FILE.read_text(encoding="utf-8"):
        probs.append("system[0] is not span_prompt.md verbatim")
    if sysb[-1].get("cache_control") != {"type": "ephemeral", "ttl": "1h"}:
        probs.append(f"no cache_control on the last system block: {sysb[-1].get('cache_control')}")
    if not all(c in sysb[-1]["text"] for c in CAST):
        probs.append("cast missing from the cached prefix")
    content = p["messages"][0]["content"]
    text = content[0]["text"]
    if not text.startswith("SPAN sp01 ") or "CAST" in text:
        probs.append("payload text wrong (span header / CAST should be in system)")
    imgs = [c for c in content if c["type"] == "image"]
    if len(imgs) != len(sp["frames"]):
        probs.append(f"{len(imgs)} images for {len(sp['frames'])} frames")
    if p["model"] != config.TAG_MODEL or "output_config" not in p:
        probs.append("model / structured output missing")
    # a missing frame is announced, not silently dropped
    p2 = T.build_params(PDIR, spans["sp02"], CAST, config.TAG_MODEL)
    if not any("FRAME NOT AVAILABLE" in c.get("text", "")
               for c in p2["messages"][0]["content"]):
        probs.append("missing frame not reported in sp02")
    return probs


def t_image_downscale(spans):
    probs = []
    big = PDIR / "frames" / "spans" / "sp01_00.jpg"
    small = PDIR / "frames" / "spans" / "sp01_01.jpg"
    if _pil() is not None:
        _mt, b64, _d = T.prep_image(big)
        if _dims(base64.b64decode(b64)) != (768, 432):
            probs.append(f"pillow: 1280x720 became {_dims(base64.b64decode(b64))}")
        _mt, b64, _d = T.prep_image(small)
        if base64.b64decode(b64) != small.read_bytes():
            probs.append("pillow: 640px frame was re-encoded")
    if _have_ffmpeg():
        saved = sys.modules.get("PIL", "absent")
        sys.modules["PIL"] = None          # import PIL -> ImportError
        try:
            _mt, b64, _d = T.prep_image(big)
            _mt, b64s, _d = T.prep_image(small)
        except Exception as e:
            probs.append(f"ffmpeg path raised {e}")
            b64 = b64s = None
        finally:
            if saved == "absent":
                sys.modules.pop("PIL", None)
            else:
                sys.modules["PIL"] = saved
        if b64:
            sz = _dims(base64.b64decode(b64))
            ss = _dims(base64.b64decode(b64s))
            if sz != (768, 432) or ss != (640, 360):
                probs.append(f"ffmpeg: big -> {sz}, small -> {ss}")
    if _pil() is None and not _have_ffmpeg():
        probs.append("neither Pillow nor ffmpeg available - nothing tested")
    return probs


def t_todo_parity(spans):
    probs = []
    d = PDIR / "spans.json.d"
    d.mkdir(exist_ok=True)
    T.write_span(d, "sp02", good_reply(spans["sp02"]))
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "check_stage.py"),
                          PROJ, "tags-todo"], capture_output=True, text=True,
                         cwd=str(ROOT)).stdout.strip()
    mine = T.tags_todo(PDIR)
    if out.split() != mine:
        probs.append(f"check_stage {out!r} vs tag_batch {mine}")
    fake = FakeClient()
    T.CLIENT_FACTORY = lambda: fake
    os.environ[T.KEY_ENV] = SENTINEL
    code, txt = _run(["submit", "--project", PROJ])
    sent = [r["custom_id"] for r in fake.messages.batches.created[0]]
    if code != 0 or sent != out.split():
        probs.append(f"submit sent {sent}, tags-todo says {out.split()} (exit {code})")
    st = json.loads((PDIR / T.STATE_FILE).read_text(encoding="utf-8"))
    b = st["batches"][0]
    if b["id"] != "msgbatch_test1" or sorted(b["custom_ids"].values()) != sorted(mine):
        probs.append(f"state not recorded right: {b}")
    if SENTINEL in txt:
        probs.append("the API key was printed")
    # a second submit while the batch is uncollected must refuse
    code2, _ = _run(["submit", "--project", PROJ])
    if code2 == 0 or len(fake.messages.batches.created) != 1:
        probs.append("second submit did not refuse while a batch is pending")
    code3, st_word = _run(["status", "--project", PROJ])
    if st_word.strip() != "PENDING":
        probs.append(f"status says {st_word.strip()} with a batch pending")
    return probs


def t_validate(spans):
    sp = spans["sp01"]
    probs = []
    good = good_reply(sp)
    if T.validate(good, sp):
        probs.append(f"good reply rejected: {T.validate(good, sp)}")

    def mut(fn):
        o = json.loads(json.dumps(good))
        fn(o)
        return o
    bad = {
        "gap": mut(lambda o: o["moments"].pop(1)),
        "overlap": mut(lambda o: o["moments"][1]["shots"].insert(0, 1)),
        "non-consecutive": mut(lambda o: o["moments"][0].__setitem__("shots", [0, 2])),
        "invented-time": mut(lambda o: o["moments"][0].__setitem__("clip_end", "00:00:04.000")),
        "no-visible": mut(lambda o: o["moments"][0].__setitem__("depicts", ["setup"])),
        "bad-vocab": mut(lambda o: o["moments"][0].__setitem__("depicts", ["action", "chase"])),
        "bad-censor": mut(lambda o: o["moments"][0].__setitem__("censor", "blur")),
        "note-on-none": mut(lambda o: o["moments"][0].__setitem__("censor_note", "x")),
        "blur-no-note": mut(lambda o: o["moments"][-1].pop("censor_note")),
        "wrong-span": mut(lambda o: o.__setitem__("span", "sp09")),
        "extra-key": mut(lambda o: o["moments"][0].__setitem__("beat", "B1")),
        "empty-action": mut(lambda o: o["moments"][0].__setitem__("action", " ")),
        "not-object": [],
    }
    for name, o in bad.items():
        if not T.validate(o, sp):
            probs.append(f"{name} accepted")
    if T.parse_reply("```json\n" + json.dumps(good) + "\n```") != good:
        probs.append("fenced JSON not parsed")
    if T.parse_reply("I could not do it") is not None:
        probs.append("prose parsed as JSON")
    return probs


def t_collect(spans):
    probs = []
    shutil.rmtree(PDIR / "spans.json.d", ignore_errors=True)
    if (PDIR / T.STATE_FILE).exists():
        (PDIR / T.STATE_FILE).unlink()
    ids = list(spans)            # sp01 sp02 sp03
    # escalate model: fixes sp02, still fails sp03
    def esc_reply(params):
        sp = _span_from_params(params, spans)
        if sp["id"] == "sp02":
            return message(good_reply(sp))
        return message("not json at all")
    fake = FakeClient(esc_reply)
    T.CLIENT_FACTORY = lambda: fake
    _run(["submit", "--project", PROJ])
    bad = good_reply(spans["sp02"])
    bad["moments"].pop(0)                                  # does not tile
    fb = fake.messages.batches
    fb.items = [
        NS(custom_id="sp01", result=NS(type="succeeded",
                                       message=message(good_reply(spans["sp01"])))),
        NS(custom_id="sp02", result=NS(type="succeeded", message=message(bad))),
        NS(custom_id="sp03", result=NS(type="errored", error=NS(
            type="error", error=NS(type="overloaded_error", message="overloaded")))),
    ]
    fb.status = "in_progress"
    code, _ = _run(["collect", "--project", PROJ])
    if code != 3:
        probs.append(f"collect on a running batch exited {code}, want 3")
    fb.status = "ended"
    code, txt = _run(["collect", "--project", PROJ])
    d = PDIR / "spans.json.d"
    have = sorted(f.stem for f in d.glob("*.json"))
    if have != ["sp01", "sp02"]:
        probs.append(f"written {have}, want sp01 (batch) + sp02 (escalated)")
    if code != 2:
        probs.append(f"collect with a failure exited {code}, want 2")
    esc_models = [c["model"] for c in fake.messages.calls]
    if esc_models != [config.TAG_ESCALATE_MODEL] * 2:
        probs.append(f"escalation calls {esc_models}")
    st = json.loads((PDIR / T.STATE_FILE).read_text(encoding="utf-8"))
    if list(st.get("failed", {})) != ["sp03"] or "sp03" not in txt:
        probs.append(f"failure list {list(st.get('failed', {}))}, not [sp03]")
    if st["batches"][0]["status"] != "collected":
        probs.append("batch not marked collected")
    _c, word = _run(["status", "--project", PROJ])
    if word.strip() != "TRIED":
        probs.append(f"status after failure is {word.strip()}, want TRIED")
    _c, out = _run(["submit", "--project", PROJ])
    if "NOTHING-TO-SUBMIT" not in out:
        probs.append("submit re-sent a span the API already failed")
    # the fallback: a subagent writes sp03 -> NONE
    T.write_span(d, "sp03", good_reply(spans["sp03"]))
    _c, word = _run(["status", "--project", PROJ])
    if word.strip() != "NONE":
        probs.append(f"status with every span tagged is {word.strip()}")
    for sid in ids:
        raw = (d / f"{sid}.json").read_bytes()
        if T.format_span_json(json.loads(raw)).encode() != raw:
            probs.append(f"{sid} not in the canonical format")
    return probs


def t_format_exact(spans):
    probs = []
    files = sorted(REAL.glob("*.json"))
    if not files:
        return ["no real files in projects/tokyodrift2006/spans.json.d"]
    for f in files:
        raw = f.read_bytes()
        if T.format_span_json(json.loads(raw)).encode("utf-8") != raw:
            probs.append(f"{f.name} differs after a round trip")
    # structure: same top keys, same moment keys and value types as a real file
    real = json.loads((REAL / "sp07.json").read_text(encoding="utf-8"))
    mine = json.loads((PDIR / "spans.json.d" / "sp01.json").read_text(encoding="utf-8"))

    def shape(o):
        return {k: type(v).__name__ for k, v in o.items()}
    if list(real) != list(mine):
        probs.append(f"top keys {list(mine)} vs {list(real)}")
    rm = {k: v for m in real["moments"] for k, v in shape(m).items()}
    mm = {k: v for m in mine["moments"] for k, v in shape(m).items()}
    if rm != mm:
        probs.append(f"moment shape {mm} vs real {rm}")
    order_real = [list(m) for m in real["moments"] if "censor_note" in m][0]
    order_mine = [list(m) for m in mine["moments"] if "censor_note" in m][0]
    if order_real != order_mine:
        probs.append(f"key order {order_mine} vs {order_real}")
    return probs


def t_downstream(spans):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "assemble_moments.py"),
                        PROJ], capture_output=True, text=True, cwd=str(ROOT))
    w = PDIR / "windows_llm.json"
    if r.returncode != 0 or not w.exists():
        return [f"assemble_moments failed: {r.stdout[-300:]}"]
    st = json.loads(w.read_text(encoding="utf-8"))["stats"]
    probs = []
    if st["validation_problems"] or st["spans_missing"]:
        probs.append(f"assemble stats {st}")
    return probs


def t_pilot(spans):
    probs = []
    shutil.rmtree(PDIR / "spans.json.d", ignore_errors=True)
    before = set()
    usage = {"input_tokens": 12000, "cache_creation_input_tokens": 3000,
             "cache_read_input_tokens": 0, "output_tokens": 900}
    fake = FakeClient(lambda p: message(good_reply(_span_from_params(p, spans)),
                                        usage=usage))
    T.CLIENT_FACTORY = lambda: fake
    os.environ[T.KEY_ENV] = SENTINEL
    code, txt = _run(["pilot", "--project", PROJ, "--n", "2"])
    if code != 0:
        probs.append(f"pilot exited {code}: {txt[-300:]}")
    if len(fake.messages.calls) != 2:
        probs.append(f"{len(fake.messages.calls)} calls for --n 2")
    # 12000*0.10 + 3000*0.125 + 900*0.50 per million = 0.002025
    if "12000" not in txt or "$ 0.0020" not in txt:
        probs.append("per-span tokens / cost not printed")
    if "verify" not in txt:
        probs.append("cost printed without the verify-the-price warning")
    pilot = sorted(f.stem for f in (PDIR / T.PILOT_DIR).glob("sp*.json"))
    if pilot != ["sp01", "sp02"]:
        probs.append(f"pilot wrote {pilot}")
    now = {f.stem for f in (PDIR / "spans.json.d").glob("*.json")} \
        if (PDIR / "spans.json.d").exists() else set()
    if now != before:
        probs.append("pilot touched spans.json.d")
    if SENTINEL in txt:
        probs.append("the API key was printed")
    # unknown model price -> tokens only, no invented cost
    saved = config.TAG_MODEL
    config.TAG_MODEL = "claude-unpriced-test"
    try:
        _c, txt2 = _run(["pilot", "--project", PROJ, "--n", "1", "--no-escalate"])
    finally:
        config.TAG_MODEL = saved
    if "tokens only" not in txt2 or "cost (synchronous" in txt2:
        probs.append("unpriced model got a cost")
    return probs


def t_missing_key(spans):
    probs = []
    T.CLIENT_FACTORY = T.make_client
    os.environ.pop(T.KEY_ENV, None)
    for cmd in (["pilot", "--project", PROJ, "--n", "1"],
                ["collect", "--project", PROJ]):
        if cmd[0] == "collect":
            # give collect something pending so it needs the client
            st = T.load_state(PDIR)
            st["batches"].append({"id": "msgbatch_x", "model": config.TAG_MODEL,
                                  "status": "submitted", "custom_ids": {}})
            T.save_state(PDIR, st)
        code, txt = _run(cmd)
        if code != 1 or "ANTHROPIC_API_KEY is not set" not in txt \
                or "Traceback" in txt:
            probs.append(f"{cmd[0]} without a key: exit {code}, {txt[:120]!r}")
    try:
        T.make_client()
        probs.append("make_client did not raise without a key")
    except T.TagBatchError:
        pass
    return probs


def t_derive_clips(spans):
    """A moment's clip window comes from its shot ids, not from the model.

    3 of 20 pilot spans went to the expensive model only because a moment's
    clip_start was not its first shot's start. The batch path must ACCEPT
    such a reply with the times derived (and say so), and must still
    escalate a real schema failure."""
    probs = []
    sp1, sp2 = spans["sp01"], spans["sp02"]
    # unit: wrong times are replaced, the difference is reported
    r = good_reply(sp1)
    r["moments"][0]["clip_start"] = "00:00:00.700"        # not shot 0's start
    r["moments"][1]["clip_end"] = "99:00:00.000"
    want = T.hms(sp1["shots"][r["moments"][0]["shots"][0]]["start"])
    notes = T.derive_clips(r, sp1)
    if len(notes) != 2 or "model wrote 00:00:00.700" not in notes[0]:
        probs.append(f"difference not logged: {notes}")
    if r["moments"][0]["clip_start"] != want or T.validate(r, sp1):
        probs.append(f"derived reply not valid: {T.validate(r, sp1)[:2]}")
    # unusable shot ids are left alone and still rejected
    bad_ids = good_reply(sp1)
    bad_ids["moments"][0]["shots"] = [99]
    T.derive_clips(bad_ids, sp1)
    if not any("out of range" in x for x in T.validate(bad_ids, sp1)):
        probs.append("out-of-range shot ids were not rejected")

    # through collect: timestamp-only reply written WITHOUT escalation;
    # a reply with a real schema failure (no VISIBLE label) IS escalated
    shutil.rmtree(PDIR / "spans.json.d", ignore_errors=True)
    if (PDIR / T.STATE_FILE).exists():
        (PDIR / T.STATE_FILE).unlink()
    fake = FakeClient(lambda params: message(
        good_reply(_span_from_params(params, spans))))
    T.CLIENT_FACTORY = lambda: fake
    _run(["submit", "--project", PROJ, "--retry-failed"])
    ts_only = good_reply(sp1)
    for m in ts_only["moments"]:
        m["clip_start"] = "00:00:00.001"
    schema_bad = good_reply(sp2)
    schema_bad["moments"][0]["depicts"] = ["setup"]          # no VISIBLE
    fb = fake.messages.batches
    fb.items = [NS(custom_id="sp01", result=NS(type="succeeded",
                                               message=message(ts_only))),
                NS(custom_id="sp02", result=NS(type="succeeded",
                                               message=message(schema_bad)))]
    fb.status = "ended"
    _code, txt = _run(["collect", "--project", PROJ])
    esc = [_span_from_params(c, spans)["id"] for c in fake.messages.calls]
    if "sp01" in esc:
        probs.append("a timestamp-only difference was escalated")
    if "sp02" not in esc:
        probs.append("a real schema failure was NOT escalated")
    f1 = PDIR / "spans.json.d" / "sp01.json"
    if not f1.exists():
        probs.append("timestamp-only reply was not written")
    else:
        got = json.loads(f1.read_text(encoding="utf-8"))
        if got["moments"][0]["clip_start"] != T.hms(sp1["shots"][0]["start"]):
            probs.append("written clip_start is not the derived one")
    if "clip times derived from shot ids" not in txt:
        probs.append("the derivation was not logged")
    return probs


TESTS = {
    "REQUEST-BUILD": t_request_build,
    "IMAGE-DOWNSCALE": t_image_downscale,
    "TODO-PARITY": t_todo_parity,
    "VALIDATE-REJECTS": t_validate,
    "COLLECT": t_collect,
    "FORMAT-EXACT": t_format_exact,
    "DOWNSTREAM": t_downstream,
    "PILOT": t_pilot,
    "MISSING-KEY": t_missing_key,
    "DERIVE-CLIPS": t_derive_clips,
}


def main() -> int:
    saved_key = os.environ.get(T.KEY_ENV)
    saved_factory = T.CLIENT_FACTORY
    bad = 0
    try:
        spans = _setup()
        for name, fn in TESTS.items():
            try:
                probs = fn(spans)
            except Exception as e:
                probs = [f"raised {type(e).__name__}: {e}"]
            ok = not probs
            bad += 0 if ok else 1
            print(f"{'PASS' if ok else 'FAIL'}  {name:17} "
                  + ("" if ok else "; ".join(probs)[:400]))
    finally:
        T.CLIENT_FACTORY = saved_factory
        if saved_key is None:
            os.environ.pop(T.KEY_ENV, None)
        else:
            os.environ[T.KEY_ENV] = saved_key
        _teardown()
    print("-" * 60)
    print(f"test_tag_batch: {bad} FAILURE(S)" if bad else "test_tag_batch: all pass")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
