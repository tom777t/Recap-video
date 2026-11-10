# -*- coding: utf-8 -*-
"""variation.py - cross-video gates: what the viewer and the bot compare.

WHY. All 117 other gates are PER-VIDEO. What YouTube's inauthentic-content
review compares is "minimal variation across videos" - cadence, openings,
titles, identical files. docs/DESIGN_human_variation.md (v2, approved)
is this module's contract:

    - measure only what a VIEWER sees: the cold open's words, the intro
      style, the title's shape, the final file's hash. Role ratios are
      NOT viewer-visible and are deliberately not gated (STRUCTURE-ECHO
      prints a cosine as a NUMBER for the template-variation ticket -
      it is a measurement, not a check);
    - brand lines are exempt: the channel greeting and the CTA may
      repeat (real channels have a familiar greeting); the CONTENT
      around them may not;
    - a missing history means NOT RUN, never a pass;
    - warn-only. The report prints at the WATCH VIDEO stop; nothing
      here blocks a ship.

NO FILM-SPECIFIC CONTENT LIVES HERE.

PURE: snapshot() reads one project's artifacts, compare() takes parsed
snapshots and returns findings. The history file's shape:

    channel/history.json  {project: {snapshot...}, ...}  keyed, newest
                          wins on re-record; shipped_at orders it
    channel/claims.jsonl  one line per shipped video, append-only
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import config

HISTORY = Path(config.ROOT) / "channel" / "history.json"
CLAIMS = Path(config.ROOT) / "channel" / "claims.jsonl"

_STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for",
         "he", "she", "they", "it", "his", "her", "their", "its", "is",
         "are", "was", "were", "be", "been", "who", "that", "this",
         "with", "from", "at", "by", "but", "can", "cannot", "only",
         "will", "would", "one", "more", "into", "out", "up", "as",
         "so", "no", "not", "and", "for", "you", "your", "i", "we"}
_WORD = re.compile(r"[a-z']+")

# the opening-craft levers (pipeline.opening.LEVERS) - recorded so the
# anti-sameness check can see when five videos in a row opened the same
# way. Kept as a copy so this module stays import-light.
LEVERS = ("FEAR", "DESIRE", "THRILL", "AWE")


def _content_words(text: str, n: int) -> list:
    return [w for w in _WORD.findall(str(text or "").lower())
            if w not in _STOP][:n]


def _jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _read(pdir: Path, name: str):
    p = Path(pdir) / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _md5(p: Path) -> str | None:
    p = Path(p)
    if not p.exists():
        return None
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ffprobe_dur(p: Path) -> float:
    import subprocess
    r = subprocess.run(
        [config.ffprobe(), "-v", "error", "-show_entries",
         "format=duration", "-of", "default=nw=1:nk=1", str(p)],
        capture_output=True, text=True)
    try:
        return round(float((r.stdout or "0").strip()), 3)
    except ValueError:
        return 0.0


# --------------------------------------------------------------------------
# the snapshot
# --------------------------------------------------------------------------

def snapshot(project: str) -> dict:
    """One project's viewer-visible facts, from artifacts already on disk.

    The greeting and the CTA are NOT captured (brand - they may repeat).
    `cold_open` is the first OPEN lines' content words; `final_thesis`
    is the outro's first sentence(s) BEFORE the call to action.
    """
    pdir = Path(config.project_dir(project))
    draft = _read(pdir, "draft.json") or {}
    lines = draft.get("lines") or []

    opens = [l for l in lines
             if str(l.get("note") or "").upper() == "OPEN"
             and str(l.get("narration") or "").strip()]
    # the outro's thesis: sentences before the CTA one
    thesis = ""
    for l in lines:
        if l.get("delivery") == "outro":
            sents = re.split(r"(?<=[.!?])\s+", str(l.get("narration") or ""))
            thesis = " ".join(sents[:-1]) if len(sents) > 1 else \
                (sents[0] if sents else "")
            break

    style = None
    sp = pdir / "intro_style.txt"
    if sp.exists():
        style = sp.read_text(encoding="utf-8-sig").strip().lower() or None

    title = str(draft.get("title") or "").strip()
    titles_txt = pdir / "titles.txt"
    final = pdir / "final.mp4"

    return {
        "project": project,
        "title": title,
        "title_shape": {"first_word":
                        (title.split()[0].lower() if title else ""),
                        "word_count": len(title.split())},
        "intro_style": style,
        "cold_open": _content_words(
            " ".join(str(l.get("narration") or "") for l in opens), 12),
        "final_thesis": _content_words(thesis, 12),
        "open_mode": draft.get("open_mode"),
        "lever": draft.get("lever"),
        "titles_txt_md5": _md5(titles_txt),
        "final_hash": ({"md5": _md5(final),
                        "bytes": (final.stat().st_size
                                  if final.exists() else 0),
                        "duration_sec": (_ffprobe_dur(final)
                                         if final.exists() else 0.0)}
                       if final.exists() else None),
    }


# --------------------------------------------------------------------------
# the comparison
# --------------------------------------------------------------------------

def _ordered(history: dict) -> list:
    def key(item):
        s = item[1] or {}
        return str(s.get("shipped_at") or "")
    return [v for _k, v in sorted(history.items(), key=key)]


def compare(history: dict, current: dict) -> list:
    """[HUMAN-VAR-*] findings for one candidate video against the shipped
    history. History empty -> every cross-video check says NOT RUN."""
    out: list = []
    prev = _ordered(history)
    if not prev:
        out.append("[HUMAN-VAR] NOT RUN - channel/history.json is empty; "
                   "nothing to compare against. This is not a pass.")
        return out

    last = prev[-1]

    # ---- TITLE-FORMULA (warn): the layer AFTER package.py was fixed ----
    same_titles_txt = [p["project"] for p in prev
                       if current.get("titles_txt_md5")
                       and p.get("titles_txt_md5") == current.get(
                           "titles_txt_md5")]
    if same_titles_txt:
        out.append(f"[TITLE-FORMULA] titles.txt is byte-identical to "
                    f"{same_titles_txt[0]} - a title bank came back. "
                    f"Titles are written per film now; a shared bank is "
                    f"the formula the policy names.")
    runs = [current.get("title_shape", {}).get("first_word")] + \
        [p.get("title_shape", {}).get("first_word") for p in reversed(prev)]
    pronoun = {"he", "she", "they", "this", "it"}
    if all(w in pronoun for w in runs[:3] if w):
        out.append(f"[TITLE-FORMULA] three titles in a row open on "
                   f"{'/'.join(sorted(set(runs[:3])))} - the classic recap "
                   f"formula. Break the pattern on the next one.")

    # ---- CROSSPOST-IDENTICAL (the one error; still print-only here) ----
    if current.get("final_hash") and current["final_hash"].get("md5"):
        twin = [p["project"] for p in prev
                if (p.get("final_hash") or {}).get("md5")
                == current["final_hash"]["md5"]]
        if twin:
            out.append(f"[CROSSPOST-IDENTICAL] final.mp4's md5 matches "
                       f"{twin[0]} - the same file is not two videos. "
                       f"Re-render or re-title before uploading.")
    else:
        out.append("[CROSSPOST-IDENTICAL] NOT RUN - no final.mp4 to hash.")

    # ---- STRUCTURE-ECHO (report): a number, not a check ------------------
    cur_roles = current.get("role_share")
    if cur_roles:
        import math
        for p in prev[-3:]:
            pr = p.get("role_share")
            if not pr:
                continue
            dot = sum(cur_roles.get(k, 0.0) * pr.get(k, 0.0)
                      for k in cur_roles)
            n1 = math.sqrt(sum(v * v for v in cur_roles.values()))
            n2 = math.sqrt(sum(v * v for v in pr.values()))
            if n1 and n2:
                out.append(f"[STRUCTURE-ECHO] role-share cosine vs "
                           f"{p['project']}: {dot / (n1 * n2):.3f} "
                           f"(measurement for the template-variation "
                           f"ticket, not a gate)")

    return out


# --------------------------------------------------------------------------
# the store
# --------------------------------------------------------------------------

def load_history() -> dict:
    if not HISTORY.exists():
        return {}
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def record(project: str, lane: str | None = None, claim_status: str | None = None,
           claimant: str | None = None, when: str | None = None) -> dict:
    """The SHIP action: snapshot + history write + claims ledger line.

    Deliberately one command (tools/ship.py): uploading is a deliberate
    act and the claim outcome is recorded at the same moment, so the
    history is always complete (the advisory's claim-rate-per-lane
    metric). Re-recording a project overwrites its own entry.
    """
    from datetime import datetime
    snap = snapshot(project)
    snap["shipped_at"] = when or datetime.now().isoformat(
        timespec="seconds")
    if lane:
        snap["lane"] = lane
    hist = load_history()
    hist[project] = snap
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(hist, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    CLAIMS.parent.mkdir(parents=True, exist_ok=True)
    with open(CLAIMS, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "shipped_at": snap["shipped_at"], "project": project,
            "lane": lane or "", "title": snap.get("title", ""),
            "claim_status": claim_status or "unknown",
            "claimant": claimant or "",
        }, ensure_ascii=False) + "\n")
    return snap
