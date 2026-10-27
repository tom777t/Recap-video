

"""
recap.py — turn a long video into a short, punchy recap/review video.

Workflow (the review checkpoint between 'ingest' and 'render' is REQUIRED):

  1. python recap.py ingest <url|path> --project NAME [--model small]
        download (if URL) + transcribe -> transcript.json
        then writes transcript_for_script.txt for the scripting step.

  2. >>> CHECKPOINT <<<
        Hand transcript_for_script.txt to OpenCode and have it write the recap
        narration into  projects/NAME/draft.json  (format in prompts/recap_style.md).
        Then:  python recap.py draft --project NAME    (validates + writes script.txt)
        Edit draft.json / script.txt as you like, re-run draft to re-check.

  3. python recap.py render --project NAME --voice tts   [--tts-voice VOICE]
     python recap.py render --project NAME --voice mine
        builds voiceover, cuts clips, burns captions -> final.mp4

Disk space:
  Temp files (audio16k.wav, _work/) are auto-removed after each step.
  Reclaim the rest by hand (always prompts before deleting):
    python recap.py clean --project NAME            # temp only
    python recap.py clean --project NAME --source   # + source.mp4 (asks!)
    python recap.py clean --project NAME --all      # keep only deliverables
  source.mp4 is NEVER auto-deleted; clean always asks first.

Quality:
  Keep --max-height 1080 so the recap stays crisp enough to post. Do not drop
  to 720 - upscaling a 720p source to the 1080p output looks blurry.

YouTube / pirate sites:
  YouTube needs a JS runtime: winget install DenoLand.Deno  (one time).
  Pirate/HLS sites: try  --cookies-browser chrome  and/or  --referer URL ;
  if that fails, grab the .m3u8 link via F12 > Network and pass it to ingest.
"""
from __future__ import annotations

import argparse
import sys

from rich.console import Console

import config

console = Console()


def cmd_ingest(args):
    from pipeline.download import fetch_source
    from pipeline.transcribe import transcribe
    from pipeline.draft import prepare_scripting

    fetch_source(args.source, args.project, args.max_height,
                 cookies_browser=args.cookies_browser, referer=args.referer)
    transcribe(args.project, args.model, keep_temp=args.keep_temp,
               insecure_ssl=args.insecure_ssl, translate=args.translate)
    script_in = prepare_scripting(args.project)

    console.print("\n[bold]Next: the review checkpoint.[/]")
    console.print(f"  1. Open: {script_in}")
    console.print(f"  2. Ask OpenCode to write the recap script into:")
    console.print(f"       {config.project_dir(args.project) / 'draft.json'}")
    console.print(f"     (style + JSON format: prompts/recap_style.md)")
    console.print(f"  3. Run: python recap.py draft --project {args.project}")


def cmd_frames(args):
    from pipeline import frames
    if args.zoom:
        frames.zoom(args.project, args.zoom, span=args.span)
    else:
        frames.overview(args.project, every=args.every)


def cmd_analyze(args):
    from pipeline import frames
    frames.analyze(args.project, every=args.every)


def cmd_names(args):
    from pipeline import names as namesmod
    entries, err, rejected, mode = namesmod.build(args.project, args.wiki,
                                                  write=not args.dry_run)
    if err:
        print(f"could not build names.json: {err}")
        return
    for r in rejected:
        print(f"  [skipped - not a name] {r}")
    if rejected:
        print()
    with_actor = [e for e in entries if e.get("actor")]
    if mode == "prose":
        print(f"parsed {len(with_actor)} entries from prose - this article has no")
        print("cast list, so the mapping was inferred from sentences. Word order")
        print("is a weaker signal than a list: check every pairing below.\n")
    elif mode == "list":
        print(f"parsed {len(with_actor)} entries from the cast list.\n")
    print(f"{len(entries)} name(s), {len(with_actor)} with an actor:\n")
    for e in entries:
        actor = e.get("actor")
        print(f"  {e['character']:<34}{actor or '(no actor - kept from the old file)'}")
    print()
    if args.dry_run:
        print("--dry-run: nothing written.")
    else:
        print(f"wrote {config.project_dir(args.project) / 'names.json'}")
    print("Check this against the cut you actually have - an extended cut can")
    print("carry people the article omits, and the article can list people your")
    print("cut removes.")


