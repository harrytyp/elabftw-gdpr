#!/usr/bin/env python3
"""eLabFTW GDPR disclosure - one-command, cross-platform entry point.

Runs everything: environment setup (first run), credential prompt (first
run), API export and report generation (HTML + PDF + ZIP).

Works on Linux, macOS and Windows:
  Linux/macOS:  python3 gdpr.py            or  ./gdpr.sh
  Windows:      py -3 gdpr.py              or  double-click gdpr.bat

Options are passed through to the export step:
  --dry-run      only fetch and count, write nothing
  --no-files     export without upload file contents
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
ENV_FILE = PROJECT_ROOT / "elabftw.env"

# venv layout differs between platforms
VENV_PYTHON = VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def setup_environment() -> str:
    """Create the venv and install dependencies on first run.

    Returns the path to the venv Python interpreter.
    """
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)

    print("[gdpr] First run - setting up Python environment...")
    subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "--quiet",
                    "-r", str(PROJECT_ROOT / "requirements.txt")], check=True)
    return str(VENV_PYTHON)


def ensure_credentials() -> None:
    """Ask for credentials on first run and store them in elabftw.env."""
    if ENV_FILE.exists():
        return
    print("[gdpr] First run - eLabFTW access credentials:")
    url = input("  Instance URL (e.g. https://eln.example.org): ").strip()
    key = input("  Sysadmin API key: ").strip()
    userid = input("  User ID of the data subject: ").strip()
    ENV_FILE.write_text(f"ELAB_URL={url}\nELAB_KEY={key}\nELAB_USERID={userid}\n")
    os.chmod(ENV_FILE, 0o600)
    print("[gdpr] Credentials saved to elabftw.env (600, gitignored).")


def run() -> int:
    """Run export (+ report) in the venv Python and print the results."""
    args = sys.argv[1:]
    python = setup_environment()

    # Re-execute inside the venv so all dependencies are importable.
    # NOTE: compare paths as strings - venv pythons are symlinks, so
    # resolve() would make the system python look identical to the venv one.
    if sys.executable != str(VENV_PYTHON):
        return subprocess.call([python, __file__, *args])

    ensure_credentials()

    print("\n[gdpr] Exporting data...")
    export_result = subprocess.call(
        [sys.executable, str(PROJECT_ROOT / "gdpr_export.py"), *args])
    if export_result != 0:
        return export_result

    if "--dry-run" not in args:
        print("\n[gdpr] Building report package...")
        report_result = subprocess.call(
            [sys.executable, str(PROJECT_ROOT / "gdpr_report.py")])
        if report_result != 0:
            return report_result

    print("")
    print("[gdpr] Done.")
    print(f"  Results: {PROJECT_ROOT / 'output' / 'User*'}")
    print("  Open the HTML explorer (output/User*/index.html) in your browser.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
