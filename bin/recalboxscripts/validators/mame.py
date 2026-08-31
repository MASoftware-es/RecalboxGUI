#!/usr/bin/python3

import argparse
import csv
import json
import os
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path


VERSION = "1.1"

ROM_DIR = Path("/recalbox/share/roms/mame")
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "mame-validator-data"
RETROARCH = Path("/usr/bin/retroarch")
LIST_DIR = Path("/recalbox/system/arcade/flats")
LIBRETRO_DIR = Path("/usr/lib/libretro")
SYSTEM_LIST = Path(
    "/recalbox/share_init/system/.emulationstation/systemlist.xml"
)
RECALBOX_CONF = Path("/recalbox/share/system/recalbox.conf")

GAMELIST = ROM_DIR / "gamelist.xml"
USERDATA = ROM_DIR / "gamelist-userdata.ini"

# Los cores instalados y el predeterminado se descubren en tiempo de
# ejecución. Esta tabla solo indica para qué salidas de core tenemos un
# analizador validado; no constituye un inventario de cores instalados.
KNOWN_CORE_ANALYZERS = {
    "mame2003_plus": "mame2003",
    "mame2003": "mame2003",
    "mame2010": "mame2010",
    "mame2015": "mame2015",
    "mame0258": "modern",
    "mame0278": "modern",
}

CORE_PREFERENCE = []
DEFAULT_CORE = ""
CORES = {}
STRUCTURED_PROGRESS = False


def emit(*parts):
    if STRUCTURED_PROGRESS:
        print("RCGUI|" + "|".join(str(part) for part in parts), flush=True)


def configure_runtime_paths(rom_dir, data_dir):
    global ROM_DIR, DATA_DIR, GAMELIST, USERDATA
    if rom_dir:
        ROM_DIR = Path(rom_dir)
    if data_dir:
        DATA_DIR = Path(data_dir)
    GAMELIST = ROM_DIR / "gamelist.xml"
    USERDATA = ROM_DIR / "gamelist-userdata.ini"


def read_configured_core(path):
    """Devuelve el override mame.core activo, si existe."""
    if not path.exists():
        return ""

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip().lower() == "mame.core":
                return value.strip().strip('"\'').lower()

    return ""


def load_mame_system_cores(path):
    """Lee cores, listas y prioridades declarados por Recalbox para MAME."""
    definitions = {}
    if not path.exists():
        return definitions

    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return definitions

    system = root.find(".//system[@name='mame']")
    if system is None:
        return definitions

    emulator = system.find("./emulatorList/emulator[@name='libretro']")
    if emulator is None:
        return definitions

    for node in emulator.findall("core"):
        name = node.get("name", "").strip().lower()
        if not name.startswith("mame"):
            continue
        arcade = node.find("arcade")
        list_name = arcade.get("file", "").strip() if arcade is not None else ""
        try:
            priority = int(node.get("priority", "9999"))
        except ValueError:
            priority = 9999
        definitions[name] = {
            "list_name": list_name,
            "priority": priority,
        }

    return definitions


def core_modernity(core_name):
    """Ordena releases 0.xxx antes de snapshots anuales de MAME."""
    release = re.fullmatch(r"mame0(\d{3,})", core_name)
    if release:
        return 2, int(release.group(1))
    snapshot = re.fullmatch(r"mame(\d{4})", core_name)
    if snapshot:
        return 1, int(snapshot.group(1))
    return 0, 0


def fallback_list_path(core_name, list_dir):
    candidates = (
        list_dir / f"{core_name}.lst",
        list_dir / f"{core_name.replace('_plus', '-plus')}.lst",
        list_dir / f"{core_name.replace('_', '-')}.lst",
    )
    return next((path for path in candidates if path.exists()), candidates[0])


def discover_cores(
    library_dir=LIBRETRO_DIR,
    list_dir=LIST_DIR,
    system_list=SYSTEM_LIST,
    recalbox_conf=RECALBOX_CONF,
):
    """Descubre los cores MAME realmente instalados en este Recalbox."""
    definitions = load_mame_system_cores(system_list)
    discovered = {}

    for library in sorted(library_dir.glob("mame*_libretro.so")):
        name = library.name.removesuffix("_libretro.so").lower()
        definition = definitions.get(name, {})
        list_name = definition.get("list_name", "")
        machine_list = (
            list_dir / list_name
            if list_name
            else fallback_list_path(name, list_dir)
        )
        discovered[name] = {
            "library": library,
            "list": machine_list,
            "priority": definition.get("priority", 9999),
            "analyzer": KNOWN_CORE_ANALYZERS.get(name, ""),
        }

    if not discovered:
        return [], "", {}

    configured = read_configured_core(recalbox_conf)
    if configured not in discovered:
        configured = ""

    declared = [
        name for name in discovered
        if discovered[name]["priority"] < 9999
    ]
    default_core = configured or (
        min(declared, key=lambda name: (discovered[name]["priority"], name))
        if declared else (
            "mame2003_plus" if "mame2003_plus" in discovered else ""
        )
    )

    remaining = [name for name in discovered if name != default_core]
    remaining.sort(
        key=lambda name: (core_modernity(name), name),
        reverse=True,
    )
    preference = ([default_core] if default_core else []) + remaining
    return preference, default_core, discovered


