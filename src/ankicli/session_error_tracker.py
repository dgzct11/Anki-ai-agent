"""Within-session error pattern tracking (P10).

Tracks errors during a practice/quiz session and flags when the
same error type occurs 2+ times.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionError:
    """A single error occurrence within a session."""

    error_type: str
    example: str
    correction: str = ""


@dataclass
class SessionErrorTracker:
    """Track errors within a single session and flag repeated patterns.

    Usage:
        tracker = SessionErrorTracker()
        tracker.record("gender_agreement", "la problema", "el problema")
        tracker.record("gender_agreement", "la sistema", "el sistema")
        # Now tracker.get_flagged_patterns() returns gender_agreement
    """

    errors: list[SessionError] = field(default_factory=list)
    _flagged: set[str] = field(default_factory=set)

    def record(self, error_type: str, example: str, correction: str = "") -> str | None:
        """Record an error and return a flag message if pattern detected.

        Args:
            error_type: Category of error (e.g. "gender_agreement")
            example: The incorrect text
            correction: The correct version

        Returns:
            A flag message string if this error type has occurred 2+ times
            in this session, otherwise None.
        """
        self.errors.append(SessionError(
            error_type=error_type,
            example=example,
            correction=correction,
        ))

        count = self.count_type(error_type)
        if count >= 2 and error_type not in self._flagged:
            self._flagged.add(error_type)
            examples = [e for e in self.errors if e.error_type == error_type]
            example_strs = []
            for e in examples[-3:]:  # Show last 3 examples
                if e.correction:
                    example_strs.append(f"'{e.example}' -> '{e.correction}'")
                else:
                    example_strs.append(f"'{e.example}'")
            return (
                f"Pattern detected: you're consistently making "
                f"'{_format_error_type(error_type)}' errors "
                f"({count}x this session). "
                f"Examples: {', '.join(example_strs)}"
            )
        return None

    def count_type(self, error_type: str) -> int:
        """Count occurrences of an error type in this session."""
        return sum(1 for e in self.errors if e.error_type == error_type)

    def get_error_counts(self) -> dict[str, int]:
        """Get counts of each error type."""
        counts: dict[str, int] = {}
        for e in self.errors:
            counts[e.error_type] = counts.get(e.error_type, 0) + 1
        return counts

    def get_flagged_patterns(self) -> list[str]:
        """Get error types that have been flagged (2+ occurrences)."""
        return sorted(self._flagged)

    def get_session_summary(self) -> str:
        """Get a summary of error patterns for this session."""
        counts = self.get_error_counts()
        if not counts:
            return "No error patterns detected this session."

        lines = ["Session error patterns:"]
        for error_type, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
            flagged = " [FLAGGED]" if error_type in self._flagged else ""
            lines.append(f"  - {_format_error_type(error_type)}: {count}x{flagged}")
        return "\n".join(lines)

    def reset(self) -> None:
        """Reset the tracker for a new session."""
        self.errors.clear()
        self._flagged.clear()


def _format_error_type(error_type: str) -> str:
    """Format a snake_case error type into readable text."""
    return error_type.replace("_", " ").replace("vs", "vs.")
