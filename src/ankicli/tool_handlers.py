"""Tool handler registry for Anki assistant.

Each handler is registered with @handler("tool_name") and receives:
    anki: AnkiClient instance
    tool_input: dict of tool parameters
    **ctx: Additional context (config, assistant, etc.)
"""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import AnkiClient
    from .config import Config

HANDLERS: dict[str, Callable] = {}


def handler(name: str):
    """Decorator to register a tool handler."""
    def decorator(fn: Callable) -> Callable:
        HANDLERS[name] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Deck operations
# ---------------------------------------------------------------------------

@handler("list_decks")
def handle_list_decks(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    decks = anki.get_decks()
    if not decks:
        return "No decks found."
    result = "Decks:\n"
    for d in decks:
        result += f"- {d.name} (New: {d.new_count}, Learn: {d.learn_count}, Review: {d.review_count})\n"
    return result


@handler("create_deck")
def handle_create_deck(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    deck_id = anki.create_deck(tool_input["name"])
    return f"Deck '{tool_input['name']}' created (ID: {deck_id})"


@handler("get_deck_stats")
def handle_get_deck_stats(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    stats = anki.get_deck_stats(tool_input["deck_name"])
    if not stats:
        return f"Could not get stats for deck '{tool_input['deck_name']}'"
    return (
        f"Deck: {stats.get('name', tool_input['deck_name'])}\n"
        f"Total cards: {stats.get('total_cards', 'unknown')}\n"
        f"New: {stats.get('new_count', 0)}\n"
        f"Learning: {stats.get('learn_count', 0)}\n"
        f"Review: {stats.get('review_count', 0)}"
    )


@handler("get_deck_summary")
def handle_get_deck_summary(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    summary = anki.get_deck_summary(
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


@handler("get_deck_cards")
def handle_get_deck_cards(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    cards = anki.get_deck_cards(
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


@handler("list_deck_fronts")
def handle_list_deck_fronts(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    fronts = anki.get_all_fronts(
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


@handler("get_collection_stats")
def handle_get_collection_stats(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    stats = anki.get_collection_stats()
    result = (
        f"Collection Overview:\n"
        f"Total decks: {stats.get('total_decks', 0)}\n"
        f"Total notes: {stats.get('total_notes', 0)}\n"
        f"Total cards: {stats.get('total_cards', 0)}\n"
        f"Cards due today: {stats.get('total_due', 0)} "
        f"(New: {stats.get('total_new', 0)}, "
        f"Learning: {stats.get('total_learning', 0)}, "
        f"Review: {stats.get('total_review', 0)})\n"
        f"\nCard breakdown:\n"
        f"  Mature (interval >= 21 days): {stats.get('mature_count', 0)}\n"
        f"  Learning: {stats.get('learning_count', 0)}\n"
        f"  New/unseen: {stats.get('new_count', 0)}\n"
        f"\nRetention rate: {stats.get('retention_rate', 0):.1f}%\n"
        f"  Total reviews: {stats.get('total_reps', 0)}\n"
        f"  Total lapses: {stats.get('total_lapses', 0)}\n"
    )
    if stats.get("decks"):
        result += "\nDecks with cards due:\n"
        for deck in stats["decks"]:
            if deck["due"] > 0:
                result += f"- {deck['name']}: {deck['due']} due\n"

    # Record progress snapshot and study activity
    try:
        from .progress_tracking import record_progress_snapshot, record_activity
        cefr_levels = {}
        try:
            from .cefr import load_progress_cache
            progress = load_progress_cache()
            if progress:
                for level_key in ("A1", "A2", "B1", "B2", "C1", "C2"):
                    level_data = progress.get(level_key)
                    cefr_levels[level_key] = level_data.percent if level_data else 0
        except Exception:
            pass
        record_progress_snapshot(
            total_cards=stats.get("total_cards", 0),
            cefr_levels=cefr_levels,
            retention_rate=stats.get("retention_rate", 0),
        )
        record_activity()
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Note type operations
# ---------------------------------------------------------------------------

@handler("list_note_types")
def handle_list_note_types(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    types = anki.get_note_types()
    if not types:
        return "No note types found."
    result = "Note types:\n"
    for t in types:
        fields = ", ".join(t.fields) if t.fields else "unknown fields"
        result += f"- {t.name} ({fields})\n"
    return result


# ---------------------------------------------------------------------------
# Card CRUD operations
# ---------------------------------------------------------------------------

def _enrich_tags_with_cefr(tags: list[str] | None) -> list[str]:
    """Add cefr:: and theme:: tags based on the word:: tag if present."""
    if not tags:
        return tags or []
    # Find word:: tag
    word = None
    for t in tags:
        if t.startswith("word::"):
            word = t[6:].strip()
            break
    if not word:
        return tags

    # Check if CEFR tags already present
    if any(t.startswith("cefr::") for t in tags):
        return tags

    try:
        from .cefr import CEFRData, get_cefr_tags_for_word
        cefr_data = CEFRData()
        cefr_data.load()
        extra = get_cefr_tags_for_word(cefr_data, word)
        if extra:
            return list(tags) + extra
    except Exception:
        pass
    return tags


@handler("add_card")
def handle_add_card(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    tags = _enrich_tags_with_cefr(tool_input.get("tags"))
    note_id = anki.add_card(
        deck_name=tool_input["deck_name"],
        front=tool_input["front"],
        back=tool_input["back"],
        tags=tags or None,
        note_type=tool_input.get("note_type", "Basic"),
    )
    assistant = ctx.get("assistant")
    if assistant:
        assistant.session_cards_added += 1
    # Invalidate CEFR cache so next progress check is fresh
    try:
        from .cefr import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
    cefr_info = ""
    if tags:
        cefr_tags = [t for t in tags if t.startswith("cefr::") or t.startswith("theme::")]
        if cefr_tags:
            cefr_info = f" [auto-tagged: {', '.join(cefr_tags)}]"
    return f"Card added successfully (note ID: {note_id}){cefr_info}"


@handler("add_multiple_cards")
def handle_add_multiple_cards(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    cards = tool_input["cards"]
    # Enrich tags for each card
    for card in cards:
        card["tags"] = _enrich_tags_with_cefr(card.get("tags"))
    note_ids = anki.add_cards(
        deck_name=tool_input["deck_name"],
        cards=cards,
        note_type=tool_input.get("note_type", "Basic"),
    )
    successful = sum(1 for nid in note_ids if nid is not None)
    duplicates = [
        cards[i]["front"][:40] for i, nid in enumerate(note_ids)
        if nid is None
    ]
    assistant = ctx.get("assistant")
    if assistant:
        assistant.session_cards_added += successful
    # Invalidate CEFR cache
    try:
        from .cefr import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
    # Count auto-tagged cards
    tagged_count = sum(
        1 for c in cards
        if any(t.startswith("cefr::") for t in (c.get("tags") or []))
    )
    cefr_info = f" ({tagged_count} CEFR-tagged)" if tagged_count else ""
    result = f"Added {successful}/{len(cards)} cards successfully{cefr_info}"
    if duplicates:
        dup_list = ", ".join(f'"{d}"' for d in duplicates[:5])
        extra = f" and {len(duplicates) - 5} more" if len(duplicates) > 5 else ""
        result += f"\nSkipped duplicates: {dup_list}{extra}"
    return result


@handler("get_note")
def handle_get_note(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    card = anki.get_note(tool_input["note_id"])
    if not card:
        return f"Note {tool_input['note_id']} not found."
    tags_str = f"\nTags: {', '.join(card.tags)}" if card.tags else ""
    return f"Note ID: {card.id}\nFront: {card.front}\nBack: {card.back}{tags_str}"


@handler("update_card")
def handle_update_card(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    anki.update_note(
        note_id=tool_input["note_id"],
        front=tool_input.get("front"),
        back=tool_input.get("back"),
        tags=tool_input.get("tags"),
    )
    return f"Card {tool_input['note_id']} updated successfully"


@handler("update_multiple_cards")
def handle_update_multiple_cards(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    updates = tool_input["updates"]
    results = anki.update_notes(updates)
    successful = sum(results)
    return f"Updated {successful}/{len(updates)} cards successfully"


@handler("delete_cards")
def handle_delete_cards(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    note_ids = tool_input["note_ids"]
    anki.delete_notes(note_ids)
    return f"Deleted {len(note_ids)} card(s)"


# ---------------------------------------------------------------------------
# Search operations
# ---------------------------------------------------------------------------

@handler("search_cards")
def handle_search_cards(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    cards = anki.search_cards(
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


@handler("check_word_exists")
def handle_check_word_exists(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    word = tool_input["word"].lower().strip()
    deck_name = tool_input.get("deck_name")

    # Try exact tag, then underscore/space variants for multi-word phrases
    candidates = [f"word::{word}"]
    if " " in word:
        candidates.append(f"word::{word.replace(' ', '_')}")
    if "_" in word:
        candidates.append(f"word::{word.replace('_', ' ')}")

    cards = []
    for tag in candidates:
        query = f'tag:"{tag}"'
        if deck_name:
            query = f'deck:"{deck_name}" {query}'
        cards = anki.search_cards(query, limit=10)
        if cards:
            break

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


@handler("check_words_exist")
def handle_check_words_exist(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    words = tool_input["words"]
    deck_name = tool_input.get("deck_name")

    found_words = []
    not_found_words = []

    for word in words:
        w = word.lower().strip()
        # Try exact tag, then underscore/space variants
        candidates = [f"word::{w}"]
        if " " in w:
            candidates.append(f"word::{w.replace(' ', '_')}")
        if "_" in w:
            candidates.append(f"word::{w.replace('_', ' ')}")

        found = False
        for tag in candidates:
            query = f'tag:"{tag}"'
            if deck_name:
                query = f'deck:"{deck_name}" {query}'
            cards = anki.search_cards(query, limit=1)
            if cards:
                found = True
                break

        if found:
            found_words.append(word)
        else:
            not_found_words.append(word)

    result = f"Checked {len(words)} words:\n\n"
    if found_words:
        result += f"ALREADY EXIST ({len(found_words)}): {', '.join(found_words)}\n\n"
    if not_found_words:
        result += f"NOT FOUND - safe to add ({len(not_found_words)}): {', '.join(not_found_words)}"

    return result


@handler("find_card_by_word")
def handle_find_card_by_word(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    word = tool_input["word"].lower().strip()
    deck_name = tool_input.get("deck_name")

    # Try exact tag, then underscore variant for multi-word phrases
    candidates = [f"word::{word}"]
    if " " in word:
        candidates.append(f"word::{word.replace(' ', '_')}")
    if "_" in word:
        candidates.append(f"word::{word.replace('_', ' ')}")

    cards = []
    for tag in candidates:
        query = f'tag:"{tag}"'
        if deck_name:
            query = f'deck:"{deck_name}" {query}'
        cards = anki.search_cards(query, limit=5)
        if cards:
            break

    if not cards:
        return f"NOT FOUND: No card with tag 'word::{word}'. Safe to add."

    result = f"FOUND: Card exists with tag 'word::{word}':\n"
    for c in cards[:3]:
        front_preview = c.front[:50] + "..." if len(c.front) > 50 else c.front
        tags_str = ", ".join(c.tags[:5]) if c.tags else "none"
        result += f"- ID: {c.id}\n  Front: {front_preview}\n  Tags: {tags_str}\n"
    return result


@handler("find_cards_by_words")
def handle_find_cards_by_words(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    words = [w.lower().strip() for w in tool_input["words"]]
    deck_name = tool_input.get("deck_name")

    found_words = []
    not_found_words = []

    for word in words:
        candidates = [f"word::{word}"]
        if " " in word:
            candidates.append(f"word::{word.replace(' ', '_')}")
        if "_" in word:
            candidates.append(f"word::{word.replace('_', ' ')}")

        found = False
        for tag in candidates:
            query = f'tag:"{tag}"'
            if deck_name:
                query = f'deck:"{deck_name}" {query}'
            cards = anki.search_cards(query, limit=1)
            if cards:
                found = True
                break

        if found:
            found_words.append(word)
        else:
            not_found_words.append(word)

    result = f"Checked {len(words)} word tags:\n\n"
    if found_words:
        result += f"ALREADY EXIST ({len(found_words)}): {', '.join(found_words)}\n\n"
    if not_found_words:
        result += f"NOT FOUND - safe to add ({len(not_found_words)}): {', '.join(not_found_words)}"

    return result


# ---------------------------------------------------------------------------
# Tag operations
# ---------------------------------------------------------------------------

@handler("add_tags_to_cards")
def handle_add_tags_to_cards(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    note_ids = tool_input["note_ids"]
    tags = " ".join(tool_input["tags"])
    anki.add_tags(note_ids, tags)
    return f"Added tags to {len(note_ids)} card(s)"


@handler("remove_tags_from_cards")
def handle_remove_tags_from_cards(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    note_ids = tool_input["note_ids"]
    tags = " ".join(tool_input["tags"])
    anki.remove_tags(note_ids, tags)
    return f"Removed tags from {len(note_ids)} card(s)"


# ---------------------------------------------------------------------------
# Card movement
# ---------------------------------------------------------------------------

@handler("move_cards_to_deck")
def handle_move_cards_to_deck(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    note_ids = tool_input["note_ids"]
    from .client import _request
    card_ids = _request("findCards", query=f"nid:{','.join(map(str, note_ids))}")
    if card_ids:
        anki.move_cards_to_deck(card_ids, tool_input["deck_name"])
        return f"Moved {len(card_ids)} card(s) to '{tool_input['deck_name']}'"
    return "No cards found to move"


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

@handler("sync_anki")
def handle_sync_anki(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    anki.sync()
    return "Sync completed successfully"


# ---------------------------------------------------------------------------
# Learning summary
# ---------------------------------------------------------------------------

@handler("get_learning_summary")
def handle_get_learning_summary(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .learning_summary import load_summary, format_summary_as_text
    summary = load_summary()
    return format_summary_as_text(summary)


@handler("update_learning_summary")
def handle_update_learning_summary(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .learning_summary import load_summary, save_summary

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
    level_data = summary["levels"].get(level, {})
    return f"Learning summary updated: +{len(words_added)} words at {level} level ({level_data.get('estimated_coverage', 0)}% coverage). Topics: {', '.join(topics) if topics else 'general'}"


# ---------------------------------------------------------------------------
# Tool notes / preferences
# ---------------------------------------------------------------------------

@handler("set_tool_note")
def handle_set_tool_note(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .config import save_config
    config: Config = ctx["config"]
    tool_target = tool_input["tool_name"]
    note = tool_input["note"]
    config.tool_notes[tool_target] = note
    save_config(config)
    return f"Preference saved for '{tool_target}': {note}"


@handler("get_tool_notes")
def handle_get_tool_notes(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .config import format_tool_notes_display
    config: Config = ctx["config"]
    return format_tool_notes_display(config)


@handler("remove_tool_note")
def handle_remove_tool_note(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .config import save_config
    config: Config = ctx["config"]
    tool_target = tool_input["tool_name"]
    if tool_target in config.tool_notes:
        del config.tool_notes[tool_target]
        save_config(config)
        return f"Preference removed for '{tool_target}'"
    return f"No preference found for '{tool_target}'"


# ---------------------------------------------------------------------------
# Compact conversation
# ---------------------------------------------------------------------------

@handler("compact_conversation")
def handle_compact_conversation(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    assistant = ctx["assistant"]
    result = assistant.compact_history()
    status = assistant.get_context_status()
    return f"{result}\nContext now at {status['percent_used']:.1f}% ({status['input_tokens']:,} tokens)"


# ---------------------------------------------------------------------------
# Delegate operations
# ---------------------------------------------------------------------------

@handler("all_cards_delegate")
def handle_all_cards_delegate(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    assistant = ctx["assistant"]
    return assistant._handle_all_cards_delegate(tool_input)


@handler("card_subset_delegate")
def handle_card_subset_delegate(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    assistant = ctx["assistant"]
    return assistant._handle_card_subset_delegate(tool_input)


# ---------------------------------------------------------------------------
# Translation practice
# ---------------------------------------------------------------------------

@handler("start_translation_practice")
def handle_start_translation_practice(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .translation_practice import (
        PracticeDirection,
        CardSource,
        PracticeSession,
        load_practice_cards,
    )

    deck_name = tool_input["deck_name"]
    count = tool_input.get("count", 10)
    direction_str = tool_input.get("direction", "en_to_es")
    source_str = tool_input.get("card_source", "mixed")

    direction = PracticeDirection(direction_str)
    source = CardSource(source_str)

    cards = load_practice_cards(anki, deck_name, source, count)
    if not cards:
        return f"No cards found in deck '{deck_name}' matching source '{source_str}'. Make sure the deck exists and has cards."

    session = PracticeSession(
        deck_name=deck_name,
        direction=direction,
        cards=cards,
    )

    # Store session on the assistant for the practice sub-loop to use
    assistant = ctx.get("assistant")
    if assistant:
        assistant._practice_session = session

    # Build a summary for Claude to use
    dir_label = "English -> Spanish" if direction == PracticeDirection.EN_TO_ES else "Spanish -> English"
    due_count = sum(1 for c in cards if c.is_due)
    new_count = sum(1 for c in cards if c.is_new)

    lines = [
        f"Practice session ready: {len(cards)} cards from '{deck_name}'",
        f"Direction: {dir_label}",
        f"Cards: {due_count} due for review, {new_count} new",
        "",
        "The chat UI will now enter practice mode. Present the first question.",
        "",
        "INSTRUCTIONS FOR PRACTICE MODE:",
        "- Present one phrase at a time for the user to translate",
        f"- Direction: {dir_label}",
        "- After the user answers, evaluate on: meaning (0-4), grammar (0-4), naturalness (0-4), vocabulary (0-4)",
        "- Give clear feedback with corrections if needed",
        "- After the session, show which words are due for Anki review and suggest what button to press",
        "- Adapt difficulty: after 3+ correct, use harder constructions; after 2+ wrong, simplify and explain grammar",
        "- Support commands: /skip, /hint, /quit, /score",
        "",
        "FIRST CARD:",
    ]

    card = session.current_card
    if card:
        if direction == PracticeDirection.EN_TO_ES:
            lines.append(f"English (front): {card.front}")
            lines.append(f"Spanish answer (back): {card.back}")
        else:
            lines.append(f"Spanish (back): {card.back}")
            lines.append(f"English answer (front): {card.front}")
        if card.is_due:
            lines.append("(This card IS due for Anki review)")
        lines.append(f"Tags: {', '.join(card.tags) if card.tags else 'none'}")

    return "\n".join(lines)


@handler("log_practice_session")
def handle_log_practice_session(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .learning_summary import load_summary, save_summary

    summary = load_summary()

    # Initialize practice_sessions list if not present
    if "practice_sessions" not in summary:
        summary["practice_sessions"] = []

    session_record = {
        "type": tool_input.get("practice_type", "translation"),
        "direction": tool_input.get("direction", ""),
        "deck_name": tool_input.get("deck_name", ""),
        "phrases_attempted": tool_input.get("phrases_attempted", 0),
        "correct": tool_input.get("correct", 0),
        "partial": tool_input.get("partial", 0),
        "incorrect": tool_input.get("incorrect", 0),
        "score_percent": tool_input.get("score_percent", 0),
        "weak_words": tool_input.get("weak_words", []),
        "common_errors": tool_input.get("common_errors", []),
        "topics": tool_input.get("topics", []),
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }

    summary["practice_sessions"].append(session_record)

    # Keep only last 50 sessions
    summary["practice_sessions"] = summary["practice_sessions"][-50:]

    save_summary(summary)

    # Record study activity for streak tracking
    try:
        from .progress_tracking import record_activity
        record_activity()
    except Exception:
        pass

    attempted = session_record["phrases_attempted"]
    correct = session_record["correct"]
    score = session_record["score_percent"]
    return f"Practice session logged: {correct}/{attempted} correct ({score:.0f}%). Total sessions recorded: {len(summary['practice_sessions'])}"


# ---------------------------------------------------------------------------
# Grammar quiz
# ---------------------------------------------------------------------------

@handler("start_grammar_quiz")
def handle_start_grammar_quiz(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .grammar_quiz import (
        QuizSession,
        build_quiz_generation_prompt,
        parse_quiz_questions,
        get_topic_mastery,
    )
    from .learning_summary import load_summary

    topic = tool_input["topic"]
    level = tool_input["level"]
    question_types = tool_input.get("question_types")

    # P1: Multiple quiz sizes
    QUIZ_SIZES = {
        "quick": {"count": 10, "description": "Quick quiz (10 questions, 1 topic)"},
        "assessment": {"count": 28, "description": "Assessment (28 questions, full CEFR level)"},
        "comprehensive": {"count": 50, "description": "Comprehensive (50 questions, multi-level)"},
    }
    size = tool_input.get("size")
    if size and size in QUIZ_SIZES:
        count = QUIZ_SIZES[size]["count"]
    else:
        count = min(tool_input.get("count", 5), 50)

    # Get known vocabulary from the learning summary so Claude uses familiar words
    summary = load_summary()
    level_data = summary.get("levels", {}).get(level, {})
    known_vocabulary = level_data.get("what_i_know", {}).get("vocabulary", [])

    # Build the generation prompt
    prompt = build_quiz_generation_prompt(
        topic=topic,
        cefr_level=level,
        count=count,
        question_types=question_types,
        known_vocabulary=known_vocabulary if known_vocabulary else None,
    )

    # Generate questions using Claude
    assistant = ctx.get("assistant")
    if not assistant:
        return "Error: assistant context not available"

    try:
        response = assistant.client.messages.create(
            model=assistant.config.subagent_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text
        questions = parse_quiz_questions(raw_text)
    except Exception as e:
        return f"Error generating quiz questions: {e}"

    if not questions:
        return "Failed to generate quiz questions. Please try again."

    # Create session and store on assistant
    session = QuizSession(
        topic=topic,
        cefr_level=level,
        questions=questions,
    )
    assistant._quiz_session = session

    # Get mastery data for context
    mastery = get_topic_mastery()
    topic_mastery = mastery.get(topic)

    lines = [
        f"Grammar quiz ready: {len(questions)} questions on '{topic}' at {level} level.",
    ]
    if topic_mastery:
        lines.append(
            f"Previous attempts: {topic_mastery['quizzed_count']}, "
            f"avg score: {topic_mastery['avg_score']:.0f}%, "
            f"mastered: {'Yes' if topic_mastery['mastered'] else 'No'}"
        )
    lines.extend([
        "",
        "The chat UI will now enter quiz mode. Present each question using Rich panels.",
        "",
        "INSTRUCTIONS FOR QUIZ MODE:",
        "- Present one question at a time with a numbered header (Q1/N, Q2/N, etc.)",
        "- Show the question type label and any instructions",
        "- For multiple choice: display all 4 options clearly",
        "- For conjugation: ask for all 6 person forms",
        "- Wait for the user's answer, then grade it",
        "- After grading, show: correct/incorrect, the correct answer, and a grammar explanation",
        "- Support commands: /skip, /hint, /quit, /score",
        "- After all questions, show a summary with score, breakdown by type, and weak areas",
        "- If score < 85%, offer to create Anki cards for the weak grammar concepts",
        "",
        "QUESTIONS (present them one at a time):",
        "",
    ])

    for i, q in enumerate(questions, 1):
        lines.append(f"Q{i}. [{q.question_type}] {q.question_text}")
        if q.options:
            for opt in q.options:
                lines.append(f"    {opt}")
        lines.append(f"    Answer: {q.correct_answer}")
        if q.hint:
            lines.append(f"    Hint: {q.hint}")
        lines.append("")

    lines.append("Present Q1 now. Do NOT reveal the answer to the user.")

    return "\n".join(lines)


@handler("log_quiz_results")
def handle_log_quiz_results(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .grammar_quiz import QuizResult, record_quiz_result, MASTERY_THRESHOLD

    topic = tool_input["topic"]
    level = tool_input["level"]
    attempted = tool_input["questions_attempted"]
    correct = tool_input["correct"]
    weak_areas = tool_input.get("weak_areas", [])

    score = (correct / attempted * 100) if attempted > 0 else 0.0

    result = QuizResult(
        topic=topic,
        cefr_level=level,
        questions_attempted=attempted,
        correct=correct,
        score=score,
        weak_areas=weak_areas,
        question_type_breakdown={},
    )

    mastery = record_quiz_result(result)

    # P2: Also record per-topic grammar scores
    from .grammar_scores import record_topic_score
    topic_score = record_topic_score(topic, level, attempted, correct)

    mastered_str = "MASTERED" if mastery["mastered"] else "not yet mastered"
    lines = [
        f"Quiz results logged for '{topic}' ({level}):",
        f"  Score: {correct}/{attempted} ({score:.0f}%)",
        f"  Status: {mastered_str} (avg: {mastery['avg_score']:.0f}%, threshold: {MASTERY_THRESHOLD:.0f}%)",
        f"  Total quizzes on this topic: {mastery['quizzed_count']}",
        f"  Per-topic score: {topic_score.average_score:.0f}% [{topic_score.mastery_level}]",
    ]
    if weak_areas:
        lines.append(f"  Weak areas: {', '.join(weak_areas)}")

    # Also update learning summary with quiz stats
    from .learning_summary import load_summary, save_summary
    summary = load_summary()
    if "quiz_results" not in summary:
        summary["quiz_results"] = []
    summary["quiz_results"].append({
        "topic": topic,
        "level": level,
        "score": score,
        "attempted": attempted,
        "correct": correct,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    })
    summary["quiz_results"] = summary["quiz_results"][-50:]
    save_summary(summary)

    # Record study activity for streak tracking
    try:
        from .progress_tracking import record_activity
        record_activity()
    except Exception:
        pass

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Error journal
# ---------------------------------------------------------------------------

@handler("get_error_patterns")
def handle_get_error_patterns(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .error_journal import get_error_patterns, format_error_patterns_text

    min_count = tool_input.get("min_count", 1)
    limit = tool_input.get("limit", 20)

    entries = get_error_patterns(min_count=min_count, limit=limit)
    return format_error_patterns_text(entries)


@handler("log_error")
def handle_log_error(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .error_journal import log_error

    entry = log_error(
        error_type=tool_input["error_type"],
        example=tool_input["example"],
        correction=tool_input.get("correction", ""),
        context=tool_input.get("context", ""),
        tags=tool_input.get("tags"),
    )

    return (
        f"Error logged: '{entry.error_type}' (total: {entry.count} occurrences). "
        f"Latest: '{tool_input['example']}'"
    )


# ---------------------------------------------------------------------------
# Conversation simulation
# ---------------------------------------------------------------------------

# Default characters per scenario
_SCENARIO_CHARACTERS: dict[str, str] = {
    "ordering_food": "a friendly waiter at a traditional tapas bar in Madrid",
    "asking_directions": "a helpful local in a Spanish city",
    "hotel_checkin": "a receptionist at a small hotel in Barcelona",
    "shopping": "a shopkeeper at a clothing store",
    "job_interview": "a hiring manager at a Spanish tech company",
    "doctor_visit": "a doctor at a local clinic",
    "phone_call": "a customer service representative",
    "apartment_rental": "a landlord showing an apartment",
    "debate": "a university student with strong opinions",
    "negotiation": "a business partner discussing contract terms",
    "complaint": "a store manager handling a customer complaint",
    "storytelling": "a friend sharing stories at a cafe",
}

# Scenario descriptions for the system prompt
_SCENARIO_DESCRIPTIONS: dict[str, str] = {
    "ordering_food": "The user is at a restaurant and needs to order food, ask about the menu, request modifications, and pay the bill.",
    "asking_directions": "The user is lost and needs to ask for directions to a specific place. Include landmarks, turns, and distance references.",
    "hotel_checkin": "The user is checking into a hotel. Handle reservation lookup, room preferences, amenities questions, and payment.",
    "shopping": "The user is shopping for clothes. Discuss sizes, colors, prices, trying things on, and making a purchase.",
    "job_interview": "The user is interviewing for a position. Ask about experience, skills, availability, and salary expectations.",
    "doctor_visit": "The user has a health concern. Ask about symptoms, medical history, and explain a diagnosis/treatment.",
    "phone_call": "The user is calling about a service issue. Handle identification, problem description, and resolution steps.",
    "apartment_rental": "The user is looking at an apartment to rent. Discuss rooms, amenities, neighborhood, lease terms, and price.",
    "debate": "Engage the user in a friendly debate on a current topic. Present counterarguments and ask for their reasoning.",
    "negotiation": "The user is negotiating terms of a deal. Discuss prices, deadlines, conditions, and reach a compromise.",
    "complaint": "The user is making a complaint about a product or service. Listen, apologize, and offer solutions.",
    "storytelling": "Exchange stories with the user. Share an anecdote and ask them to share one too. Keep it conversational.",
}


@handler("start_conversation_sim")
def handle_start_conversation_sim(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    scenario = tool_input["scenario"]
    level = tool_input["level"]
    character = tool_input.get("character")

    # Resolve character
    if not character:
        character = _SCENARIO_CHARACTERS.get(scenario, f"a Spanish speaker in a {scenario} situation")

    # Resolve scenario description
    scenario_desc = _SCENARIO_DESCRIPTIONS.get(
        scenario,
        f"A conversation about: {scenario}. Engage naturally and keep the conversation going."
    )

    # Store session on assistant
    assistant = ctx.get("assistant")
    if assistant:
        assistant._conversation_sim = {
            "scenario": scenario,
            "level": level,
            "character": character,
            "turn_count": 0,
        }

    # Build level-appropriate language guidance
    level_guides = {
        "A2": "Use simple present and past tense. Short sentences. Basic vocabulary. Speak slowly and clearly. Rephrase if the user seems confused.",
        "B1": "Use a mix of tenses including some subjunctive. Moderate vocabulary. Natural sentence length. Occasionally introduce new expressions and explain them.",
        "B2": "Use the full range of tenses, idiomatic expressions, and nuanced vocabulary. Speak naturally as you would with another adult. Challenge the user with complex structures.",
    }
    language_guide = level_guides.get(level, level_guides["B1"])

    lines = [
        f"Conversation simulation ready.",
        f"Scenario: {scenario}",
        f"Character: {character}",
        f"Level: {level}",
        "",
        "The chat UI will now enter conversation mode.",
        "",
        "INSTRUCTIONS FOR CONVERSATION MODE:",
        f"You are role-playing as: {character}",
        f"Scenario: {scenario_desc}",
        f"CEFR Level: {level}",
        f"Language guide: {language_guide}",
        "",
        "RULES:",
        "- Stay in character. Speak ONLY in Spanish (with occasional parenthetical translations for difficult words at A2 level).",
        "- Keep your responses to 2-4 sentences to give the user a chance to respond.",
        "- If the user makes grammar or vocabulary mistakes, gently correct them in-character (e.g., 'Ah, quieres decir... (correction)').",
        "- After every 3-4 exchanges, briefly note any error patterns you see and call log_error for recurring mistakes.",
        "- When the conversation ends naturally or the user says /quit, summarize the conversation performance.",
        "- After the conversation, show which vocabulary words are due for Anki review and suggest what button to press.",
        "- Track new vocabulary the user encountered and offer to create Anki cards for them.",
        "",
        "Start the conversation now. Greet the user in character and set the scene.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Daily challenge / Word of the day
# ---------------------------------------------------------------------------

@handler("get_daily_challenge")
def handle_get_daily_challenge(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    import json as _json
    from datetime import date
    from .paths import DAILY_CHALLENGE_FILE, ensure_data_dir, atomic_json_write
    from .cefr import CEFRData, load_progress_cache, match_cards_to_cefr, save_progress_cache

    today = date.today().isoformat()

    # Check if we already did today's challenge
    ensure_data_dir()
    state = {}
    if DAILY_CHALLENGE_FILE.exists():
        try:
            with open(DAILY_CHALLENGE_FILE) as f:
                state = _json.load(f)
        except (ValueError, IOError):
            state = {}

    if state.get("date") == today and not tool_input.get("force"):
        # Already done today - return the cached challenge
        return (
            f"Today's challenge has already been presented.\n"
            f"Word of the day: {state.get('word', '?')} ({state.get('english', '?')})\n"
            f"Level: {state.get('level', '?')}\n"
            f"Use force=true to generate a new challenge."
        )

    # Load CEFR data and find gap words
    cefr_data = CEFRData()
    cefr_data.load()

    progress = load_progress_cache()
    if progress is None:
        try:
            progress = match_cards_to_cefr(anki, cefr_data)
            save_progress_cache(progress)
        except Exception:
            progress = {}

    # Find unknown words from the lowest incomplete level
    challenge_word = None
    challenge_level = None
    for level_key in ("A1", "A2", "B1", "B2", "C1", "C2"):
        level_data = progress.get(level_key)
        if not level_data:
            continue
        unknown = level_data.unknown_words
        if unknown:
            # Pick a different word than yesterday
            yesterday_word = state.get("word", "")
            import random
            candidates = [w for w in unknown if w != yesterday_word]
            if not candidates:
                candidates = unknown
            challenge_word = random.choice(candidates[:20])  # pick from top 20 unknowns
            challenge_level = level_key
            break

    if challenge_word is None:
        return "Congratulations! You know all words in the CEFR lists. No daily challenge needed."

    # Look up the word details
    word_info = cefr_data._word_index.get(challenge_word)
    english = ""
    category = ""
    if word_info:
        _, cefr_word = word_info
        english = cefr_word.english
        category = cefr_word.category

    # Save today's challenge
    state = {
        "date": today,
        "word": challenge_word,
        "english": english,
        "level": challenge_level,
        "category": category,
        "completed": False,
    }
    atomic_json_write(DAILY_CHALLENGE_FILE, state)

    # Build the challenge
    lines = [
        f"DAILY CHALLENGE - {today}",
        "=" * 40,
        "",
        f"Word of the Day: {challenge_word}",
        f"English: {english}",
        f"Level: {challenge_level} | Category: {category}",
        "",
        "INSTRUCTIONS FOR THE DAILY CHALLENGE:",
        f"1. Present the word '{challenge_word}' ({english}) with pronunciation tips",
        f"2. Show 2-3 example sentences using this word",
        f"3. Quick review: ask the user to translate a sentence using '{challenge_word}'",
        f"4. Offer to create an Anki card for this word",
        "",
        "Keep it brief and encouraging - this should take 2-3 minutes max.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Smart study suggestions
# ---------------------------------------------------------------------------

@handler("get_study_suggestion")
def handle_get_study_suggestion(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .learning_summary import load_summary
    from .error_journal import get_error_patterns

    lines = []

    # 1. Deck stats - cards due
    try:
        stats = anki.get_collection_stats()
        total_due = stats.get("total_due", 0)
        total_new = stats.get("total_new", 0)
        total_review = stats.get("total_review", 0)
        lines.append(f"Cards due today: {total_due} (New: {total_new}, Review: {total_review})")
        if total_due > 20:
            lines.append("SUGGESTION: You have many cards due. Consider a review session first.")
        elif total_due > 0:
            lines.append(f"SUGGESTION: Clear your {total_due} due cards before learning new material.")
        else:
            lines.append("All caught up on reviews!")
    except Exception:
        lines.append("Could not fetch deck stats (Anki may not be connected).")

    # 2. CEFR progress - weakest areas
    try:
        from .cefr import CEFRData, load_progress_cache
        cefr_data = CEFRData()
        cefr_data.load()
        progress = load_progress_cache()
        if progress:
            # Find the lowest incomplete level
            weakest_level = None
            weakest_pct = 100.0
            for level_key, level_data in sorted(progress.items()):
                pct = level_data.percent
                if pct < 90 and pct < weakest_pct:
                    weakest_level = level_key
                    weakest_pct = pct

            if weakest_level:
                level_data = progress[weakest_level]
                lines.append(f"\nCEFR focus: {weakest_level} ({weakest_pct:.0f}% complete)")

                # Find weakest category
                cats = level_data.categories
                if cats:
                    weakest_cat = min(cats.items(), key=lambda x: x[1].percent)
                    lines.append(f"Weakest category: {weakest_cat[0]} ({weakest_cat[1].percent:.0f}%)")
                    lines.append(f"SUGGESTION: Focus on {weakest_level} {weakest_cat[0]} vocabulary.")
    except Exception:
        pass

    # 3. Error patterns - recurring mistakes
    error_patterns = get_error_patterns(min_count=2, limit=3)
    if error_patterns:
        lines.append("\nRecurring error patterns:")
        for ep in error_patterns:
            lines.append(f"  - {ep.error_type} (x{ep.count})")
        lines.append(f"SUGGESTION: Practice grammar targeting: {error_patterns[0].error_type}")

    # 4. Learning summary - recent activity
    summary = load_summary()
    total_cards = summary.get("total_cards_added", 0)
    recent = summary.get("recent_additions", [])
    if recent:
        lines.append(f"\nTotal cards created: {total_cards}")
        lines.append(f"Recent additions: {', '.join(recent[-5:])}")

    # 5. Quiz weak areas
    quiz_results = summary.get("quiz_results", [])
    if quiz_results:
        last_quiz = quiz_results[-1]
        if last_quiz.get("score", 100) < 85:
            lines.append(f"\nLast quiz: {last_quiz.get('topic', '?')} ({last_quiz.get('score', 0):.0f}%)")
            lines.append(f"SUGGESTION: Retake quiz on '{last_quiz['topic']}' to improve mastery.")

    if not lines:
        return "Start by reviewing any due cards, then explore new vocabulary with CEFR suggestions."

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Vocabulary network (related words)
# ---------------------------------------------------------------------------

@handler("get_related_words")
def handle_get_related_words(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .cefr import CEFRData

    word = tool_input["word"].lower().strip()
    limit = tool_input.get("limit", 10)

    cefr_data = CEFRData()
    cefr_data.load()

    # Find the word in CEFR data
    source_word = None
    source_level = None
    if hasattr(cefr_data, "_word_index") and word in cefr_data._word_index:
        source_level, source_word = cefr_data._word_index[word]

    if source_word is None:
        return f"'{word}' not found in CEFR word lists. Cannot find related words."

    # Gather related words: same category, same subcategory, same tags
    related = []
    seen = {word}

    # Search across all levels for words in the same category/subcategory
    for level_key in ("A1", "A2", "B1", "B2", "C1", "C2"):
        words_at_level = cefr_data._words.get(level_key, [])
        for w in words_at_level:
            if w.word in seen:
                continue
            score = 0
            # Same category = strong relation
            if w.category == source_word.category:
                score += 2
            # Same subcategory = very strong relation
            if w.subcategory == source_word.subcategory:
                score += 3
            # Shared tags
            shared_tags = set(w.tags or []) & set(source_word.tags or [])
            score += len(shared_tags)
            # Same POS = slight bonus
            if w.pos == source_word.pos:
                score += 1

            if score > 0:
                related.append((score, level_key, w))
                seen.add(w.word)

    # Sort by relevance score descending
    related.sort(key=lambda x: x[0], reverse=True)
    related = related[:limit]

    if not related:
        return f"No related words found for '{word}' in CEFR data."

    # Check which the user already has in Anki
    known_words = set()
    for _, _, w in related:
        tag = f"word::{w.word}"
        cards = anki.search_cards(f'tag:"{tag}"', limit=1)
        if cards:
            known_words.add(w.word)

    lines = [
        f"Related words for '{word}' ({source_word.category} / {source_word.subcategory}, {source_level}):",
        ""
    ]

    for score, level, w in related:
        status = "KNOWN" if w.word in known_words else "NEW"
        lines.append(f"  [{status}] {w.word} ({w.english}) - {level} {w.category}/{w.subcategory}")

    new_count = sum(1 for _, _, w in related if w.word not in known_words)
    if new_count > 0:
        new_words = [w.word for _, _, w in related if w.word not in known_words]
        lines.append(f"\n{new_count} new words you could learn: {', '.join(new_words[:10])}")
        lines.append("Want me to create Anki cards for any of these?")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Contextual sentence generator
# ---------------------------------------------------------------------------

@handler("generate_contexts")
def handle_generate_contexts(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    word = tool_input["word"]
    context_type = tool_input.get("context_type", "conversation")
    count = tool_input.get("count", 5)

    assistant = ctx.get("assistant")
    if not assistant:
        return "Error: assistant context not available"

    context_descriptions = {
        "conversation": "casual spoken conversation between friends",
        "formal": "formal written communication (business email, letter, official document)",
        "narrative": "narrative storytelling (novel, short story, personal anecdote)",
        "email": "email correspondence (professional and semi-formal)",
        "academic": "academic writing (essay, report, lecture)",
    }

    ctx_desc = context_descriptions.get(context_type, f"a {context_type} context")

    prompt = f"""Generate exactly {count} example sentences in Spanish using the word/phrase "{word}" in {ctx_desc}.

For each sentence:
1. Write the Spanish sentence
2. Provide the English translation
3. Briefly note any grammar or usage point

Return ONLY valid JSON array:
[
  {{
    "spanish": "sentence in Spanish",
    "english": "English translation",
    "note": "grammar/usage note"
  }}
]

Rules:
- Use natural, authentic Spanish
- Vary the tenses and structures
- Make sentences appropriate for the context type: {context_type}
- Include the target word/phrase naturally (not forced)"""

    try:
        response = assistant.client.messages.create(
            model=assistant.config.subagent_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text

        # Parse JSON
        import json as _json
        text = raw_text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            return f"Generated sentences for '{word}':\n\n{raw_text}"

        sentences = _json.loads(text[start:end + 1])

        lines = [f"Contextual sentences for '{word}' ({context_type}):", ""]
        for i, s in enumerate(sentences, 1):
            lines.append(f"{i}. {s.get('spanish', '')}")
            lines.append(f"   {s.get('english', '')}")
            if s.get("note"):
                lines.append(f"   Note: {s['note']}")
            lines.append("")

        lines.append(f"Want me to add these examples to the card for '{word}'?")
        return "\n".join(lines)

    except Exception as e:
        return f"Error generating contextual sentences: {e}"


# ---------------------------------------------------------------------------
# CEFR progress
# ---------------------------------------------------------------------------

@handler("get_cefr_progress")
def handle_get_cefr_progress(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .cefr import (
        CEFRData, load_progress_cache, match_cards_to_cefr,
        save_progress_cache, format_progress_text,
    )

    level = tool_input.get("level")
    category = tool_input.get("category")
    show_unknown = tool_input.get("show_unknown", False)
    deck_name = tool_input.get("deck_name")

    cefr_data = CEFRData()
    cefr_data.load()

    # Try cache first; rescan if no cache
    progress = load_progress_cache()
    if progress is None:
        progress = match_cards_to_cefr(anki, cefr_data, deck_name)
        save_progress_cache(progress)

    return format_progress_text(progress, level=level, category=category, show_unknown=show_unknown)


@handler("get_cefr_suggestions")
def handle_get_cefr_suggestions(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .cefr import (
        CEFRData, load_progress_cache, match_cards_to_cefr,
        save_progress_cache, get_suggestions, format_suggestions_text,
    )

    level = tool_input.get("level")
    count = tool_input.get("count", 10)
    deck_name = tool_input.get("deck_name")

    cefr_data = CEFRData()
    cefr_data.load()

    progress = load_progress_cache()
    if progress is None:
        progress = match_cards_to_cefr(anki, cefr_data, deck_name)
        save_progress_cache(progress)

    suggestions = get_suggestions(cefr_data, progress, level=level, count=count)
    return format_suggestions_text(suggestions)


@handler("sync_cefr_progress")
def handle_sync_cefr_progress(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .cefr import (
        CEFRData, match_cards_to_cefr, save_progress_cache,
        invalidate_cache, format_progress_text,
    )

    deck_name = tool_input.get("deck_name")

    cefr_data = CEFRData()
    cefr_data.load()

    invalidate_cache()
    progress = match_cards_to_cefr(anki, cefr_data, deck_name)
    save_progress_cache(progress)

    return "CEFR progress rescanned and cached.\n\n" + format_progress_text(progress)


# ---------------------------------------------------------------------------
# Progress tracking: skills radar, streaks, time progress, weak spots
# ---------------------------------------------------------------------------

@handler("get_skills_radar")
def handle_get_skills_radar(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .progress_tracking import get_skills_radar, format_skills_radar_text
    from .learning_summary import load_summary
    from .error_journal import get_error_patterns

    # Gather data sources
    collection_stats = None
    try:
        collection_stats = anki.get_collection_stats()
    except Exception:
        pass

    learning_summary = load_summary()
    quiz_results = learning_summary.get("quiz_results", [])

    cefr_progress = None
    try:
        from .cefr import load_progress_cache
        cefr_progress = load_progress_cache()
    except Exception:
        pass

    radar = get_skills_radar(
        collection_stats=collection_stats,
        learning_summary=learning_summary,
        error_journal_entries=get_error_patterns(),
        quiz_results=quiz_results,
        cefr_progress=cefr_progress,
    )

    # Record activity
    try:
        from .progress_tracking import record_activity
        record_activity()
    except Exception:
        pass

    return format_skills_radar_text(radar)


@handler("get_progress_over_time")
def handle_get_progress_over_time(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .progress_tracking import get_progress_over_time, format_progress_over_time_text

    period = tool_input.get("period", "month")
    progress = get_progress_over_time(period=period)
    return format_progress_over_time_text(progress)


@handler("get_weak_spots")
def handle_get_weak_spots(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .progress_tracking import get_weak_spots
    from .learning_summary import load_summary
    from .error_journal import get_error_patterns

    learning_summary = load_summary()
    quiz_results = learning_summary.get("quiz_results", [])
    error_entries = get_error_patterns()

    card_reviews = []
    try:
        card_reviews = anki.get_card_reviews()
    except Exception:
        pass

    result = get_weak_spots(
        quiz_results=quiz_results,
        error_entries=error_entries,
        card_reviews=card_reviews,
    )

    return result["summary"]


@handler("get_study_streaks")
def handle_get_study_streaks(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .progress_tracking import get_streaks_summary

    summary = get_streaks_summary()

    lines = [
        "Study Streaks",
        "=" * 40,
        f"  Current streak: {summary['current_streak']} day(s)",
        f"  Longest streak: {summary['longest_streak']} day(s)",
        f"  Total active days: {summary['total_active_days']}",
        f"  Active in last 30 days: {summary['last_30_days_active']}",
        "",
        "  Last 7 days:",
    ]

    for day_str, active in summary["last_7_days"].items():
        marker = "[##]" if active else "[  ]"
        lines.append(f"    {day_str}: {marker}")

    return "\n".join(lines)


@handler("record_study_activity")
def handle_record_study_activity(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from datetime import date
    from .progress_tracking import record_activity

    activity_date = None
    if tool_input.get("date"):
        try:
            activity_date = date.fromisoformat(tool_input["date"])
        except ValueError:
            return f"Invalid date format: {tool_input['date']}. Use YYYY-MM-DD."

    result = record_activity(activity_date)
    return (
        f"Activity recorded for {result['date_recorded']}.\n"
        f"Current streak: {result['current_streak']} day(s)\n"
        f"Longest streak: {result['longest_streak']} day(s)\n"
        f"Total active days: {result['total_active_days']}"
    )


# ---------------------------------------------------------------------------
# Cognate features (C5, C6)
# ---------------------------------------------------------------------------

@handler("scan_cognates")
def handle_scan_cognates(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .cefr import CEFRData
    from .cognates import classify_words_by_cognate_type, format_cognate_scan_text

    words = [w.lower().strip() for w in tool_input["words"]]

    cefr_data = CEFRData()
    cefr_data.load()

    groups = classify_words_by_cognate_type(words, cefr_data)
    return format_cognate_scan_text(groups)


@handler("check_false_friend")
def handle_check_false_friend(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .cognates import lookup_false_friend

    word = tool_input["word"].lower().strip()
    ff = lookup_false_friend(word)

    if ff is None:
        return f"'{word}' is NOT a known false friend. Safe to use normally."

    return (
        f"FALSE FRIEND DETECTED: {ff.spanish}\n"
        f"  Looks like English: {ff.seems_like}\n"
        f"  Actually means: {ff.actual_meaning}\n"
        f"  Correct equivalent: {ff.english_equivalent}\n"
        f"  Warning: {ff.warning}"
    )


# ---------------------------------------------------------------------------
# P9: Reading practice
# ---------------------------------------------------------------------------

@handler("start_reading_practice")
def handle_start_reading_practice(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    deck_name = tool_input["deck_name"]
    level = tool_input.get("level", "A2")
    topic = tool_input.get("topic", "")

    known_words: list[str] = []
    due_words: list[str] = []
    try:
        import re
        cards = anki.get_deck_cards(deck_name, limit=200)
        for c in cards:
            clean = re.sub(r'<[^>]+>', ' ', c.back).strip()
            word = clean.split('\n')[0].split('<')[0].strip()[:40]
            if word:
                known_words.append(word)
    except Exception:
        pass

    try:
        import re as _re
        due_cards = anki.get_due_cards(deck_name, limit=30)
        for c in due_cards:
            clean = _re.sub(r'<[^>]+>', ' ', c.back).strip()
            word = clean.split('\n')[0].split('<')[0].strip()[:40]
            if word:
                due_words.append(word)
    except Exception:
        pass

    known_sample = known_words[:40]
    due_sample = due_words[:15]
    topic_instruction = f" about '{topic}'" if topic else ""

    lines = [
        f"Reading practice session ready.",
        f"Level: {level} | Deck: {deck_name}",
        "",
        "INSTRUCTIONS FOR READING PRACTICE:",
        f"Generate a short paragraph (100-150 words) in Spanish at {level} level{topic_instruction}.",
        "",
        "VOCABULARY TO INCORPORATE:",
        f"Known words (use these naturally): {', '.join(known_sample[:20]) if known_sample else 'general A1-A2 vocabulary'}",
        f"Due for review (include some of these): {', '.join(due_sample[:10]) if due_sample else 'none'}",
        "",
        "RULES:",
        "- Write a cohesive, interesting paragraph - NOT a list of sentences",
        "- Use natural Spanish appropriate for the CEFR level",
        "- Bold key vocabulary words using **word** markdown",
        "- After the paragraph, provide a vocabulary glossary",
        "- DO NOT ask comprehension questions or test the user",
        "- DO NOT ask the user to translate anything",
        "- This is READING ONLY - just exposure to vocabulary in context",
        "- End with an encouraging message about the reading",
        "",
        "FORMAT: Present the text in a Rich panel with title 'READING PRACTICE'",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# P2: Per-topic grammar scores
# ---------------------------------------------------------------------------

@handler("get_grammar_scores")
def handle_get_grammar_scores(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .grammar_scores import format_grammar_scores_text
    return format_grammar_scores_text()


# ---------------------------------------------------------------------------
# P11: Anki review integration - session due words
# ---------------------------------------------------------------------------

@handler("get_session_due_words")
def handle_get_session_due_words(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    deck_name = tool_input["deck_name"]
    session_words = tool_input.get("session_words", [])
    session_results = tool_input.get("session_results", {})

    if not session_words:
        return "No session words provided."

    try:
        due_cards = anki.get_due_cards(deck_name, limit=200)
    except Exception:
        return "Could not fetch due cards from Anki."

    if not due_cards:
        return "No cards are due for review in this deck."

    # Match words to due cards using word:: tags (precise) instead of
    # text search (which falsely matches words in example sentences)
    due_word_map: dict[str, str] = {}
    match_method: dict[str, str] = {}  # track how each word was matched
    for word in session_words:
        word_lower = word.lower().strip()
        matched = False
        for card in due_cards:
            # Check word:: tag first (most reliable)
            has_word_tag = any(
                t.lower() == f"word::{word_lower}" for t in card.tags
            )
            if has_word_tag:
                due_word_map[word] = card.id
                match_method[word] = "tag"
                matched = True
                break
        if not matched:
            # Fallback: check if the word is the MAIN word on the card back
            # (first bold word, not in example sentences)
            import re
            for card in due_cards:
                back_text = re.sub(r'<[^>]+>', ' ', card.back).strip()
                main_word = back_text.split('\n')[0].split('(')[0].strip().lower()
                if word_lower == main_word:
                    due_word_map[word] = card.id
                    match_method[word] = "fallback (matched card back, no word:: tag found)"
                    break

    if not due_word_map:
        return "None of the session words are due for Anki review today."

    lines = [
        f"Session words due for Anki review ({len(due_word_map)}):",
        "",
    ]
    for word, card_id in sorted(due_word_map.items()):
        # Get interval estimates for each ease button
        try:
            intervals = anki.get_next_intervals(int(card_id))
        except Exception:
            intervals = {"again": "?", "hard": "?", "good": "?", "easy": "?"}

        # Suggest ease based on session performance
        word_result = session_results.get(word, "correct")
        if word_result == "incorrect":
            suggested_ease = 1
            suggested_label = "Again"
        elif word_result == "partial":
            suggested_ease = 2
            suggested_label = "Hard"
        elif word_result == "easy":
            suggested_ease = 4
            suggested_label = "Easy"
        else:
            suggested_ease = 3
            suggested_label = "Good"

        method = match_method.get(word, "tag")
        lines.append(f"  {word} (card ID: {card_id})")
        lines.append(f"    Suggested: {suggested_label} ({suggested_ease})")
        lines.append(f"    Intervals: Again={intervals['again']}, Hard={intervals['hard']}, Good={intervals['good']}, Easy={intervals['easy']}")
        if method != "tag":
            lines.append(f"    WARNING: Matched via {method} — card may not be the exact word. Verify before marking.")
        lines.append("")

    lines.extend([
        "Present a review table to the user with suggested ratings and intervals.",
        "Ask user to confirm or override ratings.",
        "Then use mark_cards_reviewed with per-card ease and card_words.",
        "Some cards may be marked successfully, others may need manual review in Anki.",
        "Present both outcomes cleanly — no confusing error messages.",
    ])
    return "\n".join(lines)


@handler("mark_cards_reviewed")
def handle_mark_cards_reviewed(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    card_ids = tool_input["card_ids"]
    default_ease = tool_input.get("ease", 3)
    per_card_ease = tool_input.get("per_card_ease", {})
    card_words = tool_input.get("card_words", {})

    if default_ease not in (1, 2, 3, 4):
        return f"Invalid ease rating: {default_ease}. Must be 1 (Again), 2 (Hard), 3 (Good), or 4 (Easy)."

    if not card_ids:
        return "No card IDs provided."

    ease_labels = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}
    marked = []
    review_in_anki = []

    for cid in card_ids:
        cid_str = str(cid)
        card_ease = per_card_ease.get(cid_str, default_ease)
        if card_ease not in (1, 2, 3, 4):
            card_ease = default_ease
        word = card_words.get(str(cid), str(cid))
        ease_label = ease_labels.get(card_ease, "Good")

        try:
            success, message = anki.answer_card(int(cid), card_ease)
            if success:
                marked.append(f"  {word} → {ease_label}")
            else:
                review_in_anki.append(f"  {word} → press {ease_label}")
        except Exception:
            review_in_anki.append(f"  {word} → press {ease_label}")

    # Record study activity for streaks
    try:
        from .progress_tracking import record_activity
        record_activity()
    except Exception:
        pass

    lines = []
    if marked:
        lines.append(f"Marked in Anki ({len(marked)}):")
        lines.extend(marked)
    if review_in_anki:
        if marked:
            lines.append("")
        lines.append(f"Review these in Anki manually ({len(review_in_anki)}):")
        lines.extend(review_in_anki)
    if not marked and not review_in_anki:
        lines.append("No cards to mark.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Micro-lesson generation (A5)
# ---------------------------------------------------------------------------

@handler("generate_micro_lesson")
def handle_generate_micro_lesson(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .error_journal import get_error_patterns

    error_type = tool_input["error_type"]
    level = tool_input.get("level", "A2")

    # Retrieve error data for context
    patterns = get_error_patterns(min_count=1, limit=50)
    target = None
    for p in patterns:
        if p.error_type == error_type:
            target = p
            break

    if target is None:
        return f"No error pattern found for '{error_type}'. Check get_error_patterns for available types."

    if target.count < 3:
        return (
            f"'{error_type}' has only {target.count} occurrence(s). "
            f"Micro-lessons are most effective with 3+ occurrences. "
            f"Keep practicing and check back later."
        )

    # Build the user's actual mistakes as context
    examples_text = ""
    for ex in target.examples[-5:]:
        inp = ex.get("input", "")
        corr = ex.get("correction", "")
        if inp:
            examples_text += f"  - Wrote: \"{inp}\""
            if corr:
                examples_text += f" -> Correct: \"{corr}\""
            examples_text += "\n"

    assistant = ctx.get("assistant")
    if not assistant:
        return "Error: assistant context not available"

    prompt = f"""Create a focused 2-3 minute micro-lesson for a Spanish learner at {level} level about: {error_type.replace('_', ' ')}

The student has made this mistake {target.count} times. Here are their actual errors:
{examples_text}

Structure the lesson as:
1. RULE: Name and explain the grammar rule clearly in 2-3 sentences
2. EXAMPLES: Show 3 correct examples demonstrating the rule
3. COMMON MISTAKES: Show 2-3 "wrong vs right" pairs using the student's actual errors above
4. PRACTICE: Create 3 fill-in-the-blank exercises (provide the answer key separately)
5. TIP: One memorable mnemonic or shortcut to remember the rule

Return ONLY valid JSON:
{{
    "title": "lesson title",
    "rule": "clear rule explanation",
    "examples": ["example 1", "example 2", "example 3"],
    "mistakes": [{{"wrong": "...", "right": "...", "explanation": "..."}}],
    "practice": [{{"question": "fill in blank", "answer": "correct answer"}}],
    "tip": "mnemonic or shortcut"
}}"""

    try:
        response = assistant.client.messages.create(
            model=assistant.config.subagent_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text.strip()

        # Parse JSON
        import json as _json
        text = raw_text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            return f"Micro-lesson for '{error_type}':\n\n{raw_text}"

        lesson = _json.loads(text[start : end + 1])

        lines = [
            f"MICRO-LESSON: {lesson.get('title', error_type.replace('_', ' ').title())}",
            f"Error pattern: {error_type} (seen {target.count}x)",
            "=" * 50,
            "",
            "RULE:",
            lesson.get("rule", ""),
            "",
            "CORRECT EXAMPLES:",
        ]
        for ex in lesson.get("examples", []):
            lines.append(f"  {ex}")

        lines.append("")
        lines.append("COMMON MISTAKES (your actual errors):")
        for m in lesson.get("mistakes", []):
            lines.append(f"  WRONG: {m.get('wrong', '')}")
            lines.append(f"  RIGHT: {m.get('right', '')}")
            lines.append(f"  Why: {m.get('explanation', '')}")
            lines.append("")

        lines.append("PRACTICE:")
        for i, p in enumerate(lesson.get("practice", []), 1):
            lines.append(f"  {i}. {p.get('question', '')}")

        lines.append("")
        lines.append(f"TIP: {lesson.get('tip', '')}")
        lines.append("")
        lines.append("Present the practice questions to the user ONE AT A TIME.")
        lines.append("After they complete the exercises, offer to create Anki cards for this grammar rule.")

        lines.append("")
        lines.append("ANSWER KEY (do NOT show to user until they answer):")
        for i, p in enumerate(lesson.get("practice", []), 1):
            lines.append(f"  {i}. {p.get('answer', '')}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error generating micro-lesson: {e}"


# ---------------------------------------------------------------------------
# Batch delegate (A6)
# ---------------------------------------------------------------------------

@handler("batch_delegate")
def handle_batch_delegate(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    from .delegate import BatchDelegateProcessor

    delegate_type = tool_input["delegate_type"]
    items = tool_input["items"]
    prompt_override = tool_input.get("prompt_override")
    workers = min(tool_input.get("workers", 5), 10)

    if not items:
        return "No items to process."

    assistant = ctx.get("assistant")
    if not assistant:
        return "Error: assistant context not available"

    processor = BatchDelegateProcessor(
        client=assistant.client,
        model=assistant.config.subagent_model,
        max_workers=workers,
        rate_limit_delay=assistant.config.delegate_rate_limit_delay,
    )

    def progress_callback(event):
        assistant._progress_queue.put({
            "type": "delegate_progress",
            "completed": event.completed,
            "total": event.total,
            "current_card": event.current_item,
            "success": event.success,
            "error": event.error,
        })

    results = processor.process_batch(
        items=items,
        delegate_type=delegate_type,
        prompt_override=prompt_override,
        progress_callback=progress_callback,
    )

    successes = [r for r in results if r.error is None]
    errors = [r for r in results if r.error is not None]

    import json as _json

    lines = [
        f"Batch delegate '{delegate_type}': {len(successes)}/{len(results)} succeeded",
    ]

    if successes:
        lines.append("")
        lines.append("Results:")
        for r in successes:
            lines.append(f"  {r.item}: {_json.dumps(r.result, ensure_ascii=False)}")

    if errors:
        lines.append("")
        lines.append(f"Errors ({len(errors)}):")
        for r in errors[:5]:
            lines.append(f"  {r.item}: {r.error}")
        if len(errors) > 5:
            lines.append(f"  ... and {len(errors) - 5} more errors")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Vocabulary Network handlers (V1, V3-V11)
# ---------------------------------------------------------------------------

@handler("update_word_network")
def handle_update_word_network(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    """V1: Update vocabulary network after adding a card."""
    from .word_network import WordNetwork, WordNode, WordConnection, \
        ensure_default_disambiguation

    network = WordNetwork()
    network.load()
    ensure_default_disambiguation(network)

    word = tool_input["word"].lower().strip()

    # Create or update the node
    node = network.get_node(word)
    if node is None:
        node = WordNode(
            word=word,
            level=tool_input.get("level", ""),
            pos=tool_input.get("pos", ""),
            theme=tool_input.get("theme", ""),
        )
    else:
        if tool_input.get("level"):
            node.level = tool_input["level"]
        if tool_input.get("pos"):
            node.pos = tool_input["pos"]
        if tool_input.get("theme"):
            node.theme = tool_input["theme"]

    if tool_input.get("family_root"):
        node.family_root = tool_input["family_root"]
    if tool_input.get("note_id"):
        node.note_id = tool_input["note_id"]
    node.in_deck = True

    network.add_word(node)

    # Add connections
    connections_added = 0
    for conn_data in tool_input.get("connections", []):
        conn_type = conn_data["type"]
        target = conn_data["target"].lower().strip()
        strength = conn_data.get("strength", 1.0)
        network.add_connection(word, target, conn_type, strength)
        connections_added += 1

    # Add collocations (V5)
    collocations_added = 0
    for coll_data in tool_input.get("collocations", []):
        network.add_collocation(
            word,
            phrase=coll_data["phrase"],
            translation=coll_data.get("translation", ""),
        )
        collocations_added += 1

    network.save()

    parts = [f"Network updated: '{word}'"]
    if connections_added:
        parts.append(f"{connections_added} connection(s)")
    if collocations_added:
        parts.append(f"{collocations_added} collocation(s)")
    parts.append(f"Network size: {network.word_count} words")

    return " | ".join(parts)


@handler("show_word_connections")
def handle_show_word_connections(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    """V1: Show all connections for a word."""
    from .word_network import WordNetwork, ensure_default_disambiguation

    network = WordNetwork()
    network.load()
    ensure_default_disambiguation(network)

    word = tool_input["word"].lower().strip()
    node = network.get_node(word)

    if not node:
        return f"'{word}' not found in the vocabulary network. Add it first with update_word_network."

    lines = [
        f"Word: {node.word}",
        f"Level: {node.level or 'unknown'} | POS: {node.pos or 'unknown'} | Theme: {node.theme or 'unknown'}",
        f"In deck: {'Yes' if node.in_deck else 'No'}",
    ]

    if node.family_root:
        lines.append(f"Family root: {node.family_root}")

    if node.connections:
        lines.append(f"\nConnections ({len(node.connections)}):")
        by_type: dict[str, list] = {}
        for conn in node.connections:
            by_type.setdefault(conn.connection_type, []).append(conn)
        for conn_type, conns in sorted(by_type.items()):
            words = ", ".join(c.target_word for c in conns)
            lines.append(f"  {conn_type}: {words}")
    else:
        lines.append("\nNo connections yet.")

    if node.collocations:
        lines.append(f"\nCollocations ({len(node.collocations)}):")
        for coll in node.collocations:
            phrase = coll.get("phrase", "")
            trans = coll.get("translation", "")
            extra = f" = {trans}" if trans else ""
            lines.append(f"  - {phrase}{extra}")

    if node.disambiguation_group:
        lines.append(f"\nDisambiguation group: {node.disambiguation_group}")

    return "\n".join(lines)


@handler("get_morphological_family")
def handle_get_morphological_family(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    """V3: Find morphological relatives of a word."""
    from .word_network import WordNetwork, get_morphological_family, \
        ensure_default_disambiguation

    network = WordNetwork()
    network.load()
    ensure_default_disambiguation(network)

    word = tool_input["word"].lower().strip()
    result = get_morphological_family(word, network)

    lines = [f"Morphological family for '{word}':", ""]

    # Check Anki status for each family member once (avoid duplicate API calls)
    known_members: set[str] = set()
    if result["family"]:
        for member in result["family"]:
            tag = f"word::{member}"
            cards = anki.search_cards(f'tag:"{tag}"', limit=1)
            if cards:
                known_members.add(member)

        for member in result["family"]:
            status = "KNOWN" if member in known_members else "NEW"
            lines.append(f"  [{status}] {member}")
    else:
        lines.append("  No morphological relatives found.")

    if result["patterns_matched"]:
        lines.append(f"\nPatterns: {', '.join(result['patterns_matched'][:5])}")

    if result["network_family"]:
        lines.append(f"Network family: {', '.join(result['network_family'])}")

    new_words = [m for m in result["family"] if m not in known_members]

    if new_words:
        lines.append(f"\n{len(new_words)} new word(s) to learn: {', '.join(new_words[:10])}")
        lines.append("Want me to create Anki cards for any of these?")

    return "\n".join(lines)


@handler("get_disambiguation_practice")
def handle_get_disambiguation_practice(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    """V4: Get a disambiguation practice exercise."""
    from .word_network import WordNetwork, ensure_default_disambiguation

    network = WordNetwork()
    network.load()
    ensure_default_disambiguation(network)

    pair_id = tool_input["pair"]
    pair = network._disambiguation.get(pair_id)

    if not pair:
        available = ", ".join(sorted(network._disambiguation.keys()))
        return f"Pair '{pair_id}' not found. Available pairs: {available}"

    words_str = " / ".join(pair.words)

    lines = [
        f"DISAMBIGUATION PRACTICE: {words_str}",
        f"Pair: {pair.pair_id} | Category: {pair.category}",
        f"Practice count: {pair.practice_count} | Errors: {pair.error_counts or 'none'}",
        "",
        "INSTRUCTIONS FOR DISAMBIGUATION PRACTICE:",
        f"Generate 5 fill-in-the-blank sentences where the user must choose between: {words_str}",
        "",
        "For each sentence:",
        f"1. Write a Spanish sentence with a blank where one of [{words_str}] should go",
        "2. Provide the correct answer",
        "3. Explain WHY that word is correct and why the others are wrong",
        "",
        "RULES:",
        "- Present one sentence at a time",
        "- Wait for the user's answer before revealing the correct one",
        "- Keep score: correct/total",
        "- After all 5, show summary and call log_disambiguation_result",
        f"- Use log_disambiguation_result with pair_id='{pair_id}'",
        "",
        "START: Present the first sentence now.",
    ]

    return "\n".join(lines)


@handler("show_disambiguation_pairs")
def handle_show_disambiguation_pairs(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    """V4: List all disambiguation pairs with stats."""
    from .word_network import WordNetwork, ensure_default_disambiguation

    network = WordNetwork()
    network.load()
    ensure_default_disambiguation(network)

    pairs = network.get_disambiguation_pairs()
    if not pairs:
        return "No disambiguation pairs configured."

    lines = [f"Disambiguation Pairs ({len(pairs)}):", ""]

    for pair in sorted(pairs, key=lambda p: p.pair_id):
        words = " / ".join(pair.words)
        practiced = f"practiced {pair.practice_count}x" if pair.practice_count else "not practiced"
        errors = ""
        if pair.error_counts:
            err_parts = [f"{w}: {c}" for w, c in pair.error_counts.items()]
            errors = f" | errors: {', '.join(err_parts)}"
        lines.append(f"  {pair.pair_id}: {words} ({practiced}{errors})")

    lines.append("")
    lines.append("Use get_disambiguation_practice(pair='pair-id') to practice a pair.")

    return "\n".join(lines)


@handler("log_disambiguation_result")
def handle_log_disambiguation_result(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    """V4: Log disambiguation practice results."""
    from .word_network import WordNetwork, ensure_default_disambiguation

    network = WordNetwork()
    network.load()
    ensure_default_disambiguation(network)

    pair_id = tool_input["pair_id"]
    correct = tool_input["correct"]
    total = tool_input["total"]
    confused_words = tool_input.get("confused_words", [])

    pair = network._disambiguation.get(pair_id)
    if not pair:
        return f"Pair '{pair_id}' not found."

    network.record_disambiguation_practice(pair_id)

    for confused in confused_words:
        network.record_disambiguation_error(pair_id, confused)

    network.save()

    score = (correct / total * 100) if total > 0 else 0
    return (
        f"Disambiguation results logged for '{pair_id}':\n"
        f"  Score: {correct}/{total} ({score:.0f}%)\n"
        f"  Total practices: {pair.practice_count}\n"
        f"  Error counts: {pair.error_counts or 'none'}"
    )


@handler("get_semantic_field_progress")
def handle_get_semantic_field_progress(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    """V9: Show vocabulary progress per semantic/thematic field."""
    from .cefr import CEFRData

    theme = tool_input.get("theme")

    cefr_data = CEFRData()
    cefr_data.load()

    all_categories: dict[str, dict] = {}

    for level_key in ("A1", "A2", "B1", "B2", "C1", "C2"):
        words = cefr_data.get_words_for_level(level_key)
        for w in words:
            cat = w.category
            if theme and cat.lower() != theme.lower():
                continue
            if cat not in all_categories:
                all_categories[cat] = {"total": 0, "known": 0, "words": [], "known_words": []}
            all_categories[cat]["total"] += 1
            all_categories[cat]["words"].append(w.word)

    # Batch: fetch all cards once and extract word:: tags into a set
    all_cards = anki.search_cards("tag:word::*", limit=5000)
    known_words_set: set[str] = set()
    for card in all_cards:
        for tag in card.tags:
            if tag.startswith("word::"):
                known_words_set.add(tag[6:])  # strip "word::" prefix

    for cat, data in all_categories.items():
        for word_str in data["words"]:
            if word_str in known_words_set:
                data["known"] += 1
                data["known_words"].append(word_str)

    if not all_categories:
        if theme:
            return f"Theme '{theme}' not found in CEFR data."
        return "No CEFR data available."

    lines = []
    if theme:
        lines.append(f"Semantic Field Progress: {theme}")
    else:
        lines.append("Semantic Field Progress (all themes)")
    lines.append("=" * 50)
    lines.append("")

    for cat in sorted(all_categories.keys()):
        data = all_categories[cat]
        total = data["total"]
        known = data["known"]
        pct = (known / total * 100) if total > 0 else 0
        bar_len = 15
        filled = int(bar_len * pct / 100)
        bar = "#" * filled + "-" * (bar_len - filled)
        lines.append(f"  {cat}: {known}/{total} [{bar}] {pct:.0f}%")

    total_all = sum(d["total"] for d in all_categories.values())
    known_all = sum(d["known"] for d in all_categories.values())
    pct_all = (known_all / total_all * 100) if total_all > 0 else 0
    lines.append(f"\n  Overall: {known_all}/{total_all} ({pct_all:.0f}%)")

    if theme and len(all_categories) == 1:
        cat_data = list(all_categories.values())[0]
        unknown = [w for w in cat_data["words"] if w not in cat_data["known_words"]]
        if unknown:
            lines.append(f"\n  Unknown words ({len(unknown)}): {', '.join(unknown[:20])}")
            if len(unknown) > 20:
                lines.append(f"  ... and {len(unknown) - 20} more")

    return "\n".join(lines)


@handler("show_connection_map")
def handle_show_connection_map(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    """V10: Display ASCII connection map for a word."""
    from .word_network import WordNetwork, build_connection_map, \
        ensure_default_disambiguation

    network = WordNetwork()
    network.load()
    ensure_default_disambiguation(network)

    word = tool_input["word"].lower().strip()
    return build_connection_map(word, network)


@handler("start_pair_review")
def handle_start_pair_review(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    """V8: Start a pair-based review session."""
    from .word_network import WordNetwork, ensure_default_disambiguation

    network = WordNetwork()
    network.load()
    ensure_default_disambiguation(network)

    pair_type = tool_input.get("pair_type", "all")
    count = tool_input.get("count", 5)

    pairs: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    for word_key, node in network._nodes.items():
        for conn in node.connections:
            if pair_type != "all" and conn.connection_type != pair_type:
                continue
            pair_key = tuple(sorted([word_key, conn.target_word]))
            if pair_key not in seen:
                seen.add(pair_key)
                pairs.append((pair_key[0], pair_key[1], conn.connection_type))

    if not pairs:
        return f"No {pair_type} pairs found in the network. Add connections with update_word_network first."

    import random
    if len(pairs) > count:
        pairs = random.sample(pairs, count)

    lines = [
        f"PAIR-BASED REVIEW: {len(pairs)} pair(s)",
        f"Type filter: {pair_type}",
        "",
        "INSTRUCTIONS FOR PAIR REVIEW:",
        "Present each pair together with their meanings and differences.",
        "For each pair:",
        "1. Show both words with their meanings",
        "2. Explain the key difference",
        "3. Give one sentence using each word",
        "4. Ask the user to create a sentence distinguishing them",
        "5. Provide feedback on the user's sentence",
        "",
        "PAIRS TO REVIEW:",
    ]

    for i, (w1, w2, conn_type) in enumerate(pairs, 1):
        lines.append(f"  {i}. {w1} <-{conn_type}-> {w2}")

    lines.append("")
    lines.append("START: Present the first pair now.")

    return "\n".join(lines)


@handler("get_network_study_suggestions")
def handle_get_network_study_suggestions(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    """V11: Get study suggestions based on network connections."""
    from .word_network import WordNetwork, ensure_default_disambiguation

    network = WordNetwork()
    network.load()
    ensure_default_disambiguation(network)

    recently_reviewed = tool_input["recently_reviewed"]
    limit = tool_input.get("limit", 5)

    suggestions = network.get_network_suggestions(recently_reviewed, limit)

    if not suggestions:
        return (
            "No network-based suggestions available. "
            "The network needs more connections. Use update_word_network after adding cards."
        )

    lines = [
        f"Network-based study suggestions ({len(suggestions)}):",
        "",
        "These words are connected to your recently reviewed words:",
        "",
    ]

    for i, word in enumerate(suggestions, 1):
        node = network.get_node(word)
        level = node.level if node else "?"
        theme = node.theme if node else "?"
        connected_to = []
        for reviewed in recently_reviewed:
            reviewed_node = network.get_node(reviewed)
            if reviewed_node:
                for conn in reviewed_node.connections:
                    if conn.target_word == word:
                        connected_to.append(f"{reviewed} ({conn.connection_type})")
                        break
        conn_str = ", ".join(connected_to[:3]) if connected_to else "network"
        lines.append(f"  {i}. {word} [{level}] ({theme}) -- via {conn_str}")

    lines.append("")
    lines.append("Study these to reinforce your vocabulary network.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Vocab staging list
# ---------------------------------------------------------------------------

def _load_vocab_list() -> list[dict]:
    """Load the vocab staging list from disk."""
    from .paths import VOCAB_LIST_FILE, ensure_data_dir
    import json
    ensure_data_dir()
    if not VOCAB_LIST_FILE.exists():
        return []
    try:
        with open(VOCAB_LIST_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_vocab_list(items: list[dict]) -> None:
    """Save the vocab staging list to disk."""
    from .paths import VOCAB_LIST_FILE, ensure_data_dir, atomic_json_write
    ensure_data_dir()
    atomic_json_write(VOCAB_LIST_FILE, items)


@handler("add_to_vocab_list")
def handle_add_to_vocab_list(anki: "AnkiClient", tool_input: dict, **ctx) -> str:
    from datetime import datetime

    word = tool_input["word"].strip()
    english = tool_input["english"].strip()
    context = tool_input.get("context", "")
    level = tool_input.get("level", "")

    items = _load_vocab_list()

    # Check for duplicates
    for item in items:
        if item.get("word", "").lower() == word.lower():
            return f"'{word}' is already on your vocab list."

    items.append({
        "word": word,
        "english": english,
        "context": context,
        "level": level,
        "added": datetime.now().isoformat()[:10],
    })
    _save_vocab_list(items)
    return f"Added '{word}' ({english}) to your vocab list. You now have {len(items)} word(s) saved."


@handler("get_vocab_list")
def handle_get_vocab_list(anki: "AnkiClient", tool_input: dict, **ctx) -> str:
    items = _load_vocab_list()
    if not items:
        return "Your vocab list is empty. Words you save will appear here."

    lines = [f"Vocab list ({len(items)} words):", ""]
    for i, item in enumerate(items, 1):
        word = item.get("word", "?")
        english = item.get("english", "?")
        level = item.get("level", "")
        context = item.get("context", "")
        added = item.get("added", "")

        label = f"  {i}. {word} — {english}"
        if level:
            label += f" [{level}]"
        if context:
            label += f" ({context})"
        if added:
            label += f" [added {added}]"
        lines.append(label)

    lines.extend(["", "Use add_card to create Anki cards for any of these, then remove them from the list."])
    return "\n".join(lines)


@handler("remove_from_vocab_list")
def handle_remove_from_vocab_list(anki: "AnkiClient", tool_input: dict, **ctx) -> str:
    word = tool_input["word"].strip()
    items = _load_vocab_list()

    original_len = len(items)
    items = [item for item in items if item.get("word", "").lower() != word.lower()]

    if len(items) == original_len:
        return f"'{word}' was not found on your vocab list."

    _save_vocab_list(items)
    return f"Removed '{word}' from your vocab list. {len(items)} word(s) remaining."
