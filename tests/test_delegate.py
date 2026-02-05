"""Tests for delegate module - sub-agent card transformation processor."""

from unittest.mock import MagicMock, patch

from ankicli.delegate import (
    CardDelegateProcessor,
    CardTransformation,
    ProgressEvent,
    SUBAGENT_SYSTEM_PROMPT,
)
from ankicli.models import Card


class TestCardTransformation:
    """Tests for CardTransformation dataclass."""

    def test_defaults(self):
        card = Card(id="1", front="hello", back="hola", deck_id="d1")
        ct = CardTransformation(
            note_id="1",
            original=card,
            transformed_front="Hello!",
            transformed_back=None,
            transformed_tags=None,
        )
        assert ct.error is None
        assert ct.changed is False
        assert ct.reasoning is None

    def test_with_error(self):
        card = Card(id="1", front="hello", back="hola", deck_id="d1")
        ct = CardTransformation(
            note_id="1",
            original=card,
            transformed_front=None,
            transformed_back=None,
            transformed_tags=None,
            error="API error",
        )
        assert ct.error == "API error"

    def test_with_changes(self):
        card = Card(id="1", front="hello", back="hola", deck_id="d1")
        ct = CardTransformation(
            note_id="1",
            original=card,
            transformed_front="Hello!",
            transformed_back="<b>hola</b>",
            transformed_tags=["spanish", "a1"],
            changed=True,
            reasoning="Added formatting",
        )
        assert ct.changed is True
        assert ct.reasoning == "Added formatting"
        assert ct.transformed_tags == ["spanish", "a1"]


class TestProgressEvent:
    """Tests for ProgressEvent dataclass."""

    def test_success(self):
        event = ProgressEvent(
            completed=3, total=10,
            current_card="hello",
            success=True,
        )
        assert event.completed == 3
        assert event.total == 10
        assert event.success is True
        assert event.error is None

    def test_failure(self):
        event = ProgressEvent(
            completed=5, total=10,
            current_card="goodbye",
            success=False,
            error="Timeout",
        )
        assert event.success is False
        assert event.error == "Timeout"


class TestSubagentSystemPrompt:
    """Tests for SUBAGENT_SYSTEM_PROMPT."""

    def test_contains_json_format(self):
        assert "JSON" in SUBAGENT_SYSTEM_PROMPT

    def test_contains_expected_fields(self):
        assert "front" in SUBAGENT_SYSTEM_PROMPT
        assert "back" in SUBAGENT_SYSTEM_PROMPT
        assert "tags" in SUBAGENT_SYSTEM_PROMPT
        assert "reasoning" in SUBAGENT_SYSTEM_PROMPT


class TestCardDelegateProcessor:
    """Tests for CardDelegateProcessor."""

    def test_max_workers_capped(self):
        client = MagicMock()
        processor = CardDelegateProcessor(client, "model", max_workers=20)
        assert processor.max_workers == 10

    def test_max_workers_normal(self):
        client = MagicMock()
        processor = CardDelegateProcessor(client, "model", max_workers=3)
        assert processor.max_workers == 3

    def test_process_single_card_success(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text='{"front": "Hello!", "back": null, "tags": null, "reasoning": "Capitalized"}')]
        client.messages.create.return_value = response

        processor = CardDelegateProcessor(client, "test-model", rate_limit_delay=0)
        card = Card(id="1", front="hello", back="hola", deck_id="d1")
        result = processor._process_single_card(card, "Capitalize the front")

        assert result.note_id == "1"
        assert result.transformed_front == "Hello!"
        assert result.transformed_back is None
        assert result.transformed_tags is None
        assert result.changed is True
        assert result.error is None

    def test_process_single_card_no_changes(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text='{"front": null, "back": null, "tags": null, "reasoning": "No changes needed"}')]
        client.messages.create.return_value = response

        processor = CardDelegateProcessor(client, "test-model", rate_limit_delay=0)
        card = Card(id="1", front="hello", back="hola", deck_id="d1")
        result = processor._process_single_card(card, "Fix any errors")

        assert result.changed is False

    def test_process_single_card_markdown_wrapped(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text='```json\n{"front": "Hello!", "back": null, "tags": null, "reasoning": "test"}\n```')]
        client.messages.create.return_value = response

        processor = CardDelegateProcessor(client, "test-model", rate_limit_delay=0)
        card = Card(id="1", front="hello", back="hola", deck_id="d1")
        result = processor._process_single_card(card, "Capitalize")

        assert result.transformed_front == "Hello!"
        assert result.error is None

    def test_process_single_card_invalid_json(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text="not json at all")]
        client.messages.create.return_value = response

        processor = CardDelegateProcessor(client, "test-model", rate_limit_delay=0)
        card = Card(id="1", front="hello", back="hola", deck_id="d1")
        result = processor._process_single_card(card, "Fix")

        assert result.error is not None
        assert "Invalid JSON" in result.error

    def test_process_single_card_api_error(self):
        client = MagicMock()
        client.messages.create.side_effect = Exception("Rate limit exceeded")

        processor = CardDelegateProcessor(client, "test-model", rate_limit_delay=0)
        card = Card(id="1", front="hello", back="hola", deck_id="d1")
        result = processor._process_single_card(card, "Fix")

        assert result.error == "Rate limit exceeded"

    def test_process_cards_empty(self):
        client = MagicMock()
        processor = CardDelegateProcessor(client, "test-model", rate_limit_delay=0)
        results = processor.process_cards([], "Fix")
        assert results == []

    def test_process_cards_with_progress(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text='{"front": null, "back": null, "tags": null, "reasoning": "ok"}')]
        client.messages.create.return_value = response

        processor = CardDelegateProcessor(client, "test-model", max_workers=1, rate_limit_delay=0)
        cards = [
            Card(id="1", front="hello", back="hola", deck_id="d1"),
            Card(id="2", front="goodbye", back="adios", deck_id="d1"),
        ]

        progress_events = []
        def on_progress(event: ProgressEvent):
            progress_events.append(event)

        results = processor.process_cards(cards, "Fix", progress_callback=on_progress)

        assert len(results) == 2
        assert len(progress_events) == 2
        assert all(e.success for e in progress_events)
        # All should report total=2
        assert all(e.total == 2 for e in progress_events)

    def test_process_cards_handles_exceptions(self):
        client = MagicMock()
        client.messages.create.side_effect = Exception("Network error")

        processor = CardDelegateProcessor(client, "test-model", max_workers=1, rate_limit_delay=0)
        cards = [Card(id="1", front="hello", back="hola", deck_id="d1")]

        results = processor.process_cards(cards, "Fix")
        assert len(results) == 1
        assert results[0].error is not None
