"""Tests for learning_summary module."""

import json
from pathlib import Path
from unittest.mock import patch

from rich.console import Console, Group
from rich.text import Text

from ankicli.learning_summary import (
    get_default_summary,
    load_summary,
    save_summary,
    format_summary_for_display,
    LEVEL_DESCRIPTIONS,
)


def _patch_summary_paths(tmp_path):
    """Create patches for learning_summary module paths."""
    data_dir = tmp_path / ".ankicli"
    summary_file = data_dir / "learning_summary.json"
    return (
        patch("ankicli.learning_summary.ensure_data_dir", lambda: data_dir.mkdir(parents=True, exist_ok=True)),
        patch("ankicli.learning_summary.SUMMARY_FILE", summary_file),
    )


def _render_to_string(renderable) -> str:
    """Render a Rich renderable to a plain string for assertions."""
    console = Console(file=None, force_terminal=False, width=120)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


class TestDefaultSummary:
    """Tests for get_default_summary."""

    def test_has_all_levels(self):
        summary = get_default_summary()
        assert "A1" in summary["levels"]
        assert "A2" in summary["levels"]
        assert "B1" in summary["levels"]
        assert "B2" in summary["levels"]

    def test_levels_have_correct_structure(self):
        summary = get_default_summary()
        for level in ["A1", "A2", "B1", "B2"]:
            data = summary["levels"][level]
            assert "what_i_know" in data
            assert "what_to_learn" in data
            assert "estimated_coverage" in data
            assert data["estimated_coverage"] == 0

    def test_what_i_know_structure(self):
        summary = get_default_summary()
        what_i_know = summary["levels"]["A1"]["what_i_know"]
        assert "summary" in what_i_know
        assert "vocabulary" in what_i_know
        assert "grammar_concepts" in what_i_know
        assert "topics_covered" in what_i_know
        assert what_i_know["summary"] == ""
        assert what_i_know["vocabulary"] == []

    def test_what_to_learn_structure(self):
        summary = get_default_summary()
        what_to_learn = summary["levels"]["A1"]["what_to_learn"]
        assert "summary" in what_to_learn
        assert "vocabulary_gaps" in what_to_learn
        assert "grammar_gaps" in what_to_learn
        assert "priority_topics" in what_to_learn
        assert len(what_to_learn["vocabulary_gaps"]) > 0

    def test_initial_values(self):
        summary = get_default_summary()
        assert summary["last_updated"] is None
        assert summary["total_cards_added"] == 0
        assert summary["recent_additions"] == []
        assert summary["notes"] == ""


class TestPersistence:
    """Tests for load/save."""

    def test_save_and_load(self, tmp_path):
        p1, p2 = _patch_summary_paths(tmp_path)
        with p1, p2:
            summary = get_default_summary()
            summary["total_cards_added"] = 42
            summary["levels"]["A1"]["estimated_coverage"] = 35
            save_summary(summary)

            loaded = load_summary()
            assert loaded["total_cards_added"] == 42
            assert loaded["levels"]["A1"]["estimated_coverage"] == 35
            assert loaded["last_updated"] is not None

    def test_load_returns_defaults_if_missing(self, tmp_path):
        p1, p2 = _patch_summary_paths(tmp_path)
        with p1, p2:
            summary = load_summary()
            assert summary["total_cards_added"] == 0
            assert summary["levels"]["A1"]["estimated_coverage"] == 0

    def test_load_handles_corrupt_json(self, tmp_path):
        data_dir = tmp_path / ".ankicli"
        data_dir.mkdir(parents=True)
        summary_file = data_dir / "learning_summary.json"
        summary_file.write_text("{not valid json")

        with patch("ankicli.learning_summary.ensure_data_dir", lambda: None), \
             patch("ankicli.learning_summary.SUMMARY_FILE", summary_file):
            summary = load_summary()
            assert summary["total_cards_added"] == 0

    def test_save_sets_last_updated(self, tmp_path):
        p1, p2 = _patch_summary_paths(tmp_path)
        with p1, p2:
            summary = get_default_summary()
            assert summary["last_updated"] is None
            save_summary(summary)
            assert summary["last_updated"] is not None


class TestFormatDisplay:
    """Tests for format_summary_for_display."""

    def test_returns_rich_group(self):
        summary = get_default_summary()
        display = format_summary_for_display(summary)
        assert isinstance(display, Group)

    def test_renders_dashboard_header(self):
        summary = get_default_summary()
        display = format_summary_for_display(summary)
        rendered = _render_to_string(display)
        assert "LEARNING DASHBOARD" in rendered

    def test_renders_all_levels(self):
        summary = get_default_summary()
        display = format_summary_for_display(summary)
        rendered = _render_to_string(display)
        assert "A1" in rendered
        assert "A2" in rendered
        assert "B1" in rendered
        assert "B2" in rendered

    def test_renders_what_i_know(self):
        summary = get_default_summary()
        summary["levels"]["A1"]["what_i_know"]["summary"] = "Knows greetings and numbers"
        display = format_summary_for_display(summary)
        rendered = _render_to_string(display)
        assert "WHAT I KNOW" in rendered
        assert "Knows greetings and numbers" in rendered

    def test_renders_what_to_learn(self):
        summary = get_default_summary()
        display = format_summary_for_display(summary)
        rendered = _render_to_string(display)
        assert "WHAT TO LEARN" in rendered

    def test_renders_recent_additions(self):
        summary = get_default_summary()
        summary["recent_additions"] = ["hablar", "comer", "vivir"]
        display = format_summary_for_display(summary)
        rendered = _render_to_string(display)
        assert "RECENT ADDITIONS" in rendered
        assert "hablar" in rendered

    def test_renders_total_cards(self):
        summary = get_default_summary()
        summary["total_cards_added"] = 100
        display = format_summary_for_display(summary)
        rendered = _render_to_string(display)
        assert "100" in rendered


class TestLevelDescriptions:
    """Tests for LEVEL_DESCRIPTIONS."""

    def test_has_all_levels(self):
        assert "A1" in LEVEL_DESCRIPTIONS
        assert "A2" in LEVEL_DESCRIPTIONS
        assert "B1" in LEVEL_DESCRIPTIONS
        assert "B2" in LEVEL_DESCRIPTIONS

    def test_values_are_strings(self):
        for level, desc in LEVEL_DESCRIPTIONS.items():
            assert isinstance(desc, str)