def configure_discovered_cores():
    global CORE_PREFERENCE, DEFAULT_CORE, CORES
    CORE_PREFERENCE, DEFAULT_CORE, CORES = discover_cores()


def configure_report_policy(report):
    global CORE_PREFERENCE, DEFAULT_CORE
    CORE_PREFERENCE = list(report.get("core_preference", []))
    DEFAULT_CORE = str(report.get("default_core", ""))


def now_stamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def format_duration(seconds):
    if seconds is None:
        return "--:--"

    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


def show_progress(done, total, started, current="", counts=None):
    if STRUCTURED_PROGRESS:
        return
    elapsed = time.monotonic() - started

    if done and elapsed > 0:
        rate = done / elapsed
        eta = (total - done) / rate if rate else None
    else:
        eta = None

    ratio = done / total if total else 1.0
    width = 26
    filled = int(width * ratio)

    bar = "#" * filled + "-" * (width - filled)

    status = ""
    if counts:
        status = (
            f" V:{counts.get('VALID', 0)}"
            f" I:{counts.get('INVALID', 0)}"
            f" U:{counts.get('UNKNOWN', 0)}"
            f" P:{counts.get('PROTECTED', 0)}"
        )

    sys.stdout.write(
        f"\r[{bar}] {ratio * 100:6.2f}% "
        f"{done}/{total} ETA {format_duration(eta)}"
        f"{status} {current[:30]:30}"
    )
    sys.stdout.flush()

    if done >= total:
        print()


def load_machine_list(path):
    machines = {}

    if not path.exists():
        return machines

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\r\n")

            if not line or line.startswith("#"):
                continue

            parts = line.split("|")
            if not parts:
                continue

            name = parts[0].replace("\\_", "_").strip().lower()

            if not name:
                continue

            machines[name] = {
                "type": parts[2].strip().lower() if len(parts) > 2 else "",
                "bios": (
                    parts[8].replace("\\_", "_").strip().lower()
                    if len(parts) > 8 else ""
                ),
                "parent": (
                    parts[9].replace("\\_", "_").strip().lower()
                    if len(parts) > 9 else ""
                ),
                "quality": (
                    parts[10].strip().lower()
                    if len(parts) > 10 else ""
                ),
            }

    return machines


def normalize_rom_name(value):
    if not value:
        return ""

    value = value.strip().replace("\\", "/")

    while value.startswith("./"):
        value = value[2:]

    return Path(value).name.lower()


def load_gamelist():
    tree = ET.parse(GAMELIST)
    root = tree.getroot()
    games = {}

    for game in root.findall("game"):
        path = game.find("path")

        if path is None or not path.text:
            continue

        name = normalize_rom_name(path.text)

        if name:
            games[name] = game

    return tree, root, games


def output_is_failure(text):
    low = text.lower()

    failure_strings = (
        "required files are missing",
        "failed to load content",
        "readroms failed",
        "could not load content",
        "unknown system",
        "unknown game",
    )

    return any(value in low for value in failure_strings)


def extract_interesting_log(lines):
    result = []

    interesting = (
        "succesfully loaded roms",
        "required files are missing",
        "readroms failed",
        "failed to load content",
        "starting game:",
        "source file:",
        "not found",
        "is required",
    )

    for line in lines:
        low = line.lower()

        if any(token in low for token in interesting):
            result.append(line)

    return result[-15:]