def cmd_verify(args):
    from pipeline import verify as verifymod
    res = verifymod.verify(args.project, model_size=args.model)
    if not isinstance(res, dict) or res.get("error"):
        sys.exit(1)
    if res["failed"] > 0:
        sys.exit(1)
    # UNMEASURED is its own exit state. Folding it into 0 would hand back a
    # green tick for lines nothing was actually established about; folding it
    # into 1 would call an unread line a defect. Neither is true, so it gets
    # its own code (matching `draft`, where 2 already means "look at this").
    if res["unmeasured"] > 0:
        console.print(f"\n[magenta]{res['unmeasured']} line(s) unmeasured - "
                      f"{res['checked']}/{res['total']} actually verified. "
                      f"(exit 2)[/]")
        sys.exit(2)


def cmd_cuts(args):
    from pipeline import cuts as cutsmod
    existing = cutsmod.load_cuts(args.project)
    if existing and not args.rescan:
        print(f"{len(existing)} cuts already cached in _cuts.json "
              f"(use --rescan to redo the ~11 minute scan)")
        return
    print("scanning source.mp4 for scene cuts (a 2h film takes ~11 minutes)...")
    got = cutsmod.detect_cuts(args.project, threshold=args.threshold)
    if got is None:
        print("could not scan: source.mp4 missing, or scenedetect not installed "
              "(pip install scenedetect)")
        return
    print(f"\ncached {len(got)} cuts -> {cutsmod.cache_path(args.project)}")
    print("`recap.py draft` will now report [SNAP-GRID].")


def cmd_broll(args):
    from pipeline import broll
    if args.scaffold:
        broll.scaffold(args.project)
    broll.summary(args.project)


def cmd_draft(args):
    from pipeline.draft import validate_draft
    result = validate_draft(args.project,
                            write_state=True,
                            promote=getattr(args, "promote", False))
    sev = (result or {}).get("_audit_severity", "clean") if isinstance(result, dict) else "clean"
    if sev == "hard":
        # Name what ACTUALLY failed. This line used to assert "[VOICE-VISUAL]
        # mismatches" for every hard severity, including runs whose own report
        # printed "Verified mismatches: 0" three lines above - a message that
        # contradicted the data it was summarising, and sent people to re-point
        # footage that was not the problem.
        r = result if isinstance(result, dict) else {}
        causes = []
        if r.get("binding_mismatch"):
            causes.append(f"{r['binding_mismatch']} [VOICE-VISUAL] mismatch(es) "
                          f"- re-point those lines' footage")
        if r.get("binding_violations"):
            causes.append(f"{r['binding_violations']} BINDING-VIOLATION(s) "
                          f"- lines exceed 1.4x shot capacity and would freeze")
        if r.get("reveal_hits"):
            causes.append(f"{r['reveal_hits']} REVEAL-TIMING hit(s) "
                          f"- a protected term appears before its landing beat")
        if not causes:
            causes.append("a hard audit finding that is NOT a binding mismatch "
                          "(binding reported 0) - read the report above for which")
        console.print("\n[red]Audit failed hard: " + "; ".join(causes) + ". (exit 1)[/]")
        sys.exit(1)
    if sev == "soft":
        console.print("\n[yellow]Audit warning: tag remaining footage / fill claims "
                      "before trusting 'clean'. (exit 2)[/]")
        console.print(f"  python recap.py render --project {args.project} --voice tts")
        sys.exit(2)
    console.print("\n[bold]Looks good.[/] Edit script.txt/draft.json if you want, then:")
    console.print(f"  python recap.py render --project {args.project} --voice tts")
    console.print(f"  python recap.py render --project {args.project} --voice mine")


