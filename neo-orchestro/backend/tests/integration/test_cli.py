"""Bootstrap CLI: the only way to create an organisation (no open sign-up endpoint)."""

import io

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from neo_orchestro.cli import main
from neo_orchestro.core.enums import Role
from neo_orchestro.db.models import Organization, User
from support import PASSWORD

BASE = [
    "create-org",
    "--name",
    "Acme",
    "--slug",
    "acme",
    "--admin-email",
    "root@acme.example.com",
    "--password-stdin",
]


def run(db_session: Session, argv: list[str], stdin_text: str = "") -> int:
    return main(argv, session_factory=lambda: db_session, stdin=io.StringIO(stdin_text))


@pytest.mark.integration
def test_create_org_reads_the_password_from_stdin(
    db_session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(db_session, BASE, PASSWORD + "\n") == 0
    out = capsys.readouterr().out
    org = db_session.scalars(select(Organization).where(Organization.slug == "acme")).one()
    admin = db_session.scalars(select(User).where(User.org_id == org.id)).one()
    assert admin.role is Role.admin
    assert admin.email == "root@acme.example.com"
    assert str(org.id) in out
    assert PASSWORD not in out  # never echoed


@pytest.mark.integration
@pytest.mark.security
def test_the_password_cannot_be_given_on_the_command_line() -> None:
    # argv is visible to every local user through `ps`; the flag must simply not exist.
    with pytest.raises(SystemExit) as exit_info:
        main([*BASE[:-1], "--password", PASSWORD])
    assert exit_info.value.code == 2


@pytest.mark.integration
@pytest.mark.parametrize("stdin_text", ["", "\n", "short\n"])
def test_weak_or_missing_passwords_fail_cleanly(
    db_session: Session, capsys: pytest.CaptureFixture[str], stdin_text: str
) -> None:
    assert run(db_session, BASE, stdin_text) == 2
    captured = capsys.readouterr()
    assert "password" in captured.err.lower()
    assert "Traceback" not in captured.err
    assert db_session.scalars(select(Organization)).all() == []


@pytest.mark.integration
def test_duplicates_fail_cleanly(db_session: Session, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(db_session, BASE, PASSWORD + "\n") == 0
    capsys.readouterr()
    assert run(db_session, BASE, PASSWORD + "\n") == 2
    assert "already exists" in capsys.readouterr().err


@pytest.mark.integration
def test_version_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0
    assert "Designed & Developed by Ronald TSR" in capsys.readouterr().out
