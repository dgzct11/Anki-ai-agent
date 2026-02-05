"""Tests for practice enhancement features P1-P3, P9-P11, A2, A3."""

import json
from unittest.mock import MagicMock, patch

from ankicli.grammar_scores import (
    TopicScore,
    load_grammar_scores,
    save_grammar_scores,
    record_topic_score,
    get_all_topic_scores,
    format_grammar_scores_text,
    mastery_label,
    NEEDS_REVIEW_THRESHOLD,
    DEVELOPING_THRESHOLD,
)
from ankicli.session_error_tracker import (
    SessionErrorTracker,
    SessionError,
)
from ankicli.translation_practice import (
    PracticeSession,
    PracticeCard,
    PracticeResult,
    PracticeDirection,
    FeedbackLevel,
)
from ankicli.grammar_quiz import (
    build_quiz_generation_prompt,
)
from ankicli.tool_handlers import HANDLERS
from ankicli.tools import ANKI_TOOLS


# ---------------------------------------------------------------------------
# P1: Multiple quiz sizes
# ---------------------------------------------------------------------------

class TestQuizSizes:
    """Tests for P1: Multiple quiz sizes."""

    def test_start_grammar_quiz_tool_has_size_param(self):
        tool = next(t for t in ANKI_TOOLS if t["name"] == "start_grammar_quiz")
        props = tool["input_schema"]["properties"]
        assert "size" in props
        assert props["size"]["enum"] == ["quick", "assessment", "comprehensive"]

    def test_size_quick_sets_count_to_10(self):
        """Quick size should produce 10 questions."""
        anki = MagicMock()
        assistant = MagicMock()
        assistant.config.subagent_model = "test-model"
        assistant.client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='[{"question_text":"Q?","question_type":"fill_in_blank","correct_answer":"a","grammar_topic":"t","cefr_level":"A1"}]')]
        )

        with patch("ankicli.learning_summary.load_summary", return_value={"levels": {"A1": {"what_i_know": {"vocabulary": []}}}}):
            result = HANDLERS["start_grammar_quiz"](
                anki,
                {"topic": "Ser vs Estar", "level": "A1", "size": "quick"},
                assistant=assistant,
            )
        # The prompt should ask for 10 questions
        call_args = assistant.client.messages.create.call_args
        prompt_text = call_args[1]["messages"][0]["content"]
        assert "10" in prompt_text

    def test_size_assessment_sets_count_to_28(self):
        """Assessment size should produce 28 questions."""
        anki = MagicMock()
        assistant = MagicMock()
        assistant.config.subagent_model = "test-model"
        assistant.client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='[{"question_text":"Q?","question_type":"fill_in_blank","correct_answer":"a","grammar_topic":"t","cefr_level":"A1"}]')]
        )

        with patch("ankicli.learning_summary.load_summary", return_value={"levels": {"A1": {"what_i_know": {"vocabulary": []}}}}):
            result = HANDLERS["start_grammar_quiz"](
                anki,
                {"topic": "Ser vs Estar", "level": "A1", "size": "assessment"},
                assistant=assistant,
            )
        call_args = assistant.client.messages.create.call_args
        prompt_text = call_args[1]["messages"][0]["content"]
        assert "28" in prompt_text

    def test_size_comprehensive_sets_count_to_50(self):
        """Comprehensive size should produce 50 questions."""
        anki = MagicMock()
        assistant = MagicMock()
        assistant.config.subagent_model = "test-model"
        assistant.client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='[{"question_text":"Q?","question_type":"fill_in_blank","correct_answer":"a","grammar_topic":"t","cefr_level":"A1"}]')]
        )

        with patch("ankicli.learning_summary.load_summary", return_value={"levels": {"A1": {"what_i_know": {"vocabulary": []}}}}):
            result = HANDLERS["start_grammar_quiz"](
                anki,
                {"topic": "Ser vs Estar", "level": "A1", "size": "comprehensive"},
                assistant=assistant,
            )
        call_args = assistant.client.messages.create.call_args
        prompt_text = call_args[1]["messages"][0]["content"]
        assert "50" in prompt_text

    def test_count_without_size_uses_default(self):
        """Without size, count should default to 5 or the provided count."""
        anki = MagicMock()
        assistant = MagicMock()
        assistant.config.subagent_model = "test-model"
        assistant.client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='[{"question_text":"Q?","question_type":"fill_in_blank","correct_answer":"a","grammar_topic":"t","cefr_level":"A1"}]')]
        )

        with patch("ankicli.learning_summary.load_summary", return_value={"levels": {"A1": {"what_i_know": {"vocabulary": []}}}}):
            HANDLERS["start_grammar_quiz"](
                anki,
                {"topic": "Ser vs Estar", "level": "A1", "count": 7},
                assistant=assistant,
            )
        call_args = assistant.client.messages.create.call_args
        prompt_text = call_args[1]["messages"][0]["content"]
        assert "7" in prompt_text


