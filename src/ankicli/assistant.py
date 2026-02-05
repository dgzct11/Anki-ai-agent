"""Claude assistant with Anki tool calling."""

import json
import os
import queue
from pathlib import Path
from typing import Generator

from anthropic import Anthropic
from dotenv import load_dotenv

# Load .env file from current directory or project root
load_dotenv()
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from .client import AnkiClient, AnkiConnectError
from .config import load_config, get_model_specs
from .conversation_store import load_conversation, save_conversation
from .delegate import CardDelegateProcessor, ProgressEvent
from .learning_summary import load_summary, save_summary, format_summary_for_display
from .tools import ANKI_TOOLS

SYSTEM_PROMPT = """You are an Anki flashcard assistant. You help users manage their Anki flashcard decks through conversation.

You can:
- List and browse decks
- Add new flashcards (single or bulk - use add_multiple_cards for efficiency)
- Edit existing cards (single or bulk)
- Delete cards
- Search cards and manage tags
- Move cards between decks
- Create new decks
- Sync with AnkiWeb

## Spanish Vocabulary Card Format

IMPORTANT: Anki uses HTML formatting. Always use HTML tags for formatting cards.

**Front (English):**
- The English definition/meaning
- Keep it clear and concise

**Back (Spanish):**
- The Spanish word (bold)
- For verbs: include conjugations in a clear format
- 5 example sentences showing the word in context
- Use a variety of tenses and conjugations in examples

Example for a verb:
Front: "to run"
Back:
<b>correr</b><br><br>
<b>Conjugation:</b><br>
• yo corro, tú corres, él corre<br>
• pretérito: corrí, corriste, corrió<br>
• imperfecto: corría<br><br>
<b>Examples:</b><br>
1. Corro todas las mañanas en el parque. <i>(present)</i><br>
2. Ayer corrí cinco kilómetros. <i>(preterite)</i><br>
3. Cuando era niño, corría muy rápido. <i>(imperfect)</i><br>
4. Mañana correré en la maratón. <i>(future)</i><br>
5. Si tuviera tiempo, correría más seguido. <i>(conditional)</i>

Example for a noun:
Front: "the book"
Back:
<b>el libro</b> <i>(m.)</i><br><br>
<b>Examples:</b><br>
1. El libro está en la mesa.<br>
2. Me regalaron un libro muy interesante.<br>
3. Los libros de esta biblioteca son antiguos.<br>
4. ¿Has leído este libro?<br>
5. Necesito comprar libros para la clase.

HTML tags to use:
- <b>bold</b> for the Spanish word and section headers
- <i>italic</i> for gender markers, tense labels, notes
- <br> for line breaks
- • for bullet points

## General Guidelines

When creating flashcards:
- For bulk operations, use add_multiple_cards to add many cards at once (10, 20, 50+ cards)
- Before adding, use check_words_exist to avoid duplicates
- Suggest tags when relevant (e.g., "verb", "noun", "adjective", "irregular")

When editing cards:
- First search to find the cards and get their note IDs
- Use update_card for single edits or update_multiple_cards for bulk edits
- Always confirm before deleting cards

When the user wants to add cards, confirm the deck name first by listing available decks if needed.
Be helpful and proactive - if the user mentions a topic they're studying, offer to create relevant flashcards.

## Learning Summary (IMPORTANT)

AFTER successfully adding cards, you MUST call update_learning_summary to update the persistent progress tracker.

For each CEFR level (A1, A2, B1, B2), the summary tracks:
- **what_i_know**: Detailed description of mastered content, vocabulary list, grammar concepts learned, topics covered
- **what_to_learn**: What's still needed to complete the level, vocabulary gaps, grammar gaps, priority topics
- **estimated_coverage**: Percentage of level completion (0-100)

When calling update_learning_summary, provide:
1. The CEFR level (A1, A2, B1, B2)
2. Words added (list of Spanish words/phrases)
3. what_i_know_summary: A detailed text description of what the user now knows at this level
4. grammar_concepts_learned: Any grammar concepts practiced (e.g., "Preterite tense", "Reflexive verbs")
5. topics_covered: Topic areas covered (e.g., "Daily routines", "Travel", "Health")
6. what_to_learn_summary: Update what's still needed to complete this level
7. vocabulary_gaps, grammar_gaps, priority_topics: Lists of what to focus on next
8. estimated_coverage: Updated percentage (be realistic based on CEFR requirements)

This summary persists across sessions and helps track long-term progress.

When asked about progress or what to learn next, use get_learning_summary to review the current state.

## Context Management

Monitor the context usage shown after each response. When context exceeds 50%, proactively use the compact_conversation tool to summarize older messages and free up space. This ensures the conversation can continue smoothly.

Keep responses concise and focused on the task at hand."""


