"""Progress tracking module: streaks, skills radar, time-based progress, weak spots."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from .paths import STREAKS_FILE, PROGRESS_HISTORY_FILE, ensure_data_dir, atomic_json_write


# ---------------------------------------------------------------------------
# P5: Study Streaks
# ---------------------------------------------------------------------------

def _load_streaks() -> dict:
    """Load streaks data from disk."""
    ensure_data_dir()
    if not STREAKS_FILE.exists():
        return {"dates": [], "longest_streak": 0}
    try:
        with open(STREAKS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"dates": [], "longest_streak": 0}


def _save_streaks(data: dict) -> None:
    """Save streaks data to disk."""
    ensure_data_dir()
    atomic_json_write(STREAKS_FILE, data)


def record_activity(activity_date: date | None = None) -> dict:
    """Record study activity for a given date.

    Args:
        activity_date: Date of activity (defaults to today).

    Returns:
        Updated streaks summary with current_streak and longest_streak.
    """
    if activity_date is None:
        activity_date = date.today()

    data = _load_streaks()
    date_str = activity_date.isoformat()

    dates = set(data.get("dates", []))
    dates.add(date_str)
    data["dates"] = sorted(dates)

    # Recalculate streaks
    current = get_current_streak(data)
    longest = get_longest_streak(data)
    data["longest_streak"] = longest

    _save_streaks(data)

    return {
        "date_recorded": date_str,
        "current_streak": current,
        "longest_streak": longest,
        "total_active_days": len(data["dates"]),
    }


def get_current_streak(data: dict | None = None) -> int:
    """Get the current consecutive-day streak ending today or yesterday.

    Args:
        data: Pre-loaded streaks data (loads from disk if None).

    Returns:
        Number of consecutive days in the current streak.
    """
    if data is None:
        data = _load_streaks()

    dates_str = data.get("dates", [])
    if not dates_str:
        return 0

    date_set = set()
    for d in dates_str:
        try:
            date_set.add(date.fromisoformat(d))
        except ValueError:
            continue

    if not date_set:
        return 0

    today = date.today()
    # Streak must include today or yesterday to be "current"
    if today not in date_set and (today - timedelta(days=1)) not in date_set:
        return 0

    # Count backwards from the most recent active day
    start = today if today in date_set else today - timedelta(days=1)
    streak = 0
    current = start
    while current in date_set:
        streak += 1
        current -= timedelta(days=1)

    return streak


def get_longest_streak(data: dict | None = None) -> int:
    """Get the longest ever consecutive-day streak.

    Args:
        data: Pre-loaded streaks data (loads from disk if None).

    Returns:
        Number of consecutive days in the longest streak.
    """
    if data is None:
        data = _load_streaks()

    dates_str = data.get("dates", [])
    if not dates_str:
        return 0

    sorted_dates = []
    for d in dates_str:
        try:
            sorted_dates.append(date.fromisoformat(d))
        except ValueError:
            continue

    if not sorted_dates:
        return 0

    sorted_dates.sort()

    longest = 1
    current_run = 1

    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] - sorted_dates[i - 1] == timedelta(days=1):
            current_run += 1
        elif sorted_dates[i] != sorted_dates[i - 1]:
            current_run = 1
        longest = max(longest, current_run)

    return longest


def get_streaks_summary() -> dict:
    """Get a full streaks summary for display.

    Returns:
        Dict with current_streak, longest_streak, total_active_days,
        last_7_days activity, last_30_days count.
    """
    data = _load_streaks()
    dates_str = set(data.get("dates", []))
    today = date.today()

    # Last 7 days activity map
    last_7 = {}
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        last_7[d.isoformat()] = d.isoformat() in dates_str

    # Last 30 days count
    last_30_count = 0
    for i in range(30):
        d = today - timedelta(days=i)
        if d.isoformat() in dates_str:
            last_30_count += 1

    return {
        "current_streak": get_current_streak(data),
        "longest_streak": get_longest_streak(data),
        "total_active_days": len(dates_str),
        "last_7_days": last_7,
        "last_30_days_active": last_30_count,
    }


# ---------------------------------------------------------------------------
# P6: Skills Radar
# ---------------------------------------------------------------------------

def get_skills_radar(
    collection_stats: dict | None = None,
    learning_summary: dict | None = None,
    error_journal_entries: list | None = None,
    quiz_results: list | None = None,
    cefr_progress: dict | None = None,
) -> dict:
    """Compute proficiency across 5 skill dimensions.

    Dimensions (each scored 0-100):
        1. vocabulary_breadth: CEFR coverage across levels
        2. grammar_accuracy: Average quiz scores
        3. productive_skill: Translation practice scores
        4. topic_coverage: Proportion of themes with learned words
        5. retention: Anki retention rate

    Args:
        collection_stats: From AnkiClient.get_collection_stats()
        learning_summary: From load_summary()
        error_journal_entries: From get_error_patterns()
        quiz_results: Quiz results list from learning_summary
        cefr_progress: From CEFR progress cache

    Returns:
        Dict with dimension scores and overall average.
    """
    dimensions: dict[str, float] = {}

    # 1. Vocabulary breadth from CEFR progress
    vocab_score = 0.0
    if cefr_progress:
        total_pct = 0.0
        count = 0
        # Weight lower levels more (A1 matters more for beginners)
        weights = {"A1": 3, "A2": 2.5, "B1": 2, "B2": 1.5, "C1": 1, "C2": 0.5}
        total_weight = 0.0
        for level_key, weight in weights.items():
            level_data = cefr_progress.get(level_key, {})
            pct = level_data.get("percent", 0)
            total_pct += pct * weight
            total_weight += weight
            count += 1
        if total_weight > 0:
            vocab_score = min(100.0, total_pct / total_weight)
    dimensions["vocabulary_breadth"] = round(vocab_score, 1)

    # 2. Grammar accuracy from quiz results
    grammar_score = 0.0
    if quiz_results:
        recent_quizzes = quiz_results[-10:]  # last 10 quizzes
        if recent_quizzes:
            scores = [q.get("score", 0) for q in recent_quizzes]
            grammar_score = sum(scores) / len(scores)
    dimensions["grammar_accuracy"] = round(grammar_score, 1)

    # 3. Productive skill from practice sessions
    productive_score = 0.0
    if learning_summary:
        sessions = learning_summary.get("practice_sessions", [])
        recent_sessions = sessions[-10:]
        if recent_sessions:
            scores = [s.get("score_percent", 0) for s in recent_sessions]
            productive_score = sum(scores) / len(scores)
    dimensions["productive_skill"] = round(productive_score, 1)

    # 4. Topic coverage
    topic_score = 0.0
    if cefr_progress:
        total_cats = 0
        cats_with_progress = 0
        for level_key in ("A1", "A2", "B1", "B2"):
            level_data = cefr_progress.get(level_key, {})
            categories = level_data.get("categories", {})
            for cat_name, cat_data in categories.items():
                total_cats += 1
                if cat_data.get("percent", 0) > 10:  # at least 10% covered
                    cats_with_progress += 1
        if total_cats > 0:
            topic_score = (cats_with_progress / total_cats) * 100
    dimensions["topic_coverage"] = round(topic_score, 1)

    # 5. Retention from Anki stats
    retention_score = 0.0
    if collection_stats:
        retention_score = collection_stats.get("retention_rate", 0.0)
    dimensions["retention"] = round(retention_score, 1)

    # Overall average
    if dimensions:
        overall = sum(dimensions.values()) / len(dimensions)
    else:
        overall = 0.0

    return {
        "dimensions": dimensions,
        "overall": round(overall, 1),
    }


# ---------------------------------------------------------------------------
# P7: Time-Based Progress
# ---------------------------------------------------------------------------

def _load_progress_history() -> list[dict]:
    """Load time-based progress snapshots from disk."""
    ensure_data_dir()
    if not PROGRESS_HISTORY_FILE.exists():
        return []
    try:
        with open(PROGRESS_HISTORY_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_progress_history(history: list[dict]) -> None:
    """Save progress history to disk."""
    ensure_data_dir()
    atomic_json_write(PROGRESS_HISTORY_FILE, history)


def record_progress_snapshot(
    total_cards: int = 0,
    cefr_levels: dict | None = None,
    retention_rate: float = 0.0,
    snapshot_date: date | None = None,
) -> dict:
    """Record a point-in-time progress snapshot.

    Args:
        total_cards: Total cards in collection.
        cefr_levels: Dict of level -> percent coverage.
        retention_rate: Current retention rate.
        snapshot_date: Date of snapshot (defaults to today).

    Returns:
        The recorded snapshot.
    """
    if snapshot_date is None:
        snapshot_date = date.today()

    history = _load_progress_history()

    snapshot = {
        "date": snapshot_date.isoformat(),
        "total_cards": total_cards,
        "cefr_levels": cefr_levels or {},
        "retention_rate": retention_rate,
        "timestamp": datetime.now().isoformat(),
    }

    # Replace existing snapshot for the same date if any
    history = [h for h in history if h.get("date") != snapshot_date.isoformat()]
    history.append(snapshot)
    history.sort(key=lambda h: h.get("date", ""))

    # Keep up to 365 days of history
    history = history[-365:]

    _save_progress_history(history)
    return snapshot


def get_progress_over_time(period: str = "month") -> dict:
    """Get progress data grouped by time period.

    Args:
        period: "week" or "month".

    Returns:
        Dict with time_series (list of period summaries),
        cards_trend, cefr_trend.
    """
    history = _load_progress_history()
    if not history:
        return {
            "period": period,
            "time_series": [],
            "total_snapshots": 0,
        }

    today = date.today()

    if period == "week":
        # Last 12 weeks
        buckets: dict[str, list[dict]] = {}
        for snap in history:
            try:
                snap_date = date.fromisoformat(snap["date"])
            except (ValueError, KeyError):
                continue
            # ISO week label
            year, week, _ = snap_date.isocalendar()
            key = f"{year}-W{week:02d}"
            buckets.setdefault(key, []).append(snap)
    else:
        # Last 12 months
        buckets = {}
        for snap in history:
            try:
                snap_date = date.fromisoformat(snap["date"])
            except (ValueError, KeyError):
                continue
            key = snap_date.strftime("%Y-%m")
            buckets.setdefault(key, []).append(snap)

    time_series = []
    for key in sorted(buckets.keys())[-12:]:
        snaps = buckets[key]
        # Use the latest snapshot in each period
        latest = max(snaps, key=lambda s: s.get("date", ""))
        earliest = min(snaps, key=lambda s: s.get("date", ""))

        cards_added = latest.get("total_cards", 0) - earliest.get("total_cards", 0)

        time_series.append({
            "period": key,
            "total_cards": latest.get("total_cards", 0),
            "cards_added_in_period": max(0, cards_added),
            "cefr_levels": latest.get("cefr_levels", {}),
            "retention_rate": latest.get("retention_rate", 0),
            "snapshots_count": len(snaps),
        })

    return {
        "period": period,
        "time_series": time_series,
        "total_snapshots": len(history),
    }


# ---------------------------------------------------------------------------
# P8: Weak Spots Dashboard
# ---------------------------------------------------------------------------

def get_weak_spots(
    quiz_results: list | None = None,
    error_entries: list | None = None,
    card_reviews: list | None = None,
) -> dict:
    """Aggregate weakest areas across quiz, errors, and Anki data.

    Args:
        quiz_results: Quiz results from learning_summary.
        error_entries: Error patterns from error_journal.
        card_reviews: Card review data from client.get_card_reviews().

    Returns:
        Dict with weak_grammar, weak_vocabulary, forgotten_cards sections.
    """
    weak_grammar: list[dict] = []
    weak_vocabulary: list[dict] = []
    forgotten_cards: list[dict] = []

    # 1. Grammar topics with lowest quiz scores
    if quiz_results:
        # Group by topic, get average score
        topic_scores: dict[str, list[float]] = {}
        for qr in quiz_results:
            topic = qr.get("topic", "unknown")
            score = qr.get("score", 0)
            topic_scores.setdefault(topic, []).append(score)

        for topic, scores in topic_scores.items():
            avg = sum(scores) / len(scores)
            if avg < 85:  # Below mastery threshold
                weak_grammar.append({
                    "topic": topic,
                    "avg_score": round(avg, 1),
                    "attempts": len(scores),
                    "last_score": scores[-1],
                })

        weak_grammar.sort(key=lambda x: x["avg_score"])
        weak_grammar = weak_grammar[:10]

    # 2. Vocabulary themes with highest error rates
    if error_entries:
        for entry in error_entries:
            if hasattr(entry, "error_type"):
                weak_vocabulary.append({
                    "error_type": entry.error_type,
                    "count": entry.count,
                    "tags": entry.tags,
                    "last_seen": entry.last_seen,
                })
            elif isinstance(entry, dict):
                weak_vocabulary.append({
                    "error_type": entry.get("error_type", ""),
                    "count": entry.get("count", 0),
                    "tags": entry.get("tags", []),
                    "last_seen": entry.get("last_seen", ""),
                })
        weak_vocabulary.sort(key=lambda x: x["count"], reverse=True)
        weak_vocabulary = weak_vocabulary[:10]

    # 3. Most-forgotten cards (high lapses, low ease factor)
    if card_reviews:
        for review in card_reviews:
            lapses = review.get("lapses", 0)
            ease = review.get("ease", 2500)
            reps = review.get("reps", 0)
            if lapses >= 2 or (ease > 0 and ease < 2000 and reps > 0):
                forgotten_cards.append({
                    "card_id": review.get("card_id"),
                    "note_id": review.get("note_id"),
                    "lapses": lapses,
                    "ease_factor": ease,
                    "reps": reps,
                    "interval": review.get("interval", 0),
                })

        forgotten_cards.sort(key=lambda x: (-x["lapses"], x["ease_factor"]))
        forgotten_cards = forgotten_cards[:15]

    return {
        "weak_grammar": weak_grammar,
        "weak_vocabulary": weak_vocabulary,
        "forgotten_cards": forgotten_cards,
        "summary": _format_weak_spots_summary(weak_grammar, weak_vocabulary, forgotten_cards),
    }


def _format_weak_spots_summary(
    weak_grammar: list[dict],
    weak_vocabulary: list[dict],
    forgotten_cards: list[dict],
) -> str:
    """Format weak spots as a text summary."""
    lines = ["Weak Spots Dashboard", "=" * 40]

    if weak_grammar:
        lines.append("\nGrammar Topics Needing Work:")
        for g in weak_grammar[:5]:
            lines.append(
                f"  - {g['topic']}: {g['avg_score']:.0f}% avg "
                f"({g['attempts']} attempts, last: {g['last_score']:.0f}%)"
            )
    else:
        lines.append("\nGrammar: No weak spots detected (or no quiz data yet)")

    if weak_vocabulary:
        lines.append("\nRecurring Error Patterns:")
        for v in weak_vocabulary[:5]:
            tags_str = ", ".join(v["tags"]) if v["tags"] else ""
            lines.append(f"  - {v['error_type']} (x{v['count']}){' [' + tags_str + ']' if tags_str else ''}")
    else:
        lines.append("\nVocabulary: No error patterns detected yet")

    if forgotten_cards:
        lines.append(f"\nMost-Forgotten Cards ({len(forgotten_cards)} cards with high lapse count):")
        for c in forgotten_cards[:5]:
            lines.append(
                f"  - Card {c['note_id']}: {c['lapses']} lapses, "
                f"ease {c['ease_factor'] / 1000:.1f}x, {c['reps']} reps"
            )
    else:
        lines.append("\nForgotten cards: No problematic cards detected")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_skills_radar_text(radar: dict) -> str:
    """Format skills radar as plain text."""
    dims = radar.get("dimensions", {})
    lines = [
        "Skills Radar",
        "=" * 40,
        "",
    ]

    labels = {
        "vocabulary_breadth": "Vocabulary Breadth",
        "grammar_accuracy": "Grammar Accuracy",
        "productive_skill": "Productive Skill",
        "topic_coverage": "Topic Coverage",
        "retention": "Retention",
    }

    for key, label in labels.items():
        score = dims.get(key, 0)
        bar_len = int(score / 5)  # 20 chars max
        bar = "#" * bar_len + "-" * (20 - bar_len)
        lines.append(f"  {label:<22} [{bar}] {score:.0f}%")

    lines.append(f"\n  Overall: {radar.get('overall', 0):.0f}%")
    return "\n".join(lines)


def format_progress_over_time_text(progress: dict) -> str:
    """Format time-based progress as plain text."""
    series = progress.get("time_series", [])
    period = progress.get("period", "month")

    if not series:
        return "No progress history recorded yet. Progress snapshots are taken automatically during study sessions."

    lines = [
        f"Progress Over Time ({period}ly)",
        "=" * 40,
        "",
    ]

    for entry in series:
        p = entry["period"]
        cards = entry.get("total_cards", 0)
        added = entry.get("cards_added_in_period", 0)
        retention = entry.get("retention_rate", 0)

        cefr = entry.get("cefr_levels", {})
        cefr_parts = []
        for level in ("A1", "A2", "B1", "B2"):
            pct = cefr.get(level, 0)
            if pct > 0:
                cefr_parts.append(f"{level}:{pct:.0f}%")
        cefr_str = " | ".join(cefr_parts) if cefr_parts else "no CEFR data"

        lines.append(f"  {p}: {cards} cards (+{added}), retention {retention:.0f}%, {cefr_str}")

    return "\n".join(lines)
