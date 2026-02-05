"""Data models for AnkiWeb CLI."""

from dataclasses import dataclass, field


@dataclass
class Deck:
    """Represents an Anki deck."""

    id: str
    name: str
    new_count: int = 0
    learn_count: int = 0
    review_count: int = 0

    @property
    def total_due(self) -> int:
        """Total cards due for review."""
        return self.new_count + self.learn_count + self.review_count


@dataclass
class Card:
    """Represents an Anki card."""

    id: str
    front: str
    back: str
    deck_id: str
    tags: list[str] = field(default_factory=list)


@dataclass
class NoteType:
    """Represents an Anki note type (model)."""

    id: str
    name: str
    fields: list[str] = field(default_factory=list)
