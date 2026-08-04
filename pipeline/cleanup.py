"""
Reclaim disk space from a project (or every project) safely.

Three tiers of removal:
  - temp   : audio16k.wav + _work/ + _clipcache/ + stray _batch_*.mp4 + logs
             (always safe junk)
  - source : source.mp4                                    (the big 2-3h file)
  - all    : temp + source + frames/ + music.mp3, keeping only the deliverables
             (final.mp4, transcript.json, draft.json, script.txt, thumbnail.jpg,
              titles.txt, narration/)

GOLDEN RULE: nothing is ever deleted without first listing what will go and
asking for confirmation. source.mp4 ALWAYS requires an explicit yes — even with
--yes we still print it loudly. The pipeline never auto-deletes source.mp4.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from rich.console import Console

import config

console = Console()

# Files/dirs that are pure throwaway temp.
TEMP_NAMES = ["audio16k.wav"]
TEMP_DIRS = ["_work", "_clipcache"]
TEMP_GLOBS = ["_batch_*.mp4", "av_xfade.mp4", "ingest.log", "ingest.err.log",
              "render.log", "render.err.log"]

# What "--all" keeps. Everything else in the project (except these) is removable.
KEEP_FOR_ALL = {
    "final.mp4", "transcript.json", "transcript_for_script.txt",
    "draft.json", "script.txt", "thumbnail.jpg", "titles.txt",
    "captions.ass", "broll.json",
    "state.json",          # engine-owned stage marker (outline/script)
}
KEEP_DIRS_FOR_ALL = {"narration"}


def _size(p: Path) -> int:
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    if p.is_file():
        return p.stat().st_size
    return 0


def _fmt(nbytes: int) -> str:
    mb = nbytes / (1024 * 1024)
    if mb >= 1024:
        return f"{mb/1024:.2f} GB"
    return f"{mb:.0f} MB"


def _collect(pdir: Path, source: bool, all_: bool,
             frames: bool = False) -> tuple[list[Path], list[Path]]:
    """
    Return (removable, source_targets).
    `removable` = temp (+ everything-but-keep when all_).
    `source_targets` = source.mp4 (only when source or all_ requested).
    """
    removable: list[Path] = []

    # temp tier (always part of any clean)
    for name in TEMP_NAMES:
        p = pdir / name
        if p.exists():
            removable.append(p)
    for d in TEMP_DIRS:
        p = pdir / d
        if p.exists():
            removable.append(p)
    for pat in TEMP_GLOBS:
        removable.extend(pdir.glob(pat))

    # frames/ are cheap montage JPGs that can be regenerated; remove on request.
    if frames or all_:
        fr = pdir / "frames"
        if fr.exists():
            removable.append(fr)

    if all_:
        # everything not on the keep-list (except source.mp4, handled separately)
        for child in pdir.iterdir():
            if child.name == "source.mp4":
                continue
            if child.is_dir() and child.name in KEEP_DIRS_FOR_ALL:
                continue
            if child.is_file() and child.name in KEEP_FOR_ALL:
                continue
            if child not in removable:
                removable.append(child)

    source_targets: list[Path] = []
    if source or all_:
        sp = pdir / "source.mp4"
        if sp.exists():
            source_targets.append(sp)

    # de-dup while keeping order
    seen = set()
    removable = [p for p in removable if not (p in seen or seen.add(p))]
    return removable, source_targets


def _confirm(prompt: str, auto_yes: bool) -> bool:
    if auto_yes:
        console.print(f"[yellow]{prompt}[/] -> auto-confirmed (--yes)")
        return True
    try:
        ans = input(f"{prompt} (y/N): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[red]Aborted.[/]")
        return False
    return ans in ("y", "yes")


def _force_writable(path: Path):
    """Clear read-only attributes OneDrive/Windows sometimes set, so deletion works."""
    import stat
    try:
        if path.is_dir():
            for child in path.rglob("*"):
                try:
                    child.chmod(stat.S_IWRITE)
                except OSError:
                    pass
        path.chmod(stat.S_IWRITE)
    except OSError:
        pass


def _delete(paths: list[Path]) -> int:
    freed = 0
    for p in paths:
        sz = _size(p)
        ok = False
        for attempt in range(2):
            try:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                ok = True
                break
            except OSError as e:
                # OneDrive / read-only files raise WinError 5; clear flags + retry.
                if attempt == 0:
                    _force_writable(p)
                    continue
                console.print(f"[yellow]Could not remove {p.name}: {e}[/]")
        if ok:
            freed += sz
    return freed


def clean_project(project: str, source: bool = False, all_: bool = False,
                  auto_yes: bool = False, frames: bool = False) -> int:
    """Clean one project. Returns bytes freed. Always asks before deleting."""
    pdir = config.project_dir(project)
    if not pdir.exists():
        console.print(f"[red]No such project:[/] {pdir}")
        return 0

    removable, source_targets = _collect(pdir, source, all_, frames=frames)

    if not removable and not source_targets:
        console.print(f"[green]Nothing to clean in '{project}'.[/] Already tidy.")
        return 0

    freed = 0

    # --- tier 1: temp / all-but-keep ----------------------------------------
    if removable:
        total = sum(_size(p) for p in removable)
        console.print(f"\n[bold]Will remove from '{project}'[/] "
                      f"({'--all mode' if all_ else 'temp'}):")
        for p in sorted(removable, key=lambda x: -_size(x)):
            tag = "DIR " if p.is_dir() else "FILE"
            console.print(f"  [{tag}] {p.name:<28} {_fmt(_size(p)):>10}")
        console.print(f"  [bold]total: {_fmt(total)}[/]")
        if _confirm("Delete these?", auto_yes):
            freed += _delete(removable)
            console.print("[green]Removed.[/]")
        else:
            console.print("[yellow]Skipped temp/all removal.[/]")

    # --- tier 2: source.mp4 (ALWAYS its own explicit confirmation) ----------
    if source_targets:
        total = sum(_size(p) for p in source_targets)
        console.print(f"\n[bold red]source.mp4 removal[/] for '{project}':")
        for p in source_targets:
            console.print(f"  [FILE] {p.name:<28} {_fmt(_size(p)):>10}")
        console.print("[yellow]This is the original 2-3h video. You'll have to "
                      "re-download it if you want to re-render or make a thumbnail.[/]")
        if _confirm("Delete source.mp4?", auto_yes):
            freed += _delete(source_targets)
            console.print("[green]source.mp4 removed.[/]")
        else:
            console.print("[yellow]Kept source.mp4.[/]")

    if freed:
        console.print(f"\n[bold green]Freed {_fmt(freed)} total.[/]")
    return freed


def clean_all_projects(source: bool = False, all_: bool = False,
                       auto_yes: bool = False, frames: bool = False) -> int:
    """Clean every project under projects/."""
    if not config.PROJECTS_DIR.exists():
        console.print("[yellow]No projects directory.[/]")
        return 0
    projects = sorted(p.name for p in config.PROJECTS_DIR.iterdir() if p.is_dir())
    if not projects:
        console.print("[yellow]No projects found.[/]")
        return 0

    console.print(f"[cyan]Cleaning {len(projects)} project(s):[/] {', '.join(projects)}")
    total_freed = 0
    for name in projects:
        total_freed += clean_project(name, source=source, all_=all_,
                                     auto_yes=auto_yes, frames=frames)
    console.print(f"\n[bold green]Grand total freed: {_fmt(total_freed)}[/]")
    return total_freed
