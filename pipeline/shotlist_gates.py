"""The SHOT LIST: a sentence that names what is already on screen and stops.

THE DEFECT
----------
A narration line ends with a sentence that is nothing but a run of
comma-separated visible nouns - a surface, a passage, a vantage point, a
vehicle arriving - with no finite verb that makes anything happen, no agent
who does anything, and no word of the narrator's own. The viewer is already
looking at all of it. The sentence costs runtime and delivers a caption.

It is a defect anywhere. IMMEDIATELY AFTER A PEAK it is worse than a defect:
the seconds after a death, a reveal or a win are the ones the recap spent its
whole contour buying, and spending them on an inventory of the set is the one
thing those seconds cannot survive. So after a peak the line must either
become a HOLD - footage and music, no narration - or carry meaning. That is
the whole rule, and it is the reason this module exists as a blocking gate
rather than as advice.

WHY THE EXISTING FRAME-ONLY DETECTOR DID NOT CATCH IT
-----------------------------------------------------
`pipeline.pacing_gates._is_frame_only` is a POSITIVE VERB MATCH over a WHOLE
LINE. Both halves of that sentence are why the shape got through:

  1. It requires a hit from a closed list of visual verbs (walks, stands,
     sits, turns, holds, ...). A bare noun list has NO FINITE VERB AT ALL -
     its only verb-shaped token is a present participle modifying one of the
     nouns - so there is nothing for the detector to match and it returns
     False. The detector is built to recognise "someone visibly does
     something"; it has no concept of "nobody does anything and here is the
     furniture", which is the strictly emptier line of the two.
  2. It measures a LINE, and the offending sentence shares its line with an
     ordinary sentence that does carry a visual verb. So on the live draft the
     line IS counted frame-only - but for the first sentence, not the second.
     The defect contributes nothing to the verdict, the verdict names no
     sentence, and the per-line frame-only SHARE was under its cap anyway, so
     the line drew no finding at all. A whole-line measure dilutes a
     one-sentence defect to the point where fixing it and not fixing it score
     the same. That dilution is the mechanism; verified on the live draft, and
     the figures are in tools/test_shotlist_gates.py.

Hence: this gate works per SENTENCE, and it is a NEGATIVE test (no
consequence, no evaluation, only furniture) rather than a positive verb hunt.

WHAT THIS GATE DOES NOT CATCH, stated because a gate trusted for more than it
measures is worse than no gate:

  * Verbs are recognised from LEXICONS, not from a parser. A sentence whose
    only consequential verb is a word neither lexicon knows reads as verbless
    and can be reported. Morphology was tried as a general substitute and
    REJECTED: an `-ed` test calls a past participle used as a modifier a
    verb - the live defect's own first item is exactly that shape - and that
    one token alone would have made the defect invisible again. The pronoun
    and proper-noun guard below is the cheap half of the fix; the rest is
    stated as a limit.
  * It is blind to a shot list written as one long verbless clause with no
    commas, because the item count is what distinguishes a list from a
    description. See `_items` for the separator rule that was tried and
    rejected.
  * `[SHOT-LIST-AFTER-PEAK]` can only run where the peaks are declared. With
    no angle.md there are no declared peaks, so the blocking half emits a NOTE
    and the warning half still runs. It never silently passes.

Every bar is read from config at call time. Nothing here raises: malformed
input returns a report that says what could not be measured.

NO FILM-SPECIFIC CONTENT LIVES IN THIS MODULE. Every lexicon below is general
English. The drafts, the titles, the character names and the real offending
text live in tools/test_shotlist_gates.py and its fixtures.
"""
from __future__ import annotations

import re
from pathlib import Path

import config

# --------------------------------------------------------------------------- #
# Sentence splitting.
#
# Split on strong terminal punctuation only. A semicolon is NOT a sentence
# break here, because a semicolon-joined run of noun phrases is one of the
# shapes being looked for and splitting on it would turn a three-item list
# into three one-item sentences, each of which passes.
#
# Abbreviations ("Mr.", "No.") would split wrongly. Accepted rather than
# worked around: recap narration is written to be read aloud and does not use
# them, and a wrong split produces a FRAGMENT with too few items, which fails
# the item test and is silent. The error direction is a miss, not a false
# alarm.
# --------------------------------------------------------------------------- #
_SENT_SPLIT = re.compile(r"(?<=[.!?\u2026])[\s\"\u201d\u2019']+")

