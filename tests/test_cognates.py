"""Tests for cognates module - false friends, disambiguation, cognate scanning."""

from unittest.mock import MagicMock

from ankicli.cognates import (
    FALSE_FRIENDS,
    DISAMBIGUATION_PAIRS,
    FalseFriend,
    EtymologyPair,
    get_all_false_friends,
    get_all_disambiguation_pairs,
    lookup_false_friend,
    lookup_disambiguation,
    classify_words_by_cognate_type,
    format_cognate_scan_text,
)
from ankicli.cefr import CEFRWord, _cognate_sort_key, get_suggestions, LevelProgress, CategoryProgress
from ankicli.tool_handlers import HANDLERS


# ---------------------------------------------------------------------------
# FalseFriend data structure tests
# ---------------------------------------------------------------------------

class TestFalseFriends:
    """Tests for false friend data and lookup."""

    def test_false_friends_count(self):
        """Should have ~20 critical false friends."""
        assert len(FALSE_FRIENDS) >= 18  # at least 18

    def test_false_friend_structure(self):
        """Each false friend should have all required fields."""
        for ff in FALSE_FRIENDS:
            assert isinstance(ff, FalseFriend)
            assert ff.spanish
            assert ff.seems_like
            assert ff.actual_meaning
            assert ff.english_equivalent
            assert ff.warning

    def test_lookup_embarazada(self):
        ff = lookup_false_friend("embarazada")
        assert ff is not None
        assert ff.actual_meaning == "pregnant"
        assert "embarrassed" in ff.seems_like.lower()

    def test_lookup_exito(self):
        ff = lookup_false_friend("éxito")
        assert ff is not None
        assert ff.actual_meaning == "success"

    def test_lookup_carpeta(self):
        ff = lookup_false_friend("carpeta")
        assert ff is not None
        assert "folder" in ff.actual_meaning.lower()

    def test_lookup_sensible(self):
        ff = lookup_false_friend("sensible")
        assert ff is not None
        assert "sensitive" in ff.actual_meaning.lower()

    def test_lookup_case_insensitive(self):
        ff = lookup_false_friend("EMBARAZADA")
        assert ff is not None
        assert ff.spanish == "embarazada"

    def test_lookup_with_spaces(self):
        ff = lookup_false_friend("  éxito  ")
        assert ff is not None

    def test_lookup_not_found(self):
        ff = lookup_false_friend("hola")
        assert ff is None

    def test_lookup_empty(self):
        ff = lookup_false_friend("")
        assert ff is None

    def test_get_all_false_friends(self):
        all_ff = get_all_false_friends()
        assert len(all_ff) == len(FALSE_FRIENDS)
        # Should be a copy, not the same object
        assert all_ff is not FALSE_FRIENDS

    def test_key_false_friends_present(self):
        """Ensure the most important false friends are included."""
        words = {ff.spanish for ff in FALSE_FRIENDS}
        critical = {
            "embarazada", "éxito", "carpeta", "actual", "realizar",
            "asistir", "sensible", "molestar", "librería", "fábrica",
            "recordar", "soportar", "largo", "ropa",
        }
        for word in critical:
            assert word in words, f"Missing critical false friend: {word}"


# ---------------------------------------------------------------------------
# EtymologyPair data structure tests
# ---------------------------------------------------------------------------

class TestDisambiguationPairs:
    """Tests for etymology disambiguation pairs."""

    def test_pairs_count(self):
        """Should have at least the 3 core pairs (ser/estar, por/para, saber/conocer)."""
        assert len(DISAMBIGUATION_PAIRS) >= 3

    def test_pair_structure(self):
        for pair in DISAMBIGUATION_PAIRS:
            assert isinstance(pair, EtymologyPair)
            assert pair.word_a
            assert pair.word_b
            assert pair.latin_a
            assert pair.latin_b
            assert pair.meaning_a
            assert pair.meaning_b
            assert pair.mnemonic

    def test_lookup_ser(self):
        pair = lookup_disambiguation("ser")
        assert pair is not None
        assert pair.word_a == "ser"
        assert pair.word_b == "estar"
        assert "sedere" in pair.latin_a.lower()

    def test_lookup_estar(self):
        pair = lookup_disambiguation("estar")
        assert pair is not None
        assert pair.word_a == "ser"
        assert "stare" in pair.latin_b.lower()

    def test_lookup_por(self):
        pair = lookup_disambiguation("por")
        assert pair is not None
        assert pair.word_b == "para"

    def test_lookup_para(self):
        pair = lookup_disambiguation("para")
        assert pair is not None
        assert pair.word_a == "por"

    def test_lookup_saber(self):
        pair = lookup_disambiguation("saber")
        assert pair is not None
        assert "sapere" in pair.latin_a.lower()

    def test_lookup_conocer(self):
        pair = lookup_disambiguation("conocer")
        assert pair is not None
        assert "cognoscere" in pair.latin_b.lower()

    def test_lookup_not_found(self):
        pair = lookup_disambiguation("hola")
        assert pair is None

    def test_lookup_case_insensitive(self):
        pair = lookup_disambiguation("SER")
        assert pair is not None

    def test_get_all_disambiguation_pairs(self):
        all_pairs = get_all_disambiguation_pairs()
        assert len(all_pairs) == len(DISAMBIGUATION_PAIRS)
        assert all_pairs is not DISAMBIGUATION_PAIRS

    def test_core_pairs_present(self):
        words = set()
        for pair in DISAMBIGUATION_PAIRS:
            words.add(pair.word_a)
            words.add(pair.word_b)
        for w in ("ser", "estar", "por", "para", "saber", "conocer"):
            assert w in words, f"Missing core pair word: {w}"


