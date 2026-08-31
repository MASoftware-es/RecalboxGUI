from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QStandardPaths


@dataclass(frozen=True)
class AppPaths:
    """Rutas escribibles de RecalboxGUI dentro del perfil del usuario."""

    config: Path
    data: Path
    cache: Path
    logs: Path
    temporary: Path

    @classmethod
    def discover(cls) -> "AppPaths":
        config = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
        data = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        cache = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation))
        return cls(
            config=config,
            data=data,
            cache=cache,
            logs=data / "logs",
            temporary=cache / "tmp",
        )

    def ensure(self) -> None:
        for directory in (self.config, self.data, self.cache, self.logs, self.temporary):
            directory.mkdir(parents=True, exist_ok=True)
