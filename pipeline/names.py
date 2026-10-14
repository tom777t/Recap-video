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
import urllib.error
import urllib.parse
import urllib.request

import config


class FetchError(Exception):
    """A page could not be fetched, for a reason the user can act on.

    Mistyping a page title is an ordinary mistake, not a defect, and a
    traceback tells the user nothing they can use. This carries a single
    sentence that names the title and what to do about it; the command prints
    it and stops.
    """

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


# --------------------------------------------------------------------------
# Prose fallback
#
# Some articles never write a cast list. Bad Genius (2017) puts the same
# mapping inside sentences - "made her film acting debut as Lynn",
# "[[Chanon Santinatornkul]] played the role of Bank" - and the bullet parser
# returns nothing at all on it. An empty list is the worst possible answer
# here: it looks like a film with no cast rather than like a parser that did
# not recognise the shape.
#
# This is deliberately reported as its own mode. Extracting a mapping from
# prose is guesswork in a way that reading a list is not: it infers which
# actor a role phrase belongs to from word order, and word order lies. The
# caller says which path ran so the output gets read with the right amount of
# suspicion.
# --------------------------------------------------------------------------

# A role phrase, and the actor sits BEFORE it: "... as Lynn", "who played
# Lynn's father", "played the role of Bank". Longest alternatives first so
# "played the role of" never degrades into a bare "played".
_ACTOR_FIRST = re.compile(
    r"\b(?:who\s+|and\s+)?"
    r"(?:played\s+the\s+role\s+of|in\s+the\s+role\s+of|"
    r"portrayed|portrays|played|plays|as)\s+",
    re.IGNORECASE,
)

# The mirror image: the role comes first and the actors follow.
# "Pat and Grace were played by [[Teeradon ...]] and [[Eisaya ...]],
# respectively" carries two complete pairs in one clause, and dropping it
# would lose two of the five principals on Bad Genius.
_LINK_RUN = re.compile(r"\[\[[^\]]+\]\](?:\s*(?:,\s*|\s+and\s+|\s*&\s*)\[\[[^\]]+\]\])*")
# The role side has to be a run of capitalised name tokens, not "anything up to
# the verb". An open-ended capture reaches backwards across "]]" and eats the
# previous clause: on Bad Genius it turned "Chanon Santinatornkul]] played the
# role of Bank" into a character name and then paired it with the wrong actor.
_NAME_RUN = r"[A-Z][\w'\u2019.\-]*(?:\s+[A-Z][\w'\u2019.\-]*){0,3}"
_ROLE_FIRST = re.compile(
    r"(?P<roles>" + _NAME_RUN + r"(?:\s*(?:,\s*|\s+and\s+)" + _NAME_RUN + r")*)"
    r"\s+(?:were|was|are|is)\s+(?:played|portrayed)\s+by\s+")

# A role ends where the sentence turns back into prose.
_ROLE_END = re.compile(r"\s*(?:[,.;:()\[<]|\s\u2013\s|\s\u2014\s|\band\b|\bwho\b|$)")


def _strip_markup(section: str) -> str:
    """Flatten wikitext to sentences, keeping [[links]] intact.

    Image captions are dropped wholesale. A caption is prose about a person
    that sits next to their name - "Lead actress [[Chutimon ...]], a fashion
    model, made her film debut" - which is exactly the shape this parser looks
    for, and exactly the place it would be wrong.
    """
    out = []
    for ln in section.splitlines():
        if re.match(r"\s*\[\[\s*(?:File|Image)\s*:", ln, re.IGNORECASE):
            continue
        out.append(ln)
    s = "\n".join(out)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/\s*>", " ", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", " ", s, flags=re.S)
    s = re.sub(r"\{\{[^{}]*\}\}", " ", s)          # innermost templates
    s = re.sub(r"\{\{[^{}]*\}\}", " ", s)          # and one level of nesting
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ")
    s = re.sub(r"''+", "", s)
    return s


def _sentences(text: str):
    """(offset, sentence) pairs. Offsets keep the output in article order."""
    pos = 0
    for part in re.split(r"(?<=[.!?])\s+", text):
        yield pos, part
        pos += len(part) + 1


def _role_at(sentence: str, start: int):
    """Read a character name out of the text following a role phrase."""
    tail = sentence[start:]
    m = _ROLE_END.search(tail)
    raw = tail[:m.start()] if m and m.start() > 0 else tail
    # A role is a name, and names are capitalised. This one test is what keeps
    # "served as acting coach" and "as her character is left-handed" out - both
    # sit in the same section as the real cast sentences on Bad Genius.
    stripped = raw.strip()
    if not stripped or not stripped[0].isupper():
        return ""
    return _clean_character(stripped)


