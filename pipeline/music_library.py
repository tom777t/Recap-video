# -*- coding: utf-8 -*-
"""music_library.py - the channel's music library: fetch it once, then give
each film its music from it (owner, 18 Nov 2026).

Before this, every project's music/ folder was filled by hand, and Furious 7
and Tokyo Drift share five cue files that nobody recorded a source or
licence for. A monetised channel cannot publish music it cannot name.

config/music_library.json is the catalogue: 48 CUE tracks by Kevin MacLeod
(incompetech.com, CC BY 4.0), classified into the moods the mix uses -
action, tense, mystery, sad, reveal. No bed (the channel has its own) and
no ending track (owner, 18 Nov).

  fetch   download every kept track into music_library/ (gitignored, next to
          the repo). Run on the machine that renders: the cloud session's
          network cannot reach incompetech.com.
              python tools/music_library.py fetch
          (The render also fetches what it is missing - see ensure_cues.)
  pick    fill projects/<name>/music/cues/ from the library:
          MUSIC_LIBRARY_CUES_PER_MOOD cues per mood (one reveal) - the ones
          whose scene words the film's draft uses most, then the LEAST
          RECENTLY USED so neighbouring videos do not repeat - with their
          descriptions in music/cues/cues.json for the render to place them,
          and write music/CREDITS_cues.md with the line the YouTube description
          must carry. The bed and anything else in music/ are left alone; an
          existing music/cues/ is moved to music/cues_old_<time>/ first,
          never overwritten.
              python tools/music_library.py pick --project furious72015
  credits print a project's description line again.

Exit 0 = done; 2 = a track is missing from the library (run fetch).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

import config  # noqa: E402

CATALOGUE = ROOT / "config" / "music_library.json"
LIB = ROOT / "music_library"
MOODS = ("action", "tense", "mystery", "sad")


def load(path: Path = CATALOGUE) -> dict:
    cat = json.loads(Path(path).read_text(encoding="utf-8"))
    cat["tracks"] = [t for t in cat["tracks"] if t.get("keep", True)]
    return cat


def url_of(cat: dict, t: dict) -> str:
    return cat["url_base"] + urllib.parse.quote(t["file"])


def fetch(cat: dict, lib: Path = LIB, opener=None) -> tuple:
    """(downloaded, already there, failed [(file, why)])."""
    try:
        import truststore  # the OS certificate store, as elsewhere
        truststore.inject_into_ssl()
    except Exception:
        pass
    lib.mkdir(parents=True, exist_ok=True)
    got, had, bad = [], [], []
    seen = set()
    for t in cat["tracks"]:
        if t["file"] in seen:
            continue
        seen.add(t["file"])
        dst = lib / t["file"]
        if dst.exists() and dst.stat().st_size > 10_000:
            had.append(t["file"])
            continue
        try:
            req = urllib.request.Request(url_of(cat, t), headers={
                "User-Agent": "recap-video music_library"})
            with (opener or urllib.request.urlopen)(req, timeout=120) as r:
                data = r.read()
            if len(data) < 10_000:
                raise ValueError(f"only {len(data)} bytes")
            tmp = dst.with_suffix(".part")
            tmp.write_bytes(data)
            os.replace(tmp, dst)
            got.append(t["file"])
            print(f"  fetched {t['file']} ({len(data) / 1e6:.1f} MB)")
        except Exception as e:                  # one bad track, not the run
            bad.append((t["file"], str(e)[:80]))
            print(f"  FAILED  {t['file']}: {str(e)[:80]}")
    return got, had, bad


def _used(lib: Path) -> dict:
    try:
        return json.loads((lib / "_used.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def film_text(pdir: Path) -> str:
    """The film's own words, to match tracks to: the draft's narration, else
    the beats, else nothing."""
    for name in ("draft.json", "beats.json"):
        try:
            d = json.loads((pdir / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows = d.get("lines") or d.get("beats") or []
        return " ".join(str(r.get("narration") or r.get("what") or
                            r.get("summary") or "") for r in rows
                        if isinstance(r, dict))
    return ""


def choose(cat: dict, used: dict, per_mood: int, text: str = "") -> dict:
    """{slot: track}. Per mood: the tracks whose scene words this film uses
    most (when its draft exists), then the least recently used (never used =
    oldest), catalogue order breaking ties; one file never in two slots."""
    from pipeline.music import scene_score
    out, taken = {}, set()

    def lru(mood, n):
        pool = [t for t in cat["tracks"] if t["mood"] == mood
                and t["file"] not in taken]
        pool.sort(key=lambda t: (-scene_score(text, t.get("scenes"))[0]
                                 if text else 0,
                                 used.get(t["file"], 0.0)))
        return pool[:n]
    for slot, mood, n in [(m, m, per_mood) for m in MOODS] + \
            [("reveal", "reveal", 1)]:
        for i, t in enumerate(lru(mood, n), 1):
            out[f"{slot}{i}"] = t
            taken.add(t["file"])
    return out


def credits_text(cat: dict, picked: dict, project: str) -> str:
    titles = []
    for t in picked.values():
        if t["title"] not in titles:
            titles.append(t["title"])
    rows = "\n".join(f"  {k:9s} = \"{t['title']}\"" for k, t in
                     sorted(picked.items()))
    return (f"# Music credits - {project} (cues)\n\n{rows}\n\n"
            f"The bed is the channel's own and is not listed here.\n\n"
            f"All tracks by {cat['author']} ({cat['source']}), licensed "
            f"under {cat['license']}.\n\n"
            f"REQUIRED in the YouTube description of this video:\n\n"
            f"Music: " + ", ".join(f'"{x}"' for x in titles) +
            f" - {cat['author']} ({cat['source']})\n"
            f"Licensed under {cat['license']}\n{cat['license_url']}\n")


def pick(cat: dict, pdir: Path, lib: Path = LIB, per_mood: int | None = None,
         now: float | None = None) -> dict:
    per_mood = int(per_mood or getattr(config, "MUSIC_LIBRARY_CUES_PER_MOOD",
                                       2))
    used = _used(lib)
    picked = choose(cat, used, per_mood, film_text(pdir))
    missing = [t["file"] for t in picked.values()
               if not (lib / t["file"]).exists()]
    if missing:
        raise FileNotFoundError(f"{len(missing)} track(s) not in {lib} - run "
                                f"`python tools/music_library.py fetch` "
                                f"first: {missing[:3]}")
    mdir = pdir / "music"
    cdir = mdir / "cues"
    if cdir.exists() and any(cdir.iterdir()):
        old = mdir / f"cues_old_{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.move(str(cdir), str(old))
        print(f"  the old music/cues/ is kept as music/{old.name}/")
    cdir.mkdir(parents=True, exist_ok=True)
    meta = {}
    for slot, t in picked.items():
        shutil.copy2(lib / t["file"], cdir / f"{slot}.mp3")
        meta[f"{slot}.mp3"] = {k: t.get(k) for k in (
            "title", "mood", "desc_vi", "sound", "scenes", "energy")}
    # the descriptions travel with the files: the render reads them to give
    # each placement the track that fits its scene (pipeline/music.py)
    (cdir / "cues.json").write_text(json.dumps(meta, indent=1,
                                               ensure_ascii=False),
                                    encoding="utf-8")
    (mdir / "CREDITS_cues.md").write_text(credits_text(cat, picked, pdir.name),
                                     encoding="utf-8")
    (mdir / "library_pick.json").write_text(json.dumps(
        {k: {"title": t["title"], "file": t["file"]}
         for k, t in picked.items()}, indent=1), encoding="utf-8")
    stamp = float(now if now is not None else time.time())
    for t in picked.values():
        used[t["file"]] = stamp
    (lib / "_used.json").write_text(json.dumps(used, indent=1),
                                    encoding="utf-8")
    return picked


def ensure_cues(pdir: Path, lib: Path = LIB, say=print) -> str:
    """The render's own selection (owner, 19 Nov: "cue thì phải có phần lựa
    ... mình có một cái library"): a project whose music/cues/ is empty gets
    its cues from the library before the music is built - fetched first if
    the library lacks them, chosen by the film's own draft. Cues already in
    the project are left alone (run `pick` to replace them). Never raises: a
    failure leaves the project without cues and says why."""
    if not getattr(config, "MUSIC_LIBRARY_AUTO", True):
        return "MUSIC_LIBRARY_AUTO is off"
    if Path(pdir).name.startswith("_"):
        # self-test projects (_smoke_render, _selftest_*): never fetch or
        # touch the library's rotation from a test
        return "a self-test project - the library is not used"
    cdir = Path(pdir) / "music" / "cues"
    if cdir.is_dir() and any(p.suffix.lower() in (".mp3", ".wav", ".m4a",
                                                  ".ogg", ".flac")
                             for p in cdir.iterdir()):
        return "the project already has its cues"
    try:
        cat = load()
        need = {t["file"] for t in choose(cat, _used(lib), int(getattr(
            config, "MUSIC_LIBRARY_CUES_PER_MOOD", 3)), film_text(pdir))
            .values()}
        if any(not (lib / f).exists() for f in need):
            say("  music library: fetching the tracks this film needs")
            sub = dict(cat, tracks=[t for t in cat["tracks"]
                                    if t["file"] in need])
            _got, _had, bad = fetch(sub, lib)
            if bad:
                return (f"could not fetch {len(bad)} track(s) - no cues "
                        f"({bad[0][1]})")
        picked = pick(cat, Path(pdir), lib)
    except Exception as e:                      # the render must go on
        return f"library pick failed - no cues ({str(e)[:80]})"
    return (f"{len(picked)} cues picked from the library: " +
            ", ".join(sorted(t["title"] for t in picked.values())))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["fetch", "pick", "credits"])
    ap.add_argument("--project")
    ap.add_argument("--library", default=str(LIB))
    ns = ap.parse_args(argv)
    cat, lib = load(), Path(ns.library)
    if ns.cmd == "fetch":
        got, had, bad = fetch(cat, lib)
        print(f"music_library: {len(got)} fetched, {len(had)} already there, "
              f"{len(bad)} failed -> {lib}")
        return 2 if bad else 0
    if not ns.project:
        ap.error("--project is required")
    pdir = config.project_dir(ns.project)
    if ns.cmd == "credits":
        p = pdir / "music" / "CREDITS_cues.md"
        print(p.read_text(encoding="utf-8") if p.exists()
              else f"no {p} - run pick first")
        return 0
    try:
        picked = pick(cat, pdir, lib)
    except FileNotFoundError as e:
        print(f"music_library: {e}")
        return 2
    for k, t in sorted(picked.items()):
        print(f"  {k:9s} {t['title']}")
    print(f"music_library: {pdir.name}/music filled; the YouTube description "
          f"line is in music/CREDITS_cues.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
