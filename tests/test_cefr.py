"""Tests for cefr module - CEFR data loading, card matching, and progress."""

from unittest.mock import MagicMock, patch

from ankicli.cefr import (
    CEFRData,
    CEFRGrammarConcept,
    CEFRWord,
    CategoryProgress,
    LEVELS,
    LevelProgress,
    _extract_spanish_word_from_back,
    _mini_bar,
    format_progress_text,
    format_suggestions_text,
    get_cefr_tags_for_word,
    get_suggestions,
    invalidate_cache,
    load_progress_cache,
    match_cards_to_cefr,
    save_progress_cache,
)


class TestLevels:
    """Tests for LEVELS constant."""

    def test_levels_tuple(self):
        assert LEVELS == ("A1", "A2", "B1", "B2", "C1", "C2")

    def test_levels_order(self):
        assert LEVELS[0] == "A1"
        assert LEVELS[-1] == "C2"


class TestCEFRWord:
    """Tests for CEFRWord dataclass."""

    def test_basic(self):
        w = CEFRWord(
            word="hola", english="hello", pos="interjection",
            gender=None, category="personal_identity",
            subcategory="greetings", tags=["basic"],
        )
        assert w.word == "hola"
        assert w.level == ""

    def test_with_level(self):
        w = CEFRWord(
            word="hola", english="hello", pos="interjection",
            gender=None, category="personal_identity",
            subcategory="greetings", tags=[], level="A1",
        )
        assert w.level == "A1"


class TestCEFRGrammarConcept:
    """Tests for CEFRGrammarConcept dataclass."""

    def test_basic(self):
        g = CEFRGrammarConcept(
            id="a1_present", concept="Present tense",
            category="verb_tenses", description="Regular present tense",
            key_verbs=["hablar"], common_errors=["wrong ending"],
            practice_patterns=["Yo ___"],
        )
        assert g.id == "a1_present"
        assert g.level == ""


class TestCategoryProgress:
    """Tests for CategoryProgress dataclass."""

    def test_percent_zero(self):
        cp = CategoryProgress(category="food", known=0, total=10)
        assert cp.percent == 0.0

    def test_percent_full(self):
        cp = CategoryProgress(category="food", known=10, total=10)
        assert cp.percent == 100.0

    def test_percent_partial(self):
        cp = CategoryProgress(category="food", known=5, total=10)
        assert cp.percent == 50.0

    def test_percent_empty(self):
        cp = CategoryProgress(category="food", known=0, total=0)
        assert cp.percent == 0.0


class TestLevelProgress:
    """Tests for LevelProgress dataclass."""

    def test_percent(self):
        lp = LevelProgress(level="A1", words_known=50, words_total=100)
        assert lp.percent == 50.0

    def test_percent_zero(self):
        lp = LevelProgress(level="A1", words_known=0, words_total=0)
        assert lp.percent == 0.0

    def test_defaults(self):
        lp = LevelProgress(level="A1")
        assert lp.matched_words == []
        assert lp.unknown_words == []
        assert lp.categories == {}


class TestCEFRData:
    """Tests for CEFRData class using real data files."""

    def test_load(self):
        data = CEFRData()
        data.load()
        assert data._loaded is True

    def test_load_is_idempotent(self):
        data = CEFRData()
        data.load()
        data.load()  # Should not raise
        assert data._loaded is True

    def test_get_words_for_level(self):
        data = CEFRData()
        words = data.get_words_for_level("A1")
        assert len(words) > 0
        assert isinstance(words[0], CEFRWord)
        assert words[0].level == "A1"

    def test_get_words_case_insensitive(self):
        data = CEFRData()
        words_upper = data.get_words_for_level("A1")
        words_lower = data.get_words_for_level("a1")
        assert len(words_upper) == len(words_lower)

    def test_get_words_nonexistent_level(self):
        data = CEFRData()
        words = data.get_words_for_level("Z9")
        assert words == []

    def test_get_grammar_for_level(self):
        data = CEFRData()
        grammar = data.get_grammar_for_level("A1")
        assert len(grammar) > 0
        assert isinstance(grammar[0], CEFRGrammarConcept)
        assert grammar[0].level == "A1"

    def test_get_all_words_up_to_level(self):
        data = CEFRData()
        a1_words = data.get_words_for_level("A1")
        a2_words = data.get_words_for_level("A2")
        up_to_a2 = data.get_all_words_up_to_level("A2")
        assert len(up_to_a2) == len(a1_words) + len(a2_words)

    def test_get_categories_for_level(self):
        data = CEFRData()
        cats = data.get_categories_for_level("A1")
        assert isinstance(cats, dict)
        assert len(cats) > 0
        for key, words in cats.items():
            assert isinstance(key, str)
            assert len(words) > 0

    def test_lookup_word_found(self):
        data = CEFRData()
        # "hola" should be in A1
        result = data.lookup_word("hola")
        assert result is not None
        level, word = result
        assert level == "A1"
        assert word.word == "hola"

    def test_lookup_word_case_insensitive(self):
        data = CEFRData()
        result = data.lookup_word("HOLA")
        assert result is not None

    def test_lookup_word_not_found(self):
        data = CEFRData()
        result = data.lookup_word("xyznonexistent")
        assert result is None

    def test_get_level_counts(self):
        data = CEFRData()
        counts = data.get_level_counts()
        assert isinstance(counts, dict)
        assert "A1" in counts
        assert counts["A1"] > 0


