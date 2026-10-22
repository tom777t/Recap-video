

"""
The semi-auto checkpoint.

`prepare_scripting`  -> writes transcript_for_script.txt (a clean, timestamped
                        transcript) so you can hand it to OpenCode to write the
                        recap narration into draft.json.

`validate_draft`     -> reads your (hand-or-LLM-edited) draft.json, checks every
                        field, and writes the readable script.txt. The render
                        step refuses to run until this passes.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from pathlib import Path

from rich.console import Console

import config
from pipeline import reviewed as _reviewed

console = Console()


def _fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def prepare_scripting(project: str) -> Path:
    """Write a clean timestamped transcript for the scripting step."""
    pdir = config.project_dir(project)
    tj = pdir / "transcript.json"
    if not tj.exists():
        console.print(f"[red]No transcript.json. Run ingest first.[/]")
        sys.exit(1)

    data = json.loads(tj.read_text(encoding="utf-8-sig"))
    lines = [
        f"# Transcript for scripting — project: {project}",
        f"# duration: {data.get('duration', 0)/60:.1f} min   language: {data.get('language')}",
        f"# Hand this whole file to OpenCode and ask it to write the recap script.",
        "",
    ]
    for seg in data["segments"]:
        lines.append(f"[{_fmt_ts(seg['start'])} -> {_fmt_ts(seg['end'])}] {seg['text']}")

    out = pdir / "transcript_for_script.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def parse_ts(ts: str) -> float:
    """Accept HH:MM:SS(.mmm) or MM:SS(.mmm) or plain seconds -> float seconds."""
    ts = str(ts).strip()
    if ":" not in ts:
        return float(ts)
    parts = ts.split(":")
    parts = [float(p) for p in parts]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts[-3], parts[-2], parts[-1]
    return h * 3600 + m * 60 + s


def validate_draft(project: str, *, write_state: bool = False,
                   promote: bool = False) -> dict:
    """Validate draft.json and (re)write script.txt. Exit non-zero on problems."""
    pdir = config.project_dir(project)
    df = pdir / "draft.json"
    if not df.exists():
        console.print(
            f"[red]No draft.json found in {pdir}[/]\n"
            f"Create it from the transcript first (see the scripting step)."
        )
        sys.exit(1)

    try:
        # utf-8-sig tolerates a BOM (common from Windows editors / PowerShell)
        draft = json.loads(df.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        console.print(f"[red]draft.json is not valid JSON:[/] {e}")
        sys.exit(1)

    if "lines" not in draft or not isinstance(draft["lines"], list) or not draft["lines"]:
        console.print("[red]draft.json must have a non-empty 'lines' array.[/]")
        sys.exit(1)

    # source duration for bounds checking
    tj = pdir / "transcript.json"
    src_dur = 0.0
    if tj.exists():
        src_dur = json.loads(tj.read_text(encoding="utf-8-sig")).get("duration", 0.0)

    # load pool meta (if any) so 'pool' lines validate + reuse can be capped
    pool_meta = {}
    bp = pdir / "broll.json"
    if bp.exists():
        try:
            bd = json.loads(bp.read_text(encoding="utf-8-sig"))
            pool_meta = bd.get("pool", bd)
        except Exception:
            pass
    pool_labels = set(pool_meta.keys())

    errors: list[str] = []
    total_words = 0
    pool_uses: dict = {}              # label -> count
    visual_uses: dict = {}            # explicit 'visual' family -> [line ids]
    explicit_times: list = []         # (line id, source seconds, visual tag)
    for i, ln in enumerate(draft["lines"], 1):
        where = f"line #{ln.get('id', i)}"
        # Gap 3 / S9 silence exception: a silence line (narration_silence_seconds)
        # is a deliberate held visual with NO narration (C1 exception). It is
        # exempt from the empty-narration requirement; every other line must
        # carry narration.
        # NOTE (2026-09-05): the empty-narration condition used to be reported
        # HERE, unlabelled, as "line #N: empty 'narration'". That message hit the
        # `if errors:` abort below, which meant the labelled [EMPTY-LINE] block
        # further down could never run - it was dead code shadowed by a
        # duplicate check, and a positive test (tools/gate_selftest.py) proved
        # it. The check now lives in ONE place: the labelled block, moved above
        # the abort. Do not reintroduce a second copy here.
        is_silence = ln.get("narration_silence_seconds") is not None
        if ln.get("visual") and not ln.get("pool") and not ln.get("montage"):
            visual_uses.setdefault(ln["visual"], []).append(ln.get("id", i))

        if ln.get("montage"):
            if not isinstance(ln["montage"], list) or len(ln["montage"]) < 2:
                errors.append(f"{where}: 'montage' must list 2+ shots")
            _m2_sum = 0.0          # Mức 2: sum of inline play_durations (if any)
            _m2_has_pd = False
            for lab in ln.get("montage", []):
                # Mức 1: a montage entry may be an INLINE timestamp segment
                # (dict {clip_start, clip_end} or [start, end]) for projects with
                # no broll.json. Validate its timestamps instead of a pool label.
                # Mức 2: a dict entry may carry an optional positive play_duration.
                if isinstance(lab, dict):
                    if not lab.get("clip_start") or not lab.get("clip_end"):
                        errors.append(f"{where}: inline montage segment needs clip_start/clip_end")
                    pd = lab.get("play_duration")
                    if pd is not None:
                        _m2_has_pd = True
                        try:
                            pdf = float(pd)
                            if pdf <= 0:
                                errors.append(f"{where}: montage play_duration must be > 0")
                            else:
                                _m2_sum += pdf
                        except (TypeError, ValueError):
                            errors.append(f"{where}: montage play_duration must be a number")
                elif isinstance(lab, (list, tuple)):
                    if len(lab) != 2:
                        errors.append(f"{where}: inline montage segment must be [start, end]")
                elif lab not in pool_labels:
                    errors.append(f"{where}: montage label '{lab}' unknown")
                else:
                    pool_uses[lab] = pool_uses.get(lab, 0) + 1
            # Mức 2: if total_visual_duration is declared, it must match the sum
            # of the per-shot play_durations (when those are given).
            tvd = ln.get("total_visual_duration")
            if tvd is not None and _m2_has_pd:
                try:
                    if abs(float(tvd) - _m2_sum) > 0.05:
                        errors.append(
                            f"{where}: total_visual_duration {tvd} != sum of "
                            f"play_durations {_m2_sum:.2f}")
                except (TypeError, ValueError):
                    errors.append(f"{where}: total_visual_duration must be a number")
        elif ln.get("pool"):
            # pool-sourced line: label must exist
            if ln["pool"] not in pool_labels:
                errors.append(f"{where}: unknown pool label '{ln['pool']}'")
            else:
                pool_uses[ln["pool"]] = pool_uses.get(ln["pool"], 0) + 1
        else:
            # explicit-timestamp line
            for key in ("clip_start", "clip_end"):
                if key not in ln:
                    errors.append(f"{where}: missing '{key}' (or add a 'pool' label)")
            if "clip_start" in ln and "clip_end" in ln:
                try:
                    a = parse_ts(ln["clip_start"])
                    b = parse_ts(ln["clip_end"])
                except ValueError:
                    errors.append(f"{where}: bad timestamp format")
                    total_words += len(ln.get("narration", "").split())
                    continue
                if b <= a:
                    errors.append(f"{where}: clip_end <= clip_start ({ln['clip_start']} -> {ln['clip_end']})")
                if src_dur and (a > src_dur + 1 or b > src_dur + 1):
                    errors.append(f"{where}: clip beyond source duration ({src_dur:.1f}s)")
                explicit_times.append((ln.get("id", i), a, ln.get("visual")))
        total_words += len(ln.get("narration", "").split())

    # reuse-cap enforcement: per-label (normal/hero) AND per visual family.
    for label, count in pool_uses.items():
        is_hero = bool(pool_meta.get(label, {}).get("hero"))
        cap = config.MAX_REUSE_HERO if is_hero else config.MAX_REUSE
        if count > cap:
            kind = "hero" if is_hero else "normal"
            errors.append(f"shot '{label}' used {count}x exceeds {kind} cap of {cap} "
                          f"(spread these lines to other shots or dialogue)")

    # [VISUAL-REPEAT]: unified family cap across pool 'family' + explicit 'visual'.
    fam_uses: dict = {}
    fam_lines: dict = {}
    for label, count in pool_uses.items():
        fam = pool_meta.get(label, {}).get("family")
        if fam:
            fam_uses[fam] = fam_uses.get(fam, 0) + count
            fam_lines.setdefault(fam, []).append(f"pool:{label}")
    for vfam, ids in visual_uses.items():
        fam_uses[vfam] = fam_uses.get(vfam, 0) + len(ids)
        fam_lines.setdefault(vfam, []).extend(f"line {i}" for i in ids)

    # NOT WIRED, and deliberately so (tried and reverted 2026-09-05).
    # `family` on shots.json entries was fed into this counter for one session.
    # It is the wrong input, because the word means two different things:
    #   broll.json pool `family`  = interchangeable B-ROLL ALTERNATES. Showing
    #       three members in a row really does read as "I just saw this", which
    #       is what cap=2 was calibrated for.
    #   shots.json `family`       = a SCENE / LOCATION label. superbad2007 has
    #       69 of them over 183 shots. Binding 8 lines to 8 different shots of
    #       cop_car_night is not repetition, it is covering the film's B-plot.
    # Wiring it flagged 22 families on superbad2007 alone - a shipped, watched
    # film - at up to 8x. That is the gate mis-measuring, not the recap being
    # repetitive. See docs/GATE_CANDIDATES.md L-FAMILY-SEMANTICS.
    # If this is ever revisited it needs its OWN cap and probably its own gate
    # name, not this counter.

    _revd, _revd_bad = _reviewed.load(pdir)
    for _b in _revd_bad:
        console.print(f"[red][REVIEWED-EXCEPTION][/] malformed entry - {_b}")
    _revd_hit = set()

    # ---- [SET-PIECE-DECLARE] + [RATCHET] --------------------------------
    # Absence must be a DECISION. SET-PIECE was a silent no-op on 14 of 17
    # projects because no fenced block existed - indistinguishable in effect
    # from the strongest possible gaming, achieved by doing nothing. Follows
    # the G2 precedent: Bad Genius recorded "AMBIGUITY-HOLD: none in this film"
    # rather than skipping it, so the negative is on the record.
    try:
        _sp_list = parse_set_pieces(project)
        _rm_list = parse_reveal_map(project)
        _bp = pdir / "beats_proposal.md"
        _bp_txt = _bp.read_text(encoding="utf-8-sig") if _bp.exists() else ""

        # ---- [STYLE-DECLARE] ---------------------------------------------
        # `style:` decides which half of the pipeline inspects this project,
        # and it was declared on 6 of 17. The other 11 defaulted to `review` by
        # absence - switching off BEAT-COVERAGE, BINDING-INTEGRITY, SNAP-GRID,
        # CATALOGUE-DENSITY and the stage machine across 44 of 204 matrix
        # cells, chosen by nobody. Same silent-default shape as
        # SET-PIECE-DECLARE and PROJECT-STATUS, one layer further up.
        # `style: review` is a perfectly good answer - it just has to be an
        # answer.
        # The sniff regex MUST match catalogue.parse_beats' own `[a-z_]+`
        # class. An earlier `\w` version accepted `style: 2linear`, which
        # silenced this warning while parse_beats still returned "review" -
        # a gate whose name and whose check disagreed, which is the exact
        # defect this audit has been removing elsewhere.
        if _bp_txt and not re.search(r"^\s*style\s*:\s*[a-z_]+",
                                     _bp_txt, re.M | re.I):
            console.print(
                "[yellow][STYLE-DECLARE][/] no `style:` line - defaulting to "
                "[bold]review[/]. That default switches OFF: BEAT-COVERAGE, "
                "BEAT-MAP, BINDING-INTEGRITY, CATALOGUE-DENSITY, SNAP-GRID, "
                "SET-PIECE coverage, REVEAL-TIMING, and the OUTLINE/SCRIPT "
                "stage machine (so DRAFT-TARGET is never stage-gated and "
                "promotion is unreachable). It switches ON the stricter "
                "per-line ACTION-SETUP. If review is right, say so: "
                "`style: review`. If it is linear, say that.")

        # ---- [PROJECT-STATUS] -------------------------------------------
        # No beats_proposal.md means SET-PIECE-DECLARE, RATCHET and the whole
        # DEPTH-* family are no-ops BY ABSENCE - the same failure one layer up.
        # Absence becomes a decision on the record (the G2 precedent), and the
        # gate names WHICH case this is rather than lumping them together:
        # a project with no source video cannot be worked on at all; one with a
        # source is merely incomplete. Note that a beat map is NOT linear-only -
        # review-mode projects carry them too (gonegirl 36 beats, joker 38,
        # parasite 28), so "review mode" is not an excuse for not having one.
        if not _bp_txt:
            _psf = pdir / "project_status.md"
            _declared_status = False
            if _psf.exists():
                _pst = _psf.read_text(encoding="utf-8-sig")
                _declared_status = bool(re.search(
                    r"```project-status\s*\n(?=(?:.*\n)*?\s*status\s*:\s*\S)"
                    r"(?=(?:.*\n)*?\s*reason\s*:\s*\S)", _pst, re.I))
            if not _declared_status:
                _has_src = any((pdir / f"source{e}").exists()
                               for e in (".mp4", ".mkv", ".mov", ".m4v")) or \
                    bool(list(pdir.glob("source.*")))
                if _has_src:
                    _case = ("a source video is present but there is no beat "
                             "map - this project is INCOMPLETE, not impossible")
                else:
                    _case = ("there is no beat map and no source video - this "
                             "project cannot be worked on as it stands")
                console.print(
                    f"[yellow][PROJECT-STATUS][/] {_case}. SET-PIECE-DECLARE, "
                    f"RATCHET and every DEPTH-* gate are no-ops here by "
                    f"absence. Declare it in project_status.md: a "
                    f"```project-status``` block with status / mode / reason.")
        _declared_none = bool(re.search(r"^\s*set-pieces\s*:\s*none\s*,\s*because\s+\S",
                                        _bp_txt, re.M | re.I))
        if _bp_txt and not _sp_list and not _declared_none:
            _has_fence = bool(re.search(r"```set-pieces", _bp_txt, re.I))
            _why = ("a ```set-pieces``` block is present but parses to ZERO "
                    "measurable rows, which is the same as having none"
                    if _has_fence else
                    "there is no ```set-pieces``` block and no explicit negative")
            console.print(
                f"[yellow][SET-PIECE-DECLARE][/] {_why}. SET-PIECE cannot "
                f"measure anything here, and silence is indistinguishable from "
                f"having none. State it: `set-pieces: none, because <reason>` "
                f"- or fix the block.")
        # Ratchet: pin at promotion; also pin on first sight so existing
        # projects acquire a baseline instead of being exempt forever.
        from pipeline import state as _rstate
        from pipeline import ratchet as _ratchet
        from pipeline import catalogue as _catr
        _nbeats = len([b for b in _catr.parse_beats(project).get("beats", [])
                       if re.match(r"^B\d+$", str(b.get("id", "")))])
        _cur = _ratchet.snapshot(_nbeats, _rm_list, _sp_list)
        _rst = _rstate.load_state(project) or {}
        _pin = _rst.get("ratchet")
        if _pin is None:
            if _cur["beats"] or _cur["reveals"] or _cur["set_pieces"]:
                _rst["ratchet"] = _cur
                _rstate.save_state(project, _rst)
        else:
            for _k, _m in _ratchet.compare(_pin, _cur):
                _exc = _revd.get(("RATCHET", _k))
                if _exc:
                    _revd_hit.add(("RATCHET", _k))
                    console.print(f"[yellow][RATCHET][/] {_m}  "
                                  f"[bold]REVIEWED {_exc[0]}[/]: {_exc[1]}")
                else:
                    console.print(f"[yellow][RATCHET][/] {_m} "
                                  f"[dim](finding key: {_k})[/]")
    except Exception as _e:                              # pragma: no cover
        console.print(f"[dim][RATCHET] skipped: {_e}[/]")
    for fam, count in fam_uses.items():
        if count > config.MAX_FAMILY_USES:
            where_list = ", ".join(fam_lines.get(fam, []))
            msg = (f"[VISUAL-REPEAT] visual family '{fam}' shown {count}x exceeds "
                   f"cap of {config.MAX_FAMILY_USES} ({where_list}) - a viewer feels "
                   f"they just saw this. Re-point extra lines to other footage, or "
                   f"split into distinct stages (setup/reversal/outcome).")
            _exc = _revd.get(("VISUAL-REPEAT", fam))
            if _exc:
                # Still printed, still visible in the run - just not fatal.
                _revd_hit.add(("VISUAL-REPEAT", fam))
                console.print(f"[yellow][VISUAL-REPEAT][/] visual family '{fam}' "
                              f"shown {count}x ({where_list}) - "
                              f"[bold]REVIEWED {_exc[0]}[/]: {_exc[1]}")
            else:
                errors.append(msg)
    # A stale exception is how a gate dies quietly in the other direction: the
    # finding goes away, the note stays, and it silently covers the next one.
    for (_g, _k), (_d, _r) in _revd.items():
        if _g == "VISUAL-REPEAT" and (_g, _k) not in _revd_hit:
            console.print(f"[yellow][REVIEWED-EXCEPTION][/] STALE - "
                          f"{_g} '{_k}' (reviewed {_d}) no longer occurs; "
                          f"delete the entry so it cannot cover a future finding.")

    # [EMPTY-LINE] - moved ABOVE the abort on 2026-09-05. It used to sit ~20
    # lines below and was unreachable: an unlabelled duplicate of this same
    # check ran first and tripped `if errors:`. Keeping it here means the
    # labelled message with the S9 exemption is the one an author actually sees.
    # A SILENCE line (Gap 3) is deliberately wordless: it carries
    # `narration_silence_seconds`, and render.py holds the visual for that long
    # with the music swelling. That is a feature, not a blank line - the first
    # version of this gate hard-failed three of four finished films for using it.
    _blank = [ln for ln in draft["lines"]
              if ln.get("clip_start")
              and not (ln.get("narration") or "").strip()
              and not ln.get("narration_silence_seconds")]
    if _blank:
        console.print("[red][EMPTY-LINE][/] line(s) with a clip window but no narration:")
        for ln in _blank:
            console.print(f"    line {ln.get('id')} at {ln.get('clip_start')}")
        console.print("[red]  Write the line or remove it. Rendering as-is puts "
                      "footage on screen with nothing said over it.[/]")
        sys.exit(1)

    # ---- [TITLE-MATCH] ---------------------------------------------------
    # 2026-09-11: tokyodrift2006/script.txt in ra "TITLE: Bad Genius (2017)".
    # Tieu de duoc chep sang tu mot project khac va khong mot gate nao thay,
    # vi khong gate nao tung doc truong `title`. Mot cai ten sai o dong dau
    # cua tai lieu nguoi doc la loi re nhat de tao ra va de nhat de bo sot.
    _title = str(draft.get("title", "") or "").strip()
    if not _title:
        # KHONG phai loi chan. Bug can bat la tieu de SAI (chep tu project
        # khac), khong phai tieu de THIEU. Lan dau toi de no la error va no
        # lam chet 4 self-test truoc khi gate dang duoc kiem kip chay - mot
        # gate moi giet cac gate cu, va "runs=False" la tat ca nhung gi hien
        # ra. Mot kiem tra phu khong duoc chan duong kiem tra chinh.
        console.print("[yellow][TITLE-MATCH][/] draft.json has no 'title' - "
                      "script.txt will have no heading.")
    # Chi so sanh trung lap khi tieu de TRONG NHU mot ten phim that. Mot
    # placeholder ("t") trung nhau giua hai project khong chung minh dieu gi -
    # va lan dau toi bo qua dieu do, bon fixture dung chung title "t" lam gate
    # nay bao loi va sys.exit() TRUOC khi gate dang duoc kiem kip chay.
    elif len(_title) >= 8 and (" " in _title or any(c.isdigit() for c in _title)):
        for _other in sorted(pdir.parent.glob("*/draft.json")):
            if _other.resolve() == (pdir / "draft.json").resolve():
                continue
            try:
                _ot = str(json.loads(_other.read_text(encoding="utf-8-sig"))
                          .get("title", "") or "").strip()
            except Exception:
                continue
            if _ot and _ot.lower() == _title.lower():
                errors.append(
                    f"[TITLE-MATCH] title {_title!r} is identical to "
                    f"{_other.parent.name}'s. It was almost certainly carried "
                    f"over when this project was copied. Set the real title.")
                break
        else:
            # Khong trung project nao -> kiem long: tieu de co dinh dang gi do
            # toi ten project khong. Chi CANH BAO, vi mot tieu de that su co
            # the khong chia se ky tu nao voi ten thu muc.
            _slug = re.sub(r"[^a-z0-9]", "", project.lower())
            _tslug = re.sub(r"[^a-z0-9]", "", _title.lower())
            if _tslug and _slug and not (_tslug[:6] in _slug or _slug[:6] in _tslug):
                console.print(
                    f"[yellow][TITLE-MATCH][/] title {_title!r} does not "
                    f"resemble project {project!r}. Not necessarily wrong - "
                    f"but check it is this film's title and not a leftover.")

    # ---- [WINDOW-OVERLAP] ------------------------------------------------
    # Hai dong cung chiem mot khoang footage thi khi render chung chong len
    # nhau: mot dong se noi de len hinh cua dong kia. Tren tokyodrift2006 co
    # dung mot cap (127/128) - cung cua so, cung noi dung, va dong thu hai
    # con them mot su that khong he duoc chieu o do.
    _wins = []
    for ln in draft["lines"]:
        if ln.get("clip_start") and ln.get("clip_end"):
            try:
                _wins.append((parse_ts(ln["clip_start"]),
                              parse_ts(ln["clip_end"]), ln.get("id")))
            except Exception:
                pass
    _wins.sort()
    for (_a1, _b1, _i1), (_a2, _b2, _i2) in zip(_wins, _wins[1:]):
        if _a2 < _b1 - 1e-6:
            errors.append(
                f"[WINDOW-OVERLAP] line {_i1} and line {_i2} share footage "
                f"({_a1:.1f}-{_b1:.1f}s vs {_a2:.1f}-{_b2:.1f}s). Two lines "
                f"over the same frames means one of them speaks over the "
                f"other's picture. Merge them or move one.")

    # ---- PHASE 1 writing-craft gates -------------------------------------
    # Nguong duoc chot tai docs/WRITING_CRAFT_CRITERION.md TRUOC khi viet gate,
    # va duoc do tren hai ban draft that (badgenius2017 = chuan vang phai pass,
    # tokyodrift2006 = ban bi che phai fail). Nam nguong trong bao cao goc da bi
    # doi vi chuan vang truot chung - chi tiet trong criterion.
    # Cac cong nay CHI ra loi cung khi draft du lon (>=40 dong co loi doc);
    # duoi do chung chi bao cao. Day khong phai su nuong tay: thong ke nhip vo
    # nghia tren fixture 3 dong, va mot gate moi giet fixture se lam chet cac
    # gate CU truoc khi chung kip chay (xem [TITLE-MATCH] ~404).
    try:
        from pipeline import craft_gates as _craft
        _cr = _craft.craft_report(draft)
        errors.extend(_cr["errors"])
        for _w in _cr["warns"]:
            console.print(f"[yellow]{_w}[/]")
        for _nt in _cr["notes"]:
            console.print(f"[dim]{_nt}[/]")
    except Exception as _ce:                              # pragma: no cover
        # D-GREEN: mot audit thieu dau vao phai NOI RA, khong duoc im lang xanh.
        console.print(f"[red][CRAFT] gates did not run: {_ce}[/] "
                      f"Treat this draft as UNCHECKED for writing craft.")

    if errors:
        console.print("[red]draft.json has problems:[/]")
        for e in errors:
            console.print(f"  - {e}")
        sys.exit(1)

    # write readable script.txt
    # 2026-09-09: day la con so NGUOI DOC THAT SU NHIN THAY, va no tung chay
    # tren 170 WPM trong khi DRAFT-TARGET chay tren nhip do duoc - hai con so
    # runtime cho cung mot ban draft. Phai dung CHINH mot co so, nen no doc
    # cung mot profile, va no NOI RA no dang dung co so nao.
    from pipeline import calibration as _cal_s
    _prof = _cal_s.get_profile(getattr(config, "DEFAULT_TTS_VOICE", None),
                               getattr(config, "DEFAULT_TTS_RATE", "+22%"))
    _wpm = (_prof.words_per_minute if _prof.is_measured
            else float(config.TTS_WORDS_PER_MINUTE))
    _basis = (f"measured {_prof.voice_id}" if _prof.is_measured
              else "config fallback (voice not measured)")
    est_min = total_words / _wpm
    script_lines = [
        f"TITLE: {draft.get('title', '(untitled)')}",
        f"Lines: {len(draft['lines'])}   Words: {total_words}   "
        f"Est. narration: {est_min:.1f} min @ {_wpm:.0f} WPM [{_basis}]   "
        f"Target: {draft.get('target_minutes', '?')} min",
        "=" * 60,
        "",
    ]
    for ln in draft["lines"]:
        if ln.get("pool"):
            src = f"pool {ln['pool']}"
        else:
            src = f"{ln.get('clip_start','?')} -> {ln.get('clip_end','?')}"
        deliv = ln.get("delivery", "normal")
        # 2026-10-20: script.txt tung KHONG in narration_silence_seconds, nen
        # ba dong giu hinh co chu y cua badgenius2017 doc nhu dead air, va mot
        # ban bao cao nghien cuu da ket luan sai dung tu cho do. Cai gi draft
        # mang thi script phai hien - neu khong nguoi doc se danh gia mot tai
        # lieu khac voi tai lieu dang chay.
        _pl = ln.get("payload")
        _tag = f"<{deliv}>" + (f" {{{_pl}}}" if _pl else "")
        _sil = ln.get("narration_silence_seconds")
        if _sil:
            _tag += f" [HOLD {float(_sil):.1f}s - no narration]"
        script_lines.append(f"[{ln['id']:>3}] ({src})  {_tag}")
        if ln.get("hook_question"):
            script_lines.append(f"      Q: {ln['hook_question']}")
        script_lines.append(f"      {ln['narration']}")
        script_lines.append("")

    (pdir / "script.txt").write_text("\n".join(script_lines), encoding="utf-8")

    # action mix + reuse histogram (visibility before render)
    if pool_uses:
        n_action = sum(pool_uses.values())
        n_total = len(draft["lines"])
        console.print(f"[bold]Action mix:[/] {n_action}/{n_total} pool clips "
                      f"({100*n_action/n_total:.0f}% action, "
                      f"{100*(n_total-n_action)/n_total:.0f}% dialogue)")

    # ---- duplicate line ids -------------------------------------------------
    # HARD failure. Line ids are the key for the TTS filename (line_041.mp3),
    # the render's by_id lookup, every gate message and every QA note. Two lines
    # sharing an id means the second silently overwrites the first's audio and
    # BOTH render with the same voiceover - which is how a late-film line ended
    # up narrating an early scene in Shutter Island, spoiling the twist 36
    # seconds in while every gate stayed green.
    _seen: dict = {}
    _dupes: list = []
    for _ln in draft["lines"]:
        _k = str(_ln.get("id"))
        if _k in _seen:
            _dupes.append((_k, _seen[_k], _ln.get("clip_start")))
        else:
            _seen[_k] = _ln.get("clip_start")
    if _dupes:
        console.print("[red][DUPLICATE-ID][/] line ids must be unique:")
        for _k, _first, _second in _dupes:
            console.print(f"    id {_k}: {_first} and {_second}")
        console.print("[red]  Renumber one of them. Rendering with duplicate ids "
                      "gives both lines the same narration audio.[/]")
        sys.exit(1)

    # ---- empty narration ----------------------------------------------------
    # MOVED 2026-09-05 to just above the `if errors:` abort (search [EMPTY-LINE]).
    # It was unreachable here: an unlabelled duplicate of the same check ran in
    # the per-line loop, appended to `errors`, and the abort fired first. The
    # rationale that used to sit here is preserved at the new site - HARD
    # failure, same class as duplicate ids: a line with a clip window but no
    # words renders anyway, TTS returns near-zero duration, and the shot flashes
    # past in under a second with nothing said over it. Found in a shipped
    # Spider-Man cut (lines 45 and 641), where no gate saw it: even
    # RENDER-VERIFY was blind, because it asks whether the audio matches the
    # line, not whether the line has any words.

    # quality linter (clarity / read-aloud / names / action-setup / visual-memory)
    _lint_script(pdir, draft, src_dur, pool_meta, explicit_times)

    # Phase 1 audits -> returns a metrics dict (or None on swallowed setup failure)
    audit = _run_phase1_audits(project, pdir)
    audit_sev = (audit or {}).get("sev", "clean") if isinstance(audit, dict) else "clean"

    console.print(
        f"[green]draft.json valid.[/]  {len(draft['lines'])} lines, "
        f"{total_words} words, est. {est_min:.1f} min narration."
    )
    console.print(f"Readable script written: {pdir / 'script.txt'}")

    # ---- STAGE MACHINE (Stage 3a/3b), engine-owned, LINEAR only -------------
    # Runs AFTER audits and ONLY when we have real metrics (a dict, not the None
    # returned on a swallowed setup failure) - so a failed audit can never
    # trigger promotion. Promotion is EXPLICIT (--promote) and one-way.
    if isinstance(audit, dict) and audit.get("style") == "linear":
        _stage_machine(project, audit, write_state=write_state, promote=promote)

    # expose the Phase 1 audit severity so the CLI can set an exit code.
    if isinstance(draft, dict):
        draft["_audit_severity"] = audit_sev or "clean"
    return draft


def outline_ready(audit: dict) -> tuple:
    """The honest 'outline done' condition. Returns (ready: bool, reason: str).

    Coverage rule: NOT strict all-beats-bound, but 'no run of >=2 consecutive
    uncovered beats'. A lone uncovered beat between two adjacent lines is a
    coarse-beat (HH:MM) granularity artifact - the neighbouring line covers that
    content. A run of >=2 consecutive uncovered beats is a genuine unnarrated
    stretch of film (the real failure mode: a skipped chunk / under-covered
    close), so that - and only that - blocks the outline.
    """
    bc = audit.get("beat_coverage", {}) or {}
    beats = bc.get("beats", 0)
    max_run = bc.get("max_consecutive_uncovered", 0)
    checks = {
        "beats_present":        beats > 0,
        # A beat map that failed validation is an UNKNOWN, not a weak signal:
        # every number below it (coverage, reveal landings, set-piece ranges)
        # is computed from timestamps we cannot vouch for. Block promotion.
        "beat_map_trusted":     not bc.get("ts_problems"),
        "no_skipped_chunk":     beats > 0 and max_run < 2,
        "no_binding_mismatch":  audit.get("binding_mismatch", 1) == 0,
        "no_unverified":        audit.get("binding_unverified", 1) == 0,
        # D-GREEN. "0 mismatch / 0 unverified" is only evidence if the audit was
        # given something to check. binding_audit only examines lines carrying a
        # `claim`; with zero claims it returns 0/0 and every check above passes
        # on an empty input. That is not a clean result, it is an ABSENT one, and
        # it let every draft in this repo promote against an audit that had
        # looked at nothing. A draft must carry at least one claim to promote.
        "audit_examined":       audit.get("binding_checked", 0) > 0,
        "continuity_clean":     audit.get("continuity_issues", 1) == 0,
        "no_binding_violation": audit.get("binding_violations", 1) == 0,
        "not_hard":             audit.get("sev") != "hard",
    }
    ready = all(checks.values())
    if ready:
        lone = len(bc.get("uncovered", []))
        note = (f", {lone} lone beat(s) tolerated (granularity)" if lone else "")
        reason = (f"outline_ready: {bc['covered']}/{beats} beats bound, "
                  f"no >=2-consecutive gap, "
                  f"{audit.get('binding_verified', 0)} verified of "
                  f"{audit.get('binding_checked', 0)} claim(s) checked, "
                  f"0 mismatch / 0 unverified, "
                  f"continuity 0, 0 violations{note}")
    else:
        failed = ", ".join(k for k, v in checks.items() if not v)
        gaps = bc.get("consecutive_gaps", [])
        gap_note = ""
        if gaps:
            gap_note = " | skipped chunks: " + "; ".join(
                "+".join(str(x) for x in g) for g in gaps)
        ts_note = ""
        if bc.get("ts_problems"):
            ts_note = " | beat map: " + "; ".join(bc["ts_problems"])
        reason = "not ready: " + failed + gap_note + ts_note
    return ready, reason


def _stage_machine(project, audit, write_state=False, promote=False):
    from pipeline import state as _state
    if _state.get_stage(project) == "script":
        console.print("[dim][STAGE] already in SCRIPT stage.[/]")
        return
    ready, reason = outline_ready(audit)
    bc = audit.get("beat_coverage", {}) or {}
    metrics = {
        "beats": bc.get("beats", 0), "covered": bc.get("covered", 0),
        "uncovered": bc.get("uncovered", []),
        "binding_mismatch": audit.get("binding_mismatch"),
        "binding_unverified": audit.get("binding_unverified"),
        "continuity_issues": audit.get("continuity_issues"),
        "binding_violations": audit.get("binding_violations"),
    }
    console.print(f"[{'green' if ready else 'yellow'}][STAGE] OUTLINE -> {reason}[/]")

    if not write_state:
        return                       # render re-validates; must never write stage
    if promote:
        if ready:
            _state.promote_to_script(project, reason, metrics)
            console.print("[bold green][STAGE] promoted to SCRIPT. DRAFT-TARGET "
                          "applies from the next draft run.[/]")
        else:
            console.print(f"[red][STAGE] --promote refused: {reason}. "
                          f"Fix the failing checks first.[/]")
    else:
        console.print("[dim][STAGE] run `recap.py draft --promote` to enter "
                      "SCRIPT stage once the checks above are green.[/]")


# --------------------------------------------------------------------------- #
# Quality linter -- 6 unique gates restored after the OneDrive revert:
#   [CLARITY] [READ-ALOUD] [NAME] [ACTION-SETUP] [VISUAL-MEMORY]
#   ([VISUAL-REPEAT] is enforced in the main loop above.)
# [FRESHNESS] is intentionally DROPPED -- continuity_check covers timeline
# position more precisely (avoids double-flagging). Warnings, not blocks.
# --------------------------------------------------------------------------- #
import re as _re

# --------------------------------------------------------------------------- #
# [NAME] guard: class-based exclusions.
#
# These are the words that survive tokenisation as false flags. They are not
# one-offs and they recur film to film, so they are named classes rather than
# entries hand-added to _stop per project. Measured before this existed: the
# residual flags on two finished films were "Civil", "War", "Deputy", "Marshal"
# (ranks and a historical event) and "Goldberg", "Hawaii", "Superbad" (crew, a
# place, the film's own title). Every one belongs to a class below except the
# crew surname.
# --------------------------------------------------------------------------- #

# Ranks, honorifics and job titles that sit in front of a name and get scanned
# as if they were one.
_RANKS = {
    "marshal", "marshall", "deputy", "sheriff", "warden", "doctor", "nurse",
    "officer", "detective", "sergeant", "captain", "colonel", "general",
    "lieutenant", "major", "corporal", "private", "admiral", "commander",
    "chief", "agent", "judge", "professor", "senator", "governor", "mayor",
    "president", "reverend", "principal", "coach", "guard", "ranger",
}

# Places. Not the whole world - the classes that actually appear in recap
# narration: US states, countries and the handful of cities a film names.
_PLACES = {
    # US states
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "hampshire", "jersey",
    "mexico", "york", "carolina", "dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "wisconsin", "wyoming",
    # countries / regions
    "america", "american", "england", "english", "britain", "british",
    "france", "french", "germany", "german", "italy", "italian", "spain",
    "spanish", "russia", "russian", "china", "chinese", "japan", "japanese",
    "korea", "korean", "thailand", "thai", "india", "indian", "canada",
    "canadian", "australia", "europe", "european", "africa", "african",
    "boston", "chicago", "angeles", "vegas", "london", "paris", "berlin",
    "tokyo", "bangkok", "seoul", "moscow",
    # recurring historical/proper-noun phrases that are not people
    "civil", "war", "christmas", "halloween", "thanksgiving", "easter",
}


def _title_tokens(pdir, draft) -> set:
    """The film's own title, from metadata already on disk.

    A recap says its own film's name. "Superbad" was flagged as an invented
    character because nothing told the guard what the film was called - while
    both draft.json ("title") and shots.json ("film_title") were sitting there
    carrying it.
    """
    out = set()
    vals = [draft.get("title") if isinstance(draft, dict) else None]
    try:
        sp = pdir / "shots.json"
        if sp.exists():
            vals.append(json.loads(sp.read_text(encoding="utf-8-sig")).get("film_title"))
    except Exception:
        pass
    for v in vals:
        if not v:
            continue
        # take the title proper, before any subtitle we added
        head = str(v).split(":")[0]
        for tok in _re.findall(r"[A-Za-z]+", head):
            if len(tok) >= 3:
                out.add(tok.lower())
    return out


_VAGUE = [
    r"\bit gets personal\b", r"\bthe leader\b", r"\bthe enemy\b",
    r"\bone of them\b", r"\bthe other guy\b", r"\bthis guy\b",
    r"\bthe man\b(?! named)", r"\bthe woman\b(?! named)",
]
_FORMAL = [
    r"\bproceeds to\b", r"\bsubsequently\b", r"\bin order to\b",
    r"\butilize\b", r"\bthereafter\b", r"\bwhom\b", r"\balbeit\b",
    r"\bnevertheless\b", r"\bcommences\b",
]
# [CAMERA-LANGUAGE] 2026-09-09.
# Narration describes the STORY. The moment it describes the apparatus - the
# camera, the cut, the frame, the take - it has stopped telling the viewer what
# happened and started telling them how it was filmed. The viewer is already
# watching the footage; they do not need it announced.
#
# This leaked in because the machine catalogue's `action` field is written by a
# tagger looking at frames, so it is FULL of shot language ("the frame pulls
# back", "one held take", "cut to"). I1 says `action` is never the prose source,
# and the draft prompt says rewrite it - but nothing MEASURED whether that had
# happened. 27 lines of the first machine draft narrated the camera.
_CAMERA = [
    r"\bthe camera\b", r"\bcamera (?:pushes|pulls|backs|holds|stays|leaves|closes)\b",
    r"\bthe (?:cut|cuts)\b", r"\bcut (?:to|back|against|out)\b", r"\bhard cut\b",
    r"\bthe frame\b", r"\bframe (?:pulls|widens|settles|closes|leaves)\b",
    r"\bin frame\b", r"\bon(?:-| )screen\b", r"\boff(?:-| )screen\b",
    r"\ban? insert\b", r"\bthe insert\b", r"\binsert cuts?\b",
    r"\bshot and reverse\b", r"\bthe reverse\b", r"\breverse shot\b",
    r"\blast (?:shot|frame)\b", r"\bfirst shot\b", r"\bfinal shot\b",
    r"\bone (?:long |held )?take\b", r"\bheld take\b", r"\bacross one take\b",
    r"\bclose(?:-| )up\b", r"\bthe wide\b", r"\bwide shot\b", r"\bthe shot\b",
    r"\bracks? (?:focus|past)\b", r"\bthe lens\b", r"\bintercut\b",
    r"\bfades? (?:in|out|into)\b", r"\bthe (?:opening|closing) shot\b",
]
# Generic action TOKENS, matched against the parts of a family name
# ("warehouse_shootout" -> {"warehouse", "shootout"} -> action). This is a
# FALLBACK; the primary signal is `depicts: action` on the shot or pool entry.
#
# Film-specific family names must never be added here. The previous version
# listed pennywise_attack / losers_fight / bowers_bully (IT 2017) as global
# constants, which meant the gate went silent on any film whose tagger named
# families differently - a gate that looks alive and is not. RULES.md B5: a
# right rule applied too narrowly. Token matching generalises it instead.
_ACTION_FAMILIES = {
    "explosion", "gunfight", "bombmaking", "chase", "fight", "shootout",
    "attack", "ambush", "raid", "breach", "escape", "battle", "brawl",
    "skydive", "standoff", "duel", "siege", "pursuit",
}


def _is_action_family(fam) -> bool:
    """True when any token of a family name is a generic action word."""
    if not fam:
        return False
    toks = set(str(fam).lower().replace("-", "_").replace(" ", "_").split("_"))
    return bool(toks & _ACTION_FAMILIES)
# Setup cues: a line sets up an action beat when it establishes WHO / WHY /
# TRIGGER / STAKES. Deliberately narrow - causal and intentional markers only.
#
# Removed from the previous version, and why:
#   when, once, after, meanwhile, however, unfortunately
#       -> bare temporal/discourse words. "When Peter turns around, the building
#          explodes" establishes nothing; it just orders two events.
#   attacks, corners, finds
#       -> these ARE the action (or the discovery), not its setup.
#   in order to
#       -> also listed in _FORMAL, so one phrase both earned a warning and
#          cleared this gate.
# The "any known character name appears" clause was dropped from _has_setup for
# the same reason: naming someone is not establishing why they are fighting.
_SETUP_CUES = [
    r"\bbecause\b", r"\bas a result\b", r"\bin response\b",
    r"\bso (?:he|she|they|now|that)\b", r"\bnow that\b",
    r"\bwants? to\b", r"\bneeds? to\b", r"\bdecides?\b", r"\bplans?\b",
    r"\bintends?\b", r"\bsets? out\b", r"\bsets? off\b",
    r"\bhunts?\b", r"\btracks? (?:down|him|her|them|it)\b",
    r"\bgoes? after\b", r"\bcomes? for\b", r"\bconfronts?\b",
    r"\bthreatens?\b", r"\bdemands?\b", r"\brefuses?\b", r"\bwarns?\b",
    r"\bif (?:he|she|they)\b",
    r"\bbefore (?:he|she|they|it)\b",
]

# NOTE - a purpose-infinitive regex was tried here and REMOVED. Measured over
# Interstellar + John Wick it fired 12 times and matched a real purpose clause
# roughly twice: it cleared action beats on the strength of "to be", "to die",
# "to every", "to hope", "to ash", "to do". Worse, it silenced the gate
# completely (34 warnings -> 1 across four films) including a verified real
# miss, Interstellar L73, cleared by "to hope" three lines earlier in an
# unrelated scene about Murph.
#
# Two attempts at a cleverer pattern both failed in opposite directions - an
# enumerated verb list was too narrow, a structural match too broad. Setup is a
# meaning, not a string, and the honest reading of the data is that a text cue
# cannot decide it. What CAN decide it is a human tag: `depicts: setup` is
# already in the controlled vocabulary and shots are tagged 100%. See
# docs/GATE_CANDIDATES.md.


def _load_shot_index(pdir):
    """[(start_sec, end_sec, depicts:set, family)] from shots.json, time-sorted.

    Lets the ACTION-SETUP gate classify lines bound to an EXPLICIT window. Pool
    and montage lines are classified from pool_meta; before this existed, every
    explicit-window line - the majority in a linear project - fell straight
    through to the hold>=5s fallback.
    """
    out = []
    sp = pdir / "shots.json"
    if not sp.exists():
        return out
    try:
        shots = json.loads(sp.read_text(encoding="utf-8-sig")).get("shots", [])
    except Exception:
        return out
    for s in shots:
        cs, ce = s.get("clip_start"), s.get("clip_end")
        if not cs or not ce:
            continue
        try:
            out.append((parse_ts(cs), parse_ts(ce),
                        set(s.get("depicts") or []), s.get("family"),
                        s.get("id") or f"clip:{cs}"))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out


def _lint_script(pdir, draft, src_dur, pool_meta=None, explicit_times=None):
    pool_meta = pool_meta or {}
    explicit_times = explicit_times or []
    shot_index = _load_shot_index(pdir)
    warns: list = []

    # --- [NAME]: invented-name guard via names.json ----------------------
    # Loaded through schemas.load_names, NOT parsed here. This used to have its
    # own inline reader that assumed names.json held plain strings; when the
    # file gained {"character", "actor"} entries, .lower() on a dict raised,
    # the except swallowed it, and `known` silently became empty - so every
    # capitalised word in the script got flagged as an invented name. One
    # loader, one format. (GATE_CANDIDATES F6: the same job written twice
    # drifts apart, and the copy nobody updated fails quietly.)
    from pipeline import schemas as _schemas
    # Tokens, not whole strings. names.json holds "Dr. John Cawley"; narration
    # says "Cawley". Whole-string membership flagged the real name, which is
    # what made this gate unreadable and what RULES B8 was written around.
    known = _schemas.load_name_tokens(pdir.name)
    # `_stop` is for genuine one-offs only. Everything enumerable and stable
    # belongs to a named class below, so the next film does not arrive needing
    # hand-additions - that hand-adding is how the list became noise the first
    # time (and B8 told authors to ignore the result rather than fix it).
    _stop = {"this", "today", "the", "and", "but", "so", "a", "i", "he", "she",
             "they", "it", "we", "his", "her", "their", "serabudabu", "god",
             "okay", "yeah", "no", "yes"}
    exclude = set(_stop) | _RANKS | _PLACES | _title_tokens(pdir, draft)
    proper_seen = {}
    for ln in draft["lines"]:
        text = ln.get("narration", "")
        for m in _re.finditer(r"\b([A-Z][a-z]{2,})\b", text):
            w = m.group(1)
            if w.lower() in _stop:
                continue
            idx = m.start()
            prev = text[:idx].rstrip()
            if prev == "" or prev.endswith((".", "!", "?")):
                continue
            proper_seen.setdefault(w, ln["id"])
    # `known` empty means either no names.json or an unreadable one - in both
    # cases every capitalised word would be flagged, which is noise, not a
    # finding. Say why the check is off instead of firing it or hiding it.
    if not known:
        warns.append("[NAME] skipped - names.json is missing or unreadable, "
                     "so there is nothing to check invented names against.")
    else:
        for w, lid in proper_seen.items():
            if w.lower() not in known and w.lower() not in exclude:
                warns.append(f"[NAME] line {lid}: '{w}' not in names.json - verify it's "
                             f"real or use a generic role (never invent).")

        # One-letter character names are NOT covered by this guard and cannot
        # be. The scanner is [A-Z][a-z]{2,}, so a token like "M" - the lead of
        # howtomakemillions2024 - is never read at all: not validated, not
        # flagged, simply invisible. Widening the pattern to see single capitals
        # does not fix it, it inverts it. Measured: with "m" present in
        # names.json, a stray mid-sentence capital M ("the sign above the door
        # read M") passes silently, because the lead's own name makes every
        # single letter acceptable. The guard would then launder precisely what
        # it exists to catch. So one-letter names stay excluded, and the gap is
        # stated rather than assumed closed.
        _one_letter = sorted(n for n in known if len(n) == 1)
        if _one_letter:
            warns.append(
                f"[NAME] {len(_one_letter)} one-letter name(s) are NOT checked "
                f"({', '.join(x.upper() for x in _one_letter)}) - the scanner "
                f"needs 3+ characters, and widening it would let any stray "
                f"capital letter pass as a name. Check these lines by eye.")

    # --- [CLARITY]: vague references -------------------------------------
    for ln in draft["lines"]:
        t = ln.get("narration", "").lower()
        for pat in _VAGUE:
            if _re.search(pat, t):
                warns.append(f"[CLARITY] line {ln['id']}: vague reference "
                             f"({pat.strip(chr(92)+'b')}) - name the character.")
                break

    # --- [READ-ALOUD]: unbreathable sentences ----------------------------
    # 2026-10-20 RECALIBRATED. Luat cu la "cau > 28 tu -> canh bao", va no
    # MAU THUAN truc tiep voi [RHYTHM] moi (doi >=2% cau dai >=30 tu). Trong
    # tai la ban NGUOI badgenius2017: luat cu bat no 12 lan, tuc chuan vang
    # vi pham chinh cai luat nay mot tuc nam; luat moi bat no 0 lan.
    # Van de that chua bao gio la DO DAI - la HOI. Mot cau 45 tu co dau phay
    # moi 12 tu thi doc duoc; mot cau 30 tu lien mot hoi thi khong. Bao cao
    # nghien cuu cung noi dung dieu do ("vai dong dai tren 40 tu se can dau
    # ngat hoi cho TTS"), khong noi phai cat ngan.
    # Do duoc: HUMAN 0 hit, TD cu 0 hit, TD moi 23 hit.
    for ln in draft["lines"]:
        text = ln.get("narration", "")
        for sent in _re.split(r"(?<=[.!?])\s+", text):
            _w = len(sent.split())
            if _w <= 28:
                continue
            _parts = _re.split(r"[,;:\u2014\u2013-]", sent)
            _run = max((len(p.split()) for p in _parts), default=_w)
            if _run > 20:
                warns.append(
                    f"[READ-ALOUD] line {ln['id']}: a {_w}-word sentence runs "
                    f"{_run} words with no comma, dash or semicolon to breathe "
                    f"at. Long sentences are REQUIRED by [RHYTHM] - add breath "
                    f"points, do not shorten it.")
                break
        for pat in _FORMAL:
            if _re.search(pat, text.lower()):
                warns.append(f"[READ-ALOUD] line {ln['id']}: formal phrasing "
                             f"({pat.strip(chr(92)+'b')}) - say it plainly.")
                break

    # --- [NAME-LEAK]: a capitalised token with no source ------------------
    # 2026-09-09. Noi transcript vao payload lam cach romanise cua may chui
    # thang vao narration: "Lin", "Rin" (deu la Lynn) va "Toe" (mot nhan vat
    # CHI ton tai trong ban dich may). Toi di bat chung bang MAT, bat duoc hai,
    # sot hai; mot lan quet regex moi ra het. Mot danh sach doc bang mat khong
    # phai mot phep do.
    #
    # Nguon hop le cho mot ten rieng trong narration:
    #   names.json  - danh sach nhan vat chinh thuc
    #   beat map    - cac DONG BEAT (Bxx | ...), noi dia danh / to chuc that su
    #                 song (Sydney, Boston, STIC, GAT, Bangkok)
    # Phan PROSE o dau beat map CO Y KHONG duoc tinh: do chinh la cho viet
    # 'transcript romanises the lead as "Lin"' - mot canh bao, khong phai mot
    # su cho phep.
    #
    # Rule B ton tai vi beat map TU MAU THUAN: header cam "Lin", nhung B05 lai
    # viet "the nickname on the form: Lin". Chi dua vao allowlist thi "Lin" lot
    # luoi. Nen mot token GAN GIONG mot ten trong names.json (edit distance <=2)
    # bi bat KE CA khi no co trong beat map - do dung la hinh dang cua loi
    # romanise-variant.
    import json as _json, glob as _glob

    def _lev(a, b):
        if a == b:
            return 0
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                               prev[j - 1] + (ca != cb)))
            prev = cur
        return prev[-1]

    # Hai LOP DONG cua tieng Anh. Liet ke duoc HET, nen day khong phai mot
    # stoplist moc dan theo tung false positive nhin thay - do chinh la kieu
    # "sua theo cai minh nho" ma rule nay sinh ra de thay the.
    _CLOSED = set("""
    one two three four five six seven eight nine ten eleven twelve thirteen
    fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty
    fifty sixty seventy eighty ninety hundred thousand million billion dozen
    first second third fourth fifth sixth seventh eighth ninth tenth
    meanwhile however afterwards nevertheless moreover therefore besides
    otherwise likewise instead suddenly finally eventually afterward
    """.split())

    _proper, _allow = set(), set()
    try:
        _nj = _json.loads((pdir / "names.json").read_text(encoding="utf-8-sig"))
        for e in (_nj.get("names") or []):
            _t = _re.findall(r"[A-Za-z][A-Za-z'-]*", str(e.get("character", "")))
            if _t:
                # "Lynn's father" -> ten rieng la "lynn"; "father" la VAI TRO
                _proper.add(_t[0].split("'")[0].lower())
    except Exception:
        pass
    _allow |= _proper
    # CHI cac DONG BEAT. Phan prose dau beat map co y khong duoc tinh: do la
    # cho viet 'transcript romanises the lead as "Lin"' - mot canh bao, khong
    # phai mot su cho phep.
    try:
        _bl = (pdir / "beats_proposal.md").read_text(
            encoding="utf-8-sig").splitlines()
        _rows = " ".join(l for l in _bl if _re.match(r"^\s*B\d+\s*\|", l))
        for t in _re.findall(r"\b[A-Z][A-Za-z'-]*\b", _rows):
            _allow.add(t.split("'")[0].lower())
    except Exception:
        pass

    # Tu dien VIET THUONG: mot tu xuat hien o dang thuong trong tai lieu tieng
    # Anh cua repo thi no la tu thuong, khong phai ten rieng. Dung ca kho de
    # "Sixty / Daylight / Backstage / Whatever" khong bi goi la ten ma khong
    # can ai go tay chung vao mot danh sach.
    _lower = set(_CLOSED)
    _texts = [(pdir / "beats_proposal.md")]
    _corpus = []
    try:
        _corpus += [str(s.get("action", "")) for s in
                    _json.loads((pdir / "shots.json").read_text(
                        encoding="utf-8-sig")).get("shots", [])]
    except Exception:
        pass
    _corpus += [str(l.get("narration", "")) for l in draft["lines"]]
    _root = str(pdir.parent)
    # 2026-09-09: o day tung goi io.open(), nhung draft.py KHONG import io.
    # NameError bi chinh `except Exception` nay nuot, nen kho corpus toan repo
    # lang le khong bao gio nap - va rule bao 21 loi thay vi 15, trong do co
    # "Bar"/"Bad" bi goi la bien the cua "Bank". Mot except qua rong bien mot
    # loi lap trinh thanh mot ket qua sai IM LANG. Bat dung loai I/O thoi.
    _loaded = 0
    for _p in _glob.glob(_root + r"\*\transcript.json"):
        try:
            _corpus += [str(s.get("text", "")) for s in
                        _json.loads(Path(_p).read_text(encoding="utf-8-sig"))
                        .get("segments", [])]
            _loaded += 1
        except (OSError, ValueError):
            pass
    for _p in _glob.glob(_root + r"\*\beats_proposal.md"):
        try:
            _corpus.append(Path(_p).read_text(encoding="utf-8-sig"))
        except OSError:
            pass
    if _loaded == 0:
        warns.append("[NAME-LEAK] no transcript corpus loaded - the "
                     "capitalised-token check is running on a thin vocabulary "
                     "and will over-report. This is a setup fault, not a draft "
                     "fault.")
    for _txt in _corpus:
        for _w in _re.findall(r"\b[a-z][a-z'-]*\b", _txt):
            _lower.add(_w.split("'")[0])
            for _part in _w.split("-"):
                if _part:
                    _lower.add(_part.split("'")[0])

    for ln in draft["lines"]:
        text = str(ln.get("narration", ""))
        seen = set()
        for tok in _re.findall(r"\b[A-Z][A-Za-z'-]*\b", text):
            base = tok.lower().split("'")[0]      # "I'm"->"i", "Lynn's"->"lynn"
            if len(base) < 2 or base in seen or base in _lower:
                continue
            if "-" in base and all(p in _lower for p in base.split("-") if p):
                continue
            seen.add(base)
            # Mot BIEN THE cua ten that phai giu CHU CAI DAU, neu khong thi
            # "Venn"~"Lynn" / "Bar"~"Bank" deu bi goi la bien the chi vi tinh
            # co. Token VIET HOA TOAN BO la viet tat (STIC, GAT, CCTV), khong
            # bao gio la mot cach danh van sai cua ten nguoi.
            near = ([] if (tok.isupper() and len(tok) > 1) else
                    [c for c in _proper
                     if base != c and base[:1] == c[:1]
                     and _lev(base, c) <= 2 and abs(len(base) - len(c)) <= 1])
            if base in _allow and not near:
                continue
            if near:
                warns.append(
                    f"[NAME-LEAK] line {ln['id']}: '{tok}' is "
                    f"{_lev(base, near[0])} edit(s) from '{near[0].title()}' in "
                    f"names.json - almost certainly a transcript romanisation, "
                    f"not a second character. Use the names.json spelling.")
            else:
                warns.append(
                    f"[NAME-LEAK] line {ln['id']}: '{tok}' is in neither "
                    f"names.json nor the beat map. Verify it is real on-screen "
                    f"text, or use a generic role - never invent a name.")

    # --- [CAMERA-LANGUAGE]: narrate the story, not the apparatus ---------
    for ln in draft["lines"]:
        t = str(ln.get("narration", "")).lower()
        hits = [pat for pat in _CAMERA if _re.search(pat, t)]
        if hits:
            warns.append(
                f"[CAMERA-LANGUAGE] line {ln['id']}: narrates the camera "
                f"({', '.join(p.strip(chr(92)+'b')[:28] for p in hits[:2])}) - "
                f"say what HAPPENS, not how it was shot.")

    # --- [TONE-FLAT]: a draft that is all one tone is untagged, not calm --
    # 2026-09-09: the first machine draft was 186/187 lines `normal`, against a
    # human draft of 70 tense / 45 normal / 24 sad. One tone across a whole film
    # is not an editorial choice, it is the field never being filled - and it
    # renders as a flat read for 20 minutes. This fires on the DISTRIBUTION, not
    # on any line, because no single line is wrong.
    _tones = [str(ln.get("delivery") or "normal").lower()
              for ln in draft["lines"]]
    if len(_tones) >= 20:
        from collections import Counter as _Counter
        _top, _n = _Counter(_tones).most_common(1)[0]
        _share = _n / len(_tones)
        if _share > 0.90:
            warns.append(
                f"[TONE-FLAT] {_n}/{len(_tones)} lines ({_share*100:.0f}%) are "
                f"'{_top}' - over the 90% limit. A whole film at one tone is an "
                f"unfilled field, not a choice; it renders flat. Assign tone per "
                f"line (hook/tense/sad/mystery/reveal/normal).")

    # --- [ACTION-SETUP]: action beats need setup in the prior 4 lines ----
    lines = draft["lines"]

    def _families_of(ln):
        labs = ln.get("montage") or ([ln["pool"]] if ln.get("pool") else [])
        # inline montage segments (dict/list) have no pool family - skip them.
        return {pool_meta.get(l, {}).get("family")
                for l in labs if l and isinstance(l, str)}

    def _depicts_of(ln):
        """Union of `depicts` from the pool entries AND the shot this line is
        bound to. Either source is enough; both are often present."""
        dep = set()
        for lab in (ln.get("montage") or ([ln["pool"]] if ln.get("pool") else [])):
            if isinstance(lab, str):
                dep |= set((pool_meta.get(lab, {}) or {}).get("depicts") or [])
        cs = ln.get("clip_start")
        if cs and shot_index:
            try:
                t = parse_ts(cs)
                for a, b, sdep, _fam, _sid in shot_index:
                    if a <= t < b:
                        dep |= sdep
                        break
            except Exception:
                pass
        return dep

    def _is_action(ln):
        # 1. explicit tag - the only signal that generalises across films
        if "action" in _depicts_of(ln):
            return True
        # 2. family name containing a generic action token
        if any(_is_action_family(f) for f in _families_of(ln) if f):
            return True
        # 3. long hold (weakest fallback; a long hold is often a fight beat)
        try:
            return float(ln.get("hold", 0) or 0) >= 5.0
        except (TypeError, ValueError):
            return False

    def _has_setup(ln):
        """Setup = a narrow causal cue in the NARRATION. Nothing else.

        `depicts: setup` was tried here as an authoritative signal and removed.
        Two reasons, both measured: shots are tagged ~100%, so some shot in any
        4-line window carries `setup` and the gate cleared everything (34 -> 2
        across four films, losing the verified real miss at Interstellar L73);
        and it is the wrong object anyway - `depicts` describes the FOOTAGE,
        while this rule is about whether the NARRATION established who and why.
        A setup-looking shot next to a fight proves nothing about what the
        viewer was told.
        """
        low = (ln.get("narration") or "").lower()
        return any(_re.search(pat, low) for pat in _SETUP_CUES)

    # Never silently no-op: if nothing carries `depicts`, action detection is
    # running on family names and hold>=5s alone, and the gate is much weaker
    # than it looks. Say so rather than reporting a clean pass.
    _has_depicts = any(dep for _, _, dep, _, _ in shot_index) or any(
        (v or {}).get("depicts") for v in pool_meta.values() if isinstance(v, dict))
    if lines and not _has_depicts:
        warns.append("[ACTION-SETUP] no `depicts` tags on any shot or pool entry "
                     "- action detection fell back to family names and hold>=5s. "
                     "Tag shots.json/broll.json to make this gate real.")

    # Setup -> Action -> Consequence is a rule about a BEAT, not about every
    # line. Inside a sustained sequence the middle lines ARE the Action; making
    # each of them re-establish why would be padding, and the opening setup
    # falls out of a 4-line window by the fifth line anyway. So only the line
    # that OPENS an action run is checked. (Measured: Interstellar fired 9 times
    # across lines 73-81 for what is one docking beat.)
    # Known limit: a long sequence that shifts to a new sub-beat needing fresh
    # setup is not caught. That is the Stage-7 watch's job.
    action_flags = [_is_action(x) for x in lines]

    hits = []
    for i, ln in enumerate(lines):
        if not action_flags[i] or ln.get("setup_ok") or ln.get("delivery") in ("hook", "intro"):
            continue
        if i > 0 and action_flags[i - 1]:
            continue                      # mid-run: not a new action beat
        window = lines[max(0, i - 4):i]
        if any(_has_setup(p) for p in window) or _has_setup(ln):
            continue
        fams = sorted(f for f in _families_of(ln) if f)
        if not fams:
            fams = ["depicts:action"] if "action" in _depicts_of(ln) else ["hold>=5s"]
        hits.append((ln["id"], ", ".join(fams)))

    # Stage-aware, like DRAFT-TARGET and SET-PIECE. An OUTLINE is deliberately
    # thin - setup lines are density, and density arrives with enrichment - so
    # flagging every unset-up action beat at outline stage is a false alarm on a
    # draft that is doing exactly what it is meant to do. Still reported as a
    # count, never silently dropped: an outline with a lot of these is telling
    # you where the enrichment pass has to go.
    _stage = "script"
    try:
        from pipeline import state as _state2
        from pipeline import catalogue as _cat3
        _proj = pdir.name
        if _cat3.parse_beats(_proj).get("style") == "linear":
            _stage = _state2.get_stage(_proj)
    except Exception:
        _stage = "script"

    if hits and _stage == "script":
        for lid, fams in hits:
            warns.append(f"[ACTION-SETUP] line {lid}: action beat ({fams}) "
                         f"has no setup in the prior 4 lines - establish who/why/"
                         f"trigger/stakes BEFORE it (Setup -> Action -> Consequence).")
    elif hits:
        ids = ", ".join(str(lid) for lid, _ in hits[:12])
        warns.append(f"[ACTION-SETUP] outline stage - {len(hits)} action beat(s) "
                     f"open without setup: {ids}"
                     f"{' ...' if len(hits) > 12 else ''}. Not a failure at this "
                     f"stage; this is the list the enrichment pass should cover.")

    # --- [VISUAL-MEMORY]: proximity hint on untagged explicit clips ------
    untagged = sorted((t, lid) for (lid, t, vis) in explicit_times if not vis)
    clusters: list = []
    for t, lid in untagged:
        if clusters and t - clusters[-1][-1][0] <= 30.0:
            clusters[-1].append((t, lid))
        else:
            clusters.append([(t, lid)])
    for cl in clusters:
        if len(cl) >= 3:
            ids = ", ".join(str(lid) for _, lid in cl)
            mm = int(cl[0][0] // 60)
            warns.append(f"[VISUAL-MEMORY] lines {ids} all pull footage from ~{mm} min "
                         f"of the film - they may read as the SAME action a viewer "
                         f"remembers. Tag repeats with the same 'visual' family, or "
                         f"confirm they are distinct stages / scenes.")

    if warns:
        # 2026-09-09: truoc day la `warns[:40]` CAM LANG - 62 phat hien, in 40,
        # 22 cai bien mat khong mot dong nao noi rang chung ton tai. [TONE-FLAT]
        # roi dung vao phan bi cat, nen mot gate vua viet xong da "im" ngay lan
        # chay dau tien va toi suyt ket luan no khong fire. Cat thi duoc, GIAU
        # thi khong (D-GREEN). Phat hien o CAP DU THAO (khong gan voi mot dong
        # cu the) luon duoc in truoc vi chi co mot dong moi.
        _draft_level = [w for w in warns if w.startswith(("[TONE-FLAT]",))]
        _rest = [w for w in warns if w not in _draft_level]
        console.print(f"[yellow]Quality linter: {len(warns)} item(s) to review[/]")
        for w in _draft_level:
            console.print(f"  {w}")
        _cap = 40
        for w in _rest[:_cap]:
            console.print(f"  {w}")
        if len(_rest) > _cap:
            from collections import Counter as _C
            _hidden = _C(w.split(']')[0] + ']' for w in _rest[_cap:])
            console.print(f"  [yellow]... {len(_rest)-_cap} further item(s) NOT "
                          f"shown: "
                          + ", ".join(f"{k} x{v}" for k, v in _hidden.most_common())
                          + "[/]")
    else:
        console.print("[green]Quality linter: clean.[/]")


# --------------------------------------------------------------------------- #
# Phase 1 audits (coverage / binding / continuity) -- additive, non-blocking.
# skeleton.json is RECOMMENDED, not required. Never hard-fails. ASCII output.
# --------------------------------------------------------------------------- #
# --- beat-map timestamps --------------------------------------------------- #
# A 2-part beat timestamp 'A:B' is AMBIGUOUS. Every linear beats_proposal so far
# means A hours + B minutes; MM:SS is the natural instinct and is exactly what
# parse_ts() assumes for the line clip_starts in this same file. The two
# readings differ by 60x on identical-looking text.
#
# THREE gates read these numbers - beat-coverage, REVEAL-TIMING and SET-PIECE -
# and the stage machine promotes OUTLINE -> SCRIPT off the first one. A silently
# misread beat map corrupts all three at once and nothing complains.
#
# So the format is never guessed:
#   * declare it in the beats_proposal header:   ts_format: HH:MM   (or MM:SS)
#   * absent -> HH:MM, the convention of the existing proposals
#   * a 3-part 'A:B:C' is always HH:MM:SS regardless of the declaration
# and the resolved map is validated before any gate uses it (see beat_times).
_BEAT_TS_FORMATS = ("HH:MM", "MM:SS")
_BEAT_TS_DEFAULT = "HH:MM"


def _beat_ts_seconds(ts, fmt=_BEAT_TS_DEFAULT):
    """Parse ONE beat timestamp to seconds under an explicit format.

    fmt applies only to 2-part 'A:B'. 3-part is always HH:MM:SS; a bare number
    is minutes (coarse). Returns float seconds, or None if unparseable.
    """
    ts = str(ts).strip()
    if ":" not in ts:
        try:
            return float(ts) * 60.0          # bare number = minutes (coarse)
        except Exception:
            return None
    parts = ts.split(":")
    try:
        nums = [float(p) for p in parts]
    except Exception:
        return None
    if len(parts) == 2:
        if fmt == "MM:SS":
            return nums[0] * 60 + nums[1]
        return nums[0] * 3600 + nums[1] * 60           # HH:MM
    if len(parts) >= 3:
        return nums[-3] * 3600 + nums[-2] * 60 + nums[-1]   # HH:MM:SS
    return None


def _film_duration(project):
    """Film runtime in seconds from transcript.json, or None when unavailable."""
    try:
        tj = config.project_dir(project) / "transcript.json"
        if not tj.exists():
            return None
        dur = json.loads(tj.read_text(encoding="utf-8-sig")).get("duration")
        return float(dur) if dur else None
    except Exception:
        return None


def beat_times(project) -> dict:
    """Resolve a project's beat map to seconds ONCE, with validation.

    Returns {
      "fmt":      "HH:MM" | "MM:SS",   # format actually used
      "declared": bool,                # True when ts_format: was in the header
      "ordered":  [(beat_id, secs)],   # sorted by time
      "by_id":    {beat_id: secs},
      "problems": [str],               # non-empty -> DO NOT TRUST the numbers
    }

    Validation, run whenever there are >=2 dated beats:
      1. strictly increasing in WRITTEN order. A beat map is authored in film
         order, so one beat edited in the other convention breaks this before
         anything else does.
      2. no beat past the end of the film (transcript.json duration, +2% slack).
         Skipped when transcript.json is absent.

    A failing beat map is not a weaker signal - it is an unknown one. Callers
    must surface `problems` rather than quietly carrying on with the numbers.
    """
    from pipeline import catalogue as _cat
    binfo = _cat.parse_beats(project)
    declared = binfo.get("ts_format")
    fmt = declared if declared in _BEAT_TS_FORMATS else _BEAT_TS_DEFAULT
    other = "MM:SS" if fmt == "HH:MM" else "HH:MM"

    written = []          # (beat_id, secs, raw_ts) in WRITTEN order
    unparsed = []
    problems = []
    for b in binfo.get("beats", []):
        ts = b.get("ts")
        if not b.get("id") or not ts:
            continue
        secs = _beat_ts_seconds(ts, fmt)
        if secs is None:
            unparsed.append(f"{b.get('id')} ({ts})")
            continue
        written.append((b.get("id"), secs, ts))

    if unparsed:
        problems.append("beat timestamps that do not parse: " + ", ".join(unparsed[:5])
                        + (" ..." if len(unparsed) > 5 else ""))

    # 1. monotonic in written order
    for (pid, psec, pts), (cid, csec, cts) in zip(written, written[1:]):
        if csec <= psec:
            problems.append(
                f"beat map is not in increasing film order: {cid} ({cts}) comes "
                f"after {pid} ({pts}) but reads as earlier under {fmt}. If this "
                f"map is written in {other}, add 'ts_format: {other}' to the "
                f"beats_proposal.md header.")
            break

    # 2. inside the film
    dur = _film_duration(project)
    if dur:
        over = [f"{bid} ({ts})" for bid, secs, ts in written if secs > dur * 1.02]
        if over:
            problems.append(
                f"beat timestamps land past the end of the film "
                f"({dur / 60:.1f} min) when read as {fmt}: "
                + ", ".join(over[:5]) + (" ..." if len(over) > 5 else "")
                + f". A beat map written in {other} is the usual cause.")

    ordered = sorted(((bid, secs) for bid, secs, _ in written), key=lambda x: x[1])
    return {
        "fmt": fmt,
        "declared": declared in _BEAT_TS_FORMATS,
        "ordered": ordered,
        "by_id": {bid: secs for bid, secs in ordered},
        "problems": problems,
    }


def _fld(obj, key, default=None):
    """Read a field from either a dict or a schemas dataclass.

    `validate_draft` hands raw JSON dicts around; `_run_phase1_audits` hands
    parsed Draft/Line dataclasses. Both call into here, so neither shape may be
    assumed - an earlier version used .get() only, tested fine against a JSON
    fixture, and crashed the whole audit on the real pipeline.
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _lines_of(d):
    return _fld(d, "lines", None) or []