def test_core(core_name, rom_path, config_path, timeout_seconds):
    core = CORES[core_name]
    library = core["library"]

    if not library.exists():
        return {
            "status": "UNKNOWN",
            "reason": "Core no instalado",
            "elapsed": 0,
            "log": [],
        }

    analyzer = core.get("analyzer", "")
    if not analyzer:
        return {
            "status": "UNKNOWN",
            "reason": "Core detectado sin analizador de salida validado",
            "elapsed": 0,
            "log": [],
        }

    command = [
        str(RETROARCH),
        "-v",
        "--appendconfig",
        str(config_path),
        "-L",
        str(library),
        str(rom_path),
    ]

    started = time.monotonic()

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
    except Exception as exc:
        return {
            "status": "UNKNOWN",
            "reason": f"No se pudo iniciar RetroArch: {exc}",
            "elapsed": round(time.monotonic() - started, 3),
            "log": [],
        }

    fd = process.stdout.fileno()
    os.set_blocking(fd, False)

    captured = bytearray()
    status = None
    reason = None

    failure_strings = (
        "required files are missing",
        "failed to load content",
        "readroms failed",
        "could not load content",
        "unknown system",
        "unknown game",
    )

    deadline = started + timeout_seconds

    try:
        while time.monotonic() < deadline:
            got_data = False

            while True:
                try:
                    chunk = os.read(fd, 65536)
                except BlockingIOError:
                    break
                except OSError:
                    break

                if not chunk:
                    break

                captured.extend(chunk)
                got_data = True

            text = captured.decode("utf-8", errors="replace")
            low = text.lower()

            if any(token in low for token in failure_strings):
                status = "FAIL"
                reason = "El core rechazó el romset"
                break

            if analyzer == "mame2003":
                if (
                    "succesfully loaded roms." in low
                    or "gameinfo:" in low
                ):
                    status = "OK"
                    reason = "Carga de ROMs confirmada por el core"
                    break

            elif analyzer == "mame2010":
                if "source file:" in low:
                    # SOURCE FILE aparece antes de que termine el audit.
                    # Esperamos brevemente para evitar falsos positivos.
                    time.sleep(0.20)

                    while True:
                        try:
                            chunk = os.read(fd, 65536)
                        except (BlockingIOError, OSError):
                            break

                        if not chunk:
                            break

                        captured.extend(chunk)

                    text = captured.decode("utf-8", errors="replace")
                    low = text.lower()

                    if any(token in low for token in failure_strings):
                        status = "FAIL"
                        reason = "El core rechazó el romset"
                    else:
                        status = "OK"
                        reason = "Máquina iniciada sin errores de audit"

                    break

            elif analyzer == "mame2015":
                if "starting game:" in low or "source file:" in low:
                    # Damos un pequeño margen para que aparezca un
                    # posible error de audit inmediatamente posterior.
                    time.sleep(0.12)

                    while True:
                        try:
                            chunk = os.read(fd, 65536)
                        except (BlockingIOError, OSError):
                            break

                        if not chunk:
                            break

                        captured.extend(chunk)

                    text = captured.decode("utf-8", errors="replace")
                    low = text.lower()

                    if any(token in low for token in failure_strings):
                        status = "FAIL"
                        reason = "El core rechazó el romset"
                    else:
                        status = "OK"
                        reason = "Máquina iniciada sin errores de audit"

                    break

            elif analyzer == "modern":
                if "starting game:" in low:
                    # En MAME moderno "Starting game" aparece antes
                    # del audit. Esperamos brevemente el resultado.
                    time.sleep(0.20)

                    while True:
                        try:
                            chunk = os.read(fd, 65536)
                        except (BlockingIOError, OSError):
                            break

                        if not chunk:
                            break

                        captured.extend(chunk)

                    text = captured.decode("utf-8", errors="replace")
                    low = text.lower()

                    if any(token in low for token in failure_strings):
                        status = "FAIL"
                        reason = "El core rechazó el romset"
                    else:
                        status = "OK"
                        reason = "Máquina iniciada sin errores de audit"

                    break

            if process.poll() is not None:
                # El proceso terminó: recoger cualquier salida que
                # todavía quede pendiente en la tubería.
                while True:
                    try:
                        chunk = os.read(fd, 65536)
                    except (BlockingIOError, OSError):
                        break

                    if not chunk:
                        break

                    captured.extend(chunk)

                break

            if not got_data:
                time.sleep(0.01)

        # Última lectura antes de decidir UNKNOWN por timeout/salida.
        while True:
            try:
                chunk = os.read(fd, 65536)
            except (BlockingIOError, OSError):
                break

            if not chunk:
                break

            captured.extend(chunk)

        text = captured.decode("utf-8", errors="replace")
        low = text.lower()

        # Un fallo explícito siempre tiene prioridad.
        if any(token in low for token in failure_strings):
            status = "FAIL"
            reason = "El core rechazó el romset"

        elif status is None:
            if (
                analyzer == "mame2003"
                and (
                    "succesfully loaded roms." in low
                    or "gameinfo:" in low
                )
            ):
                status = "OK"
                reason = "Carga de ROMs confirmada por el core"
            else:
                status = "UNKNOWN"
                reason = "Resultado no concluyente"

    finally:
        if process.poll() is None:
            # Es un proceso de prueba aislado. No necesitamos esperar
            # el cierre normal de RetroArch una vez obtenido el audit.
            process.kill()

        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            pass

        try:
            process.stdout.close()
        except Exception:
            pass

    elapsed = round(time.monotonic() - started, 3)
    lines = captured.decode(
        "utf-8",
        errors="replace",
    ).splitlines()

    return {
        "status": status,
        "reason": reason,
        "elapsed": elapsed,
        "log": extract_interesting_log(lines),
    }

def atomic_json(path, value):
    temp = path.with_name("." + path.name + ".tmp")

    with temp.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)

    os.replace(temp, path)


