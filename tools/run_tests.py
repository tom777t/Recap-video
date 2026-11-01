# -*- coding: utf-8 -*-
"""run_tests.py - one command for every test suite in the repo.

    python tools/run_tests.py                 # every suite (before a push)
    python tools/run_tests.py --changed       # only suites touched by your edits
    python tools/run_tests.py --changed origin/main
    python tools/run_tests.py test_preflight test_stems   # by name
    python tools/run_tests.py --list          # show what would run, run nothing

WHY. The repo grew ~30 standalone `tools/test_*.py` suites plus
`gate_selftest.py` and `check_config_usage.py`, each run by hand. "29 suites
green" was a claim nobody could reproduce with one command, and a full run
takes ~8 minutes on a laptop, so agents re-ran everything after every small
edit. This runner gives:

  * ONE verdict for a push: every suite, summary table, non-zero exit on any
    failure or timeout.
  * A FAST inner loop: `--changed` selects only the suites whose source (or
    whose imported pipeline modules, followed transitively) were edited, so an
    edit to pipeline/stems.py re-runs test_stems.py and the suites that import
    stems, not the 3-minute render smoke test.

`--changed` is a speed aid, never a substitute for the full run before
pushing: it follows imports it can see by text, and a suite that reaches a
module dynamically (subprocess `recap.py ...`) is caught by the ALWAYS_IF rule
below, which widens to everything when an entry point or config changes.

Exit 0 = every selected suite passed.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
PIPE = os.path.join(ROOT, "pipeline")

# Suites that are not named test_*.py but are part of the verdict.
EXTRA_SUITES = ["gate_selftest.py", "check_config_usage.py"]

# A change to any of these can reach every suite (entry points, shared
# config, the test harness itself), so --changed widens to the full set.
ALWAYS_IF = {"config.py", "recap.py", "run.ps1", "requirements.txt",
             "pipeline/__init__.py", "tools/run_tests.py"}

TIMEOUT_SEC = 1800


def suites() -> list[str]:
    names = sorted(f for f in os.listdir(TOOLS)
                   if f.startswith("test_") and f.endswith(".py"))
    return names + [s for s in EXTRA_SUITES
                    if os.path.exists(os.path.join(TOOLS, s))]


_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+pipeline(?:\.(\w+))?\s+import\s+([\w\s,()]+)"
    r"|import\s+pipeline\.(\w+))", re.M)


def _imports(path: str) -> set[str]:
    """Pipeline module names a file imports, by text."""
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return set()
    out: set[str] = set()
    for m in _IMPORT_RE.finditer(src):
        if m.group(1):
            out.add(m.group(1))
        elif m.group(2):  # from pipeline import a, b
            for n in re.split(r"[\s,()]+", m.group(2)):
                if n and n != "as":
                    out.add(n)
        elif m.group(3):
            out.add(m.group(3))
    # relative imports inside pipeline/ (from .x import y)
    for m in re.finditer(r"^\s*from\s+\.(\w+)\s+import", src, re.M):
        out.add(m.group(1))
    mods = {f[:-3] for f in os.listdir(PIPE) if f.endswith(".py")}
    return out & mods


def _module_closure(start: set[str]) -> set[str]:
    """Every pipeline module reachable from `start` by import."""
    seen: set[str] = set()
    todo = list(start)
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.add(m)
        todo.extend(_imports(os.path.join(PIPE, m + ".py")) - seen)
    return seen


def changed_files(base: str | None) -> list[str]:
    """Files changed vs `base` (default: HEAD), plus untracked files."""
    ref = base or "HEAD"
    out = subprocess.run(["git", "diff", "--name-only", ref], cwd=ROOT,
                         capture_output=True, text=True).stdout.split()
    out += subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                          cwd=ROOT, capture_output=True, text=True).stdout.split()
    return sorted({p.replace("\\", "/") for p in out})


def select_changed(files: list[str]) -> tuple[list[str], str]:
    all_s = suites()
    if any(f in ALWAYS_IF for f in files):
        hit = sorted(f for f in files if f in ALWAYS_IF)
        return all_s, f"full set: shared file changed ({', '.join(hit)})"
    mods = {os.path.basename(f)[:-3] for f in files
            if f.startswith("pipeline/") and f.endswith(".py")}
    tool_names = {os.path.basename(f) for f in files if f.startswith("tools/")}
    picked = []
    for s in all_s:
        if s in tool_names:
            picked.append(s)
            continue
        path = os.path.join(TOOLS, s)
        reach = _module_closure(_imports(path))
        src = open(path, encoding="utf-8", errors="replace").read()
        # a suite that shells out to a changed tool (python tools/x.py)
        tool_hit = any(t[:-3] in src for t in tool_names if t.endswith(".py"))
        if reach & mods or tool_hit:
            picked.append(s)
    return picked, f"{len(picked)} suite(s) touched by {len(files)} changed file(s)"


def run(names: list[str]) -> int:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    rows = []
    t_all = time.time()
    for n in names:
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, os.path.join("tools", n)],
                               cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               timeout=TIMEOUT_SEC, env=env)
            ok, code, tail = r.returncode == 0, r.returncode, (r.stdout + r.stderr)
        except subprocess.TimeoutExpired:
            ok, code, tail = False, "timeout", ""
        dt = time.time() - t0
        rows.append((n, ok, code, dt))
        mark = "PASS" if ok else "FAIL"
        print(f"  {mark}  {n:<34} {dt:6.1f}s", flush=True)
        if not ok:
            last = "\n".join(tail.strip().splitlines()[-15:])
            print("        " + last.replace("\n", "\n        "), flush=True)
    bad = [r for r in rows if not r[1]]
    print(f"\n{len(rows) - len(bad)}/{len(rows)} suites passed "
          f"in {time.time() - t_all:.0f}s")
    for n, _, code, _ in bad:
        print(f"  FAILED: {n} (exit {code})")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("names", nargs="*", help="suite names (with or without .py)")
    ap.add_argument("--changed", nargs="?", const="", metavar="BASE",
                    help="only suites touched by changes vs BASE (default HEAD)")
    ap.add_argument("--list", action="store_true", help="print the selection only")
    a = ap.parse_args()

    all_s = suites()
    if a.names:
        want = {n if n.endswith(".py") else n + ".py" for n in a.names}
        missing = want - set(all_s)
        if missing:
            print(f"unknown suite(s): {', '.join(sorted(missing))}")
            return 2
        names, why = [s for s in all_s if s in want], "named"
    elif a.changed is not None:
        names, why = select_changed(changed_files(a.changed or None))
    else:
        names, why = all_s, "full set"

    print(f"run_tests: {why}")
    if a.list or not names:
        for n in names:
            print(f"  {n}")
        if not names:
            print("  (nothing to run)")
        return 0
    return run(names)


if __name__ == "__main__":
    sys.exit(main())
