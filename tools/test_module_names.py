# -*- coding: utf-8 -*-
"""test_module_names.py - no module uses a standard name it never imported.

recap.py's voice stage printed "[ANCHOR] check could not run: name 'Path'
is not defined" on every run (Lost in the Stars): the words-vs-picture
check never ran, and the try/except around it turned the crash into a
yellow line nobody acts on. This scans recap.py, pipeline/ and tools/ for
the standard names most often used without an import.

    python tools/test_module_names.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCH = {"Path", "json", "re", "os", "sys", "subprocess", "shutil", "time",
         "math", "tempfile", "datetime", "config", "statistics"}


def problems(path: Path) -> list:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except (SyntaxError, UnicodeDecodeError) as e:
        return [f"{path.name}: does not parse ({e})"]
    bound = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                if a.name == "*":
                    return []            # star import: cannot tell
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                            ast.ClassDef)):
            bound.add(n.name)
            for a in getattr(n, "args", None) and (
                    n.args.args + n.args.kwonlyargs + n.args.posonlyargs) or []:
                bound.add(a.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store,
                                                            ast.Del)):
            bound.add(n.id)
        elif isinstance(n, ast.arg):
            bound.add(n.arg)
        elif isinstance(n, (ast.ExceptHandler,)) and n.name:
            bound.add(n.name)
        elif isinstance(n, ast.alias):
            pass
    used = {n.id: n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return [f"{path.relative_to(ROOT)}:{ln}: '{name}' is used but never "
            f"imported" for name, ln in sorted(used.items())
            if name in WATCH and name not in bound]


def main() -> int:
    files = [ROOT / "recap.py"] + sorted((ROOT / "pipeline").glob("*.py")) \
        + sorted((ROOT / "tools").glob("*.py"))
    bad = [p_ for f in files for p_ in problems(f)]
    ok = not bad
    print(f'{"PASS" if ok else "FAIL"}  STD-NAMES-IMPORTED  '
          f"{len(files)} modules" + ("" if ok else ":\n  " + "\n  ".join(bad)))
    # control: the bug this exists for is caught
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        t = Path(d) / "x.py"
        t.write_text("import sys\ndef f():\n    return Path(sys.argv[0])\n")
        ctl = bool(problems_rel(t))
    print(f'{"PASS" if ctl else "FAIL"}  CONTROL             a module calling '
          f"Path() without importing it is caught")
    # every undefined name, not only the watched standard ones (pyflakes,
    # when installed: pip install pyflakes)
    try:
        from pyflakes import api as _pf, reporter as _rep
    except ImportError:
        _pf = None
    und = []
    if _pf is not None:
        import io as _io

        class _R(_rep.Reporter):
            def __init__(self):
                super().__init__(_io.StringIO(), _io.StringIO())

            def flake(self, m):
                if type(m).__name__ in ("UndefinedName", "UndefinedLocal",
                                        "UndefinedExport"):
                    und.append(str(m))
        r = _R()
        for f in files:
            if not f.name.startswith("test_"):
                _pf.checkPath(str(f), r)
        print(f'{"PASS" if not und else "FAIL"}  NO-UNDEFINED-NAME  '
              + ("pyflakes: no undefined name in production code" if not und
                 else "\n  " + "\n  ".join(und[:20])))
    else:
        print("SKIP  NO-UNDEFINED-NAME  pyflakes not installed "
              "(pip install pyflakes)")
    print("-" * 60)
    n = (not ok) + (not ctl) + bool(und)
    print("test_module_names: all pass" if not n else
          f"test_module_names: {n} FAILURE(S)")
    return 1 if n else 0


def problems_rel(path: Path) -> list:
    global ROOT
    keep, ROOT = ROOT, path.parent
    try:
        return problems(path)
    finally:
        ROOT = keep


if __name__ == "__main__":
    sys.exit(main())
