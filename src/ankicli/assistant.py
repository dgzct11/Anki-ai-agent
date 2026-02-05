"""Claude assistant with Anki tool calling."""

import json
import os
import queue
import time
from pathlib import Path
from typing import Generator

from anthropic import Anthropic
from dotenv import load_dotenv

# Load .env file from current directory or project root
load_dotenv()
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from .client import AnkiClient, AnkiConnectError
from .config import load_config, save_config, get_model_specs, format_tool_notes_display
from .conversation_store import load_conversation, save_conversation
from .delegate import CardDelegateProcessor, ProgressEvent
from .learning_summary import load_summary, save_summary, format_summary_as_text
from .tool_handlers import HANDLERS
from .tools import ANKI_TOOLS

_CORE_IDENTITY = """You are an Anki flashcard assistant. You help users manage their Anki flashcard decks through conversation.

You can:
- List and browse decks
- Add new flashcards (single or bulk - use add_multiple_cards for efficiency)
- Edit existing cards (single or bulk)
- Delete cards
- Search cards and manage tags
- Move cards between decks
- Create new decks
- Sync with AnkiWeb"""

_CARD_FORMAT_GUIDE = """## Spanish Vocabulary Card Format

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
- • for bullet points"""

_GENERAL_GUIDELINES = """## General Guidelines

When creating flashcards:
- For bulk operations, use add_multiple_cards to add many cards at once (10, 20, 50+ cards)
- Before adding, use check_words_exist to avoid duplicates
- Suggest tags when relevant (e.g., "verb", "noun", "adjective", "irregular")

When editing cards:
- First search to find the cards and get their note IDs
- Use update_card for single edits or update_multiple_cards for bulk edits
- Always confirm before deleting cards

When the user wants to add cards, confirm the deck name first by listing available decks if needed.
Be helpful and proactive - if the user mentions a topic they're studying, offer to create relevant flashcards."""

_LEARNING_SUMMARY_GUIDE = """## Learning Summary (IMPORTANT)

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

When asked about progress or what to learn next, use get_learning_summary to review the current state."""

_CONTEXT_MANAGEMENT = """## Context Management

Monitor the context usage shown after each response. When context exceeds 50%, proactively use the compact_conversation tool to summarize older messages and free up space. This ensures the conversation can continue smoothly.

Keep responses concise and focused on the task at hand."""

_CEFR_GUIDE = """## CEFR Progress Tracking

You have access to CEFR (Common European Framework) vocabulary and grammar lists for Spanish (A1-C2).

Use these tools to give users concrete, data-driven progress:
- **get_cefr_progress**: Shows "142/500 A1 words known" with per-category breakdown
- **get_cefr_suggestions**: Suggests specific words to learn next based on gaps
- **sync_cefr_progress**: Full rescan of cards against CEFR lists (use after bulk changes)

When the user asks about progress, prefer get_cefr_progress over the older get_learning_summary for vocabulary metrics.

Auto-tagging: When cards are added with a word:: tag, CEFR level and theme tags (cefr::a1, theme::food_nutrition) are automatically added.

When suggesting what to learn next, use get_cefr_suggestions to give specific word recommendations from CEFR gaps."""

_PRACTICE_EVALUATION_GUIDE = """## Translation Practice Evaluation

When evaluating translations in practice mode (messages starting with [PRACTICE MODE]):

**Scoring Rubric (0-4 for each):**
- **Meaning** (0-4): 0=completely wrong, 1=major errors, 2=partially correct, 3=correct with minor issues, 4=perfect
- **Grammar** (0-4): 0=incomprehensible, 1=major grammar errors, 2=some errors, 3=minor errors, 4=grammatically perfect
- **Naturalness** (0-4): 0=not natural at all, 1=understandable but awkward, 2=somewhat natural, 3=mostly natural, 4=sounds native
- **Vocabulary** (0-4): 0=wrong words, 1=poor word choices, 2=acceptable, 3=good vocabulary, 4=excellent/precise

**Response Format:**
Always include scores in this format: Meaning: X/4, Grammar: X/4, Naturalness: X/4, Vocabulary: X/4

**Feedback Guidelines:**
- Be encouraging but honest
- If incorrect, show the correct translation
- Explain WHY something is wrong (grammar rule, vocabulary choice)
- For partial answers, highlight what was good AND what needs improvement
- Adapt complexity: if user gets 3+ right, use more complex phrases; if 2+ wrong, simplify and explain grammar

**CRITICAL: Anki Review Marking:**
When a card is marked as due for review, you MUST ask: "This word is due for Anki review. Mark as reviewed? (y/n)"
NEVER auto-mark cards. Always ask the user first."""

