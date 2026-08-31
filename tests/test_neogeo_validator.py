from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "bin"
    / "recalboxscripts"
    / "validators"
    / "neogeo.py"
)
SPEC = importlib.util.spec_from_file_location("neogeo_validator", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
NEOGEO = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NEOGEO)


class NeoGeoDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.libraries = self.root / "libretro"
        self.lists = self.root / "flats"
        self.libraries.mkdir()
        self.lists.mkdir()
        self.system_list = self.root / "systemlist.xml"
        self.conf = self.root / "recalbox.conf"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_discovers_only_declared_installed_neogeo_cores(self) -> None:
        self.system_list.write_text(
            '<systemList><system name="neogeo"><emulatorList>'
            '<emulator name="libretro">'
            '<core name="fbneo" priority="1" extensions=".zip! .7z!"/>'
            '<core name="mame2003_plus" priority="3" extensions=".zip!"/>'
            '<core name="geolith" priority="9" extensions=".neo"/>'
            '</emulator></emulatorList></system></systemList>',
            encoding="utf-8",
        )
        for core in ("fbneo", "mame2003_plus", "geolith", "mame0278"):
            (self.libraries / f"{core}_libretro.so").touch()
        (self.lists / "fbneo.lst").touch()
        (self.lists / "mame2003-plus.lst").touch()

        preference, default, cores = NEOGEO.discover_cores(
            self.libraries, self.lists, self.system_list, self.conf
        )

        self.assertEqual(default, "fbneo")
        self.assertEqual(preference, ["fbneo", "mame2003_plus", "geolith"])
        self.assertNotIn("mame0278", cores)
        self.assertEqual(cores["fbneo"]["extensions"], {".zip", ".7z"})
        self.assertEqual(cores["geolith"]["extensions"], {".neo"})

    def test_user_override_becomes_default_when_installed(self) -> None:
        self.system_list.write_text(
            '<systemList><system name="neogeo"><emulatorList>'
            '<emulator name="libretro">'
            '<core name="fbneo" priority="1" extensions=".zip!"/>'
            '<core name="mame2003" priority="4" extensions=".zip!"/>'
            '</emulator></emulatorList></system></systemList>',
            encoding="utf-8",
        )
        for core in ("fbneo", "mame2003"):
            (self.libraries / f"{core}_libretro.so").touch()
        self.conf.write_text("neogeo.core=mame2003\n", encoding="utf-8")

        preference, default, _cores = NEOGEO.discover_cores(
            self.libraries, self.lists, self.system_list, self.conf
        )

        self.assertEqual(default, "mame2003")
        self.assertEqual(preference, ["mame2003", "fbneo"])

    def test_fbneo_requires_romset_crc_and_timing_markers(self) -> None:
        valid = "\n".join(
            (
                "[FBNeo] Romset found at /roms/neogeo/game",
                "[FBNeo] Using ROM with known crc 0x1234",
                "[FBNeo] Timing set to 60.000000 Hz",
            )
        )
        self.assertTrue(NEOGEO.fbneo_output_is_success(valid))
        self.assertFalse(
            NEOGEO.fbneo_output_is_success("[FBNeo] Timing set to 60.0 Hz")
        )


if __name__ == "__main__":
    unittest.main()
