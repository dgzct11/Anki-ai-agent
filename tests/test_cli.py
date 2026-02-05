"""Tests for cli module - Click command registration and basic behavior."""

from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from ankicli.cli import cli


class TestCLIGroup:
    """Tests for the top-level CLI group."""

    def test_cli_group_exists(self):
        assert cli is not None

    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Anki CLI" in result.output

    def test_cli_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0


class TestCLICommands:
    """Tests that all expected commands are registered."""

    def _get_command_names(self):
        return list(cli.commands.keys())

    def test_chat_command_registered(self):
        assert "chat" in self._get_command_names()

    def test_practice_command_registered(self):
        assert "practice" in self._get_command_names()

    def test_quiz_command_registered(self):
        assert "quiz" in self._get_command_names()

    def test_converse_command_registered(self):
        assert "converse" in self._get_command_names()

    def test_model_command_registered(self):
        assert "model" in self._get_command_names()

    def test_status_command_registered(self):
        assert "status" in self._get_command_names()

    def test_decks_command_registered(self):
        assert "decks" in self._get_command_names()

    def test_add_command_registered(self):
        assert "add" in self._get_command_names()

    def test_search_command_registered(self):
        assert "search" in self._get_command_names()

    def test_note_types_command_registered(self):
        assert "note-types" in self._get_command_names()

    def test_bulk_add_command_registered(self):
        assert "bulk-add" in self._get_command_names()

    def test_sync_command_registered(self):
        assert "sync" in self._get_command_names()

    def test_create_deck_command_registered(self):
        assert "create-deck" in self._get_command_names()

    def test_cards_command_registered(self):
        assert "cards" in self._get_command_names()

    def test_notes_group_registered(self):
        assert "notes" in self._get_command_names()

    def test_cefr_group_registered(self):
        assert "cefr" in self._get_command_names()

    def test_errors_command_registered(self):
        assert "errors" in self._get_command_names()

    def test_daily_command_registered(self):
        assert "daily" in self._get_command_names()


class TestCLICommandHelp:
    """Tests that all commands have help text."""

    def test_chat_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["chat", "--help"])
        assert result.exit_code == 0
        assert "interactive" in result.output.lower() or "chat" in result.output.lower()

    def test_practice_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["practice", "--help"])
        assert result.exit_code == 0
        assert "translation" in result.output.lower() or "practice" in result.output.lower()

    def test_quiz_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["quiz", "--help"])
        assert result.exit_code == 0
        assert "grammar" in result.output.lower() or "quiz" in result.output.lower()

    def test_model_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["model", "--help"])
        assert result.exit_code == 0
        assert "model" in result.output.lower()

    def test_status_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])
        assert result.exit_code == 0

    def test_decks_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["decks", "--help"])
        assert result.exit_code == 0

    def test_search_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0

    def test_daily_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["daily", "--help"])
        assert result.exit_code == 0
        assert "daily" in result.output.lower() or "challenge" in result.output.lower()


class TestModelCommand:
    """Tests for the model command."""

    @patch("ankicli.cli.load_config")
    def test_model_show_current(self, mock_config):
        from ankicli.config import Config
        mock_config.return_value = Config()

        runner = CliRunner()
        result = runner.invoke(cli, ["model"])
        assert result.exit_code == 0
        assert "Current model" in result.output or "model" in result.output.lower()

    @patch("ankicli.cli.save_config")
    @patch("ankicli.cli.load_config")
    def test_model_switch_valid(self, mock_config, mock_save):
        from ankicli.config import Config
        mock_config.return_value = Config()

        runner = CliRunner()
        result = runner.invoke(cli, ["model", "claude-opus-4-6"])
        assert result.exit_code == 0
        assert "Switched" in result.output or "Opus" in result.output

    @patch("ankicli.cli.load_config")
    def test_model_switch_invalid(self, mock_config):
        from ankicli.config import Config
        mock_config.return_value = Config()

        runner = CliRunner()
        result = runner.invoke(cli, ["model", "nonexistent-model"])
        assert result.exit_code != 0 or "Unknown" in result.output


