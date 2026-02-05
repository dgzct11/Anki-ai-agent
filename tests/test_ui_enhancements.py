"""Tests for UI enhancement features U1-U8."""

from datetime import date, timedelta
from unittest.mock import patch

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ankicli.chat import (
    create_cefr_deep_dive_panel,
    create_conjugation_table,
    create_context_bar,
    create_grammar_mastery_checklist,
    create_practice_feedback_panel,
    create_practice_question_panel,
    create_quiz_question_panel,
    create_quiz_summary_panel,
    create_quiz_type_breakdown_table,
    create_session_progress_bar,
    highlight_word_diff,
)
from ankicli.learning_summary import (
    _create_activity_heatmap,
    compute_study_streak,
)
from ankicli.translation_practice import FeedbackLevel, PracticeDirection


def _render(renderable) -> str:
    """Render a Rich renderable to plain string for assertions."""
    console = Console(file=None, force_terminal=False, width=80)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


# ---------------------------------------------------------------------------
# U1: Refined practice feedback panels with word-level highlighting
# ---------------------------------------------------------------------------


class TestHighlightWordDiff:
    """Tests for highlight_word_diff (U1)."""

    def test_all_correct_words_green(self):
        result = highlight_word_diff("yo como pan", "yo como pan")
        rendered = _render(result)
        assert "yo" in rendered
        assert "como" in rendered
        assert "pan" in rendered

    def test_wrong_words_present(self):
        result = highlight_word_diff("yo como pan", "yo bebo agua")
        # Result should contain user's words
        rendered = _render(result)
        assert "yo" in rendered
        assert "como" in rendered
        assert "pan" in rendered

    def test_partial_match_words(self):
        result = highlight_word_diff("comer", "comemos")
        # "comer" partially contains "come" from "comemos"
        rendered = _render(result)
        assert "comer" in rendered

    def test_extra_words_in_user_answer(self):
        result = highlight_word_diff("yo como mucho pan", "yo como pan")
        rendered = _render(result)
        assert "mucho" in rendered

    def test_empty_user_answer(self):
        result = highlight_word_diff("", "yo como pan")
        rendered = _render(result)
        assert rendered.strip() == ""

    def test_returns_text_object(self):
        result = highlight_word_diff("hola", "hola")
        assert isinstance(result, Text)

    def test_exact_match_single_word(self):
        result = highlight_word_diff("hola", "hola")
        # Should have green style for correct word
        assert len(result._spans) > 0


class TestPracticeFeedbackPanel:
    """Tests for create_practice_feedback_panel with U1 enhancements."""

    def test_correct_feedback_no_diff(self):
        """Correct answers don't show word diff."""
        panel = create_practice_feedback_panel(
            feedback_level=FeedbackLevel.CORRECT,
            feedback_text="Perfect!",
            scores={"Meaning": 4, "Grammar": 4, "Natural": 4, "Vocab": 4},
            user_answer="yo como",
            correct_answer="yo como",
        )
        rendered = _render(panel)
        assert "CORRECT" in rendered

    def test_incorrect_shows_word_diff(self):
        """Incorrect answers show word-level highlighting."""
        panel = create_practice_feedback_panel(
            feedback_level=FeedbackLevel.INCORRECT,
            feedback_text="Try again",
            scores={"Meaning": 1, "Grammar": 1, "Natural": 1, "Vocab": 1},
            user_answer="yo como pan",
            correct_answer="yo bebo agua",
        )
        rendered = _render(panel)
        assert "INCORRECT" in rendered
        assert "Your answer:" in rendered
        assert "Correct:" in rendered

    def test_partial_shows_word_diff(self):
        """Partial answers show word-level highlighting."""
        panel = create_practice_feedback_panel(
            feedback_level=FeedbackLevel.PARTIAL,
            feedback_text="Almost",
            scores={"Meaning": 3, "Grammar": 2, "Natural": 2, "Vocab": 3},
            user_answer="yo como pan",
            correct_answer="yo como arroz",
        )
        rendered = _render(panel)
        assert "PARTIAL" in rendered

    def test_backward_compatible_without_answers(self):
        """Still works without user_answer/correct_answer."""
        panel = create_practice_feedback_panel(
            feedback_level=FeedbackLevel.CORRECT,
            feedback_text="Good job!",
            scores={"Meaning": 4, "Grammar": 4, "Natural": 4, "Vocab": 4},
        )
        rendered = _render(panel)
        assert "CORRECT" in rendered
        assert "Scores:" in rendered

    def test_scores_displayed(self):
        panel = create_practice_feedback_panel(
            feedback_level=FeedbackLevel.PARTIAL,
            feedback_text="Close",
            scores={"Meaning": 3, "Grammar": 2, "Natural": 3, "Vocab": 2},
        )
        rendered = _render(panel)
        assert "Meaning" in rendered
        assert "Grammar" in rendered

    def test_returns_panel(self):
        panel = create_practice_feedback_panel(
            feedback_level=FeedbackLevel.CORRECT,
            feedback_text="OK",
            scores={"Meaning": 4},
        )
        assert isinstance(panel, Panel)


