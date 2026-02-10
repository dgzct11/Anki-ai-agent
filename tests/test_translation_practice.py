"""Tests for translation_practice module."""

from unittest.mock import MagicMock

from ankicli.translation_practice import (
    CardSource,
    FeedbackLevel,
    PracticeCard,
    PracticeDirection,
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
        """Score extraction regex patterns (formerly in chat.py practice loop)."""
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
