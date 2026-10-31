"""The machine-readable parts of angle.md: ANCHORS, PERSONA, HOOK PROMISES.

WHY THESE LIVE IN angle.md
--------------------------
angle.md already decides what the recap is about and how the narrator feels
about each character. What it never said was:

  * which scenes the recap is built to ARRIVE at, so the writer spread its
    attention evenly and 56 of ~80 beats got exactly one line;
  * how the narrator SOUNDS, so only 14 of 109 lines carried any judgment and
    the voice was not recognisable;
  * what the hook PROMISES, so "before he has learned to turn" was paid off by
    a single "Long story short" line.

All three are editorial decisions, so they belong in the editorial document
rather than in code - but they have to be parseable, or no gate can check
them. Hence a fixed heading and a fixed line format, and a parser that FAILS
LOUDLY rather than returning an empty list, because an empty list would make
every gate below it vacuously pass.
"""
from __future__ import annotations

import re
from pathlib import Path


class AngleSpecError(Exception):
    """angle.md is missing a section a gate depends on."""


def _section(text: str, title: str) -> str:
    """The body of a `## TITLE` section, or '' if absent."""
    m = re.search(rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)",
                  text, re.M | re.S)
    return (m.group(1) if m else "").strip()


def beat_ids(s: str) -> list:
    """Every B-number in a string, in order, de-duplicated."""
    out = []
    for m in re.finditer(r"\bB(\d{1,3})\b", s):
        b = f"B{int(m.group(1)):02d}"
        if b not in out:
            out.append(b)
    return out


def load(pdir: Path) -> dict:
    """Parse angle.md. Returns {anchors, persona, promises, raw}."""
    p = Path(pdir) / "angle.md"
    if not p.exists():
        raise AngleSpecError(f"no angle.md in {pdir}")
    text = p.read_text(encoding="utf-8-sig")

    # ---- ANCHORS ------------------------------------------------------- #
    # Format, one per line:
    #   - **B57/B58** | thesis | Han on the footbridge: Tokyo is his Mexico
    body = _section(text, "ANCHORS")
    anchors = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith(("-", "*")):
            continue
        parts = [x.strip() for x in line.lstrip("-* ").split("|")]
        if len(parts) < 2:
            continue
        bs = beat_ids(parts[0])
        if not bs:
            continue
        # `evidence: "..."` - a VERBATIM quote from the beat map's own `what`
        # text for one of the named beats. Required because the angle's claim
        # about a beat used to be the only thing any gate read, and one
        # mapping pointed at three beats of which two did not deliver it.
        ev = ""
        for seg in parts[1:]:
            m = re.search(r'evidence\s*:\s*["\u201c](?P<q>[^"\u201d]+)',
                          seg, re.I)
            if m:
                ev = m.group("q").strip()
        anchors.append({
            "beats": bs,
            "kind": parts[1].strip("*_ ").lower(),
            "why": (parts[2] if len(parts) > 2 else "").strip(),
            "evidence": ev,
        })

    # ---- PERSONA ------------------------------------------------------- #
    pbody = _section(text, "NARRATOR PERSONA")
    persona = {"stance": "", "moves": [], "never": []}
    cur = None
    for line in pbody.splitlines():
        t = line.strip()
        low = t.lower()
        if low.startswith("**stance"):
            persona["stance"] = t.split(":", 1)[-1].strip(" *")
            cur = None
            continue
        if low.startswith(("**moves", "**signature")):
            cur = "moves"
            continue
        if low.startswith("**never"):
            cur = "never"
            continue
        if cur and t.startswith(("-", "*")):
            persona[cur].append(t.lstrip("-* ").strip())

    # ---- HOOK PROMISES -------------------------------------------------- #
    # Format:  - "before he has learned to turn" -> B47-B60 | the drift arc
    hbody = _section(text, "HOOK PROMISES")
    promises = []
    for line in hbody.splitlines():
        t = line.strip()
        if not t.startswith(("-", "*")):
            continue
        t = t.lstrip("-* ").strip()
        m = re.match(r'["“](?P<q>[^"”]+)["”]\s*(?:->|→|=>)\s*(?P<rest>.+)$', t)
        if not m:
            continue
        rest = m.group("rest")
        em = re.search(r'evidence\s*:\s*["\u201c](?P<q>[^"\u201d]+)',
                       rest, re.I)
        promises.append({"clause": m.group("q").strip(),
                         "beats": beat_ids(rest.split("evidence")[0]),
                         "evidence": em.group("q").strip() if em else "",
                         "note": rest.split("|")[1].strip()
                         if "|" in rest else ""})

    # ---- beats the angle itself demotes --------------------------------- #
    # A beat cannot be an anchor or a promise target AND be listed as
    # footage-only texture. B60 was both: it is the only beat where Sean is
    # actually taught to drift, and the angle filed it under "compress to a
    # line or hold on footage".
    sel = _section(text, "WHAT THE ANGLE SELECTS")
    demoted: dict = {}
    for raw in sel.splitlines():
        t = raw.strip()
        low = t.lower()
        if not t.startswith(("-", "*")):
            continue
        if ("footage-only" in low or "compress to a line" in low
                or "hold on footage" in low or low.endswith("skip.")
                or "- skip" in low or "— skip" in low):
            for b in beat_ids(t):
                demoted[b] = t.lstrip("-* ").strip()

    # ---- RUNNING BITS (motifs) ------------------------------------------ #
    # The section has existed in angle.md since the angle was written and
    # NOTHING PARSED IT, so the budget for a callback was whatever the writer
    # felt like: one bit's phrase reached twelve lines. The format already in
    # use is kept as-is rather than invented:
    #
    #   1. **"being moved on."** - gloss. **Setup: B13** (...) ->
    #      **Payoff: B91/B101/outro** - payoff gloss.
    #
    # `name` is the quoted phrase, which is what the gate counts in the prose.
    # `outro` and reveal ids (R3) appear alongside beat ids as payoff targets
    # and are kept as written - a payoff can legitimately land in the outro,
    # which is not a beat.
    rbody = _section(text, "RUNNING BITS")
    motifs = []
    for raw in re.split(r"(?m)^(?=\s*\d+\.\s)", rbody):
        t = " ".join(raw.split()).strip()
        if not t or not re.match(r"^\d+\.", t):
            continue
        # Two forms are in use: a quoted catchphrase, and a bare bolded label
        # for a bit that is a NAME rather than a phrase ("Donkey Kong -> Drift
        # King"). The first version of this parser required the quotes and
        # silently dropped the other one - a parser that skips what it cannot
        # match is how a budget ends up unenforced on the exact bit that broke
        # it. Unparseable entries are RETURNED as `unparsed` so the gate can
        # say so out loud.
        nm = re.search(r'["\u201c](?P<q>[^"\u201d]+)["\u201d]', t)
        if nm:
            name = nm.group("q").strip().rstrip(".").strip()
        else:
            bm = re.search(r"\*\*(?P<b>[^*]+)\*\*", t)
            name = (bm.group("b").strip().rstrip(".").strip() if bm else "")
        if not name:
            motifs.append({"name": "", "unparsed": t[:160]})
            continue
        setup = t.split("Setup", 1)[1] if "Setup" in t else ""
        payoff = t.split("Payoff", 1)[1] if "Payoff" in t else ""
        # A name joined by an arrow or slash is two surface forms of one bit
        # and neither appears in the prose as the whole string, so the gate
        # counts the PARTS. Each part is kept whole: a bit is recognised by
        # its wording, and cutting it into single words would match any line
        # containing "car".
        parts = [p.strip(" .\u2014-") for p in
                 re.split(r"->|\u2192|=>|/|\|", name) if p.strip(" .\u2014-")]
        motifs.append({
            "name": name,
            "keywords": parts or [name],
            "setup_beats": beat_ids(setup.split("Payoff")[0]),
            "payoff_beats": beat_ids(payoff),
            "payoff_outro": "outro" in payoff.lower(),
            "text": t,
        })

    return {"anchors": anchors, "persona": persona, "promises": promises,
            "demoted": demoted, "motifs": motifs, "raw": text}


