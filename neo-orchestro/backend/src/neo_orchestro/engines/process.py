"""Safe execution of external tools (ADR 0007).

Rules enforced here, so adapters cannot get them wrong:

* argv is a list of strings: **no shell**, ever (a plain string is refused);
* the executable is resolved against a fixed ``PATH``, the child gets a minimal
  environment (application secrets never leak) and a closed stdin;
* it runs in its own session/process group and the *whole group* is killed on timeout,
  cancellation or exit, so no stray background process survives;
* CPU, address-space and file-size limits are applied, and captured output is bounded.
"""

import os
import resource
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import IO

from neo_orchestro.engines.base import EngineError

SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
_DEFAULT_MEMORY = 1024 * 1024 * 1024  # 1 GiB address space
_MAX_FILE_SIZE = 100 * 1024 * 1024
_POLL_SECONDS = 0.05


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int | None
    stdout: str
    stderr: str
    truncated: bool
    timed_out: bool
    cancelled: bool
    duration: float


class _Capture:
    """Reads a pipe into a bounded buffer; keeps draining so the child never blocks."""

    def __init__(self, stream: IO[bytes], limit: int) -> None:
        self.data = bytearray()
        self.truncated = False
        self._stream = stream
        self._limit = limit
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while chunk := self._stream.read1(65536):  # type: ignore[attr-defined]
            room = self._limit - len(self.data)
            if room > 0:
                self.data.extend(chunk[:room])
            if len(chunk) > max(room, 0):
                self.truncated = True


def _kill_group(pid: int) -> None:
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGKILL)


def _apply_limits(pid: int, memory_bytes: int, cpu_seconds: int) -> None:
    for limit, value in (
        (resource.RLIMIT_AS, memory_bytes),
        (resource.RLIMIT_CPU, cpu_seconds),
        (resource.RLIMIT_FSIZE, _MAX_FILE_SIZE),
    ):
        with suppress(ProcessLookupError, PermissionError, ValueError, OSError):
            resource.prlimit(pid, limit, (value, value))


def run_command(
    argv: Sequence[str],
    *,
    timeout: float,
    max_output_bytes: int = 2_000_000,
    memory_bytes: int = _DEFAULT_MEMORY,
    should_stop: Callable[[], bool] | None = None,
    extra_env: Mapping[str, str] | None = None,
) -> CommandResult:
    """Run ``argv`` (never through a shell) and return its bounded output.

    Raises:
        TypeError: ``argv`` is a string (would invite shell-style concatenation).
        ValueError: ``argv`` is empty or an argument is not a NUL-free string.
        EngineError: the executable cannot be found on the fixed ``PATH``.
    """
    if isinstance(argv, str | bytes):
        raise TypeError("argv must be a list of arguments, never a shell command string")
    args = list(argv)
    if not args or any(not isinstance(a, str) or "\x00" in a for a in args) or not args[0]:
        raise ValueError("argv must be a non-empty list of NUL-free strings")

    executable = args[0] if os.path.isabs(args[0]) else shutil.which(args[0], path=SAFE_PATH)
    if executable is None or not os.access(executable, os.X_OK):
        raise EngineError("executable_not_found", f"required tool not available: {args[0][:60]}")

    env = {"PATH": SAFE_PATH, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "HOME": "/nonexistent"}
    env.update(extra_env or {})

    started = time.monotonic()
    process = subprocess.Popen(  # noqa: S603  (argv list, shell=False, validated above)
        [executable, *args[1:]],
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        close_fds=True,
        start_new_session=True,
    )
    _apply_limits(process.pid, memory_bytes, int(timeout) + 5)
    if process.stdout is None or process.stderr is None:  # pragma: no cover - PIPE requested
        raise RuntimeError("subprocess pipes were not created")
    out = _Capture(process.stdout, max_output_bytes)
    err = _Capture(process.stderr, max_output_bytes)

    timed_out = cancelled = False
    deadline = started + timeout
    try:
        while True:
            try:
                process.wait(timeout=_POLL_SECONDS)
                break
            except subprocess.TimeoutExpired:
                pass
            if should_stop is not None and should_stop():
                cancelled = True
            elif time.monotonic() >= deadline:
                timed_out = True
            if cancelled or timed_out:
                _kill_group(process.pid)
                process.wait()
                break
    finally:
        _kill_group(process.pid)  # also reaps background children of a normal exit
        for capture in (out, err):
            capture.thread.join(timeout=2)
        for stream in (process.stdout, process.stderr):
            with suppress(OSError):
                stream.close()

    return CommandResult(
        returncode=process.returncode,
        stdout=out.data.decode("utf-8", errors="replace"),
        stderr=err.data.decode("utf-8", errors="replace"),
        truncated=out.truncated or err.truncated,
        timed_out=timed_out,
        cancelled=cancelled,
        duration=time.monotonic() - started,
    )
