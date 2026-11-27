# -*- coding: utf-8 -*-
"""test_windows_encoding.py - every text the pipeline reads, writes or gets
back from a program names its encoding.

On Windows Python's default text encoding is the locale's (cp1252), not
UTF-8. A file read or written without encoding=, and a subprocess run with
text=True and no encoding=, then decodes a Chinese film title, a Thai
subtitle or a Vietnamese path as cp1252 - mojibake, or a UnicodeDecodeError
that stops the stage. Linux never shows it, so it has to be checked by
reading the code.

  FILES-NAME-ENCODING   open() in text mode, Path.read_text / write_text
  PROGRAMS-NAME-ENCODING subprocess.run / Popen / check_output with text=True

    python tools/test_windows_encoding.py          # report
    python tools/test_windows_encoding.py --fix    # add encoding= in place
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DIRS = ("pipeline", "tools")
FILES = ("recap.py", "config.py")
SUBP = {"run", "Popen", "check_output", "check_call", "call"}


def sources():
    for d in DIRS:
        for p in sorted((ROOT / d).glob("*.py")):
            if not p.name.startswith("test_"):
                yield p
    for f in FILES:
        if (ROOT / f).exists():
            yield ROOT / f


def _kw(call, name):
    return next((k for k in call.keywords if k.arg == name), None)


def _text_mode(call) -> bool:
    """open(...) in text mode (no 'b' in its mode)."""
    mode = None
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
        mode = call.args[1].value
    k = _kw(call, "mode")
    if k is not None and isinstance(k.value, ast.Constant):
        mode = k.value.value
    if mode is None:
        return not (len(call.args) > 1 or k is not None)  # default "r"
    return isinstance(mode, str) and "b" not in mode


def offenders(path: Path):
    """[(kind, line, col_of_insert, text)] for one file."""
    src = path.read_bytes().decode("utf-8-sig")
    tree = ast.parse(src)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else (
            f.id if isinstance(f, ast.Name) else "")
        if any(k.arg is None for k in node.keywords):
            continue                          # **kwargs: cannot tell
        if name in SUBP and isinstance(f, ast.Attribute) and isinstance(
                f.value, ast.Name) and f.value.id in ("subprocess", "sp",
                                                      "_sp", "_subprocess"):
            t = _kw(node, "text") or _kw(node, "universal_newlines")
            if (t is not None and isinstance(t.value, ast.Constant)
                    and t.value.value is True and _kw(node, "encoding") is None):
                out.append(("program", t.value.end_lineno,
                            t.value.end_col_offset,
                            ', encoding="utf-8", errors="replace"'))
        elif name in ("read_text", "write_text") and isinstance(
                f, ast.Attribute):
            if _kw(node, "encoding") is None:
                n_pos = len(node.args)
                if name == "read_text" and n_pos >= 1:
                    continue                      # encoding given by position
                if name == "write_text" and n_pos >= 2:
                    continue
                out.append(("file", node.end_lineno, node.end_col_offset - 1,
                            (', ' if node.args or node.keywords else '')
                            + 'encoding="utf-8"'))
        elif name == "open" and (isinstance(f, ast.Name) or (
                isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                and f.value.id in ("io", "codecs"))):
            if _text_mode(node) and _kw(node, "encoding") is None and \
                    len(node.args) < 4:
                out.append(("file", node.end_lineno, node.end_col_offset - 1,
                            ', encoding="utf-8"'))
    return out


def fix(path: Path, offs) -> int:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    lines = raw.decode("utf-8-sig").split("\n")
    # right to left within a line so the columns stay valid
    for kind, ln, col, ins in sorted(offs, key=lambda x: (x[1], x[2]),
                                     reverse=True):
        s = lines[ln - 1]
        b = s.encode("utf-8")
        lines[ln - 1] = (b[:col] + ins.encode("utf-8") + b[col:]).decode(
            "utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"")
                     + "\n".join(lines).encode("utf-8"))
    return len(offs)


def main() -> int:
    do_fix = "--fix" in sys.argv
    files = progs = 0
    rows = []
    for p in sources():
        offs = offenders(p)
        if do_fix and offs:
            fix(p, offs)
            offs = offenders(p)
        for kind, ln, _c, _i in offs:
            rows.append(f"  {p.relative_to(ROOT)}:{ln} ({kind})")
            files += kind == "file"
            progs += kind == "program"
    res = [("FILES-NAME-ENCODING", files == 0,
            f"{files} text file read/write(s) with no encoding"),
           ("PROGRAMS-NAME-ENCODING", progs == 0,
            f"{progs} subprocess call(s) with text=True and no encoding")]
    bad = 0
    for name, ok, msg in res:
        print(f'{"PASS" if ok else "FAIL"}  {name:<23} {msg}')
        bad += not ok
    if rows:
        print("\n".join(rows[:60]))
    print("-" * 60)
    print("test_windows_encoding: all pass" if not bad else
          f"test_windows_encoding: {bad} FAILURE(S)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