class TestExtractSpanishWord:
    """Tests for _extract_spanish_word_from_back."""

    def test_bold_tag(self):
        html = "<b>gato</b> - cat"
        assert _extract_spanish_word_from_back(html) == "gato"

    def test_bold_tag_with_article(self):
        html = "<b>el gato</b>"
        assert _extract_spanish_word_from_back(html) == "gato"

    def test_bold_tag_with_gender(self):
        html = "<b>gato (m.)</b>"
        assert _extract_spanish_word_from_back(html) == "gato"

    def test_no_bold_tag(self):
        html = "just plain text"
        assert _extract_spanish_word_from_back(html) is None

    def test_empty_bold(self):
        html = "<b></b>"
        assert _extract_spanish_word_from_back(html) is None

    def test_la_article(self):
        html = "<b>la casa</b>"
        assert _extract_spanish_word_from_back(html) == "casa"

    def test_los_article(self):
        html = "<b>los amigos</b>"
        assert _extract_spanish_word_from_back(html) == "amigos"


class TestMatchCardsToCefr:
    """Tests for match_cards_to_cefr using mocked Anki."""

    def test_matches_by_word_tag(self):
        anki = MagicMock()
        card = MagicMock()
        card.tags = ["word::hola"]
        card.back = ""
        anki.search_cards.return_value = [card]

        cefr_data = CEFRData()
        cefr_data.load()

        progress = match_cards_to_cefr(anki, cefr_data)
        a1_progress = progress.get("A1")
        assert a1_progress is not None
        assert a1_progress.words_known >= 1
        assert "hola" in a1_progress.matched_words

    def test_matches_by_html_back(self):
        anki = MagicMock()
        card = MagicMock()
        card.tags = []
        card.back = "<b>hola</b>"
        anki.search_cards.return_value = [card]

        cefr_data = CEFRData()
        cefr_data.load()

        progress = match_cards_to_cefr(anki, cefr_data)
        a1_progress = progress.get("A1")
        assert a1_progress is not None
        assert a1_progress.words_known >= 1

    def test_no_cards(self):
        anki = MagicMock()
        anki.search_cards.return_value = []

        cefr_data = CEFRData()
        cefr_data.load()

        progress = match_cards_to_cefr(anki, cefr_data)
        for level, lp in progress.items():
            assert lp.words_known == 0

    def test_with_deck_name(self):
        anki = MagicMock()
        anki.search_cards.return_value = []
        match_cards_to_cefr(anki, CEFRData(), deck_name="Spanish")
        anki.search_cards.assert_called_once_with('deck:"Spanish"', limit=5000)


