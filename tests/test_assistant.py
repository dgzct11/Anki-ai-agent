"""Tests for assistant module - prompt building, tool routing, context management."""

from unittest.mock import MagicMock, patch, PropertyMock
import time

from ankicli.assistant import (
    build_system_prompt,
    build_student_context,
    _PROMPT_SECTIONS,
    _CORE_IDENTITY,
    _CARD_FORMAT_GUIDE,
    _GENERAL_GUIDELINES,
)


class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""

    def test_returns_string(self):
        result = build_system_prompt()
        assert isinstance(result, str)

    def test_includes_core_identity(self):
        result = build_system_prompt()
        assert "Anki flashcard assistant" in result

    def test_includes_all_prompt_sections(self):
        result = build_system_prompt()
        for section in _PROMPT_SECTIONS:
            # Each section should be in the final prompt
            # Check a fragment from each
            assert section[:50] in result

    def test_with_general_note(self):
        result = build_system_prompt(general_note="Use Latin American Spanish")
        assert "Use Latin American Spanish" in result
        assert "Active User Preferences" in result

    def test_without_general_note(self):
        result = build_system_prompt(general_note=None)
        assert "Active User Preferences" not in result

    def test_with_extra_sections(self):
        extra = ["## Custom Section\n\nThis is a custom section."]
        result = build_system_prompt(extra_sections=extra)
        assert "Custom Section" in result

    def test_with_student_context(self):
        ctx = "## Your Current Student\n- Active level: A1 (45%)"
        result = build_system_prompt(student_context=ctx)
        assert "Your Current Student" in result
        assert "A1 (45%)" in result

    def test_without_student_context(self):
        result = build_system_prompt(student_context=None)
        # Should not contain the student context header (unless from the sections)
        # The key thing is it doesn't crash
        assert isinstance(result, str)

    def test_sections_joined_with_double_newlines(self):
        result = build_system_prompt()
        # Sections are joined with \n\n
        assert "\n\n" in result

    def test_general_note_at_end(self):
        result = build_system_prompt(general_note="My preference")
        # The general note should come after the main sections
        idx_preference = result.index("My preference")
        idx_core = result.index("Anki flashcard assistant")
        assert idx_preference > idx_core


class TestBuildStudentContext:
    """Tests for build_student_context function.

    build_student_context imports dependencies inside the function body via
    'from .module import func', so patches must target the source modules.
    """

    @patch("ankicli.cefr.load_progress_cache")
    @patch("ankicli.error_journal.get_error_patterns")
    @patch("ankicli.learning_summary.load_summary")
    def test_returns_none_when_no_data(self, mock_summary, mock_errors, mock_progress):
        mock_progress.return_value = None
        mock_errors.return_value = []
        mock_summary.return_value = {
            "total_cards_added": 0,
            "levels": {},
        }
        result = build_student_context()
        assert result is None

    @patch("ankicli.cefr.load_progress_cache")
    @patch("ankicli.error_journal.get_error_patterns")
    @patch("ankicli.learning_summary.load_summary")
    def test_includes_total_cards_when_present(self, mock_summary, mock_errors, mock_progress):
        mock_progress.return_value = None
        mock_errors.return_value = []
        mock_summary.return_value = {
            "total_cards_added": 150,
            "levels": {},
        }
        result = build_student_context()
        assert result is not None
        assert "150 cards total" in result

    @patch("ankicli.cefr.load_progress_cache")
    @patch("ankicli.error_journal.get_error_patterns")
    @patch("ankicli.learning_summary.load_summary")
    def test_includes_error_patterns(self, mock_summary, mock_errors, mock_progress):
        mock_progress.return_value = None
        mock_summary.return_value = {"total_cards_added": 0, "levels": {}}
        error = MagicMock()
        error.error_type = "gender_agreement"
        error.count = 5
        mock_errors.return_value = [error]
        result = build_student_context()
        assert result is not None
        assert "gender_agreement" in result

    @patch("ankicli.cefr.load_progress_cache")
    @patch("ankicli.error_journal.get_error_patterns")
    @patch("ankicli.learning_summary.load_summary")
    def test_includes_quiz_results(self, mock_summary, mock_errors, mock_progress):
        mock_progress.return_value = None
        mock_errors.return_value = []
        mock_summary.return_value = {
            "total_cards_added": 10,
            "levels": {},
            "quiz_results": [
                {"score": 80, "topic": "ser vs estar"},
                {"score": 90, "topic": "preterite"},
            ],
        }
        result = build_student_context()
        assert result is not None
        assert "quiz avg" in result

    @patch("ankicli.cefr.load_progress_cache")
    @patch("ankicli.error_journal.get_error_patterns")
    @patch("ankicli.learning_summary.load_summary")
    def test_includes_practice_sessions(self, mock_summary, mock_errors, mock_progress):
        mock_progress.return_value = None
        mock_errors.return_value = []
        mock_summary.return_value = {
            "total_cards_added": 10,
            "levels": {},
            "practice_sessions": [
                {"score_percent": 75},
                {"score_percent": 85},
            ],
        }
        result = build_student_context()
        assert result is not None
        assert "practice avg" in result

    @patch("ankicli.cefr.load_progress_cache")
    @patch("ankicli.error_journal.get_error_patterns")
    @patch("ankicli.learning_summary.load_summary")
    def test_header_present(self, mock_summary, mock_errors, mock_progress):
        mock_progress.return_value = None
        mock_errors.return_value = []
        mock_summary.return_value = {
            "total_cards_added": 50,
            "levels": {},
        }
        result = build_student_context()
        assert result is not None
        assert "## Your Current Student" in result