# Curly punctuation folded before any matching. The draft JSON is machine
# written and uses straight quotes; hand-edited lines use curly ones. Same
# normalisation as pipeline/motif_gates.py, and no more than that: no
# stemming, no plural folding beyond the single trailing -s stripped in
# `_lemma`.
_FOLD = {
    "\u2018": "'", "\u2019": "'", "\u201b": "'", "\u02bc": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": " - ", "\u2014": " - ", "\u2212": " - ",
    "\u00a0": " ",
}

_EDGE = "\"'`.,;:!?()[]{}<>-_*\u2026"


def _fold(s: str) -> str:
    out = str(s or "")
    for k, v in _FOLD.items():
        if k in out:
            out = out.replace(k, v)
    return out


def split_sentences(text: str) -> list:
    """The sentences of a narration line, in order, non-empty.

    Public because the gate reports per sentence and the test harness has to
    be able to ask for the same split the gate used.
    """
    out = []
    for part in _SENT_SPLIT.split(_fold(text)):
        p = part.strip()
        if p.strip(_EDGE):
            out.append(p)
    return out


def _tokens(s: str) -> list:
    """Lowercased word tokens, punctuation stripped from the edges only."""
    out = []
    for w in _fold(s).lower().split():
        w = w.strip(_EDGE)
        if w:
            out.append(w)
    return out


def _lemma(w: str) -> str:
    """A crude singular: one trailing -s removed, -ss and -us left alone.

    Enough to let a plural noun hit a singular lexicon entry. Deliberately
    not a stemmer: stemming collapsed distinct words onto the same key in
    testing and the gate's decisions became unexplainable.
    """
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


# --------------------------------------------------------------------------- #
# EXISTENCE / APPEARANCE verbs. A sentence whose only verbs are these says
# that something IS somewhere or CAME INTO VIEW. Nothing is decided, nobody
# pays for anything, and the information is on the screen already - so for the
# purpose of this gate such a sentence counts as VERBLESS.
#
# AMBIGUOUS VERBS ARE DELIBERATELY NOT IN HERE. "runs", "turns", "opens",
# "holds", "pulls", "leads", "drifts", "slips" all have a stative reading (a
# road runs, a corridor turns, smoke drifts) and a consequential one (he runs
# the race, he turns on his friend, he drifts the corner). Every one of them
# sits in the CONSEQUENTIAL set below instead,
# because membership of this set makes the gate FIRE and membership of the
# other set makes it stay silent: the ambiguous cases are sent to the quiet
# side on purpose. A false alarm on a line the writer worked on costs more
# trust than a miss.
# --------------------------------------------------------------------------- #
_EXISTENCE = frozenset("""
is are was were be been being am
sits sit sitting sat
stands stand standing stood
lies lie lying lay
hangs hang hanging hung
slides slide sliding slid
rolls roll rolling rolled
moves move moving moved
passes pass passing passed
waits wait waiting waited
glows glow glowing glowed
flickers flicker flickering flickered
rests rest resting rested
floats float floating floated
gleams gleam gleaming gleamed
shines shine shining shone
glints glint glinting glinted
sways sway swaying swayed
hums hum humming hummed
drips drip dripping dripped
idles idle idling idled
looms loom looming loomed
spreads spreading
stretches stretching stretched
glitters glittering flashes flashing
hovers hovering hovered
lingers lingering lingered
remains remaining remained
exists existing existed
appears appearing appeared
seems seeming seemed
""".split())