def binding_integrity(pdir, d) -> dict:
    """Report-only (stage 1). Which lines are bound to a catalogued shot?

    A line may declare `shot_id`; if it does, the id must exist and the line's
    clip window must sit inside that shot's window. If it does not, the shot is
    inferred from the timestamp - and a line whose clip_start falls in no
    catalogued window is FREE: nothing in shots.json stands behind it, so
    binding_audit / continuity_check / tag_audit have nothing to compare it to.

    Measured 2026-08-08: John Wick 0/91 free, Interstellar 0/106, Spider-Man
    19/76, Shutter Island 27/58. The free ones appear where the act-by-act
    enrichment pass (RULES A1) added lines without extending the catalogue.

    Returns {"total", "bound", "free", "free_ids", "bad_ref"}.
    """
    idx = _load_shot_index(pdir)
    out = {"total": 0, "bound": 0, "free": 0, "free_ids": [], "bad_ref": []}
    if not idx:
        return out
    by_id = {sid: (a, b) for a, b, _d, _f, sid in idx}

    for ln in _lines_of(d):
        # pool / montage lines already reference a catalogue label by name
        if _fld(ln, "pool") or _fld(ln, "montage"):
            continue
        cs = _fld(ln, "clip_start")
        if not cs:
            continue
        out["total"] += 1
        try:
            t = parse_ts(cs)
        except Exception:
            out["free"] += 1
            out["free_ids"].append(str(_fld(ln, "id")))
            continue

        sid = _fld(ln, "shot_id")
        if sid:
            win = by_id.get(str(sid))
            if not win:
                out["bad_ref"].append(
                    f"line {_fld(ln, 'id')}: shot_id {sid!r} not in catalogue")
            elif not (win[0] - 0.6 <= t < win[1]):
                out["bad_ref"].append(
                    f"line {_fld(ln, 'id')}: clip_start {cs} is outside shot {sid}")
            else:
                out["bound"] += 1
                continue

        if any(a - 0.6 <= t < b for a, b, _d, _f, _s in idx):
            out["bound"] += 1
        else:
            out["free"] += 1
            out["free_ids"].append(str(_fld(ln, "id")))
    return out