def cmd_skeleton(args):
    """Validate skeleton.json schema for a project (Phase 1 coverage plan)."""
    from pipeline import schemas
    try:
        skel = schemas.load_skeleton(args.project)
    except FileNotFoundError:
        console.print(f"[yellow]No skeleton.json in projects/{args.project}/[/] "
                      f"(optional, but enables per-unit coverage checks).")
        return
    except Exception as e:
        console.print(f"[red]skeleton.json schema error:[/] {e}")
        sys.exit(1)
    total = sum(u.target_words for u in skel.units)
    wpm = config.TTS_WORDS_PER_MINUTE
    console.print(f"[green]skeleton.json valid[/] — {len(skel.units)} units, "
                  f"declared runtime {skel.predicted_runtime_min} min")
    console.print(f"  total target words: {total}  (~{total/wpm:.1f} min at {wpm} WPM)")
    for u in skel.units:
        console.print(f"  {u.id} [{u.tier:<8}] {u.target_words:>4}w  "
                      f"must_cover={len(u.must_cover)}  {u.label}")


def cmd_render(args):
    from pipeline.draft import validate_draft
    from pipeline.tts import generate_tts, collect_mine
    from pipeline.render import render
    from pipeline.download import fetch_music

    draft = validate_draft(args.project)  # re-validate so render is always safe

    # The draft audit's findings have to reach the render too, not just
    # `recap.py draft`: a draft carrying 17 [BINDING-VIOLATION]s rendered
    # anyway and died in the clip loop much later.
    #
    # But only the findings that actually BREAK a render may block it. A
    # [VOICE-VISUAL] mismatch means the footage may not match the words - a
    # quality finding, already reported at draft time, and not a reason the
    # encode will fail. Blocking on it would stop every render of this project
    # over 86 pre-existing mismatches and teach everyone to pass
    # --ignore-audit, which is how a gate becomes decoration.
    _r = draft if isinstance(draft, dict) else {}
    _fatal = []
    if _r.get("binding_violations"):
        from pipeline.schemas import BINDING_SLOWDOWN_MAX as _SM
        _fatal.append(f"{_r['binding_violations']} BINDING-VIOLATION(s) - "
                      f"line(s) exceed {_SM:.2f}x shot capacity and would "
                      f"freeze")
    if _r.get("reveal_hits"):
        _fatal.append(f"{_r['reveal_hits']} REVEAL-TIMING hit(s) - a protected "
                      f"term appears before its landing beat")
    if _fatal and not args.ignore_audit:
        console.print("[red]Refusing to render: " + "; ".join(_fatal) + ".[/]")
        console.print(f"  See `python recap.py draft --project {args.project}`. "
                      f"For capacity, `python tools/fit_narration.py --project "
                      f"{args.project} --apply` resolves them in one pass.")
        console.print("  --ignore-audit renders anyway.")
        sys.exit(1)
    if _r.get("_audit_severity") == "hard" and not _fatal:
        console.print(
            f"[yellow]Draft audit is HARD but nothing in it stops a render[/] "
            f"(binding mismatches: {_r.get('binding_mismatch', '?')}). "
            f"Rendering. Fix them before publishing - see `recap.py draft`.")

    if args.voice == "tts":
        from pipeline.tts import VoiceUnavailable
        try:
            narration = generate_tts(args.project, draft,
                                     voice=args.tts_voice, rate=args.tts_rate,
                                     allow_edge=args.allow_edge)
        except VoiceUnavailable as e:
            console.print(f"[red]VOICE: {e}[/]")
            sys.exit(1)
    else:
        narration = collect_mine(args.project, draft)

    music = None
    if args.music:
        music = fetch_music(args.music, args.project)
    else:
        # Auto-discover projects/<project>/music.mp3 (or .m4a/.wav/.ogg) so the
        # music bed is applied WITHOUT needing an explicit --music flag. This
        # avoids the silent-no-music footgun: previously, omitting --music meant
        # render did a voice-only encode and never mixed the music bed/swell.
        pdir = config.project_dir(args.project)
        for name in ("music.mp3", "music.m4a", "music.wav", "music.ogg"):
            cand = pdir / name
            if cand.exists():
                music = cand
                console.print(f"[dim]Auto-using music bed: {cand.name} "
                              f"(pass --music to override, or delete it to render voice-only).[/]")
                break
        if music is None:
            console.print("[yellow]No --music and no music.* in the project dir - "
                          "rendering VOICE-ONLY (no background music).[/]")

    # captions: default from config (OFF), opt in with --captions, off with
    # --no-captions (explicit override wins).
    if args.captions:
        use_caps = True
    elif args.no_captions:
        use_caps = False
    else:
        use_caps = config.DEFAULT_CAPTIONS

    render(args.project, draft, narration, music=music,
           captions=use_caps, keep_temp=args.keep_temp,
           force_clips=args.force_clips)


