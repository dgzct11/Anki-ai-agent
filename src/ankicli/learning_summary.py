"""Persistent learning summary storage."""

import json
from datetime import datetime, date, timedelta

from rich import box
from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .paths import SUMMARY_FILE, ensure_data_dir

# CEFR level descriptions
LEVEL_DESCRIPTIONS = {
    "A1": "Beginner",
    "A2": "Elementary",
    "B1": "Intermediate",
    "B2": "Upper Intermediate",
}


def get_default_summary() -> dict:
    """Return a default empty summary structure."""
    return {
        "last_updated": None,
        "total_cards_added": 0,
        "levels": {
            "A1": {
                "what_i_know": {
                    "summary": "",
                    "vocabulary": [],
                    "grammar_concepts": [],
                    "topics_covered": []
                },
                "what_to_learn": {
                    "summary": "Basic greetings, introductions, numbers 1-100, colors, days/months, telling time, basic present tense verbs (ser, estar, tener, ir), simple questions, basic pronouns",
                    "vocabulary_gaps": ["greetings", "numbers", "colors", "days", "months", "basic-verbs", "pronouns", "family", "common-objects"],
                    "grammar_gaps": ["Present tense regular verbs", "Ser vs Estar basics", "Gender and number agreement", "Basic question formation"],
                    "priority_topics": ["Self-introduction", "Basic conversation", "Numbers and time", "Common everyday objects"]
                },
                "estimated_coverage": 0
            },
            "A2": {
                "what_i_know": {
                    "summary": "",
                    "vocabulary": [],
                    "grammar_concepts": [],
                    "topics_covered": []
                },
                "what_to_learn": {
                    "summary": "Everyday vocabulary for routine activities, past tense (preterite/imperfect), reflexive verbs, direct/indirect object pronouns, comparisons, basic connectors",
                    "vocabulary_gaps": ["daily-routine", "food", "travel", "work", "health", "emotions", "directions", "shopping"],
                    "grammar_gaps": ["Preterite tense", "Imperfect tense", "Reflexive verbs", "Object pronouns", "Comparatives/superlatives"],
                    "priority_topics": ["Daily routines", "Restaurant/food", "Travel basics", "Describing past events"]
                },
                "estimated_coverage": 0
            },
            "B1": {
                "what_i_know": {
                    "summary": "",
                    "vocabulary": [],
                    "grammar_concepts": [],
                    "topics_covered": []
                },
                "what_to_learn": {
                    "summary": "Subjunctive mood (present), conditional tense, future tense, relative clauses, advanced connectors, abstract vocabulary, opinions and hypotheticals",
                    "vocabulary_gaps": ["abstract-concepts", "opinions", "media", "environment", "politics", "culture", "idioms"],
                    "grammar_gaps": ["Present subjunctive", "Conditional tense", "Future tense", "Relative pronouns", "Subjunctive triggers"],
                    "priority_topics": ["Expressing opinions", "Hypothetical situations", "News and media", "Cultural topics"]
                },
                "estimated_coverage": 0
            },
            "B2": {
                "what_i_know": {
                    "summary": "",
                    "vocabulary": [],
                    "grammar_concepts": [],
                    "topics_covered": []
                },
                "what_to_learn": {
                    "summary": "Imperfect subjunctive, conditional perfect, passive voice, advanced idiomatic expressions, nuanced vocabulary, formal/informal register",
                    "vocabulary_gaps": ["professional", "academic", "nuanced-expressions", "regional-variations", "advanced-idioms"],
                    "grammar_gaps": ["Imperfect subjunctive", "Conditional perfect", "Passive constructions", "Sequence of tenses", "Advanced clause structures"],
                    "priority_topics": ["Professional communication", "Academic discourse", "Nuanced argumentation", "Literary and formal styles"]
                },
                "estimated_coverage": 0
            }
        },
        "recent_additions": [],
        "notes": ""
    }


def load_summary() -> dict:
    """Load the learning summary from disk."""
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
    """Save the learning summary to disk."""
    ensure_data_dir()
    summary["last_updated"] = datetime.now().isoformat()
    with open(SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


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


def _create_activity_heatmap(summary: dict) -> Text:
    """Create a 14-day activity heatmap using Unicode blocks."""
    activity = summary.get("daily_activity", {})
    today = date.today()

    text = Text()
    text.append("  ACTIVITY ", style="bold dim")
    text.append("(last 14 days)\n", style="dim")
    text.append("  ", style="")

    for days_ago in range(13, -1, -1):
        d = today - timedelta(days=days_ago)
        day_key = d.isoformat()
        count = activity.get(day_key, 0)

        if count == 0:
            text.append("\u2591\u2591", style="dim")
        elif count <= 5:
            text.append("\u2592\u2592", style="yellow")
        elif count <= 10:
            text.append("\u2593\u2593", style="cyan")
        else:
            text.append("\u2588\u2588", style="green")
        text.append(" ", style="")

    text.append("\n  ", style="")
    text.append("\u2591\u2591", style="dim")
    text.append("=0  ", style="dim")
    text.append("\u2592\u2592", style="yellow")
    text.append("=1-5  ", style="dim")
    text.append("\u2593\u2593", style="cyan")
    text.append("=6-10  ", style="dim")
    text.append("\u2588\u2588", style="green")
    text.append("=11+", style="dim")

    return text


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