def catalogue_density(project, pdir) -> dict:
    """Is the catalogue rich enough to TELL the story, beat by beat?

    Not a shots-per-line ratio - shots per BEAT. The beat map is the human's own
    declaration of what the film's content is, so "enough footage to recap the
    content" is measurable against it: a beat with no catalogued shot cannot be
    shown at all, and a beat with one shot can only be shown one way.

    Why this is the preventive half of BINDING-INTEGRITY: a thin catalogue is
    what pushes the enrichment pass into inventing windows. Measured shots/beat
    - John Wick 3.07 and Interstellar 2.97 (both 0% free lines), Spider-Man 2.65
    (25% free), Shutter Island 1.11 (47% free).

    PROVISIONAL: four films. The global ratio alone does NOT separate Spider-Man
    from the healthy two - the per-beat list below is the signal that does, and
    the band should be re-derived after two more films.

    No-ops (and says so) without a beat map or without shots.json.
    """
    idx = _load_shot_index(pdir)
    bt = beat_times(project)
    bounds = bt.get("ordered") or []
    out = {"ok": False, "reason": "", "shots": len(idx), "beats": len(bounds),
           "ratio": 0.0, "empty": [], "thin": []}
    if not idx:
        out["reason"] = "no shots.json - cannot measure"
        return out
    if len(bounds) < 2:
        out["reason"] = "no usable beat map - cannot measure"
        return out

    dur = _film_duration(project) or (bounds[-1][1] + 600.0)
    edges = [(bid, s, (bounds[i + 1][1] if i + 1 < len(bounds) else dur))
             for i, (bid, s) in enumerate(bounds)]
    for bid, a, b in edges:
        n = sum(1 for s, _e, _d, _f, _i in idx if a <= s < b)
        if n == 0:
            out["empty"].append(str(bid))
        elif n == 1:
            out["thin"].append(str(bid))
    out["ratio"] = len(idx) / max(1, len(bounds))
    out["ok"] = True
    return out


