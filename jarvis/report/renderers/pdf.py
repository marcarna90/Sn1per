"""Optional PDF export.

PDF is a convenience, not a hard dependency. Jarvis tries, in order, the
helpers most likely to already be present on a pentest box and degrades
gracefully with an actionable message if none is available:

1. WeasyPrint (pure-Python, best fidelity, no external binary)
2. wkhtmltopdf  (already referenced by Sn1per's legacy ``bin/report.py``)
3. headless Chromium/Chrome (bundled on many systems, incl. this one)
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class PdfUnavailable(RuntimeError):
    """Raised when no PDF backend is available on the host."""


def _try_weasyprint(html: str, out_path: Path) -> bool:
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:
        return False
    try:
        HTML(string=html).write_pdf(str(out_path))
        return True
    except Exception:
        return False


def _try_wkhtmltopdf(html_path: Path, out_path: Path) -> bool:
    binary = shutil.which("wkhtmltopdf")
    if not binary:
        return False
    try:
        subprocess.run(
            [binary, "--quiet", "--enable-local-file-access", str(html_path), str(out_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
        return out_path.exists()
    except (subprocess.SubprocessError, OSError):
        return False


def _try_chromium(html_path: Path, out_path: Path) -> bool:
    import os

    # Allow an explicit override, then fall back to the usual browser names
    # plus the modern "headless shell" distributables.
    candidates = [
        os.environ.get("JARVIS_CHROME", ""),
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
        "chrome-headless-shell",
        "headless_shell",
    ]
    binary = ""
    for name in candidates:
        if name and (shutil.which(name) or (os.path.isfile(name) and os.access(name, os.X_OK))):
            binary = shutil.which(name) or name
            break
    if not binary:
        return False
    try:
        subprocess.run(
            [
                binary,
                "--headless",
                "--no-sandbox",
                "--disable-gpu",
                f"--print-to-pdf={out_path}",
                "--no-pdf-header-footer",
                html_path.as_uri(),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
        return out_path.exists()
    except (subprocess.SubprocessError, OSError):
        return False


def render_to_file(html: str, out_path: str) -> str:
    """Write ``html`` to a PDF at ``out_path``. Returns the path on success."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if _try_weasyprint(html, out):
        return str(out)

    # The CLI backends need the HTML on disk.
    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(html)
        tmp_path = Path(tmp.name)
    try:
        if _try_wkhtmltopdf(tmp_path, out):
            return str(out)
        if _try_chromium(tmp_path, out):
            return str(out)
    finally:
        tmp_path.unlink(missing_ok=True)

    raise PdfUnavailable(
        "No PDF backend found. Install one of: 'pip install weasyprint', "
        "'wkhtmltopdf', or a Chromium/Chrome browser. The HTML report was "
        "still generated and can be printed to PDF from any browser."
    )
