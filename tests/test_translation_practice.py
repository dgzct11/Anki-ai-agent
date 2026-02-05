"""Tests for translation_practice module."""

from unittest.mock import MagicMock

from ankicli.translation_practice import (
    CardSource,
    FeedbackLevel,
    PracticeCard,
    PracticeDirection,
    PracticeResult,
    PracticeSession,
    EASE_AGAIN,
    EASE_GOOD,
    EASE_HARD,
    feedback_to_ease,
    load_practice_cards,
)


class TestEnums:
    """Tests for practice enums."""

    def test_practice_direction_values(self):
        assert PracticeDirection.EN_TO_ES == "en_to_es"
        assert PracticeDirection.ES_TO_EN == "es_to_en"

    def test_card_source_values(self):
        assert CardSource.DUE == "due"
        assert CardSource.NEW == "new"
        assert CardSource.MIXED == "mixed"
        assert CardSource.ALL == "all"

    def test_feedback_level_values(self):
        assert FeedbackLevel.CORRECT == "correct"
        assert FeedbackLevel.PARTIAL == "partial"
        assert FeedbackLevel.INCORRECT == "incorrect"


class TestPracticeResult:
    """Tests for PracticeResult dataclass."""

    def _make_result(self, **kwargs):
        defaults = {
            "card_id": "1",
            "front": "hello",
            "back": "hola",
            "user_answer": "hola",
            "feedback_level": FeedbackLevel.CORRECT,
            "feedback_text": "Great!",
        }
        defaults.update(kwargs)
        return PracticeResult(**defaults)

    def test_defaults(self):
        result = self._make_result()
        assert result.meaning_score == 0
        assert result.grammar_score == 0
        assert result.naturalness_score == 0
        assert result.vocabulary_score == 0
        assert result.is_due_for_review is False
        assert result.marked_reviewed is False

    def test_total_score(self):
        result = self._make_result(
            meaning_score=4, grammar_score=3,
            naturalness_score=2, vocabulary_score=1,
        )
        assert result.total_score == 10

    def test_max_score(self):
        result = self._make_result()
        assert result.max_score == 16

    def test_score_percent(self):
        result = self._make_result(
            meaning_score=4, grammar_score=4,
            naturalness_score=4, vocabulary_score=4,
        )
        assert result.score_percent == 100.0

    def test_score_percent_zero(self):
        result = self._make_result()
        assert result.score_percent == 0.0

    def test_score_percent_half(self):
        result = self._make_result(
            meaning_score=2, grammar_score=2,
            naturalness_score=2, vocabulary_score=2,
        )
        assert result.score_percent == 50.0


class TestPracticeCard:
    """Tests for PracticeCard dataclass."""

    def test_defaults(self):
        card = PracticeCard(card_id="1", front="hello", back="hola")
        assert card.tags == []
        assert card.is_due is False
        assert card.is_new is False

    def test_with_tags(self):
        card = PracticeCard(
            card_id="1", front="hello", back="hola",
            tags=["spanish", "a1"],
        )
        assert len(card.tags) == 2

    def test_due_card(self):
        card = PracticeCard(
            card_id="1", front="hello", back="hola", is_due=True,
        )
        assert card.is_due is True


