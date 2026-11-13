# FILM FACTS - the only real-world facts the recap may say

You write `projects/<p>/film_facts.json`. The film-intro block ("this is X, from
YEAR, directed by...") states facts the footage cannot show, so [FILM-INTRO] and
the fact audit check every such claim against THIS file and reject anything not
in it. Format example: `projects/tokyodrift2006/film_facts.json`.

## Source

English Wikipedia's article for the film, one revision. Record it in
`_source` (title + `oldid` + fetch date). Wikipedia decides what is true here;
the transcript, the catalogue and your memory are not sources.

## Fields

    title, year, genre, runtime_minutes, franchise_position (or null),
    director, writer, composer, studio,
    cast: [{actor, role, lead: bool, note}],
    facts: [{id: "F1", text, source: "Wikipedia, <Section> > <Subsection>"}],
    withheld: [{what, reveal: "R..", why, ban: ["exact phrase", ...]}]

- `genre`: Wikipedia's infobox genre list verbatim, comma-separated
  ("Thriller", "Coming-of-age comedy"). The opening-craft lever is chosen
  from these words - no genre, no lever, and the default is wrong for
  comedies and romances.
- `facts`: 3-6 production facts a viewer would enjoy (how a stunt was done, a
  casting story, a box-office turn). Each one sentence, each with its section.
- `cast`: leads first; `note` is Wikipedia's own one-line description.

## Withheld - read `projects/<p>/reveals.json` first

Two things are left out even when Wikipedia states them plainly, and listed
under `withheld` with the reveal they would give away:

1. a cast member whose APPEARANCE is itself a reveal (a cameo, a twist identity);
2. any franchise or production fact that implies a character's fate.

The omission must be visible in the file, not silent.

Every `withheld` entry carries `ban`: the exact phrases that would give it
away if the intro said them (the actor's name, the character's name, a
nickname - 1-6 short phrases). [FILM-INTRO] can only enforce what `ban`
lists; an entry without one protects nothing.
