# -*- coding: utf-8 -*-
"""write_api.py - the writing stages through the Anthropic API.

    python tools/write_api.py beats      --project P   # chunks (batch) + reveals
    python tools/write_api.py facts      --project P [--wiki "Title (film)"]
    python tools/write_api.py angle      --project P
    python tools/write_api.py plan       --project P   # plan.json, gate-checked
    python tools/write_api.py draft      --project P   # plan + acts (batch) + <=2 rounds
    python tools/write_api.py resolve    --project P   # close review findings, <=2 rounds
    python tools/write_api.py filmspeaks --project P   # selection + apply
    python tools/write_api.py estimate   --project P   # tokens/USD, no API call

WHY. These stages were OpenCode subagent halts in run.ps1 (.opencode/command/
film.md). Each one is now the SAME unit of work as a request: the stage's
prompt file VERBATIM as the system prompt (plus a short note on how to reply,
since there is no file system), and the SAME payload the subagent was told to
read, printed by the SAME payload tool (beat_payload.py, act_payload.py,
speech_at.py). The reply is written in the exact file format the existing
validators read (assemble_beats.py, assemble_draft.py, angle_spec.load,
recap.py draft, apply_film_speaks.py), and those validators are run.

COST (target ~0.5-1 USD a film). Chunks and acts go in Message Batches (half
price; latency is fine because the pipeline halts anyway). Every stable
prefix (the prompt, the style guide, the beat map an act writer shares with
the other acts) carries cache_control so it is paid once per batch window.
Payloads are the existing compact tools. Models come from config.WRITE_MODEL_*.
Every call is appended to cost_ledger.jsonl (tag_batch.ledger_append).

PLAN + RESOLVE (tools/write_plan.py): the draft is planned before it is
written (plan.json - lines per beat, holds, film_speaks spots, a word budget
per act, the title and the hook - validated with the gates' own code, one
revision on failure) and each act follows its slice; after the review stage
`resolve` closes the readers' findings in their artifacts. A bound window on
black or a text card is moved mechanically before any writer is asked.

THE DRAFT LOOP. Acts are written in one batch, assembled, and the draft gates
run (recap.py draft). Each act then gets back ONLY the findings that name its
own lines (draft-wide findings go to every act, marked as such), for at most
config.WRITE_DRAFT_FEEDBACK_ROUNDS rounds. Then it STOPS and lists what is
left - it does not loop. The review gates (COLD-READ / REVIEWER /
ENDING-READ) are not fed back here: their artifacts are written after this
by tools/review_api.py, and closing them needs RESOLVED/ANSWERED entries.

SLOTS (tools/write_slots.py). After the plan validates, code turns it into
one SLOT per line in plan.json - beat, role, length band, loop, quote, and a
clip window code assigns. Each act request carries its slots and a WRITER
BRIEF generated from the gates' constants; the reply is one line per slot
(no ids, beats or timestamps) and is merged onto the slots. Deviations from
the slots go back ONCE inside the stage. See docs/stage2/
GATES_BY_CONSTRUCTION.md for what that settles and what stays a check.

SCHEMA FIRST. Every act reply (first write and feedback rounds) and every
resolve edit is checked with schemas.line_problems - the same Line validator
schemas.load_draft runs - BEFORE it is saved. A reply that fails is not
written; its exact errors go back to the model inside the stage (counted
against the round limit). The requests also carry a json_schema output
format derived from the same schema (enums for delivery / payload /
claim.type, LINE_BOUNDS for the numbers), merged next to the effort.

Reuses tools/tag_batch.py's client (ANTHROPIC_API_KEY from the environment
only), reply parsing, usage, PRICES and ledger. Pending batches are recorded
in projects/<p>/write_api.json so an interrupted run collects them instead
of paying again.

Exit: 0 done | 1 hard error | 2 written but gates/validators still report
findings (listed) | 3 a batch is still running (run again later).
"""
from __future__ import annotations

import argparse
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
import tag_batch as TB  # noqa: E402

TOOLS = ROOT / "tools"
PROMPTS = {
    "beats": TOOLS / "beats_prompt.md",
    "reveals": TOOLS / "reveals_prompt.md",
    "facts": TOOLS / "film_facts_prompt.md",
    "angle": TOOLS / "angle_prompt.md",
    "draft": TOOLS / "draft_prompt.md",
    "filmspeaks": ROOT / "prompts" / "film_speaks_select.md",
    "plan": TOOLS / "plan_prompt.md",
    "resolve": TOOLS / "resolve_prompt.md",
}
STYLE = ROOT / "prompts" / "recap_style.md"
VOICE = ROOT / "docs" / "NARRATOR_VOICE.md"
ANGLE_EXAMPLE = ROOT / "projects" / "tokyodrift2006" / "angle.md"
STATE_FILE = "write_api.json"
MAX_TOKENS = {"beats": 8192, "reveals": 8192, "facts": 8192, "angle": 12000,
              "draft": 32000, "filmspeaks": 8192, "plan": 32000,
              "resolve": 32000}
REVIEW_GATES = ("COLD-READ", "REVIEWER", "ENDING-READ")

NOTE = ("## Delivery in this session\n\n"
        "You are called through the API: you cannot open files, run commands "
        "or write anything to disk. Everything the instructions above tell you "
        "to read is in the user message (or, where a command is named, "
        "available as a tool). Wherever the instructions say to WRITE a file, "
        "reply instead with ONLY {what} - no prose outside it, no code fence.")


class WriteError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _model(stage: str) -> str:
    """The model for a stage, read from config at call time."""
    return {"beats": config.WRITE_MODEL_BEATS,
            "reveals": config.WRITE_MODEL_REVEALS,
            "facts": config.WRITE_MODEL_FACTS,
            "angle": config.WRITE_MODEL_ANGLE,
            "draft": config.WRITE_MODEL_DRAFT,
            "filmspeaks": config.WRITE_MODEL_FILMSPEAKS,
            "plan": config.WRITE_MODEL_PLAN,
            "resolve": config.WRITE_MODEL_RESOLVE}[stage]


def _read(p: Path, missing_ok: bool = False) -> str:
    try:
        return Path(p).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        if missing_ok:
            return ""
        raise WriteError(f"missing {p}")


