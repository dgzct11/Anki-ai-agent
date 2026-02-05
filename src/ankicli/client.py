"""AnkiConnect client for interacting with Anki desktop."""

import json
import urllib.request
from typing import Any

from .models import Card, Deck, NoteType

ANKI_CONNECT_URL = "http://localhost:8765"


class AnkiConnectError(Exception):
    """Base exception for AnkiConnect errors."""
    pass


class ConnectionError(AnkiConnectError):
    """Could not connect to AnkiConnect."""
    pass


def _request(action: str, **params) -> Any:
    """Make a request to AnkiConnect."""
    payload = json.dumps({
        "action": action,
        "version": 6,
        "params": params
    }).encode("utf-8")

    try:
        req = urllib.request.Request(ANKI_CONNECT_URL, payload)
        req.add_header("Content-Type", "application/json")
        response = urllib.request.urlopen(req, timeout=10)
        result = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise ConnectionError(
            "Cannot connect to Anki. Make sure Anki is running with AnkiConnect installed."
        ) from e

    if result.get("error"):
        raise AnkiConnectError(result["error"])

    return result.get("result")


def _format_interval(days: float) -> str:
    """Format a day count as a human-readable interval string."""
    if days < 0:
        seconds = abs(days)
        if seconds < 60:
            return "<1 min"
        return f"{int(seconds / 60)} min"
    elif days < 1.0 / 24 / 60:
        return "<1 min"
    elif days < 1.0 / 24:
        minutes = max(1, int(days * 24 * 60))
        return f"{minutes} min"
    elif days < 1:
        hours = max(1, round(days * 24))
        return f"{hours} hour{'s' if hours != 1 else ''}"
    elif days < 30:
        d = max(1, round(days))
        return f"{d} day{'s' if d != 1 else ''}"
    elif days < 365:
        m = max(1, round(days / 30))
        return f"{m} month{'s' if m != 1 else ''}"
    else:
        y = round(days / 365, 1)
        return f"{y} year{'s' if y != 1 else ''}"


