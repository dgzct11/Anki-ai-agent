"""Per-topic grammar scoring across sessions.

Tracks scores per grammar topic across quiz sessions.
Stored in .ankicli/grammar_scores.json.

Mastery levels:
  - Below 70%: needs_review
  - 70-85%: developing
  - 85%+: mastered
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime

from .paths import DATA_DIR, ensure_data_dir, atomic_json_write

GRAMMAR_SCORES_FILE = DATA_DIR / "grammar_scores.json"

# Mastery thresholds
NEEDS_REVIEW_THRESHOLD = 70.0
DEVELOPING_THRESHOLD = 85.0


def mastery_label(score: float) -> str:
    """Return mastery level label for a score percentage."""
    if score >= DEVELOPING_THRESHOLD:
        return "mastered"
    elif score >= NEEDS_REVIEW_THRESHOLD:
        return "developing"
    return "needs_review"


@dataclass
class TopicScore:
    """Score tracking for a single grammar topic."""

    topic: str
    total_questions: int = 0
    total_correct: int = 0
    sessions: int = 0
    last_score: float = 0.0
    last_session: str = ""
    cefr_level: str = ""

    @property
    def average_score(self) -> float:
        if self.total_questions == 0:
            return 0.0
        return (self.total_correct / self.total_questions) * 100

    @property
    def mastery_level(self) -> str:
        return mastery_label(self.average_score)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["average_score"] = self.average_score
        d["mastery_level"] = self.mastery_level
        return d

    @classmethod
    def from_dict(cls, data: dict) -> TopicScore:
        return cls(
            topic=data.get("topic", ""),
            total_questions=data.get("total_questions", 0),
            total_correct=data.get("total_correct", 0),
            sessions=data.get("sessions", 0),
            last_score=data.get("last_score", 0.0),
            last_session=data.get("last_session", ""),
            cefr_level=data.get("cefr_level", ""),
        )


def load_grammar_scores() -> dict[str, TopicScore]:
    """Load per-topic grammar scores from disk."""
    ensure_data_dir()
    if not GRAMMAR_SCORES_FILE.exists():
        return {}
    try:
        with open(GRAMMAR_SCORES_FILE) as f:
            raw = json.load(f)
        return {k: TopicScore.from_dict(v) for k, v in raw.items()}
    except (json.JSONDecodeError, IOError):
        return {}


def save_grammar_scores(scores: dict[str, TopicScore]) -> None:
    """Save per-topic grammar scores to disk."""
    ensure_data_dir()
    raw = {k: v.to_dict() for k, v in scores.items()}
    atomic_json_write(GRAMMAR_SCORES_FILE, raw)


def record_topic_score(
    topic: str,
    cefr_level: str,
    questions: int,
    correct: int,
) -> TopicScore:
    """Record a quiz result for a grammar topic.

    Args:
        topic: Grammar topic name
        cefr_level: CEFR level (A1-B2)
        questions: Number of questions attempted
        correct: Number of correct answers

    Returns:
        Updated TopicScore for the topic.
    """
    scores = load_grammar_scores()
    now = datetime.now().isoformat()

    entry = scores.get(topic)
    if entry is None:
        entry = TopicScore(topic=topic, cefr_level=cefr_level)

    entry.total_questions += questions
    entry.total_correct += correct
    entry.sessions += 1
    entry.last_score = (correct / questions * 100) if questions > 0 else 0.0
    entry.last_session = now
    entry.cefr_level = cefr_level

    scores[topic] = entry
    save_grammar_scores(scores)
    return entry


def get_all_topic_scores() -> dict[str, TopicScore]:
    """Get all topic scores."""
    return load_grammar_scores()


def format_grammar_scores_text(scores: dict[str, TopicScore] | None = None) -> str:
    """Format grammar scores as readable text.

    Shows percentage per topic with mastery levels.
    """
    if scores is None:
        scores = load_grammar_scores()

    if not scores:
        return "No grammar scores recorded yet. Take a quiz to start tracking!"

    lines = ["Grammar Score Breakdown:", ""]

    # Group by CEFR level
    by_level: dict[str, list[TopicScore]] = {}
    for ts in scores.values():
        level = ts.cefr_level or "Unknown"
        by_level.setdefault(level, []).append(ts)

    for level in sorted(by_level.keys()):
        lines.append(f"  {level}:")
        topic_scores = sorted(by_level[level], key=lambda t: t.average_score, reverse=True)
        for ts in topic_scores:
            avg = ts.average_score
            label = ts.mastery_level
            indicator = {
                "mastered": "[M]",
                "developing": "[D]",
                "needs_review": "[!]",
            }.get(label, "[?]")
            lines.append(
                f"    {indicator} {ts.topic}: {avg:.0f}% "
                f"({ts.total_correct}/{ts.total_questions} across {ts.sessions} session(s))"
            )
        lines.append("")

    # Summary
    all_scores = list(scores.values())
    mastered = sum(1 for s in all_scores if s.mastery_level == "mastered")
    developing = sum(1 for s in all_scores if s.mastery_level == "developing")
    needs_review = sum(1 for s in all_scores if s.mastery_level == "needs_review")
    lines.append(
        f"  Summary: {mastered} mastered, {developing} developing, "
        f"{needs_review} needs review"
    )

    return "\n".join(lines)
