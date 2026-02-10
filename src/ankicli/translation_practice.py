"""Translation practice mode with Anki review integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import AnkiClient


class PracticeDirection(str, Enum):
    EN_TO_ES = "en_to_es"
    ES_TO_EN = "es_to_en"


class CardSource(str, Enum):
    DUE = "due"
    NEW = "new"
    MIXED = "mixed"
    ALL = "all"


class FeedbackLevel(str, Enum):
    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"


@dataclass
class PracticeCard:
    """A card queued for practice."""

    card_id: str
    front: str
    back: str
    tags: list[str] = field(default_factory=list)
    is_due: bool = False
    is_new: bool = False


@dataclass
class PracticeSessionState:
    """Lightweight session state shared across practice tool calls."""

    deck_name: str
    direction: PracticeDirection
    count: int = 10
    card_source: CardSource = CardSource.MIXED
    served_card_ids: set[str] = field(default_factory=set)

    def record_served(self, card_ids: list[str]) -> None:
        """Track which cards have been shown to avoid repeats."""
        self.served_card_ids.update(card_ids)


# Module-level session state — shared across tool handler calls within a conversation.
_active_session: PracticeSessionState | None = None


def start_session(
    deck_name: str,
    direction: PracticeDirection,
    count: int = 10,
    card_source: CardSource = CardSource.MIXED,
) -> PracticeSessionState:
    """Create and store a new practice session."""
    global _active_session
    _active_session = PracticeSessionState(
        deck_name=deck_name,
        direction=direction,
        count=count,
        card_source=card_source,
    )
    return _active_session


def get_session() -> PracticeSessionState | None:
    """Get the current active session, if any."""
    return _active_session


def clear_session() -> None:
    """Clear the active session."""
    global _active_session
    _active_session = None


def load_practice_cards(
    anki: AnkiClient,
    deck_name: str,
    source: CardSource,
    count: int = 10,
) -> list[PracticeCard]:
    """Load cards from Anki for a practice session.

    Args:
        anki: AnkiClient instance
        deck_name: Name of the deck to pull from
        source: Which cards to pull (due, new, mixed, all)
        count: Number of cards to load

    Returns:
        List of PracticeCard objects
    """
    cards: list[PracticeCard] = []

    if source in (CardSource.DUE, CardSource.MIXED):
        due_cards = anki.get_due_cards(deck_name, limit=count)
        for c in due_cards:
            cards.append(PracticeCard(
                card_id=c.id,
                front=c.front,
                back=c.back,
                tags=c.tags,
                is_due=True,
            ))

    if source in (CardSource.NEW, CardSource.MIXED):
        # For MIXED, always fetch some new cards (at least 1/3 of count) so
        # new cards aren't starved when there are many due cards.
        if source == CardSource.MIXED:
            new_limit = max(count // 3, 2)
        else:
            new_limit = count - len(cards)
        if new_limit > 0:
            new_cards = anki.get_new_cards(deck_name, limit=new_limit)
            existing_ids = {pc.card_id for pc in cards}
            for c in new_cards:
                if c.id not in existing_ids:
                    cards.append(PracticeCard(
                        card_id=c.id,
                        front=c.front,
                        back=c.back,
                        tags=c.tags,
                        is_new=True,
                    ))

    if source == CardSource.ALL:
        all_cards = anki.get_deck_cards(deck_name, limit=count)
        # Check which ones are due
        due_ids = set()
        try:
            due_results = anki.get_due_cards(deck_name, limit=500)
            due_ids = {c.id for c in due_results}
        except Exception:
            pass

        for c in all_cards[:count]:
            cards.append(PracticeCard(
                card_id=c.id,
                front=c.front,
                back=c.back,
                tags=c.tags,
                is_due=c.id in due_ids,
            ))

    # Fix #44: Sort due cards first so practice prioritizes them
    cards.sort(key=lambda c: (not c.is_due, c.card_id))
    return cards[:count]