def save_reports(report):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    json_path = DATA_DIR / "latest.json"
    csv_path = DATA_DIR / "latest.csv"

    atomic_json(json_path, report)

    temp = DATA_DIR / ".latest.csv.tmp"

    columns = [
        "rom",
        "status",
        "best_core",
        "compatible_cores",
        "dependencies",
    ] + CORE_PREFERENCE

    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()

        for item in report["roms"]:
            row = {
                "rom": item["rom"],
                "status": item["status"],
                "best_core": item.get("best_core", ""),
                "compatible_cores": ";".join(
                    item.get("compatible_cores", [])
                ),
                "dependencies": ";".join(
                    item.get("dependencies", [])
                ),
            }

            for core in CORE_PREFERENCE:
                row[core] = (
                    item.get("cores", {})
                    .get(core, {})
                    .get("status", "NOT_TESTED")
                )

            writer.writerow(row)

    os.replace(temp, csv_path)

    return json_path, csv_path


def detect(args):
    configure_discovered_cores()

    if not ROM_DIR.is_dir():
        sys.exit(f"ERROR: no existe {ROM_DIR}")

    if not GAMELIST.exists():
        sys.exit(f"ERROR: no existe {GAMELIST}")

    if not RETROARCH.exists():
        sys.exit(f"ERROR: no existe {RETROARCH}")

    if not CORE_PREFERENCE:
        sys.exit("ERROR: no se ha encontrado ningún core MAME instalado.")

    _, _, games = load_gamelist()

    lists = {
        core: load_machine_list(CORES[core]["list"])
        for core in CORE_PREFERENCE
    }

    roms = sorted(
        [
            path
            for path in ROM_DIR.iterdir()
            if path.is_file() and path.suffix.lower() == ".zip"
        ],
        key=lambda path: path.name.lower(),
    )

    if args.limit is not None:
        roms = roms[:args.limit]

    if not roms:
        print("No hay ROMs ZIP que analizar.")

    fd, config_name = tempfile.mkstemp(
        prefix="mame-validator-",
        suffix=".cfg",
        dir="/tmp",
    )
    os.close(fd)

    config = Path(config_name)
    config.write_text(
        'video_driver = "null"\n'
        'audio_driver = "null"\n'
        'video_fullscreen = "false"\n',
        encoding="utf-8",
    )

    report = {
        "schema": 1,
        "program_version": VERSION,
        "created": datetime.now().isoformat(timespec="seconds"),
        "rom_dir": str(ROM_DIR),
        "default_core": DEFAULT_CORE,
        "core_preference": CORE_PREFERENCE,
        "discovered_cores": {
            core: {
                "library": str(CORES[core]["library"]),
                "list": str(CORES[core]["list"]),
                "priority": CORES[core]["priority"],
                "analyzer": CORES[core]["analyzer"] or None,
            }
            for core in CORE_PREFERENCE
        },
        "roms": [],
    }

    started = time.monotonic()
    counts = Counter()
    emit("PLAN", "DETECT", len(roms))

    print()
    print("MAME Validator - DETECT")
    print("=======================")
    print(f"ROMs encontradas : {len(roms)}")
    print(f"Cores detectados : {', '.join(CORE_PREFERENCE)}")
    print(f"Core predeterminado: {DEFAULT_CORE or 'no determinado'}")
    for core in CORE_PREFERENCE:
        if not CORES[core]["list"].exists():
            print(f"AVISO: no existe la lista de máquinas de {core}")
        if not CORES[core]["analyzer"]:
            print(f"AVISO: {core} no tiene un analizador de salida validado")
    print("UNKNOWN nunca será considerado eliminable.")
    print()

    try:
        for number, rom in enumerate(roms, 1):
            rom_key = rom.name.lower()
            machine = rom.stem.lower()

            stat = rom.stat()

            item = {
                "rom": rom.name,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "status": "",
                "best_core": "",
                "compatible_cores": [],
                "dependencies": [],
                "cores": {},
            }

            # neogeo.zip y otros ZIP auxiliares sin entrada visible de juego
            # quedan protegidos automáticamente.
            if rom_key not in games:
                item["status"] = "PROTECTED"
                item["reason"] = (
                    "ZIP sin entrada en gamelist.xml; posible BIOS/dependencia"
                )

            else:
                applicable = []
                unknown = False

                for core in CORE_PREFERENCE:
                    if machine not in lists[core]:
                        item["cores"][core] = {
                            "status": "NOT_LISTED",
                            "reason": "No aparece en la lista del core",
                        }
                        continue

                    applicable.append(core)

                    result = test_core(
                        core,
                        rom,
                        config,
                        args.timeout,
                    )

                    item["cores"][core] = result

                    if result["status"] == "OK":
                        item["compatible_cores"].append(core)
                        break

                    elif result["status"] == "UNKNOWN":
                        unknown = True

                if item["compatible_cores"]:
                    item["status"] = "VALID"

                    # CORE_PREFERENCE ya expresa exactamente nuestra política.
                    item["best_core"] = next(
                        core
                        for core in CORE_PREFERENCE
                        if core in item["compatible_cores"]
                    )

                    info = lists[item["best_core"]].get(machine, {})

                    dependencies = []

                    for field in ("bios", "parent"):
                        dep = info.get(field, "")

                        if (
                            dep
                            and dep != machine
                            and dep not in dependencies
                        ):
                            dependencies.append(dep)

                    item["dependencies"] = dependencies
                    item["reason"] = (
                        f"Compatible con: "
                        f"{', '.join(item['compatible_cores'])}"
                    )

                elif not applicable:
                    item["status"] = "UNKNOWN"
                    item["reason"] = (
                        "No aparece en ninguna lista de los cores MAME"
                    )

                elif unknown:
                    item["status"] = "UNKNOWN"
                    item["reason"] = (
                        "Ningún core confirmó la carga y existe "
                        "al menos un resultado no concluyente"
                    )

                else:
                    item["status"] = "INVALID"
                    item["reason"] = (
                        "Todos los cores aplicables rechazaron el romset"
                    )

            report["roms"].append(item)
            counts[item["status"]] += 1

            show_progress(
                number,
                len(roms),
                started,
                rom.name,
                counts,
            )
            emit(
                "PROGRESS",
                "DETECT",
                number,
                len(roms),
                item["status"],
                rom.name,
            )

    except KeyboardInterrupt:
        print("\nAnálisis cancelado. No se guardará un informe incompleto.")
        return

    finally:
        try:
            config.unlink()
        except OSError:
            pass

    json_path, csv_path = save_reports(report)

    print()
    print("RESULTADO")
    print("=========")
    print(f"VALID     : {counts['VALID']}")
    print(f"INVALID   : {counts['INVALID']}")
    print(f"UNKNOWN   : {counts['UNKNOWN']}")
    print(f"PROTECTED : {counts['PROTECTED']}")
    print()
    print(f"Informe CSV : {csv_path}")
    print(f"Informe JSON: {json_path}")
    emit(
        "RESULT",
        "DETECT",
        counts["VALID"],
        counts["INVALID"],
        counts["UNKNOWN"],
        counts["PROTECTED"],
    )


