#!/usr/bin/env python3
"""gdpr_detect.py - recursive autodetection of eLabFTW DB targets.

Used by gdpr_db_full.py (pipeline B) to find, without hardcoded names:

  container (mysql/mariadb) -> compose/env file -> DB name -> ELAB URL

Each step picks the unique match when unambiguous and asks the user
(recursively) when several candidates exist. Override flags
(--db-container / --db-env-file / --db-name) always take precedence.

On a Linux server with docker-compose this is a true 1-click: no env file,
no API key, no code edits.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

try:  # optional niceties; fall back to plain input()
    import questionary  # type: ignore
except ImportError:
    questionary = None

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], timeout: int = 15) -> str | None:
    """Run a command, return stdout stripped or None on failure."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0:
            return r.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def pick(title: str, options: list[str], allow_skip: bool = False) -> str | None:
    """Choose among options. 1 -> unique. >1 -> ask user (recursive)."""
    if not options:
        return None
    if len(options) == 1:
        return options[0]
    if questionary is not None:
        sel = questionary.select(title, choices=options).ask()
        if sel:
            return sel
        return None
    print(title)
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    while True:
        raw = input("  choose (number): ").strip()
        if allow_skip and raw in ("", "s", "skip"):
            return None
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        print("  invalid - pick a number")


def pick_multi(title: str, options: list[str]) -> list[str]:
    """Choose several among options; asks when >1."""
    if not options:
        return []
    if len(options) == 1:
        return options
    if questionary is not None:
        sel = questionary.checkbox(title, choices=options).ask()
        return sel or []
    print(title)
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    raw = input("  choose numbers, comma-separated (empty = all): ").strip()
    if not raw:
        return options
    out = []
    for part in raw.split(","):
        try:
            idx = int(part)
            if 1 <= idx <= len(options):
                out.append(options[idx - 1])
        except ValueError:
            pass
    return out or options


# ---------------------------------------------------------------------------
# Docker / filesystem discovery
# ---------------------------------------------------------------------------


def find_mysql_containers() -> list[str]:
    """Running containers whose image/name suggests MySQL/MariaDB."""
    out = _run(["docker", "ps", "--format", "{{.Names}}\t{{.Image}}"])
    if not out:
        return []
    found = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name, image = parts[0], parts[1].lower()
        if any(tok in image for tok in ("mysql", "mariadb")):
            found.append(name)
    return found


def find_elab_containers() -> list[str]:
    """Running containers whose image suggests the eLabFTW app itself."""
    out = _run(["docker", "ps", "--format", "{{.Names}}\t{{.Image}}"])
    if not out:
        return []
    found = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name, image = parts[0], parts[1].lower()
        if "elabftw" in image or "elabimg" in image:
            found.append(name)
    return found


def find_compose_files() -> list[Path]:
    """docker-compose.yml files in likely locations + cwd parents."""
    candidates: list[Path] = []
    roots: list[Path] = [Path.cwd()]
    home = Path.home()
    for extra in ("unified-researchdata-mcp", "elabftw", "elab", "docker"):
        roots.append(home / extra)
    roots.append(home)
    roots.append(Path("/opt"))
    for root in roots:
        if not root.is_dir():
            continue
        for fn in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
            p = root / fn
            if p.is_file():
                candidates.append(p)
        if root == Path("/opt"):
            # /opt/elabftw*/docker-compose.yml etc.
            try:
                for sub in root.iterdir():
                    if "elab" in sub.name.lower():
                        for fn in ("docker-compose.yml", "docker-compose.yaml"):
                            p = sub / fn
                            if p.is_file():
                                candidates.append(p)
            except OSError:
                pass
    # dedupe
    seen: set[Path] = set()
    out: list[Path] = []
    for p in candidates:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def read_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE env file."""
    env: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return env
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def find_env_files() -> list[Path]:
    """.env files that likely belong to an eLabFTW stack."""
    out: list[Path] = []
    for p in find_compose_files():
        out.append(p.parent / ".env")
        out.append(p.parent / ".env.example")
    # also plain ./.env, ~/unified-researchdata-mcp/.env
    for cand in (Path.cwd() / ".env", Path.home() / ".env",
                 Path.home() / "unified-researchdata-mcp" / ".env"):
        if cand.is_file():
            out.append(cand)
    seen: set[Path] = set()
    res: list[Path] = []
    for p in out:
        rp = p.resolve()
        if rp not in seen and p.exists():
            seen.add(rp)
            res.append(p)
    return res


def find_db_names(container: str) -> list[str]:
    """SHOW DATABASES on the given MySQL/MariaDB container."""
    out = _run(["docker", "exec", container, "sh", "-c",
                "mysql -uroot -e 'SHOW DATABASES' 2>/dev/null || true"])
    if not out:
        # try without creds on the socket
        out = _run(["docker", "exec", container, "sh", "-c",
                    "mysql -e 'SHOW DATABASES' 2>/dev/null || true"])
    if not out:
        return []
    names = [ln.strip() for ln in out.splitlines() if ln.strip()]
    # filter system DBs
    return [n for n in names if n not in
            ("information_schema", "performance_schema", "mysql", "sys", "Database")]


def db_has_elab_schema(container: str, dbname: str) -> bool:
    """True if the DB has eLabFTW's config table."""
    out = _run(["docker", "exec", container, "sh", "-c",
                f"mysql -uroot -N -e \"SELECT COUNT(*) FROM information_schema.tables "
                f"WHERE table_schema='{dbname}' AND table_name='config'\" 2>/dev/null || true"])
    if out and out.strip() == "1":
        return True
    # fallback: try unauthenticated
    out = _run(["docker", "exec", container, "sh", "-c",
                f"mysql -N -e \"SELECT COUNT(*) FROM information_schema.tables "
                f"WHERE table_schema='{dbname}' AND table_name='config'\" 2>/dev/null || true"])
    return bool(out and out.strip() == "1")


