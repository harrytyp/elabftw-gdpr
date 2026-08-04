"""eLabFTW GDPR Art. 15 data export - API part.

Pulls all personal data of one or more target users that is reachable
through the eLabFTW REST API v2 using a sysadmin API key, via the official
elabapy wrapper. Output: one folder per user under ``output/``
(e.g. ``output/User75/``), see README.

NOT covered by the API (needs DB/CLI access - see ``gdpr_cli.sql``):
  audit_logs, authfail, changelog (structured), other users' api_keys,
  exports, todolist, unfinished_steps, favtags, pins, sig_keys,
  exclusive_edit_mode, lockout_devices

Standalone usage:
  gdpr_export.py [--users 75,82] [--dry-run] [--no-files] [--json]
                 [--env-file PATH]

Usually invoked through the gdpr.py entry point (subcommand "export").
Credentials: ELAB_URL / ELAB_KEY / ELAB_USERID from elabftw.env or
environment variables (env wins).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import elabapy
import requests

# elabapy raises requests.HTTPError from send_req, not its own Error class
HTTP_ERRORS = (elabapy.Error, requests.HTTPError)

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / "elabftw.env"
OUTPUT_DIR = PROJECT_ROOT / "output"
PAGE_SIZE = 50  # entries per API page

logger = logging.getLogger(__name__)


def load_env(env_file: str | None = None) -> dict:
    """Merge environment variables with values from an env file (env wins)."""
    env = dict(os.environ)
    path = Path(env_file) if env_file else ENV_FILE
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return env


def parse_user_ids(value: str | None) -> list[int]:
    """Parse a comma-separated user id string ('75, 82') into ints."""
    if not value:
        return []
    return [int(x) for x in str(value).replace(" ", "").split(",") if x]


def get_manager(env: dict) -> elabapy.Manager:
    return elabapy.Manager(endpoint=f"{env['ELAB_URL'].rstrip('/')}/api/v2/",
                           token=env["ELAB_KEY"])


def list_users(manager: elabapy.Manager) -> list[dict]:
    """Return all users visible to the sysadmin key (id, fullname, email)."""
    users = manager.send_req("users") or []
    return [{"userid": u.get("userid"), "fullname": u.get("fullname"),
             "email": u.get("email")} for u in users]


def sanitize_filename(name: str) -> str:
    """Filesystem-safe file name (keeps letters, digits, . _ - space)."""
    keep = "".join(c for c in name if c.isalnum() or c in "._- ")
    return keep.strip() or "file"


def fetch_paginated(manager: elabapy.Manager, path: str, params: dict) -> list:
    """Page through a collection endpoint (limit/offset) until an empty page."""
    out: list = []
    params = dict(params)
    params.setdefault("limit", PAGE_SIZE)
    offset = 0
    while True:
        params["offset"] = offset
        page = manager.send_req(path, params, param_name="params") or []
        out.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return out


def save_json(out_dir: Path, name: str, data) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str)
    )


def export_one_user(manager: elabapy.Manager, target: int, out_dir: Path,
                    dry_run: bool, no_files: bool) -> tuple[bool, dict]:
    """Export all API-reachable personal data for a single user.

    Returns (success, counts-dict); counts is empty on failure.
    """
    counts: dict = {"userid": target}

    # --- 1. Account data: profile, teams, roles -----------------------------
    try:
        user = manager.send_req(f"users/{target}")
    except HTTP_ERRORS as e:
        logger.error("User %s not retrievable: %s", target, e)
        return False, counts
    if not user:
        logger.error("User %s not found (404)", target)
        return False, counts
    teams = user.get("teams", [])
    team_ids = [t["id"] for t in teams if t.get("id")]
    counts.update(fullname=user.get("fullname"), email=user.get("email"),
                  teams=len(teams))
    print(f"User: {user.get('fullname')} <{user.get('email')}> | "
          f"Teams: {[t.get('name') for t in teams]}")

    # --- 2. User-level sub-resources (sysadmin-readable) ---------------------
    user_subs = {}
    for name, path in {
        "rors": f"users/{target}/rors",
        "request_actions": f"users/{target}/request_actions",
        "notifications": f"users/{target}/notifications",
    }.items():
        try:
            data = manager.send_req(path)
            user_subs[name] = data if data is not None else []
        except HTTP_ERRORS as e:
            logger.warning("user %s: %s not retrievable: %s", target, name, e)
            user_subs[name] = None

    # --- 3. Team level: group memberships + procurement requests ------------
    groups = []
    procurement = []
    for tid in team_ids:
        try:
            response = manager.send_req(f"teams/{tid}/teamgroups")
            if isinstance(response, dict):
                # API returns {group_id: {id, name, users: [...]}}
                groups.extend(response.values())
            elif response:
                groups.extend(response)
        except HTTP_ERRORS as e:
            logger.warning("user %s: teamgroups team %s: %s", target, tid, e)
        try:
            requests_list = manager.send_req(f"teams/{tid}/procurement_requests") or []
            procurement.extend(
                [r for r in requests_list if r.get("requester_userid") == target]
            )
        except HTTP_ERRORS as e:
            logger.warning("user %s: procurement team %s: %s", target, tid, e)

    # --- 4. Entities owned by the user (scope=3, incl. archived + deleted) --
    entity_types = ["experiments", "items", "experiments_templates", "items_types"]
    entities = {et: [] for et in entity_types}
    for et in entity_types:
        try:
            entities[et] = fetch_paginated(manager, et,
                                           {"owner": target, "scope": 3, "state": "1,2,3"})
        except HTTP_ERRORS as e:
            logger.warning("user %s: %s not retrievable: %s", target, et, e)

    # --- 5. Scheduler bookings -------------------------------------------------
    bookings = []
    try:
        events = manager.send_req("events", {"eventOwner": target}, param_name="params") or []
        bookings = [e for e in events if e.get("userid") == target]
    except HTTP_ERRORS as e:
        logger.warning("user %s: events: %s", target, e)

    counts.update(notifications=len(user_subs.get("notifications") or []),
                  groups=len(groups), procurement=len(procurement),
                  bookings=len(bookings),
                  entities={et: len(entities[et]) for et in entity_types})

    if dry_run:
        print(f"\n=== DRY RUN user {target} ===")
        print(f"Account:      {user.get('fullname')} <{user.get('email')}>")
        print(f"Teams:        {len(teams)}")
        for name in ("rors", "request_actions", "notifications"):
            data = user_subs.get(name)
            print(f"{name:16s} {len(data) if data else 0}")
        print(f"Groups:       {len(groups)}")
        print(f"Procurement:  {len(procurement)}")
        print(f"Bookings:     {len(bookings)}")
        for et in entity_types:
            print(f"{et:22s} {len(entities[et])}")
        return True, counts

    # --- 6. Per-entity detail: comments, revisions, steps, tags, actions ----
    detail_subs = ["comments", "revisions", "steps", "tags", "request_actions"]
    details = {}
    for et in entity_types:
        for ent in entities[et]:
            eid = ent["id"]
            details[(et, eid)] = {"entity": ent}
            for sub in detail_subs:
                try:
                    details[(et, eid)][sub] = manager.send_req(f"{et}/{eid}/{sub}") or []
                except HTTP_ERRORS as e:
                    logger.warning("user %s: %s/%s/%s: %s", target, et, eid, sub, e)
                    details[(et, eid)][sub] = []

    # --- 7. Uploads: metadata + file contents (real_name = original name) ----
    upload_meta = {}
    files_downloaded = 0
    for (et, eid), entry in details.items():
        try:
            uploads = manager.send_req(f"{et}/{eid}/uploads") or []
        except HTTP_ERRORS as e:
            logger.warning("user %s: %s/%s/uploads: %s", target, et, eid, e)
            continue
        upload_meta[(et, eid)] = uploads
        if not no_files:
            for upload in uploads:
                uid = upload["id"]
                try:
                    content = manager.send_req(f"{et}/{eid}/uploads/{uid}",
                                               {"format": "binary"}, verb="GET",
                                               binary=True, param_name="params")
                    # real_name = original upload name, long_name = internal path
                    fname = sanitize_filename(upload.get("real_name")
                                              or upload.get("long_name")
                                              or f"upload-{uid}")
                    file_dir = out_dir / "files" / f"{et}-{eid}"
                    file_dir.mkdir(parents=True, exist_ok=True)
                    (file_dir / f"{uid}-{fname}").write_bytes(content)
                    files_downloaded += 1
                    time.sleep(0.1)
                except HTTP_ERRORS as e:
                    logger.warning("user %s: download upload %s: %s", target, uid, e)

    # --- 8. Lookups: status/category names per team (for the report) ---------
    # items_types is a top-level endpoint, not a team submodel
    try:
        items_types_data = manager.send_req("items_types") or []
        items_types_map = {str(d.get("id")): d.get("title") for d in items_types_data}
    except HTTP_ERRORS as e:
        logger.warning("user %s: items_types lookup: %s", target, e)
        items_types_map = {}
    lookups = {}
    for tid in team_ids:
        team_lookups = {}
        for key, sub in [("experiments_status", "experiments_status"),
                         ("experiments_categories", "experiments_categories"),
                         ("items_status", "items_status"),
                         ("items_categories", "resources_categories")]:
            try:
                data = manager.send_req(f"teams/{tid}/{sub}") or []
                team_lookups[key] = {str(d.get("id")): d.get("title") for d in data}
            except HTTP_ERRORS as e:
                logger.warning("user %s: lookup %s team %s: %s", target, sub, tid, e)
                team_lookups[key] = {}
        team_lookups["items_types"] = items_types_map
        lookups[str(tid)] = team_lookups

    # --- 9. Persist raw export ------------------------------------------------
    save_json(out_dir, "user.json", user)
    for name in ["rors", "request_actions", "notifications"]:
        save_json(out_dir, f"{name}.json", user_subs[name] or [])
    save_json(out_dir, "groups.json", groups)
    save_json(out_dir, "procurement.json", procurement)
    save_json(out_dir, "bookings.json", bookings)
    save_json(out_dir, "manifest.json", {
        "target_userid": target,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "user": user,
        "rors": user_subs["rors"],
        "request_actions_user": user_subs["request_actions"],
        "notifications": user_subs["notifications"],
        "groups": groups,
        "procurement": procurement,
        "bookings": bookings,
        "entities": {et: [e["id"] for e in entities[et]] for et in entity_types},
        "upload_files_downloaded": files_downloaded,
        "lookups": lookups,
        "cli_only_notes": [
            "api_keys: DB only (self-scoped)",
            "exports: DB only (self-scoped)",
            "todolist/unfinished_steps/favtags/pins: DB only (self-scoped)",
            "sig_keys: DB only (self-scoped)",
            "audit_logs: DB only (no API route)",
            "authfail: DB only (no API route)",
            "changelog: DB only or via PDF export (format=pdf&changelog=1)",
            "exclusive_edit_mode/lockout_devices: DB only",
        ],
    })

    for et in entity_types:
        for ent in entities[et]:
            eid = ent["id"]
            entry = details[(et, eid)]
            entry_dir = out_dir / et / str(eid)
            save_json(entry_dir, "entity.json", entry["entity"])
            for sub in detail_subs:
                save_json(entry_dir, f"{sub}.json", entry[sub])
            if (et, eid) in upload_meta:
                save_json(entry_dir, "uploads.json", upload_meta[(et, eid)])

    # --- 10. Readable summary (index.md) --------------------------------------
    lines = [
        f"# eLabFTW GDPR disclosure - User {target} ({user.get('fullname')})",
        "",
        f"Email: {user.get('email')}  |  Created: {user.get('created_at')}  |  "
        f"Last login: {user.get('last_login')}",
        f"Teams/roles: {json.dumps(teams, ensure_ascii=False)}",
        "",
        "## Counts",
    ]
    for name, label in [("rors", "ROR affiliations"),
                        ("request_actions", "Request actions"),
                        ("notifications", "Notifications")]:
        lines.append(f"- {label}: {len(user_subs[name] or [])}")
    lines.append(f"- Groups: {len(groups)}")
    lines.append(f"- Procurement requests: {len(procurement)}")
    lines.append(f"- Bookings: {len(bookings)}")
    for et in entity_types:
        n = len(entities[et])
        comments = sum(len(details[(et, e["id"])].get("comments", [])) for e in entities[et])
        revisions = sum(len(details[(et, e["id"])].get("revisions", [])) for e in entities[et])
        uploads = sum(len(upload_meta.get((et, e["id"]), [])) for e in entities[et])
        lines.append(f"- {et}: {n} entries, {comments} comments, {revisions} revisions, {uploads} uploads")
    lines.append(f"- Upload files downloaded: {files_downloaded}")
    lines.append("")
    lines.append("## DB/CLI only (see gdpr_cli.sql)")
    lines.append("- audit_logs, authfail, changelog (structured), api_keys, exports,")
    lines.append("  todolist, unfinished_steps, favtags, pins, sig_keys, edit_mode, lockout_devices")
    (out_dir / "index.md").write_text("\n".join(lines))

    counts.update(uploads=sum(len(v) for v in upload_meta.values()),
                  files_downloaded=files_downloaded)
    print(f"\nDone user {target}: {out_dir}")
    print("Entities: " + ", ".join(f"{et}={len(entities[et])}" for et in entity_types))
    print(f"Upload files: {files_downloaded} | Uploads total: "
          f"{sum(len(v) for v in upload_meta.values())}")
    return True, counts


def export_users(env: dict, users: list[int], base_dir: Path,
                 dry_run: bool, no_files: bool) -> dict:
    """Export all listed users; returns {userid: counts} (empty counts on failure)."""
    manager = get_manager(env)
    results = {}
    for uid in users:
        print(f"\n===== User {uid} =====")
        logger.info("Export user %s (dry_run=%s, no_files=%s)", uid, dry_run, no_files)
        out_dir = base_dir / f"User{uid}"
        ok, counts = export_one_user(manager, uid, out_dir, dry_run, no_files)
        results[uid] = counts if ok else None
        logger.info("User %s export %s", uid, "ok" if ok else "failed")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="eLabFTW GDPR Art. 15 data export (API part, sysadmin key)")
    parser.add_argument("--users", default=None,
                        help="comma-separated user IDs (default: ELAB_USERID)")
    parser.add_argument("--env-file", default=None,
                        help="path to the credentials file (default: elabftw.env)")
    parser.add_argument("--out-dir", default=str(OUTPUT_DIR),
                        help="base directory for the per-user export folders")
    parser.add_argument("--dry-run", action="store_true",
                        help="only fetch and count, write nothing")
    parser.add_argument("--no-files", action="store_true",
                        help="skip downloading upload file contents")
    parser.add_argument("--json", action="store_true",
                        help="print the summary as JSON on stdout")
    args = parser.parse_args()

    env = load_env(args.env_file)
    url = env.get("ELAB_URL")
    key = env.get("ELAB_KEY")
    if not url or not key:
        print(f"Missing credentials - run gdpr.py first or fill {ENV_FILE.name}")
        return 2
    users = parse_user_ids(args.users) or parse_user_ids(env.get("ELAB_USERID"))
    if not users:
        print("No user IDs given - use --users 75,82 or set ELAB_USERID")
        return 2

    results = export_users(env, users, Path(args.out_dir), args.dry_run, args.no_files)
    ok = sum(1 for v in results.values() if v is not None)

    if args.json:
        print(json.dumps({"users": results, "ok": ok, "total": len(results)},
                         indent=2, ensure_ascii=False, default=str))
    else:
        print(f"\nExported {ok}/{len(users)} users")
    return 0 if ok == len(users) else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(main())