def cmd_package(args):
    from pipeline import package
    package.make_thumbnail(args.project, args.at, args.thumb_text, sub=args.sub)
    package.write_titles(args.project)


def cmd_clean(args):
    from pipeline import cleanup
    if args.all_projects:
        cleanup.clean_all_projects(source=args.source, all_=args.all,
                                   auto_yes=args.yes, frames=args.frames)
    else:
        if not args.project:
            console.print("[red]Provide --project NAME or use --all-projects.[/]")
            sys.exit(1)
        cleanup.clean_project(args.project, source=args.source, all_=args.all,
                              auto_yes=args.yes, frames=args.frames)


def cmd_voices(args):
    """List a few recommended Edge-TTS English voices."""
    console.print("[bold]Recommended Edge-TTS English voices:[/]")
    for v, d in [
        ("en-US-AndrewMultilingualNeural", "warm, natural male (default)"),
        ("en-US-AvaMultilingualNeural", "natural, expressive female"),
        ("en-US-GuyNeural", "confident male, good for trailers"),
        ("en-US-AriaNeural", "clear female news-style"),
        ("en-GB-RyanNeural", "British male"),
        ("en-GB-SoniaNeural", "British female"),
    ]:
        console.print(f"  {v:<34} {d}")
    console.print("\nFull list: run  python -m edge_tts --list-voices")


