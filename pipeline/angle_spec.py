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
        anchors.append({
            "beats": bs,
            "kind": parts[1].strip("*_ ").lower(),
            "why": (parts[2] if len(parts) > 2 else "").strip(),
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
        promises.append({"clause": m.group("q").strip(),
                         "beats": beat_ids(rest),
                         "note": rest.split("|")[-1].strip()
                         if "|" in rest else ""})

    return {"anchors": anchors, "persona": persona, "promises": promises,
            "raw": text}


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
    if missing:
        raise AngleSpecError(
            "angle.md is missing section(s) the draft gates depend on:\n  "
            + "\n  ".join(missing))
    return spec