# ---------------------------------------------------------------------------
# U2: Score progress bar during sessions
# ---------------------------------------------------------------------------


class TestSessionProgressBar:
    """Tests for create_session_progress_bar (U2)."""

    def test_renders_question_count(self):
        bar = create_session_progress_bar(3, 10)
        rendered = _render(bar)
        assert "Question 3/10" in rendered
        assert "30%" in rendered

    def test_full_progress(self):
        bar = create_session_progress_bar(10, 10)
        rendered = _render(bar)
        assert "100%" in rendered

    def test_zero_progress(self):
        bar = create_session_progress_bar(0, 10)
        rendered = _render(bar)
        assert "0%" in rendered

    def test_single_question(self):
        bar = create_session_progress_bar(1, 1)
        rendered = _render(bar)
        assert "Question 1/1" in rendered
        assert "100%" in rendered

    def test_handles_zero_total(self):
        # Zero total defaults to 1 to avoid division by zero
        bar = create_session_progress_bar(0, 0)
        rendered = _render(bar)
        assert "0%" in rendered

    def test_returns_text(self):
        bar = create_session_progress_bar(5, 10)
        assert isinstance(bar, Text)

    def test_practice_panel_has_progress_bar(self):
        panel = create_practice_question_panel(
            question_num=3,
            total=10,
            phrase="Hello world",
            direction=PracticeDirection.EN_TO_ES,
            is_due=False,
            difficulty="normal",
        )
        rendered = _render(panel)
        assert "Question 3/10" in rendered
        assert "30%" in rendered

    def test_quiz_panel_has_progress_bar(self):
        panel = create_quiz_question_panel(
            question_num=2,
            total=5,
            question_text="Yo ___ (comer) pizza.",
            question_type="fill_in_blank",
        )
        rendered = _render(panel)
        assert "Question 2/5" in rendered
        assert "40%" in rendered


# ---------------------------------------------------------------------------
# U3: Conjugation table format
# ---------------------------------------------------------------------------


class TestConjugationTable:
    """Tests for create_conjugation_table (U3)."""

    def test_creates_table(self):
        table = create_conjugation_table("hablar", "presente")
        assert isinstance(table, Table)

    def test_has_persons(self):
        table = create_conjugation_table("comer")
        rendered = _render(table)
        assert "yo" in rendered
        assert "nosotros" in rendered
        assert "ellos" in rendered

    def test_shows_verb_name(self):
        table = create_conjugation_table("vivir", "preterito")
        rendered = _render(table)
        assert "vivir" in rendered

    def test_quiz_panel_conjugation_type_shows_grid(self):
        panel = create_quiz_question_panel(
            question_num=1,
            total=5,
            question_text="Conjugate 'hablar' in present tense:",
            question_type="conjugation",
        )
        rendered = _render(panel)
        assert "yo" in rendered
        assert "nosotros" in rendered


# ---------------------------------------------------------------------------
# U4: Per-type quiz score breakdown
# ---------------------------------------------------------------------------


