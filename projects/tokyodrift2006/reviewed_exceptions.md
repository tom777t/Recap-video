# Reviewed exceptions — The Fast and the Furious: Tokyo Drift (2006)

Findings **looked at and deliberately kept**. Each still prints on every run
and stays visible in the report; it just is not counted as a problem.

Not a mute button: the key names the exact finding, never the gate; a blanket
entry is refused by the parser; an entry with no date or reason is refused;
and if the finding stops occurring the run reports it **STALE** and asks for
deletion, so a leftover note cannot cover the next one.

```reviewed-exceptions
REVEAL-TIMING | R4 ? 87260c8b | 2026-10-31 | The matched term is "returning" inside a VERBATIM quotation - "I'm only returning what belonged to you in the first place, sir" - which is about handing back money, at 01:22:29. R4 protects a returning CHARACTER, who lands at 01:36:38, fourteen minutes later. REVEAL-TIMING is a literal-term scan and says so in its own output; it cannot tell returning money from a returning man. Rewording is refused on a different ground from the usual one: the clause is a quotation checked against the transcript, and paraphrasing it to satisfy a regex would make the recap misquote the film.
REVEAL-TIMING | R4 ? eafdc58b | 2026-10-31 | The matched term is "family" in "somebody who ran with Han, and who told Twinkie that Han was family", at 01:35:49, forty-nine seconds before the reveal lands at 01:36:38. This one is NOT a false positive - it is deliberate foreshadowing, and the viewer asked for it in writing: "Keep 'Han was family' as the emotional bridge into Dom." It names no character, no film and no franchise, so it cannot disclose WHO the challenger is; what it does is make the arrival land instead of appearing from nowhere. Verified that no other held term appears before the landing: no Dominic, Dom, Toretto, Vin Diesel, cameo, familiar face, "he knew Han", "an old friend of Han's", or any reference to earlier films.
```

## Why this one is kept

The reveal-map on this film is deliberately strict — four protected facts,
two of them (Sean taking the crown, and the final-scene cameo) landing in the
last four minutes. That strictness is what makes a false positive worth
recording rather than quietly rewritten: the alternative is a habit of
rephrasing whenever a gate complains, which over time removes the gate's
ability to mean anything.

## What was verified before keeping it

- Every draft line between `01:05:24` and `01:15:07` read in full.
- No past-tense reference to Han anywhere before the crash.
- The word "dead" first appears at `01:15:39`, after the land.
- "stealing" first appears at `01:07:29.823`, exactly on R1's land.

## Not reviewed — left live on purpose

`[NAME-LEAK]` currently reports ten tokens that are real-world proper nouns
rather than characters: *Ken, Barbie, Japan, Hulk, Donkey Kong, Corolla,
Australian, Kabukicho, Ford's*. These are the gate's "verify this is real
on-screen text" class and they are correct to fire — each one is a claim about
the world that a reader should be able to check. They are **not** suppressed.

## Deleted

- `REVEAL-TIMING | R2 L103` (added 2026-09-11, deleted 2026-10-30).
  The run reported it STALE: the "smile dies" sentence is not in the
  rewritten draft, so the entry covers nothing, and the mechanism's
  own rule is that a leftover note must not be left to cover a future
  finding. No replacement entry was added - the five R4 hits in the
  new draft ("family", "returning") were REWORDED instead, because
  unlike the dying smile those words were not load-bearing and
  changing them cost the prose nothing.
