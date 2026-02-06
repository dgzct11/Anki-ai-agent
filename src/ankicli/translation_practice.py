"""Translation practice mode with Anki review integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
class PracticeResult:
    """Result of evaluating a single practice question."""

    card_id: str
    front: str
    back: str
    user_answer: str
    feedback_level: FeedbackLevel
    feedback_text: str
    meaning_score: int = 0       # 0-4
    grammar_score: int = 0       # 0-4
    naturalness_score: int = 0   # 0-4
    vocabulary_score: int = 0    # 0-4
    is_due_for_review: bool = False
    marked_reviewed: bool = False

    @property
    def total_score(self) -> int:
        return self.meaning_score + self.grammar_score + self.naturalness_score + self.vocabulary_score

    @property
    def max_score(self) -> int:
        return 16

    @property
    def score_percent(self) -> float:
        return (self.total_score / self.max_score) * 100 if self.max_score > 0 else 0


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
class PracticeSession:
    """Tracks state for an active practice session."""

    deck_name: str
    direction: PracticeDirection
    cards: list[PracticeCard] = field(default_factory=list)
    results: list[PracticeResult] = field(default_factory=list)
    current_index: int = 0
    correct_streak: int = 0
    incorrect_streak: int = 0
    difficulty_num: int = 2  # A2: 1-5 scale, start at 2 (simple sentence)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def total_questions(self) -> int:
        return len(self.cards)

    @property
    def questions_answered(self) -> int:
        return len(self.results)

    @property
    def questions_remaining(self) -> int:
        return self.total_questions - self.current_index

    @property
    def current_card(self) -> PracticeCard | None:
        if self.current_index < len(self.cards):
            return self.cards[self.current_index]
        return None

    @property
    def is_finished(self) -> bool:
        return self.current_index >= len(self.cards)

    @property
    def correct_count(self) -> int:
        return sum(1 for r in self.results if r.feedback_level == FeedbackLevel.CORRECT)

    @property
    def partial_count(self) -> int:
        return sum(1 for r in self.results if r.feedback_level == FeedbackLevel.PARTIAL)

    @property
    def incorrect_count(self) -> int:
        return sum(1 for r in self.results if r.feedback_level == FeedbackLevel.INCORRECT)

    @property
    def total_score(self) -> int:
        return sum(r.total_score for r in self.results)

    @property
    def max_possible_score(self) -> int:
        return len(self.results) * 16

    @property
    def score_percent(self) -> float:
        return (self.total_score / self.max_possible_score) * 100 if self.max_possible_score > 0 else 0

    # A2: Difficulty level labels
    DIFFICULTY_LABELS = {
        1: "single word",
        2: "simple sentence",
        3: "tense targeting",
        4: "complex sentence",
        5: "conversational context",
    }

    @property
    def difficulty_level(self) -> str:
        """Adaptive difficulty based on streak."""
        if self.correct_streak >= 3:
            return "harder"
        elif self.incorrect_streak >= 2:
            return "easier"
        return "normal"

    @property
    def difficulty_label(self) -> str:
        """Human-readable label for current difficulty level."""
        return self.DIFFICULTY_LABELS.get(self.difficulty_num, "normal")

    def record_result(self, result: PracticeResult, defer_difficulty: bool = False) -> None:
        """Record a practice result and update streaks + adaptive difficulty.

        Args:
            result: The practice result to record.
            defer_difficulty: If True, record the result and advance the index
                but don't update streaks or difficulty. Use this for grouped
                cards where difficulty should only change after the entire group.
        """
        self.results.append(result)
        self.current_index += 1
        if defer_difficulty:
            return
        self._update_difficulty(result.feedback_level)

    def _update_difficulty(self, feedback_level: FeedbackLevel) -> None:
        """Update streaks and adaptive difficulty based on feedback level."""
        if feedback_level == FeedbackLevel.CORRECT:
            self.correct_streak += 1
            self.incorrect_streak = 0
            # A2: Increase difficulty after 3+ correct
            if self.correct_streak >= 3 and self.difficulty_num < 5:
                self.difficulty_num += 1
                self.correct_streak = 0  # Reset streak after level change
        elif feedback_level == FeedbackLevel.INCORRECT:
            self.incorrect_streak += 1
            self.correct_streak = 0
            # A2: Decrease difficulty after 2+ wrong
            if self.incorrect_streak >= 2 and self.difficulty_num > 1:
                self.difficulty_num -= 1
                self.incorrect_streak = 0  # Reset streak after level change
        else:
            # Partial - reset both streaks
            self.correct_streak = 0
            self.incorrect_streak = 0

    def get_weak_words(self) -> list[str]:
        """Return words the user got wrong or partially wrong."""
        weak = []
        for r in self.results:
            if r.feedback_level in (FeedbackLevel.INCORRECT, FeedbackLevel.PARTIAL):
                weak.append(r.front)
        return weak

    def get_summary_dict(self) -> dict:
        """Return a summary dict for logging/display."""
        return {
            "deck_name": self.deck_name,
            "direction": self.direction.value,
            "total_questions": self.questions_answered,
            "correct": self.correct_count,
            "partial": self.partial_count,
            "incorrect": self.incorrect_count,
            "score_percent": round(self.score_percent, 1),
            "weak_words": self.get_weak_words(),
            "cards_marked_reviewed": sum(1 for r in self.results if r.marked_reviewed),
            "started_at": self.started_at,
            "finished_at": datetime.now().isoformat(),
        }


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
        remaining = count - len(cards)
        if remaining > 0:
            new_cards = anki.get_new_cards(deck_name, limit=remaining)
            for c in new_cards:
                # Skip duplicates
                existing_ids = {pc.card_id for pc in cards}
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


# Ease ratings for AnkiConnect answerCards
EASE_AGAIN = 1  # Wrong
EASE_HARD = 2
EASE_GOOD = 3
EASE_EASY = 4


def feedback_to_ease(level: FeedbackLevel) -> int:
    """Convert a feedback level to an Anki ease rating."""
    if level == FeedbackLevel.CORRECT:
        return EASE_GOOD
    elif level == FeedbackLevel.PARTIAL:
        return EASE_HARD
    return EASE_AGAIN
