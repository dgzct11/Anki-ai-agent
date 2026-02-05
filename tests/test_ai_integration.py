"""Tests for AI integration features (A1, A4, A5, A6)."""

from unittest.mock import MagicMock, patch

from ankicli.assistant import (
    _PREFERENCE_DETECTION_GUIDE,
    _MICRO_LESSON_GUIDE,
    _PROMPT_SECTIONS,
    build_student_context,
    build_system_prompt,
)
from ankicli.delegate import (
    BATCH_DELEGATE_PROMPTS,
    BatchDelegateProcessor,
    BatchProgressEvent,
    BatchResult,
)
from ankicli.error_journal import ErrorEntry
from ankicli.tool_handlers import HANDLERS


# ===================================================================
# A1: Proactive preference detection
# ===================================================================

class TestPreferenceDetectionGuide:
    """Tests for the _PREFERENCE_DETECTION_GUIDE prompt section."""

    def test_guide_exists_and_not_empty(self):
        assert _PREFERENCE_DETECTION_GUIDE
        assert len(_PREFERENCE_DETECTION_GUIDE) > 100

    def test_guide_in_prompt_sections(self):
        assert _PREFERENCE_DETECTION_GUIDE in _PROMPT_SECTIONS

    def test_guide_mentions_key_concepts(self):
        assert "preference" in _PREFERENCE_DETECTION_GUIDE.lower()
        assert "set_tool_note" in _PREFERENCE_DETECTION_GUIDE
        assert "pattern" in _PREFERENCE_DETECTION_GUIDE.lower()

    def test_guide_includes_examples(self):
        assert "Card style" in _PREFERENCE_DETECTION_GUIDE or "card style" in _PREFERENCE_DETECTION_GUIDE.lower()
        assert "Language variant" in _PREFERENCE_DETECTION_GUIDE or "dialect" in _PREFERENCE_DETECTION_GUIDE.lower()

    def test_guide_included_in_system_prompt(self):
        prompt = build_system_prompt()
        assert "Proactive Preference Detection" in prompt


# ===================================================================
# A4: Level-aware context injection
# ===================================================================