# ---------------------------------------------------------------------------
# Cognate classification tests
# ---------------------------------------------------------------------------

class TestClassifyWordsByCognateType:
    """Tests for classify_words_by_cognate_type."""

    def _make_mock_cefr(self, words_data):
        """Create a mock CEFRData with given word data."""
        from unittest.mock import MagicMock
        from ankicli.cefr import CEFRWord

        cefr = MagicMock()
        cefr._loaded = True

        def mock_load():
            pass
        cefr.load = mock_load

        def mock_lookup(word):
            for level, w in words_data:
                if w.word.lower() == word.lower():
                    return (level, w)
            return None
        cefr.lookup_word = mock_lookup

        return cefr

    def test_transparent_classification(self):
        from ankicli.cefr import CEFRWord
        words_data = [
            ("A1", CEFRWord(
                word="hotel", english="hotel", pos="noun", gender="m",
                category="travel", subcategory="accommodation",
                tags=["cognate::transparent"], level="A1",
                cognate_type="transparent",
            )),
        ]
        cefr = self._make_mock_cefr(words_data)
        result = classify_words_by_cognate_type(["hotel"], cefr)
        assert len(result["transparent"]) == 1
        assert result["transparent"][0]["word"] == "hotel"

    def test_false_friend_classification(self):
        from ankicli.cefr import CEFRWord
        words_data = [
            ("A2", CEFRWord(
                word="embarazada", english="pregnant", pos="adjective", gender=None,
                category="health", subcategory="conditions",
                tags=["cognate::false_friend"], level="A2",
                cognate_type="false_friend",
            )),
        ]
        cefr = self._make_mock_cefr(words_data)
        result = classify_words_by_cognate_type(["embarazada"], cefr)
        assert len(result["false_friend"]) == 1

    def test_unknown_word(self):
        from ankicli.cefr import CEFRWord
        cefr = self._make_mock_cefr([])
        result = classify_words_by_cognate_type(["xyznotaword"], cefr)
        assert len(result["unknown"]) == 1

    def test_no_cognate_type_defaults_to_none(self):
        from ankicli.cefr import CEFRWord
        words_data = [
            ("A1", CEFRWord(
                word="casa", english="house", pos="noun", gender="f",
                category="home", subcategory="rooms",
                tags=[], level="A1",
            )),
        ]
        cefr = self._make_mock_cefr(words_data)
        result = classify_words_by_cognate_type(["casa"], cefr)
        assert len(result["none"]) == 1

    def test_cognate_from_tag(self):
        """When cognate_type attr is None but tag is present, should classify from tag."""
        from ankicli.cefr import CEFRWord
        words_data = [
            ("A1", CEFRWord(
                word="restaurante", english="restaurant", pos="noun", gender="m",
                category="food", subcategory="dining",
                tags=["cognate::transparent"], level="A1",
            )),
        ]
        cefr = self._make_mock_cefr(words_data)
        result = classify_words_by_cognate_type(["restaurante"], cefr)
        assert len(result["transparent"]) == 1

    def test_multiple_words(self):
        from ankicli.cefr import CEFRWord
        words_data = [
            ("A1", CEFRWord(
                word="hotel", english="hotel", pos="noun", gender="m",
                category="travel", subcategory="accommodation",
                tags=["cognate::transparent"], level="A1",
                cognate_type="transparent",
            )),
            ("A2", CEFRWord(
                word="largo", english="long", pos="adjective", gender=None,
                category="description", subcategory="size",
                tags=["cognate::false_friend"], level="A2",
                cognate_type="false_friend",
            )),
        ]
        cefr = self._make_mock_cefr(words_data)
        result = classify_words_by_cognate_type(
            ["hotel", "largo", "unknownword"], cefr
        )
        assert len(result["transparent"]) == 1
        assert len(result["false_friend"]) == 1
        assert len(result["unknown"]) == 1

    def test_empty_word_list(self):
        cefr = self._make_mock_cefr([])
        result = classify_words_by_cognate_type([], cefr)
        assert all(len(v) == 0 for v in result.values())