class TestQuizTypeBreakdownTable:
    """Tests for create_quiz_type_breakdown_table (U4)."""

    def test_creates_table(self):
        breakdown = {
            "fill_in_blank": {"correct": 4, "total": 5, "score": 80.0},
            "multiple_choice": {"correct": 3, "total": 3, "score": 100.0},
        }
        table = create_quiz_type_breakdown_table(breakdown)
        assert isinstance(table, Table)

    def test_shows_question_types(self):
        breakdown = {
            "fill_in_blank": {"correct": 4, "total": 5, "score": 80.0},
            "conjugation": {"correct": 1, "total": 2, "score": 50.0},
        }
        table = create_quiz_type_breakdown_table(breakdown)
        rendered = _render(table)
        assert "Fill in the Blank" in rendered
        assert "Conjugation" in rendered

    def test_shows_scores(self):
        breakdown = {
            "fill_in_blank": {"correct": 4, "total": 5, "score": 80.0},
        }
        table = create_quiz_type_breakdown_table(breakdown)
        rendered = _render(table)
        assert "4/5" in rendered
        assert "80%" in rendered

    def test_empty_breakdown(self):
        table = create_quiz_type_breakdown_table({})
        rendered = _render(table)
        # Should render without error
        assert rendered is not None

    def test_quiz_summary_panel_has_type_bars(self):
        panel = create_quiz_summary_panel(
            topic="Ser vs Estar",
            level="A1",
            correct=7,
            total=10,
            score=70.0,
            type_breakdown={
                "fill_in_blank": {"correct": 4, "total": 5, "score": 80.0},
                "multiple_choice": {"correct": 3, "total": 5, "score": 60.0},
            },
            weak_areas=["ser vs estar"],
            mastered=False,
        )
        rendered = _render(panel)
        assert "BY TYPE" in rendered
        assert "4/5" in rendered


# ---------------------------------------------------------------------------
# U5: 14-day activity heatmap with streak
# ---------------------------------------------------------------------------


class TestActivityHeatmap:
    """Tests for _create_activity_heatmap and compute_study_streak (U5)."""

    def test_streak_zero_no_activity(self):
        summary = {"daily_activity": {}}
        streak = compute_study_streak(summary)
        assert streak == 0

    def test_streak_today_only(self):
        today = date.today().isoformat()
        summary = {"daily_activity": {today: 5}}
        streak = compute_study_streak(summary)
        assert streak == 1

    def test_streak_consecutive_days(self):
        activity = {}
        for i in range(5):
            d = (date.today() - timedelta(days=i)).isoformat()
            activity[d] = 3
        summary = {"daily_activity": activity}
        streak = compute_study_streak(summary)
        assert streak == 5

    def test_streak_breaks_on_gap(self):
        activity = {}
        for i in range(3):
            d = (date.today() - timedelta(days=i)).isoformat()
            activity[d] = 2
        # Skip day 3
        d = (date.today() - timedelta(days=4)).isoformat()
        activity[d] = 5
        summary = {"daily_activity": activity}
        streak = compute_study_streak(summary)
        assert streak == 3

    def test_heatmap_shows_streak(self):
        today = date.today().isoformat()
        summary = {"daily_activity": {today: 5}}
        text = _create_activity_heatmap(summary)
        rendered = _render(text)
        assert "Streak: 1d" in rendered

    def test_heatmap_shows_activity_label(self):
        summary = {"daily_activity": {}}
        text = _create_activity_heatmap(summary)
        rendered = _render(text)
        assert "ACTIVITY" in rendered
        assert "last 14 days" in rendered

    def test_heatmap_no_streak_without_activity(self):
        summary = {"daily_activity": {}}
        text = _create_activity_heatmap(summary)
        rendered = _render(text)
        assert "Streak" not in rendered

    def test_heatmap_legend(self):
        summary = {"daily_activity": {}}
        text = _create_activity_heatmap(summary)
        rendered = _render(text)
        assert "=0" in rendered
        assert "=11+" in rendered


# ---------------------------------------------------------------------------
# U6: Grammar mastery checklist
# ---------------------------------------------------------------------------


