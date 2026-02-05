"""Terminal chat UI for Anki assistant."""

import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table
from rich.text import Text

from .assistant import AnkiAssistant
from .chat_log import add_exchange, format_history_for_display, clear_log
from .client import AnkiClient
from .config import CLAUDE_MODELS, get_model_specs, load_config, save_config, format_tool_notes_display
from .conversation_store import get_conversation_age
from .learning_summary import (
    load_summary,
    format_summary_for_display,
    create_progress_bar,
    LEVEL_DESCRIPTIONS,
)
from .paths import DATA_DIR, HISTORY_FILE
from .grammar_quiz import (
    GRAMMAR_TOPICS,
    QUESTION_TYPE_LABELS,
    QuestionType,
    get_topic_mastery,
    get_quiz_history,
)
from .translation_practice import (
    PracticeSession,
    PracticeDirection,
    FeedbackLevel,
    feedback_to_ease,
)

# Style for prompt_toolkit
PROMPT_STYLE = Style.from_dict({
    "prompt": "cyan bold",
})


def format_tokens(n: int) -> str:
    """Format token count for display."""
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


def create_context_bar(status: dict) -> Text:
    """Create a richer context usage bar with session stats (U8).

    Format: Context: [........] 23% | 12 min | +5 cards | A2: 147/500 | Streak: 12d
    """
    percent = status["percent_used"]
    input_tokens = status["input_tokens"]
    max_tokens = status["max_tokens"]

    # Determine color based on usage
    if percent < 50:
        color = "green"
    elif percent < 75:
        color = "yellow"
    elif percent < 90:
        color = "orange1"
    else:
        color = "red"

    # Create bar (narrower to fit more stats in 70 chars)
    bar_width = 10
    filled = int(bar_width * percent / 100)
    empty = bar_width - filled
    bar = "\u2588" * filled + "\u2591" * empty

    text = Text()
    text.append("Context: [", style="dim")
    text.append(bar, style=color)
    text.append("] ", style="dim")
    text.append(f"{percent:.0f}%", style=color)

    # Session stats
    session_minutes = status.get("session_minutes", 0)
    session_cards = status.get("session_cards_added", 0)
    if session_minutes > 0:
        text.append(" | ", style="dim")
        text.append(f"{session_minutes} min", style="cyan")
    if session_cards > 0:
        text.append(" | ", style="dim")
        text.append(f"+{session_cards} cards", style="green")

    # CEFR level progress (if available in status)
    cefr_level = status.get("cefr_current_level")
    cefr_known = status.get("cefr_known", 0)
    cefr_total = status.get("cefr_total", 0)
    if cefr_level and cefr_total > 0:
        text.append(" | ", style="dim")
        text.append(f"{cefr_level}: {cefr_known}/{cefr_total}", style="cyan")

    # Study streak (if available)
    streak = status.get("streak_days", 0)
    if streak > 0:
        text.append(" | ", style="dim")
        text.append(f"Streak: {streak}d", style="bright_green")

    return text


def create_tool_panel(name: str, input_data: dict) -> Panel:
    """Create a panel showing tool usage."""
    content = Text()
    content.append(f"{name}\n", style="bold yellow")
    for key, value in input_data.items():
        if isinstance(value, list):
            content.append(f"  {key}: ", style="dim")
            content.append(f"{len(value)} items\n", style="white")
        elif isinstance(value, str) and len(value) > 60:
            content.append(f"  {key}: ", style="dim")
            content.append(f"{value[:60]}...\n", style="white")
        else:
            content.append(f"  {key}: ", style="dim")
            content.append(f"{value}\n", style="white")
    return Panel(content, title="[bold blue]Tool Call[/bold blue]", border_style="blue")


def create_result_panel(name: str, result: str) -> Panel:
    """Create a panel showing tool result."""
    # Truncate long results
    if len(result) > 500:
        display_result = result[:500] + "..."
    else:
        display_result = result
    return Panel(
        Text(display_result, style="green"),
        title=f"[bold green]Result: {name}[/bold green]",
        border_style="green",
    )


def _summarize_tool_input(tool_name: str, input_data: dict) -> str:
    """Create a brief summary of tool input for logging."""

    # Special handling for card operations - extract the words/fronts
    if tool_name == "add_card":
        front = input_data.get("front", "")
        if len(front) > 50:
            front = front[:50] + "..."
        return f"'{front}'"

    elif tool_name == "add_multiple_cards":
        cards = input_data.get("cards", [])
        if cards:
            # Extract fronts (English definitions)
            fronts = []
            for card in cards[:10]:  # Limit to first 10
                front = card.get("front", "")
                # Clean up and truncate
                front = front.replace("\n", " ").strip()
                if len(front) > 40:
                    front = front[:40] + "..."
                fronts.append(front)

            summary = ", ".join(fronts)
            if len(cards) > 10:
                summary += f" (+{len(cards) - 10} more)"
            return f"{len(cards)} cards: {summary}"
        return f"{len(cards)} cards"

    elif tool_name == "update_card":
        note_id = input_data.get("note_id", "?")
        front = input_data.get("front", "")
        if front:
            if len(front) > 40:
                front = front[:40] + "..."
            return f"ID {note_id}: '{front}'"
        return f"ID {note_id}"

    elif tool_name == "update_multiple_cards":
        updates = input_data.get("updates", [])
        if updates:
            ids = [str(u.get("note_id", "?")) for u in updates[:5]]
            summary = ", ".join(ids)
            if len(updates) > 5:
                summary += f" (+{len(updates) - 5} more)"
            return f"{len(updates)} cards: IDs {summary}"
        return f"{len(updates)} cards"

    elif tool_name == "delete_cards":
        note_ids = input_data.get("note_ids", [])
        return f"{len(note_ids)} cards deleted"

    elif tool_name in ("search_cards", "check_word_exists", "find_card_by_word"):
        query = input_data.get("query", input_data.get("word", ""))
        return f"'{query}'"

    elif tool_name in ("check_words_exist", "find_cards_by_words"):
        words = input_data.get("words", [])
        if words:
            preview = ", ".join(words[:5])
            if len(words) > 5:
                preview += f" (+{len(words) - 5} more)"
            return preview
        return ""

    elif tool_name == "update_learning_summary":
        words = input_data.get("words_added", [])
        level = input_data.get("level", "")
        return f"{level}: +{len(words)} words"

    elif tool_name == "all_cards_delegate":
        deck = input_data.get("deck_name", "")
        prompt = input_data.get("prompt", "")
        dry_run = input_data.get("dry_run", False)
        limit = input_data.get("limit")
        prompt_preview = prompt[:40] + "..." if len(prompt) > 40 else prompt
        parts = [f"deck='{deck}'", f"prompt='{prompt_preview}'"]
        if dry_run:
            parts.append("DRY RUN")
        if limit:
            parts.append(f"limit={limit}")
        return ", ".join(parts)

    elif tool_name == "card_subset_delegate":
        note_ids = input_data.get("note_ids", [])
        prompt = input_data.get("prompt", "")
        dry_run = input_data.get("dry_run", False)
        prompt_preview = prompt[:40] + "..." if len(prompt) > 40 else prompt
        parts = [f"{len(note_ids)} cards", f"prompt='{prompt_preview}'"]
        if dry_run:
            parts.append("DRY RUN")
        return ", ".join(parts)

    elif tool_name == "set_tool_note":
        tool_target = input_data.get("tool_name", "")
        note = input_data.get("note", "")
        if len(note) > 40:
            note = note[:40] + "..."
        return f"[{tool_target}] {note}"

    elif tool_name == "get_tool_notes":
        return "listing preferences"

    elif tool_name == "remove_tool_note":
        return f"[{input_data.get('tool_name', '')}]"

    elif tool_name == "start_translation_practice":
        deck = input_data.get("deck_name", "")
        count = input_data.get("count", 10)
        direction = input_data.get("direction", "en_to_es")
        return f"deck='{deck}', {count}q, {direction}"

    elif tool_name == "log_practice_session":
        ptype = input_data.get("practice_type", "")
        attempted = input_data.get("phrases_attempted", 0)
        correct = input_data.get("correct", 0)
        return f"{ptype}: {correct}/{attempted} correct"

    elif tool_name == "start_grammar_quiz":
        topic = input_data.get("topic", "")
        level = input_data.get("level", "")
        count = input_data.get("count", 5)
        return f"'{topic}' ({level}), {count}q"

    elif tool_name == "log_quiz_results":
        topic = input_data.get("topic", "")
        attempted = input_data.get("questions_attempted", 0)
        correct = input_data.get("correct", 0)
        return f"'{topic}': {correct}/{attempted} correct"

    elif tool_name == "get_error_patterns":
        return "listing error patterns"

    elif tool_name == "log_error":
        error_type = input_data.get("error_type", "")
        example = input_data.get("example", "")
        if len(example) > 30:
            example = example[:30] + "..."
        return f"{error_type}: '{example}'"

    elif tool_name == "start_conversation_sim":
        scenario = input_data.get("scenario", "")
        level = input_data.get("level", "")
        return f"'{scenario}' ({level})"

    # Default handling for other tools
    parts = []
    for key, value in input_data.items():
        if isinstance(value, list):
            parts.append(f"{key}={len(value)} items")
        elif isinstance(value, str):
            if len(value) > 30:
                parts.append(f"{key}='{value[:30]}...'")
            else:
                parts.append(f"{key}='{value}'")
        else:
            parts.append(f"{key}={value}")
    return ", ".join(parts[:3])  # Limit to 3 key params