def beat_coverage(project, d) -> dict:
    """Skeleton-free beat coverage for LINEAR projects.

    Each beat in beats_proposal.md carries a timestamp ('ts'). A beat is
    'covered' when >=1 draft line's clip_start falls in [this beat ts, next
    beat ts). Returns:
        {"beats": N, "covered": M, "uncovered": [beat_id, ...],
         "counts": {beat_id: n_lines}}
    Gate report AND stage machine both read these numbers (single source).
    Returns {"beats": 0, ...} when no beats have parseable timestamps.
    """
    bt = beat_times(project)
    result = {"beats": 0, "covered": 0, "uncovered": [], "counts": {},
              "ts_format": bt["fmt"], "ts_declared": bt["declared"],
              "ts_problems": bt["problems"]}
    bounds = bt["ordered"]
    if not bounds:
        return result

    # Explicit-timestamp line starts. Pool/montage lines have NO clip_start, so
    # they cannot be placed on the film's timeline and contribute nothing here.
    # That is invisible in linear mode (every linear project is 0-pool) but it
    # matters now this gate also runs on review projects: a beat covered ONLY by
    # a pool line would otherwise be reported UNCOVERED, which is a false
    # finding. Count them and make the report say so rather than stay silent
    # about the assumption it is standing on.
    line_secs = []
    unplaceable = 0
    for ln in d.lines:
        cs = getattr(ln, "clip_start", None)
        if not cs:
            unplaceable += 1
            continue
        try:
            line_secs.append(parse_ts(cs))
        except Exception:
            unplaceable += 1
            continue

    counts = {bid: 0 for bid, _ in bounds}
    for i, (bid, start) in enumerate(bounds):
        end = bounds[i + 1][1] if i + 1 < len(bounds) else float("inf")
        counts[bid] = sum(1 for s in line_secs if start <= s < end)

    covered = sum(1 for c in counts.values() if c > 0)

    # Longest RUN of consecutive uncovered beats (in film time order). A lone
    # uncovered beat between two adjacent lines is a coarse-beat granularity
    # artifact (a neighbouring line covers that content); a run of >=2 is a real
    # unnarrated stretch of film - the actual failure mode. We also record the
    # first such run so the report can name the skipped chunk.
    max_run = 0
    run = 0
    worst_run = []
    cur_run = []
    for bid, _ in bounds:
        if counts[bid] == 0:
            run += 1
            cur_run.append(bid)
            if run > max_run:
                max_run = run
                worst_run = list(cur_run)
        else:
            run = 0
            cur_run = []
    # collect every run of >=2 (all the genuine holes), for reporting
    consecutive_gaps = []
    cur = []
    for bid, _ in bounds:
        if counts[bid] == 0:
            cur.append(bid)
        else:
            if len(cur) >= 2:
                consecutive_gaps.append(list(cur))
            cur = []
    if len(cur) >= 2:
        consecutive_gaps.append(list(cur))

    result.update(
        beats=len(bounds),
        covered=covered,
        uncovered=[bid for bid, c in counts.items() if c == 0],
        counts=counts,
        max_consecutive_uncovered=max_run,
        consecutive_gaps=consecutive_gaps,
        unplaceable=unplaceable,
    )
    return result