class TestGrammarMasteryChecklist:
    """Tests for create_grammar_mastery_checklist (U6)."""

    def test_returns_panel(self):
        with patch("ankicli.chat.get_topic_mastery", return_value={}):
            panel = create_grammar_mastery_checklist()
        assert isinstance(panel, Panel)

    def test_shows_title(self):
        with patch("ankicli.chat.get_topic_mastery", return_value={}):
            panel = create_grammar_mastery_checklist()
        rendered = _render(panel)
        assert "GRAMMAR" in rendered

    def test_shows_levels(self):
        with patch("ankicli.chat.get_topic_mastery", return_value={}):
            panel = create_grammar_mastery_checklist()
        rendered = _render(panel)
        assert "A1" in rendered
        assert "A2" in rendered

    def test_mastered_topic_shows_check(self):
        mastery = {
            "Present tense - regular verbs": {
                "avg_score": 90.0,
                "mastered": True,
                "quizzed_count": 3,
            }
        }
        with patch("ankicli.chat.get_topic_mastery", return_value=mastery):
            panel = create_grammar_mastery_checklist()
        rendered = _render(panel)
        assert "\u2713" in rendered

    def test_developing_topic_shows_tilde(self):
        mastery = {
            "Ser vs Estar": {
                "avg_score": 75.0,
                "mastered": False,
                "quizzed_count": 2,
            }
        }
        with patch("ankicli.chat.get_topic_mastery", return_value=mastery):
            panel = create_grammar_mastery_checklist()
        rendered = _render(panel)
        assert "~" in rendered

    def test_weak_topic_shows_x(self):
        mastery = {
            "Gender and number agreement": {
                "avg_score": 40.0,
                "mastered": False,
                "quizzed_count": 1,
            }
        }
        with patch("ankicli.chat.get_topic_mastery", return_value=mastery):
            panel = create_grammar_mastery_checklist()
        rendered = _render(panel)
        assert "\u2717" in rendered

    def test_legend_shown(self):
        with patch("ankicli.chat.get_topic_mastery", return_value={}):
            panel = create_grammar_mastery_checklist()
        rendered = _render(panel)
        assert "mastered" in rendered
        assert "developing" in rendered
        assert "needs review" in rendered


# ---------------------------------------------------------------------------
# U7: CEFR deep-dive view
# ---------------------------------------------------------------------------


class TestCEFRDeepDivePanel:
    """Tests for create_cefr_deep_dive_panel (U7)."""

    def _sample_level_progress(self):
        return {
            "words_known": 147,
            "words_total": 500,
            "categories": {
                "greetings": {"known": 20, "total": 25, "percent": 80.0},
                "food": {"known": 10, "total": 30, "percent": 33.3},
                "travel": {"known": 5, "total": 20, "percent": 25.0},
            },
        }

    def test_returns_panel(self):
        panel = create_cefr_deep_dive_panel(
            "A2",
            self._sample_level_progress(),
            {},
        )
        assert isinstance(panel, Panel)

    def test_shows_level(self):
        panel = create_cefr_deep_dive_panel(
            "A2",
            self._sample_level_progress(),
            {},
        )
        rendered = _render(panel)
        assert "A2" in rendered

    def test_shows_vocabulary_count(self):
        panel = create_cefr_deep_dive_panel(
            "A2",
            self._sample_level_progress(),
            {},
        )
        rendered = _render(panel)
        assert "147/500" in rendered

    def test_shows_categories(self):
        panel = create_cefr_deep_dive_panel(
            "A2",
            self._sample_level_progress(),
            {},
        )
        rendered = _render(panel)
        assert "CATEGORIES" in rendered
        assert "greetings" in rendered
        assert "food" in rendered

    def test_shows_grammar_section(self):
        panel = create_cefr_deep_dive_panel(
            "A1",
            {"words_known": 50, "words_total": 200, "categories": {}},
            {},
        )
        rendered = _render(panel)
        assert "GRAMMAR" in rendered

    def test_shows_recommendations(self):
        panel = create_cefr_deep_dive_panel(
            "A2",
            self._sample_level_progress(),
            {},
        )
        rendered = _render(panel)
        assert "RECOMMENDATIONS" in rendered

    def test_recommendation_for_low_coverage(self):
        panel = create_cefr_deep_dive_panel(
            "A2",
            {"words_known": 10, "words_total": 500, "categories": {
                "basic": {"known": 10, "total": 500, "percent": 2.0},
            }},
            {},
        )
        rendered = _render(panel)
        assert "core vocabulary" in rendered

    def test_recommendation_for_high_coverage(self):
        panel = create_cefr_deep_dive_panel(
            "A1",
            {"words_known": 400, "words_total": 500, "categories": {
                "basic": {"known": 400, "total": 500, "percent": 80.0},
            }},
            {},
        )
        rendered = _render(panel)
        assert "mastery" in rendered

    def test_grammar_mastery_integrated(self):
        mastery = {
            "Present tense - regular verbs": {
                "avg_score": 90,
                "mastered": True,
            },
            "Ser vs Estar": {
                "avg_score": 60,
                "mastered": False,
            },
        }
        panel = create_cefr_deep_dive_panel(
            "A1",
            {"words_known": 100, "words_total": 200, "categories": {}},
            mastery,
        )
        rendered = _render(panel)
        assert "\u2713" in rendered  # mastered check
        assert "\u2717" in rendered  # needs review x


