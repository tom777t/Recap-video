# -*- coding: utf-8 -*-
"""fetch_plot_ref.py - a second plot reference for a film (Plot Explained /
What's After the Movie), READ ONLY, saved next to the project.

What it is for (owner, 17 Nov): a cross-check when the plan's story spine is
built. If a reference names an event the plan never mentions ("Jakande takes
God's Eye"), the plan has dropped a story step. The text is NEVER copied into
the script - it is a checklist, not a source of sentences - and an event only
this reference has is marked [kiem tra] until the transcript or the picture
confirms it. Measured on Furious 7: this source missed the villains' alliance
and the whole LA climax that Wikipedia has, so it is the THIRD source after the
transcript and Wikipedia, never the first.

The key lives ONLY in the environment variable PLOT_API_KEY (Windows: User
scope). This file never prints it, never writes it, and the repo is public -
never put it in config.py or a .env.

    python tools/fetch_plot_ref.py --project doublelife2023
    python tools/fetch_plot_ref.py --project furious72015 --slug furious-7
    python tools/fetch_plot_ref.py --project furious72015 --probe
        (--probe prints the SHAPE of each reply - keys, types, the first words
         of each text - so the format can be checked without a key in chat)

Writes projects/<p>/plot_ref/plotexplained.json (raw replies) and
plotexplained.md (readable) - ONLY when the reply is this film. A title and a
year do not identify a film: on 17 Nov "Double Life" 2023 returned a
Paramount thriller (Sharon, Mark, Larry) instead of the short drama (Natalie
Quinn, Sebastian Klein). So the reply must name at least one character from
the project's names.json; if it names none, it is saved as
plotexplained_REJECTED.* and nothing else is kept. With no names.json the
file is saved marked UNVERIFIED. One film = 1 details call + up to 3 sections
(summary, ending, timeline) = at most 4 requests; the free tier is 100/month.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402

BASE = "https://whatsafterthemovie-main-0565fcb.zuplo.app/v1"
SECTIONS = ("summary", "ending", "timeline")
ENV = "PLOT_API_KEY"
UA = "RecapVidTool/1.0 (personal film-recap pipeline)"
SOURCE = "Plot Explained / What's After the Movie (plotexplained.com)"


class RefError(Exception):
    """One sentence the user can act on; printed, no traceback."""


def api_key() -> str:
    k = os.environ.get(ENV, "").strip()
    if not k and os.name == "nt":
        # a User variable set after this terminal opened is not in os.environ
        # yet; read it where Windows keeps it rather than asking for a restart
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                k = str(winreg.QueryValueEx(h, ENV)[0]).strip()
        except OSError:
            k = ""
    if not k:
        raise RefError(f"no {ENV} in the environment. In PowerShell: "
                       f"[Environment]::SetEnvironmentVariable(\"{ENV}\", "
                       f"\"<key>\", \"User\")  - then run this again.")
    return k


def slugify(title: str) -> str:
    t = title.lower().replace("&", "and")
    t = re.sub(r"['’]", "", t)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _get(url: str, key: str, opener=None) -> tuple[int, object]:
    """(status, parsed JSON or text). Never raises on an HTTP status."""
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {key}", "Accept": "application/json",
        "User-Agent": UA})
    op = opener or urllib.request.urlopen
    try:
        with op(req, timeout=30) as r:
            status, body = getattr(r, "status", 200), r.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read() or b""
    except urllib.error.URLError as e:
        raise RefError(f"could not reach the plot API: {e.reason}") from None
    text = body.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text


def _why(status: int, body) -> str:
    if status == 401 or status == 403:
        return ("the key was refused (HTTP %d) - check that PLOT_API_KEY is "
                "the key from your plotexplained.com account" % status)
    if status == 429:
        return "rate limit or monthly quota reached (HTTP 429) - try later"
    msg = body.get("message") or body.get("error") if isinstance(body, dict) \
        else str(body)[:120]
    return f"HTTP {status}: {msg}"


def shape(obj, depth: int = 0, key: str = "") -> list:
    """The structure of a reply with text cut to its first words - safe to
    paste into a chat (no key, no full text)."""
    pad = "  " * depth
    out = []
    if isinstance(obj, dict):
        out.append(f"{pad}{key}{{}} keys: {', '.join(list(obj)[:40])}")
        for k, v in list(obj.items())[:40]:
            out += shape(v, depth + 1, f"{k}: ")
    elif isinstance(obj, list):
        out.append(f"{pad}{key}[] {len(obj)} item(s)")
        if obj:
            out += shape(obj[0], depth + 1, "[0]: ")
    elif isinstance(obj, str):
        w = obj.split()
        out.append(f"{pad}{key}str {len(w)} words: "
                   f"\"{' '.join(w[:8])}{' ...' if len(w) > 8 else ''}\"")
    else:
        out.append(f"{pad}{key}{type(obj).__name__}: {obj!r}"[:120])
    return out


def texts(obj) -> list:
    """Readable text from a reply of unknown schema, in document order:
    every string of 6+ words, with a timeline entry's time / title kept on
    the same line as its text."""
    out = []
    if isinstance(obj, dict):
        head = [str(obj[k]) for k in ("time", "timestamp", "minute", "order",
                                     "title", "heading", "name", "event")
                if isinstance(obj.get(k), (str, int, float))
                and len(str(obj[k]).split()) < 12]
        body = []
        for k, v in obj.items():
            if isinstance(v, str) and len(v.split()) >= 6:
                body.append(v.strip())
            elif isinstance(v, (dict, list)):
                body += texts(v)
        if head and body:
            body[0] = f"[{' | '.join(head)}] {body[0]}"
        out += body
    elif isinstance(obj, list):
        for v in obj:
            out += texts(v)
    elif isinstance(obj, str) and len(obj.split()) >= 6:
        out.append(obj.strip())
    return out


def fetch(title: str, year, slug: str | None, key: str, opener=None,
          probe: bool = False) -> dict:
    tried, det, used = [], None, None
    cands = [slug] if slug else [slugify(title)] + (
        [f"{slugify(title)}-{year}"] if year else [])
    calls = 0
    for s in cands:
        st, body = _get(f"{BASE}/movies/{urllib.parse.quote(s)}", key, opener)
        calls += 1
        tried.append(f"{s} -> {st}")
        if st in (401, 403, 429):
            raise RefError(_why(st, body))
        if st == 200:
            det, used = body, s
            break
    if det is None:
        raise RefError("film not found under " + ", ".join(tried) + ". Open "
                       "the film on plotexplained.com and pass the last part "
                       "of its URL: --slug <that>")
    if probe:
        print(f"== details ({used})")
        print("\n".join(shape(det)))
    data = det.get("data", det) if isinstance(det, dict) else {}
    avail = data.get("available_content") if isinstance(data, dict) else None
    want = [s for s in SECTIONS if avail is None or s in avail]
    out = {"source": SOURCE, "slug": used, "fetched": date.today().isoformat(),
           "details": det, "sections": {}, "missing": []}
    for sec in want:
        st, body = _get(f"{BASE}/movies/{urllib.parse.quote(used)}/content/"
                        f"{sec}", key, opener)
        calls += 1
        if st in (401, 403, 429):
            raise RefError(_why(st, body))
        if st != 200:
            out["missing"].append(f"{sec}: {_why(st, body)}")
            continue
        out["sections"][sec] = body
        if probe:
            print(f"== {sec}")
            print("\n".join(shape(body)))
    out["missing"] += [f"{s}: not offered for this film" for s in SECTIONS
                       if s not in want]
    out["requests"] = calls
    return out


_GENERIC = {"mother", "father", "brother", "sister", "wife", "husband",
            "son", "daughter", "the", "man", "woman", "girl", "boy", "uncle",
            "aunt", "friend", "boss", "doctor", "officer", "detective", "mr",
            "mrs", "ms", "dr", "young", "old", "agent"}


def name_tokens(pdir: Path) -> list:
    """Character names from names.json, as whole names and as single names
    of 4+ letters that are not role words ("Natalie's mother" -> Natalie)."""
    try:
        nj = json.loads((pdir / "names.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    chars = [str(n.get("character") or "") for n in nj.get("names") or []]
    chars += list((nj.get("aliases") or {}).keys())
    toks = set()
    for c in chars:
        c = re.sub(r"['’]s\b", "", c).strip()
        if not c:
            continue
        toks.add(c)
        for w in re.findall(r"[A-Za-z][A-Za-z.'-]+", c):
            if len(w) >= 4 and w.lower() not in _GENERIC:
                toks.add(w)
    return sorted(toks)


def identity(ref: dict, pdir: Path) -> tuple[str, list]:
    """("ok" | "mismatch" | "unverified", the character names it found)."""
    toks = name_tokens(pdir)
    if not toks:
        return "unverified", []
    pool = " ".join(texts(ref.get("details"))
                    + [x for s in ref["sections"].values() for x in texts(s)])
    hit = [t for t in toks if re.search(r"\b" + re.escape(t) + r"\b", pool)]
    return ("ok" if hit else "mismatch"), hit


def to_md(ref: dict, title: str) -> str:
    lines = [f"# {title} - plot reference (cross-check only)", "",
             f"Source: {ref['source']}, /{ref['slug']}, fetched "
             f"{ref['fetched']}. Third source after the transcript and "
             f"Wikipedia. Never copy its wording into the script; an event "
             f"only this source has is [kiem tra] until the film confirms it.",
             ""]
    for sec in SECTIONS:
        if sec not in ref["sections"]:
            continue
        lines += [f"## {sec}", ""]
        t = texts(ref["sections"][sec])
        lines += ([f"- {x}" for x in t] if sec == "timeline" else
                  [x + "\n" for x in t]) or ["(no text in the reply)"]
        lines.append("")
    if ref["missing"]:
        lines += ["## not fetched", ""] + [f"- {m}" for m in ref["missing"]]
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None, opener=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--slug")
    ap.add_argument("--title")
    ap.add_argument("--year")
    ap.add_argument("--probe", action="store_true")
    a = ap.parse_args(argv)
    pdir = Path(config.project_dir(a.project))
    facts = {}
    try:
        facts = json.loads((pdir / "film_facts.json").read_text(
            encoding="utf-8-sig"))
    except (OSError, ValueError):
        pass
    title = a.title or facts.get("title")
    year = a.year or facts.get("year")
    if not title and not a.slug:
        print(f"fetch_plot_ref: no title - film_facts.json is missing; pass "
              f"--title \"...\" --year ... or --slug ...")
        return 2
    try:
        ref = fetch(title or a.slug, year, a.slug, api_key(), opener, a.probe)
    except RefError as e:
        print(f"fetch_plot_ref: {e}")
        return 2
    state, hit = identity(ref, pdir)
    ref["identity"] = {"state": state, "names_found": hit}
    det = ref["details"].get("data", ref["details"]) \
        if isinstance(ref["details"], dict) else {}
    desc = " ".join(str(det.get("description") or "").split()[:14])
    od = pdir / "plot_ref"
    od.mkdir(parents=True, exist_ok=True)
    md = to_md(ref, title or a.slug)
    if state == "mismatch":
        # never leave a wrong film where the plan would read it
        for old in ("plotexplained.json", "plotexplained.md"):
            try:
                (od / old).unlink()
            except OSError:
                pass
        (od / "plotexplained_REJECTED.json").write_text(
            json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")
        (od / "plotexplained_REJECTED.md").write_text(
            "# REJECTED - a different film with the same title\n\n" + md,
            encoding="utf-8")
        print(f"fetch_plot_ref: /{ref['slug']} is NOT this film - its text "
              f"names none of the characters in names.json. It says: "
              f"\"{desc} ...\". Saved as plot_ref/plotexplained_REJECTED.md "
              f"for reference only. If plotexplained.com has the right film "
              f"under another URL, run again with --slug <that>.")
        return 3
    if state == "unverified":
        md = ("> UNVERIFIED: no names.json to check that this is the right "
              "film. Read the first paragraph before using it.\n\n" + md)
    (od / "plotexplained.json").write_text(
        json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")
    (od / "plotexplained.md").write_text(md, encoding="utf-8")
    words = sum(len(x.split()) for s in ref["sections"].values()
                for x in texts(s))
    print(f"fetch_plot_ref: {a.project} -> plot_ref/plotexplained.md "
          f"(/{ref['slug']}; sections {', '.join(ref['sections']) or 'none'}; "
          f"{words} words; {ref['requests']} request(s); "
          + (f"names it: {', '.join(hit[:4])}" if state == "ok"
             else "UNVERIFIED - no names.json") + ")")
    for m in ref["missing"]:
        print(f"  not fetched: {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