class TestPracticeSession:
    """Tests for PracticeSession dataclass."""

    def _make_session(self, num_cards=3) -> PracticeSession:
        cards = [
            PracticeCard(card_id=str(i), front=f"front_{i}", back=f"back_{i}")
            for i in range(num_cards)
        ]
        return PracticeSession(
            deck_name="Spanish",
            direction=PracticeDirection.EN_TO_ES,
            cards=cards,
        )

    def _make_result(self, level=FeedbackLevel.CORRECT) -> PracticeResult:
        return PracticeResult(
            card_id="1", front="front", back="back",
            user_answer="answer",
            feedback_level=level,
            feedback_text="feedback",
            meaning_score=4 if level == FeedbackLevel.CORRECT else 1,
            grammar_score=4 if level == FeedbackLevel.CORRECT else 1,
            naturalness_score=4 if level == FeedbackLevel.CORRECT else 1,
            vocabulary_score=4 if level == FeedbackLevel.CORRECT else 1,
        )

    def test_initial_state(self):
        session = self._make_session()
        assert session.total_questions == 3
        assert session.questions_answered == 0
        assert session.questions_remaining == 3
        assert session.current_index == 0
        assert session.correct_streak == 0
        assert session.incorrect_streak == 0
        assert session.is_finished is False

    def test_current_card(self):
        session = self._make_session()
        assert session.current_card is not None
        assert session.current_card.card_id == "0"

    def test_current_card_none_when_finished(self):
        session = self._make_session(num_cards=0)
        assert session.current_card is None

    def test_record_correct_result(self):
        session = self._make_session()
        result = self._make_result(FeedbackLevel.CORRECT)
        session.record_result(result)
        assert session.questions_answered == 1
        assert session.current_index == 1
        assert session.correct_streak == 1
        assert session.incorrect_streak == 0

    def test_record_incorrect_result(self):
        session = self._make_session()
        result = self._make_result(FeedbackLevel.INCORRECT)
        session.record_result(result)
        assert session.incorrect_streak == 1
        assert session.correct_streak == 0

    def test_record_partial_resets_streaks(self):
        session = self._make_session()
        # Build up a streak first
        session.record_result(self._make_result(FeedbackLevel.CORRECT))
        assert session.correct_streak == 1
        # Partial resets both
        session.record_result(self._make_result(FeedbackLevel.PARTIAL))
        assert session.correct_streak == 0
        assert session.incorrect_streak == 0

    def test_correct_streak_increases(self):
        session = self._make_session(num_cards=5)
        for _ in range(3):
            session.record_result(self._make_result(FeedbackLevel.CORRECT))
        assert session.correct_streak == 3

    def test_incorrect_resets_correct_streak(self):
        session = self._make_session(num_cards=5)
        session.record_result(self._make_result(FeedbackLevel.CORRECT))
        session.record_result(self._make_result(FeedbackLevel.CORRECT))
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        assert session.correct_streak == 0
        assert session.incorrect_streak == 1

    def test_is_finished(self):
        session = self._make_session(num_cards=1)
        assert session.is_finished is False
        session.record_result(self._make_result())
        assert session.is_finished is True

    def test_correct_count(self):
        session = self._make_session(num_cards=3)
        session.record_result(self._make_result(FeedbackLevel.CORRECT))
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        session.record_result(self._make_result(FeedbackLevel.CORRECT))
        assert session.correct_count == 2
        assert session.incorrect_count == 1
        assert session.partial_count == 0

    def test_total_score(self):
        session = self._make_session(num_cards=2)
        session.record_result(self._make_result(FeedbackLevel.CORRECT))
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        # Correct: 4+4+4+4=16, Incorrect: 1+1+1+1=4
        assert session.total_score == 20
        assert session.max_possible_score == 32

    def test_score_percent_empty(self):
        session = self._make_session()
        assert session.score_percent == 0.0

    def test_difficulty_level_normal(self):
        session = self._make_session()
        assert session.difficulty_level == "normal"

    def test_difficulty_level_harder(self):
        session = self._make_session(num_cards=5)
        for _ in range(3):
            session.record_result(self._make_result(FeedbackLevel.CORRECT))
        assert session.difficulty_level == "harder"

    def test_difficulty_level_easier(self):
        session = self._make_session(num_cards=5)
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        assert session.difficulty_level == "easier"

    def test_get_weak_words(self):
        session = self._make_session(num_cards=3)
        r1 = PracticeResult(
            card_id="0", front="hello", back="hola",
            user_answer="hola", feedback_level=FeedbackLevel.CORRECT,
            feedback_text="good",
        )
        r2 = PracticeResult(
            card_id="1", front="goodbye", back="adios",
            user_answer="chao", feedback_level=FeedbackLevel.INCORRECT,
            feedback_text="wrong",
        )
        r3 = PracticeResult(
            card_id="2", front="please", back="por favor",
            user_answer="porfavor", feedback_level=FeedbackLevel.PARTIAL,
            feedback_text="close",
        )
        session.record_result(r1)
        session.record_result(r2)
        session.record_result(r3)
        weak = session.get_weak_words()
        assert "goodbye" in weak
        assert "please" in weak
        assert "hello" not in weak

    def test_get_summary_dict(self):
        session = self._make_session(num_cards=1)
        session.record_result(self._make_result(FeedbackLevel.CORRECT))
        summary = session.get_summary_dict()
        assert summary["deck_name"] == "Spanish"
        assert summary["direction"] == "en_to_es"
        assert summary["total_questions"] == 1
        assert summary["correct"] == 1
        assert summary["incorrect"] == 0
        assert summary["partial"] == 0
        assert "score_percent" in summary
        assert "started_at" in summary
        assert "finished_at" in summary

    def test_started_at_is_set(self):
        session = self._make_session()
        assert session.started_at is not None
        assert len(session.started_at) > 0


