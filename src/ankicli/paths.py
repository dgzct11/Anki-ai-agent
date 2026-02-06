"""Centralized storage paths for ankicli."""

import json
import os
import tempfile
from pathlib import Path

# Base data directory for all persistent storage
DATA_DIR = Path(__file__).parent.parent.parent / ".ankicli"

# Configuration
CONFIG_FILE = DATA_DIR / "config.json"

# Conversation persistence
CONVERSATION_FILE = DATA_DIR / "conversation.json"

# Chat log (readable history)
CHAT_LOG_FILE = DATA_DIR / "chat_log.json"

# Learning summary
SUMMARY_FILE = DATA_DIR / "learning_summary.json"

# Progress tracking
PROGRESS_FILE = DATA_DIR / "progress.json"

# CEFR data (bundled with package)
CEFR_DATA_DIR = Path(__file__).parent / "data" / "cefr"
CEFR_VOCAB_DIR = CEFR_DATA_DIR / "vocabulary"
CEFR_GRAMMAR_DIR = CEFR_DATA_DIR / "grammar"

# CEFR progress cache
CEFR_CACHE_FILE = DATA_DIR / "cefr_progress_cache.json"

# Word network
WORD_NETWORK_FILE = DATA_DIR / "word_network.json"

# Disambiguation pairs
DISAMBIGUATION_FILE = DATA_DIR / "disambiguation.json"

# Error journal
ERROR_JOURNAL_FILE = DATA_DIR / "error_journal.json"

# Daily challenge state
DAILY_CHALLENGE_FILE = DATA_DIR / "daily_challenge.json"

# Chat input history (prompt_toolkit)
HISTORY_FILE = DATA_DIR / "chat_history"

# Study streaks
STREAKS_FILE = DATA_DIR / "streaks.json"

# Time-based progress history
PROGRESS_HISTORY_FILE = DATA_DIR / "progress_history.json"

# New vocab staging list
VOCAB_LIST_FILE = DATA_DIR / "new_vocab.json"


def ensure_data_dir() -> None:
    """Ensure the data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def atomic_json_write(path: Path, data, *, indent: int = 2, ensure_ascii: bool = False) -> None:
    """Write JSON data to a file atomically.

    Writes to a temporary file in the same directory, then renames it
    to the target path. This prevents data loss if a crash occurs mid-write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        os.rename(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
