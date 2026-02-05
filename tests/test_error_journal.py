"""Tests for error_journal module - persistent error pattern tracking."""

from unittest.mock import patch

from ankicli.error_journal import (
    ErrorEntry,
    format_error_patterns_text,
    get_error_patterns,
    load_journal,
    log_error,
    save_journal,
)


class TestErrorEntry:
    """Tests for ErrorEntry dataclass."""

    def test_defaults(self):
        entry = ErrorEntry(error_type="gender_agreement")
        assert entry.error_type == "gender_agreement"
        assert entry.count == 0
        assert entry.examples == []
        assert entry.last_seen == ""
        assert entry.first_seen == ""
        assert entry.tags == []

    def test_to_dict(self):
        entry = ErrorEntry(
            error_type="accent_missing",
            count=3,
            examples=[{"input": "cafe", "correction": "café", "context": "quiz"}],
            last_seen="2025-01-01T12:00:00",
            first_seen="2025-01-01T10:00:00",
            tags=["spelling", "A1"],
        )
        d = entry.to_dict()
        assert d["error_type"] == "accent_missing"
        assert d["count"] == 3
        assert len(d["examples"]) == 1
        assert d["tags"] == ["spelling", "A1"]

    def test_from_dict(self):
        data = {
            "error_type": "ser_vs_estar",
            "count": 5,
            "examples": [{"input": "soy cansado", "correction": "estoy cansado", "context": "practice"}],
            "last_seen": "2025-01-02",
            "first_seen": "2025-01-01",
            "tags": ["grammar", "A2"],
        }
        entry = ErrorEntry.from_dict(data)
        assert entry.error_type == "ser_vs_estar"
        assert entry.count == 5
        assert entry.tags == ["grammar", "A2"]

    def test_from_dict_missing_fields(self):
        entry = ErrorEntry.from_dict({})
        assert entry.error_type == ""
        assert entry.count == 0
        assert entry.examples == []
        assert entry.tags == []

    def test_roundtrip(self):
        original = ErrorEntry(
            error_type="gender_agreement",
            count=2,
            examples=[{"input": "la problema", "correction": "el problema", "context": ""}],
            last_seen="2025-01-01",
            first_seen="2025-01-01",
            tags=["grammar"],
        )
        restored = ErrorEntry.from_dict(original.to_dict())
        assert restored.error_type == original.error_type
        assert restored.count == original.count
        assert restored.examples == original.examples
        assert restored.tags == original.tags


