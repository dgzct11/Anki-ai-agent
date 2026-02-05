"""Tests for typed learning summary dataclasses and conversion."""

import json
from unittest.mock import patch

from ankicli.learning_summary import (
    KnowledgeItem,
    LearningProgress,
    LevelData,
    get_default_progress,
    get_default_summary,
    load_progress,
    load_summary,
    save_progress,
    save_summary,
)


class TestKnowledgeItem:
    """Tests for KnowledgeItem dataclass."""

    def test_defaults(self):
        ki = KnowledgeItem()
        assert ki.summary == ""
        assert ki.vocabulary == []
        assert ki.grammar_concepts == []
        assert ki.topics_covered == []
        assert ki.vocabulary_gaps == []
        assert ki.grammar_gaps == []
        assert ki.priority_topics == []

    def test_with_values(self):
        ki = KnowledgeItem(
            summary="Knows greetings",
            vocabulary=["hola", "adios"],
            grammar_concepts=["present tense"],
        )
        assert ki.summary == "Knows greetings"
        assert len(ki.vocabulary) == 2


class TestLevelData:
    """Tests for LevelData dataclass."""

    def test_defaults(self):
        ld = LevelData()
        assert isinstance(ld.what_i_know, KnowledgeItem)
        assert isinstance(ld.what_to_learn, KnowledgeItem)
        assert ld.estimated_coverage == 0

    def test_with_coverage(self):
        ld = LevelData(estimated_coverage=50)
        assert ld.estimated_coverage == 50


class TestLearningProgress:
    """Tests for LearningProgress dataclass."""

    def test_defaults(self):
        lp = LearningProgress()
        assert lp.last_updated is None
        assert lp.total_cards_added == 0
        assert lp.levels == {}
        assert lp.recent_additions == []
        assert lp.notes == ""

    def test_to_dict_basic(self):
        lp = LearningProgress(total_cards_added=10, notes="test")
        d = lp.to_dict()
        assert d["total_cards_added"] == 10
        assert d["notes"] == "test"
        assert d["last_updated"] is None

    def test_to_dict_levels_structure(self):
        lp = LearningProgress(
            levels={
                "A1": LevelData(
                    what_i_know=KnowledgeItem(summary="knows stuff", vocabulary=["hola"]),
                    what_to_learn=KnowledgeItem(
                        summary="learn more",
                        vocabulary_gaps=["greetings"],
                        grammar_gaps=["present tense"],
                        priority_topics=["basics"],
                    ),
                    estimated_coverage=25,
                ),
            }
        )
        d = lp.to_dict()
        a1 = d["levels"]["A1"]

        # what_i_know should have vocabulary, NOT vocabulary_gaps
        assert "vocabulary" in a1["what_i_know"]
        assert "vocabulary_gaps" not in a1["what_i_know"]

        # what_to_learn should have vocabulary_gaps, NOT vocabulary
        assert "vocabulary_gaps" in a1["what_to_learn"]
        assert "vocabulary" not in a1["what_to_learn"]

        assert a1["estimated_coverage"] == 25

    def test_from_dict_roundtrip(self):
        original = LearningProgress(
            total_cards_added=42,
            notes="hello",
            recent_additions=["gato", "perro"],
            levels={
                "A1": LevelData(
                    what_i_know=KnowledgeItem(
                        summary="knows greetings",
                        vocabulary=["hola"],
                        grammar_concepts=["present tense"],
                        topics_covered=["introductions"],
                    ),
                    what_to_learn=KnowledgeItem(
                        summary="learn more",
                        vocabulary_gaps=["numbers"],
                        grammar_gaps=["ser vs estar"],
                        priority_topics=["conversation"],
                    ),
                    estimated_coverage=30,
                ),
            },
        )
        d = original.to_dict()
        restored = LearningProgress.from_dict(d)

        assert restored.total_cards_added == 42
        assert restored.notes == "hello"
        assert restored.recent_additions == ["gato", "perro"]
        assert "A1" in restored.levels
        assert restored.levels["A1"].what_i_know.summary == "knows greetings"
        assert restored.levels["A1"].what_i_know.vocabulary == ["hola"]
        assert restored.levels["A1"].what_to_learn.vocabulary_gaps == ["numbers"]
        assert restored.levels["A1"].estimated_coverage == 30

    def test_from_dict_with_existing_json_format(self):
        """Ensure we can parse the old dict-based JSON format."""
        raw = {
            "last_updated": "2025-01-01T00:00:00",
            "total_cards_added": 100,
            "levels": {
                "A1": {
                    "what_i_know": {
                        "summary": "Knows basic greetings",
                        "vocabulary": ["hola", "adios"],
                        "grammar_concepts": ["present tense"],
                        "topics_covered": ["introductions"],
                    },
                    "what_to_learn": {
                        "summary": "Need numbers",
                        "vocabulary_gaps": ["numbers"],
                        "grammar_gaps": ["ser vs estar"],
                        "priority_topics": ["conversation"],
                    },
                    "estimated_coverage": 35,
                },
            },
            "recent_additions": ["hola"],
            "notes": "test",
        }
        progress = LearningProgress.from_dict(raw)
        assert progress.total_cards_added == 100
        assert progress.last_updated == "2025-01-01T00:00:00"
        assert progress.levels["A1"].estimated_coverage == 35
        assert progress.levels["A1"].what_i_know.vocabulary == ["hola", "adios"]
        assert progress.levels["A1"].what_to_learn.vocabulary_gaps == ["numbers"]

    def test_from_dict_missing_fields(self):
        """Gracefully handle missing fields in JSON."""
        raw = {"total_cards_added": 5}
        progress = LearningProgress.from_dict(raw)
        assert progress.total_cards_added == 5
        assert progress.levels == {}
        assert progress.recent_additions == []


