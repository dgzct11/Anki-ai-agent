"""Tests for tool_handlers module - handler registry and coverage."""

from unittest.mock import MagicMock, patch
import inspect

from ankicli.tool_handlers import HANDLERS, handler
from ankicli.tools import ANKI_TOOLS


class TestHandlerRegistry:
    """Tests for the handler decorator and HANDLERS dict."""

    def test_handlers_is_dict(self):
        assert isinstance(HANDLERS, dict)

    def test_handlers_not_empty(self):
        assert len(HANDLERS) > 0

    def test_handler_decorator_registers(self):
        """The @handler decorator should add to HANDLERS."""
        original_len = len(HANDLERS)

        @handler("__test_dummy__")
        def dummy(anki, tool_input, **ctx):
            pass

        assert "__test_dummy__" in HANDLERS
        assert HANDLERS["__test_dummy__"] is dummy

        # Clean up
        del HANDLERS["__test_dummy__"]
        assert len(HANDLERS) == original_len

    def test_handler_decorator_returns_function(self):
        """The @handler decorator should return the original function."""
        def my_func(anki, tool_input, **ctx):
            pass

        result = handler("__test_return__")(my_func)
        assert result is my_func

        # Clean up
        del HANDLERS["__test_return__"]

    def test_all_handlers_are_callable(self):
        for name, fn in HANDLERS.items():
            assert callable(fn), f"Handler '{name}' is not callable"

    def test_all_handlers_accept_anki_and_tool_input(self):
        """Every handler should accept at least (anki, tool_input, **ctx)."""
        for name, fn in HANDLERS.items():
            sig = inspect.signature(fn)
            params = list(sig.parameters.keys())
            assert len(params) >= 2, (
                f"Handler '{name}' has too few parameters: {params}"
            )


class TestHandlerToolCoverage:
    """Tests that handlers cover the tools defined in ANKI_TOOLS."""

    # Tools that are handled specially (not through HANDLERS dispatch)
    SPECIAL_TOOLS = set()

    def _get_tool_names(self):
        return {t["name"] for t in ANKI_TOOLS}

    def test_every_tool_has_handler(self):
        """Every tool in ANKI_TOOLS should have a registered handler."""
        tool_names = self._get_tool_names()
        handler_names = set(HANDLERS.keys())

        missing = tool_names - handler_names - self.SPECIAL_TOOLS
        assert len(missing) == 0, (
            f"Tools without handlers: {missing}"
        )

    def test_no_orphan_handlers(self):
        """Every handler should correspond to a tool in ANKI_TOOLS."""
        tool_names = self._get_tool_names()
        handler_names = set(HANDLERS.keys())

        orphans = handler_names - tool_names
        assert len(orphans) == 0, (
            f"Handlers without corresponding tools: {orphans}"
        )


class TestExpectedHandlers:
    """Tests that specific important handlers are registered."""

    def test_list_decks_handler(self):
        assert "list_decks" in HANDLERS

    def test_add_card_handler(self):
        assert "add_card" in HANDLERS

    def test_add_multiple_cards_handler(self):
        assert "add_multiple_cards" in HANDLERS

    def test_search_cards_handler(self):
        assert "search_cards" in HANDLERS

    def test_update_card_handler(self):
        assert "update_card" in HANDLERS

    def test_delete_cards_handler(self):
        assert "delete_cards" in HANDLERS

    def test_get_learning_summary_handler(self):
        assert "get_learning_summary" in HANDLERS

    def test_update_learning_summary_handler(self):
        assert "update_learning_summary" in HANDLERS

    def test_compact_conversation_handler(self):
        assert "compact_conversation" in HANDLERS

    def test_set_tool_note_handler(self):
        assert "set_tool_note" in HANDLERS

    def test_sync_anki_handler(self):
        assert "sync_anki" in HANDLERS

    def test_check_word_exists_handler(self):
        assert "check_word_exists" in HANDLERS

    def test_find_card_by_word_handler(self):
        assert "find_card_by_word" in HANDLERS


