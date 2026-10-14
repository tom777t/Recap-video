# DESIGN — Stage 4 architecture

*Status: DESIGN REQUIREMENT, not built. Recorded 2026-09-05.*

---

## R1. The reveal-map alias list must be generated blind to the narration

### The requirement

> **The call that generates a reveal's `hold:` alias list MUST NOT be able to
> see the narration it will be checked against.**
>
> This is **independence**, not ordering. Writing the alias list into
> `beats_proposal.md` at Stage 1.5, before any draft exists, satisfies ordering
> and provides almost nothing — because in the automated loop the same model
> writes the beat map and the narration. Ordering without independence is
> theatre.

### Why this and not a ratchet

The 2026-09-05 ratchet handles three of the four self-certification cases, and
it handles the *tampering* half of this one: aliases may grow, shrinking is
printed and named; `land:` may move earlier, later is printed and named.

It does not touch the half that actually matters.

| how `reveal-map` fails | ratchet catches it |
|---|---|
| narrow the alias list after writing the narration | **yes** |
| push `land:` later so more of the draft is unprotected | **yes** |
| **never think of the alias in the first place** | **no** |

The third is dominant, and it is not adversarial. Nobody omits *"the man with
metal arms"* to cheat; they omit it because it did not occur to them.
**RULES B11** is the recorded case: at Shutter Island a line reading *"the
stories people tell themselves to survive"* implied the entire twist, and
`REVEAL-TIMING` saw nothing, because no listed term appeared.

A ratchet proves a list did not shrink. It cannot prove the list was ever
adequate. **Locking an incomplete list fixes the incompleteness in place.**

### What independence buys

An alias list written by a call that can see the narration is subject to a
quiet, entirely honest-feeling bias: the author reads what they wrote, sees no
leak, and produces a list that describes the prose rather than the reveal. The
list and the text agree because they came from the same place.

A call that sees only the **film's plot** (A7's Wikipedia read, the cast list,
the beat map) and never the narration has nothing to accommodate. It enumerates
how the reveal *could* be given away, not how this draft happens to give it
away.

### Shape

    generate_reveal_aliases(film_plot, cast, beat_map) -> {reveal_id: [aliases]}
        MUST NOT receive: draft.json, script.txt, any narration text
        MUST receive:     enough about the film to enumerate paraphrase

The boundary is the point. If the function signature can reach the narration,
the requirement is not met, however carefully the prompt asks it not to look.

### Interaction with what already exists

- **`REVEAL-TIMING`** — unchanged. Still a literal-term scan, still a floor,
  still blind to paraphrase not in the list. Independence makes the list better;
  it does not make the gate smarter.
- **`RATCHET`** — complementary and still needed. Independence produces a good
  list once; the ratchet stops it degrading afterwards.
- **`H-REVEAL-B`** (`GATE_CANDIDATES.md`) — the `carried: image | dialogue`
  column belongs to the same block and should be declared in the same blind
  call. A dialogue-carried reveal cannot be verified by any footage check, and
  the generator is where that fact gets recorded.
- **`J1`** (`RULES.md`) — unaffected. Speech claims remain a floor that verifies
  speaker presence and never content.

### Why it is not built yet

It needs a call boundary that does not exist. Stage 4 has no notion of a
context that is denied an input; every stage today reads whatever is in the
project directory. Bolting it onto the ratchet would produce the ordering
illusion again — a file written earlier by the same agent — which is the thing
this requirement exists to reject.

Build it when Stage 4 gets real call boundaries. Not before.

---

## Related, recorded elsewhere

- `docs/RULES.md` — **A11 retired**: a threshold whose subject also supplies its
  reference data measures the label, not the work. The general repair is to make
  it an input, then check the input only ever moves toward strictness.
- `docs/GATE_CANDIDATES.md` — `H-REVEAL`, `H-REVEAL-B`, `J-SPEECH-CONTENT`,
  `K-OVERFILL`, `L-FAMILY-SEMANTICS`.
- `tools/gate_selftest.py` — positive tests. Any gate added here needs one
  before it is trusted; "never fires" and "cannot fire" are indistinguishable
  from outside.