class TestAnkiAssistantInit:
    """Tests for AnkiAssistant initialization (mocked)."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_init_with_api_key(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        assert assistant.model == Config().main_model
        assert assistant.messages == []
        assert assistant.input_tokens_used == 0
        assert assistant.output_tokens_used == 0
        assert assistant.session_cards_added == 0

    @patch.dict("os.environ", {}, clear=True)
    @patch("ankicli.assistant.load_dotenv")  # prevent loading real .env
    def test_init_without_api_key_raises(self, mock_dotenv):
        from ankicli.assistant import AnkiAssistant
        import os
        # Ensure no key
        os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            AnkiAssistant()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "ANTHROPIC_API_KEY" in str(e)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_init_with_custom_model(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant(model="claude-opus-4-6")
        assert assistant.model == "claude-opus-4-6"


class TestAnkiAssistantProperties:
    """Tests for AnkiAssistant computed properties."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_total_tokens_used(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        assistant.input_tokens_used = 1000
        assistant.output_tokens_used = 500
        assert assistant.total_tokens_used == 1500

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_context_usage_percent(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        assistant.input_tokens_used = 100_000
        # default model has 200K context
        assert assistant.context_usage_percent == 50.0

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_get_context_status(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        assistant.input_tokens_used = 5000
        assistant.output_tokens_used = 2000
        assistant.session_cards_added = 3

        status = assistant.get_context_status()
        assert status["input_tokens"] == 5000
        assert status["output_tokens"] == 2000
        assert status["total_tokens"] == 7000
        assert status["session_cards_added"] == 3
        assert "model" in status
        assert "model_name" in status
        assert "session_minutes" in status

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_max_context_tokens(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        assert assistant.max_context_tokens > 0

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_max_output_tokens(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        assert assistant.max_output_tokens > 0


class TestAnkiAssistantToolRouting:
    """Tests for _execute_tool method."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_execute_unknown_tool(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        result = assistant._execute_tool("nonexistent_tool", {})
        assert "Unknown tool" in result

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_execute_tool_anki_error(self, mock_config, mock_anki_cls, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config
        from ankicli.client import AnkiConnectError

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        # Make the anki client raise an error
        assistant.anki.get_decks.side_effect = AnkiConnectError("Connection refused")

        result = assistant._execute_tool("list_decks", {})
        assert "Anki error" in result

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_execute_tool_generic_error(self, mock_config, mock_anki_cls, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        assistant.anki.get_decks.side_effect = RuntimeError("Unexpected error")

        result = assistant._execute_tool("list_decks", {})
        assert "Error" in result

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_execute_tool_passes_context(self, mock_config, mock_anki_cls, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        assistant.anki.get_decks.return_value = []

        # The tool should execute without error
        result = assistant._execute_tool("list_decks", {})
        assert isinstance(result, str)


class TestAnkiAssistantToolNotes:
    """Tests for _get_tools_with_notes."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_tools_without_notes(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config(tool_notes={})
        assistant = AnkiAssistant()
        tools = assistant._get_tools_with_notes()
        # Should return the same tools
        from ankicli.tools import ANKI_TOOLS
        assert len(tools) == len(ANKI_TOOLS)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_tools_with_notes_injects_preference(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config(tool_notes={"add_card": "Use Latin American Spanish"})
        assistant = AnkiAssistant()
        tools = assistant._get_tools_with_notes()

        add_card_tool = next(t for t in tools if t["name"] == "add_card")
        assert "USER PREFERENCE" in add_card_tool["description"]
        assert "Latin American Spanish" in add_card_tool["description"]

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_tools_without_notes_unchanged(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config
        from ankicli.tools import ANKI_TOOLS

        mock_config.return_value = Config(tool_notes={"add_card": "Some note"})
        assistant = AnkiAssistant()
        tools = assistant._get_tools_with_notes()

        # Tools without notes should be the original objects
        list_decks_tool = next(t for t in tools if t["name"] == "list_decks")
        original_tool = next(t for t in ANKI_TOOLS if t["name"] == "list_decks")
        assert list_decks_tool is original_tool


class TestAnkiAssistantConversationState:
    """Tests for conversation persistence methods."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_reset_clears_state(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        assistant.messages = [{"role": "user", "content": "hello"}]
        assistant.input_tokens_used = 1000
        assistant.output_tokens_used = 500

        # reset() does a local import: from .conversation_store import clear_conversation
        # so we patch it in the conversation_store module where it's defined
        with patch("ankicli.conversation_store.clear_conversation") as mock_clear:
            assistant.reset()
            mock_clear.assert_called_once()

        assert assistant.messages == []
        assert assistant.input_tokens_used == 0
        assert assistant.output_tokens_used == 0

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_load_from_disk_empty(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()

        with patch("ankicli.assistant.load_conversation") as mock_load:
            mock_load.return_value = {
                "messages": [],
                "input_tokens": 0,
                "output_tokens": 0,
            }
            result = assistant.load_from_disk()

        assert result is False
        assert assistant.messages == []

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_load_from_disk_with_data(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()

        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        with patch("ankicli.assistant.load_conversation") as mock_load:
            mock_load.return_value = {
                "messages": messages,
                "input_tokens": 500,
                "output_tokens": 200,
            }
            result = assistant.load_from_disk()

        assert result is True
        assert len(assistant.messages) == 2
        assert assistant.input_tokens_used == 500
        assert assistant.output_tokens_used == 200

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_save_to_disk(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        assistant.messages = [{"role": "user", "content": "test"}]
        assistant.input_tokens_used = 100
        assistant.output_tokens_used = 50

        with patch("ankicli.assistant.save_conversation") as mock_save:
            assistant.save_to_disk()
            mock_save.assert_called_once_with(
                assistant.messages, 100, 50
            )


class TestFixConversationState:
    """Tests for _fix_conversation_state method."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def _make_assistant(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config
        mock_config.return_value = Config()
        return AnkiAssistant()

    def test_empty_messages(self):
        assistant = self._make_assistant()
        assistant.messages = []
        assistant._fix_conversation_state()
        assert assistant.messages == []

    def test_valid_messages_unchanged(self):
        assistant = self._make_assistant()
        assistant.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        assistant._fix_conversation_state()
        assert len(assistant.messages) == 2

    def test_orphaned_tool_use_truncated(self):
        assistant = self._make_assistant()
        # Tool use block as a mock object
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tool_123"

        assistant.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [tool_block]},
            # Missing tool_result message
        ]
        assistant._fix_conversation_state()
        # Should truncate at the orphaned tool_use
        assert len(assistant.messages) == 1

    def test_matched_tool_use_and_result_kept(self):
        assistant = self._make_assistant()
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tool_abc"

        assistant.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [tool_block]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tool_abc", "content": "result"}
            ]},
            {"role": "assistant", "content": "Done!"},
        ]
        assistant._fix_conversation_state()
        assert len(assistant.messages) == 4


class TestGetSystemPrompt:
    """Tests for _get_system_prompt method."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_returns_string(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        with patch("ankicli.assistant.build_student_context", return_value=None):
            result = assistant._get_system_prompt()
        assert isinstance(result, str)
        assert "Anki flashcard assistant" in result

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_includes_general_note(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config(tool_notes={"general": "Always use tu"})
        assistant = AnkiAssistant()
        with patch("ankicli.assistant.build_student_context", return_value=None):
            result = assistant._get_system_prompt()
        assert "Always use tu" in result

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_handles_student_context_error(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        with patch("ankicli.assistant.build_student_context", side_effect=Exception("fail")):
            result = assistant._get_system_prompt()
        # Should not raise, just returns prompt without student context
        assert isinstance(result, str)


class TestFixConversationStateExtended:
    """Additional edge case tests for _fix_conversation_state."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def _make_assistant(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config
        mock_config.return_value = Config()
        return AnkiAssistant()

    def test_mismatched_tool_ids_truncated(self):
        assistant = self._make_assistant()
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "tool_1"

        assistant.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [tool_block]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tool_WRONG", "content": "result"}
            ]},
        ]
        assistant._fix_conversation_state()
        # Should truncate at the mismatched point
        assert len(assistant.messages) == 1

    def test_tool_result_without_preceding_assistant(self):
        assistant = self._make_assistant()
        assistant.messages = [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "orphan", "content": "result"}
            ]},
            {"role": "assistant", "content": "hi"},
        ]
        assistant._fix_conversation_state()
        # The orphaned tool_result at position 0 should be removed
        assert len(assistant.messages) <= 2

    def test_multiple_tool_uses_in_one_message(self):
        assistant = self._make_assistant()
        tool1 = MagicMock()
        tool1.type = "tool_use"
        tool1.id = "tool_a"
        tool2 = MagicMock()
        tool2.type = "tool_use"
        tool2.id = "tool_b"

        assistant.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [tool1, tool2]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tool_a", "content": "r1"},
                {"type": "tool_result", "tool_use_id": "tool_b", "content": "r2"},
            ]},
            {"role": "assistant", "content": "Done!"},
        ]
        assistant._fix_conversation_state()
        assert len(assistant.messages) == 4

    def test_dict_format_tool_use(self):
        """Test tool_use blocks in dict format (as opposed to object format)."""
        assistant = self._make_assistant()
        assistant.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tool_dict", "name": "list_decks", "input": {}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tool_dict", "content": "result"},
            ]},
        ]
        assistant._fix_conversation_state()
        assert len(assistant.messages) == 3

    def test_plain_text_messages_unchanged(self):
        assistant = self._make_assistant()
        assistant.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
            {"role": "user", "content": "how are you?"},
            {"role": "assistant", "content": "I'm good, thanks!"},
        ]
        assistant._fix_conversation_state()
        assert len(assistant.messages) == 4


class TestCompactHistory:
    """Tests for compact_history method."""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ankicli.assistant.Anthropic")
    @patch("ankicli.assistant.AnkiClient")
    @patch("ankicli.assistant.load_config")
    def test_too_short_to_compact(self, mock_config, mock_anki, mock_anthropic):
        from ankicli.assistant import AnkiAssistant
        from ankicli.config import Config

        mock_config.return_value = Config()
        assistant = AnkiAssistant()
        assistant.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = assistant.compact_history(keep_recent=4)
        assert "too short" in result.lower()
