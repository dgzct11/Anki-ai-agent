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
        raw = response.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise ConnectionError(
            "Cannot connect to Anki. Make sure Anki is running with AnkiConnect installed."
        ) from e
    except TimeoutError as e:
        raise ConnectionError(
            "Anki is not responding (timed out after 10s). "
            "Check if Anki is frozen or busy syncing."
        ) from e

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AnkiConnectError(
            f"Invalid response from AnkiConnect for action '{action}': {raw[:200]}"
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
                if stats and stats.keys():
                    deck_id = next(iter(stats.keys()))
                    stat = stats[deck_id]
                else:
                    stat = {}
                decks.append(Deck(
                    id=str(stat.get("deck_id", name)),
                    name=name,
                    new_count=stat.get("new_count", 0),
                    learn_count=stat.get("learn_count", 0),
                    review_count=stat.get("review_count", 0),
                ))
            except AnkiConnectError:
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
            except AnkiConnectError:
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
                "options": {
                    "allowDuplicate": False,
                },
            })

        # addNotes returns note IDs (null for failures) in the result field,
        # but also sets the error field for duplicates. We need the result
        # even when there are errors, so bypass _request and parse manually.
        payload = json.dumps({
            "action": "addNotes",
            "version": 6,
            "params": {"notes": notes},
        }).encode("utf-8")

        try:
            req = urllib.request.Request(ANKI_CONNECT_URL, payload)
            req.add_header("Content-Type", "application/json")
            response = urllib.request.urlopen(req, timeout=10)
            raw = response.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise ConnectionError(
                "Cannot connect to Anki. Make sure Anki is running with AnkiConnect installed."
            ) from e

        parsed = json.loads(raw)
        result = parsed.get("result")

        # If we got a result list, return it (None entries = duplicates/failures)
        if isinstance(result, list):
            return result

        # No result at all — raise whatever error AnkiConnect reported
        error = parsed.get("error")
        if error:
            raise AnkiConnectError(error)

        return []

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

    def update_notes(self, updates: list[dict]) -> list[tuple[bool, str]]:
        """
        Update multiple notes at once.

        Args:
            updates: List of dicts with 'note_id' and optional 'front', 'back', 'tags'

        Returns:
            List of (success, message) tuples
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
                results.append((True, "OK"))
            except AnkiConnectError as e:
                results.append((False, str(e)))
            except Exception as e:
                results.append((False, f"Unexpected error: {e}"))
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
        if not note.get("noteId"):
            return None
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

    def get_next_intervals(self, note_id: int) -> dict[str, str]:
        """Estimate the next review intervals for each ease button.

        Uses cardsInfo to get current interval and ease factor, then
        estimates what each button would do. Matches Anki's actual
        scheduling behavior as closely as possible.

        Args:
            note_id: The note ID (Card.id stores note IDs from findNotes).

        Returns:
            Dict with keys "again", "hard", "good", "easy" mapping to
            human-readable interval strings like "10 min", "2 days", etc.
        """
        unknown = {"again": "?", "hard": "?", "good": "?", "easy": "?"}
        try:
            card_ids = _request("findCards", query=f"nid:{note_id}")
        except AnkiConnectError:
            return unknown
        if not card_ids:
            return unknown

        try:
            cards_info = _request("cardsInfo", cards=[card_ids[0]])
            if not cards_info:
                return unknown
            info = cards_info[0]
        except (AnkiConnectError, IndexError):
            return unknown

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

    # ------------------------------------------------------------------
    # Review helpers
    # ------------------------------------------------------------------

    def suspend_cards(self, card_ids: list[int]) -> None:
        """Suspend cards so they are excluded from review."""
        if card_ids:
            _request("suspend", cards=card_ids)

    def unsuspend_cards(self, card_ids: list[int]) -> None:
        """Unsuspend previously suspended cards.

        Exits the review session first (via guiDeckBrowser) to avoid
        Anki search index conflicts, then unsuspends cards one at a time
        to avoid UNIQUE constraint DB errors that occur with batch unsuspend.
        """
        if not card_ids:
            return

        # Exit review session first — avoids Anki DB conflicts
        try:
            _request("guiDeckBrowser")
        except AnkiConnectError:
            pass

        # Unsuspend one at a time to avoid UNIQUE constraint DB errors
        for cid in card_ids:
            try:
                _request("unsuspend", cards=[cid])
            except AnkiConnectError:
                pass  # Card may already be unsuspended or deleted

    def _answer_cards_direct(self, answers: list[dict]) -> list:
        """Call answerCards, retrying once via guiDeckBrowser if needed.

        Anki's V3 scheduler rejects answerCards with "not at top of queue"
        when the GUI reviewer is active. Calling guiDeckBrowser and retrying
        clears this state and allows answerCards to work for any card.

        Args:
            answers: List of {"cardId": int, "ease": int} dicts.

        Returns:
            List of booleans from answerCards.

        Raises:
            AnkiConnectError: If answerCards fails even after retry.
        """
        try:
            result = _request("answerCards", answers=answers)
            if isinstance(result, list):
                return result
        except AnkiConnectError as e:
            if "not at top of queue" not in str(e):
                raise

        # Scheduler rejected it — exit reviewer and retry once
        try:
            _request("guiDeckBrowser")
        except AnkiConnectError:
            pass

        return _request("answerCards", answers=answers)

    def answer_card(self, note_id: int, ease: int, deck_name: str | None = None) -> tuple[bool, str]:
        """Mark a card as reviewed via AnkiConnect's answerCards.

        Resolves the note ID to a card ID and calls answerCards directly.
        If Anki's V3 scheduler rejects the call (e.g. because the GUI
        reviewer is open), exits the reviewer and retries once.

        Args:
            note_id: The note ID to answer. Will find associated card IDs.
            ease: Ease rating (1=Again, 2=Hard, 3=Good, 4=Easy).
            deck_name: Unused, kept for API compatibility.

        Returns:
            Tuple of (success: bool, message: str).
        """
        try:
            card_ids = _request("findCards", query=f"nid:{note_id}")
        except AnkiConnectError as e:
            return False, f"Could not look up card for note {note_id}: {e}"
        if not card_ids:
            return False, f"No card found for note ID {note_id}"

        target_card_id = card_ids[0]

        # Pre-condition: ensure non-new cards are answerable by the scheduler.
        # Skip for new cards (type=0) — setDueDate would corrupt their SRS
        # by converting them to review cards and skipping learning steps.
        try:
            info = _request("cardsInfo", cards=[target_card_id])
            if info and info[0].get("type", 0) != 0:
                _request("setDueDate", cards=[target_card_id], days="0")
        except AnkiConnectError:
            pass

        try:
            result = self._answer_cards_direct([{"cardId": target_card_id, "ease": ease}])
            if isinstance(result, list) and result and result[0] is True:
                return True, "OK"
            return False, f"answerCards returned {result}"
        except AnkiConnectError as e:
            return False, f"answerCards failed: {e}"

    def answer_cards_batch(
        self,
        note_ease_pairs: list[tuple[int, int]],
        deck_name: str | None = None,
    ) -> dict[int, tuple[bool, str]]:
        """Answer multiple cards via AnkiConnect's answerCards.

        Resolves each note ID to a card ID, then answers all cards in a
        single API call. If Anki's V3 scheduler rejects the call (e.g.
        because the GUI reviewer is open), exits the reviewer and retries.

        Args:
            note_ease_pairs: List of (note_id, ease) tuples.
            deck_name: Unused, kept for API compatibility.

        Returns:
            Dict mapping note_id -> (success, message).
        """
        if not note_ease_pairs:
            return {}

        # Resolve note IDs to card IDs and build answers list
        note_to_card: dict[int, int] = {}
        answers: list[dict] = []
        resolve_errors: dict[int, str] = {}

        for note_id, ease in note_ease_pairs:
            try:
                card_ids = _request("findCards", query=f"nid:{note_id}")
            except AnkiConnectError as e:
                resolve_errors[note_id] = f"Could not find card: {e}"
                continue
            if card_ids:
                note_to_card[note_id] = card_ids[0]
                answers.append({"cardId": card_ids[0], "ease": ease})

        # If no cards were resolved, return errors for all
        if not answers:
            return {
                nid: (False, resolve_errors.get(nid, "No card found"))
                for nid, _ in note_ease_pairs
            }

        # Pre-condition: setDueDate ensures non-new cards are answerable.
        # Without this, Anki's V3 scheduler rejects cards that aren't "due"
        # with "not at top of queue" error.
        # IMPORTANT: Do NOT call setDueDate on new cards (type=0) — it converts
        # them to review cards, skipping learning steps and corrupting SRS.
        # answerCards works directly on new cards without pre-conditioning.
        all_card_ids = [a["cardId"] for a in answers]
        try:
            cards_info = _request("cardsInfo", cards=all_card_ids)
            non_new_ids = [
                c["cardId"] for c in (cards_info or [])
                if c.get("type", 0) != 0
            ]
            if non_new_ids:
                _request("setDueDate", cards=non_new_ids, days="0")
        except AnkiConnectError:
            pass  # Best effort — answerCards might still work

        # Answer all cards in a single API call
        try:
            results = self._answer_cards_direct(answers)
        except AnkiConnectError as e:
            # Batch failed — try one at a time
            results = []
            for answer in answers:
                try:
                    r = _request("answerCards", answers=[answer])
                    results.append(r[0] if isinstance(r, list) and r else False)
                except AnkiConnectError:
                    results.append(False)

        # Build output from results
        output: dict[int, tuple[bool, str]] = {}

        for note_id, _ in note_ease_pairs:
            if note_id in resolve_errors:
                output[note_id] = (False, resolve_errors[note_id])
                continue
            card_id = note_to_card.get(note_id)
            if card_id is None:
                output[note_id] = (False, "No card found")
                continue

            # Find this card's result in the answers list
            answer_idx = next(
                (i for i, a in enumerate(answers) if a["cardId"] == card_id),
                None,
            )
            if answer_idx is not None and isinstance(results, list) and answer_idx < len(results):
                if results[answer_idx] is True:
                    output[note_id] = (True, "OK")
                else:
                    output[note_id] = (False, "Anki scheduler rejected the card")
            else:
                output[note_id] = (False, "No result from answerCards")

        return output

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
        # Get review data via cardsInfo which has interval/ease/due info
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
        stats_note = None

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

                if len(all_cards) > 2000:
                    stats_note = (
                        f"Stats based on first 2000 of {len(all_cards)} cards. "
                        "Retention rate and maturity counts may be incomplete."
                    )
            except AnkiConnectError:
                # Fall back to deck-level stats
                new_count = total_new
                learning_count = total_learn
                stats_note = (
                    "Could not fetch detailed card stats. "
                    "Retention rate unavailable; counts are estimates from deck-level data."
                )

        # Retention rate: (reps - lapses) / reps * 100
        retention_rate = 0.0
        if total_reps > 0:
            retention_rate = ((total_reps - total_lapses) / total_reps) * 100

        result = {
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
        if stats_note:
            result["stats_note"] = stats_note
        return result