def load_report():
    path = DATA_DIR / "latest.json"

    if not path.exists():
        sys.exit(
            "ERROR: no existe latest.json. Ejecuta primero 'detect'."
        )

    with path.open("r", encoding="utf-8") as handle:
        report = json.load(handle)

    if Path(report.get("rom_dir", "")).resolve() != ROM_DIR.resolve():
        sys.exit("ERROR: el informe pertenece a otro directorio de ROMs.")

    return report


def backup(path):
    if not path.exists():
        return None

    directory = DATA_DIR / "backups"
    directory.mkdir(parents=True, exist_ok=True)

    target = directory / f"{path.name}.{now_stamp()}.bak"
    shutil.copy2(path, target)

    return target


def read_userdata():
    if not USERDATA.exists():
        return []

    return USERDATA.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()


def userdata_key(line):
    if ":" not in line:
        return ""

    key = line.split(":", 1)[0]

    # Algunas versiones/entradas pueden escapar caracteres.
    return key.replace("\\.", ".").replace("\\_", "_").lower()


def field_name(field):
    return field.split("=", 1)[0].strip().lower()


def atomic_text(path, text):
    temp = path.with_name("." + path.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)



def move_unknown_roms(report, dry_run=False):
    unknown_items = [
        item
        for item in report["roms"]
        if item.get("status") == "UNKNOWN"
    ]

    result = {
        "total": len(unknown_items),
        "moved": 0,
        "already_there": 0,
        "changed": 0,
        "missing": 0,
        "conflicts": 0,
        "xml_removed": 0,
        "userdata_removed": 0,
        "media_removed": 0,
    }

    if not unknown_items:
        return result

    # Primero determinamos qué UNKNOWN pueden ponerse realmente
    # en cuarentena. Solo esos podrán perder sus metadatos.
    eligible = []

    unknown_dir = ROM_DIR / "unknown"

    for item in unknown_items:
        source = ROM_DIR / item["rom"]
        target = unknown_dir / source.name

        if target.exists():
            if source.exists():
                result["conflicts"] += 1
                continue

            # El ZIP ya fue movido en una ejecución anterior.
            eligible.append((item, source, target, True))
            result["already_there"] += 1
            continue

        if not source.exists():
            result["missing"] += 1
            continue

        stat = source.stat()

        if (
            stat.st_size != item.get("size")
            or stat.st_mtime_ns != item.get("mtime_ns")
        ):
            result["changed"] += 1
            continue

        eligible.append((item, source, target, False))

    successful_names = set()

    # En dry-run todos los elegibles se consideran operaciones válidas,
    # pero no se modifica nada.
    for item, source, target, already_there in eligible:
        if dry_run:
            result["moved"] += 1
            successful_names.add(item["rom"].lower())
            continue

        if already_there:
            result["moved"] += 1
            successful_names.add(item["rom"].lower())
            continue

        # Segunda comprobación justo antes de mover.
        if not source.exists():
            result["missing"] += 1
            continue

        stat = source.stat()

        if (
            stat.st_size != item.get("size")
            or stat.st_mtime_ns != item.get("mtime_ns")
        ):
            result["changed"] += 1
            continue

        if target.exists():
            result["conflicts"] += 1
            continue

        try:
            unknown_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            result["moved"] += 1
            successful_names.add(item["rom"].lower())
        except OSError as exc:
            print(f"\nERROR moviendo {source}: {exc}")

    if not successful_names:
        return result

    # Identificar entradas XML y medios asociados.
    tree, root, _ = load_gamelist()

    remove_nodes = []
    candidate_media = set()
    retained_media = set()

    for game in root.findall("game"):
        path_node = game.find("path")

        if path_node is None or not path_node.text:
            continue

        rom = normalize_rom_name(path_node.text)
        media = []

        for tag in ("image", "thumbnail", "video"):
            node = game.find(tag)

            if node is not None and node.text:
                safe = safe_media_path(node.text)

                if safe:
                    media.append(safe)

        if rom in successful_names:
            remove_nodes.append(game)
            candidate_media.update(media)
        else:
            retained_media.update(media)

    media_to_remove = candidate_media - retained_media

    userdata = read_userdata()
    new_userdata = []

    for line in userdata:
        if userdata_key(line) in successful_names:
            result["userdata_removed"] += 1
        else:
            new_userdata.append(line)

    result["xml_removed"] = len(remove_nodes)

    if dry_run:
        result["media_removed"] = sum(
            1
            for media in media_to_remove
            if media.exists() and media.is_file()
        )
        return result

    # Backup antes de modificar XML/INI.
    if remove_nodes or result["userdata_removed"]:
        gamelist_backup = backup(GAMELIST)
        userdata_backup = backup(USERDATA)

        if gamelist_backup:
            print(f"Backup: {gamelist_backup}")

        if userdata_backup:
            print(f"Backup: {userdata_backup}")

    if remove_nodes:
        for node in remove_nodes:
            root.remove(node)

        temp_xml = GAMELIST.with_name(".gamelist.xml.tmp")

        tree.write(
            temp_xml,
            encoding="utf-8",
            xml_declaration=True,
        )

        os.replace(temp_xml, GAMELIST)

    if USERDATA.exists() and result["userdata_removed"]:
        text = "\n".join(new_userdata)

        if text:
            text += "\n"

        atomic_text(USERDATA, text)

    for media in media_to_remove:
        if not media.exists() or not media.is_file():
            continue

        try:
            media.unlink()
            result["media_removed"] += 1
        except OSError as exc:
            print(f"\nERROR eliminando medio {media}: {exc}")

    return result


