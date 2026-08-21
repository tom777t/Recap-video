"""Build names.json from a film's Wikipedia *Cast* section.

PRE-CATALOGUE (RULES A7) already requires reading Wikipedia's Plot and Cast.
The Cast section maps actors to characters - "Leonardo DiCaprio as Teddy
Daniels" - and names.json was keeping only the character half. That discarded
half is the one field that lets anything put a name to a face, and the vision
experiments stalled on exactly its absence.

So: fetch it once, keep both halves, and stop retyping character names by hand.

Deliberately NOT automatic. It prints what it found and writes the file, but
whether the cast list is right for the cut you actually have is a judgement -
an extended cut can carry people the article does not list, and the article can
list people your cut cuts. Read the output.

Only the Cast section is fetched. Not the plot, not reviews - RULES A7 forbids
review and rating material, and there is no reason for this command to see it.

Uses urllib from the standard library; no new dependency.
"""
from __future__ import annotations

import io
import json
import re
import urllib.parse
import urllib.request

import config

UA = "RecapVidTool/1.0 (personal film-recap pipeline)"
RAW = "https://en.wikipedia.org/w/index.php?title={title}&action=raw"

# "* [[Leonardo DiCaprio]] as Edward "Teddy" Daniels ..." and its variants
# Everything before the FIRST " as " is the actor side, whatever shape it takes.
# Two shapes that a stricter single-actor pattern got wrong on real articles:
#   "[[Emily Mortimer]] and [[Patricia Clarkson]] as Rachel Solando"
#       - two actors, one character. The old pattern could not cross the "]]"
#         and skipped the line entirely, losing the character.
#   "** Mortimer portrays the version presented by Cawley as the one who..."
#       - a sub-bullet whose own " as " looks like a cast line. Caught by
#         _looks_like_a_name / _looks_like_a_character rather than by the regex.
LINE = re.compile(
    r"^\*+\s*(?P<actors>.+?)\s+as\s+(?P<character>[^\n]+)$",
    re.MULTILINE,
)

# the display half of a piped link is the name people use; the target half
# carries disambiguation like "(actress)" that is not part of anyone's name
LINK = re.compile(r"\[\[([^\]\|]+?)(?:\|([^\]]+?))?\]\]")


def _clean_character(s: str) -> str:
    s = re.sub(r"\[\[([^\]\|]+)\|([^\]]+)\]\]", r"\2", s)   # [[a|b]] -> b
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)               # [[a]]   -> a
    s = re.sub(r"\{\{[^}]*\}\}", "", s)                     # templates
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.split(",")[0]                                     # drop the description
    s = s.split(":")[0]
    s = re.sub(r"''+", "", s)
    s = s.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip(" .;-\u2013\u2014")


def _clean_actor(s: str) -> str:
    s = re.sub(r"''+", "", s)
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)      # drop "(actress)" style disambiguation
    return re.sub(r"\s+", " ", s).strip()


def _split_aliases(character: str):
    """One actor, several character names.

    Film articles write a dual identity as "Teddy Daniels / Andrew Laeddis",
    and that slash is not decoration - it IS the twist. Splitting it gives both
    names the same actor, which is exactly the mapping the vision scoring
    needed: the hand tags switch to the true name after the reveal while a
    model going by face keeps the first one, and without this pairing the two
    look like two different people.

    Also strips the nickname quotes in 'Edward "Teddy" Daniels' and keeps the
    quoted form too, since that is what narration actually calls him.
    """
    parts = [p.strip() for p in re.split(r"\s*/\s*", character) if p.strip()]
    out = []
    for part in parts:
        out.append(re.sub(r'\s+', ' ', part.replace('"', "").replace("\u201c", "")
                          .replace("\u201d", "")).strip())
        nick = re.search(r'"([^"]+)"', part)
        if nick:
            surname = re.sub(r'^.*?"[^"]+"\s*', "", part).strip()
            if surname:
                out.append(f"{nick.group(1)} {surname}")
    seen, uniq = set(), []
    for o in out:
        if o and o.lower() not in seen:
            seen.add(o.lower())
            uniq.append(o)
    return uniq


_PARTICLES = {"van", "von", "de", "der", "den", "di", "da", "la", "le", "du", "of",
              "del", "dos", "das", "do", "bin", "ibn", "al", "y", "e"}

