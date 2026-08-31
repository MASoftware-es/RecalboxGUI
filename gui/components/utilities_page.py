from __future__ import annotations

import posixpath

from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from ..connection import (
    RecalboxConnection,
    RemoteDirectoryAttempt,
    RemoteScriptAttempt,
    RemoteScriptResult,
)
from ..i18n import Translator
from ..utilities import UTILITIES, UtilityDefinition
from ..utils import (
    ask_confirmation,
    AnonymousSambaOpener,
    show_error,
    show_information,
    show_warning,
)
from .clean_media_controls import CleanMediaControls
from .mame_validator_controls import RomValidatorControls
from .page_title import PageTitle
from .service_restart_controls import ServiceRestartControls


class UtilitiesPage(QWidget):
    recalboxRestartScheduled = Signal()
    recalboxShutdownScheduled = Signal()

    def __init__(self, connection: RecalboxConnection, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        self.connection = connection
        self.translator = translator
        self._selected: UtilityDefinition | None = None
        self._thread: QThread | None = None
        self._worker: QObject | None = None
        self._mode = ""
        self._queued_mode = ""
        self._directories_loaded = False
        self._validator_reports_ready: dict[str, bool] = {}
        self._samba_opener = AnonymousSambaOpener(self)
        self._samba_opener.busyChanged.connect(
            lambda busy: self.rom_validator.open_folder_button.setEnabled(
                not busy and not self.busy
            )
        )
        self._samba_opener.failed.connect(self._samba_open_failed)

        self.utility_list = QListWidget()
        self.utility_list.setMinimumWidth(280)
        self.title = PageTitle()
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.form = QFormLayout()
        self.form_container = QWidget()
        self.form_container.setLayout(self.form)
        self.clean_media = CleanMediaControls(translator)
        self.rom_validator = RomValidatorControls(translator, "utility.mame")
        self.service_restart = ServiceRestartControls(translator)
        self.status = QLabel()
        self.status.setProperty("role", "muted")
        self.status.setWordWrap(True)
        self.apply_button = QPushButton()
        self.apply_button.setProperty("execution", True)

        detail = QVBoxLayout()
        detail.addWidget(self.title)
        detail.addWidget(self.description)
        detail.addWidget(self.form_container)
        detail.addWidget(self.clean_media, 1)
        detail.addWidget(self.rom_validator)
        detail.addWidget(self.service_restart)
        detail.addStretch()
        detail.addWidget(self.status)
        detail.addWidget(self.apply_button, 0, Qt.AlignmentFlag.AlignRight)
        body = QHBoxLayout(self)
        body.addWidget(self.utility_list, 1)
        body.addLayout(detail, 2)

        self.utility_list.currentRowChanged.connect(self._select_utility)
        self.apply_button.clicked.connect(lambda: self._start_patch_script("check"))
        self.clean_media.testRequested.connect(lambda: self._start_clean_media(False))
        self.clean_media.executeRequested.connect(lambda: self._start_clean_media(True))
        self.rom_validator.analyzeRequested.connect(self._start_validator_analysis)
        self.rom_validator.correctRequested.connect(self._start_validator_correction)
        self.rom_validator.openFolderRequested.connect(self._open_validator_folder)
        self.service_restart.restartEmulationStationRequested.connect(
            lambda: self._start_service_restart("restart-emulationstation")
        )
        self.service_restart.restartRecalboxRequested.connect(
            lambda: self._start_service_restart("restart-recalbox")
        )
        self.service_restart.shutdownRecalboxRequested.connect(
            lambda: self._start_service_restart("shutdown-recalbox")
        )
        self._populate()

    @property
    def busy(self) -> bool:
        return self._thread is not None

    def _populate(self) -> None:
        selected_id = self._selected.identifier if self._selected else ""
        self.utility_list.blockSignals(True)
        self.utility_list.clear()
        selected_row = 0
        for row, utility in enumerate(UTILITIES):
            item = QListWidgetItem(self.translator(utility.name_key))
            item.setData(Qt.ItemDataRole.UserRole, utility.identifier)
            self.utility_list.addItem(item)
            if utility.identifier == selected_id:
                selected_row = row
        self.utility_list.blockSignals(False)
        if UTILITIES:
            self.utility_list.setCurrentRow(selected_row)
            self._select_utility(selected_row)

    def _select_utility(self, row: int) -> None:
        self._selected = UTILITIES[row] if 0 <= row < len(UTILITIES) else None
        self.status.clear()
        self._update_detail()
        if self._selected and self._selected.kind == "clean_media" and not self._directories_loaded:
            self._load_directories()

    def _update_detail(self) -> None:
        enabled = self._selected is not None
        is_action = bool(self._selected and self._selected.kind == "action")
        is_clean_media = bool(self._selected and self._selected.kind == "clean_media")
        is_rom_validator = bool(self._selected and self._selected.kind == "rom_validator")
        is_restart_services = bool(
            self._selected and self._selected.kind == "restart_services"
        )
        self.title.setVisible(enabled)
        self.description.setVisible(enabled)
        self.form_container.setVisible(is_action and self.form.rowCount() > 0)
        self.apply_button.setVisible(is_action)
        self.apply_button.setEnabled(is_action and not self.busy)
        self.clean_media.setVisible(is_clean_media)
        self.clean_media.set_busy(self.busy)
        self.rom_validator.setVisible(is_rom_validator)
        self.rom_validator.set_busy(self.busy)
        if is_rom_validator:
            system = self._selected.validator_system
            self.rom_validator.set_translation_prefix(f"utility.{system}")
            self.rom_validator.set_report_ready(
                self._validator_reports_ready.get(system, False)
            )
        self.service_restart.setVisible(is_restart_services)
        self.service_restart.set_busy(self.busy)
        if self._selected:
            self.title.setText(self.translator(self._selected.name_key))
            self.description.setText(self.translator(self._selected.description_key))
            self.apply_button.setText(self.translator("utility.apply"))

    def retranslate_ui(self) -> None:
        self.clean_media.retranslate_ui()
        self.rom_validator.retranslate_ui()
        self.service_restart.retranslate_ui()
        self._populate()
        self._update_detail()

    def _begin_worker(self, worker: QObject) -> None:
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._worker_finished)
        self._thread = thread
        self._worker = worker
        self.utility_list.setEnabled(False)
        self._update_detail()
        thread.start()

    def _load_directories(self) -> None:
        if self.busy:
            return
        self._mode = "list_directories"
        self.status.setText(self.translator("utility.clean_media.loading"))
        worker = RemoteDirectoryAttempt(self.connection, self.connection.environment.roms_path)
        worker.succeeded.connect(self._directories_succeeded)
        worker.failed.connect(self._worker_failed)
        self._begin_worker(worker)

    def _directories_succeeded(self, names: list[str]) -> None:
        self._directories_loaded = True
        self.clean_media.directories.set_directories(names)
        key = "utility.clean_media.loaded" if names else "utility.clean_media.empty"
        self.status.setText(self.translator(key, count=len(names)))

    def _start_patch_script(self, mode: str) -> None:
        if not self._validate_script():
            return
        self._mode = mode
        self.status.setText(self.translator("utility.checking" if mode == "check" else "utility.applying"))
        worker = RemoteScriptAttempt(
            self.connection,
            self._selected.script,
            ("--check",) if mode == "check" else ("--apply",),
        )
        worker.succeeded.connect(self._patch_script_succeeded)
        worker.failed.connect(self._worker_failed)
        self._begin_worker(worker)

    def _start_clean_media(self, execute: bool) -> None:
        if not self._validate_script():
            return
        directories = self.clean_media.selected_directories()
        if not directories:
            return
        if execute and not ask_confirmation(
            self,
            self.translator("utility.clean_media.confirm_title"),
            self.translator("utility.clean_media.confirm_execute", count=len(directories)),
        ):
            return
        root = self.connection.environment.roms_path.rstrip("/")
        paths = tuple(posixpath.join(root, name) for name in directories)
        arguments = ("--progress", *(tuple() if execute else ("--dry-run",)), *paths)
        self._mode = "clean_execute" if execute else "clean_test"
        self.status.setText(
            self.translator("utility.clean_media.executing" if execute else "utility.clean_media.testing")
        )
        self.clean_media.reset_progress()
        worker = RemoteScriptAttempt(self.connection, self._selected.script, arguments)
        worker.outputLine.connect(self._clean_media_output)
        worker.succeeded.connect(self._clean_media_succeeded)
        worker.failed.connect(self._worker_failed)
        self._begin_worker(worker)

    def _validator_system(self) -> str:
        return self._selected.validator_system if self._selected else ""

    def _validator_arguments(self, command: str) -> tuple[str, ...]:
        system = self._validator_system()
        rom_dir = posixpath.join(
            self.connection.environment.roms_path.rstrip("/"), system
        )
        data_dir = self._validator_data_dir(system)
        return (
            "--rom-dir",
            rom_dir,
            "--data-dir",
            data_dir,
            "--progress",
            command,
        )

    @staticmethod
    def _validator_data_dir(system: str) -> str:
        return f"/recalbox/share/system/recalboxgui/validators/{system}"

    def _register_validator_report_cleanup(self, system: str) -> None:
        data_dir = self._validator_data_dir(system)
        self.connection.register_cleanup_paths(
            f"{data_dir}/latest.json",
            f"{data_dir}/latest.csv",
            f"{data_dir}/.latest.json.tmp",
            f"{data_dir}/.latest.csv.tmp",
        )

    def _open_validator_folder(self) -> None:
        system = self._validator_system()
        remote_root = self.connection.environment.roms_path.rstrip("/")
        remote_path = posixpath.join(remote_root, system)
        share_root = "/recalbox/share"
        if remote_path != share_root and not remote_path.startswith(share_root + "/"):
            show_error(
                self,
                self.translator("utility.samba.open_error_title"),
                self.translator("utility.samba.open_unshared", path=remote_path),
            )
            return
        relative = remote_path[len(share_root):].lstrip("/")
        url = QUrl()
        url.setScheme("smb")
        url.setHost(self.connection.environment.host)
        url.setPath("/share" + (f"/{relative}" if relative else ""))
        if not self._samba_opener.open(url) and not self._samba_opener.busy:
            show_error(
                self,
                self.translator("utility.samba.open_error_title"),
                self.translator("utility.samba.open_error", url=url.toString()),
            )

    def _samba_open_failed(self, detail: str) -> None:
        if detail == "GVFS_NOT_AVAILABLE":
            message = self.translator("utility.samba.gio_missing")
        elif detail == "FILE_MANAGER_FAILED":
            message = self.translator("utility.samba.open_error", url="smb://")
        else:
            message = self.translator(
                "utility.samba.anonymous_error", detail=detail
            )
        show_error(
            self,
            self.translator("utility.samba.open_error_title"),
            message,
        )

    def _start_validator_analysis(self) -> None:
        if not self._validate_script():
            return
        system = self._validator_system()
        self._mode = "validator_analyze"
        self._validator_reports_ready[system] = False
        self.rom_validator.set_report_ready(False)
        self._register_validator_report_cleanup(system)
        self.rom_validator.reset_progress()
        self.status.setText(self.translator(f"utility.{system}.analyzing"))
        worker = RemoteScriptAttempt(
            self.connection,
            self._selected.script,
            self._validator_arguments("detect"),
            interpreter="python3",
            timeout=86400.0,
        )
        worker.outputLine.connect(self._validator_output)
        worker.succeeded.connect(self._validator_succeeded)
        worker.failed.connect(self._worker_failed)
        self._begin_worker(worker)

    def _start_validator_correction(self) -> None:
        system = self._validator_system()
        if not self._validator_reports_ready.get(system, False) or not self._validate_script():
            return
        if not ask_confirmation(
            self,
            self.translator(f"utility.{system}.confirm_title"),
            self.translator(f"utility.{system}.confirm_correct"),
        ):
            return
        self._mode = "validator_correct"
        self._validator_reports_ready[system] = False
        self.rom_validator.set_report_ready(False)
        self.rom_validator.reset_progress()
        self.status.setText(self.translator(f"utility.{system}.correcting"))
        worker = RemoteScriptAttempt(
            self.connection,
            self._selected.script,
            self._validator_arguments("repair"),
            interpreter="python3",
            timeout=86400.0,
        )
        worker.outputLine.connect(self._validator_output)
        worker.succeeded.connect(self._validator_succeeded)
        worker.failed.connect(self._worker_failed)
        self._begin_worker(worker)

    def _start_service_restart(self, action: str) -> None:
        if not self._validate_script():
            return
        is_recalbox = action == "restart-recalbox"
        is_shutdown = action == "shutdown-recalbox"
        confirm_key = (
            "utility.services.confirm_shutdown"
            if is_shutdown
            else (
                "utility.services.confirm_recalbox"
                if is_recalbox
                else "utility.services.confirm_emulationstation"
            )
        )
        if not ask_confirmation(
            self,
            self.translator("utility.services.confirm_title"),
            self.translator(confirm_key),
        ):
            return
        if is_recalbox or is_shutdown:
            self.connection.cleanup_registered_paths()
        self._mode = (
            "shutdown_recalbox"
            if is_shutdown
            else ("restart_recalbox" if is_recalbox else "restart_emulationstation")
        )
        status_key = (
            "utility.services.shutting_down_recalbox"
            if is_shutdown
            else (
                "utility.services.restarting_recalbox"
                if is_recalbox
                else "utility.services.restarting_emulationstation"
            )
        )
        self.status.setText(self.translator(status_key))
        worker = RemoteScriptAttempt(
            self.connection,
            self._selected.script,
            (action,),
        )
        worker.succeeded.connect(self._service_restart_succeeded)
        worker.failed.connect(self._worker_failed)
        self._begin_worker(worker)

    def _validate_script(self) -> bool:
        if self.busy or self._selected is None:
            return False
        if self._selected.script.is_file():
            return True
        show_error(
            self,
            self.translator("utility.error_title"),
            self.translator("utility.script_missing", path=self._selected.script),
        )
        return False

    def _clean_media_output(self, line: str) -> None:
        parts = line.split("|")
        if len(parts) >= 5 and parts[:2] == ["RCGUI", "PLAN"]:
            self.clean_media.set_progress_plan(int(parts[4]))
        elif len(parts) >= 4 and parts[:2] == ["RCGUI", "PROGRESS"]:
            self.clean_media.set_progress_value(int(parts[2]))

    def _validator_output(self, line: str) -> None:
        parts = line.split("|")
        try:
            if len(parts) >= 4 and parts[:2] == ["RCGUI", "PLAN"]:
                self.rom_validator.set_progress_plan(int(parts[3]))
            elif len(parts) >= 5 and parts[:2] == ["RCGUI", "PROGRESS"]:
                self.rom_validator.set_progress_value(int(parts[3]))
        except ValueError:
            return

    @staticmethod
    def _script_status(result: RemoteScriptResult) -> str:
        for line in reversed(result.stdout.splitlines()):
            if line.startswith("STATUS="):
                return line.split("=", 1)[1].strip()
        return ""

    @staticmethod
    def _clean_result(result: RemoteScriptResult) -> tuple[int, int, int, int, int, int] | None:
        for line in reversed(result.stdout.splitlines()):
            if line.startswith("RCGUI|RESULT|"):
                try:
                    return tuple(int(value) for value in line.split("|")[2:8])
                except ValueError:
                    return None
        return None

    @staticmethod
    def _validator_result(result: RemoteScriptResult, operation: str) -> tuple[int, ...] | None:
        prefix = f"RCGUI|RESULT|{operation}|"
        for line in reversed(result.stdout.splitlines()):
            if line.startswith(prefix):
                try:
                    return tuple(int(value) for value in line.split("|")[3:])
                except ValueError:
                    return None
        return None

    def _patch_script_succeeded(self, result: RemoteScriptResult) -> None:
        status = self._script_status(result)
        if self._mode == "check" and result.exit_code == 0 and status == "ALREADY_APPLIED":
            self.status.setText(self.translator("utility.already_applied"))
            show_information(self, self.translator("utility.result_title"), self.translator("utility.already_applied"))
        elif self._mode == "check" and result.exit_code == 10 and status == "PATCH_REQUIRED":
            self.status.setText(self.translator("utility.patch_required"))
            if ask_confirmation(
                self,
                self.translator("utility.confirm_title"),
                self.translator("utility.confirm_apply", name=self.translator(self._selected.name_key)),
            ):
                self._queued_mode = "patch_apply"
        elif self._mode == "apply" and result.exit_code == 0 and status in {"APPLIED", "ALREADY_APPLIED"}:
            key = "utility.applied" if status == "APPLIED" else "utility.already_applied"
            self.status.setText(self.translator(key))
            show_information(self, self.translator("utility.result_title"), self.translator(key))
        else:
            self._show_result_error(result.combined_output)

    def _clean_media_succeeded(self, result: RemoteScriptResult) -> None:
        values = self._clean_result(result)
        if result.exit_code != 0 or values is None:
            self._show_result_error(result.combined_output)
            return
        checked, referenced, orphaned, removed, errors, skipped = values
        key = "utility.clean_media.test_result" if self._mode == "clean_test" else "utility.clean_media.execute_result"
        message = self.translator(
            key,
            checked=checked,
            referenced=referenced,
            orphaned=orphaned,
            removed=removed,
            errors=errors,
            skipped=skipped,
        )
        self.status.setText(message)
        self.clean_media.set_progress_value(self.clean_media.progress.maximum())
        show_information(self, self.translator("utility.result_title"), message)

    def _validator_succeeded(self, result: RemoteScriptResult) -> None:
        system = self._validator_system()
        operation = "DETECT" if self._mode == "validator_analyze" else "REPAIR"
        values = self._validator_result(result, operation)
        expected = 4 if operation == "DETECT" else 9
        if result.exit_code != 0 or values is None or len(values) != expected:
            self._show_result_error(result.combined_output)
            return

        if operation == "DETECT":
            valid, invalid, unknown, protected = values
            message = self.translator(
                f"utility.{system}.analyze_result",
                valid=valid,
                invalid=invalid,
                unknown=unknown,
                protected=protected,
            )
            self._validator_reports_ready[system] = True
            self.rom_validator.set_report_ready(True)
        else:
            invalid, unknown, protected, changed, missing, conflicts, xml, ini, media = values
            message = self.translator(
                f"utility.{system}.correct_result",
                invalid=invalid,
                unknown=unknown,
                protected=protected,
                changed=changed,
                missing=missing,
                conflicts=conflicts,
                xml=xml,
                ini=ini,
                media=media,
            )

        self.status.setText(message)
        self.rom_validator.set_progress_value(
            self.rom_validator.progress.maximum()
        )
        show_information(self, self.translator("utility.result_title"), message)

    def _service_restart_succeeded(self, result: RemoteScriptResult) -> None:
        status = self._script_status(result)
        if status == "FRONTEND_BUSY":
            self.status.setText(self.translator("utility.services.frontend_busy"))
            show_warning(
                self,
                self.translator("utility.services.result_title"),
                self.translator("utility.services.frontend_busy"),
            )
            return
        if result.exit_code != 0:
            self._show_result_error(result.combined_output)
            return
        if status == "EMULATIONSTATION_RESTARTED":
            message = self.translator("utility.services.emulationstation_restarted")
            self.status.setText(message)
            show_information(
                self, self.translator("utility.services.result_title"), message
            )
            return
        if status == "RECALBOX_RESTART_SCHEDULED":
            message = self.translator("utility.services.recalbox_restarting")
            self.status.setText(message)
            show_information(
                self, self.translator("utility.services.result_title"), message
            )
            self.recalboxRestartScheduled.emit()
            return
        if status == "RECALBOX_SHUTDOWN_SCHEDULED":
            message = self.translator("utility.services.recalbox_shutting_down")
            self.status.setText(message)
            show_information(
                self, self.translator("utility.services.result_title"), message
            )
            self.recalboxShutdownScheduled.emit()
            return
        self._show_result_error(result.combined_output)

    def _worker_failed(self, detail: str) -> None:
        self._show_result_error(detail)

    def _show_result_error(self, detail: str) -> None:
        self.status.setText(self.translator("utility.failed"))
        show_error(
            self,
            self.translator("utility.error_title"),
            self.translator("utility.execution_error", detail=detail or self.translator("unknown")),
        )

    def _worker_finished(self) -> None:
        self._thread = None
        self._worker = None
        self.utility_list.setEnabled(True)
        queued_mode, self._queued_mode = self._queued_mode, ""
        self._update_detail()
        if queued_mode == "patch_apply":
            self._start_patch_script("apply")