def repair(args):
    report = load_report()
    configure_report_policy(report)

    valid = [
        item
        for item in report["roms"]
        if item["status"] == "VALID" and item.get("best_core")
    ]

    if not valid:
        print("No hay ROMs VALID que reparar.")

    original = read_userdata()
    lines = list(original)

    positions = {}

    for index, line in enumerate(lines):
        key = userdata_key(line)

        if key:
            positions.setdefault(key, []).append(index)

    changed = 0
    added = 0
    started = time.monotonic()
    non_valid_count = sum(
        1 for item in report["roms"]
        if item["status"] in {"INVALID", "UNKNOWN"}
    )
    progress_total = len(valid) + non_valid_count
    emit("PLAN", "REPAIR", progress_total)

    for number, item in enumerate(valid, 1):
        rom = item["rom"]
        key = rom.lower()
        best = item["best_core"]

        existing = positions.get(key, [])

        if existing:
            for index in existing:
                line = lines[index]

                if ":" not in line:
                    continue

                raw_key, values = line.split(":", 1)

                fields = [
                    value.strip()
                    for value in values.split(",")
                    if value.strip()
                ]

                fields = [
                    value
                    for value in fields
                    if field_name(value) not in ("core", "emulator")
                ]

                # Para mame2003_plus dejamos que Recalbox use su default.
                if best != DEFAULT_CORE:
                    fields.append(f"core={best}")
                    fields.append("emulator=libretro")

                new_line = (
                    f"{raw_key}:{','.join(fields)}"
                    if fields else ""
                )

                if new_line != line:
                    lines[index] = new_line
                    changed += 1

        elif best != DEFAULT_CORE:
            lines.append(
                f"{rom}:core={best},emulator=libretro"
            )
            positions.setdefault(key, []).append(len(lines) - 1)
            changed += 1
            added += 1

        show_progress(
            number,
            len(valid),
            started,
            rom,
        )
        emit("PROGRESS", "REPAIR", number, progress_total, "VALID", rom)

    lines = [line for line in lines if line.strip()]

    print()
    print(f"ROMs VALID revisadas: {len(valid)}")
    print(f"Cambios necesarios  : {changed}")
    print(f"Entradas nuevas     : {added}")

    if args.dry_run:
        print("DRY-RUN: no se modificará gamelist-userdata.ini.")
    elif lines == original:
        print("No es necesario modificar gamelist-userdata.ini.")
    else:
        backup_path = backup(USERDATA)

        text = "\n".join(lines)

        if text:
            text += "\n"

        atomic_text(USERDATA, text)

        if backup_path:
            print(f"Backup: {backup_path}")

        print(f"Actualizado: {USERDATA}")

    quarantine_non_valid(args, len(valid), progress_total)


