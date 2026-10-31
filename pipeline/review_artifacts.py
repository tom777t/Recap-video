# -*- coding: utf-8 -*-
"""review_artifacts.py - the cold read and the independent review, as GATES.

THE DEFECT
----------
A human reviewer read a finished draft and found three things that every
automated gate had passed:

  1. A line referred to "the standoff" and to a gun being taken off someone's
     head as though the viewer had just watched it - but the beat containing
     that standoff had been CUT from the draft during trimming. The referent
     was dangling: the text pointed at something the recap never showed. No
     gate could see it, because every gate checks a line against the FILM, and
     against the film the line was perfectly true. It was only false against
     the DRAFT, read front to back, by someone who had not written it.

  2. Two ambiguous pronouns. One line said a character had "lost a nephew" in
     a context where the plain reading was that the nephew had died, when he
     had not. Another used "he" where either of the two men named in the
     preceding sentence could have been meant, and the two readings said
     opposite things about the film. Both lines are grammatical, both are
     inside their beat's evidence, and both are wrong only to a reader who does
     not already know which reading was intended.

  3. A narrator claim about what a character "spent the whole film" saying.
     That sentence appears in no transcript line and in no beat. It is not a
     misquote - it is an invented pattern, a summary of a repetition that never
     happened, and it reads as the most authoritative line in the paragraph.

None of the three is detectable by text rules. A dangling referent requires
knowing what was cut; an ambiguous pronoun requires not already knowing the
answer; an invented "whole film" claim requires having read the whole film. All
three require a FRESH READER.

So the pipeline now requires two review ARTIFACTS, written by agents that did
not write the draft, and this module's job is exactly the job the angle
evidence audit does for anchor mappings (see pipeline/pacing_gates.py, the
ANCHOR-EVIDENCE audit block): prove the review HAPPENED, prove it is CURRENT,
and prove every finding was RESOLVED or ANSWERED. It does not judge the prose.
It cannot. It enforces that somebody did.

  cold_read.md  -> [COLD-READ]   a blind first read, narration only
  review.md     -> [REVIEWER]    a second pass with the draft and the film

THE ARTIFACT FORMAT
-------------------
Both artifacts are documents a human reads, so prose outside the fenced blocks
is allowed and ignored. Two fenced blocks carry the machine-readable part.

A signature block, one reviewed narrated line per entry:

    ```review-signatures
      12 1a2b3c4d
      13 9f8e7d6c
    ```

`<line_id> <sig8>`, where sig8 is `line_signature()` of the narration text the
reviewer actually read. This is what makes staleness measurable: it is the same
mechanism as pipeline/draft.py `exception_key`, which hashes the
whitespace-normalised, lowercased text precisely so a human-reviewed note STOPS
applying the moment the text is edited. Nobody reviewed the new sentence.

A findings block, one finding per entry, exactly four pipe-separated fields:

    ```review-findings
    FINDING  | dangling-ref      | 41,42 | "the standoff" has no beat in the draft
    RESOLVED | dangling-ref      | 41,42 | the clause was cut in the 2026-06-14 pass
    ANSWERED | ambiguous-pronoun | 77    | the antecedent is fixed by the prior clause, which names only one man
    FINDING  | invented-claim    | -     | the narrator claims a repetition no line supports
    ```

    <STATUS> | <kind> | <line ids, comma separated, or -> | <text>

STATUS is FINDING, RESOLVED or ANSWERED. `kind` is a short slug. A FINDING is
closed by a LATER RESOLVED or ANSWERED with the same `kind` whose line ids
overlap. An ANSWERED must carry a real argument - see
REVIEW_ANSWER_MIN_WORDS - because "answered" with no reason is the same thing
as no review at all.

Prose INSIDE a fenced block is a MALFORMED entry, never a skipped one. This
mirrors pipeline/reviewed.py, which refuses what it cannot read in its own
fence. A parser that silently skips the entries it does not understand is
precisely how this class of defect survives: the reviewer writes four findings
in a shape the parser does not know, the parser reports zero findings, and the
gate goes green on a draft nobody fixed.

WHAT WAS TRIED AND REJECTED
---------------------------
- mtime staleness ("is cold_read.md newer than draft.json?"). Rejected: it is
  true for the whole file after any edit anywhere, so it fires on a typo fix in
  line 3 and stays silent when line 41 is rewritten and the artifact is then
  touched by an unrelated save. Content signatures answer the question actually
  being asked, which is "was THIS sentence reviewed".
- a `#` comment carve-out inside the fences, as pipeline/reviewed.py allows.
  Rejected here: a cold reader writing its prose observations as `# the
  standoff has no beat` would have them silently dropped, which is the exact
  failure this module exists to prevent. Blank lines are the only thing skipped.
- text-rule detectors for the three defects themselves (a pronoun-antecedent
  counter, a "whole film" phrase matcher). Rejected as a REPLACEMENT for the
  artifacts: they are worth having separately, but any one of them going green
  would read as "the draft was reviewed", and none of them read the draft front
  to back. They are a different claim.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import config

# Same fence style as pipeline/reviewed.py, so the two artifact formats in this
# repo are read the same way.
_SIG_BLOCK = re.compile(r"```review-signatures[ \t]*\r?\n(.*?)```", re.S)
_FIND_BLOCK = re.compile(r"```review-findings[ \t]*\r?\n(.*?)```", re.S)
_SIG8 = re.compile(r"^[0-9a-f]{8}$")
_STATUSES = ("FINDING", "RESOLVED", "ANSWERED")

# (filename, gate name, config flag). Both artifacts live in the PROJECT dir,
# next to the draft they describe, so the review travels with the project
# instead of sitting in a docs tree that gets copied forward by accident.
ARTIFACTS = (
    ("cold_read.md", "COLD-READ", "REVIEW_REQUIRE_COLD_READ"),
    ("review.md", "REVIEWER", "REVIEW_REQUIRE_REVIEWER"),
)


# ---- signatures ---------------------------------------------------------- #

def line_signature(text: str) -> str:
    """sha1 of the whitespace-normalised, lowercased text, 8 hex chars.

    Byte-for-byte the normalisation pipeline/draft.py `exception_key` uses, and
    for the same reason: a review must survive a reflow or a capitalisation fix
    (nothing was reviewed differently) and must NOT survive a word change
    (nobody reviewed the new sentence). Reusing the exact rule rather than
    inventing a second one means the two staleness mechanisms in this repo can
    never disagree about whether a line changed.
    """
    norm = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:8]


def _norm_id(raw) -> str:
    """A line id as a comparable string.

    Draft ids are ints; a reviewer writes "41", "L41" or "041". All three mean
    the same line, and refusing two of them would train reviewers to fight the
    parser instead of reading the draft. Anything non-numeric is kept as a
    lowercased token so a non-standard id is still matchable rather than lost.
    """
    s = str(raw if raw is not None else "").strip()
    s = s[1:] if s[:1] in ("L", "l") and s[1:].isdigit() else s
    return str(int(s)) if s.isdigit() else s.lower()


def _scan_draft(draft) -> tuple[dict, int]:
    """({line_id: sig} for narrated lines, count of unusable line records).

    The skip count is RETURNED rather than swallowed: a draft with 10 lines
    this function could not read is a draft whose coverage denominator is
    wrong, and the caller has to be able to say so.
    """
    sigs: dict = {}
    skipped = 0
    lines = (draft or {}).get("lines") if isinstance(draft, dict) else None
    if not isinstance(lines, list):
        return sigs, skipped
    for ln in lines:
        if not isinstance(ln, dict):
            skipped += 1
            continue
        if ln.get("id") is None:
            skipped += 1
            continue
        text = str(ln.get("narration") or "").strip()
        if not text:
            continue                      # film audio / hold-only unit
        sigs[_norm_id(ln.get("id"))] = line_signature(text)
    return sigs, skipped


def draft_signatures(draft: dict) -> dict:
    """{line_id: sig} for the draft's NARRATED lines only.

    A line with no narration is not something a reader can review, so it is not
    in the denominator - otherwise a draft carrying film-audio units could
    never reach the coverage bar no matter how completely it was read.
    """
    return _scan_draft(draft)[0]


# ---- the artifact parser ------------------------------------------------- #

def parse_artifact(path: Path) -> dict:
    """{"signatures": {...}, "findings": [...], "errors": [...]}.

    `findings` entries are
        {"status", "kind", "ids": [...], "text", "raw", "at"}
    in file order; `at` is the line number inside the artifact, so a malformed
    entry can be pointed at rather than described.

    Never raises. An unreadable or absent file comes back as an error string,
    because a parser that throws here would take the whole gate with it and the
    report would say nothing at all.
    """
    out: dict = {"signatures": {}, "findings": [], "errors": []}
    p = Path(path)
    try:
        txt = p.read_text(encoding="utf-8-sig", errors="replace")
    except FileNotFoundError:
        out["errors"].append(f"{p.name} does not exist")
        return out
    except Exception as e:
        out["errors"].append(f"{p.name} is unreadable: {type(e).__name__}: {e}")
        return out

    # Binary junk survives errors="replace" as U+FFFD. Saying so beats letting
    # it fail the "no signature block" check, which would send the reader
    # looking for a missing fence in a file that is not text.
    if "\ufffd" in txt:
        out["errors"].append(
            f"{p.name} is not valid UTF-8 text (replacement characters "
            f"present); it cannot be read as a review artifact")

    m = _SIG_BLOCK.search(txt)
    if m:
        base = txt[:m.start(1)].count("\n") + 1
        for i, raw in enumerate(m.group(1).splitlines()):
            entry = raw.strip()
            if not entry:
                continue
            at = base + i
            parts = entry.split()
            if len(parts) != 2:
                out["errors"].append(
                    f"{p.name} line {at}: a review-signatures entry is "
                    f"'<line_id> <sig8>', got {len(parts)} field(s): "
                    f"{entry[:60]!r}")
                continue
            lid, sig = _norm_id(parts[0]), parts[1].strip().lower()
            if not _SIG8.match(sig):
                out["errors"].append(
                    f"{p.name} line {at}: {sig[:20]!r} is not an 8-character "
                    f"hex signature (line id {lid})")
                continue
            out["signatures"][lid] = sig

    m = _FIND_BLOCK.search(txt)
    if m:
        base = txt[:m.start(1)].count("\n") + 1
        for i, raw in enumerate(m.group(1).splitlines()):
            entry = raw.strip()
            if not entry:
                continue
            at = base + i
            parts = [f.strip() for f in entry.split("|")]
            if len(parts) < 4:
                out["errors"].append(
                    f"{p.name} line {at}: a review-findings entry is "
                    f"'<STATUS> | <kind> | <ids or -> | <text>', got "
                    f"{len(parts)} field(s): {entry[:60]!r}")
                continue
            status = parts[0].upper()
            if status not in _STATUSES:
                out["errors"].append(
                    f"{p.name} line {at}: {parts[0][:20]!r} is not one of "
                    f"{'/'.join(_STATUSES)}: {entry[:60]!r}")
                continue
            ids = [] if parts[2] in ("-", "") else [
                _norm_id(x) for x in parts[2].split(",") if x.strip()]
            out["findings"].append({
                "status": status,
                "kind": parts[1].lower(),
                "ids": ids,
                "text": " | ".join(parts[3:]).strip(),
                "raw": entry,
                "at": at,
            })
    return out


def _closes(finding: dict, res: dict) -> bool:
    """Does `res` (a RESOLVED/ANSWERED) close `finding`?

    Same kind, and overlapping line ids. A finding with NO ids ("-") is a
    whole-draft observation; it is closed by any resolution of the same kind,
    because requiring an id match would make such a finding unclosable and the
    reviewer would learn to stop writing them.
    """
    if finding["kind"] != res["kind"]:
        return False
    if not finding["ids"] or not res["ids"]:
        return True
    return bool(set(finding["ids"]) & set(res["ids"]))


# ---- the gate ------------------------------------------------------------ #

def _cap(ids, n: int) -> str:
    ids = list(ids)
    head = ", ".join(str(x) for x in ids[:n])
    return head + (f" (+{len(ids) - n} more)" if len(ids) > n else "")


def _check_one(name: str, gate: str, path: Path, cur: dict,
               min_cov: float, min_words: int, cap: int,
               accounted_extra: set | None = None) -> dict:
    """One artifact. Returns {"errors","warns","notes","stats"}.

    ccounted_extra carries the line ids closed by a resolved finding in ANY
    review artifact, so an edit the other review accounted for does not read
    as an unreviewed one here.
    """
    E: list = []
    W: list = []
    N: list = []
    S: dict = {"exists": path.exists(), "signed": False, "coverage": None,
               "signed_lines": 0, "narrated_lines": len(cur),
               "changed_ids": [], "unreviewed_ids": [],
               "findings": 0, "resolved": 0, "answered": 0,
               "unresolved": 0, "malformed": 0}

    # 1. MISSING
    if not path.exists():
        E.append(
            f"[{gate}] no {name} in {path.parent.name}. A fresh reader must "
            f"read the draft and record what it found at {path}, and it must "
            f"be an agent that did not write the draft - the defects this "
            f"catches (a referent whose beat was cut, a pronoun with two "
            f"antecedents, a claim about a repetition that never happened) "
            f"are invisible to whoever already knows the intended reading.")
        return {"errors": E, "warns": W, "notes": N, "stats": S}

    art = parse_artifact(path)
    sigs = art["signatures"]
    finds = art["findings"]
    S["signed_lines"] = len(sigs)
    S["findings"] = sum(1 for f in finds if f["status"] == "FINDING")
    S["resolved"] = sum(1 for f in finds if f["status"] == "RESOLVED")
    S["answered"] = sum(1 for f in finds if f["status"] == "ANSWERED")

    # 5. MALFORMED - reported before anything derived from the file, because a
    # file the parser only half understood makes every count below a floor
    # rather than a measurement.
    if art["errors"]:
        S["malformed"] = len(art["errors"])
        E.append(
            f"[{gate}] {len(art['errors'])} malformed entr(ies) in {name}: "
            + "; ".join(art["errors"][:cap])
            + (f" (+{len(art['errors']) - cap} more)"
               if len(art["errors"]) > cap else "")
            + ". These entries were NOT skipped and NOT counted as reviewed - "
              "fix the shape and re-run. Prose belongs outside the fences.")

    # 2. UNSIGNED
    if not sigs:
        E.append(
            f"[{gate}] {name} carries no review-signatures block, or the "
            f"block is empty, so there is no record of WHICH text was read. "
            f"This is treated as STALE, not as missing - the file exists, but "
            f"an unknown answer must not masquerade as a fresh one. Re-run "
            f"the review and paste the review-signatures block that "
            f"tools/cold_read_payload.py prints with the narration.")
        return {"errors": E, "warns": W, "notes": N, "stats": S}
    S["signed"] = True

    # 3. STALE
    if not cur:
        N.append(
            f"[{gate}] the draft has no narrated lines, so {name} coverage "
            f"CANNOT BE MEASURED and the staleness check did not run. The "
            f"count below is not a pass.")
    else:
        changed = sorted(k for k, v in cur.items()
                         if k in sigs and sigs[k] != v)
        unrev = sorted(k for k in cur if k not in sigs)
        # Which changed lines are ACCOUNTED FOR - computed before coverage,
        # because coverage depends on it.
        accounted = set()
        for f in finds:
            if str(f.get("status") or "").upper() in ("RESOLVED", "ANSWERED"):
                for i in (f.get("ids") or []):
                    accounted.add(str(i))
        accounted |= set(accounted_extra or ())

        # A LINE EDITED BECAUSE THE REVIEW SAID SO IS STILL COVERED BY IT.
        #
        # The first version counted every changed line against coverage, and
        # using the gate for real immediately showed why that is wrong: a cold
        # read produced 128 findings, fixing them edited 20 of 105 lines, and
        # coverage fell to 81% against a 95% bar. The more thorough the
        # review, the staler it made itself - so the gate punished exactly the
        # behaviour it exists to produce, and the only way to pass was to
        # review carefully and then fix nothing.
        #
        # The purpose of coverage is "this review describes the current text".
        # A line the review named, and whose fix the review records, IS
        # described by it. A line that changed and is named nowhere is not,
        # and that is the separate error below - which is the check that
        # actually catches an unreviewed edit, at any coverage.
        accounted_changed = [k for k in changed if str(k) in accounted]
        covered = len(cur) - len(changed) - len(unrev) + len(accounted_changed)
        cov = covered / float(len(cur))
        S["coverage"] = cov
        S["changed_ids"] = changed
        S["unreviewed_ids"] = unrev
        S["accounted_changed_ids"] = accounted_changed
        # A PERCENTAGE BAR ALONE IS NOT ENOUGH, and the arithmetic says so:
        # at 95% on a 111-line draft, five lines can be rewritten after the
        # review and coverage still reads 95.5% - a pass. But an edit made IN
        # RESPONSE to a finding is legitimate, and re-reviewing after every
        # such edit would never terminate. So the two cases are separated:
        # a line that changed AND is named in a finding that was resolved or
        # answered is accounted for; a line that changed and is named nowhere
        # is an unreviewed edit, and one of those is enough.
        silent = [k for k in changed if str(k) not in accounted]
        S["silent_edits"] = silent
        if silent:
            E.append(
                f"[{gate}] {len(silent)} line(s) were edited after {name} was "
                f"written and are named in no resolved finding: "
                f"{_cap(silent, cap)}. The review describes text that is no "
                f"longer in the draft. Either re-run the review on the "
                f"current text, or record the change as a finding it "
                f"resolved.")
        if cov < min_cov:
            bits = []
            if changed:
                bits.append(f"{len(changed)} line(s) have been EDITED since "
                            f"the review: {_cap(changed, cap)}")
            if unrev:
                bits.append(f"{len(unrev)} narrated line(s) were never "
                            f"signed: {_cap(unrev, cap)}")
            E.append(
                f"[{gate}] {name} covers {cov:.0%} of the draft's "
                f"{len(cur)} narrated line(s); the bar is {min_cov:.0%}. "
                + "; ".join(bits)
                + f". A review of text that has since been rewritten reads as "
                  f"a pass while covering nothing, which is worse than no "
                  f"review at all. Re-run the review on the CURRENT text "
                  f"(tools/cold_read_payload.py) and replace {name}.")

    # 4. UNRESOLVED findings, and ANSWERED with no argument
    thin: list = []
    valid_res: list = []
    for f in finds:
        if f["status"] == "FINDING":
            continue
        if f["status"] == "ANSWERED" and len(f["text"].split()) < min_words:
            thin.append(f)
            continue              # a reasonless ANSWERED closes nothing
        valid_res.append(f)
    if thin:
        E.append(
            f"[{gate}] {len(thin)} ANSWERED entr(ies) in {name} carry fewer "
            f"than {min_words} words of reason: "
            + "; ".join(f"line {t['at']} ({t['kind']}) {t['text'][:40]!r}"
                        for t in thin[:cap])
            + ". 'ANSWERED' means the reviewer was wrong and here is why - it "
              "needs the argument, not the verdict. These entries do NOT "
              "close their findings; either argue the case or fix the line.")

    unresolved = []
    for idx, f in enumerate(finds):
        if f["status"] != "FINDING":
            continue
        if not any(_closes(f, r) for r in valid_res if r["at"] > f["at"]):
            unresolved.append(f)
    S["unresolved"] = len(unresolved)
    if unresolved:
        ids = []
        for f in unresolved:
            ids.append(f"{f['kind']}@" + (",".join(f["ids"]) or "-"))
        E.append(
            f"[{gate}] {len(unresolved)} of {S['findings']} finding(s) in "
            f"{name} are UNRESOLVED: " + _cap(ids, cap)
            + f". Each needs a LATER line with the same kind and an "
              f"overlapping line id, either 'RESOLVED | <kind> | <ids> | what "
              f"changed' or 'ANSWERED | <kind> | <ids> | why the reading is "
              f"wrong' with at least {min_words} words. An open finding is a "
              f"defect somebody read and nobody acted on.")

    # Symmetric check, the one pipeline/reviewed.py `stale` exists for: a
    # resolution that closes nothing is either a typo in the kind or a note
    # left behind after the finding moved, and the next finding of that kind
    # would be covered by it. A warning, not an error: it does not hide a
    # defect by itself.
    orphan = [r for r in valid_res
              if not any(_closes(f, r) and f["at"] < r["at"]
                         for f in finds if f["status"] == "FINDING")]
    if orphan:
        W.append(
            f"[{gate}] {len(orphan)} RESOLVED/ANSWERED entr(ies) in {name} "
            f"close no earlier FINDING: "
            + _cap([f"line {o['at']} ({o['kind']})" for o in orphan], cap)
            + ". Check the kind slug and the ids - a resolution left behind "
              "after its finding moved will silently cover the next one.")

    # 6. a passing review is VISIBLE
    if not E:
        cov_txt = ("coverage not measurable" if S["coverage"] is None
                   else f"coverage {S['coverage']:.0%} of {len(cur)} "
                        f"narrated line(s)")
        N.append(
            f"[{gate}] {name} is present and current: {cov_txt}, "
            f"{S['signed_lines']} line(s) signed, {S['findings']} finding(s) "
            f"- {S['resolved']} resolved, {S['answered']} answered.")
    return {"errors": E, "warns": W, "notes": N, "stats": S}


def review_report(draft: dict, pdir: Path) -> dict:
    """COLD-READ and REVIEWER: the review happened, is current, and is closed.

    {"errors", "warns", "notes", "stats"} - the pipeline/pacing_gates.py
    convention. NEVER raises: anything this function cannot measure becomes a
    stated "cannot measure" in `errors`, because a gate that dies on malformed
    input hands the caller an empty report, and an empty report is read as a
    pass by every caller in this repo.
    """
    errors: list = []
    warns: list = []
    notes: list = []
    stats: dict = {}

    min_cov = float(getattr(config, "REVIEW_SIGNATURE_MIN_COVERAGE", 0.95))
    min_words = int(getattr(config, "REVIEW_ANSWER_MIN_WORDS", 8))
    cap = int(getattr(config, "REVIEW_MAX_IDS_IN_MESSAGE", 8))

    try:
        pdir = Path(pdir)
    except Exception:
        return {"errors": ["[COLD-READ] the project directory could not be "
                           "resolved, so the review artifacts CANNOT BE "
                           "MEASURED. This is not a pass."],
                "warns": [], "notes": [], "stats": {}}

    cur, skipped = _scan_draft(draft)
    stats["narrated_lines"] = len(cur)
    stats["unreadable_lines"] = skipped
    if not isinstance(draft, dict) or not isinstance(draft.get("lines"), list):
        errors.append(
            "[COLD-READ] the draft has no readable `lines` list, so review "
            "coverage CANNOT BE MEASURED. Nothing here is a pass; fix the "
            "draft and re-run.")
    if skipped:
        errors.append(
            f"[COLD-READ] {skipped} line record(s) in the draft are not "
            f"usable (not an object, or carrying no id), so they are outside "
            f"the coverage denominator and their review status CANNOT BE "
            f"MEASURED. Coverage below is a ceiling, not a measurement.")

    # AN EDIT REVIEWED BY THE *OTHER* ARTIFACT IS STILL A REVIEWED EDIT.
    #
    # Each artifact used to be judged in complete isolation, and running the
    # real sequence showed why that is wrong: the cold read is written first,
    # then an independent reviewer reads the draft and files its own findings,
    # then those get fixed. Every line the SECOND review caused to change was
    # unaccounted for in the FIRST review's ledger - so the cold read went
    # stale precisely because a later, more independent pass did its job.
    #
    # The question the check exists to answer is "was this edit reviewed by
    # somebody?", not "was it reviewed by this particular document". So the
    # accounted set is the UNION across artifacts. What this does NOT relax:
    # an edit named in no resolved finding anywhere is still an error, which
    # is the case that catches an unreviewed change.
    accounted_all: set = set()
    for _n, _g, _f in ARTIFACTS:
        if not getattr(config, _f, True):
            continue
        try:
            _a = parse_artifact(pdir / _n)
        except Exception:
            continue
        for _fi in (_a.get("findings") or []):
            if str(_fi.get("status") or "").upper() in ("RESOLVED",
                                                        "ANSWERED"):
                for _i in (_fi.get("ids") or []):
                    accounted_all.add(str(_i))

    for name, gate, flag in ARTIFACTS:
        key = gate.lower().replace("-", "_")
        if not getattr(config, flag, True):
            notes.append(
                f"[{gate}] config.{flag} is off, so {name} was not required "
                f"and the review was NOT checked. Nothing about the draft's "
                f"readability was verified by this run.")
            stats[key] = {"required": False}
            continue
        try:
            r = _check_one(name, gate, pdir / name, cur,
                           min_cov, min_words, cap,
                           accounted_extra=accounted_all)
        except Exception as e:                              # pragma: no cover
            # The house rule: degrade to a stated "cannot measure", never to a
            # silent pass. The type and message go in so the failure is
            # fixable rather than merely reported.
            errors.append(
                f"[{gate}] {name} CANNOT BE MEASURED: "
                f"{type(e).__name__}: {e}. Treat this as a missing review, "
                f"not as a pass.")
            stats[key] = {"required": True, "error": f"{type(e).__name__}"}
            continue
        errors.extend(r["errors"])
        warns.extend(r["warns"])
        notes.extend(r["notes"])
        st = r["stats"]
        st["required"] = True
        stats[key] = st

    return {"errors": errors, "warns": warns, "notes": notes, "stats": stats}
