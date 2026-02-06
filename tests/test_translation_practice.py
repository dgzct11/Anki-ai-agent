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
        # After 3 correct, adaptive difficulty triggers: difficulty_num increases
        # and correct_streak resets to 0
        assert session.correct_streak == 0
        assert session.difficulty_num == 3  # went from 2 to 3

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
        # After 3 correct, adaptive difficulty increases difficulty_num from 2->3
        # and resets correct_streak to 0, so difficulty_level returns "normal"
        assert session.difficulty_level == "normal"
        assert session.difficulty_num == 3  # difficulty actually went up

    def test_difficulty_level_easier(self):
        session = self._make_session(num_cards=5)
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        # After 2 incorrect, adaptive difficulty decreases difficulty_num from 2->1
        # and resets incorrect_streak to 0, so difficulty_level returns "normal"
        assert session.difficulty_level == "normal"
        assert session.difficulty_num == 1  # difficulty actually went down

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

    def test_defer_difficulty_no_change_mid_group(self):
        """Fix #41: defer_difficulty=True should not update streaks/difficulty."""
        session = self._make_session(num_cards=5)
        # Record 3 correct results with defer_difficulty=True (simulating a group)
        for _ in range(3):
            session.record_result(self._make_result(FeedbackLevel.CORRECT), defer_difficulty=True)
        # Streaks should not have changed, difficulty should remain at 2
        assert session.correct_streak == 0
        assert session.difficulty_num == 2
        assert session.current_index == 3  # index still advances

    def test_defer_difficulty_last_card_updates(self):
        """Fix #41: Last card in group should update difficulty."""
        session = self._make_session(num_cards=5)
        # Simulate a group of 3 cards: defer first 2, update on last
        session.record_result(self._make_result(FeedbackLevel.CORRECT), defer_difficulty=True)
        session.record_result(self._make_result(FeedbackLevel.CORRECT), defer_difficulty=True)
        session.record_result(self._make_result(FeedbackLevel.CORRECT), defer_difficulty=False)
        # Only the last record_result triggers a difficulty update
        assert session.correct_streak == 1  # only one non-deferred correct
        assert session.difficulty_num == 2  # not enough non-deferred to trigger change


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

    def test_load_mixed_due_first_ordering(self):
        """Fix #44: Mixed source should have due cards before new cards."""
        anki = MagicMock()
        anki.get_due_cards.return_value = [
            self._make_anki_card("5", "cat", "gato"),
        ]
        anki.get_new_cards.return_value = [
            self._make_anki_card("1", "dog", "perro"),
            self._make_anki_card("3", "fish", "pez"),
        ]
        cards = load_practice_cards(anki, "Spanish", CardSource.MIXED, count=5)
        assert len(cards) == 3
        # Due card should come first
        assert cards[0].is_due is True
        assert cards[0].card_id == "5"

    def test_load_due_cards_sorted_first(self):
        """Fix #44: Due cards should be sorted before non-due cards."""
        anki = MagicMock()
        anki.get_deck_cards.return_value = [
            self._make_anki_card("1", "hello", "hola"),
            self._make_anki_card("2", "goodbye", "adios"),
            self._make_anki_card("3", "please", "por favor"),
        ]
        # Only card "2" is due
        anki.get_due_cards.return_value = [
            self._make_anki_card("2", "goodbye", "adios"),
        ]
        cards = load_practice_cards(anki, "Spanish", CardSource.ALL, count=5)
        assert len(cards) == 3
        # Due card should come first
        assert cards[0].card_id == "2"
        assert cards[0].is_due is True


