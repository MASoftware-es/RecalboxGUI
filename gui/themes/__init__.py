from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


THEMES_DIR = Path(__file__).resolve().parent
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@dataclass(frozen=True)
class Theme:
    identifier: str
    names: dict[str, str]
    stylesheet: str
    colors: dict[str, str]

    def display_name(self, language: str) -> str:
        return self.names.get(language) or self.names.get("es") or self.identifier


def _merge(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    merged = dict(parent)
    for key, value in child.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _variables(data: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for section in ("colors", "metrics", "assets"):
        for key, value in data.get(section, {}).items():
            if isinstance(value, (str, int, float)):
                values[str(key)] = str(value)
    return values


def discover_themes() -> dict[str, Theme]:
    raw: dict[str, tuple[Path, dict[str, Any]]] = {}
    for metadata_path in sorted(THEMES_DIR.glob("*/theme.json")):
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
            identifier = str(data.get("id", metadata_path.parent.name))
            raw[identifier] = metadata_path.parent, data
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue

    resolved: dict[str, tuple[Path, dict[str, Any]]] = {}

    def resolve(identifier: str, chain: frozenset[str] = frozenset()) -> tuple[Path, dict[str, Any]]:
        if identifier in resolved:
            return resolved[identifier]
        if identifier in chain or identifier not in raw:
            raise ValueError(f"Invalid theme inheritance: {identifier}")
        directory, own_data = raw[identifier]
        data = own_data
        parent_id = own_data.get("inherits")
        if parent_id:
            parent_directory, parent_data = resolve(str(parent_id), chain | {identifier})
            data = _merge(parent_data, own_data)
            if "stylesheet" not in own_data:
                directory = parent_directory
        resolved[identifier] = directory, data
        return resolved[identifier]

    themes: dict[str, Theme] = {}
    for identifier in sorted(raw, key=lambda item: (item != "default", item)):
        try:
            stylesheet_directory, data = resolve(identifier)
            names = {str(key): str(value) for key, value in data["names"].items()}
            template = (stylesheet_directory / str(data.get("stylesheet", "style.qss"))).read_text(encoding="utf-8")
            values = _variables(data)
            stylesheet = VARIABLE.sub(lambda match: values[match.group(1)], template)
            themes[identifier] = Theme(identifier, names, stylesheet, {str(key): str(value) for key, value in data.get("colors", {}).items()})
        except (OSError, KeyError, TypeError, ValueError):
            continue
    return themes