class TestGetDefaultProgress:
    """Tests for get_default_progress."""

    def test_has_all_levels(self):
        progress = get_default_progress()
        assert "A1" in progress.levels
        assert "A2" in progress.levels
        assert "B1" in progress.levels
        assert "B2" in progress.levels

    def test_levels_have_defaults(self):
        progress = get_default_progress()
        for level in ["A1", "A2", "B1", "B2"]:
            ld = progress.levels[level]
            assert ld.estimated_coverage == 0
            assert ld.what_i_know.summary == ""
            assert ld.what_i_know.vocabulary == []
            assert ld.what_to_learn.summary != ""  # Defaults have content
            assert len(ld.what_to_learn.vocabulary_gaps) > 0

    def test_to_dict_matches_get_default_summary(self):
        """The typed default should produce the same dict as the old default."""
        progress = get_default_progress()
        d = progress.to_dict()
        old = get_default_summary()

        # Compare structure (ignoring daily_activity which typed version includes)
        for level in ["A1", "A2", "B1", "B2"]:
            assert d["levels"][level]["estimated_coverage"] == old["levels"][level]["estimated_coverage"]
            assert d["levels"][level]["what_i_know"]["summary"] == old["levels"][level]["what_i_know"]["summary"]
            assert d["levels"][level]["what_to_learn"]["summary"] == old["levels"][level]["what_to_learn"]["summary"]
            assert d["levels"][level]["what_to_learn"]["vocabulary_gaps"] == old["levels"][level]["what_to_learn"]["vocabulary_gaps"]


def _patch_summary_paths(tmp_path):
    """Create patches for learning_summary module paths."""
    data_dir = tmp_path / ".ankicli"
    summary_file = data_dir / "learning_summary.json"
    return (
        patch("ankicli.learning_summary.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
        patch("ankicli.learning_summary.SUMMARY_FILE", summary_file),
        summary_file,
    )


class TestTypedPersistence:
    """Tests for typed load_progress / save_progress."""

    def test_save_and_load_typed(self, tmp_path):
        p1, p2, sf = _patch_summary_paths(tmp_path)
        with p1, p2:
            progress = get_default_progress()
            progress.total_cards_added = 42
            progress.levels["A1"].estimated_coverage = 35
            progress.levels["A1"].what_i_know.vocabulary = ["hola", "adios"]
            save_progress(progress)

            loaded = load_progress()
            assert loaded.total_cards_added == 42
            assert loaded.levels["A1"].estimated_coverage == 35
            assert loaded.levels["A1"].what_i_know.vocabulary == ["hola", "adios"]
            assert loaded.last_updated is not None

    def test_load_progress_returns_defaults_if_missing(self, tmp_path):
        p1, p2, sf = _patch_summary_paths(tmp_path)
        with p1, p2:
            progress = load_progress()
            assert progress.total_cards_added == 0
            assert "A1" in progress.levels

    def test_load_progress_handles_corrupt_json(self, tmp_path):
        p1, p2, sf = _patch_summary_paths(tmp_path)
        with p1, p2:
            sf.parent.mkdir(parents=True, exist_ok=True)
            sf.write_text("{not valid json")
            progress = load_progress()
            assert progress.total_cards_added == 0

    def test_backward_compat_dict_functions_still_work(self, tmp_path):
        """Ensure the old dict-based save_summary/load_summary still work."""
        p1, p2, sf = _patch_summary_paths(tmp_path)
        with p1, p2:
            # Save with typed
            progress = get_default_progress()
            progress.total_cards_added = 99
            save_progress(progress)

            # Load with dict-based
            summary = load_summary()
            assert summary["total_cards_added"] == 99

    def test_dict_save_typed_load(self, tmp_path):
        """Save with dict, load with typed."""
        p1, p2, sf = _patch_summary_paths(tmp_path)
        with p1, p2:
            summary = get_default_summary()
            summary["total_cards_added"] = 55
            save_summary(summary)

            progress = load_progress()
            assert progress.total_cards_added == 55
            assert "A1" in progress.levels

    def test_json_on_disk_matches_expected_format(self, tmp_path):
        """Verify that what we write to disk is valid and has expected structure."""
        p1, p2, sf = _patch_summary_paths(tmp_path)
        with p1, p2:
            progress = get_default_progress()
            progress.total_cards_added = 10
            save_progress(progress)

            raw = json.loads(sf.read_text())
            assert raw["total_cards_added"] == 10
            assert "levels" in raw
            assert "what_i_know" in raw["levels"]["A1"]
            assert "what_to_learn" in raw["levels"]["A1"]
            # Verify the clean dict format
            assert "vocabulary" in raw["levels"]["A1"]["what_i_know"]
            assert "vocabulary_gaps" in raw["levels"]["A1"]["what_to_learn"]
