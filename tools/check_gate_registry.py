# -*- coding: utf-8 -*-
"""check_gate_registry.py - one list of every gate, kept honest by the code.

    python tools/check_gate_registry.py           # fail if code and registry differ
    python tools/check_gate_registry.py --write   # add new gates / drop dead ones

WHY. ~120 gates are printed as `[NAME]` across pipeline/ and recap.py, with
no single place saying which exist, how loud each is or where it lives.
"81 gates" and "~100 gates" were both quoted in reports and neither was
checkable. config/gates.json is that list:

    {"NAME": {"severity": "error|warn|note|report",
              "modules": ["pipeline/draft.py", ...],
              "what": "one line, edited by hand",
              "severity_source": "inferred|declared"}}

CHECK mode fails when the code prints a gate the registry does not list (a
gate added without being declared) or the registry lists a gate the code no
longer prints (a deleted gate still claimed). --write reconciles both ways:
new gates come in with severity INFERRED from how they print (red / yellow /
dim, or an `errors.append` / `sev = "hard"` nearby) and are marked so;
anything a human has set to "declared" is never overwritten.

Severity here describes the gate, it does not enforce it - enforcement stays
in the code. The inferred value is a starting point a person corrects once.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "config", "gates.json")
SOURCES = ["recap.py"] + sorted(
    os.path.join("pipeline", f) for f in os.listdir(os.path.join(ROOT, "pipeline"))
    if f.endswith(".py"))

# Bracketed tokens that are not gates: catalogue markers, a diagram, a
# directory-listing label, a verify sub-status.
NOT_GATES = {"S6", "S7", "XF", "FILE", "ESCALATED"}

_TAG = re.compile(r"\[([A-Z][A-Z0-9]+(?:-[A-Z0-9]+)*)\]")


def scan() -> dict:
    """{gate: {"modules": set, "contexts": [str]}} from string literals."""
    found: dict = {}
    for rel in SOURCES:
        src = open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace").read()
        lines = src.splitlines()
        for i, line in enumerate(lines):
            if '"' not in line and "'" not in line:
                continue
            code = line.split("#", 1)[0] if not line.lstrip().startswith(("f\"", "\"", "f'", "'")) else line
            for m in _TAG.finditer(code):
                g = m.group(1)
                if g in NOT_GATES or len(g) < 3:
                    continue
                e = found.setdefault(g, {"modules": set(), "contexts": []})
                e["modules"].add(rel.replace("\\", "/"))
                e["contexts"].append("\n".join(lines[max(0, i - 3): i + 4]))
    return found


def infer_severity(contexts: list) -> str:
    blob = "\n".join(contexts)
    if re.search(r"errors\.append|sev\s*=\s*\"hard\"|sys\.exit\(1\)|problems\.append|_fatal", blob):
        return "error"
    if "[red]" in blob:
        return "error"
    if "[yellow]" in blob or "warns.append" in blob:
        return "warn"
    if "[dim]" in blob or "notes.append" in blob:
        return "note"
    return "report"


def _what(contexts: list, gate: str) -> str:
    for c in contexts:
        m = re.search(r"\[" + re.escape(gate) + r"\]\[?/?\]?\s*([^\"'{]{12,90})", c)
        if m and "\n" not in m.group(1):
            return m.group(1).strip().rstrip(".:-") + " ..."
    return ""


def load() -> dict:
    if not os.path.exists(REG):
        return {}
    return json.load(open(REG, encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    code = scan()
    reg = load()
    new = sorted(set(code) - set(reg))
    dead = sorted(set(reg) - set(code))

    if a.write:
        for g in new:
            reg[g] = {"severity": infer_severity(code[g]["contexts"]),
                      "modules": sorted(code[g]["modules"]),
                      "what": _what(code[g]["contexts"], g),
                      "severity_source": "inferred"}
        for g in dead:
            del reg[g]
        for g, e in reg.items():            # modules always follow the code
            e["modules"] = sorted(code[g]["modules"])
        os.makedirs(os.path.dirname(REG), exist_ok=True)
        with open(REG, "w", encoding="utf-8") as f:
            json.dump(dict(sorted(reg.items())), f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"gates.json: {len(reg)} gate(s); +{len(new)} added, "
              f"-{len(dead)} removed")
        return 0

    by_sev: dict = {}
    for e in reg.values():
        by_sev[e["severity"]] = by_sev.get(e["severity"], 0) + 1
    print(f"gate registry: {len(reg)} registered, {len(code)} in code  "
          + "  ".join(f"{k} {v}" for k, v in sorted(by_sev.items())))
    if new or dead:
        if new:
            print(f"[GATE-REGISTRY] {len(new)} gate(s) printed by the code but "
                  f"not registered: {', '.join(new)}")
        if dead:
            print(f"[GATE-REGISTRY] {len(dead)} registered gate(s) the code no "
                  f"longer prints: {', '.join(dead)}")
        print("  Run `python tools/check_gate_registry.py --write`, then fill in "
              "'what' and check 'severity' for the new entries.")
        return 1
    print("GATE-REGISTRY: clean - every gate in the code is registered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
