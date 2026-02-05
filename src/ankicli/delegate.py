"""Sub-agent processor for parallel card transformations and batch operations."""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from anthropic import Anthropic

from .models import Card


@dataclass
class CardTransformation:
    """Result of transforming a single card."""

    note_id: str
    original: Card
    transformed_front: str | None
    transformed_back: str | None
    transformed_tags: list[str] | None
    error: str | None = None
    changed: bool = False
    reasoning: str | None = None


@dataclass
class ProgressEvent:
    """Progress update during card processing."""

    completed: int
    total: int
    current_card: str
    success: bool
    error: str | None = None


SUBAGENT_SYSTEM_PROMPT = """You are a flashcard transformation assistant. You receive a flashcard and instructions for how to transform it.

IMPORTANT: Respond ONLY with valid JSON in this exact format:
{
    "front": "new front content or null if unchanged",
    "back": "new back content or null if unchanged",
    "tags": ["list", "of", "tags"] or null if unchanged,
    "reasoning": "brief explanation of what you changed"
}

Guidelines:
- Use HTML formatting: <b>bold</b>, <i>italic</i>, <br> for line breaks
- Set a field to null if you are NOT changing it
- Only make changes that are directly requested
- Be conservative - don't change things unless needed"""


class CardDelegateProcessor:
    """Processes cards in parallel using Claude sub-agents."""

    def __init__(
        self,
        client: Anthropic,
        model: str,
        max_workers: int = 5,
        rate_limit_delay: float = 0.1,
    ):
        """
        Initialize the processor.

        Args:
            client: Anthropic client instance
            model: Model to use for sub-agents
            max_workers: Maximum parallel workers (capped at 10)
            rate_limit_delay: Delay between API calls in seconds
        """
        self.client = client
        self.model = model
        self.max_workers = min(max_workers, 10)  # Cap at 10
        self.rate_limit_delay = rate_limit_delay

    def _process_single_card(
        self, card: Card, prompt: str
    ) -> CardTransformation:
        """Process a single card with the sub-agent."""
        user_message = f"""Transform this flashcard according to the instructions.

CARD:
- Note ID: {card.id}
- Front: {card.front}
- Back: {card.back}
- Tags: {', '.join(card.tags) if card.tags else 'none'}

INSTRUCTIONS:
{prompt}

Respond with JSON only."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=SUBAGENT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )

            # Extract response text
            response_text = response.content[0].text.strip()

            # Parse JSON response
            # Handle potential markdown code blocks
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                # Remove first and last lines (```json and ```)
                response_text = "\n".join(lines[1:-1])

            result = json.loads(response_text)

            # Determine if anything changed
            front_changed = result.get("front") is not None
            back_changed = result.get("back") is not None
            tags_changed = result.get("tags") is not None
            changed = front_changed or back_changed or tags_changed

            return CardTransformation(
                note_id=card.id,
                original=card,
                transformed_front=result.get("front"),
                transformed_back=result.get("back"),
                transformed_tags=result.get("tags"),
                changed=changed,
                reasoning=result.get("reasoning"),
            )

        except json.JSONDecodeError as e:
            return CardTransformation(
                note_id=card.id,
                original=card,
                transformed_front=None,
                transformed_back=None,
                transformed_tags=None,
                error=f"Invalid JSON response: {e}",
            )
        except Exception as e:
            return CardTransformation(
                note_id=card.id,
                original=card,
                transformed_front=None,
                transformed_back=None,
                transformed_tags=None,
                error=str(e),
            )

    def process_cards(
        self,
        cards: list[Card],
        prompt: str,
        progress_callback: Callable[[ProgressEvent], None] | None = None,
    ) -> list[CardTransformation]:
        """
        Process cards in parallel with ThreadPoolExecutor.

        Args:
            cards: List of cards to process
            prompt: Instructions for transforming each card
            progress_callback: Optional callback for progress updates

        Returns:
            List of CardTransformation results
        """
        results: list[CardTransformation] = []
        total = len(cards)
        completed = 0

        def process_with_delay(card: Card) -> CardTransformation:
            """Process a card with rate limiting."""
            time.sleep(self.rate_limit_delay)
            return self._process_single_card(card, prompt)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_card = {
                executor.submit(process_with_delay, card): card
                for card in cards
            }

            # Collect results as they complete
            for future in as_completed(future_to_card):
                card = future_to_card[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1

                    if progress_callback:
                        progress_callback(
                            ProgressEvent(
                                completed=completed,
                                total=total,
                                current_card=card.front[:50],
                                success=result.error is None,
                                error=result.error,
                            )
                        )
                except Exception as e:
                    # Handle unexpected errors
                    results.append(
                        CardTransformation(
                            note_id=card.id,
                            original=card,
                            transformed_front=None,
                            transformed_back=None,
                            transformed_tags=None,
                            error=f"Unexpected error: {e}",
                        )
                    )
                    completed += 1

                    if progress_callback:
                        progress_callback(
                            ProgressEvent(
                                completed=completed,
                                total=total,
                                current_card=card.front[:50],
                                success=False,
                                error=str(e),
                            )
                        )

        return results


# ---------------------------------------------------------------------------
# Batch delegate: general-purpose parallel processing
# ---------------------------------------------------------------------------

# Built-in prompt templates for each delegate type.
BATCH_DELEGATE_PROMPTS: dict[str, str] = {
    "cognate_scan": (
        "Classify the following Spanish word by cognate type relative to English.\n\n"
        "Word: {item}\n\n"
        "Respond ONLY with valid JSON:\n"
        '{{"word": "{item}", "cognate_type": "perfect|near|false|none", '
        '"english_cognate": "the English cognate or empty string", '
        '"confidence": 0.0-1.0, "reasoning": "brief explanation"}}'
    ),
    "network_update": (
        "Generate word connections for the Spanish word below. "
        "List synonyms, antonyms, and semantically related words.\n\n"
        "Word: {item}\n\n"
        "Respond ONLY with valid JSON:\n"
        '{{"word": "{item}", "synonyms": ["..."], "antonyms": ["..."], '
        '"related": ["..."], "category": "theme category"}}'
    ),
    "difficulty_score": (
        "Rate the difficulty of this Spanish word for an English speaker learning Spanish.\n\n"
        "Word: {item}\n\n"
        "Consider: cognate similarity, pronunciation, irregularity, usage frequency, "
        "false-friend risk.\n\n"
        "Respond ONLY with valid JSON:\n"
        '{{"word": "{item}", "difficulty": 1-5, '
        '"factors": {{"cognate_ease": 1-5, "pronunciation": 1-5, "irregularity": 1-5, '
        '"frequency": 1-5}}, "reasoning": "brief explanation"}}'
    ),
    "context_generation": (
        "Generate 3 natural example sentences in Spanish using this word/phrase. "
        "Vary the tenses and include English translations.\n\n"
        "Word: {item}\n\n"
        "Respond ONLY with valid JSON:\n"
        '{{"word": "{item}", "sentences": ['
        '{{"spanish": "...", "english": "...", "tense": "..."}}]}}'
    ),
}


@dataclass
class BatchResult:
    """Result of processing a single item in a batch delegate."""

    item: str
    result: dict | None = None
    raw_response: str = ""
    error: str | None = None


@dataclass
class BatchProgressEvent:
    """Progress update during batch processing."""

    completed: int
    total: int
    current_item: str
    success: bool
    error: str | None = None


class BatchDelegateProcessor:
    """Processes a list of items in parallel using Claude sub-agents.

    Each item is formatted into a prompt template and sent to a sub-agent.
    Results are collected as parsed JSON.
    """

    def __init__(
        self,
        client: Anthropic,
        model: str,
        max_workers: int = 5,
        rate_limit_delay: float = 0.1,
    ):
        self.client = client
        self.model = model
        self.max_workers = min(max_workers, 10)
        self.rate_limit_delay = rate_limit_delay

    def _process_single_item(
        self, item: str, prompt_template: str
    ) -> BatchResult:
        """Process a single item with the sub-agent."""
        prompt = prompt_template.replace("{item}", item)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text.strip()

            # Strip markdown code fences if present
            text = raw
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])

            # Extract JSON object
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                parsed = json.loads(text[start : end + 1])
                return BatchResult(item=item, result=parsed, raw_response=raw)
            else:
                return BatchResult(
                    item=item, raw_response=raw,
                    error="No JSON object found in response",
                )

        except json.JSONDecodeError as e:
            return BatchResult(item=item, raw_response=raw, error=f"Invalid JSON: {e}")
        except Exception as e:
            return BatchResult(item=item, error=str(e))

    def process_batch(
        self,
        items: list[str],
        delegate_type: str,
        prompt_override: str | None = None,
        progress_callback: Callable[[BatchProgressEvent], None] | None = None,
    ) -> list[BatchResult]:
        """Process a batch of items in parallel.

        Args:
            items: List of items to process.
            delegate_type: One of the built-in delegate types.
            prompt_override: Custom prompt template (uses {item} placeholder).
            progress_callback: Optional callback for progress updates.

        Returns:
            List of BatchResult objects.
        """
        template = prompt_override or BATCH_DELEGATE_PROMPTS.get(delegate_type)
        if not template:
            return [
                BatchResult(item=it, error=f"Unknown delegate type: {delegate_type}")
                for it in items
            ]

        results: list[BatchResult] = []
        total = len(items)
        completed = 0

        def process_with_delay(item: str) -> BatchResult:
            time.sleep(self.rate_limit_delay)
            return self._process_single_item(item, template)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {
                executor.submit(process_with_delay, item): item
                for item in items
            }

            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1

                    if progress_callback:
                        progress_callback(
                            BatchProgressEvent(
                                completed=completed,
                                total=total,
                                current_item=item,
                                success=result.error is None,
                                error=result.error,
                            )
                        )
                except Exception as e:
                    results.append(BatchResult(item=item, error=f"Unexpected: {e}"))
                    completed += 1

                    if progress_callback:
                        progress_callback(
                            BatchProgressEvent(
                                completed=completed,
                                total=total,
                                current_item=item,
                                success=False,
                                error=str(e),
                            )
                        )

        return results