# Words that belong to a SENTENCE about a person, never inside the person's
# name. This is what separates a clause from a name once length stops being a
# usable signal - a title-cased clause passes a capitalisation test, but no
# actor is called "Portrays" or "Revealed".
_CLAUSE_WORDS = {
    "portrays", "portrayed", "plays", "played", "appears", "appeared",
    "presents", "presented", "reveals", "revealed", "voices", "voiced",
    "stars", "starred", "depicts", "depicted", "credited", "reprises",
    "returns", "becomes", "became", "is", "was", "are", "were", "has",
    "had", "been", "being", "version", "role",
}

# Only DOUBLE quotes (straight or curly). Single quotes are left alone on
# purpose: O'Brien and D'Angelo are names, not nicknames.
_NICKNAME_RE = re.compile(r'["\u201c\u201d]\s*([^"\u201c\u201d]+?)\s*["\u201c\u201d]')


def _split_nickname(actor: str):
    """('Putthipong "Billkin" Assaratanakul') -> ('Putthipong Assaratanakul', 'Billkin').

    Thai credits carry the nickname inline, and it is not decoration: Billkin is
    what audiences and the narration actually call him. Returns (name, nickname)
    with nickname None when there is no quoted element.
    """
    m = _NICKNAME_RE.search(actor)
    if not m:
        return actor, None
    nick = m.group(1).strip()
    base = re.sub(r"\s+", " ", _NICKNAME_RE.sub(" ", actor)).strip()
    return (base or actor), (nick or None)


def _looks_like_a_name(actor: str) -> bool:
    """Reject a half-sentence that happened to sit before the word "as".

    Cast lines are not always one clean "X as Y". Emily Mortimer's line on the
    Shutter Island article contains " as " twice, and the second one turned
    "Mortimer portrays the version presented by Cawley" into an actor - which
    then took the real Rachel Solando entry out of the list entirely.

    The original test was `1 <= len(words) <= 4` plus a capitalisation walk.
    Both halves were scoped to Western naming and dropped five principals from
    howtomakemillions2024, including both leads:

      - `Putthipong "Billkin" Assaratanakul` is only three words, so length was
        never the problem there - the quoted nickname failed the capitalisation
        walk, because `"` is not stripped and `"Billkin"[0]` is not uppercase.
      - the four-word ceiling separately rejects long Iberian names such as
        `Maria Isabel Lopez de la Vega`.

    So: strip the nickname before counting, allow up to six words, and lean on
    capitalisation plus a clause-word test rather than on length. A name is
    capitalised throughout apart from particles; a clause contains a verb.
    """
    base, _nick = _split_nickname(actor)
    words = base.split()
    if not (1 <= len(words) <= 6):
        return False

    # A long line is only a name if it is a plain run of tokens. Slashes and
    # brackets at this length mean two people, or a parenthetical, not a name.
    if len(words) >= 5 and re.search(r"[/()\[\]]", base):
        return False

    # Length alone can no longer reject a clause, so name the clause directly.
    # Skipped for one- and two-word inputs, which cannot be a clause and where
    # a false positive would cost a real name.
    if len(words) >= 3:
        lowered = {w.strip("'\u2019.,;:-").lower() for w in words}
        if lowered & _CLAUSE_WORDS:
            return False

    caps = 0
    for w in words:
        stripped = w.strip("'\u2019.-\"\u201c\u201d")
        if not stripped:
            return False
        if stripped.lower() in _PARTICLES:
            continue
        if not stripped[0].isupper():
            return False
        caps += 1
    # Every non-particle token is capitalised by now. A 5-6 word line still has
    # to carry real name tokens rather than being mostly particles.
    return caps >= 3 if len(words) >= 5 else caps >= 1


def _looks_like_a_character(name: str) -> bool:
    """Reject a description. "the one who escaped Shutter Island" is not a name."""
    if not name or len(name) > 60:
        return False
    first = name.split()[0].lower()
    return first not in {"the", "a", "an", "his", "her", "their", "who", "one"}


def _title_from(arg: str) -> str:
    if arg.startswith("http"):
        path = urllib.parse.urlparse(arg).path
        return urllib.parse.unquote(path.rsplit("/", 1)[-1])
    return arg.replace(" ", "_")