def parse_reveal_map(project) -> list:
    """Parse the machine-readable ```reveal-map``` fenced block from
    beats_proposal.md into structured reveals. Returns [] when the block is
    absent (the gate is then a no-op).

    Block format (one reveal per line inside a ```reveal-map fence):
        R1 | land: B08 | hold: Doc Ock, Doctor Octopus, Otto Octavius
    - land:  a beat id (B08, resolved via parse_beats' HH:MM beat time) OR a raw
             HH:MM:SS timestamp OR 'mid-credits'/'stinger'/'none' (= protect
             always: land time +inf so ANY earlier mention flags).
    - hold:  comma-separated protected terms/aliases (word-boundary matched).
    Returns: [{"id": str, "land_ref": str, "land_sec": float, "holds": [str]}].
    """
    import re as _re
    from pipeline import catalogue as _cat
    pdir = config.project_dir(project)
    bp = pdir / "beats_proposal.md"
    if not bp.exists():
        return []
    text = bp.read_text(encoding="utf-8-sig")
    m = _re.search(r"```reveal-map\s*\n(.*?)```", text, _re.DOTALL | _re.IGNORECASE)
    if not m:
        return []
    block = m.group(1)

    # beat-id -> seconds, from the ONE validated resolution (see beat_times)
    beat_sec = {str(bid).upper(): s
                for bid, s in beat_times(project)["by_id"].items()}

    INF = float("inf")
    always = {"mid-credits", "midcredits", "stinger", "none", "credits"}
    reveals = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        rid = parts[0]
        land_ref, holds = None, []
        for seg in parts[1:]:
            low = seg.lower()
            if low.startswith("land:"):
                land_ref = seg.split(":", 1)[1].strip()
            elif low.startswith("hold:"):
                holds = [h.strip() for h in seg.split(":", 1)[1].split(",") if h.strip()]
        if not land_ref or not holds:
            continue
        # resolve landing time
        lr = land_ref.strip()
        if lr.lower() in always:
            land_sec = INF
        elif lr.upper() in beat_sec:
            land_sec = beat_sec[lr.upper()]
        else:
            try:
                land_sec = parse_ts(lr)          # raw HH:MM:SS
            except Exception:
                land_sec = INF                   # unresolvable -> protect always
        reveals.append({"id": rid, "land_ref": land_ref,
                        "land_sec": land_sec, "holds": holds})
    return reveals


