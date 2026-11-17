# ANGLE - what this recap is about, and who is telling it

You write `projects/<p>/angle.md` and `projects/<p>/coverage_policy.json` for
one film. You run AFTER the beat map and reveal map are locked and BEFORE any
draft line is written. The draft writers read your file; the gates parse it.

## Read first

- `projects/<p>/beats_proposal.md` (beat ids B01... with timestamps and what happens)
- `projects/<p>/reveals.json` (what the film hides, and when it lands)
- `projects/<p>/names.json`, `projects/<p>/film_facts.json`
- `prompts/story_guide.md`: how this channel tells a film. Your angle serves
  a recap that someone who never saw the film can follow on ONE hearing.

Do not watch or summarise the film beat by beat. Your job is to CHOOSE.

## The sections (fixed headings - `pipeline/angle_spec.py` parses them and fails loudly)

### `## ANGLE`
One sentence: the human thread this recap follows from the first minute to the
last, in plain words (no metaphor the listener would have to decode). Then 2-4
sentences on the spine the film actually plays, as a chain of causes, citing
beat ids. Then **three questions** a listener must be able to answer at the
end ("Why are Shaw and Jakande on the same side?"), as a list.

### `## ATTITUDE TO CHARACTERS`
One bullet per main character: how the narrator FEELS about them (fond, wary,
teasing, afraid of, protective of), and the one thing it refuses to reduce
them to. This is where real reactions come from: knowing when to be glad,
annoyed or moved.

### `## SETUPS AND PAYOFFS`
Details **that are in the film** and come back later: a clue, an object, a
line of dialogue planted early and paid off. Examples: a slip of the tongue
("Boss") that gives away a secret identity, or a decoy CEO set up in gossip
and exposed by a news headline. 0-4 numbered entries:

    1. **"Boss"** - Daniel's slip. **Setup: B07** (the prison walk) -> **Payoff: B52** (Cassie overhears it)

Never a phrase or metaphor the NARRATOR invents and repeats ("the ledger",
"the exchange rate"). Listeners hear a refrain like that as a riddle. If the
film has no such detail, write `None.` under the heading.
Budget: each entry = setup once + at most 2 callbacks + payoff once.

### `## ANCHORS`
The scenes the recap is built to ARRIVE at - hook payoff, thesis, reveals,
emotional peaks. Name as many as THIS film really has (most films have 4-10);
do not pad to a number or cut to one. An anchor gets room to land; the beats
between anchors still tell the story - who does what and why - not a summary.
Format, one per line:

    - **B13** | emotional peak | why it is load-bearing | evidence: "verbatim words from B13's `what` in the beat map"

Every anchor MUST end with `evidence: "..."` quoting the beat map's own `what`
text VERBATIM ([ANCHOR-EVIDENCE] checks it against the beat). An anchor that is also listed as secondary/footage-only
below is an error. Check each quote against `beats_proposal.md` before writing.

### `## HOOK PROMISES`
Every clause the hook/intro will promise, mapped to the anchor that cashes it:

    - "clause" -> B35, B60 | note | evidence: "verbatim words from the delivering beat's `what`"

A promise may not land in a compressed or footage-only beat ([HOOK-PAYOFF]).

### `## NARRATOR PERSONA`
- `**Stance:**` one sentence: who is telling this, as a person (e.g. a friend
  who loves car films and will not pretend the plot is cleverer than it is).
- `**Never:**` 0-3 bullets, only for this film's own traps (e.g. "never treat
  his wealth as the romance"). The general rules are in the story guide.

No "signature moves". Stock moves repeated across a video are what made our
old scripts sound machine-made.

### `## WHAT THE ANGLE SELECTS`
- **Mandatory regardless** (spine + every reveal + every reveal's setup), as beat ranges.
- **Kept because they serve the angle.**
- **Secondary - compress to a line or hold on footage.**

## coverage_policy.json

    {"_note": "derived from angle.md", "mandatory": ["B01", "B10", ...]}

`mandatory` = every beat id in "Mandatory regardless" + every anchor + every
reveal's landing and setup beats. Nothing else. [BEAT-COVERAGE] fails the draft
if a mandatory beat has no line, so do not pad it.

## intro_style.txt - a SUGGESTION, the owner decides

If `projects/<p>/intro_style.txt` does NOT exist, write it with the intro
montage edit style you suggest for this film and why, in this shape:

    emotional
    # suggested by the angle stage: <one line - why this film's opening wants it>

The first line is exactly one of: energetic, emotional, suspense, mystery,
horror, comedy, epic, romance. Choose from the ANGLE and the ATTITUDE, not
from the music. **If the file already exists, do not touch it** - it is the
owner's choice once it is there.

## Before you finish

- Every B-number you cite exists in `beats_proposal.md`.
- No anchor is also secondary. Every hook promise maps to an anchor.
- No reveal is spoiled by the ANGLE sentence itself being read early - the
  writers will quote it.