def create_cefr_deep_dive_panel(
    level: str,
    level_progress: dict,
    grammar_mastery: dict,
) -> Panel:
    """Create a CEFR deep-dive panel for a specific level (U7).

    Shows per-category known/missing words, grammar checklist for
    that level, and actionable recommendations.
    """
    content = Text()
    content.append(f"CEFR {level} DEEP DIVE\n\n", style="bold cyan")

    words_known = level_progress.get("words_known", 0)
    words_total = level_progress.get("words_total", 0)
    pct = (words_known / words_total * 100) if words_total > 0 else 0

    # Overall bar
    bar_w = 25
    filled = int(bar_w * pct / 100)
    empty = bar_w - filled
    color = "green" if pct >= 75 else "yellow" if pct >= 50 else "red"
    content.append("  Vocabulary: ", style="bold")
    content.append(f"{words_known}/{words_total} ", style=color)
    content.append("[", style="dim")
    content.append("\u2588" * filled, style=color)
    content.append("\u2591" * empty, style="dim")
    content.append("] ", style="dim")
    content.append(f"{pct:.0f}%\n\n", style=f"bold {color}")

    # Per-category breakdown
    categories = level_progress.get("categories", {})
    if categories:
        content.append("  CATEGORIES\n", style="bold dim")
        sorted_cats = sorted(categories.items(), key=lambda x: x[1].get("percent", 0))
        for cat_name, cat_data in sorted_cats[:12]:
            k = cat_data.get("known", 0)
            t = cat_data.get("total", 0)
            cp = cat_data.get("percent", 0)
            cat_bar_w = 8
            cat_filled = int(cat_bar_w * cp / 100)
            cat_empty = cat_bar_w - cat_filled
            cat_color = "green" if cp >= 75 else "yellow" if cp >= 50 else "red"
            content.append(f"    {cat_name:<22}", style="dim")
            content.append(f"{k:>3}/{t:<3} ", style=cat_color)
            content.append("\u2588" * cat_filled, style=cat_color)
            content.append("\u2591" * cat_empty, style="dim")
            content.append(f" {cp:.0f}%\n", style=cat_color)
        content.append("\n")

    # Grammar checklist for this level
    topics = GRAMMAR_TOPICS.get(level, [])
    if topics:
        content.append("  GRAMMAR\n", style="bold dim")
        for topic in topics:
            topic_data = grammar_mastery.get(topic)
            if topic_data and topic_data.get("mastered"):
                icon = "\u2713"
                style = "green"
            elif topic_data and topic_data.get("avg_score", 0) >= 70:
                icon = "~"
                style = "yellow"
            elif topic_data:
                icon = "\u2717"
                style = "red"
            else:
                icon = "\u2717"
                style = "dim"
            content.append(f"    {icon} ", style=f"bold {style}")
            content.append(f"{topic}\n", style=style)
        content.append("\n")

    # Recommendations
    content.append("  RECOMMENDATIONS\n", style="bold dim")
    if pct < 50:
        content.append("    Focus on building core vocabulary\n", style="yellow")
    elif pct < 75:
        content.append("    Fill category gaps to reach 75%\n", style="yellow")
    else:
        content.append("    Near mastery - review weak categories\n", style="green")

    # Find weakest categories
    weak_cats = [name for name, d in sorted_cats[:3]] if categories else []
    if weak_cats:
        content.append(f"    Weakest areas: {', '.join(weak_cats)}\n", style="yellow")

    # Find unmastered grammar
    unmastered = [t for t in topics if not grammar_mastery.get(t, {}).get("mastered")]
    if unmastered:
        content.append(f"    Grammar to practice: {', '.join(unmastered[:3])}\n", style="yellow")

    return Panel(
        content,
        title=f"[bold cyan]{level} Progress[/bold cyan]",
        border_style="cyan",
        box=box.DOUBLE,
        padding=(1, 2),
    )