def exception_key(reveal_id, beat_id, narration) -> str:
    """Durable key for reviewed_exceptions.md: reveal id + beat id + text hash.

    2026-10-20. The key USED to be "<reveal_id> L<line_id>", and line ids are
    assigned by assemble_draft.py in clip order - so renumbering the draft
    silently invalidated every declared exception. It happened: 'R2 L103' went
    stale the moment tokyodrift2006 was redrafted, and a stale entry is exactly
    how a gate dies quietly in the other direction (the finding moves, the note
    stays, and it covers the next one).

    Beat id survives renumbering. The text hash makes the entry specific to the
    WORDING a human actually reviewed: edit the line and the exception stops
    applying, which is correct - nobody reviewed the new sentence.
    """
    import hashlib as _hl
    import re as _re2
    norm = _re2.sub(r"\s+", " ", str(narration or "")).strip().lower()
    h8 = _hl.sha1(norm.encode("utf-8")).hexdigest()[:8]
    return f"{reveal_id} {beat_id or '?'} {h8}"


def reveal_timing_check(project, d) -> list:
    """REVEAL-TIMING: flag any protected reveal term spoken in narration BEFORE
    its landing time. Returns a list of hits:
        {reveal_id, term, line_id, beat_id, key, line_sec, land_ref, land_sec}
    LITERAL word-boundary text scan only - see the printed limit note. No-op
    (returns []) when there is no reveal-map block.
    """
    import re as _re
    reveals = parse_reveal_map(project)
    if not reveals:
        return []
    # precompile a word-boundary, case-insensitive matcher per term
    compiled = []
    for rv in reveals:
        for term in rv["holds"]:
            pat = _re.compile(r"\b" + _re.escape(term) + r"\b", _re.IGNORECASE)
            compiled.append((rv, term, pat))

    hits = []
    for ln in d.lines:
        narr = getattr(ln, "narration", "") or ""
        if not narr.strip():
            continue
        cs = getattr(ln, "clip_start", None)
        if not cs:                       # montage/pool: no film-time -> skip
            continue
        try:
            line_sec = parse_ts(cs)
        except Exception:
            continue
        _beat = (getattr(ln, "note", None)
                 or getattr(ln, "beat_id", None) or None)
        for rv, term, pat in compiled:
            if line_sec < rv["land_sec"] and pat.search(narr):
                hits.append({
                    "reveal_id": rv["id"], "term": term,
                    "line_id": getattr(ln, "id", "?"),
                    "beat_id": _beat,
                    "key": exception_key(rv["id"], _beat, narr),
                    "line_sec": line_sec,
                    "land_ref": rv["land_ref"], "land_sec": rv["land_sec"],
                })
    return hits


def parse_set_pieces(project) -> list:
    """Parse the machine-readable ```set-pieces``` fenced block from
    beats_proposal.md into structured set-pieces. Returns [] when the block is
    absent (the gate is then a no-op).

    Block format (one set-piece per line inside a ```set-pieces fence):
        SP3 | Statue of Liberty | 01:53:44 - 02:03:20 | verified: dense | keep
    - name:     free-text label (report readability).
    - start-end: film-time range. Each side is a beat id (B21, resolved via the
                HH:MM beat time) OR a raw HH:MM:SS timestamp.
    - verified: dense | sampled | unverified. 'dense' = frame-verified
                start-to-finish (trusted). Anything else on a KEPT row warns -
                a boundary you sampled is a boundary you cannot trust.
    - keep/drop: only 'keep' rows are measured; 'drop' rows are recorded so the
                human decision stays visible and is never silently re-proposed.
    Returns: [{"id","name","start_sec","end_sec","verified","keep","start_ref",
               "end_ref"}], drop rows included (keep=False) for reporting.
    """
    import re as _re
    from pipeline import catalogue as _cat
    pdir = config.project_dir(project)
    bp = pdir / "beats_proposal.md"
    if not bp.exists():
        return []
    text = bp.read_text(encoding="utf-8-sig")
    m = _re.search(r"```set-pieces\s*\n(.*?)```", text, _re.DOTALL | _re.IGNORECASE)
    if not m:
        return []
    block = m.group(1)

    # beat-id -> seconds, from the ONE validated resolution (see beat_times)
    beat_sec = {str(bid).upper(): s
                for bid, s in beat_times(project)["by_id"].items()}

    def _resolve(ref):
        ref = ref.strip()
        if ref.upper() in beat_sec:
            return beat_sec[ref.upper()]
        try:
            return parse_ts(ref)                 # raw HH:MM:SS
        except Exception:
            return None

    out = []
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        sp_id = parts[0]
        name, rng, verified, keep = "", None, "unverified", True
        # parts[1] is the name; the remaining segments are range / verified /
        # keep-drop in any order (range is the one containing a '-').
        name = parts[1]
        for seg in parts[2:]:
            low = seg.lower()
            if low.startswith("verified:"):
                verified = seg.split(":", 1)[1].strip().lower()
            elif low in ("keep", "drop"):
                keep = (low == "keep")
            elif "-" in seg and rng is None:
                rng = seg
        if rng is None:
            continue
        # split the range on the first ' - ' (times themselves have no bare ' - ')
        rparts = _re.split(r"\s-\s", rng, maxsplit=1)
        if len(rparts) != 2:
            continue
        start_sec = _resolve(rparts[0])
        end_sec = _resolve(rparts[1])
        if start_sec is None or end_sec is None or end_sec <= start_sec:
            continue
        out.append({
            "id": sp_id, "name": name,
            "start_sec": start_sec, "end_sec": end_sec,
            "start_ref": rparts[0].strip(), "end_ref": rparts[1].strip(),
            "verified": verified, "keep": keep,
        })
    return out


def _film_median_line_gap(d) -> float:
    """Median gap (seconds) between consecutive explicit-timestamp draft lines
    across the WHOLE film. This is the recap's own cadence - the reference the
    set-piece max-gap scales from. Returns 0.0 if <2 timed lines."""
    import statistics as _stats
    secs = []
    for ln in d.lines:
        cs = getattr(ln, "clip_start", None)
        if not cs:
            continue
        try:
            secs.append(parse_ts(cs))
        except Exception:
            continue
    secs.sort()
    gaps = [secs[i + 1] - secs[i] for i in range(len(secs) - 1)]
    return _stats.median(gaps) if gaps else 0.0


def set_piece_coverage(project, d) -> dict:
    """SET-PIECE COVERAGE: within each kept, dense-verified set-piece, no gap
    between consecutive narration lines (or from a range edge) may exceed the
    tier-relative max-gap. Returns:
        {"present": bool, "threshold": float, "median_gap": float,
         "results": [{id,name,worst_gap,worst_from,coverage,n_lines,
                      over,start_sec,end_sec}],
         "over": [id,...], "untrusted": [id,...]}
    No-op ({"present": False}) when there is no set-pieces block.

    Threshold (v1, provisional - calibrated on one film, revisit after the next):
        max(SETPIECE_MAXGAP_FLOOR, SETPIECE_MAXGAP_MULT x film median line gap)
    The failure mode is an unnarrated stretch a viewer can't follow, not a raw
    coverage %, so the largest gap decides. Non-combat stretches are unmarked
    (never measured) - the gate cannot fire on a quiet/dialogue scene.
    """
    sps = parse_set_pieces(project)
    if not sps:
        return {"present": False}

    floor = float(getattr(config, "SETPIECE_MAXGAP_FLOOR", 240.0))
    mult = float(getattr(config, "SETPIECE_MAXGAP_MULT", 3.0))
    median = _film_median_line_gap(d)
    threshold = max(floor, mult * median) if median > 0 else floor

    # explicit-timestamp line starts (montage/pool lines have no film time)
    line_secs = []
    for ln in d.lines:
        cs = getattr(ln, "clip_start", None)
        if not cs:
            continue
        try:
            line_secs.append(parse_ts(cs))
        except Exception:
            continue
    line_secs.sort()

    results, over, untrusted = [], [], []
    for sp in sps:
        if not sp["keep"]:
            continue                          # drop rows are recorded, not measured
        a, b = sp["start_sec"], sp["end_sec"]
        inr = [s for s in line_secs if a <= s < b]
        # gaps: from range start -> first line, between lines, last line -> end.
        pts = [a] + inr + [b]
        gaps = [(pts[i + 1] - pts[i], pts[i]) for i in range(len(pts) - 1)]
        if gaps:
            worst_gap, worst_at = max(gaps, key=lambda g: g[0])
        else:
            worst_gap, worst_at = (b - a), a
        span = b - a
        # coverage %: fraction of the span within ~half-threshold of a line
        # (context only; the gap decides). Reported, never gates.
        coverage = (len(inr) / max(1.0, span / max(1.0, median or 60.0))) if span else 0.0
        coverage = min(1.0, coverage)
        is_over = worst_gap > threshold
        res = {
            "id": sp["id"], "name": sp["name"],
            "worst_gap": worst_gap, "worst_from": worst_at,
            "n_lines": len(inr), "coverage": coverage,
            "over": is_over, "start_sec": a, "end_sec": b,
            "verified": sp["verified"],
        }
        results.append(res)
        if is_over:
            over.append(sp["id"])
        if sp["verified"] != "dense":
            untrusted.append(sp["id"])

    return {
        "present": True, "threshold": threshold, "median_gap": median,
        "floor": floor, "mult": mult,
        "results": results, "over": over, "untrusted": untrusted,
    }


