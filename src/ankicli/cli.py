"""CLI commands for AnkiWeb CLI."""

import sys

import click
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from . import __version__
from .client import AnkiClient, AnkiConnectError, ConnectionError
from .config import CLAUDE_MODELS, get_model_specs, load_config, save_config

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


def main() -> None:
    """Entry point for the CLI."""
    cli()
