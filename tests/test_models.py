"""Tests for data models."""

from ankicli.models import Card, Deck, NoteType


def test_deck_total_due():
    """Test Deck.total_due property."""
    deck = Deck(
        id="123",
        name="Test Deck",
        new_count=5,
        learn_count=3,
        review_count=10,
    )
    assert deck.total_due == 18


def test_deck_default_counts():
    """Test Deck with default counts."""
    deck = Deck(id="123", name="Test Deck")
    assert deck.new_count == 0
    assert deck.learn_count == 0
    assert deck.review_count == 0
    assert deck.total_due == 0


def test_card_creation():
    """Test Card creation."""
    card = Card(
        id="456",
        front="Hello",
        back="World",
        deck_id="123",
        tags=["tag1", "tag2"],
    )
    assert card.id == "456"
    assert card.front == "Hello"
    assert card.back == "World"
    assert card.deck_id == "123"
    assert card.tags == ["tag1", "tag2"]


def test_card_default_tags():
    """Test Card with default tags."""
    card = Card(id="456", front="Hello", back="World", deck_id="123")
    assert card.tags == []


def test_note_type_creation():
    """Test NoteType creation."""
    note_type = NoteType(
        id="789",
        name="Basic",
        fields=["Front", "Back"],
    )
    assert note_type.id == "789"
    assert note_type.name == "Basic"
    assert note_type.fields == ["Front", "Back"]
