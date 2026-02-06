"""Tests for config module."""

import json
from pathlib import Path
from unittest.mock import patch

from ankicli.config import (
    Config,
    CLAUDE_MODELS,
    get_model_specs,
    load_config,
    save_config,
    get_tool_notes,
    set_tool_note,
    remove_tool_note,
    format_tool_notes_display,
)


class TestConfig:
    """Tests for the Config dataclass."""

    def test_default_values(self):
        config = Config()
        assert config.main_model == "claude-opus-4-6"
        assert config.subagent_model == "claude-opus-4-6"
        assert config.delegate_max_workers == 5
        assert config.delegate_rate_limit_delay == 0.1
        assert config.tool_notes == {}

    def test_custom_values(self):
        config = Config(
            main_model="claude-opus-4-6",
            subagent_model="claude-haiku-4-5-20251001",
            delegate_max_workers=3,
            delegate_rate_limit_delay=0.5,
            tool_notes={"general": "test note"},
        )
        assert config.main_model == "claude-opus-4-6"
        assert config.subagent_model == "claude-haiku-4-5-20251001"
        assert config.delegate_max_workers == 3
        assert config.delegate_rate_limit_delay == 0.5
        assert config.tool_notes == {"general": "test note"}

    def test_tool_notes_is_dict(self):
        config = Config()
        assert isinstance(config.tool_notes, dict)
        # Ensure each instance gets its own dict (not shared default)
        config2 = Config()
        config.tool_notes["key"] = "value"
        assert "key" not in config2.tool_notes


class TestGetModelSpecs:
    """Tests for get_model_specs."""

    def test_known_model(self):
        specs = get_model_specs("claude-opus-4-6")
        assert specs["name"] == "Claude Opus 4.6"
        assert specs["context_window"] == 200_000
        assert specs["max_output_tokens"] == 32_000

    def test_opus_model(self):
        specs = get_model_specs("claude-opus-4-6")
        assert "Opus" in specs["name"] or "opus" in specs.get("model", "")
        assert specs["context_window"] >= 200_000

    def test_unknown_model_returns_defaults(self):
        specs = get_model_specs("unknown-model")
        assert specs["name"] == "unknown-model"
        assert specs["context_window"] == 200_000
        assert specs["max_output_tokens"] == 8_192


class TestClaudeModels:
    """Tests for the CLAUDE_MODELS constant."""

    def test_has_expected_models(self):
        assert "claude-opus-4-6" in CLAUDE_MODELS
        assert "claude-sonnet-4-5-20250929" in CLAUDE_MODELS
        assert "claude-haiku-4-5-20251001" in CLAUDE_MODELS
        assert "claude-opus-4-6" in CLAUDE_MODELS

    def test_all_models_have_required_keys(self):
        for model_id, specs in CLAUDE_MODELS.items():
            assert "name" in specs, f"Missing 'name' for {model_id}"
            assert "context_window" in specs, f"Missing 'context_window' for {model_id}"
            assert "max_output_tokens" in specs, f"Missing 'max_output_tokens' for {model_id}"


class TestPersistence:
    """Tests for config save/load."""

    def test_save_and_load(self, tmp_path):
        config_dir = tmp_path / ".ankicli"
        config_file = config_dir / "config.json"

        with patch("ankicli.config.DATA_DIR", config_dir), \
             patch("ankicli.config.CONFIG_FILE", config_file):
            config = Config(main_model="claude-opus-4-6", tool_notes={"general": "hello"})
            save_config(config)

            loaded = load_config()
            assert loaded.main_model == "claude-opus-4-6"
            assert loaded.tool_notes == {"general": "hello"}

    def test_load_creates_defaults_if_missing(self, tmp_path):
        config_dir = tmp_path / ".ankicli"
        config_file = config_dir / "config.json"

        with patch("ankicli.config.DATA_DIR", config_dir), \
             patch("ankicli.config.CONFIG_FILE", config_file):
            config = load_config()
            assert config.main_model == "claude-opus-4-6"
            # Config file should have been created
            assert config_file.exists()

    def test_load_handles_corrupt_json(self, tmp_path):
        config_dir = tmp_path / ".ankicli"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        config_file.write_text("not valid json {{{")

        with patch("ankicli.config.DATA_DIR", config_dir), \
             patch("ankicli.config.CONFIG_FILE", config_file):
            config = load_config()
            # Should return defaults
            assert config.main_model == "claude-opus-4-6"

    def test_load_ignores_unknown_fields(self, tmp_path):
        config_dir = tmp_path / ".ankicli"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        config_file.write_text(json.dumps({
            "main_model": "claude-opus-4-6",
            "unknown_field": "should_be_ignored",
            "another_unknown": 42,
        }))

        with patch("ankicli.config.DATA_DIR", config_dir), \
             patch("ankicli.config.CONFIG_FILE", config_file):
            config = load_config()
            assert config.main_model == "claude-opus-4-6"
            assert not hasattr(config, "unknown_field")


class TestToolNotes:
    """Tests for tool notes operations."""

    def test_get_tool_notes_empty(self):
        config = Config()
        notes = get_tool_notes(config)
        assert notes == {}

    def test_get_tool_notes_returns_copy(self):
        config = Config(tool_notes={"general": "note"})
        notes = get_tool_notes(config)
        notes["new_key"] = "new_value"
        # Should not mutate the original
        assert "new_key" not in config.tool_notes

    def test_set_tool_note(self, tmp_path):
        config_dir = tmp_path / ".ankicli"
        config_file = config_dir / "config.json"

        with patch("ankicli.config.DATA_DIR", config_dir), \
             patch("ankicli.config.CONFIG_FILE", config_file):
            config = Config()
            set_tool_note(config, "add_card", "Use informal Spanish")
            assert config.tool_notes["add_card"] == "Use informal Spanish"
            # Should be persisted
            assert config_file.exists()

    def test_remove_tool_note_exists(self, tmp_path):
        config_dir = tmp_path / ".ankicli"
        config_file = config_dir / "config.json"

        with patch("ankicli.config.DATA_DIR", config_dir), \
             patch("ankicli.config.CONFIG_FILE", config_file):
            config = Config(tool_notes={"add_card": "note to remove"})
            result = remove_tool_note(config, "add_card")
            assert result is True
            assert "add_card" not in config.tool_notes

    def test_remove_tool_note_not_exists(self):
        config = Config()
        result = remove_tool_note(config, "nonexistent")
        assert result is False

    def test_format_display_empty(self):
        config = Config()
        display = format_tool_notes_display(config)
        assert "No preferences set" in display

    def test_format_display_with_notes(self):
        config = Config(tool_notes={
            "general": "Use Latin American Spanish",
            "add_card": "Include 3 examples",
        })
        display = format_tool_notes_display(config)
        assert "general" in display
        assert "Use Latin American Spanish" in display
        assert "add_card" in display
        assert "Include 3 examples" in display

    def test_format_display_general_first(self):
        config = Config(tool_notes={
            "add_card": "specific note",
            "general": "general note",
        })
        display = format_tool_notes_display(config)
        general_pos = display.index("[general]")
        add_card_pos = display.index("[add_card]")
        assert general_pos < add_card_pos
