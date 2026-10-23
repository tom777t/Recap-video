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

import json
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

# --- [NARRATOR-VOICE] do bang MARKERS PER MINUTE (C2, 2026-10-21) ---------
# Thanh do cu la "% dong mang judgment", calibrate tu ban Bad Genius nguoi
# viet (7.5%). Hai van de:
#   1. no khong cung don vi voi phep do giong ke (markers/1000 tu), nen khong
#      the so sanh voi kenh mau duoc;
#   2. no calibrate tu SAI MAU. Mau bay gio la SAKURA REVIEW.
# Per-minute lam MAU SO trung tinh ngon ngu. TU SO chi dung GIAO cua nhung gi
# ca hai ngon ngu dien dat duoc - tu chi nguoi ke, noi voi nguoi xem, the hien
# thai do, cau hoi. Tieu tu cuoi cau tieng Viet bi LOAI khoi thanh do (tieng
# Anh khong co o tuong duong) va duoc bao cao rieng nhu mot thiet bi phai adapt.
# Do duoc (docs/NARRATOR_VOICE.md):
#   SAKURA 3 video       1.82 - 2.35/min, trung binh 2.05
#   SAKURA 1/3 cuoi      3.15 - 3.74/min  <- hinh dang TANG DAN phai duoc phep
#   Vua Phim             1.41/min
#   Movie Recaps x4      0.00/min   (zero, sau khi boc loi thoai)
#   TheCutFrame          0.00/min
#   ban Bad Genius nguoi 0.79/min
#   TD pre-craft         0.58/min
#   TD final             1.88/min
BAR_VOICE_PER_MIN_MIN = 1.2    # duoi Sakura-min 1.82 va duoi Vua Phim 1.41;
                               # tu choi 0.00 / 0.47 / 0.58 / 0.79
BAR_VOICE_PER_MIN_MAX = 3.0    # tren Sakura-max 2.35
BAR_VOICE_THIRD_MAX = 4.5      # tren 1/3 cuoi cao nhat cua Sakura (3.74)

# Giao cua hai ngon ngu. KHONG gom tieu tu cuoi cau.
_VOICE_SHARED = {
    "self": re.compile(r"\b(i|i'm|i've|i'd|me|my)\b", re.I),
    "address": re.compile(r"\b(you|your|you're)\b", re.I),
    "stance": re.compile(r"\b(honestly|frankly|of course|apparently|somehow|"
                         r"obviously|clearly|naturally|turns out)\b", re.I),
    "question": re.compile(r"\?"),
}

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

BAR_HOOK_OPENER_WORDS = 6      # it has to land on the music drop

# A PROXY for "this reads like a shot description", not a decision procedure.
# The real separation - "the cars drive sideways" (premise, allowed) versus
# "he lifts out the clamps" (frame, banned) - is a judgment no regex makes, so
# this is a WARNING and the auditor rules. What it catches is the commonest
# shape of a shot tag: a concrete article-noun performing a physical action,
# or an explicit spatial placement.
_FRAME_DESC = re.compile(
    r"\b(?:a|an|the)\s+\w+(?:\s+\w+)??\s+"
    r"(?:sits?|stands?|lies?|leans?|walks?|opens?|closes?|lifts?|picks?|"
    r"puts?|drops?|holds?|turns?|reaches?|pulls?|pushes?|hands?|slides?|"
    r"kneels?|steps?)\b"
    r"|\b(?:in the (?:frame|foreground|background|corner)|"
    r"on the (?:left|right)|behind (?:him|her|them)|across the room)\b",
    re.I)