# --------------------------------------------------------------------------- #
# CONSEQUENTIAL verbs: an agent does something that costs, changes or decides
# something. One of these anywhere in the sentence and it is NOT a bare shot
# list, whatever else it contains. The list includes the whole of
# pacing_gates._VISUAL_VERB (walks, stands excepted, turns, holds, ...) plus
# every ambiguous verb discussed above, so that the two detectors cannot
# disagree about an ordinary action sentence.
# --------------------------------------------------------------------------- #
_CONSEQUENTIAL = frozenset("""
decide decides decided deciding
refuse refuses refused refusing
pay pays paid paying
hit hits hitting
leave leaves left leaving
lied
walk walks walked walking
drive drives drove driving driven
run runs ran running
turn turns turned turning
look looks looked looking
hold holds held holding
open opens opened opening
close closes closed closing
pull pulls pulled pulling
push pushes pushed pushing
step steps stepped stepping
watch watches watched watching
enter enters entered entering
cross crosses crossed crossing
lift lifts lifted lifting
point points pointed pointing
nod nods nodded nodding
smile smiles smiled smiling
say says said saying
tell tells told telling
ask asks asked asking
answer answers answered answering
shout shouts shouted shouting
call calls called calling
take takes took taking taken
give gives gave giving given
get gets got getting
put puts putting
set sets setting
make makes made making
do does did doing done
go goes went going gone
come comes came coming
bring brings brought bringing
send sends sent sending
keep keeps kept keeping
lose loses lost losing
win wins won winning
find finds found finding
buy buys bought buying
sell sells sold selling
steal steals stole stealing stolen
break breaks broke breaking broken
fix fixes fixed fixing
build builds built building
throw throws threw throwing thrown
catch catches caught catching
shoot shoots shot shooting
kill kills killed killing
die dies died dying
beat beats beating
hurt hurts hurting
save saves saved saving
help helps helped helping
hide hides hid hiding hidden
follow follows followed following
chase chases chased chasing
escape escapes escaped escaping
agree agrees agreed agreeing
admit admits admitted admitting
promise promises promised promising
choose chooses chose choosing chosen
start starts started starting
stop stops stopped stopping
finish finishes finished finishing
learn learns learned learnt learning
teach teaches taught teaching
want wants wanted wanting
need needs needed needing
know knows knew knowing known
think thinks thought thinking
believe believes believed believing
remember remembers remembered remembering
forget forgets forgot forgetting forgotten
blame blames blamed blaming
forgive forgives forgave forgiving
owe owes owed owing
cost costs costing
spend spends spent spending
earn earns earned earning
trust trusts trusted trusting
betray betrays betrayed betraying
lead leads led leading
let lets letting
allow allows allowed allowing
force forces forced forcing
order orders ordered ordering
warn warns warned warning
threaten threatens threatened threatening
offer offers offered offering
accept accepts accepted accepting
return returns returned returning
drift drifts drifted drifting
slip slips slipped slipping
arrive arrives arrived arriving
reach reaches reached reaching
meet meets met meeting
join joins joined joining
quit quits quitting
try tries tried trying
fail fails failed failing
race races raced racing
crash crashes crashed crashing
burn burns burned burnt burning
cut cuts cutting
wear wears wore wearing worn
eat eats ate eating eaten
drink drinks drank drinking drunk
sleep sleeps slept sleeping
write writes wrote writing written
read reads reading
show shows showed showing shown
explain explains explained explaining
realise realises realised realising
realize realizes realized realizing
understand understands understood understanding
""".split())

# --------------------------------------------------------------------------- #
# VISIBLE-SCENE nouns: general English words for things a camera can point at.
# This is NOT a vocabulary taken from any draft - it is the ordinary furniture
# of filmed places, people and weather. Plurals are matched through `_lemma`.
# --------------------------------------------------------------------------- #
_VISIBLE = frozenset("""
floor ceiling wall door doorway doorstep window windowsill pane glass
room hall hallway corridor passage passageway walkway landing stairs
staircase stair step escalator elevator lift turnstile barrier railing
gate fence hedge wall yard courtyard garden porch balcony terrace roof
rooftop chimney attic basement cellar garage shed warehouse factory
street road lane alley avenue boulevard pavement sidewalk kerb curb
crossing junction bridge tunnel underpass overpass flyover motorway
highway track rails rail platform station terminal concourse depot
airport runway port dock pier harbour harbor quay
train carriage tram subway metro bus coach taxi cab car truck lorry van
pickup motorcycle motorbike bike bicycle scooter engine bonnet hood boot
trunk tyre tire wheel windscreen windshield headlight taillight bumper
mirror dashboard horn exhaust
table chair stool bench sofa couch bed mattress desk shelf cupboard
cabinet drawer wardrobe counter till register locker crate box carton
bag suitcase case backpack rucksack basket bucket tray bin
lamp bulb light lights lantern torch candle neon sign signboard banner
poster billboard screen monitor television radio speaker phone handset
receiver camera clock watch calendar
cup mug glass bottle can flask kettle pot pan plate bowl knife fork
spoon napkin towel cloth rag sheet blanket pillow curtain blind carpet
rug mat
coat jacket shirt sleeve collar pocket trousers jeans skirt dress suit
uniform tie belt glove hat cap helmet mask scarf shoe boot sock
paper letter envelope note book notebook page photograph photo picture
map ticket receipt card badge key lock chain rope wire cable pipe hose
drain gutter tap faucet switch button handle hinge nail screw bolt
sky cloud sun moon star rain snow sleet hail fog mist smoke steam fire
flame ash dust mud gravel concrete tile brick stone steel metal wood
plank glass water puddle river stream sea ocean lake pond beach sand
shore hill mountain slope cliff valley field grass lawn tree branch
leaf bush flower forest wood park
crowd queue line group pair man woman men women boy girl child children
kid baby passenger passengers commuter commuters driver rider pedestrian
customer waiter waitress clerk guard porter cleaner nurse doctor cop
police officer soldier worker stranger neighbour neighbor
face head hair eye eyes mouth lip teeth nose ear chin cheek neck
shoulder arm elbow hand finger thumb fist palm chest back waist hip leg
knee ankle foot feet skin blood bruise scar
cigarette ash lighter match matchbox pack bottle wallet purse coin note
banknote watch ring necklace bracelet
""".split())

