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

# CEFR data
CEFR_DATA_DIR = Path(__file__).parent / "data"
CEFR_SPANISH_FILE = CEFR_DATA_DIR / "cefr_spanish.json"

# CEFR progress cache
CEFR_CACHE_FILE = DATA_DIR / "cefr_progress_cache.json"

# Chat input history (prompt_toolkit)
HISTORY_FILE = DATA_DIR / "chat_history"


def ensure_data_dir() -> None:
    """Ensure the data directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
