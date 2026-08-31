#!/bin/bash

set -u

VERSION="2.0"
DRY_RUN=0
ITERATE=0
PROGRESS=0
PATHS=()
SYSTEM_DIRS=()
SYSTEM_TOTAL=0
FILE_TOTAL=0
WORK_TOTAL=0
WORK_DONE=0
GLOBAL_CHECKED=0
GLOBAL_REFERENCED=0
GLOBAL_UNREFERENCED=0
GLOBAL_REMOVED=0
GLOBAL_ERRORS=0
GLOBAL_SKIPPED=0

usage() {
    echo "Uso:"
    echo "  bash $0 [--dry-run] [--progress] /ruta/sistema/ [/ruta/sistema2/ ...]"
    echo "  bash $0 --iterate [--dry-run] [--progress] /ruta/roms/"
    echo
    echo "Opciones:"
    echo "  --dry-run   Simula la limpieza sin eliminar archivos."
    echo "  --iterate   Itera por cada subdirectorio de una única ruta."
    echo "  --progress  Emite eventos estructurados para mostrar progreso."
    echo "  --version   Muestra la versión del script."
    echo "  -h, --help  Muestra esta ayuda."
    echo
    echo "Sin --iterate pueden indicarse uno o varios directorios de sistemas."
    echo "--iterate exige exactamente una ruta raíz."
    echo
    echo "Procesa únicamente:"
    echo "  media/images"
    echo "  media/thumbnails"
    echo "  media/videos"
    echo
    echo "Una referencia <image>, <thumbnail> o <video> puede apuntar a"
    echo "cualquiera de esas tres carpetas. No modifica downloaded_images."
}

emit() {
    [ "$PROGRESS" -eq 1 ] || return 0
    echo "RCGUI|$*"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --iterate) ITERATE=1 ;;
        --progress) PROGRESS=1 ;;
        --version) echo "recalbox-clean-media $VERSION"; exit 0 ;;
        -h|--help) usage; exit 0 ;;
        --)
            shift
            while [ "$#" -gt 0 ]; do
                PATHS+=("${1%/}")
                shift
            done
            break
            ;;
        -*)
            echo "ERROR: opción desconocida: $1"
            echo
            usage
            exit 2
            ;;
        *) PATHS+=("${1%/}") ;;
    esac
    shift
done

if [ "${#PATHS[@]}" -eq 0 ]; then
    echo "ERROR: debe indicarse al menos un directorio."
    echo
    usage
    exit 2
fi
if [ "$ITERATE" -eq 1 ] && [ "${#PATHS[@]}" -ne 1 ]; then
    echo "ERROR: --iterate solo puede utilizarse con una única ruta."
    exit 2
fi

# Validar todas las rutas antes de iniciar cualquier posible eliminación.
for index in "${!PATHS[@]}"; do
    path="${PATHS[$index]}"
    if [ ! -d "$path" ]; then
        echo "ERROR: no existe el directorio: $path"
        exit 2
    fi
    PATHS[$index]="$(cd "$path" && pwd -P)"
done
for first in "${!PATHS[@]}"; do
    for second in "${!PATHS[@]}"; do
        if [ "$first" -lt "$second" ] && [ "${PATHS[$first]}" = "${PATHS[$second]}" ]; then
            echo "ERROR: el directorio está repetido: ${PATHS[$first]}"
            exit 2
        fi
    done
done

if [ "$ITERATE" -eq 1 ]; then
    while IFS= read -r -d '' system_dir; do
        SYSTEM_DIRS+=("${system_dir%/}")
    done < <(find "${PATHS[0]}" -mindepth 1 -maxdepth 1 -type d -print0)
else
    SYSTEM_DIRS=("${PATHS[@]}")
fi

count_media_files() {
    local roms_dir="${1%/}"
    local subdir
    local file
    local count=0
    for subdir in images thumbnails videos; do
        [ -d "$roms_dir/media/$subdir" ] || continue
        while IFS= read -r -d '' file; do
            count=$((count + 1))
        done < <(find "$roms_dir/media/$subdir" -maxdepth 1 -type f -print0)
    done
    COUNT_RESULT=$count
}

