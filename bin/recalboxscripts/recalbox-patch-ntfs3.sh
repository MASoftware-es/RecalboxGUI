#!/bin/bash

# Parche NTFS3 para RecalboxGUI.
# Corrige 3mounts para usar el driver ntfs3 cuando udev detecta NTFS.

set -u

VERSION="2.0"
THREEMOUNTS="/usr/bin/3mounts"
CONFIG="/etc/3mounts/3mounts.conf"
PATCH_LINE='    [ "$fstype" = "ntfs" ] && fstype=ntfs3'
MODE="apply"
ROOT_REMOUNTED=0
TEMP_THREEMOUNTS=""
TEMP_CONFIG=""

usage() {
    echo "Uso: bash $0 [--check|--apply|--version]"
}

cleanup() {
    result=$?
    [ -z "$TEMP_THREEMOUNTS" ] || rm -f "$TEMP_THREEMOUNTS"
    [ -z "$TEMP_CONFIG" ] || rm -f "$TEMP_CONFIG"
    if [ "$ROOT_REMOUNTED" -eq 1 ]; then
        sync
        if ! mount -o remount,ro /; then
            echo "ERROR: No se pudo devolver / al modo de solo lectura."
            result=1
        fi
    fi
    trap - EXIT
    exit "$result"
}
trap cleanup EXIT

case "${1:-}" in
    ""|--apply) MODE="apply" ;;
    --check) MODE="check" ;;
    --version) echo "recalbox-patch-ntfs3 $VERSION"; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: Opción desconocida: $1"; usage; exit 2 ;;
esac

if [ "$#" -gt 1 ]; then
    usage
    exit 2
fi

echo "=== Parche NTFS3 para Recalbox ==="
echo "MODE=$MODE"

if [ ! -f "$THREEMOUNTS" ]; then
    echo "STATUS=UNSUPPORTED"
    echo "ERROR: No existe $THREEMOUNTS"
    exit 20
fi
if [ ! -f "$CONFIG" ]; then
    echo "STATUS=UNSUPPORTED"
    echo "ERROR: No existe $CONFIG"
    exit 20
fi

patch_3mounts=0
patch_config=0
grep -Fq '[ "$fstype" = "ntfs" ] && fstype=ntfs3' "$THREEMOUNTS" && patch_3mounts=1
if grep '^FILESYSTEMS=' "$CONFIG" | grep -qw ntfs3; then
    patch_config=1
fi

echo "PATCH_3MOUNTS=$patch_3mounts"
echo "PATCH_CONFIG=$patch_config"

if [ "$patch_3mounts" -eq 1 ] && [ "$patch_config" -eq 1 ]; then
    echo "STATUS=ALREADY_APPLIED"
    echo "OK: El parche NTFS3 ya está aplicado completamente."
    exit 0
fi

echo "STATUS=PATCH_REQUIRED"
if [ "$MODE" = "check" ]; then
    echo "INFO: El parche NTFS3 todavía necesita aplicarse."
    exit 10
fi

if [ "$(id -u)" != "0" ]; then
    echo "STATUS=ERROR"
    echo "ERROR: Este script debe ejecutarse como root."
    exit 1
fi

# Validar los puntos de inserción antes de hacer escribible la raíz.
if [ "$patch_3mounts" -eq 0 ] && ! grep -Fq 'fstype=$ID_FS_TYPE' "$THREEMOUNTS"; then
    echo "STATUS=UNSUPPORTED"
    echo "ERROR: No se encuentra el punto de inserción esperado en $THREEMOUNTS"
    exit 20
fi
if [ "$patch_config" -eq 0 ]; then
    if ! grep '^FILESYSTEMS=' "$CONFIG" | grep -qw ntfs; then
        echo "STATUS=UNSUPPORTED"
        echo "ERROR: No se encuentra NTFS en la variable FILESYSTEMS de $CONFIG"
        exit 20
    fi
fi

TEMP_THREEMOUNTS="$(mktemp /tmp/recalboxgui-3mounts.XXXXXX)" || exit 1
TEMP_CONFIG="$(mktemp /tmp/recalboxgui-3mounts-conf.XXXXXX)" || exit 1
cp -p "$THREEMOUNTS" "$TEMP_THREEMOUNTS" || exit 1
cp -p "$CONFIG" "$TEMP_CONFIG" || exit 1

if [ "$patch_3mounts" -eq 0 ]; then
    sed -i '/fstype=\$ID_FS_TYPE/a\    [ "$fstype" = "ntfs" ] \&\& fstype=ntfs3' "$TEMP_THREEMOUNTS"
    if ! grep -Fq '[ "$fstype" = "ntfs" ] && fstype=ntfs3' "$TEMP_THREEMOUNTS"; then
        echo "STATUS=ERROR"
        echo "ERROR: No se pudo preparar el parche para $THREEMOUNTS"
        exit 1
    fi
fi

if [ "$patch_config" -eq 0 ]; then
    sed -i '/^FILESYSTEMS=/ s/ntfs/ntfs ntfs3/' "$TEMP_CONFIG"
    if ! grep '^FILESYSTEMS=' "$TEMP_CONFIG" | grep -qw ntfs3; then
        echo "STATUS=ERROR"
        echo "ERROR: No se pudo preparar el parche para $CONFIG"
        exit 1
    fi
fi

root_options="$(awk '$2 == "/" { print $4; exit }' /proc/mounts)"
case ",$root_options," in
    *,rw,*) ;;
    *)
        echo "INFO: Montando / en modo lectura/escritura..."
        if ! mount -o remount,rw /; then
            echo "STATUS=ERROR"
            echo "ERROR: No se pudo montar / en modo lectura/escritura."
            exit 1
        fi
        ROOT_REMOUNTED=1
        ;;
esac

# Los backups validados no se sobrescriben en ejecuciones posteriores.
if [ "$patch_3mounts" -eq 0 ]; then
    [ -e "${THREEMOUNTS}.recalboxgui.bak" ] || cp -p "$THREEMOUNTS" "${THREEMOUNTS}.recalboxgui.bak"
    cp -p "$TEMP_THREEMOUNTS" "$THREEMOUNTS"
fi
if [ "$patch_config" -eq 0 ]; then
    [ -e "${CONFIG}.recalboxgui.bak" ] || cp -p "$CONFIG" "${CONFIG}.recalboxgui.bak"
    cp -p "$TEMP_CONFIG" "$CONFIG"
fi

if ! grep -Fq '[ "$fstype" = "ntfs" ] && fstype=ntfs3' "$THREEMOUNTS" || \
   ! grep '^FILESYSTEMS=' "$CONFIG" | grep -qw ntfs3; then
    echo "STATUS=ERROR"
    echo "ERROR: La verificación posterior del parche ha fallado."
    exit 1
fi

if modprobe ntfs3; then
    echo "OK: El módulo ntfs3 está disponible."
else
    echo "WARNING: No se pudo cargar el módulo ntfs3."
fi

if [ "$ROOT_REMOUNTED" -eq 1 ]; then
    echo "INFO: Devolviendo / al modo de solo lectura..."
    sync
    if ! mount -o remount,ro /; then
        echo "STATUS=ERROR"
        echo "ERROR: El parche se aplicó, pero no se pudo proteger de nuevo la raíz."
        exit 1
    fi
    ROOT_REMOUNTED=0
fi

echo "STATUS=APPLIED"
echo "OK: El parche NTFS3 se ha aplicado y verificado correctamente."
