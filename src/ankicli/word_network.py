"""Vocabulary network graph for tracking word relationships.

Stores connections between words (antonyms, morphological family, collocations,
thematic groups, synonyms, confusables) and disambiguation tracking.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal

from .paths import WORD_NETWORK_FILE, DISAMBIGUATION_FILE, ensure_data_dir

ConnectionType = Literal[
    "antonym", "morphological", "collocation", "thematic", "synonym", "confusable"
]


@dataclass
class WordConnection:
    connection_type: ConnectionType
    target_word: str
    strength: float = 1.0


@dataclass
class WordNode:
    word: str
    level: str
    pos: str
    theme: str
    family_root: str | None = None
    in_deck: bool = False
    note_id: int | None = None
    connections: list[WordConnection] = field(default_factory=list)
    collocations: list[dict] = field(default_factory=list)
    disambiguation_group: str | None = None


@dataclass
class DisambiguationPair:
    pair_id: str  # e.g. "ser-estar"
    words: list[str] = field(default_factory=list)
    category: str = ""
    error_counts: dict[str, int] = field(default_factory=dict)
    practice_count: int = 0
    last_practiced: str = ""


class WordNetwork:
    """In-memory vocabulary network backed by JSON storage."""

    def __init__(self) -> None:
        self._nodes: dict[str, WordNode] = {}
        self._disambiguation: dict[str, DisambiguationPair] = {}

    # -- Persistence --

    def load(self) -> None:
        """Load word network and disambiguation data from disk."""
        if WORD_NETWORK_FILE.exists():
            try:
                raw = json.loads(WORD_NETWORK_FILE.read_text(encoding="utf-8"))
                for key, entry in raw.items():
                    connections = [
                        WordConnection(**c) for c in entry.get("connections", [])
                    ]
                    node = WordNode(
                        word=entry["word"],
                        level=entry["level"],
                        pos=entry["pos"],
                        theme=entry["theme"],
                        family_root=entry.get("family_root"),
                        in_deck=entry.get("in_deck", False),
                        note_id=entry.get("note_id"),
                        connections=connections,
                        collocations=entry.get("collocations", []),
                        disambiguation_group=entry.get("disambiguation_group"),
                    )
                    self._nodes[key] = node
            except (json.JSONDecodeError, KeyError):
                self._nodes = {}

        if DISAMBIGUATION_FILE.exists():
            try:
                raw = json.loads(DISAMBIGUATION_FILE.read_text(encoding="utf-8"))
                for key, entry in raw.items():
                    self._disambiguation[key] = DisambiguationPair(
                        pair_id=entry["pair_id"],
                        words=entry.get("words", []),
                        category=entry.get("category", ""),
                        error_counts=entry.get("error_counts", {}),
                    )
            except (json.JSONDecodeError, KeyError):
                self._disambiguation = {}

    def save(self) -> None:
        """Save word network and disambiguation data to disk."""
        ensure_data_dir()
        network_data = {}
        for key, node in self._nodes.items():
            network_data[key] = asdict(node)
        WORD_NETWORK_FILE.write_text(
            json.dumps(network_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        disambig_data = {}
        for key, pair in self._disambiguation.items():
            disambig_data[key] = asdict(pair)
        DISAMBIGUATION_FILE.write_text(
            json.dumps(disambig_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # -- Node operations --

    def add_word(self, node: WordNode) -> None:
        """Add or update a word node in the network."""
        self._nodes[node.word.lower()] = node

    def get_node(self, word: str) -> WordNode | None:
        """Look up a single word node."""
        return self._nodes.get(word.lower())

    def get_connections(self, word: str, connection_type: ConnectionType | None = None) -> list[WordConnection]:
        """Get connections for a word, optionally filtered by type."""
        node = self._nodes.get(word.lower())
        if not node:
            return []
        if connection_type is None:
            return list(node.connections)
        return [c for c in node.connections if c.connection_type == connection_type]

    def get_family(self, word: str) -> list[WordNode]:
        """Get all words sharing the same family_root."""
        node = self._nodes.get(word.lower())
        if not node or not node.family_root:
            return [node] if node else []
        root = node.family_root.lower()
        return [n for n in self._nodes.values() if n.family_root and n.family_root.lower() == root]

    def get_semantic_field(self, word: str) -> list[WordNode]:
        """Get all words in the same theme as the given word."""
        node = self._nodes.get(word.lower())
        if not node:
            return []
        return [n for n in self._nodes.values() if n.theme == node.theme]

    # -- Disambiguation --

    def add_disambiguation_pair(self, pair: DisambiguationPair) -> None:
        """Add or update a disambiguation pair."""
        self._disambiguation[pair.pair_id] = pair

    def get_disambiguation_pairs(self, word: str | None = None) -> list[DisambiguationPair]:
        """Get disambiguation pairs, optionally filtered to those containing a word."""
        if word is None:
            return list(self._disambiguation.values())
        word_lower = word.lower()
        return [
            p for p in self._disambiguation.values()
            if word_lower in [w.lower() for w in p.words]
        ]

    # -- Connection helpers --

    def add_connection(self, word1: str, word2: str,
                       connection_type: ConnectionType, strength: float = 1.0) -> None:
        """Add a bidirectional connection between two words.

        Creates minimal WordNode stubs if either word is missing.
        """
        w1 = word1.lower()
        w2 = word2.lower()
        if w1 not in self._nodes:
            self._nodes[w1] = WordNode(word=w1, level="", pos="", theme="")
        if w2 not in self._nodes:
            self._nodes[w2] = WordNode(word=w2, level="", pos="", theme="")

        # w1 -> w2
        if not any(c.target_word == w2 and c.connection_type == connection_type
                    for c in self._nodes[w1].connections):
            self._nodes[w1].connections.append(
                WordConnection(connection_type=connection_type,
                               target_word=w2, strength=strength))
        # w2 -> w1
        if not any(c.target_word == w1 and c.connection_type == connection_type
                    for c in self._nodes[w2].connections):
            self._nodes[w2].connections.append(
                WordConnection(connection_type=connection_type,
                               target_word=w1, strength=strength))

    def add_collocation(self, word: str, phrase: str,
                        translation: str = "", strength: float = 1.0) -> None:
        """Add a collocation for a word."""
        key = word.lower()
        if key not in self._nodes:
            self._nodes[key] = WordNode(word=key, level="", pos="", theme="")
        for c in self._nodes[key].collocations:
            if c.get("phrase") == phrase:
                return
        self._nodes[key].collocations.append({
            "phrase": phrase,
            "translation": translation,
            "strength": strength,
        })

    def record_disambiguation_error(self, pair_id: str, confused_word: str) -> None:
        """Record an error for a disambiguation pair."""
        pair = self._disambiguation.get(pair_id)
        if pair:
            pair.error_counts[confused_word] = pair.error_counts.get(confused_word, 0) + 1

    def record_disambiguation_practice(self, pair_id: str) -> None:
        """Record that a disambiguation pair was practiced."""
        pair = self._disambiguation.get(pair_id)
        if pair:
            pair.practice_count += 1
            pair.last_practiced = datetime.now().isoformat()

    def get_recently_connected(self, word: str, depth: int = 2) -> list[str]:
        """Get words within N connection hops from a word."""
        visited: set[str] = set()
        current = {word.lower()}

        for _ in range(depth):
            next_level: set[str] = set()
            for w in current:
                if w in visited:
                    continue
                visited.add(w)
                node = self._nodes.get(w)
                if node:
                    for conn in node.connections:
                        if conn.target_word not in visited:
                            next_level.add(conn.target_word)
            current = next_level

        visited.update(current)
        visited.discard(word.lower())
        return sorted(visited)

    def get_network_suggestions(self, recently_reviewed: list[str],
                                limit: int = 5) -> list[str]:
        """V11: Suggest words connected to recently-reviewed words.

        Words connected to recently reviewed words get higher priority.
        """
        scores: dict[str, float] = {}
        reviewed_set = {w.lower() for w in recently_reviewed}

        for reviewed_word in recently_reviewed:
            node = self._nodes.get(reviewed_word.lower())
            if not node:
                continue
            for conn in node.connections:
                target = conn.target_word
                if target in reviewed_set:
                    continue
                target_node = self._nodes.get(target)
                if target_node and target_node.in_deck:
                    scores[target] = scores.get(target, 0) + conn.strength

        suggestions = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in suggestions[:limit]]

    # -- Stats --

    @property
    def word_count(self) -> int:
        return len(self._nodes)

    @property
    def disambiguation_count(self) -> int:
        return len(self._disambiguation)


# ---------------------------------------------------------------------------
# Default disambiguation pairs (top confusable pairs)
# ---------------------------------------------------------------------------

DEFAULT_DISAMBIGUATION_PAIRS = [
    DisambiguationPair("ser-estar", ["ser", "estar"], "verb_confusion"),
    DisambiguationPair("saber-conocer", ["saber", "conocer"], "verb_confusion"),
    DisambiguationPair("por-para", ["por", "para"], "preposition_confusion"),
    DisambiguationPair("tomar-llevar-coger", ["tomar", "llevar", "coger"], "verb_confusion"),
    DisambiguationPair("preguntar-pedir", ["preguntar", "pedir"], "verb_confusion"),
    DisambiguationPair("jugar-tocar", ["jugar", "tocar"], "verb_confusion"),
    DisambiguationPair("ponerse-volverse-hacerse-convertirse",
                       ["ponerse", "volverse", "hacerse", "convertirse"], "verb_confusion"),
    DisambiguationPair("salir-irse-dejar", ["salir", "irse", "dejar"], "verb_confusion"),
    DisambiguationPair("volver-devolver", ["volver", "devolver"], "verb_confusion"),
    DisambiguationPair("tiempo-vez-hora", ["tiempo", "vez", "hora"], "noun_confusion"),
    DisambiguationPair("extranar-perder-faltar",
                       ["extranar", "perder", "faltar"], "verb_confusion"),
    DisambiguationPair("darse_cuenta-realizar",
                       ["darse cuenta", "realizar"], "verb_confusion"),
]


def ensure_default_disambiguation(network: WordNetwork) -> None:
    """Populate default disambiguation pairs if not already present."""
    for pair in DEFAULT_DISAMBIGUATION_PAIRS:
        if pair.pair_id not in network._disambiguation:
            network.add_disambiguation_pair(pair)


# ---------------------------------------------------------------------------
# Morphological patterns for Spanish (V3)
# ---------------------------------------------------------------------------

MORPHOLOGICAL_PATTERNS: list[dict] = [
    {"suffix": "cion", "base_suffix": "r", "pos_from": "verb", "pos_to": "noun",
     "description": "verb -> noun (-cion)"},
    {"suffix": "mente", "base_suffix": "", "pos_from": "adjective", "pos_to": "adverb",
     "description": "adjective -> adverb (-mente)"},
    {"suffix": "dor", "base_suffix": "r", "pos_from": "verb", "pos_to": "noun",
     "description": "verb -> agent noun (-dor)"},
    {"suffix": "dora", "base_suffix": "r", "pos_from": "verb", "pos_to": "noun",
     "description": "verb -> agent noun (-dora)"},
    {"suffix": "able", "base_suffix": "r", "pos_from": "verb", "pos_to": "adjective",
     "description": "verb -> adjective (-able)"},
    {"suffix": "ible", "base_suffix": "r", "pos_from": "verb", "pos_to": "adjective",
     "description": "verb -> adjective (-ible)"},
    {"prefix": "des", "pos_from": "adjective", "pos_to": "adjective",
     "description": "negation (des-)"},
    {"prefix": "in", "pos_from": "adjective", "pos_to": "adjective",
     "description": "negation (in-)"},
    {"prefix": "re", "pos_from": "verb", "pos_to": "verb",
     "description": "repetition (re-)"},
    {"suffix": "idad", "base_suffix": "o", "pos_from": "adjective", "pos_to": "noun",
     "description": "adjective -> noun (-idad)"},
    {"suffix": "oso", "base_suffix": "", "pos_from": "noun", "pos_to": "adjective",
     "description": "noun -> adjective (-oso)"},
    {"suffix": "ero", "base_suffix": "", "pos_from": "noun", "pos_to": "noun",
     "description": "noun -> profession (-ero)"},
    {"suffix": "eria", "base_suffix": "", "pos_from": "noun", "pos_to": "noun",
     "description": "noun -> place (-eria)"},
    {"suffix": "anza", "base_suffix": "r", "pos_from": "verb", "pos_to": "noun",
     "description": "verb -> noun (-anza)"},
    {"suffix": "miento", "base_suffix": "r", "pos_from": "verb", "pos_to": "noun",
     "description": "verb -> noun (-miento)"},
]


def get_morphological_family(word: str, network: WordNetwork | None = None) -> dict:
    """Find morphological relatives of a Spanish word.

    Checks suffix/prefix patterns to suggest family members.

    Returns:
        Dict with 'word', 'family', 'patterns_matched', 'network_family'.
    """
    word_lower = word.lower().strip()
    family: set[str] = set()
    patterns_matched: list[str] = []

    for pat in MORPHOLOGICAL_PATTERNS:
        if "suffix" in pat:
            suffix = pat["suffix"]
            base_suffix = pat.get("base_suffix", "")

            # Check if this word IS a derived form (has the suffix)
            if word_lower.endswith(suffix):
                base = word_lower[:-len(suffix)]
                if base_suffix:
                    base += base_suffix
                if len(base) >= 3:
                    family.add(base)
                    patterns_matched.append(pat["description"])

            # Check if we can derive a form FROM this word
            if base_suffix and word_lower.endswith(base_suffix):
                derived = word_lower[:-len(base_suffix)] + suffix
                if len(derived) >= 4:
                    family.add(derived)
                    patterns_matched.append(pat["description"])
            elif not base_suffix:
                derived = word_lower + suffix
                family.add(derived)
                patterns_matched.append(pat["description"])

        elif "prefix" in pat:
            prefix = pat["prefix"]
            if word_lower.startswith(prefix):
                base = word_lower[len(prefix):]
                if len(base) >= 3:
                    family.add(base)
                    patterns_matched.append(pat["description"])
            derived = prefix + word_lower
            family.add(derived)
            patterns_matched.append(pat["description"])

    family.discard(word_lower)

    network_family: list[str] = []
    if network:
        node = network.get_node(word_lower)
        if node:
            for conn in node.connections:
                if conn.connection_type == "morphological":
                    network_family.append(conn.target_word)
                    family.add(conn.target_word)

    return {
        "word": word_lower,
        "family": sorted(family),
        "patterns_matched": sorted(set(patterns_matched)),
        "network_family": network_family,
    }


# ---------------------------------------------------------------------------
# False friends (V6)
# ---------------------------------------------------------------------------

FALSE_FRIENDS: list[dict] = [
    {"spanish": "embarazada", "false_english": "embarrassed", "actual": "pregnant"},
    {"spanish": "realizar", "false_english": "realize", "actual": "to carry out, accomplish"},
    {"spanish": "constipado", "false_english": "constipated", "actual": "having a cold"},
    {"spanish": "actual", "false_english": "actual", "actual": "current, present"},
    {"spanish": "eventualmente", "false_english": "eventually", "actual": "possibly, by chance"},
    {"spanish": "exito", "false_english": "exit", "actual": "success"},
    {"spanish": "sensible", "false_english": "sensible", "actual": "sensitive"},
    {"spanish": "soportar", "false_english": "support", "actual": "to bear, endure"},
    {"spanish": "asistir", "false_english": "assist", "actual": "to attend"},
    {"spanish": "carpeta", "false_english": "carpet", "actual": "folder"},
    {"spanish": "contestar", "false_english": "contest", "actual": "to answer"},
    {"spanish": "decepcionar", "false_english": "deceive", "actual": "to disappoint"},
    {"spanish": "introducir", "false_english": "introduce (person)", "actual": "to insert, put in"},
    {"spanish": "largo", "false_english": "large", "actual": "long"},
    {"spanish": "libreria", "false_english": "library", "actual": "bookstore"},
    {"spanish": "molestar", "false_english": "molest", "actual": "to bother, annoy"},
    {"spanish": "pretender", "false_english": "pretend", "actual": "to attempt, try for"},
    {"spanish": "recordar", "false_english": "record", "actual": "to remember"},
    {"spanish": "ropa", "false_english": "rope", "actual": "clothes"},
    {"spanish": "suceso", "false_english": "success", "actual": "event, incident"},
]


def check_false_friend(word: str) -> dict | None:
    """Check if a word is a known false friend. Returns the entry or None."""
    word_lower = word.lower().strip()
    for ff in FALSE_FRIENDS:
        if ff["spanish"].lower() == word_lower:
            return ff
    return None


# ---------------------------------------------------------------------------
# ASCII connection map (V10)
# ---------------------------------------------------------------------------

def build_connection_map(word: str, network: WordNetwork) -> str:
    """Build an ASCII connection map for a word and its network."""
    node = network.get_node(word)
    if not node:
        return f"'{word}' not found in the vocabulary network."

    center = word.lower()
    lines = [
        f"  Connection Map: {center.upper()}",
        f"  {'=' * (18 + len(center))}",
        "",
        f"       [{center}]",
    ]

    by_type: dict[str, list[WordConnection]] = {}
    for conn in node.connections:
        by_type.setdefault(conn.connection_type, []).append(conn)

    type_symbols = {
        "synonym": "~", "antonym": "<->", "morphological": "-->",
        "collocation": "+", "thematic": "#", "confusable": "!",
    }

    if not by_type and not node.collocations:
        lines.append("       (no connections yet)")
        return "\n".join(lines)

    lines.append(f"       {'|':^{len(center) + 2}}")

    for conn_type, connections in sorted(by_type.items()):
        symbol = type_symbols.get(conn_type, "-")
        lines.append(f"       +-- {conn_type} {symbol}")
        for i, conn in enumerate(connections):
            is_last = i == len(connections) - 1
            prefix = "       |   " if not is_last else "           "
            marker = "|-- " if not is_last else "\\-- "
            target_node = network.get_node(conn.target_word)
            deck_marker = "*" if target_node and target_node.in_deck else " "
            lines.append(f"{prefix}{marker}{conn.target_word} [{deck_marker}]")

    if node.collocations:
        lines.append(f"       +-- collocations +")
        for i, coll in enumerate(node.collocations):
            is_last = i == len(node.collocations) - 1
            prefix = "       |   " if not is_last else "           "
            marker = "|-- " if not is_last else "\\-- "
            phrase = coll.get("phrase", "")
            translation = coll.get("translation", "")
            extra = f" ({translation})" if translation else ""
            lines.append(f"{prefix}{marker}{phrase}{extra}")

    lines.append("")
    lines.append("  Legend: * = in Anki deck")
    return "\n".join(lines)