def _run_phase1_audits(project, pdir):
    try:
        from pipeline import schemas
        from pipeline.coverage_audit import coverage_audit
        from pipeline.binding_audit import binding_audit
        from pipeline.continuity_check import continuity_check
        from pipeline.tag_audit import tag_audit
        from pipeline.validator_report import format_validator_report
    except Exception as e:
        console.print(f"[dim]Phase 1 audits unavailable: {e}[/]")
        return
    try:
        d = schemas.load_draft(project)
    except Exception as e:
        console.print(f"[dim]Phase 1 audits skipped (draft parse): {e}[/]")
        return
    skel = None
    try:
        skel = schemas.load_skeleton(project)
    except FileNotFoundError:
        skel = None
    except Exception as e:
        console.print(f"[yellow]skeleton.json present but invalid: {e}[/]")
        skel = None
    try:
        shots_by_id, pool_families, shot_problems = schemas.load_shots(project)
    except Exception as e:
        console.print(f"[red]footage could not be loaded at all: {e}[/]")
        shots_by_id, pool_families, shot_problems = {}, {}, [str(e)]
    # A dropped entry is invisible footage: every audit below runs on what
    # loaded, so a clean result means nothing until this list is empty. Loud,
    # red, and repeated in the summary - never a single yellow line that scrolls
    # past while the report underneath says "clean".
    for _p in shot_problems:
        console.print(f"[red][FOOTAGE-DROPPED][/] {_p}")
    if shot_problems:
        console.print(f"[red]  {len(shot_problems)} footage entr(ies) were skipped - "
                      f"the audits below are DEGRADED and cannot certify clean.[/]")
    names = schemas.load_names(project)
    cov = coverage_audit(d, skel) if skel is not None else []
    bind = binding_audit(d, shots_by_id, pool_families, names)
    cont = continuity_check(d, shots_by_id)
    tag_issues = tag_audit(shots_by_id)

    # ---- tag-coverage stats (so the audit can never silently no-op) ---------
    raw_pool = {}
    try:
        bp = pdir / "broll.json"
        if bp.exists():
            bd = json.loads(bp.read_text(encoding="utf-8-sig"))
            raw_pool = bd.get("pool", bd)
    except Exception:
        raw_pool = {}
    broll_total = len(raw_pool)
    broll_tagged = sum(1 for v in raw_pool.values()
                       if isinstance(v, dict) and (v.get("depicts") or v.get("chars")))
    untagged_broll = [k for k, v in raw_pool.items()
                      if isinstance(v, dict) and not (v.get("depicts") or v.get("chars"))]

    raw_shots = []
    sp = pdir / "shots.json"
    if sp.exists():
        try:
            raw_shots = json.loads(sp.read_text(encoding="utf-8-sig")).get("shots", [])
        except Exception:
            raw_shots = []
    shots_total = len(raw_shots)
    shots_tagged = sum(1 for s in raw_shots if s.get("depicts") or s.get("chars"))
    untagged_shots = [s.get("id", "?") for s in raw_shots
                      if not (s.get("depicts") or s.get("chars"))]

    lines_total = len(d.lines)
    lines_with_claim = sum(1 for l in d.lines if l.claim is not None)

    tag_stats = {
        "broll_total": broll_total, "broll_tagged": broll_tagged,
        "shots_total": shots_total, "shots_tagged": shots_tagged,
        "lines_total": lines_total, "lines_with_claim": lines_with_claim,
    }

    # explicit untagged-data warnings (visible, never silent)
    if untagged_broll:
        console.print(f"[yellow][UNTAGGED_BROLL][/] {len(untagged_broll)}/{broll_total} "
                      f"broll entries missing depicts/chars: "
                      f"{', '.join(untagged_broll[:8])}"
                      + (" ..." if len(untagged_broll) > 8 else ""))
    if untagged_shots:
        console.print(f"[yellow][UNTAGGED_SHOT][/] {len(untagged_shots)}/{shots_total} "
                      f"shots.json entries missing depicts/chars: "
                      f"{', '.join(str(x) for x in untagged_shots[:8])}")
    if lines_with_claim < lines_total:
        console.print(f"[yellow][LINE_NO_CLAIM][/] Lines with claim: "
                      f"{lines_with_claim}/{lines_total} "
                      f"({100*lines_with_claim/max(1,lines_total):.0f}%)")

    report_lines, sev = format_validator_report(cov, bind, cont, skel, d, tag_stats,
                                                tag_issues)
    for line in report_lines:
        console.print(line)

    # ---- Mức 1 binding-capacity check (surface BindingViolations PRE-render) -
    # The render no longer silently freezes a clip when narration overruns the
    # shot window; it raises BindingViolation. We surface those here, before any
    # render attempt, so the fix (split / multi-shot) happens at authoring time.
    try:
        from pipeline.schemas import binding_capacity_check, BINDING_SLOWDOWN_MAX
        cap = binding_capacity_check(d, shots_by_id)
    except Exception as e:
        console.print(f"[dim]binding-capacity check unavailable: {e}[/]")
        cap = []
    violations = [c for c in cap if c["severity"] == "violation"]
    slowdowns = [c for c in cap if c["severity"] == "slowdown"]
    if slowdowns:
        console.print(
            f"[yellow][BINDING-SLOWDOWN][/] {len(slowdowns)} line(s) need mild "
            f"slow-motion (<= {BINDING_SLOWDOWN_MAX:.1f}x) to fill their shot - OK, no freeze:")
        for c in slowdowns:
            console.print(
                f"    line {c['line_id']}: narr ~{c['narr_est']:.1f}s vs "
                f"shot {c['shot_dur']:.1f}s (cap {c['capacity']:.1f}s)")
    if violations:
        console.print(
            f"[red][BINDING-VIOLATION][/] {len(violations)} line(s) exceed shot "
            f"capacity ({BINDING_SLOWDOWN_MAX:.1f}x) - would freeze. Split further "
            f"or bind a multi-shot sequence:")
        for c in violations:
            console.print(
                f"    line {c['line_id']}: narr ~{c['narr_est']:.1f}s "
                f"> capacity {c['capacity']:.1f}s "
                f"(shot window {c['shot_dur']:.1f}s, {c['words']} words)")
        sev = "hard"   # block render until resolved

    # ---- Mức 3 capacity-aware narration check (per-shot word ceiling) --------
    # Using the calibrated voice profile, every shot has a max_narration_words_en.
    # Surface lines APPROACHING that ceiling (>= 80%) as a soft heads-up so the
    # writer knows they are near the limit, BEFORE they push a shot into a
    # render-time slowdown/violation. Information only; never hard-fails here
    # (the Mức 1 sum-based check above is the actual gate).
    try:
        from pipeline.catalogue import capacity_map
        cmap = capacity_map(project)
    except Exception as e:
        console.print(f"[dim]Mức 3 capacity map unavailable: {e}[/]")
        cmap = {}
    if cmap:
        near = []
        over = []
        for ln in d.lines:
            if ln.montage or ln.pool or ln.word_count() == 0:
                continue
            cs = ln.clip_start
            if not cs or cs not in cmap:
                continue
            ceiling = cmap[cs]
            if ceiling <= 0:
                continue
            w = ln.word_count()
            ratio = w / ceiling
            if ratio > 1.0:
                over.append((ln.id, w, ceiling))
            elif ratio >= 0.8:
                near.append((ln.id, w, ceiling))
        if over:
            console.print(
                f"[yellow][CAPACITY-WORDS][/] {len(over)} line(s) exceed the "
                f"calibrated word ceiling for their shot (will need slow-mo):")
            for lid, w, ce in over[:20]:
                console.print(f"    line {lid}: {w} words > shot max {ce}")
        if near:
            console.print(
                f"[dim][CAPACITY-WORDS] {len(near)} line(s) within 80-100% of "
                f"their shot word ceiling (approaching limit): "
                f"{', '.join('L%d %d/%d' % (lid, w, ce) for lid, w, ce in near[:12])}[/]")
        if not over and not near:
            console.print("[dim][CAPACITY-WORDS] all lines comfortably within "
                          "calibrated shot word ceilings.[/]")

    # ---- stage-aware gating (Stage 3a OUTLINE / 3b SCRIPT) -------------------
    # DRAFT-TARGET (real-rate / fill / tier-floor) is meaningless for a thin
    # OUTLINE pass whose job is coverage+binding. Run it ONLY in SCRIPT stage,
    # and ONLY for linear projects (review flow unchanged: always "script").
    from pipeline import state as _state
    from pipeline import catalogue as _cat2
    style = _cat2.parse_beats(project).get("style", "review")
    stage = _state.get_stage(project) if style == "linear" else "script"
    if stage == "script":
        _draft_target_report(project, d, cmap)
    else:
        console.print("[dim][STAGE] outline stage - DRAFT-TARGET skipped "
                      "(coverage/binding gate only).[/]")

    # ---- beat-coverage (skeleton-free; linear) - same numbers the stage
    # machine uses; surfaced here for visibility.
    # BEAT-COVERAGE: needs a beat map and timestamped lines. Neither is
    # linear-only - review projects carry beat maps too (gonegirl2014 36,
    # joker2019 37, parasite2019 28). Self-no-ops to {"beats": 0} when the beat
    # map is missing or unparseable, so it is safe to call unconditionally.
    # `bc` also feeds audit["beat_coverage"] -> outline_ready, but the stage
    # machine is separately gated on style == "linear" (see :475), so widening
    # this report does not reach it.
    bc = beat_coverage(project, d)
    if bc.get("beats"):
        # Always say WHICH timestamp convention produced these numbers, and
        # whether it was declared or assumed - the gate must never be silent
        # about the assumption it is standing on.
        src_note = "declared" if bc.get("ts_declared") else "assumed"
        msg = (f"[bold][BEAT-COVERAGE][/] {bc['covered']}/{bc['beats']} "
               f"beats have >=1 bound line "
               f"[dim](beat ts read as {bc.get('ts_format')}, {src_note})[/]")
        if bc["uncovered"]:
            msg += f"; uncovered: {', '.join(map(str, bc['uncovered'][:10]))}"
        console.print(msg)
        if bc.get("unplaceable"):
            console.print(
                f"    [dim]{bc['unplaceable']} line(s) unplaceable (no "
                f"clip_start - pool/montage): they cover no beat in this "
                f"count, so an 'uncovered' beat above may in fact be shown by "
                f"one of them.[/]")
    for _prob in bc.get("ts_problems", []):
        console.print(f"[red][BEAT-MAP][/] {_prob}")

    # ---- BINDING-INTEGRITY (stage 1: report only, never blocks) -------------
    pdir = config.project_dir(project)

    # BINDING-INTEGRITY is MODE-INDEPENDENT and no longer gated on style.
    # It asks one question - does this line's window land on a catalogued shot?
    # - of shots.json and clip_start, neither of which is linear-only. It
    # already skips pool/montage lines by hand (see :1180), which is the proof
    # it was written mode-safe; and it returns total=0 when shots.json is
    # absent, so it self-no-ops. Behind `if style == "linear":` it was dark on
    # 11 of 17 projects over data that was fully present - the same over-wide
    # scope this audit has been removing elsewhere (B5).
    bi = binding_integrity(pdir, d)
    if bi["total"]:
        if bi["free"]:
            ids = ", ".join(bi["free_ids"][:20])
            console.print(
                f"[yellow][BINDING-INTEGRITY][/] {bi['free']}/{bi['total']} "
                f"explicit-window line(s) are bound to NO catalogued shot: {ids}"
                f"{' ...' if len(bi['free_ids']) > 20 else ''}")
            console.print(
                "    Nothing in shots.json stands behind these, so the footage "
                "audits cannot check them at all. Split or add catalogue entries "
                "rather than pointing a line at a bare timestamp.")
            console.print("    [dim](report only for now - this does not block)[/]")
        else:
            console.print(f"[bold][BINDING-INTEGRITY][/] all {bi['bound']} "
                          f"explicit-window line(s) land on a catalogued shot")
    for _br in bi["bad_ref"]:
        console.print(f"[red][BINDING-INTEGRITY][/] {_br}")

    # ---- CATALOGUE-DENSITY ------------------------------------------------
    # Also mode-independent: shots.json + beat map, and it already self-no-ops
    # with a STATED reason when either is missing (see :1238) - i.e. it was
    # written to be called unconditionally and the style gate was redundant.
    # The beat map is the author's declaration of what the film contains; that
    # declaration exists in review mode too.
    cd = catalogue_density(project, pdir)
    if not cd["ok"]:
        console.print(f"[dim][CATALOGUE-DENSITY] not measured: {cd['reason']}[/]")
    else:
        msg = (f"[CATALOGUE-DENSITY] {cd['shots']} shots / {cd['beats']} beats "
               f"= {cd['ratio']:.2f} per beat")
        if cd["empty"]:
            console.print(f"[yellow][/]{msg}")
            console.print(f"    [yellow]{len(cd['empty'])} beat(s) have NO shot "
                          f"catalogued: {', '.join(cd['empty'][:15])}[/] - these "
                          f"cannot be shown at all; the draft will have to invent "
                          f"windows for them.")
        elif cd["thin"]:
            console.print(f"[bold]{msg}[/]")
            console.print(f"    [dim]{len(cd['thin'])} beat(s) have only one shot: "
                          f"{', '.join(cd['thin'][:15])} - one way to show them.[/]")
        else:
            console.print(f"[bold]{msg}[/] [dim]- every beat has >=2 shots[/]")
        console.print("    [dim]band PROVISIONAL (4 films): the per-beat list is "
                      "the signal, the ratio alone does not separate a healthy "
                      "catalogue from a thin one.[/]")

    if style == "linear":
        # ---- SNAP-GRID: do catalogue boundaries land on real visual cuts? ----
        # NOT moved. It is arguably mode-independent too, but it was not part of
        # this change and moving it because it is ADJACENT is exactly how the
        # style conditional got over-wide in the first place. Assessed and left;
        # see the report.
        from pipeline import cuts as _cuts
        sg = _cuts.snap_report(project, _load_shot_index(pdir))
        if not sg["measured"]:
            console.print(f"[dim][SNAP-GRID] not measured: {sg['reason']}[/]")
        elif sg["off"]:
            pct = 100.0 * sg["off"] / sg["total"]
            console.print(f"[yellow][SNAP-GRID][/] {sg['off']}/{sg['total']} boundaries "
                          f"({pct:.0f}%) sit more than {sg['tolerance']:.0f}s from any "
                          f"detected cut - those clips open or close mid-scene.")
            # NB: no loop variable here may be named `d` - that is the Draft
            # object for this whole function, and shadowing it breaks every
            # audit that runs after this block.
            for _sid, _kind, _t, _dist in sg["offenders"][:8]:
                console.print(f"    {int(_t)//60:02d}:{int(_t)%60:02d}  {_kind:<5} "
                              f"off by {_dist:5.1f}s   {_sid}")
            if len(sg["offenders"]) > 8:
                console.print(f"    ... and {len(sg['offenders']) - 8} more")
        else:
            console.print(f"[bold][SNAP-GRID][/] all {sg['total']} boundaries land "
                          f"within {sg['tolerance']:.0f}s of a real cut "
                          f"[dim]({sg['cuts']} cuts detected)[/]")

    # ---- SET-PIECE COVERAGE (linear, SCRIPT stage ONLY) ----------------------
    # A followability-critical fight needs no long unnarrated stretch. Measures
    # ONLY human-confirmed, dense-verified set-piece ranges (never a quiet scene
    # - non-combat is deliberately unmarked). Script-only, because an OUTLINE is
    # thin everywhere by design (mirrors DRAFT-TARGET's stage gating). Soft-only:
    # escalate sev, never downgrade hard. No-op without a set-pieces block.
    sp_cov = {"present": False}
    if style == "linear" and stage == "script":
        sp_cov = set_piece_coverage(project, d)
    if sp_cov.get("present"):
        thr = sp_cov["threshold"]
        console.print(
            f"[bold][SET-PIECE][/] max-gap threshold [bold]{thr:.0f}s[/] "
            f"= max({sp_cov['floor']:.0f}, {sp_cov['mult']:.0f}x median "
            f"{sp_cov['median_gap']:.0f}s) | measuring "
            f"{len(sp_cov['results'])} kept set-piece(s)")
        for r in sp_cov["results"]:
            tag = "[yellow]OVER[/]" if r["over"] else "[green]ok[/]"
            console.print(
                f"    {tag} {r['id']} {r['name']}: worst gap "
                f"{r['worst_gap']:.0f}s @ ~{r['worst_from']/60:.1f} min "
                f"({r['n_lines']} line(s) in range)")
        if sp_cov["over"]:
            console.print(
                f"[yellow][SET-PIECE-UNDER][/] {len(sp_cov['over'])} set-piece(s) "
                f"have an unnarrated stretch over {thr:.0f}s "
                f"({', '.join(sp_cov['over'])}) - the fight may lose its thread. "
                f"Add a stage-line inside the gap (Setup -> Action -> Consequence).")
            sev = "hard" if sev == "hard" else "soft"
        if sp_cov["untrusted"]:
            # method-honesty: a KEPT range not dense-verified cannot be trusted.
            console.print(
                f"[yellow][SET-PIECE-UNVERIFIED][/] {len(sp_cov['untrusted'])} "
                f"kept set-piece(s) not marked 'verified: dense' "
                f"({', '.join(sp_cov['untrusted'])}) - the RANGE itself is "
                f"untrusted (a sampled boundary drifts). Dense-verify start/end "
                f"before relying on this gate for them.")
            sev = "hard" if sev == "hard" else "soft"
        console.print("[dim][SET-PIECE] measures ONLY human-confirmed combat "
                      "ranges; quiet/dialogue scenes are unmarked by design and "
                      "never flagged. Threshold is v1 (provisional).[/]")
    elif style == "linear" and stage != "script":
        console.print("[dim][SET-PIECE] outline stage - skipped "
                      "(density is only expected once enriching).[/]")

    # ---- REVEAL-TIMING (linear, ALWAYS-ON regardless of stage) ---------------
    # A spoiler can enter at outline OR during enrichment, and even a thin
    # outline can spoil, so this is not stage-gated. Soft-only: escalate sev to
    # "soft" if any hit, but NEVER downgrade an existing "hard". No-op when the
    # project has no reveal-map block.
    reveal_hits = reveal_timing_check(project, d) if style == "linear" else []
    # 2026-09-10: REVEAL-TIMING truoc day KHONG tra cuu reviewed_exceptions.md.
    # Viet mot muc cho no vao file do se la mot ghi chep CHET - trong giong nhu
    # da duoc xu ly, ma khong he duoc doc.
    # 2026-10-20: khoa KHONG con la "<reveal_id> L<line_id>". Line id do
    # assemble_draft.py gan theo thu tu clip, nen danh so lai lam moi muc da
    # khai bao mat hieu luc trong im lang - va dieu do da xay ra: 'R2 L103'
    # thanh STALE ngay khi tokyodrift2006 duoc viet lai. Khoa moi la
    # "<reveal_id> <beat_id> <hash8 cua loi>": beat id song qua danh so lai, va
    # hash buoc muc nay vao DUNG cau ma nguoi ta da doc.
    # `_revd` song trong validate_draft, khong phai trong ham nay - lan dau toi
    # dung thang no o day va duoc NameError. Nap lai tai cho.
    _revd, _ = _reviewed.load(pdir)
    _revd_hit = set()
    _rt_reviewed = []
    if reveal_hits:
        _keep = []
        for h in reveal_hits:
            _k = h["key"]
            _exc = _revd.get(("REVEAL-TIMING", _k))
            if not _exc:
                # Khoa cu ("R2 L103") van duoc NHAN RA de bao cho nguoi dung
                # biet phai doi sang dang nao - nhung KHONG duoc dung de mien
                # tru. Mot khoa het han thi phai het han.
                _legacy = f"{h['reveal_id']} L{h['line_id']}"
                if ("REVEAL-TIMING", _legacy) in _revd:
                    console.print(
                        f"[yellow][REVIEWED-EXCEPTION][/] '{_legacy}' uses the "
                        f"OLD line-number key and no longer grants anything. "
                        f"Line numbers move when a draft is renumbered. "
                        f"Replace it with:\n    REVEAL-TIMING | {_k} | "
                        f"<YYYY-MM-DD> | <reason>")
            if _exc:
                _revd_hit.add(("REVEAL-TIMING", _k))
                _rt_reviewed.append((_k, _exc))
            else:
                _keep.append(h)
        reveal_hits = _keep
    for _k, (_dt_, _rs) in _rt_reviewed:
        console.print(f"[dim][REVEAL-TIMING] {_k}: REVIEWED {_dt_} - "
                      f"{_rs[:120]}[/]")
    # Kiem tra "stale" cho REVEAL-TIMING phai nam O DAY, khong phai cung cho
    # voi VISUAL-REPEAT o dau ham: vong lap kia chay TRUOC khi reveal check
    # chay, nen luc do _revd_hit con rong va moi muc REVEAL-TIMING deu se bi
    # goi nham la stale.
    for (_g, _k), (_d2, _r2) in _revd.items():
        if _g == "REVEAL-TIMING" and (_g, _k) not in _revd_hit:
            console.print(f"[yellow][REVIEWED-EXCEPTION][/] STALE - "
                          f"REVEAL-TIMING '{_k}' (reviewed {_d2}) no longer "
                          f"occurs; delete the entry so it cannot cover a "
                          f"future finding.")
    if reveal_hits:
        console.print(f"[yellow][REVEAL-TIMING][/] {len(reveal_hits)} "
                      f"possible early reveal(s) - a protected term appears "
                      f"BEFORE its landing beat:")
        for h in reveal_hits[:20]:
            land = "always" if h["land_sec"] == float("inf") else h["land_ref"]
            console.print(
                f"    {h['reveal_id']}: \"{h['term']}\" in line {h['line_id']} "
                f"(~{h['line_sec']/60:.1f} min) lands before {land}")
            # In ra DUNG khoa can dan vao reviewed_exceptions.md. Khong co no,
            # nguoi dung phai tu doan hash, va se quay ve dat khoa theo so dong.
            console.print(f"[dim]      key: {h['key']}[/]")
        # escalate to soft, never downgrade hard
        sev = "hard" if sev == "hard" else "soft"
    # Honest-limit note prints whenever a reveal-map exists (hits or not), so no
    # one mistakes a clean pass for spoiler-proof.
    if style == "linear" and parse_reveal_map(project):
        console.print("[dim][REVEAL-TIMING] literal-term text scan; it cannot "
                      "catch paraphrase or implied foreshadowing - the Stage-7 "
                      "watch remains the spoiler backstop.[/]")

    # Return everything the stage machine needs (sev + honest metrics).
    # bind.verified_mismatch / bind.unverified are the SAME ints the Summary
    # line prints (BindingResult fields), so numbers cannot diverge.
    return {
        "sev": sev,
        "style": style,
        "stage": stage,
        "beat_coverage": bc,
        "binding_mismatch": bind.verified_mismatch,
        "binding_unverified": bind.unverified,
        # How much the binding audit actually LOOKED AT. Without these,
        # "0 mismatch / 0 unverified" is indistinguishable from "the audit was
        # never given an input" - which is how every draft in this repo promoted
        # while binding_audit examined nothing. See outline_ready/audit_examined.
        "binding_checked": bind.checked,
        "binding_verified": bind.verified_match + bind.speaker_verified,
        "continuity_issues": len(cont),
        "binding_violations": len(violations),
        "reveal_hits": len(reveal_hits),
        "set_piece_over": len(sp_cov.get("over", [])) if sp_cov.get("present") else 0,
    }