# ---------------------------------------------------------------------------
# top-level orchestration (recursive ask at each ambiguous step)
# ---------------------------------------------------------------------------


def resolve_db_target(env: dict, args) -> dict:
    """Return {container, compose_file, db_name, url, db_password, db_user}.

    Precedence: explicit CLI overrides > env vars (ELAB_DB_*) > autodetect.
    At every autodetect step the user is asked if more than one candidate.
    """
    # 1) explicit overrides
    container = getattr(args, "db_container", None) or env.get("ELAB_DB_CONTAINER")
    compose_file = getattr(args, "db_env_file", None) or env.get("ELAB_DB_ENV_FILE")
    db_name = getattr(args, "db_name", None) or env.get("ELAB_DB_NAME")

    # 2) autodetect container
    if not container:
        cands = find_mysql_containers()
        if cands:
            container = pick("Multiple MySQL containers found - which one?",
                             cands) if len(cands) > 1 else cands[0]

    # 3) autodetect compose / env file
    compose_path: Path | None = None
    env_path: Path | None = None
    if compose_file:
        compose_path = Path(compose_file)
    else:
        env_cands = find_env_files()
        # prefer those that mention ELABFTW_DB_PASSWORD
        elab_envs = [p for p in env_cands
                     if "ELABFTW_DB_PASSWORD" in read_env_file(p)]
        if not elab_envs and env_cands:
            elab_envs = env_cands
        if elab_envs:
            chosen = (elab_envs[0] if len(elab_envs) == 1
                      else pick("Multiple eLabFTW env files found - which one?",
                                [str(p) for p in elab_envs]))
            if chosen:
                env_path = Path(chosen)
                # compose file is a sibling (only used for db name/url hints)
                cand = env_path.parent / "docker-compose.yml"
                if not cand.is_file():
                    cand = env_path.parent / "docker-compose.yaml"
                compose_path = cand if cand.is_file() else env_path

    # 4) DB name
    if not db_name and container:
        names = find_db_names(container)
        if names:
            elab_names = [n for n in names if db_has_elab_schema(container, n)]
            pool = elab_names or names
            db_name = (pool[0] if len(pool) == 1
                       else pick("Multiple databases found - which one?",
                                 pool))
        elif compose_path:
            ce = read_env_file(compose_path)
            db_name = ce.get("ELABFTW_DB_NAME") or ce.get("DB_NAME") or "elabftw"

    # 5) credentials - read from the ENV file (the compose file itself
    #    only references $ELABFTW_DB_PASSWORD; the .env holds the value)
    db_password = env.get("ELAB_DB_PASSWORD")
    db_user = env.get("ELAB_DB_USER", "elabftw")
    cred_file = env_path or compose_path
    if cred_file and not db_password:
        ce = read_env_file(cred_file)
        db_password = ce.get("ELABFTW_DB_PASSWORD") or ce.get("MYSQL_ROOT_PASSWORD")
        db_user = ce.get("ELABFTW_DB_USER") or db_user

    # 6) ELAB URL
    url = env.get("ELAB_URL")
    if not url and (env_path or compose_path):
        ce = read_env_file(env_path or compose_path)
        url = ce.get("SITE_URL") or ce.get("ELAB_URL")
        if url and url.startswith("https://"):
            url = url.rstrip("/")
    if not url and container:
        # try the app container's env for SITE_URL
        app_c = find_elab_containers()
        if app_c:
            picked = app_c[0] if len(app_c) == 1 else pick(
                "Multiple eLabFTW app containers found - which one?",
                app_c)
            if picked:
                env_out = _run(["docker", "exec", picked, "env"]) or ""
                for ln in env_out.splitlines():
                    if ln.startswith("SITE_URL="):
                        url = ln.split("=", 1)[1].strip().rstrip("/")

    return {
        "container": container,
        "compose_file": str(compose_path) if compose_path else None,
        "db_name": db_name or "elabftw",
        "db_user": db_user,
        "db_password": db_password,
        "url": url,
    }


def ssh_cmd(host: str, cmd: str) -> str | None:
    """Run a remote command via ssh (for ELAB_SSH_HOST mode)."""
    return _run(["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
                 host, cmd])


if __name__ == "__main__":
    import json
    from gdpr_export import load_env
    env = load_env()
    result = resolve_db_target(env, type("A", (), {"db_container": None,
                                                   "db_env_file": None,
                                                   "db_name": None})())
    print(json.dumps(result, indent=2, ensure_ascii=False))