_ERROR_JOURNAL_GUIDE = """## Error Journal

You have access to a persistent error journal that tracks the user's recurring mistakes across practice and quiz sessions.

**When to log errors:**
- During translation practice: if the user makes a grammar mistake (gender agreement, verb form, preposition, etc.), call log_error
- During grammar quizzes: if the user gets a question wrong, log the specific error pattern
- During conversation simulations: if you correct a mistake, log it
- Use consistent error_type labels: gender_agreement, ser_vs_estar, accent_missing, verb_conjugation, word_order, preposition_choice, article_usage, subjunctive_needed, preterite_vs_imperfect, false_friend, spelling

**When to check errors:**
- At the start of practice/quiz sessions, call get_error_patterns to see what the user struggles with
- Use this to focus practice on weak areas
- Mention progress when a previously frequent error stops appearing

Do NOT over-log: only log genuine mistakes, not typos or one-off slips. Focus on patterns that appear 2+ times."""

_CONVERSATION_SIM_GUIDE = """## Conversation Simulation Mode

You can start role-play conversation simulations using start_conversation_sim. In conversation mode:

**Scenarios by CEFR level:**
- A2: ordering_food, asking_directions, hotel_checkin, shopping
- B1: job_interview, doctor_visit, phone_call, apartment_rental
- B2: debate, negotiation, complaint, storytelling

**During conversation (messages starting with [CONVERSATION MODE]):**
- Stay in character and speak Spanish (with parenthetical translations at A2)
- Keep responses to 2-4 sentences
- Gently correct mistakes in-character
- Call log_error for recurring mistake patterns
- After the conversation ends, summarize performance and offer to create Anki cards for new vocabulary
- If practiced words are due for Anki review, ASK the user before marking them

When the user asks to practice conversation or role-play, use start_conversation_sim."""

_DAILY_CHALLENGE_GUIDE = """## Word of the Day / Daily Challenge

At the start of each new session, call get_daily_challenge to offer the user a word of the day.
The challenge picks a word from their CEFR gap areas and provides:
1. The word with pronunciation tips
2. Example sentences
3. A quick translation exercise
4. An offer to create an Anki card

Keep it brief (2-3 minutes). Only present once per day unless the user asks for a new one.
If the user declines, move on without insisting."""

_STUDY_SUGGESTIONS_GUIDE = """## Smart Study Suggestions

Use get_study_suggestion to give personalized recommendations based on:
- Cards due today (review first before new material)
- Weakest CEFR level and category
- Recurring error patterns from the error journal
- Recent quiz performance

Call this at the start of a session or when the user asks "what should I study?" to provide data-driven advice."""

_VOCAB_NETWORK_GUIDE = """## Vocabulary Network

When the user adds a new word, use get_related_words to suggest semantically related words from CEFR lists.
This helps build vocabulary clusters rather than isolated words. Example:
- User adds "comprar" -> suggest "vender", "precio", "tienda", "dinero"
- User adds "hospital" -> suggest "medico", "enfermero", "paciente", "enfermedad"

Only suggest when relevant - don't overwhelm the user after every card addition."""

_CONTEXTUAL_SENTENCES_GUIDE = """## Contextual Sentence Generator

Use generate_contexts to create example sentences for a word in specific contexts:
- "conversation": casual spoken dialogue
- "formal": business/official communication
- "narrative": storytelling, literature
- "email": correspondence
- "academic": essays, reports

Use this when:
- Enriching an existing card with more examples
- The user wants to see a word used in different registers
- Creating cards that show real-world usage patterns"""

_TOOL_NOTES_GUIDE = """## User Preferences (Tool Notes)

You can save and manage user preferences using the set_tool_note, get_tool_notes, and remove_tool_note tools.

When the user expresses a preference about how cards should be created or how you should behave, proactively offer to save it as a tool note so it persists across sessions. Examples:
- "I prefer informal Spanish" -> offer to save as general note
- "Use 3 examples instead of 5" -> offer to save for add_card/add_multiple_cards
- "Always use Latin American Spanish" -> offer to save as general note
- "I don't need conjugation tables for adjectives" -> offer to save for card creation

Always check and follow any saved preferences when performing actions."""

_GRAMMAR_QUIZ_GUIDE = """## Grammar Quiz Mode

You can start grammar quizzes using the start_grammar_quiz tool. The quiz system:
- Generates questions dynamically based on CEFR level and grammar topic
- Supports 5 question types: fill-in-the-blank, multiple choice, conjugation table, error correction, sentence transformation
- Tracks mastery per topic (>85% = mastered)
- After a quiz, offers to create Anki cards for weak areas

When presenting quiz questions (messages starting with [QUIZ SESSION]):
- Present one question at a time in a clear format
- Do NOT reveal the answer until the user responds
- After each answer, provide grammar feedback with the rule explanation
- Use the log_quiz_results tool after the quiz ends to save results

When the user asks to practice grammar or take a quiz, use start_grammar_quiz.
Use get_learning_summary to check grammar gaps and recommend topics."""