def _fetch_raw(title: str) -> str:
    url = RAW.format(title=urllib.parse.quote(title, safe="_()'"))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_cast(page: str):
    """[(actor, character)] from the Cast section, in article order."""
    title = _title_from(page)
    wikitext = _fetch_raw(title)

    # Follow redirects. "Superbad (film)" is a redirect to "Superbad", and
    # action=raw returns the redirect line rather than the article - so the Cast
    # search found nothing and the command dead-ended with a message that did
    # not say why. Two hops is plenty; Wikipedia does not chain further.
    for _ in range(2):
        m = re.match(r"^\s*#REDIRECT\s*\[\[([^\]#|]+)", wikitext, re.IGNORECASE)
        if not m:
            break
        title = m.group(1).strip().replace(" ", "_")
        wikitext = _fetch_raw(title)

    # keep only the Cast section - nothing else on the page is in scope
    m = re.search(r"^==+\s*Cast[^=]*==+\s*$", wikitext, re.MULTILINE | re.IGNORECASE)
    if not m:
        # say WHAT the page does have, so the next step is obvious instead of
        # guessing at titles
        heads = re.findall(r"^==+\s*([^=\n]+?)\s*==+\s*$", wikitext, re.MULTILINE)
        detail = ("; sections on '%s': %s" % (title, ", ".join(heads[:12]))
                  if heads else "; the page appears to be empty or does not exist")
        return [], "no Cast section found" + detail, []
    rest = wikitext[m.end():]
    nxt = re.search(r"^==[^=]", rest, re.MULTILINE)
    section = rest[:nxt.start()] if nxt else rest

    out, seen, rejected = [], set(), []
    for hit in LINE.finditer(section):
        raw_actors = hit.group("actors")
        links = LINK.findall(raw_actors)
        if links:
            people = [_clean_actor(disp or target) for target, disp in links]
        else:
            people = [_clean_actor(raw_actors)]
        # Keep the nickname OUT of the stored actor name but not out of the
        # data: the display name is the formal one, the nickname rides along as
        # an alias because that is what people call him.
        kept_people, nicknames = [], []
        for a in people:
            if not a or not _looks_like_a_name(a):
                continue
            base, nick = _split_nickname(a)
            kept_people.append(base)
            if nick:
                nicknames.append(nick)
        people = kept_people

        character = _clean_character(hit.group("character"))
        if not people or not character or len(character) > 80:
            rejected.append(f"{_clean_actor(raw_actors)[:60]} | {character[:60]}")
            continue
        # one character genuinely played by two people (a role shown in two
        # versions) keeps both - which one a given frame shows is a judgement
        actor = " / ".join(dict.fromkeys(people))
        alias = " / ".join(dict.fromkeys(nicknames)) or None
        for name in _split_aliases(character):
            key = name.lower()
            if key in seen or not _looks_like_a_character(name):
                continue
            seen.add(key)
            out.append((actor, name, alias))
    return out, "", rejected


def build(project: str, page: str, write: bool = True):
    """Fetch, merge with any existing names.json, write. Returns the entries."""
    cast, err, rejected = fetch_cast(page)
    if err:
        return None, err, []
    if not cast:
        return None, "Cast section found but no 'Actor as Character' lines parsed", rejected

    p = config.project_dir(project) / "names.json"
    existing = []
    if p.exists():
        try:
            nd = json.load(io.open(p, encoding="utf-8-sig"))
            existing = nd.get("names", nd) if isinstance(nd, dict) else nd
        except Exception:
            existing = []

    entries = []
    for a, c, alias in cast:
        e = {"character": c, "actor": a}
        if alias:
            # Optional key. Consumers read "character"/"actor"; this rides
            # alongside so the nickname is not thrown away.
            e["actor_alias"] = alias
        entries.append(e)
    known = {e["character"].lower() for e in entries}

    # keep hand-added names the article does not list - they were added for a
    # reason, and this command is not entitled to decide it was a bad one
    kept = []
    for n in existing:
        name = n.get("character") or n.get("name") if isinstance(n, dict) else n
        if name and str(name).lower() not in known:
            kept.append({"character": str(name)} if not isinstance(n, dict) else n)
    entries.extend(kept)

    if write:
        io.open(p, "w", encoding="utf-8").write(
            json.dumps({"names": entries}, ensure_ascii=False, indent=2))
    return entries, "", rejected
