# -*- coding: utf-8 -*-
"""cost_report.py - what this film cost to make, from its own ledger.

    python tools/cost_report.py --project P

Reads projects/<p>/cost_ledger.jsonl - one row per Anthropic API call,
appended by tools/tag_batch.py's ledger_append() from every API caller
(tag_batch, review_api, picture_check, write_api) - and writes
projects/<p>/cost_report.md: totals per stage and per model, the grand total,
and the Inworld TTS characters of the narration on disk (from the narration
manifest, narration/_cache.json, counted on the current draft's text for the
lines the manifest holds).

USD is the price at tools/tag_batch.py PRICES when the call was made. A model
with no listed price is shown with its tokens and "n/a" - an invented price
is worse than none - and the total says it is incomplete.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import tag_batch as TB  # noqa: E402


def read_ledger(pdir: Path) -> tuple:
    rows, bad = [], 0
    p = pdir / TB.LEDGER_FILE
    if not p.exists():
        return rows, bad
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except ValueError:
            bad += 1
    return rows, bad


def _group(rows: list, key) -> dict:
    out: dict = {}
    for r in rows:
        g = out.setdefault(key(r), {"calls": 0, "input": 0, "output": 0,
                                    "cache_write": 0, "cache_read": 0,
                                    "usd": 0.0, "unpriced": 0})
        g["calls"] += 1
        for k in ("input", "output", "cache_write", "cache_read"):
            g[k] += int(r.get(k) or 0)
        if r.get("usd") is None:
            g["unpriced"] += 1
        else:
            g["usd"] += float(r["usd"])
    return out


def tts_characters(pdir: Path) -> tuple:
    """(characters, lines) of narration the manifest holds audio for."""
    try:
        man = json.loads((pdir / "narration" / "_cache.json")
                         .read_text(encoding="utf-8"))
        draft = json.loads((pdir / "draft.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None, 0
    chars = n = 0
    for ln in draft.get("lines") or []:
        t = str(ln.get("narration") or "").strip()
        if t and f"line_{int(ln['id']):03d}.mp3" in man:
            chars += len(t)
            n += 1
    return chars, n


def _usd(g) -> str:
    return (f"${g['usd']:.4f}" + (f" (+{g['unpriced']} unpriced)"
                                  if g["unpriced"] else ""))


def build(project: str) -> tuple:
    pdir = config.project_dir(project)
    rows, bad = read_ledger(pdir)
    L = [f"# Cost report - {project}", ""]
    if not rows:
        L += ["No API calls recorded (no cost_ledger.jsonl rows).", ""]
    else:
        tot = _group(rows, lambda r: "all")["all"]
        L += [f"- API calls: **{tot['calls']}**",
              f"- total: **{_usd(tot)}** at tools/tag_batch.py PRICES"
              + (" - INCOMPLETE: some calls are on a model with no listed "
                 "price" if tot["unpriced"] else ""),
              f"- tokens: input {tot['input']}, output {tot['output']}, "
              f"cache write {tot['cache_write']}, cache read "
              f"{tot['cache_read']}", ""]
        for title, key in (("Per stage", lambda r: r.get("stage") or "?"),
                           ("Per model", lambda r: r.get("model") or "?")):
            L += [f"## {title}", "",
                  "| | calls | input | output | cache write | cache read | USD |",
                  "|---|---|---|---|---|---|---|"]
            for k, g in sorted(_group(rows, key).items(),
                               key=lambda kv: -kv[1]["usd"]):
                L.append(f"| {k} | {g['calls']} | {g['input']} | "
                         f"{g['output']} | {g['cache_write']} | "
                         f"{g['cache_read']} | {_usd(g)} |")
            L.append("")
        if bad:
            L += [f"{bad} ledger row(s) could not be read and are NOT "
                  f"counted - the totals above are a floor.", ""]
    chars, n = tts_characters(pdir)
    L += ["## TTS (Inworld)", ""]
    L.append(f"- {chars} characters of narration over {n} line(s) with "
             f"audio in narration/_cache.json" if chars is not None else
             "- no narration manifest or draft - characters not counted")
    L.append("")
    out = pdir / "cost_report.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out, rows, bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--project", required=True)
    a = ap.parse_args(argv)
    out, rows, _bad = build(a.project)
    print(out.read_text(encoding="utf-8"))
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
