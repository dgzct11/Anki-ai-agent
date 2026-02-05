"""Configuration management for ankicli."""

import json
from pathlib import Path
from dataclasses import dataclass, asdict

CONFIG_DIR = Path(__file__).parent.parent.parent / ".ankicli"
CONFIG_FILE = CONFIG_DIR / "config.json"

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

    main_model: str = "claude-sonnet-4-20250514"
    subagent_model: str = "claude-sonnet-4-20250514"
    delegate_max_workers: int = 5
    delegate_rate_limit_delay: float = 0.1


def load_config() -> Config:
    """Load config from disk, creating defaults if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
            return Config(
                **{k: v for k, v in data.items() if k in Config.__dataclass_fields__}
            )
        except (json.JSONDecodeError, TypeError):
            pass

    # Return defaults and save them
    config = Config()
    save_config(config)
    return config


def save_config(config: Config) -> None:
    """Save config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(asdict(config), f, indent=2)