class TestHandlerBehavior:
    """Tests for specific handler behaviors using mocks."""

    def test_list_decks_no_decks(self):
        anki = MagicMock()
        anki.get_decks.return_value = []
        result = HANDLERS["list_decks"](anki, {})
        assert "No decks" in result

    def test_list_decks_with_decks(self):
        anki = MagicMock()
        deck = MagicMock()
        deck.name = "Spanish"
        deck.new_count = 5
        deck.learn_count = 3
        deck.review_count = 10
        anki.get_decks.return_value = [deck]
        result = HANDLERS["list_decks"](anki, {})
        assert "Spanish" in result
        assert "5" in result

    def test_create_deck(self):
        anki = MagicMock()
        anki.create_deck.return_value = 123
        result = HANDLERS["create_deck"](anki, {"name": "TestDeck"})
        assert "TestDeck" in result
        assert "123" in result
        anki.create_deck.assert_called_once_with("TestDeck")

    def test_add_card_increments_session_count(self):
        anki = MagicMock()
        anki.add_card.return_value = 456
        assistant = MagicMock()
        assistant.session_cards_added = 0
        result = HANDLERS["add_card"](
            anki,
            {"deck_name": "Spanish", "front": "hola", "back": "hello"},
            assistant=assistant,
        )
        assert "456" in result
        assert assistant.session_cards_added == 1

    def test_add_multiple_cards_counts_successes(self):
        anki = MagicMock()
        anki.add_cards.return_value = [1, None, 3]  # 2 succeeded, 1 failed
        assistant = MagicMock()
        assistant.session_cards_added = 0
        cards = [
            {"front": "a", "back": "b"},
            {"front": "c", "back": "d"},
            {"front": "e", "back": "f"},
        ]
        result = HANDLERS["add_multiple_cards"](
            anki,
            {"deck_name": "Spanish", "cards": cards},
            assistant=assistant,
        )
        assert "2/3" in result
        assert assistant.session_cards_added == 2

    def test_search_cards_no_results(self):
        anki = MagicMock()
        anki.search_cards.return_value = []
        result = HANDLERS["search_cards"](anki, {"query": "nothing"})
        assert "No cards found" in result

    def test_search_cards_with_results(self):
        anki = MagicMock()
        card = MagicMock()
        card.front = "hola"
        card.back = "hello"
        card.id = 1
        card.tags = []
        anki.search_cards.return_value = [card]
        result = HANDLERS["search_cards"](anki, {"query": "hola"})
        assert "1 card" in result
        assert "hola" in result

    def test_delete_cards(self):
        anki = MagicMock()
        result = HANDLERS["delete_cards"](anki, {"note_ids": [1, 2, 3]})
        assert "3" in result
        anki.delete_notes.assert_called_once_with([1, 2, 3])

    def test_sync_anki(self):
        anki = MagicMock()
        result = HANDLERS["sync_anki"](anki, {})
        assert "Sync" in result
        anki.sync.assert_called_once()

    def test_check_word_exists_not_found(self):
        anki = MagicMock()
        anki.search_cards.return_value = []
        result = HANDLERS["check_word_exists"](anki, {"word": "gato"})
        assert "NOT FOUND" in result
        assert "gato" in result

    def test_check_word_exists_found(self):
        anki = MagicMock()
        card = MagicMock()
        card.front = "el gato"
        card.back = "the cat"
        card.tags = []
        anki.search_cards.return_value = [card]
        result = HANDLERS["check_word_exists"](anki, {"word": "gato"})
        assert "FOUND" in result

    def test_set_tool_note(self):
        anki = MagicMock()
        config = MagicMock()
        config.tool_notes = {}
        with patch("ankicli.config.save_config"):
            result = HANDLERS["set_tool_note"](
                anki,
                {"tool_name": "add_card", "note": "Always use Spanish deck"},
                config=config,
            )
        assert "add_card" in result
        assert config.tool_notes["add_card"] == "Always use Spanish deck"

    def test_list_note_types_empty(self):
        anki = MagicMock()
        anki.get_note_types.return_value = []
        result = HANDLERS["list_note_types"](anki, {})
        assert "No note types" in result

    def test_list_note_types_with_types(self):
        anki = MagicMock()
        note_type = MagicMock()
        note_type.name = "Basic"
        note_type.fields = ["Front", "Back"]
        anki.get_note_types.return_value = [note_type]
        result = HANDLERS["list_note_types"](anki, {})
        assert "Basic" in result
        assert "Front" in result

    def test_get_note_found(self):
        anki = MagicMock()
        card = MagicMock()
        card.id = 789
        card.front = "hola"
        card.back = "hello"
        card.tags = ["spanish"]
        anki.get_note.return_value = card
        result = HANDLERS["get_note"](anki, {"note_id": 789})
        assert "789" in result
        assert "hola" in result
        assert "spanish" in result

    def test_get_note_not_found(self):
        anki = MagicMock()
        anki.get_note.return_value = None
        result = HANDLERS["get_note"](anki, {"note_id": 999})
        assert "not found" in result