def create_grammar_mastery_checklist() -> Panel:
    """Create a grammar mastery checklist grouped by CEFR level (U6).

    Shows: check for mastered (85%+), ~ for developing (70-84%), x for needs review (<70%).
    """
    mastery = get_topic_mastery()

    content = Text()
    content.append("GRAMMAR MASTERY\n\n", style="bold")

    for level in ["A1", "A2", "B1", "B2"]:
        topics = GRAMMAR_TOPICS.get(level, [])
        if not topics:
            continue

        content.append(f"  {level}\n", style="bold cyan")

        for topic in topics:
            topic_data = mastery.get(topic)
            if topic_data and topic_data.get("mastered"):
                icon = "\u2713"
                style = "green"
                pct = topic_data.get("avg_score", 100)
            elif topic_data:
                avg = topic_data.get("avg_score", 0)
                pct = avg
                if avg >= 70:
                    icon = "~"
                    style = "yellow"
                else:
                    icon = "\u2717"
                    style = "red"
            else:
                icon = "\u2717"
                style = "dim"
                pct = 0

            content.append(f"    {icon} ", style=f"bold {style}")
            content.append(f"{topic:<40}", style=style)
            if pct > 0:
                content.append(f" {pct:.0f}%", style=style)
            content.append("\n")

        content.append("\n")

    # Legend
    content.append("  ", style="")
    content.append("\u2713", style="bold green")
    content.append(" mastered (85%+)  ", style="dim")
    content.append("~", style="bold yellow")
    content.append(" developing (70-84%)  ", style="dim")
    content.append("\u2717", style="bold red")
    content.append(" needs review (<70%)", style="dim")

    return Panel(
        content,
        title="[bold cyan]GRAMMAR[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )


def create_conjugation_table(verb: str, tense: str = "") -> Table:
    """Create a Rich Table for conjugation quiz questions.

    Displays rows for each person (yo, tu, el, nosotros, vosotros, ellos).
    """
    table = Table(
        title=f"{verb} - {tense}" if tense else verb,
        title_style="bold magenta",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold",
        padding=(0, 1),
    )
    table.add_column("Person", style="cyan", min_width=12)
    table.add_column("Conjugation", style="bold white", min_width=15)

    persons = ["yo", "tu", "el/ella/Ud.", "nosotros", "vosotros", "ellos/Uds."]
    for person in persons:
        table.add_row(person, "___")

    return table


def create_session_progress_bar(current: int, total: int) -> Text:
    """Create a progress bar for quiz/practice sessions.

    Renders: "Question 3/10 [===......] 30%"
    """
    if total <= 0:
        total = 1
    percent = int(current / total * 100)
    bar_width = 20
    filled = int(bar_width * current / total)
    empty = bar_width - filled

    if percent >= 80:
        color = "green"
    elif percent >= 50:
        color = "yellow"
    else:
        color = "cyan"

    text = Text()
    text.append(f"Question {current}/{total} ", style="bold")
    text.append("[", style="dim")
    text.append("\u2588" * filled, style=color)
    text.append("\u2591" * empty, style="dim")
    text.append("] ", style="dim")
    text.append(f"{percent}%", style=f"bold {color}")
    return text


def create_practice_question_panel(
    question_num: int,
    total: int,
    phrase: str,
    direction: PracticeDirection,
    is_due: bool,
    difficulty: str,
    target_words: str = "",
) -> Panel:
    """Create a styled panel for a practice question."""
    content = Text()

    # U2: Progress bar in header
    content.append_text(create_session_progress_bar(question_num, total))
    if difficulty == "harder":
        content.append("  [HARDER]", style="bold magenta")
    elif difficulty == "easier":
        content.append("  [EASIER]", style="bold yellow")
    content.append("\n\n")

    if direction == PracticeDirection.EN_TO_ES:
        content.append("Translate to Spanish:\n", style="dim")
    else:
        content.append("Translate to English:\n", style="dim")

    content.append(f"  {phrase}", style="bold white")

    if target_words:
        content.append("\n")
        content.append(f"  Target words: {target_words}", style="cyan")

    if is_due:
        content.append("\n")
        content.append("  (due for Anki review)", style="dim italic")

    return Panel(
        content,
        title="[bold bright_blue]TRANSLATE[/bold bright_blue]",
        border_style="bright_blue",
        padding=(1, 2),
    )


def highlight_word_diff(user_answer: str, correct_answer: str) -> Text:
    """Highlight words in user's answer: green=correct, red=wrong, yellow=partial.

    Compares user answer words to correct answer words positionally.
    """
    import re as _re

    user_words = _re.findall(r'\S+', user_answer.strip())
    correct_words = _re.findall(r'\S+', correct_answer.strip())

    result = Text()

    for i, word in enumerate(user_words):
        if i > 0:
            result.append(" ")
        if i < len(correct_words):
            clean_u = _re.sub(r'[^\w]', '', word.lower())
            clean_c = _re.sub(r'[^\w]', '', correct_words[i].lower())
            if clean_u == clean_c:
                result.append(word, style="green")
            elif clean_u and clean_c and (clean_u in clean_c or clean_c in clean_u):
                result.append(word, style="yellow")
            else:
                result.append(word, style="red")
        else:
            result.append(word, style="red")

    return result


def create_practice_feedback_panel(
    feedback_level: FeedbackLevel,
    feedback_text: str,
    scores: dict[str, int],
    user_answer: str = "",
    correct_answer: str = "",
) -> Panel:
    """Create a styled feedback panel after answer evaluation.

    When user_answer and correct_answer are provided, highlights words
    in the user's answer: green for correct, red for wrong, yellow for
    partially matching words.
    """
    if feedback_level == FeedbackLevel.CORRECT:
        border = "green"
        title = "[bold green]CORRECT[/bold green]"
        icon = "+"
    elif feedback_level == FeedbackLevel.PARTIAL:
        border = "yellow"
        title = "[bold yellow]PARTIAL[/bold yellow]"
        icon = "~"
    else:
        border = "red"
        title = "[bold red]INCORRECT[/bold red]"
        icon = "x"

    content = Text()
    content.append(f" {icon} ", style=f"bold {border}")

    # U1: Word-level highlighting when both answers are available
    if user_answer and correct_answer and feedback_level != FeedbackLevel.CORRECT:
        content.append("Your answer: ", style="dim")
        content.append_text(highlight_word_diff(user_answer, correct_answer))
        content.append("\n")
        content.append("  Correct:    ", style="dim")
        content.append(correct_answer, style="green")
        content.append("\n\n")
    else:
        content.append(feedback_text)
        content.append("\n\n")

    # Score breakdown
    content.append("Scores: ", style="bold dim")
    score_parts = []
    for label, score in scores.items():
        if score >= 3:
            style = "green"
        elif score >= 2:
            style = "yellow"
        else:
            style = "red"
        score_parts.append((f"{label}:{score}/4", style))

    for i, (text, style) in enumerate(score_parts):
        if i > 0:
            content.append("  ", style="dim")
        content.append(text, style=style)

    return Panel(
        content,
        title=title,
        border_style=border,
        padding=(0, 2),
    )


def create_practice_summary_panel(session: PracticeSession) -> Panel:
    """Create a session summary panel."""
    content = Text()

    # Score bar
    content.append("SCORE\n", style="bold")
    score_pct = session.score_percent
    bar_width = 30
    filled = int(bar_width * score_pct / 100)
    empty = bar_width - filled
    bar = "\u2588" * filled + "\u2591" * empty

    if score_pct >= 80:
        color = "green"
    elif score_pct >= 60:
        color = "yellow"
    else:
        color = "red"

    content.append("  [", style="dim")
    content.append(bar, style=color)
    content.append("] ", style="dim")
    content.append(f"{score_pct:.0f}%\n\n", style=f"bold {color}")

    # Counts
    content.append(f"  Correct:   {session.correct_count}", style="green")
    content.append(f"  Partial: {session.partial_count}", style="yellow")
    content.append(f"  Wrong:   {session.incorrect_count}\n", style="red")

    # Reviewed
    reviewed = sum(1 for r in session.results if r.marked_reviewed)
    if reviewed > 0:
        content.append(f"  Anki reviews marked: {reviewed}\n", style="cyan")

    # Weak words
    weak = session.get_weak_words()
    if weak:
        content.append("\n")
        content.append("  Words to review: ", style="bold dim")
        content.append(", ".join(weak[:10]), style="yellow")
        if len(weak) > 10:
            content.append(f" (+{len(weak) - 10} more)", style="dim")

    return Panel(
        content,
        title="[bold cyan]SESSION COMPLETE[/bold cyan]",
        border_style="cyan",
        box=box.DOUBLE,
        padding=(1, 2),
    )


def create_practice_commands_panel() -> Panel:
    """Create a small panel showing available practice commands."""
    content = Text()
    content.append("/skip", style="cyan")
    content.append(" skip  ", style="dim")
    content.append("/hint", style="cyan")
    content.append(" hint  ", style="dim")
    content.append("/score", style="cyan")
    content.append(" scores  ", style="dim")
    content.append("/quit", style="cyan")
    content.append(" end session", style="dim")
    return Panel(content, border_style="dim", box=box.ROUNDED, padding=(0, 1))


def run_practice_loop(
    console: Console,
    assistant: AnkiAssistant,
    session: PracticeSession,
    prompt_session: PromptSession,
) -> None:
    """Run the interactive practice sub-loop.

    This takes over the terminal with a question-answer-feedback cycle,
    sending user translations through the assistant for Claude to evaluate.
    """
    console.print()
    console.print(create_practice_commands_panel())
    console.print()

    import re as _re_group

    def _extract_word(c):
        """Extract the main word from a card's back field."""
        clean = _re_group.sub(r'<[^>]+>', '', c.back).strip()
        first_line = clean.split('\n')[0].split('(')[0].strip()
        return first_line[:30]

    while not session.is_finished:
        card = session.current_card
        if card is None:
            break

        # Build list of remaining words for Claude to see
        remaining_cards = []
        for idx in range(session.current_index, min(session.current_index + 10, len(session.cards))):
            remaining_cards.append(session.cards[idx])

        remaining_info = []
        for rc in remaining_cards:
            clean_word = _re_group.sub(r'<[^>]+>', '', rc.back).strip().split('\n')[0][:40]
            remaining_info.append(f"  - {clean_word} (EN: {rc.front})")
        remaining_section = "\n".join(remaining_info)
        current_word = _extract_word(card)

        # Step 1: Ask Claude to generate a sentence combining multiple target words
        direction_label = "English" if session.direction == PracticeDirection.EN_TO_ES else "Spanish"
        target_lang = "Spanish" if session.direction == PracticeDirection.EN_TO_ES else "English"
        gen_prompt = (
            f"[PRACTICE MODE - GENERATE SENTENCE]\n"
            f"Question {session.current_index + 1}/{session.total_questions}\n"
            f"Difficulty level: {session.difficulty_num}/5 ({session.difficulty_label})\n\n"
            f"Upcoming words to practice ({len(remaining_cards)}):\n{remaining_section}\n\n"
            f"Generate a SINGLE {direction_label} sentence for the user to translate to {target_lang}.\n"
            f"The sentence MUST use the word '{current_word}' and should also naturally include 1-2 other "
            f"words from the list above if they fit well together.\n"
            f"Do NOT reveal the target words or the {target_lang} translation.\n"
            f"Just present the sentence to translate. Keep it appropriate for difficulty level {session.difficulty_num}/5.\n"
            f"Format: just the sentence, nothing else."
        )

        # Get Claude's generated sentence
        generated_sentence = ""
        try:
            with console.status("[cyan]Generating sentence...[/cyan]", spinner="dots"):
                for event in assistant.chat(gen_prompt):
                    if event["type"] == "text_delta":
                        generated_sentence += event["content"]
        except Exception as e:
            console.print(f"[red]Error generating sentence: {e}[/red]")
            # Fall back to showing card directly
            if session.direction == PracticeDirection.EN_TO_ES:
                generated_sentence = card.front
            else:
                generated_sentence = card.back

        generated_sentence = generated_sentence.strip().strip('"').strip("'")

        # Show question panel with Claude's generated sentence (no target words shown)
        console.print(create_practice_question_panel(
            question_num=session.current_index + 1,
            total=session.total_questions,
            phrase=generated_sentence,
            direction=session.direction,
            is_due=card.is_due,
            difficulty=session.difficulty_level,
        ))

        # Get user answer
        try:
            answer = prompt_session.prompt(
                [("class:prompt", "Your translation: ")],
            ).strip()
        except (KeyboardInterrupt, EOFError):
            answer = "/quit"

        if not answer:
            continue

        # Handle practice commands
        if answer.lower() == "/quit":
            console.print("[dim]Ending practice session...[/dim]")
            break

        if answer.lower() == "/skip":
            from .translation_practice import PracticeResult
            session.record_result(PracticeResult(
                card_id=card.card_id,
                front=card.front,
                back=card.back,
                user_answer="(skipped)",
                feedback_level=FeedbackLevel.INCORRECT,
                feedback_text="Skipped",
            ))
            console.print("[dim]Skipped.[/dim]\n")
            continue

        if answer.lower() == "/score":
            if session.results:
                console.print(f"[bold]Current score:[/bold] {session.correct_count}/{session.questions_answered} correct ({session.score_percent:.0f}%)")
            else:
                console.print("[dim]No answers yet.[/dim]")
            console.print()
            continue

        if answer.lower() == "/hint":
            if session.direction == PracticeDirection.EN_TO_ES:
                hint_source = card.back
            else:
                hint_source = card.front
            import re
            clean = re.sub(r'<[^>]+>', ' ', hint_source).strip()
            hint = clean[:3] + "..." if len(clean) > 3 else clean
            console.print(f"[dim]Hint: {hint}[/dim]\n")
            continue

        # Step 2: Ask Claude to evaluate the translation
        eval_prompt = (
            f"[PRACTICE MODE - EVALUATE TRANSLATION]\n"
            f"The sentence was: {generated_sentence}\n"
            f"User's translation to {target_lang}: {answer}\n"
            f"Primary target word: {current_word}\n"
            f"Words from the deck that could appear in the sentence:\n{remaining_section}\n\n"
            f"Evaluate the translation. Score each 0-4: Meaning, Grammar, Naturalness, Vocabulary.\n"
            f"Give per-word feedback on target words used in the sentence.\n"
            f"Show the correct translation if wrong."
        )

        # Stream Claude's evaluation
        response_text = ""
        spinner_active = False
        status_ctx = None

        try:
            for event in assistant.chat(eval_prompt):
                if event["type"] == "text_delta":
                    if not spinner_active:
                        status_ctx = console.status("[cyan]Evaluating...[/cyan]", spinner="dots")
                        status_ctx.start()
                        spinner_active = True
                    response_text += event["content"]
                elif event["type"] == "tool_use":
                    if spinner_active and status_ctx:
                        status_ctx.stop()
                        spinner_active = False
                    console.print(create_tool_panel(event["name"], event["input"]))
                elif event["type"] == "tool_result":
                    console.print(create_result_panel(event["name"], event["result"]))
                elif event["type"] == "context_status":
                    pass  # Suppress context bar during practice

            if spinner_active and status_ctx:
                status_ctx.stop()
        except Exception as e:
            if spinner_active and status_ctx:
                status_ctx.stop()
            console.print(f"[red]Error during evaluation: {e}[/red]")
            response_text = "Could not evaluate. Moving to next question."

        # Parse Claude's evaluation from the response text
        # Try to extract scores from the response
        import re
        meaning = grammar = naturalness = vocabulary = 2  # Default middle scores
        feedback_level = FeedbackLevel.PARTIAL

        # Look for score patterns like "Meaning: 4/4" or "meaning: 3"
        score_patterns = [
            (r'[Mm]eaning[:\s]+(\d)/4', 'meaning'),
            (r'[Gg]rammar[:\s]+(\d)/4', 'grammar'),
            (r'[Nn]aturalness[:\s]+(\d)/4', 'naturalness'),
            (r'[Vv]ocabulary[:\s]+(\d)/4', 'vocabulary'),
        ]
        for pattern, key in score_patterns:
            match = re.search(pattern, response_text)
            if match:
                val = int(match.group(1))
                if key == 'meaning':
                    meaning = val
                elif key == 'grammar':
                    grammar = val
                elif key == 'naturalness':
                    naturalness = val
                elif key == 'vocabulary':
                    vocabulary = val

        # Determine feedback level from scores
        total = meaning + grammar + naturalness + vocabulary
        if total >= 14:
            feedback_level = FeedbackLevel.CORRECT
        elif total >= 8:
            feedback_level = FeedbackLevel.PARTIAL
        else:
            feedback_level = FeedbackLevel.INCORRECT

        # Show feedback panel
        console.print()
        # Determine the correct answer for word-level diff (U1)
        import re as _re_clean
        if session.direction == PracticeDirection.EN_TO_ES:
            correct_ans = _re_clean.sub(r'<[^>]+>', ' ', card.back).strip()
        else:
            correct_ans = _re_clean.sub(r'<[^>]+>', ' ', card.front).strip()

        console.print(create_practice_feedback_panel(
            feedback_level=feedback_level,
            feedback_text=response_text[:300] if len(response_text) > 300 else response_text,
            scores={
                "Meaning": meaning,
                "Grammar": grammar,
                "Natural": naturalness,
                "Vocab": vocabulary,
            },
            user_answer=answer,
            correct_answer=correct_ans,
        ))

        # Record results for all grouped cards
        from .translation_practice import PracticeResult
        for gc in group_cards:
            result = PracticeResult(
                card_id=gc.card_id,
                front=gc.front,
                back=gc.back,
                user_answer=answer,
                feedback_level=feedback_level,
                feedback_text=response_text,
                meaning_score=meaning,
                grammar_score=grammar,
                naturalness_score=naturalness,
                vocabulary_score=vocabulary,
                is_due_for_review=gc.is_due,
            )

            # Track due cards for session-end review summary
            if gc.is_due:
                result.is_due_for_review = True

            session.record_result(result)

        # Skip ahead past the grouped cards (first one was already advanced by record_result)
        # record_result increments current_index, so after recording all group_cards,
        # current_index is already at the right position
        console.print()

    # Show session summary
    if session.results:
        console.print(create_practice_summary_panel(session))

        # Show Anki review recommendations for due cards
        due_results = [r for r in session.results if r.is_due_for_review]
        if due_results:
            import re as _re_review
            ease_labels = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}
            console.print()
            console.print("[bold cyan]Anki Review Suggestions:[/bold cyan]")
            console.print("[dim]When you review these in Anki, I suggest pressing:[/dim]")
            for r in due_results:
                clean_word = _re_review.sub(r'<[^>]+>', '', r.back).strip()[:30]
                suggested = feedback_to_ease(r.feedback_level)
                label = ease_labels.get(suggested, "Good")
                if r.feedback_level == FeedbackLevel.CORRECT:
                    reason = "got it right"
                elif r.feedback_level == FeedbackLevel.PARTIAL:
                    reason = "partially correct"
                else:
                    reason = "needs more practice"
                console.print(f"  [cyan]{clean_word}[/cyan] → [bold]{label}[/bold] [dim]({reason})[/dim]")
            console.print()

        # Log the session via Claude
        summary = session.get_summary_dict()
        log_prompt = (
            f"[PRACTICE SESSION COMPLETE - LOG IT]\n"
            f"Please call log_practice_session with these results:\n"
            f"practice_type: translation\n"
            f"direction: {summary['direction']}\n"
            f"deck_name: {summary['deck_name']}\n"
            f"phrases_attempted: {summary['total_questions']}\n"
            f"correct: {summary['correct']}\n"
            f"partial: {summary['partial']}\n"
            f"incorrect: {summary['incorrect']}\n"
            f"score_percent: {summary['score_percent']}\n"
            f"weak_words: {summary['weak_words']}\n\n"
            f"Also briefly summarize the practice session results to the user."
        )

        # Run the logging through the assistant
        response_text = ""
        try:
            for event in assistant.chat(log_prompt):
                if event["type"] == "text_delta":
                    response_text += event["content"]
                elif event["type"] == "tool_use":
                    console.print(create_tool_panel(event["name"], event["input"]))
                elif event["type"] == "tool_result":
                    console.print(create_result_panel(event["name"], event["result"]))

            if response_text.strip():
                from rich.markdown import Markdown as Md
                console.print("[bold cyan]Assistant:[/bold cyan]")
                console.print(Md(response_text))
        except Exception as e:
            console.print(f"[yellow]Could not log session: {e}[/yellow]")

    console.print()