def require(pdir: Path) -> dict:
    """Like load(), but raises when a gate-critical section is missing.

    Deliberately NOT a soft default. An absent ANCHORS section with an empty
    list would make PACING-CONTOUR pass on every draft ever written, which is
    the failure mode this whole series has been about: a gate that is green
    because its input is missing.
    """
    spec = load(pdir)
    missing = []
    if not spec["anchors"]:
        missing.append("## ANCHORS (5-8 lines of `- **B..** | kind | why`)")
    if not spec["persona"].get("stance"):
        missing.append("## NARRATOR PERSONA with a `**Stance:**` line")
    if not spec["persona"].get("moves"):
        missing.append("## NARRATOR PERSONA with `**Signature moves:**`")
    if not spec["promises"]:
        missing.append('## HOOK PROMISES (`- "clause" -> B.. | note`)')
    no_ev = [("/".join(a["beats"])) for a in spec["anchors"]
             if not a.get("evidence")]
    if no_ev:
        missing.append(
            "an `evidence: \"...\"` quote on anchor(s) " + ", ".join(no_ev)
            + " - a verbatim phrase from that beat's own `what` text")
    no_pev = [p["clause"] for p in spec["promises"] if not p.get("evidence")]
    if no_pev:
        missing.append(
            "an `evidence: \"...\"` quote on promise(s) "
            + ", ".join(f'"{c}"' for c in no_pev))
    if missing:
        raise AngleSpecError(
            "angle.md is missing section(s) the draft gates depend on:\n  "
            + "\n  ".join(missing))
    return spec
