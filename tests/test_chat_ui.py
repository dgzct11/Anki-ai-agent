"""Tests for chat.py UI helper functions."""

from rich.panel import Panel
from rich.text import Text

from ankicli.chat import (
    format_tokens,
    create_context_bar,
    create_tool_panel,
    create_result_panel,
    _summarize_tool_input,
)


class TestFormatTokens:
    """Tests for format_tokens helper."""

    def test_small_number(self):
        assert format_tokens(500) == "500"

    def test_exact_thousand(self):
        assert format_tokens(1000) == "1.0K"

    def test_large_number(self):
        assert format_tokens(150000) == "150.0K"

    def test_zero(self):
        assert format_tokens(0) == "0"

    def test_just_below_thousand(self):
        assert format_tokens(999) == "999"

    def test_fractional_thousands(self):
        assert format_tokens(1500) == "1.5K"

    def test_tens_of_thousands(self):
        assert format_tokens(42500) == "42.5K"


class TestCreateContextBar:
    """Tests for create_context_bar function."""

    def test_returns_text(self):
        status = {
            "percent_used": 25.0,
            "input_tokens": 50000,
            "max_tokens": 200000,
        }
        result = create_context_bar(status)
        assert isinstance(result, Text)

    def test_low_usage_is_green(self):
        status = {
            "percent_used": 10.0,
            "input_tokens": 20000,
            "max_tokens": 200000,
        }
        result = create_context_bar(status)
        rendered = str(result)
        assert "10%" in rendered

    def test_high_usage_shows_percent(self):
        status = {
            "percent_used": 95.0,
            "input_tokens": 190000,
            "max_tokens": 200000,
        }
        result = create_context_bar(status)
        rendered = str(result)
        assert "95%" in rendered

    def test_includes_session_minutes(self):
        status = {
            "percent_used": 30.0,
            "input_tokens": 60000,
            "max_tokens": 200000,
            "session_minutes": 15,
        }
        result = create_context_bar(status)
        rendered = str(result)
        assert "15 min" in rendered

    def test_includes_cards_added(self):
        status = {
            "percent_used": 30.0,
            "input_tokens": 60000,
            "max_tokens": 200000,
            "session_cards_added": 5,
        }
        result = create_context_bar(status)
        rendered = str(result)
        assert "+5 cards" in rendered

    def test_zero_session_minutes_hidden(self):
        status = {
            "percent_used": 30.0,
            "input_tokens": 60000,
            "max_tokens": 200000,
            "session_minutes": 0,
        }
        result = create_context_bar(status)
        rendered = str(result)
        assert "min" not in rendered

    def test_zero_cards_hidden(self):
        status = {
            "percent_used": 30.0,
            "input_tokens": 60000,
            "max_tokens": 200000,
            "session_cards_added": 0,
        }
        result = create_context_bar(status)
        rendered = str(result)
        assert "cards" not in rendered

    def test_includes_cefr_level(self):
        status = {
            "percent_used": 30.0,
            "input_tokens": 60000,
            "max_tokens": 200000,
            "cefr_current_level": "A2",
            "cefr_known": 147,
            "cefr_total": 500,
        }
        result = create_context_bar(status)
        rendered = str(result)
        assert "A2: 147/500" in rendered

    def test_includes_streak(self):
        status = {
            "percent_used": 30.0,
            "input_tokens": 60000,
            "max_tokens": 200000,
            "streak_days": 12,
        }
        result = create_context_bar(status)
        rendered = str(result)
        assert "Streak: 12d" in rendered


class TestCreateToolPanel:
    """Tests for create_tool_panel function."""

    def test_returns_panel(self):
        result = create_tool_panel("add_card", {"front": "hello", "back": "hola"})
        assert isinstance(result, Panel)

    def test_shows_tool_name(self):
        panel = create_tool_panel("search_cards", {"query": "deck:Spanish"})
        # The panel content contains the tool name
        content = panel.renderable
        assert isinstance(content, Text)
        plain = str(content)
        assert "search_cards" in plain

    def test_truncates_long_values(self):
        long_value = "x" * 100
        panel = create_tool_panel("add_card", {"front": long_value})
        content = str(panel.renderable)
        assert "..." in content

    def test_shows_list_count(self):
        panel = create_tool_panel("delete_cards", {"note_ids": [1, 2, 3]})
        content = str(panel.renderable)
        assert "3 items" in content


class TestCreateResultPanel:
    """Tests for create_result_panel function."""

    def test_returns_panel(self):
        result = create_result_panel("add_card", "Card added (note ID: 12345)")
        assert isinstance(result, Panel)

    def test_truncates_long_results(self):
        long_result = "x" * 1000
        panel = create_result_panel("search_cards", long_result)
        content = str(panel.renderable)
        assert "..." in content
        assert len(content) < 1000

    def test_short_result_not_truncated(self):
        panel = create_result_panel("list_decks", "Spanish, English")
        content = str(panel.renderable)
        assert "..." not in content


