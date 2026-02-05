"""Centralized storage paths for ankicli."""

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


def ensure_data_dir() -> None:
    """Ensure the data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
