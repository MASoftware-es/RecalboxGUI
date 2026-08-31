from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import uuid4


DEFAULT_ROMS_PATH = "/recalbox/share/roms"
DEFAULT_HOST = "recalbox.local"
DEFAULT_USERNAME = "root"
DEFAULT_PASSWORD = "recalboxroot"


@dataclass
class RecalboxEnvironment:
    identifier: str
    name: str
    host: str = DEFAULT_HOST
    username: str = DEFAULT_USERNAME
    password: str = DEFAULT_PASSWORD
    roms_path: str = DEFAULT_ROMS_PATH

    @classmethod
    def create(cls, name: str) -> "RecalboxEnvironment":
        return cls(identifier=str(uuid4()), name=name)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "RecalboxEnvironment":
        return cls(
            identifier=str(data.get("identifier") or uuid4()),
            name=str(data.get("name") or "Recalbox"),
            host=str(data.get("host") or DEFAULT_HOST),
            username=str(data.get("username") or DEFAULT_USERNAME),
            password=str(data.get("password", DEFAULT_PASSWORD) or ""),
            roms_path=str(data.get("roms_path") or DEFAULT_ROMS_PATH),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
