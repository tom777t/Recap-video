# -*- coding: utf-8 -*-
"""craft_gates.py - PHASE 1 writing-craft gates.

Cai nay do THU VIET, khong do tinh dung. Moi nguong o day duoc chot trong
`docs/WRITING_CRAFT_CRITERION.md` TRUOC khi gate duoc viet, va moi nguong
deu duoc do tren hai ban draft that:

    HUMAN   projects/badgenius2017/draft.json    (chuan vang, PHAI pass)
    MACHINE projects/tokyodrift2006/draft.json   (ban bi che, PHAI fail)

Bao cao goc (`docs/RECAP_CRAFT_RESEARCH.md`) de xuat 11 nguong. NAM trong so
do bi bo hoac doi, vi do tren hai ban draft that thi:
  - 2b (>=5% cau >=30 tu): ban NGUOI chi dat 4.3% -> chuan vang truot cong.
  - 2c (>=15% cau <=5 tu): ban MAY da dat 16.3% -> cong khong tu choi duoc gi.
  - 2d (<=15% mo dau chi noi/thoi gian): lat nguoc theo dinh nghia regex.
  - 4  (hook >=20% runtime): ban NGUOI o 1.05%, SOM HON ban may 2.23%.
  - 8  (phan xet moi 8 dong): bang chung cua chinh bao cao la ~1 moi 25 dong.
Mot cong ma chuan vang truot la cong sai, khong phai chuan vang sai.

YEU DIEM DA BIET: `payload` va `hook_question` la truong TU KHAI. Mot nguoi
viet co the gan nhan `stake` cho mot dong ta canh thuan tuy va PAYLOAD-MIX se
xanh - dung nhu B9 (fill mu truoc comprehension) va B11 (cong xanh khong
chung minh gi). Vi vay AUDIT bang subagent ngu canh moi LA MOT PHAN cua cong:
khong co audit thi PAYLOAD-MIX chi la trang tri.
"""
from __future__ import annotations

import re
import statistics as _st

# --- nguong, chot tai docs/WRITING_CRAFT_CRITERION.md ----------------------
PAYLOAD_KINDS = ("stake", "reasoning", "judgment", "loop", "rest")

BAR_REST_SHARE = 0.25        # item 1
BAR_REST_RUN = 3             # item 1
BAR_SD = 9.0                 # item 2a  (HUMAN 13.7 / MACHINE 3.9)
BAR_LONG_SHARE = 0.02        # item 2b  (HUMAN 4.3% - bao cao doi 5%, chuan vang truot)
BAR_PUNCH_SHARE = 0.03       # item 2c  (HUMAN 5.9% / MACHINE 1.3%)
BAR_OPENER_SHARE = 0.15      # item 2d  (canh bao)
BAR_JUDGE_EVERY = 30         # item 8   (HUMAN ~1 moi 24.5)
BAR_JUDGE_MIN = 4            # item 8
BAR_LOOP_GAP = 12            # item 9   (~2x mat do HUMAN bao cao trich)
BAR_SILENCE_MIN = 2.0        # item 11
BAR_SILENCE_WARN = 12.0      # item 11  (HUMAN co mot don 20.0s)
BAR_SILENCE_COUNT = (3, 6)   # item 11
BAR_ACTION_STAKE_EVERY = 4   # item 7

# --- TRAN (ceilings), them 2026-10-20 -------------------------------------
# Lan chay lai dau tien dat MOI nguong tren va cho ra mot ban 58 phut. Ly do
# khong phai target do dai bi bo - ma la MOI nguong o tren deu la SAN khong co
# TRAN. Tam nguoi viet act doc lap, moi nguoi toi da hoa tung san:
#   cau dai  4.3% (nguoi) -> 18.9%   (4.4x)
#   phan xet 7.5% (nguoi) -> 27.5%   (3.7x)
#   dong/beat 1.93 (nguoi) -> 3.24   (1.7x)
# Ban draft di tu "moi dong la mot dong nghi" sang "moi dong deu nang" - mot
# loi KHAC, khong phai loi da sua. Duc tinh cua ban nguoi la TY LE cua no,
# khong phai muc toi thieu cua no. Nen cac dai duoi day do tu ban nguoi, co
# khoang du ca hai chieu. Day la cong THU VIET, khong phai cong THOI LUONG:
# khong co gi so sanh voi mot so phut nao ca.
BAR_LONG_SHARE_MAX = 0.12      # nguoi 4.3%  (du 2.8x) | lan chay lai 18.9% truot
BAR_JUDGE_SHARE_MAX = 0.15     # nguoi 7.5%  (du 2.0x) | lan chay lai 27.5% truot
BAR_LINES_PER_BEAT_MAX = 2.5   # nguoi 1.93  (du 1.3x) | lan chay lai 3.24 truot

