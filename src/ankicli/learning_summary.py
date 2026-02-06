"""Persistent learning summary storage."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, timedelta

from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .paths import SUMMARY_FILE, ensure_data_dir, atomic_json_write

# CEFR level descriptions
LEVEL_DESCRIPTIONS = {
    "A1": "Beginner",
    "A2": "Elementary",
    "B1": "Intermediate",
    "B2": "Upper Intermediate",
}


# ---------------------------------------------------------------------------
# Typed dataclasses for the learning summary
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeItem:
    """What the learner knows or needs to learn for a CEFR level."""
    summary: str = ""
    vocabulary: list[str] = field(default_factory=list)
    grammar_concepts: list[str] = field(default_factory=list)
    topics_covered: list[str] = field(default_factory=list)
    vocabulary_gaps: list[str] = field(default_factory=list)
    grammar_gaps: list[str] = field(default_factory=list)
    priority_topics: list[str] = field(default_factory=list)


@dataclass
class LevelData:
    """Data for a single CEFR level in the learning summary."""
    what_i_know: KnowledgeItem = field(default_factory=KnowledgeItem)
    what_to_learn: KnowledgeItem = field(default_factory=KnowledgeItem)
    estimated_coverage: int = 0


@dataclass
class LearningProgress:
    """Top-level learning summary with typed fields."""
    last_updated: str | None = None
    total_cards_added: int = 0
    levels: dict[str, LevelData] = field(default_factory=dict)
    recent_additions: list[str] = field(default_factory=list)
    notes: str = ""
    daily_activity: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to a plain dict matching the JSON format."""
        result = asdict(self)
        # Flatten KnowledgeItem into what_i_know / what_to_learn sub-dicts
        # asdict already handles this, but we clean up empty fields from
        # what_i_know (remove gap fields) and what_to_learn (remove vocab/grammar/topics).
        for level_key, level_data in result.get("levels", {}).items():
            wi = level_data.get("what_i_know", {})
            # Remove gap-related keys from what_i_know to match original format
            wi.pop("vocabulary_gaps", None)
            wi.pop("grammar_gaps", None)
            wi.pop("priority_topics", None)

            wl = level_data.get("what_to_learn", {})
            # Remove knowledge-related keys from what_to_learn to match original format
            wl.pop("vocabulary", None)
            wl.pop("grammar_concepts", None)
            wl.pop("topics_covered", None)
        return result

    @classmethod
    def from_dict(cls, data: dict) -> LearningProgress:
        """Create a LearningProgress from a plain dict (e.g. loaded from JSON)."""
        levels = {}
        for level_key, level_raw in data.get("levels", {}).items():
            wi_raw = level_raw.get("what_i_know", {})
            wl_raw = level_raw.get("what_to_learn", {})
            levels[level_key] = LevelData(
                what_i_know=KnowledgeItem(
                    summary=wi_raw.get("summary", ""),
                    vocabulary=wi_raw.get("vocabulary", []),
                    grammar_concepts=wi_raw.get("grammar_concepts", []),
                    topics_covered=wi_raw.get("topics_covered", []),
                ),
                what_to_learn=KnowledgeItem(
                    summary=wl_raw.get("summary", ""),
                    vocabulary_gaps=wl_raw.get("vocabulary_gaps", []),
                    grammar_gaps=wl_raw.get("grammar_gaps", []),
                    priority_topics=wl_raw.get("priority_topics", []),
                ),
                estimated_coverage=level_raw.get("estimated_coverage", 0),
            )
        return cls(
            last_updated=data.get("last_updated"),
            total_cards_added=data.get("total_cards_added", 0),
            levels=levels,
            recent_additions=data.get("recent_additions", []),
            notes=data.get("notes", ""),
            daily_activity=data.get("daily_activity", {}),
        )


# ---------------------------------------------------------------------------
# Default summary data
# ---------------------------------------------------------------------------

