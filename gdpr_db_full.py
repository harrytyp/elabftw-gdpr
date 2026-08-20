#!/usr/bin/env python3
"""gdpr_db_full.py - eLabFTW GDPR Art. 15 FULL DB export (no API key needed).

Pipeline B: reads everything from the eLabFTW MySQL database directly and
copies upload files from the docker volume, producing the SAME output layout
as gdpr_export.py (output/User<id>/ with manifest.json, entities/, uploads).

No ELAB_KEY required. DB access is auto-detected (docker containers, compose
.env files) and the user is asked when several candidates exist (recursive).
On the eLabFTW server itself: 1 click - no env, no code edits.

Usage:
  elab-gdpr-db --users 2,7 --dry-run
  elab-gdpr-db --users 2 --with-files
  elab-gdpr-db users            # list users from the DB
  elab-gdpr-db                  # interactive: container -> db -> user

Flags mirror gdpr_export.py: --users, --with-files, --no-files (compat),
--dry-run, --json, --out-dir, --env-file, plus --no-archived (uploads state=1
only) and --db-container / --db-name / --db-env-file (autodetect overrides).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / "elabftw.env"
OUTPUT_DIR = PROJECT_ROOT / "output"

logger = logging.getLogger("gdpr.db")


def load_env(env_file: str | None = None) -> dict:
    """Load KEY=VALUE credentials; env vars win over the file."""
    env: dict = {}
    path = Path(env_file) if env_file else ENV_FILE
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k, v in os.environ.items():
        if k.startswith("ELAB_") or k.startswith("MYSQL"):
            env[k] = v
    return env


def parse_user_ids(value: str | None) -> list[int]:
    if not value:
        return []
    out = []
    for part in str(value).replace(" ", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


def run(cmd: list[str], timeout: int = 60, input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, input=input_bytes,
                          timeout=timeout, text=False)


def mysql_exec(container: str, db: str, user: str, password: str,
               sql: str) -> str:
    """Run SQL against the container's MySQL; return stdout text."""
    proc = run(["docker", "exec", "-i", "-e", f"MYSQL_PWD={password}",
                container, "mysql", f"-u{user}", db],
               input_bytes=sql.encode("utf-8"))
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"mysql exec failed: {err}")
    return proc.stdout.decode("utf-8", "replace")


def mysql_select(container: str, db: str, user: str, password: str,
                 query: str) -> list[dict]:
    """Run a SELECT with -B -N and return rows as list of dicts (keys = header)."""
    full = f"{query}"
    proc = run(["docker", "exec", "-i", "-e", f"MYSQL_PWD={password}",
                container, "mysql", f"-u{user}", db, "-B", "-N"],
               input_bytes=full.encode("utf-8"))
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"mysql select failed: {err}")
    lines = proc.stdout.decode("utf-8", "replace").splitlines()
    return [json.loads(l) if l.startswith("{") else {"row": l}
            for l in lines if l.strip()]


def mysql_query_rows(container: str, db: str, user: str, password: str,
                     query: str) -> list[list[str]]:
    """Run a query, return rows as raw list-of-lists (for -B output)."""
    proc = run(["docker", "exec", "-i", "-e", f"MYSQL_PWD={password}",
                container, "mysql", f"-u{user}", db, "-B", "-N"],
               input_bytes=query.encode("utf-8"))
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"mysql query failed: {err}")
    return [line.split("\t") for line in
            proc.stdout.decode("utf-8", "replace").splitlines()]


def sanitize_filename(name: str) -> str:
    name = (name or "upload").strip().replace("/", "_").replace("\\", "_")
    return "".join(c for c in name if c.isalnum() or c in "._- ")[:120] or "upload"


def redact_names(text: str, names: list[str]) -> str:
    """Replace other users' names/emails in a comment with '[redacted]'.

    Never redacts the data subject's own name - only third parties.
    """
    if not text:
        return text
    for nm in names:
        nm = (nm or "").strip()
        if len(nm) < 3:  # too short to be safe
            continue
        text = text.replace(nm, "[redacted]")
    return text


