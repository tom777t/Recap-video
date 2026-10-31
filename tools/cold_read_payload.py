# -*- coding: utf-8 -*-
"""cold_read_payload.py - the draft as a BLIND READER sees it.

    python tools/cold_read_payload.py <project>

WHY THIS EXISTS INSTEAD OF script.txt
-------------------------------------
script.txt prints, above every line, `<delivery> {payload}` and - on a hook -
a `Q:` line. Those are the WRITER'S SELF-DECLARATION. An agent handed script.txt
is told in advance that line 6 is judgment and line 1 is a loop, and it reads
the draft looking for the thing it has been told is there. That is not a blind
read, and a review that is not blind cannot find the defects a blind read
exists to find:

  - a referent the script never introduces (a line that names a confrontation
    whose beat was cut in trimming reads perfectly well to anyone who knows the
    film, and to anyone told the line's payload is `stake`);
  - a pronoun with two possible antecedents (the writer knows which one is
    meant, so the writer cannot see the ambiguity, and neither can a reader
    reading the writer's labels);
  - a narrator claim about what a character repeatedly said or did, which is
    only checkable by someone reading the whole thing front to back.

So this tool prints the NARRATION ONLY, with line ids, and strips delivery,
payload, hook_question and the beat note.

A HOLD IS STILL VISIBLE
-----------------------
A deliberate pause carries meaning, so it is printed as `[pause]` - with NO
duration, which would be a production detail and another thing to judge. The
duration is withheld; the pause is not. An earlier research pass read a script
that printed nothing at all where the draft held, and concluded that three
deliberate silences were dead air. Whatever the draft carries, the reader must
see; otherwise the reader is reviewing a different document from the one that
will be rendered.

IT PRINTS THE SIGNATURE BLOCK
-----------------------------
The `review-signatures` block is computed by review_artifacts.draft_signatures
over the SAME draft this payload was printed from, and handed over ready to
paste. The reviewer cannot sign text it did not read, and cannot hand-type a
signature wrong, because it never types one.

TWO OPERATIONAL RULES, BOTH PAID FOR
------------------------------------
- `sys.stdout.reconfigure(encoding='utf-8')`. This repo has twice shipped a
  payload tool that died on a cp1252 UnicodeEncodeError the first time its
  output was redirected to a file - mid-list, on the first curly quote or dash
  in the narration. The agent received a plausible-looking PREFIX of the
  payload and reviewed a third of the draft without any way to know.
- every dict access through `.get`. Same failure, different cause: a KeyError
  on 10 of 531 records once truncated a payload at a third of its length, and
  the output above the traceback looked complete.
"""
from __future__ import annotations

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                          # noqa: E402
from pipeline import review_artifacts as ra            # noqa: E402

CHECKLIST = """\
## CHECKLIST - what to look for, and what to write

You have read the narration and nothing else: no beat map, no transcript, no
delivery or payload labels, no film. That is deliberate. You are the only
reader of this draft who does not already know what it meant to say.

List EVERY instance of these four, one FINDING per issue:

  1. UNINTRODUCED REFERENT - the script refers to something as already known
     that it never introduced. "the standoff", "the deal", "that promise",
     "his partner" - anything you are expected to recognise but were never
     shown. Scan back: if no earlier line introduces it, it is a finding.
     Beats get cut during trimming and the lines that pointed at them survive.

  2. AMBIGUOUS PRONOUN - any he / she / they / him / her / his / their / it
     with more than one possible antecedent in the preceding lines. Do not
     resolve it from what seems likely. If two people were named and either
     could be meant, that is a finding, and say what the two readings are.
     Include quantity and outcome ambiguity: whether someone died, whether
     something was won or lost, whether a thing was given or taken.

  3. CONFUSING ON A SINGLE READ - anywhere you had to go back. You get one
     pass; a viewer gets less. Say which line sent you backwards and why.

  4. A CLAIM ABOUT REPETITION OR HABIT - any assertion about what a character
     "spent the whole film" doing, "kept" saying, "always" does, "never" does.
     These are the easiest sentences to invent and the hardest to check, and
     they read as the most authoritative line in the paragraph. Flag every one
     so it can be checked against the transcript.

Output EXACTLY two fenced blocks and nothing else that matters:

  - the ```review-signatures block below, copied VERBATIM. Do not edit it, do
    not recompute it, do not drop lines you had no finding on. It records which
    text you read.
  - a ```review-findings block, one entry per line, four pipe-separated fields:

        <STATUS> | <kind> | <line ids, comma separated, or -> | <text>

    STATUS is FINDING for everything you found. kind is a short slug -
    dangling-ref, ambiguous-pronoun, single-read, invented-claim. ids are the
    draft line ids the issue is in, or `-` if it is about the draft as a whole.
    text is one sentence saying what is wrong.

    Example:
        FINDING | dangling-ref | 41,42 | "the standoff" is never set up; no
        earlier line shows a confrontation

    One FINDING per issue. Do not merge two issues into one entry and do not
    write RESOLVED or ANSWERED - those are for whoever acts on your findings.
    Prose outside the fences is read by a human and ignored by the gate; prose
    INSIDE a fence is a malformed entry and will fail the gate, so keep your
    reasoning above the blocks.

If you found nothing, write an empty ```review-findings block and say in prose
what you checked. "Nothing found" from a reader who skimmed is the outcome this
whole step exists to prevent.
"""


