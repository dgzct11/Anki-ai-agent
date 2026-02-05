"""Cognate data and utilities for Spanish-English-French-Romanian learning.

Provides false friend warnings, cognate hints, and etymology-based
disambiguation for the Anki assistant.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# False Friends (~20 critical false cognates ES-EN)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FalseFriend:
    """A false cognate between Spanish and English."""
    spanish: str
    seems_like: str  # English word it resembles
    actual_meaning: str  # What it really means in Spanish
    english_equivalent: str  # The correct Spanish word for the English meaning
    warning: str  # Brief warning for the learner


FALSE_FRIENDS: list[FalseFriend] = [
    FalseFriend(
        spanish="embarazada",
        seems_like="embarrassed",
        actual_meaning="pregnant",
        english_equivalent="avergonzado/a = embarrassed",
        warning="embarazada means pregnant, NOT embarrassed",
    ),
    FalseFriend(
        spanish="éxito",
        seems_like="exit",
        actual_meaning="success",
        english_equivalent="salida = exit",
        warning="éxito means success, NOT exit",
    ),
    FalseFriend(
        spanish="carpeta",
        seems_like="carpet",
        actual_meaning="folder",
        english_equivalent="alfombra = carpet",
        warning="carpeta means folder, NOT carpet",
    ),
    FalseFriend(
        spanish="actual",
        seems_like="actual",
        actual_meaning="current, present-day",
        english_equivalent="real/verdadero = actual",
        warning="actual means current, NOT actual/real",
    ),
    FalseFriend(
        spanish="realizar",
        seems_like="realize",
        actual_meaning="to carry out, to accomplish",
        english_equivalent="darse cuenta = to realize",
        warning="realizar means to carry out, NOT to realize",
    ),
    FalseFriend(
        spanish="asistir",
        seems_like="assist",
        actual_meaning="to attend",
        english_equivalent="ayudar = to assist",
        warning="asistir means to attend, NOT to assist",
    ),
    FalseFriend(
        spanish="sensible",
        seems_like="sensible",
        actual_meaning="sensitive",
        english_equivalent="sensato = sensible",
        warning="sensible means sensitive, NOT sensible",
    ),
    FalseFriend(
        spanish="molestar",
        seems_like="molest",
        actual_meaning="to bother, to annoy",
        english_equivalent="abusar = to molest",
        warning="molestar means to bother, NOT to molest",
    ),
    FalseFriend(
        spanish="constipado",
        seems_like="constipated",
        actual_meaning="having a cold",
        english_equivalent="estreñido = constipated",
        warning="constipado means having a cold, NOT constipated",
    ),
    FalseFriend(
        spanish="librería",
        seems_like="library",
        actual_meaning="bookstore",
        english_equivalent="biblioteca = library",
        warning="librería means bookstore, NOT library",
    ),
    FalseFriend(
        spanish="fábrica",
        seems_like="fabric",
        actual_meaning="factory",
        english_equivalent="tela = fabric",
        warning="fábrica means factory, NOT fabric",
    ),
    FalseFriend(
        spanish="recordar",
        seems_like="record",
        actual_meaning="to remember",
        english_equivalent="grabar = to record",
        warning="recordar means to remember, NOT to record",
    ),
    FalseFriend(
        spanish="soportar",
        seems_like="support",
        actual_meaning="to bear, to endure",
        english_equivalent="apoyar = to support",
        warning="soportar means to endure, NOT to support",
    ),
    FalseFriend(
        spanish="largo",
        seems_like="large",
        actual_meaning="long",
        english_equivalent="grande = large",
        warning="largo means long, NOT large",
    ),
    FalseFriend(
        spanish="suceso",
        seems_like="success",
        actual_meaning="event, incident",
        english_equivalent="éxito = success",
        warning="suceso means event/incident, NOT success",
    ),
    FalseFriend(
        spanish="contestar",
        seems_like="contest",
        actual_meaning="to answer",
        english_equivalent="competir/disputar = to contest",
        warning="contestar means to answer, NOT to contest",
    ),
    FalseFriend(
        spanish="introducir",
        seems_like="introduce (a person)",
        actual_meaning="to insert, to input",
        english_equivalent="presentar = to introduce (a person)",
        warning="introducir means to insert/input, NOT to introduce someone",
    ),
    FalseFriend(
        spanish="compromiso",
        seems_like="compromise",
        actual_meaning="commitment, obligation",
        english_equivalent="acuerdo mutuo = compromise",
        warning="compromiso means commitment, NOT compromise",
    ),
    FalseFriend(
        spanish="pretender",
        seems_like="pretend",
        actual_meaning="to try, to attempt, to aspire to",
        english_equivalent="fingir = to pretend",
        warning="pretender means to try/aspire, NOT to pretend",
    ),
    FalseFriend(
        spanish="ropa",
        seems_like="rope",
        actual_meaning="clothing",
        english_equivalent="cuerda = rope",
        warning="ropa means clothing, NOT rope",
    ),
]

# Index by lowercase Spanish word for quick lookup
_FALSE_FRIENDS_INDEX: dict[str, FalseFriend] = {
    ff.spanish.lower(): ff for ff in FALSE_FRIENDS
}


def lookup_false_friend(word: str) -> FalseFriend | None:
    """Check if a word is a known false friend. Returns None if not."""
    return _FALSE_FRIENDS_INDEX.get(word.lower().strip())


def get_all_false_friends() -> list[FalseFriend]:
    """Return all false friends."""
    return list(FALSE_FRIENDS)


# ---------------------------------------------------------------------------
# Etymology data for disambiguation pairs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EtymologyPair:
    """A pair of Spanish words that learners confuse, with etymology to help."""
    word_a: str
    word_b: str
    latin_a: str  # Latin root of word_a
    latin_b: str  # Latin root of word_b
    meaning_a: str
    meaning_b: str
    mnemonic: str  # Memory aid using the etymology


DISAMBIGUATION_PAIRS: list[EtymologyPair] = [
    EtymologyPair(
        word_a="ser",
        word_b="estar",
        latin_a="sedere (to sit, to be settled)",
        latin_b="stare (to stand, to be in a state)",
        meaning_a="permanent/essential traits (identity, profession, origin)",
        meaning_b="temporary states, location, conditions",
        mnemonic="SER from sedere = settled/permanent. ESTAR from stare = standing/temporary state.",
    ),
    EtymologyPair(
        word_a="por",
        word_b="para",
        latin_a="pro (on behalf of, because of)",
        latin_b="per ad (through toward, for the purpose of)",
        meaning_a="cause, exchange, duration, through, by",
        meaning_b="purpose, destination, deadline, recipient",
        mnemonic="POR from pro = cause/reason behind. PARA from per ad = goal/destination ahead.",
    ),
    EtymologyPair(
        word_a="saber",
        word_b="conocer",
        latin_a="sapere (to taste, to have wisdom)",
        latin_b="cognoscere (to become acquainted with)",
        meaning_a="facts, information, how-to (learned knowledge)",
        meaning_b="people, places, familiarity (experiential knowledge)",
        mnemonic="SABER from sapere = tasting/knowing facts. CONOCER from cognoscere = getting to know.",
    ),
    EtymologyPair(
        word_a="pedir",
        word_b="preguntar",
        latin_a="petere (to seek, to request)",
        latin_b="percontari (to inquire)",
        meaning_a="to request, to ask for (something)",
        meaning_b="to ask (a question)",
        mnemonic="PEDIR = request something. PREGUNTAR = ask a question.",
    ),
    EtymologyPair(
        word_a="llevar",
        word_b="traer",
        latin_a="levare (to lift, to carry away)",
        latin_b="trahere (to pull, to draw toward)",
        meaning_a="to carry/take (away from here)",
        meaning_b="to bring (toward here)",
        mnemonic="LLEVAR = carry away (from speaker). TRAER = bring here (toward speaker).",
    ),
]

# Index by either word in the pair
_DISAMBIGUATION_INDEX: dict[str, EtymologyPair] = {}
for _pair in DISAMBIGUATION_PAIRS:
    _DISAMBIGUATION_INDEX[_pair.word_a.lower()] = _pair
    _DISAMBIGUATION_INDEX[_pair.word_b.lower()] = _pair


def lookup_disambiguation(word: str) -> EtymologyPair | None:
    """Check if a word is part of a disambiguation pair. Returns None if not."""
    return _DISAMBIGUATION_INDEX.get(word.lower().strip())


def get_all_disambiguation_pairs() -> list[EtymologyPair]:
    """Return all disambiguation pairs."""
    return list(DISAMBIGUATION_PAIRS)


# ---------------------------------------------------------------------------
# Cognate scan utilities (C6) - depends on cognate_type in CEFR data
# ---------------------------------------------------------------------------

def classify_words_by_cognate_type(
    words: list[str],
    cefr_data,
) -> dict[str, list[dict]]:
    """Classify a list of words by their cognate_type field from CEFR data.

    Returns a dict with keys: transparent, semi_transparent, false_friend, none, unknown.
    Each value is a list of dicts with word info.

    Requires cognate_type field in CEFR data (added by cognate taggers).
    """
    groups: dict[str, list[dict]] = {
        "transparent": [],
        "semi_transparent": [],
        "false_friend": [],
        "none": [],
        "unknown": [],
    }

    cefr_data.load()

    for word in words:
        result = cefr_data.lookup_word(word)
        if result is None:
            groups["unknown"].append({"word": word})
            continue

        level, cefr_word = result
        # Check if the cognate_type field exists (it's added dynamically
        # by the cognate taggers modifying the JSON data files)
        cognate_type = None
        if hasattr(cefr_word, "cognate_type"):
            cognate_type = cefr_word.cognate_type
        # Also check the raw tags for cognate:: prefix
        for tag in (cefr_word.tags or []):
            if tag.startswith("cognate::"):
                cognate_type = tag.split("::", 1)[1]
                break

        if cognate_type and cognate_type in groups:
            groups[cognate_type].append({
                "word": cefr_word.word,
                "english": cefr_word.english,
                "level": level,
                "cognate_type": cognate_type,
            })
        else:
            groups["none"].append({
                "word": cefr_word.word,
                "english": cefr_word.english,
                "level": level,
                "cognate_type": cognate_type or "none",
            })

    return groups


def format_cognate_scan_text(groups: dict[str, list[dict]]) -> str:
    """Format cognate scan results as plain text."""
    lines = ["Cognate Scan Results", "=" * 40, ""]

    section_labels = {
        "transparent": "You probably already recognize these (transparent cognates):",
        "semi_transparent": "These are close -- easy to learn (semi-transparent):",
        "false_friend": "Watch out for these false friends!",
        "none": "These need real study (no cognate connection):",
        "unknown": "Not found in CEFR word lists:",
    }

    for key, label in section_labels.items():
        items = groups.get(key, [])
        if not items:
            continue
        lines.append(f"{label} ({len(items)})")
        for item in items:
            eng = item.get("english", "")
            lvl = item.get("level", "")
            suffix = f" - {eng}" if eng else ""
            suffix += f" [{lvl}]" if lvl else ""
            lines.append(f"  {item['word']}{suffix}")
        lines.append("")

    total = sum(len(v) for v in groups.values())
    lines.append(f"Total: {total} words scanned")
    return "\n".join(lines)