# --- [DENSITY] tran TU-TREN-BEAT ------------------------------------------
# Day la dai luong chan viec PHINH TONG. Khong phai words-per-line: dat tran
# len do dai DONG chinh la cach ban pre-craft dat SD 3.9 - moi dong bi cat
# bang nhau. Tu-tren-beat chan tong ma van de nguoi viet dai ngan tuy y, vi
# san SD (BAR_SD) van bat buoc phai co bien thien.
# Do duoc tren hai ban da duoc nguoi duyet:
#     badgenius2017 (nguoi viet)          45.6 w/beat
#     badgenius2017_machine (da render)   42.9 w/beat
# va tren hai ban bi tu choi:
#     tokyodrift pre-craft                31.4  (khong phinh - no NGHEO noi dung)
#     tokyodrift lan chay lai 58 phut    105.7
BAR_WORDS_PER_BEAT_MAX = 60.0  # du 1.32x so voi 45.6 | ban 58 phut 105.7 truot

# Duoi nguong nay, thong ke nhip khong co nghia -> KHONG ra loi cung.
# Ly do thuc dung: gate_selftest.py chay hang chuc fixture 2-5 dong. Mot gate
# moi giet cac fixture do se lam CHET cac gate cu truoc khi chung kip chay -
# dung loi da xay ra voi [TITLE-MATCH] (xem draft.py ~404).
MIN_LINES_FOR_STATS = 40

_OPENER_NARROW = re.compile(
    r"^(in|at|on|outside|inside|across|down the|up the|night|day|morning|"
    r"evening|later|meanwhile|dawn|dusk|by the|from the|through the|over the|"
    r"under the|behind the|beside the|near the|back (at|in|on))\b", re.I)

_SPEECH_HARD = [
    (re.compile(r"whatever (he|she|they) (say|says)", re.I),
     "\"whatever he/she says\" - the narrator is admitting it did not read the "
     "transcript. Say what was said, or cut the line."),
    (re.compile(r"\b(answers|replies|responds|says)\s+"
                r"(loudly|quietly|softly|flatly|sharply|coldly|calmly)\b", re.I),
     "reports HOW a line was delivered but not WHAT was said. Quote it or cut it."),
]
_SPEECH_SOFT = [
    (re.compile(r"\bsays something\b", re.I),
     "\"says something\" - acceptable only if the line also gives the "
     "consequence. Prefer the actual words."),
    (re.compile(r"\ba visitor\b", re.I),
     "introduces \"a visitor\" - an unresolved referent. Name them here or "
     "within the next few lines."),
]

# Phan xet / aside cua nguoi ke. Day la mot PROXY bang regex cho mot thuoc
# tinh ngu nghia; no bat duoc 6 dong trong ban NGUOI va 0 trong ban MAY, nhung
# no se bo sot cac cach dien dat khac. Tren draft v2, nhan `payload: judgment`
# moi la nguon chinh; regex chi de cham diem draft cu.
_JUDGE = [
    re.compile(r"\bwhich is (what|the part|worse|new|enough|why)\b", re.I),
    re.compile(r"\bthat is the (whole|only|part)\b", re.I),
    re.compile(r"\b(honestly|frankly|of course|somehow|apparently)\b", re.I),
    re.compile(r"\bthe (film|movie|camera|script) (keeps|stays|never|cuts|holds|gives)\b", re.I),
    re.compile(r"\bnobody .{0,24}\b(likes|trusts|cares)\b", re.I),
    re.compile(r"\bwhich is worse than\b", re.I),
    re.compile(r"\bin the way that\b", re.I),
]