def safe_media_path(value):
    if not value:
        return None

    candidate = Path(value.strip())

    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (ROM_DIR / candidate).resolve()

    try:
        common = os.path.commonpath(
            [str(ROM_DIR.resolve()), str(resolved)]
        )
    except ValueError:
        return None

    if common != str(ROM_DIR.resolve()):
        return None

    return resolved


def quarantine_non_valid(args, progress_offset=0, progress_total=0):
    report = load_report()

    invalid_items = [
        item for item in report["roms"]
        if item["status"] == "INVALID"
    ]
    unknown_items = [
        item for item in report["roms"]
        if item["status"] == "UNKNOWN"
    ]

    # Dependencias de juegos válidos: nunca deben ponerse en cuarentena.
    protected_dependencies = set()
    for item in report["roms"]:
        if item["status"] != "VALID":
            continue
        protected_dependencies.update(
            dep.lower()
            for dep in item.get("dependencies", [])
            if dep
        )

    quarantine = []
    protected = 0
    changed = 0
    missing = 0
    conflicts = 0
    already_there = 0

    for status, items, dirname in (
        ("INVALID", invalid_items, "invalids"),
        ("UNKNOWN", unknown_items, "unknown"),
    ):
        target_dir = ROM_DIR / dirname

        for item in items:
            source = ROM_DIR / item["rom"]
            target = target_dir / source.name
            stem = source.stem.lower()

            if stem in protected_dependencies:
                protected += 1
                continue

            if target.exists():
                if source.exists():
                    conflicts += 1
                    continue

                # Ya fue movido anteriormente. Podemos purgar sus metadatos.
                quarantine.append((item, source, target, status, True))
                already_there += 1
                continue

            if not source.exists():
                missing += 1
                continue

            stat = source.stat()
            if (
                stat.st_size != item.get("size")
                or stat.st_mtime_ns != item.get("mtime_ns")
            ):
                changed += 1
                continue

            quarantine.append((item, source, target, status, False))

    purge_names = {
        item["rom"].lower()
        for item, _, _, _, _ in quarantine
    }

    tree, root, _ = load_gamelist()

    remove_nodes = []
    candidate_media = set()
    retained_media = set()

    for game in root.findall("game"):
        path_node = game.find("path")
        if path_node is None or not path_node.text:
            continue

        rom = normalize_rom_name(path_node.text)
        media = []

        for tag in ("image", "thumbnail", "video"):
            node = game.find(tag)
            if node is not None and node.text:
                safe = safe_media_path(node.text)
                if safe:
                    media.append(safe)

        if rom in purge_names:
            remove_nodes.append(game)
            candidate_media.update(media)
        else:
            retained_media.update(media)

    media_to_remove = candidate_media - retained_media

    userdata = read_userdata()
    new_userdata = []
    userdata_removed = 0

    for line in userdata:
        key = userdata_key(line)
        if key in purge_names:
            userdata_removed += 1
        else:
            new_userdata.append(line)

    print()
    print("MAME Validator - REPAIR / QUARANTINE")
    print("=================================")
    print(f"INVALID detectados : {len(invalid_items)}")
    print(f"UNKNOWN detectados : {len(unknown_items)}")
    print(f"En cuarentena      : {len(quarantine)}")

    if args.dry_run:
        print("DRY-RUN activo: no se modificará nada.")

    moved_invalid = 0
    moved_unknown = 0
    move_failed = set()

    started = time.monotonic()

    for number, (item, source, target, status, already) in enumerate(
        quarantine, 1
    ):
        if already:
            pass
        elif args.dry_run:
            if status == "INVALID":
                moved_invalid += 1
            else:
                moved_unknown += 1
        else:
            # Segunda comprobación inmediatamente antes de mover.
            if not source.exists():
                missing += 1
                move_failed.add(item["rom"].lower())
            else:
                stat = source.stat()
                if (
                    stat.st_size != item.get("size")
                    or stat.st_mtime_ns != item.get("mtime_ns")
                ):
                    changed += 1
                    move_failed.add(item["rom"].lower())
                elif target.exists():
                    conflicts += 1
                    move_failed.add(item["rom"].lower())
                else:
                    try:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(source), str(target))
                        if status == "INVALID":
                            moved_invalid += 1
                        else:
                            moved_unknown += 1
                    except OSError as exc:
                        move_failed.add(item["rom"].lower())
                        print(f"\nERROR moviendo {source}: {exc}")

        show_progress(
            number,
            len(quarantine),
            started,
            item["rom"],
        )
        emit(
            "PROGRESS",
            "REPAIR",
            progress_offset + number,
            progress_total,
            status,
            item["rom"],
        )

    # Si un movimiento real falló, NO purgar sus metadatos.
    if move_failed:
        purge_names -= move_failed

        remove_nodes = []
        candidate_media = set()
        retained_media = set()

        for game in root.findall("game"):
            path_node = game.find("path")
            if path_node is None or not path_node.text:
                continue

            rom = normalize_rom_name(path_node.text)
            media = []

            for tag in ("image", "thumbnail", "video"):
                node = game.find(tag)
                if node is not None and node.text:
                    safe = safe_media_path(node.text)
                    if safe:
                        media.append(safe)

            if rom in purge_names:
                remove_nodes.append(game)
                candidate_media.update(media)
            else:
                retained_media.update(media)

        media_to_remove = candidate_media - retained_media

        new_userdata = []
        userdata_removed = 0
        for line in userdata:
            key = userdata_key(line)
            if key in purge_names:
                userdata_removed += 1
            else:
                new_userdata.append(line)

    media_removed = 0

    if not args.dry_run and purge_names:
        gamelist_backup = backup(GAMELIST)
        userdata_backup = backup(USERDATA)

        if gamelist_backup:
            print(f"Backup: {gamelist_backup}")
        if userdata_backup:
            print(f"Backup: {userdata_backup}")

        for node in remove_nodes:
            root.remove(node)

        temp_xml = GAMELIST.with_name(".gamelist.xml.tmp")
        tree.write(
            temp_xml,
            encoding="utf-8",
            xml_declaration=True,
        )
        os.replace(temp_xml, GAMELIST)

        if USERDATA.exists():
            text = "\n".join(new_userdata)
            if text:
                text += "\n"
            atomic_text(USERDATA, text)

    for media in media_to_remove:
        if not media.exists() or not media.is_file():
            continue

        if args.dry_run:
            media_removed += 1
        else:
            try:
                media.unlink()
                media_removed += 1
            except OSError as exc:
                print(f"\nERROR eliminando medio {media}: {exc}")

    print()
    print("RESULTADO")
    print("=========")
    print(f"INVALID movibles/movidos : {moved_invalid}")
    print(f"UNKNOWN movibles/movidos : {moved_unknown}")
    print(f"Ya estaban en cuarentena : {already_there}")
    print(f"Dependencias protegidas  : {protected}")
    print(f"Cambiados desde detect   : {changed}")
    print(f"No encontrados           : {missing}")
    print(f"Conflictos de destino    : {conflicts}")
    print(f"Entradas XML retiradas   : {len(remove_nodes)}")
    print(f"Entradas INI retiradas   : {userdata_removed}")
    print(f"Medios retirados         : {media_removed}")

    if args.dry_run:
        print()
        print("DRY-RUN terminado. No se realizó ningún cambio.")

    emit("PROGRESS", "REPAIR", progress_total, progress_total, "DONE", "")
    emit(
        "RESULT",
        "REPAIR",
        moved_invalid,
        moved_unknown,
        protected,
        changed,
        missing,
        conflicts,
        len(remove_nodes),
        userdata_removed,
        media_removed,
    )


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Validador y reparador de ROMsets MAME para Recalbox."
        ),
        epilog=(
            "Flujo recomendado: detect -> revisar latest.csv -> "
            "repair --dry-run -> repair"
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    parser.add_argument(
        "--rom-dir",
        default=None,
        help="Directorio de ROMs MAME (default: /recalbox/share/roms/mame)",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directorio persistente para informes y copias de seguridad",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Emitir eventos estructurados para una interfaz gráfica",
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    detect_parser = commands.add_parser(
        "detect",
        help="Analizar todos los ZIP y generar un informe",
    )
    detect_parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="Timeout máximo por prueba/core (default: 3 segundos)",
    )
    detect_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Analizar solo las primeras N ROMs (para pruebas)",
    )
    detect_parser.set_defaults(function=detect)

    repair_parser = commands.add_parser(
        "repair",
        help="Reparar VALID y poner INVALID/UNKNOWN en cuarentena",
    )
    repair_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simular reparación/cuarentena sin modificar ni mover archivos",
    )
    repair_parser.set_defaults(function=repair)

    return parser


def main():
    global STRUCTURED_PROGRESS
    parser = build_parser()
    args = parser.parse_args()
    configure_runtime_paths(args.rom_dir, args.data_dir)
    STRUCTURED_PROGRESS = args.progress
    args.function(args)


if __name__ == "__main__":
    main()
