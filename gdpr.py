#!/usr/bin/env python3
"""eLabFTW GDPR disclosure - CLI entry point (cross-platform).

Subcommands (default: all):

  all      export data + build report package (HTML + PDF + ZIP)
  export   API export for one or more users
  report   build report package from an existing export
  users    list users visible to the sysadmin key
  status   show what is currently in output/
  config   show or update credentials (elabftw.env)

Options common to export/all are passed through (--dry-run, --no-files,
--users, --json, --env-file). Works on Linux, macOS and Windows
(Windows: gdpr.bat or `py -3 gdpr.py`).

Examples:
  gdpr.py                          # export + report for ELAB_USERID
  gdpr.py --dry-run                # count only, write nothing
  gdpr.py export --no-files        # metadata only (small, fast)
  gdpr.py export --users 75,82 --json
  gdpr.py users                    # list user IDs from the instance
  gdpr.py status --json
  gdpr.py config set userid 75,82

First run: creates .venv, installs dependencies, asks for instance URL,
sysadmin API key and user ID(s) (stored in elabftw.env, chmod 600,
gitignored). All runs are logged to output/gdpr.log (Art. 5(2) GDPR).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

try:
    from colorama import just_fix_windows_console
except ImportError:
    just_fix_windows_console = None

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / "elabftw.env"
OUTPUT_DIR = PROJECT_ROOT / "output"
LOG_FILE = OUTPUT_DIR / "gdpr.log"

# venv layout differs between platforms. On Windows the venv is always kept
# under %LOCALAPPDATA%: a venv on a UNC share (\\server\share) is unreliable
# and slow, and after `pushd` in gdpr.bat a UNC path becomes a mapped drive
# letter, so path-based detection cannot be trusted. A local venv is
# deterministic and fast. On Linux/macOS the venv lives next to the project.
if os.name == "nt":
    VENV_DIR = Path(os.environ.get("LOCALAPPDATA", PROJECT_ROOT)) / "elabftw_gdpr" / ".venv"
else:
    VENV_DIR = PROJECT_ROOT / ".venv"
VENV_PYTHON = VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

logger = logging.getLogger("gdpr")

# ANSI colors (disabled for pipes/cron and when NO_COLOR is set)
_COLORS = {"green": "32", "yellow": "33", "red": "31", "bold": "1", "dim": "2"}
_COLOR_DISABLED = False


def color(text: str, style: str = "bold") -> str:
    if _COLOR_DISABLED or not sys.stdout.isatty():
        return text
    return f"\033[{_COLORS[style]}m{text}\033[0m"


def setup_logging() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    stream_handler.setLevel(logging.WARNING)  # terminal: warnings/errors only
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def _venv_has_deps(python: Path) -> bool:
    """True if all runtime dependencies import in the given venv."""
    probe = ("import elabapy, PIL, reportlab, colorama; "
             "import sys; sys.exit(0)")
    try:
        return subprocess.run([str(python), "-c", probe],
                              capture_output=True, timeout=60).returncode == 0
    except OSError:
        return False


def setup_environment() -> str:
    """Create the venv and install dependencies when missing.

    Returns the path to the venv Python interpreter.
    """
    if VENV_PYTHON.exists() and _venv_has_deps(VENV_PYTHON):
        return str(VENV_PYTHON)

    if not VENV_PYTHON.exists():
        print("[gdpr] First run - setting up Python environment...")
        VENV_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)

    print("[gdpr] Installing dependencies...")
    subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "--quiet",
                    "-r", str(PROJECT_ROOT / "requirements.txt")], check=True)
    return str(VENV_PYTHON)


def update_env_file(env_file: Path, updates: dict) -> None:
    """Set/overwrite keys in an env file, keeping all other lines."""
    lines = env_file.read_text().splitlines() if env_file.exists() else []
    for key, value in updates.items():
        line = f"{key}={value}"
        for i, existing in enumerate(lines):
            if existing.strip().startswith(f"{key}="):
                lines[i] = line
                break
        else:
            lines.append(line)
    env_file.write_text("\n".join(lines) + "\n")
    try:
        os.chmod(env_file, 0o600)
    except OSError:
        pass  # Windows: no Unix permissions


def select_users_interactive(manager) -> list[int]:
    """Show all users from the instance and let the operator pick some."""
    from gdpr_export import list_users

    users = list_users(manager)
    if not users:
        print(color("No users visible to this key.", "red"))
        return []
    print("Users on the instance:")
    for i, u in enumerate(users, 1):
        print(f"  {i:3d}) {u['userid']:6d}  {u['fullname']} <{u['email']}>")
    print("Select user(s) by number (e.g. '1,3' or '1 4 7'):")
    choice = input("> ").strip()
    picked = []
    for part in choice.replace(",", " ").split():
        if part.isdigit():
            idx = int(part)
            if 1 <= idx <= len(users):
                picked.append(users[idx - 1]["userid"])
    return picked


def ensure_credentials(env: dict, env_file: Path) -> dict:
    """Prompt for missing credentials/user IDs and store them in the env file."""
    env_file = env_file or ENV_FILE
    updates = {}

    if not env.get("ELAB_URL") or not env.get("ELAB_KEY"):
        print("[gdpr] First run - eLabFTW access credentials:")
        url = input("  Instance URL (e.g. https://eln.example.org): ").strip()
        key = input("  Sysadmin API key: ").strip()
        updates["ELAB_URL"] = url
        updates["ELAB_KEY"] = key
        env["ELAB_URL"] = url
        env["ELAB_KEY"] = key
        print(f"[gdpr] Credentials saved to {env_file} (600, gitignored).")

    if not env.get("ELAB_USERID"):
        from gdpr_export import get_manager
        picked = select_users_interactive(get_manager(env))
        if not picked:
            print(color("No users selected - set ELAB_USERID=75,82 in the env file.", "yellow"))
        else:
            env["ELAB_USERID"] = ",".join(str(u) for u in picked)
            updates["ELAB_USERID"] = env["ELAB_USERID"]

    if updates:
        update_env_file(env_file, updates)
    return env


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def print_api_limitations() -> None:
    """Tell the operator how to complete the API export with DB/CLI data."""
    print("\nNext steps: the API export is not the complete disclosure by itself.")
    print("Some data requires a separate DB/CLI step, including audit logs, failed")
    print("login attempts and self-scoped metadata such as exports and todolists.")
    print(f"  SQL checklist: {PROJECT_ROOT / 'gdpr_cli.sql'}")
    print(f"  API/CLI guide: {PROJECT_ROOT / 'docs' / 'api-vs-cli.md'}")
    print("Review and redact third-party data before sending the disclosure.")


def cmd_export(args) -> int:
    from gdpr_export import (ENV_FILE as EXPORT_ENV, export_users,
                             load_env, parse_user_ids)

    env_file = Path(args.env_file) if args.env_file else EXPORT_ENV
    env = load_env(args.env_file)
    if not env.get("ELAB_URL") or not env.get("ELAB_KEY"):
        print(color("Missing credentials - run 'gdpr.py' once or fill the env file.", "red"))
        return 2
    users = parse_user_ids(args.users) or parse_user_ids(env.get("ELAB_USERID"))
    if not users:
        print(color("No user IDs - use --users 75,82 or set ELAB_USERID.", "yellow"))
        return 2

    if args.json:
        with contextlib.redirect_stdout(sys.stderr):
            results = export_users(env, users, Path(args.out_dir), args.dry_run, args.no_files)
    else:
        results = export_users(env, users, Path(args.out_dir), args.dry_run, args.no_files)
    ok = sum(1 for v in results.values() if v is not None)
    if args.json:
        # Keep stdout valid JSON for pipes and automation. Human progress goes
        # to stderr when JSON mode is selected.
        print(json.dumps({"users": results, "ok": ok, "total": len(results)},
                         indent=2, ensure_ascii=False, default=str))
    else:
        print(f"\n{color('Exported', 'green')} {ok}/{len(users)} users")
        print_api_limitations()
    return 0 if ok == len(users) else 1


def cmd_report(args) -> int:
    from gdpr_report import build_reports

    user_filter = None
    if args.user:
        user_filter = [int(x) for x in args.user.replace(" ", "").split(",") if x]
    results = build_reports(Path(args.out_dir), user_filter)
    if not results:
        return 1
    return 0 if all(v == 0 for v in results.values()) else 1


def cmd_all(args) -> int:
    from gdpr_export import (ENV_FILE as EXPORT_ENV, export_users,
                             load_env, parse_user_ids)
    from gdpr_report import build_reports

    env_file = Path(args.env_file) if args.env_file else EXPORT_ENV
    env = ensure_credentials(load_env(args.env_file), env_file)
    if not env.get("ELAB_URL") or not env.get("ELAB_KEY"):
        print(color("No credentials provided - aborting.", "red"))
        return 2
    users = parse_user_ids(args.users) or parse_user_ids(env.get("ELAB_USERID"))
    if not users:
        print(color("No users selected - aborting.", "red"))
        return 2

    logger.info("Run: users=%s dry_run=%s no_files=%s", users, args.dry_run, args.no_files)
    print(f"[gdpr] Exporting data for {len(users)} user(s)...")
    base_dir = Path(args.out_dir)
    results = export_users(env, users, base_dir, args.dry_run, args.no_files)
    ok = sum(1 for v in results.values() if v is not None)
    if ok != len(users):
        logger.error("Export incomplete: %s/%s users", ok, len(users))
        print(color(f"Export incomplete ({ok}/{len(users)}) - see output/gdpr.log", "red"))
        return 1
    if args.dry_run:
        print(color("\n[gdpr] Dry run - nothing written. Done.", "green"))
        return 0

    print(f"\n[gdpr] Building report package...")
    report_results = build_reports(base_dir, users if args.users else None)
    if not report_results:
        return 1

    logger.info("Run finished: %s users exported, %s reports built",
                len(users), sum(1 for v in report_results.values() if v == 0))
    print_api_limitations()
    print(color("\n[gdpr] Done.", "green"))
    print(f"  Results:   {OUTPUT_DIR / 'User*'}")
    print(f"  HTML:      {OUTPUT_DIR / 'User*' / 'index.html'} (open in browser)")
    print(f"  PDF:       {OUTPUT_DIR / 'User*' / 'Disclosure_User*.pdf'}")
    print(f"  Log:       {LOG_FILE}")
    return 0


def cmd_users(args) -> int:
    from gdpr_export import ENV_FILE as EXPORT_ENV
    from gdpr_export import get_manager, list_users, load_env

    env = load_env(args.env_file)
    if not env.get("ELAB_URL") or not env.get("ELAB_KEY"):
        print(color("Missing credentials - run 'gdpr.py' once or fill the env file.", "red"))
        return 2
    try:
        users = list_users(get_manager(env))
    except Exception as e:  # elabapy/requests errors
        print(color(f"Could not list users: {e}", "red"))
        return 1
    if args.json:
        print(json.dumps(users, indent=2, ensure_ascii=False, default=str))
    else:
        for u in users:
            print(f"{u['userid']:6d}  {u['fullname']} <{u['email']}>")
        print(f"\n{len(users)} user(s) visible to this key.")
    return 0


def cmd_status(args) -> int:
    rows = []
    for user_dir in sorted(OUTPUT_DIR.glob("User*")):
        manifest_path = user_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        user = manifest.get("user") or {}
        entities = manifest.get("entities", {})
        n_entities = sum(len(v) for v in entities.values())
        pdf = sorted(user_dir.glob("Disclosure_User*.pdf"))
        zipf = sorted(user_dir.glob("gdpr_disclosure_User*.zip"))
        rows.append({
            "user": user_dir.name,
            "fullname": user.get("fullname"),
            "exported_at": manifest.get("exported_at"),
            "entities": n_entities,
            "uploads": manifest.get("upload_files_downloaded", 0),
            "pdf": pdf[0].name if pdf else None,
            "zip": zipf[0].name if zipf else None,
        })
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False, default=str))
    else:
        if not rows:
            print("No exports yet - run 'gdpr.py' first.")
            return 0
        print(f"{'folder':<10}{'name':<28}{'exported':<20}{'entries':>8}{'uploads':>9}  pdf/zip")
        for r in rows:
            flags = ("PDF" if r["pdf"] else "--") + "/" + ("ZIP" if r["zip"] else "--")
            name = (r["fullname"] or "")[:27]
            print(f"{r['user']:<10}{name:<28}{(r['exported_at'] or '')[:19]:<20}"
                  f"{r['entities']:>8}{r['uploads']:>9}  {flags}")
    return 0


def cmd_config(args, env_file: Path) -> int:
    if args.action == "show":
        from gdpr_export import load_env
        env = load_env(str(env_file))
        print(f"env file:      {env_file}")
        print(f"instance URL:  {env.get('ELAB_URL', '(not set)')}")
        print(f"user IDs:      {env.get('ELAB_USERID', '(not set)')}")
        print(f"API key:       {'(set, hidden)' if env.get('ELAB_KEY') else '(not set)'}")
        print(f"output dir:    {OUTPUT_DIR}")
        print(f"log file:      {LOG_FILE}")
        print(f"venv:          {VENV_PYTHON} ({'ready' if VENV_PYTHON.exists() else 'not created yet'})")
        return 0
    # set
    allowed = {"url": "ELAB_URL", "userid": "ELAB_USERID"}
    if args.key not in allowed:
        print(color(f"Unknown key '{args.key}' - allowed: {', '.join(allowed)}", "red"))
        return 2
    update_env_file(env_file, {allowed[args.key]: args.value})
    print(f"{allowed[args.key]} updated in {env_file}.")
    logger.info("Config updated: %s", allowed[args.key])
    return 0


# ---------------------------------------------------------------------------
# Argument parsing + dispatch
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    # shared options: available globally and on the relevant subcommands
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", action="store_true",
                        help="only fetch and count, write nothing")
    common.add_argument("--no-files", action="store_true",
                        help="skip uploading file contents (fast, small)")
    common.add_argument("--users", default=None,
                        help="comma-separated user IDs (default: ELAB_USERID)")
    common.add_argument("--env-file", default=None,
                        help="path to credentials file (default: elabftw.env)")
    common.add_argument("--json", action="store_true",
                        help="print summary as JSON on stdout")
    common.add_argument("--out-dir", default=str(OUTPUT_DIR),
                        help="base directory for per-user export folders")

    parser = argparse.ArgumentParser(
        prog="gdpr",
        parents=[common],
        description="eLabFTW GDPR Art. 15 disclosure tool (sysadmin API key)",
        epilog=(
            "Examples:\n"
            "  gdpr.py                      export + report (ELAB_USERID)\n"
            "  gdpr.py --dry-run            count only\n"
            "  gdpr.py export --no-files    metadata only\n"
            "  gdpr.py export --users 75,82 --json\n"
            "  gdpr.py users                list users from the instance\n"
            "  gdpr.py status               what is in output/\n"
            "  gdpr.py config set userid 75,82\n"
            "  ELAB_USERID=75,82 gdpr.py    override user IDs per run\n"
            "\nFirst run creates .venv and asks for credentials once. "
            "All runs are logged to output/gdpr.log. Docs: docs/ in this repo."
        ),
    )
    parser.add_argument("--no-color", action="store_true",
                        help="disable colored output (also honors NO_COLOR)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("all", parents=[common], help="export + report (default)")
    sub.add_parser("export", parents=[common],
                   help="API export for one or more users")

    p_report = sub.add_parser("report", parents=[common],
                              help="build report package from exports")
    p_report.add_argument("--user", default=None,
                          help="comma-separated user IDs (default: all exported)")

    sub.add_parser("users", parents=[common],
                   help="list users visible to the key")
    sub.add_parser("status", parents=[common],
                   help="show what is in output/")

    p_config = sub.add_parser("config", help="show or update credentials")
    p_config.add_argument("action", choices=["show", "set"])
    p_config.add_argument("key", nargs="?", help="url | userid")
    p_config.add_argument("value", nargs="?", help="new value")
    return parser


def main() -> int:
    # Enable ANSI support in Windows 10+ CMD/PowerShell through colorama.
    # Pipes and NO_COLOR are still handled by color().
    if just_fix_windows_console is not None:
        just_fix_windows_console()
    python = setup_environment()

    # Re-execute inside the venv so all dependencies are importable.
    # NOTE: compare paths as strings - venv pythons are symlinks, so
    # resolve() would make the system python look identical to the venv one.
    if sys.executable != str(VENV_PYTHON):
        return subprocess.call([python, __file__, *sys.argv[1:]])

    setup_logging()
    parser = build_parser()
    try:
        import argcomplete
        argcomplete.autocomplete(parser)
    except ImportError:
        pass  # optional: pip install argcomplete for tab completion
    args = parser.parse_args()

    global _COLOR_DISABLED
    _COLOR_DISABLED = args.no_color or os.environ.get("NO_COLOR") is not None

    command = args.command or "all"
    logger.info("Command: %s %s", command, " ".join(sys.argv[1:]))
    if command == "export":
        return cmd_export(args)
    if command == "report":
        return cmd_report(args)
    if command == "users":
        return cmd_users(args)
    if command == "status":
        return cmd_status(args)
    if command == "config":
        env_file = ENV_FILE
        return cmd_config(args, env_file)
    return cmd_all(args)


if __name__ == "__main__":
    sys.exit(main())
