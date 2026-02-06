"""Tests for grammar_quiz module."""

import json
from unittest.mock import patch

from ankicli.grammar_quiz import (
    GRAMMAR_TOPICS,
    MASTERY_THRESHOLD,
    QUESTION_TYPE_LABELS,
    QuestionType,
    QuizAnswer,
    QuizQuestion,
    QuizResult,
    QuizSession,
    build_grading_prompt,
    build_quiz_generation_prompt,
    get_quiz_history,
    get_topic_mastery,
    load_quiz_data,
    parse_quiz_questions,
    record_quiz_result,
    save_quiz_data,
)


class TestQuestionType:
    """Tests for QuestionType enum."""

    def test_values(self):
        assert QuestionType.FILL_IN_BLANK == "fill_in_blank"
        assert QuestionType.MULTIPLE_CHOICE == "multiple_choice"
        assert QuestionType.CONJUGATION == "conjugation"
        assert QuestionType.ERROR_CORRECTION == "error_correction"
        assert QuestionType.SENTENCE_TRANSFORMATION == "sentence_transformation"

    def test_all_types_have_labels(self):
        for qt in QuestionType:
            assert qt in QUESTION_TYPE_LABELS


class TestQuizQuestion:
    """Tests for QuizQuestion dataclass."""

    def test_defaults(self):
        q = QuizQuestion(
            question_text="Test?",
            question_type="fill_in_blank",
            correct_answer="answer",
            grammar_topic="topic",
            cefr_level="A1",
        )
        assert q.options == []
        assert q.hint == ""
        assert q.instruction == ""

    def test_to_dict(self):
        q = QuizQuestion(
            question_text="Test?",
            question_type="fill_in_blank",
            correct_answer="answer",
            grammar_topic="topic",
            cefr_level="A1",
        )
        d = q.to_dict()
        assert d["question_text"] == "Test?"
        assert d["correct_answer"] == "answer"

    def test_from_dict(self):
        data = {
            "question_text": "Test?",
            "question_type": "fill_in_blank",
            "correct_answer": "answer",
            "grammar_topic": "topic",
            "cefr_level": "A1",
            "options": ["A", "B"],
            "hint": "hint",
            "instruction": "instr",
        }
        q = QuizQuestion.from_dict(data)
        assert q.question_text == "Test?"
        assert q.options == ["A", "B"]

    def test_from_dict_ignores_extra_keys(self):
        data = {
            "question_text": "Test?",
            "question_type": "fill_in_blank",
            "correct_answer": "answer",
            "grammar_topic": "topic",
            "cefr_level": "A1",
            "extra_field": "should be ignored",
        }
        q = QuizQuestion.from_dict(data)
        assert q.question_text == "Test?"