def _tool(script: str, *args) -> str:
    """stdout of one of the repo's payload tools, UTF-8, or WriteError."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(TOOLS / script), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), env=env)
    if r.returncode != 0:
        raise WriteError(f"{script} {' '.join(map(str, args))} failed: "
                         f"{(r.stdout + r.stderr).strip()[-300:]}")
    return r.stdout


def system_blocks(stage: str, what: str, extra: list | None = None,
                  ttl: str | None = None) -> list:
    """Prompt file verbatim + delivery note, cached; optional extra stable
    blocks (style guide, shared beat map) after it, the LAST one cached."""
    cc = {"type": "ephemeral"}
    if ttl:
        cc["ttl"] = ttl
    blocks = [{"type": "text", "text": _read(PROMPTS[stage])},
              {"type": "text", "text": NOTE.format(what=what)}]
    for t in extra or []:
        blocks.append({"type": "text", "text": t})
    blocks[-1]["cache_control"] = cc
    return blocks


def params(stage: str, system: list, user, model: str | None = None) -> dict:
    # EFFORT IS SET, NEVER LEFT TO THE DEFAULT. Claude 5.5 models think
    # adaptively by default at effort "high", and thinking shares max_tokens
    # with the reply. On furious72015 all four draft acts spent the whole
    # 32,000-token budget thinking and returned zero text - twice, because a
    # re-run changes nothing. config.WRITE_EFFORT sets it per stage.
    eff = dict(getattr(config, "WRITE_EFFORT", {})).get(stage)
    p = {"model": model or _model(stage), "max_tokens": MAX_TOKENS[stage],
         "system": system,
         "messages": [{"role": "user", "content": user}]}
    if eff:
        p["output_config"] = {"effort": eff}
    return p


# --------------------------------------------------------------------------- #
# calls: synchronous and batched, every one into the ledger
# --------------------------------------------------------------------------- #
def call(client, pdir: Path, stage: str, p: dict, note: str | None = None):
    msg = TB.create_message(client, **p)
    TB.ledger_append(pdir, stage, p["model"], TB.usage_of(msg), batch=False,
                     note=note)
    return msg


def _state(pdir: Path) -> dict:
    p = pdir / STATE_FILE
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            raise WriteError(f"{p} is not valid JSON - fix or delete it")
    return {}


def _save_state(pdir: Path, st: dict) -> None:
    (pdir / STATE_FILE).write_text(json.dumps(st, indent=1), encoding="utf-8")


def batch(client, pdir: Path, stage: str, reqs: dict, wait: bool = True,
          poll: float = 30.0) -> dict:
    """{custom_id: message} for {custom_id: params}, through ONE batch.

    The batch id is saved before waiting; a later run with the same stage
    collects it instead of submitting again. Raises WriteError(3) style
    'still running' as BatchRunning when not waiting."""
    st = _state(pdir)
    pend = st.get(stage)
    if not pend:
        b = client.messages.batches.create(requests=[
            {"custom_id": cid, "params": p} for cid, p in reqs.items()])
        pend = {"batch_id": TB._get(b, "id"), "submitted_at": _now(),
                "models": {cid: p["model"] for cid, p in reqs.items()}}
        st[stage] = pend
        _save_state(pdir, st)
        print(f"{stage}: submitted batch {pend['batch_id']} "
              f"({len(reqs)} request(s))")
    while True:
        r = client.messages.batches.retrieve(pend["batch_id"])
        if TB._get(r, "processing_status") == "ended":
            break
        if not wait:
            raise BatchRunning(f"{stage}: batch {pend['batch_id']} still "
                               f"{TB._get(r, 'processing_status')}")
        time.sleep(poll)
    out = {}
    for item in client.messages.batches.results(pend["batch_id"]):
        cid = TB._get(item, "custom_id")
        res = TB._get(item, "result")
        if TB._get(res, "type") != "succeeded":
            out[cid] = None
            # name the API's reason (e.g. a schema keyword it refuses) -
            # "the request failed" alone cannot be acted on
            print(f"{stage}: {cid} {TB._get(res, 'type')}: "
                  f"{str(TB._get(res, 'error') or '')[:300]}")
            continue
        msg = TB._get(res, "message")
        TB.ledger_append(pdir, stage, pend["models"].get(cid, "?"),
                         TB.usage_of(msg), batch=True, note=cid)
        out[cid] = msg
    st = _state(pdir)
    st.pop(stage, None)
    _save_state(pdir, st)
    return out


class BatchRunning(Exception):
    pass


def _json_reply(msg, stage: str):
    if msg is None:
        return None, "the request failed in the batch"
    if TB._get(msg, "stop_reason") == "max_tokens":
        if not str(TB.reply_text(msg) or "").strip():
            return None, (f"all {MAX_TOKENS[stage]} output tokens went to "
                          f"THINKING and no reply was written - lower "
                          f"config.WRITE_EFFORT['{stage}'] or raise "
                          f"MAX_TOKENS; re-running unchanged fails the same "
                          f"way and is billed again")
        return None, f"reply truncated at max_tokens={MAX_TOKENS[stage]}"
    obj = TB.parse_reply(TB.reply_text(msg))
    if not isinstance(obj, dict):
        return None, "reply is not a JSON object"
    return obj, None


# --------------------------------------------------------------------------- #
# beats: 8 chunks in one batch, then the reveals pass with speech_at as a tool
# --------------------------------------------------------------------------- #
KINDS = {"setup", "action", "dialogue", "discovery", "reveal", "emotion",
         "aftermath", "transition", "montage"}
_TS = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def chunks_todo(pdir: Path) -> list:
    from check_stage import N_BEAT_CHUNKS
    d = pdir / "beats.json.d"
    have = {f.stem for f in d.glob("chunk*.json")} if d.exists() else set()
    return [k for k in range(1, N_BEAT_CHUNKS + 1) if f"chunk{k}" not in have]


# Structured output: the API itself refuses a reply outside this shape. The
# first real film (furious72015) lost 3 of 8 chunks to beats whose `kind` was
# "decision", "reversal" or "reaction" - words the prompt never offered and
# check_chunk rightly rejects. A schema enum makes that reply impossible
# instead of a re-run that may or may not pass.
CHUNK_SCHEMA = {
    "type": "object",
    "properties": {
        "chunk": {"type": "integer"},
        "beats": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "ts": {"type": "string"},
                "what": {"type": "string"},
                "chars": {"type": "array", "items": {"type": "string"}},
                "kind": {"type": "string", "enum": sorted(KINDS)},
            },
            "required": ["ts", "what", "chars", "kind"],
            "additionalProperties": False}},
        "reveals": {"type": "string"},
        "set_pieces": {"type": "string"},
    },
    "required": ["chunk", "beats", "reveals", "set_pieces"],
    "additionalProperties": False,
}


def chunk_request(project: str, k: int, n: int) -> dict:
    sysb = system_blocks(
        "beats", 'the JSON object {"chunk": K, "beats": [...], "reveals": '
        '"<your REVEALS report>", "set_pieces": "<your SET-PIECES report>"} '
        "- the file's content plus the two reports the instructions ask for "
        "in your reply", ttl="1h")
    p = params("beats", sysb, _tool("beat_payload.py", project, k, n))
    p.setdefault("output_config", {})["format"] = {"type": "json_schema",
                                                   "schema": CHUNK_SCHEMA}
    return p


def check_chunk(obj: dict, k: int) -> list:
    p = []
    if obj.get("chunk") != k:
        p.append(f"chunk is {obj.get('chunk')!r}, expected {k}")
    beats = obj.get("beats")
    if not isinstance(beats, list) or not beats:
        return p + ["no beats"]
    prev = ""
    for i, b in enumerate(beats):
        if not isinstance(b, dict):
            p.append(f"beat {i} is not an object")
            continue
        if not _TS.match(str(b.get("ts") or "")):
            p.append(f"beat {i}: ts {b.get('ts')!r} is not HH:MM:SS")
        elif b["ts"] < prev:
            p.append(f"beat {i}: not in time order")
        else:
            prev = b["ts"]
        if b.get("kind") not in KINDS:
            p.append(f"beat {i}: kind {b.get('kind')!r}")
        if not str(b.get("what") or "").strip():
            p.append(f"beat {i}: empty what")
        if not isinstance(b.get("chars"), list):
            p.append(f"beat {i}: chars is not a list")
    return p


SPEECH_TOOL = {
    "name": "speech_at",
    "description": ("python tools/speech_at.py <project> <start> <end>: the "
                    "transcript and the moment descriptions between two "
                    "timestamps (HH:MM:SS)."),
    "input_schema": {"type": "object", "properties": {
        "start": {"type": "string"}, "end": {"type": "string"}},
        "required": ["start", "end"]},
}


def reveals_pass(client, project: str, pdir: Path, notes: str) -> dict:
    """Tool loop: the model calls speech_at as the prompt tells it to."""
    sysb = system_blocks(
        "reveals", 'the JSON object {"reveals": [...], "set_pieces": [...], '
        '"landing_notes": "<for each kept reveal, the timestamp first '
        'considered and the one settled on>"}')
    user = ("# beats_proposal_machine.md\n\n"
            + _read(pdir / "beats_proposal_machine.md")
            + ("\n\n# What the chunk readers reported (REVEALS / SET-PIECES)"
               "\n\n" + notes if notes.strip() else ""))
    p = params("reveals", sysb, [{"type": "text", "text": user}])
    p["tools"] = [SPEECH_TOOL]
    limit = int(config.WRITE_REVEALS_MAX_TOOL_CALLS)
    used = 0
    while True:
        msg = call(client, pdir, "reveals", p)
        uses = [b for b in (TB._get(msg, "content") or [])
                if TB._get(b, "type") == "tool_use"]
        if not uses:
            obj, why = _json_reply(msg, "reveals")
            if obj is None:
                raise WriteError(f"reveals: {why}")
            return obj
        results = []
        for u in uses:
            used += 1
            inp = TB._get(u, "input") or {}
            if used > limit:
                txt = (f"Tool budget spent ({limit} calls). Answer now with "
                       f"the JSON object.")
            else:
                try:
                    txt = _tool("speech_at.py", project, inp.get("start"),
                                inp.get("end"))[:20000]
                except WriteError as e:
                    txt = f"error: {e}"
            # An empty tool_result becomes an empty text block, which the
            # API rejects ("text content blocks must be non-empty") - the
            # furious72015 reveals pass died on exactly that when speech_at
            # had nothing in the asked range.
            if not str(txt or "").strip():
                txt = ("(nothing in that range: no transcript lines and no "
                       "moment descriptions between those timestamps)")
            results.append({"type": "tool_result",
                            "tool_use_id": TB._get(u, "id"), "content": txt})
        # the conversation so far is a stable prefix: cache it
        for m in p["messages"]:
            for blk in (m["content"] if isinstance(m["content"], list) else []):
                if isinstance(blk, dict):
                    blk.pop("cache_control", None)
        results[-1]["cache_control"] = {"type": "ephemeral"}
        _echo = [x for x in (_block(b) for b in TB._get(msg, "content"))
                 if x is not None]
        p["messages"] += [{"role": "assistant", "content": _echo},
                          {"role": "user", "content": results}]
        if used > limit + 2:
            raise WriteError("reveals: the model kept calling the tool past "
                             "its budget")


def _block(b):
    """An assistant block as it must be sent back in the tool loop, or None.

    Empty text blocks are dropped (the API rejects them), and thinking blocks
    are passed back unchanged with their signature, as tool use requires,
    instead of being flattened into empty text.
    """
    t = TB._get(b, "type")
    if t == "tool_use":
        return {"type": "tool_use", "id": TB._get(b, "id"),
                "name": TB._get(b, "name"), "input": TB._get(b, "input")}
    if t == "thinking":
        return {"type": "thinking", "thinking": TB._get(b, "thinking") or "",
                "signature": TB._get(b, "signature") or ""}
    if t == "redacted_thinking":
        return {"type": "redacted_thinking", "data": TB._get(b, "data") or ""}
    txt = TB._get(b, "text") or ""
    return {"type": "text", "text": txt} if txt.strip() else None


def check_reveals(obj: dict) -> list:
    p = []
    for i, r in enumerate(obj.get("reveals") or []):
        if not _TS.match(str(r.get("land") or "")) or not r.get("hold"):
            p.append(f"reveal {i}: needs land HH:MM:SS and hold phrases")
    if not isinstance(obj.get("reveals"), list):
        p.append("no reveals list")
    if not isinstance(obj.get("set_pieces", []), list):
        p.append("set_pieces is not a list")
    return p


def cmd_beats(a, client) -> int:
    pdir = config.project_dir(a.project)
    from check_stage import N_BEAT_CHUNKS
    todo = chunks_todo(pdir)
    d = pdir / "beats.json.d"
    d.mkdir(exist_ok=True)
    bad = {}
    if todo:
        reqs = {f"chunk{k}": chunk_request(a.project, k, N_BEAT_CHUNKS)
                for k in todo}
        got = batch(client, pdir, "beats", reqs, wait=not a.no_wait,
                    poll=a.poll)
        for k in todo:
            obj, why = _json_reply(got.get(f"chunk{k}"), "beats")
            probs = [why] if obj is None else check_chunk(obj, k)
            if probs:
                bad[k] = probs
                continue
            (d / f"chunk{k}.json").write_text(json.dumps(
                {"chunk": k, "beats": obj["beats"]}, ensure_ascii=False,
                indent=2), encoding="utf-8")
            (d / f"chunk{k}.notes.md").write_text(
                f"## REVEALS\n\n{obj.get('reveals') or ''}\n\n"
                f"## SET-PIECES\n\n{obj.get('set_pieces') or ''}\n",
                encoding="utf-8")
        print(f"beats: wrote {len(todo) - len(bad)}/{len(todo)} chunk(s)")
    if bad:
        for k, pr in bad.items():
            print(f"  chunk{k}: {'; '.join(pr[:3])}")
        print("beats: re-run to retry the failed chunks (or write them with "
              "a subagent per tools/beats_prompt.md)")
        return 2
    if not (pdir / "reveals.json").exists():
        _tool("assemble_beats.py", a.project)        # -> beats_proposal_machine.md
        notes = "\n\n".join(
            f"### chunk{k}\n" + _read(d / f"chunk{k}.notes.md", True)
            for k in range(1, N_BEAT_CHUNKS + 1)
            if (d / f"chunk{k}.notes.md").exists())
        obj = reveals_pass(client, a.project, pdir, notes)
        probs = check_reveals(obj)
        if probs:
            print("reveals: " + "; ".join(probs[:4]) + " - nothing written")
            return 2
        (pdir / "reveals.json").write_text(json.dumps(
            {"reveals": obj["reveals"], "set_pieces": obj.get("set_pieces") or []},
            ensure_ascii=False, indent=2), encoding="utf-8")
        (pdir / "reveals_notes.md").write_text(
            str(obj.get("landing_notes") or ""), encoding="utf-8")
        print(f"reveals: wrote reveals.json ({len(obj['reveals'])} reveal(s), "
              f"{len(obj.get('set_pieces') or [])} set-piece(s))")
    out = _tool("assemble_beats.py", a.project, "--out", "beats_proposal.md")
    print("beats: " + (out.strip().splitlines() or ["assembled"])[-1])
    return 0


# --------------------------------------------------------------------------- #
# facts: Wikipedia (one pinned revision) -> film_facts.json
# --------------------------------------------------------------------------- #
def wiki_title(pdir: Path, arg: str | None) -> str:
    if arg:
        return arg
    try:
        src = json.loads(_read(pdir / "names.json")).get("_source", "")
    except (WriteError, ValueError):
        src = ""
    m = re.search(r"https?://en\.wikipedia\.org/wiki/[^\s)'\"]+", src)
    if not m:
        raise WriteError("no --wiki given and names.json names no Wikipedia "
                         "URL - pass --wiki \"<Title (film)>\"")
    return m.group(0)


def compact_wikitext(t: str) -> str:
    """Wikitext without references and comments - the facts, fewer tokens."""
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"<ref[^>/]*/>", "", t)
    t = re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    return re.sub(r"\n{3,}", "\n\n", t)


FACT_FIELDS = ("title", "year", "director", "cast", "facts", "withheld")


def cmd_facts(a, client) -> int:
    from pipeline import names as N
    pdir = config.project_dir(a.project)
    if (pdir / "film_facts.json").exists() and not a.force:
        print("facts: film_facts.json exists - kept (--force to redo)")
        return 0
    rev = N.fetch_revision(wiki_title(pdir, a.wiki))
    sysb = system_blocks("facts", "the JSON object film_facts.json holds")
    user = (f"# Wikipedia: {rev['title']} (oldid={rev['oldid']}, fetched "
            f"{rev['fetched']})\n\n{compact_wikitext(rev['wikitext'])}\n\n"
            f"# projects/{a.project}/reveals.json\n\n"
            + _read(pdir / "reveals.json", True))
    for attempt in (1, 2):
        msg = call(client, pdir, "facts", params("facts", sysb, user))
        obj, why = _json_reply(msg, "facts")
        miss = [] if obj is None else [f for f in FACT_FIELDS if f not in obj]
        if obj is not None and not miss:
            # [FILM-INTRO] enforces a withheld entry only through its `ban`
            nob = [str(w.get("what", "?"))[:60] for w in obj.get("withheld") or []
                   if not [b for b in w.get("ban") or [] if str(b).strip()]]
            if not nob:
                break
            why = (f"{len(nob)} withheld entr(ies) with no `ban` list: "
                   + "; ".join(nob))
            miss = ["ban"]
        print(f"facts: attempt {attempt}: {why or 'missing fields ' + str(miss)}")
        if attempt == 2:
            print("facts: nothing written")
            return 2
        user += (f"\n\n# YOUR LAST REPLY WAS NOT SAVED\n\n- {why or miss}\n"
                 f"Every withheld entry needs `ban`: the exact phrases that "
                 f"would give it away.")
    # the source line is the tool's to write: it fetched the revision
    obj["_source"] = (f"English Wikipedia, '{rev['title']}', revision "
                      f"oldid={rev['oldid']}, fetched {rev['fetched']}.")
    (pdir / "film_facts.json").write_text(json.dumps(obj, ensure_ascii=False,
                                                     indent=2), encoding="utf-8")
    print(f"facts: wrote film_facts.json from oldid={rev['oldid']} "
          f"({len(obj.get('facts') or [])} fact(s), "
          f"{len(obj.get('withheld') or [])} withheld)")
    return 0


# --------------------------------------------------------------------------- #
# angle: angle.md + coverage_policy.json, checked by angle_spec.load
# --------------------------------------------------------------------------- #
def angle_request(pdir: Path) -> dict:
    sysb = system_blocks(
        "angle", 'the JSON object {"angle_md": "<the whole angle.md>", '
        '"coverage_policy": {"_note": "...", "mandatory": [...]}, '
        '"intro_style": {"preset": "<one preset name>", "reason": "<one '
        'line>"}} - intro_style is what intro_style.txt would hold',
        extra=["# prompts/recap_style.md\n\n" + _read(STYLE),
               "# docs/NARRATOR_VOICE.md\n\n" + _read(VOICE),
               "# One shipped example - FORMAT, not content: "
               "projects/tokyodrift2006/angle.md\n\n"
               + _read(ANGLE_EXAMPLE, True)])
    user = "\n\n".join(f"# {n}\n\n{_read(pdir / n, n != 'beats_proposal.md')}"
                       for n in ("beats_proposal.md", "reveals.json",
                                 "names.json", "film_facts.json"))
    return params("angle", sysb, user)


ANGLE_HEADINGS = ("ANGLE", "ATTITUDE TO CHARACTERS", "RUNNING BITS",
                  "ANCHORS", "HOOK PROMISES", "NARRATOR PERSONA",
                  "WHAT THE ANGLE SELECTS")


def angle_problems(spec: dict, obj: dict) -> str | None:
    """What angle_spec.load PARSED, checked against angle_prompt.md's fixed
    format. load() is lenient - it returns empty sections rather than
    failing - so an empty parse is reported here instead of written."""
    md = str(obj.get("angle_md") or "")
    miss = [h for h in ANGLE_HEADINGS
            if not re.search(rf"^##\s+{re.escape(h)}\s*$", md, re.M)]
    bits = []
    if miss:
        bits.append(f"missing section(s) {miss}")
    for key, what in (("anchors", "ANCHORS"), ("promises", "HOOK PROMISES"),
                      ("motifs", "RUNNING BITS"), ("persona", "NARRATOR PERSONA")):
        if not spec.get(key):
            bits.append(f"angle_spec.load parsed no {what} entries")
    mand = (obj.get("coverage_policy") or {}).get("mandatory")
    if not isinstance(mand, list) or not mand:
        bits.append("coverage_policy.json has no `mandatory` list")
    return "; ".join(bits) or None


def suggest_intro_style(pdir: Path, sug) -> None:
    """intro_style.txt with the angle writer's SUGGESTION - never over an
    existing file (the owner's choice). A bad suggestion is reported, not
    written, and does not fail the angle."""
    from pipeline import intro_style as _st
    if (pdir / _st.STYLE_FILE).exists():
        print(f"angle: {_st.STYLE_FILE} exists - kept (the owner's choice)")
        return
    if not isinstance(sug, dict) or not sug.get("preset"):
        print(f"angle: no intro_style suggested - {_st.STYLE_FILE} not "
              f"written; the intro keeps the legacy style until one is set")
        return
    try:
        _st.write_suggestion(pdir, sug["preset"], sug.get("reason") or "")
        print(f"angle: wrote {_st.STYLE_FILE} = {sug['preset']} (a suggestion "
              f"- edit the file to change it)")
    except _st.IntroStyleError as e:
        print(f"angle: suggested intro style NOT written - {e}")


def cmd_angle(a, client) -> int:
    from pipeline import angle_spec
    pdir = config.project_dir(a.project)
    if ((pdir / "angle.md").exists() and (pdir / "coverage_policy.json").exists()
            and not a.force):
        print("angle: angle.md + coverage_policy.json exist - kept")
        return 0
    p = angle_request(pdir)
    for attempt in (1, 2):
        msg = call(client, pdir, "angle", p, note=f"attempt {attempt}")
        obj, why = _json_reply(msg, "angle")
        if obj is None or not str(obj.get("angle_md") or "").strip() \
                or not isinstance(obj.get("coverage_policy"), dict):
            why = why or "reply lacks angle_md / coverage_policy"
        else:
            (pdir / "angle.md").write_text(obj["angle_md"], encoding="utf-8")
            (pdir / "coverage_policy.json").write_text(json.dumps(
                obj["coverage_policy"], ensure_ascii=False, indent=2),
                encoding="utf-8")
            try:
                why = angle_problems(angle_spec.load(pdir), obj)
            except Exception as e:
                why = f"angle_spec.load rejected it: {e}"
            if not why:
                print(f"angle: wrote angle.md + coverage_policy.json "
                      f"(attempt {attempt}); angle_spec.load OK")
                suggest_intro_style(pdir, obj.get("intro_style"))
                return 0
        print(f"angle: attempt {attempt}: {why}")
        # one retry with the parser's own words - cheap, and the parser is
        # the authority on the format
        p["messages"] = p["messages"][:1] + [
            {"role": "assistant",
             "content": TB.reply_text(msg) or "(empty reply)"},
            {"role": "user", "content": f"That reply failed: {why}. Reply "
             f"again with the corrected JSON object only."}]
    for n in ("angle.md", "coverage_policy.json"):
        (pdir / n).unlink(missing_ok=True)
    return 2


# --------------------------------------------------------------------------- #
# draft: acts in one batch, gates, <= N rounds of each act's own findings
# --------------------------------------------------------------------------- #
def n_acts(pdir: Path) -> int:
    bp = pdir / "beats_proposal.md"
    n = 0
    if bp.exists():
        n = len(re.findall(r"^ACT \d", _read(bp), re.M))
    return n or int(os.environ.get("RECAP_ACTS", "4"))


def acts_todo(pdir: Path) -> list:
    d = pdir / "draft.json.d"
    have = {f.stem for f in d.glob("act*.json")} if d.exists() else set()
    return [k for k in range(1, n_acts(pdir) + 1)
            if not any(h.startswith(f"act{k}") for h in have)]


def draft_system(pdir: Path) -> list:
    cuts = _read(pdir / "_cuts.json", True)
    return system_blocks(
        "draft", 'the JSON object act<N>.json holds: {"act": N, "lines": [...]}',
        extra=["# projects/<p>/beats_proposal.md (header and house rules "
               "apply to every act)\n\n" + _read(pdir / "beats_proposal.md")
               + "\n\n# projects/<p>/names.json\n\n"
               + _read(pdir / "names.json", True)
               + ("\n\n# projects/<p>/_cuts.json (ONLY for the "
                  "window-extension rule)\n\n" + cuts if cuts else "")],
        ttl="1h")


def act_request(project: str, pdir: Path, k: int, sysb: list,
                feedback: str | None = None, previous: dict | None = None,
                plan_text: str | None = None,
                slots: list | None = None, plan: dict | None = None) -> dict:
    """One act's request. With `slots` (write_slots.derive_slots) the writer
    gets its slots and the WRITER BRIEF, and the reply schema asks for one
    line per slot - no id, beat or timestamps, which code owns."""
    import write_slots as WS
    user = _tool("act_payload.py", project, k)
    if plan_text:
        user += "\n\n" + plan_text
    mine = WS.slots_for_act(slots or [], k)
    if mine:
        user += ("\n\n" + WS.writer_brief(pdir, plan or {}, k)
                 + "\n\n# YOUR SLOTS - one reply line per slot (the windows "
                   "are assigned; write to their footage)\n\n"
                 + WS.slots_text(mine))
    if feedback:
        user += ("\n\n# YOUR PREVIOUS act" + str(k) + ".json\n\n"
                 + json.dumps(previous, ensure_ascii=False)
                 + "\n\n# GATE FINDINGS ON YOUR LINES - fix exactly these, "
                   "change nothing else, reply with the whole corrected act\n\n"
                 + feedback)
    sch = act_schema(SLOT_LINE_FIELDS, SLOT_LINE_REQUIRED) if mine \
        else act_schema()
    return with_format(params("draft", sysb, user), sch)


def act_lines(obj: dict, k: int, slots: list | None, plan: dict | None,
              hook: bool = True) -> list:
    """The lines an act file gets for a reply: the writer's hook dropped
    (the plan's is used), a slot-based reply merged onto its slots' beats,
    windows and holds (write_slots.merge)."""
    import write_plan as WP
    import write_slots as WS
    lines = [l for l in obj.get("lines") or [] if isinstance(l, dict)
             and not (l.get("delivery") == "hook" or l.get("over_montage"))]
    if slots and any(l.get("slot") for l in lines):
        lines = WS.merge(lines, slots, k)
    if hook and k == 1 and plan:
        # the plan's hook, over the montage, no clip window
        lines = [WP.hook_line(plan)] + lines
    return lines


def slot_deviations(obj: dict, k: int, slots: list | None,
                    pdir: Path | None = None) -> list:
    import write_slots as WS
    lines = [l for l in obj.get("lines") or [] if isinstance(l, dict)]
    if not slots or not any(l.get("slot") for l in lines):
        return []
    return WS.check_slots(lines, WS.slots_for_act(slots, k), pdir)


def check_act(obj: dict, k: int, slots: list | None = None,
              plan: dict | None = None) -> list:
    if not isinstance(obj.get("lines"), list) or not obj["lines"]:
        return ["no lines"]
    if obj.get("act") not in (k, str(k)):
        return [f"act is {obj.get('act')!r}, expected {k}"]
    shape = [f"line {i} is not an object" for i, l in enumerate(obj["lines"])
             if not isinstance(l, dict)]
    # CORRECT BY CONSTRUCTION: the reply is checked with the SAME Line
    # validator schemas.load_draft uses, before anything is saved. A line
    # with "narration_silence_seconds": 0 used to be written, assembled, and
    # only surface as AUDIT-UNPARSEABLE - with ten audits silently skipped.
    return shape or schema_problems(act_lines(obj, k, slots, plan))


# --------------------------------------------------------------------------- #
# the draft line schema: for the request (structured output) and the reply
# --------------------------------------------------------------------------- #
def schema_problems(lines: list) -> list:
    """schemas.line_problems: what load_draft would reject, every offender."""
    from pipeline import schemas as S
    return S.line_problems(lines)


def _bounded(field: str) -> dict:
    """A number property with the bounds of schemas.LINE_BOUNDS."""
    from pipeline import schemas as S
    lo, hi, _why = S.LINE_BOUNDS[field]
    d: dict = {"type": "number"}
    rule = f"must be > {lo:g}" + (f" and <= {hi:g}" if hi is not None else "")
    if getattr(config, "WRITE_SCHEMA_NUMERIC_BOUNDS", True):
        d["exclusiveMinimum"] = lo
        if hi is not None:
            d["maximum"] = hi
    d["description"] = f"{field} {rule}; omit the field otherwise"
    return d


def line_properties() -> dict:
    """Every line property a writer may emit, typed from the draft schema:
    claim.type from schemas.ClaimType, delivery from config.TTS_DELIVERY
    (what [DELIVERY-UNKNOWN] and the TTS read), payload from
    craft_gates.PAYLOAD_KINDS (what [PAYLOAD-MIX] reads), numeric bounds
    from schemas.LINE_BOUNDS. Nothing here is a hand copy of a rule."""
    from pipeline import craft_gates as CG
    from pipeline import schemas as S
    s, b, i = {"type": "string"}, {"type": "boolean"}, {"type": "integer"}
    return {
        "id": i, "slot": s, "narration": s, "note": s,
        "clip_start": s, "clip_end": s,
        "delivery": {"type": "string", "enum": sorted(config.TTS_DELIVERY)},
        "payload": {"type": "string", "enum": list(CG.PAYLOAD_KINDS)},
        "narrative_jump": b, "bridge": b, "film_intro": b,
        "window_adjusted": b, "callback_beat": s, "hook_question": s,
        "claim": {"type": "object", "properties": {
            "type": {"type": "string", "enum": sorted(S._CLAIM_TYPES)},
            "subject": s, "requires_visual": b},
            "required": ["type"], "additionalProperties": False},
        **{f: _bounded(f) for f in S.LINE_BOUNDS},
    }


ACT_LINE_FIELDS = ("id", "narration", "note", "clip_start", "clip_end",
                   "delivery", "payload", "narrative_jump", "bridge",
                   "film_intro", "window_adjusted", "callback_beat",
                   "hook_question", "claim", "narration_silence_seconds")
ACT_LINE_REQUIRED = ("id", "narration", "note", "delivery", "payload")
# a slot-based act: code owns id, note (the beat), the window and the holds
SLOT_LINE_FIELDS = ("slot", "narration", "delivery", "payload",
                    "narrative_jump", "bridge", "film_intro", "callback_beat",
                    "claim")
SLOT_LINE_REQUIRED = ("slot", "narration", "delivery", "payload")


def act_schema(fields=ACT_LINE_FIELDS, required=ACT_LINE_REQUIRED) -> dict:
    props = line_properties()
    return {"type": "object", "properties": {
        "act": {"type": "integer"},
        "lines": {"type": "array", "items": {
            "type": "object",
            "properties": {f: props[f] for f in fields},
            "required": list(required), "additionalProperties": False}}},
        "required": ["act", "lines"], "additionalProperties": False}


def with_format(p: dict, schema: dict) -> dict:
    """Attach a json_schema output format, MERGED into output_config so the
    effort params() set is kept."""
    p.setdefault("output_config", {})["format"] = {"type": "json_schema",
                                                   "schema": schema}
    return p


def schema_feedback(errs: list) -> str:
    return ("That reply was NOT saved: these lines break the draft schema "
            "(pipeline/schemas.py, the same check recap.py draft runs):\n"
            + "\n".join(f"- {e}" for e in errs)
            + "\nFix exactly these fields (omit an optional number rather "
              "than writing 0) and reply with the whole corrected JSON "
              "object only.")


def slot_feedback(devs: list) -> str:
    return ("That reply was saved, but it does not follow its slots:\n"
            + "\n".join(f"- {e}" for e in devs)
            + "\nFix exactly these and reply with the whole act again, one "
              "line per slot.")


def retry_params(p: dict, msg, errs: list, text: str | None = None) -> dict:
    """The same request with the rejected reply and its exact errors."""
    q = json.loads(json.dumps(p))
    q["messages"] = q["messages"][:1] + [
        {"role": "assistant",
         "content": str(TB.reply_text(msg) or "") or "(empty reply)"},
        {"role": "user", "content": text or schema_feedback(errs)}]
    return q


def run_gates(project: str) -> tuple:
    """(exit code, [finding strings]) from `recap.py draft`, unwrapped."""
    env = dict(os.environ, COLUMNS="100000", PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "recap.py", "draft", "--project",
                        project], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(ROOT),
                       env=env)
    out = r.stdout + r.stderr
    finds, on = [], False
    # the Phase-1 audit prints some hard findings only to the console and
    # then exits with "Audit failed hard"; [BRIDGE] names the line after
    # each unbridged gap, so resolve can be pointed at it
    finds += [ln.strip() for ln in out.splitlines()
              if ln.startswith("[BRIDGE] beats") and "the line after it" in ln]
    # BINDING-VIOLATION (narration longer than its footage - the picture
    # freezes) lists its lines under the header, one per row: one finding
    # per line, so resolve shortens exactly those
    rows = out.splitlines()
    for i, ln in enumerate(rows):
        if ln.startswith("[BINDING-VIOLATION]"):
            for r_ in rows[i + 1:]:
                m_ = re.match(r"\s+line (\d+): (.*)", r_)
                if not m_:
                    break
                finds.append(f"[BINDING-VIOLATION] line {m_.group(1)}: "
                             f"{m_.group(2).strip()} - the narration is "
                             f"longer than its footage and the picture would "
                             f"freeze: say it in fewer words")
    for ln in out.splitlines():
        if ln.startswith("draft.json has problems:"):
            on = True
            continue
        if on and ln.startswith("  - "):
            finds.append(ln[4:].strip())
        elif on and ln.strip() and not ln.startswith("    "):
            on = False
        if ln.startswith("Audit failed hard:"):
            finds.append(ln.strip())
    return r.returncode, finds


_IDS = re.compile(r"\blines?(?:\(s\))?\s+#?(\d+(?:\s*(?:,|\+|/|-|and|&)\s*#?\d+)*)",
                  re.I)
# the gates also list ids as "[14, 30, 32]" or "...: 1, 10, 103" after line(s)
_ID_LIST = re.compile(r"\[(\d+(?:,\s*\d+)*)\]")
_AFTER_COLON = re.compile(r"\blines?(?:\(s\))?\b[^:]{0,120}:\s*(\d+(?:,\s*\d+)+)", re.I)


def finding_ids(text: str) -> set:
    ids = set()
    if re.search(r"\blines?\b|\bline\(s\)", text, re.I):
        for m in list(_ID_LIST.finditer(text)) + list(_AFTER_COLON.finditer(text)):
            ids.update(int(x) for x in re.findall(r"\d+", m.group(1)))
    for m in _IDS.finditer(text):
        nums = [int(x) for x in re.findall(r"\d+", m.group(1))]
        if "-" in m.group(1) and len(nums) == 2 and 0 < nums[1] - nums[0] < 40:
            ids.update(range(nums[0], nums[1] + 1))
        else:
            ids.update(nums)
    return ids


def act_of_lines(pdir: Path) -> dict:
    """{draft line id: (act number, the act file's own id)}."""
    d = pdir / "draft.json.d"
    key = {}
    for f in sorted(d.glob("act*.json")):
        m = re.match(r"act(\d+)", f.stem)
        try:
            o = json.loads(_read(f))
        except ValueError:
            continue
        for ln in o.get("lines") or []:
            key[(ln.get("clip_start"), str(ln.get("narration") or "").strip())] = \
                (int(m.group(1)), ln.get("id"))
    dr = json.loads(_read(pdir / "draft.json"))
    out = {}
    for ln in dr.get("lines") or []:
        k = (ln.get("clip_start"), str(ln.get("narration") or "").strip())
        if k in key:
            out[ln["id"]] = key[k]
    return out


def feedback_by_act(findings: list, owner: dict, acts: list) -> dict:
    """{act: text} - each act gets ONLY findings naming its lines; a finding
    that names no line is draft-wide and goes to every act, marked."""
    fb = {k: [] for k in acts}
    for f in findings:
        if any(f.startswith(f"[{g}]") for g in REVIEW_GATES + ("SAME-POINT",)):
            continue                      # next stage's artifacts, not fixable here
        ids = finding_ids(f)
        mine = {owner[i][0] for i in ids if i in owner}
        if not ids:
            for k in acts:
                fb[k].append("(draft-wide) " + f)
            continue
        for k in mine:
            m = ", ".join(f"draft {i} = your {owner[i][1]}" for i in sorted(ids)
                          if i in owner and owner[i][0] == k)
            fb[k].append(f"{f}\n    (line ids: {m})")
    return {k: "\n".join(f"- {x}" for x in v) for k, v in fb.items() if v}


def _assemble(project: str) -> None:
    """assemble_draft.py, with the PLAN's title when there is a plan - the
    title used to default to the project id."""
    pdir = config.project_dir(project)
    title = None
    try:
        title = json.loads(_read(pdir / "plan.json")).get("title")
    except (WriteError, ValueError):
        title = None
    _tool("assemble_draft.py", project, *(["--title", title] if title else []))


# --------------------------------------------------------------------------- #
# plan: one request before any act, validated with the gates' own code
# --------------------------------------------------------------------------- #
# exit code when the plan is rejected twice: run.ps1 halts on it with the
# plan's own message instead of falling through to the subagent loop
PLAN_STOPPED = 4


def cmd_plan(a, client) -> int:
    import write_plan as WP
    pdir = config.project_dir(a.project)
    out = pdir / "plan.json"
    if out.exists() and not a.force:
        print("plan: plan.json exists - kept (--force to re-plan)")
        return 0
    ab = WP.act_beats(a.project, _tool)
    # A plan already paid for and rejected only on counts is repaired, not
    # re-bought: if code alone makes it pass, it is the plan.
    rej = pdir / "plan_rejected.json"
    if rej.exists() and not a.force:
        try:
            old = json.loads(_read(rej))
        except ValueError:
            old = None
        if isinstance(old, dict):
            fixed = WP.repair_contour(old, pdir)
            if not WP.validate_plan(old, a.project, pdir, ab):
                out.write_text(json.dumps(old, ensure_ascii=False, indent=1),
                               encoding="utf-8")
                rej.replace(pdir / "plan_rejected.repaired.json")
                save_slots(a.project, pdir, old, ab)
                print(f"plan: repaired the rejected plan by code "
                      f"({len(fixed)} count change(s)) - no new API call")
                for c in fixed[:12]:
                    print(f"  - {c}")
                return 0
    sysb = system_blocks("plan", "the plan JSON object")
    p = params("plan", sysb, WP.plan_user(a.project, pdir, _tool, _read))
    p.setdefault("output_config", {})["format"] = {
        "type": "json_schema", "schema": WP.PLAN_SCHEMA}
    for attempt in (1, 2):
        msg = call(client, pdir, "plan", p, note=f"attempt {attempt}")
        obj, why = _json_reply(msg, "plan")
        if obj is not None:
            # counts are arithmetic: code makes them pass the contour gate
            fixed = WP.repair_contour(obj, pdir)
            if fixed:
                print(f"plan: code adjusted {len(fixed)} beat count(s) to fit "
                      f"[PACING-CONTOUR]:")
                for c in fixed[:12]:
                    print(f"  - {c}")
                if len(fixed) > 12:
                    print(f"  ... and {len(fixed) - 12} more (marked [code: ...] "
                          f"in plan.json)")
        viol = [why] if obj is None else WP.validate_plan(obj, a.project,
                                                          pdir, ab)
        if not viol:
            out.write_text(json.dumps(obj, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            save_slots(a.project, pdir, obj, ab)
            n = sum(int(b.get("lines") or 0) for b in obj["beats"])
            print(f"plan: wrote plan.json (attempt {attempt}) - {n} lines over "
                  f"{len(obj['beats'])} beats, "
                  f"{sum(x['word_budget'] for x in obj['acts'])} words, "
                  f"title {obj['title']!r}")
            return 0
        print(f"plan: attempt {attempt} fails {len(viol)} check(s):")
        for v in viol:
            print(f"  - {v}")
        if attempt == 1:
            # ONE revision, with the violations in the gates' own words
            p["messages"] = p["messages"][:1] + [
                {"role": "assistant",
                 "content": TB.reply_text(msg) or "(empty reply)"},
                {"role": "user", "content": "That plan fails these checks:\n"
                 + "\n".join(f"- {v}" for v in viol)
                 + "\nReply with the whole corrected plan JSON only."}]
    if obj is not None:
        (pdir / "plan_rejected.json").write_text(
            json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    print("plan: STOPPING - no act is written to a plan that misses the gates "
          "(the last attempt is in plan_rejected.json)")
    return PLAN_STOPPED


def save_slots(project: str, pdir: Path, plan: dict, ab: dict,
               r: dict | None = None) -> bool:
    """plan.json grows one SLOT per line, derived by code from the plan's
    per-beat counts and the gate rules (tools/write_slots.py). `r` = an
    already-derived result (fix_line compares before it saves)."""
    import write_slots as WS
    try:
        r = r if r is not None else WS.derive_slots(plan, project, pdir, ab)
    except Exception as e:
        # no slots = the act writers get the plan slice as before; say so
        print(f"plan: slots NOT derived ({type(e).__name__}: {e}) - the acts "
              f"are written from the per-beat plan alone")
        return False
    plan["slots"] = r["slots"]
    plan["slot_problems"] = r["problems"]
    plan["slots_version"] = r.get("version", 1)
    (pdir / "plan.json").write_text(json.dumps(plan, ensure_ascii=False,
                                               indent=1), encoding="utf-8")
    nar = sum(1 for x in r["slots"] if x["role"] not in ("hold",
                                                          "film_speaks"))
    print(f"plan: {len(r['slots'])} slot(s) ({nar} narrated) with code-"
          f"assigned windows" + (f"; {len(r['problems'])} problem(s): "
                                 + "; ".join(r["problems"][:3])
                                 if r["problems"] else ""))
    return True


def cmd_draft(a, client) -> int:
    pdir = config.project_dir(a.project)
    d = pdir / "draft.json.d"
    d.mkdir(exist_ok=True)
    import write_plan as WP
    sysb = draft_system(pdir)
    todo = acts_todo(pdir)
    plan, ab = None, {}
    if todo or a.feedback_only:
        if not (pdir / "plan.json").exists():
            rc = cmd_plan(a, client)
            if rc:
                return rc
        plan = json.loads(_read(pdir / "plan.json"))
        ab = WP.act_beats(a.project, _tool)
        import write_slots as WS
        if not plan.get("slots") or plan.get("slots_version") != WS.SLOTS_VERSION:
            # no slots yet, or slots an older derive_slots built: re-derive
            # from the SAME plan (no API call) so a fix reaches this project
            if plan.get("slots"):
                print(f"plan: slots are version {plan.get('slots_version', 1)}, "
                      f"code is {WS.SLOTS_VERSION} - re-deriving them from "
                      f"plan.json")
            save_slots(a.project, pdir, plan, ab)
    slots = (plan or {}).get("slots") or None
    if not todo and not a.feedback_only:
        print("draft: every act is written - nothing to do "
              "(--feedback-only to run the gate-feedback rounds)")
        return 0
    rounds = int(config.WRITE_DRAFT_FEEDBACK_ROUNDS)
    used = 0
    if todo:
        pending = {f"act{k}": act_request(
            a.project, pdir, k, sysb,
            plan_text=WP.plan_for_act(plan, ab.get(k, []), k),
            slots=slots, plan=plan) for k in todo}
        bad, tag, slot_fb = {}, "draft", set()
        sent_devs: dict = {}
        while pending:
            got = batch(client, pdir, tag, pending, wait=not a.no_wait,
                        poll=a.poll)
            retry = {}
            for cid, p in pending.items():
                k = int(cid[3:])
                obj, why = _json_reply(got.get(cid), "draft")
                probs = [why] if obj is None else check_act(obj, k, slots,
                                                            plan)
                if probs:
                    if (d / f"act{k}.json").exists() and k in slot_fb:
                        # the slot round's reply broke the schema: the
                        # schema-valid first reply stays
                        print(f"  act{k}: slot-round reply NOT saved "
                              f"({'; '.join(probs[:2])}) - kept the first")
                        continue
                    bad[k] = probs
                    # a reply that parsed but breaks the schema goes back
                    # with its exact errors, inside this stage; it is never
                    # written. Each such round counts toward the limit.
                    if obj is not None and used < rounds:
                        retry[cid] = retry_params(p, got.get(cid), probs)
                    continue
                bad.pop(k, None)
                af = d / f"act{k}.json"
                if slots and k in slot_fb and af.exists():
                    # the slot-fix reply REVISES the saved act slot by slot:
                    # a slot it leaves out keeps its line (a fix reply that
                    # omitted S049 used to delete it for good)
                    import write_slots as WS
                    lines_, notes_ = WS.merge_revision(
                        json.loads(_read(af))["lines"],
                        [l for l in obj.get("lines") or []
                         if isinstance(l, dict)],
                        WS.slots_for_act(slots, k), k,
                        # the deviations sent back may be about labels
                        # (ACTION-STAKE's "payload stake"): let the fix in
                        allow_labels=any("payload" in x for x in
                                         sent_devs.get(k, [])))
                    for n_ in notes_[:4]:
                        print(f"  act{k}: {n_}")
                else:
                    lines_ = act_lines(obj, k, slots, plan)
                af.write_text(json.dumps(
                    {"act": k, "lines": lines_},
                    ensure_ascii=False, indent=2), encoding="utf-8")
                # checked against its slots AT ONCE - on what was SAVED, not
                # on the reply (a refused rewrite leaves the old fault); the
                # deviations go back ONCE inside the stage
                devs = slot_deviations({"lines": lines_}, k, slots, pdir)
                if devs and k not in slot_fb and used < rounds:
                    sent_devs[k] = devs
                    slot_fb.add(k)
                    retry[cid] = retry_params(p, got.get(cid), devs,
                                              slot_feedback(devs))
                elif devs:
                    print(f"  act{k}: {len(devs)} slot deviation(s) left for "
                          f"the gates: {'; '.join(devs[:3])}")
            if not retry:
                break
            used += 1
            tag = f"draft-schema{used}"
            print(f"draft: {len(retry)} act(s) sent back (schema errors: not "
                  f"saved; slot deviations: saved, one fix) - round "
                  f"{used}/{rounds}")
            pending = retry
        print(f"draft: wrote {len(todo) - len(bad)}/{len(todo)} act(s)")
        if bad:
            for k, pr in bad.items():
                print(f"  act{k}: {'; '.join(pr[:3])}")
            return 2
    _fix_windows(a.project)
    _assemble(a.project)
    rounds -= used
    acts = list(range(1, n_acts(pdir) + 1))
    carry: dict = {}           # {act: schema errors of a rejected reply}
    for rnd in range(1, rounds + 2):
        rc, finds = run_gates(a.project)
        fb = feedback_by_act(finds, act_of_lines(pdir), acts)
        for k, errs in carry.items():
            fb[k] = ("\n".join(f"- (schema - your last reply was NOT saved) "
                                f"{e}" for e in errs)
                     + ("\n" + fb[k] if fb.get(k) else ""))
        carry = {}
        if plan:
            # did each act follow the plan? (check_act's plan half)
            for k in acts:
                f = d / f"act{k}.json"
                if not f.exists():
                    continue
                mm = WP.check_plan_counts(json.loads(_read(f))["lines"], plan,
                                          ab.get(k, []))
                if mm:
                    fb[k] = (fb.get(k, "") + ("\n" if fb.get(k) else "")
                             + "\n".join(f"- (plan) {m}" for m in mm))
        if not fb:
            left = [f for f in finds
                    if not any(f.startswith(f"[{g}]") for g in REVIEW_GATES)]
            print(f"draft: gates clean apart from the review stage "
                  f"({len(finds) - len(left)} review-artifact finding(s) - "
                  f"tools/review_api.py writes those next)" if finds else
                  "draft: gates clean")
            return 0
        if rnd > rounds:
            print(f"draft: {rounds} feedback round(s) done; STOPPING with "
                  f"{sum(v.count(chr(10) + '- ') + 1 for v in fb.values())} "
                  f"finding(s) still open - for a human or the subagent "
                  f"round in run.ps1:")
            for k, v in fb.items():
                print(f"  act{k}:\n" + "\n".join("    " + x
                                                 for x in v.splitlines()))
            return 2
        reqs = {f"act{k}": act_request(
            a.project, pdir, k, sysb, feedback=v,
            previous=json.loads(_read(d / f"act{k}.json")),
            plan_text=(WP.plan_for_act(plan, ab.get(k, []), k) if plan
                       else None), slots=slots, plan=plan)
            for k, v in fb.items()}
        print(f"draft: feedback round {rnd}/{rounds} - "
              f"{len(reqs)} act(s) with findings")
        got = batch(client, pdir, f"draft-round{rnd}", reqs,
                    wait=not a.no_wait, poll=a.poll)
        for cid, msg in got.items():
            k = int(cid[3:])
            obj, why = _json_reply(msg, "draft")
            probs = [why] if obj is None else check_act(obj, k, slots, plan)
            if probs:
                print(f"  act{k}: round {rnd} reply NOT saved "
                      f"({'; '.join(probs[:2])}) - kept the previous")
                if obj is not None:
                    carry[k] = probs
                continue
            prev = json.loads(_read(d / f"act{k}.json"))["lines"]
            if slots and any(l.get("slot") for l in prev):
                # slot-written act: the revision is applied slot by slot -
                # it can improve a line, never drop one or break its slot
                import write_slots as WS
                lines, notes = WS.merge_revision(
                    prev, [l for l in obj.get("lines") or []
                           if isinstance(l, dict)],
                    WS.slots_for_act(slots, k), k,
                    allow_labels=any(g in str(fb.get(k) or "")
                                     for g in LABEL_FINDINGS))
                for n_ in notes[:6]:
                    print(f"  act{k}: {n_}")
                (d / f"act{k}.json").write_text(json.dumps(
                    {"act": k, "lines": lines}, ensure_ascii=False,
                    indent=2), encoding="utf-8")
                continue
            keep = [l for l in prev if l.get("over_montage")
                    or l.get("delivery") == "hook"]
            new = act_lines(obj, k, slots, plan, hook=False)
            (d / f"act{k}.json").write_text(json.dumps(
                {"act": k, "lines": keep + new}, ensure_ascii=False,
                indent=2), encoding="utf-8")
        _fix_windows(a.project)
        _assemble(a.project)
    return 2


def _fix_windows(project: str) -> None:
    """UNWATCHABLE-FOOTAGE, mechanically, on the act files before the gates
    (write_plan.fix_unwatchable)."""
    import write_plan as WP
    d = config.project_dir(project) / "draft.json.d"
    files = sorted(d.glob("act*.json"))
    acts = [(f, json.loads(_read(f))) for f in files]
    lines = [l for _f, o in acts for l in o.get("lines") or []]
    done = WP.fix_unwatchable(project, lines)
    for m in done:
        print(f"draft: UNWATCHABLE-FOOTAGE {m}")
    if any("moved to" in m for m in done):
        for f, o in acts:
            f.write_text(json.dumps(o, ensure_ascii=False, indent=2),
                         encoding="utf-8")


# --------------------------------------------------------------------------- #
# resolve: act on the review findings, close them in the artifacts
# --------------------------------------------------------------------------- #
# Gate findings that are ABOUT labels: a line they name may change its
# payload / delivery (other rewrites keep the labels they had - a reviser
# that echoes fields back relabelled 68 lines on Furious 7).
LABEL_FINDINGS = ("PAYLOAD", "DELIVERY", "[ACTION-STAKE]", "[LOOP-CADENCE]")


def gate_findings(project: str, wide: list | None = None) -> list:
    """The draft gates' hard errors that name lines, as resolve findings.
    The review-artifact gates are not here - open_findings has those. Hard
    errors that name NO line go into `wide` (if given): resolve cannot route
    them, and must not call the draft clean while they stand."""
    _rc, errs = run_gates(project)
    out = []
    for e in errs:
        if any(e.startswith(f"[{g}]") for g in REVIEW_GATES + ("SAME-POINT",)):
            continue
        ids = sorted(finding_ids(e))
        if ids:
            out.append({"artifact": None, "kind": "gate", "gate": True,
                        "ids": [str(i) for i in ids], "text": e})
        elif wide is not None:
            wide.append(e)
    return out


def resolve_tags(slot_of: dict, by_id: dict) -> dict:
    """{line id: its slot AND what is wrong with the line right now}, so a
    fix is aimed (Furious 7: line 188 read as commentary because of "the
    whole"; the reviser saw only "ACTION on an ANCHOR"). Every line of a real
    draft passes through here - holds included."""
    import write_slots as WS
    tags = {}
    for lid, sl in slot_of.items():
        now = [m.split(": ", 1)[-1] for m in
               WS.line_deviations(by_id[lid], sl)] if lid in by_id else []
        tags[lid] = WS.slot_tag(sl) + (f"; NOW WRONG: {'; '.join(now)}"
                                       if now else "")
    return tags


def slots_of_lines(pdir: Path, owner: dict) -> dict:
    """{draft line id (str): its slot} for a slot-written draft, else {}."""
    f = pdir / "plan.json"
    if not f.exists():
        return {}                       # not a slot-written draft
    try:
        plan = json.loads(f.read_text(encoding="utf-8-sig"))
    except ValueError:
        return {}
    by_slot = {s["slot"]: s for s in plan.get("slots") or []}
    if not by_slot:
        return {}
    own = {}
    for f in sorted((pdir / "draft.json.d").glob("act*.json")):
        m = re.match(r"act(\d+)$", f.stem)
        if not m:
            continue
        for ln in json.loads(_read(f)).get("lines") or []:
            if ln.get("slot") in by_slot:
                own[(int(m.group(1)), ln.get("id"))] = by_slot[ln["slot"]]
    return {str(lid): own[ko] for lid, ko in owner.items() if ko in own}


def write_back(pdir: Path, draft: dict, by_id: dict, owner: dict,
               edits: dict, changes: dict, entries: dict) -> None:
    """The ONE way a line change is saved after the review stage: draft.json
    AND the act files (assembly reads those), the changed lines re-signed in
    every review artifact, and the RESOLVED / ANSWERED entries appended.
    resolve and tools/fix_line.py both go through here - a hand edit to
    draft.json alone leaves the artifacts' signatures stale."""
    from pipeline import review_artifacts as RA
    import write_plan as WP
    d = pdir / "draft.json.d"
    for lid, new in changes.items():
        edits.setdefault(lid, {})["narration"] = new
    acts_ = {f: json.loads(_read(f)) for f in sorted(d.glob("act*.json"))}
    for lid, fe in edits.items():
        by_id[lid].update(fe)
        k, own = owner.get(int(lid), (None, None))
        for f, o in acts_.items():
            if k is not None and re.match(rf"act{k}\b|act{k}[a-z]", f.stem):
                for ln in o.get("lines") or []:
                    if ln.get("id") == own:
                        ln.update(fe)
    (pdir / "draft.json").write_text(json.dumps(draft, ensure_ascii=False,
                                                indent=2), encoding="utf-8")
    for f, o in acts_.items():
        f.write_text(json.dumps(o, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    resign = {RA._norm_id(i): RA.line_signature(t) for i, t in changes.items()}
    for art in WP.ARTIFACTS:
        p = pdir / art
        if p.exists() and (entries.get(art) or resign):
            WP.write_artifact(p, entries.get(art, []), resign)


def cmd_resolve(a, client) -> int:
    import write_plan as WP
    import write_slots as WS
    from pipeline import review_artifacts as RA
    pdir = config.project_dir(a.project)
    d = pdir / "draft.json.d"
    rounds = int(config.WRITE_RESOLVE_ROUNDS)
    carry: dict = {}
    for rnd in range(1, rounds + 2):
        draft = json.loads(_read(pdir / "draft.json"))
        finds = WP.open_findings(pdir, draft)
        # the draft's own gates are findings too, IN THE SAME ROUND: a fix
        # that clears the readers but breaks a gate is not a fix, and waiting
        # for the readers to be closed first meant (Furious 7 run 6) that two
        # unclosable reader findings kept three gate errors from ever being
        # sent. Each gate finding names its lines; a draft-wide one with no
        # line is the layout's job.
        wide: list = []
        for i, f in enumerate(gate_findings(a.project, wide), 1):
            f["key"] = f"G{i}"
            finds.append(f)
        if not finds:
            if wide:
                # not clean: draft-wide errors name no line, so no reviser
                # can be pointed at them - say so instead of "clean"
                print(f"resolve: no line-level finding left, but "
                      f"{len(wide)} draft-wide gate error(s) name no line:")
                for w in wide[:6]:
                    print(f"  - {w[:200]}")
                return 2
            print("resolve: no open review finding, draft gates clean")
            return 0
        if rnd > rounds:
            print(f"resolve: {rounds} round(s) done; STOPPING with "
                  f"{len(finds)} finding(s) still open:")
            for f in finds:
                print(f"  {f['artifact']}: {f['kind']} @ "
                      f"{','.join(f['ids']) or '-'} - {f['text'][:120]}")
            return 2
        owner = act_of_lines(pdir)
        by_id = {str(l["id"]): l for l in draft["lines"]}
        slot_of = slots_of_lines(pdir, owner)
        tags = resolve_tags(slot_of, by_id)
        groups: dict = {}
        for f in finds:
            acts_ = {owner[int(i)][0] for i in f["ids"]
                     if i.isdigit() and int(i) in owner}
            groups.setdefault(min(acts_) if acts_ else 1, []).append(f)
        reqs = {}
        sysb = system_blocks("resolve", "the JSON object {lines, responses}",
                             ttl="1h")
        for k, fs in groups.items():
            mine = [l for l in draft["lines"]
                    if owner.get(l["id"], (None,))[0] == k
                    or str(l["id"]) in {i for f in fs for i in f["ids"]}]
            user = WP.resolve_user(mine, fs, tags)
            if carry.get(k):
                user += ("\n\n# YOUR LAST EDITS THAT WERE NOT SAVED (they "
                         "break the draft schema, their slot, or a draft "
                         "gate that judges one line). If a slot "
                         "cannot hold the fix - its footage holds too few "
                         "words - answer the finding ANSWERED and say so "
                         "instead of rewriting again.\n\n"
                         + "\n".join(f"- {e}" for e in carry[k]))
            reqs[f"act{k}"] = with_format(params("resolve", sysb, user),
                                          resolve_schema())
        print(f"resolve: round {rnd}/{rounds} - {len(finds)} open finding(s) "
              f"over {len(reqs)} act(s)")
        got = batch(client, pdir, f"resolve-round{rnd}", reqs,
                    wait=not a.no_wait, poll=a.poll)
        changes, entries, rejects, edits = {}, {}, [], {}
        carry = {}
        from pipeline import line_rules as LR
        proposed: dict = {}
        for cid_, msg_ in got.items():
            o_, _w = _json_reply(msg_, "resolve")
            for ln_ in (o_ or {}).get("lines") or []:
                t_ = " ".join(str(ln_.get("narration") or "").split())
                if t_ and str(ln_.get("id")) in by_id:
                    proposed[str(ln_.get("id"))] = t_
        for cid, msg in got.items():
            k = int(cid[3:])
            obj, why = _json_reply(msg, "resolve")
            if obj is None:
                rejects.append(f"act{k}: {why}")
                continue
            # every edit is checked against the draft schema BEFORE anything
            # is applied or closed: a bad line is dropped from the reply (so
            # a RESOLVED cannot ride on it) and goes back next round
            named = {i for f in groups[k] for i in f["ids"]}
            keep, fedits = [], {}
            for ln in obj.get("lines") or []:
                lid = str(ln.get("id"))
                if lid not in by_id or lid not in named:
                    keep.append(ln)             # apply_resolution rejects it
                    continue
                sl = slot_of.get(lid)
                fields = EDIT_FIELDS
                if sl is not None and not any(
                        any(g in f["text"] for g in LABEL_FINDINGS)
                        for f in groups[k] if lid in f["ids"]):
                    # a reviser that echoes every field back (Furious 7: 68
                    # rewrites, rest share 25% -> 39%) relabels lines it was
                    # only asked to reword; labels change only for a finding
                    # ABOUT labels
                    fields = ("narration_silence_seconds",)
                fe = {f: ln[f] for f in fields
                      if f in ln and ln[f] != by_id[lid].get(f)}
                new = dict(by_id[lid], **fe)
                if "narration" in ln:
                    new["narration"] = " ".join(str(ln["narration"]).split())
                if sl is not None:
                    # the slot binds a rewrite exactly as it bound the first
                    # write: code's labels, and no NEW deviation from it
                    new = WS.code_labels(new, sl)
                    fe = {f: new[f] for f in EDIT_FIELDS
                          if f in new and new[f] != by_id[lid].get(f)}
                    broke = (WS.new_deviations(by_id[lid], new, sl)
                             + WS.unfixed_deviations(by_id[lid], new, sl))
                    if broke:
                        carry.setdefault(k, []).extend(
                            f"line {lid}: {b}" for b in broke)
                        rejects.append(f"act{k}: line {lid} NOT saved - it "
                                       f"breaks its slot: {'; '.join(broke)}")
                        continue
                errs = schema_problems([new])
                if errs:
                    carry.setdefault(k, []).extend(errs)
                    rejects.append(f"act{k}: line {lid} NOT saved - "
                                   f"{'; '.join(errs)}")
                    continue
                if "narration" in ln and new.get("narration") != \
                        by_id[lid].get("narration"):
                    # the draft gates that judge one line, asked BEFORE it
                    # is saved, against the draft as it will stand (other
                    # rewrites of this round included) - pipeline/line_rules
                    # the other lines as this round proposes them (every
                    # act's reply, read up front): the order of rewrites
                    # does not decide what is a repeat. A proposal refused
                    # later can leave a repeat - the next round's gate
                    # findings carry it back.
                    view = [dict(x, narration=proposed.get(str(x["id"]),
                                                           x.get("narration")))
                            if str(x["id"]) != lid else x
                            for x in draft["lines"]]
                    lr = LR.problems(pdir, view, lid, new["narration"])
                    if lr:
                        carry.setdefault(k, []).extend(
                            f"line {lid}: {b}" for b in lr)
                        rejects.append(f"act{k}: line {lid} NOT saved - "
                                       f"{'; '.join(lr)}")
                        continue
                keep.append(ln)
                if fe:
                    fedits[lid] = fe
            obj = dict(obj, lines=keep)
            ch, en, rj = WP.apply_resolution(groups[k], obj, by_id)
            changes.update(ch)
            for lid, fe in fedits.items():
                edits.setdefault(lid, {}).update(fe)
            for art, e in en.items():
                entries.setdefault(art, []).extend(e)
            rejects += [f"act{k}: {x}" for x in rj]
        write_back(pdir, draft, by_id, owner, edits, changes, entries)
        print(f"resolve: {len(edits)} line(s) changed, "
              f"{sum(len(v) for v in entries.values())} entr(ies) written")
        for r in rejects[:20]:
            print(f"  - {r}")
        run_gates(a.project)
    return 2


# fields a resolve reply may change besides the narration (a gate finding
# may need a payload, a delivery or a hold length fixed, not only words)
EDIT_FIELDS = ("delivery", "payload", "narration_silence_seconds")


def resolve_schema() -> dict:
    """write_plan.RESOLVE_SCHEMA with its line items typed from the draft
    line schema (line_properties) rather than by hand."""
    import write_plan as WP
    sch = json.loads(json.dumps(WP.RESOLVE_SCHEMA))
    props = line_properties()
    items = sch["properties"]["lines"]["items"]
    items["properties"] = {f: props[f] for f in items["properties"]}
    return sch


# --------------------------------------------------------------------------- #
# filmspeaks: the selection, then apply_film_speaks.py
# --------------------------------------------------------------------------- #
def filmspeaks_request(pdir: Path) -> dict:
    sysb = system_blocks("filmspeaks", "the JSON object "
                         "film_speaks_selection.json holds")
    dr = json.loads(_read(pdir / "draft.json"))
    lines = "\n".join(
        f"[{l.get('id')}] {l.get('clip_start', '-')}..{l.get('clip_end', '-')} "
        f"({l.get('note') or ''}) {str(l.get('narration') or '').strip()}"
        for l in dr.get("lines") or [])
    user = "\n\n".join([
        "# film_speaks_candidates.json\n\n"
        + _read(pdir / "film_speaks_candidates.json"),
        "# draft.json - the lines (id, clip window, beat, narration)\n\n" + lines,
        "# angle.md\n\n" + _read(pdir / "angle.md", True),
        "# beats_proposal.md\n\n" + _read(pdir / "beats_proposal.md", True),
        "# reveals.json\n\n" + _read(pdir / "reveals.json", True)])
    return params("filmspeaks", sysb, user)


def cmd_filmspeaks(a, client) -> int:
    pdir = config.project_dir(a.project)
    sel = pdir / "film_speaks_selection.json"
    if not sel.exists() or a.force:
        if not (pdir / "film_speaks_candidates.json").exists():
            raise WriteError("no film_speaks_candidates.json - run "
                             "tools/film_speaks_candidates.py first")
        obj, why = _json_reply(call(client, pdir, "filmspeaks",
                                    filmspeaks_request(pdir)), "filmspeaks")
        if obj is None or not isinstance(obj.get("selected"), list):
            print(f"filmspeaks: {why or 'no selected list'} - nothing written")
            return 2
        sel.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"filmspeaks: wrote {sel.name} ({len(obj['selected'])} pick(s))")
    r = subprocess.run([sys.executable, str(TOOLS / "apply_film_speaks.py"),
                        "--project", a.project], cwd=str(ROOT))
    return 0 if r.returncode == 0 else 2


# --------------------------------------------------------------------------- #
# estimate: tokens and USD from the real payloads, no API call
# --------------------------------------------------------------------------- #
CHARS_PER_TOKEN = 3.6           # conservative for English prose + timestamps


def _tok(s: str) -> int:
    return int(len(s) / CHARS_PER_TOKEN) + 1


def _usd(model: str, inp: int, out: int, cw: int = 0, cr: int = 0,
         batch_: bool = False):
    return TB.cost_usd(model, {"in": inp, "out": out, "cw": cw, "cr": cr,
                               "cw1h": cw}, batch=batch_)


def cmd_estimate(a, client=None) -> int:
    from check_stage import N_BEAT_CHUNKS
    pdir = config.project_dir(a.project)
    rows = []

    def add(stage, model, calls, inp, out, cw=0, cr=0, batch_=False):
        rows.append((stage, model, calls, inp, out, cw, cr, batch_,
                     _usd(model, inp, out, cw, cr, batch_)))

    pb = _tok(_read(PROMPTS["beats"]))
    ch = sum(_tok(_tool("beat_payload.py", a.project, k, N_BEAT_CHUNKS))
             for k in range(1, N_BEAT_CHUNKS + 1))
    add("beats", _model("beats"), N_BEAT_CHUNKS, ch, 1800 * N_BEAT_CHUNKS,
        cw=pb, cr=pb * (N_BEAT_CHUNKS - 1), batch_=True)
    bm = _tok(_read(pdir / "beats_proposal.md", True))
    rv = _tok(_read(PROMPTS["reveals"]))
    # 6 turns, each re-sending the growing conversation from cache plus ~3k
    # tokens of new speech_at output
    add("reveals", _model("reveals"), 6, 6 * 3000, 6 * 600,
        cw=rv + bm + 6 * 3000, cr=6 * (rv + bm) + 15 * 3000)
    add("facts", _model("facts"), 1, 22000, 2500)
    ang_fixed = sum(_tok(_read(p, True)) for p in
                    (PROMPTS["angle"], STYLE, VOICE, ANGLE_EXAMPLE))
    ang_var = sum(_tok(_read(pdir / n, True)) for n in
                  ("beats_proposal.md", "reveals.json", "names.json",
                   "film_facts.json"))
    add("angle", _model("angle"), 1, ang_var, 4000, cw=ang_fixed)
    na = n_acts(pdir)
    ds = _tok(_read(PROMPTS["draft"])) + bm + _tok(_read(pdir / "names.json", True))
    acts = [_tok(_tool("act_payload.py", a.project, k)) for k in range(1, na + 1)]
    out_act = int(_tok(_read(pdir / "draft.json", True)) / max(1, na)) or 5000
    add("draft", _model("draft"), na, sum(acts), out_act * na,
        cw=ds, cr=ds * (na - 1), batch_=True)
    # feedback: assume half the acts come back in each of the rounds
    fbk = max(1, na // 2) * int(config.WRITE_DRAFT_FEEDBACK_ROUNDS)
    add("draft feedback", _model("draft"), fbk,
        fbk * (sum(acts) // na + out_act + 800), fbk * out_act,
        cr=fbk * ds, batch_=True)
    # plan: angle + coverage + beat map + reveals + thresholds in; one plan
    # out (~45 tokens a beat); assume one revision
    pl_in = _tok(_read(PROMPTS["plan"])) + sum(
        _tok(_read(pdir / n, True)) for n in
        ("angle.md", "coverage_policy.json", "beats_proposal.md",
         "reveals.json")) + 600
    nb = len(re.findall(r"^\s*\|?\s*B\d{2,3}\b", _read(pdir / "beats_proposal.md",
                                                        True), re.M)) or 100
    add("plan (+1 revision)", _model("plan"), 2, 2 * pl_in + 45 * nb,
        2 * 45 * nb)
    # resolve: per act, its lines + its findings in, revised lines + one
    # response a finding out; 2 rounds, about half the acts in round 2
    act_lines = int(_tok(_read(pdir / "draft.json", True)) / max(1, na)) or 4000
    rs = _tok(_read(PROMPTS["resolve"]))
    calls = na + max(1, na // 2)
    add("resolve (2 rounds)", _model("resolve"), calls,
        calls * (act_lines // 2 + 2500), calls * 3000, cw=rs,
        cr=rs * (calls - 1), batch_=True)
    fs = sum(_tok(_read(pdir / n, True)) for n in
             ("film_speaks_candidates.json", "draft.json", "angle.md",
              "beats_proposal.md", "reveals.json"))
    add("filmspeaks", _model("filmspeaks"), 1, fs, 2500,
        cw=_tok(_read(PROMPTS["filmspeaks"])))
    print(f"ESTIMATE for {a.project} - token counts from the real payloads "
          f"({CHARS_PER_TOKEN} chars/token), USD at tag_batch.PRICES; output "
          f"tokens are assumptions:")
    print(f"  {'stage':<15} {'model':<18} {'calls':>5} {'input':>8} "
          f"{'cache_w':>8} {'cache_r':>8} {'output':>7} {'USD':>8}")
    tot, known = 0.0, True
    for st, m, c, i, o, cw, cr, b, usd in rows:
        known = known and usd is not None
        tot += usd or 0.0
        print(f"  {st:<15} {m:<18} {c:>5} {i:>8} {cw:>8} {cr:>8} {o:>7} "
              + (f"${usd:7.4f}" if usd is not None else "     n/a")
              + (" batch" if b else ""))
    print(f"  {'TOTAL':<15} {'':<18} {'':>5} {'':>8} {'':>8} {'':>8} {'':>7} "
          f"${tot:7.4f}" + ("" if known else " + unpriced model(s)"))
    return 0


# --------------------------------------------------------------------------- #
CMDS = {"plan": cmd_plan, "resolve": cmd_resolve,
        "beats": cmd_beats, "facts": cmd_facts, "angle": cmd_angle,
        "draft": cmd_draft, "filmspeaks": cmd_filmspeaks,
        "estimate": cmd_estimate}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("cmd", choices=list(CMDS))
    ap.add_argument("--project", required=True)
    ap.add_argument("--wiki", help="facts: the Wikipedia title or URL")
    ap.add_argument("--force", action="store_true",
                    help="facts/angle/filmspeaks: redo an existing output")
    ap.add_argument("--feedback-only", action="store_true",
                    help="draft: run only the gate-feedback rounds")
    ap.add_argument("--no-wait", action="store_true",
                    help="submit / check a batch and return (exit 3 if running)")
    ap.add_argument("--poll", type=float, default=30.0)
    a = ap.parse_args(argv)
    try:
        client = None if a.cmd == "estimate" else TB.CLIENT_FACTORY()
        return CMDS[a.cmd](a, client)
    except BatchRunning as e:
        print(f"{e} - run the same command again later")
        return 3
    except TB.TagBatchError as e:
        print(str(e))
        return 1
    except WriteError as e:
        print(f"write_api {a.cmd}: {e}")
        return 1
    except Exception as e:
        try:
            from pipeline.names import FetchError
        except Exception:                                   # pragma: no cover
            FetchError = ()
        if FetchError and isinstance(e, FetchError):
            print(f"write_api {a.cmd}: {e}")
            return 1
        print(f"write_api {a.cmd}: API error {type(e).__name__}: "
              f"{str(e)[:200]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
