"""One file holding every measurement taken on the finished render.

WHY
---
Seven defects were found by watching a render that every gate had passed. The
gates were then rewritten to measure the finished file rather than the plan -
but their output was scattered across a few hundred lines of console log, in
dim grey, interleaved with the build. A number that scrolled past at 02:14 of a
render is not evidence anybody can check.

So every final-file check also writes here: its verdict, every number it
measured, and the OUTPUT timestamp of every finding. Output timestamps, not
source timestamps, because the question a reader has is "where do I scrub to".

The report is written even when a check FAILS AND STOPS THE RENDER. That is
when it is most useful, and it is the easy thing to get wrong - a report
emitted only on the happy path tells you nothing about the run you actually
need to understand.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def hms(t) -> str:
    """Output timestamp as m:ss.cc - the form you type into a player."""
    try:
        t = float(t)
    except (TypeError, ValueError):
        return "?"
    sign = "-" if t < 0 else ""
    t = abs(t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    if h:
        return f"{sign}{h}:{m:02d}:{s:05.2f}"
    return f"{sign}{m}:{s:05.2f}"


class Report:
    """Accumulates check results, then writes final_report.md."""

    def __init__(self, project: str, final: Path):
        self.project = project
        self.final = Path(final)
        self.started = datetime.now(timezone.utc)
        self.checks: list = []
        self.notes: list = []

    # -- collection ------------------------------------------------------- #
    def add(self, name: str, ok: bool | None, summary: str,
            numbers: dict | None = None, rows: list | None = None,
            findings: list | None = None, fatal: bool = False,
            why: str = "") -> None:
        """Record one check.

        `ok=None` means "could not run" - reported as SKIPPED rather than as a
        pass, because an unknown answer must not read as a clean one. That
        distinction is the whole reason the truncated render shipped: a freeze
        check that scanned 255s of a 1054s film reported no freezes.
        """
        self.checks.append({
            "name": name,
            "ok": ok,
            "fatal": bool(fatal),
            "summary": summary,
            "why": why,
            "numbers": dict(numbers or {}),
            "rows": list(rows or []),
            "findings": list(findings or []),
        })

    def note(self, text: str) -> None:
        self.notes.append(text)

    # -- rendering -------------------------------------------------------- #
    def _verdict(self, c: dict) -> str:
        if c["ok"] is None:
            return "SKIPPED"
        return "PASS" if c["ok"] else ("FAIL" if c["fatal"] else "WARN")

    def write(self, path: Path | None = None) -> Path:
        path = Path(path or (self.final.parent / "final_report.md"))
        L: list = []
        a = L.append

        n_fail = sum(1 for c in self.checks
                     if c["ok"] is False and c["fatal"])
        n_warn = sum(1 for c in self.checks
                     if c["ok"] is False and not c["fatal"])
        n_skip = sum(1 for c in self.checks if c["ok"] is None)
        n_pass = sum(1 for c in self.checks if c["ok"] is True)

        a(f"# Final render report - {self.project}")
        a("")
        a(f"- file: `{self.final}`")
        a(f"- measured: {self.started.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        a(f"- checks: **{n_pass} pass, {n_fail} fail, {n_warn} warn, "
          f"{n_skip} skipped**")
        a("")
        a("Every number below was measured on the finished file. All "
          "timestamps are OUTPUT positions in `final.mp4`.")
        a("")

        # ---- summary table ---------------------------------------------- #
        a("## Verdicts")
        a("")
        a("| check | verdict | summary |")
        a("|---|---|---|")
        for c in self.checks:
            s = str(c["summary"]).replace("|", "\\|")
            a(f"| `{c['name']}` | **{self._verdict(c)}** | {s} |")
        a("")

        # ---- findings first, with timestamps ---------------------------- #
        allf = [(c["name"], f) for c in self.checks for f in c["findings"]]
        a("## Findings")
        a("")
        if not allf:
            a("None. No check reported a defect.")
        else:
            a(f"{len(allf)} finding(s), worst first within each check.")
            a("")
            for name, f in allf:
                if isinstance(f, dict):
                    at = f.get("at")
                    txt = f.get("text") or f.get("msg") or json.dumps(f)
                    stamp = f" **[{hms(at)}]**" if at is not None else ""
                    a(f"- `{name}`{stamp} {txt}")
                else:
                    a(f"- `{name}` {f}")
        a("")

        # ---- per-check detail ------------------------------------------- #
        a("## Measurements")
        for c in self.checks:
            a("")
            a(f"### {c['name']} - {self._verdict(c)}")
            a("")
            if c["why"]:
                a(f"_{c['why']}_")
                a("")
            a(c["summary"])
            a("")
            if c["numbers"]:
                a("| measure | value |")
                a("|---|---|")
                for k, v in c["numbers"].items():
                    a(f"| {k} | {_fmt(v)} |")
                a("")
            if c["rows"]:
                keys = []
                for r in c["rows"]:
                    for k in r:
                        if k not in keys:
                            keys.append(k)
                a("| " + " | ".join(keys) + " |")
                a("|" + "|".join("---" for _ in keys) + "|")
                for r in c["rows"]:
                    a("| " + " | ".join(_fmt(r.get(k)) for k in keys) + " |")
                a("")

        if self.notes:
            a("## Notes")
            a("")
            for n in self.notes:
                a(f"- {n}")
            a("")

        path.write_text("\n".join(L) + "\n", encoding="utf-8")
        return path


def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".")
    if isinstance(v, (list, tuple)):
        return ", ".join(_fmt(x) for x in v) if v else "-"
    s = str(v)
    return s.replace("|", "\\|")