_ANON = re.compile(
    r"\bthe (gangster|man|woman|guy|boy|girl|kid|leader|enemy|stranger)\b"
    r"|\bone of them\b", re.I)

_CTA = re.compile(r"\b(subscribe|comment|like (this|the) video|tell me what|"
                  r"hit the bell|the channel)\b", re.I)

_TITLE_YEAR = re.compile(r"\(\s*(19|20)\d{2}\s*\)\s*$")

# Mot tieu de tien de la MOT MENH DE ("Students Don't Realise Their Teacher Is
# A Kungfu Legend"), con mot tieu de ten phim la mot CUM DANH TU ("Tokyo
# Drift", "Bad Genius (2017)"). Thu phan biet duoc hai thu do bang may la: co
# mot dong tu hay khong. Day la PROXY, khong phai phan tich cu phap - nhung do
# tren bay tieu de that thi no phan loai dung ca bay:
#   premise  : badgenius nguoi (11 tu), tokyodrift moi (17), hai cua
#              Mystery Recapped (9, 10)
#   name-only: "The Fast and the Furious: Tokyo Drift (2006)", "Tokyo Drift",
#              "Bad Genius (2017)"
_TITLE_VERB = re.compile(
    r"\b("
    r"is|are|was|were|be|been|has|have|had|do|does|did|can|can't|cant|could|"
    r"will|would|won't|wont|must|should|may|might|gets?|got|goes|went|makes?|"
    r"made|takes?|took|owes?|owed|pays?|paid|steps?|stepped|crossed|realises?|"
    r"realizes?|moves?|moved|finds?|found|keeps?|kept|turns?|turned|leaves?|"
    r"left|wins?|won|loses?|lost|shipped|avoids?|becomes?|became|discovers?|"
    r"learns?|refuses?|dies|died|kills?|killed|sells?|sold|buys?|bought|"
    r"breaks?|broke|builds?|built|runs?|ran|hides?|hid|saves?|saved"
    r")\b", re.I)
_TITLE_EDING = re.compile(r"\b\w{4,}(ed|ing)\b", re.I)

_ACTION_DELIVERY = {"action", "tense"}


# ---------------------------------------------------------------- helpers --
def _narr(ln) -> str:
    return str(ln.get("narration", "") or "").strip()


def _sentences(text: str) -> list:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def _wc(s: str) -> int:
    return len(s.split())


def is_v2(draft: dict) -> bool:
    """A draft is v2 once any line declares `payload` or `hook_question`."""
    return any(("payload" in ln) or ("hook_question" in ln)
               for ln in draft.get("lines", []))