class AnkiAssistant:
    """Claude-powered Anki assistant with tool calling."""

    def __init__(self, model: str | None = None):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Get your API key from https://console.anthropic.com/"
            )

        self.config = load_config()
        self.client = Anthropic(api_key=api_key)
        self.anki = AnkiClient()
        self.model = model or self.config.main_model
        self._model_specs = get_model_specs(self.model)
        self.messages: list[dict] = []
        self.input_tokens_used = 0
        self.output_tokens_used = 0
        self._auto_save = True  # Auto-save conversation after each exchange
        self._progress_queue: queue.Queue[dict] = queue.Queue()

    @property
    def max_context_tokens(self) -> int:
        """Context window size for the current model."""
        return self._model_specs["context_window"]

    @property
    def max_output_tokens(self) -> int:
        """Maximum output tokens for the current model."""
        return self._model_specs["max_output_tokens"]

    @property
    def model_name(self) -> str:
        """Human-readable name for the current model."""
        return self._model_specs["name"]

    @property
    def total_tokens_used(self) -> int:
        """Total tokens used in the conversation."""
        return self.input_tokens_used + self.output_tokens_used

    @property
    def context_usage_percent(self) -> float:
        """Percentage of context window used."""
        return (self.input_tokens_used / self.max_context_tokens) * 100

    def get_context_status(self) -> dict:
        """Get current context usage status."""
        return {
            "input_tokens": self.input_tokens_used,
            "output_tokens": self.output_tokens_used,
            "total_tokens": self.total_tokens_used,
            "max_tokens": self.max_context_tokens,
            "percent_used": self.context_usage_percent,
            "model": self.model,
            "model_name": self.model_name,
        }

    def load_from_disk(self) -> bool:
        """
        Load conversation from disk.

        Returns:
            True if conversation was loaded, False if starting fresh
        """
        data = load_conversation()
        if data["messages"]:
            self.messages = data["messages"]
            self.input_tokens_used = data["input_tokens"]
            self.output_tokens_used = data["output_tokens"]
            return True
        return False

    def save_to_disk(self) -> None:
        """Save current conversation to disk."""
        save_conversation(
            self.messages,
            self.input_tokens_used,
            self.output_tokens_used
        )

    def _auto_save_if_enabled(self) -> None:
        """Auto-save if enabled."""
        if self._auto_save:
            self.save_to_disk()

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute an Anki tool and return the result."""
        try:
            if tool_name == "list_decks":
                decks = self.anki.get_decks()
                if not decks:
                    return "No decks found."
                result = "Decks:\n"
                for d in decks:
                    result += f"- {d.name} (New: {d.new_count}, Learn: {d.learn_count}, Review: {d.review_count})\n"
                return result

            elif tool_name == "list_note_types":
                types = self.anki.get_note_types()
                if not types:
                    return "No note types found."
                result = "Note types:\n"
                for t in types:
                    fields = ", ".join(t.fields) if t.fields else "unknown fields"
                    result += f"- {t.name} ({fields})\n"
                return result

            elif tool_name == "add_card":
                note_id = self.anki.add_card(
                    deck_name=tool_input["deck_name"],
                    front=tool_input["front"],
                    back=tool_input["back"],
                    tags=tool_input.get("tags"),
                    note_type=tool_input.get("note_type", "Basic"),
                )
                return f"Card added successfully (note ID: {note_id})"

            elif tool_name == "add_multiple_cards":
                cards = tool_input["cards"]
                note_ids = self.anki.add_cards(
                    deck_name=tool_input["deck_name"],
                    cards=cards,
                    note_type=tool_input.get("note_type", "Basic"),
                )
                successful = sum(1 for nid in note_ids if nid is not None)
                return f"Added {successful}/{len(cards)} cards successfully"

            elif tool_name == "search_cards":
                cards = self.anki.search_cards(
                    query=tool_input["query"],
                    limit=tool_input.get("limit", 20),
                )
                if not cards:
                    return "No cards found matching the query."
                result = f"Found {len(cards)} card(s):\n"
                for c in cards:
                    front_preview = c.front[:50] + "..." if len(c.front) > 50 else c.front
                    back_preview = c.back[:50] + "..." if len(c.back) > 50 else c.back
                    tags_str = f" [tags: {', '.join(c.tags)}]" if c.tags else ""
                    result += f"- ID: {c.id}\n  Front: {front_preview}\n  Back: {back_preview}{tags_str}\n"
                return result

            elif tool_name == "get_deck_cards":
                cards = self.anki.get_deck_cards(
                    deck_name=tool_input["deck_name"],
                    limit=tool_input.get("limit", 50),
                )
                if not cards:
                    return f"No cards found in deck '{tool_input['deck_name']}'."
                result = f"Cards in '{tool_input['deck_name']}' ({len(cards)} shown):\n"
                for c in cards[:10]:
                    front_preview = c.front[:40] + "..." if len(c.front) > 40 else c.front
                    result += f"- {front_preview}\n"
                if len(cards) > 10:
                    result += f"... and {len(cards) - 10} more"
                return result

            elif tool_name == "create_deck":
                deck_id = self.anki.create_deck(tool_input["name"])
                return f"Deck '{tool_input['name']}' created (ID: {deck_id})"

            elif tool_name == "sync_anki":
                self.anki.sync()
                return "Sync completed successfully"

            elif tool_name == "get_note":
                card = self.anki.get_note(tool_input["note_id"])
                if not card:
                    return f"Note {tool_input['note_id']} not found."
                tags_str = f"\nTags: {', '.join(card.tags)}" if card.tags else ""
                return f"Note ID: {card.id}\nFront: {card.front}\nBack: {card.back}{tags_str}"

            elif tool_name == "update_card":
                self.anki.update_note(
                    note_id=tool_input["note_id"],
                    front=tool_input.get("front"),
                    back=tool_input.get("back"),
                    tags=tool_input.get("tags"),
                )
                return f"Card {tool_input['note_id']} updated successfully"

            elif tool_name == "update_multiple_cards":
                updates = tool_input["updates"]
                results = self.anki.update_notes(updates)
                successful = sum(results)
                return f"Updated {successful}/{len(updates)} cards successfully"

            elif tool_name == "delete_cards":
                note_ids = tool_input["note_ids"]
                self.anki.delete_notes(note_ids)
                return f"Deleted {len(note_ids)} card(s)"

            elif tool_name == "add_tags_to_cards":
                note_ids = tool_input["note_ids"]
                tags = " ".join(tool_input["tags"])
                self.anki.add_tags(note_ids, tags)
                return f"Added tags to {len(note_ids)} card(s)"

            elif tool_name == "remove_tags_from_cards":
                note_ids = tool_input["note_ids"]
                tags = " ".join(tool_input["tags"])
                self.anki.remove_tags(note_ids, tags)
                return f"Removed tags from {len(note_ids)} card(s)"

            elif tool_name == "move_cards_to_deck":
                # Need to get card IDs from note IDs
                note_ids = tool_input["note_ids"]
                # For AnkiConnect, we need card IDs not note IDs for changeDeck
                # Each note can have multiple cards, so we search for them
                card_ids = []
                for nid in note_ids:
                    cards = self.anki.search_cards(f"nid:{nid}", limit=10)
                    # The card ID is typically different from note ID
                    # We'll use findCards instead
                from .client import _request
                card_ids = _request("findCards", query=f"nid:{','.join(map(str, note_ids))}")
                if card_ids:
                    self.anki.move_cards_to_deck(card_ids, tool_input["deck_name"])
                    return f"Moved {len(card_ids)} card(s) to '{tool_input['deck_name']}'"
                return "No cards found to move"

            elif tool_name == "get_deck_stats":
                stats = self.anki.get_deck_stats(tool_input["deck_name"])
                if not stats:
                    return f"Could not get stats for deck '{tool_input['deck_name']}'"
                return (
                    f"Deck: {stats.get('name', tool_input['deck_name'])}\n"
                    f"Total cards: {stats.get('total_cards', 'unknown')}\n"
                    f"New: {stats.get('new_count', 0)}\n"
                    f"Learning: {stats.get('learn_count', 0)}\n"
                    f"Review: {stats.get('review_count', 0)}"
                )

            elif tool_name == "get_deck_summary":
                summary = self.anki.get_deck_summary(
                    tool_input["deck_name"],
                    limit=tool_input.get("limit", 100)
                )
                result = (
                    f"Deck: {summary.get('name', tool_input['deck_name'])}\n"
                    f"Total cards: {summary.get('total_cards', 'unknown')}\n"
                    f"New: {summary.get('new_count', 0)} | "
                    f"Learning: {summary.get('learn_count', 0)} | "
                    f"Review: {summary.get('review_count', 0)}\n"
                )
                if summary.get("all_tags"):
                    result += f"Tags used: {', '.join(summary['all_tags'])}\n"
                if summary.get("sample_cards"):
                    result += f"\nSample cards ({len(summary['sample_cards'])} shown):\n"
                    for card in summary["sample_cards"][:15]:
                        front_preview = card.front[:60] + "..." if len(card.front) > 60 else card.front
                        result += f"- {front_preview}\n"
                    if len(summary["sample_cards"]) > 15:
                        result += f"... and {len(summary['sample_cards']) - 15} more"
                return result

            elif tool_name == "list_deck_fronts":
                fronts = self.anki.get_all_fronts(
                    tool_input["deck_name"],
                    limit=tool_input.get("limit", 200)
                )
                if not fronts:
                    return f"No cards found in deck '{tool_input['deck_name']}'"
                result = f"Front sides of cards in '{tool_input['deck_name']}' ({len(fronts)} cards):\n\n"
                for i, front in enumerate(fronts, 1):
                    front_clean = front.replace('\n', ' ').strip()
                    front_preview = front_clean[:80] + "..." if len(front_clean) > 80 else front_clean
                    result += f"{i}. {front_preview}\n"
                return result

            elif tool_name == "get_collection_stats":
                stats = self.anki.get_collection_stats()
                result = (
                    f"Collection Overview:\n"
                    f"Total decks: {stats.get('total_decks', 0)}\n"
                    f"Total notes: {stats.get('total_notes', 0)}\n"
                    f"Cards due today: {stats.get('total_due', 0)} "
                    f"(New: {stats.get('total_new', 0)}, "
                    f"Learning: {stats.get('total_learning', 0)}, "
                    f"Review: {stats.get('total_review', 0)})\n"
                )
                if stats.get("decks"):
                    result += "\nDecks with cards due:\n"
                    for deck in stats["decks"]:
                        if deck["due"] > 0:
                            result += f"- {deck['name']}: {deck['due']} due\n"
                return result

            elif tool_name == "check_word_exists":
                word = tool_input["word"]
                deck_name = tool_input.get("deck_name")

                # Build search query
                query = f"*{word}*"
                if deck_name:
                    query = f'deck:"{deck_name}" {query}'

                cards = self.anki.search_cards(query, limit=10)

                if not cards:
                    return f"NOT FOUND: '{word}' does not exist in {'deck ' + deck_name if deck_name else 'any deck'}. Safe to add."

                result = f"FOUND: '{word}' already exists ({len(cards)} match(es)):\n"
                for c in cards[:5]:
                    front_preview = c.front[:50] + "..." if len(c.front) > 50 else c.front
                    back_preview = c.back[:50] + "..." if len(c.back) > 50 else c.back
                    result += f"- Front: {front_preview}\n  Back: {back_preview}\n"
                if len(cards) > 5:
                    result += f"... and {len(cards) - 5} more matches"
                return result

            elif tool_name == "check_words_exist":
                words = tool_input["words"]
                deck_name = tool_input.get("deck_name")

                found_words = []
                not_found_words = []

                for word in words:
                    query = f"*{word}*"
                    if deck_name:
                        query = f'deck:"{deck_name}" {query}'

                    cards = self.anki.search_cards(query, limit=1)
                    if cards:
                        found_words.append(word)
                    else:
                        not_found_words.append(word)

                result = f"Checked {len(words)} words:\n\n"
                if found_words:
                    result += f"ALREADY EXIST ({len(found_words)}): {', '.join(found_words)}\n\n"
                if not_found_words:
                    result += f"NOT FOUND - safe to add ({len(not_found_words)}): {', '.join(not_found_words)}"

                return result

            elif tool_name == "find_card_by_word":
                word = tool_input["word"].lower().strip()
                deck_name = tool_input.get("deck_name")

                # Search by word tag
                tag = f"word::{word}"
                query = f'tag:"{tag}"'
                if deck_name:
                    query = f'deck:"{deck_name}" {query}'

                cards = self.anki.search_cards(query, limit=5)

                if not cards:
                    return f"NOT FOUND: No card with tag 'word::{word}'. Safe to add."

                result = f"FOUND: Card exists with tag 'word::{word}':\n"
                for c in cards[:3]:
                    front_preview = c.front[:50] + "..." if len(c.front) > 50 else c.front
                    tags_str = ", ".join(c.tags[:5]) if c.tags else "none"
                    result += f"- ID: {c.id}\n  Front: {front_preview}\n  Tags: {tags_str}\n"
                return result

            elif tool_name == "find_cards_by_words":
                words = [w.lower().strip() for w in tool_input["words"]]
                deck_name = tool_input.get("deck_name")

                found_words = []
                not_found_words = []

                for word in words:
                    tag = f"word::{word}"
                    query = f'tag:"{tag}"'
                    if deck_name:
                        query = f'deck:"{deck_name}" {query}'

                    cards = self.anki.search_cards(query, limit=1)
                    if cards:
                        found_words.append(word)
                    else:
                        not_found_words.append(word)

                result = f"Checked {len(words)} word tags:\n\n"
                if found_words:
                    result += f"ALREADY EXIST ({len(found_words)}): {', '.join(found_words)}\n\n"
                if not_found_words:
                    result += f"NOT FOUND - safe to add ({len(not_found_words)}): {', '.join(not_found_words)}"

                return result

            elif tool_name == "compact_conversation":
                reason = tool_input.get("reason", "manual request")
                result = self.compact_history()
                status = self.get_context_status()
                return f"{result}\nContext now at {status['percent_used']:.1f}% ({status['input_tokens']:,} tokens)"

            elif tool_name == "get_learning_summary":
                summary = load_summary()
                return format_summary_for_display(summary)

            elif tool_name == "update_learning_summary":
                summary = load_summary()

                # Update total cards
                words_added = tool_input.get("words_added", [])
                summary["total_cards_added"] = summary.get("total_cards_added", 0) + len(words_added)

                # Update level info
                level = tool_input.get("level", "A1")
                if level in summary["levels"]:
                    level_data = summary["levels"][level]

                    # Update what_i_know
                    what_i_know = level_data.get("what_i_know", {})
                    if tool_input.get("what_i_know_summary"):
                        what_i_know["summary"] = tool_input["what_i_know_summary"]

                    # Add words to vocabulary (avoid duplicates)
                    vocab = what_i_know.get("vocabulary", [])
                    for word in words_added:
                        if word not in vocab:
                            vocab.append(word)
                    what_i_know["vocabulary"] = vocab

                    # Update grammar concepts
                    if tool_input.get("grammar_concepts_learned"):
                        existing = set(what_i_know.get("grammar_concepts", []))
                        existing.update(tool_input["grammar_concepts_learned"])
                        what_i_know["grammar_concepts"] = list(existing)

                    # Update topics covered
                    if tool_input.get("topics_covered"):
                        existing = set(what_i_know.get("topics_covered", []))
                        existing.update(tool_input["topics_covered"])
                        what_i_know["topics_covered"] = list(existing)

                    level_data["what_i_know"] = what_i_know

                    # Update what_to_learn
                    what_to_learn = level_data.get("what_to_learn", {})
                    if tool_input.get("what_to_learn_summary"):
                        what_to_learn["summary"] = tool_input["what_to_learn_summary"]
                    if tool_input.get("vocabulary_gaps"):
                        what_to_learn["vocabulary_gaps"] = tool_input["vocabulary_gaps"]
                    if tool_input.get("grammar_gaps"):
                        what_to_learn["grammar_gaps"] = tool_input["grammar_gaps"]
                    if tool_input.get("priority_topics"):
                        what_to_learn["priority_topics"] = tool_input["priority_topics"]
                    level_data["what_to_learn"] = what_to_learn

                    # Update coverage estimate
                    if tool_input.get("estimated_coverage") is not None:
                        level_data["estimated_coverage"] = tool_input["estimated_coverage"]

                # Update recent additions (keep last 50)
                for word in words_added:
                    if word not in summary["recent_additions"]:
                        summary["recent_additions"].append(word)
                summary["recent_additions"] = summary["recent_additions"][-50:]

                # Update notes
                if tool_input.get("notes"):
                    summary["notes"] = tool_input["notes"]

                save_summary(summary)

                topics = tool_input.get("topics_covered", [])
                return f"Learning summary updated: +{len(words_added)} words at {level} level ({level_data.get('estimated_coverage', 0)}% coverage). Topics: {', '.join(topics) if topics else 'general'}"

            elif tool_name == "all_cards_delegate":
                return self._handle_all_cards_delegate(tool_input)

            elif tool_name == "card_subset_delegate":
                return self._handle_card_subset_delegate(tool_input)

            else:
                return f"Unknown tool: {tool_name}"

        except AnkiConnectError as e:
            return f"Anki error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def _handle_all_cards_delegate(self, tool_input: dict) -> str:
        """Handle the all_cards_delegate tool."""
        deck_name = tool_input["deck_name"]
        prompt = tool_input["prompt"]
        workers = min(tool_input.get("workers", self.config.delegate_max_workers), 10)
        dry_run = tool_input.get("dry_run", False)
        limit = tool_input.get("limit")

        # Fetch cards from deck
        cards = self.anki.get_deck_cards(deck_name, limit=limit or 1000)
        if not cards:
            return f"No cards found in deck '{deck_name}'"

        if limit:
            cards = cards[:limit]

        # Create processor
        processor = CardDelegateProcessor(
            client=self.client,
            model=self.config.subagent_model,
            max_workers=workers,
            rate_limit_delay=self.config.delegate_rate_limit_delay,
        )

        # Progress callback that pushes to queue
        def progress_callback(event: ProgressEvent) -> None:
            self._progress_queue.put({
                "type": "delegate_progress",
                "completed": event.completed,
                "total": event.total,
                "current_card": event.current_card,
                "success": event.success,
                "error": event.error,
            })

        # Process cards
        results = processor.process_cards(cards, prompt, progress_callback)

        # Build summary
        changed = [r for r in results if r.changed]
        errors = [r for r in results if r.error]

        summary_parts = [
            f"Processed {len(results)} cards from '{deck_name}'",
            f"Changed: {len(changed)}, Errors: {len(errors)}",
        ]

        if dry_run:
            summary_parts.insert(0, "[DRY RUN - No changes applied]")
            if changed:
                summary_parts.append("\nPreview of changes:")
                for r in changed[:5]:
                    summary_parts.append(f"\n- Card {r.note_id}:")
                    if r.transformed_front:
                        summary_parts.append(f"  Front: {r.transformed_front[:50]}...")
                    if r.transformed_back:
                        summary_parts.append(f"  Back: {r.transformed_back[:50]}...")
                    if r.reasoning:
                        summary_parts.append(f"  Reason: {r.reasoning}")
                if len(changed) > 5:
                    summary_parts.append(f"\n... and {len(changed) - 5} more changes")
        else:
            # Apply changes
            applied = 0
            for r in changed:
                try:
                    self.anki.update_note(
                        note_id=int(r.note_id),
                        front=r.transformed_front,
                        back=r.transformed_back,
                        tags=r.transformed_tags,
                    )
                    applied += 1
                except Exception as e:
                    errors.append(r)

            summary_parts.append(f"Applied: {applied}")

        if errors:
            summary_parts.append(f"\nErrors:")
            for r in errors[:3]:
                summary_parts.append(f"- Card {r.note_id}: {r.error}")
            if len(errors) > 3:
                summary_parts.append(f"... and {len(errors) - 3} more errors")

        return "\n".join(summary_parts)

    def _handle_card_subset_delegate(self, tool_input: dict) -> str:
        """Handle the card_subset_delegate tool."""
        note_ids = tool_input["note_ids"]
        prompt = tool_input["prompt"]
        workers = min(tool_input.get("workers", self.config.delegate_max_workers), 10)
        dry_run = tool_input.get("dry_run", False)

        # Fetch cards by note IDs
        cards = []
        for note_id in note_ids:
            card = self.anki.get_note(note_id)
            if card:
                cards.append(card)

        if not cards:
            return f"No cards found for the given note IDs"

        # Create processor
        processor = CardDelegateProcessor(
            client=self.client,
            model=self.config.subagent_model,
            max_workers=workers,
            rate_limit_delay=self.config.delegate_rate_limit_delay,
        )

        # Progress callback that pushes to queue
        def progress_callback(event: ProgressEvent) -> None:
            self._progress_queue.put({
                "type": "delegate_progress",
                "completed": event.completed,
                "total": event.total,
                "current_card": event.current_card,
                "success": event.success,
                "error": event.error,
            })

        # Process cards
        results = processor.process_cards(cards, prompt, progress_callback)

        # Build summary
        changed = [r for r in results if r.changed]
        errors = [r for r in results if r.error]

        summary_parts = [
            f"Processed {len(results)} cards",
            f"Changed: {len(changed)}, Errors: {len(errors)}",
        ]

        if dry_run:
            summary_parts.insert(0, "[DRY RUN - No changes applied]")
            if changed:
                summary_parts.append("\nPreview of changes:")
                for r in changed[:5]:
                    summary_parts.append(f"\n- Card {r.note_id}:")
                    if r.transformed_front:
                        summary_parts.append(f"  Front: {r.transformed_front[:50]}...")
                    if r.transformed_back:
                        summary_parts.append(f"  Back: {r.transformed_back[:50]}...")
                    if r.reasoning:
                        summary_parts.append(f"  Reason: {r.reasoning}")
                if len(changed) > 5:
                    summary_parts.append(f"\n... and {len(changed) - 5} more changes")
        else:
            # Apply changes
            applied = 0
            for r in changed:
                try:
                    self.anki.update_note(
                        note_id=int(r.note_id),
                        front=r.transformed_front,
                        back=r.transformed_back,
                        tags=r.transformed_tags,
                    )
                    applied += 1
                except Exception as e:
                    errors.append(r)

            summary_parts.append(f"Applied: {applied}")

        if errors:
            summary_parts.append(f"\nErrors:")
            for r in errors[:3]:
                summary_parts.append(f"- Card {r.note_id}: {r.error}")
            if len(errors) > 3:
                summary_parts.append(f"... and {len(errors) - 3} more errors")

        return "\n".join(summary_parts)

    def _fix_conversation_state(self) -> None:
        """Fix conversation state if there are orphaned tool_use or tool_result blocks."""
        if not self.messages:
            return

        # Helper to get tool_use IDs from a message
        def get_tool_use_ids(content) -> set:
            ids = set()
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        ids.add(block.id)
                    elif isinstance(block, dict) and block.get("type") == "tool_use":
                        ids.add(block.get("id"))
            return ids

        # Helper to get tool_result IDs from a message
        def get_tool_result_ids(content) -> set:
            ids = set()
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        ids.add(block.get("tool_use_id"))
            return ids

        # Scan through messages and validate tool_use/tool_result pairs
        i = 0
        while i < len(self.messages):
            msg = self.messages[i]

            # Check for assistant messages with tool_use
            if msg["role"] == "assistant":
                tool_use_ids = get_tool_use_ids(msg.get("content", []))

                if tool_use_ids:
                    # Must have a following user message with matching tool_results
                    if i + 1 >= len(self.messages):
                        # No following message, truncate here
                        self.messages = self.messages[:i]
                        return

                    next_msg = self.messages[i + 1]
                    if next_msg["role"] != "user":
                        # Next message isn't user, truncate
                        self.messages = self.messages[:i]
                        return

                    tool_result_ids = get_tool_result_ids(next_msg.get("content", []))

                    # Check if IDs match
                    if tool_use_ids != tool_result_ids:
                        # Mismatch - truncate conversation at this point
                        self.messages = self.messages[:i]
                        return

            # Check for user messages with tool_result (must follow assistant with tool_use)
            elif msg["role"] == "user":
                tool_result_ids = get_tool_result_ids(msg.get("content", []))

                if tool_result_ids:
                    # Must have a preceding assistant message with matching tool_use
                    if i == 0:
                        # No preceding message, remove this message
                        self.messages = self.messages[1:]
                        continue

                    prev_msg = self.messages[i - 1]
                    if prev_msg["role"] != "assistant":
                        # Previous isn't assistant, truncate before this
                        self.messages = self.messages[:i]
                        return

                    tool_use_ids = get_tool_use_ids(prev_msg.get("content", []))

                    if tool_use_ids != tool_result_ids:
                        # Mismatch - truncate before this tool_result message
                        self.messages = self.messages[:i]
                        return

            i += 1

    def chat(self, user_message: str) -> Generator[dict, None, None]:
        """
        Send a message and yield response events.

        Yields dicts with 'type' and 'content':
        - {"type": "text", "content": "..."}
        - {"type": "tool_use", "name": "...", "input": {...}}
        - {"type": "tool_result", "name": "...", "result": "..."}
        """
        # Fix any corrupted conversation state before adding new message
        self._fix_conversation_state()
        self.messages.append({"role": "user", "content": user_message})

        while True:
            # Stream the response
            collected_text = ""
            tool_uses = []

            try:
                stream_ctx = self.client.messages.stream(
                    model=self.model,
                    max_tokens=self.max_output_tokens,
                    system=SYSTEM_PROMPT,
                    tools=ANKI_TOOLS,
                    messages=self.messages,
                )
            except Exception as e:
                error_str = str(e)
                if "tool_use" in error_str and "tool_result" in error_str:
                    # Conversation state is corrupted, try to fix it
                    yield {"type": "error", "content": "Recovering from corrupted conversation state..."}

                    # Remove the user message we just added
                    if self.messages and self.messages[-1]["role"] == "user":
                        self.messages.pop()

                    # Aggressively fix the conversation
                    self._fix_conversation_state()

                    # If still having issues, try removing more messages
                    if len(self.messages) > 2:
                        # Keep removing last message pair until we have a clean state
                        while len(self.messages) > 0:
                            try:
                                # Test if state is valid by trying a minimal API call
                                test_messages = self.messages + [{"role": "user", "content": "test"}]
                                # Just validate, don't actually call
                                break
                            except Exception:
                                # Remove last message and try again
                                self.messages.pop()

                    # Re-add user message and retry
                    self.messages.append({"role": "user", "content": user_message})
                    self._auto_save_if_enabled()
                    continue
                raise

            with stream_ctx as stream:
                for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_start":
                            if hasattr(event, "content_block"):
                                if event.content_block.type == "tool_use":
                                    tool_uses.append({
                                        "id": event.content_block.id,
                                        "name": event.content_block.name,
                                        "input": ""
                                    })
                        elif event.type == "content_block_delta":
                            if hasattr(event, "delta"):
                                if hasattr(event.delta, "text"):
                                    collected_text += event.delta.text
                                    yield {"type": "text_delta", "content": event.delta.text}
                                elif hasattr(event.delta, "partial_json"):
                                    if tool_uses:
                                        tool_uses[-1]["input"] += event.delta.partial_json

            # Get the final message
            response = stream.get_final_message()

            # Track token usage
            if hasattr(response, "usage"):
                self.input_tokens_used = response.usage.input_tokens
                self.output_tokens_used += response.usage.output_tokens

            # Yield context status update
            yield {"type": "context_status", "status": self.get_context_status()}

            # Add assistant response to messages
            self.messages.append({"role": "assistant", "content": response.content})

            # Check if we need to execute tools
            if response.stop_reason == "tool_use":
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        yield {
                            "type": "tool_use",
                            "name": block.name,
                            "input": block.input
                        }

                        # For delegate tools, yield progress events during execution
                        is_delegate_tool = block.name in (
                            "all_cards_delegate",
                            "card_subset_delegate",
                        )

                        if is_delegate_tool:
                            # Clear the queue before starting
                            while not self._progress_queue.empty():
                                try:
                                    self._progress_queue.get_nowait()
                                except queue.Empty:
                                    break

                            # Execute in a way that allows yielding progress
                            import threading

                            result_holder: list[str] = []

                            def run_tool():
                                result_holder.append(
                                    self._execute_tool(block.name, block.input)
                                )

                            thread = threading.Thread(target=run_tool)
                            thread.start()

                            # Poll for progress events while tool runs
                            while thread.is_alive():
                                try:
                                    progress_event = self._progress_queue.get(timeout=0.1)
                                    yield progress_event
                                except queue.Empty:
                                    continue

                            thread.join()

                            # Drain remaining progress events
                            while not self._progress_queue.empty():
                                try:
                                    yield self._progress_queue.get_nowait()
                                except queue.Empty:
                                    break

                            result = result_holder[0] if result_holder else "Error: Tool execution failed"
                        else:
                            # Execute the tool normally
                            result = self._execute_tool(block.name, block.input)

                        yield {
                            "type": "tool_result",
                            "name": block.name,
                            "result": result
                        }

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })

                # Add tool results to messages and continue
                self.messages.append({"role": "user", "content": tool_results})
            else:
                # No more tool calls, we're done
                # Auto-save conversation
                self._auto_save_if_enabled()
                break

    def reset(self) -> None:
        """Clear conversation history and saved state."""
        self.messages = []
        self.input_tokens_used = 0
        self.output_tokens_used = 0
        # Clear saved conversation
        from .conversation_store import clear_conversation
        clear_conversation()

    def compact_history(self, keep_recent: int = 4) -> str:
        """
        Compact conversation history by summarizing older messages.

        Args:
            keep_recent: Number of recent message pairs to keep intact

        Returns:
            Summary of what was compacted
        """
        if len(self.messages) <= keep_recent * 2:
            return "Conversation too short to compact."

        # Split messages into old (to summarize) and recent (to keep)
        split_point = len(self.messages) - (keep_recent * 2)
        old_messages = self.messages[:split_point]
        recent_messages = self.messages[split_point:]

        # Strip orphaned tool_result blocks from the first recent message
        # These would have no matching tool_use after compacting
        if recent_messages and recent_messages[0]["role"] == "user":
            content = recent_messages[0].get("content", [])
            if isinstance(content, list):
                # Filter out tool_result blocks
                filtered_content = [
                    block for block in content
                    if not (isinstance(block, dict) and block.get("type") == "tool_result")
                ]
                if filtered_content:
                    recent_messages[0] = {**recent_messages[0], "content": filtered_content}
                else:
                    # If the message only had tool_results, remove it entirely
                    recent_messages = recent_messages[1:]

        # Build a text representation of old messages for summarization
        conversation_text = ""
        for msg in old_messages:
            role = msg["role"]
            content = msg.get("content", "")

            if isinstance(content, str):
                conversation_text += f"{role.upper()}: {content}\n\n"
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_result":
                            conversation_text += f"TOOL RESULT: {block.get('content', '')[:200]}...\n\n"
                        elif block.get("type") == "text":
                            conversation_text += f"{role.upper()}: {block.get('text', '')}\n\n"
                    elif hasattr(block, "type"):
                        if block.type == "text":
                            conversation_text += f"{role.upper()}: {block.text}\n\n"
                        elif block.type == "tool_use":
                            conversation_text += f"TOOL CALL: {block.name}({block.input})\n\n"

        # Use Claude to summarize
        summary_response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""Summarize this conversation history concisely, preserving key information:
- What decks/cards were discussed
- What cards were added (include the words/terms)
- Any user preferences mentioned
- Current task context

Conversation:
{conversation_text[:15000]}

Provide a brief summary (2-4 paragraphs max):"""
            }]
        )

        summary = summary_response.content[0].text

        # Create new message history with summary + recent messages
        self.messages = [
            {
                "role": "user",
                "content": f"[CONVERSATION SUMMARY]\n{summary}\n[END SUMMARY]\n\nContinuing our conversation..."
            },
            {
                "role": "assistant",
                "content": "I understand. I've noted the context from our previous conversation. How can I help you continue?"
            }
        ] + recent_messages

        # Update token tracking (estimate reduction)
        old_tokens = self.input_tokens_used
        self.input_tokens_used = int(self.input_tokens_used * 0.3)  # Rough estimate
        tokens_saved = old_tokens - self.input_tokens_used

        # Save compacted conversation to disk
        self._auto_save_if_enabled()

        return f"Compacted {len(old_messages)} messages into summary. Estimated tokens saved: ~{tokens_saved:,}"