# --------------------------------------------------------------------------- #
# ABSTRACT nouns, used ONLY by the general concrete-noun test below. A
# determiner followed by one of these is not furniture; it is an idea, and a
# run of ideas is a thesis being restated, which is a different gate's
# business (see pipeline/motif_gates.py).
# --------------------------------------------------------------------------- #
_ABSTRACT = frozenset("""
mistake point problem truth trick joke cost price difference promise
chance idea reason pride love fear hope plan debt future past moment
memory choice decision sense shame guilt respect honour honor loyalty
thing things way kind sort type part lot end start beginning time day
days week year years life death fact question answer matter issue result
effect cause purpose meaning value risk threat luck fate dream wish need
want feeling emotion anger joy sadness grief relief trust doubt faith
belief opinion view thought mind soul spirit heart courage nerve habit
pattern rule law order peace war silence noise quiet rest work job
business deal money cash price payment debt loan favour favor secret
story film movie scene shot line word words name title version
""".split())

# Determiners that open a noun phrase. A list item that starts with one of
# these is being presented AS A THING rather than as a clause.
_DETERMINERS = frozenset("""
a an the this that these those his her its their my our your one two
three four five six seven eight nine ten some another each every both
half several many few no more another
""".split())

# Function words, so the general concrete test cannot mistake one for a noun.
_FUNCTION = frozenset("""
a an the and or but nor so yet if then than that this these those
of in on at to for from with without into onto over under about after
before between during through across against along among around behind
below beneath beside beyond near past since toward towards until upon
within out up down off back again still just only also too very much
more most less least not no never ever it its he she they them their
there here what which who whom whose when where why how while because
though although unless whether you your yours we our ours us i me my
mine him his her hers one two three some any each both few other
another same such own as by
""".split())

# Separators that make a run of phrases a LIST. Commas and semicolons only.
#
# TRIED AND REJECTED: adding " and ", " then " and the prepositions as
# separators so that a comma-free noun sequence would also be measured. On
# ordinary prose that splitter turns a perfectly good sentence - a subject, a
# verb and two prepositional phrases - into a four-item "list", and it did
# exactly that to the harmless first sentence of the very line this gate was
# built for. The item count is the only thing separating a list from a
# description, so the separator has to be the punctuation a writer uses to
# make a list and nothing else. A LIST CONJUNCTION is handled: once the comma
# split has produced two or more parts, a trailing "and"/"or" inside the last
# part is split too, because "A, B, and C" and "A, B and C" are the same list.
_ITEM_SPLIT = re.compile(r"[,;:]|\s+-\s+")
_LIST_CONJ = re.compile(r"\s+(?:and|or|then|plus)\s+", re.I)
# Nominative pronouns. Their presence means the sentence has a SUBJECT - it is
# about someone, not about the furniture - and it is therefore not a bare
# noun-phrase sequence, whether or not either verb lexicon recognises what
# that subject does. This is the cheap half of the cover for an unknown verb.
_NOMINATIVE = frozenset("he she they we i you who nobody everyone someone "
                        "anyone one".split())


