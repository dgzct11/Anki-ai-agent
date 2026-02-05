"""Sub-agent processor for parallel card transformations."""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
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