class TestStatusCommand:
    """Tests for the status command."""

    @patch("ankicli.cli.AnkiClient")
    def test_status_connected(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Connected" in result.output

    @patch("ankicli.cli.AnkiClient")
    def test_status_not_connected(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.ping.return_value = False
        mock_client_cls.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
        assert result.exit_code != 0
        assert "Cannot connect" in result.output


class TestDecksCommand:
    """Tests for the decks command."""

    @patch("ankicli.cli.get_client")
    def test_decks_empty(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get_decks.return_value = []
        mock_get_client.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["decks"])
        assert result.exit_code == 0
        assert "No decks" in result.output

    @patch("ankicli.cli.get_client")
    def test_decks_with_decks(self, mock_get_client):
        mock_client = MagicMock()
        deck = MagicMock()
        deck.name = "Spanish"
        deck.new_count = 5
        deck.learn_count = 3
        deck.review_count = 10
        deck.total_due = 18
        mock_client.get_decks.return_value = [deck]
        mock_get_client.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["decks"])
        assert result.exit_code == 0
        assert "Spanish" in result.output


class TestNotesSubcommands:
    """Tests for the notes subcommand group."""

    def test_notes_subcommands_exist(self):
        from ankicli.cli import notes
        subcmds = list(notes.commands.keys())
        assert "list" in subcmds
        assert "set" in subcmds
        assert "remove" in subcmds
        assert "clear" in subcmds

    @patch("ankicli.cli.load_config")
    def test_notes_list(self, mock_config):
        from ankicli.config import Config
        mock_config.return_value = Config(tool_notes={"general": "test note"})

        runner = CliRunner()
        result = runner.invoke(cli, ["notes", "list"])
        assert result.exit_code == 0
        assert "test note" in result.output

    @patch("ankicli.cli.save_config")
    @patch("ankicli.cli.load_config")
    def test_notes_set(self, mock_config, mock_save):
        from ankicli.config import Config
        mock_config.return_value = Config()

        runner = CliRunner()
        result = runner.invoke(cli, ["notes", "set", "general", "Use informal"])
        assert result.exit_code == 0
        assert "saved" in result.output.lower()

    @patch("ankicli.cli.save_config")
    @patch("ankicli.cli.load_config")
    def test_notes_clear_empty(self, mock_config, mock_save):
        from ankicli.config import Config
        mock_config.return_value = Config(tool_notes={})

        runner = CliRunner()
        result = runner.invoke(cli, ["notes", "clear"])
        assert result.exit_code == 0


class TestCEFRSubcommands:
    """Tests for the cefr subcommand group."""

    def test_cefr_subcommands_exist(self):
        from ankicli.cli import cefr
        subcmds = list(cefr.commands.keys())
        assert "status" in subcmds
        assert "progress" in subcmds
        assert "suggest" in subcmds
        assert "scan" in subcmds


class TestProgressCommand:
    """Tests for the progress command."""

    def test_progress_command_registered(self):
        assert "progress" in list(cli.commands.keys())

    def test_progress_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["progress", "--help"])
        assert result.exit_code == 0
        assert "progress" in result.output.lower() or "streak" in result.output.lower()


class TestErrorsCommand:
    """Tests for the errors command."""

    @patch("ankicli.error_journal.get_error_patterns")
    @patch("ankicli.error_journal.format_error_patterns_text")
    def test_errors_output(self, mock_format, mock_patterns):
        mock_patterns.return_value = []
        mock_format.return_value = "No error patterns recorded."

        runner = CliRunner()
        result = runner.invoke(cli, ["errors"])
        assert result.exit_code == 0


class TestPracticeCommandArgs:
    """Tests for the practice command argument parsing."""

    def test_practice_help_has_direction(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["practice", "--help"])
        assert result.exit_code == 0
        assert "direction" in result.output.lower()

    def test_practice_help_has_count(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["practice", "--help"])
        assert result.exit_code == 0
        assert "count" in result.output.lower()

    def test_practice_help_has_focus(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["practice", "--help"])
        assert result.exit_code == 0
        assert "focus" in result.output.lower()


class TestQuizCommandArgs:
    """Tests for the quiz command argument parsing."""

    def test_quiz_help_has_level(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["quiz", "--help"])
        assert result.exit_code == 0
        assert "level" in result.output.lower()

    def test_quiz_help_has_topic(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["quiz", "--help"])
        assert result.exit_code == 0
        assert "topic" in result.output.lower()

    def test_quiz_help_has_count(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["quiz", "--help"])
        assert result.exit_code == 0
        assert "count" in result.output.lower()