class TestBuildStudentContext:
    """Tests for build_student_context function."""

    def test_returns_none_when_no_data(self):
        with patch("ankicli.cefr.load_progress_cache", return_value=None), \
             patch("ankicli.learning_summary.load_summary", return_value={
                 "levels": {}, "total_cards_added": 0
             }), \
             patch("ankicli.error_journal.get_error_patterns", return_value=[]):
            result = build_student_context()
            assert result is None

    def test_includes_cefr_levels(self):
        mock_progress = {
            "A1": MagicMock(words_total=100, words_known=80, percent=80.0),
            "A2": MagicMock(words_total=200, words_known=50, percent=25.0),
        }
        with patch("ankicli.cefr.load_progress_cache", return_value=mock_progress), \
             patch("ankicli.learning_summary.load_summary", return_value={
                 "levels": {}, "total_cards_added": 0
             }), \
             patch("ankicli.error_journal.get_error_patterns", return_value=[]):
            result = build_student_context()
            assert result is not None
            assert "A1 (80%)" in result
            assert "A2 (25%)" in result
            assert "Your Current Student" in result

    def test_includes_card_count(self):
        with patch("ankicli.cefr.load_progress_cache", return_value=None), \
             patch("ankicli.learning_summary.load_summary", return_value={
                 "levels": {}, "total_cards_added": 276,
                 "last_updated": "2026-02-04T10:00:00"
             }), \
             patch("ankicli.error_journal.get_error_patterns", return_value=[]):
            result = build_student_context()
            assert result is not None
            assert "276 cards total" in result
            assert "2026-02-04" in result

    def test_includes_strong_and_weak_areas(self):
        summary = {
            "levels": {
                "A2": {
                    "estimated_coverage": 60,
                    "what_i_know": {
                        "grammar_concepts": ["preterite", "imperfect", "reflexive verbs"],
                    },
                    "what_to_learn": {
                        "grammar_gaps": ["conditional tense", "indirect object pronouns"],
                    },
                },
            },
            "total_cards_added": 100,
        }
        with patch("ankicli.cefr.load_progress_cache", return_value=None), \
             patch("ankicli.learning_summary.load_summary", return_value=summary), \
             patch("ankicli.error_journal.get_error_patterns", return_value=[]):
            result = build_student_context()
            assert result is not None
            assert "preterite" in result
            assert "conditional tense" in result

    def test_includes_quiz_scores(self):
        summary = {
            "levels": {},
            "total_cards_added": 10,
            "quiz_results": [
                {"score": 80, "topic": "preterite"},
                {"score": 90, "topic": "ser_vs_estar"},
            ],
        }
        with patch("ankicli.cefr.load_progress_cache", return_value=None), \
             patch("ankicli.learning_summary.load_summary", return_value=summary), \
             patch("ankicli.error_journal.get_error_patterns", return_value=[]):
            result = build_student_context()
            assert result is not None
            assert "quiz avg" in result.lower()

    def test_includes_error_patterns(self):
        errors = [
            ErrorEntry(error_type="gender_agreement", count=5),
            ErrorEntry(error_type="ser_vs_estar", count=3),
        ]
        with patch("ankicli.cefr.load_progress_cache", return_value=None), \
             patch("ankicli.learning_summary.load_summary", return_value={
                 "levels": {}, "total_cards_added": 0
             }), \
             patch("ankicli.error_journal.get_error_patterns", return_value=errors):
            result = build_student_context()
            assert result is not None
            assert "gender_agreement" in result
            assert "x5" in result

    def test_injected_in_system_prompt(self):
        student_ctx = "## Your Current Student\n- Active level: A2 (50%)"
        prompt = build_system_prompt(student_context=student_ctx)
        assert "Your Current Student" in prompt
        assert "A2 (50%)" in prompt

    def test_student_context_before_preferences(self):
        student_ctx = "## Your Current Student\n- Active level: A2 (50%)"
        prompt = build_system_prompt(
            general_note="Use informal Spanish",
            student_context=student_ctx,
        )
        # Student context should appear before preferences
        ctx_pos = prompt.index("Your Current Student")
        pref_pos = prompt.index("Active User Preferences")
        assert ctx_pos < pref_pos


# ===================================================================
# A5: Micro-lesson generation
# ===================================================================

class TestMicroLessonGuide:
    """Tests for the _MICRO_LESSON_GUIDE prompt section."""

    def test_guide_exists_and_not_empty(self):
        assert _MICRO_LESSON_GUIDE
        assert len(_MICRO_LESSON_GUIDE) > 50

    def test_guide_in_prompt_sections(self):
        assert _MICRO_LESSON_GUIDE in _PROMPT_SECTIONS

    def test_guide_mentions_key_concepts(self):
        assert "generate_micro_lesson" in _MICRO_LESSON_GUIDE
        assert "3" in _MICRO_LESSON_GUIDE  # 3+ occurrences threshold
        assert "error" in _MICRO_LESSON_GUIDE.lower()

    def test_guide_included_in_system_prompt(self):
        prompt = build_system_prompt()
        assert "Micro-Lesson" in prompt


