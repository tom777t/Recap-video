# -*- coding: utf-8 -*-
"""
tag_batch.py - tag spans through the Anthropic API instead of subagents.

    python tools/tag_batch.py pilot   --project P [--n 20] [--spans sp03 sp07]
    python tools/tag_batch.py submit  --project P [--retry-failed]
    python tools/tag_batch.py collect --project P [--wait] [--no-escalate]
    python tools/tag_batch.py status  --project P      # one word, for run.ps1

WHY (Phase 3, docs/stage2/STAGE2_PLAN.md). The TAG SPANS stage ran one
OpenCode subagent per span: hours per film, and every one of them spent the
subscription's weekly limit that the writing stages need. Tagging is
look-and-label work, so a small model in a Message Batch (half price, paid
from API credits) does it instead. The subagent path stays as the fallback
for whatever the API cannot get right.

THE UNIT IS UNCHANGED. One request = one span = what one subagent got:
  system  tools/span_prompt.md, verbatim, + a short note saying how to reply
          (there is no file to write) + the CAST lines from names.json
          -> cache_control here: it is identical for every span of a film
  user    span_payload.py's text for that span (header + shot table), then
          every frame the table lists, each labelled with its filename
The reply must be the JSON that spans.json.d/<span>.json holds. It is
validated against the rules assemble_moments.py and span_prompt.md enforce
and written in the SAME byte format the existing files have, so
assemble_moments.py and everything after it cannot tell which path made it.

Why not split a span into 10-20 shot requests as the plan suggests: the span
IS the editorial unit - the moments must tile it and the 20s tail is there so
a moment crossing own_end can be seen whole. Halving it would break exactly
the seam logic make_spans.py was built around. A span is ~20-40 shots and
<= 64 frames at 640px, well under the 100k-token line where Haiku's price
jumps, which is the reason the plan gave for small requests.

The key comes ONLY from the ANTHROPIC_API_KEY environment variable and is
never printed. A key was pushed to this repo once (see pre_push_guard.py).

Exit codes: 0 done | 1 hard error | 2 some spans failed (listed, use the
subagent fallback) | 3 batch still running (collect again later).
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import span_payload as SP  # noqa: E402
from check_stage import tags_todo  # noqa: E402
from assemble_moments import VISIBLE, STORY, CENSOR, pt, hms  # noqa: E402

VOCAB = VISIBLE | STORY
PROMPT_FILE = ROOT / "tools" / "span_prompt.md"
FRAME_DIR = Path("frames") / "spans"     # make_spans.py --out default
STATE_FILE = "tag_batch.json"
PILOT_DIR = "tag_pilot"

# Images: the plan priced a film at 768x432. make_spans.py grabs 640 wide, so
# normally nothing is resized and the model sees the same pixels a subagent
# did; anything bigger is brought down to this long side, never up.
MAX_SIDE = 768
JPEG_QUALITY = 85
# A span's reply is ~10-20 moments of ~60 tokens. 8192 leaves room without
# letting a runaway reply cost much; hitting it is reported as truncation.
MAX_TOKENS = 8192
# The Batches API takes at most 256 MB per batch. A long film with 64 frames a
# span can approach that, so requests are split across several batches.
BATCH_MAX_BYTES = 150 * 1024 * 1024

# Strict JSON via structured outputs (output_config.format). It guarantees the
# SHAPE; tiling and timestamps still need validate() below.
USE_STRUCTURED_OUTPUT = True

# How the reply is delivered. span_prompt.md tells a subagent to WRITE a file;
# through the API there is no file system, so this is the only addition to
# the instructions. Everything about WHAT to write stays in span_prompt.md.
API_NOTE = (
    "## Delivery in this session\n\n"
    "You are called through the API: you cannot open files, run commands or "
    "write anything to disk. The user message holds exactly what "
    "`span_payload.py` prints for this span (minus the CAST lines, which are "
    "below), followed by every frame it lists, each image preceded by its "
    "filename and shot index. Reply with ONLY the JSON object that "
    "`spans.json.d/<span_id>.json` must contain - no prose, no code fence.")

# --------------------------------------------------------------------------- #
# PRICES - VERIFY AGAINST THE PRICING PAGE before trusting any cost printed.
#   https://platform.claude.com/docs/en/about-claude/pricing
# Copied from that page on 2026-11-01. USD per MILLION tokens. Haiku 5.5
# charges a whole request at the higher row once its prompt (cache reads and
# writes included) passes 100,000 tokens. A model missing here gets tokens
# only, no cost - an invented price is worse than none.
# --------------------------------------------------------------------------- #
PRICES = {
    "claude-haiku-5-5": [
        (100_000, {"in": 0.10, "cw5m": 0.125, "cw1h": 0.20, "cr": 0.01, "out": 0.50}),
        (None, {"in": 0.50, "cw5m": 0.625, "cw1h": 1.00, "cr": 0.05, "out": 2.50}),
    ],
    "claude-sonnet-5-5": [
        (None, {"in": 2.00, "cw5m": 2.50, "cw1h": 4.00, "cr": 0.10, "out": 10.00}),
    ],
}
# Batch input/output are listed at half price. ASSUMED to apply to the cache
# rows too (the page lists batch input and output only) - verify.
BATCH_FACTOR = 0.5

KEY_ENV = "ANTHROPIC_API_KEY"
MISSING_KEY_MSG = (
    f"{KEY_ENV} is not set. The API tagging path reads the key ONLY from that "
    "environment variable (never from a file in the repo). In PowerShell:\n"
    f"    $env:{KEY_ENV} = \"<key from console.anthropic.com>\"\n"
    "or leave it unset and tag with subagents (run.ps1 prints that worklist).")

MOMENT_KEYS = ["shots", "clip_start", "clip_end", "depicts", "chars",
               "action", "censor", "censor_note"]
REQUIRED_MOMENT_KEYS = MOMENT_KEYS[:-1]

SCHEMA = {
    "type": "object",
    "properties": {
        "span": {"type": "string"},
        "moments": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "shots": {"type": "array", "items": {"type": "integer"}},
                "clip_start": {"type": "string"},
                "clip_end": {"type": "string"},
                "depicts": {"type": "array",
                            "items": {"type": "string", "enum": sorted(VOCAB)}},
                "chars": {"type": "array", "items": {"type": "string"}},
                "action": {"type": "string"},
                "censor": {"type": "string", "enum": sorted(CENSOR)},
                "censor_note": {"type": "string"},
            },
            "required": REQUIRED_MOMENT_KEYS,
            "additionalProperties": False,
        }},
    },
    "required": ["span", "moments"],
    "additionalProperties": False,
}


class TagBatchError(Exception):
    """A failure the user fixes by reading one message, not a traceback."""


# --------------------------------------------------------------------------- #
# client
# --------------------------------------------------------------------------- #
def make_client():
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise TagBatchError(MISSING_KEY_MSG)
    try:
        import anthropic
    except ImportError:
        raise TagBatchError("the `anthropic` package is not installed: "
                            "pip install -r requirements.txt")
    # Passed explicitly so no other credential in the environment is used.
    return anthropic.Anthropic(api_key=key)


# Tests replace this; nothing else should.
CLIENT_FACTORY = make_client


def _get(o, name, default=None):
    if o is None:
        return default
    if isinstance(o, dict):
        return o.get(name, default)
    return getattr(o, name, default)


# --------------------------------------------------------------------------- #
# project data
# --------------------------------------------------------------------------- #
def load_spans(pdir: Path) -> dict:
    p = pdir / "spans.json"
    if not p.exists():
        raise TagBatchError(f"missing {p} - run the spans stage first "
                            f"(.\\run.ps1 -Project {pdir.name} -From spans)")
    meta = json.loads(p.read_text(encoding="utf-8"))
    return {s["id"]: s for s in meta.get("spans", [])}


def find_frame(pdir: Path, name: str):
    p = pdir / FRAME_DIR / name
    if p.exists():
        return p
    # make_spans.py --out can move them; spans.json does not record where.
    for q in (pdir / "frames").rglob(name) if (pdir / "frames").exists() else []:
        return q
    return None


def prep_image(path: Path):
    """(media_type, base64, (w, h) or None). Long side capped at MAX_SIDE."""
    raw = path.read_bytes()
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image is not None:
        im = Image.open(io.BytesIO(raw))
        w, h = im.size
        if max(w, h) <= MAX_SIDE and (im.format or "").upper() == "JPEG":
            # Already small and already JPEG: send the file untouched, the
            # same bytes a subagent would have read.
            return "image/jpeg", base64.b64encode(raw).decode("ascii"), (w, h)
        im = im.convert("RGB")
        if max(w, h) > MAX_SIDE:
            im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=JPEG_QUALITY)
        return ("image/jpeg", base64.b64encode(buf.getvalue()).decode("ascii"),
                im.size)
    # No Pillow: ffmpeg is a pipeline dependency anyway. The box is
    # min(MAX_SIDE, own size) so a small frame is never enlarged.
    vf = (f"scale='min({MAX_SIDE},iw)':'min({MAX_SIDE},ih)'"
          ":force_original_aspect_ratio=decrease")
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error",
                        "-i", str(path), "-vf", vf, "-q:v", "3",
                        "-f", "image2", "-c:v", "mjpeg", "pipe:1"],
                       capture_output=True, timeout=60)
    if r.returncode != 0 or not r.stdout:
        raise TagBatchError(f"ffmpeg could not resize {path.name}")
    return "image/jpeg", base64.b64encode(r.stdout).decode("ascii"), None


def system_blocks(cast, ttl=None) -> list:
    cc = {"type": "ephemeral"}
    if ttl:
        cc["ttl"] = ttl
    prefix = API_NOTE + "\n\n" + "\n".join(SP.cast_lines(cast))
    return [
        {"type": "text", "text": PROMPT_FILE.read_text(encoding="utf-8")},
        # The breakpoint sits on the LAST stable block, so prompt + note +
        # cast are one cached prefix shared by every span of the film.
        {"type": "text", "text": prefix, "cache_control": cc},
    ]


def user_content(pdir: Path, sp: dict) -> list:
    text = "\n".join([SP.header_line(sp)] + SP.shot_lines(sp))
    content = [{"type": "text", "text": text}]
    by_shot = SP.frames_by_shot(sp)
    for s in sp["shots"]:
        for name in by_shot.get(s["i"], []):
            f = find_frame(pdir, name)
            if f is None:
                # The prompt already says what to do with an unverified shot;
                # tell the model plainly instead of silently skipping.
                content.append({"type": "text", "text":
                                f"{name} (shot {s['i']}): FRAME NOT AVAILABLE"})
                continue
            mt, b64, _dims = prep_image(f)
            content.append({"type": "text", "text": f"{name} (shot {s['i']}):"})
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": mt, "data": b64}})
    return content


def build_params(pdir: Path, sp: dict, cast, model: str, ttl=None) -> dict:
    params = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system_blocks(cast, ttl),
        "messages": [{"role": "user", "content": user_content(pdir, sp)}],
    }
    if USE_STRUCTURED_OUTPUT:
        params["output_config"] = {"format": {"type": "json_schema",
                                              "schema": SCHEMA}}
    return params


def custom_id(sid: str) -> str:
    # Batch custom_id allows [A-Za-z0-9_-]{1,64}; make_spans ids already fit.
    return re.sub(r"[^A-Za-z0-9_-]", "_", sid)[:64]


# --------------------------------------------------------------------------- #
# replies: parse, validate, write
# --------------------------------------------------------------------------- #
def reply_text(message) -> str:
    return "".join(_get(b, "text", "") or "" for b in (_get(message, "content") or [])
                   if _get(b, "type") == "text")


def parse_reply(text: str):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        a, b = t.find("{"), t.rfind("}")
        if a >= 0 and b > a:
            try:
                return json.loads(t[a:b + 1])
            except Exception:
                pass
    return None


def validate(obj, sp: dict) -> list:
    """Problems that make a reply unusable. Empty list = accept.

    Same rules as assemble_moments.py (which only WARNS, because by then the
    file is all there is) plus span_prompt.md's "Rules for the file". Here a
    retry is cheap, so anything assemble would have to patch is a reject."""
    if not isinstance(obj, dict):
        return ["reply is not a JSON object"]
    p = []
    extra = set(obj) - {"span", "moments"}
    if extra:
        p.append(f"unexpected top-level keys {sorted(extra)}")
    if obj.get("span") != sp["id"]:
        p.append(f"span is {obj.get('span')!r}, expected {sp['id']!r}")
    moms = obj.get("moments")
    if not isinstance(moms, list) or not moms:
        return p + ["moments missing or empty"]
    shots = sp["shots"]
    nsh = len(shots)
    seen = []
    for k, m in enumerate(moms):
        if not isinstance(m, dict):
            p.append(f"#{k}: not an object")
            continue
        miss = [x for x in REQUIRED_MOMENT_KEYS if x not in m]
        bad = [x for x in m if x not in MOMENT_KEYS]
        if miss:
            p.append(f"#{k}: missing {miss}")
        if bad:
            p.append(f"#{k}: unknown keys {bad}")
        if miss:
            continue
        idx = m["shots"]
        if (not isinstance(idx, list) or not idx
                or not all(isinstance(i, int) and not isinstance(i, bool) for i in idx)):
            p.append(f"#{k}: shots must be a non-empty list of integers")
            continue
        if idx != list(range(idx[0], idx[-1] + 1)):
            p.append(f"#{k}: shots not consecutive {idx}")
        if idx[0] < 0 or idx[-1] >= nsh:
            p.append(f"#{k}: shot index out of range {idx} (span has {nsh})")
            continue
        seen += idx
        try:
            ca, cb = pt(m["clip_start"]), pt(m["clip_end"])
            a0, b0 = shots[idx[0]]["start"], shots[idx[-1]]["end"]
            if abs(ca - a0) > 0.05 or abs(cb - b0) > 0.05:
                p.append(f"#{k}: clip {m['clip_start']}..{m['clip_end']} is not "
                         f"the shot list's {hms(a0)}..{hms(b0)}")
        except Exception:
            p.append(f"#{k}: clip_start/clip_end not timestamps")
        dep = m["depicts"]
        if not isinstance(dep, list) or not all(isinstance(x, str) for x in dep):
            p.append(f"#{k}: depicts must be a list of strings")
        else:
            off = [x for x in dep if x not in VOCAB]
            if off:
                p.append(f"#{k}: depicts outside the vocabulary {off}")
            if not set(dep) & VISIBLE:
                p.append(f"#{k}: no VISIBLE label in depicts {dep}")
        if not isinstance(m["chars"], list) or not all(isinstance(x, str) for x in m["chars"]):
            p.append(f"#{k}: chars must be a list of strings")
        if not isinstance(m["action"], str) or not m["action"].strip():
            p.append(f"#{k}: action empty")
        cen = m["censor"]
        if cen not in CENSOR:
            p.append(f"#{k}: censor is {cen!r}")
        elif cen == "none" and "censor_note" in m:
            p.append(f"#{k}: censor_note given with censor none")
        elif cen != "none" and not str(m.get("censor_note") or "").strip():
            p.append(f"#{k}: censor {cen} without a censor_note")
    if seen != list(range(nsh)):
        miss = sorted(set(range(nsh)) - set(seen))
        dup = sorted({x for x in seen if seen.count(x) > 1})
        p.append(f"moments do not tile the span in order (missing {miss[:6]}, "
                 f"duplicated {dup[:6]})")
    return p


def _inline(v) -> str:
    return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in v) + "]"


def format_span_json(obj: dict) -> str:
    """The exact layout of the existing spans.json.d files: 2-space indent,
    scalar lists on one line, moment keys in a fixed order, final newline.
    Checked byte-for-byte against all 70 tokyodrift2006 files by the test."""
    lines = ["{", f'  "span": {json.dumps(obj["span"], ensure_ascii=False)},',
             '  "moments": [']
    moms = obj["moments"]
    for k, m in enumerate(moms):
        items = []
        for key in MOMENT_KEYS:
            if key in m:
                v = m[key]
                s = _inline(v) if isinstance(v, list) else json.dumps(v, ensure_ascii=False)
                items.append(f'      "{key}": {s}')
        lines.append("    {")
        lines.append(",\n".join(items))
        lines.append("    }" + ("," if k < len(moms) - 1 else ""))
    lines += ["  ]", "}"]
    return "\n".join(lines) + "\n"


def write_span(out_dir: Path, sid: str, obj: dict, overwrite=False) -> bool:
    """Write one span file. Never overwrites by default: if a subagent wrote
    the span while the batch ran, its file stands."""
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{sid}.json"
    if dst.exists() and not overwrite:
        return False
    tmp = dst.with_suffix(".json.tmp")
    # Bytes, not text mode: on Windows text mode would write \r\n and the
    # file would no longer match the subagent ones byte for byte.
    tmp.write_bytes(format_span_json(obj).encode("utf-8"))
    os.replace(tmp, dst)
    return True


# --------------------------------------------------------------------------- #
# usage and cost
# --------------------------------------------------------------------------- #
def usage_of(message) -> dict:
    u = _get(message, "usage")
    cc = _get(u, "cache_creation")
    out = {"in": int(_get(u, "input_tokens", 0) or 0),
           "cw": int(_get(u, "cache_creation_input_tokens", 0) or 0),
           "cr": int(_get(u, "cache_read_input_tokens", 0) or 0),
           "out": int(_get(u, "output_tokens", 0) or 0)}
    out["cw1h"] = int(_get(cc, "ephemeral_1h_input_tokens", 0) or 0)
    return out


def cost_usd(model: str, u: dict, batch=False):
    """USD for one request, or None when the model has no listed price."""
    tiers = PRICES.get(model)
    if not tiers:
        return None
    prompt = u["in"] + u["cw"] + u["cr"]
    rate = next(r for lim, r in tiers if lim is None or prompt <= lim)
    cw5 = max(0, u["cw"] - u.get("cw1h", 0))
    usd = (u["in"] * rate["in"] + cw5 * rate["cw5m"]
           + u.get("cw1h", 0) * rate["cw1h"] + u["cr"] * rate["cr"]
           + u["out"] * rate["out"]) / 1e6
    return usd * (BATCH_FACTOR if batch else 1.0)


def _fmt_cost(c) -> str:
    return "     n/a" if c is None else f"${c:7.4f}"


# --------------------------------------------------------------------------- #
# state
# --------------------------------------------------------------------------- #
def load_state(pdir: Path) -> dict:
    p = pdir / STATE_FILE
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            raise TagBatchError(f"{p} is not valid JSON - fix or delete it "
                                "(it only records batch ids and failures)")
    return {"project": pdir.name, "batches": [], "failed": {}}


def save_state(pdir: Path, st: dict) -> None:
    (pdir / STATE_FILE).write_text(json.dumps(st, ensure_ascii=False, indent=2),
                                   encoding="utf-8")


def pending(st: dict) -> list:
    return [b for b in st.get("batches", []) if b.get("status") != "collected"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# one synchronous span (pilot + escalation)
# --------------------------------------------------------------------------- #
def tag_sync(client, pdir, sp, cast, model):
    """(obj or None, problems, usage, cost)."""
    msg = client.messages.create(**build_params(pdir, sp, cast, model))
    u = usage_of(msg)
    c = cost_usd(model, u)
    if _get(msg, "stop_reason") == "max_tokens":
        return None, [f"reply truncated at max_tokens={MAX_TOKENS}"], u, c
    obj = parse_reply(reply_text(msg))
    if obj is None:
        return None, ["reply is not JSON"], u, c
    return obj, validate(obj, sp), u, c


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_pilot(a) -> int:
    pdir = config.project_dir(a.project)
    spans = load_spans(pdir)
    cast = SP.load_cast(pdir)
    if a.spans:
        unknown = [s for s in a.spans if s not in spans]
        if unknown:
            raise TagBatchError(f"unknown span ids {unknown}")
        pick = a.spans
    else:
        # Untagged spans first; on a film already tagged by subagents the
        # pilot takes spans in film order, so the two can be compared.
        todo = tags_todo(pdir)
        pick = (todo + [s for s in spans if s not in todo])[:a.n]
    model, esc = config.TAG_MODEL, config.TAG_ESCALATE_MODEL
    client = CLIENT_FACTORY()
    out_dir = pdir / PILOT_DIR
    print(f"pilot: {len(pick)} span, model {model}, synchronous (NOT batch "
          f"price), results -> {out_dir} (spans.json.d is not touched)")
    if not cast:
        print("  !! no names.json - chars will be descriptions only")
    print(f"\n{'span':6} {'shots':>5} {'imgs':>4} {'model':18} {'in':>7} "
          f"{'cache_w':>7} {'cache_r':>7} {'out':>6} {'cost':>8}  result")
    rows, tot_shots = [], 0
    for sid in pick:
        sp = spans[sid]
        nimg = sum(len(v) for v in SP.frames_by_shot(sp).values())
        tot_shots += len(sp["shots"])
        tries = [model] + ([esc] if a.escalate and esc != model else [])
        for att, m in enumerate(tries):
            try:
                obj, probs, u, c = tag_sync(client, pdir, sp, cast, m)
            except TagBatchError:
                raise                     # local problem (frames): stop
            except Exception as e:        # API problem: record, go on
                obj, probs = None, [f"API error: {type(e).__name__}: {e}"[:200]]
                u, c = {"in": 0, "cw": 0, "cr": 0, "out": 0, "cw1h": 0}, None
            res = "ok" if obj is not None and not probs else probs[0][:60]
            print(f"{sid:6} {len(sp['shots']):5} {nimg:4} {m:18} {u['in']:7} "
                  f"{u['cw']:7} {u['cr']:7} {u['out']:6} {_fmt_cost(c)}  {res}")
            row = {"span": sid, "model": m, "attempt": att + 1,
                   "shots": len(sp["shots"]), "images": nimg, "usage": u,
                   "cost_usd": c, "problems": probs}
            rows.append(row)
            if obj is not None and not probs:
                write_span(out_dir, sid, obj, overwrite=True)
                prev = pdir / "spans.json.d" / f"{sid}.json"
                if prev.exists():
                    try:
                        old = json.loads(prev.read_text(encoding="utf-8"))
                        row["compare"] = {
                            "moments_api": len(obj["moments"]),
                            "moments_existing": len(old.get("moments") or [])}
                    except Exception:
                        pass
                break
    costs = [r["cost_usd"] for r in rows]
    tin = sum(r["usage"]["in"] + r["usage"]["cw"] + r["usage"]["cr"] for r in rows)
    tout = sum(r["usage"]["out"] for r in rows)
    print(f"\ntokens: prompt {tin} (incl. cache) | output {tout} | "
          f"{len(pick)} span, {tot_shots} shots")
    ok = {r["span"] for r in rows if not r["problems"]}
    print(f"valid: {len(ok)}/{len(pick)}"
          + (f" | escalated: {sum(1 for r in rows if r['attempt'] > 1)}"
             if a.escalate else ""))
    if all(c is not None for c in costs) and pick:
        total = sum(costs)
        per_span = total / len(pick)
        print(f"cost (synchronous, list price): ${total:.4f} total | "
              f"${per_span:.4f}/span | ${total / max(1, tot_shots):.5f}/shot")
        print(f"whole film estimate in a batch ({len(spans)} spans x "
              f"{BATCH_FACTOR}): ~${per_span * len(spans) * BATCH_FACTOR:.3f}")
        print("PRICES in tools/tag_batch.py were copied 2026-11-01 - verify "
              "against https://platform.claude.com/docs/en/about-claude/pricing")
    else:
        print("cost: no listed price for at least one model - tokens only")
    cmp = [r["compare"] for r in rows if r.get("compare")]
    if cmp:
        print(f"vs existing subagent tags ({len(cmp)} span): moments "
              f"{sum(c['moments_api'] for c in cmp)} API / "
              f"{sum(c['moments_existing'] for c in cmp)} subagent "
              f"- diff {out_dir} against spans.json.d to judge quality")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_report.json").write_text(json.dumps(
        {"generated": _now(), "model": model, "rows": rows}, indent=2),
        encoding="utf-8")
    return 0 if len(ok) == len(pick) else 2


def cmd_submit(a) -> int:
    pdir = config.project_dir(a.project)
    spans = load_spans(pdir)
    st = load_state(pdir)
    if pending(st) and not a.force:
        ids = ", ".join(b["id"] for b in pending(st))
        print(f"a batch is still uncollected ({ids}) - run:\n"
              f"  python tools/tag_batch.py collect --project {a.project}")
        return 1
    todo = tags_todo(pdir)
    failed = st.get("failed", {})
    if not a.retry_failed:
        # A span the API already failed twice (model + escalation) goes to
        # the subagents; resubmitting it every run would just pay again.
        todo = [s for s in todo if s not in failed]
    if not todo:
        print("NOTHING-TO-SUBMIT")
        return 0
    cast = SP.load_cast(pdir)
    model = config.TAG_MODEL
    # Batches can take far longer than 5 minutes, so the 1h cache lifetime is
    # the one that has a chance of being hit (hits are best-effort anyway).
    groups, cur, size = [], [], 0
    for sid in todo:
        req = {"custom_id": custom_id(sid),
               "params": build_params(pdir, spans[sid], cast, model, ttl="1h")}
        n = len(json.dumps(req))
        if cur and size + n > BATCH_MAX_BYTES:
            groups.append(cur)
            cur, size = [], 0
        cur.append((sid, req))
        size += n
    if cur:
        groups.append(cur)
    client = CLIENT_FACTORY()
    for g in groups:
        batch = client.messages.batches.create(requests=[r for _s, r in g])
        st.setdefault("batches", []).append({
            "id": _get(batch, "id"), "model": model, "submitted_at": _now(),
            "status": "submitted",
            "custom_ids": {r["custom_id"]: s for s, r in g}})
        save_state(pdir, st)       # after EACH batch: an id lost is money lost
        print(f"submitted batch {_get(batch, 'id')}: {len(g)} span, {model}")
    print(f"\nrecorded in {pdir / STATE_FILE}. Batches take minutes to hours. "
          f"Collect with:\n  python tools/tag_batch.py collect --project "
          f"{a.project} [--wait]")
    return 0


def cmd_collect(a) -> int:
    pdir = config.project_dir(a.project)
    spans = load_spans(pdir)
    st = load_state(pdir)
    pend = pending(st)
    if not pend:
        print("no uncollected batch")
        return 0
    client = CLIENT_FACTORY()
    while True:
        running = []
        for b in pend:
            r = client.messages.batches.retrieve(b["id"])
            if _get(r, "processing_status") != "ended":
                rc = _get(r, "request_counts")
                running.append(f"{b['id']}: {_get(r, 'processing_status')} "
                               f"(processing {_get(rc, 'processing', '?')}, "
                               f"succeeded {_get(rc, 'succeeded', '?')})")
        if not running or not a.wait:
            break
        print("waiting: " + "; ".join(running))
        time.sleep(a.poll)
    if running:
        print("batch not finished yet:\n  " + "\n  ".join(running))
        print(f"collect again later: python tools/tag_batch.py collect "
              f"--project {a.project} [--wait]")
        return 3

    out_dir = pdir / "spans.json.d"
    cast = SP.load_cast(pdir)
    wrote, kept, fails = [], [], {}
    usage_tot = {"in": 0, "cw": 0, "cr": 0, "out": 0}
    cost_tot, cost_known = 0.0, True
    for b in pend:
        seen = set()
        for item in client.messages.batches.results(b["id"]):
            cid = _get(item, "custom_id")
            sid = b["custom_ids"].get(cid)
            if sid is None or sid not in spans:
                continue
            seen.add(cid)
            res = _get(item, "result")
            kind = _get(res, "type")
            if kind != "succeeded":
                err = _get(_get(_get(res, "error"), "error"), "message", "")
                fails[sid] = f"batch result {kind}{': ' + str(err)[:120] if err else ''}"
                continue
            msg = _get(res, "message")
            u = usage_of(msg)
            for k in usage_tot:
                usage_tot[k] += u[k]
            c = cost_usd(b["model"], u, batch=True)
            cost_known = cost_known and c is not None
            cost_tot += c or 0.0
            if _get(msg, "stop_reason") == "max_tokens":
                fails[sid] = f"reply truncated at max_tokens={MAX_TOKENS}"
                continue
            obj = parse_reply(reply_text(msg))
            probs = ["reply is not JSON"] if obj is None else validate(obj, spans[sid])
            if probs:
                fails[sid] = "; ".join(probs[:3])
                continue
            (wrote if write_span(out_dir, sid, obj) else kept).append(sid)
        for cid, sid in b["custom_ids"].items():
            if cid not in seen and sid not in fails:
                fails[sid] = "no result returned for this request"
        b["status"] = "collected"
        b["collected_at"] = _now()
    save_state(pdir, st)     # results are on disk; never fetch them twice

    print(f"batch: wrote {len(wrote)} span | already had a file (kept) "
          f"{len(kept)} | failed {len(fails)}")
    print(f"tokens: in {usage_tot['in']} | cache write {usage_tot['cw']} | "
          f"cache read {usage_tot['cr']} | out {usage_tot['out']}"
          + (f" | cost ~${cost_tot:.3f} (batch price, verify PRICES)"
             if cost_known else " | cost n/a (no listed price)"))

    esc = config.TAG_ESCALATE_MODEL
    if fails and a.escalate and esc and esc != config.TAG_MODEL:
        print(f"\nretrying {len(fails)} failed span once on {esc} "
              f"(synchronous, list price):")
        for sid in sorted(fails):
            if (out_dir / f"{sid}.json").exists():
                fails.pop(sid)
                continue
            try:
                obj, probs, u, c = tag_sync(client, pdir, spans[sid], cast, esc)
            except Exception as e:
                obj, probs, c = None, [f"API error: {type(e).__name__}"], None
            if obj is not None and not probs:
                write_span(out_dir, sid, obj)
                print(f"  {sid}: ok {_fmt_cost(c)}")
                fails.pop(sid)
            else:
                fails[sid] = f"{fails[sid]} | {esc}: {'; '.join(probs[:2])}"
                print(f"  {sid}: still failing - {probs[0][:90]}")

    # `failed` is what `status` and `submit` read to send a span to the
    # subagents instead of paying for it again. A file on disk clears it.
    failed = st.setdefault("failed", {})
    for sid, why in fails.items():
        failed[sid] = {"reason": why, "at": _now()}
    for sid in list(failed):
        if (out_dir / f"{sid}.json").exists():
            failed.pop(sid)
    save_state(pdir, st)
    if fails:
        print(f"\n{len(fails)} span NOT tagged - subagent fallback "
              f"(tools/span_prompt.md), or resubmit with --retry-failed:")
        for sid in sorted(fails):
            print(f"  {sid}: {fails[sid][:160]}")
        return 2
    return 0


def cmd_status(a) -> int:
    """One word for run.ps1. Reads local files only: no key, no network."""
    pdir = config.project_dir(a.project)
    st = load_state(pdir)
    todo = tags_todo(pdir)
    if pending(st):
        print("PENDING")
    elif not todo:
        print("NONE")
    elif [s for s in todo if s not in st.get("failed", {})]:
        print("NEW")
    else:
        print("TRIED")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pilot")
    p.add_argument("--project", required=True)
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--spans", nargs="*")
    p.add_argument("--no-escalate", dest="escalate", action="store_false")
    p = sub.add_parser("submit")
    p.add_argument("--project", required=True)
    p.add_argument("--retry-failed", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="submit even though an earlier batch is uncollected")
    p = sub.add_parser("collect")
    p.add_argument("--project", required=True)
    p.add_argument("--wait", action="store_true")
    p.add_argument("--poll", type=int, default=60)
    p.add_argument("--no-escalate", dest="escalate", action="store_false")
    p = sub.add_parser("status")
    p.add_argument("--project", required=True)
    a = ap.parse_args(argv)
    try:
        return {"pilot": cmd_pilot, "submit": cmd_submit,
                "collect": cmd_collect, "status": cmd_status}[a.cmd](a)
    except TagBatchError as e:
        print(f"tag_batch: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
