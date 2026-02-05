"""Persistent error journal for tracking recurring mistakes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from .paths import ERROR_JOURNAL_FILE, ensure_data_dir


@dataclass
class ErrorEntry:
    """A recurring error pattern."""

    error_type: str  # e.g., "gender_agreement", "ser_vs_estar", "accent_missing"
    count: int = 0
    examples: list[dict] = field(default_factory=list)  # [{input, correction, context}]
    last_seen: str = ""
    first_seen: str = ""
    tags: list[str] = field(default_factory=list)  # e.g., ["grammar", "A2"]

    def to_dict(self) -> dict:
        return {
            "error_type": self.error_type,
            "count": self.count,
            "examples": self.examples,
            "last_seen": self.last_seen,
            "first_seen": self.first_seen,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ErrorEntry:
        return cls(
            error_type=data.get("error_type", ""),
            count=data.get("count", 0),
            examples=data.get("examples", []),
            last_seen=data.get("last_seen", ""),
            first_seen=data.get("first_seen", ""),
            tags=data.get("tags", []),
        )


def load_journal() -> dict[str, ErrorEntry]:
    """Load the error journal from disk.

    Returns:
        Dict mapping error_type to ErrorEntry.
    """
    ensure_data_dir()
    if not ERROR_JOURNAL_FILE.exists():
        return {}
    try:
        with open(ERROR_JOURNAL_FILE) as f:
            raw = json.load(f)
        return {k: ErrorEntry.from_dict(v) for k, v in raw.items()}
    except (json.JSONDecodeError, IOError):
        return {}


def save_journal(journal: dict[str, ErrorEntry]) -> None:
    """Save the error journal to disk."""
    ensure_data_dir()
    raw = {k: v.to_dict() for k, v in journal.items()}
    with open(ERROR_JOURNAL_FILE, "w") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)


def log_error(
    error_type: str,
    example: str,
    correction: str = "",
    context: str = "",
    tags: list[str] | None = None,
) -> ErrorEntry:
    """Log a new error occurrence.

    Args:
        error_type: Category of the error (e.g., "gender_agreement")
        example: The user's incorrect text
        correction: The correct version
        context: Additional context (e.g., "translation practice", "quiz")
        tags: Optional tags (e.g., ["grammar", "A2"])

    Returns:
        The updated ErrorEntry.
    """
    journal = load_journal()
    now = datetime.now().isoformat()

    entry = journal.get(error_type)
    if entry is None:
        entry = ErrorEntry(
            error_type=error_type,
            first_seen=now,
            tags=tags or [],
        )

    entry.count += 1
    entry.last_seen = now

    # Add example (keep last 10)
    example_record = {"input": example, "correction": correction, "context": context}
    entry.examples.append(example_record)
    entry.examples = entry.examples[-10:]

    # Merge tags
    if tags:
        for t in tags:
            if t not in entry.tags:
                entry.tags.append(t)

    journal[error_type] = entry
    save_journal(journal)
    return entry


def get_error_patterns(
    min_count: int = 1,
    limit: int = 20,
) -> list[ErrorEntry]:
    """Get error patterns sorted by frequency.

    Args:
        min_count: Minimum occurrences to include.
        limit: Maximum entries to return.

    Returns:
        List of ErrorEntry sorted by count (descending).
    """
    journal = load_journal()
    entries = [e for e in journal.values() if e.count >= min_count]
    entries.sort(key=lambda e: e.count, reverse=True)
    return entries[:limit]


def format_error_patterns_text(entries: list[ErrorEntry]) -> str:
    """Format error patterns as plain text for tool results."""
    if not entries:
        return "No error patterns recorded yet."

    lines = [f"Error Journal - {len(entries)} pattern(s):\n"]
    for e in entries:
        lines.append(f"  {e.error_type} (x{e.count})")
        if e.tags:
            lines.append(f"    Tags: {', '.join(e.tags)}")
        if e.examples:
            latest = e.examples[-1]
            lines.append(f"    Latest: '{latest.get('input', '')}' -> '{latest.get('correction', '')}'")
        lines.append(f"    Last seen: {e.last_seen[:16]}")
        lines.append("")

    return "\n".join(lines)
