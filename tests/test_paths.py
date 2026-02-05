"""Tests for paths module - centralized path definitions."""

from pathlib import Path

from ankicli.paths import (
    DATA_DIR,
    CONFIG_FILE,
    CONVERSATION_FILE,
    CHAT_LOG_FILE,
    SUMMARY_FILE,
    PROGRESS_FILE,
    CEFR_DATA_DIR,
    CEFR_VOCAB_DIR,
    CEFR_GRAMMAR_DIR,
    CEFR_CACHE_FILE,
    ERROR_JOURNAL_FILE,
    DAILY_CHALLENGE_FILE,
    HISTORY_FILE,
    ensure_data_dir,
)


class TestPathDefinitions:
    """Tests that all paths are properly defined."""

    def test_data_dir_is_path(self):
        assert isinstance(DATA_DIR, Path)

    def test_config_file_in_data_dir(self):
        assert CONFIG_FILE.parent == DATA_DIR

    def test_conversation_file_in_data_dir(self):
        assert CONVERSATION_FILE.parent == DATA_DIR

    def test_chat_log_file_in_data_dir(self):
        assert CHAT_LOG_FILE.parent == DATA_DIR

    def test_summary_file_in_data_dir(self):
        assert SUMMARY_FILE.parent == DATA_DIR

    def test_progress_file_in_data_dir(self):
        assert PROGRESS_FILE.parent == DATA_DIR

    def test_cefr_cache_file_in_data_dir(self):
        assert CEFR_CACHE_FILE.parent == DATA_DIR

    def test_history_file_in_data_dir(self):
        assert HISTORY_FILE.parent == DATA_DIR

    def test_error_journal_file_in_data_dir(self):
        assert ERROR_JOURNAL_FILE.parent == DATA_DIR

    def test_daily_challenge_file_in_data_dir(self):
        assert DAILY_CHALLENGE_FILE.parent == DATA_DIR

    def test_cefr_data_dir_is_path(self):
        assert isinstance(CEFR_DATA_DIR, Path)

    def test_cefr_vocab_dir_under_cefr_data(self):
        assert CEFR_VOCAB_DIR.parent == CEFR_DATA_DIR

    def test_cefr_grammar_dir_under_cefr_data(self):
        assert CEFR_GRAMMAR_DIR.parent == CEFR_DATA_DIR

    def test_file_extensions(self):
        assert CONFIG_FILE.suffix == ".json"
        assert CONVERSATION_FILE.suffix == ".json"
        assert CHAT_LOG_FILE.suffix == ".json"
        assert SUMMARY_FILE.suffix == ".json"
        assert PROGRESS_FILE.suffix == ".json"
        assert CEFR_CACHE_FILE.suffix == ".json"
        assert ERROR_JOURNAL_FILE.suffix == ".json"
        assert DAILY_CHALLENGE_FILE.suffix == ".json"


class TestEnsureDataDir:
    """Tests for ensure_data_dir."""

    def test_ensure_data_dir_creates_directory(self, tmp_path):
        from unittest.mock import patch
        test_dir = tmp_path / "test_data"
        with patch("ankicli.paths.DATA_DIR", test_dir):
            ensure_data_dir()
            assert test_dir.exists()
            assert test_dir.is_dir()

    def test_ensure_data_dir_idempotent(self, tmp_path):
        from unittest.mock import patch
        test_dir = tmp_path / "test_data"
        with patch("ankicli.paths.DATA_DIR", test_dir):
            ensure_data_dir()
            ensure_data_dir()  # Should not raise
            assert test_dir.exists()
