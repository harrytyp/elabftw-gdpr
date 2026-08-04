"""eLabFTW GDPR Art. 15 data export - API part.

Pulls all personal data of a target user that is reachable through the
eLabFTW REST API v2 using a sysadmin API key, via the official elabapy
wrapper. Output: structured JSON under ``out/`` (see README).

NOT covered by the API (needs DB/CLI access - see ``sql/gdpr_cli.sql``):
  audit_logs, authfail, changelog (structured), other users' api_keys,
  exports, todolist, unfinished_steps, favtags, pins, sig_keys,
  exclusive_edit_mode, lockout_devices

Usage:
  gdpr-export [--dry-run] [--no-files] [--out-dir DIR]

Credentials are read from ``elabftw.env`` in the project root:
  ELAB_URL=https://eln.example.org
  ELAB_KEY=<sysadmin-api-key>
  ELAB_USERID=42
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import elabapy
import requests

# elabapy raises requests.HTTPError from send_req, not its own Error class
HTTP_ERRORS = (elabapy.Error, requests.HTTPError)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / "elabftw.env"
PAGE_SIZE = 50  # entries per API page


def load_env() -> dict:
    """Merge environment variables with values from elabftw.env (env wins)."""
    env = dict(os.environ)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="eLabFTW GDPR Art. 15 data export (API part, sysadmin key)")
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "out"),
                        help="target directory for raw JSON export")
    parser.add_argument("--dry-run", action="store_true",
                        help="only fetch and count, write nothing")
    parser.add_argument("--no-files", action="store_true",
                        help="skip downloading upload file contents")
    args = parser.parse_args()

    env = load_env()
    url = env.get("ELAB_URL")
    key = env.get("ELAB_KEY")
    userid = env.get("ELAB_USERID")
    missing = [k for k, v in (("ELAB_URL", url), ("ELAB_KEY", key),
                              ("ELAB_USERID", userid)) if not v]
    if missing:
        print(f"Missing: {', '.join(missing)} (env or {ENV_FILE.name})")
        return 1

    manager = elabapy.Manager(endpoint=f"{url.rstrip('/')}/api/v2/", token=key)
    target = int(userid)
    out_dir = Path(args.out_dir)

    # --- 1. Account data: profile, teams, roles -----------------------------
    try:
        user = manager.send_req(f"users/{target}")
    except HTTP_ERRORS as e:
        print(f"User {target} not retrievable: {e}")
        return 1
    if not user:
        print(f"User {target} not found (404)")
        return 1
    teams = user.get("teams", [])
    team_ids = [t["id"] for t in teams if t.get("id")]
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
            print(f"  ! {name}: {e}")
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
            print(f"  ! teamgroups team {tid}: {e}")
        try:
            requests_list = manager.send_req(f"teams/{tid}/procurement_requests") or []
            procurement.extend(
                [r for r in requests_list if r.get("requester_userid") == target]
            )
        except HTTP_ERRORS as e:
            print(f"  ! procurement team {tid}: {e}")

    # --- 4. Entities owned by the user (scope=3, incl. archived + deleted) --
    entity_types = ["experiments", "items", "experiments_templates", "items_types"]
    entities = {et: [] for et in entity_types}
    for et in entity_types:
        try:
            entities[et] = fetch_paginated(manager, et,
                                           {"owner": target, "scope": 3, "state": "1,2,3"})
        except HTTP_ERRORS as e:
            print(f"  ! {et}: {e}")

    # --- 5. Scheduler bookings -------------------------------------------------
    bookings = []
    try:
        events = manager.send_req("events", {"eventOwner": target}, param_name="params") or []
        bookings = [e for e in events if e.get("userid") == target]
    except HTTP_ERRORS as e:
        print(f"  ! events: {e}")

    if args.dry_run:
        print("\n=== DRY RUN ===")
        print(f"Account:      {user.get('fullname')} <{user.get('email')}>")
        print(f"Teams:        {len(teams)}")
        for name, data in user_subs.items():
            print(f"{name:16s} {len(data) if data else 0}")
        print(f"Groups:       {len(groups)}")
        print(f"Procurement:  {len(procurement)}")
        print(f"Bookings:     {len(bookings)}")
        for et in entity_types:
            print(f"{et:22s} {len(entities[et])}")
        return 0

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
                    print(f"  ! {et}/{eid}/{sub}: {e}")
                    details[(et, eid)][sub] = []

    # --- 7. Uploads: metadata + file contents (real_name = original name) ----
    upload_meta = {}
    files_downloaded = 0
    for (et, eid), entry in details.items():
        try:
            uploads = manager.send_req(f"{et}/{eid}/uploads") or []
        except HTTP_ERRORS as e:
            print(f"  ! {et}/{eid}/uploads: {e}")
            continue
        upload_meta[(et, eid)] = uploads
        if not args.no_files:
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
                    print(f"  ! download upload {uid}: {e}")

    # --- 8. Lookups: status/category names per team (for the report) ---------
    lookups = {}
    for tid in team_ids:
        team_lookups = {}
        for key, sub in [("experiments_status", "experiments_status"),
                         ("experiments_categories", "experiments_categories"),
                         ("items_status", "items_status"),
                         ("items_categories", "resources_categories"),
                         ("items_types", "items_types")]:
            try:
                data = manager.send_req(f"teams/{tid}/{sub}") or []
                team_lookups[key] = {str(d.get("id")): d.get("title") for d in data}
            except HTTP_ERRORS as e:
                print(f"  ! lookup {sub} team {tid}: {e}")
                team_lookups[key] = {}
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
    lines.append("## DB/CLI only (see sql/gdpr_cli.sql)")
    lines.append("- audit_logs, authfail, changelog (structured), api_keys, exports,")
    lines.append("  todolist, unfinished_steps, favtags, pins, sig_keys, edit_mode, lockout_devices")
    (out_dir / "index.md").write_text("\n".join(lines))

    print(f"\nDone. Output: {out_dir}")
    print("Entities: " + ", ".join(f"{et}={len(entities[et])}" for et in entity_types))
    print(f"Upload files: {files_downloaded} | Uploads total: "
          f"{sum(len(v) for v in upload_meta.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