# The story's first shot-bound line has to anchor the viewer in a time or a
# place. Three shapes are accepted, all of which read as "here is how it
# started":
#   "It starts in Arizona."            - an explicit opening formula
#   "Arizona, and a boy who ..."       - a proper noun, then a comma
#   "In 2001, a boy ..." / "One night" - a time or place preposition
# NOTE this deliberately asks for the construction [RHYTHM] caps at 15% of
# lines. One such line is the point; fifteen in a row is the problem [RHYTHM]
# is for, and the two rules do not collide at one line.
_ANCHOR = re.compile(
    r"^\s*(?:"
    # "It starts in ...", "The story begins ..."
    r"(?i:(?:it|this|the\s+story|everything)\s+(?:all\s+)?"
    r"(?:starts?|start(?:s|ed)\s+out|begins?|began|opens?|opened|"
    r"kicks?\s+off)\b)"
    # "Arizona," / "Oro Valley, Arizona." - a CAPITALISED place, then a comma
    # or full stop. Case-sensitive on purpose: under re.I this branch matched
    # "A wrench in his hand," because [A-Z] stops meaning capital.
    r"|(?-i:[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*)*\s*[,.])"
    # a place preposition, or a real time expression
    r"|(?i:(?:in|on|at|back\s+in|out\s+in|deep\s+in|somewhere\s+in)\b)"
    r"|(?i:(?:one|two|three|four|five|six|a\s+few|several)\s+"
    r"(?:years?|months?|weeks?|days?|nights?|hours?|minutes?)\b)"
    r"|(?i:(?:one\s+(?:night|morning|afternoon|evening)|late\s+one|"
    r"long\s+before|years?\s+before|the\s+night\s+before)\b)"
    r")")

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


def facts_for(draft: dict):
    """Load projects/<name>/film_facts.json, or None.

    The draft carries no project name, so the path comes from the caller via
    `draft['_facts_path']` when craft_report is driven by a tool, or is found
    next to the draft when the validator runs. Returns None rather than
    raising: a draft with no film_intro lines does not need the file, and the
    gate only demands it when the block exists.
    """
    import os
    p = draft.get("_facts_path")
    if not p:
        p = draft.get("_dir")
        p = os.path.join(p, "film_facts.json") if p else None
    if not p or not os.path.exists(p):
        return None
    try:
        return json.loads(io_open_text(p))
    except Exception:
        return None


def io_open_text(p: str) -> str:
    import io as _io
    return _io.open(p, encoding="utf-8-sig").read()


def _withheld_tokens(what: str) -> list:
    """Distinctive names/titles inside a `withheld` entry.

    Matching the whole sentence would never fire; matching every word would
    fire on 'the' and 'film'. Proper nouns and franchise titles are what
    actually give a reveal away.
    """
    toks = re.findall(r"\b[A-Z][A-Za-z0-9']+(?:\s+[A-Z][A-Za-z0-9']+)*\b", what)
    out = []
    for t in toks:
        if len(t) < 3:
            continue
        if t.lower() in ("the", "his", "her", "a", "an", "it", "naming",
                         "director", "universal", "wikipedia"):
            continue
        out.append(t)
    return out


