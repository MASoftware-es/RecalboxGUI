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
    / "mame.py"
)
SPEC = importlib.util.spec_from_file_location("mame_validator", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MAME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MAME)


class CoreDiscoveryTests(unittest.TestCase):
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

    def install(self, core: str, list_name: str | None = None) -> None:
        (self.libraries / f"{core}_libretro.so").touch()
        (self.lists / (list_name or f"{core}.lst")).touch()

    def write_system(self, cores: list[tuple[str, int, str]]) -> None:
        entries = "".join(
            f'<core name="{name}" priority="{priority}">'
            f'<arcade file="{machine_list}"/></core>'
            for name, priority, machine_list in cores
        )
        self.system_list.write_text(
            '<systemList><system name="mame"><emulatorList>'
            f'<emulator name="libretro">{entries}</emulator>'
            '</emulatorList></system></systemList>',
            encoding="utf-8",
        )

    def discover(self):
        return MAME.discover_cores(
            self.libraries,
            self.lists,
            self.system_list,
            self.conf,
        )

    def test_current_policy_is_derived_from_recalbox_metadata(self) -> None:
        cores = [
            ("mame2003_plus", 3, "mame2003-plus.lst"),
            ("mame0278", 7, "mame0278.lst"),
            ("mame0258", 6, "mame0258.lst"),
            ("mame2015", 7, "mame2015.lst"),
            ("mame2010", 6, "mame2010.lst"),
            ("mame2003", 4, "mame2003.lst"),
        ]
        for name, _priority, machine_list in cores:
            self.install(name, machine_list)
        self.write_system(cores)

        preference, default, discovered = self.discover()

        self.assertEqual(default, "mame2003_plus")
        self.assertEqual(
            preference,
            [
                "mame2003_plus",
                "mame0278",
                "mame0258",
                "mame2015",
                "mame2010",
                "mame2003",
            ],
        )
        self.assertEqual(discovered["mame2003_plus"]["list"].name, "mame2003-plus.lst")

    def test_new_core_is_discovered_but_kept_conservative(self) -> None:
        cores = [
            ("mame2003_plus", 3, "mame2003-plus.lst"),
            ("mame0300", 8, "mame0300.lst"),
        ]
        for name, _priority, machine_list in cores:
            self.install(name, machine_list)
        self.write_system(cores)

        preference, default, discovered = self.discover()

        self.assertEqual(default, "mame2003_plus")
        self.assertEqual(preference, ["mame2003_plus", "mame0300"])
        self.assertEqual(discovered["mame0300"]["analyzer"], "")

    def test_removed_core_and_user_override_are_respected(self) -> None:
        cores = [
            ("mame2003_plus", 3, "mame2003-plus.lst"),
            ("mame0278", 7, "mame0278.lst"),
        ]
        self.install("mame0278")
        self.write_system(cores)
        self.conf.write_text("mame.core=mame0278\n", encoding="utf-8")

        preference, default, discovered = self.discover()

        self.assertEqual(default, "mame0278")
        self.assertEqual(preference, ["mame0278"])
        self.assertEqual(set(discovered), {"mame0278"})


if __name__ == "__main__":
    unittest.main()