class TestPersistence:
    """Tests for load/save journal."""

    def _patch_journal(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        journal_file = data_dir / "error_journal.json"
        return (
            patch("ankicli.error_journal.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
            patch("ankicli.error_journal.ERROR_JOURNAL_FILE", journal_file),
        )

    def test_load_empty(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            journal = load_journal()
            assert journal == {}

    def test_save_and_load(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            journal = {
                "gender_agreement": ErrorEntry(
                    error_type="gender_agreement", count=3,
                    tags=["grammar"],
                ),
            }
            save_journal(journal)
            loaded = load_journal()
            assert "gender_agreement" in loaded
            assert loaded["gender_agreement"].count == 3

    def test_load_handles_corrupt(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        data_dir.mkdir(parents=True)
        journal_file = data_dir / "error_journal.json"
        journal_file.write_text("not json!")
        with patch("ankicli.error_journal.ensure_data_dir", lambda: None), \
             patch("ankicli.error_journal.ERROR_JOURNAL_FILE", journal_file):
            journal = load_journal()
            assert journal == {}


class TestLogError:
    """Tests for log_error function."""

    def _patch_journal(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        journal_file = data_dir / "error_journal.json"
        return (
            patch("ankicli.error_journal.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
            patch("ankicli.error_journal.ERROR_JOURNAL_FILE", journal_file),
        )

    def test_log_new_error(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            entry = log_error(
                error_type="accent_missing",
                example="cafe",
                correction="café",
                context="quiz",
                tags=["spelling"],
            )
            assert entry.count == 1
            assert entry.error_type == "accent_missing"
            assert len(entry.examples) == 1
            assert entry.examples[0]["input"] == "cafe"
            assert entry.first_seen != ""
            assert entry.last_seen != ""

    def test_log_increments_count(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            log_error("gender", example="la problema")
            entry = log_error("gender", example="la sol")
            assert entry.count == 2
            assert len(entry.examples) == 2

    def test_log_keeps_last_10_examples(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            for i in range(15):
                entry = log_error("gender", example=f"example_{i}")
            assert len(entry.examples) == 10
            # Should keep last 10 (indices 5-14)
            assert entry.examples[0]["input"] == "example_5"
            assert entry.examples[-1]["input"] == "example_14"

    def test_log_merges_tags(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            log_error("gender", example="la problema", tags=["grammar"])
            entry = log_error("gender", example="la sol", tags=["grammar", "A1"])
            assert "grammar" in entry.tags
            assert "A1" in entry.tags
            # "grammar" should not be duplicated
            assert entry.tags.count("grammar") == 1

    def test_log_without_tags(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            entry = log_error("spelling", example="tanbien")
            assert entry.tags == []

    def test_log_persists(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            log_error("gender", example="la problema", tags=["grammar"])
            journal = load_journal()
            assert "gender" in journal
            assert journal["gender"].count == 1


class TestGetErrorPatterns:
    """Tests for get_error_patterns function."""

    def _patch_journal(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        journal_file = data_dir / "error_journal.json"
        return (
            patch("ankicli.error_journal.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
            patch("ankicli.error_journal.ERROR_JOURNAL_FILE", journal_file),
        )

    def test_empty_journal(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            patterns = get_error_patterns()
            assert patterns == []

    def test_sorted_by_count(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            for _ in range(5):
                log_error("frequent", example="x")
            for _ in range(2):
                log_error("rare", example="y")
            for _ in range(8):
                log_error("most_frequent", example="z")

            patterns = get_error_patterns()
            assert patterns[0].error_type == "most_frequent"
            assert patterns[1].error_type == "frequent"
            assert patterns[2].error_type == "rare"

    def test_min_count_filter(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            log_error("once", example="x")
            for _ in range(3):
                log_error("thrice", example="y")

            patterns = get_error_patterns(min_count=2)
            assert len(patterns) == 1
            assert patterns[0].error_type == "thrice"

    def test_limit(self, tmp_path):
        p1, p2 = self._patch_journal(tmp_path)
        with p1, p2:
            for i in range(10):
                log_error(f"error_{i}", example="x")

            patterns = get_error_patterns(limit=3)
            assert len(patterns) == 3


class TestFormatErrorPatterns:
    """Tests for format_error_patterns_text function."""

    def test_empty(self):
        text = format_error_patterns_text([])
        assert "No error patterns" in text

    def test_with_entries(self):
        entries = [
            ErrorEntry(
                error_type="gender_agreement",
                count=5,
                examples=[{"input": "la problema", "correction": "el problema", "context": "quiz"}],
                last_seen="2025-01-15T10:30:00",
                tags=["grammar", "A2"],
            ),
        ]
        text = format_error_patterns_text(entries)
        assert "gender_agreement" in text
        assert "x5" in text
        assert "grammar" in text
        assert "la problema" in text
        assert "el problema" in text

    def test_multiple_entries(self):
        entries = [
            ErrorEntry(error_type="type_a", count=10, last_seen="2025-01-01T00:00:00"),
            ErrorEntry(error_type="type_b", count=3, last_seen="2025-01-02T00:00:00"),
        ]
        text = format_error_patterns_text(entries)
        assert "2 pattern(s)" in text
        assert "type_a" in text
        assert "type_b" in text

    def test_no_tags(self):
        entries = [
            ErrorEntry(error_type="test", count=1, last_seen="2025-01-01T00:00:00"),
        ]
        text = format_error_patterns_text(entries)
        assert "test" in text
        # Should not crash without tags
