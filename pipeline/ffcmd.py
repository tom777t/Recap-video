# -*- coding: utf-8 -*-
"""ffcmd.py - keep an ffmpeg command short enough for the OS to start.

Lost in the Stars' final mix - a 20-minute bed with 11 cues and 26 reveal
dips - built a filter graph past Windows' 32,767-character command-line
limit and died with "[WinError 206] The filename or extension is too long"
after the whole video had been encoded. Any graph that grows with the film
(cue mixes, crossfade chains, censor overlays) can do the same, so every
ffmpeg call that takes a -filter_complex goes through fit(): a long graph is
written to a file and ffmpeg reads it from there -
`-/filter_complex FILE` (ffmpeg 7.0+) or `-filter_complex_script FILE`.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

CMD_MAX = 8000     # characters; Windows refuses a command line over 32767
_MAJOR: dict = {}


def ff_major(ff: str) -> int:
    """ffmpeg's major version (0 when unknown), asked once per binary."""
    if ff not in _MAJOR:
        try:
            out = subprocess.run([ff, "-version"], capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=20).stdout
            m = re.search(r"ffmpeg version n?(\d+)", out)
            _MAJOR[ff] = int(m.group(1)) if m else 0
        except Exception:
            _MAJOR[ff] = 0
    return _MAJOR[ff]


def cmd_len(cmd: list) -> int:
    return sum(len(str(c)) + 1 for c in cmd)


def short_cmd(cmd: list, workdir: Path, major: int) -> list:
    """The same command with each long -filter_complex moved into a file,
    when the whole command is over CMD_MAX; otherwise `cmd` itself."""
    if cmd_len(cmd) <= CMD_MAX:
        return cmd
    out = list(cmd)
    for i, c in enumerate(out[:-1]):
        if c == "-filter_complex" and len(str(out[i + 1])) > 200:
            g = str(out[i + 1])
            Path(workdir).mkdir(parents=True, exist_ok=True)
            f = Path(workdir) / (
                "graph_" + hashlib.sha1(g.encode("utf-8")).hexdigest()[:16]
                + ".txt")
            f.write_text(g, encoding="utf-8")
            out[i] = "-/filter_complex" if major >= 7 else \
                "-filter_complex_script"
            out[i + 1] = str(f)
    return out


def fit(cmd: list) -> list:
    """`cmd`, made short enough to start (a no-op for ordinary commands)."""
    if cmd_len(cmd) <= CMD_MAX:
        return cmd
    return short_cmd(cmd, Path(tempfile.gettempdir()) / "recap_graphs",
                     ff_major(str(cmd[0])))
