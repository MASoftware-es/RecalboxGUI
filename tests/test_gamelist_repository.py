import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from gui.connection import RemoteFileSnapshot
from gui.gamelist import GameListRepository, GameListValidationError


XML = b"""<?xml version='1.0' encoding='utf-8'?>
<gameList>
  <game source="Recalbox" timestamp="123">
    <hash>ABC</hash>
    <genreid>262</genreid>
    <genre>Fighting</genre>
    <desc>Old description</desc>
    <image>media/images/old.png</image>
    <thumbnail>media/thumbnails/old.png</thumbnail>
    <name>Old name</name>
    <path>game.zip</path>
    <custom>must remain</custom>
  </game>
</gameList>"""


class FakeEnvironment:
    roms_path = "/roms"


class FakeConnection:
    environment = FakeEnvironment()

    def __init__(self) -> None:
        self.data = XML
        self.existing = {"/roms/arcade/game.zip"}
        self.removed = []
        self.fail_remove = False

    def list_directories(self, path):
        return ["arcade"]

    def remote_file_is_regular(self, path):
        return path == "/roms/arcade/gamelist.xml" or path in self.existing

    def read_file(self, path):
        return RemoteFileSnapshot(path, self.data, hashlib.sha256(self.data).hexdigest())

    def write_file_atomic(self, path, data, expected_sha256):
        if hashlib.sha256(self.data).hexdigest() != expected_sha256:
            raise AssertionError("unexpected concurrent change")
        self.data = data
        return RemoteFileSnapshot(path, data, hashlib.sha256(data).hexdigest())

    def create_file_exclusive(self, path, data):
        self.data = data
        return RemoteFileSnapshot(path, data, hashlib.sha256(data).hexdigest())

    def remove_file(self, path, *, missing_ok=False):
        if self.fail_remove:
            raise OSError("remove failed")
        self.removed.append((path, missing_ok))


class GameListRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.connection = FakeConnection()
        self.repository = GameListRepository(self.connection)
        self.data = self.repository.load_system("arcade")

    def test_save_preserves_attributes_and_unedited_fields(self):
        game = self.data.games[0]
        values = dict(game.values)
        values.update(
            {
                "name": "Rock & Roll <Test>",
                "desc": "Line one\nLine two",
                "aliases": "Alias A|Alias B",
            }
        )

        updated = self.repository.save_game(self.data, game, values)

        text = updated.snapshot.data.decode("utf-8")
        self.assertIn('source="Recalbox"', text)
        self.assertIn('timestamp="123"', text)
        self.assertIn("<hash>ABC</hash>", text)
        self.assertIn("<custom>must remain</custom>", text)
        self.assertIn("Rock &amp; Roll &lt;Test&gt;", text)
        self.assertEqual(updated.games[0].values["aliases"], "Alias A|Alias B")

    def test_path_must_exist_inside_system_directory(self):
        game = self.data.games[0]
        values = dict(game.values)
        values["path"] = "../outside.zip"
        with self.assertRaises(GameListValidationError) as caught:
            self.repository.save_game(self.data, game, values)
        self.assertEqual(caught.exception.key, "gamelist.invalid_relative_path")

        values["path"] = "missing.zip"
        with self.assertRaises(GameListValidationError) as caught:
            self.repository.save_game(self.data, game, values)
        self.assertEqual(caught.exception.key, "gamelist.rom_not_found")

    def test_uploaded_names_are_made_unique(self):
        with TemporaryDirectory() as directory:
            local = Path(directory) / "cover.png"
            local.write_bytes(b"png")
            uploaded = []

            def upload_unique_file(local_path, remote_directory):
                uploaded.append((local_path, remote_directory))
                return remote_directory + "/cover_2.png"

            self.connection.upload_unique_file = upload_unique_file
            result = self.repository.upload_image(self.data, local, "image")

        self.assertEqual(result, "media/images/cover_2.png")
        self.assertEqual(uploaded[0][1], "/roms/arcade/media/images")

    def test_reload_game_refreshes_only_selected_entry(self):
        game = self.data.games[0]
        self.connection.data = self.connection.data.replace(b"Old name", b"Fresh name")

        updated, refreshed = self.repository.reload_game(self.data, game)

        self.assertEqual(refreshed.values["name"], "Fresh name")
        self.assertEqual(updated.games[0], refreshed)

    def test_create_and_delete_game(self):
        values = dict(self.data.games[0].values)
        values.update({"path": "second.zip", "name": "Second"})
        self.connection.existing.add("/roms/arcade/second.zip")

        created = self.repository.create_game(self.data, values)
        self.assertEqual([game.display_name for game in created.games], ["Old name", "Second"])

        deleted = self.repository.delete_game(created, created.games[0])
        self.assertEqual([game.display_name for game in deleted.games], ["Second"])
        self.assertEqual(self.connection.removed, [])

    def test_delete_game_can_remove_rom_and_associated_resources(self):
        deleted = self.repository.delete_game(
            self.data,
            self.data.games[0],
            delete_associated_files=True,
        )

        self.assertEqual(deleted.games, ())
        removed = {path for path, missing_ok in self.connection.removed if missing_ok}
        self.assertEqual(
            removed,
            {
                "/roms/arcade/game.zip",
                "/roms/arcade/media/images/old.png",
                "/roms/arcade/media/thumbnails/old.png",
            },
        )

    def test_create_empty_gamelist(self):
        created = self.repository.create_empty("arcade")
        self.assertEqual(created.games, ())
        self.assertIn(b"<gameList", created.snapshot.data)

    def test_delete_media_clears_xml_and_removes_physical_file(self):
        updated = self.repository.delete_media(
            self.data, self.data.games[0], "image"
        )

        self.assertEqual(updated.games[0].values["image"], "")
        self.assertNotIn(b"media/images/old.png", updated.snapshot.data)
        self.assertEqual(
            self.connection.removed,
            [("/roms/arcade/media/images/old.png", True)],
        )

    def test_delete_media_restores_xml_if_physical_delete_fails(self):
        original = self.connection.data
        self.connection.fail_remove = True

        with self.assertRaises(OSError):
            self.repository.delete_media(self.data, self.data.games[0], "thumbnail")

        self.assertEqual(self.connection.data, original)


if __name__ == "__main__":
    unittest.main()