class TestFormatCognateScanText:
    """Tests for format_cognate_scan_text."""

    def test_basic_format(self):
        groups = {
            "transparent": [{"word": "hotel", "english": "hotel", "level": "A1"}],
            "semi_transparent": [],
            "false_friend": [{"word": "largo", "english": "long", "level": "A2"}],
            "none": [{"word": "casa", "english": "house", "level": "A1"}],
            "unknown": [],
        }
        text = format_cognate_scan_text(groups)
        assert "hotel" in text
        assert "largo" in text
        assert "casa" in text
        assert "Total: 3 words scanned" in text

    def test_empty_groups(self):
        groups = {
            "transparent": [],
            "semi_transparent": [],
            "false_friend": [],
            "none": [],
            "unknown": [],
        }
        text = format_cognate_scan_text(groups)
        assert "Total: 0 words scanned" in text

    def test_transparent_label(self):
        groups = {
            "transparent": [{"word": "hotel", "english": "hotel", "level": "A1"}],
            "semi_transparent": [],
            "false_friend": [],
            "none": [],
            "unknown": [],
        }
        text = format_cognate_scan_text(groups)
        assert "probably already recognize" in text.lower()

    def test_false_friend_label(self):
        groups = {
            "transparent": [],
            "semi_transparent": [],
            "false_friend": [{"word": "largo", "english": "long", "level": "A2"}],
            "none": [],
            "unknown": [],
        }
        text = format_cognate_scan_text(groups)
        assert "false friend" in text.lower()


# ---------------------------------------------------------------------------
# C5: Cognate-first sorting in get_suggestions
# ---------------------------------------------------------------------------

class TestCognateSortKey:
    """Tests for _cognate_sort_key used in C5 ordering."""

    def test_transparent_first(self):
        w = CEFRWord(
            word="hotel", english="hotel", pos="noun", gender="m",
            category="travel", subcategory="", tags=[], level="A1",
            cognate_type="transparent",
        )
        assert _cognate_sort_key(w) == 0

    def test_semi_transparent_second(self):
        w = CEFRWord(
            word="familia", english="family", pos="noun", gender="f",
            category="family", subcategory="", tags=[], level="A1",
            cognate_type="semi_transparent",
        )
        assert _cognate_sort_key(w) == 1

    def test_false_friend_third(self):
        w = CEFRWord(
            word="largo", english="long", pos="adjective", gender=None,
            category="description", subcategory="", tags=[], level="A2",
            cognate_type="false_friend",
        )
        assert _cognate_sort_key(w) == 2

    def test_none_type_last(self):
        w = CEFRWord(
            word="mesa", english="table", pos="noun", gender="f",
            category="home", subcategory="", tags=[], level="A1",
        )
        assert _cognate_sort_key(w) == 3

    def test_sorting_order(self):
        """Transparent < semi_transparent < false_friend < none."""
        transparent = CEFRWord(
            word="hotel", english="hotel", pos="noun", gender="m",
            category="travel", subcategory="", tags=[], cognate_type="transparent",
        )
        semi = CEFRWord(
            word="familia", english="family", pos="noun", gender="f",
            category="family", subcategory="", tags=[], cognate_type="semi_transparent",
        )
        false_f = CEFRWord(
            word="largo", english="long", pos="adjective", gender=None,
            category="desc", subcategory="", tags=[], cognate_type="false_friend",
        )
        none_type = CEFRWord(
            word="mesa", english="table", pos="noun", gender="f",
            category="home", subcategory="", tags=[],
        )
        words = [none_type, false_f, transparent, semi]
        sorted_words = sorted(words, key=_cognate_sort_key)
        assert sorted_words[0].word == "hotel"
        assert sorted_words[1].word == "familia"
        assert sorted_words[2].word == "largo"
        assert sorted_words[3].word == "mesa"