class TestQuizSession:
    """Tests for QuizSession dataclass."""

    def _make_question(self, topic="topic") -> QuizQuestion:
        return QuizQuestion(
            question_text="Q?",
            question_type="fill_in_blank",
            correct_answer="answer",
            grammar_topic=topic,
            cefr_level="A1",
        )

    def _make_answer(self, q, correct=True) -> QuizAnswer:
        return QuizAnswer(
            question=q,
            user_answer="answer" if correct else "wrong",
            correct=correct,
            feedback="Good" if correct else "Bad",
            score=1.0 if correct else 0.0,
        )

    def test_initial_state(self):
        session = QuizSession(topic="topic", cefr_level="A1")
        assert session.total_questions == 0
        assert session.is_complete is True  # no questions = complete
        assert session.current_question is None
        assert session.score == 0.0

    def test_with_questions(self):
        q1, q2 = self._make_question(), self._make_question()
        session = QuizSession(
            topic="topic", cefr_level="A1",
            questions=[q1, q2],
        )
        assert session.total_questions == 2
        assert session.is_complete is False
        assert session.current_question is q1

    def test_correct_count(self):
        q1, q2, q3 = [self._make_question() for _ in range(3)]
        session = QuizSession(topic="topic", cefr_level="A1", questions=[q1, q2, q3])
        session.answers = [
            self._make_answer(q1, correct=True),
            self._make_answer(q2, correct=False),
            self._make_answer(q3, correct=True),
        ]
        session.current_index = 3
        assert session.correct_count == 2

    def test_score(self):
        q1, q2 = self._make_question(), self._make_question()
        session = QuizSession(topic="topic", cefr_level="A1", questions=[q1, q2])
        session.answers = [
            self._make_answer(q1, correct=True),
            self._make_answer(q2, correct=False),
        ]
        # 1 correct out of 2 = (1.0 + 0.0) / 2 * 100 = 50.0
        assert session.score == 50.0

    def test_score_by_type(self):
        q1 = QuizQuestion(
            question_text="Q?", question_type="fill_in_blank",
            correct_answer="a", grammar_topic="t", cefr_level="A1",
        )
        q2 = QuizQuestion(
            question_text="Q?", question_type="multiple_choice",
            correct_answer="b", grammar_topic="t", cefr_level="A1",
        )
        session = QuizSession(topic="t", cefr_level="A1", questions=[q1, q2])
        session.answers = [
            self._make_answer(q1, correct=True),
            self._make_answer(q2, correct=False),
        ]
        by_type = session.score_by_type()
        assert by_type["fill_in_blank"]["correct"] == 1
        assert by_type["multiple_choice"]["correct"] == 0

    def test_weak_areas(self):
        q1 = self._make_question(topic="ser_vs_estar")
        q2 = self._make_question(topic="preterite")
        session = QuizSession(topic="mix", cefr_level="A1", questions=[q1, q2])
        session.answers = [
            self._make_answer(q1, correct=True),
            self._make_answer(q2, correct=False),
        ]
        weak = session.weak_areas()
        assert "preterite" in weak
        assert "ser_vs_estar" not in weak

    def test_started_at_is_set(self):
        session = QuizSession(topic="topic", cefr_level="A1")
        assert session.started_at is not None
        assert len(session.started_at) > 0


class TestQuizResult:
    """Tests for QuizResult dataclass."""

    def test_from_session(self):
        q = QuizQuestion(
            question_text="Q?", question_type="fill_in_blank",
            correct_answer="a", grammar_topic="topic", cefr_level="A1",
        )
        session = QuizSession(topic="topic", cefr_level="A1", questions=[q])
        session.answers = [QuizAnswer(
            question=q, user_answer="a", correct=True,
            feedback="OK", score=1.0,
        )]
        session.current_index = 1

        result = QuizResult.from_session(session)
        assert result.topic == "topic"
        assert result.cefr_level == "A1"
        assert result.questions_attempted == 1
        assert result.correct == 1
        assert result.score == 100.0
        assert result.completed_at is not None

    def test_to_dict(self):
        result = QuizResult(
            topic="topic", cefr_level="A1",
            questions_attempted=5, correct=3,
            score=60.0, weak_areas=["ser_vs_estar"],
            question_type_breakdown={},
        )
        d = result.to_dict()
        assert d["topic"] == "topic"
        assert d["score"] == 60.0


class TestGrammarTopics:
    """Tests for GRAMMAR_TOPICS dict."""

    def test_has_expected_levels(self):
        assert "A1" in GRAMMAR_TOPICS
        assert "A2" in GRAMMAR_TOPICS
        assert "B1" in GRAMMAR_TOPICS
        assert "B2" in GRAMMAR_TOPICS

    def test_topics_are_nonempty(self):
        for level, topics in GRAMMAR_TOPICS.items():
            assert len(topics) > 0, f"{level} has no topics"
            for topic in topics:
                assert isinstance(topic, str)
                assert len(topic) > 0


