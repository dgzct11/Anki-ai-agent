"""CLI commands for AnkiWeb CLI."""

import sys

import click
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from . import __version__
from .client import AnkiClient, AnkiConnectError, ConnectionError
from .config import CLAUDE_MODELS, get_model_specs, load_config, save_config, format_tool_notes_display

console = Console()


def get_client() -> AnkiClient:
    """Get an AnkiConnect client, checking connection first."""
    client = AnkiClient()
    if not client.ping():
        console.print(
            "[red]✗ Cannot connect to Anki.[/red]\n"
            "[dim]Make sure Anki is running with AnkiConnect installed.[/dim]"
        )
        sys.exit(1)
    return client


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Anki CLI - Manage your Anki decks from the terminal.

    Requires Anki desktop running with AnkiConnect plugin installed.
    """
    pass


@cli.command()
def chat() -> None:
    """Start interactive AI chat to manage Anki.

    Chat with Claude to add cards, browse decks, and more.
    Requires ANTHROPIC_API_KEY environment variable.
    """
    from .chat import run_chat
    run_chat()


@cli.command()
def worker() -> None:
    """Start a stateless worker session for bulk card editing.

    A lightweight chat mode that can run alongside a regular chat session.
    Does NOT read or write any state files (conversation, progress, etc.).
    Has full access to Anki for editing cards, searching, and deck management.

    \b
    Use cases:
      - Bulk edit cards while practicing in another window
      - Add cognate hints to existing cards
      - Reorganize tags or decks
      - Any Anki operation that doesn't need learning state
    """
    from .chat import run_worker
    run_worker()


@cli.command()
@click.argument("deck", required=False)
@click.option("-n", "--count", default=10, help="Number of questions (default: 10)")
@click.option("-d", "--direction", default="en_to_es", type=click.Choice(["en_to_es", "es_to_en"]), help="Translation direction")
@click.option("-f", "--focus", default="mixed", type=click.Choice(["due", "new", "mixed", "all"]), help="Card source")
def practice(deck: str | None, count: int, direction: str, focus: str) -> None:
    """Start a translation practice session.

    Practice translating phrases from your Anki deck.
    If DECK is not specified, starts the chat and asks which deck to use.
    """
    from .chat import run_chat
    # We start the chat UI which handles the practice command
    # by simulating the "practice" command input
    import os
    os.environ["_ANKICLI_PRACTICE_ARGS"] = f"{deck or ''} --count {count} --direction {direction} --focus {focus}"
    run_chat()


@cli.command()
@click.option("-t", "--topic", default=None, help="Grammar topic to quiz on")
@click.option("-l", "--level", default="A1", type=click.Choice(["A1", "A2", "B1", "B2"]), help="CEFR level (default: A1)")
@click.option("-n", "--count", default=5, help="Number of questions (default: 5)")
@click.option("-s", "--size", default=None, type=click.Choice(["quick", "assessment", "comprehensive"]), help="Quiz size preset (overrides count)")
def quiz(topic: str | None, level: str, count: int, size: str | None) -> None:
    """Start an interactive grammar quiz.

    Tests grammar knowledge with fill-in-the-blank, multiple choice,
    conjugation, error correction, and sentence transformation questions.
    If TOPIC is not specified, shows a topic selection menu.
    """
    from .chat import run_chat
    import os
    args = f"--level {level} --count {count}"
    if size:
        args += f" --size {size}"
    if topic:
        args += f" --topic {topic}"
    os.environ["_ANKICLI_QUIZ_ARGS"] = args
    run_chat()


@cli.command()
@click.option("-s", "--scenario", default=None, help="Conversation scenario (e.g., ordering_food, job_interview)")
@click.option("-l", "--level", default="B1", type=click.Choice(["A2", "B1", "B2"]), help="CEFR level (default: B1)")
@click.option("-c", "--character", default=None, help="Character for Claude to play")
def converse(scenario: str | None, level: str, character: str | None) -> None:
    """Start a conversation simulation.

    Practice speaking Spanish in a role-play scenario where Claude
    plays a character (waiter, doctor, interviewer, etc.).
    If SCENARIO is not specified, shows a scenario selection menu.
    """
    from .chat import run_chat
    import os
    args = f"--level {level}"
    if scenario:
        args += f" --scenario {scenario}"
    if character:
        args += f" --character {character}"
    os.environ["_ANKICLI_CONVERSE_ARGS"] = args
    run_chat()


@cli.command()
@click.argument("model_id", required=False)
def model(model_id: str | None) -> None:
    """Show or change the Claude model.

    Without arguments, shows the current model and available options.
    With a model ID, switches to that model.
    """
    config = load_config()
    specs = get_model_specs(config.main_model)

    if model_id is None:
        # Show current model and list options
        console.print(f"\n[bold]Current model:[/bold] [green]{specs['name']}[/green] [dim]({config.main_model})[/dim]")
        console.print(f"  Context window: {specs['context_window']:,} tokens")
        console.print(f"  Max output:     {specs['max_output_tokens']:,} tokens\n")
        console.print("[bold]Available models:[/bold]")

        table = Table()
        table.add_column("#", style="cyan", justify="right")
        table.add_column("Model", style="bold")
        table.add_column("ID", style="dim")
        table.add_column("Context", justify="right")
        table.add_column("Max Output", justify="right")
        table.add_column("", style="green")

        for i, (mid, info) in enumerate(CLAUDE_MODELS.items(), 1):
            marker = "current" if mid == config.main_model else ""
            table.add_row(
                str(i),
                info["name"],
                mid,
                f"{info['context_window'] // 1000}K",
                f"{info['max_output_tokens'] // 1000}K",
                marker,
            )
        console.print(table)
        console.print(f"\n[dim]Usage: ankicli model <model-id>[/dim]")
    else:
        # Switch model
        if model_id in CLAUDE_MODELS:
            config.main_model = model_id
            save_config(config)
            new_specs = get_model_specs(model_id)
            console.print(
                f"[green]Switched to {new_specs['name']}[/green] [dim]({model_id})[/dim]\n"
                f"  Context: {new_specs['context_window']:,} | Max output: {new_specs['max_output_tokens']:,}"
            )
        else:
            # Try partial match
            matches = [m for m in CLAUDE_MODELS if model_id.lower() in m.lower()]
            if len(matches) == 1:
                config.main_model = matches[0]
                save_config(config)
                new_specs = get_model_specs(matches[0])
                console.print(
                    f"[green]Switched to {new_specs['name']}[/green] [dim]({matches[0]})[/dim]\n"
                    f"  Context: {new_specs['context_window']:,} | Max output: {new_specs['max_output_tokens']:,}"
                )
            elif len(matches) > 1:
                console.print(f"[yellow]Ambiguous match: {', '.join(matches)}[/yellow]")
            else:
                console.print(f"[red]Unknown model '{model_id}'.[/red]")
                console.print("[dim]Run 'ankicli model' to see available models.[/dim]")
                sys.exit(1)


@cli.command()
def status() -> None:
    """Check connection to Anki."""
    client = AnkiClient()
    if client.ping():
        console.print("[green]✓ Connected to Anki[/green]")
    else:
        console.print(
            "[red]✗ Cannot connect to Anki[/red]\n"
            "[dim]Make sure Anki is running with AnkiConnect installed.[/dim]"
        )
        sys.exit(1)


@cli.command()
def decks() -> None:
    """List all decks."""
    client = get_client()

    try:
        deck_list = client.get_decks()
    except AnkiConnectError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        sys.exit(1)

    if not deck_list:
        console.print("[yellow]No decks found[/yellow]")
        return

    table = Table(title="Your Decks")
    table.add_column("Deck", style="cyan")
    table.add_column("New", justify="right", style="blue")
    table.add_column("Learn", justify="right", style="red")
    table.add_column("Review", justify="right", style="green")
    table.add_column("Total Due", justify="right", style="bold")

    for deck in deck_list:
        table.add_row(
            deck.name,
            str(deck.new_count),
            str(deck.learn_count),
            str(deck.review_count),
            str(deck.total_due),
        )

    console.print(table)


@cli.command()
@click.argument("deck")
@click.option("-f", "--front", help="Card front content")
@click.option("-b", "--back", help="Card back content")
@click.option("-t", "--tags", help="Tags (space-separated)")
@click.option("-n", "--note-type", default="Basic", help="Note type (default: Basic)")
def add(
    deck: str,
    front: str | None,
    back: str | None,
    tags: str | None,
    note_type: str,
) -> None:
    """Add a card to a deck.

    If front/back are not provided, prompts interactively.
    """
    client = get_client()

    # Interactive mode if front/back not provided
    if not front:
        front = Prompt.ask("Front")
    if not back:
        back = Prompt.ask("Back")

    tag_list = tags.split() if tags else None

    try:
        note_id = client.add_card(deck, front, back, tag_list, note_type)
        console.print(f"[green]✓ Card added (note ID: {note_id})[/green]")

        # Show what was added
        console.print()
        console.print(f"[dim]Deck:[/dim] {deck}")
        console.print(f"[dim]Front:[/dim] {front[:50]}{'...' if len(front) > 50 else ''}")
        console.print(f"[dim]Back:[/dim] {back[:50]}{'...' if len(back) > 50 else ''}")
        if tag_list:
            console.print(f"[dim]Tags:[/dim] {', '.join(tag_list)}")

    except AnkiConnectError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("query")
@click.option("-l", "--limit", default=20, help="Maximum results to show")
def search(query: str, limit: int) -> None:
    """Search for cards.

    Uses Anki search syntax (e.g., 'deck:MyDeck', 'tag:mytag', 'front:*word*').
    """
    client = get_client()

    try:
        cards = client.search_cards(query, limit=limit)
    except AnkiConnectError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        sys.exit(1)

    if not cards:
        console.print("[yellow]No cards found[/yellow]")
        return

    table = Table(title=f"Search Results: {query}")
    table.add_column("Front", style="cyan", max_width=40)
    table.add_column("Back", style="green", max_width=40)
    table.add_column("Tags", style="dim", max_width=20)

    for card in cards:
        front_preview = card.front[:40] + "..." if len(card.front) > 40 else card.front
        back_preview = card.back[:40] + "..." if len(card.back) > 40 else card.back
        tags_str = ", ".join(card.tags) if card.tags else ""
        table.add_row(front_preview, back_preview, tags_str)

    console.print(table)
    console.print(f"\n[dim]Found {len(cards)} card(s)[/dim]")


@cli.command()
def note_types() -> None:
    """List available note types."""
    client = get_client()

    try:
        types = client.get_note_types()
    except AnkiConnectError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        sys.exit(1)

    if not types:
        console.print("[yellow]No note types found[/yellow]")
        return

    table = Table(title="Note Types")
    table.add_column("Name", style="cyan")
    table.add_column("Fields", style="dim")

    for nt in types:
        fields_str = ", ".join(nt.fields) if nt.fields else ""
        table.add_row(nt.name, fields_str)

    console.print(table)


@cli.command()
@click.argument("deck")
def bulk_add(deck: str) -> None:
    """Add multiple cards interactively.

    Prompts for front/back repeatedly until you enter an empty front.
    """
    client = get_client()

    console.print(f"[bold]Adding cards to '{deck}'[/bold]")
    console.print("[dim]Enter empty front to finish[/dim]\n")

    count = 0
    while True:
        front = Prompt.ask(f"[{count + 1}] Front")
        if not front:
            break

        back = Prompt.ask(f"[{count + 1}] Back")
        if not back:
            console.print("[yellow]Skipping card with empty back[/yellow]")
            continue

        tags_str = Prompt.ask(f"[{count + 1}] Tags (optional)", default="")
        tags = tags_str.split() if tags_str else None

        try:
            client.add_card(deck, front, back, tags)
            count += 1
            console.print(f"[green]✓ Card {count} added[/green]\n")
        except AnkiConnectError as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            console.print("[yellow]Continuing...[/yellow]\n")

    console.print(f"\n[bold green]Done! Added {count} card(s) to '{deck}'[/bold green]")


@cli.command()
def sync() -> None:
    """Sync with AnkiWeb."""
    client = get_client()

    with console.status("Syncing with AnkiWeb..."):
        try:
            client.sync()
            console.print("[green]✓ Sync complete[/green]")
        except AnkiConnectError as e:
            console.print(f"[red]✗ Sync failed: {e}[/red]")
            sys.exit(1)


@cli.command()
@click.argument("name")
def create_deck(name: str) -> None:
    """Create a new deck."""
    client = get_client()

    try:
        deck_id = client.create_deck(name)
        console.print(f"[green]✓ Deck '{name}' created (ID: {deck_id})[/green]")
    except AnkiConnectError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("deck")
@click.option("-l", "--limit", default=50, help="Maximum cards to show")
def cards(deck: str, limit: int) -> None:
    """List cards in a deck."""
    client = get_client()

    try:
        card_list = client.get_deck_cards(deck, limit=limit)
    except AnkiConnectError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        sys.exit(1)

    if not card_list:
        console.print(f"[yellow]No cards found in '{deck}'[/yellow]")
        return

    table = Table(title=f"Cards in '{deck}'")
    table.add_column("Front", style="cyan", max_width=40)
    table.add_column("Back", style="green", max_width=40)
    table.add_column("Tags", style="dim", max_width=20)

    for card in card_list:
        front_preview = card.front[:40] + "..." if len(card.front) > 40 else card.front
        back_preview = card.back[:40] + "..." if len(card.back) > 40 else card.back
        tags_str = ", ".join(card.tags) if card.tags else ""
        table.add_row(front_preview, back_preview, tags_str)

    console.print(table)
    console.print(f"\n[dim]Showing {len(card_list)} card(s)[/dim]")


@cli.group()
def notes() -> None:
    """Manage saved preferences (tool notes).

    Without a subcommand, shows all saved preferences.
    """
    pass


@notes.command("list")
def notes_list() -> None:
    """Show all saved preferences."""
    config = load_config()
    console.print(format_tool_notes_display(config))


@notes.command("set")
@click.argument("tool_name")
@click.argument("note")
def notes_set(tool_name: str, note: str) -> None:
    """Set a preference for a tool.

    TOOL_NAME is the tool to attach the note to (or 'general' for global preferences).
    NOTE is the preference text.
    """
    config = load_config()
    config.tool_notes[tool_name] = note
    save_config(config)
    console.print(f"[green]Preference saved for '{tool_name}':[/green] {note}")


@notes.command("remove")
@click.argument("tool_name")
def notes_remove(tool_name: str) -> None:
    """Remove a saved preference.

    TOOL_NAME is the tool whose preference to remove (or 'general').
    """
    config = load_config()
    if tool_name in config.tool_notes:
        del config.tool_notes[tool_name]
        save_config(config)
        console.print(f"[green]Preference removed for '{tool_name}'.[/green]")
    else:
        console.print(f"[yellow]No preference found for '{tool_name}'.[/yellow]")
        sys.exit(1)


@notes.command("clear")
def notes_clear() -> None:
    """Clear all saved preferences."""
    config = load_config()
    if not config.tool_notes:
        console.print("[dim]No preferences to clear.[/dim]")
        return
    count = len(config.tool_notes)
    config.tool_notes.clear()
    save_config(config)
    console.print(f"[green]Cleared {count} preference(s).[/green]")


@cli.group()
def cefr() -> None:
    """CEFR vocabulary progress tracking.

    Track your Spanish vocabulary against official CEFR level word lists.
    """
    pass


@cefr.command("status")
def cefr_status() -> None:
    """Show CEFR progress overview for all levels."""
    from .cefr import CEFRData, load_progress_cache, match_cards_to_cefr, save_progress_cache, format_progress_text

    cefr_data = CEFRData()
    cefr_data.load()

    level_counts = cefr_data.get_level_counts()
    if not any(level_counts.values()):
        console.print("[yellow]No CEFR data files found. Run the data generation task first.[/yellow]")
        return

    progress = load_progress_cache()
    if progress is None:
        console.print("[dim]No cached progress. Scanning cards...[/dim]")
        client = get_client()
        progress = match_cards_to_cefr(client, cefr_data)
        save_progress_cache(progress)

    console.print(format_progress_text(progress))


@cefr.command("progress")
@click.argument("level")
@click.option("--unknown", is_flag=True, help="Show unknown words")
def cefr_progress(level: str, unknown: bool) -> None:
    """Show detailed progress for a specific CEFR level (U7 deep-dive)."""
    from .cefr import CEFRData, load_progress_cache, match_cards_to_cefr, save_progress_cache, format_progress_text
    from .grammar_quiz import get_topic_mastery

    level = level.upper()
    if level not in ("A1", "A2", "B1", "B2", "C1", "C2"):
        console.print(f"[red]Invalid level: {level}. Use A1, A2, B1, B2, C1, or C2.[/red]")
        return

    cefr_data = CEFRData()
    cefr_data.load()

    progress = load_progress_cache()
    if progress is None:
        client = get_client()
        progress = match_cards_to_cefr(client, cefr_data)
        save_progress_cache(progress)

    # U7: Rich deep-dive panel
    lp = progress.get(level)
    if lp:
        from .chat import create_cefr_deep_dive_panel
        grammar_mastery = get_topic_mastery()
        # Convert LevelProgress object to dict for the panel
        level_dict = {
            "words_known": lp.words_known,
            "words_total": lp.words_total,
            "categories": {
                name: {"known": cat.known, "total": cat.total, "percent": cat.percent}
                for name, cat in lp.categories.items()
            },
        }
        console.print(create_cefr_deep_dive_panel(level, level_dict, grammar_mastery))
    else:
        console.print(format_progress_text(progress, level=level, show_unknown=unknown))


@cefr.command("suggest")
@click.option("-l", "--level", help="CEFR level (auto-detect if omitted)")
@click.option("-n", "--count", default=10, help="Number of suggestions")
def cefr_suggest(level: str | None, count: int) -> None:
    """Suggest words to learn next based on CEFR gaps."""
    from .cefr import CEFRData, load_progress_cache, match_cards_to_cefr, save_progress_cache, get_suggestions, format_suggestions_text

    cefr_data = CEFRData()
    cefr_data.load()

    progress = load_progress_cache()
    if progress is None:
        client = get_client()
        progress = match_cards_to_cefr(client, cefr_data)
        save_progress_cache(progress)

    suggestions = get_suggestions(cefr_data, progress, level=level, count=count)
    console.print(format_suggestions_text(suggestions))


@cefr.command("scan")
@click.option("-d", "--deck", help="Deck to scan (all decks if omitted)")
def cefr_scan(deck: str | None) -> None:
    """Rescan Anki cards against CEFR word lists."""
    from .cefr import CEFRData, match_cards_to_cefr, save_progress_cache, invalidate_cache, format_progress_text

    client = get_client()
    cefr_data = CEFRData()
    cefr_data.load()

    with console.status("Scanning cards against CEFR lists..."):
        invalidate_cache()
        progress = match_cards_to_cefr(client, cefr_data, deck)
        save_progress_cache(progress)

    console.print("[green]Scan complete.[/green]\n")
    console.print(format_progress_text(progress))


@cli.command()
def errors() -> None:
    """Show recurring error patterns from practice sessions."""
    from .error_journal import get_error_patterns, format_error_patterns_text

    patterns = get_error_patterns(min_count=1, limit=20)
    console.print(format_error_patterns_text(patterns))


@cli.command()
@click.argument("action", type=click.Choice(["list", "add", "remove", "clear"]), default="list")
@click.argument("word", required=False)
@click.option("--english", "-e", help="English translation (for add)")
def vocab(action: str, word: str | None, english: str | None) -> None:
    """Manage your vocab staging list.

    Save words you might want to add to your Anki deck later.

    \b
    Examples:
      ankicli vocab list
      ankicli vocab add comprar -e "to buy"
      ankicli vocab remove comprar
      ankicli vocab clear
    """
    from .tool_handlers import _load_vocab_list, _save_vocab_list

    if action == "list":
        items = _load_vocab_list()
        if not items:
            console.print("[dim]Your vocab list is empty.[/dim]")
            return
        console.print(f"[cyan]Vocab list ({len(items)} words):[/cyan]\n")
        for i, item in enumerate(items, 1):
            w = item.get("word", "?")
            en = item.get("english", "?")
            level = item.get("level", "")
            ctx = item.get("context", "")
            added = item.get("added", "")
            line = f"  {i}. [bold]{w}[/bold] — {en}"
            if level:
                line += f" [cyan][{level}][/cyan]"
            if ctx:
                line += f" [dim]({ctx})[/dim]"
            if added:
                line += f" [dim][{added}][/dim]"
            console.print(line)

    elif action == "add":
        if not word:
            console.print("[red]Please provide a word: ankicli vocab add <word> -e <english>[/red]")
            return
        if not english:
            console.print("[red]Please provide an English translation with -e[/red]")
            return
        items = _load_vocab_list()
        for item in items:
            if item.get("word", "").lower() == word.lower():
                console.print(f"[yellow]'{word}' is already on your vocab list.[/yellow]")
                return
        from datetime import datetime
        items.append({"word": word, "english": english, "context": "CLI", "level": "", "added": datetime.now().isoformat()[:10]})
        _save_vocab_list(items)
        console.print(f"[green]Added '{word}' ({english}) to your vocab list.[/green]")

    elif action == "remove":
        if not word:
            console.print("[red]Please provide a word: ankicli vocab remove <word>[/red]")
            return
        items = _load_vocab_list()
        new_items = [item for item in items if item.get("word", "").lower() != word.lower()]
        if len(new_items) == len(items):
            console.print(f"[yellow]'{word}' was not found on your vocab list.[/yellow]")
            return
        _save_vocab_list(new_items)
        console.print(f"[green]Removed '{word}' from your vocab list.[/green]")

    elif action == "clear":
        _save_vocab_list([])
        console.print("[green]Vocab list cleared.[/green]")


@cli.command()
@click.option("--force", is_flag=True, help="Generate a new challenge even if today's was already done")
def daily(force: bool) -> None:
    """Show the daily word challenge.

    Picks a word from your CEFR gap areas and presents a mini exercise.
    """
    import json as _json
    import random
    from datetime import date
    from .paths import DAILY_CHALLENGE_FILE, ensure_data_dir
    from .cefr import CEFRData, load_progress_cache, match_cards_to_cefr, save_progress_cache

    today = date.today().isoformat()

    ensure_data_dir()
    state = {}
    if DAILY_CHALLENGE_FILE.exists():
        try:
            with open(DAILY_CHALLENGE_FILE) as f:
                state = _json.load(f)
        except (ValueError, IOError):
            state = {}

    if state.get("date") == today and not force:
        console.print(f"[bold cyan]Word of the Day:[/bold cyan] {state.get('word', '?')}")
        console.print(f"[dim]English:[/dim] {state.get('english', '?')}")
        console.print(f"[dim]Level:[/dim] {state.get('level', '?')} | Category: {state.get('category', '?')}")
        console.print("\n[dim]Use --force to generate a new challenge.[/dim]")
        return

    cefr_data = CEFRData()
    cefr_data.load()

    progress = load_progress_cache()
    if progress is None:
        client = get_client()
        progress = match_cards_to_cefr(client, cefr_data)
        save_progress_cache(progress)

    challenge_word = None
    challenge_level = None
    for level_key in ("A1", "A2", "B1", "B2", "C1", "C2"):
        level_data = progress.get(level_key, {})
        unknown = level_data.get("unknown_words", [])
        if unknown:
            yesterday_word = state.get("word", "")
            candidates = [w for w in unknown if w != yesterday_word]
            if not candidates:
                candidates = unknown
            challenge_word = random.choice(candidates[:20])
            challenge_level = level_key
            break

    if challenge_word is None:
        console.print("[green]You know all CEFR words! No daily challenge needed.[/green]")
        return

    word_info = cefr_data._word_index.get(challenge_word)
    english = ""
    category = ""
    if word_info:
        _, cefr_word = word_info
        english = cefr_word.english
        category = cefr_word.category

    state = {
        "date": today,
        "word": challenge_word,
        "english": english,
        "level": challenge_level,
        "category": category,
        "completed": False,
    }
    with open(DAILY_CHALLENGE_FILE, "w") as f:
        _json.dump(state, f, indent=2, ensure_ascii=False)

    console.print(f"\n[bold cyan]Daily Challenge - {today}[/bold cyan]")
    console.print(f"[bold]Word of the Day:[/bold] [green]{challenge_word}[/green]")
    console.print(f"[dim]English:[/dim] {english}")
    console.print(f"[dim]Level:[/dim] {challenge_level} | Category: {category}")
    console.print(f"\n[dim]Start a chat session to practice with this word![/dim]")


@cli.command()
@click.option("--detailed", is_flag=True, help="Show full progress dashboard with all sections")
def progress(detailed: bool) -> None:
    """Show progress dashboard with streaks, skills, and weak spots.

    Shows study streaks, skills radar, and optionally time-based progress
    and weak spots analysis.
    """
    from .progress_tracking import (
        get_streaks_summary,
        get_skills_radar,
        get_progress_over_time,
        get_weak_spots,
        format_skills_radar_text,
        format_progress_over_time_text,
    )
    from .learning_summary import load_summary
    from .error_journal import get_error_patterns

    # Streaks
    streaks = get_streaks_summary()
    console.print(f"\n[bold cyan]Study Streaks[/bold cyan]")
    console.print(f"  Current streak: [bold]{streaks['current_streak']}[/bold] day(s)")
    console.print(f"  Longest streak: {streaks['longest_streak']} day(s)")
    console.print(f"  Active in last 30 days: {streaks['last_30_days_active']}")

    # Last 7 days
    days_line = "  Last 7 days: "
    for day_str, active in streaks["last_7_days"].items():
        days_line += "[green]##[/green]" if active else "[dim]..[/dim]"
    console.print(days_line)

    # Skills radar
    learning_summary = load_summary()
    quiz_results = learning_summary.get("quiz_results", [])
    cefr_progress = None
    try:
        from .cefr import load_progress_cache
        cefr_progress = load_progress_cache()
    except Exception:
        pass

    collection_stats = None
    try:
        client = get_client()
        collection_stats = client.get_collection_stats()
    except Exception:
        pass

    radar = get_skills_radar(
        collection_stats=collection_stats,
        learning_summary=learning_summary,
        error_journal_entries=get_error_patterns(),
        quiz_results=quiz_results,
        cefr_progress=cefr_progress,
    )
    console.print(f"\n{format_skills_radar_text(radar)}")

    if detailed:
        # Time-based progress
        time_progress = get_progress_over_time(period="month")
        console.print(f"\n{format_progress_over_time_text(time_progress)}")

        # Weak spots
        error_entries = get_error_patterns()
        card_reviews = []
        try:
            card_reviews = client.get_card_reviews()
        except Exception:
            pass

        weak = get_weak_spots(
            quiz_results=quiz_results,
            error_entries=error_entries,
            card_reviews=card_reviews,
        )
        console.print(f"\n{weak['summary']}")


def main() -> None:
    """Entry point for the CLI."""
    cli()