class TestGenerateMicroLessonHandler:
    """Tests for the generate_micro_lesson tool handler."""

    def test_handler_registered(self):
        assert "generate_micro_lesson" in HANDLERS

    def test_error_not_found(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        journal_file = data_dir / "error_journal.json"
        with patch("ankicli.error_journal.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)), \
             patch("ankicli.error_journal.ERROR_JOURNAL_FILE", journal_file):
            result = HANDLERS["generate_micro_lesson"](
                MagicMock(),
                {"error_type": "nonexistent_error"},
                assistant=MagicMock(),
            )
            assert "No error pattern found" in result

    def test_insufficient_occurrences(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        data_dir.mkdir(parents=True)
        journal_file = data_dir / "error_journal.json"
        import json
        journal_file.write_text(json.dumps({
            "gender_agreement": {
                "error_type": "gender_agreement",
                "count": 2,
                "examples": [{"input": "la problema", "correction": "el problema", "context": ""}],
                "last_seen": "2026-01-01",
                "first_seen": "2026-01-01",
                "tags": [],
            }
        }))
        with patch("ankicli.error_journal.ensure_data_dir", lambda: None), \
             patch("ankicli.error_journal.ERROR_JOURNAL_FILE", journal_file):
            result = HANDLERS["generate_micro_lesson"](
                MagicMock(),
                {"error_type": "gender_agreement"},
                assistant=MagicMock(),
            )
            assert "only 2 occurrence(s)" in result
            assert "3+" in result

    def test_generates_lesson_with_enough_errors(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        data_dir.mkdir(parents=True)
        journal_file = data_dir / "error_journal.json"
        import json
        journal_file.write_text(json.dumps({
            "gender_agreement": {
                "error_type": "gender_agreement",
                "count": 5,
                "examples": [
                    {"input": "la problema", "correction": "el problema", "context": "quiz"},
                    {"input": "el mano", "correction": "la mano", "context": "practice"},
                    {"input": "la sistema", "correction": "el sistema", "context": "quiz"},
                ],
                "last_seen": "2026-01-15",
                "first_seen": "2026-01-01",
                "tags": ["grammar"],
            }
        }))

        # Mock the Claude API response
        mock_assistant = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "title": "Spanish Noun Gender Agreement",
            "rule": "In Spanish, nouns have grammatical gender.",
            "examples": ["El problema es grande.", "La mano está fría.", "El sistema funciona."],
            "mistakes": [
                {"wrong": "la problema", "right": "el problema", "explanation": "Problema is masculine despite -a ending."}
            ],
            "practice": [
                {"question": "___ problema (el/la)", "answer": "el"},
                {"question": "___ mano (el/la)", "answer": "la"},
                {"question": "___ sistema (el/la)", "answer": "el"},
            ],
            "tip": "Words ending in -ma from Greek are usually masculine: problema, sistema, programa."
        }))]
        mock_assistant.client.messages.create.return_value = mock_response
        mock_assistant.config.subagent_model = "test-model"

        with patch("ankicli.error_journal.ensure_data_dir", lambda: None), \
             patch("ankicli.error_journal.ERROR_JOURNAL_FILE", journal_file):
            result = HANDLERS["generate_micro_lesson"](
                MagicMock(),
                {"error_type": "gender_agreement", "level": "A2"},
                assistant=mock_assistant,
            )
            assert "MICRO-LESSON" in result
            assert "gender_agreement" in result
            assert "seen 5x" in result
            assert "RULE:" in result
            assert "PRACTICE:" in result
            assert "ANSWER KEY" in result

    def test_no_assistant_context(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        data_dir.mkdir(parents=True)
        journal_file = data_dir / "error_journal.json"
        import json
        journal_file.write_text(json.dumps({
            "gender_agreement": {
                "error_type": "gender_agreement",
                "count": 5,
                "examples": [],
                "last_seen": "2026-01-15",
                "first_seen": "2026-01-01",
                "tags": [],
            }
        }))
        with patch("ankicli.error_journal.ensure_data_dir", lambda: None), \
             patch("ankicli.error_journal.ERROR_JOURNAL_FILE", journal_file):
            result = HANDLERS["generate_micro_lesson"](
                MagicMock(),
                {"error_type": "gender_agreement"},
            )
            assert "assistant context not available" in result


# ===================================================================
# A6: Expanded delegate system
# ===================================================================

class TestBatchDelegatePrompts:
    """Tests for the built-in batch delegate prompt templates."""

    def test_all_types_have_prompts(self):
        expected_types = ["cognate_scan", "network_update", "difficulty_score", "context_generation"]
        for dt in expected_types:
            assert dt in BATCH_DELEGATE_PROMPTS
            assert "{item}" in BATCH_DELEGATE_PROMPTS[dt]

    def test_cognate_scan_prompt(self):
        prompt = BATCH_DELEGATE_PROMPTS["cognate_scan"]
        assert "cognate" in prompt.lower()
        assert "JSON" in prompt

    def test_network_update_prompt(self):
        prompt = BATCH_DELEGATE_PROMPTS["network_update"]
        assert "synonyms" in prompt.lower()
        assert "antonyms" in prompt.lower()

    def test_difficulty_score_prompt(self):
        prompt = BATCH_DELEGATE_PROMPTS["difficulty_score"]
        assert "difficulty" in prompt.lower()
        assert "1-5" in prompt

    def test_context_generation_prompt(self):
        prompt = BATCH_DELEGATE_PROMPTS["context_generation"]
        assert "sentences" in prompt.lower()
        assert "Spanish" in prompt


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_defaults(self):
        r = BatchResult(item="hablar")
        assert r.item == "hablar"
        assert r.result is None
        assert r.raw_response == ""
        assert r.error is None

    def test_with_result(self):
        r = BatchResult(
            item="hablar",
            result={"word": "hablar", "difficulty": 2},
            raw_response='{"word": "hablar"}',
        )
        assert r.result["difficulty"] == 2
        assert r.error is None

    def test_with_error(self):
        r = BatchResult(item="hablar", error="API timeout")
        assert r.error == "API timeout"
        assert r.result is None


class TestBatchProgressEvent:
    """Tests for BatchProgressEvent dataclass."""

    def test_success(self):
        event = BatchProgressEvent(
            completed=5, total=10,
            current_item="hablar",
            success=True,
        )
        assert event.completed == 5
        assert event.total == 10
        assert event.success is True
        assert event.error is None

    def test_failure(self):
        event = BatchProgressEvent(
            completed=3, total=10,
            current_item="casa",
            success=False,
            error="Timeout",
        )
        assert event.success is False
        assert event.error == "Timeout"


class TestBatchDelegateProcessor:
    """Tests for BatchDelegateProcessor."""

    def test_max_workers_capped(self):
        client = MagicMock()
        processor = BatchDelegateProcessor(client, "model", max_workers=20)
        assert processor.max_workers == 10

    def test_max_workers_normal(self):
        client = MagicMock()
        processor = BatchDelegateProcessor(client, "model", max_workers=3)
        assert processor.max_workers == 3

    def test_process_single_item_success(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text='{"word": "hablar", "difficulty": 2, "factors": {}, "reasoning": "common verb"}')]
        client.messages.create.return_value = response

        processor = BatchDelegateProcessor(client, "test-model", rate_limit_delay=0)
        result = processor._process_single_item("hablar", "Rate: {item}")

        assert result.item == "hablar"
        assert result.result is not None
        assert result.result["word"] == "hablar"
        assert result.error is None

    def test_process_single_item_markdown_wrapped(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text='```json\n{"word": "casa", "difficulty": 1}\n```')]
        client.messages.create.return_value = response

        processor = BatchDelegateProcessor(client, "test-model", rate_limit_delay=0)
        result = processor._process_single_item("casa", "Rate: {item}")

        assert result.result is not None
        assert result.result["word"] == "casa"
        assert result.error is None

    def test_process_single_item_invalid_json(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text="not json at all")]
        client.messages.create.return_value = response

        processor = BatchDelegateProcessor(client, "test-model", rate_limit_delay=0)
        result = processor._process_single_item("hablar", "Rate: {item}")

        assert result.error is not None
        assert "No JSON object found" in result.error

    def test_process_single_item_api_error(self):
        client = MagicMock()
        client.messages.create.side_effect = Exception("Rate limit exceeded")

        processor = BatchDelegateProcessor(client, "test-model", rate_limit_delay=0)
        result = processor._process_single_item("hablar", "Rate: {item}")

        assert result.error == "Rate limit exceeded"

    def test_process_batch_empty(self):
        client = MagicMock()
        processor = BatchDelegateProcessor(client, "test-model", rate_limit_delay=0)
        results = processor.process_batch([], "cognate_scan")
        assert results == []

    def test_process_batch_unknown_type(self):
        client = MagicMock()
        processor = BatchDelegateProcessor(client, "test-model", rate_limit_delay=0)
        results = processor.process_batch(["hablar", "casa"], "nonexistent_type")
        assert len(results) == 2
        assert all(r.error is not None for r in results)
        assert "Unknown delegate type" in results[0].error

    def test_process_batch_with_progress(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text='{"word": "test", "difficulty": 1}')]
        client.messages.create.return_value = response

        processor = BatchDelegateProcessor(client, "test-model", max_workers=1, rate_limit_delay=0)

        progress_events = []
        def on_progress(event: BatchProgressEvent):
            progress_events.append(event)

        results = processor.process_batch(
            ["hablar", "casa"],
            "difficulty_score",
            progress_callback=on_progress,
        )

        assert len(results) == 2
        assert len(progress_events) == 2
        assert all(e.success for e in progress_events)
        assert all(e.total == 2 for e in progress_events)

    def test_process_batch_with_custom_prompt(self):
        client = MagicMock()
        response = MagicMock()
        response.content = [MagicMock(text='{"word": "test", "custom": true}')]
        client.messages.create.return_value = response

        processor = BatchDelegateProcessor(client, "test-model", max_workers=1, rate_limit_delay=0)
        results = processor.process_batch(
            ["hablar"],
            "cognate_scan",
            prompt_override="Custom prompt for {item}",
        )

        assert len(results) == 1
        assert results[0].error is None
        # Verify the custom prompt was used (check the API call)
        call_args = client.messages.create.call_args
        assert "Custom prompt for hablar" in call_args[1]["messages"][0]["content"]

    def test_process_batch_handles_exceptions(self):
        client = MagicMock()
        client.messages.create.side_effect = Exception("Network error")

        processor = BatchDelegateProcessor(client, "test-model", max_workers=1, rate_limit_delay=0)
        results = processor.process_batch(["hablar"], "cognate_scan")

        assert len(results) == 1
        assert results[0].error is not None


