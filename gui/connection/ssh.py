from __future__ import annotations

import socket
import threading
import shlex
import stat
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from collections.abc import Callable

import paramiko
from PySide6.QtCore import QObject, Signal, Slot

from ..models import RecalboxEnvironment


class RecalboxConnection:
    """Sesión SSH activa asociada a un entorno Recalbox."""

    def __init__(self, environment: RecalboxEnvironment, client: paramiko.SSHClient) -> None:
        self.environment = environment
        self._client = client
        self._lock = threading.Lock()
        self._cleanup_paths: set[str] = set()

    @classmethod
    def open(cls, environment: RecalboxEnvironment, known_hosts: Path) -> "RecalboxConnection":
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        if known_hosts.exists():
            client.load_host_keys(str(known_hosts))
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=environment.host,
                port=22,
                username=environment.username,
                password=environment.password,
                timeout=8.0,
                banner_timeout=8.0,
                auth_timeout=8.0,
                allow_agent=True,
                look_for_keys=True,
            )
            transport = client.get_transport()
            if transport is None or not transport.is_active() or not transport.is_authenticated():
                raise ConnectionError("La sesión SSH no quedó autenticada")
            known_hosts.parent.mkdir(parents=True, exist_ok=True)
            client.save_host_keys(str(known_hosts))
            known_hosts.chmod(0o600)
            return cls(environment, client)
        except Exception:
            client.close()
            raise

    @property
    def active(self) -> bool:
        transport = self._client.get_transport()
        return bool(transport and transport.is_active() and transport.is_authenticated())

    def close(self) -> None:
        with self._lock:
            self._cleanup_registered_paths_unlocked()
            transport = self._client.get_transport()
            if transport is not None:
                transport.close()
            self._client.close()

    def register_cleanup_paths(self, *remote_paths: str) -> None:
        """Registra archivos de sesión que deben retirarse antes de cerrar SSH."""
        with self._lock:
            self._cleanup_paths.update(path for path in remote_paths if path)

    def cleanup_registered_paths(self) -> None:
        with self._lock:
            self._cleanup_registered_paths_unlocked()

    def _cleanup_registered_paths_unlocked(self) -> None:
        if self.active and self._cleanup_paths:
            try:
                sftp = self._client.open_sftp()
                try:
                    for remote_path in tuple(self._cleanup_paths):
                        try:
                            sftp.remove(remote_path)
                        except OSError:
                            pass
                finally:
                    sftp.close()
            except (OSError, paramiko.SSHException):
                pass
        self._cleanup_paths.clear()

    def run_script(
        self,
        local_path: Path,
        arguments: tuple[str, ...] = (),
        timeout: float = 90.0,
        output_line: Callable[[str], None] | None = None,
        interpreter: str = "bash",
    ) -> "RemoteScriptResult":
        suffix = local_path.suffix or ".tmp"
        remote_path = f"/tmp/recalboxgui-{uuid4().hex}{suffix}"
        with self._lock:
            if not self.active:
                raise ConnectionError("La conexión SSH ya no está activa")
            sftp = self._client.open_sftp()
            stdin = stdout = stderr = None
            try:
                sftp.put(str(local_path), remote_path)
                command = " ".join(
                    shlex.quote(value)
                    for value in (interpreter, remote_path, *arguments)
                )
                stdin, stdout, stderr = self._client.exec_command(
                    command, timeout=timeout
                )
                stdin.close()
                output_lines = []
                while True:
                    raw_line = stdout.readline()
                    if not raw_line:
                        break
                    line = (
                        raw_line.decode("utf-8", errors="replace")
                        if isinstance(raw_line, bytes)
                        else raw_line
                    )
                    output_lines.append(line)
                    if output_line is not None:
                        output_line(line.rstrip("\r\n"))
                output = "".join(output_lines)
                error_output = stderr.read().decode("utf-8", errors="replace")
                exit_code = stdout.channel.recv_exit_status()
                return RemoteScriptResult(exit_code, output, error_output)
            finally:
                for stream in (stdin, stdout, stderr):
                    if stream is not None:
                        try:
                            stream.close()
                        except OSError:
                            pass
                try:
                    sftp.remove(remote_path)
                except OSError:
                    pass
                sftp.close()

    def list_directories(self, remote_path: str) -> list[str]:
        with self._lock:
            if not self.active:
                raise ConnectionError("La conexión SSH ya no está activa")
            sftp = self._client.open_sftp()
            try:
                names = [
                    item.filename
                    for item in sftp.listdir_attr(remote_path)
                    if stat.S_ISDIR(item.st_mode) and item.filename not in {".", ".."}
                ]
                return sorted(names, key=str.casefold)
            finally:
                sftp.close()


@dataclass(frozen=True)
class RemoteScriptResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        values = [value.strip() for value in (self.stdout, self.stderr) if value.strip()]
        return "\n".join(values)


def connection_error_key(error: Exception) -> tuple[str, str]:
    if isinstance(error, paramiko.AuthenticationException):
        return "connection.error_authentication", ""
    if isinstance(error, paramiko.BadHostKeyException):
        return "connection.error_host_key", str(error)
    if isinstance(error, socket.gaierror):
        return "connection.error_name", str(error)
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "connection.error_timeout", str(error)
    if isinstance(error, paramiko.SSHException):
        return "connection.error_ssh", str(error)
    if isinstance(error, OSError):
        return "connection.error_network", str(error)
    return "connection.error_unknown", str(error)


class ConnectionAttempt(QObject):
    connected = Signal(str, object)
    failed = Signal(str, str, str)
    finished = Signal(str)

    def __init__(self, environment: RecalboxEnvironment, known_hosts: Path) -> None:
        super().__init__()
        self.environment = environment
        self.known_hosts = known_hosts

    @Slot()
    def run(self) -> None:
        try:
            connection = RecalboxConnection.open(self.environment, self.known_hosts)
            self.connected.emit(self.environment.identifier, connection)
        except Exception as error:
            key, detail = connection_error_key(error)
            self.failed.emit(self.environment.identifier, key, detail)
        finally:
            self.finished.emit(self.environment.identifier)