# ---------------------------------------------------------------------------
# Grammar quiz UI
# ---------------------------------------------------------------------------

def create_quiz_topic_panel(level: str) -> Panel:
    """Create a topic selection panel for the grammar quiz."""
    topics = GRAMMAR_TOPICS.get(level, [])
    mastery = get_topic_mastery()

    content = Text()
    content.append(f"Grammar Topics - {level}\n\n", style="bold")

    for i, topic in enumerate(topics, 1):
        topic_data = mastery.get(topic)
        if topic_data and topic_data.get("mastered"):
            status = "[mastered]"
            style = "green"
        elif topic_data:
            avg = topic_data.get("avg_score", 0)
            status = f"[{avg:.0f}%]"
            style = "yellow"
        else:
            status = "[new]"
            style = "dim"

        # Recommend topics that haven't been mastered
        recommend = ""
        if not topic_data or not topic_data.get("mastered"):
            if not topic_data or topic_data.get("quizzed_count", 0) == 0:
                recommend = "  [recommended]"

        content.append(f"  {i:2}. ", style="cyan")
        content.append(f"{topic:<45}", style=style)
        content.append(f" {status}", style=style)
        if recommend:
            content.append(recommend, style="bold magenta")
        content.append("\n")

    content.append("\n")
    content.append("Enter a number, topic name, or 'back' to cancel.", style="dim")

    return Panel(
        content,
        title="[bold bright_blue]GRAMMAR QUIZ[/bold bright_blue]",
        border_style="bright_blue",
        padding=(1, 2),
    )


def create_quiz_question_panel(
    question_num: int,
    total: int,
    question_text: str,
    question_type: str,
    options: list[str] | None = None,
    instruction: str = "",
) -> Panel:
    """Create a styled panel for a quiz question."""
    type_label = QUESTION_TYPE_LABELS.get(
        QuestionType(question_type) if question_type in [qt.value for qt in QuestionType] else QuestionType.FILL_IN_BLANK,
        question_type.replace("_", " ").title(),
    )

    content = Text()

    # U2: Progress bar in header
    content.append_text(create_session_progress_bar(question_num, total))
    content.append(f"  [{type_label}]", style="bold magenta")
    content.append("\n\n")

    if instruction:
        content.append(f"{instruction}\n\n", style="dim italic")

    # U3: Conjugation table display
    if question_type == "conjugation":
        content.append(f"  {question_text}", style="bold white")
        content.append("\n\n")
        content.append("  yo ___  |  nosotros ___\n", style="dim")
        content.append("  tu ___  |  vosotros ___\n", style="dim")
        content.append("  el ___  |  ellos    ___\n", style="dim")
    else:
        content.append(f"  {question_text}", style="bold white")

    if options:
        content.append("\n\n")
        for opt in options:
            content.append(f"  {opt}\n", style="white")

    # Determine border color by question type
    type_colors = {
        "fill_in_blank": "bright_blue",
        "multiple_choice": "cyan",
        "conjugation": "magenta",
        "error_correction": "yellow",
        "sentence_transformation": "bright_green",
    }
    border = type_colors.get(question_type, "bright_blue")

    return Panel(
        content,
        title=f"[bold {border}]QUIZ[/bold {border}]",
        border_style=border,
        padding=(1, 2),
    )


def create_quiz_feedback_panel(correct: bool, feedback: str, correct_answer: str, user_answer: str) -> Panel:
    """Create a feedback panel after answering a quiz question."""
    if correct:
        border = "green"
        title = "[bold green]CORRECT[/bold green]"
        icon = "+"
    else:
        border = "red"
        title = "[bold red]INCORRECT[/bold red]"
        icon = "x"

    content = Text()
    content.append(f" {icon} ", style=f"bold {border}")

    if not correct:
        content.append("Your answer: ", style="dim")
        content.append(f"{user_answer}\n", style="red")
        content.append("  Correct answer: ", style="dim")
        content.append(f"{correct_answer}\n\n", style="green")

    content.append(feedback)

    return Panel(
        content,
        title=title,
        border_style=border,
        padding=(0, 2),
    )


def create_quiz_type_breakdown_table(type_breakdown: dict[str, dict]) -> Table:
    """Create a Rich Table showing per-type quiz score breakdown (U4).

    Example output:
      Fill-in-blank    4/5  80%
      Multiple choice  3/3 100%
      Conjugation      1/2  50%
    """
    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold dim",
        padding=(0, 1),
    )
    table.add_column("Question Type", style="dim", min_width=22)
    table.add_column("Score", justify="right", min_width=5)
    table.add_column("%", justify="right", min_width=5)

    for qt, data in type_breakdown.items():
        label = QUESTION_TYPE_LABELS.get(
            QuestionType(qt) if qt in [q.value for q in QuestionType] else QuestionType.FILL_IN_BLANK,
            qt.replace("_", " ").title(),
        )
        pct = data.get("score", 0)
        ct = data.get("correct", 0)
        tot = data.get("total", 0)
        if pct >= 85:
            style = "green"
        elif pct >= 60:
            style = "yellow"
        else:
            style = "red"
        table.add_row(label, f"[{style}]{ct}/{tot}[/{style}]", f"[{style}]{pct:.0f}%[/{style}]")

    return table


def create_quiz_summary_panel(
    topic: str,
    level: str,
    correct: int,
    total: int,
    score: float,
    type_breakdown: dict[str, dict],
    weak_areas: list[str],
    mastered: bool,
) -> Panel:
    """Create a summary panel after quiz completion."""
    content = Text()

    # Score bar
    content.append("SCORE\n", style="bold")
    bar_width = 30
    filled = int(bar_width * score / 100)
    empty = bar_width - filled
    bar = "\u2588" * filled + "\u2591" * empty

    if score >= 85:
        color = "green"
    elif score >= 60:
        color = "yellow"
    else:
        color = "red"

    content.append("  [", style="dim")
    content.append(bar, style=color)
    content.append("] ", style="dim")
    content.append(f"{score:.0f}%", style=f"bold {color}")
    content.append(f"  ({correct}/{total} correct)\n\n", style="dim")

    # Mastery status
    if mastered or score >= 85:
        content.append("  MASTERED ", style="bold green")
        content.append("This topic is now mastered!\n\n", style="green")
    else:
        content.append("  NOT YET MASTERED ", style="bold yellow")
        content.append(f"Need 85% to master (got {score:.0f}%)\n\n", style="yellow")

    # U4: Per-type quiz score breakdown as a Rich Table
    if type_breakdown:
        content.append("\n")
        type_table = create_quiz_type_breakdown_table(type_breakdown)
        # We embed the table content as text lines for panel compatibility
        content.append("  BY TYPE\n", style="bold dim")
        for qt, data in type_breakdown.items():
            label = QUESTION_TYPE_LABELS.get(
                QuestionType(qt) if qt in [q.value for q in QuestionType] else QuestionType.FILL_IN_BLANK,
                qt.replace("_", " ").title(),
            )
            pct = data.get("score", 0)
            ct = data.get("correct", 0)
            tot = data.get("total", 0)
            bar_w = 10
            filled = int(bar_w * pct / 100)
            empty = bar_w - filled
            if pct >= 85:
                style = "green"
            elif pct >= 60:
                style = "yellow"
            else:
                style = "red"
            content.append(f"    {label:<25} ", style="dim")
            content.append(f"{ct}/{tot}", style=style)
            content.append(" [", style="dim")
            content.append("\u2588" * filled, style=style)
            content.append("\u2591" * empty, style="dim")
            content.append("]\n", style="dim")
        content.append("\n")

    # Weak areas
    if weak_areas:
        content.append("  WEAK AREAS\n", style="bold dim")
        for area in weak_areas:
            content.append(f"    - {area}\n", style="yellow")

    return Panel(
        content,
        title=f"[bold cyan]QUIZ COMPLETE: {topic} ({level})[/bold cyan]",
        border_style="cyan",
        box=box.DOUBLE,
        padding=(1, 2),
    )


def create_quiz_commands_panel() -> Panel:
    """Create a small panel showing available quiz commands."""
    content = Text()
    content.append("/skip", style="cyan")
    content.append(" skip  ", style="dim")
    content.append("/hint", style="cyan")
    content.append(" hint  ", style="dim")
    content.append("/score", style="cyan")
    content.append(" scores  ", style="dim")
    content.append("/quit", style="cyan")
    content.append(" end quiz", style="dim")
    return Panel(content, border_style="dim", box=box.ROUNDED, padding=(0, 1))


def _get_quiz_answer(prompt_session: PromptSession, prompt_text: str) -> str:
    """Get user input, handling interrupts."""
    try:
        return prompt_session.prompt(
            [("class:prompt", prompt_text)],
        ).strip()
    except (KeyboardInterrupt, EOFError):
        return "/quit"


