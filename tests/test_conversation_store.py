"""Tests for conversation_store module."""

import json
from pathlib import Path
from unittest.mock import patch

from ankicli.conversation_store import (
    save_conversation,
    load_conversation,
    clear_conversation,
    get_conversation_age,
)


def _patch_conv_paths(tmp_path):
    """Create patches for conversation_store module paths."""
    data_dir = tmp_path / ".ankicli"
    conv_file = data_dir / "conversation.json"
    return (
        patch("ankicli.conversation_store.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
        patch("ankicli.conversation_store.CONVERSATION_FILE", conv_file),
    )


class TestSaveAndLoad:
    """Tests for saving and loading conversations."""

    def test_save_and_load_simple(self, tmp_path):
        p1, p2 = _patch_conv_paths(tmp_path)
        with p1, p2:
            messages = [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ]
            save_conversation(messages, input_tokens=100, output_tokens=50)

            data = load_conversation()
            assert len(data["messages"]) == 2
            assert data["messages"][0]["role"] == "user"
            assert data["messages"][0]["content"] == "hello"
            assert data["input_tokens"] == 100
            assert data["output_tokens"] == 50
            assert data["last_saved"] is not None

    def test_load_empty(self, tmp_path):
        p1, p2 = _patch_conv_paths(tmp_path)
        with p1, p2:
            data = load_conversation()
            assert data["messages"] == []
            assert data["input_tokens"] == 0
            assert data["output_tokens"] == 0
            assert data["last_saved"] is None

    def test_load_handles_corrupt_file(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        data_dir.mkdir(parents=True)
        conv_file = data_dir / "conversation.json"
        conv_file.write_text("not valid json")

        with patch("ankicli.conversation_store.ensure_data_dir", lambda: None), \
             patch("ankicli.conversation_store.CONVERSATION_FILE", conv_file):
            data = load_conversation()
            assert data["messages"] == []

    def test_save_with_list_content(self, tmp_path):
        p1, p2 = _patch_conv_paths(tmp_path)
        with p1, p2:
            messages = [
                {"role": "user", "content": "hello"},
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Let me check."},
                    ],
                },
            ]
            save_conversation(messages)
            data = load_conversation()
            assert len(data["messages"]) == 2
            assert data["messages"][1]["content"][0]["type"] == "text"

    def test_save_with_tool_result_content(self, tmp_path):
        p1, p2 = _patch_conv_paths(tmp_path)
        with p1, p2:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "abc123",
                            "content": "Card added",
                        }
                    ],
                },
            ]
            save_conversation(messages)
            data = load_conversation()
            assert data["messages"][0]["content"][0]["type"] == "tool_result"


class TestClearConversation:
    """Tests for clear_conversation."""

    def test_clear(self, tmp_path):
        p1, p2 = _patch_conv_paths(tmp_path)
        with p1, p2:
            save_conversation([{"role": "user", "content": "hi"}])
            conv_file = tmp_path / ".ankicli" / "conversation.json"
            assert conv_file.exists()
            clear_conversation()
            assert not conv_file.exists()

    def test_clear_nonexistent(self, tmp_path):
        p1, p2 = _patch_conv_paths(tmp_path)
        with p1, p2:
            # Should not raise
            clear_conversation()


class TestGetConversationAge:
    """Tests for get_conversation_age."""

    def test_no_conversation(self, tmp_path):
        p1, p2 = _patch_conv_paths(tmp_path)
        with p1, p2:
            age = get_conversation_age()
            assert age is None

    def test_recent_conversation(self, tmp_path):
        p1, p2 = _patch_conv_paths(tmp_path)
        with p1, p2:
            save_conversation([{"role": "user", "content": "hi"}])
            age = get_conversation_age()
            assert age is not None
            assert "just now" in age or "minute" in age or "second" in age
