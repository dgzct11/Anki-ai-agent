"""Chat log storage for readable history."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_DIR = Path(__file__).parent.parent.parent / ".ankicli"
LOG_FILE = LOG_DIR / "chat_log.json"

# Maximum number of exchanges to keep
MAX_EXCHANGES = 100


def _ensure_dir():
    """Ensure the log directory exists."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def load_log() -> list[dict]:
    """Load the chat log from disk."""
    _ensure_dir()
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_log(log: list[dict]) -> None:
    """Save the chat log to disk."""
    _ensure_dir()
    # Keep only the most recent exchanges
    log = log[-MAX_EXCHANGES:]
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def add_exchange(
    user_message: str,
    assistant_response: str,
    tool_calls: Optional[list[dict]] = None
) -> None:
    """
    Add a chat exchange to the log.

    Args:
        user_message: The user's input
        assistant_response: The assistant's text response
        tool_calls: List of tool calls with 'name' and 'summary' keys
    """
    log = load_log()

    exchange = {
        "timestamp": datetime.now().isoformat(),
        "user": user_message,
        "assistant": assistant_response,
        "tools": tool_calls or []
    }

    log.append(exchange)
    save_log(log)


def get_recent_exchanges(count: int = 10) -> list[dict]:
    """Get the most recent exchanges."""
    log = load_log()
    return log[-count:]


def format_exchange_for_display(exchange: dict, index: int) -> str:
    """Format a single exchange for display."""
    lines = []

    # Timestamp
    timestamp = exchange.get("timestamp", "")
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            time_str = timestamp[:16]
    else:
        time_str = "unknown"

    lines.append(f"─── Exchange {index} ({time_str}) ───")

    # User message
    user_msg = exchange.get("user", "")
    if len(user_msg) > 100:
        user_msg = user_msg[:100] + "..."
    lines.append(f"You: {user_msg}")

    # Tool calls
    tools = exchange.get("tools", [])
    if tools:
        for t in tools[:5]:
            name = t.get("name", "?")
            summary = t.get("summary", "")
            if summary:
                lines.append(f"  → {name}: {summary}")
            else:
                lines.append(f"  → {name}")
        if len(tools) > 5:
            lines.append(f"  → (+{len(tools) - 5} more tools)")

    # Assistant response
    assistant_msg = exchange.get("assistant", "")
    if len(assistant_msg) > 200:
        assistant_msg = assistant_msg[:200] + "..."
    # Clean up markdown for display
    assistant_msg = assistant_msg.replace("\n", " ").strip()
    lines.append(f"Assistant: {assistant_msg}")

    return "\n".join(lines)


def format_history_for_display(count: int = 10) -> str:
    """Format recent history for display."""
    exchanges = get_recent_exchanges(count)

    if not exchanges:
        return "No chat history yet."

    output = []
    output.append("=" * 60)
    output.append(f"RECENT CHAT HISTORY ({len(exchanges)} exchanges)")
    output.append("=" * 60)

    for i, exchange in enumerate(exchanges, 1):
        output.append("")
        output.append(format_exchange_for_display(exchange, i))

    output.append("")
    output.append("=" * 60)

    return "\n".join(output)


def clear_log() -> None:
    """Clear the chat log."""
    save_log([])