def run_quiz_loop(
    console: Console,
    assistant: AnkiAssistant,
    prompt_session: PromptSession,
) -> None:
    """Run the interactive grammar quiz sub-loop."""
    from .grammar_quiz import QuizSession, build_grading_prompt

    quiz_session: QuizSession | None = getattr(assistant, "_quiz_session", None)

    if quiz_session is None:
        console.print("[yellow]No quiz session active.[/yellow]")
        return

    questions = quiz_session.questions
    if not questions:
        console.print("[yellow]No questions generated. Try again.[/yellow]")
        return

    console.print()
    console.print(create_quiz_commands_panel())
    console.print()

    correct_count = 0
    total_answered = 0
    type_scores: dict[str, dict] = {}

    for i, question in enumerate(questions):
        # Show question panel
        console.print(create_quiz_question_panel(
            question_num=i + 1,
            total=len(questions),
            question_text=question.question_text,
            question_type=question.question_type,
            options=question.options if question.options else None,
            instruction=question.instruction,
        ))

        # Choose prompt based on question type
        if question.question_type == "conjugation":
            prompt_text = "Conjugations (comma-separated): "
        elif question.question_type == "multiple_choice":
            prompt_text = "Your answer (A/B/C/D): "
        else:
            prompt_text = "Your answer: "

        answer = _get_quiz_answer(prompt_session, prompt_text)

        if not answer:
            continue

        # Handle quiz commands (with re-prompt loop)
        while answer.lower() in ("/score", "/hint"):
            if answer.lower() == "/score":
                if total_answered > 0:
                    pct = correct_count / total_answered * 100
                    console.print(f"[bold]Current score:[/bold] {correct_count}/{total_answered} correct ({pct:.0f}%)")
                else:
                    console.print("[dim]No answers yet.[/dim]")
                console.print()
            elif answer.lower() == "/hint":
                if question.hint:
                    console.print(f"[dim]Hint: {question.hint}[/dim]")
                else:
                    hint = question.correct_answer[:3] + "..." if len(question.correct_answer) > 3 else question.correct_answer
                    console.print(f"[dim]Hint: starts with '{hint}'[/dim]")
                console.print()
            answer = _get_quiz_answer(prompt_session, prompt_text)

        if answer.lower() == "/quit":
            console.print("[dim]Ending quiz...[/dim]")
            break

        if answer.lower() == "/skip":
            total_answered += 1
            console.print("[dim]Skipped.[/dim]\n")
            continue

        # Grade the answer via Claude
        grading_prompt = build_grading_prompt(question, answer)

        try:
            grade_result = assistant.client.messages.create(
                model=assistant.config.subagent_model,
                max_tokens=500,
                messages=[{"role": "user", "content": grading_prompt}],
            )
            grade_response = grade_result.content[0].text
        except Exception as e:
            grade_response = f'{{"correct": false, "score": 0.0, "feedback": "Could not grade: {e}"}}'

        # Parse grading result
        import json as _json
        is_correct = False
        score = 0.0
        feedback = ""

        try:
            resp_text = grade_response.strip()
            if "```json" in resp_text:
                resp_text = resp_text.split("```json")[1].split("```")[0].strip()
            elif "```" in resp_text:
                resp_text = resp_text.split("```")[1].split("```")[0].strip()

            start = resp_text.find("{")
            end = resp_text.rfind("}")
            if start != -1 and end != -1:
                grade_data = _json.loads(resp_text[start : end + 1])
                is_correct = grade_data.get("correct", False)
                score = grade_data.get("score", 1.0 if is_correct else 0.0)
                feedback = grade_data.get("feedback", "")
        except (_json.JSONDecodeError, ValueError):
            is_correct = answer.strip().lower() == question.correct_answer.strip().lower()
            score = 1.0 if is_correct else 0.0
            feedback = "Correct!" if is_correct else f"The correct answer is: {question.correct_answer}"

        total_answered += 1
        if is_correct or score >= 0.8:
            correct_count += 1

        # Track by type
        qt = question.question_type
        if qt not in type_scores:
            type_scores[qt] = {"total": 0, "correct": 0}
        type_scores[qt]["total"] += 1
        if is_correct or score >= 0.8:
            type_scores[qt]["correct"] += 1

        # Show feedback
        console.print()
        console.print(create_quiz_feedback_panel(
            correct=is_correct,
            feedback=feedback,
            correct_answer=question.correct_answer,
            user_answer=answer,
        ))
        console.print()

    # Compute final scores
    final_score = correct_count / total_answered * 100 if total_answered > 0 else 0.0

    type_breakdown = {}
    for qt, data in type_scores.items():
        total = data["total"]
        correct = data["correct"]
        type_breakdown[qt] = {
            "total": total,
            "correct": correct,
            "score": correct / total * 100 if total > 0 else 0,
        }

    weak_areas = []
    if final_score < 85:
        weak_areas.append(quiz_session.topic)

    mastered = final_score >= 85

    # Show summary
    if total_answered > 0:
        console.print(create_quiz_summary_panel(
            topic=quiz_session.topic,
            level=quiz_session.cefr_level,
            correct=correct_count,
            total=total_answered,
            score=final_score,
            type_breakdown=type_breakdown,
            weak_areas=weak_areas,
            mastered=mastered,
        ))

        # Log results via Claude
        log_prompt = (
            f"[QUIZ SESSION COMPLETE - LOG RESULTS]\n"
            f"Please call log_quiz_results with:\n"
            f"topic: {quiz_session.topic}\n"
            f"level: {quiz_session.cefr_level}\n"
            f"questions_attempted: {total_answered}\n"
            f"correct: {correct_count}\n"
            f"weak_areas: {weak_areas}\n\n"
        )
        if final_score < 85:
            log_prompt += (
                f"The user scored {final_score:.0f}% which is below the 85% mastery threshold.\n"
                f"After logging, offer to create Anki flashcards for the grammar concepts they struggled with.\n"
                f"Suggest specific card ideas based on '{quiz_session.topic}' at {quiz_session.cefr_level} level."
            )
        else:
            log_prompt += "The user mastered this topic! Congratulate them and suggest what to study next."

        response_text = ""
        try:
            for event in assistant.chat(log_prompt):
                if event["type"] == "text_delta":
                    response_text += event["content"]
                elif event["type"] == "tool_use":
                    console.print(create_tool_panel(event["name"], event["input"]))
                elif event["type"] == "tool_result":
                    console.print(create_result_panel(event["name"], event["result"]))

            if response_text.strip():
                console.print("[bold cyan]Assistant:[/bold cyan]")
                console.print(Markdown(response_text))
        except Exception as e:
            console.print(f"[yellow]Could not log quiz results: {e}[/yellow]")

    console.print()


# ---------------------------------------------------------------------------
# Conversation simulation UI
# ---------------------------------------------------------------------------

def create_conversation_scenario_panel(
    scenario: str,
    level: str,
    character: str,
) -> Panel:
    """Create a panel showing the conversation scenario."""
    content = Text()
    content.append("CONVERSATION SIMULATION\n\n", style="bold")
    content.append("Scenario: ", style="dim")
    content.append(f"{scenario}\n", style="bold white")
    content.append("Character: ", style="dim")
    content.append(f"{character}\n", style="bold white")
    content.append("Level: ", style="dim")
    content.append(f"{level}\n\n", style="bold white")
    content.append("Speak in Spanish! Type ", style="dim")
    content.append("/quit", style="cyan")
    content.append(" to end the conversation.", style="dim")

    return Panel(
        content,
        title="[bold bright_green]CONVERSE[/bold bright_green]",
        border_style="bright_green",
        padding=(1, 2),
    )


def create_conversation_commands_panel() -> Panel:
    """Create a small panel showing available conversation commands."""
    content = Text()
    content.append("/hint", style="cyan")
    content.append(" vocabulary help  ", style="dim")
    content.append("/vocab", style="cyan")
    content.append(" new words  ", style="dim")
    content.append("/quit", style="cyan")
    content.append(" end conversation", style="dim")
    return Panel(content, border_style="dim", box=box.ROUNDED, padding=(0, 1))