def _parse_prose(section: str):
    """[(offset, actor, character)] mined from sentences. Order is article order."""
    text = _strip_markup(section)
    found, rejected = [], []

    for base, sent in _sentences(text):
        links = [(m.start(), m.end(), m) for m in LINK.finditer(sent)]
        if not links:
            continue
        masked = [False] * len(sent)

        def _actor_before(pos):
            best = None
            for ls, le, m in links:
                if le <= pos:
                    best = m
                else:
                    break
            if not best:
                return None
            return _clean_actor(best.group(2) or best.group(1))

        # role-first, possibly several roles to several actors
        for m in _ROLE_FIRST.finditer(sent):
            run = _LINK_RUN.match(sent, m.end())
            if not run:
                continue
            actors = [_clean_actor(d or t) for t, d in LINK.findall(run.group(0))]
            roles = [r.strip() for r in re.split(r"\s*,\s*|\s+and\s+", m.group("roles"))
                     if r.strip()]
            roles = [r for r in roles if r and r[0].isupper()]
            if len(roles) != len(actors) or not roles:
                rejected.append(f"{' / '.join(roles)[:40]} | played by "
                                f"{' / '.join(actors)[:40]} (counts do not pair)")
                continue
            for i, (r, a) in enumerate(zip(roles, actors)):
                found.append((base + m.start("roles") + i, a, _clean_character(r)))
            for i in range(m.start(), run.end()):
                masked[i] = True

        # actor-first
        for m in _ACTOR_FIRST.finditer(sent):
            if masked[m.start()]:
                continue
            character = _role_at(sent, m.end())
            if not character:
                continue
            actor = _actor_before(m.start())
            if not actor:
                continue
            found.append((base + m.end(), actor, character))

    return found, rejected


def _title_from(arg: str) -> str:
    if arg.startswith("http"):
        path = urllib.parse.urlparse(arg).path
        return urllib.parse.unquote(path.rsplit("/", 1)[-1])
    return arg.replace(" ", "_")


def _fetch_raw(title: str) -> str:
    url = RAW.format(title=urllib.parse.quote(title, safe="_()'"))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FetchError(
                f"no Wikipedia page titled '{title.replace('_', ' ')}' "
                f"- check the title, or paste the article URL instead") from None
        raise FetchError(
            f"Wikipedia returned HTTP {e.code} ({e.reason}) for "
            f"'{title.replace('_', ' ')}'") from None
    except urllib.error.URLError as e:
        raise FetchError(f"could not reach Wikipedia: {e.reason}") from None


def fetch_cast(page: str):
    """[(actor, character)] from the Cast section, in article order."""
    title = _title_from(page)
    try:
        wikitext = _fetch_raw(title)

        # Follow redirects. "Superbad (film)" is a redirect to "Superbad", and
        # action=raw returns the redirect line rather than the article - so the
        # Cast search found nothing and the command dead-ended with a message
        # that did not say why. Two hops is plenty; Wikipedia does not chain
        # further.
        for _ in range(2):
            m = re.match(r"^\s*#REDIRECT\s*\[\[([^\]#|]+)", wikitext, re.IGNORECASE)
            if not m:
                break
            title = m.group(1).strip().replace(" ", "_")
            wikitext = _fetch_raw(title)
    except FetchError as e:
        return [], str(e), [], ""

    # keep only the Cast section - nothing else on the page is in scope
    m = re.search(r"^==+\s*Cast[^=]*==+\s*$", wikitext, re.MULTILINE | re.IGNORECASE)
    if not m:
        # say WHAT the page does have, so the next step is obvious instead of
        # guessing at titles
        heads = re.findall(r"^==+\s*([^=\n]+?)\s*==+\s*$", wikitext, re.MULTILINE)
        detail = ("; sections on '%s': %s" % (title, ", ".join(heads[:12]))
                  if heads else "; the page appears to be empty or does not exist")
        return [], "no Cast section found" + detail, [], ""
    rest = wikitext[m.end():]
    # Stop at the next heading of the SAME level or shallower. The old test
    # only stopped at "==", so a "===Casting===" subsection ran on through
    # Filming and everything after it - which does not matter to a bullet
    # parser that finds nothing there anyway, but hands the prose parser three
    # thousand characters of camera talk to misread.
    depth = len(re.match(r"=+", m.group(0).strip()).group(0))
    nxt = re.search(r"^={2,%d}[^=]" % depth, rest, re.MULTILINE)
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
    if out:
        return out, "", rejected, "list"

    # The list parser found nothing. Before giving up, try the section as
    # prose - but say so, because it is a weaker reading of a weaker source.
    prose, prose_rejected = _parse_prose(section)
    for _off, actor, character in sorted(prose, key=lambda p: p[0]):
        if not actor or not _looks_like_a_name(actor):
            continue
        base, nick = _split_nickname(actor)
        for name in _split_aliases(character):
            key = name.lower()
            if key in seen or not _looks_like_a_character(name):
                continue
            seen.add(key)
            out.append((base, name, nick))
    if out:
        return out, "", rejected + prose_rejected, "prose"

    # Still nothing. Name the shape that was actually there. "no lines parsed"
    # is the message that sent this bug looking in the wrong place twice.
    if re.search(r"^\s*\{\|", section, re.MULTILINE):
        shape = "the section is a wikitable, which this parser does not read"
    elif re.search(r"<gallery", section, re.IGNORECASE):
        shape = "the section is a gallery, which this parser does not read"
    elif re.search(r"^\*", section, re.MULTILINE):
        shape = ("the section is a bullet list, but no line matched "
                 "'Actor as Character'")
    elif section.strip():
        shape = ("the section is prose, and no 'as/played/in the role of' "
                 "phrasing tied an actor to a character")
    else:
        shape = "the section is empty"
    return [], f"Cast section found but nothing could be read from it - {shape}", \
        rejected + prose_rejected, ""


def build(project: str, page: str, write: bool = True):
    """Fetch, merge with any existing names.json, write. Returns the entries."""
    cast, err, rejected, mode = fetch_cast(page)
    if err:
        return None, err, rejected, mode
    if not cast:
        return None, "Cast section found but no 'Actor as Character' lines parsed", \
            rejected, mode

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
    return entries, "", rejected, mode
