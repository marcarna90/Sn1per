"""Safe subprocess execution: argv only, no shell, bounded, killable (ADR 0007)."""

import os
import sys
import time

import pytest

from neo_orchestro.engines import EngineError, run_command
from neo_orchestro.scope import InvalidTargetError, parse_target


@pytest.mark.unit
@pytest.mark.security
def test_arguments_are_passed_verbatim_and_never_interpreted_by_a_shell() -> None:
    hostile = "$(echo pwned); `id` | cat && echo x > /tmp/neo-should-not-exist-$$"
    result = run_command(["echo", hostile], timeout=5)
    assert result.returncode == 0
    assert result.stdout.strip() == hostile
    assert not os.path.exists("/tmp/neo-should-not-exist-")  # noqa: S108


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.parametrize("bad", ["echo hi", b"echo hi"])
def test_a_shell_string_is_refused(bad: object) -> None:
    with pytest.raises(TypeError):
        run_command(bad, timeout=5)  # type: ignore[arg-type]


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.parametrize("bad", [[], [""], ["echo", "a\x00b"], ["echo", 1]])
def test_malformed_argv_is_refused(bad: list[object]) -> None:
    with pytest.raises((ValueError, TypeError)):
        run_command(bad, timeout=5)  # type: ignore[arg-type]


@pytest.mark.unit
def test_unknown_executables_raise_a_clean_engine_error() -> None:
    with pytest.raises(EngineError) as caught:
        run_command(["definitely-not-a-real-binary-xyz"], timeout=5)
    assert caught.value.code == "executable_not_found"


@pytest.mark.unit
@pytest.mark.security
def test_the_child_gets_a_minimal_environment_without_application_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEO_SECRET_KEY", "super-secret-value")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "another-secret")
    result = run_command(["env"], timeout=5)
    assert "super-secret-value" not in result.stdout
    assert "another-secret" not in result.stdout
    assert "NEO_" not in result.stdout
    assert "PATH=" in result.stdout


@pytest.mark.unit
@pytest.mark.security
def test_stdin_is_closed_even_when_the_parent_has_an_open_stdin() -> None:
    # Give *this* process an stdin that never reaches EOF (like an interactive terminal).
    # If the child inherited it, `cat` would block until the timeout.
    read_end, write_end = os.pipe()
    saved = os.dup(0)
    try:
        os.dup2(read_end, 0)
        result = run_command(["cat"], timeout=3)
    finally:
        os.dup2(saved, 0)
        for fd in (saved, read_end, write_end):
            os.close(fd)
    assert result.timed_out is False
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.unit
def test_timeouts_kill_the_process_promptly() -> None:
    started = time.monotonic()
    result = run_command(["sleep", "30"], timeout=0.5)
    assert result.timed_out is True
    assert result.returncode != 0
    assert time.monotonic() - started < 5


@pytest.mark.unit
@pytest.mark.security
def test_timeouts_kill_the_whole_process_group() -> None:
    result = run_command(["sh", "-c", "sleep 60 & echo $!; wait"], timeout=1)
    assert result.timed_out is True
    grandchild = int(result.stdout.split()[0])
    for _ in range(50):  # allow the kernel a moment to reap it
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    pytest.fail("a grandchild process survived the timeout")


@pytest.mark.unit
def test_cancellation_stops_the_process() -> None:
    started = time.monotonic()
    result = run_command(
        ["sleep", "30"], timeout=30, should_stop=lambda: time.monotonic() - started > 0.3
    )
    assert result.cancelled is True
    assert time.monotonic() - started < 5


@pytest.mark.unit
@pytest.mark.security
def test_output_is_bounded() -> None:
    result = run_command(["head", "-c", "2000000", "/dev/zero"], timeout=10, max_output_bytes=1000)
    assert result.truncated is True
    assert len(result.stdout) <= 1000


@pytest.mark.unit
@pytest.mark.security
def test_memory_is_limited() -> None:
    code = "x = bytearray(1024 * 1024 * 1024); print('allocated')"
    result = run_command([sys.executable, "-c", code], timeout=20, memory_bytes=256 * 1024 * 1024)
    assert "allocated" not in result.stdout
    assert result.returncode != 0


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.parametrize("target", ["-oX.example.com", "--script=evil.example.com", "-1.2.3.4"])
def test_validated_targets_can_never_look_like_command_options(target: str) -> None:
    """Option injection guard: engines may pass the target as an argument safely."""
    with pytest.raises(InvalidTargetError):
        parse_target(target)
