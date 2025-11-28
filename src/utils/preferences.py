"""Simple preference storage for user-specific chat settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ..config.settings import get_settings


def _prefs_path() -> Path:
    settings = get_settings()
    return Path(settings.paths.data_dir) / "preferences.json"


def load_preferences() -> Dict[str, Any]:
    """Load stored preferences from disk."""
    path = _prefs_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_preferences(prefs: Dict[str, Any]) -> None:
    """Persist preferences to disk."""
    path = _prefs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2, ensure_ascii=False)
