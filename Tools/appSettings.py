import json
import os


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _settings_path() -> str:
    return os.path.join(_project_root(), "Settings", "Winter_Event.json")


def load_settings() -> dict:
    path = _settings_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _to_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def get_bool(*names: str, default: bool = False) -> bool:
    data = load_settings()
    for name in names:
        if name in data:
            return _to_bool(data.get(name), default=default)
    return default