def main():
    p = argparse.ArgumentParser(prog="recap.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest", help="download + transcribe")
    pi.add_argument("source", help="URL or local path to the source video")
    pi.add_argument("--project", required=True, help="project name (folder)")
    pi.add_argument("--model", default=config.DEFAULT_WHISPER_MODEL,
                    choices=["tiny", "base", "small", "medium", "large", "large-v3"],
                    help="whisper model size (speed vs accuracy)")
    pi.add_argument("--max-height", type=int, default=1080,
                    help="cap download resolution (default 1080; keep 1080 for "
                         "post-quality recaps - do NOT go to 720)")
    pi.add_argument("--keep-temp", action="store_true",
                    help="keep audio16k.wav after transcription (debugging)")
    pi.add_argument("--cookies-browser", default=None,
                    help="send cookies from a browser (chrome/edge/firefox/brave) "
                         "for login-walled or pirate sites")
    pi.add_argument("--referer", default=None,
                    help="override the Referer header (helps hotlink-protected HLS)")
    pi.add_argument("--insecure-ssl", action="store_true",
                    help="skip TLS verification for the one-time Whisper model "
                         "download (use on school/company networks that inspect "
                         "HTTPS; does not affect the video or output)")
    pi.add_argument("--translate", action="store_true",
                    help="translate foreign speech to English (use 'small' or "
                         "'medium' model for accuracy on non-English films)")
    pi.set_defaults(func=cmd_ingest)

    pf = sub.add_parser("frames", help="sample frames so the script matches the footage")
    pf.add_argument("--project", required=True)
    pf.add_argument("--every", type=float, default=5.0,
                    help="overview: 1 frame every N seconds (default 5)")
    pf.add_argument("--zoom", default=None,
                    help="dense burst around a timestamp HH:MM:SS instead of overview")
    pf.add_argument("--span", type=float, default=6.0,
                    help="zoom window length in seconds (default 6)")
    pf.set_defaults(func=cmd_frames)

    pa = sub.add_parser("analyze", help="measure action vs dialogue, recommend ratio")
    pa.add_argument("--project", required=True)
    pa.add_argument("--every", type=float, default=5.0)
    pa.set_defaults(func=cmd_analyze)

    pnm = sub.add_parser("names", help="build names.json from the Wikipedia Cast section")
    pnm.add_argument("--project", required=True)
    pnm.add_argument("--wiki", required=True,
                     help="Wikipedia URL or page title, e.g. 'Shutter Island (film)'")
    pnm.add_argument("--dry-run", action="store_true", help="print, do not write")
    pnm.set_defaults(func=cmd_names)

    pvf = sub.add_parser("verify",
                         help="transcribe final.mp4 and check it says what draft.json says")
    pvf.add_argument("--project", required=True)
    pvf.add_argument("--model", default="small", help="whisper model for the check")
    pvf.set_defaults(func=cmd_verify)

    pcu = sub.add_parser("cuts", help="detect scene cuts once, cache them for SNAP-GRID")
    pcu.add_argument("--project", required=True)
    pcu.add_argument("--rescan", action="store_true", help="redo the scan even if cached")
    pcu.add_argument("--threshold", type=float, default=27.0,
                     help="ContentDetector sensitivity; lower finds more cuts")
    pcu.set_defaults(func=cmd_cuts)

    pb = sub.add_parser("broll", help="create/inspect the action B-roll pool")
    pb.add_argument("--project", required=True)
    pb.add_argument("--scaffold", action="store_true", help="write a starter broll.json")
    pb.set_defaults(func=cmd_broll)

    pk = sub.add_parser("skeleton", help="validate skeleton.json (Phase 1 coverage plan)")
    pk.add_argument("--project", required=True)
    pk.set_defaults(func=cmd_skeleton)

    pd = sub.add_parser("draft", help="validate draft.json + write script.txt")
    pd.add_argument("--project", required=True)
    pd.add_argument("--promote", action="store_true",
                    help="If the outline passes coverage/binding, enter SCRIPT "
                         "stage (enables DRAFT-TARGET). Linear projects; one-way.")
    pd.set_defaults(func=cmd_draft)

    pr = sub.add_parser("render", help="voiceover + cut + captions -> final.mp4")
    pr.add_argument("--project", required=True)
    pr.add_argument("--voice", choices=["tts", "mine"], required=True)
    pr.add_argument("--tts-voice", default=config.DEFAULT_TTS_VOICE)
    pr.add_argument("--tts-rate", default=config.DEFAULT_TTS_RATE)
    pr.add_argument("--ignore-audit", action="store_true",
                    help="render even though the draft audit failed hard "
                         "(binding violations, reveal leaks). For diagnosis "
                         "only - the render will likely fail or ship a defect.")
    pr.add_argument("--allow-edge", action="store_true",
                    help="narrate on the Edge fallback voice when the "
                         "production voice (Inworld) is unavailable. Without "
                         "this flag a missing INWORLD_API_KEY is a STOP, not a "
                         "silent downgrade to a voice that cannot act.")
    pr.add_argument("--music", default=None,
                    help="background music: a URL (downloaded) or local file path")
    pr.add_argument("--captions", action="store_true",
                    help="burn in animated captions (default off)")
    pr.add_argument("--no-captions", action="store_true",
                    help="do not burn subtitles into the video")
    pr.add_argument("--force-clips", action="store_true",
                    help="rebuild all clips, ignoring the clip cache")
    pr.add_argument("--keep-temp", action="store_true",
                    help="keep the _work/ intermediate clips after rendering")
    pr.set_defaults(func=cmd_render)

    pp = sub.add_parser("package", help="make a thumbnail + title options")
    pp.add_argument("--project", required=True)
    pp.add_argument("--at", required=True, help="timestamp for thumbnail frame HH:MM:SS")
    pp.add_argument("--thumb-text", required=True, help="headline text for the thumbnail")
    pp.add_argument("--sub", default=None, help="optional smaller sub-text")
    pp.set_defaults(func=cmd_package)

    pc = sub.add_parser("clean", help="reclaim disk space (always asks first)")
    pc.add_argument("--project", default=None, help="project to clean")
    pc.add_argument("--all-projects", action="store_true",
                    help="clean every project under projects/")
    pc.add_argument("--source", action="store_true",
                    help="also remove source.mp4 (the big 2-3h file; confirmed)")
    pc.add_argument("--all", action="store_true",
                    help="remove everything except final.mp4 + transcript/draft/"
                         "script/thumbnail/titles/narration")
    pc.add_argument("--frames", action="store_true",
                    help="also remove the frames/ montage JPGs (regenerable)")
    pc.add_argument("--yes", action="store_true",
                    help="skip the y/N prompt (source.mp4 is still printed loudly)")
    pc.set_defaults(func=cmd_clean)

    pv = sub.add_parser("voices", help="list recommended TTS voices")
    pv.set_defaults(func=cmd_voices)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()