def run_conversation_loop(
    console: Console,
    assistant: AnkiAssistant,
    sim_data: dict,
    prompt_session: PromptSession,
) -> None:
    """Run the interactive conversation simulation sub-loop."""
    console.print()
    console.print(create_conversation_scenario_panel(
        scenario=sim_data["scenario"],
        level=sim_data["level"],
        character=sim_data["character"],
    ))
    console.print(create_conversation_commands_panel())
    console.print()

    turn_count = 0
    new_vocab: list[str] = []

    while True:
        # Get user input
        try:
            user_input = prompt_session.prompt(
                [("class:prompt", "Tu: ")],
            ).strip()
        except (KeyboardInterrupt, EOFError):
            user_input = "/quit"

        if not user_input:
            continue

        if user_input.lower() == "/quit":
            console.print("[dim]Ending conversation...[/dim]")
            break

        if user_input.lower() == "/hint":
            hint_prompt = (
                f"[CONVERSATION MODE - VOCABULARY HELP]\n"
                f"The user needs help with vocabulary for this scenario: {sim_data['scenario']}.\n"
                f"Level: {sim_data['level']}.\n"
                f"Give 5-8 useful Spanish phrases/words for this situation with translations."
            )
            response_text = ""
            try:
                for event in assistant.chat(hint_prompt):
                    if event["type"] == "text_delta":
                        response_text += event["content"]
                if response_text.strip():
                    console.print("[bold cyan]Vocabulary help:[/bold cyan]")
                    console.print(Markdown(response_text))
            except Exception as e:
                console.print(f"[yellow]Error: {e}[/yellow]")
            console.print()
            continue

        if user_input.lower() == "/vocab":
            if new_vocab:
                console.print("[bold]New vocabulary this session:[/bold]")
                for word in new_vocab:
                    console.print(f"  - {word}", style="cyan")
            else:
                console.print("[dim]No new vocabulary recorded yet.[/dim]")
            console.print()
            continue

        turn_count += 1

        # Send to Claude in conversation mode
        conv_prompt = (
            f"[CONVERSATION MODE - TURN {turn_count}]\n"
            f"Scenario: {sim_data['scenario']} | Level: {sim_data['level']} | "
            f"Character: {sim_data['character']}\n\n"
            f"User says (in Spanish): {user_input}\n\n"
            f"Respond in character. Stay in Spanish. "
            f"If the user made a mistake, correct it gently in-character. "
            f"If you notice a recurring error pattern, call log_error. "
            f"Keep your response to 2-4 sentences."
        )

        response_text = ""
        spinner_active = False
        status_ctx = None

        try:
            for event in assistant.chat(conv_prompt):
                if event["type"] == "text_delta":
                    if not spinner_active:
                        status_ctx = console.status("[cyan]...[/cyan]", spinner="dots")
                        status_ctx.start()
                        spinner_active = True
                    response_text += event["content"]
                elif event["type"] == "tool_use":
                    if spinner_active and status_ctx:
                        status_ctx.stop()
                        spinner_active = False
                    # Show tool calls briefly (log_error calls are expected)
                    if event["name"] != "log_error":
                        console.print(create_tool_panel(event["name"], event["input"]))
                elif event["type"] == "tool_result":
                    if event["name"] != "log_error":
                        console.print(create_result_panel(event["name"], event["result"]))
                elif event["type"] == "context_status":
                    pass  # Suppress context bar during conversation

            if spinner_active and status_ctx:
                status_ctx.stop()
        except Exception as e:
            if spinner_active and status_ctx:
                status_ctx.stop()
            console.print(f"[red]Error: {e}[/red]")
            response_text = "Lo siento, hubo un error. Continuemos..."

        if response_text.strip():
            # Show character's response in a styled panel
            char_label = sim_data["character"].split(",")[0].strip()[:30]
            console.print(Panel(
                Markdown(response_text),
                title=f"[bold bright_green]{char_label}[/bold bright_green]",
                border_style="bright_green",
                padding=(0, 2),
            ))
        console.print()

    # End of conversation - ask Claude to summarize
    if turn_count > 0:
        summary_prompt = (
            f"[CONVERSATION MODE - SESSION COMPLETE]\n"
            f"The conversation simulation has ended after {turn_count} turns.\n"
            f"Scenario: {sim_data['scenario']} | Level: {sim_data['level']}\n\n"
            f"Please:\n"
            f"1. Summarize the user's performance (grammar, vocabulary, fluency)\n"
            f"2. Call log_practice_session with practice_type='conversation', "
            f"phrases_attempted={turn_count}, and your assessment of correct/partial/incorrect turns\n"
            f"3. If you noticed new vocabulary the user could learn, offer to create Anki cards\n"
            f"4. Check get_error_patterns to see if this session reinforced any known weak areas"
        )

        response_text = ""
        try:
            for event in assistant.chat(summary_prompt):
                if event["type"] == "text_delta":
                    response_text += event["content"]
                elif event["type"] == "tool_use":
                    console.print(create_tool_panel(event["name"], event["input"]))
                elif event["type"] == "tool_result":
                    console.print(create_result_panel(event["name"], event["result"]))

            if response_text.strip():
                console.print("[bold cyan]Assistant:[/bold cyan]")
                console.print(Markdown(response_text))
        except Exception as e:
            console.print(f"[yellow]Could not summarize conversation: {e}[/yellow]")

    # Clean up
    if hasattr(assistant, "_conversation_sim"):
        assistant._conversation_sim = None

    console.print()


