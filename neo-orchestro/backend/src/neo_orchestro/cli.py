"""Administrative command line: ``neo-orchestro create-org`` and ``neo-orchestro version``.

Organisations are created only here (there is deliberately no public sign-up endpoint).
The administrator password is read from stdin or an interactive prompt, **never** from
argv, where any local user could see it in the process list.
"""

import argparse
import getpass
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from sqlalchemy.orm import Session

from neo_orchestro import SIGNATURE, __version__
from neo_orchestro.core.errors import AppError
from neo_orchestro.db.session import get_session_factory
from neo_orchestro.services.orgs import bootstrap_organization

SessionFactory = Callable[[], Session]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="neo-orchestro", description=SIGNATURE)
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-org", help="create an organisation and its first admin")
    create.add_argument("--name", required=True, help="organisation display name")
    create.add_argument("--slug", required=True, help="url-safe id: lowercase letters, digits, -")
    create.add_argument("--admin-email", required=True)
    create.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the admin password from stdin (otherwise prompt interactively)",
    )

    commands.add_parser("version", help="print the version")
    return parser


def _read_password(from_stdin: bool, stdin: TextIO) -> str:
    if from_stdin:
        return stdin.readline().rstrip("\r\n")
    first = getpass.getpass("Administrator password: ")
    if first != getpass.getpass("Repeat password: "):
        raise AppError("passwords do not match")
    return first


def main(
    argv: Sequence[str] | None = None,
    *,
    session_factory: SessionFactory | None = None,
    stdin: TextIO | None = None,
) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "version":
        print(f"neo-orchestro {__version__} — {SIGNATURE}")
        return 0

    factory = session_factory or get_session_factory()
    session = factory()
    try:
        password = _read_password(args.password_stdin, stdin or sys.stdin)
        org, admin = bootstrap_organization(
            session,
            name=args.name,
            slug=args.slug,
            admin_email=args.admin_email,
            admin_password=password,
        )
        summary = f"Created organisation {org.slug} ({org.id}) with administrator {admin.email}"
    except AppError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 2
    finally:
        session.close()
    print(summary)  # built before close(): ORM objects are detached afterwards
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