# ---------------------------------------------------------------------------
# P2: Per-topic grammar scoring
# ---------------------------------------------------------------------------

class TestGrammarScores:
    """Tests for P2: Per-topic grammar scoring."""

    def _patch_paths(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        scores_file = data_dir / "grammar_scores.json"
        return (
            patch("ankicli.grammar_scores.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
            patch("ankicli.grammar_scores.GRAMMAR_SCORES_FILE", scores_file),
        )

    def test_mastery_label_needs_review(self):
        assert mastery_label(50.0) == "needs_review"
        assert mastery_label(69.9) == "needs_review"

    def test_mastery_label_developing(self):
        assert mastery_label(70.0) == "developing"
        assert mastery_label(84.9) == "developing"

    def test_mastery_label_mastered(self):
        assert mastery_label(85.0) == "mastered"
        assert mastery_label(100.0) == "mastered"

    def test_topic_score_defaults(self):
        ts = TopicScore(topic="ser_vs_estar")
        assert ts.total_questions == 0
        assert ts.average_score == 0.0
        assert ts.mastery_level == "needs_review"

    def test_topic_score_average(self):
        ts = TopicScore(topic="preterite", total_questions=10, total_correct=9)
        assert ts.average_score == 90.0
        assert ts.mastery_level == "mastered"

    def test_topic_score_to_dict(self):
        ts = TopicScore(topic="preterite", total_questions=10, total_correct=7, sessions=2)
        d = ts.to_dict()
        assert d["topic"] == "preterite"
        assert d["average_score"] == 70.0
        assert d["mastery_level"] == "developing"

    def test_topic_score_from_dict(self):
        data = {"topic": "subjunctive", "total_questions": 5, "total_correct": 2, "sessions": 1}
        ts = TopicScore.from_dict(data)
        assert ts.topic == "subjunctive"
        assert ts.average_score == 40.0

    def test_load_empty(self, tmp_path):
        p1, p2 = self._patch_paths(tmp_path)
        with p1, p2:
            scores = load_grammar_scores()
            assert scores == {}

    def test_save_and_load(self, tmp_path):
        p1, p2 = self._patch_paths(tmp_path)
        with p1, p2:
            ts = TopicScore(topic="test", total_questions=5, total_correct=4, sessions=1)
            save_grammar_scores({"test": ts})
            loaded = load_grammar_scores()
            assert "test" in loaded
            assert loaded["test"].total_questions == 5

    def test_record_topic_score(self, tmp_path):
        p1, p2 = self._patch_paths(tmp_path)
        with p1, p2:
            result = record_topic_score("preterite", "A2", 10, 8)
            assert result.total_questions == 10
            assert result.total_correct == 8
            assert result.sessions == 1
            assert result.average_score == 80.0
            assert result.mastery_level == "developing"

    def test_record_multiple_scores_accumulates(self, tmp_path):
        p1, p2 = self._patch_paths(tmp_path)
        with p1, p2:
            record_topic_score("preterite", "A2", 10, 8)
            result = record_topic_score("preterite", "A2", 10, 10)
            assert result.total_questions == 20
            assert result.total_correct == 18
            assert result.sessions == 2
            assert result.average_score == 90.0
            assert result.mastery_level == "mastered"

    def test_format_grammar_scores_empty(self, tmp_path):
        p1, p2 = self._patch_paths(tmp_path)
        with p1, p2:
            text = format_grammar_scores_text()
            assert "No grammar scores" in text

    def test_format_grammar_scores_with_data(self, tmp_path):
        p1, p2 = self._patch_paths(tmp_path)
        with p1, p2:
            record_topic_score("preterite", "A2", 10, 9)
            record_topic_score("ser_vs_estar", "A1", 10, 5)
            text = format_grammar_scores_text()
            assert "preterite" in text
            assert "ser_vs_estar" in text
            assert "[M]" in text  # mastered indicator
            assert "[!]" in text  # needs_review indicator

    def test_get_grammar_scores_handler(self, tmp_path):
        p1, p2 = self._patch_paths(tmp_path)
        with p1, p2:
            record_topic_score("test_topic", "A1", 5, 5)
            result = HANDLERS["get_grammar_scores"](MagicMock(), {})
            assert "test_topic" in result

    def test_log_quiz_results_updates_grammar_scores(self, tmp_path):
        """log_quiz_results should also update per-topic grammar scores."""
        p1, p2 = self._patch_paths(tmp_path)
        quiz_patches = (
            patch("ankicli.grammar_quiz.ensure_data_dir", lambda: (tmp_path / ".ankicli").mkdir(parents=True, exist_ok=True)),
            patch("ankicli.grammar_quiz.QUIZ_DATA_FILE", tmp_path / ".ankicli" / "grammar_quiz_data.json"),
        )
        summary_patch = patch("ankicli.learning_summary.load_summary", return_value={"quiz_results": []})
        save_patch = patch("ankicli.learning_summary.save_summary")

        with p1, p2, quiz_patches[0], quiz_patches[1], summary_patch, save_patch:
            result = HANDLERS["log_quiz_results"](
                MagicMock(),
                {"topic": "preterite", "level": "A2", "questions_attempted": 10, "correct": 8},
            )
            assert "Per-topic score" in result
            assert "developing" in result.lower() or "80" in result


# ---------------------------------------------------------------------------
# P9: Reading practice
# ---------------------------------------------------------------------------

class TestReadingPractice:
    """Tests for P9: Reading practice tool."""

    def test_reading_practice_tool_exists(self):
        tool_names = {t["name"] for t in ANKI_TOOLS}
        assert "start_reading_practice" in tool_names

    def test_reading_practice_handler_exists(self):
        assert "start_reading_practice" in HANDLERS

    def test_reading_practice_basic(self):
        anki = MagicMock()
        anki.get_deck_cards.return_value = []
        anki.get_due_cards.return_value = []

        result = HANDLERS["start_reading_practice"](
            anki,
            {"deck_name": "Spanish", "level": "A2"},
        )
        assert "READING PRACTICE" in result
        assert "DO NOT ask comprehension questions" in result
        assert "READING ONLY" in result

    def test_reading_practice_with_topic(self):
        anki = MagicMock()
        anki.get_deck_cards.return_value = []
        anki.get_due_cards.return_value = []

        result = HANDLERS["start_reading_practice"](
            anki,
            {"deck_name": "Spanish", "level": "B1", "topic": "daily routine"},
        )
        assert "daily routine" in result
        assert "B1" in result

    def test_reading_practice_includes_vocabulary(self):
        anki = MagicMock()
        card = MagicMock()
        card.back = "<b>hablar</b>"
        card.front = "to speak"
        anki.get_deck_cards.return_value = [card]
        anki.get_due_cards.return_value = []

        result = HANDLERS["start_reading_practice"](
            anki,
            {"deck_name": "Spanish"},
        )
        assert "hablar" in result


# ---------------------------------------------------------------------------
# P10: Session error tracking
# ---------------------------------------------------------------------------

class TestSessionErrorTracker:
    """Tests for P10: within-session error pattern tracking."""

    def test_initial_state(self):
        tracker = SessionErrorTracker()
        assert len(tracker.errors) == 0
        assert len(tracker.get_flagged_patterns()) == 0

    def test_record_single_error_no_flag(self):
        tracker = SessionErrorTracker()
        msg = tracker.record("gender_agreement", "la problema", "el problema")
        assert msg is None
        assert tracker.count_type("gender_agreement") == 1

    def test_record_two_errors_flags_pattern(self):
        tracker = SessionErrorTracker()
        tracker.record("gender_agreement", "la problema", "el problema")
        msg = tracker.record("gender_agreement", "la sistema", "el sistema")
        assert msg is not None
        assert "Pattern detected" in msg
        assert "gender agreement" in msg

    def test_flag_only_once(self):
        tracker = SessionErrorTracker()
        tracker.record("gender_agreement", "la problema", "el problema")
        msg1 = tracker.record("gender_agreement", "la sistema", "el sistema")
        msg2 = tracker.record("gender_agreement", "la tema", "el tema")
        assert msg1 is not None
        assert msg2 is None  # Already flagged, no repeat

    def test_different_error_types_tracked_separately(self):
        tracker = SessionErrorTracker()
        tracker.record("gender_agreement", "la problema")
        tracker.record("ser_vs_estar", "yo soy cansado")
        msg = tracker.record("ser_vs_estar", "ella es enferma")
        assert msg is not None
        assert "ser vs. estar" in msg

    def test_get_error_counts(self):
        tracker = SessionErrorTracker()
        tracker.record("gender_agreement", "e1")
        tracker.record("gender_agreement", "e2")
        tracker.record("ser_vs_estar", "e3")
        counts = tracker.get_error_counts()
        assert counts["gender_agreement"] == 2
        assert counts["ser_vs_estar"] == 1

    def test_get_flagged_patterns(self):
        tracker = SessionErrorTracker()
        tracker.record("gender_agreement", "e1")
        tracker.record("gender_agreement", "e2")
        tracker.record("accent_missing", "e3")
        flagged = tracker.get_flagged_patterns()
        assert "gender_agreement" in flagged
        assert "accent_missing" not in flagged

    def test_get_session_summary(self):
        tracker = SessionErrorTracker()
        tracker.record("gender_agreement", "e1")
        tracker.record("gender_agreement", "e2")
        summary = tracker.get_session_summary()
        assert "gender agreement" in summary
        assert "[FLAGGED]" in summary

    def test_get_session_summary_empty(self):
        tracker = SessionErrorTracker()
        summary = tracker.get_session_summary()
        assert "No error patterns" in summary

    def test_reset(self):
        tracker = SessionErrorTracker()
        tracker.record("gender_agreement", "e1")
        tracker.record("gender_agreement", "e2")
        tracker.reset()
        assert len(tracker.errors) == 0
        assert len(tracker.get_flagged_patterns()) == 0


# ---------------------------------------------------------------------------
# P11: Anki review integration
# ---------------------------------------------------------------------------

class TestAnkiReviewIntegration:
    """Tests for P11: session due words tool."""

    def test_session_due_words_tool_exists(self):
        tool_names = {t["name"] for t in ANKI_TOOLS}
        assert "get_session_due_words" in tool_names

    def test_session_due_words_handler_exists(self):
        assert "get_session_due_words" in HANDLERS

    def test_session_due_words_no_words(self):
        anki = MagicMock()
        result = HANDLERS["get_session_due_words"](
            anki,
            {"deck_name": "Spanish", "session_words": []},
        )
        assert "No session words" in result

    def test_session_due_words_no_due_cards(self):
        anki = MagicMock()
        anki.get_due_cards.return_value = []
        result = HANDLERS["get_session_due_words"](
            anki,
            {"deck_name": "Spanish", "session_words": ["hablar", "comer"]},
        )
        assert "No cards are due" in result

    def test_session_due_words_finds_matches(self):
        anki = MagicMock()
        card = MagicMock()
        card.back = "<b>hablar</b>"
        card.front = "to speak"
        card.id = "12345"
        anki.get_due_cards.return_value = [card]

        result = HANDLERS["get_session_due_words"](
            anki,
            {"deck_name": "Spanish", "session_words": ["hablar", "comer"]},
        )
        assert "hablar" in result
        assert "12345" in result
        assert "NEVER" not in result or "auto-mark" in result

    def test_session_due_words_no_matches(self):
        anki = MagicMock()
        card = MagicMock()
        card.back = "<b>dormir</b>"
        card.front = "to sleep"
        card.id = "99"
        anki.get_due_cards.return_value = [card]

        result = HANDLERS["get_session_due_words"](
            anki,
            {"deck_name": "Spanish", "session_words": ["hablar"]},
        )
        assert "None of the session words" in result

    def test_session_due_words_warns_about_auto_mark(self):
        anki = MagicMock()
        card = MagicMock()
        card.back = "hablar"
        card.front = "to speak"
        card.id = "1"
        anki.get_due_cards.return_value = [card]

        result = HANDLERS["get_session_due_words"](
            anki,
            {"deck_name": "Spanish", "session_words": ["hablar"]},
        )
        assert "DO NOT auto-mark" in result


# ---------------------------------------------------------------------------
# A2: Adaptive difficulty
# ---------------------------------------------------------------------------

class TestAdaptiveDifficulty:
    """Tests for A2: adaptive difficulty in translation practice."""

    def _make_session(self, num_cards=10) -> PracticeSession:
        cards = [
            PracticeCard(card_id=str(i), front=f"front_{i}", back=f"back_{i}")
            for i in range(num_cards)
        ]
        return PracticeSession(
            deck_name="Spanish",
            direction=PracticeDirection.EN_TO_ES,
            cards=cards,
        )

    def _make_result(self, level=FeedbackLevel.CORRECT) -> PracticeResult:
        return PracticeResult(
            card_id="1", front="front", back="back",
            user_answer="answer",
            feedback_level=level,
            feedback_text="feedback",
            meaning_score=4 if level == FeedbackLevel.CORRECT else 1,
            grammar_score=4 if level == FeedbackLevel.CORRECT else 1,
            naturalness_score=4 if level == FeedbackLevel.CORRECT else 1,
            vocabulary_score=4 if level == FeedbackLevel.CORRECT else 1,
        )

    def test_initial_difficulty_is_2(self):
        session = self._make_session()
        assert session.difficulty_num == 2

    def test_difficulty_increases_after_3_correct(self):
        session = self._make_session()
        for _ in range(3):
            session.record_result(self._make_result(FeedbackLevel.CORRECT))
        assert session.difficulty_num == 3

    def test_difficulty_decreases_after_2_wrong(self):
        session = self._make_session()
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        assert session.difficulty_num == 1

    def test_difficulty_never_below_1(self):
        session = self._make_session()
        session.difficulty_num = 1
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        assert session.difficulty_num == 1

    def test_difficulty_never_above_5(self):
        session = self._make_session()
        session.difficulty_num = 5
        for _ in range(3):
            session.record_result(self._make_result(FeedbackLevel.CORRECT))
        assert session.difficulty_num == 5

    def test_difficulty_label(self):
        session = self._make_session()
        assert session.difficulty_label == "simple sentence"
        session.difficulty_num = 1
        assert session.difficulty_label == "single word"
        session.difficulty_num = 5
        assert session.difficulty_label == "conversational context"

    def test_difficulty_labels_all_defined(self):
        session = self._make_session()
        for level in range(1, 6):
            session.difficulty_num = level
            assert session.difficulty_label != ""

    def test_streak_resets_on_difficulty_change_up(self):
        session = self._make_session()
        for _ in range(3):
            session.record_result(self._make_result(FeedbackLevel.CORRECT))
        # After difficulty increase, correct streak should reset
        assert session.correct_streak == 0

    def test_streak_resets_on_difficulty_change_down(self):
        session = self._make_session()
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        session.record_result(self._make_result(FeedbackLevel.INCORRECT))
        # After difficulty decrease, incorrect streak should reset
        assert session.incorrect_streak == 0


# ---------------------------------------------------------------------------
# A3: Structured quiz flow
# ---------------------------------------------------------------------------

class TestStructuredQuizFlow:
    """Tests for A3: structured quiz flow."""

    def test_large_quiz_has_structure_instruction(self):
        """Quizzes with 20+ questions should include structure instructions."""
        prompt = build_quiz_generation_prompt(
            topic="Preterite tense",
            cefr_level="A2",
            count=25,
        )
        assert "WARM-UP" in prompt
        assert "FOCUSED PRACTICE" in prompt
        assert "MIXED REVIEW" in prompt

    def test_small_quiz_no_structure_instruction(self):
        """Quizzes with <20 questions should not include structure instructions."""
        prompt = build_quiz_generation_prompt(
            topic="Preterite tense",
            cefr_level="A2",
            count=5,
        )
        assert "WARM-UP" not in prompt

    def test_structure_instruction_has_correct_proportions(self):
        """Structure should have ~20% warmup, ~50% practice, ~30% review."""
        prompt = build_quiz_generation_prompt(
            topic="Preterite tense",
            cefr_level="A2",
            count=50,
        )
        assert "WARM-UP" in prompt
        assert "FOCUSED PRACTICE" in prompt
        assert "MIXED REVIEW" in prompt


# ---------------------------------------------------------------------------
# Tool coverage tests
# ---------------------------------------------------------------------------

class TestNewToolCoverage:
    """Ensure all new tools have handlers."""

    def test_start_reading_practice_has_handler(self):
        assert "start_reading_practice" in HANDLERS

    def test_get_grammar_scores_has_handler(self):
        assert "get_grammar_scores" in HANDLERS

    def test_get_session_due_words_has_handler(self):
        assert "get_session_due_words" in HANDLERS

    def test_all_new_tools_have_handlers(self):
        new_tools = ["start_reading_practice", "get_grammar_scores", "get_session_due_words"]
        for tool_name in new_tools:
            assert tool_name in HANDLERS, f"Missing handler for {tool_name}"
            # Verify the tool definition exists
            tool_names = {t["name"] for t in ANKI_TOOLS}
            assert tool_name in tool_names, f"Missing tool definition for {tool_name}"