SYSTEM_TOTAL=${#SYSTEM_DIRS[@]}
for system_dir in "${SYSTEM_DIRS[@]}"; do
    count_media_files "$system_dir"
    FILE_TOTAL=$((FILE_TOTAL + COUNT_RESULT))
done
WORK_TOTAL=$((SYSTEM_TOTAL + FILE_TOTAL))
emit "PLAN|$SYSTEM_TOTAL|$FILE_TOTAL|$WORK_TOTAL|$DRY_RUN"

emit_progress() {
    emit "PROGRESS|$WORK_DONE|$WORK_TOTAL|$1|$SYSTEM_TOTAL"
}

advance_skipped_system() {
    local roms_dir="$1"
    local system_index="$2"
    count_media_files "$roms_dir"
    WORK_DONE=$((WORK_DONE + COUNT_RESULT + 1))
    emit_progress "$system_index"
}

validate_xml() {
    command -v python3 >/dev/null 2>&1 || return 1
    python3 - "$1" <<'PY'
import sys
import xml.etree.ElementTree as ET

try:
    ET.parse(sys.argv[1])
except (OSError, ET.ParseError):
    raise SystemExit(1)
PY
}

clean_system() {
    local roms_dir="${1%/}"
    local system_index="$2"
    local gamelist="$roms_dir/gamelist.xml"
    local media_dir="$roms_dir/media"
    local total=0
    local referenced=0
    local unreferenced=0
    local removed=0
    local errors=0

    echo "Procesando: $roms_dir"
    emit "SYSTEM|START|$system_index|$SYSTEM_TOTAL"

    if [ ! -f "$gamelist" ]; then
        echo "OMITIDO: $roms_dir (sin gamelist.xml)"
        GLOBAL_SKIPPED=$((GLOBAL_SKIPPED + 1))
        emit "SYSTEM|SKIPPED|$system_index|NO_GAMELIST"
        advance_skipped_system "$roms_dir" "$system_index"
        return
    fi
    if [ ! -d "$media_dir" ]; then
        echo "OMITIDO: $roms_dir (sin carpeta media)"
        GLOBAL_SKIPPED=$((GLOBAL_SKIPPED + 1))
        emit "SYSTEM|SKIPPED|$system_index|NO_MEDIA"
        advance_skipped_system "$roms_dir" "$system_index"
        return
    fi
    if [ ! -r "$gamelist" ]; then
        echo "ERROR: no se puede leer $gamelist"
        errors=$((errors + 1))
        GLOBAL_ERRORS=$((GLOBAL_ERRORS + 1))
        emit "SYSTEM|ERROR|$system_index|UNREADABLE_GAMELIST"
        advance_skipped_system "$roms_dir" "$system_index"
        return
    fi
    if ! validate_xml "$gamelist"; then
        echo "ERROR: $gamelist no es un XML válido o no puede analizarse."
        echo "No se eliminará ningún medio de este sistema."
        errors=$((errors + 1))
        GLOBAL_ERRORS=$((GLOBAL_ERRORS + 1))
        emit "SYSTEM|ERROR|$system_index|INVALID_GAMELIST"
        advance_skipped_system "$roms_dir" "$system_index"
        return
    fi

    echo
    echo "Clean Media"
    echo "==========="
    echo "ROMs     : $roms_dir"
    echo "Gamelist : $gamelist"
    echo "Media    : $media_dir"
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "Modo     : DRY-RUN"
    else
        echo "Modo     : BORRADO"
    fi
    echo

    clean_directory() {
        local subdir="$1"
        local dir="$media_dir/$subdir"
        local file
        local filename
        local xml_filename
        [ -d "$dir" ] || return
        echo "--- $subdir ---"

        while IFS= read -r -d '' file; do
            total=$((total + 1))
            filename="${file##*/}"
            xml_filename="$(printf '%s' "$filename" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')"

            if grep -Fq "<image>media/$subdir/$xml_filename</image>" "$gamelist" || \
               grep -Fq "<image>./media/$subdir/$xml_filename</image>" "$gamelist" || \
               grep -Fq "<thumbnail>media/$subdir/$xml_filename</thumbnail>" "$gamelist" || \
               grep -Fq "<thumbnail>./media/$subdir/$xml_filename</thumbnail>" "$gamelist" || \
               grep -Fq "<video>media/$subdir/$xml_filename</video>" "$gamelist" || \
               grep -Fq "<video>./media/$subdir/$xml_filename</video>" "$gamelist"; then
                referenced=$((referenced + 1))
            else
                unreferenced=$((unreferenced + 1))
                echo "NO REFERENCIADO: $subdir/$filename"
                if [ "$DRY_RUN" -eq 0 ]; then
                    if rm -f "$file"; then
                        removed=$((removed + 1))
                    else
                        echo "ERROR eliminando: $file"
                        errors=$((errors + 1))
                    fi
                fi
            fi
            WORK_DONE=$((WORK_DONE + 1))
            emit_progress "$system_index"
        done < <(find "$dir" -maxdepth 1 -type f -print0)
    }

    clean_directory "images"
    clean_directory "thumbnails"
    clean_directory "videos"

    WORK_DONE=$((WORK_DONE + 1))
    emit_progress "$system_index"
    GLOBAL_CHECKED=$((GLOBAL_CHECKED + total))
    GLOBAL_REFERENCED=$((GLOBAL_REFERENCED + referenced))
    GLOBAL_UNREFERENCED=$((GLOBAL_UNREFERENCED + unreferenced))
    GLOBAL_REMOVED=$((GLOBAL_REMOVED + removed))
    GLOBAL_ERRORS=$((GLOBAL_ERRORS + errors))

    echo
    echo "RESULTADO"
    echo "========="
    echo "Archivos comprobados: $total"
    echo "Referenciados       : $referenced"
    echo "No referenciados    : $unreferenced"
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "Se eliminarían      : $unreferenced"
    else
        echo "Eliminados          : $removed"
        echo "Errores             : $errors"
    fi
    emit "SYSTEM|DONE|$system_index|$total|$referenced|$unreferenced|$removed|$errors"
}

system_index=0
for system_dir in "${SYSTEM_DIRS[@]}"; do
    system_index=$((system_index + 1))
    clean_system "$system_dir" "$system_index"
done

echo
echo "RESULTADO GLOBAL"
echo "================"
echo "Sistemas procesados : $SYSTEM_TOTAL"
echo "Sistemas omitidos   : $GLOBAL_SKIPPED"
echo "Archivos comprobados: $GLOBAL_CHECKED"
echo "Referenciados       : $GLOBAL_REFERENCED"
echo "No referenciados    : $GLOBAL_UNREFERENCED"
if [ "$DRY_RUN" -eq 1 ]; then
    echo "Se eliminarían      : $GLOBAL_UNREFERENCED"
else
    echo "Eliminados          : $GLOBAL_REMOVED"
fi
echo "Errores             : $GLOBAL_ERRORS"
emit "RESULT|$GLOBAL_CHECKED|$GLOBAL_REFERENCED|$GLOBAL_UNREFERENCED|$GLOBAL_REMOVED|$GLOBAL_ERRORS|$GLOBAL_SKIPPED"

[ "$GLOBAL_ERRORS" -eq 0 ] || exit 1