class TestFeedbackToEase:
    """Tests for feedback_to_ease function."""

    def test_correct_returns_good(self):
        assert feedback_to_ease(FeedbackLevel.CORRECT) == EASE_GOOD

    def test_partial_returns_hard(self):
        assert feedback_to_ease(FeedbackLevel.PARTIAL) == EASE_HARD

    def test_incorrect_returns_again(self):
        assert feedback_to_ease(FeedbackLevel.INCORRECT) == EASE_AGAIN

    def test_ease_values(self):
        assert EASE_AGAIN == 1
        assert EASE_HARD == 2
        assert EASE_GOOD == 3


class TestLoadPracticeCards:
    """Tests for load_practice_cards function."""

    def _make_anki_card(self, card_id, front, back, tags=None):
        card = MagicMock()
        card.id = card_id
        card.front = front
        card.back = back
        card.tags = tags or []
        return card

    def test_load_due_cards(self):
        anki = MagicMock()
        anki.get_due_cards.return_value = [
            self._make_anki_card("1", "hello", "hola"),
            self._make_anki_card("2", "goodbye", "adios"),
        ]
        cards = load_practice_cards(anki, "Spanish", CardSource.DUE, count=5)
        assert len(cards) == 2
        assert cards[0].is_due is True
        assert cards[0].card_id == "1"
        anki.get_due_cards.assert_called_once_with("Spanish", limit=5)

    def test_load_new_cards(self):
        anki = MagicMock()
        anki.get_new_cards.return_value = [
            self._make_anki_card("3", "please", "por favor"),
        ]
        cards = load_practice_cards(anki, "Spanish", CardSource.NEW, count=5)
        assert len(cards) == 1
        assert cards[0].is_new is True

    def test_load_mixed_cards(self):
        anki = MagicMock()
        anki.get_due_cards.return_value = [
            self._make_anki_card("1", "hello", "hola"),
        ]
        anki.get_new_cards.return_value = [
            self._make_anki_card("2", "goodbye", "adios"),
        ]
        cards = load_practice_cards(anki, "Spanish", CardSource.MIXED, count=5)
        assert len(cards) == 2
        assert cards[0].is_due is True
        assert cards[1].is_new is True

    def test_load_all_cards(self):
        anki = MagicMock()
        anki.get_deck_cards.return_value = [
            self._make_anki_card("1", "hello", "hola"),
            self._make_anki_card("2", "goodbye", "adios"),
        ]
        anki.get_due_cards.return_value = [
            self._make_anki_card("1", "hello", "hola"),
        ]
        cards = load_practice_cards(anki, "Spanish", CardSource.ALL, count=5)
        assert len(cards) == 2
        assert cards[0].is_due is True
        assert cards[1].is_due is False

    def test_load_respects_count_limit(self):
        anki = MagicMock()
        anki.get_due_cards.return_value = [
            self._make_anki_card(str(i), f"front_{i}", f"back_{i}")
            for i in range(10)
        ]
        cards = load_practice_cards(anki, "Spanish", CardSource.DUE, count=3)
        assert len(cards) == 3

    def test_mixed_avoids_duplicates(self):
        anki = MagicMock()
        anki.get_due_cards.return_value = [
            self._make_anki_card("1", "hello", "hola"),
        ]
        anki.get_new_cards.return_value = [
            self._make_anki_card("1", "hello", "hola"),  # Same card
            self._make_anki_card("2", "goodbye", "adios"),
        ]
        cards = load_practice_cards(anki, "Spanish", CardSource.MIXED, count=5)
        card_ids = [c.card_id for c in cards]
        assert len(card_ids) == len(set(card_ids)), "Duplicate cards found"

    def test_load_all_handles_due_error(self):
        anki = MagicMock()
        anki.get_deck_cards.return_value = [
            self._make_anki_card("1", "hello", "hola"),
        ]
        anki.get_due_cards.side_effect = Exception("connection error")
        cards = load_practice_cards(anki, "Spanish", CardSource.ALL, count=5)
        assert len(cards) == 1
        assert cards[0].is_due is False
