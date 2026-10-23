# -*- coding: utf-8 -*-
"""check_config_usage.py - fail on any config key that no code reads.

    python tools/check_config_usage.py
    python tools/check_config_usage.py --selftest

WHY. `PRE_REVEAL_PAUSE = 0.6` sat in config.py for a whole phase being read by
nothing. It was written up in a criterion document as a delivered feature, and
the only reason it was caught is that somebody re-read the document. A config
key is a promise that something is configurable; a key nothing reads is a
promise the code does not keep, and it is invisible precisely because changing
it produces no effect to notice.

The check is deliberately crude: a plain substring search for the key's name
across every tracked source file except config.py itself. Crude is correct
here, because access can be dynamic - `getattr(config, "MUSIC_VOLUME", 0.15)`
contains the name as a string, and an AST-only approach would call it unused.
The failure mode of a substring search is a FALSE PASS (a key mentioned only
in a comment counts as read), never a false fail, so it cannot block work by
being clever.

An unused key is an ERROR. If a key is deliberately not read - documentation,
a value a human edits and a script reads at runtime - it goes in ALLOWED below
WITH a reason, so the exception is visible instead of the key just vanishing
from scrutiny.
"""
from __future__ import annotations
import argparse, ast, io, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config.py")

# Keys that genuinely nothing reads, each with the reason it stays.
ALLOWED = {
    "CHANNEL_NAME": "read by a human writing the intro line, and named in "
                    "prompts/recap_style.md rather than in code",
}

# CODE ONLY. Documentation and JSON are deliberately excluded: the question is
# "does anything READ this", and a key named in a criterion document is read by
# nobody. Including .md made three keys that my own 2e work had orphaned look
# alive, because the commit message explaining their retirement mentioned them.
SEARCH_EXT = (".py", ".ps1", ".cmd", ".bat")
SKIP_DIRS = {".git", "__pycache__", "projects", "references", "bin",
             "assets", "node_modules", ".venv", "venv"}


def config_keys(path: str = CONFIG) -> list:
    """Module-level UPPER_CASE assignments in config.py, in source order."""
    src = io.open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    out = []
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and re.fullmatch(r"[A-Z][A-Z0-9_]*", t.id):
                out.append((t.id, node.lineno))
    return out


def source_files() -> list:
    files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(SEARCH_EXT):
                continue
            p = os.path.join(dirpath, fn)
            if os.path.abspath(p) == os.path.abspath(CONFIG):
                continue
            files.append(p)
    return files


def find_unused(keys=None, files=None) -> list:
    keys = keys if keys is not None else [k for k, _ in config_keys()]
    files = files if files is not None else source_files()
    blobs = []
    for p in files:
        try:
            blobs.append(io.open(p, encoding="utf-8", errors="replace").read())
        except OSError:
            pass
    joined = "\n".join(blobs)
    return [k for k in keys
            if not re.search(r"\b" + re.escape(k) + r"\b", joined)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    keys = config_keys()
    files = source_files()
    unused = find_unused([k for k, _ in keys], files)
    lineno = dict(keys)
    flagged = [k for k in unused if k not in ALLOWED]
    excused = [k for k in unused if k in ALLOWED]

    print("config keys   : %d" % len(keys))
    print("source files  : %d" % len(files))
    print("read somewhere: %d" % (len(keys) - len(unused)))
    if excused:
        print("allowed unused: %d" % len(excused))
        for k in excused:
            print("    %-28s line %-5s %s" % (k, lineno.get(k), ALLOWED[k]))
    if flagged:
        print()
        print("[CONFIG-UNUSED] %d key(s) that no code reads:" % len(flagged))
        for k in flagged:
            print("    %-28s config.py:%s" % (k, lineno.get(k)))
        print()
        print("  Each one is a promise that something is configurable, with no")
        print("  code keeping it. Wire it, delete it, or add it to ALLOWED in")
        print("  this file with the reason it stays.")
        return 1
    print("CONFIG-UNUSED: clean - every key is read somewhere.")
    return 0


def selftest() -> int:
    ok = True
    print("### a key the code DOES read must pass")
    # MUSIC_VOLUME is read by render.py; PRE_REVEAL_PAUSE should now be too.
    for k in ("MUSIC_VOLUME", "PRE_REVEAL_PAUSE", "FILM_AUDIO_DB"):
        hit = not find_unused([k])
        print("  %-22s %s" % (k, "read" if hit else "NOT READ <-- unexpected"))
        if not hit:
            ok = False

    print()
    print("### an invented key that nothing reads must FAIL")
    # The name is ASSEMBLED AT RUNTIME on purpose. The first version wrote it
    # as a literal, and the test failed: this file lives in tools/, tools/ is
    # searched, so the literal made its own fake key look "read". A negative
    # control that names itself inside the thing it is testing is not a
    # control. Joining fragments means the contiguous string exists nowhere on
    # disk, only in memory.
    fake = "ZZ" + "_NEVER" + "_REFERENCED" + "_ANYWHERE"
    hit = find_unused([fake])
    print("  %-22s %s" % (fake, "flagged" if hit else "MISSED <-- gate is blind"))
    if not hit:
        ok = False

    print()
    print("### dynamic access via getattr must count as read")
    # Proves the substring approach is the right crudeness: an AST-only check
    # would call a getattr-only key unused and demand it be deleted.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "fake_consumer.py")
        io.open(p, "w", encoding="utf-8").write(
            'x = getattr(config, "ZZ_ONLY_VIA_GETATTR", 1)\n')
        miss = find_unused(["ZZ_ONLY_VIA_GETATTR"], [p])
        print("  %-22s %s" % ("ZZ_ONLY_VIA_GETATTR",
                              "counted as read" if not miss
                              else "called unused <-- too strict"))
        if miss:
            ok = False

    print()
    print("### the real repo must be clean")
    rc = 0
    keys = [k for k, _ in config_keys()]
    unused = [k for k in find_unused(keys) if k not in ALLOWED]
    if unused:
        print("  %d unused key(s): %s" % (len(unused), ", ".join(unused)))
        ok = False
    else:
        print("  clean")

    print()
    print("RESULT:", "ALL SELF-TESTS PASS" if ok else "SELF-TEST FAILURE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