def _draft_target_report(project, d, cmap):
    """DRAFT-TARGET: real-rate runtime + tier-floor + capacity-fill (all soft)."""
    from pipeline import calibration as _cal
    from pipeline import catalogue as _cat

    profile = _cal.get_profile(
        getattr(config, "DEFAULT_TTS_VOICE", None),
        getattr(config, "DEFAULT_TTS_RATE", "+22%"))

    # --- real-rate runtime: sum per-line spoken seconds + silence seconds ----
    # Narrated seconds come from the draft lines (at the calibrated rate).
    real_sec = 0.0
    total_words = 0
    # Silence seconds come from the DRAFT LINES, not from shots.json.
    #
    # The comment that used to sit here said the opposite - "silence seconds
    # live on SHOTS (a silence shot binds no draft line, per C1)" - and that is
    # the inverse of C1. TAGGING_GUIDE S9 and SCRIPTING_CHECKLIST C1 both state,
    # in bold, that the RENDERER iterates draft LINES and that a silence tagged
    # only on a shot "is silently DROPPED at render" (the 2026-07-01 Interstellar
    # bug). So a correctly authored silence beat is a draft line, and reading
    # shots.json meant this gate graded a number unrelated to the draft.
    #
    # Measured on howtomakemillions2024 before the fix: the draft held 243s
    # across 15 silence LINES, of which this counted 0; it counted 29s from four
    # SHOTS tagged in passes 1-2, two of which that cut does not stop on. The
    # gate then told a 20-minute draft to "enrich the narration" for runtime it
    # already had. The faster the cut, the smaller the error, which is why eight
    # films never surfaced it.
    sil_sec = 0.0
    n_sil = 0
    for ln in d.lines:
        s = getattr(ln, "narration_silence_seconds", None)
        if s:
            # a silence line carries no words but real runtime
            sil_sec += float(s)
            n_sil += 1
            continue
        w = ln.word_count() if hasattr(ln, "word_count") else len(str(getattr(ln, "narration", "")).split())
        if w == 0:
            continue
        total_words += w
        real_sec += profile.estimate_narration_seconds(getattr(ln, "narration", "") or "")
    real_sec += sil_sec
    # --- ONE runtime basis: the MEASURED rate of the voice being rendered ---
    # 2026-09-09: truoc day o day in RA HAI con so runtime - `real_min` theo
    # nhip do duoc cua giong (3.5 w/s = 210 WPM) va `cons_min` theo 170 WPM -
    # trong khi script.txt chi in con so 170. Hai co so cung song, va ngan sach
    # tu duoc lap tu con so nho hon: draft "dat" 20.6 phut trong khi tai lieu
    # nguoi doc that su noi 24.7. Mot dai luong, mot co so.
    # Nhip do duoc 3.5 w/s KHONG bi xoa khoi repo - no van la phep do that cho
    # voice_profiles.json va van dung cho TRAN capacity (max_words_for_capacity,
    # thu no duoc hieu chuan de lam). No chi khong con la mot co so runtime
    # thu hai nua. He qua phai noi ro: uoc tinh 170 WPM la CO Y BAO THU, va
    # video that se ngan hon con so nay khoang 19%.
    # 2026-09-09 (v2): co so la NHIP DO DUOC cua chinh giong se duoc render.
    # Ban truoc chon 170 WPM lam co so duy nhat; 170 la mot heuristic bao thu,
    # con 3.5 w/s la mot phep DO tren dau ra TTS that cua giong do. Lay con so
    # te hon lam chuan chi vi no "an toan" la danh doi do chinh xac lay su de
    # chiu. config.TTS_WORDS_PER_MINUTE gio chi la DU PHONG cho giong chua tung
    # duoc do - va ban in ra luon noi ro no dang dung co so nao.
    if profile.is_measured:
        wpm = profile.words_per_minute
        basis = f"measured rate of {profile.voice_id}"
    else:
        wpm = float(getattr(config, "TTS_WORDS_PER_MINUTE", 170))
        basis = (f"config.TTS_WORDS_PER_MINUTE fallback - no measured profile "
                 f"for this voice")
    # Khoang nghi giua cac dong la runtime THAT. Bo qua no thi uoc tinh luon
    # ngan hon thuc te mot cach co he thong: tren ban render badgenius2017_machine
    # loi do do la +7.4%, trong do 190 x 0.18s = 34s la khoang nghi.
    _n_narr = sum(1 for ln in d.lines
                  if not getattr(ln, "narration_silence_seconds", None)
                  and str(getattr(ln, "narration", "") or "").strip())
    gap_sec = _n_narr * float(profile.pause_overhead_sec)
    est_min = total_words / wpm + (sil_sec + gap_sec) / 60.0
    cons_min = est_min

    console.print(f"[bold cyan][DRAFT-TARGET][/] runtime est: "
                  f"[bold]{est_min:.1f} min[/] "
                  f"({total_words} words at {wpm:.0f} WPM"
                  + (f" + {sil_sec:.0f}s silence" if sil_sec else "")
                  + f" + {gap_sec:.0f}s line gaps"
                  + f"; basis: {basis})")
    if not profile.is_measured:
        console.print(f"    [yellow]no measured profile for "
                      f"{getattr(config, 'DEFAULT_TTS_VOICE', '?')} - this "
                      f"figure is a heuristic, not a measurement. Calibrate "
                      f"with: python -m pipeline.calibration --project "
                      f"{project} --voice <id>[/]")
    if n_sil:
        console.print(f"    [dim]includes {sil_sec:.0f}s of authored silence "
                      f"across {n_sil} beat(s), read from draft lines[/]")

    # 2026-09-09: o day tung co mot "divergence note" bao nguoi doc HAY TIN con
    # so real-rate thay vi con so 170 WPM. Do chinh la cai lam cho hai co so
    # cung ton tai va khien toi lap ngan sach tu con so sai. Da bo. Phan cong bo
    # ve nhip do duoc nay nam ngay duoi con so runtime duy nhat, va no noi ro
    # con so nao la co so lap ngan sach.

    # --- tier floor check ----------------------------------------------------
    tiers = getattr(config, "DEPTH_TIERS", {})
    try:
        binfo = _cat.parse_beats(project)
        tier = binfo.get("tier") or binfo.get("tier_inferred")
        style = binfo.get("style", "review")
    except Exception:
        tier = None
        style = "review"
    _guide = "prompts/style_linear_vn.md" if style == "linear" else "prompts/recap_style.md"
    console.print(f"    [dim]narration style: [bold]{style}[/] ({_guide})[/]")
    # TIER IS AN INPUT, NOT A GATE (2026-09-05). [DRAFT-UNDER-TARGET] compared
    # real-rate runtime against a per-tier floor and warned below it. It was
    # removed, not relaxed, because the floor was the cheapest red-to-green move
    # in the repo: the same author who fails it also chooses the tier, so the
    # warning clears by editing one word in beats_proposal.md. That happened to
    # badgenius2017 on 2026-09-04 - dropped video_essay -> fuller_recap, three
    # paragraphs of justification, and the number it rested on turned out to be
    # an artefact of a broken capacity denominator. The rule governing it (A11)
    # is retired in docs/RULES.md for the same reason: the rule was sound, the
    # thing it governed should never have been a gate.
    # The tier NAME stays as a descriptive label. It carries no threshold.
    if tier:
        console.print(f"    [dim]tier label: {tier} (descriptive only - no "
                      f"runtime threshold is applied)[/]")
    # [TARGET-LOCK] - target_minutes is the AUTHOR's declaration of scale.
    # It replaces the tier floor as the thing that says how long this should be,
    # and it is deliberately NOT a threshold: nothing compares runtime against
    # it. What IS checked is that it stays the author's number. The engine pins
    # it in state.json the first time it sees it; a later disagreement is
    # reported with both values. A writing model can still edit the file - it
    # just cannot do so silently, which is the whole difference between an input
    # and a gate you can move.
    # read from the FILE: `d` here is the typed Draft object, which carries only
    # project+lines - target_minutes lives in the raw json.
    try:
        _declared = json.loads(
            (config.project_dir(project) / "draft.json").read_text(
                encoding="utf-8-sig")).get("target_minutes")
    except Exception:
        _declared = None
    if _declared:
        try:
            from pipeline import state as _state
            _st = _state.load_state(project) or {}
            _pinned = _st.get("declared_target_minutes")
            if _pinned is None:
                _st["declared_target_minutes"] = _declared
                _st["declared_target_pinned"] = _dt.datetime.now(
                    _dt.timezone.utc).isoformat(timespec="seconds")
                _state.save_state(project, _st)
                console.print(f"    [dim]author target: {_declared} min "
                              f"(pinned; guidance on scale, not a threshold)[/]")
            elif float(_pinned) != float(_declared):
                console.print(f"    [yellow][TARGET-LOCK][/] target_minutes "
                              f"changed: author declared [bold]{_pinned}[/], "
                              f"draft.json now says [bold]{_declared}[/]. The "
                              f"target is an INPUT - if the length should "
                              f"change, the author changes it, not the draft.")
            else:
                console.print(f"    [dim]author target: {_declared} min "
                              f"(guidance on scale; nothing is compared "
                              f"against it)[/]")
        except Exception as _e:                       # pragma: no cover
            console.print(f"    [dim]author target: {_declared} min[/]")

    # --- capacity fill -------------------------------------------------------
    if cmap:
        used = 0
        ceil_sum = 0
        per_unit_head: dict = {}   # unit_id -> (words, ceiling)
        for ln in d.lines:
            if getattr(ln, "montage", None) or getattr(ln, "pool", None):
                continue
            cs = getattr(ln, "clip_start", None)
            if not cs or cs not in cmap:
                continue
            ceiling = cmap[cs]
            if ceiling <= 0:
                continue
            w = ln.word_count() if hasattr(ln, "word_count") else len(str(getattr(ln, "narration", "")).split())
            used += w
            ceil_sum += ceiling
            uid = getattr(ln, "unit_id", None) or "?"
            pw, pc = per_unit_head.get(uid, (0, 0))
            per_unit_head[uid] = (pw + w, pc + ceiling)
        if ceil_sum > 0:
            fill = used / ceil_sum
            lo, hi = getattr(config, "DRAFT_FILL_TARGET", (0.70, 0.85))
            under = float(getattr(config, "DRAFT_FILL_UNDER_WARN", 0.65))
            over = float(getattr(config, "DRAFT_FILL_OVER_WARN", 0.90))
            band_note = ("within target" if lo <= fill <= hi else
                         "UNDER target" if fill < lo else "over target")
            console.print(f"    capacity fill: [bold]{fill*100:.0f}%[/] "
                          f"({used}/{ceil_sum} words; target {int(lo*100)}-{int(hi*100)}%) "
                          f"[{band_note}]")
            if fill < under:
                # surface the units with the most unused capacity headroom
                room = sorted(
                    ((uid, pc - pw, pw, pc) for uid, (pw, pc) in per_unit_head.items() if pc > pw),
                    key=lambda x: -x[1])[:6]
                room_str = ", ".join(f"{uid} ({pw}/{pc}w)" for uid, _, pw, pc in room)
                console.print(f"    [yellow][DRAFT-UNDERFILL][/] fill {fill*100:.0f}% "
                              f"is below {int(under*100)}% - the draft leaves shot "
                              f"capacity unused. Most room to enrich: {room_str}.")
            elif fill > over:
                console.print(f"    [yellow][DRAFT-OVERFILL][/] fill {fill*100:.0f}% "
                              f"exceeds {int(over*100)}% - lines are near capacity; "
                              f"expect slow-motion across many shots.")