_DEFAULT_WHAT_TO_LEARN = {
    "A1": KnowledgeItem(
        summary="Basic greetings, introductions, numbers 1-100, colors, days/months, telling time, basic present tense verbs (ser, estar, tener, ir), simple questions, basic pronouns",
        vocabulary_gaps=["greetings", "numbers", "colors", "days", "months", "basic-verbs", "pronouns", "family", "common-objects"],
        grammar_gaps=["Present tense regular verbs", "Ser vs Estar basics", "Gender and number agreement", "Basic question formation"],
        priority_topics=["Self-introduction", "Basic conversation", "Numbers and time", "Common everyday objects"],
    ),
    "A2": KnowledgeItem(
        summary="Everyday vocabulary for routine activities, past tense (preterite/imperfect), reflexive verbs, direct/indirect object pronouns, comparisons, basic connectors",
        vocabulary_gaps=["daily-routine", "food", "travel", "work", "health", "emotions", "directions", "shopping"],
        grammar_gaps=["Preterite tense", "Imperfect tense", "Reflexive verbs", "Object pronouns", "Comparatives/superlatives"],
        priority_topics=["Daily routines", "Restaurant/food", "Travel basics", "Describing past events"],
    ),
    "B1": KnowledgeItem(
        summary="Subjunctive mood (present), conditional tense, future tense, relative clauses, advanced connectors, abstract vocabulary, opinions and hypotheticals",
        vocabulary_gaps=["abstract-concepts", "opinions", "media", "environment", "politics", "culture", "idioms"],
        grammar_gaps=["Present subjunctive", "Conditional tense", "Future tense", "Relative pronouns", "Subjunctive triggers"],
        priority_topics=["Expressing opinions", "Hypothetical situations", "News and media", "Cultural topics"],
    ),
    "B2": KnowledgeItem(
        summary="Imperfect subjunctive, conditional perfect, passive voice, advanced idiomatic expressions, nuanced vocabulary, formal/informal register",
        vocabulary_gaps=["professional", "academic", "nuanced-expressions", "regional-variations", "advanced-idioms"],
        grammar_gaps=["Imperfect subjunctive", "Conditional perfect", "Passive constructions", "Sequence of tenses", "Advanced clause structures"],
        priority_topics=["Professional communication", "Academic discourse", "Nuanced argumentation", "Literary and formal styles"],
    ),
}


def get_default_progress() -> LearningProgress:
    """Return a default typed LearningProgress."""
    levels = {}
    for level in ("A1", "A2", "B1", "B2"):
        levels[level] = LevelData(
            what_i_know=KnowledgeItem(),
            what_to_learn=KnowledgeItem(
                summary=_DEFAULT_WHAT_TO_LEARN[level].summary,
                vocabulary_gaps=list(_DEFAULT_WHAT_TO_LEARN[level].vocabulary_gaps),
                grammar_gaps=list(_DEFAULT_WHAT_TO_LEARN[level].grammar_gaps),
                priority_topics=list(_DEFAULT_WHAT_TO_LEARN[level].priority_topics),
            ),
            estimated_coverage=0,
        )
    return LearningProgress(levels=levels)


def get_default_summary() -> dict:
    """Return a default empty summary structure (dict form for backward compat)."""
    return get_default_progress().to_dict()


def load_progress() -> LearningProgress:
    """Load the learning summary from disk as a typed LearningProgress."""
    ensure_data_dir()
    if not SUMMARY_FILE.exists():
        return get_default_progress()
    try:
        with open(SUMMARY_FILE) as f:
            data = json.load(f)
            if data.get("levels") and "what_i_know" not in data["levels"].get("A1", {}):
                return get_default_progress()
            return LearningProgress.from_dict(data)
    except (json.JSONDecodeError, IOError):
        return get_default_progress()


def save_progress(progress: LearningProgress) -> None:
    """Save a typed LearningProgress to disk."""
    ensure_data_dir()
    progress.last_updated = datetime.now().isoformat()
    data = progress.to_dict()
    atomic_json_write(SUMMARY_FILE, data)


def load_summary() -> dict:
    """Load the learning summary from disk (dict form for backward compat)."""
    ensure_data_dir()
    if not SUMMARY_FILE.exists():
        return get_default_summary()
    try:
        with open(SUMMARY_FILE) as f:
            data = json.load(f)
            # Migrate old format to new format if needed
            if data.get("levels") and "what_i_know" not in data["levels"].get("A1", {}):
                return get_default_summary()
            return data
    except (json.JSONDecodeError, IOError):
        return get_default_summary()


def save_summary(summary: dict) -> None:
    """Save the learning summary to disk (dict form for backward compat)."""
    ensure_data_dir()
    summary["last_updated"] = datetime.now().isoformat()
    atomic_json_write(SUMMARY_FILE, summary)


def create_progress_bar(known: int, total: int, bar_width: int = 20) -> Text:
    """Create a colored progress bar from known/total counts.

    Designed so CEFR concrete numbers can replace estimated percentages
    by simply passing (matched_words, total_cefr_words) instead of
    (estimated_coverage, 100).
    """
    if total <= 0:
        percent = 0.0
    else:
        percent = (known / total) * 100

    filled = int(bar_width * percent / 100)
    empty = bar_width - filled
    bar_str = "\u2588" * filled + "\u2591" * empty

    # Color based on percentage
    if percent < 25:
        color = "red"
    elif percent < 50:
        color = "yellow"
    elif percent < 75:
        color = "cyan"
    else:
        color = "green"

    text = Text()
    text.append("[", style="dim")
    text.append(bar_str, style=color)
    text.append("] ", style="dim")
    text.append(f"{percent:.0f}%", style=f"bold {color}")
    return text