def _items(sentence: str) -> list:
    """The list items of a sentence, in order, non-empty."""
    parts = [p.strip() for p in _ITEM_SPLIT.split(sentence)]
    parts = [p for p in parts if p.strip(_EDGE)]
    if len(parts) >= 2:
        out: list = []
        for p in parts:
            for q in _LIST_CONJ.split(p):
                q = q.strip()
                if q.strip(_EDGE):
                    out.append(q)
        return out
    return parts


def _verb_profile(sentence: str) -> tuple:
    """(existence_verbs, consequential_verbs, has_subject).

    `has_subject` is the pronoun / proper-noun guard: a nominative pronoun
    anywhere, or a capitalised token that is not the first word of the
    sentence, is read as an agent being talked about.
    """
    raw = _fold(sentence).split()
    toks = _tokens(sentence)
    exist = [w for w in toks if w in _EXISTENCE]
    cons = [w for w in toks if w in _CONSEQUENTIAL]
    subject = any(w in _NOMINATIVE for w in toks)
    if not subject:
        for w in raw[1:]:
            t = w.strip(_EDGE)
            if len(t) >= 2 and t[:1].isupper() and not t.isupper():
                subject = True
                break
    return exist, cons, subject


def _item_visibility(item: str) -> str:
    """'lexicon', 'concrete' or '' - how this item reads as a visible thing.

    'lexicon': a token (singularised) is in the visible-scene lexicon.
    'concrete': THE GENERAL TEST. The item opens with a determiner and
        contains at least one word that is not a function word, not in either
        verb lexicon, not an -ly adverb, not on the abstract-noun list and at
        least three characters long. That word is taken to be a plain concrete
        noun.

    The general test is what lets an ordinary English noun the lexicon has
    never heard of still count as furniture. Its blind spot is stated rather
    than hidden: an abstract noun that is not on `_ABSTRACT` reads as
    concrete. That is why `is_shotlist_sentence` additionally requires at
    least ONE lexicon hit before it will call a sentence a shot list - a
    sentence of three determiner-led unknown words is not evidence of
    anything, and requiring one known piece of furniture is the cheapest
    available proof that the sentence really is pointing at the set.
    """
    toks = _tokens(item)
    if not toks:
        return ""
    for w in toks:
        if _lemma(w) in _VISIBLE or w in _VISIBLE:
            return "lexicon"
    if toks[0] not in _DETERMINERS:
        return ""
    for w in toks[1:]:
        if (len(w) >= 3 and w not in _FUNCTION and w not in _EXISTENCE
                and w not in _CONSEQUENTIAL and _lemma(w) not in _ABSTRACT
                and w not in _ABSTRACT and not w.endswith("ly")):
            return "concrete"
    return ""


def is_shotlist_sentence(sentence: str) -> tuple:
    """(is_shot_list, why) for ONE sentence. Never raises.

    ALL of the following must hold, and `why` names the first that does not:
      * at least config.SHOTLIST_MIN_ITEMS list items;
      * no consequential finite verb and no agent (existence / appearance
        verbs and participles do not count as verbs here);
      * pipeline.pacing_gates.classify_judgment does not read it as the
        narrator's evaluation;
      * at least config.SHOTLIST_MIN_VISIBLE items are visible things, of
        which at least one is in the visible-scene lexicon.
    """
    try:
        min_items = int(getattr(config, "SHOTLIST_MIN_ITEMS", 3))
        min_vis = int(getattr(config, "SHOTLIST_MIN_VISIBLE", 2))
        items = _items(sentence)
        if len(items) < min_items:
            return False, f"{len(items)} item(s) < {min_items}"
        exist, cons, subject = _verb_profile(sentence)
        if cons:
            return False, f"consequential verb {cons[0]!r}"
        if subject:
            return False, "has an agent as its subject"
        # THE CLASSIFIER REUSE, and the function-local import that makes it
        # possible. pipeline.pacing_gates imports this module from inside
        # `_is_frame_only` and this module imports from pacing_gates here, so
        # one of the two directions has to be deferred to call time or Python
        # cannot finish either module. Both are deferred, so neither module
        # cares which one is imported first. The cost is a dict lookup in
        # sys.modules per sentence.
        #
        # Reusing classify_judgment rather than writing a second evaluation
        # test is the point: if this gate had its own idea of what counts as
        # meaning, a sentence could be "evaluation" to the persona gates and
        # "empty" to this one, and the writer would be given two instructions
        # that cannot both be followed.
        from pipeline.pacing_gates import classify_judgment
        judged, jwhy = classify_judgment(sentence)
        if judged:
            return False, f"carries evaluation ({jwhy})"
        vis = [_item_visibility(it) for it in items]
        n_vis = sum(1 for v in vis if v)
        if n_vis < min_vis:
            return False, f"{n_vis} visible item(s) < {min_vis}"
        if "lexicon" not in vis:
            return False, "no item is a known visible-scene noun"
        return True, (f"{len(items)} items, {n_vis} visible, "
                      f"{len(exist)} existence verb(s), no consequence")
    except Exception as e:                                  # noqa: BLE001
        # A sentence that cannot be measured is NOT a sentence that passed.
        # The caller turns this into a stated "cannot measure".
        return False, f"!{type(e).__name__}: {e}"


