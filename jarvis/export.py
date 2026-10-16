"""Export workspace reports off the box (VM guest / container) to the host.

Running inside a VM or container, the reports land in the guest filesystem.
This module bundles them into a single portable ``.zip`` and offers two
transport paths that work regardless of the virtualisation setup:

* copy the bundle to a path (e.g. a mounted VirtualBox/VMware shared folder);
* serve the reports over HTTP so the host browser can download them.

Pure stdlib (``zipfile``, ``http.server``, ``socket``) — no new dependency.
"""

from __future__ import annotations

import os
import shutil
import socket
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# Report artifacts worth bundling (produced by `jarvis report` / `jarvis asm`).
_REPORT_GLOBS = ("*.html", "*.pdf", "*.md", "*.json", "*.csv")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _slug(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in name).strip("-")
    return safe or "workspace"


def collect_report_files(reports_dir: Path) -> list[Path]:
    files: list[Path] = []
    if not reports_dir.is_dir():
        return files
    for pattern in _REPORT_GLOBS:
        files.extend(sorted(reports_dir.glob(pattern)))
    # De-duplicate while keeping order.
    seen: set[Path] = set()
    out: list[Path] = []
    for f in files:
        if f.is_file() and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def bundle(
    workspace: str | os.PathLike,
    out: str | os.PathLike | None = None,
    reports_dir: str | os.PathLike | None = None,
    name: str | None = None,
) -> str:
    """Zip a workspace's report files into a single archive. Returns its path.

    ``out`` may be a directory (the archive is named automatically) or a full
    ``.zip`` path. Defaults to the workspace directory.
    """
    ws = Path(workspace).expanduser().resolve()
    if not ws.is_dir():
        raise FileNotFoundError(f"Workspace not found: {ws}")
    rdir = Path(reports_dir).expanduser() if reports_dir else ws / "reports"
    files = collect_report_files(rdir)
    if not files:
        raise FileNotFoundError(
            f"No report files found in {rdir}. Run 'jarvis report' / 'jarvis asm' first."
        )

    base = _slug(name or ws.name)
    archive_name = f"{base}-reports-{_timestamp()}.zip"
    if out is None:
        archive_path = ws / archive_name
    else:
        out_p = Path(out).expanduser()
        archive_path = out_p if out_p.suffix == ".zip" else out_p / archive_name
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=f.name)
    return str(archive_path)


def copy_to(archive_path: str | os.PathLike, dest_dir: str | os.PathLike) -> str:
    """Copy a bundle to a destination directory (e.g. a shared-folder mount)."""
    dest = Path(dest_dir).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / Path(archive_path).name
    shutil.copy2(archive_path, target)
    return str(target)


def primary_ip() -> str:
    """Best-effort primary non-loopback IP of this guest (no packets sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        s.close()


def serve(directory: str | os.PathLike, port: int = 8000, bind: str = "0.0.0.0"):
    """Serve ``directory`` over HTTP until interrupted (blocking).

    Returns nothing; intended for CLI use. Kept thin so it can be imported
    without side effects.
    """
    import functools
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    directory = str(Path(directory).expanduser().resolve())
    handler = functools.partial(SimpleHTTPRequestHandler, directory=directory)
    httpd = ThreadingHTTPServer((bind, port), handler)
    return httpd
