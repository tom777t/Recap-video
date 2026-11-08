# -*- coding: utf-8 -*-
"""review_api.py - the three review readers through the Anthropic API.

    python tools/review_api.py cold-read   --project P
    python tools/review_api.py review      --project P
    python tools/review_api.py ending-read --project P
    python tools/review_api.py all         --project P   [--force]

WHY. The draft stage halts for three fresh OpenCode subagents (run.ps1, film.md
### REVIEW): a cold read, an independent reviewer and an ending read. Each is a
reader that did NOT write the draft. Through the API every reader is a FRESH
request - no conversation, no files, nothing but what its stage allows:

  cold-read    tools/cold_read_payload.py's narration text and its CHECKLIST.
               No beats, no angle, no delivery/payload labels.
  review       the fixed checklist from run.ps1's halt text, the draft lines,
               the film's beat map, angle.md, and the cold read's FINDINGS.
  ending-read  the same payload, but ONLY the closing window's lines
               (config.ENDING_WINDOW_LINES, the window [ENDING-READ] checks).

The model replies in strict JSON (findings only). THIS TOOL writes the
markdown artifact, and computes the review-signatures block with the repo's
own pipeline/review_artifacts.line_signature over exactly the lines that
reader was shown - so the artifact format cannot drift and a reader cannot
sign text it did not see. The written file is re-parsed with
review_artifacts.parse_artifact before it is kept.

The readers write FINDINGs only. RESOLVED / ANSWERED entries are for whoever
acts on them, so an artifact with findings FAILS its gate until they are
closed - which is the point. An existing artifact is never overwritten (it
may carry resolutions) unless --force.

Reuses tools/tag_batch.py's client (ANTHROPIC_API_KEY from the environment
only, never printed), reply parsing, usage and PRICES. Exit: 0 written (or
already present) | 1 hard error (no key, API error) | 2 a reply was invalid.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import tag_batch as TB  # noqa: E402
import cold_read_payload as CRP  # noqa: E402
from pipeline import review_artifacts as RA  # noqa: E402

MAX_TOKENS = 8192
STAGES = ("cold-read", "review", "ending-read")
FILES = {"cold-read": "cold_read.md", "review": "review.md",
         "ending-read": "ending_read.md"}

SCHEMA = {
    "type": "object",
    "properties": {
        "checked": {"type": "string"},
        "findings": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "ids": {"type": "array", "items": {"type": "integer"}},
                "text": {"type": "string"},
            },
            "required": ["kind", "ids", "text"],
            "additionalProperties": False,
        }},
    },
    "required": ["checked", "findings"],
    "additionalProperties": False,
}

JSON_NOTE = (
    "## How to reply\n\n"
    "You are called through the API: no files, no tools. Reply with ONLY a "
    "JSON object, no prose around it and no code fence:\n"
    '{"checked": "<one or two sentences: what you checked>", '
    '"findings": [{"kind": "<short-slug>", "ids": [<line ids>], '
    '"text": "<one sentence: what is wrong>"}]}\n'
    "`ids` are the bracketed line ids the issue is in; [] when it is about "
    "the text as a whole. One finding per issue. If you found nothing, "
    "return an empty findings list and say in `checked` what you checked - "
    "'nothing found' from a reader who skimmed is the failure this step "
    "exists to prevent.")

# run.ps1's REVIEWER halt text, as a fixed checklist (film.md ### REVIEW 2).
REVIEW_CHECKLIST = """\
You are the INDEPENDENT REVIEWER of a film-recap narration draft. You did not
write it, and you have not seen the writer's reasoning. Read the draft against
the film's beat map and check, line by line, exactly these:

  1. COLD-READ FINDINGS - every finding the blind cold read made is listed
     below. For each one that still holds in the draft, file it again with
     the same kind and line ids; a finding you judge to be wrong is still
     listed, with your reason in the text.
  2. MOTIF BUDGET - a running bit or motif (see the angle's motifs) used more
     often than the angle allows, or so often it stops landing.
  3. REPEATED PHRASING - the same phrase, construction or opener reused across
     lines where a viewer would hear it twice.
  4. UNSUPPORTED CLAIMS ABOUT THE FILM - a statement about what happens, who
     says what, or why, that the beat map does not support.
  5. NAMING AT A REVEAL - a reveal that names (or withholds) the thing it
     reveals at the wrong moment, or spoils it early.
  6. PEAKS TALKED OVER - a peak moment of the film narrated over instead of
     shown: the narration explains what the picture should be allowed to do.

Use the kinds: cold-read-<its kind>, motif-budget, repeated-phrasing,
unsupported-claim, reveal-naming, talked-over-peak.
"""

ENDING_CHECKLIST = """\
You are reading ONLY the closing lines of a film-recap narration, once, as a
viewer hears the close. You did not write it and you have not seen the rest.
Check:

  1. WHO SAYS WHAT - every attributed line or quote: is it clear who says it,
     and could it be read as someone else?
  2. WHERE EACH CALLBACK POINTS - anything referred to as already known (a
     line, a promise, a place, an object): can you tell what it points back to?
  3. DOES IT END - does the last line close the story, or trail off, restate,
     or open something new?

Use the kinds: attribution, callback, ending.
"""


class ReviewApiError(Exception):
    pass


def _client():
    return TB.CLIENT_FACTORY()


def _load_draft(pdir: Path) -> dict:
    p = pdir / "draft.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        raise ReviewApiError(f"no draft.json in {pdir}")
    except ValueError as e:
        raise ReviewApiError(f"draft.json is not valid JSON: {e}")
    if not isinstance(d, dict) or not isinstance(d.get("lines"), list):
        raise ReviewApiError("draft.json has no `lines` list")
    return d


def window_ids(draft: dict) -> list:
    """The closing window exactly as [ENDING-READ] computes it."""
    from pipeline import ending_gates as EG
    n = int(getattr(config, "ENDING_WINDOW_LINES", 5))
    lines = [ln for ln in draft.get("lines") or []
             if isinstance(ln, dict) and EG._narr(ln)]
    return [ln.get("id") for ln in (lines[-n:] if n > 0 else [])]


def _signed(draft: dict, ids=None) -> dict:
    """{norm_id: sig} for the narrated lines the reader was shown."""
    sigs = RA.draft_signatures(draft)
    if ids is None:
        return sigs
    keep = {RA._norm_id(i) for i in ids}
    return {k: v for k, v in sigs.items() if k in keep}


def _read_optional(p: Path, limit: int = 60000) -> str:
    try:
        t = p.read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    return t if len(t) <= limit else t[:limit] + "\n[... truncated ...]\n"


def cold_findings(pdir: Path) -> list:
    """The cold read's open FINDING entries, from cold_read.md."""
    art = RA.parse_artifact(pdir / FILES["cold-read"])
    if art["errors"] and not art["findings"]:
        raise ReviewApiError("cold_read.md could not be read: "
                             + "; ".join(art["errors"][:3]))
    return [f for f in art["findings"] if f["status"] == "FINDING"]


# --------------------------------------------------------------------------- #
# requests - each one holds ONLY what its reader may see
# --------------------------------------------------------------------------- #
def build_request(stage: str, pdir: Path, draft: dict, model: str) -> dict:
    if stage == "cold-read":
        system = CRP.CHECKLIST + "\n\n" + JSON_NOTE
        user = CRP.narration_payload(draft)
    elif stage == "ending-read":
        system = ENDING_CHECKLIST + "\n\n" + JSON_NOTE
        user = CRP.narration_payload(draft, ids=window_ids(draft))
    elif stage == "review":
        system = REVIEW_CHECKLIST + "\n\n" + JSON_NOTE
        parts = [f"# DRAFT - {draft.get('title') or '(untitled)'}", ""]
        for ln in draft["lines"]:
            if not isinstance(ln, dict):
                continue
            t = str(ln.get("narration") or "").strip()
            beat = str(ln.get("note") or "").strip()
            if t:
                parts.append(f"[{ln.get('id')}] ({beat}) {t}")
            elif ln.get("film_speaks_seconds") is not None:
                parts.append(f"[{ln.get('id')}] ({beat}) <the film speaks: "
                             f"{ln.get('film_speaks_quote') or 'original dialogue'}>")
            elif ln.get("narration_silence_seconds") is not None:
                parts.append(f"[{ln.get('id')}] ({beat}) [pause]")
        cf = cold_findings(pdir)
        parts += ["", "# COLD-READ FINDINGS", ""]
        parts += ([f"- {f['kind']} | {','.join(f['ids']) or '-'} | {f['text']}"
                   for f in cf] or ["(the cold read filed no findings)"])
        for name in ("beats_proposal.md", "angle.md"):
            t = _read_optional(pdir / name)
            parts += ["", f"# {name}", "", t or f"({name} not present)"]
        user = "\n".join(parts)
    else:
        raise ReviewApiError(f"unknown stage {stage}")
    params = {"model": model, "max_tokens": MAX_TOKENS,
              "system": [{"type": "text", "text": system}],
              "messages": [{"role": "user", "content": user}]}
    # Effort set explicitly, as in write_api: 5.5 models default to adaptive
    # thinking at "high", which shares max_tokens with the reply.
    _eff = dict(getattr(config, "WRITE_EFFORT", {})).get("review", "medium")
    params["output_config"] = {"effort": _eff}
    if TB.USE_STRUCTURED_OUTPUT:
        params["output_config"]["format"] = {"type": "json_schema",
                                             "schema": SCHEMA}
    return params


# --------------------------------------------------------------------------- #
# reply -> artifact
# --------------------------------------------------------------------------- #
def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s.replace("|", "/").replace("```", "'''")


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", str(s or "").lower()).strip("-")
    return s[:40] or "finding"


def validate_reply(obj, allowed: set) -> tuple:
    """(findings, problems). Findings are cleaned; ids outside what the
    reader was shown are dropped and reported, never silently kept."""
    probs = []
    if not isinstance(obj, dict) or not isinstance(obj.get("findings"), list):
        return [], ["reply is not {checked, findings[]}"]
    out = []
    for i, f in enumerate(obj["findings"], 1):
        if not isinstance(f, dict) or not str(f.get("text") or "").strip():
            probs.append(f"finding {i} has no text")
            continue
        ids, bad = [], []
        for x in f.get("ids") or []:
            (ids if RA._norm_id(x) in allowed else bad).append(RA._norm_id(x))
        if bad:
            probs.append(f"finding {i} cites line(s) {bad} the reader was "
                         f"not shown - dropped from its ids")
        out.append({"kind": _slug(f.get("kind")), "ids": ids,
                    "text": _clean(f["text"])})
    return out, probs


def render_artifact(stage: str, model: str, sigs: dict, findings: list,
                    checked: str, notes: list) -> str:
    who = {"cold-read": "Cold read - narration only, blind",
           "review": "Independent review - fixed checklist",
           "ending-read": "Ending read - the closing window only"}[stage]
    lines = [f"# {who}", "",
             f"Written by tools/review_api.py: one fresh API request "
             f"({model}) that did not write the draft and saw only what this "
             f"stage allows. {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.",
             "", f"What the reader checked: {_clean(checked) or '(not stated)'}",
             ""]
    if notes:
        lines += ["Tool notes:", ""] + [f"- {n}" for n in notes] + [""]
    lines += [f"{len(findings)} finding(s). Each must become RESOLVED or "
              f"ANSWERED by whoever acts on it.", "",
              "```review-signatures"]
    lines += [f"  {lid} {sig}" for lid, sig in sigs.items()]
    lines += ["```", "", "```review-findings"]
    lines += [f"FINDING | {f['kind']} | {','.join(f['ids']) or '-'} | "
              f"{f['text']}" for f in findings]
    lines += ["```", ""]
    return "\n".join(lines)


def run_stage(stage: str, project: str, force: bool = False,
              client=None) -> tuple:
    """(exit_code, cost or None). Writes projects/<p>/<artifact>."""
    pdir = config.project_dir(project)
    out = pdir / FILES[stage]
    if out.exists() and not force:
        print(f"{stage}: {out.name} already exists - kept (it may carry "
              f"resolutions; --force to re-read)")
        return 0, 0.0
    draft = _load_draft(pdir)
    model = config.REVIEW_API_MODEL
    ids = window_ids(draft) if stage == "ending-read" else None
    sigs = _signed(draft, ids)
    if not sigs:
        raise ReviewApiError(f"{stage}: the draft has no narrated lines to read")
    params = build_request(stage, pdir, draft, model)
    client = client or _client()
    msg = TB.create_message(client, **params)
    u = TB.usage_of(msg)
    cost = TB.cost_usd(model, u)
    TB.ledger_append(pdir, f"review:{stage}", model, u, batch=False)
    print(f"{stage}: tokens in {u['in']} out {u['out']} | cost "
          + (f"${cost:.4f}" if cost is not None else "n/a (no listed price)"))
    if TB._get(msg, "stop_reason") == "max_tokens":
        print(f"{stage}: reply truncated at max_tokens={MAX_TOKENS} - "
              f"nothing written")
        return 2, cost
    obj = TB.parse_reply(TB.reply_text(msg))
    if not isinstance(obj, dict) or not isinstance(obj.get("findings"), list):
        print(f"{stage}: reply is not the JSON {{checked, findings[]}} - "
              f"nothing written")
        return 2, cost
    findings, probs = validate_reply(obj, set(sigs))
    text = render_artifact(stage, model, sigs, findings,
                           obj.get("checked", ""), probs)
    tmp = out.with_suffix(".md.tmp")
    tmp.write_text(text, encoding="utf-8")
    art = RA.parse_artifact(tmp)
    if (art["errors"] or art["signatures"] != sigs
            or len(art["findings"]) != len(findings)):
        tmp.unlink()
        raise ReviewApiError(f"{stage}: the written artifact does not parse "
                             f"back ({art['errors'][:2]}) - nothing kept")
    tmp.replace(out)
    print(f"{stage}: wrote {out.name} - {len(sigs)} line(s) signed, "
          f"{len(findings)} finding(s)")
    for p in probs:
        print(f"  note: {p}")
    return 0, cost


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("stage", choices=STAGES + ("all",))
    ap.add_argument("--project", required=True)
    ap.add_argument("--force", action="store_true",
                    help="re-read even if the artifact exists")
    a = ap.parse_args(argv)
    stages = STAGES if a.stage == "all" else (a.stage,)
    total, known, worst = 0.0, True, 0
    try:
        client = None
        for st in stages:
            out = config.project_dir(a.project) / FILES[st]
            if client is None and (a.force or not out.exists()):
                client = _client()
            rc, c = run_stage(st, a.project, a.force, client)
            known = known and c is not None
            total += c or 0.0
            worst = max(worst, rc)
            if rc and st == "cold-read" and "review" in stages:
                print("the reviewer needs the cold read's findings - stopped")
                break
    except TB.TagBatchError as e:
        print(str(e))
        return 1
    except ReviewApiError as e:
        print(f"review_api: {e}")
        return 1
    except Exception as e:                       # API/network errors
        print(f"review_api: API error {type(e).__name__}: {str(e)[:200]}")
        return 1
    print("total cost " + (f"~${total:.4f}" if known else "n/a")
          + " (list price, verify tag_batch.PRICES)")
    return worst


if __name__ == "__main__":
    sys.exit(main())
