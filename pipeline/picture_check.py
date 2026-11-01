# -*- coding: utf-8 -*-
"""Does the PICTURE show what the narration says? Measured on final.mp4.

WHY
---
Every binding gate checks the PLAN: the line's clip window against the shot
catalogue. None of them looks at the finished file, so a cut that lands on
the wrong shot, a window that runs on into the next scene, or the same shot
reused under two different lines is only ever found by watching the render.
This asks a fresh vision request, per narrated line, the viewer's question.

WHAT EACH REQUEST SEES - and nothing else
-----------------------------------------
  * the line's NARRATION TEXT, and
  * config.PICTURE_CHECK_FRAMES frames from the line's REAL span in the
    render (timeline out_start..out_end, which already includes the
    prepended intro - checked, see load_spans), long side
    config.PICTURE_CHECK_FRAME_SIDE.
No beat map, no shot labels, no clip plan.

THE QUESTION (recalibrated 2026-11-01)
--------------------------------------
The first version asked "do the frames show what the sentence describes?".
On a render the viewer judged to have almost no mismatch it answered 4 match,
89 partial, 11 mismatch: a recap narrates dialogue content, motives and
context that NO picture can show, so almost every line was "partial". The
question is now the viewer's: is the picture from the RIGHT SCENE / moment
with the right people, does anything on screen CONTRADICT the line, and is
the picture watchable at all. Answers:

  fits         right scene and people, nothing contradicts - even when the
               line says far more than the picture shows
  unclear      cannot tell either way (no visual anchor in the line)
  wrong-scene  the frames are from another scene / moment / people   DEFECT
  contradicts  something visible contradicts the line                 DEFECT
  unwatchable  black, end credits, a text card, a logo, or a burned-in
               title over the picture                                 DEFECT

CAUSE is assigned HERE, from the render's own clip plan (the timeline's
source windows), never by the model:
  unwatchable footage / contradicts the line - as answered
  wrong-scene ->  repeated footage   (source window shared with another line)
                  runs into a neighbouring scene (first frame fits, a later
                  one does not)
                  wrong shot         (everything else)

[PICTURE-CHECK] is a WARN: a vision judgment is fuzzy and must not block a
publish, but its worst rows go into final_report.md with output timestamps.
A check that could not run is SKIPPED, never PASS. `calibrate`
(tools/picture_check.py) runs it on two renders a viewer already judged, so
the defect rate can be compared with the viewer's verdict before anyone
trusts it.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from rich.console import Console

import config

console = Console()

STATE_FILE = "picture_check.json"
NAME = "PICTURE-CHECK"
MAX_TOKENS = 400
VERDICTS = ("fits", "unclear", "wrong-scene", "contradicts", "unwatchable")
DEFECTS = ("wrong-scene", "contradicts", "unwatchable")

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "reason": {"type": "string"},
        "frames": {"type": "array", "items": {"type": "boolean"}},
    },
    "required": ["verdict", "reason", "frames"],
    "additionalProperties": False,
}

SYSTEM = (
    "You check one line of a film recap against the picture shown under it: "
    "the narration sentence, then frames taken in order while it is spoken.\n"
    "A recap narrates dialogue, motives, backstory and context that no "
    "picture can show. That is NORMAL and is not a problem. Do not ask "
    "whether the frames show everything the sentence says. Ask only:\n"
    "1. Is the picture from the scene or moment the line is about, with the "
    "people it is about?\n"
    "2. Does anything visible CONTRADICT the line (the line says night and "
    "it is day, says he is alone and three people are there, says the car "
    "crashes and it is parked)?\n"
    "3. Is the picture unwatchable: black or near-black, end credits, a "
    "text card, a distributor logo, or a burned-in title or caption over "
    "the picture?\n"
    "verdict:\n"
    "  fits - plausibly the right scene and people and nothing contradicts "
    "the line, even if the line says much more than the picture shows.\n"
    "  unclear - you cannot tell either way.\n"
    "  wrong-scene - the frames clearly show a different scene, moment or "
    "people than the line is about.\n"
    "  contradicts - something visible contradicts the line.\n"
    "  unwatchable - any frame is black, credits, a text card, a logo or a "
    "burned-in title.\n"
    "frames: one boolean per frame, true if that frame is from the scene the "
    "line is about (false for an unwatchable frame).\n"
    "reason: one short sentence naming what is on screen.\n"
    "Reply with ONLY the JSON object.")


# --------------------------------------------------------------------------- #
# what to look at
# --------------------------------------------------------------------------- #
def _parse_ts(v):
    from pipeline.draft import parse_ts
    try:
        return parse_ts(v) if v else None
    except Exception:
        return None


def load_spans(pdir: Path, timeline: Path | None = None) -> tuple:
    """([{id, a, b, src_a, src_b}], intro_offset, notes) from timeline.json.

    out_start/out_end are FINAL-FILE positions: render.py shifts them by the
    intro it prepends. A timeline whose story lines start before the intro
    ends was written unshifted (an older render) and is shifted here, with a
    note, rather than sampling the intro block for every line.
    """
    tl = json.loads(Path(timeline or (pdir / "timeline.json"))
                    .read_text(encoding="utf-8"))
    off = float(tl.get("intro_offset") or 0.0)
    rows, notes = [], []
    for t in tl.get("lines") or []:
        try:
            a, b = float(t["out_start"]), float(t["out_end"])
        except (KeyError, TypeError, ValueError):
            continue
        if t.get("id") is None or b <= a:
            continue
        rows.append({"id": t["id"], "a": a, "b": b,
                     "src_a": _parse_ts(t.get("clip_start")),
                     "src_b": _parse_ts(t.get("clip_end"))})
    if off > 0 and rows and min(r["a"] for r in rows) < off - 0.05:
        notes.append(f"timeline.json positions start before the "
                     f"{off:.2f}s intro - treated as unshifted and moved by "
                     f"the intro offset")
        for r in rows:
            r["a"] += off
            r["b"] += off
    return rows, off, notes


def frame_times(a: float, b: float, n: int) -> list:
    return [round(a + (b - a) * (k + 0.5) / n, 3) for k in range(n)]


def extract_frame(final: Path, t: float, side: int) -> bytes:
    vf = (f"scale='if(gt(iw,ih),{side},-2)':'if(gt(iw,ih),-2,{side})'")
    r = subprocess.run([config.ffmpeg(), "-v", "error", "-ss", f"{t:.3f}",
                        "-i", str(final), "-frames:v", "1", "-vf", vf,
                        "-q:v", "4", "-f", "image2", "-c:v", "mjpeg",
                        "pipe:1"], capture_output=True)
    return r.stdout if r.returncode == 0 else b""


def build_request(narration: str, frames: list, model: str) -> dict:
    """`frames` = [(t, jpeg bytes)]. The narration and the frames, nothing
    else."""
    import base64
    content = [{"type": "text", "text": f"Narration: {narration}"}]
    for k, (t, jpg) in enumerate(frames, 1):
        content.append({"type": "text", "text": f"Frame {k} of {len(frames)}:"})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg",
            "data": base64.b64encode(jpg).decode("ascii")}})
    return {"model": model, "max_tokens": MAX_TOKENS,
            "system": [{"type": "text", "text": SYSTEM}],
            "messages": [{"role": "user", "content": content}],
            "output_config": {"format": {"type": "json_schema",
                                         "schema": SCHEMA}}}


def _cid(lid) -> str:
    return f"line-{lid}"


def requests_for(project: str, final: Path | None = None,
                 timeline: Path | None = None) -> tuple:
    """([(custom_id, line_id, span, params)], notes, skipped).

    `final` / `timeline` default to the project's final.mp4 / timeline.json;
    calibration points them at an earlier render and ITS timeline (the two
    must belong together - a timeline describes one cut)."""
    pdir = config.project_dir(project)
    final = Path(final or (pdir / "final.mp4"))
    if not final.exists():
        raise FileNotFoundError(f"{final} does not exist")
    draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    text = {ln.get("id"): str(ln.get("narration") or "").strip()
            for ln in draft.get("lines") or [] if isinstance(ln, dict)}
    spans, _off, notes = load_spans(pdir, timeline)
    n = int(config.PICTURE_CHECK_FRAMES)
    side = int(config.PICTURE_CHECK_FRAME_SIDE)
    out, skipped = [], []
    for sp in spans:
        narr = text.get(sp["id"])
        if not narr:
            continue                       # wordless unit: nothing to judge
        frames = [(t, extract_frame(final, t, side))
                  for t in frame_times(sp["a"], sp["b"], n)]
        if not all(j for _t, j in frames):
            skipped.append(sp["id"])
            continue
        out.append((_cid(sp["id"]), sp["id"], sp,
                    build_request(narr, frames, config.PICTURE_CHECK_MODEL)))
    return out, notes, skipped


# --------------------------------------------------------------------------- #
# classification - from the render's clip plan, never from the model
# --------------------------------------------------------------------------- #
def classify(res: dict, spans: list) -> str | None:
    """The cause of a DEFECT, from the clip plan; None for fits/unclear."""
    v = res.get("verdict")
    if v not in DEFECTS:
        return None
    if v == "unwatchable":
        return "unwatchable footage"
    if v == "contradicts":
        return "contradicts the line"
    me = next((s for s in spans if s["id"] == res["id"]), None)
    min_ov = float(config.FOOTAGE_REUSE_MIN_OVERLAP_SEC)
    if me and me["src_a"] is not None and me["src_b"] is not None:
        for o in spans:
            if o["id"] == me["id"] or o["src_a"] is None or o["src_b"] is None:
                continue
            ov = min(me["src_b"], o["src_b"]) - max(me["src_a"], o["src_a"])
            if ov > min_ov:
                return f"repeated footage (shares source with line {o['id']})"
    fr = list(res.get("frames") or [])
    if len(fr) >= 2 and fr[0] and not all(fr[1:]):
        return "runs into a neighbouring scene"
    return "wrong shot"


def _hms(t: float) -> str:
    from pipeline.final_report import hms
    return hms(t)


def summarise(results: list, spans: list, worst_n: int) -> dict:
    """Verdict, counts, defects by cause and the worst rows."""
    for r in results:
        r["cause"] = classify(r, spans)
    sev = {"unwatchable": 0, "contradicts": 1, "wrong-scene": 2}
    defects = [r for r in results if r["verdict"] in DEFECTS]
    worst = sorted(defects, key=lambda r: (sev[r["verdict"]], r["at"]))
    counts = {v: sum(1 for r in results if r["verdict"] == v)
              for v in VERDICTS}
    by_cause: dict = {}
    for r in defects:
        k = r["cause"].split(" (")[0]
        by_cause[k] = by_cause.get(k, 0) + 1
    return {"ok": (not defects) if results else None,
            "counts": counts, "by_cause": by_cause,
            "worst": worst[:worst_n], "defects": len(defects),
            "lines": len(results)}


def counts_text(summ: dict) -> str:
    c = summ["counts"]
    return ", ".join(f"{c[v]} {v}" for v in VERDICTS)


def write_report(pdir: Path, summ: dict, info: dict) -> Path:
    """Add the PICTURE-CHECK row to the render's final_report.md."""
    from pipeline.final_report import Report
    jp = pdir / "final_report.json"
    try:
        rep = Report.load(jp)
    except FileNotFoundError:
        rep = Report(pdir.name, pdir / "final.mp4")
        rep.note("final_report.json was not found (render older than the "
                 "picture check), so this report holds the picture check "
                 "ONLY - re-render to get every check in one file.")
    summary = (f"{summ['lines']} line(s) looked at: {counts_text(summ)}; "
               f"{summ['defects']} defect(s)"
               + (" (" + ", ".join(f"{k} {v}" for k, v in
                                    summ["by_cause"].items()) + ")"
                  if summ["by_cause"] else ""))
    if summ["ok"] is None:
        summary = "no line could be judged: " + info.get("why", "no results")
    rep.replace(NAME, ok=summ["ok"], summary=summary, fatal=False,
                numbers={"model": info.get("model"),
                         "frames per line": config.PICTURE_CHECK_FRAMES,
                         "frame long side (px)":
                             config.PICTURE_CHECK_FRAME_SIDE,
                         "lines skipped (no frame)": info.get("skipped"),
                         "tokens in": info.get("tokens_in"),
                         "tokens out": info.get("tokens_out"),
                         "cost (USD, batch)": info.get("cost")},
                rows=[{"at": _hms(r["at"]), "line": r["id"],
                       "verdict": r["verdict"], "cause": r.get("cause"),
                       "reason": r.get("reason")} for r in summ["worst"]],
                findings=[{"at": r["at"],
                           "text": f"line {r['id']} {r['verdict']} - "
                                   f"{r.get('cause')}: {r.get('reason')}"}
                          for r in summ["worst"]],
                why=("a fresh vision request per narrated line sees ONLY the "
                     "narration and frames from its real span in final.mp4 "
                     "and answers: right scene, contradicted, or unwatchable "
                     "- a recap narrates far more than a picture shows, so "
                     "'the picture does not show all of it' is not asked; "
                     "the cause comes from the render's clip plan"))
    return rep.write(pdir / "final_report.md")


def print_summary(summ: dict, info: dict) -> None:
    if summ["ok"] is None:
        console.print(f"[yellow][PICTURE-CHECK] did NOT run on this file: "
                      f"{info.get('why')} - this is not a pass.[/]")
        return
    colour = "dim" if summ["ok"] else "yellow"
    console.print(f"[{colour}][PICTURE-CHECK] {counts_text(summ)}; "
                  f"{summ['defects']} defect(s)"
                  + (f" ({', '.join(f'{k} {v}' for k, v in summ['by_cause'].items())})"
                     if summ["by_cause"] else "") + "[/]")
    for r in summ["worst"]:
        console.print(f"    {_hms(r['at'])}  line {r['id']:>4}  "
                      f"{r['verdict']:<12} {r.get('cause')}: {r.get('reason')}")
