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
    WORD_NETWORK_FILE,
    DISAMBIGUATION_FILE,
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

    def test_word_network_file_in_data_dir(self):
        assert WORD_NETWORK_FILE.parent == DATA_DIR

    def test_disambiguation_file_in_data_dir(self):
        assert DISAMBIGUATION_FILE.parent == DATA_DIR

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
        assert WORD_NETWORK_FILE.suffix == ".json"
        assert DISAMBIGUATION_FILE.suffix == ".json"


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


class TestAtomicJsonWrite:
    """Regression tests for atomic_json_write (temp+rename pattern)."""

    def test_writes_valid_json(self, tmp_path):
        from ankicli.paths import atomic_json_write
        import json
        target = tmp_path / "test.json"
        data = {"key": "value", "numbers": [1, 2, 3]}
        atomic_json_write(target, data)
        assert target.exists()
        with open(target) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_no_leftover_temp_files(self, tmp_path):
        from ankicli.paths import atomic_json_write
        target = tmp_path / "test.json"
        atomic_json_write(target, {"ok": True})
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0, f"Leftover temp files: {tmp_files}"

    def test_creates_parent_directories(self, tmp_path):
        from ankicli.paths import atomic_json_write
        target = tmp_path / "sub" / "dir" / "test.json"
        atomic_json_write(target, {"nested": True})
        assert target.exists()

    def test_overwrites_existing_file(self, tmp_path):
        from ankicli.paths import atomic_json_write
        import json
        target = tmp_path / "test.json"
        atomic_json_write(target, {"version": 1})
        atomic_json_write(target, {"version": 2})
        with open(target) as f:
            loaded = json.load(f)
        assert loaded["version"] == 2