# ------------------------------------------------------------------ gates --
def craft_report(draft: dict) -> dict:
    """Return {'errors','warns','notes','metrics'}.

    `errors` block the draft; `warns` and `notes` only print. Nothing here
    exits the process - draft.py owns the abort.
    """
    errors: list = []
    warns: list = []
    notes: list = []
    m: dict = {}

    lines = draft.get("lines", []) or []
    narrated = [ln for ln in lines if _narr(ln)]
    n = len(narrated)
    m["narrated_lines"] = n
    v2 = is_v2(draft)
    m["schema"] = "v2" if v2 else "v1"

    # Thong ke nhip can mot mau du lon. Duoi nguong -> chi ghi chu.
    stats_ok = n >= MIN_LINES_FOR_STATS
    m["stats_applied"] = stats_ok
    if not stats_ok:
        notes.append(
            f"[CRAFT] {n} narrated line(s) < {MIN_LINES_FOR_STATS} - rhythm "
            f"and voice statistics are not meaningful at this size, so they "
            f"are reported but NOT enforced. This is what keeps a new craft "
            f"gate from killing small fixtures before the gate under test runs.")

    def hard(msg):
        (errors if stats_ok else notes).append(msg)

    # ---- item 1: [PAYLOAD-MIX] -------------------------------------------
    if not v2:
        notes.append(
            "[PAYLOAD-MIX] NOT-MEASURABLE - this draft declares no `payload` "
            "on any line (v1 schema). This is not a pass. The gate cannot "
            "tell a stake from a screen description without the label.")
        m["payload"] = None
    else:
        bad = [ln.get("id") for ln in narrated
               if str(ln.get("payload", "")) not in PAYLOAD_KINDS]
        if bad:
            errors.append(
                f"[PAYLOAD-MIX] {len(bad)} line(s) carry no valid `payload` "
                f"(one of {', '.join(PAYLOAD_KINDS)}): {bad[:12]}"
                + (" ..." if len(bad) > 12 else ""))
        kinds = [str(ln.get("payload", "")) for ln in narrated]
        counts = {k: kinds.count(k) for k in PAYLOAD_KINDS}
        m["payload"] = counts
        if n:
            share = counts["rest"] / n
            m["rest_share"] = share
            if share > BAR_REST_SHARE:
                errors.append(
                    f"[PAYLOAD-MIX] {counts['rest']}/{n} lines "
                    f"({share*100:.0f}%) are `rest` - the bar is "
                    f"{BAR_REST_SHARE*100:.0f}%. A rest line is a breath "
                    f"between loaded lines; a draft of them is a shot list.")
        run = 0
        runs = []
        for ln in narrated:
            if str(ln.get("payload")) == "rest":
                run += 1
                if run == BAR_REST_RUN:
                    runs.append(ln.get("id"))
            else:
                run = 0
        if runs:
            errors.append(
                f"[PAYLOAD-MIX] {len(runs)} place(s) with {BAR_REST_RUN}+ "
                f"consecutive `rest` lines (ending at line "
                f"{', '.join(str(r) for r in runs[:8])}). Three descriptions "
                f"in a row is where a viewer leaves.")

    # ---- item 2: [RHYTHM] -------------------------------------------------
    if n:
        wl = [_wc(_narr(ln)) for ln in narrated]
        sd = _st.pstdev(wl) if len(wl) > 1 else 0.0
        m["sd_words_per_line"] = round(sd, 2)
        m["mean_words_per_line"] = round(_st.mean(wl), 2)
        if sd < BAR_SD:
            hard(f"[RHYTHM] words-per-line SD is {sd:.1f}, below the bar of "
                 f"{BAR_SD:.0f}. (human reference 13.7, the rejected machine "
                 f"draft 3.9). Every line the same length reads as a metronome "
                 f"before TTS touches it.")

        seq = []
        for ln in narrated:
            seq += [_wc(s) for s in _sentences(_narr(ln))]
        ns = len(seq)
        m["sentences"] = ns
        if ns:
            long_share = sum(1 for x in seq if x >= 30) / ns
            m["long_sentence_share"] = round(long_share, 4)
            if long_share < BAR_LONG_SHARE:
                hard(f"[RHYTHM] {long_share*100:.1f}% of sentences are >=30 "
                     f"words, below the bar of {BAR_LONG_SHARE*100:.0f}% "
                     f"(human reference 4.3%). With no long sentence there is "
                     f"nothing for a short one to land against.")
            elif long_share > BAR_LONG_SHARE_MAX:
                hard(f"[RHYTHM] {long_share*100:.1f}% of sentences are >=30 "
                     f"words, ABOVE the ceiling of "
                     f"{BAR_LONG_SHARE_MAX*100:.0f}% (human reference 4.3%). "
                     f"Long sentences are a device, not a default - when most "
                     f"of them are long, none of them lands and the read "
                     f"becomes relentless. Variety has two sides.")
            punch = sum(1 for a, b in zip(seq, seq[1:]) if a >= 20 and b <= 5)
            punch_share = punch / ns
            m["punch_share"] = round(punch_share, 4)
            m["punch_count"] = punch
            if punch_share < BAR_PUNCH_SHARE:
                hard(f"[RHYTHM] {punch} punch sentence(s) "
                     f"({punch_share*100:.1f}%) - a <=5-word sentence straight "
                     f"after a >=20-word one. Bar is "
                     f"{BAR_PUNCH_SHARE*100:.0f}% (human reference 5.9%, the "
                     f"rejected draft 1.3%). NOTE: counting short sentences on "
                     f"their own does NOT work - the rejected draft already "
                     f"had 16.3% of them, all the same stunted mould.")

        opener = sum(1 for ln in narrated if _OPENER_NARROW.match(_narr(ln)))
        m["opener_share"] = round(opener / n, 4)
        if opener / n > BAR_OPENER_SHARE:
            warns.append(
                f"[RHYTHM] {opener}/{n} lines ({opener*100.0/n:.0f}%) open "
                f"with a place/time phrase; the bar is "
                f"{BAR_OPENER_SHARE*100:.0f}%. WARNING ONLY - this one flips "
                f"on how the regex is written (under a broader pattern the "
                f"human reference scores worse), and it is satisfiable by "
                f"rewording rather than rethinking.")

        thens = [i for i, ln in enumerate(narrated)
                 if _narr(ln).lower().startswith("then")]
        consec = sum(1 for a, b in zip(thens, thens[1:]) if b == a + 1)
        m["consecutive_then"] = consec
        if consec:
            warns.append(f"[RHYTHM] {consec} pair(s) of consecutive lines open "
                         f"with \"Then\".")
        else:
            notes.append("[RHYTHM] consecutive-\"Then\" lint: 0 hits. "
                         "DECORATIVE - it scored 0 on both reference drafts "
                         "too, so it has never discriminated anything.")

    # ---- item 3: [SPEECH-BLIND] ------------------------------------------
    sb_hard, sb_soft = [], []
    for ln in narrated:
        t = _narr(ln)
        has_quote = ('"' in t) or ("\u201c" in t)
        for rx, why in _SPEECH_HARD:
            if rx.search(t) and not has_quote:
                sb_hard.append((ln.get("id"), why))
        for rx, why in _SPEECH_SOFT:
            if rx.search(t):
                sb_soft.append((ln.get("id"), why))
    m["speech_blind_hard"] = len(sb_hard)
    m["speech_blind_soft"] = len(sb_soft)
    for lid, why in sb_hard:
        errors.append(f"[SPEECH-BLIND] line {lid}: {why}")
    for lid, why in sb_soft:
        warns.append(f"[SPEECH-BLIND] line {lid}: {why}")

    # ---- item 4: [HOOK] ---------------------------------------------------
    title = str(draft.get("title", "") or "").strip()
    m["title"] = title
    if title and _TITLE_YEAR.search(title):
        errors.append(
            f"[HOOK] title {title!r} is \"<film> (<year>)\". The genre's "
            f"strongest device is a premise title - [role] + [extraordinary "
            f"premise stated as fact] + [withheld consequence]. The human "
            f"reference uses \"Bad Genius - the exam heist that crossed a "
            f"time zone\".")
    elif (title and stats_ok
          and not (_TITLE_VERB.search(title) or _TITLE_EDING.search(title))):
        # Nua CON LAI cua item 4: khong chi "khong duoc la ten phim + nam", ma
        # phai LA mot tien de. Mot tien de la mot menh de; mot ten phim la mot
        # cum danh tu. Proxy: co dong tu hay khong.
        errors.append(
            f"[HOOK] title {title!r} reads as a name, not a premise - there is "
            f"no verb in it, so nothing is being claimed. The pattern is "
            f"[role] + [extraordinary premise stated as fact] + [withheld "
            f"consequence]: \"Students Don't Realise Their Teacher Is A Kungfu "
            f"Legend\", \"Bad Genius - the exam heist that crossed a time "
            f"zone\". NOTE: this is a verb-presence proxy, not grammar "
            f"analysis; whether the premise is actually withheld and actually "
            f"extraordinary is checked by the payload auditor, not here.")
    hooks = [ln for ln in lines if ln.get("delivery") == "hook"]
    m["hook_lines"] = len(hooks)
    if not v2:
        notes.append(
            "[HOOK] question NOT-MEASURABLE - no `hook_question` field on this "
            "v1 draft. NOTE: the report's other hook rule (clip_start must be "
            ">=20% into the runtime) was DROPPED - measured, the human hook "
            "sits at 1.05% of runtime, earlier than the machine draft's 2.23%.")
    else:
        # Size-gated like the rhythm statistics: a six-line fixture has no hook
        # because it is not a film, and hard-failing it would stop the gates
        # under test from running at all.
        if not hooks:
            hard("[HOOK] no line is tagged <hook>.")
        for h in hooks:
            q = str(h.get("hook_question", "") or "").strip()
            if len(q) < 10:
                errors.append(
                    f"[HOOK] line {h.get('id')} is tagged <hook> but names no "
                    f"`hook_question`. If you cannot name the specific "
                    f"question the hook raises, it is a statement, not a hook.")

    # ---- [DELIVERY-UNKNOWN]: catch a dead tag at DRAFT time ---------------
    # tts.py now refuses an unknown tag, but that is at render time - minutes
    # of work later, and only if somebody renders. The writer should hear about
    # it while the draft is still the thing being edited.
    try:
        import config as _cfg
        _known = set(getattr(_cfg, "TTS_DELIVERY", {}) or {})
    except Exception:                                     # pragma: no cover
        _known = set()
    if _known:
        _bad = {}
        for ln in narrated:
            _t = ln.get("delivery")
            if _t in (None, ""):
                continue
            if str(_t) not in _known:
                _bad.setdefault(str(_t), []).append(ln.get("id"))
        for _t, _ids in sorted(_bad.items()):
            errors.append(
                f"[DELIVERY-UNKNOWN] {len(_ids)} line(s) tagged <{_t}>, which "
                f"has no TTS preset: {_ids[:10]}"
                + (" ..." if len(_ids) > 10 else "")
                + f". Known: {', '.join(sorted(_known))}. An unknown tag used "
                  f"to be read at normal pace in silence.")

    # ---- item 5: [INTRO-OUTRO] -------------------------------------------
    tags = [ln.get("delivery") for ln in lines]
    m["has_intro"] = tags.count("intro")
    m["has_outro"] = tags.count("outro")
    if stats_ok and not m["has_intro"]:
        errors.append("[INTRO-OUTRO] no <intro> line. The draft starts "
                      "narrating with no one introducing it.")
    if stats_ok and not m["has_outro"]:
        errors.append("[INTRO-OUTRO] no <outro> line. The draft stops instead "
                      "of ending.")
    for ln in lines:
        if ln.get("delivery") != "outro":
            continue
        sents = _sentences(_narr(ln))
        cta_at = [i for i, s in enumerate(sents) if _CTA.search(s)]
        if not sents:
            continue
        if cta_at and cta_at[0] == 0:
            errors.append(
                f"[INTRO-OUTRO] line {ln.get('id')}: the <outro> opens with "
                f"the call to action. A thesis - what the ending MEANS - has "
                f"to come first. Human reference: \"The only one who pays in "
                f"full is the one who decides to stop.\" then the CTA.")
        elif not cta_at and len(sents) < 2:
            warns.append(
                f"[INTRO-OUTRO] line {ln.get('id')}: the <outro> has neither a "
                f"second sentence nor a call to action.")

    # ---- item 6: [SPINE] (warning - regex proxy for a semantic property) --
    anon = [ln.get("id") for ln in narrated if _ANON.search(_narr(ln))]
    m["anonymous_epithets"] = len(anon)
    if anon:
        warns.append(
            f"[SPINE] {len(anon)} line(s) refer to someone as \"the "
            f"gangster/the man/one of them\": {anon[:10]}"
            + (" ..." if len(anon) > 10 else "")
            + ". Give a name or a role the viewer can see on screen.")

    # ---- item 7: [ACTION-STAKE] ------------------------------------------
    if v2:
        run = []
        offenders = []
        for ln in narrated + [None]:
            if ln is not None and ln.get("delivery") in _ACTION_DELIVERY:
                run.append(ln)
                continue
            if len(run) >= BAR_ACTION_STAKE_EVERY:
                gap = 0
                for r in run:
                    if str(r.get("payload")) in ("stake", "reasoning"):
                        gap = 0
                    else:
                        gap += 1
                        if gap >= BAR_ACTION_STAKE_EVERY:
                            offenders.append(r.get("id"))
                            gap = 0
            run = []
        m["action_stake_offenders"] = len(offenders)
        if offenders:
            errors.append(
                f"[ACTION-STAKE] {len(offenders)} point(s) in an action run go "
                f"{BAR_ACTION_STAKE_EVERY}+ lines with no `stake` or "
                f"`reasoning` (at line "
                f"{', '.join(str(o) for o in offenders[:8])}). An action "
                f"sequence with no restated stake is a list of manoeuvres.")
    else:
        notes.append("[ACTION-STAKE] NOT-MEASURABLE - needs `payload` labels.")

    # ---- item 8: [NARRATOR-VOICE] ----------------------------------------
    judged = []
    for ln in narrated:
        if str(ln.get("payload")) == "judgment":
            judged.append(ln.get("id"))
        elif any(rx.search(_narr(ln)) for rx in _JUDGE):
            judged.append(ln.get("id"))
    m["judgment_lines"] = len(judged)
    if n:
        need = max(BAR_JUDGE_MIN, n / BAR_JUDGE_EVERY)
        m["judgment_needed"] = round(need, 1)
        if len(judged) < need:
            hard(f"[NARRATOR-VOICE] {len(judged)} judgment/aside line(s); this "
                 f"draft needs {need:.0f} (>=1 per {BAR_JUDGE_EVERY} lines, "
                 f"minimum {BAR_JUDGE_MIN}). The human reference has 6 in 147. "
                 f"A narrator with no opinion is the \"chi Google\" read.")
        elif len(judged) / n > BAR_JUDGE_SHARE_MAX:
            hard(f"[NARRATOR-VOICE] {len(judged)}/{n} lines "
                 f"({len(judged)*100.0/n:.0f}%) carry a judgment or aside, "
                 f"above the ceiling of {BAR_JUDGE_SHARE_MAX*100:.0f}% "
                 f"(human reference 7.5%). An opinion on every line is not a "
                 f"point of view, it is a running commentary - and it leaves "
                 f"the story no room. Keep the best ones.")

    # ---- dong tren mot beat: tran, khong phai muc tieu thoi luong ---------
    # Beat o day la so beat ban draft THUC SU phuc vu (so gia tri `note` khac
    # nhau), khong phai so beat trong beat map. Neu draft bo beat thi mau so
    # nho di va ty le trong len - no khong the lam cong nay de hon.
    _beats = {str(ln.get("note")) for ln in lines if ln.get("note")}
    m["beats_served"] = len(_beats)
    if _beats and n:
        # ---- [DENSITY]: tu tren beat ------------------------------------
        _words = sum(_wc(_narr(ln)) for ln in narrated)
        wpb = _words / len(_beats)
        m["words"] = _words
        m["words_per_beat"] = round(wpb, 1)
        if wpb > BAR_WORDS_PER_BEAT_MAX:
            hard(f"[DENSITY] {_words} words over {len(_beats)} beats = "
                 f"{wpb:.1f} words per beat, above the ceiling of "
                 f"{BAR_WORDS_PER_BEAT_MAX:.0f}. Measured references: the "
                 f"human draft 45.6, the rendered machine draft 42.9. This "
                 f"caps the TOTAL, not the line - vary line length as much as "
                 f"you like (the SD floor of {BAR_SD:.0f} requires it), but a "
                 f"beat cannot be told twice as fully as the reference tells "
                 f"it. Cut {int(_words - BAR_WORDS_PER_BEAT_MAX * len(_beats))} "
                 f"words.")

        lpb = n / len(_beats)
        m["lines_per_beat"] = round(lpb, 2)
        if lpb > BAR_LINES_PER_BEAT_MAX:
            hard(f"[BEAT-BUDGET] {n} lines over {len(_beats)} beats = "
                 f"{lpb:.2f} lines per beat, above the ceiling of "
                 f"{BAR_LINES_PER_BEAT_MAX}. Human reference 1.93. This is "
                 f"not a runtime target - nothing here is compared against a "
                 f"number of minutes - it is the measure of whether a beat is "
                 f"being told or re-told. Three lines on one beat usually "
                 f"means two of them say the same thing.")

    # ---- item 9: [LOOP-CADENCE] ------------------------------------------
    if v2:
        pos = [i for i, ln in enumerate(narrated)
               if str(ln.get("payload")) == "loop"]
        m["loop_count"] = len(pos)
        bad_gaps = []
        prev = -1
        for p in pos:
            if p - prev > BAR_LOOP_GAP:
                bad_gaps.append((prev + 1, p))
            prev = p
        if not pos:
            hard(
                f"[LOOP-CADENCE] no line carries `payload: loop`. Nothing in "
                f"this draft promises the viewer a reason to stay.")
        elif bad_gaps:
            errors.append(
                f"[LOOP-CADENCE] {len(bad_gaps)} stretch(es) longer than "
                f"{BAR_LOOP_GAP} lines with no open loop "
                f"(lines {bad_gaps[0][0]+1}-{bad_gaps[0][1]+1}"
                + (f", +{len(bad_gaps)-1} more" if len(bad_gaps) > 1 else "")
                + "). A loop can be a flat promise - \"Now meet the other "
                  "one.\" - it does not need a question mark.")
    else:
        notes.append("[LOOP-CADENCE] NOT-MEASURABLE - needs `payload` labels.")

    # ---- item 11: [SILENCE-UNIT] -----------------------------------------
    # KHONG tao tag `<hold>` moi. Co che da ton tai:
    # `narration_silence_seconds`, da duoc [EMPTY-LINE] mien tru va da duoc
    # render.py ton trong. Bao cao doc script.txt (khong in truong nay) nen
    # tuong ba dong trong cua ban NGUOI la dead air - chung khong phai.
    sil = [(ln.get("id"), float(ln.get("narration_silence_seconds") or 0))
           for ln in lines if ln.get("narration_silence_seconds")]
    m["silence_units"] = len(sil)
    for lid, secs in sil:
        if secs < BAR_SILENCE_MIN:
            errors.append(
                f"[SILENCE-UNIT] line {lid}: a {secs:.1f}s hold is too short "
                f"to read as deliberate (minimum {BAR_SILENCE_MIN:.0f}s).")
        elif secs > BAR_SILENCE_WARN:
            warns.append(
                f"[SILENCE-UNIT] line {lid}: a {secs:.1f}s hold is long "
                f"(warning above {BAR_SILENCE_WARN:.0f}s). The human "
                f"reference does hold 20.0s once, so this is not an error - "
                f"but silence with no movement is a retention risk.")
    if stats_ok:
        lo, hi = BAR_SILENCE_COUNT
        if not (lo <= len(sil) <= hi):
            warns.append(
                f"[SILENCE-UNIT] {len(sil)} silence unit(s); {lo}-{hi} is the "
                f"expected range for a feature recap. Use "
                f"`narration_silence_seconds` after a reveal, a death, or a "
                f"climax - let the picture carry it.")
    by_id = {ln.get("id"): ln for ln in lines}
    order = [ln.get("id") for ln in lines]
    for lid, _secs in sil:
        try:
            idx = order.index(lid)
        except ValueError:
            continue
        prev = None
        for j in range(idx - 1, -1, -1):
            if _narr(by_id.get(order[j], {})):
                prev = by_id[order[j]]
                break
        if prev is not None and prev.get("delivery") not in (
                "reveal", "sad", "tense", "hook", "action"):
            warns.append(
                f"[SILENCE-UNIT] line {lid} follows a "
                f"<{prev.get('delivery') or 'normal'}> line. A hold earns its "
                f"silence after a reveal, a death or a climax.")

    return {"errors": errors, "warns": warns, "notes": notes, "metrics": m}
