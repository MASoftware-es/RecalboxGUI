from __future__ import annotations

import json

from PySide6.QtCore import QByteArray, QSettings

from .models import RecalboxEnvironment
from .security import decrypt_text, encrypt_text


class UserSettings:
    """Configuración persistente del usuario actual."""

    def __init__(self, backend: QSettings | None = None) -> None:
        self._backend = backend or QSettings()

    @property
    def language(self) -> str:
        return str(self._backend.value("appearance/language", "es"))

    @language.setter
    def language(self, value: str) -> None:
        self._backend.setValue("appearance/language", value)

    @property
    def theme(self) -> str:
        return str(self._backend.value("appearance/theme", "default"))

    @theme.setter
    def theme(self, value: str) -> None:
        self._backend.setValue("appearance/theme", value)

    def value(self, key: str, default: object = None) -> object:
        return self._backend.value(key, default)

    def set_value(self, key: str, value: object) -> None:
        self._backend.setValue(key, value)

    def sync(self) -> None:
        self._backend.sync()

    def environments(self) -> list[RecalboxEnvironment]:
        raw = str(self._backend.value("recalbox/environments", "[]"))
        try:
            values = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if not isinstance(values, list):
            return []
        environments = []
        for item in values:
            if not isinstance(item, dict):
                continue
            data = dict(item)
            if "password_encrypted" in data:
                data["password"] = decrypt_text(str(data.pop("password_encrypted")))
            environments.append(RecalboxEnvironment.from_dict(data))
        return environments

    def save_environments(self, environments: list[RecalboxEnvironment]) -> None:
        serialized = []
        for environment in environments:
            data = environment.to_dict()
            password = str(data.pop("password", ""))
            data["password_encrypted"] = encrypt_text(password)
            serialized.append(data)
        value = json.dumps(serialized, ensure_ascii=False)
        self._backend.setValue("recalbox/environments", value)
        self._backend.sync()

    def window_geometry(self) -> QByteArray | None:
        value = self._backend.value("window/geometry")
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def save_window_geometry(self, geometry: QByteArray) -> None:
        self._backend.setValue("window/geometry", geometry)
        self._backend.sync()
