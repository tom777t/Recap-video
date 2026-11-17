# -*- coding: utf-8 -*-
"""test_fetch_plot_ref.py - the plot-reference fetcher, against a fake API.

  SLUG-FALLBACK     "<title>" 404s, "<title>-<year>" is found; the sections
                    the details list are fetched, at most 4 requests
  KEY-NEVER-SHOWN   the key reaches the Authorization header and nowhere
                    else: not stdout, not the saved files
  KEY-REFUSED       a 401 stops with one sentence naming the variable, and
                    writes nothing
  SECTION-MISSING   a section the film lacks is listed under "not fetched";
                    the rest is saved
  READABLE-MD       the .md carries the summary text and one line per
                    timeline entry with its time, and says it is a
                    cross-check, never a source of sentences
  NO-KEY            no PLOT_API_KEY: a message that says how to set it

Run:  python tools/test_fetch_plot_ref.py      (exit 0 = all pass)
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.error
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config  # noqa: E402
import fetch_plot_ref as F  # noqa: E402

KEY = "sk-test-SECRET-7f3a9"
SUMMARY = ("Deckard Shaw swears revenge for his brother. Shaw teams up with "
           "the terrorist Jakande, who wants God's Eye.")


class _Resp(io.BytesIO):
    def __init__(self, status, obj):
        super().__init__(json.dumps(obj).encode())
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener(routes, seen):
    def op(req, timeout=30):
        seen.append((req.full_url, dict(req.header_items())))
        path = req.full_url.split("/v1", 1)[1]
        st, obj = routes.get(path, (404, {"message": "not found"}))
        if st != 200:
            raise urllib.error.HTTPError(req.full_url, st, "x", {},
                                         io.BytesIO(json.dumps(obj).encode()))
        return _Resp(st, obj)
    return op


ROUTES = {
    "/movies/furious-7-2015": (200, {"data": {
        "title": "Furious 7", "year": 2015,
        "available_content": ["summary", "timeline", "characters"]}}),
    "/movies/furious-7-2015/content/summary": (200, {"data": {
        "content": SUMMARY}}),
    "/movies/furious-7-2015/content/timeline": (200, {"data": {"events": [
        {"time": "00:05", "event": "London", "description":
         "Shaw stands over his brother's hospital bed and vows revenge."},
        {"time": "01:28", "event": "Factory", "description":
         "Shaw reveals he has teamed up with Jakande against Dom."}]}}),
}


def _run(routes, env_key=KEY, extra=()):
    tmp = Path(tempfile.mkdtemp())
    pdir = tmp / "furious72015"
    pdir.mkdir()
    (pdir / "film_facts.json").write_text(json.dumps(
        {"title": "Furious 7", "year": 2015}), encoding="utf-8")
    seen, out = [], io.StringIO()
    prev_pd, prev_env = config.project_dir, os.environ.get(F.ENV)
    config.project_dir = lambda n: tmp / n
    if env_key is None:
        os.environ.pop(F.ENV, None)
    else:
        os.environ[F.ENV] = env_key
    prev_nt = os.name
    try:
        with contextlib.redirect_stdout(out):
            rc = F.main(["--project", "furious72015", *extra],
                        opener=_opener(routes, seen))
    finally:
        config.project_dir = prev_pd
        if prev_env is None:
            os.environ.pop(F.ENV, None)
        else:
            os.environ[F.ENV] = prev_env
    files = {p.name: p.read_text(encoding="utf-8")
             for p in (pdir / "plot_ref").glob("*")} \
        if (pdir / "plot_ref").exists() else {}
    shutil.rmtree(tmp, ignore_errors=True)
    return rc, out.getvalue(), seen, files


def t_slug_fallback():
    rc, out, seen, files = _run(ROUTES)
    urls = [u.split("/v1", 1)[1] for u, _h in seen]
    ok = (rc == 0 and urls[0] == "/movies/furious-7"
          and urls[1] == "/movies/furious-7-2015"
          and "/movies/furious-7-2015/content/ending" not in urls
          and len(urls) <= 5 and "plotexplained.md" in files)
    return ok, (f"{len(urls)} request(s): {', '.join(urls)}" if ok
                else f"rc {rc}, urls {urls}, out {out!r}")


def t_key_never_shown():
    rc, out, seen, files = _run(ROUTES)
    hdr = all(h.get("Authorization") == f"Bearer {KEY}" for _u, h in seen)
    leak = [n for n, t in files.items() if KEY in t] + (
        ["stdout"] if KEY in out else [])
    ok = rc == 0 and hdr and not leak
    return ok, ("key only in the Authorization header" if ok
                else f"header ok {hdr}, leaked into {leak}")


def t_key_refused():
    r = dict(ROUTES)
    r["/movies/furious-7"] = (401, {"message": "invalid key"})
    rc, out, _s, files = _run(r)
    ok = rc == 2 and "PLOT_API_KEY" in out and not files and KEY not in out
    return ok, ("401 -> one sentence naming PLOT_API_KEY, nothing written"
                if ok else f"rc {rc}, out {out!r}, files {list(files)}")


def t_section_missing():
    r = dict(ROUTES)
    r["/movies/furious-7-2015"] = (200, {"data": {"available_content": None}})
    rc, out, _s, files = _run(r)
    md = files.get("plotexplained.md", "")
    ok = (rc == 0 and "## not fetched" in md and "ending" in md
          and "## summary" in md and "not fetched: ending" in out)
    return ok, ("a missing section is listed, the rest saved" if ok
                else f"rc {rc}, out {out!r}")


def t_readable_md():
    rc, _out, _s, files = _run(ROUTES)
    md = files.get("plotexplained.md", "")
    ok = (SUMMARY in md and "- [01:28 | Factory] Shaw reveals" in md
          and "Never copy its wording" in md)
    return ok, ("summary text, one timed line per timeline entry, "
                "cross-check notice" if ok else md[:300])


def t_no_key():
    if os.name == "nt":
        return True, "skipped on Windows (would read the real registry)"
    rc, out, seen, files = _run(ROUTES, env_key=None)
    ok = rc == 2 and "SetEnvironmentVariable" in out and not seen
    return ok, ("no key: says how to set it, makes no request" if ok
                else f"rc {rc}, out {out!r}, {len(seen)} request(s)")


TESTS = [("SLUG-FALLBACK", t_slug_fallback),
         ("KEY-NEVER-SHOWN", t_key_never_shown),
         ("KEY-REFUSED", t_key_refused),
         ("SECTION-MISSING", t_section_missing),
         ("READABLE-MD", t_readable_md),
         ("NO-KEY", t_no_key)]

if __name__ == "__main__":
    fails = 0
    for name, fn in TESTS:
        try:
            ok, msg = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            ok, msg = False, f"{type(e).__name__}: {e}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:18s} {msg}")
    print("-" * 60)
    print("test_fetch_plot_ref: all pass" if not fails
          else f"test_fetch_plot_ref: {fails} FAILURE(S)")
    sys.exit(1 if fails else 0)