# ---------------------------------------------------------------------------
# U8: Richer stats bar
# ---------------------------------------------------------------------------


class TestRicherStatsBar:
    """Tests for create_context_bar enhancements (U8)."""

    def test_basic_context_bar(self):
        status = {
            "percent_used": 23.0,
            "input_tokens": 2300,
            "max_tokens": 10000,
        }
        bar = create_context_bar(status)
        rendered = _render(bar)
        assert "Context:" in rendered
        assert "23%" in rendered

    def test_shows_session_minutes(self):
        status = {
            "percent_used": 50.0,
            "input_tokens": 5000,
            "max_tokens": 10000,
            "session_minutes": 12,
        }
        bar = create_context_bar(status)
        rendered = _render(bar)
        assert "12 min" in rendered

    def test_shows_cards_added(self):
        status = {
            "percent_used": 50.0,
            "input_tokens": 5000,
            "max_tokens": 10000,
            "session_cards_added": 5,
        }
        bar = create_context_bar(status)
        rendered = _render(bar)
        assert "+5 cards" in rendered

    def test_shows_cefr_progress(self):
        status = {
            "percent_used": 50.0,
            "input_tokens": 5000,
            "max_tokens": 10000,
            "cefr_current_level": "A2",
            "cefr_known": 147,
            "cefr_total": 500,
        }
        bar = create_context_bar(status)
        rendered = _render(bar)
        assert "A2: 147/500" in rendered

    def test_shows_streak(self):
        status = {
            "percent_used": 50.0,
            "input_tokens": 5000,
            "max_tokens": 10000,
            "streak_days": 12,
        }
        bar = create_context_bar(status)
        rendered = _render(bar)
        assert "Streak: 12d" in rendered

    def test_all_stats_together(self):
        status = {
            "percent_used": 23.0,
            "input_tokens": 2300,
            "max_tokens": 10000,
            "session_minutes": 12,
            "session_cards_added": 5,
            "cefr_current_level": "A2",
            "cefr_known": 147,
            "cefr_total": 500,
            "streak_days": 12,
        }
        bar = create_context_bar(status)
        rendered = _render(bar)
        assert "23%" in rendered
        assert "12 min" in rendered
        assert "+5 cards" in rendered
        assert "A2: 147/500" in rendered
        assert "Streak: 12d" in rendered

    def test_returns_text(self):
        status = {
            "percent_used": 50.0,
            "input_tokens": 5000,
            "max_tokens": 10000,
        }
        bar = create_context_bar(status)
        assert isinstance(bar, Text)

    def test_no_cefr_no_streak_no_crash(self):
        status = {
            "percent_used": 10.0,
            "input_tokens": 1000,
            "max_tokens": 10000,
        }
        bar = create_context_bar(status)
        rendered = _render(bar)
        assert "Streak" not in rendered
        assert "Context:" in rendered