def main() -> int:
    # Before anything is printed. See the module docstring: a payload that
    # dies mid-list hands the reader a plausible prefix.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                   # pragma: no cover
        pass                                            # pre-3.7 / odd stream

    if len(sys.argv) < 2:
        print("usage: python tools/cold_read_payload.py <project>")
        return 2
    project = sys.argv[1]
    pdir = config.project_dir(project)
    dp = pdir / "draft.json"
    if not dp.exists():
        print(f"no draft.json in {pdir}")
        return 1
    try:
        draft = json.load(io.open(dp, encoding="utf-8-sig"))
    except Exception as e:
        print(f"draft.json in {pdir} is unreadable: {type(e).__name__}: {e}")
        return 1
    if not isinstance(draft, dict) or not isinstance(draft.get("lines"), list):
        print(f"draft.json in {pdir} has no `lines` list")
        return 1

    lines = draft.get("lines") or []
    rows = []
    unusable = 0
    silent = 0
    holds = 0
    for ln in lines:
        if not isinstance(ln, dict):
            unusable += 1
            continue
        text = str(ln.get("narration") or "").strip()
        hold = bool(ln.get("narration_silence_seconds"))
        # 2026-10-30, found by running this against a real project: in that
        # draft all three deliberate holds are units carrying
        # narration_silence_seconds and an EMPTY narration string. The first
        # version of this loop skipped every line with no text, so it printed
        # the count of silent units and NOT ONE `[pause]` - reproducing exactly
        # the failure the docstring above says this tool exists to avoid. A
        # hold is a unit whose entire content IS the pause; it is the one
        # textless unit that must still appear.
        if not text:
            if hold:
                holds += 1
                rows.append((ln.get("id"), None, True))
            else:
                silent += 1
            continue
        holds += hold
        rows.append((ln.get("id"), text, hold))

    print("# COLD READ - narration only")
    print()
    # The title is the one piece of metadata kept: a reader with no title
    # cannot tell an unintroduced referent from the film's own premise.
    print(f"Film: {draft.get('title') or '(untitled)'}")
    _spoken = [t for _, t, _ in rows if t]
    print(f"Lines of narration: {len(_spoken)}   "
          f"Words: {sum(len(t.split()) for t in _spoken)}   "
          f"Deliberate pauses: {holds}")
    print()
    print("Read this top to bottom, ONCE, in order, as a viewer would hear it.")
    print("Delivery tags, payload labels, the hook question and the beat notes")
    print("have been removed: they are the writer's own account of what the")
    print("line does, and you are here to read what it SAYS.")
    print("`[pause]` is a deliberate silence the draft carries. Duration is")
    print("withheld on purpose; the pause itself is not.")
    if silent:
        print(f"{silent} unit(s) carry neither narration nor a hold (film")
        print("audio) and are not printed - they have no text to read.")
    if unusable:
        print(f"!! {unusable} line record(s) could not be read and are MISSING")
        print("   from this payload. This payload is INCOMPLETE; say so in")
        print("   your review rather than signing it as a full read.")
    print()
    print("=" * 60)
    print()

    for lid, text, hold in rows:
        try:
            tag = f"[{int(lid):>3}]"
        except Exception:
            tag = f"[{str(lid)[:3]:>3}]"
        if text:
            print(f"{tag} {text}")
            if hold:
                print("      [pause]")
        else:
            print(f"{tag} [pause]")
        print()

    print("=" * 60)
    print()
    print(CHECKLIST)
    print()
    print("Copy this block verbatim into your artifact:")
    print()
    print("```review-signatures")
    # draft_signatures returns the lines in DRAFT ORDER (dicts preserve
    # insertion order), so the block reads in the same order as the payload
    # above it. Sorting it would make the two lists diverge and invite the
    # reviewer to re-derive rather than copy.
    for lid, sig in ra.draft_signatures(draft).items():
        print(f"  {lid} {sig}")
    print("```")
    print()
    print(f"Write your artifact to: {pdir / 'cold_read.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