def _create_level_table(data: dict) -> Table:
    """Create a two-column table for WHAT I KNOW vs WHAT TO LEARN."""
    table = Table(
        show_header=True,
        header_style="bold",
        box=box.ROUNDED,
        expand=True,
        padding=(0, 1),
    )
    table.add_column("WHAT I KNOW", style="green", ratio=1)
    table.add_column("WHAT TO LEARN", style="yellow", ratio=1)

    # Build left column (what I know)
    left_parts = []
    what_i_know = data.get("what_i_know", {})

    if what_i_know.get("summary"):
        summary_text = what_i_know["summary"]
        # Truncate long summaries
        if len(summary_text) > 200:
            summary_text = summary_text[:200] + "..."
        left_parts.append(summary_text)

    vocab = what_i_know.get("vocabulary", [])
    if vocab:
        left_parts.append(f"\nVocabulary: {len(vocab)} words")

    grammar = what_i_know.get("grammar_concepts", [])
    if grammar:
        left_parts.append(f"Grammar: {', '.join(grammar[:5])}")
        if len(grammar) > 5:
            left_parts.append(f"  (+{len(grammar) - 5} more)")

    topics = what_i_know.get("topics_covered", [])
    if topics:
        left_parts.append(f"Topics: {', '.join(topics[:5])}")
        if len(topics) > 5:
            left_parts.append(f"  (+{len(topics) - 5} more)")

    if not left_parts:
        left_parts.append("[dim]Not started yet[/dim]")

    # Build right column (what to learn)
    right_parts = []
    what_to_learn = data.get("what_to_learn", {})

    if what_to_learn.get("summary"):
        summary_text = what_to_learn["summary"]
        if len(summary_text) > 200:
            summary_text = summary_text[:200] + "..."
        right_parts.append(summary_text)

    vocab_gaps = what_to_learn.get("vocabulary_gaps", [])
    if vocab_gaps:
        right_parts.append(f"\nVocab gaps: {', '.join(vocab_gaps[:5])}")

    grammar_gaps = what_to_learn.get("grammar_gaps", [])
    if grammar_gaps:
        right_parts.append(f"Grammar gaps: {', '.join(grammar_gaps[:4])}")

    priority = what_to_learn.get("priority_topics", [])
    if priority:
        right_parts.append(f"\nPriority: {', '.join(priority[:3])}")

    if not right_parts:
        right_parts.append("[dim]No gaps identified[/dim]")

    table.add_row("\n".join(left_parts), "\n".join(right_parts))
    return table


def compute_study_streak(summary: dict) -> int:
    """Compute the current study streak (consecutive days with activity)."""
    activity = summary.get("daily_activity", {})
    today = date.today()
    streak = 0
    for days_ago in range(0, 365):
        d = today - timedelta(days=days_ago)
        day_key = d.isoformat()
        if activity.get(day_key, 0) > 0:
            streak += 1
        else:
            break
    return streak


def _create_activity_heatmap(summary: dict) -> Text:
    """Create a 14-day activity heatmap using colored blocks (U5).

    bright_green for active days, dim for inactive. Shows streak count.
    """
    activity = summary.get("daily_activity", {})
    today = date.today()
    streak = compute_study_streak(summary)

    text = Text()
    text.append("  ACTIVITY ", style="bold dim")
    text.append("(last 14 days)", style="dim")
    if streak > 0:
        text.append(f"  Streak: {streak}d", style="bold bright_green")
    text.append("\n  ", style="")

    for days_ago in range(13, -1, -1):
        d = today - timedelta(days=days_ago)
        day_key = d.isoformat()
        count = activity.get(day_key, 0)

        if count == 0:
            text.append("\u2591\u2591", style="dim")
        elif count <= 5:
            text.append("\u2592\u2592", style="yellow")
        elif count <= 10:
            text.append("\u2593\u2593", style="bright_green")
        else:
            text.append("\u2588\u2588", style="bright_green")
        text.append(" ", style="")

    text.append("\n  ", style="")
    text.append("\u2591\u2591", style="dim")
    text.append("=0  ", style="dim")
    text.append("\u2592\u2592", style="yellow")
    text.append("=1-5  ", style="dim")
    text.append("\u2593\u2593", style="bright_green")
    text.append("=6-10  ", style="dim")
    text.append("\u2588\u2588", style="bright_green")
    text.append("=11+", style="dim")

    return text