class TestProgressCache:
    """Tests for save/load progress cache."""

    def _patch_cache(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        cache_file = data_dir / "cefr_cache.json"
        return (
            patch("ankicli.cefr.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
            patch("ankicli.cefr.CEFR_CACHE_FILE", cache_file),
        )

    def test_load_no_cache(self, tmp_path):
        p1, p2 = self._patch_cache(tmp_path)
        with p1, p2:
            result = load_progress_cache()
            assert result is None

    def test_save_and_load(self, tmp_path):
        p1, p2 = self._patch_cache(tmp_path)
        with p1, p2:
            progress = {
                "A1": LevelProgress(
                    level="A1", words_known=50, words_total=100,
                    matched_words=["hola", "adios"],
                    categories={
                        "personal_identity": CategoryProgress("personal_identity", known=10, total=20),
                    },
                ),
            }
            save_progress_cache(progress)
            loaded = load_progress_cache()
            assert loaded is not None
            assert loaded["A1"].words_known == 50
            assert loaded["A1"].words_total == 100
            assert "personal_identity" in loaded["A1"].categories

    def test_invalidate_cache(self, tmp_path):
        p1, p2 = self._patch_cache(tmp_path)
        with p1, p2:
            progress = {"A1": LevelProgress(level="A1", words_known=1, words_total=1)}
            save_progress_cache(progress)
            assert load_progress_cache() is not None
            invalidate_cache()
            assert load_progress_cache() is None

    def test_invalidate_no_cache(self, tmp_path):
        p1, p2 = self._patch_cache(tmp_path)
        with p1, p2:
            invalidate_cache()  # Should not raise


class TestGetSuggestions:
    """Tests for get_suggestions function."""

    def test_suggestions_from_lowest_level(self):
        cefr_data = CEFRData()
        cefr_data.load()

        # Simulate empty progress
        progress = {
            "A1": LevelProgress(
                level="A1", words_known=0, words_total=100,
                categories={
                    "personal_identity": CategoryProgress("personal_identity", known=0, total=20),
                },
            ),
        }
        suggestions = get_suggestions(cefr_data, progress, count=5)
        assert len(suggestions) == 5
        assert all(isinstance(s, CEFRWord) for s in suggestions)

    def test_suggestions_specific_level(self):
        cefr_data = CEFRData()
        cefr_data.load()

        progress = {}
        suggestions = get_suggestions(cefr_data, progress, level="A2", count=5)
        assert len(suggestions) == 5

    def test_suggestions_no_progress_data(self):
        cefr_data = CEFRData()
        cefr_data.load()

        suggestions = get_suggestions(cefr_data, {}, count=3)
        assert len(suggestions) == 3


class TestGetCefrTagsForWord:
    """Tests for get_cefr_tags_for_word function."""

    def test_known_word(self):
        cefr_data = CEFRData()
        tags = get_cefr_tags_for_word(cefr_data, "hola")
        assert len(tags) >= 1
        assert any(t.startswith("cefr::") for t in tags)

    def test_unknown_word(self):
        cefr_data = CEFRData()
        tags = get_cefr_tags_for_word(cefr_data, "xyznonexistent")
        assert tags == []


class TestFormatting:
    """Tests for text formatting functions."""

    def test_format_progress_text(self):
        progress = {
            "A1": LevelProgress(
                level="A1", words_known=50, words_total=100,
                categories={
                    "food": CategoryProgress("food", known=5, total=10),
                },
            ),
        }
        text = format_progress_text(progress)
        assert "A1" in text
        assert "50/100" in text
        assert "50%" in text

    def test_format_progress_single_level(self):
        progress = {
            "A1": LevelProgress(level="A1", words_known=50, words_total=100),
            "A2": LevelProgress(level="A2", words_known=10, words_total=200),
        }
        text = format_progress_text(progress, level="A1")
        assert "A1" in text
        assert "A2" not in text.split("Overall")[0]  # A2 shouldn't appear before Overall

    def test_format_progress_show_unknown(self):
        progress = {
            "A1": LevelProgress(
                level="A1", words_known=1, words_total=3,
                unknown_words=["gato", "perro"],
            ),
        }
        text = format_progress_text(progress, show_unknown=True)
        assert "gato" in text

    def test_format_suggestions_empty(self):
        text = format_suggestions_text([])
        assert "No suggestions" in text

    def test_format_suggestions(self):
        words = [
            CEFRWord(
                word="gato", english="cat", pos="noun",
                gender="m", category="animals", subcategory="pets",
                tags=[], level="A1",
            ),
        ]
        text = format_suggestions_text(words)
        assert "gato" in text
        assert "cat" in text

    def test_mini_bar(self):
        assert len(_mini_bar(50, width=10)) == 10
        assert len(_mini_bar(0, width=10)) == 10
        assert len(_mini_bar(100, width=10)) == 10