def shotlist_sentences(text: str) -> list:
    """[(sentence, why)] - every shot-list sentence in a narration line."""
    out = []
    for s in split_sentences(text):
        ok, why = is_shotlist_sentence(s)
        if ok:
            out.append((s, why))
    return out


def has_shotlist_sentence(text: str) -> bool:
    """Does this line contain a shot-list sentence?

    The entry point pipeline.pacing_gates._is_frame_only calls. Cheap: it
    stops at the first hit and does no reporting work.
    """
    if not text:
        return False
    for s in split_sentences(text):
        if is_shotlist_sentence(s)[0]:
            return True
    return False


# --------------------------------------------------------------------------- #
# PEAKS. Taken from angle.md's declared anchors, exactly as the [PEAK-ORDER]
# block of pipeline/pacing_gates.py does it: an anchor is a peak when its
# `kind`/`why` text contains one of these words.
#
# The tuple is duplicated here rather than imported because in pacing_gates it
# is a local variable inside pacing_report, not a module constant, and the
# brief for this change permits editing exactly one function in that file.
# Promoting it there and importing it here is the right follow-up; until then
# this comment is the link between the two copies, and
# tools/test_shotlist_gates.py asserts the two agree on the live angle.
#
# Why the angle's declaration and not a keyword hunt over the narration: the
# angle already says which beats the recap is built to arrive at. A text rule
# looking for death words would miss a quiet reveal and fire on a line that
# merely mentions one.
# --------------------------------------------------------------------------- #
# Imported, not re-declared: pacing_gates owns this definition and
# [PEAK-ORDER] and this gate must never disagree about what a peak is.
from pipeline.pacing_gates import PEAK_WORDS  # noqa: E402

def _narr(ln) -> str:
    if not isinstance(ln, dict):
        return ""
    return str(ln.get("narration") or "").strip()


def _beat_of(ln) -> str:
    """The beat id a line belongs to: the first token of `note`.

    Same normalisation as pacing_gates._beat_of (B7 -> B07), including its
    fallback, so a beat means the same thing to both gates.
    """
    if not isinstance(ln, dict):
        return ""
    b = str(ln.get("note") or "").strip()
    m = re.match(r"B(\d{1,3})", b)
    if m:
        return f"B{int(m.group(1)):02d}"
    return b if b else f"_line{ln.get('id')}"


def _lid(ln, idx: int):
    """The line's id, or its position when it has none. Never None."""
    if isinstance(ln, dict) and ln.get("id") is not None:
        return ln.get("id")
    return f"#{idx}"


