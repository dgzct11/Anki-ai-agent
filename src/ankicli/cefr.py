"""CEFR data loading, card matching, and progress tracking."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .paths import CEFR_CACHE_FILE, DATA_DIR, ensure_data_dir

# Where the vocabulary/grammar JSON files live
_CEFR_DIR = Path(__file__).parent / "data" / "cefr"

LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CEFRWord:
    word: str
    english: str
    pos: str
    gender: str | None
    category: str
    subcategory: str
    tags: list[str]
    level: str = ""
    cognate_type: str | None = None  # transparent, semi_transparent, false_friend, or None


@dataclass
class CEFRGrammarConcept:
    id: str
    concept: str
    category: str
    description: str
    key_verbs: list[str]
    common_errors: list[str]
    practice_patterns: list[str]
    level: str = ""


@dataclass
class CategoryProgress:
    category: str
    known: int = 0
    total: int = 0

    @property
    def percent(self) -> float:
        return (self.known / self.total * 100) if self.total > 0 else 0.0


@dataclass
class LevelProgress:
    level: str
    words_known: int = 0
    words_total: int = 0
    matched_words: list[str] = field(default_factory=list)
    unknown_words: list[str] = field(default_factory=list)
    categories: dict[str, CategoryProgress] = field(default_factory=dict)

    @property
    def percent(self) -> float:
        return (self.words_known / self.words_total * 100) if self.words_total > 0 else 0.0


# ---------------------------------------------------------------------------
# CEFRData: loads and queries vocabulary/grammar files
# ---------------------------------------------------------------------------

class CEFRData:
    """Loads CEFR vocabulary and grammar data from JSON files."""

    def __init__(self) -> None:
        self._words: dict[str, list[CEFRWord]] = {}
        self._grammar: dict[str, list[CEFRGrammarConcept]] = {}
        self._word_index: dict[str, tuple[str, CEFRWord]] = {}  # word -> (level, CEFRWord)
        self._loaded = False

    def load(self) -> None:
        """Load all available CEFR data files."""
        if self._loaded:
            return

        vocab_dir = _CEFR_DIR / "vocabulary"
        grammar_dir = _CEFR_DIR / "grammar"

        for level in LEVELS:
            # Vocabulary
            vocab_file = vocab_dir / f"{level.lower()}.json"
            if vocab_file.exists():
                try:
                    raw = json.loads(vocab_file.read_text(encoding="utf-8"))
                    words = []
                    for entry in raw:
                        w = CEFRWord(
                            word=entry["word"],
                            english=entry["english"],
                            pos=entry["pos"],
                            gender=entry.get("gender"),
                            category=entry["category"],
                            subcategory=entry.get("subcategory", ""),
                            tags=entry.get("tags", []),
                            level=level,
                            cognate_type=entry.get("cognate_type"),
                        )
                        words.append(w)
                        # Index by lowercase word for fast lookup
                        self._word_index[w.word.lower()] = (level, w)
                    self._words[level] = words
                except (json.JSONDecodeError, KeyError):
                    self._words[level] = []
            else:
                self._words[level] = []

            # Grammar
            grammar_file = grammar_dir / f"{level.lower()}.json"
            if grammar_file.exists():
                try:
                    raw = json.loads(grammar_file.read_text(encoding="utf-8"))
                    concepts = []
                    for entry in raw:
                        g = CEFRGrammarConcept(
                            id=entry["id"],
                            concept=entry["concept"],
                            category=entry.get("category", ""),
                            description=entry.get("description", ""),
                            key_verbs=entry.get("key_verbs", []),
                            common_errors=entry.get("common_errors", []),
                            practice_patterns=entry.get("practice_patterns", []),
                            level=level,
                        )
                        concepts.append(g)
                    self._grammar[level] = concepts
                except (json.JSONDecodeError, KeyError):
                    self._grammar[level] = []
            else:
                self._grammar[level] = []

        self._loaded = True

    # -- Query methods --

    def get_words_for_level(self, level: str) -> list[CEFRWord]:
        self.load()
        return self._words.get(level.upper(), [])

    def get_grammar_for_level(self, level: str) -> list[CEFRGrammarConcept]:
        self.load()
        return self._grammar.get(level.upper(), [])

    def get_all_words_up_to_level(self, level: str) -> list[CEFRWord]:
        """Get all words from A1 up to and including *level*."""
        self.load()
        result = []
        for lv in LEVELS:
            result.extend(self._words.get(lv, []))
            if lv.upper() == level.upper():
                break
        return result

    def get_categories_for_level(self, level: str) -> dict[str, list[CEFRWord]]:
        """Group words by category for a level."""
        self.load()
        by_cat: dict[str, list[CEFRWord]] = {}
        for w in self._words.get(level.upper(), []):
            by_cat.setdefault(w.category, []).append(w)
        return by_cat

    def lookup_word(self, word: str) -> tuple[str, CEFRWord] | None:
        """Look up a word. Returns (level, CEFRWord) or None."""
        self.load()
        return self._word_index.get(word.lower())

    def get_level_counts(self) -> dict[str, int]:
        """Return {level: word_count} for all levels with data."""
        self.load()
        return {lv: len(ws) for lv, ws in self._words.items()}


# ---------------------------------------------------------------------------
# Card matching
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_BOLD_RE = re.compile(r"<b>(.*?)</b>", re.IGNORECASE)


def _extract_spanish_word_from_back(back_html: str) -> str | None:
    """Try to extract the main Spanish word from the back of a card.

    Looks for the first <b>...</b> tag which typically contains the Spanish word.
    """
    m = _BOLD_RE.search(back_html)
    if m:
        text = m.group(1).strip()
        # Strip gender markers like "(m.)" or "(f.)"
        text = re.sub(r"\s*\(.*?\)\s*$", "", text).strip()
        # Strip articles
        for art in ("el ", "la ", "los ", "las ", "un ", "una "):
            if text.lower().startswith(art):
                text = text[len(art):]
                break
        return text.lower().strip() if text else None
    return None


def match_cards_to_cefr(
    anki,
    cefr_data: CEFRData,
    deck_name: str | None = None,
) -> dict[str, LevelProgress]:
    """Match existing Anki cards against CEFR word lists.

    Uses two tiers:
      Tier 1: word:: tags (exact match, fast)
      Tier 2: HTML back-field extraction (fallback)

    Returns a dict of level -> LevelProgress.
    """
    cefr_data.load()

    # Collect word:: tags from all cards in the deck
    query = f'deck:"{deck_name}"' if deck_name else "*"
    cards = anki.search_cards(query, limit=5000)

    # Build set of known words from card tags
    known_words: set[str] = set()
    for card in cards:
        for tag in card.tags:
            if tag.startswith("word::"):
                known_words.add(tag[6:].lower().strip())

        # Tier 2: extract from back HTML
        extracted = _extract_spanish_word_from_back(card.back)
        if extracted:
            known_words.add(extracted)

    # Match against CEFR levels
    progress: dict[str, LevelProgress] = {}
    for level in LEVELS:
        words = cefr_data.get_words_for_level(level)
        if not words:
            continue

        lp = LevelProgress(level=level, words_total=len(words))
        by_cat: dict[str, CategoryProgress] = {}

        for w in words:
            cat_key = w.category
            if cat_key not in by_cat:
                by_cat[cat_key] = CategoryProgress(category=cat_key)
            by_cat[cat_key].total += 1

            if w.word.lower() in known_words:
                lp.words_known += 1
                lp.matched_words.append(w.word)
                by_cat[cat_key].known += 1
            else:
                lp.unknown_words.append(w.word)

        lp.categories = by_cat
        progress[level] = lp

    return progress


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

def save_progress_cache(progress: dict[str, LevelProgress]) -> None:
    """Save progress to cache file."""
    ensure_data_dir()
    data = {}
    for level, lp in progress.items():
        data[level] = {
            "words_known": lp.words_known,
            "words_total": lp.words_total,
            "matched_words": lp.matched_words,
            "categories": {
                k: {"known": v.known, "total": v.total}
                for k, v in lp.categories.items()
            },
        }
    CEFR_CACHE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_progress_cache() -> dict[str, LevelProgress] | None:
    """Load progress from cache. Returns None if no cache exists."""
    if not CEFR_CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CEFR_CACHE_FILE.read_text(encoding="utf-8"))
        progress = {}
        for level, lp_data in data.items():
            lp = LevelProgress(
                level=level,
                words_known=lp_data["words_known"],
                words_total=lp_data["words_total"],
                matched_words=lp_data.get("matched_words", []),
            )
            for cat_key, cat_data in lp_data.get("categories", {}).items():
                lp.categories[cat_key] = CategoryProgress(
                    category=cat_key,
                    known=cat_data["known"],
                    total=cat_data["total"],
                )
            progress[level] = lp
        return progress
    except (json.JSONDecodeError, KeyError):
        return None


def invalidate_cache() -> None:
    """Remove the progress cache."""
    if CEFR_CACHE_FILE.exists():
        CEFR_CACHE_FILE.unlink()


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------

# Cognate type sort priority: transparent first, then semi, false_friend, then none/unknown
_COGNATE_SORT_ORDER = {
    "transparent": 0,
    "semi_transparent": 1,
    "false_friend": 2,
}


def _cognate_sort_key(word: CEFRWord) -> int:
    """Return sort key for cognate-first ordering. Lower = show first."""
    return _COGNATE_SORT_ORDER.get(word.cognate_type or "", 3)


def get_suggestions(
    cefr_data: CEFRData,
    progress: dict[str, LevelProgress],
    level: str | None = None,
    count: int = 10,
    cognate_first: bool = True,
) -> list[CEFRWord]:
    """Get suggested words to learn next based on gaps.

    Prioritizes the lowest incomplete level, then categories with worst coverage.
    When cognate_first=True (C5), sorts suggestions by cognate_type:
    transparent first, then semi_transparent, then false_friend, then none.
    """
    cefr_data.load()

    # Pick level: use supplied or find lowest incomplete
    target_level = level
    if not target_level:
        for lv in LEVELS:
            lp = progress.get(lv)
            if lp and lp.percent < 90:
                target_level = lv
                break
        if not target_level:
            target_level = "A1"

    lp = progress.get(target_level.upper())
    if not lp:
        # No progress data, just return first N words
        words = cefr_data.get_words_for_level(target_level)
        if cognate_first:
            words = sorted(words, key=_cognate_sort_key)
        return words[:count]

    # Sort categories by worst coverage
    sorted_cats = sorted(
        lp.categories.values(),
        key=lambda c: c.percent,
    )

    known_set = set(w.lower() for w in lp.matched_words)
    suggestions: list[CEFRWord] = []

    # Pick unknown words from worst categories first
    for cat in sorted_cats:
        if len(suggestions) >= count:
            break
        cat_words = [
            w for w in cefr_data.get_words_for_level(target_level)
            if w.category == cat.category and w.word.lower() not in known_set
        ]
        suggestions.extend(cat_words[:count - len(suggestions)])

    # C5: Sort by cognate type (transparent first) when cognate data is available
    if cognate_first:
        suggestions = sorted(suggestions, key=_cognate_sort_key)

    return suggestions[:count]


# ---------------------------------------------------------------------------
# Difficulty scoring (C7)
# ---------------------------------------------------------------------------

# Cognate type to base difficulty mapping:
#   1 = transparent cognate in 2+ languages
#   2 = cognate in 1 language or morphological derivative
#   3 = semi-transparent cognate or partial cognate
#   4 = no cognate but concrete meaning
#   5 = abstract non-cognate or false friend
_COGNATE_DIFFICULTY: dict[str, int] = {
    "transparent_multi": 1,
    "transparent": 2,
    "cognate_multi": 1,
    "cognate": 2,
    "semi_transparent": 3,
    "partial_cognate": 3,
    "false_friend": 5,
    "none": 4,
}

# Abstract categories bump difficulty up by 1 (capped at 5)
_ABSTRACT_CATEGORIES = frozenset({
    "perception_emotions",
    "abstract_concepts",
    "politics",
    "philosophy",
    "opinions",
    "mental_processes",
})


def score_word_difficulty(
    cognate_type: str | None = None,
    category: str = "",
    is_morphological_derivative: bool = False,
) -> int:
    """Score word difficulty from 1 (easiest) to 5 (hardest).

    Args:
        cognate_type: Value of the cognate_type field from CEFR data.
            One of: transparent_multi, transparent, cognate_multi, cognate,
            semi_transparent, partial_cognate, false_friend, none.
        category: The thematic category of the word.
        is_morphological_derivative: True if the word can be derived from
            a known root (e.g. "librería" from "libro").
    """
    if not cognate_type:
        base = 4  # Default: no cognate info means assume harder
    else:
        base = _COGNATE_DIFFICULTY.get(cognate_type.lower().strip(), 4)

    # Morphological derivatives are easier
    if is_morphological_derivative and base > 1:
        base = min(base, 2)

    # Abstract categories are harder
    if category.lower() in _ABSTRACT_CATEGORIES and base < 5:
        base += 1

    return max(1, min(5, base))


def get_difficulty_distribution(anki, deck_name: str | None = None) -> dict[int, int]:
    """Get current difficulty distribution from Anki tags.

    Returns a dict {difficulty_level: count} for levels 1-5.
    Reads difficulty::N tags from cards.
    """
    query = f'deck:"{deck_name}"' if deck_name else "*"
    cards = anki.search_cards(query, limit=10000)

    distribution: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for card in cards:
        for tag in card.tags:
            if tag.startswith("difficulty::"):
                try:
                    level = int(tag.split("::")[1])
                    if 1 <= level <= 5:
                        distribution[level] += 1
                except (ValueError, IndexError):
                    pass
    return distribution


# ---------------------------------------------------------------------------
# Auto-tagging helper
# ---------------------------------------------------------------------------

def get_cefr_tags_for_word(cefr_data: CEFRData, word: str) -> list[str]:
    """Return CEFR tags for a word, e.g. ['cefr::a1', 'theme::personal_identity'].

    Returns empty list if word not found in CEFR data.
    """
    result = cefr_data.lookup_word(word)
    if not result:
        return []
    level, cefr_word = result
    tags = [f"cefr::{level.lower()}"]
    if cefr_word.category:
        tags.append(f"theme::{cefr_word.category}")
    return tags


# ---------------------------------------------------------------------------
# Text formatting for tool results
# ---------------------------------------------------------------------------

def format_progress_text(
    progress: dict[str, LevelProgress],
    level: str | None = None,
    category: str | None = None,
    show_unknown: bool = False,
) -> str:
    """Format progress as plain text for tool responses."""
    lines = []

    levels_to_show = [level.upper()] if level else [lv for lv in LEVELS if lv in progress]

    for lv in levels_to_show:
        lp = progress.get(lv)
        if not lp:
            lines.append(f"{lv}: No data available")
            continue

        lines.append(f"{lv}: {lp.words_known}/{lp.words_total} words ({lp.percent:.0f}%)")

        if category:
            cat = lp.categories.get(category)
            if cat:
                lines.append(f"  {category}: {cat.known}/{cat.total} ({cat.percent:.0f}%)")
            else:
                lines.append(f"  Category '{category}' not found at {lv}")
        else:
            # Show top categories
            sorted_cats = sorted(lp.categories.values(), key=lambda c: c.percent)
            if sorted_cats:
                lines.append("  Categories (weakest first):")
                for cat in sorted_cats[:8]:
                    bar = _mini_bar(cat.percent)
                    lines.append(f"    {cat.category:<25} {cat.known:>3}/{cat.total:<3} {bar} {cat.percent:.0f}%")

        if show_unknown and lp.unknown_words:
            sample = lp.unknown_words[:20]
            lines.append(f"  Unknown words ({len(lp.unknown_words)} total): {', '.join(sample)}")
            if len(lp.unknown_words) > 20:
                lines.append(f"    ... and {len(lp.unknown_words) - 20} more")

        lines.append("")

    total_known = sum(lp.words_known for lp in progress.values())
    total_words = sum(lp.words_total for lp in progress.values())
    if total_words > 0:
        lines.append(f"Overall: {total_known}/{total_words} words ({total_known/total_words*100:.0f}%)")

    return "\n".join(lines)


def format_suggestions_text(suggestions: list[CEFRWord]) -> str:
    """Format suggestions as plain text."""
    if not suggestions:
        return "No suggestions available."
    lines = [f"Suggested words to learn ({len(suggestions)}):"]
    for w in suggestions:
        cognate_label = ""
        if w.cognate_type:
            labels = {
                "transparent": " [cognate - easy!]",
                "semi_transparent": " [semi-cognate]",
                "false_friend": " [FALSE FRIEND!]",
            }
            cognate_label = labels.get(w.cognate_type, "")
        lines.append(f"  {w.word} - {w.english}  [{w.category}] ({w.level}){cognate_label}")
    return "\n".join(lines)


def _mini_bar(percent: float, width: int = 10) -> str:
    filled = int(width * percent / 100)
    empty = width - filled
    return "\u2588" * filled + "\u2591" * empty
