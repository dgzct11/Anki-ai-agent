"""Tests for difficulty scoring functions in cefr module."""

from unittest.mock import MagicMock

from ankicli.cefr import (
    get_difficulty_distribution,
    score_word_difficulty,
)


class TestScoreWordDifficulty:
    """Tests for score_word_difficulty function."""

    def test_transparent_multi_cognate(self):
        assert score_word_difficulty(cognate_type="transparent_multi") == 1

    def test_cognate_multi(self):
        assert score_word_difficulty(cognate_type="cognate_multi") == 1

    def test_transparent_single(self):
        assert score_word_difficulty(cognate_type="transparent") == 2

    def test_cognate_single(self):
        assert score_word_difficulty(cognate_type="cognate") == 2

    def test_semi_transparent(self):
        assert score_word_difficulty(cognate_type="semi_transparent") == 3

    def test_partial_cognate(self):
        assert score_word_difficulty(cognate_type="partial_cognate") == 3

    def test_no_cognate(self):
        assert score_word_difficulty(cognate_type="none") == 4

    def test_false_friend(self):
        assert score_word_difficulty(cognate_type="false_friend") == 5

    def test_none_cognate_type(self):
        # No cognate info defaults to 4
        assert score_word_difficulty(cognate_type=None) == 4

    def test_unknown_cognate_type(self):
        assert score_word_difficulty(cognate_type="unknown_value") == 4

    def test_morphological_derivative_lowers_difficulty(self):
        # Even if cognate_type is "none" (base=4), derivative caps at 2
        assert score_word_difficulty(
            cognate_type="none", is_morphological_derivative=True
        ) == 2

    def test_morphological_derivative_doesnt_lower_below_1(self):
        # transparent_multi is already 1; derivative shouldn't lower it further
        assert score_word_difficulty(
            cognate_type="transparent_multi", is_morphological_derivative=True
        ) == 1

    def test_abstract_category_increases_difficulty(self):
        # cognate is base 2, abstract bumps to 3
        assert score_word_difficulty(
            cognate_type="cognate", category="perception_emotions"
        ) == 3

    def test_abstract_category_caps_at_5(self):
        # false_friend is base 5, abstract shouldn't go above 5
        assert score_word_difficulty(
            cognate_type="false_friend", category="abstract_concepts"
        ) == 5

    def test_combined_derivative_and_abstract(self):
        # Derivative caps at 2, then abstract bumps to 3
        result = score_word_difficulty(
            cognate_type="none",
            category="perception_emotions",
            is_morphological_derivative=True,
        )
        assert result == 3

    def test_case_insensitive_cognate_type(self):
        assert score_word_difficulty(cognate_type="Transparent_Multi") == 1

    def test_whitespace_stripped(self):
        assert score_word_difficulty(cognate_type=" transparent ") == 2

    def test_concrete_non_cognate(self):
        # "none" cognate with non-abstract category stays at 4
        assert score_word_difficulty(cognate_type="none", category="animals") == 4

    def test_result_always_in_range(self):
        """Ensure all known cognate types produce results in 1-5."""
        types = [
            "transparent_multi", "transparent", "cognate_multi", "cognate",
            "semi_transparent", "partial_cognate", "false_friend", "none", None,
        ]
        categories = ["", "animals", "perception_emotions", "abstract_concepts"]
        for ct in types:
            for cat in categories:
                for deriv in [True, False]:
                    result = score_word_difficulty(
                        cognate_type=ct, category=cat,
                        is_morphological_derivative=deriv,
                    )
                    assert 1 <= result <= 5, f"Out of range for {ct}, {cat}, {deriv}: {result}"


class TestGetDifficultyDistribution:
    """Tests for get_difficulty_distribution function."""

    def test_empty_deck(self):
        anki = MagicMock()
        anki.search_cards.return_value = []
        dist = get_difficulty_distribution(anki)
        assert dist == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    def test_counts_difficulty_tags(self):
        anki = MagicMock()
        card1 = MagicMock()
        card1.tags = ["difficulty::1", "word::hola"]
        card2 = MagicMock()
        card2.tags = ["difficulty::3"]
        card3 = MagicMock()
        card3.tags = ["difficulty::1"]
        anki.search_cards.return_value = [card1, card2, card3]

        dist = get_difficulty_distribution(anki)
        assert dist == {1: 2, 2: 0, 3: 1, 4: 0, 5: 0}

    def test_ignores_invalid_difficulty_tags(self):
        anki = MagicMock()
        card = MagicMock()
        card.tags = ["difficulty::abc", "difficulty::0", "difficulty::6"]
        anki.search_cards.return_value = [card]

        dist = get_difficulty_distribution(anki)
        assert dist == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    def test_with_deck_name(self):
        anki = MagicMock()
        anki.search_cards.return_value = []
        get_difficulty_distribution(anki, deck_name="Spanish")
        anki.search_cards.assert_called_once_with('deck:"Spanish"', limit=10000)

    def test_without_deck_name(self):
        anki = MagicMock()
        anki.search_cards.return_value = []
        get_difficulty_distribution(anki)
        anki.search_cards.assert_called_once_with("*", limit=10000)

    def test_all_levels_present(self):
        anki = MagicMock()
        cards = []
        for level in range(1, 6):
            card = MagicMock()
            card.tags = [f"difficulty::{level}"]
            cards.append(card)
        anki.search_cards.return_value = cards

        dist = get_difficulty_distribution(anki)
        assert dist == {1: 1, 2: 1, 3: 1, 4: 1, 5: 1}