def run_chat():
    """Run the interactive chat interface."""
    console = Console()

    # Check Anki connection first
    anki = AnkiClient()
    if not anki.ping():
        console.print(
            "[red]✗ Cannot connect to Anki[/red]\n"
            "[dim]Make sure Anki is running with AnkiConnect installed.[/dim]"
        )
        sys.exit(1)

    # Initialize assistant
    try:
        assistant = AnkiAssistant()
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        sys.exit(1)

    model_specs = get_model_specs(assistant.model)
    console.print()

    # Build welcome dashboard
    welcome_text = Text()
    welcome_text.append("ANKI ASSISTANT\n", style="bold cyan")
    welcome_text.append(f"Model: {model_specs['name']}", style="green")
    welcome_text.append(f"  ({assistant.model})", style="dim")
    welcome_text.justify = "center"

    console.print(Panel(welcome_text, border_style="cyan", box=box.DOUBLE))

    # CEFR progress summary
    summary = load_summary()
    levels_data = summary.get("levels", {})
    total_cards = summary.get("total_cards_added", 0)

    if total_cards > 0:
        progress_text = Text()
        progress_text.append("  PROGRESS  ", style="bold")
        progress_text.append(f"{total_cards} cards total\n", style="dim")
        for level in ["A1", "A2", "B1", "B2"]:
            data = levels_data.get(level, {})
            coverage = data.get("estimated_coverage", 0)
            vocab_count = len(data.get("what_i_know", {}).get("vocabulary", []))
            desc = LEVEL_DESCRIPTIONS.get(level, "")
            progress_text.append(f"  {level} {desc:<20}", style="bold")
            bar = create_progress_bar(coverage, 100, bar_width=15)
            progress_text.append_text(bar)
            if vocab_count > 0:
                progress_text.append(f"  {vocab_count} words", style="dim")
            progress_text.append("\n")
        console.print(progress_text)

    # Commands table
    cmd_table = Table(show_header=False, box=None, padding=(0, 2))
    cmd_table.add_column(style="cyan", min_width=10)
    cmd_table.add_column(style="dim")
    cmd_table.add_row("history", "Show recent chat history")
    cmd_table.add_row("progress", "Show learning dashboard")
    cmd_table.add_row("status", "Show context usage")
    cmd_table.add_row("model", "Show or change Claude model")
    cmd_table.add_row("notes", "Show saved preferences")
    cmd_table.add_row("compact", "Summarize history to free context")
    cmd_table.add_row("practice", "Start translation practice")
    cmd_table.add_row("quiz", "Start grammar quiz")
    cmd_table.add_row("converse", "Start conversation simulation")
    cmd_table.add_row("clear/new", "Reset conversation")
    cmd_table.add_row("exit", "Quit")
    console.print(Panel(cmd_table, title="[bold dim]Commands[/bold dim]", border_style="dim", box=box.ROUNDED))
    console.print()

    # Try to load previous conversation
    conversation_age = get_conversation_age()
    if assistant.load_from_disk():
        console.print(f"[green]✓ Restored previous conversation[/green] [dim](from {conversation_age})[/dim]")
        status = assistant.get_context_status()
        console.print(create_context_bar(status))
        console.print(f"[dim]Messages: {len(assistant.messages)} | Type 'new' to start fresh[/dim]")
        console.print()

    # Set up prompt with history
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        session: PromptSession = PromptSession(
            history=FileHistory(str(HISTORY_FILE)),
            style=PROMPT_STYLE,
        )
    except Exception:
        session = PromptSession(style=PROMPT_STYLE)

    while True:
        try:
            # Get user input
            user_input = session.prompt(
                [("class:prompt", "You: ")],
            ).strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            if user_input.lower() in ("clear", "new"):
                assistant.reset()
                console.print("[dim]Conversation cleared. Starting fresh.[/dim]")
                console.print("[dim](Chat log preserved - use 'history' to view)[/dim]\n")
                continue

            if user_input.lower() == "compact":
                console.print("[dim]Compacting conversation history...[/dim]")
                try:
                    result = assistant.compact_history()
                    console.print(f"[green]✓ {result}[/green]")
                    status = assistant.get_context_status()
                    console.print(create_context_bar(status))
                except Exception as e:
                    console.print(f"[red]Error compacting: {e}[/red]")
                console.print()
                continue

            if user_input.lower() == "status":
                status = assistant.get_context_status()
                console.print(f"[bold]Model:[/bold] [green]{status['model_name']}[/green] [dim]({status['model']})[/dim]")
                console.print(create_context_bar(status))
                console.print(f"[dim]Messages in history: {len(assistant.messages)}[/dim]")
                console.print()
                continue

            if user_input.lower() == "progress":
                summary = load_summary()
                console.print(format_summary_for_display(summary))
                console.print()
                continue

            if user_input.lower() == "history":
                console.print(format_history_for_display(10))
                console.print()
                continue

            if user_input.lower().startswith("notes"):
                parts = user_input.strip().split(maxsplit=2)
                config = load_config()

                if len(parts) == 1:
                    # Show current notes
                    console.print(format_tool_notes_display(config))
                elif parts[1].lower() == "clear":
                    if config.tool_notes:
                        config.tool_notes.clear()
                        save_config(config)
                        console.print("[green]All preferences cleared.[/green]")
                    else:
                        console.print("[dim]No preferences to clear.[/dim]")
                elif parts[1].lower() == "remove" and len(parts) >= 3:
                    tool_name = parts[2]
                    if tool_name in config.tool_notes:
                        del config.tool_notes[tool_name]
                        save_config(config)
                        # Reload into assistant
                        assistant.config = config
                        console.print(f"[green]Preference removed for '{tool_name}'.[/green]")
                    else:
                        console.print(f"[yellow]No preference found for '{tool_name}'.[/yellow]")
                else:
                    console.print(
                        "[dim]Usage:[/dim]\n"
                        "  [cyan]notes[/cyan]              - Show all preferences\n"
                        "  [cyan]notes remove <tool>[/cyan] - Remove a preference\n"
                        "  [cyan]notes clear[/cyan]         - Clear all preferences\n\n"
                        "[dim]To add preferences, tell the assistant in chat (e.g., 'I prefer informal Spanish').[/dim]"
                    )
                console.print()
                continue

            if user_input.lower().startswith("model"):
                parts = user_input.strip().split(maxsplit=1)
                if len(parts) == 1:
                    # Show current model and list available models
                    specs = get_model_specs(assistant.model)
                    console.print(f"\n[bold]Current model:[/bold] [green]{specs['name']}[/green] [dim]({assistant.model})[/dim]")
                    console.print(f"  Context window: {specs['context_window']:,} tokens")
                    console.print(f"  Max output: {specs['max_output_tokens']:,} tokens\n")
                    console.print("[bold]Available models:[/bold]")
                    for i, (model_id, model_info) in enumerate(CLAUDE_MODELS.items(), 1):
                        marker = " [green]<-- current[/green]" if model_id == assistant.model else ""
                        console.print(
                            f"  [cyan]{i}[/cyan]. {model_info['name']} [dim]({model_id})[/dim]"
                            f"  context={model_info['context_window'] // 1000}K"
                            f"  output={model_info['max_output_tokens'] // 1000}K"
                            f"{marker}"
                        )
                    console.print(f"\n[dim]Usage: model <number> or model <model-id>[/dim]")
                else:
                    choice = parts[1].strip()
                    model_ids = list(CLAUDE_MODELS.keys())
                    new_model_id = None

                    # Try as a number
                    if choice.isdigit():
                        idx = int(choice) - 1
                        if 0 <= idx < len(model_ids):
                            new_model_id = model_ids[idx]
                        else:
                            console.print(f"[red]Invalid choice. Pick 1-{len(model_ids)}.[/red]")
                    else:
                        # Try as model ID (exact or partial match)
                        if choice in CLAUDE_MODELS:
                            new_model_id = choice
                        else:
                            matches = [m for m in model_ids if choice.lower() in m.lower()]
                            if len(matches) == 1:
                                new_model_id = matches[0]
                            elif len(matches) > 1:
                                console.print(f"[yellow]Ambiguous match: {', '.join(matches)}[/yellow]")
                            else:
                                console.print(f"[red]Unknown model '{choice}'. Use 'model' to see options.[/red]")

                    if new_model_id:
                        assistant.model = new_model_id
                        assistant._model_specs = get_model_specs(new_model_id)
                        # Persist to config
                        config = load_config()
                        config.main_model = new_model_id
                        save_config(config)
                        specs = get_model_specs(new_model_id)
                        console.print(
                            f"[green]Switched to {specs['name']}[/green] [dim]({new_model_id})[/dim]\n"
                            f"  Context: {specs['context_window']:,} | Max output: {specs['max_output_tokens']:,}"
                        )
                console.print()
                continue

            if user_input.lower().startswith("practice"):
                # Parse practice command: practice [deck] [--count N] [--direction DIR] [--focus SOURCE]
                parts = user_input.strip().split()
                deck_name = None
                count = 10
                direction = "en_to_es"
                card_source = "mixed"

                # Simple argument parsing
                i = 1
                while i < len(parts):
                    if parts[i] == "--count" and i + 1 < len(parts):
                        try:
                            count = int(parts[i + 1])
                        except ValueError:
                            pass
                        i += 2
                    elif parts[i] == "--direction" and i + 1 < len(parts):
                        direction = parts[i + 1]
                        i += 2
                    elif parts[i] == "--focus" and i + 1 < len(parts):
                        card_source = parts[i + 1]
                        i += 2
                    elif not parts[i].startswith("--"):
                        deck_name = parts[i]
                        i += 1
                    else:
                        i += 1

                if not deck_name:
                    # Ask Claude to pick a deck via natural language
                    console.print("[dim]Starting practice session via AI...[/dim]")
                    # Fall through to let Claude handle "start a practice session"
                    user_input = "Start a translation practice session. Use the main Spanish deck, 10 questions, English to Spanish, mixed cards."
                else:
                    # Start practice directly
                    console.print(f"[dim]Starting practice: deck={deck_name}, count={count}, direction={direction}[/dim]")
                    console.print()

                    # Trigger via the assistant so Claude can manage the session
                    user_input = (
                        f"Start a translation practice session from deck '{deck_name}' "
                        f"with {count} questions, direction {direction}, card source {card_source}."
                    )

                # Send to assistant and check if practice session was started
                response_text = ""
                full_response = ""
                context_status = None
                spinner_active = False
                status_ctx = None
                tool_calls = []
                delegate_progress = None
                delegate_task = None

                try:
                    for event in assistant.chat(user_input):
                        if event["type"] == "text_delta":
                            if not spinner_active:
                                status_ctx = console.status("[cyan]Setting up practice...[/cyan]", spinner="dots")
                                status_ctx.start()
                                spinner_active = True
                            response_text += event["content"]
                            full_response += event["content"]
                        elif event["type"] == "tool_use":
                            if spinner_active and status_ctx:
                                status_ctx.stop()
                                spinner_active = False
                                if response_text.strip():
                                    console.print("[bold cyan]Assistant:[/bold cyan]")
                                    console.print(Markdown(response_text))
                                response_text = ""
                            console.print()
                            console.print(create_tool_panel(event["name"], event["input"]))
                            tool_summary = _summarize_tool_input(event["name"], event["input"])
                            tool_calls.append({"name": event["name"], "summary": tool_summary})
                        elif event["type"] == "tool_result":
                            console.print(create_result_panel(event["name"], event["result"]))
                            console.print()
                        elif event["type"] == "context_status":
                            context_status = event["status"]

                    if spinner_active and status_ctx:
                        status_ctx.stop()
                    if response_text.strip():
                        console.print("[bold cyan]Assistant:[/bold cyan]")
                        console.print(Markdown(response_text))

                    # Check if a practice session was created on the assistant
                    practice_session = getattr(assistant, "_practice_session", None)
                    if practice_session and not practice_session.is_finished:
                        run_practice_loop(console, assistant, practice_session, session)
                        # Clean up
                        assistant._practice_session = None
                    elif not practice_session:
                        console.print("[yellow]Could not start practice session. Try specifying a deck name.[/yellow]")

                    if context_status:
                        console.print(create_context_bar(context_status))

                    add_exchange(user_input, full_response, tool_calls if tool_calls else None)

                except Exception as e:
                    if spinner_active and status_ctx:
                        status_ctx.stop()
                    console.print(f"\n[red]Error: {e}[/red]")

                console.print()
                continue

            if user_input.lower().startswith("quiz"):
                # Parse quiz command: quiz [--level LEVEL] [--topic TOPIC] [--count N]
                parts = user_input.strip().split()
                level = None
                topic = None
                count = 5

                idx = 1
                while idx < len(parts):
                    if parts[idx] == "--level" and idx + 1 < len(parts):
                        level = parts[idx + 1].upper()
                        idx += 2
                    elif parts[idx] == "--topic" and idx + 1 < len(parts):
                        # Collect remaining as topic
                        topic = " ".join(parts[idx + 1:])
                        break
                    elif parts[idx] == "--count" and idx + 1 < len(parts):
                        try:
                            count = int(parts[idx + 1])
                        except ValueError:
                            pass
                        idx += 2
                    else:
                        idx += 1

                # Default level
                if not level:
                    level = "A1"

                # If no topic specified, show topic selection
                if not topic:
                    console.print(create_quiz_topic_panel(level))
                    try:
                        choice = session.prompt(
                            [("class:prompt", f"Select topic ({level}): ")],
                        ).strip()
                    except (KeyboardInterrupt, EOFError):
                        console.print()
                        continue

                    if choice.lower() in ("back", "cancel", ""):
                        console.print()
                        continue

                    topics = GRAMMAR_TOPICS.get(level, [])
                    if choice.isdigit():
                        idx_choice = int(choice) - 1
                        if 0 <= idx_choice < len(topics):
                            topic = topics[idx_choice]
                        else:
                            console.print(f"[red]Invalid choice. Pick 1-{len(topics)}.[/red]")
                            console.print()
                            continue
                    else:
                        # Try to match by name
                        matched = [t for t in topics if choice.lower() in t.lower()]
                        if len(matched) == 1:
                            topic = matched[0]
                        elif len(matched) > 1:
                            console.print(f"[yellow]Ambiguous match: {', '.join(matched[:3])}[/yellow]")
                            console.print()
                            continue
                        else:
                            topic = choice  # Use as-is

                console.print(f"[dim]Starting grammar quiz: {topic} ({level}), {count} questions...[/dim]")
                console.print()

                # Send to assistant to trigger the start_grammar_quiz tool
                quiz_prompt = (
                    f"Start a grammar quiz on '{topic}' at {level} level with {count} questions. "
                    f"Use the start_grammar_quiz tool."
                )

                response_text = ""
                full_response = ""
                context_status = None
                spinner_active = False
                status_ctx = None
                tool_calls = []

                try:
                    for event in assistant.chat(quiz_prompt):
                        if event["type"] == "text_delta":
                            if not spinner_active:
                                status_ctx = console.status("[cyan]Generating quiz...[/cyan]", spinner="dots")
                                status_ctx.start()
                                spinner_active = True
                            response_text += event["content"]
                            full_response += event["content"]
                        elif event["type"] == "tool_use":
                            if spinner_active and status_ctx:
                                status_ctx.stop()
                                spinner_active = False
                                if response_text.strip():
                                    console.print("[bold cyan]Assistant:[/bold cyan]")
                                    console.print(Markdown(response_text))
                                response_text = ""
                            console.print()
                            console.print(create_tool_panel(event["name"], event["input"]))
                            tool_summary = _summarize_tool_input(event["name"], event["input"])
                            tool_calls.append({"name": event["name"], "summary": tool_summary})
                        elif event["type"] == "tool_result":
                            console.print(create_result_panel(event["name"], event["result"]))
                            console.print()
                        elif event["type"] == "context_status":
                            context_status = event["status"]

                    if spinner_active and status_ctx:
                        status_ctx.stop()
                    if response_text.strip():
                        console.print("[bold cyan]Assistant:[/bold cyan]")
                        console.print(Markdown(response_text))

                    # Check if a quiz session was created
                    quiz_session = getattr(assistant, "_quiz_session", None)
                    if quiz_session and quiz_session.questions:
                        run_quiz_loop(console, assistant, session)
                        assistant._quiz_session = None
                    elif not quiz_session:
                        console.print("[yellow]Could not start quiz. Try again.[/yellow]")

                    if context_status:
                        console.print(create_context_bar(context_status))

                    add_exchange(quiz_prompt, full_response, tool_calls if tool_calls else None)

                except Exception as e:
                    if spinner_active and status_ctx:
                        status_ctx.stop()
                    console.print(f"\n[red]Error: {e}[/red]")

                console.print()
                continue

            if user_input.lower().startswith("converse"):
                # Parse converse command: converse [--level LEVEL] [--scenario SCENARIO]
                parts = user_input.strip().split()
                level = None
                scenario = None
                character = None

                idx = 1
                while idx < len(parts):
                    if parts[idx] == "--level" and idx + 1 < len(parts):
                        level = parts[idx + 1].upper()
                        idx += 2
                    elif parts[idx] == "--scenario" and idx + 1 < len(parts):
                        # Collect remaining as scenario
                        scenario = " ".join(parts[idx + 1:])
                        break
                    elif parts[idx] == "--character" and idx + 1 < len(parts):
                        character = " ".join(parts[idx + 1:])
                        break
                    else:
                        idx += 1

                # Default level
                if not level:
                    level = "B1"

                # If no scenario, show options
                if not scenario:
                    scenarios_by_level = {
                        "A2": ["ordering_food", "asking_directions", "hotel_checkin", "shopping"],
                        "B1": ["job_interview", "doctor_visit", "phone_call", "apartment_rental"],
                        "B2": ["debate", "negotiation", "complaint", "storytelling"],
                    }
                    available = scenarios_by_level.get(level, scenarios_by_level["B1"])

                    scenario_panel_content = Text()
                    scenario_panel_content.append(f"Conversation Scenarios - {level}\n\n", style="bold")
                    for i, sc in enumerate(available, 1):
                        label = sc.replace("_", " ").title()
                        scenario_panel_content.append(f"  {i}. ", style="cyan")
                        scenario_panel_content.append(f"{label}\n", style="white")
                    scenario_panel_content.append("\n")
                    scenario_panel_content.append("Enter a number, scenario name, or 'back' to cancel.", style="dim")

                    console.print(Panel(
                        scenario_panel_content,
                        title="[bold bright_green]CONVERSATION SIMULATION[/bold bright_green]",
                        border_style="bright_green",
                        padding=(1, 2),
                    ))

                    try:
                        choice = session.prompt(
                            [("class:prompt", f"Select scenario ({level}): ")],
                        ).strip()
                    except (KeyboardInterrupt, EOFError):
                        console.print()
                        continue

                    if choice.lower() in ("back", "cancel", ""):
                        console.print()
                        continue

                    if choice.isdigit():
                        idx_choice = int(choice) - 1
                        if 0 <= idx_choice < len(available):
                            scenario = available[idx_choice]
                        else:
                            console.print(f"[red]Invalid choice. Pick 1-{len(available)}.[/red]")
                            console.print()
                            continue
                    else:
                        # Try to match by name
                        matched = [s for s in available if choice.lower().replace(" ", "_") in s]
                        if len(matched) == 1:
                            scenario = matched[0]
                        elif len(matched) > 1:
                            console.print(f"[yellow]Ambiguous: {', '.join(matched[:3])}[/yellow]")
                            console.print()
                            continue
                        else:
                            scenario = choice  # Custom scenario

                console.print(f"[dim]Starting conversation: {scenario} ({level})...[/dim]")
                console.print()

                # Send to assistant to trigger start_conversation_sim
                converse_prompt = (
                    f"Start a conversation simulation with scenario '{scenario}' at {level} level."
                )
                if character:
                    converse_prompt += f" Play the character: {character}."
                converse_prompt += " Use the start_conversation_sim tool."

                response_text = ""
                full_response = ""
                context_status = None
                spinner_active = False
                status_ctx = None
                tool_calls = []

                try:
                    for event in assistant.chat(converse_prompt):
                        if event["type"] == "text_delta":
                            if not spinner_active:
                                status_ctx = console.status("[cyan]Setting up conversation...[/cyan]", spinner="dots")
                                status_ctx.start()
                                spinner_active = True
                            response_text += event["content"]
                            full_response += event["content"]
                        elif event["type"] == "tool_use":
                            if spinner_active and status_ctx:
                                status_ctx.stop()
                                spinner_active = False
                                if response_text.strip():
                                    console.print("[bold cyan]Assistant:[/bold cyan]")
                                    console.print(Markdown(response_text))
                                response_text = ""
                            console.print()
                            console.print(create_tool_panel(event["name"], event["input"]))
                            tool_summary = _summarize_tool_input(event["name"], event["input"])
                            tool_calls.append({"name": event["name"], "summary": tool_summary})
                        elif event["type"] == "tool_result":
                            console.print(create_result_panel(event["name"], event["result"]))
                            console.print()
                        elif event["type"] == "context_status":
                            context_status = event["status"]

                    if spinner_active and status_ctx:
                        status_ctx.stop()

                    # Show Claude's opening lines (in-character greeting)
                    if response_text.strip():
                        char_label = (character or scenario.replace("_", " ")).split(",")[0].strip()[:30]
                        console.print(Panel(
                            Markdown(response_text),
                            title=f"[bold bright_green]{char_label}[/bold bright_green]",
                            border_style="bright_green",
                            padding=(0, 2),
                        ))

                    # Check if a conversation sim was created
                    sim_data = getattr(assistant, "_conversation_sim", None)
                    if sim_data:
                        run_conversation_loop(console, assistant, sim_data, session)
                    else:
                        console.print("[yellow]Could not start conversation. Try again.[/yellow]")

                    if context_status:
                        console.print(create_context_bar(context_status))

                    add_exchange(converse_prompt, full_response, tool_calls if tool_calls else None)

                except Exception as e:
                    if spinner_active and status_ctx:
                        status_ctx.stop()
                    console.print(f"\n[red]Error: {e}[/red]")

                console.print()
                continue

            # Process with assistant
            console.print()
            response_text = ""
            full_response = ""  # Collect all response text for logging
            context_status = None
            spinner_active = False
            status_ctx = None
            tool_calls = []  # Track tool calls for logging
            delegate_progress = None  # Rich Progress for delegate operations
            delegate_task = None

            try:
                for event in assistant.chat(user_input):
                    if event["type"] == "text_delta":
                        # Collect text for markdown rendering
                        if not spinner_active:
                            status_ctx = console.status("[cyan]Thinking...[/cyan]", spinner="dots")
                            status_ctx.start()
                            spinner_active = True
                        response_text += event["content"]
                        full_response += event["content"]

                    elif event["type"] == "tool_use":
                        if spinner_active and status_ctx:
                            status_ctx.stop()
                            spinner_active = False
                            # Render any collected text before tool call
                            if response_text.strip():
                                console.print("[bold cyan]Assistant:[/bold cyan]")
                                console.print(Markdown(response_text))
                            response_text = ""
                        console.print()
                        console.print(create_tool_panel(event["name"], event["input"]))

                        # Track tool call for logging
                        tool_summary = _summarize_tool_input(event["name"], event["input"])
                        tool_calls.append({
                            "name": event["name"],
                            "summary": tool_summary
                        })

                    elif event["type"] == "delegate_progress":
                        # Handle delegate progress events with a progress bar
                        if delegate_progress is None:
                            delegate_progress = Progress(
                                SpinnerColumn(),
                                TextColumn("[cyan]{task.description}"),
                                BarColumn(),
                                TaskProgressColumn(),
                                TextColumn("{task.completed}/{task.total}"),
                                console=console,
                            )
                            delegate_progress.start()
                            delegate_task = delegate_progress.add_task(
                                "Processing cards...",
                                total=event["total"]
                            )

                        delegate_progress.update(
                            delegate_task,
                            completed=event["completed"],
                            description=f"Processing: {event['current_card'][:30]}..."
                            if event.get("current_card")
                            else "Processing cards..."
                        )

                        # Stop progress bar when complete
                        if event["completed"] == event["total"]:
                            delegate_progress.stop()
                            delegate_progress = None
                            delegate_task = None

                    elif event["type"] == "tool_result":
                        # Ensure progress bar is stopped before showing result
                        if delegate_progress is not None:
                            delegate_progress.stop()
                            delegate_progress = None
                            delegate_task = None
                        console.print(create_result_panel(event["name"], event["result"]))
                        console.print()

                    elif event["type"] == "error":
                        if spinner_active and status_ctx:
                            status_ctx.stop()
                            spinner_active = False
                        if delegate_progress is not None:
                            delegate_progress.stop()
                            delegate_progress = None
                        console.print(f"[yellow]{event['content']}[/yellow]")

                    elif event["type"] == "context_status":
                        context_status = event["status"]

                # Ensure progress bar is stopped
                if delegate_progress is not None:
                    delegate_progress.stop()
                    delegate_progress = None

                # Stop spinner and render final response with markdown
                if spinner_active and status_ctx:
                    status_ctx.stop()
                if response_text.strip():
                    console.print("[bold cyan]Assistant:[/bold cyan]")
                    console.print(Markdown(response_text))

                # Show context usage bar
                if context_status:
                    console.print(create_context_bar(context_status))

                # Save exchange to chat log
                add_exchange(user_input, full_response, tool_calls if tool_calls else None)

            except Exception as e:
                # Ensure cleanup on error
                if delegate_progress is not None:
                    delegate_progress.stop()
                console.print(f"\n[red]Error: {e}[/red]")

            console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Use 'exit' to quit[/dim]")
            continue
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break


