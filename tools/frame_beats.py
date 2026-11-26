# -*- coding: utf-8 -*-
"""frame_beats.py - mark each beat as the film's present, the past, or
something imagined (pipeline/time_frame.py says why).

One call reads the whole beat map (and the Plot, when there is one): a
flashback is often only visible from its neighbours - Lost in the Stars'
"A man finds a contract and divorce papers in a drawer" (B106) is the
nurse's story of the past only because of the beats around it.

Writes:
  beat_frames.json         {"<HH:MM:SS>": "past" | "imagined"} - by the
                           beat's timestamp, so a re-assembled map (ids
                           renumbered) keeps its frames
  beats_proposal.md        a sixth column on every beat line (and on
  (+ _machine.md)          beats_proposal_machine.md); nothing else changes

    python tools/frame_beats.py <project>            # one API call (cheap)
    python tools/frame_beats.py <project> --show     # print the frames
    python tools/frame_beats.py <project> --apply-only
                                   # rewrite the column from beat_frames.json
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402

FRAMES = ("now", "past", "imagined")
_ROW = re.compile(r"^\s*(B\d{1,3})\s*\|")

PROMPT = """You read the beat map of a film - one line per beat:
id | time | what happens | who | kind - and say, for every beat that is NOT
the film's present story, which frame it is in:

  past      a flashback; a memory shown on screen; a past that a character
            recounts while the film shows it; a backstory montage
  imagined  a dream, nightmare, vision, hallucination or fantasy; a false
            version of events shown on screen as if it happened

Everything else is the present ("now") - do not list it. A recap narrator
will use this to tell a listener, who cannot see the film's own cues, that
the picture has left the present and when it comes back.

Read the beats around each one: a flashback often shows only as a break in
time or place between its neighbours (a dinner at home in the middle of a
hospital interrogation; a younger cast; a character's story being told).
The Plot, when given, says what happened when. Do not mark a beat for
being sad, tense or quiet; only for WHEN or WHETHER it happens.

Reply with ONLY the JSON object:
{"frames": [{"beat": "B05", "frame": "imagined", "why": "<6-15 words>"}]}
"""

SCHEMA = {
    "type": "object",
    "properties": {"frames": {"type": "array", "items": {
        "type": "object",
        "properties": {"beat": {"type": "string"},
                       "frame": {"type": "string",
                                 "enum": ["past", "imagined"]},
                       "why": {"type": "string"}},
        "required": ["beat", "frame", "why"],
        "additionalProperties": False}}},
    "required": ["frames"],
    "additionalProperties": False,
}


def beat_rows(text: str) -> list:
    """[(id, ts, line)] for every beat line of a beat map."""
    out = []
    for raw in text.splitlines():
        m = _ROW.match(raw)
        if not m:
            continue
        parts = [x.strip() for x in raw.strip().split("|")]
        bid = f"B{int(m.group(1)[1:]):02d}"
        out.append((bid, parts[1] if len(parts) > 1 else "", raw))
    return out


def request(pdir: Path) -> dict:
    bp = (pdir / "beats_proposal.md").read_text(encoding="utf-8-sig")
    rows = beat_rows(bp)
    body = "\n".join(" | ".join(x.strip() for x in r[2].strip().split("|")[:5])
                     for r in rows)
    user = "# BEAT MAP\n\n" + body
    pp = pdir / "plot.md"
    if pp.exists():
        user = ("# THE FILM'S PLOT (English Wikipedia)\n\n"
                + pp.read_text(encoding="utf-8-sig") + "\n\n" + user)
    eff = dict(getattr(config, "WRITE_EFFORT", {})).get("beats", "low")
    return {"model": getattr(config, "WRITE_MODEL_BEATS",
                             "claude-sonnet-5-5"),
            "max_tokens": 8192,
            "system": [{"type": "text", "text": PROMPT}],
            "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": eff,
                              "format": {"type": "json_schema",
                                         "schema": SCHEMA}}}


def frames_from_reply(obj: dict, rows: list) -> tuple:
    """({ts: frame}, problems) from the model's reply."""
    ts_of = {bid: ts for bid, ts, _ in rows}
    out, probs = {}, []
    for f in (obj or {}).get("frames") or []:
        bid = str(f.get("beat") or "").strip()
        m = re.match(r"^B(\d{1,3})$", bid)
        if not m:
            probs.append(f"not a beat id: {bid!r}")
            continue
        bid = f"B{int(m.group(1)):02d}"
        if bid not in ts_of:
            probs.append(f"{bid} is not in the beat map")
            continue
        if f.get("frame") not in ("past", "imagined"):
            probs.append(f"{bid}: frame {f.get('frame')!r}")
            continue
        out[ts_of[bid]] = f["frame"]
    return out, probs


def with_column(text: str, frames: dict) -> str:
    """The beat map with a sixth `frame` column on every beat line."""
    out = []
    for raw in text.splitlines():
        m = _ROW.match(raw)
        if raw.startswith("KEY: id | ts | what happens | chars | kind"):
            out.append("KEY: id | ts | what happens | chars | kind | frame "
                       "(now / past / imagined: when or whether it happens)")
            continue
        if not m:
            out.append(raw)
            continue
        parts = [x.strip() for x in raw.strip().split("|")]
        if len(parts) > 5 and parts[5].lower() in FRAMES:
            parts = parts[:5]
        parts = (parts + [""] * 5)[:5]
        out.append(" | ".join(parts + [frames.get(parts[1], "now")]))
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def apply(pdir: Path, frames: dict) -> int:
    n = 0
    for name in ("beats_proposal.md", "beats_proposal_machine.md"):
        p = pdir / name
        if p.exists():
            t = p.read_text(encoding="utf-8-sig")
            p.write_text(with_column(t, frames), encoding="utf-8")
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--apply-only", action="store_true")
    a = ap.parse_args()
    pdir = config.project_dir(a.project)
    fj = pdir / "beat_frames.json"
    rows = beat_rows((pdir / "beats_proposal.md").read_text(
        encoding="utf-8-sig"))
    if a.show or a.apply_only:
        frames = json.loads(fj.read_text(encoding="utf-8")) \
            if fj.exists() else {}
        if a.apply_only:
            print(f"frame_beats: column written to {apply(pdir, frames)} "
                  f"beat map(s) from beat_frames.json")
        for bid, ts, raw in rows:
            if ts in frames:
                what = raw.split("|")[2].strip() if raw.count("|") > 2 else ""
                print(f"  {bid} {ts} {frames[ts]:<9} {what[:90]}")
        return 0
    import tag_batch as TB
    p = request(pdir)
    client = TB.CLIENT_FACTORY()
    msg = TB.create_message(client, **p)
    u = TB.usage_of(msg)
    TB.ledger_append(pdir, "frames", p["model"], u, batch=False)
    obj = TB.parse_reply(TB.reply_text(msg))
    frames, probs = frames_from_reply(obj, rows)
    for x in probs:
        print(f"frame_beats: note: {x}")
    fj.write_text(json.dumps(frames, indent=1), encoding="utf-8")
    n = apply(pdir, frames)
    why = {f"B{int(str(f.get('beat'))[1:]):02d}": f.get("why")
           for f in (obj or {}).get("frames") or []
           if re.match(r"^B\d{1,3}$", str(f.get("beat") or ""))}
    print(f"frame_beats: {len(frames)} of {len(rows)} beat(s) are not the "
          f"present (${TB.cost_usd(p['model'], u):.3f}); column written to "
          f"{n} beat map(s)")
    for bid, ts, raw in rows:
        if ts in frames:
            print(f"  {bid} {ts} {frames[ts]:<9} {why.get(bid) or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
