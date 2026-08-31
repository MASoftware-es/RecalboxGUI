from dataclasses import dataclass
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "bin" / "recalboxscripts"


@dataclass(frozen=True)
class UtilityDefinition:
    identifier: str
    name_key: str
    description_key: str
    script: Path
    kind: str = "action"
    validator_system: str = ""


UTILITIES = (
    UtilityDefinition(
        identifier="patch_ntfs3",
        name_key="utility.ntfs3.name",
        description_key="utility.ntfs3.description",
        script=SCRIPTS_DIR / "recalbox-patch-ntfs3.sh",
    ),
    UtilityDefinition(
        identifier="clean_media",
        name_key="utility.clean_media.name",
        description_key="utility.clean_media.description",
        script=SCRIPTS_DIR / "recalbox-clean-media.sh",
        kind="clean_media",
    ),
    UtilityDefinition(
        identifier="validate_mame",
        name_key="utility.mame.name",
        description_key="utility.mame.description",
        script=SCRIPTS_DIR / "validators" / "mame.py",
        kind="rom_validator",
        validator_system="mame",
    ),
    UtilityDefinition(
        identifier="validate_neogeo",
        name_key="utility.neogeo.name",
        description_key="utility.neogeo.description",
        script=SCRIPTS_DIR / "validators" / "neogeo.py",
        kind="rom_validator",
        validator_system="neogeo",
    ),
    UtilityDefinition(
        identifier="restart_services",
        name_key="utility.services.name",
        description_key="utility.services.description",
        script=SCRIPTS_DIR / "recalbox-restart-services.sh",
        kind="restart_services",
    ),
)