def peak_beats(pdir: Path) -> tuple:
    """(set of peak beat ids, how_it_went).

    how_it_went is "" on success, otherwise a sentence saying why the peaks
    could not be determined. Never raises.
    """
    p = Path(pdir) / "angle.md"
    if not p.exists():
        return set(), (f"there is no angle.md in {Path(pdir).name}, and the "
                       f"peaks are its ANCHORS section")
    try:
        from pipeline import angle_spec
        spec = angle_spec.load(Path(pdir))
    except Exception as e:                                  # noqa: BLE001
        return set(), (f"angle.md in {Path(pdir).name} exists but could not be "
                       f"parsed ({type(e).__name__}: {e})")
    anchors = spec.get("anchors") or []
    out: set = set()
    for a in anchors:
        if not isinstance(a, dict):
            continue
        blob = f"{a.get('kind', '')} {a.get('why', '')}".lower()
        if any(w in blob for w in PEAK_WORDS):
            for b in (a.get("beats") or []):
                out.add(str(b))
    if not anchors:
        return set(), (f"angle.md in {Path(pdir).name} declares no anchors, so "
                       f"no beat can be read as a peak")
    if not out:
        return set(), (f"none of the {len(anchors)} anchor(s) in "
                       f"{Path(pdir).name}/angle.md is declared a peak "
                       f"(kind/why containing one of "
                       f"{', '.join(PEAK_WORDS)})")
    return out, ""


def _after_peak_positions(narrated: list, peaks: set, window: int) -> dict:
    """{position in `narrated` -> why it is after a peak}.

    A narrated line is after a peak when its own beat is a peak beat, or when
    it sits within `window` narrated lines after the LAST narrated line on a
    peak beat. The window is measured in NARRATED lines, not in draft lines: a
    hold between the peak and the shot list is precisely the remedy this gate
    prescribes, and counting it against the window would mean taking the
    remedy pushed the offending line out of the gate's reach.
    """
    out: dict = {}
    beats = [_beat_of(ln) for ln in narrated]
    last_on: dict = {}
    for i, b in enumerate(beats):
        if b in peaks:
            out[i] = f"on peak beat {b}"
            last_on[b] = i
    for b, i in last_on.items():
        for j in range(i + 1, min(len(narrated), i + 1 + max(0, window))):
            if j not in out:
                out[j] = (f"{j - i} narrated line(s) after the last line on "
                          f"peak beat {b}")
    return out


def shotlist_report(draft: dict, pdir: Path) -> dict:
    """[SHOT-LIST] and [SHOT-LIST-AFTER-PEAK]. Never raises.

    Anything that cannot be measured is SAID - as a note when the gate
    legitimately does not apply, as an error when the input is present but
    broken - and never as an absent finding, which reads as a pass.
    """
    try:
        return _report(draft, pdir)
    except Exception as e:                                  # noqa: BLE001
        # LAST RESORT, and it reports an ERROR rather than swallowing. The
        # house rule is that a gate must not raise, because the callers run
        # the gates in a list and one exception stops every gate after it. The
        # rule is NOT that a broken gate is a passing gate.
        import traceback
        return {"errors": [f"[SHOT-LIST] the shot-list gates could not run on "
                           f"{Path(pdir).name}: {type(e).__name__}: {e}. "
                           f"NOTHING was measured, so treat this as unchecked "
                           f"rather than clean, and fix the gate."],
                "warns": [], "notes": [traceback.format_exc(limit=4)],
                "stats": {}}