class TestGetSuggestionsCognateFirst:
    """Tests for C5: cognate-first ordering in get_suggestions."""

    def _make_cefr_data(self, words):
        """Create a mock CEFRData with given words at A1."""
        cefr = MagicMock()
        cefr._loaded = True
        cefr.load = MagicMock()
        cefr.get_words_for_level = MagicMock(return_value=words)
        return cefr

    def test_cognate_first_sorts_transparent_first(self):
        words = [
            CEFRWord(word="mesa", english="table", pos="noun", gender="f",
                     category="home", subcategory="furniture", tags=[], level="A1"),
            CEFRWord(word="hotel", english="hotel", pos="noun", gender="m",
                     category="travel", subcategory="accommodation", tags=[], level="A1",
                     cognate_type="transparent"),
        ]
        cefr = self._make_cefr_data(words)
        progress = {
            "A1": LevelProgress(
                level="A1", words_known=0, words_total=2,
                categories={"home": CategoryProgress("home", 0, 1),
                             "travel": CategoryProgress("travel", 0, 1)},
            )
        }
        result = get_suggestions(cefr, progress, level="A1", count=10, cognate_first=True)
        assert result[0].word == "hotel"  # transparent first

    def test_cognate_first_false_param(self):
        words = [
            CEFRWord(word="mesa", english="table", pos="noun", gender="f",
                     category="home", subcategory="furniture", tags=[], level="A1"),
            CEFRWord(word="hotel", english="hotel", pos="noun", gender="m",
                     category="travel", subcategory="accommodation", tags=[], level="A1",
                     cognate_type="transparent"),
        ]
        cefr = self._make_cefr_data(words)
        progress = {
            "A1": LevelProgress(
                level="A1", words_known=0, words_total=2,
                categories={"home": CategoryProgress("home", 0, 1),
                             "travel": CategoryProgress("travel", 0, 1)},
            )
        }
        result = get_suggestions(cefr, progress, level="A1", count=10, cognate_first=False)
        # Without cognate sorting, category-based ordering applies
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Handler registration tests
# ---------------------------------------------------------------------------

class TestCognateHandlerRegistration:
    """Tests that cognate handlers are properly registered."""

    def test_scan_cognates_handler_exists(self):
        assert "scan_cognates" in HANDLERS

    def test_check_false_friend_handler_exists(self):
        assert "check_false_friend" in HANDLERS

    def test_check_false_friend_handler_found(self):
        handler = HANDLERS["check_false_friend"]
        anki = MagicMock()
        result = handler(anki, {"word": "embarazada"})
        assert "FALSE FRIEND DETECTED" in result
        assert "pregnant" in result

    def test_check_false_friend_handler_not_found(self):
        handler = HANDLERS["check_false_friend"]
        anki = MagicMock()
        result = handler(anki, {"word": "hola"})
        assert "NOT a known false friend" in result


# ---------------------------------------------------------------------------
# Prompt section integration tests
# ---------------------------------------------------------------------------

class TestCognatePromptSections:
    """Tests that cognate prompt sections are included in system prompt."""

    def test_c1_cognate_guide_in_prompt(self):
        from ankicli.assistant import build_system_prompt
        prompt = build_system_prompt()
        assert "Cognate Hints on Card Backs (C1)" in prompt

    def test_c2_false_friends_guide_in_prompt(self):
        from ankicli.assistant import build_system_prompt
        prompt = build_system_prompt()
        assert "False Friend Warnings (C2)" in prompt

    def test_c3_etymology_guide_in_prompt(self):
        from ankicli.assistant import build_system_prompt
        prompt = build_system_prompt()
        assert "Etymology for Disambiguation (C3)" in prompt

    def test_false_friends_list_in_prompt(self):
        from ankicli.assistant import build_system_prompt
        prompt = build_system_prompt()
        assert "embarazada = pregnant" in prompt
        assert "éxito = success" in prompt

    def test_etymology_pairs_in_prompt(self):
        from ankicli.assistant import build_system_prompt
        prompt = build_system_prompt()
        assert "sedere" in prompt  # ser etymology
        assert "stare" in prompt   # estar etymology
        assert "sapere" in prompt  # saber etymology


# ---------------------------------------------------------------------------
# CEFRWord cognate_type field tests
# ---------------------------------------------------------------------------

class TestCEFRWordCognateType:
    """Tests for the cognate_type field on CEFRWord."""

    def test_default_cognate_type_is_none(self):
        w = CEFRWord(
            word="casa", english="house", pos="noun", gender="f",
            category="home", subcategory="rooms", tags=[],
        )
        assert w.cognate_type is None

    def test_cognate_type_set(self):
        w = CEFRWord(
            word="hotel", english="hotel", pos="noun", gender="m",
            category="travel", subcategory="accommodation", tags=[],
            cognate_type="transparent",
        )
        assert w.cognate_type == "transparent"

    def test_format_suggestions_with_cognate_type(self):
        from ankicli.cefr import format_suggestions_text
        words = [
            CEFRWord(word="hotel", english="hotel", pos="noun", gender="m",
                     category="travel", subcategory="", tags=[], level="A1",
                     cognate_type="transparent"),
            CEFRWord(word="largo", english="long", pos="adjective", gender=None,
                     category="desc", subcategory="", tags=[], level="A2",
                     cognate_type="false_friend"),
            CEFRWord(word="mesa", english="table", pos="noun", gender="f",
                     category="home", subcategory="", tags=[], level="A1"),
        ]
        text = format_suggestions_text(words)
        assert "[cognate - easy!]" in text
        assert "[FALSE FRIEND!]" in text
        # mesa has no cognate type, should not have a label
        assert "mesa - table" in text