def format_summary_as_text(summary: dict) -> str:
    """Format the summary as plain text for tool results / API responses."""
    lines = []
    total_cards = summary.get("total_cards_added", 0)
    lines.append(f"Learning Summary - {total_cards} cards total")
    lines.append("=" * 50)

    levels_data = summary.get("levels", {})
    for level in ["A1", "A2", "B1", "B2"]:
        data = levels_data.get(level, {})
        coverage = data.get("estimated_coverage", 0)
        desc = LEVEL_DESCRIPTIONS.get(level, "")
        vocab_count = len(data.get("what_i_know", {}).get("vocabulary", []))

        lines.append(f"\n{level} ({desc}) - {coverage}% coverage, {vocab_count} words")

        what_i_know = data.get("what_i_know", {})
        if what_i_know.get("summary"):
            lines.append(f"  Know: {what_i_know['summary'][:200]}")
        grammar = what_i_know.get("grammar_concepts", [])
        if grammar:
            lines.append(f"  Grammar: {', '.join(grammar[:5])}")
        topics = what_i_know.get("topics_covered", [])
        if topics:
            lines.append(f"  Topics: {', '.join(topics[:5])}")

        what_to_learn = data.get("what_to_learn", {})
        if what_to_learn.get("summary"):
            lines.append(f"  To learn: {what_to_learn['summary'][:200]}")
        priority = what_to_learn.get("priority_topics", [])
        if priority:
            lines.append(f"  Priority: {', '.join(priority[:3])}")

    recent = summary.get("recent_additions", [])
    if recent:
        lines.append(f"\nRecent additions: {', '.join(recent[-15:])}")

    if summary.get("notes"):
        lines.append(f"\nNotes: {summary['notes']}")

    return "\n".join(lines)


def format_summary_for_display(summary: dict) -> Group:
    """Format the summary as Rich renderables for display."""
    elements = []

    # Header panel
    total_cards = summary.get("total_cards_added", 0)
    last_updated = summary.get("last_updated", "")
    if last_updated:
        last_updated = last_updated[:16].replace("T", " ")

    header_text = Text()
    header_text.append("LEARNING DASHBOARD\n", style="bold cyan")
    header_text.append(f"Spanish - {total_cards} cards", style="dim")
    if last_updated:
        header_text.append(f"  |  Last updated: {last_updated}", style="dim")
    header_text.justify = "center"

    elements.append(Panel(header_text, border_style="cyan", box=box.DOUBLE))

    # Overall progress
    overall_text = Text()
    overall_text.append("  OVERALL PROGRESS\n", style="bold")

    levels_data = summary.get("levels", {})
    level_summaries = []
    for level in ["A1", "A2", "B1", "B2"]:
        data = levels_data.get(level, {})
        coverage = data.get("estimated_coverage", 0)
        vocab_count = len(data.get("what_i_know", {}).get("vocabulary", []))
        level_summaries.append(f"{level}: {coverage}%")

    # Overall bar (average of all levels)
    total_coverage = sum(
        levels_data.get(lv, {}).get("estimated_coverage", 0)
        for lv in ["A1", "A2", "B1", "B2"]
    )
    avg_coverage = total_coverage / 4

    overall_text.append("  ")
    bar = create_progress_bar(int(avg_coverage), 100, bar_width=30)
    overall_text.append_text(bar)
    overall_text.append("\n  ")
    overall_text.append("  |  ".join(level_summaries), style="dim")

    elements.append(overall_text)

    # Per-level sections
    for level in ["A1", "A2", "B1", "B2"]:
        data = levels_data.get(level, {})
        coverage = data.get("estimated_coverage", 0)
        description = LEVEL_DESCRIPTIONS.get(level, "")
        vocab_count = len(data.get("what_i_know", {}).get("vocabulary", []))

        # Level header with progress bar
        level_header = Text()
        level_header.append(f"  {level}  {description}", style="bold")
        level_header.append("  ")
        if vocab_count > 0:
            level_header.append(f"{vocab_count} words  ", style="dim")
        level_bar = create_progress_bar(coverage, 100)
        level_header.append_text(level_bar)

        elements.append(Rule(style="dim"))
        elements.append(level_header)

        # Two-column table
        elements.append(_create_level_table(data))

    # Activity heatmap
    elements.append(Rule(style="dim"))
    elements.append(_create_activity_heatmap(summary))

    # Recent additions
    recent = summary.get("recent_additions", [])
    if recent:
        elements.append(Rule(style="dim"))
        recent_text = Text()
        recent_text.append("  RECENT ADDITIONS ", style="bold dim")
        recent_text.append(f"(last {min(len(recent), 15)})\n", style="dim")
        recent_text.append("  ", style="")
        display_recent = recent[-15:]
        recent_text.append(", ".join(display_recent), style="cyan")
        elements.append(recent_text)

    # Notes
    if summary.get("notes"):
        elements.append(Rule(style="dim"))
        notes_text = Text()
        notes_text.append("  NOTES\n", style="bold dim")
        notes_text.append(f"  {summary['notes']}", style="dim italic")
        elements.append(notes_text)

    return Group(*elements)
