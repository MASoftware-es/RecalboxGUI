from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


LANGUAGES_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    strings: dict[str, str]


def discover_languages() -> dict[str, Language]:
    raw_languages: dict[str, tuple[str, str, dict[str, str]]] = {}
    for path in sorted(LANGUAGES_DIR.glob("*/language.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            code = str(data["code"])
            name = str(data["name"])
            strings = data["strings"]
            if not isinstance(strings, dict):
                continue
            raw_languages[code] = (name, str(data.get("inherits", "")), {str(key): str(value) for key, value in strings.items()})
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    languages: dict[str, Language] = {}

    def resolve(code: str, resolving: set[str] | None = None) -> Language | None:
        if code in languages:
            return languages[code]
        if code not in raw_languages:
            return None
        resolving = set() if resolving is None else resolving
        if code in resolving:
            return None
        resolving.add(code)
        name, parent_code, own_strings = raw_languages[code]
        parent = resolve(parent_code, resolving) if parent_code else None
        strings = dict(parent.strings) if parent else {}
        strings.update(own_strings)
        language = Language(code, name, strings)
        languages[code] = language
        resolving.remove(code)
        return language

    for code in raw_languages:
        resolve(code)
    return languages


def text(languages: dict[str, Language], language: str, key: str) -> str:
    selected = languages.get(language) or languages.get("es")
    fallback = languages.get("es")
    if selected and key in selected.strings:
        return selected.strings[key]
    if fallback and key in fallback.strings:
        return fallback.strings[key]
    return key


class Translator:
    """Traductor inyectable con castellano como idioma de respaldo."""

    def __init__(self, languages: dict[str, Language], language: str = "es") -> None:
        self.languages = languages
        self.language = language

    def __call__(self, key: str, **values: object) -> str:
        value = text(self.languages, self.language, key)
        try:
            return value.format(**values)
        except (KeyError, ValueError):
            return value