def ln_by_id(lines: list, lid) -> dict:
    for l in lines:
        if l.get("id") == lid:
            return l
    return {}


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

    # ---- [FILM-SPEAKS] ----------------------------------------------------
    # narration stops, the film's own exchange plays at full level.
    _fs = [(ln.get("id"), float(ln.get("film_speaks_seconds") or 0))
           for ln in lines if ln.get("film_speaks_seconds")]
    m["film_speaks"] = len(_fs)
    _order = [ln.get("id") for ln in lines]
    try:
        import config as _c3
        _fmin = float(getattr(_c3, "FILM_SPEAKS_MIN_SEC", 3.0))
        _fmax = float(getattr(_c3, "FILM_SPEAKS_MAX_SEC", 15.0))
        _fcap = int(getattr(_c3, "FILM_SPEAKS_MAX_PER_FILM", 5))
        _fspace = int(getattr(_c3, "FILM_SPEAKS_MIN_SPACING_LINES", 15))
    except Exception:                                      # pragma: no cover
        _fmin, _fmax, _fcap, _fspace = 3.0, 15.0, 5, 15
    for lid, secs in _fs:
        if secs < _fmin or secs > _fmax:
            errors.append(
                f"[FILM-SPEAKS] line {lid}: {secs:.1f}s is outside "
                f"{_fmin:.0f}-{_fmax:.0f}s. Under {_fmin:.0f}s nobody registers "
                f"an exchange; over {_fmax:.0f}s it stops being a recap and "
                f"starts being a clip.")
        if str(ln_by_id(lines, lid).get("narration", "") or "").strip():
            errors.append(
                f"[FILM-SPEAKS] line {lid} carries narration. The whole point "
                f"is that the narrator stops - the film is talking.")
    if len(_fs) > _fcap:
        errors.append(
            f"[FILM-SPEAKS] {len(_fs)} units, cap is {_fcap} (about one per "
            f"act). Original audio is a copyright exposure and the device "
            f"stops working when it is everywhere.")
    _pos = [_order.index(lid) for lid, _ in _fs if lid in _order]
    for a, b in zip(sorted(_pos), sorted(_pos)[1:]):
        if b - a < _fspace:
            errors.append(
                f"[FILM-SPEAKS] two units only {b - a} lines apart "
                f"(minimum {_fspace}). They cannot cluster.")
    # The line BEFORE a film_speaks unit must not paraphrase what is about to
    # be heard. That is a judgment a reader has to make, so this is a WARNING
    # with a mechanical proxy: a speech-reporting verb right before the film
    # speaks is the most likely way to say it twice.
    _spverb = re.compile(r"\b(says?|told?|tells|asks?|answers?|replies|"
                         r"explains?|admits?|argues?|insists?)\b", re.I)
    for lid, _ in _fs:
        i = _order.index(lid) if lid in _order else -1
        if i <= 0:
            continue
        prev = None
        for j in range(i - 1, -1, -1):
            if _narr(lines[j]):
                prev = lines[j]
                break
        if prev is not None and _spverb.search(_narr(prev)):
            warns.append(
                f"[FILM-SPEAKS] the line before unit {lid} "
                f"(line {prev.get('id')}) reports speech. If the film is about "
                f"to say it, do not say it first - the viewer hears it twice "
                f"and the second time is the one that sounds padded.")

    # ---- item 3: [SPEECH-BLIND] ------------------------------------------
    # Lines immediately before a <film_speaks> unit are EXEMPT: not saying what
    # was said is correct there, because the film is about to say it.
    _fs_exempt = set()
    for lid, _ in _fs:
        i = _order.index(lid) if lid in _order else -1
        for j in range(i - 1, -1, -1):
            if j >= 0 and _narr(lines[j]):
                _fs_exempt.add(lines[j].get("id"))
                break
    sb_hard, sb_soft = [], []
    for ln in narrated:
        if ln.get("id") in _fs_exempt:
            continue
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

    # ---- the hook plays OVER THE MONTAGE, so it cannot describe a frame ----
    # See docs/NARRATOR_VOICE.md "Hooks". On tokyodrift2006 the montage is 20
    # cuts in 13.7s: a line describing one shot is describing something that
    # is on screen for 0.65s, if at all. These rules apply to EVERY line
    # spoken over the montage, not only the one tagged `hook`.
    # A draft is MONTAGE-ERA once any line declares `over_montage`. Before
    # that it was written against the old design, where the hook was bound to
    # a shot like any other line - the human badgenius2017 draft is such a
    # draft and its hook is correctly shot-bound FOR ITS ERA. Hard-failing it
    # on a rule invented afterwards would be the same mistake as calibrating a
    # bar the gold standard cannot meet, so legacy drafts get warnings and
    # montage-era drafts get errors.
    _montage_era = any(ln.get("over_montage") for ln in lines)
    m["montage_era"] = _montage_era

    def _hook_fail(msg):
        (errors if _montage_era else warns).append(
            msg if _montage_era
            else msg + " (WARNING: this draft predates the intro montage - "
                       "the rule becomes an error once any line is marked "
                       "`over_montage`)")

    _over = [ln for ln in narrated
             if ln.get("over_montage") or ln.get("delivery") == "hook"]
    m["over_montage_lines"] = len(_over)
    for ln in _over:
        _t = _narr(ln)
        _lid = ln.get("id")
        if ln.get("clip_start"):
            # A line that CLAIMS over_montage and still carries a window is a
            # contradiction in the same line, so that is always an error.
            (errors if ln.get("over_montage") else warns).append(
                f"[HOOK] line {_lid} is spoken over the montage but carries a "
                f"clip window. It binds to the montage, which keeps cutting "
                f"under it - binding one cut is how a hook turns into a shot "
                f"description.")
        # 4: opener <= 6 words, so it can land on the music drop
        _s = _sentences(_t)
        if _s and _wc(_s[0]) > BAR_HOOK_OPENER_WORDS:
            _hook_fail(
                f"[HOOK] line {_lid}: the opening sentence is {_wc(_s[0])} "
                f"words ({BAR_HOOK_OPENER_WORDS} max). It has to land on the "
                f"music drop. The reference openers are 2, 8 and 7 words and "
                f"the two-word one lands hardest.")
        # 2: no visual description of a specific frame. MECHANICAL PROXY ONLY -
        # the real check is the auditor's, because "the cars drive sideways"
        # is a premise and "he lifts out the clamps" is a frame, and no regex
        # separates those. This catches the commonest shape: a concrete thing
        # doing a physical action, which is what a shot tag reads like.
        if _FRAME_DESC.search(_t):
            warns.append(
                f"[HOOK] line {_lid} reads like a shot description: "
                f"{_FRAME_DESC.search(_t).group(0)!r}. The hook plays over a "
                f"montage of many cuts. Test: would this line still be true "
                f"if the montage cut to twenty different shots? The auditor "
                f"decides this one.")
    # 3: the hook has to pay off the title's promise
    if hooks and title and stats_ok:
        _stop = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for",
                 "he", "she", "his", "her", "it", "is", "are", "who", "that",
                 "with", "from", "at", "by", "but", "can", "cannot", "only"}
        _tw = {w.lower().strip(".,:;!?-") for w in title.split()}
        _tw = {w for w in _tw if w and w not in _stop and len(w) > 2}
        _hw = set()
        for h in hooks:
            _hw |= {w.lower().strip(".,:;!?-") for w in _narr(h).split()}
        if _tw and not (_tw & _hw):
            warns.append(
                f"[HOOK] the hook shares no content word with the title. The "
                f"title sells a promise ({', '.join(sorted(_tw)[:6])}) and the "
                f"hook should pay it off - a title and a hook pulling in "
                f"different directions waste each other.")
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

    # ---- [FILM-INTRO]: the block of real-world facts after the hook ------
    # These lines say things that are NOT in the footage - a director, a cast,
    # a production story - so no footage-based gate can check them. They are
    # checked against projects/<name>/film_facts.json, and anything that file
    # marks `withheld` may not be said at all.
    _fi = [ln for ln in narrated if ln.get("film_intro")]
    m["film_intro_lines"] = len(_fi)
    if _fi:
        _facts = facts_for(draft)
        if _facts is None:
            errors.append(
                "[FILM-INTRO] the draft has film_intro lines but no "
                "film_facts.json. Every claim in that block has to be checked "
                "against a sourced file - without it the block is unverifiable "
                "assertion about the real world.")
        else:
            _blob = " ".join(_narr(l) for l in _fi)
            _low = _blob.lower()
            # 1. nothing the facts file withholds may appear.
            # Uses the entry's EXPLICIT `ban` list. Inferring the terms from
            # the description was tried and was badly wrong: "Han Lue returns
            # in Fast Five..." made the gate ban the name "Han Lue", who is a
            # lead and must be named, and ban "Fast", which is in the title.
            # What a withheld entry withholds is the CLAIM, not the name.
            for w in _facts.get("withheld", []):
                _bans = w.get("ban")
                if not _bans:
                    warns.append(
                        f"[FILM-INTRO] withheld entry {w.get('what','')[:50]!r} "
                        f"has no `ban` list, so nothing enforces it. Add the "
                        f"exact phrases that would give it away.")
                    continue
                for _tok in _bans:
                    if re.search(r"\b" + re.escape(str(_tok).lower()) + r"\b",
                                 _low):
                        errors.append(
                            f"[FILM-INTRO] the intro block says {_tok!r}, which "
                            f"film_facts.json withholds ({w.get('reveal','?')}): "
                            f"{w.get('why','')[:150]}")
                        break
            # 2. required elements
            _need = {
                "title": str(_facts.get("title", "")).split(":")[-1].strip(),
                "year": str(_facts.get("year", "")),
                "director": str(_facts.get("director", "")),
            }
            for _k, _v in _need.items():
                if _v and _v.lower() not in _low:
                    errors.append(
                        f"[FILM-INTRO] the block never states the {_k} "
                        f"({_v!r}). Required: channel greeting, title and "
                        f"year, franchise position, director, 2-4 leads with "
                        f"their roles, and one interesting fact.")
            # 3. 2-4 leads, each with a role
            _named = [c for c in _facts.get("cast", [])
                      if c.get("actor", "").lower() in _low]
            m["film_intro_actors"] = len(_named)
            if not (2 <= len(_named) <= 4):
                errors.append(
                    f"[FILM-INTRO] {len(_named)} cast member(s) named; the "
                    f"block wants 2-4 leads. Naming nobody is a listings "
                    f"entry, naming everybody is a credits roll.")
            for c in _named:
                if str(c.get("role", "")).split()[0].lower() not in _low:
                    warns.append(
                        f"[FILM-INTRO] {c['actor']} is named without the role "
                        f"({c.get('role')}). An actor with no character is a "
                        f"name the viewer cannot place.")
            # 4. any actor named must EXIST in the facts file
            for _m2 in re.finditer(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", _blob):
                _cand = _m2.group(0)
                if _cand.lower() in _low and not any(
                        _cand.lower() == c.get("actor", "").lower()
                        or _cand.lower() in str(c.get("role", "")).lower()
                        for c in _facts.get("cast", [])):
                    # "The Fast" is two capitalised words and is part of the
                    # title, not a person. Anything contained in the title,
                    # or in a crew name, is not an unsourced person.
                    _tl = str(_facts.get("title", "")).lower()
                    if (_cand.lower() not in _tl
                            and _cand.lower() not in (
                                str(_facts.get("director", "")).lower(),
                                str(_facts.get("writer", "")).lower(),
                                str(_facts.get("composer", "")).lower(),
                                str(_facts.get("studio", "")).lower())):
                        warns.append(
                            f"[FILM-INTRO] {_cand!r} reads like a person's "
                            f"name and is not in film_facts.json. The FACT "
                            f"auditor decides, but an unsourced name in the "
                            f"intro block is the easiest thing here to get "
                            f"wrong.")

    # ---- [TRANSITION]: where the story actually starts -------------------
    # Everything before this point is spoken over a montage or over the
    # film-intro block. The first SHOT-BOUND line is where narration starts
    # pointing at the picture again, and it has to tell the viewer they have
    # arrived somewhere: a time or a place. Without it the recap cuts from a
    # trailer voice straight into the middle of a scene.
    if _fi or any(l.get("over_montage") for l in lines):
        _last_unbound = -1
        for i, ln in enumerate(lines):
            if ln.get("film_intro") or ln.get("over_montage"):
                _last_unbound = i
        _first_bound = None
        for ln in lines[_last_unbound + 1:]:
            if ln.get("clip_start") and _narr(ln):
                _first_bound = ln
                break
        if _first_bound is not None:
            _t = _narr(_first_bound).strip()
            m["transition_line"] = _first_bound.get("id")
            if not _ANCHOR.match(_t):
                hard(f"[TRANSITION] line {_first_bound.get('id')} is the first "
                     f"shot-bound line after the opening, and it opens without "
                     f"a time or place anchor: {_t[:70]!r}. This is where the "
                     f"story starts and the viewer has just come off a montage "
                     f"and a block of credits - they need telling where they "
                     f"are. \"It starts in Arizona.\", \"Arizona, and a boy who "
                     f"cannot stop racing.\", \"Three years before Tokyo, ...\"")

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

    # ---- [VOICE-PRESENCE]: markers per MINUTE, calibrated on SAKURA -------
    # Replaces the old judgment-share ceiling, which was calibrated on the Bad
    # Genius draft and could not be compared with any measured channel because
    # it was in a different unit. See the bar comments above.
    if n:
        _text = " ".join(_narr(l) for l in narrated)
        _words = len(_text.split())
        try:
            import config as _c2
            _wpm = float(getattr(_c2, "TTS_WORDS_PER_MINUTE", 186) or 186)
            _gap = float(getattr(_c2, "GAP_BETWEEN_LINES", 0.18) or 0.18)
        except Exception:                                  # pragma: no cover
            _wpm, _gap = 186.0, 0.18
        _mins = (_words / _wpm) + (_gap * n / 60.0)
        _mk = {k: len(rx.findall(_text)) for k, rx in _VOICE_SHARED.items()}
        _tot = sum(_mk.values())
        _pm = _tot / max(1e-9, _mins)
        m["voice_markers"] = _mk
        m["voice_per_min"] = round(_pm, 2)
        m["narration_min"] = round(_mins, 1)
        if _pm < BAR_VOICE_PER_MIN_MIN:
            hard(f"[VOICE-PRESENCE] {_tot} narrator markers over "
                 f"{_mins:.1f} min = {_pm:.2f}/min, below the floor of "
                 f"{BAR_VOICE_PER_MIN_MIN}. Measured: SAKURA REVIEW (the voice "
                 f"model) runs 1.82-2.35/min; Movie Recaps and TheCutFrame run "
                 f"**0.00** across five videos. A narrator who never says "
                 f"\"I\", never says \"you\" and never asks anything is the "
                 f"plot-summary service, not the host. Counted: "
                 f"{', '.join(f'{k}={v}' for k, v in _mk.items())}.")
        elif _pm > BAR_VOICE_PER_MIN_MAX:
            hard(f"[VOICE-PRESENCE] {_pm:.2f} markers/min is above the ceiling "
                 f"of {BAR_VOICE_PER_MIN_MAX} (SAKURA peaks at 2.35 over a "
                 f"whole video). Presence is not the same as chatter.")
        # Hinh dang TANG DAN phai duoc phep: Sakura len 3.15-3.74 o 1/3 cuoi.
        # Chi chan khi MOT phan ba vuot han nguong rieng, cao hon ca dinh cua
        # Sakura - neu khong, cong nay se phat dung cai nhip ma mau co.
        if n >= 30:
            _k = n // 3
            for _i, _seg in enumerate((narrated[:_k], narrated[_k:2 * _k],
                                       narrated[2 * _k:])):
                if not _seg:
                    continue
                _st_ = " ".join(_narr(l) for l in _seg)
                _sw = len(_st_.split())
                _sm = (_sw / _wpm) + (_gap * len(_seg) / 60.0)
                _sc = sum(len(rx.findall(_st_)) for rx in _VOICE_SHARED.values())
                _spm = _sc / max(1e-9, _sm)
                m[f"voice_third{_i+1}"] = round(_spm, 2)
                if _spm > BAR_VOICE_THIRD_MAX:
                    warns.append(
                        f"[VOICE-PRESENCE] third {_i+1} runs {_spm:.2f} "
                        f"markers/min, above {BAR_VOICE_THIRD_MAX}. A rising "
                        f"final third is the model's own shape (SAKURA reaches "
                        f"3.74) so this is a warning, not an error - but this "
                        f"is past anything measured.")

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
