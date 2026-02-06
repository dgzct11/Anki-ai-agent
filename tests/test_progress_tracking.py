"""Tests for progress_tracking module - streaks, skills radar, time progress, weak spots."""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest

from ankicli.progress_tracking import (
    _load_streaks,
    _save_streaks,
    record_activity,
    get_current_streak,
    get_longest_streak,
    get_streaks_summary,
    get_skills_radar,
    format_skills_radar_text,
    _load_progress_history,
    _save_progress_history,
    record_progress_snapshot,
    get_progress_over_time,
    format_progress_over_time_text,
    get_weak_spots,
)
from ankicli.error_journal import ErrorEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_streaks(tmp_path):
    data_dir = tmp_path / ".ankicli"
    streaks_file = data_dir / "streaks.json"
    return (
        patch("ankicli.progress_tracking.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
        patch("ankicli.progress_tracking.STREAKS_FILE", streaks_file),
    )


def _patch_progress_history(tmp_path):
    data_dir = tmp_path / ".ankicli"
    history_file = data_dir / "progress_history.json"
    return (
        patch("ankicli.progress_tracking.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
        patch("ankicli.progress_tracking.PROGRESS_HISTORY_FILE", history_file),
    )


# ---------------------------------------------------------------------------
# P5: Study Streaks
# ---------------------------------------------------------------------------

class TestStreaksPersistence:
    """Test load/save of streaks data."""

    def test_load_empty(self, tmp_path):
        p1, p2 = _patch_streaks(tmp_path)
        with p1, p2:
            data = _load_streaks()
            assert data["dates"] == []
            assert data["longest_streak"] == 0

    def test_save_and_load(self, tmp_path):
        p1, p2 = _patch_streaks(tmp_path)
        with p1, p2:
            data = {"dates": ["2025-01-01", "2025-01-02"], "longest_streak": 2}
            _save_streaks(data)
            loaded = _load_streaks()
            assert loaded["dates"] == ["2025-01-01", "2025-01-02"]
            assert loaded["longest_streak"] == 2


class TestRecordActivity:
    """Test record_activity function."""

    def test_record_today(self, tmp_path):
        p1, p2 = _patch_streaks(tmp_path)
        with p1, p2:
            result = record_activity()
            assert result["date_recorded"] == date.today().isoformat()
            assert result["current_streak"] >= 1
            assert result["total_active_days"] == 1

    def test_record_specific_date(self, tmp_path):
        p1, p2 = _patch_streaks(tmp_path)
        with p1, p2:
            d = date(2025, 6, 15)
            result = record_activity(d)
            assert result["date_recorded"] == "2025-06-15"
            assert result["total_active_days"] == 1

    def test_record_duplicate_date(self, tmp_path):
        p1, p2 = _patch_streaks(tmp_path)
        with p1, p2:
            d = date.today()
            record_activity(d)
            result = record_activity(d)
            assert result["total_active_days"] == 1  # not duplicated

    def test_record_consecutive_days(self, tmp_path):
        p1, p2 = _patch_streaks(tmp_path)
        with p1, p2:
            today = date.today()
            record_activity(today - timedelta(days=2))
            record_activity(today - timedelta(days=1))
            result = record_activity(today)
            assert result["current_streak"] == 3
            assert result["longest_streak"] == 3
            assert result["total_active_days"] == 3


class TestGetCurrentStreak:
    """Test get_current_streak function."""

    def test_empty(self):
        assert get_current_streak({"dates": []}) == 0

    def test_today_only(self):
        today = date.today()
        assert get_current_streak({"dates": [today.isoformat()]}) == 1

    def test_yesterday_only(self):
        yesterday = date.today() - timedelta(days=1)
        assert get_current_streak({"dates": [yesterday.isoformat()]}) == 1

    def test_two_days_ago_only(self):
        two_days = date.today() - timedelta(days=2)
        assert get_current_streak({"dates": [two_days.isoformat()]}) == 0

    def test_consecutive_ending_today(self):
        today = date.today()
        dates = [(today - timedelta(days=i)).isoformat() for i in range(5)]
        assert get_current_streak({"dates": dates}) == 5

    def test_gap_breaks_streak(self):
        today = date.today()
        dates = [
            today.isoformat(),
            (today - timedelta(days=1)).isoformat(),
            # gap on day 2
            (today - timedelta(days=3)).isoformat(),
        ]
        assert get_current_streak({"dates": dates}) == 2


class TestGetLongestStreak:
    """Test get_longest_streak function."""

    def test_empty(self):
        assert get_longest_streak({"dates": []}) == 0

    def test_single_day(self):
        assert get_longest_streak({"dates": ["2025-01-01"]}) == 1

    def test_consecutive(self):
        dates = ["2025-01-01", "2025-01-02", "2025-01-03"]
        assert get_longest_streak({"dates": dates}) == 3

    def test_gap(self):
        dates = ["2025-01-01", "2025-01-02", "2025-01-05", "2025-01-06", "2025-01-07", "2025-01-08"]
        assert get_longest_streak({"dates": dates}) == 4

    def test_multiple_streaks(self):
        dates = [
            "2025-01-01", "2025-01-02",  # streak of 2
            "2025-01-10", "2025-01-11", "2025-01-12", "2025-01-13",  # streak of 4
            "2025-01-20", "2025-01-21", "2025-01-22",  # streak of 3
        ]
        assert get_longest_streak({"dates": dates}) == 4


class TestGetStreaksSummary:
    """Test get_streaks_summary function."""

    def test_empty(self, tmp_path):
        p1, p2 = _patch_streaks(tmp_path)
        with p1, p2:
            summary = get_streaks_summary()
            assert summary["current_streak"] == 0
            assert summary["longest_streak"] == 0
            assert summary["total_active_days"] == 0
            assert len(summary["last_7_days"]) == 7
            assert summary["last_30_days_active"] == 0

    def test_with_activity(self, tmp_path):
        p1, p2 = _patch_streaks(tmp_path)
        with p1, p2:
            today = date.today()
            record_activity(today)
            record_activity(today - timedelta(days=1))
            summary = get_streaks_summary()
            assert summary["current_streak"] == 2
            assert summary["total_active_days"] == 2
            assert summary["last_30_days_active"] == 2


# ---------------------------------------------------------------------------
# P6: Skills Radar
# ---------------------------------------------------------------------------

class TestSkillsRadar:
    """Test get_skills_radar function."""

    def test_empty_data(self):
        radar = get_skills_radar()
        dims = radar["dimensions"]
        assert dims["vocabulary_breadth"] == 0
        assert dims["grammar_accuracy"] == 0
        assert dims["productive_skill"] == 0
        assert dims["topic_coverage"] == 0
        assert dims["retention"] == 0
        assert radar["overall"] == 0

    def test_with_retention(self):
        stats = {"retention_rate": 92.5}
        radar = get_skills_radar(collection_stats=stats)
        assert radar["dimensions"]["retention"] == 92.5

    def test_with_quiz_results(self):
        quiz_results = [
            {"score": 80},
            {"score": 90},
            {"score": 70},
        ]
        radar = get_skills_radar(quiz_results=quiz_results)
        assert radar["dimensions"]["grammar_accuracy"] == 80.0

    def test_with_practice_sessions(self):
        summary = {
            "practice_sessions": [
                {"score_percent": 85},
                {"score_percent": 75},
            ]
        }
        radar = get_skills_radar(learning_summary=summary)
        assert radar["dimensions"]["productive_skill"] == 80.0

    def test_with_cefr_progress(self):
        from unittest.mock import MagicMock
        lp_a1 = MagicMock()
        lp_a1.percent = 80
        cat_food = MagicMock(); cat_food.percent = 90
        cat_travel = MagicMock(); cat_travel.percent = 50
        lp_a1.categories = {"food": cat_food, "travel": cat_travel}
        lp_a2 = MagicMock()
        lp_a2.percent = 40
        cat_work = MagicMock(); cat_work.percent = 20
        lp_a2.categories = {"work": cat_work}
        cefr_progress = {"A1": lp_a1, "A2": lp_a2}
        radar = get_skills_radar(cefr_progress=cefr_progress)
        assert radar["dimensions"]["vocabulary_breadth"] > 0
        assert radar["dimensions"]["topic_coverage"] > 0

    def test_overall_is_average(self):
        from unittest.mock import MagicMock
        stats = {"retention_rate": 100}
        quiz_results = [{"score": 100}]
        summary = {"practice_sessions": [{"score_percent": 100}]}
        lp = MagicMock()
        lp.percent = 100
        cat = MagicMock(); cat.percent = 100
        lp.categories = {"food": cat}
        cefr_progress = {"A1": lp}
        radar = get_skills_radar(
            collection_stats=stats,
            quiz_results=quiz_results,
            learning_summary=summary,
            cefr_progress=cefr_progress,
        )
        # All should be 100 except topic_coverage which needs all levels
        assert radar["overall"] > 0


class TestFormatSkillsRadar:
    """Test format_skills_radar_text function."""

    def test_format(self):
        radar = {
            "dimensions": {
                "vocabulary_breadth": 50,
                "grammar_accuracy": 80,
                "productive_skill": 60,
                "topic_coverage": 30,
                "retention": 90,
            },
            "overall": 62,
        }
        text = format_skills_radar_text(radar)
        assert "Skills Radar" in text
        assert "Vocabulary Breadth" in text
        assert "Overall" in text


# ---------------------------------------------------------------------------
# P7: Time-Based Progress
# ---------------------------------------------------------------------------

class TestProgressHistory:
    """Test progress history persistence."""

    def test_load_empty(self, tmp_path):
        p1, p2 = _patch_progress_history(tmp_path)
        with p1, p2:
            history = _load_progress_history()
            assert history == []

    def test_record_snapshot(self, tmp_path):
        p1, p2 = _patch_progress_history(tmp_path)
        with p1, p2:
            snap = record_progress_snapshot(
                total_cards=100,
                cefr_levels={"A1": 50, "A2": 20},
                retention_rate=85.5,
            )
            assert snap["total_cards"] == 100
            assert snap["date"] == date.today().isoformat()
            assert snap["retention_rate"] == 85.5

    def test_record_replaces_same_day(self, tmp_path):
        p1, p2 = _patch_progress_history(tmp_path)
        with p1, p2:
            today = date.today()
            record_progress_snapshot(total_cards=100, snapshot_date=today)
            record_progress_snapshot(total_cards=120, snapshot_date=today)
            history = _load_progress_history()
            assert len(history) == 1
            assert history[0]["total_cards"] == 120

    def test_multiple_days(self, tmp_path):
        p1, p2 = _patch_progress_history(tmp_path)
        with p1, p2:
            today = date.today()
            record_progress_snapshot(total_cards=100, snapshot_date=today - timedelta(days=1))
            record_progress_snapshot(total_cards=110, snapshot_date=today)
            history = _load_progress_history()
            assert len(history) == 2
            assert history[0]["total_cards"] == 100
            assert history[1]["total_cards"] == 110


class TestGetProgressOverTime:
    """Test get_progress_over_time function."""

    def test_empty(self, tmp_path):
        p1, p2 = _patch_progress_history(tmp_path)
        with p1, p2:
            result = get_progress_over_time()
            assert result["time_series"] == []
            assert result["total_snapshots"] == 0

    def test_monthly_aggregation(self, tmp_path):
        p1, p2 = _patch_progress_history(tmp_path)
        with p1, p2:
            # Record some snapshots across months
            record_progress_snapshot(
                total_cards=50,
                snapshot_date=date(2025, 1, 1),
            )
            record_progress_snapshot(
                total_cards=80,
                snapshot_date=date(2025, 1, 15),
            )
            record_progress_snapshot(
                total_cards=100,
                snapshot_date=date(2025, 2, 1),
            )

            result = get_progress_over_time(period="month")
            assert len(result["time_series"]) == 2
            assert result["total_snapshots"] == 3

            # January should show latest (80)
            jan = result["time_series"][0]
            assert jan["period"] == "2025-01"
            assert jan["total_cards"] == 80

    def test_weekly_aggregation(self, tmp_path):
        p1, p2 = _patch_progress_history(tmp_path)
        with p1, p2:
            record_progress_snapshot(
                total_cards=50,
                snapshot_date=date(2025, 1, 6),  # Monday of week 2
            )
            record_progress_snapshot(
                total_cards=60,
                snapshot_date=date(2025, 1, 13),  # Monday of week 3
            )

            result = get_progress_over_time(period="week")
            assert len(result["time_series"]) == 2


class TestFormatProgressOverTime:
    """Test format_progress_over_time_text function."""

    def test_empty(self):
        text = format_progress_over_time_text({"period": "month", "time_series": [], "total_snapshots": 0})
        assert "No progress history" in text

    def test_with_data(self):
        progress = {
            "period": "month",
            "time_series": [
                {
                    "period": "2025-01",
                    "total_cards": 100,
                    "cards_added_in_period": 30,
                    "cefr_levels": {"A1": 50},
                    "retention_rate": 85,
                    "snapshots_count": 2,
                },
            ],
            "total_snapshots": 2,
        }
        text = format_progress_over_time_text(progress)
        assert "2025-01" in text
        assert "100 cards" in text


# ---------------------------------------------------------------------------
# P8: Weak Spots
# ---------------------------------------------------------------------------

class TestWeakSpots:
    """Test get_weak_spots function."""

    def test_empty(self):
        result = get_weak_spots()
        assert result["weak_grammar"] == []
        assert result["weak_vocabulary"] == []
        assert result["forgotten_cards"] == []
        assert "Weak Spots" in result["summary"]

    def test_weak_grammar(self):
        quiz_results = [
            {"topic": "ser_vs_estar", "score": 60},
            {"topic": "ser_vs_estar", "score": 50},
            {"topic": "preterite", "score": 90},
        ]
        result = get_weak_spots(quiz_results=quiz_results)
        assert len(result["weak_grammar"]) == 1
        assert result["weak_grammar"][0]["topic"] == "ser_vs_estar"
        assert result["weak_grammar"][0]["avg_score"] == 55.0

    def test_weak_vocabulary(self):
        entries = [
            ErrorEntry(error_type="gender_agreement", count=8, tags=["grammar", "A2"], last_seen="2025-01-01"),
            ErrorEntry(error_type="accent_missing", count=3, tags=["spelling"], last_seen="2025-01-02"),
        ]
        result = get_weak_spots(error_entries=entries)
        assert len(result["weak_vocabulary"]) == 2
        assert result["weak_vocabulary"][0]["error_type"] == "gender_agreement"

    def test_forgotten_cards(self):
        reviews = [
            {"card_id": 1, "note_id": 100, "lapses": 5, "ease": 1500, "reps": 10, "interval": 3},
            {"card_id": 2, "note_id": 200, "lapses": 0, "ease": 2500, "reps": 5, "interval": 21},
            {"card_id": 3, "note_id": 300, "lapses": 3, "ease": 1800, "reps": 8, "interval": 7},
        ]
        result = get_weak_spots(card_reviews=reviews)
        assert len(result["forgotten_cards"]) == 2
        # Highest lapses first
        assert result["forgotten_cards"][0]["note_id"] == 100
        assert result["forgotten_cards"][1]["note_id"] == 300

    def test_combined(self):
        quiz_results = [{"topic": "subjunctive", "score": 40}]
        entries = [ErrorEntry(error_type="accent", count=5, tags=[], last_seen="2025-01-01")]
        reviews = [{"card_id": 1, "note_id": 10, "lapses": 4, "ease": 1500, "reps": 10, "interval": 2}]

        result = get_weak_spots(
            quiz_results=quiz_results,
            error_entries=entries,
            card_reviews=reviews,
        )
        assert len(result["weak_grammar"]) == 1
        assert len(result["weak_vocabulary"]) == 1
        assert len(result["forgotten_cards"]) == 1
        assert "subjunctive" in result["summary"]
        assert "accent" in result["summary"]


# ---------------------------------------------------------------------------
# Integration: paths.py
# ---------------------------------------------------------------------------

class TestPathsIntegration:
    """Verify STREAKS_FILE and PROGRESS_HISTORY_FILE are defined in paths."""

    def test_streaks_file_exists(self):
        from ankicli.paths import STREAKS_FILE
        assert "streaks.json" in str(STREAKS_FILE)

    def test_progress_history_file_exists(self):
        from ankicli.paths import PROGRESS_HISTORY_FILE
        assert "progress_history.json" in str(PROGRESS_HISTORY_FILE)


# ---------------------------------------------------------------------------
# P11: Anki Review Integration - handler tests
# ---------------------------------------------------------------------------

class TestMarkCardsReviewedHandler:
    """Test mark_cards_reviewed handler."""

    def test_handler_registered(self):
        from ankicli.tool_handlers import HANDLERS
        assert "mark_cards_reviewed" in HANDLERS

    def test_mark_success(self):
        from ankicli.tool_handlers import HANDLERS
        handler_fn = HANDLERS["mark_cards_reviewed"]

        mock_anki = MagicMock()
        mock_anki.answer_cards_batch.return_value = {
            123: (True, "OK"),
            456: (True, "OK"),
        }

        result = handler_fn(mock_anki, {"card_ids": ["123", "456"], "ease": 3})
        assert "Marked in Anki" in result
        assert "Good" in result

    def test_mark_with_failures(self):
        from ankicli.tool_handlers import HANDLERS
        handler_fn = HANDLERS["mark_cards_reviewed"]

        mock_anki = MagicMock()
        mock_anki.answer_cards_batch.return_value = {
            123: (True, "OK"),
            456: (False, "not in queue"),
        }

        result = handler_fn(mock_anki, {"card_ids": ["123", "456"], "ease": 3})
        assert "Marked in Anki" in result
        assert "Review these in Anki manually" in result

    def test_invalid_ease(self):
        from ankicli.tool_handlers import HANDLERS
        handler_fn = HANDLERS["mark_cards_reviewed"]

        mock_anki = MagicMock()
        result = handler_fn(mock_anki, {"card_ids": ["123"], "ease": 5})
        assert "Invalid ease" in result

    def test_empty_card_ids(self):
        from ankicli.tool_handlers import HANDLERS
        handler_fn = HANDLERS["mark_cards_reviewed"]

        mock_anki = MagicMock()
        result = handler_fn(mock_anki, {"card_ids": []})
        assert "No card IDs" in result

    def test_default_ease_is_good(self):
        from ankicli.tool_handlers import HANDLERS
        handler_fn = HANDLERS["mark_cards_reviewed"]

        mock_anki = MagicMock()
        mock_anki.answer_cards_batch.return_value = {123: (True, "OK")}

        result = handler_fn(mock_anki, {"card_ids": ["123"]})
        # Verify batch was called with ease=3 (Good)
        call_args = mock_anki.answer_cards_batch.call_args[0][0]
        assert call_args[0] == (123, 3)
        assert "Good" in result


class TestGetSessionDueWordsHandler:
    """Test get_session_due_words handler."""

    def test_handler_registered(self):
        from ankicli.tool_handlers import HANDLERS
        assert "get_session_due_words" in HANDLERS

    def test_no_words(self):
        from ankicli.tool_handlers import HANDLERS
        handler_fn = HANDLERS["get_session_due_words"]

        mock_anki = MagicMock()
        result = handler_fn(mock_anki, {"deck_name": "Test", "session_words": []})
        assert "No session words" in result

    def test_no_due_cards(self):
        from ankicli.tool_handlers import HANDLERS
        handler_fn = HANDLERS["get_session_due_words"]

        mock_anki = MagicMock()
        mock_anki.get_due_cards.return_value = []

        result = handler_fn(mock_anki, {"deck_name": "Test", "session_words": ["hablar"]})
        assert "No cards are due" in result

    def test_matching_due_words(self):
        from ankicli.tool_handlers import HANDLERS
        from ankicli.models import Card
        handler_fn = HANDLERS["get_session_due_words"]

        mock_anki = MagicMock()
        mock_anki.get_due_cards.return_value = [
            Card(id="100", front="to speak", back="<b>hablar</b>", deck_id="1"),
            Card(id="200", front="to eat", back="<b>comer</b>", deck_id="1"),
        ]

        result = handler_fn(mock_anki, {
            "deck_name": "Test",
            "session_words": ["hablar", "dormir"],
        })
        assert "hablar" in result
        assert "card ID: 100" in result
        assert "dormir" not in result  # dormir is not due

    def test_never_auto_mark(self):
        from ankicli.tool_handlers import HANDLERS
        from ankicli.models import Card
        handler_fn = HANDLERS["get_session_due_words"]

        mock_anki = MagicMock()
        mock_anki.get_due_cards.return_value = [
            Card(id="100", front="to speak", back="hablar", deck_id="1"),
        ]

        result = handler_fn(mock_anki, {
            "deck_name": "Test",
            "session_words": ["hablar"],
        })
        # Must include instructions about reviewing
        assert "mark_cards_reviewed" in result or "review" in result.lower()
        # Handler itself does not call answer_card (that's mark_cards_reviewed's job)
        mock_anki.answer_card.assert_not_called()