def _report(draft: dict, pdir: Path) -> dict:
    errors: list = []
    warns: list = []
    notes: list = []
    stats: dict = {}
    pdir = Path(pdir)

    min_items = int(getattr(config, "SHOTLIST_MIN_ITEMS", 3))
    min_vis = int(getattr(config, "SHOTLIST_MIN_VISIBLE", 2))
    window = int(getattr(config, "SHOTLIST_PEAK_WINDOW_LINES", 2))
    # Message formatting only, so it reuses the existing report-width
    # constant rather than adding a fourth one nobody calibrated.
    id_cap = int(getattr(config, "REVIEW_MAX_IDS_IN_MESSAGE", 8))

    raw = draft.get("lines") if isinstance(draft, dict) else None
    if not isinstance(raw, list):
        return {"errors": [], "warns": [],
                "notes": [f"[SHOT-LIST] the draft for {pdir.name} has no "
                          f"`lines` list, so no narration text could be read "
                          f"and NOTHING was measured. This is not a pass."],
                "stats": {"narrated_lines": 0, "sentences_examined": 0}}

    narrated = [ln for ln in raw if _narr(ln)]
    stats["draft_lines"] = len(raw)
    stats["narrated_lines"] = len(narrated)

    # ---- the shape, per sentence ----------------------------------------- #
    examined = 0
    found: list = []        # (position, line id, beat, sentence, why)
    unmeasurable: list = []
    for pos, ln in enumerate(narrated):
        lid = _lid(ln, pos)
        for s in split_sentences(_narr(ln)):
            examined += 1
            ok, why = is_shotlist_sentence(s)
            if why.startswith("!"):
                unmeasurable.append((lid, why[1:]))
                continue
            if ok:
                found.append((pos, lid, _beat_of(ln), s, why))
    stats["sentences_examined"] = examined
    stats["shotlist_sentences"] = len(found)
    stats["shotlist_line_ids"] = [f[1] for f in found]
    stats["min_items"] = min_items
    stats["min_visible"] = min_vis
    stats["peak_window_lines"] = window

    if unmeasurable:
        errors.append(
            f"[SHOT-LIST] {len(unmeasurable)} sentence(s) could not be "
            f"measured at all: "
            + "; ".join(f"line {i} ({w})" for i, w in unmeasurable[:id_cap])
            + ". Those sentences are UNCHECKED, not clean.")

    if not narrated:
        notes.append(
            f"[SHOT-LIST] {pdir.name}: 0 of {len(raw)} line(s) carry "
            f"narration, so there was no text to measure. Nothing was "
            f"checked.")

    # ---- the peaks -------------------------------------------------------- #
    peaks, trouble = peak_beats(pdir)
    stats["peak_beats"] = sorted(peaks)
    if trouble:
        # THE BLOCKING HALF CANNOT RUN, AND SAYS SO. It is a NOTE rather than
        # an error because a project that has not reached the angle stage must
        # not be blocked by this gate - the same reasoning, and the same
        # failure it is avoiding, as pacing_gates.pacing_report's own comment
        # about small fixtures with no angle. The WARNING half below still
        # runs, so a shot list is never silently passed.
        notes.append(
            f"[SHOT-LIST-AFTER-PEAK] could not run: {trouble}. A shot-list "
            f"sentence after a peak is the ERROR half of this gate and it was "
            f"NOT checked; every finding below is reported as a warning "
            f"instead, including any that sits on a peak. This is unchecked, "
            f"not clean.")
        after: dict = {}
    else:
        after = _after_peak_positions(narrated, peaks, window)
    stats["after_peak_positions"] = len(after)

    # ---- split the findings ----------------------------------------------- #
    bad_peak = [(f, after[f[0]]) for f in found if f[0] in after]
    bad_else = [f for f in found if f[0] not in after]
    stats["after_peak_line_ids"] = [f[1] for f, _w in bad_peak]
    stats["shotlist_beats"] = sorted({f[2] for f in found})

    if bad_peak:
        shown = "; ".join(
            f"line {f[1]} ({w}): \"{f[3]}\""
            for f, w in bad_peak[:id_cap])
        more = ("" if len(bad_peak) <= id_cap
                else f" (+{len(bad_peak) - id_cap} more)")
        errors.append(
            f"[SHOT-LIST-AFTER-PEAK] {len(bad_peak)} sentence(s) list what is "
            f"already on screen within {window} narrated line(s) of a peak "
            f"(peak beats {', '.join(sorted(peaks)) or '-'}): {shown}{more}. "
            f"These are the seconds the whole contour was built to buy, and "
            f"an inventory of the set is the one thing they cannot carry. For "
            f"each line, do ONE of two things: make it a HOLD - clear "
            f"`narration` and set `narration_silence_seconds` so the footage "
            f"and the music play alone - or give the line a POINT, a sentence "
            f"that says what the moment costs or means rather than what it "
            f"looks like. Deleting the sentence and leaving the rest of the "
            f"line is also a hold if nothing is left to say.")

    if bad_else:
        shown = "; ".join(f"line {f[1]} (beat {f[2]}): \"{f[3]}\""
                          for f in bad_else[:id_cap])
        more = ("" if len(bad_else) <= id_cap
                else f" (+{len(bad_else) - id_cap} more)")
        warns.append(
            f"[SHOT-LIST] {len(bad_else)} sentence(s) are a list of "
            f"{min_items}+ visible things with no verb of consequence and no "
            f"word of the narrator's own, i.e. a caption for a picture the "
            f"viewer is already looking at: {shown}{more}. Cut each one, or "
            f"replace it with what the place costs the person standing in it. "
            f"A sentence that only names the set spends runtime and delivers "
            f"nothing.")

    return {"errors": errors, "warns": warns, "notes": notes, "stats": stats}
