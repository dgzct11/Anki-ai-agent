"""Tests for chat_log module."""

import json
from pathlib import Path
from unittest.mock import patch

from ankicli.chat_log import (
    load_log,
    save_log,
    add_exchange,
    get_recent_exchanges,
    format_exchange_for_display,
    format_history_for_display,
    clear_log,
    MAX_EXCHANGES,
)


def _patch_chat_log_paths(tmp_path):
    """Create patches for chat_log module paths."""
    data_dir = tmp_path / ".ankicli"
    log_file = data_dir / "chat_log.json"
    return (
        patch("ankicli.chat_log.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
        patch("ankicli.chat_log.CHAT_LOG_FILE", log_file),
    )


class TestLoadSaveLog:
    """Tests for load and save operations."""

    def test_load_empty_log(self, tmp_path):
        p1, p2 = _patch_chat_log_paths(tmp_path)
        with p1, p2:
            log = load_log()
            assert log == []

    def test_save_and_load(self, tmp_path):
        p1, p2 = _patch_chat_log_paths(tmp_path)
        with p1, p2:
            entries = [
                {"timestamp": "2026-01-01T10:00:00", "user": "hello", "assistant": "hi", "tools": []},
            ]
            save_log(entries)
            loaded = load_log()
            assert len(loaded) == 1
            assert loaded[0]["user"] == "hello"

    def test_save_truncates_at_max(self, tmp_path):
        p1, p2 = _patch_chat_log_paths(tmp_path)
        with p1, p2:
            entries = [
                {"timestamp": f"2026-01-01T{i:02d}:00:00", "user": f"msg{i}", "assistant": f"resp{i}", "tools": []}
                for i in range(MAX_EXCHANGES + 20)
            ]
            save_log(entries)
            loaded = load_log()
            assert len(loaded) == MAX_EXCHANGES
            # Should keep the most recent
            assert loaded[-1]["user"] == f"msg{MAX_EXCHANGES + 19}"

    def test_load_handles_corrupt_file(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        data_dir.mkdir(parents=True)
        log_file = data_dir / "chat_log.json"
        log_file.write_text("corrupt data")

        with patch("ankicli.chat_log.ensure_data_dir", lambda: None), \
             patch("ankicli.chat_log.CHAT_LOG_FILE", log_file):
            log = load_log()
            assert log == []


class TestAddExchange:
    """Tests for add_exchange."""

    def test_add_exchange(self, tmp_path):
        p1, p2 = _patch_chat_log_paths(tmp_path)
        with p1, p2:
            add_exchange("hello", "hi there")
            log = load_log()
            assert len(log) == 1
            assert log[0]["user"] == "hello"
            assert log[0]["assistant"] == "hi there"
            assert log[0]["tools"] == []
            assert "timestamp" in log[0]

    def test_add_exchange_with_tools(self, tmp_path):
        p1, p2 = _patch_chat_log_paths(tmp_path)
        with p1, p2:
            tools = [{"name": "add_card", "summary": "'hablar'"}]
            add_exchange("add a card", "done", tools)
            log = load_log()
            assert len(log[0]["tools"]) == 1
            assert log[0]["tools"][0]["name"] == "add_card"

    def test_add_multiple_exchanges(self, tmp_path):
        p1, p2 = _patch_chat_log_paths(tmp_path)
        with p1, p2:
            add_exchange("msg1", "resp1")
            add_exchange("msg2", "resp2")
            add_exchange("msg3", "resp3")
            log = load_log()
            assert len(log) == 3


class TestGetRecentExchanges:
    """Tests for get_recent_exchanges."""

    def test_get_recent(self, tmp_path):
        p1, p2 = _patch_chat_log_paths(tmp_path)
        with p1, p2:
            for i in range(10):
                add_exchange(f"msg{i}", f"resp{i}")
            recent = get_recent_exchanges(3)
            assert len(recent) == 3
            assert recent[0]["user"] == "msg7"

    def test_get_recent_from_empty(self, tmp_path):
        p1, p2 = _patch_chat_log_paths(tmp_path)
        with p1, p2:
            recent = get_recent_exchanges(5)
            assert recent == []


class TestFormatting:
    """Tests for formatting functions."""

    def test_format_exchange(self):
        exchange = {
            "timestamp": "2026-01-15T14:30:00",
            "user": "Add a card for 'hablar'",
            "assistant": "I'll add that card now.",
            "tools": [{"name": "add_card", "summary": "'hablar'"}],
        }
        display = format_exchange_for_display(exchange, 1)
        assert "Exchange 1" in display
        assert "2026-01-15 14:30" in display
        assert "hablar" in display
        assert "add_card" in display

    def test_format_exchange_truncates_long_messages(self):
        exchange = {
            "timestamp": "2026-01-15T14:30:00",
            "user": "x" * 200,
            "assistant": "y" * 400,
            "tools": [],
        }
        display = format_exchange_for_display(exchange, 1)
        assert "..." in display

    def test_format_history_empty(self, tmp_path):
        p1, p2 = _patch_chat_log_paths(tmp_path)
        with p1, p2:
            display = format_history_for_display()
            assert "No chat history yet" in display

    def test_format_history_with_entries(self, tmp_path):
        p1, p2 = _patch_chat_log_paths(tmp_path)
        with p1, p2:
            add_exchange("hello", "hi")
            display = format_history_for_display()
            assert "RECENT CHAT HISTORY" in display
            assert "1 exchanges" in display


class TestClearLog:
    """Tests for clear_log."""

    def test_clear(self, tmp_path):
        p1, p2 = _patch_chat_log_paths(tmp_path)
        with p1, p2:
            add_exchange("hello", "hi")
            assert len(load_log()) == 1
            clear_log()
            assert len(load_log()) == 0
