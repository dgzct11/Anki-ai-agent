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
    return f"Added {successful}/{len(cards)} cards successfully{cefr_info}"


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
    word = tool_input["word"]
    deck_name = tool_input.get("deck_name")

    query = f"*{word}*"
    if deck_name:
        query = f'deck:"{deck_name}" {query}'

    cards = anki.search_cards(query, limit=10)

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
        query = f"*{word}*"
        if deck_name:
            query = f'deck:"{deck_name}" {query}'

        cards = anki.search_cards(query, limit=1)
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


@handler("find_card_by_word")
def handle_find_card_by_word(anki: AnkiClient, tool_input: dict, **ctx) -> str:
    word = tool_input["word"].lower().strip()
    deck_name = tool_input.get("deck_name")

    tag = f"word::{word}"
    query = f'tag:"{tag}"'
    if deck_name:
        query = f'deck:"{deck_name}" {query}'

    cards = anki.search_cards(query, limit=5)

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
        tag = f"word::{word}"
        query = f'tag:"{tag}"'
        if deck_name:
            query = f'deck:"{deck_name}" {query}'

        cards = anki.search_cards(query, limit=1)
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
        "- If the word is due for Anki review, ASK the user if they want to mark it reviewed",
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
    count = min(tool_input.get("count", 5), 10)
    question_types = tool_input.get("question_types")

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

    mastered_str = "MASTERED" if mastery["mastered"] else "not yet mastered"
    lines = [
        f"Quiz results logged for '{topic}' ({level}):",
        f"  Score: {correct}/{attempted} ({score:.0f}%)",
        f"  Status: {mastered_str} (avg: {mastery['avg_score']:.0f}%, threshold: {MASTERY_THRESHOLD:.0f}%)",
        f"  Total quizzes on this topic: {mastery['quizzed_count']}",
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
        "- If any vocabulary from the conversation matches due Anki cards, ASK the user if they want to mark them reviewed.",
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
    from .paths import DAILY_CHALLENGE_FILE, ensure_data_dir
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
        level_data = progress.get(level_key, {})
        unknown = level_data.get("unknown_words", [])
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
    with open(DAILY_CHALLENGE_FILE, "w") as f:
        _json.dump(state, f, indent=2, ensure_ascii=False)

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
                pct = level_data.get("percent", 0)
                if pct < 90 and pct < weakest_pct:
                    weakest_level = level_key
                    weakest_pct = pct

            if weakest_level:
                level_data = progress[weakest_level]
                lines.append(f"\nCEFR focus: {weakest_level} ({weakest_pct:.0f}% complete)")

                # Find weakest category
                cats = level_data.get("categories", {})
                if cats:
                    weakest_cat = min(cats.items(), key=lambda x: x[1].get("percent", 0))
                    lines.append(f"Weakest category: {weakest_cat[0]} ({weakest_cat[1].get('percent', 0):.0f}%)")
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