class TestConverseCommandArgs:
    """Tests for the converse command argument parsing."""

    def test_converse_help_has_scenario(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["converse", "--help"])
        assert result.exit_code == 0
        assert "scenario" in result.output.lower()

    def test_converse_help_has_level(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["converse", "--help"])
        assert result.exit_code == 0
        assert "level" in result.output.lower()

    def test_converse_help_has_character(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["converse", "--help"])
        assert result.exit_code == 0
        assert "character" in result.output.lower()


class TestSearchCommand:
    """Tests for the search command."""

    @patch("ankicli.cli.get_client")
    def test_search_no_results(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search_cards.return_value = []
        mock_get_client.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["search", "nonexistent"])
        assert result.exit_code == 0
        assert "No cards" in result.output

    @patch("ankicli.cli.get_client")
    def test_search_with_results(self, mock_get_client):
        mock_client = MagicMock()
        card = MagicMock()
        card.front = "hello"
        card.back = "hola"
        card.tags = ["word::hola"]
        mock_client.search_cards.return_value = [card]
        mock_get_client.return_value = mock_client

        runner = CliRunner()
        result = runner.invoke(cli, ["search", "deck:Spanish"])
        assert result.exit_code == 0
        assert "hello" in result.output

    @patch("ankicli.cli.get_client")
    def test_search_respects_limit(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search_cards.return_value = []
        mock_get_client.return_value = mock_client

        runner = CliRunner()
        runner.invoke(cli, ["search", "test", "-l", "5"])
        mock_client.search_cards.assert_called_once_with("test", limit=5)


class TestModelCommandExtended:
    """Extended tests for the model command."""

    @patch("ankicli.cli.save_config")
    @patch("ankicli.cli.load_config")
    def test_model_partial_match(self, mock_config, mock_save):
        from ankicli.config import Config
        mock_config.return_value = Config()

        runner = CliRunner()
        result = runner.invoke(cli, ["model", "opus"])
        # Should match claude-opus-4-6
        assert result.exit_code == 0
        assert "Opus" in result.output or "Switched" in result.output

    @patch("ankicli.cli.load_config")
    def test_model_shows_available_models(self, mock_config):
        from ankicli.config import Config
        mock_config.return_value = Config()

        runner = CliRunner()
        result = runner.invoke(cli, ["model"])
        assert result.exit_code == 0
        assert "Available" in result.output or "Model" in result.output


class TestNotesSubcommandsExtended:
    """Extended tests for notes subcommands."""

    @patch("ankicli.cli.save_config")
    @patch("ankicli.cli.load_config")
    def test_notes_remove_nonexistent(self, mock_config, mock_save):
        from ankicli.config import Config
        mock_config.return_value = Config(tool_notes={})

        runner = CliRunner()
        result = runner.invoke(cli, ["notes", "remove", "nonexistent"])
        assert result.exit_code != 0 or "No preference" in result.output

    @patch("ankicli.cli.save_config")
    @patch("ankicli.cli.load_config")
    def test_notes_remove_existing(self, mock_config, mock_save):
        from ankicli.config import Config
        mock_config.return_value = Config(tool_notes={"general": "test"})

        runner = CliRunner()
        result = runner.invoke(cli, ["notes", "remove", "general"])
        assert result.exit_code == 0
        assert "removed" in result.output.lower()

    @patch("ankicli.cli.save_config")
    @patch("ankicli.cli.load_config")
    def test_notes_clear_with_notes(self, mock_config, mock_save):
        from ankicli.config import Config
        mock_config.return_value = Config(tool_notes={"general": "a", "add_card": "b"})

        runner = CliRunner()
        result = runner.invoke(cli, ["notes", "clear"])
        assert result.exit_code == 0
        assert "2" in result.output or "Cleared" in result.output


class TestCEFRSubcommandsHelp:
    """Tests for CEFR subcommand help text."""

    def test_cefr_status_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["cefr", "status", "--help"])
        assert result.exit_code == 0

    def test_cefr_progress_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["cefr", "progress", "--help"])
        assert result.exit_code == 0
        assert "unknown" in result.output.lower() or "level" in result.output.lower()

    def test_cefr_suggest_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["cefr", "suggest", "--help"])
        assert result.exit_code == 0
        assert "level" in result.output.lower() or "count" in result.output.lower()

    def test_cefr_scan_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["cefr", "scan", "--help"])
        assert result.exit_code == 0
        assert "deck" in result.output.lower() or "scan" in result.output.lower()


class TestDailyCommandHelp:
    """Tests for daily command help."""

    def test_daily_has_force_option(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["daily", "--help"])
        assert result.exit_code == 0
        assert "force" in result.output.lower()