# All prompt sections in order, for build_system_prompt to assemble.
_PROMPT_SECTIONS = [
    _CORE_IDENTITY,
    _CARD_FORMAT_GUIDE,
    _GENERAL_GUIDELINES,
    _LEARNING_SUMMARY_GUIDE,
    _CEFR_GUIDE,
    _PRACTICE_EVALUATION_GUIDE,
    _GRAMMAR_QUIZ_GUIDE,
    _CONVERSATION_SIM_GUIDE,
    _ERROR_JOURNAL_GUIDE,
    _DAILY_CHALLENGE_GUIDE,
    _STUDY_SUGGESTIONS_GUIDE,
    _VOCAB_NETWORK_GUIDE,
    _CONTEXTUAL_SENTENCES_GUIDE,
    _CONTEXT_MANAGEMENT,
    _TOOL_NOTES_GUIDE,
]


def build_system_prompt(*, general_note: str | None = None, extra_sections: list[str] | None = None) -> str:
    """Assemble the system prompt from composable sections.

    Args:
        general_note: User-set general preference note (injected at end).
        extra_sections: Additional prompt sections to append (e.g. CEFR guide).
    """
    sections = list(_PROMPT_SECTIONS)
    if extra_sections:
        sections.extend(extra_sections)
    prompt = "\n\n".join(sections)
    if general_note:
        prompt += f"\n\n## Active User Preferences\n\nIMPORTANT - The user has set these global preferences. Always follow them:\n{general_note}"
    return prompt


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
        # Session tracking
        self.session_start_time = time.time()
        self.session_cards_added = 0

    def _get_tools_with_notes(self) -> list[dict]:
        """Return tools list with user preference notes injected into descriptions."""
        tools = []
        for tool in ANKI_TOOLS:
            note = self.config.tool_notes.get(tool["name"])
            if note:
                tool_copy = {**tool}
                tool_copy["description"] = tool["description"] + f"\n\nUSER PREFERENCE: {note}"
                tools.append(tool_copy)
            else:
                tools.append(tool)
        return tools

    def _get_system_prompt(self) -> str:
        """Return system prompt with user preferences injected."""
        return build_system_prompt(
            general_note=self.config.tool_notes.get("general"),
        )

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
        elapsed = time.time() - self.session_start_time
        session_minutes = int(elapsed / 60)
        return {
            "input_tokens": self.input_tokens_used,
            "output_tokens": self.output_tokens_used,
            "total_tokens": self.total_tokens_used,
            "max_tokens": self.max_context_tokens,
            "percent_used": self.context_usage_percent,
            "model": self.model,
            "model_name": self.model_name,
            "session_minutes": session_minutes,
            "session_cards_added": self.session_cards_added,
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
            handler_fn = HANDLERS.get(tool_name)
            if handler_fn is None:
                return f"Unknown tool: {tool_name}"
            return handler_fn(
                self.anki,
                tool_input,
                config=self.config,
                assistant=self,
            )
        except AnkiConnectError as e:
            return f"Anki error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def _run_delegate(self, cards: list, prompt: str, source_label: str,
                      workers: int, dry_run: bool) -> str:
        """Run the delegate processor on a list of cards and return a summary.

        Shared implementation for both all_cards_delegate and card_subset_delegate.
        """
        processor = CardDelegateProcessor(
            client=self.client,
            model=self.config.subagent_model,
            max_workers=workers,
            rate_limit_delay=self.config.delegate_rate_limit_delay,
        )

        def progress_callback(event: ProgressEvent) -> None:
            self._progress_queue.put({
                "type": "delegate_progress",
                "completed": event.completed,
                "total": event.total,
                "current_card": event.current_card,
                "success": event.success,
                "error": event.error,
            })

        results = processor.process_cards(cards, prompt, progress_callback)

        changed = [r for r in results if r.changed]
        errors = [r for r in results if r.error]

        summary_parts = [
            f"Processed {len(results)} cards{source_label}",
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

    def _handle_all_cards_delegate(self, tool_input: dict) -> str:
        """Handle the all_cards_delegate tool."""
        deck_name = tool_input["deck_name"]
        limit = tool_input.get("limit")
        workers = min(tool_input.get("workers", self.config.delegate_max_workers), 10)

        cards = self.anki.get_deck_cards(deck_name, limit=limit or 1000)
        if not cards:
            return f"No cards found in deck '{deck_name}'"
        if limit:
            cards = cards[:limit]

        return self._run_delegate(
            cards, tool_input["prompt"], f" from '{deck_name}'",
            workers, tool_input.get("dry_run", False),
        )

    def _handle_card_subset_delegate(self, tool_input: dict) -> str:
        """Handle the card_subset_delegate tool."""
        workers = min(tool_input.get("workers", self.config.delegate_max_workers), 10)

        cards = []
        for note_id in tool_input["note_ids"]:
            card = self.anki.get_note(note_id)
            if card:
                cards.append(card)

        if not cards:
            return "No cards found for the given note IDs"

        return self._run_delegate(
            cards, tool_input["prompt"], "",
            workers, tool_input.get("dry_run", False),
        )

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
                    system=self._get_system_prompt(),
                    tools=self._get_tools_with_notes(),
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
