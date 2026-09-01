from __future__ import annotations

import io
import posixpath
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from ..connection import RecalboxConnection, RemoteFileSnapshot


EDITABLE_FIELDS = (
    "path",
    "name",
    "aliases",
    "genre",
    "genreid",
    "publisher",
    "developer",
    "desc",
    "image",
    "thumbnail",
)
ASSOCIATED_FILE_FIELDS = (
    "image",
    "thumbnail",
    "video",
    "marquee",
    "wheel",
    "fanart",
    "boxart",
    "manual",
    "map",
    "bezel",
)
_ILLEGAL_XML = re.compile(
    "[\x00-\x08\x0B\x0C\x0E-\x1F\uD800-\uDFFF\uFFFE\uFFFF]"
)


@dataclass(frozen=True)
class EditableGame:
    index: int
    values: dict[str, str]

    @property
    def display_name(self) -> str:
        return self.values.get("name") or self.values.get("path") or "—"


@dataclass(frozen=True)
class GameListData:
    system: str
    system_path: str
    snapshot: RemoteFileSnapshot
    games: tuple[EditableGame, ...]


class GameListValidationError(ValueError):
    def __init__(self, key: str, **values: object) -> None:
        super().__init__(key)
        self.key = key
        self.values = values


class GameListRepository:
    def __init__(self, connection: RecalboxConnection) -> None:
        self.connection = connection
        self.roms_path = connection.environment.roms_path.rstrip("/")

    def list_systems(self) -> list[str]:
        return self.connection.list_directories(self.roms_path)

    def load_system(self, system: str) -> GameListData:
        system_path = self._system_path(system)
        gamelist_path = posixpath.join(system_path, "gamelist.xml")
        if not self.connection.remote_file_is_regular(gamelist_path):
            raise GameListValidationError("gamelist.no_gamelist")
        snapshot = self.connection.read_file(gamelist_path)
        root = self._parse(snapshot.data)
        games = tuple(
            EditableGame(
                index,
                {field: (element.findtext(field) or "") for field in EDITABLE_FIELDS},
            )
            for index, element in enumerate(root.findall("game"))
        )
        return GameListData(system, system_path, snapshot, games)

    def create_empty(self, system: str) -> GameListData:
        system_path = self._system_path(system)
        gamelist_path = posixpath.join(system_path, "gamelist.xml")
        serialized = b"<?xml version='1.0' encoding='utf-8'?>\n<gameList />\n"
        snapshot = self.connection.create_file_exclusive(gamelist_path, serialized)
        return GameListData(system, system_path, snapshot, ())

    def reload_game(
        self, data: GameListData, game: EditableGame
    ) -> tuple[GameListData, EditableGame]:
        snapshot = self.connection.read_file(data.snapshot.path)
        root = self._parse(snapshot.data)
        elements = root.findall("game")
        if game.index >= len(elements):
            raise GameListValidationError("gamelist.game_changed")
        element = elements[game.index]
        if (element.findtext("path") or "") != game.values.get("path", ""):
            raise GameListValidationError("gamelist.game_changed")
        refreshed = EditableGame(
            game.index,
            {field: (element.findtext(field) or "") for field in EDITABLE_FIELDS},
        )
        games = list(data.games)
        games[game.index] = refreshed
        return replace(data, snapshot=snapshot, games=tuple(games)), refreshed

    def read_media(self, data: GameListData, relative_path: str) -> bytes:
        if not relative_path.strip():
            return b""
        remote_path = self._safe_child_path(data.system_path, relative_path)
        return self.connection.read_file(remote_path).data

    def read_media_pair(self, data: GameListData, game: EditableGame) -> dict[str, bytes]:
        result: dict[str, bytes] = {}
        for field in ("image", "thumbnail"):
            try:
                result[field] = self.read_media(data, game.values.get(field, ""))
            except (OSError, GameListValidationError):
                result[field] = b""
        return result

    def upload_image(self, data: GameListData, local_path: Path, kind: str) -> str:
        subdirectory = "images" if kind == "image" else "thumbnails"
        remote_directory = posixpath.join(data.system_path, "media", subdirectory)
        uploaded = self.connection.upload_unique_file(local_path, remote_directory)
        return posixpath.relpath(uploaded, data.system_path)

    def save_game(
        self,
        data: GameListData,
        game: EditableGame,
        values: dict[str, str],
    ) -> GameListData:
        cleaned = self._validate_values(data.system_path, values)
        root = self._parse(data.snapshot.data)
        elements = root.findall("game")
        if game.index >= len(elements):
            raise GameListValidationError("gamelist.game_changed")
        element = elements[game.index]
        if (element.findtext("path") or "") != game.values.get("path", ""):
            raise GameListValidationError("gamelist.game_changed")
        self._update_element(element, cleaned)
        serialized = self._serialize(root)
        snapshot = self.connection.write_file_atomic(
            data.snapshot.path, serialized, data.snapshot.sha256
        )
        return self.load_system_from_snapshot(data.system, data.system_path, snapshot)

    def create_game(self, data: GameListData, values: dict[str, str]) -> GameListData:
        cleaned = self._validate_values(data.system_path, values)
        root = self._parse(data.snapshot.data)
        element = ET.SubElement(root, "game")
        self._update_element(element, cleaned)
        serialized = self._serialize(root)
        snapshot = self.connection.write_file_atomic(
            data.snapshot.path, serialized, data.snapshot.sha256
        )
        return self.load_system_from_snapshot(data.system, data.system_path, snapshot)

    def delete_game(
        self,
        data: GameListData,
        game: EditableGame,
        *,
        delete_associated_files: bool = False,
    ) -> GameListData:
        root = self._parse(data.snapshot.data)
        elements = root.findall("game")
        if game.index >= len(elements):
            raise GameListValidationError("gamelist.game_changed")
        element = elements[game.index]
        if (element.findtext("path") or "") != game.values.get("path", ""):
            raise GameListValidationError("gamelist.game_changed")
        associated_paths: list[str] = []
        if delete_associated_files:
            raw_paths = [element.findtext("path") or ""]
            raw_paths.extend(element.findtext(field) or "" for field in ASSOCIATED_FILE_FIELDS)
            associated_paths = [
                self._safe_child_path(data.system_path, path)
                for path in raw_paths
                if path.strip()
            ]
        root.remove(element)
        serialized = self._serialize(root)
        snapshot = self.connection.write_file_atomic(
            data.snapshot.path, serialized, data.snapshot.sha256
        )
        for remote_path in dict.fromkeys(associated_paths):
            self.connection.remove_file(remote_path, missing_ok=True)
        return self.load_system_from_snapshot(data.system, data.system_path, snapshot)

    def delete_media(
        self, data: GameListData, game: EditableGame, kind: str
    ) -> GameListData:
        if kind not in {"image", "thumbnail"}:
            raise ValueError(f"Unsupported media kind: {kind}")
        relative_path = game.values.get(kind, "").strip()
        if not relative_path:
            return data
        remote_path = self._safe_child_path(data.system_path, relative_path)
        values = dict(game.values)
        values[kind] = ""
        updated = self.save_game(data, game, values)
        try:
            self.connection.remove_file(remote_path, missing_ok=True)
        except Exception:
            # Si el borrado físico falla, recuperamos el XML anterior para que
            # no quede una modificación parcial difícil de entender.
            try:
                self.connection.write_file_atomic(
                    updated.snapshot.path,
                    data.snapshot.data,
                    updated.snapshot.sha256,
                )
            except Exception:
                pass
            raise
        return updated

    def load_system_from_snapshot(
        self, system: str, system_path: str, snapshot: RemoteFileSnapshot
    ) -> GameListData:
        root = self._parse(snapshot.data)
        games = tuple(
            EditableGame(
                index,
                {field: (element.findtext(field) or "") for field in EDITABLE_FIELDS},
            )
            for index, element in enumerate(root.findall("game"))
        )
        return GameListData(system, system_path, snapshot, games)

    def _validate_values(self, system_path: str, values: dict[str, str]) -> dict[str, str]:
        cleaned = {field: str(values.get(field, "")).strip() for field in EDITABLE_FIELDS}
        if not cleaned["path"]:
            raise GameListValidationError("gamelist.path_required")
        if not cleaned["name"]:
            raise GameListValidationError("gamelist.name_required")
        for field, value in cleaned.items():
            if _ILLEGAL_XML.search(value):
                raise GameListValidationError("gamelist.invalid_xml_text", field=field)
        rom_path = self._safe_child_path(system_path, cleaned["path"])
        if not self.connection.remote_file_is_regular(rom_path):
            raise GameListValidationError(
                "gamelist.rom_not_found", path=cleaned["path"]
            )
        for field in ("image", "thumbnail"):
            if cleaned[field]:
                self._safe_child_path(system_path, cleaned[field])
        return cleaned

    @staticmethod
    def _update_element(element: ET.Element, values: dict[str, str]) -> None:
        for field in EDITABLE_FIELDS:
            child = element.find(field)
            value = values[field]
            if child is not None:
                child.text = value
                continue
            if not value:
                continue
            child = ET.Element(field)
            child.text = value
            children = list(element)
            desired_index = EDITABLE_FIELDS.index(field)
            insert_at = len(children)
            for index, existing in enumerate(children):
                if existing.tag in EDITABLE_FIELDS:
                    if EDITABLE_FIELDS.index(existing.tag) > desired_index:
                        insert_at = index
                        break
            indentation = children[0].tail if children else "\n\t\t"
            child.tail = indentation
            element.insert(insert_at, child)

    @staticmethod
    def _parse(data: bytes) -> ET.Element:
        try:
            parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
            root = ET.fromstring(data, parser=parser)
        except ET.ParseError as error:
            raise GameListValidationError("gamelist.invalid_xml", detail=str(error)) from error
        if root.tag != "gameList":
            raise GameListValidationError("gamelist.invalid_root")
        return root

    @staticmethod
    def _serialize(root: ET.Element) -> bytes:
        tree = ET.ElementTree(root)
        output = io.BytesIO()
        tree.write(output, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
        serialized = output.getvalue()
        GameListRepository._parse(serialized)
        return serialized

    def _system_path(self, system: str) -> str:
        if not system or "/" in system or system in {".", ".."}:
            raise GameListValidationError("gamelist.invalid_system")
        return posixpath.join(self.roms_path, system)

    @staticmethod
    def _safe_child_path(parent: str, relative_path: str) -> str:
        normalized = relative_path.strip().replace("\\", "/")
        pure = PurePosixPath(normalized)
        if pure.is_absolute() or not pure.name or ".." in pure.parts:
            raise GameListValidationError(
                "gamelist.invalid_relative_path", path=relative_path
            )
        candidate = posixpath.normpath(posixpath.join(parent, normalized))
        if candidate == parent or not candidate.startswith(parent.rstrip("/") + "/"):
            raise GameListValidationError(
                "gamelist.invalid_relative_path", path=relative_path
            )
        return candidate