class TestSummarizeToolInput:
    """Tests for _summarize_tool_input function."""

    def test_add_card(self):
        result = _summarize_tool_input("add_card", {"front": "to run"})
        assert "'to run'" in result

    def test_add_card_long_front(self):
        result = _summarize_tool_input("add_card", {"front": "x" * 100})
        assert "..." in result

    def test_add_multiple_cards(self):
        cards = [{"front": f"word_{i}"} for i in range(3)]
        result = _summarize_tool_input("add_multiple_cards", {"cards": cards})
        assert "3 cards" in result
        assert "word_0" in result

    def test_add_multiple_cards_many(self):
        cards = [{"front": f"word_{i}"} for i in range(15)]
        result = _summarize_tool_input("add_multiple_cards", {"cards": cards})
        assert "15 cards" in result
        assert "+5 more" in result

    def test_add_multiple_cards_empty(self):
        result = _summarize_tool_input("add_multiple_cards", {"cards": []})
        assert "0 cards" in result

    def test_update_card(self):
        result = _summarize_tool_input("update_card", {"note_id": 123, "front": "hello"})
        assert "ID 123" in result
        assert "'hello'" in result

    def test_update_card_no_front(self):
        result = _summarize_tool_input("update_card", {"note_id": 123})
        assert "ID 123" in result

    def test_update_multiple_cards(self):
        updates = [{"note_id": 1}, {"note_id": 2}, {"note_id": 3}]
        result = _summarize_tool_input("update_multiple_cards", {"updates": updates})
        assert "3 cards" in result

    def test_delete_cards(self):
        result = _summarize_tool_input("delete_cards", {"note_ids": [1, 2]})
        assert "2 cards" in result

    def test_search_cards(self):
        result = _summarize_tool_input("search_cards", {"query": "deck:Spanish"})
        assert "'deck:Spanish'" in result

    def test_check_words_exist(self):
        result = _summarize_tool_input("check_words_exist", {"words": ["hola", "adios", "gato"]})
        assert "hola" in result
        assert "adios" in result

    def test_check_words_exist_many(self):
        words = [f"word_{i}" for i in range(10)]
        result = _summarize_tool_input("check_words_exist", {"words": words})
        assert "+5 more" in result

    def test_update_learning_summary(self):
        result = _summarize_tool_input("update_learning_summary", {
            "level": "A1", "words_added": ["hola", "adios"],
        })
        assert "A1" in result
        assert "+2 words" in result

    def test_all_cards_delegate(self):
        result = _summarize_tool_input("all_cards_delegate", {
            "deck_name": "Spanish", "prompt": "Add etymology info",
        })
        assert "Spanish" in result
        assert "Add etymology" in result

    def test_all_cards_delegate_dry_run(self):
        result = _summarize_tool_input("all_cards_delegate", {
            "deck_name": "Spanish", "prompt": "test", "dry_run": True,
        })
        assert "DRY RUN" in result

    def test_card_subset_delegate(self):
        result = _summarize_tool_input("card_subset_delegate", {
            "note_ids": [1, 2, 3], "prompt": "Fix formatting",
        })
        assert "3 cards" in result

    def test_set_tool_note(self):
        result = _summarize_tool_input("set_tool_note", {
            "tool_name": "add_card", "note": "Use Latin American Spanish",
        })
        assert "[add_card]" in result
        assert "Latin American" in result

    def test_get_tool_notes(self):
        result = _summarize_tool_input("get_tool_notes", {})
        assert "listing preferences" in result

    def test_remove_tool_note(self):
        result = _summarize_tool_input("remove_tool_note", {"tool_name": "add_card"})
        assert "[add_card]" in result

    def test_start_translation_practice(self):
        result = _summarize_tool_input("start_translation_practice", {
            "deck_name": "Spanish", "count": 10, "direction": "en_to_es",
        })
        assert "Spanish" in result
        assert "10q" in result
        assert "en_to_es" in result

    def test_start_grammar_quiz(self):
        result = _summarize_tool_input("start_grammar_quiz", {
            "topic": "ser_vs_estar", "level": "A1", "count": 5,
        })
        assert "ser_vs_estar" in result
        assert "A1" in result

    def test_log_error(self):
        result = _summarize_tool_input("log_error", {
            "error_type": "gender_agreement", "example": "la problema",
        })
        assert "gender_agreement" in result
        assert "la problema" in result

    def test_unknown_tool_default(self):
        result = _summarize_tool_input("unknown_tool", {"key": "value", "num": 42})
        assert "key='value'" in result
        assert "num=42" in result

    def test_default_truncates_long_strings(self):
        result = _summarize_tool_input("unknown_tool", {"key": "x" * 50})
        assert "..." in result

    def test_default_limits_to_3_params(self):
        result = _summarize_tool_input("unknown_tool", {
            "a": "1", "b": "2", "c": "3", "d": "4",
        })
        # Should only show 3 parameters
        assert result.count("=") <= 3