# ---------------------------------------------------------------------------
# Vocabulary Network handler tests (V1, V3-V11)
# ---------------------------------------------------------------------------

class TestNetworkHandlers:
    """Tests for vocabulary network handler behaviors."""

    def test_update_word_network_basic(self):
        """V1: update_word_network creates a node."""
        anki = MagicMock()
        with patch("ankicli.word_network.WORD_NETWORK_FILE") as mock_nf, \
             patch("ankicli.word_network.DISAMBIGUATION_FILE") as mock_df, \
             patch("ankicli.word_network.ensure_data_dir"):
            mock_nf.exists.return_value = False
            mock_df.exists.return_value = False

            result = HANDLERS["update_word_network"](anki, {
                "word": "gato",
                "level": "A1",
                "pos": "noun",
                "theme": "animals",
            })
            assert "gato" in result
            assert "Network updated" in result

    def test_update_word_network_with_connections(self):
        """V1: update_word_network adds connections."""
        anki = MagicMock()
        with patch("ankicli.word_network.WORD_NETWORK_FILE") as mock_nf, \
             patch("ankicli.word_network.DISAMBIGUATION_FILE") as mock_df, \
             patch("ankicli.word_network.ensure_data_dir"):
            mock_nf.exists.return_value = False
            mock_df.exists.return_value = False

            result = HANDLERS["update_word_network"](anki, {
                "word": "bueno",
                "connections": [
                    {"type": "antonym", "target": "malo"},
                    {"type": "synonym", "target": "bien"},
                ],
                "collocations": [
                    {"phrase": "bueno para", "translation": "good for"},
                ],
            })
            assert "2 connection(s)" in result
            assert "1 collocation(s)" in result

    def test_show_word_connections_not_found(self):
        """V1: show_word_connections for unknown word."""
        anki = MagicMock()
        with patch("ankicli.word_network.WORD_NETWORK_FILE") as mock_nf, \
             patch("ankicli.word_network.DISAMBIGUATION_FILE") as mock_df, \
             patch("ankicli.word_network.ensure_data_dir"):
            mock_nf.exists.return_value = False
            mock_df.exists.return_value = False

            result = HANDLERS["show_word_connections"](anki, {"word": "nonexistent"})
            assert "not found" in result

    def test_get_morphological_family(self):
        """V3: get_morphological_family finds relatives."""
        anki = MagicMock()
        anki.search_cards.return_value = []  # No cards in Anki
        with patch("ankicli.word_network.WORD_NETWORK_FILE") as mock_nf, \
             patch("ankicli.word_network.DISAMBIGUATION_FILE") as mock_df, \
             patch("ankicli.word_network.ensure_data_dir"):
            mock_nf.exists.return_value = False
            mock_df.exists.return_value = False

            result = HANDLERS["get_morphological_family"](anki, {"word": "educar"})
            assert "educacion" in result
            assert "Morphological family" in result

    def test_show_disambiguation_pairs(self):
        """V4: show_disambiguation_pairs lists defaults."""
        anki = MagicMock()
        with patch("ankicli.word_network.WORD_NETWORK_FILE") as mock_nf, \
             patch("ankicli.word_network.DISAMBIGUATION_FILE") as mock_df, \
             patch("ankicli.word_network.ensure_data_dir"):
            mock_nf.exists.return_value = False
            mock_df.exists.return_value = False

            result = HANDLERS["show_disambiguation_pairs"](anki, {})
            assert "ser-estar" in result
            assert "por-para" in result
            assert "saber-conocer" in result

    def test_get_disambiguation_practice(self):
        """V4: get_disambiguation_practice returns instructions."""
        anki = MagicMock()
        with patch("ankicli.word_network.WORD_NETWORK_FILE") as mock_nf, \
             patch("ankicli.word_network.DISAMBIGUATION_FILE") as mock_df, \
             patch("ankicli.word_network.ensure_data_dir"):
            mock_nf.exists.return_value = False
            mock_df.exists.return_value = False

            result = HANDLERS["get_disambiguation_practice"](anki, {"pair": "ser-estar"})
            assert "DISAMBIGUATION PRACTICE" in result
            assert "ser / estar" in result

    def test_get_disambiguation_practice_not_found(self):
        """V4: get_disambiguation_practice for unknown pair."""
        anki = MagicMock()
        with patch("ankicli.word_network.WORD_NETWORK_FILE") as mock_nf, \
             patch("ankicli.word_network.DISAMBIGUATION_FILE") as mock_df, \
             patch("ankicli.word_network.ensure_data_dir"):
            mock_nf.exists.return_value = False
            mock_df.exists.return_value = False

            result = HANDLERS["get_disambiguation_practice"](anki, {"pair": "nonexistent-pair"})
            assert "not found" in result

    def test_log_disambiguation_result(self):
        """V4: log_disambiguation_result records results."""
        anki = MagicMock()
        with patch("ankicli.word_network.WORD_NETWORK_FILE") as mock_nf, \
             patch("ankicli.word_network.DISAMBIGUATION_FILE") as mock_df, \
             patch("ankicli.word_network.ensure_data_dir"):
            mock_nf.exists.return_value = False
            mock_df.exists.return_value = False

            result = HANDLERS["log_disambiguation_result"](anki, {
                "pair_id": "ser-estar",
                "correct": 4,
                "total": 5,
                "confused_words": ["estar"],
            })
            assert "80%" in result
            assert "ser-estar" in result

    def test_show_connection_map_not_found(self):
        """V10: show_connection_map for unknown word."""
        anki = MagicMock()
        with patch("ankicli.word_network.WORD_NETWORK_FILE") as mock_nf, \
             patch("ankicli.word_network.DISAMBIGUATION_FILE") as mock_df, \
             patch("ankicli.word_network.ensure_data_dir"):
            mock_nf.exists.return_value = False
            mock_df.exists.return_value = False

            result = HANDLERS["show_connection_map"](anki, {"word": "unknown"})
            assert "not found" in result

    def test_start_pair_review_empty_network(self):
        """V8: start_pair_review with no pairs."""
        anki = MagicMock()
        with patch("ankicli.word_network.WORD_NETWORK_FILE") as mock_nf, \
             patch("ankicli.word_network.DISAMBIGUATION_FILE") as mock_df, \
             patch("ankicli.word_network.ensure_data_dir"):
            mock_nf.exists.return_value = False
            mock_df.exists.return_value = False

            result = HANDLERS["start_pair_review"](anki, {})
            assert "No" in result

    def test_get_network_study_suggestions_empty(self):
        """V11: get_network_study_suggestions with empty network."""
        anki = MagicMock()
        with patch("ankicli.word_network.WORD_NETWORK_FILE") as mock_nf, \
             patch("ankicli.word_network.DISAMBIGUATION_FILE") as mock_df, \
             patch("ankicli.word_network.ensure_data_dir"):
            mock_nf.exists.return_value = False
            mock_df.exists.return_value = False

            result = HANDLERS["get_network_study_suggestions"](anki, {
                "recently_reviewed": ["gato", "perro"],
            })
            assert "No network-based suggestions" in result

    def test_network_handler_names_registered(self):
        """All network tools have registered handlers."""
        network_tools = [
            "update_word_network", "show_word_connections",
            "get_morphological_family", "get_disambiguation_practice",
            "show_disambiguation_pairs", "log_disambiguation_result",
            "get_semantic_field_progress", "show_connection_map",
            "start_pair_review", "get_network_study_suggestions",
        ]
        for tool_name in network_tools:
            assert tool_name in HANDLERS, f"Handler '{tool_name}' not registered"
