"""Get the source video into the project as source.mp4 (URL or local file)."""
from __future__ import annotations

import shutil
import subprocess
import sys
from urllib.parse import urlsplit
from pathlib import Path

from rich.console import Console

import config

console = Console()


def _is_url(s: str) -> bool:
    return s.lower().startswith(("http://", "https://", "www."))


def _is_youtube(url: str) -> bool:
    host = urlsplit(url if "//" in url else "https://" + url).netloc.lower()
    return any(h in host for h in ("youtube.com", "youtu.be", "youtube-nocookie.com"))


def _origin_referer(url: str) -> str:
    """Best-effort 'https://host/' to use as a Referer for hotlink-protected sites."""
    parts = urlsplit(url if "//" in url else "https://" + url)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}/"
    return ""


def fetch_source(source: str, project: str, max_height: int = 1080,
                 cookies_browser: str | None = None,
                 referer: str | None = None) -> Path:
    """
    Resolve `source` (URL or local path) into <project>/source.mp4.
    Returns the path to the source video.

    cookies_browser : pass a browser name (chrome/edge/firefox/brave) to send
                      its cookies — needed by many login-walled / pirate sites.
    referer         : override the Referer header (defaults to the URL's origin)
                      to get past hotlink protection on HLS/.m3u8 streams.
    """
    pdir = config.ensure_project(project)
    dest = pdir / "source.mp4"

    if dest.exists():
        console.print(f"[yellow]source.mp4 already exists[/], reusing: {dest}")
        return dest

    if _is_url(source):
        return _download_url(source, dest, max_height,
                             cookies_browser=cookies_browser, referer=referer)
    else:
        return _copy_local(source, dest)


def _copy_local(path_str: str, dest: Path) -> Path:
    src = Path(path_str).expanduser()
    if not src.exists():
        console.print(f"[red]Local file not found:[/] {src}")
        sys.exit(1)
    console.print(f"Copying local file -> {dest.name}")
    shutil.copy2(src, dest)
    return dest


def fetch_music(source: str, project: str) -> Path:
    """
    Resolve a music source (URL or local path) into <project>/music.<ext>.
    For URLs, downloads best audio via yt-dlp and converts to mp3.
    Returns the path to the music file.
    """
    pdir = config.ensure_project(project)

    if not _is_url(source):
        src = Path(source).expanduser()
        if not src.exists():
            console.print(f"[red]Music file not found:[/] {src}")
            sys.exit(1)
        dest = pdir / ("music" + src.suffix.lower())
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)
        console.print(f"Using music: {dest.name}")
        return dest

    dest = pdir / "music.mp3"
    if dest.exists():
        console.print(f"[yellow]music.mp3 already exists[/], reusing.")
        return dest

    console.print(f"[cyan]Downloading music audio[/] {source}")
    ytdlp_exe = config.yt_dlp()
    args = [
        "-f", "bestaudio/best",
        "-x", "--audio-format", "mp3", "--audio-quality", "0",
        "-o", str(pdir / "music.%(ext)s"),
        "--no-playlist", source,
    ]
    cmd = ([ytdlp_exe] + args) if ytdlp_exe else ([sys.executable, "-m", "yt_dlp"] + args)
    if subprocess.run(cmd).returncode != 0:
        console.print("[red]Music download failed.[/]")
        sys.exit(1)
    if dest.exists():
        return dest
    cand = sorted(pdir.glob("music.*"))
    cand = [c for c in cand if c.suffix.lower() in (".mp3", ".m4a", ".opus", ".webm", ".wav")]
    if cand:
        return cand[0]
    console.print("[red]Music download produced no file.[/]")
    sys.exit(1)


def _has_deno() -> bool:
    """yt-dlp needs a JS runtime (deno) to fully extract modern YouTube."""
    if shutil.which("deno"):
        return True
    try:
        config.find_tool("deno")  # also checks ./bin and the winget store
        return True
    except FileNotFoundError:
        return False


def _ytdlp_base() -> list[str]:
    exe = config.yt_dlp()
    return [exe] if exe else [sys.executable, "-m", "yt_dlp"]


def _normalise_output(dest: Path) -> Path | None:
    """yt-dlp may write source.mp4 or source.<ext>; return the final source.mp4."""
    if dest.exists():
        return dest
    cand = sorted(dest.parent.glob(dest.stem + ".*"))
    cand = [c for c in cand if c.suffix.lower() in
            (".mp4", ".mkv", ".webm", ".m4v", ".mov")]
    if cand:
        cand[0].rename(dest)
        return dest
    return None


def _download_url(url: str, dest: Path, max_height: int = 1080,
                  cookies_browser: str | None = None,
                  referer: str | None = None) -> Path:
    console.print(f"[cyan]Downloading[/] {url}  (cap {max_height}p, target 1080p quality)")

    is_yt = _is_youtube(url)
    if is_yt and not _has_deno():
        console.print(
            "[yellow]Heads up:[/] no [bold]deno[/] JS runtime found. Modern YouTube "
            "needs it for full 1080p formats.\n"
            "  Install once:  [bold]winget install DenoLand.Deno[/]\n"
            "  or drop deno.exe into:  " + str(config.BIN_DIR) + "\n"
            "  Trying anyway with a fallback format (may be lower quality).\n"
        )

    # Prefer a single mp4 (h264+aac) capped to max_height so render stays 1080p.
    fmt = (
        f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/"
        f"best[height<={max_height}][ext=mp4]/"
        f"best[height<={max_height}]/best"
    )
    out_tmpl = str(dest.with_suffix("")) + ".%(ext)s"

    # Common args shared by every attempt.
    common = [
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        "--no-playlist",
    ]
    if cookies_browser:
        common += ["--cookies-from-browser", cookies_browser]
        console.print(f"[dim]Using cookies from browser: {cookies_browser}[/]")

    # Referer helps hotlink-protected HLS streams on pirate sites.
    ref = referer or (_origin_referer(url) if not is_yt else None)
    if ref:
        common += ["--add-header", f"Referer: {ref}"]
        console.print(f"[dim]Using Referer: {ref}[/]")

    base_args = ["-f", fmt] + common + [url]
    proc = subprocess.run(_ytdlp_base() + base_args)

    if proc.returncode == 0 and _normalise_output(dest):
        return dest

    # ---- Fallback: looser format selection (e.g. YouTube w/o deno, or odd HLS).
    console.print("[yellow]First attempt didn't produce a file. Retrying with a "
                  "looser format selector...[/]")
    fallback_fmt = f"best[height<={max_height}]/best"
    fb_args = ["-f", fallback_fmt] + common + [url]
    proc = subprocess.run(_ytdlp_base() + fb_args)

    if proc.returncode == 0 and _normalise_output(dest):
        return dest

    # ---- Give up with an actionable message. -------------------------------
    console.print("\n[red]yt-dlp could not download this URL.[/]")
    if is_yt:
        console.print(
            "  YouTube: most likely the missing JS runtime. Install deno and retry:\n"
            "    [bold]winget install DenoLand.Deno[/]\n"
        )
    else:
        host = urlsplit(url if "//" in url else "https://" + url).netloc
        console.print(
            f"  Pirate/streaming site ([bold]{host}[/]) tips, try in order:\n"
            f"    1. add your browser session:  --cookies-browser chrome\n"
            f"    2. set a referer:             --referer \"{_origin_referer(url)}\"\n"
            f"    3. grab the real stream link manually:\n"
            f"       open the page > F12 > Network tab > filter '.m3u8'\n"
            f"       copy that .m3u8 URL and pass IT to  recap.py ingest  instead.\n"
        )
    sys.exit(1)