class TestPersistence:
    """Tests for load/save quiz data."""

    def _patch_quiz_paths(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        quiz_file = data_dir / "grammar_quiz_data.json"
        return (
            patch("ankicli.grammar_quiz.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
            patch("ankicli.grammar_quiz.QUIZ_DATA_FILE", quiz_file),
        )

    def test_load_empty(self, tmp_path):
        p1, p2 = self._patch_quiz_paths(tmp_path)
        with p1, p2:
            data = load_quiz_data()
            assert data["mastery"] == {}
            assert data["history"] == []

    def test_save_and_load(self, tmp_path):
        p1, p2 = self._patch_quiz_paths(tmp_path)
        with p1, p2:
            data = {"mastery": {"topic": {"score": 90}}, "history": []}
            save_quiz_data(data)
            loaded = load_quiz_data()
            assert loaded["mastery"]["topic"]["score"] == 90

    def test_load_handles_corrupt(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        data_dir.mkdir(parents=True)
        quiz_file = data_dir / "grammar_quiz_data.json"
        quiz_file.write_text("not json")
        with patch("ankicli.grammar_quiz.ensure_data_dir", lambda: None), \
             patch("ankicli.grammar_quiz.QUIZ_DATA_FILE", quiz_file):
            data = load_quiz_data()
            assert data["mastery"] == {}

    def test_record_quiz_result(self, tmp_path):
        p1, p2 = self._patch_quiz_paths(tmp_path)
        with p1, p2:
            result = QuizResult(
                topic="ser_vs_estar", cefr_level="A1",
                questions_attempted=5, correct=4,
                score=80.0, weak_areas=[],
                question_type_breakdown={},
            )
            mastery = record_quiz_result(result)
            assert mastery["quizzed_count"] == 1
            assert mastery["avg_score"] == 80.0
            assert mastery["mastered"] is False

    def test_record_multiple_results_running_avg(self, tmp_path):
        p1, p2 = self._patch_quiz_paths(tmp_path)
        with p1, p2:
            r1 = QuizResult(
                topic="topic", cefr_level="A1",
                questions_attempted=5, correct=4,
                score=80.0, weak_areas=[],
                question_type_breakdown={},
            )
            r2 = QuizResult(
                topic="topic", cefr_level="A1",
                questions_attempted=5, correct=5,
                score=100.0, weak_areas=[],
                question_type_breakdown={},
            )
            record_quiz_result(r1)
            mastery = record_quiz_result(r2)
            # Average of 80 and 100 = 90
            assert mastery["quizzed_count"] == 2
            assert mastery["avg_score"] == 90.0
            assert mastery["mastered"] is True  # 90 >= 85

    def test_get_topic_mastery(self, tmp_path):
        p1, p2 = self._patch_quiz_paths(tmp_path)
        with p1, p2:
            result = QuizResult(
                topic="topic", cefr_level="A1",
                questions_attempted=5, correct=5,
                score=100.0, weak_areas=[],
                question_type_breakdown={},
            )
            record_quiz_result(result)
            mastery = get_topic_mastery()
            assert "topic" in mastery

    def test_get_quiz_history(self, tmp_path):
        p1, p2 = self._patch_quiz_paths(tmp_path)
        with p1, p2:
            result = QuizResult(
                topic="topic", cefr_level="A1",
                questions_attempted=5, correct=5,
                score=100.0, weak_areas=[],
                question_type_breakdown={},
            )
            record_quiz_result(result)
            history = get_quiz_history()
            assert len(history) == 1
            assert history[0]["topic"] == "topic"

    def test_history_limit(self, tmp_path):
        p1, p2 = self._patch_quiz_paths(tmp_path)
        with p1, p2:
            for i in range(5):
                result = QuizResult(
                    topic=f"topic_{i}", cefr_level="A1",
                    questions_attempted=1, correct=1,
                    score=100.0, weak_areas=[],
                    question_type_breakdown={},
                )
                record_quiz_result(result)
            history = get_quiz_history(limit=3)
            assert len(history) == 3


class TestParseQuizQuestions:
    """Tests for parse_quiz_questions."""

    def test_parse_json_array(self):
        response = json.dumps([{
            "question_text": "Ayer yo _____ (ir) al mercado.",
            "question_type": "fill_in_blank",
            "correct_answer": "fui",
            "grammar_topic": "preterite",
            "cefr_level": "A2",
            "options": [],
            "hint": "preterite of ir",
            "instruction": "Fill in the blank",
        }])
        questions = parse_quiz_questions(response)
        assert len(questions) == 1
        assert questions[0].correct_answer == "fui"

    def test_parse_markdown_wrapped(self):
        response = '```json\n[{"question_text": "Q?", "question_type": "fill_in_blank", "correct_answer": "a", "grammar_topic": "t", "cefr_level": "A1"}]\n```'
        questions = parse_quiz_questions(response)
        assert len(questions) == 1

    def test_parse_code_block_wrapped(self):
        response = '```\n[{"question_text": "Q?", "question_type": "fill_in_blank", "correct_answer": "a", "grammar_topic": "t", "cefr_level": "A1"}]\n```'
        questions = parse_quiz_questions(response)
        assert len(questions) == 1

    def test_parse_with_surrounding_text(self):
        response = 'Here are the questions:\n[{"question_text": "Q?", "question_type": "fill_in_blank", "correct_answer": "a", "grammar_topic": "t", "cefr_level": "A1"}]\nDone!'
        questions = parse_quiz_questions(response)
        assert len(questions) == 1

    def test_parse_no_json_raises(self):
        import pytest
        with pytest.raises(ValueError, match="No JSON array"):
            parse_quiz_questions("No JSON here")

    def test_parse_fills_defaults(self):
        response = json.dumps([{
            "question_text": "Q?",
            "question_type": "",
            "correct_answer": "a",
            "grammar_topic": "t",
            "cefr_level": "A1",
        }])
        questions = parse_quiz_questions(response)
        assert len(questions) == 1
        assert questions[0].question_type == ""
        assert questions[0].options == []

    def test_parse_skips_empty_question_text(self):
        """Fix #38: Questions with empty question_text are skipped."""
        response = json.dumps([
            {"question_text": "", "correct_answer": "a", "grammar_topic": "t", "cefr_level": "A1"},
            {"question_text": "Q?", "correct_answer": "b", "grammar_topic": "t", "cefr_level": "A1"},
        ])
        questions = parse_quiz_questions(response)
        assert len(questions) == 1
        assert questions[0].correct_answer == "b"

    def test_parse_skips_empty_correct_answer(self):
        """Fix #38: Questions with empty correct_answer are skipped."""
        response = json.dumps([
            {"question_text": "Q?", "correct_answer": "", "grammar_topic": "t", "cefr_level": "A1"},
            {"question_text": "Q2?", "correct_answer": "b", "grammar_topic": "t", "cefr_level": "A1"},
        ])
        questions = parse_quiz_questions(response)
        assert len(questions) == 1
        assert questions[0].question_text == "Q2?"

    def test_parse_skips_whitespace_only_fields(self):
        """Fix #38: Questions with whitespace-only required fields are skipped."""
        response = json.dumps([
            {"question_text": "  ", "correct_answer": "a", "grammar_topic": "t", "cefr_level": "A1"},
        ])
        questions = parse_quiz_questions(response)
        assert len(questions) == 0


class TestBuildPrompts:
    """Tests for prompt building functions."""

    def test_build_quiz_generation_prompt(self):
        prompt = build_quiz_generation_prompt(
            topic="Ser vs Estar",
            cefr_level="A1",
            count=5,
        )
        assert "Ser vs Estar" in prompt
        assert "A1" in prompt
        assert "5" in prompt
        assert "JSON" in prompt

    def test_build_quiz_generation_prompt_with_vocab(self):
        prompt = build_quiz_generation_prompt(
            topic="Preterite",
            cefr_level="A2",
            count=3,
            known_vocabulary=["hablar", "comer", "vivir"],
        )
        assert "hablar" in prompt

    def test_build_quiz_generation_prompt_custom_types(self):
        prompt = build_quiz_generation_prompt(
            topic="topic",
            cefr_level="A1",
            count=3,
            question_types=["fill_in_blank", "multiple_choice"],
        )
        assert "Fill-in-the-blank" in prompt
        assert "Multiple choice" in prompt

    def test_build_grading_prompt(self):
        q = QuizQuestion(
            question_text="Ayer yo _____ (ir)",
            question_type="fill_in_blank",
            correct_answer="fui",
            grammar_topic="preterite",
            cefr_level="A2",
        )
        prompt = build_grading_prompt(q, "fui")
        assert "fui" in prompt
        assert "fill_in_blank" in prompt
        assert "JSON" in prompt


class TestMasteryThreshold:
    """Tests for mastery threshold constant."""

    def test_threshold_value(self):
        assert MASTERY_THRESHOLD == 85.0
