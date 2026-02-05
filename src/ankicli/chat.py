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
    """Create a context usage bar with session stats."""
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

    # Create bar
    bar_width = 30
    filled = int(bar_width * percent / 100)
    empty = bar_width - filled
    bar = "\u2588" * filled + "\u2591" * empty

    text = Text()
    text.append("Context: [", style="dim")
    text.append(bar, style=color)
    text.append("] ", style="dim")
    text.append(f"{percent:.1f}%", style=color)
    text.append(f" ({format_tokens(input_tokens)}/{format_tokens(max_tokens)})", style="dim")

    # Session stats
    session_minutes = status.get("session_minutes", 0)
    session_cards = status.get("session_cards_added", 0)
    if session_minutes > 0 or session_cards > 0:
        text.append("  |  ", style="dim")
        text.append(f"{session_minutes} min", style="cyan")
        if session_cards > 0:
            text.append(f"  +{session_cards} cards", style="green")

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
    console.print(Panel(
        "[bold]Anki Assistant[/bold]\n\n"
        "Chat with Claude to manage your Anki flashcards.\n"
        f"Model: [bold green]{model_specs['name']}[/bold green] [dim]({assistant.model})[/dim]\n\n"
        "Commands:\n"
        "  [cyan]history[/cyan]  - Show recent chat history\n"
        "  [cyan]progress[/cyan] - Show learning progress summary\n"
        "  [cyan]status[/cyan]   - Show context usage\n"
        "  [cyan]model[/cyan]    - Show or change the Claude model\n"
        "  [cyan]notes[/cyan]    - Show saved preferences\n"
        "  [cyan]compact[/cyan]  - Summarize history to free context\n"
        "  [cyan]clear[/cyan]    - Reset conversation\n"
        "  [cyan]new[/cyan]      - Start fresh (discard history)\n"
        "  [cyan]exit[/cyan]     - Quit",
        border_style="cyan",
    ))
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
