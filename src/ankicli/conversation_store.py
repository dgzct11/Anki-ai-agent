"""Persistent conversation storage."""

import json
from datetime import datetime

from .paths import CONVERSATION_FILE, ensure_data_dir, atomic_json_write


def _serialize_message(msg: dict) -> dict:
    """Serialize a message for JSON storage."""
    serialized = {"role": msg["role"]}
    content = msg.get("content")

    if isinstance(content, str):
        serialized["content"] = content
    elif isinstance(content, list):
        serialized_content = []
        for block in content:
            if isinstance(block, dict):
                serialized_content.append(block)
            elif hasattr(block, "type"):
                # Handle Anthropic message blocks
                if block.type == "text":
                    serialized_content.append({
                        "type": "text",
                        "text": block.text
                    })
                elif block.type == "tool_use":
                    serialized_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })
                elif block.type == "tool_result":
                    serialized_content.append({
                        "type": "tool_result",
                        "tool_use_id": getattr(block, "tool_use_id", ""),
                        "content": getattr(block, "content", "")
                    })
            else:
                serialized_content.append(block)
        serialized["content"] = serialized_content
    else:
        serialized["content"] = content

    return serialized


def save_conversation(messages: list[dict], input_tokens: int = 0, output_tokens: int = 0) -> None:
    """Save conversation history to disk."""
    ensure_data_dir()

    # Serialize messages
    serialized_messages = [_serialize_message(msg) for msg in messages]

    data = {
        "last_saved": datetime.now().isoformat(),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "messages": serialized_messages,
    }

    atomic_json_write(CONVERSATION_FILE, data)


def load_conversation() -> dict:
    """
    Load conversation history from disk.

    Returns:
        Dict with 'messages', 'input_tokens', 'output_tokens', 'last_saved'
    """
    ensure_data_dir()

    if not CONVERSATION_FILE.exists():
        return {
            "messages": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "last_saved": None,
        }

    try:
        with open(CONVERSATION_FILE) as f:
            data = json.load(f)
        return {
            "messages": data.get("messages", []),
            "input_tokens": data.get("input_tokens", 0),
            "output_tokens": data.get("output_tokens", 0),
            "last_saved": data.get("last_saved"),
        }
    except (json.JSONDecodeError, IOError):
        return {
            "messages": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "last_saved": None,
        }


def clear_conversation() -> None:
    """Delete saved conversation."""
    if CONVERSATION_FILE.exists():
        CONVERSATION_FILE.unlink()


def get_conversation_age() -> str | None:
    """Get human-readable age of saved conversation."""
    if not CONVERSATION_FILE.exists():
        return None

    try:
        with open(CONVERSATION_FILE) as f:
            data = json.load(f)
        last_saved = data.get("last_saved")
        if not last_saved:
            return None

        saved_time = datetime.fromisoformat(last_saved)
        delta = datetime.now() - saved_time

        if delta.days > 0:
            return f"{delta.days} day(s) ago"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600} hour(s) ago"
        elif delta.seconds > 60:
            return f"{delta.seconds // 60} minute(s) ago"
        else:
            return "just now"
    except Exception:
        return None