class TestScoreRegexPatterns:
    """Fix #33: Tests for flexible score regex parsing in chat.py."""

    def _extract_scores(self, response_text):
        """Mirror the score extraction logic from chat.py run_practice_loop."""
        import re
        meaning = grammar = naturalness = vocabulary = 2

        score_patterns = [
            (r'\*{0,2}[Mm]eaning\*{0,2}\s*[:\-\u2014]\s*(\d)(?:/4)?', 'meaning'),
            (r'\*{0,2}[Mm]eaning\*{0,2}\s*\((\d)(?:/4)?\)', 'meaning'),
            (r'\*{0,2}[Gg]rammar\*{0,2}\s*[:\-\u2014]\s*(\d)(?:/4)?', 'grammar'),
            (r'\*{0,2}[Gg]rammar\*{0,2}\s*\((\d)(?:/4)?\)', 'grammar'),
            (r'\*{0,2}[Nn]aturalness\*{0,2}\s*[:\-\u2014]\s*(\d)(?:/4)?', 'naturalness'),
            (r'\*{0,2}[Nn]aturalness\*{0,2}\s*\((\d)(?:/4)?\)', 'naturalness'),
            (r'\*{0,2}[Vv]ocabulary\*{0,2}\s*[:\-\u2014]\s*(\d)(?:/4)?', 'vocabulary'),
            (r'\*{0,2}[Vv]ocabulary\*{0,2}\s*\((\d)(?:/4)?\)', 'vocabulary'),
        ]
        for pattern, key in score_patterns:
            match = re.search(pattern, response_text)
            if match:
                val = max(0, min(4, int(match.group(1))))
                if key == 'meaning':
                    meaning = val
                elif key == 'grammar':
                    grammar = val
                elif key == 'naturalness':
                    naturalness = val
                elif key == 'vocabulary':
                    vocabulary = val

        return meaning, grammar, naturalness, vocabulary

    def test_standard_format(self):
        text = "Meaning: 4/4\nGrammar: 3/4\nNaturalness: 2/4\nVocabulary: 4/4"
        m, g, n, v = self._extract_scores(text)
        assert (m, g, n, v) == (4, 3, 2, 4)

    def test_bold_markdown_format(self):
        text = "**Meaning**: 4/4\n**Grammar**: 3/4\n**Naturalness**: 2/4\n**Vocabulary**: 4/4"
        m, g, n, v = self._extract_scores(text)
        assert (m, g, n, v) == (4, 3, 2, 4)

    def test_no_slash_four(self):
        text = "Meaning: 4\nGrammar: 3\nNaturalness: 2\nVocabulary: 1"
        m, g, n, v = self._extract_scores(text)
        assert (m, g, n, v) == (4, 3, 2, 1)

    def test_parentheses_format(self):
        text = "Meaning (4/4)\nGrammar (3/4)\nNaturalness (2/4)\nVocabulary (4/4)"
        m, g, n, v = self._extract_scores(text)
        assert (m, g, n, v) == (4, 3, 2, 4)

    def test_parentheses_no_slash(self):
        text = "Meaning (3)\nGrammar (2)\nNaturalness (4)\nVocabulary (1)"
        m, g, n, v = self._extract_scores(text)
        assert (m, g, n, v) == (3, 2, 4, 1)

    def test_em_dash_format(self):
        text = "Meaning \u2014 4/4\nGrammar \u2014 3/4\nNaturalness \u2014 2/4\nVocabulary \u2014 4/4"
        m, g, n, v = self._extract_scores(text)
        assert (m, g, n, v) == (4, 3, 2, 4)

    def test_clamp_high_score(self):
        """Fix #43: Scores above 4 should be clamped to 4."""
        text = "Meaning: 9/4\nGrammar: 5/4\nNaturalness: 7/4\nVocabulary: 6/4"
        m, g, n, v = self._extract_scores(text)
        assert (m, g, n, v) == (4, 4, 4, 4)

    def test_defaults_when_no_match(self):
        text = "Good job! Your translation was accurate."
        m, g, n, v = self._extract_scores(text)
        assert (m, g, n, v) == (2, 2, 2, 2)

    def test_mixed_formats(self):
        text = "**Meaning**: 4/4\nGrammar: 3\nNaturalness (2/4)\n**Vocabulary** - 4/4"
        m, g, n, v = self._extract_scores(text)
        assert m == 4
        assert g == 3
        assert n == 2
        assert v == 4


class TestSentenceValidation:
    """Fix #37: Tests for generated sentence validation."""

    def _validate_sentence(self, raw):
        """Mirror the sentence validation logic from chat.py."""
        import re
        sentence = raw.strip().strip('"').strip("'")
        if sentence:
            sentence = re.sub(
                r'^(?:(?:Here(?:\'s| is) (?:a |the )?(?:sentence|translation|example)[:\.]?\s*)|(?:Sure[,!:]?\s*)|(?:Of course[,!:]?\s*))',
                '', sentence, flags=re.IGNORECASE
            ).strip()
            sent_match = re.match(r'^(.+?[.!?])(?:\s|$)', sentence)
            if sent_match:
                sentence = sent_match.group(1).strip()
            sentence = sentence.split('\n')[0].strip()
            sentence = sentence.strip('"').strip("'")
        return sentence

    def test_clean_sentence_unchanged(self):
        assert self._validate_sentence("The cat is on the table.") == "The cat is on the table."

    def test_strips_prefix_heres(self):
        assert self._validate_sentence("Here's a sentence: The cat sleeps.") == "The cat sleeps."

    def test_strips_prefix_sure(self):
        assert self._validate_sentence("Sure! The dog runs fast.") == "The dog runs fast."

    def test_takes_first_sentence_only(self):
        result = self._validate_sentence("The cat sleeps. The dog runs. The bird flies.")
        assert result == "The cat sleeps."

    def test_strips_trailing_commentary(self):
        result = self._validate_sentence("The cat sleeps.\nThis uses the word 'gato'.")
        assert result == "The cat sleeps."

    def test_strips_quotes(self):
        assert self._validate_sentence('"The cat sleeps."') == "The cat sleeps."

    def test_empty_string(self):
        assert self._validate_sentence("") == ""

    def test_question_mark_sentence(self):
        assert self._validate_sentence("Do you like cats?") == "Do you like cats?"

    def test_exclamation_sentence(self):
        assert self._validate_sentence("What a beautiful day!") == "What a beautiful day!"