def run_worker():
    """Run a stateless worker chat session.

    This is a lightweight chat mode that:
    - Does NOT read or write conversation state files
    - Does NOT update learning summary, streaks, or progress
    - Does NOT persist between sessions
    - CAN read/write Anki cards via AnkiConnect
    - Can run in parallel with a regular chat window

    Use this for bulk card editing, deck management, etc.
    """
    console = Console()

    # Check Anki connection
    anki = AnkiClient()
    if not anki.ping():
        console.print(
            "[red]Cannot connect to Anki[/red]\n"
            "[dim]Make sure Anki is running with AnkiConnect installed.[/dim]"
        )
        sys.exit(1)

    # Initialize stateless assistant
    try:
        assistant = AnkiAssistant(stateless=True)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    console.print()
    worker_text = Text()
    worker_text.append("ANKI WORKER", style="bold yellow")
    worker_text.append("\n")
    worker_text.append("Stateless mode — no files read or written", style="dim")
    worker_text.append("\n")
    worker_text.append("Safe to run alongside a chat session", style="dim")
    worker_text.justify = "center"
    console.print(Panel(worker_text, border_style="yellow", box=box.DOUBLE))
    console.print("[dim]Type your instructions. Use 'exit' to quit.[/dim]\n")

    session: PromptSession = PromptSession(style=PROMPT_STYLE)

    while True:
        try:
            user_input = session.prompt(
                [("class:prompt", "Worker: ")],
            ).strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                console.print("[dim]Worker session ended.[/dim]")
                break

            if user_input.lower() in ("clear", "new"):
                assistant.messages.clear()
                assistant.input_tokens_used = 0
                assistant.output_tokens_used = 0
                console.print("[dim]Conversation cleared.[/dim]\n")
                continue

            if user_input.lower() == "status":
                status = assistant.get_context_status()
                console.print(f"[bold]Model:[/bold] [green]{status['model_name']}[/green]")
                console.print(create_context_bar(status))
                console.print(f"[dim]Messages: {len(assistant.messages)}[/dim]\n")
                continue

            # Stream Claude's response
            full_response = ""
            spinner_active = False
            status_ctx = None

            try:
                for event in assistant.chat(user_input):
                    if event["type"] == "text_delta":
                        if spinner_active and status_ctx:
                            status_ctx.stop()
                            spinner_active = False
                        console.print(event["content"], end="", highlight=False)
                        full_response += event["content"]
                    elif event["type"] == "text_stop":
                        console.print()
                    elif event["type"] == "tool_use":
                        if spinner_active and status_ctx:
                            status_ctx.stop()
                            spinner_active = False
                        console.print(create_tool_panel(event["name"], event["input"]))
                    elif event["type"] == "tool_result":
                        console.print(create_result_panel(event["name"], event["result"]))
                        status_ctx = console.status("[cyan]Thinking...[/cyan]", spinner="dots")
                        status_ctx.start()
                        spinner_active = True
                    elif event["type"] == "context_status":
                        pass

                if spinner_active and status_ctx:
                    status_ctx.stop()

            except Exception as e:
                if spinner_active and status_ctx:
                    status_ctx.stop()
                console.print(f"\n[red]Error: {e}[/red]")

            console.print()

        except KeyboardInterrupt:
            console.print("\n[dim]Use 'exit' to quit[/dim]")
            continue
        except EOFError:
            console.print("\n[dim]Worker session ended.[/dim]")
            break