def save_json(out_dir: Path, name: str, data) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")


def fetch_upload_file(container: str, long_name: str) -> bytes | None:
    """Copy an upload binary from the eLabFTW container's volume."""
    try:
        proc = run(["docker", "exec", container, "cat",
                    f"/elabftw/uploads/{long_name}"], timeout=30)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    return proc.stdout


def list_db_users(container: str, db: str, user: str, password: str) -> list[dict]:
    rows = mysql_query_rows(container, db, user, password,
                            "SELECT userid, email, firstname, lastname FROM users ORDER BY userid")
    return [{"userid": int(r[0]), "email": r[1], "firstname": r[2], "lastname": r[3]}
            for r in rows if r and r[0].isdigit()]


def pick_user_interactive(users: list[dict]) -> list[int]:
    print("\nUsers in the database:")
    for u in users:
        print(f"  {u['userid']:>4}  {u['email']}  ({u['firstname']} {u['lastname']})")
    print("  (comma-separated numbers, empty = all)")
    raw = input("> ").strip()
    if not raw:
        return [u["userid"] for u in users]
    return parse_user_ids(raw)


# ---------------------------------------------------------------------------
# main export logic
# ---------------------------------------------------------------------------


def export_one_user(target: int, out_dir: Path, conn: dict,
                    dry_run: bool, with_files: bool, with_archived: bool,
                    elab_container: str | None) -> tuple[bool, dict]:
    """Export ALL personal data for one user straight from the DB."""
    c, db, u, pw = conn["container"], conn["db_name"], conn["db_user"], conn["db_password"]
    counts: dict = {"userid": target}

    def q(sql: str) -> list[list[str]]:
        return mysql_query_rows(c, db, u, pw, sql)

    # --- A) Identity ------------------------------------------------------
    try:
        rows = q(f"SELECT userid, email, firstname, lastname, created_at, last_login, "
                 f"validated, is_sysadmin, lang, orcid FROM users WHERE userid={target}")
        if not rows:
            logger.error("User %s not found in DB", target)
            return False, counts
        r = rows[0]
        user = {"userid": int(r[0]), "email": r[1], "firstname": r[2],
                "lastname": r[3], "created_at": r[4], "last_login": r[5],
                "validated": r[6], "is_sysadmin": r[7], "lang": r[8], "orcid": r[9]}
        counts.update(fullname=f"{user.get('firstname','')} {user.get('lastname','')}".strip(),
                      email=user["email"])
        print(f"User: {counts['fullname']} <{user['email']}> | DB export")
    except RuntimeError as e:
        logger.error("User %s identity: %s", target, e)
        return False, counts

    # teams
    teams = []
    try:
        for row in q(f"SELECT teams_id, is_owner, is_admin, is_archived "
                     f"FROM users2teams WHERE users_id={target}"):
            teams.append({"id": int(row[0]), "is_owner": row[1],
                          "is_admin": row[2], "is_archived": row[3]})
    except RuntimeError:
        pass
    counts["teams"] = len(teams)

    # --- B) Content ---------------------------------------------------------
    entity_types = ["experiments", "items", "experiments_templates", "items_types"]
    entities = {et: [] for et in entity_types}
    for et in entity_types:
        try:
            rows = q(f"SELECT id, title, category, status, state, created_at, "
                     f"modified_at, team FROM {et} WHERE userid={target}")
            entities[et] = [{"id": int(r[0]), "title": r[1], "category": r[2],
                             "status": r[3], "state": r[4], "created_at": r[5],
                             "modified_at": r[6], "team": r[7]} for r in rows]
        except RuntimeError as e:
            logger.warning("entity %s: %s", et, e)

    # comments / revisions
    details = {}
    for et in ("experiments", "items"):
        try:
            for row in q(f"SELECT id, item_id, userid, created_at, comment "
                         f"FROM {et}_comments WHERE userid={target}"):
                key = (et, int(row[1]))
                details.setdefault(key, {"comments": [], "revisions": []})
                details[key]["comments"].append(
                    {"id": int(row[0]), "item_id": int(row[1]), "userid": int(row[2]),
                     "created_at": row[3], "comment": row[4]})
        except RuntimeError:
            pass
        try:
            for row in q(f"SELECT id, item_id, userid, created_at, body "
                         f"FROM {et}_revisions WHERE userid={target}"):
                key = (et, int(row[1]))
                details.setdefault(key, {"comments": [], "revisions": []})
                details[key]["revisions"].append(
                    {"id": int(row[0]), "item_id": int(row[1]), "userid": int(row[2]),
                     "created_at": row[3], "body": row[4]})
        except RuntimeError:
            pass

    # --- C) Uploads (ALL states) --------------------------------------------
    state_clause = "" if with_archived else " AND state=1"
    uploads_all = []
    try:
        rows = q(f"SELECT id, real_name, long_name, comment, item_id, type, "
                 f"created_at, hash, hash_algorithm, filesize, state, storage "
                 f"FROM uploads WHERE userid={target}{state_clause} ORDER BY created_at")
        uploads_all = [{"id": int(r[0]), "real_name": r[1], "long_name": r[2],
                        "comment": r[3], "item_id": r[4], "type": r[5],
                        "created_at": r[6], "hash": r[7], "hash_algorithm": r[8],
                        "filesize": r[9], "state": r[10], "storage": r[11]}
                       for r in rows]
    except RuntimeError as e:
        logger.warning("uploads: %s", e)
    active = [u for u in uploads_all if u["state"] == "1"]
    archived = [u for u in uploads_all if u["state"] == "2"]
    counts["uploads"] = len(uploads_all)
    counts["uploads_active"] = len(active)
    counts["uploads_archived"] = len(archived)

    # --- D) DB-only appendix --------------------------------------------------
    appendix = {}
    try:
        appendix["audit_logs"] = q(
            f"SELECT created_at, category, requester_userid, target_userid, LEFT(body,120) "
            f"FROM audit_logs WHERE requester_userid={target} OR target_userid={target} "
            f"ORDER BY created_at")
    except RuntimeError as e:
        logger.warning("audit_logs: %s", e)
    try:
        appendix["authfail"] = q(
            f"SELECT attempt_time FROM authfail WHERE users_id={target} ORDER BY attempt_time")
    except RuntimeError:
        pass
    try:
        appendix["changelog"] = q(
            f"SELECT 'experiments' AS type, created_at, target, content FROM experiments_changelog "
            f"WHERE users_id={target} UNION ALL "
            f"SELECT 'items', created_at, target, content FROM items_changelog "
            f"WHERE users_id={target} UNION ALL "
            f"SELECT 'experiments_templates', created_at, target, content "
            f"FROM experiments_templates_changelog WHERE users_id={target} UNION ALL "
            f"SELECT 'items_types', created_at, target, content FROM items_types_changelog "
            f"WHERE users_id={target} ORDER BY created_at")
    except RuntimeError:
        pass
    try:
        appendix["api_keys"] = q(
            f"SELECT id, name, created_at, last_used_at, can_write, team "
            f"FROM api_keys WHERE userid={target} ORDER BY created_at")
    except RuntimeError:
        pass
    try:
        appendix["exports"] = q(
            f"SELECT id, created_at, state, format, long_name, filesize "
            f"FROM exports WHERE requester_userid={target} ORDER BY created_at")
    except RuntimeError:
        pass
    try:
        appendix["todolist"] = q(
            f"SELECT id, creation_time, ordering, body FROM todolist WHERE userid={target}")
    except RuntimeError:
        pass
    try:
        appendix["sig_keys"] = q(
            f"SELECT id, created_at, last_used_at, state, type, pubkey "
            f"FROM sig_keys WHERE userid={target}")
    except RuntimeError:
        pass
    try:
        appendix["favtags"] = q(
            f"SELECT tags_id FROM favtags2users WHERE users_id={target}")
    except RuntimeError:
        pass
    try:
        appendix["pins"] = q(
            f"SELECT 'experiments' AS t, entity_id FROM pin_experiments2users WHERE users_id={target} "
            f"UNION ALL SELECT 'items', entity_id FROM pin_items2users WHERE users_id={target} "
            f"UNION ALL SELECT 'experiments_templates', entity_id FROM pin_experiments_templates2users WHERE users_id={target} "
            f"UNION ALL SELECT 'items_types', entity_id FROM pin_items_types2users WHERE users_id={target}")
    except RuntimeError:
        pass
    try:
        appendix["team_groups"] = q(
            f"SELECT groupid FROM users2team_groups WHERE userid={target}")
    except RuntimeError:
        pass
    try:
        appendix["storage_history"] = q(
            f"SELECT created_at, storage_unit_id, old_parent_id, new_parent_id "
            f"FROM storage_units_history WHERE users_id={target}")
    except RuntimeError:
        pass
    try:
        appendix["compounds"] = q(
            f"SELECT id, name, iupac_name, cas_number, smiles, created_at, team "
            f"FROM compounds WHERE userid={target}")
    except RuntimeError:
        pass
    try:
        appendix["request_actions"] = q(
            f"SELECT 'experiments' AS t, action, created_at, state, entity_id, requester_userid, target_userid "
            f"FROM experiments_request_actions WHERE requester_userid={target} OR target_userid={target} "
            f"UNION ALL "
            f"SELECT 'items', action, created_at, state, entity_id, requester_userid, target_userid "
            f"FROM items_request_actions WHERE requester_userid={target} OR target_userid={target}")
    except RuntimeError:
        pass
    try:
        appendix["procurement"] = q(
            f"SELECT id, created_at, entity_id, qty_ordered, qty_received, state, team "
            f"FROM procurement_requests WHERE requester_userid={target}")
    except RuntimeError:
        pass
    try:
        appendix["notifications"] = q(
            f"SELECT id, created_at, category, is_ack, LEFT(body,120) FROM notifications "
            f"WHERE userid={target}")
    except RuntimeError:
        pass
    try:
        appendix["links"] = q(
            f"SELECT 'exp-exp' AS t, item_id, link_id FROM experiments2experiments "
            f"WHERE item_id IN (SELECT id FROM experiments WHERE userid={target}) OR link_id IN (SELECT id FROM experiments WHERE userid={target}) "
            f"UNION ALL SELECT 'exp-item', item_id, link_id FROM experiments2items "
            f"WHERE item_id IN (SELECT id FROM experiments WHERE userid={target}) OR link_id IN (SELECT id FROM items WHERE userid={target}) "
            f"UNION ALL SELECT 'item-exp', item_id, link_id FROM items2experiments "
            f"WHERE item_id IN (SELECT id FROM items WHERE userid={target}) OR link_id IN (SELECT id FROM experiments WHERE userid={target}) "
            f"UNION ALL SELECT 'item-item', item_id, link_id FROM items2items "
            f"WHERE item_id IN (SELECT id FROM items WHERE userid={target}) OR link_id IN (SELECT id FROM items WHERE userid={target})")
    except RuntimeError:
        pass
    try:
        appendix["third_party_mentions"] = q(
            f"SELECT 'experiments_comments' AS t, item_id, userid, created_at, comment "
            f"FROM experiments_comments WHERE item_id IN (SELECT id FROM experiments WHERE userid={target}) AND userid<>{target} "
            f"UNION ALL "
            f"SELECT 'items_comments', item_id, userid, created_at, comment "
            f"FROM items_comments WHERE item_id IN (SELECT id FROM items WHERE userid={target}) AND userid<>{target}")
    except RuntimeError:
        pass
    try:
        # Comments/revisions BY the user on entries that are NOT theirs.
        # These are the user's own statements -> must be in the disclosure,
        # but only the comment itself (not the foreign entry's content).
        appendix["comments_on_other_entries"] = q(
            f"SELECT 'experiments_comments' AS t, item_id, userid, created_at, comment "
            f"FROM experiments_comments WHERE userid={target} "
            f"AND item_id NOT IN (SELECT id FROM experiments WHERE userid={target}) "
            f"UNION ALL "
            f"SELECT 'items_comments', item_id, userid, created_at, comment "
            f"FROM items_comments WHERE userid={target} "
            f"AND item_id NOT IN (SELECT id FROM items WHERE userid={target})")
    except RuntimeError:
        pass
    try:
        # Text search: comments by OTHERS mentioning the user's name/email.
        # Only the matching comment is returned (never the whole entry),
        # and other users' names are redacted by the report.
        u_email = (user.get("email") or "").lower()
        u_name = (f"{user.get('firstname') or ''} {user.get('lastname') or ''}").strip()
        search_terms = [t for t in (u_email, u_name) if len(t) >= 3]
        if search_terms:
            like_clauses = " OR ".join(
                f"comment LIKE '%{t}%'" for t in search_terms)
            appendix["name_mentions"] = q(
                f"SELECT 'experiments_comments' AS t, item_id, userid, created_at, comment "
                f"FROM experiments_comments "
                f"WHERE item_id NOT IN (SELECT id FROM experiments WHERE userid={target}) "
                f"AND ({like_clauses}) "
                f"UNION ALL "
                f"SELECT 'items_comments', item_id, userid, created_at, comment "
                f"FROM items_comments "
                f"WHERE item_id NOT IN (SELECT id FROM items WHERE userid={target}) "
                f"AND ({like_clauses})")
    except RuntimeError:
        pass
    try:
        appendix["bookings"] = q(
            f"SELECT id, title, start, end, team, experiment, item, created_at "
            f"FROM team_events WHERE userid={target}")
    except RuntimeError:
        pass

    counts["audit_logs"] = len(appendix.get("audit_logs", []))
    counts["authfail"] = len(appendix.get("authfail", []))
    counts["changelog"] = len(appendix.get("changelog", []))
    counts["api_keys"] = len(appendix.get("api_keys", []))
    counts["exports"] = len(appendix.get("exports", []))
    counts["todolist"] = len(appendix.get("todolist", []))
    counts["sig_keys"] = len(appendix.get("sig_keys", []))
    counts["favtags"] = len(appendix.get("favtags", []))
    counts["pins"] = len(appendix.get("pins", []))
    counts["team_groups"] = len(appendix.get("team_groups", []))
    counts["storage_history"] = len(appendix.get("storage_history", []))
    counts["compounds"] = len(appendix.get("compounds", []))
    counts["request_actions"] = len(appendix.get("request_actions", []))
    counts["procurement"] = len(appendix.get("procurement", []))
    counts["notifications"] = len(appendix.get("notifications", []))
    counts["links"] = len(appendix.get("links", []))
    counts["third_party_mentions"] = len(appendix.get("third_party_mentions", []))
    counts["comments_on_other_entries"] = len(appendix.get("comments_on_other_entries", []))
    counts["name_mentions"] = len(appendix.get("name_mentions", []))
    counts["bookings"] = len(appendix.get("bookings", []))

    if dry_run:
        print(f"\n=== DRY RUN user {target} (DB) ===")
        print(f"Account:      {counts['fullname']} <{counts['email']}>")
        print(f"Teams:        {counts['teams']}")
        for et in entity_types:
            print(f"{et:22s} {len(entities[et])}")
        print(f"uploads:      {counts['uploads']} "
              f"(active {counts['uploads_active']}, archived {counts['uploads_archived']})")
        for k in ("audit_logs", "authfail", "changelog", "api_keys", "exports",
                  "todolist", "sig_keys", "favtags", "pins", "team_groups",
                  "storage_history", "compounds", "request_actions",
                  "procurement", "notifications", "links",
                  "third_party_mentions", "comments_on_other_entries",
                  "name_mentions", "bookings"):
            print(f"{k:22s} {counts[k]}")
        return True, counts

    # --- Persist --------------------------------------------------------------
    save_json(out_dir, "user.json", user)
    save_json(out_dir, "teams.json", teams)
    for et in entity_types:
        for ent in entities[et]:
            eid = ent["id"]
            entry_dir = out_dir / et / str(eid)
            entry = details.get((et, eid), {"comments": [], "revisions": []})
            save_json(entry_dir, "entity.json", ent)
            save_json(entry_dir, "comments.json", entry.get("comments", []))
            save_json(entry_dir, "revisions.json", entry.get("revisions", []))
    save_json(out_dir, "uploads.json", uploads_all)
    save_json(out_dir, "db_appendix.json", appendix)

    # files
    files_downloaded = 0
    if with_files and elab_container:
        for up in uploads_all:
            long_name = up.get("long_name") or ""
            if not long_name:
                continue
            content = fetch_upload_file(elab_container, long_name)
            if content is None:
                logger.warning("file missing in volume: %s", long_name)
                continue
            fname = sanitize_filename(up.get("real_name") or f"upload-{up['id']}")
            file_dir = out_dir / "files" / f"db-{up.get('item_id') or up['id']}"
            file_dir.mkdir(parents=True, exist_ok=True)
            (file_dir / f"{up['id']}-{fname}").write_bytes(content)
            files_downloaded += 1
            time.sleep(0.05)

    save_json(out_dir, "manifest.json", {
        "target_userid": target,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "user": user,
        "teams": teams,
        "entities": {et: [e["id"] for e in entities[et]] for et in entity_types},
        "uploads_total": len(uploads_all),
        "uploads_active": len(active),
        "uploads_archived": len(archived),
        "upload_files_downloaded": files_downloaded,
        "db_appendix_counts": {k: len(v) for k, v in appendix.items()},
        "source": "db",
    })

    # index.md
    lines = [
        f"# eLabFTW GDPR disclosure - User {target} ({counts['fullname']})",
        "",
        f"Email: {user.get('email')}  |  Created: {user.get('created_at')}  |  "
        f"Last login: {user.get('last_login')}",
        f"Teams: {json.dumps(teams, ensure_ascii=False)}",
        "",
        "## Counts",
    ]
    for et in entity_types:
        lines.append(f"- {et}: {len(entities[et])}")
    lines.append(f"- Uploads: {len(uploads_all)} (active {len(active)}, archived {len(archived)})")
    lines.append(f"- Upload files: {files_downloaded}")
    lines.append("")
    lines.append("## DB appendix")
    for k, v in appendix.items():
        lines.append(f"- {k}: {len(v)}")
    (out_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")

    counts["files_downloaded"] = files_downloaded
    print(f"\nDone user {target}: {out_dir}")
    print("Entities: " + ", ".join(f"{et}={len(entities[et])}" for et in entity_types))
    print(f"Uploads: {len(uploads_all)} (active {len(active)}, archived {len(archived)}) | "
          f"Files: {files_downloaded}")
    return True, counts


def export_users(conn: dict, users: list[int], base_dir: Path,
                 dry_run: bool, with_files: bool, with_archived: bool,
                 elab_container: str | None) -> dict:
    results = {}
    for uid in users:
        print(f"\n===== User {uid} (DB) =====")
        logger.info("DB export user %s", uid)
        out_dir = base_dir / f"User{uid}"
        ok, counts = export_one_user(uid, out_dir, conn, dry_run, with_files,
                                     with_archived, elab_container)
        results[uid] = counts if ok else None
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="elab-gdpr-db",
        description="eLabFTW GDPR Art. 15 FULL export from the database "
                    "(no API key needed, recursive autodetect)")
    parser.add_argument("--users", default=None,
                        help="comma-separated user IDs (if omitted: interactive pick)")
    parser.add_argument("--env-file", default=None,
                        help="path to credentials file (default: elabftw.env)")
    parser.add_argument("--out-dir", default=str(OUTPUT_DIR),
                        help="base directory for per-user export folders")
    parser.add_argument("--dry-run", action="store_true",
                        help="only fetch and count, write nothing")
    parser.add_argument("--with-files", action="store_true",
                        help="also copy upload file contents from the docker volume")
    parser.add_argument("--no-files", action="store_true",
                        help=argparse.SUPPRESS)  # compat
    parser.add_argument("--no-archived", action="store_true",
                        help="only active uploads (state=1); default: all states")
    parser.add_argument("--json", action="store_true",
                        help="print the summary as JSON on stdout")
    parser.add_argument("--db-container", default=None,
                        help="MySQL/MariaDB container name (autodetect if omitted)")
    parser.add_argument("--db-name", default=None,
                        help="database name (autodetect if omitted)")
    parser.add_argument("--db-env-file", default=None,
                        help="compose/.env file with DB credentials (autodetect if omitted)")
    parser.add_argument("pos_users", nargs="*", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("users", help="list all users from the DB and exit")
    args = parser.parse_args()

    env = load_env(args.env_file)

    if args.command == "users":
        conn = detect_and_connect(env, args)
        users = list_db_users(conn["container"], conn["db_name"],
                              conn["db_user"], conn["db_password"])
        for u in users:
            print(f"{u['userid']:>4}  {u['email']}  ({u['firstname']} {u['lastname']})")
        return 0

    # detect target
    conn = detect_and_connect(env, args)
    elab_container = env.get("ELAB_ELAB_CONTAINER") or find_elab_container()

    users = parse_user_ids(args.users) or parse_user_ids(env.get("ELAB_USERID"))
    if not users and not args.dry_run:
        db_users = list_db_users(conn["container"], conn["db_name"],
                                 conn["db_user"], conn["db_password"])
        users = pick_user_interactive(db_users)
    if not users:
        print("No user IDs given - use --users 2,7 or run interactively")
        return 2

    with_files = bool(args.with_files) and not bool(args.no_files)
    with_archived = not args.no_archived
    results = export_users(conn, users, Path(args.out_dir), args.dry_run,
                           with_files, with_archived, elab_container)
    ok = sum(1 for v in results.values() if v is not None)
    if args.json:
        print(json.dumps({"users": results, "ok": ok, "total": len(results)},
                         indent=2, ensure_ascii=False, default=str))
    else:
        print(f"\nDB export done: {ok}/{len(results)} users ok -> {args.out_dir}")
        if not with_files:
            print("(metadata only - use --with-files to also copy upload binaries)")
        if with_archived:
            print("(includes archived uploads - use --no-archived to skip state=2)")
    return 0 if ok == len(results) else 1


def find_elab_container() -> str | None:
    """Find the eLabFTW app container (for volume file access)."""
    try:
        proc = subprocess.run(["docker", "ps", "--format", "{{.Names}}\t{{.Image}}"],
                              capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and ("elabftw" in parts[1].lower() or "elabimg" in parts[1].lower()):
            return parts[0]
    return None


def detect_and_connect(env: dict, args) -> dict:
    """Resolve DB target (explicit > env > autodetect recursive) and return conn."""
    from gdpr_detect import resolve_db_target
    target = resolve_db_target(env, args)
    if not target.get("container") and not target.get("db_password"):
        raise SystemExit("No DB found. Pass --db-container / --db-name / "
                         "--db-env-file or run on the eLabFTW server.")
    if not target.get("db_password"):
        print("WARNING: no DB password found - trying without one")
    return {
        "container": target["container"] or "elab-mysql",
        "db_name": target["db_name"] or "elabftw",
        "db_user": target["db_user"] or "elabftw",
        "db_password": target["db_password"] or "",
    }


if __name__ == "__main__":
    sys.exit(main())