class TestBatchDelegateHandler:
    """Tests for the batch_delegate tool handler."""

    def test_handler_registered(self):
        assert "batch_delegate" in HANDLERS

    def test_empty_items(self):
        result = HANDLERS["batch_delegate"](
            MagicMock(),
            {"delegate_type": "cognate_scan", "items": []},
            assistant=MagicMock(),
        )
        assert "No items to process" in result

    def test_no_assistant_context(self):
        result = HANDLERS["batch_delegate"](
            MagicMock(),
            {"delegate_type": "cognate_scan", "items": ["hablar"]},
        )
        assert "assistant context not available" in result


# ===================================================================
# Tool definitions
# ===================================================================

class TestToolDefinitions:
    """Tests for the new tool definitions in ANKI_TOOLS."""

    def test_generate_micro_lesson_tool_exists(self):
        from ankicli.tools import ANKI_TOOLS
        names = [t["name"] for t in ANKI_TOOLS]
        assert "generate_micro_lesson" in names

    def test_generate_micro_lesson_schema(self):
        from ankicli.tools import ANKI_TOOLS
        tool = next(t for t in ANKI_TOOLS if t["name"] == "generate_micro_lesson")
        schema = tool["input_schema"]
        assert "error_type" in schema["properties"]
        assert "level" in schema["properties"]
        assert "error_type" in schema["required"]

    def test_batch_delegate_tool_exists(self):
        from ankicli.tools import ANKI_TOOLS
        names = [t["name"] for t in ANKI_TOOLS]
        assert "batch_delegate" in names

    def test_batch_delegate_schema(self):
        from ankicli.tools import ANKI_TOOLS
        tool = next(t for t in ANKI_TOOLS if t["name"] == "batch_delegate")
        schema = tool["input_schema"]
        assert "delegate_type" in schema["properties"]
        assert "items" in schema["properties"]
        assert "prompt_override" in schema["properties"]
        assert "delegate_type" in schema["required"]
        assert "items" in schema["required"]
        # Check enum values
        enums = schema["properties"]["delegate_type"]["enum"]
        assert "cognate_scan" in enums
        assert "network_update" in enums
        assert "difficulty_score" in enums
        assert "context_generation" in enums