class AnkiClient:
    """Client for interacting with Anki via AnkiConnect."""

    def ping(self) -> bool:
        """Check if AnkiConnect is available."""
        try:
            result = _request("version")
            return result is not None
        except Exception:
            return False

    def get_decks(self) -> list[Deck]:
        """Fetch all decks from Anki."""
        deck_names = _request("deckNames")
        decks = []

        for name in deck_names:
            # Get deck stats
            try:
                stats = _request("getDeckStats", decks=[name])
                stat = stats.get(str(list(stats.keys())[0]), {}) if stats else {}
                decks.append(Deck(
                    id=str(stat.get("deck_id", name)),
                    name=name,
                    new_count=stat.get("new_count", 0),
                    learn_count=stat.get("learn_count", 0),
                    review_count=stat.get("review_count", 0),
                ))
            except Exception:
                decks.append(Deck(id=name, name=name))

        return decks

    def get_note_types(self) -> list[NoteType]:
        """Fetch available note types (models)."""
        model_names = _request("modelNames")
        note_types = []

        for name in model_names:
            try:
                fields = _request("modelFieldNames", modelName=name)
                note_types.append(NoteType(
                    id=name,
                    name=name,
                    fields=fields or []
                ))
            except Exception:
                note_types.append(NoteType(id=name, name=name))

        return note_types

    def add_card(
        self,
        deck_name: str,
        front: str,
        back: str,
        tags: list[str] | None = None,
        note_type: str = "Basic",
    ) -> int:
        """
        Add a new card to a deck.

        Returns:
            The note ID of the created card
        """
        note = {
            "deckName": deck_name,
            "modelName": note_type,
            "fields": {
                "Front": front,
                "Back": back,
            },
            "tags": tags or [],
            "options": {
                "allowDuplicate": False,
            },
        }

        note_id = _request("addNote", note=note)
        return note_id

    def add_cards(
        self,
        deck_name: str,
        cards: list[dict],
        note_type: str = "Basic",
    ) -> list[int]:
        """
        Add multiple cards at once.

        Args:
            deck_name: Target deck
            cards: List of dicts with 'front', 'back', and optional 'tags'
            note_type: Note type to use

        Returns:
            List of note IDs
        """
        notes = []
        for card in cards:
            notes.append({
                "deckName": deck_name,
                "modelName": note_type,
                "fields": {
                    "Front": card["front"],
                    "Back": card["back"],
                },
                "tags": card.get("tags", []),
            })

        result = _request("addNotes", notes=notes)
        return result

    def search_cards(self, query: str, limit: int = 50) -> list[Card]:
        """
        Search for cards using Anki's search syntax.

        Args:
            query: Search query (e.g., 'deck:MyDeck', 'tag:mytag')
            limit: Maximum results to return
        """
        note_ids = _request("findNotes", query=query)

        if not note_ids:
            return []

        # Limit results
        note_ids = note_ids[:limit]

        # Get note info
        notes_info = _request("notesInfo", notes=note_ids)

        cards = []
        for note in notes_info:
            fields = note.get("fields", {})
            front = fields.get("Front", {}).get("value", "")
            back = fields.get("Back", {}).get("value", "")

            cards.append(Card(
                id=str(note.get("noteId", "")),
                front=front,
                back=back,
                deck_id="",
                tags=note.get("tags", []),
            ))

        return cards

    def get_deck_cards(self, deck_name: str, limit: int = 100) -> list[Card]:
        """Get all cards in a deck."""
        return self.search_cards(f'deck:"{deck_name}"', limit=limit)

    def sync(self) -> None:
        """Trigger a sync with AnkiWeb."""
        _request("sync")

    def create_deck(self, name: str) -> int:
        """Create a new deck."""
        return _request("createDeck", deck=name)

    def update_note(
        self,
        note_id: int,
        front: str | None = None,
        back: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """
        Update an existing note's fields and/or tags.

        Args:
            note_id: The note ID to update
            front: New front content (None to keep existing)
            back: New back content (None to keep existing)
            tags: New tags (None to keep existing)
        """
        note_update: dict = {"id": note_id}

        if front is not None or back is not None:
            fields = {}
            if front is not None:
                fields["Front"] = front
            if back is not None:
                fields["Back"] = back
            note_update["fields"] = fields

        if tags is not None:
            note_update["tags"] = tags

        _request("updateNote", note=note_update)

    def update_notes(self, updates: list[dict]) -> list[bool]:
        """
        Update multiple notes at once.

        Args:
            updates: List of dicts with 'note_id' and optional 'front', 'back', 'tags'

        Returns:
            List of success booleans
        """
        results = []
        for update in updates:
            try:
                self.update_note(
                    note_id=update["note_id"],
                    front=update.get("front"),
                    back=update.get("back"),
                    tags=update.get("tags"),
                )
                results.append(True)
            except Exception:
                results.append(False)
        return results

    def delete_notes(self, note_ids: list[int]) -> None:
        """
        Delete notes by their IDs.

        Args:
            note_ids: List of note IDs to delete
        """
        _request("deleteNotes", notes=note_ids)

    def delete_note(self, note_id: int) -> None:
        """Delete a single note by ID."""
        self.delete_notes([note_id])

    def get_note(self, note_id: int) -> Card | None:
        """Get a single note by ID."""
        notes_info = _request("notesInfo", notes=[note_id])
        if not notes_info:
            return None

        note = notes_info[0]
        fields = note.get("fields", {})
        return Card(
            id=str(note.get("noteId", "")),
            front=fields.get("Front", {}).get("value", ""),
            back=fields.get("Back", {}).get("value", ""),
            deck_id="",
            tags=note.get("tags", []),
        )

    def move_cards_to_deck(self, card_ids: list[int], deck_name: str) -> None:
        """Move cards to a different deck."""
        _request("changeDeck", cards=card_ids, deck=deck_name)

    def add_tags(self, note_ids: list[int], tags: str) -> None:
        """Add tags to notes (space-separated tag string)."""
        _request("addTags", notes=note_ids, tags=tags)

    def remove_tags(self, note_ids: list[int], tags: str) -> None:
        """Remove tags from notes (space-separated tag string)."""
        _request("removeTags", notes=note_ids, tags=tags)

    def find_and_replace(
        self,
        note_ids: list[int],
        field: str,
        search: str,
        replace: str,
        regex: bool = False,
    ) -> int:
        """
        Find and replace text in a field across multiple notes.

        Returns:
            Number of notes modified
        """
        return _request(
            "findAndReplaceInModels" if regex else "findAndReplaceInModels",
            notes=note_ids,
            field=field,
            find=search,
            replace=replace,
            regex=regex,
        )

    def get_deck_stats(self, deck_name: str) -> dict:
        """
        Get detailed statistics for a deck.

        Returns:
            Dict with total_cards, new_count, learn_count, review_count, etc.
        """
        stats = _request("getDeckStats", decks=[deck_name])
        if not stats:
            return {}
        # Get the first (and only) deck's stats
        deck_id = list(stats.keys())[0]
        stat = stats[deck_id]
        return {
            "deck_id": stat.get("deck_id"),
            "name": stat.get("name", deck_name),
            "total_cards": stat.get("total_in_deck", 0),
            "new_count": stat.get("new_count", 0),
            "learn_count": stat.get("learn_count", 0),
            "review_count": stat.get("review_count", 0),
        }

    def get_all_fronts(self, deck_name: str, limit: int = 500) -> list[str]:
        """
        Get just the front text of all cards in a deck.

        Returns:
            List of front text strings
        """
        cards = self.search_cards(f'deck:"{deck_name}"', limit=limit)
        return [c.front for c in cards]

    def get_deck_summary(self, deck_name: str, limit: int = 100) -> dict:
        """
        Get a comprehensive summary of a deck.

        Returns:
            Dict with stats and sample cards
        """
        stats = self.get_deck_stats(deck_name)
        cards = self.search_cards(f'deck:"{deck_name}"', limit=limit)

        # Collect unique tags
        all_tags = set()
        for card in cards:
            all_tags.update(card.tags)

        return {
            **stats,
            "sample_cards": cards[:20],
            "all_tags": sorted(all_tags),
            "cards_fetched": len(cards),
        }

    def get_due_cards(self, deck_name: str, limit: int = 50) -> list[Card]:
        """Get cards that are due for review in a deck."""
        return self.search_cards(f'deck:"{deck_name}" is:due', limit=limit)

    def get_new_cards(self, deck_name: str, limit: int = 50) -> list[Card]:
        """Get new (unseen) cards in a deck."""
        return self.search_cards(f'deck:"{deck_name}" is:new', limit=limit)

    def get_next_intervals(self, card_id: int) -> dict[str, str]:
        """Estimate the next review intervals for each ease button.

        Uses cardsInfo to get current interval and ease factor, then
        estimates what each button would do. Matches Anki's actual
        scheduling behavior as closely as possible.

        Args:
            card_id: The card/note ID.

        Returns:
            Dict with keys "again", "hard", "good", "easy" mapping to
            human-readable interval strings like "10 min", "2 days", etc.
        """
        card_ids = _request("findCards", query=f"nid:{card_id}")
        if not card_ids:
            return {"again": "?", "hard": "?", "good": "?", "easy": "?"}

        try:
            cards_info = _request("cardsInfo", cards=[card_ids[0]])
            if not cards_info:
                return {"again": "?", "hard": "?", "good": "?", "easy": "?"}
            info = cards_info[0]
        except (AnkiConnectError, IndexError):
            return {"again": "?", "hard": "?", "good": "?", "easy": "?"}

        interval = info.get("interval", 0)  # current interval in days (negative = seconds)
        factor = info.get("factor", 2500) / 1000  # ease factor (e.g., 2.5)
        card_type = info.get("type", 0)  # 0=new, 1=learning, 2=review, 3=relearn

        if card_type in (0, 1, 3):  # new, learning, or relearning
            return {
                "again": "<1 min",
                "hard": "6 min",
                "good": "10 min",
                "easy": "4 days",
            }

        # Review card: estimate based on current interval and ease factor
        # Again: card lapses -> enters relearning (steps are in minutes, not days)
        # Anki default relearn steps: [10 min]. The "new interval" after lapse
        # is typically 0% of original (configurable), so the card restarts.
        # The immediate next review is the first relearn step.
        again_str = "10 min"

        # Hard: interval * 1.2 (but at least current interval)
        hard_ivl = max(1, interval * 1.2)

        # Good: interval * ease_factor
        good_ivl = max(1, interval * factor)

        # Easy: interval * ease_factor * easy_bonus (default 1.3)
        easy_ivl = max(1, interval * factor * 1.3)

        return {
            "again": again_str,
            "hard": _format_interval(hard_ivl),
            "good": _format_interval(good_ivl),
            "easy": _format_interval(easy_ivl),
        }

    def answer_card(self, card_id: int, ease: int) -> bool:
        """Mark a card as reviewed in Anki with the given ease rating.

        Tries answerCards first (full SRS update, but only works if the card
        is at the top of Anki's review queue). Falls back to setDueDate with
        '!' suffix which reschedules the card with an appropriate interval.

        setDueDate limitations vs answerCards:
        - Creates a "Manual" revlog entry (type 4) instead of a proper review
        - Does not update ease factor or FSRS stability/difficulty
        - For learning cards, graduates them directly to review
        These tradeoffs are acceptable for CLI practice review marking.

        Args:
            card_id: The note ID to answer. Will find associated card IDs.
            ease: Ease rating (1=Again, 2=Hard, 3=Good, 4=Easy).

        Returns:
            True if successful, False if failed.
        """
        # Find actual card IDs for this note
        card_ids = _request("findCards", query=f"nid:{card_id}")
        if not card_ids:
            return False

        # Try answerCards first — full SRS update but requires card in reviewer
        for cid in card_ids:
            try:
                result = _request("answerCards", answers=[{"cardId": cid, "ease": ease}])
                if isinstance(result, list) and result and result[0] is True:
                    return True
            except AnkiConnectError:
                pass

        # Fallback: setDueDate with '!' suffix
        # This reschedules the card and creates a Manual revlog entry.
        # Get current card info to compute appropriate interval
        try:
            cards_info = _request("cardsInfo", cards=[card_ids[0]])
            info = cards_info[0] if cards_info else {}
        except (AnkiConnectError, IndexError):
            info = {}

        interval = info.get("interval", 0)
        factor = info.get("factor", 2500) / 1000
        card_type = info.get("type", 0)  # 0=new, 1=learning, 2=review, 3=relearn

        # Again (1): due today for review cards, skip for learning
        if ease == 1:
            due_days = 0
        elif card_type in (0, 1, 3):
            # New/learning: graduate with appropriate interval
            due_days = {2: 1, 3: 1, 4: 4}.get(ease, 1)
        else:
            # Review card: compute from current interval and ease factor
            if ease == 2:
                due_days = max(1, round(interval * 1.2))
            elif ease == 3:
                due_days = max(1, round(interval * factor))
            else:
                due_days = max(1, round(interval * factor * 1.3))

        try:
            _request("setDueDate", cards=card_ids, days=f"{due_days}!")
            return True
        except AnkiConnectError:
            return False

    def get_card_reviews(self, deck_name: str | None = None) -> list[dict]:
        """
        Get review history for cards via AnkiConnect.

        Uses cardReviews or getReviewsOfCards to pull review data.
        Falls back to estimating from card intervals if review API unavailable.

        Args:
            deck_name: Optional deck to filter by.

        Returns:
            List of review dicts with card_id, ease, interval, etc.
        """
        query = f'deck:"{deck_name}"' if deck_name else "*"
        card_ids = _request("findCards", query=query)
        if not card_ids:
            return []

        reviews = []
        # Try to get review data via cardsInfo which has interval/ease/due info
        try:
            cards_info = _request("cardsInfo", cards=card_ids[:500])
            for info in (cards_info or []):
                reviews.append({
                    "card_id": info.get("cardId"),
                    "note_id": info.get("note"),
                    "interval": info.get("interval", 0),
                    "ease": info.get("factor", 0),
                    "due": info.get("due", 0),
                    "type": info.get("type", 0),  # 0=new, 1=learning, 2=review, 3=relearn
                    "queue": info.get("queue", 0),
                    "reps": info.get("reps", 0),
                    "lapses": info.get("lapses", 0),
                })
        except AnkiConnectError:
            pass

        return reviews

    def get_collection_stats(self) -> dict:
        """
        Get overall collection statistics including retention data.

        Returns:
            Dict with total decks, cards, mature/learning/new counts,
            retention rate, etc.
        """
        decks = self.get_decks()
        total_new = sum(d.new_count for d in decks)
        total_learn = sum(d.learn_count for d in decks)
        total_review = sum(d.review_count for d in decks)

        # Get total cards count
        all_notes = _request("findNotes", query="*")

        # Get card-level stats for retention calculation
        all_cards = _request("findCards", query="*")
        mature_count = 0
        learning_count = 0
        new_count = 0
        total_reps = 0
        total_lapses = 0

        if all_cards:
            try:
                cards_info = _request("cardsInfo", cards=all_cards[:2000])
                for info in (cards_info or []):
                    card_type = info.get("type", 0)
                    interval = info.get("interval", 0)
                    reps = info.get("reps", 0)
                    lapses = info.get("lapses", 0)
                    total_reps += reps
                    total_lapses += lapses

                    if card_type == 0:
                        new_count += 1
                    elif interval >= 21:
                        mature_count += 1
                    else:
                        learning_count += 1
            except AnkiConnectError:
                # Fall back to deck-level stats
                new_count = total_new
                learning_count = total_learn

        # Retention rate: (reps - lapses) / reps * 100
        retention_rate = 0.0
        if total_reps > 0:
            retention_rate = ((total_reps - total_lapses) / total_reps) * 100

        return {
            "total_decks": len(decks),
            "total_notes": len(all_notes) if all_notes else 0,
            "total_cards": len(all_cards) if all_cards else 0,
            "total_new": total_new,
            "total_learning": total_learn,
            "total_review": total_review,
            "total_due": total_new + total_learn + total_review,
            "mature_count": mature_count,
            "learning_count": learning_count,
            "new_count": new_count,
            "total_reps": total_reps,
            "total_lapses": total_lapses,
            "retention_rate": round(retention_rate, 1),
            "decks": [{"name": d.name, "due": d.total_due} for d in decks],
        }
