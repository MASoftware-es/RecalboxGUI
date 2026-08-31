#!/usr/bin/env bash

set -u

VERSION="1.1"
ES_SERVICE="/etc/init.d/S31emulationstation"

emit_result() {
    printf 'STATUS=%s\n' "$1"
    printf 'RCGUI|RESULT|SERVICES|%s\n' "$1"
}

frontend_busy() {
    pidof retroarch kodi kodi.bin emulatorlauncher >/dev/null 2>&1
}

case "${1:-}" in
    status)
        [ -x "$ES_SERVICE" ] || {
            emit_result "EMULATIONSTATION_SERVICE_MISSING"
            exit 2
        }
        if frontend_busy; then
            emit_result "FRONTEND_BUSY"
        else
            emit_result "READY"
        fi
        ;;
    restart-emulationstation)
        [ -x "$ES_SERVICE" ] || {
            emit_result "EMULATIONSTATION_SERVICE_MISSING"
            exit 2
        }
        if frontend_busy; then
            emit_result "FRONTEND_BUSY"
            exit 20
        fi
        "$ES_SERVICE" restart
        attempts=0
        while [ "$attempts" -lt 50 ]; do
            if "$ES_SERVICE" status >/dev/null 2>&1; then
                emit_result "EMULATIONSTATION_RESTARTED"
                exit 0
            fi
            sleep 0.1
            attempts=$((attempts + 1))
        done
        emit_result "EMULATIONSTATION_START_FAILED"
        exit 1
        ;;
    restart-recalbox)
        [ -x /sbin/shutdown ] || {
            emit_result "REBOOT_COMMAND_MISSING"
            exit 2
        }
        # El retraso permite devolver el resultado, retirar este script de
        # /tmp y cerrar ordenadamente la sesión SSH antes del reinicio.
        (sleep 3; /sbin/shutdown -r now) >/dev/null 2>&1 &
        emit_result "RECALBOX_RESTART_SCHEDULED"
        ;;
    shutdown-recalbox)
        [ -x /sbin/shutdown ] || {
            emit_result "SHUTDOWN_COMMAND_MISSING"
            exit 2
        }
        # El retraso permite devolver el resultado, retirar este script de
        # /tmp y cerrar ordenadamente la sesión SSH antes del apagado.
        (sleep 3; /sbin/shutdown -h now) >/dev/null 2>&1 &
        emit_result "RECALBOX_SHUTDOWN_SCHEDULED"
        ;;
    --version)
        printf 'recalbox-restart-services %s\n' "$VERSION"
        ;;
    *)
        printf 'Uso: %s {status|restart-emulationstation|restart-recalbox|shutdown-recalbox}\n' "$0" >&2
        exit 2
        ;;
esac
