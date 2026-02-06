"""Configuration management for ankicli."""

import json
import shutil
from dataclasses import dataclass, field, asdict

from .paths import DATA_DIR, CONFIG_FILE, atomic_json_write

# Available Claude models with their specifications
CLAUDE_MODELS: dict[str, dict] = {
    "claude-opus-4-6": {
        "name": "Claude Opus 4.6",
        "context_window": 200_000,
        "max_output_tokens": 32_000,
    },
    "claude-sonnet-4-5-20250929": {
        "name": "Claude Sonnet 4.5",
        "context_window": 200_000,
        "max_output_tokens": 16_384,
    },
    "claude-haiku-4-5-20251001": {
        "name": "Claude Haiku 4.5",
        "context_window": 200_000,
        "max_output_tokens": 8_192,
    },
    "claude-sonnet-4-20250514": {
        "name": "Claude Sonnet 4",
        "context_window": 200_000,
        "max_output_tokens": 16_384,
    },
}


def get_model_specs(model_id: str) -> dict:
    """Get specs for a model, with fallback defaults."""
    return CLAUDE_MODELS.get(model_id, {
        "name": model_id,
        "context_window": 200_000,
        "max_output_tokens": 8_192,
    })


@dataclass
class Config:
    """Application configuration."""

    main_model: str = "claude-opus-4-6"
    subagent_model: str = "claude-opus-4-6"
    delegate_max_workers: int = 5
    delegate_rate_limit_delay: float = 0.1
    tool_notes: dict[str, str] = field(default_factory=dict)


def load_config() -> Config:
    """Load config from disk, creating defaults if needed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            return Config(
                **{k: v for k, v in data.items() if k in Config.__dataclass_fields__}
            )
        except (json.JSONDecodeError, TypeError):
            # Back up corrupted config before overwriting with defaults
            backup_path = CONFIG_FILE.with_suffix(".json.bak")
            try:
                shutil.copy2(CONFIG_FILE, backup_path)
            except OSError:
                pass

    # Return defaults and save them
    config = Config()
    save_config(config)
    return config


def save_config(config: Config) -> None:
    """Save config to disk."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    atomic_json_write(CONFIG_FILE, asdict(config))


def get_tool_notes(config: Config) -> dict[str, str]:
    """Get all tool notes from config."""
    return dict(config.tool_notes)


def set_tool_note(config: Config, tool_name: str, note: str) -> None:
    """Set a tool note and save config."""
    config.tool_notes[tool_name] = note
    save_config(config)


def remove_tool_note(config: Config, tool_name: str) -> bool:
    """Remove a tool note. Returns True if it existed."""
    if tool_name in config.tool_notes:
        del config.tool_notes[tool_name]
        save_config(config)
        return True
    return False


def format_tool_notes_display(config: Config) -> str:
    """Format tool notes for display."""
    notes = config.tool_notes
    if not notes:
        return "No preferences set. Tell the assistant your preferences and it can save them."

    lines = []
    lines.append("User Preferences / Tool Notes")
    lines.append("=" * 50)

    # Show general notes first
    if "general" in notes:
        lines.append(f"\n  [general]")
        lines.append(f"    {notes['general']}")

    # Then tool-specific notes
    for tool_name, note in sorted(notes.items()):
        if tool_name == "general":
            continue
        lines.append(f"\n  [{tool_name}]")
        lines.append(f"    {note}")

    lines.append("")
    lines.append("=" * 50)
    return "\n".join(lines)
