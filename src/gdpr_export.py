#!/usr/bin/env python3
"""
eLabFTW — DSGVO Art. 15 Auskunft: Export-Skript (API-Teil).

Nutzt den offiziellen API-Wrapper elabapy (https://github.com/elabftw/elabapy)
mit einem Sysadmin-API-Key. Zieht alle personenbezogenen Daten eines Ziel-Users,
die per REST-API v2 erreichbar sind (siehe Recherche: Tabellen-Inventur +
ApiEndpoint/SubModels-Check im elabftw-Code).

NICHT per API abgedeckt (braucht DB/CLI — siehe gdpr_cli.sql):
  audit_logs, authfail, changelog (strukturiert), api_keys fremder User,
  exports fremder User, todolist/unfinished_steps/favtags/pins fremder User,
  sig_keys fremder User, exclusive_edit_mode, lockout_devices

Nutzung:
  ELAB_URL=https://eln.example.org ELAB_KEY=<sysadmin-key> ELAB_USERID=42 \
      .venv/bin/python gdpr_export.py [--out-dir DIR] [--dry-run] [--no-files]

  Oder Werte in elabftw.env (gleiche Keys, eine Zeile pro Key=Wert).
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import elabapy
import requests

HTTP_ERR = (elabapy.Error, requests.HTTPError)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENVFILE = PROJECT_ROOT / "elabftw.env"
PAGE = 50  # Eintraege pro API-Seite


def load_env() -> dict:
    env = dict(os.environ)
    if ENVFILE.exists():
        for line in ENVFILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def save_json(out_dir: Path, name: str, data) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / name).write_text(
        json.dumps(data, indent=2, ensure_ascii=False, default=str)
    )


def sanitize(name: str) -> str:
    keep = "".join(c for c in name if c.isalnum() or c in "._- ")
    return keep.strip() or "file"


def get_paged(manager, path: str, params: dict) -> list:
    """Paginiert ueber limit/offset, bis eine leere Seite kommt."""
    out = []
    params = dict(params)
    params.setdefault("limit", PAGE)
    offset = 0
    while True:
        params["offset"] = offset
        page = manager.send_req(path, params, param_name="params") or []
        out.extend(page)
        if len(page) < PAGE:
            break
        offset += PAGE
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(PROJECT_ROOT / "out"))
    ap.add_argument("--dry-run", action="store_true", help="nur zaehlen, nichts speichern")
    ap.add_argument("--no-files", action="store_true", help="Upload-Dateien nicht laden")
    args = ap.parse_args()

    env = load_env()
    url = env.get("ELAB_URL")
    key = env.get("ELAB_KEY")
    userid = env.get("ELAB_USERID")
    missing = [k for k, v in (("ELAB_URL", url), ("ELAB_KEY", key), ("ELAB_USERID", userid)) if not v]
    if missing:
        print(f"FEHLT: {', '.join(missing)} (Env oder {ENVFILE.name})")
        return 1

    manager = elabapy.Manager(endpoint=f"{url.rstrip('/')}/api/v2/", token=key)
    target = int(userid)
    out_dir = Path(args.out_dir)

    # 1) Stammdaten + Teams + Rollen (users/{id} enthaelt teams-JSON, last_login, ...)
    try:
        user = manager.send_req(f"users/{target}")
    except HTTP_ERR as e:
        print(f"User {target} nicht abrufbar: {e}")
        return 1
    if not user:
        print(f"User {target} nicht gefunden (404)")
        return 1
    teams = user.get("teams", [])
    team_ids = [t["id"] for t in teams if t.get("id")]
    print(f"User: {user.get('fullname')} <{user.get('email')}> | Teams: {[t.get('name') for t in teams]}")

    # 2) Submodelle auf User-Ebene (sysadmin-lesbar)
    sub_data = {}
    for name, path in {
        "rors": f"users/{target}/rors",
        "request_actions": f"users/{target}/request_actions",
        "notifications": f"users/{target}/notifications",
    }.items():
        try:
            data = manager.send_req(path)
            sub_data[name] = data if data is not None else []
        except HTTP_ERR as e:
            print(f"  ! {name}: {e}")
            sub_data[name] = None

    # 3) Team-Ebene: Gruppen + Procurement-Requests (nur seine)
    groups = []
    procurement = []
    for tid in team_ids:
        try:
            g = manager.send_req(f"teams/{tid}/teamgroups")
            if isinstance(g, dict):
                # API liefert {gruppen_id: {id, name, users: [...]}}
                groups.extend(g.values())
            elif g:
                groups.extend(g)
        except HTTP_ERR as e:
            print(f"  ! teamgroups team {tid}: {e}")
        try:
            pr = manager.send_req(f"teams/{tid}/procurement_requests") or []
            procurement.extend([r for r in pr if r.get("requester_userid") == target])
        except HTTP_ERR as e:
            print(f"  ! procurement team {tid}: {e}")

    # 4) Entries des Users (owner-Filter, scope=3 = alles, state 1,2,3 = inkl. archiviert+soft-deleted)
    entity_types = ["experiments", "items", "experiments_templates", "items_types"]
    entities = {et: [] for et in entity_types}
    for et in entity_types:
        try:
            entities[et] = get_paged(manager, et, {"owner": target, "scope": 3, "state": "1,2,3"})
        except HTTP_ERR as e:
            print(f"  ! {et}: {e}")

    # 5) Bookings (Scheduler-Events)
    bookings = []
    try:
        ev = manager.send_req("events", {"eventOwner": target}, param_name="params") or []
        bookings = [e for e in ev if e.get("userid") == target]
    except HTTP_ERR as e:
        print(f"  ! events: {e}")

    if args.dry_run:
        print("\n=== DRY RUN ===")
        print(f"Stammdaten:   {user.get('fullname')} <{user.get('email')}>")
        print(f"Teams:        {len(teams)}")
        for name, data in sub_data.items():
            print(f"{name:16s} {len(data) if data else 0}")
        print(f"Gruppen:      {len(groups)}")
        print(f"Procurement:  {len(procurement)}")
        print(f"Bookings:     {len(bookings)}")
        for et in entity_types:
            print(f"{et:22s} {len(entities[et])}")
        return 0

    # 6) Detail-Daten pro Entry
    subs = ["comments", "revisions", "steps", "tags", "request_actions"]
    details = {}
    for et in entity_types:
        for ent in entities[et]:
            eid = ent["id"]
            details[(et, eid)] = {"entity": ent}
            for sub in subs:
                try:
                    details[(et, eid)][sub] = manager.send_req(f"{et}/{eid}/{sub}") or []
                except HTTP_ERR as e:
                    print(f"  ! {et}/{eid}/{sub}: {e}")
                    details[(et, eid)][sub] = []

    # 7) Uploads (Metadaten + Dateien)
    upload_meta = {}
    files = 0
    for (et, eid), d in details.items():
        try:
            ups = manager.send_req(f"{et}/{eid}/uploads") or []
        except HTTP_ERR as e:
            print(f"  ! {et}/{eid}/uploads: {e}")
            continue
        upload_meta[(et, eid)] = ups
        if not args.no_files:
            for up in ups:
                uid = up["id"]
                try:
                    content = manager.send_req(f"{et}/{eid}/uploads/{uid}",
                                               {"format": "binary"}, verb="GET",
                                               binary=True, param_name="params")
                    # real_name = Originalname, long_name = interner Speicherpfad
                    fname = sanitize(up.get("real_name") or up.get("long_name") or f"upload-{uid}")
                    fdir = out_dir / "files" / f"{et}-{eid}"
                    fdir.mkdir(parents=True, exist_ok=True)
                    (fdir / f"{uid}-{fname}").write_bytes(content)
                    files += 1
                    time.sleep(0.1)
                except HTTP_ERR as e:
                    print(f"  ! download upload {uid}: {e}")

    # 7b) Lookups: Status-/Kategorie-Namen pro Team (fuer den Report)
    lookups = {}
    for tid in team_ids:
        team_lk = {}
        for lk, sub in [("experiments_status", "experiments_status"),
                        ("experiments_categories", "experiments_categories"),
                        ("items_status", "items_status"),
                        ("items_categories", "resources_categories"),
                        ("items_types", "items_types")]:
            try:
                data = manager.send_req(f"teams/{tid}/{sub}") or []
                team_lk[lk] = {str(d.get("id")): d.get("title") for d in data}
            except HTTP_ERR as e:
                print(f"  ! lookup {sub} team {tid}: {e}")
                team_lk[lk] = {}
        lookups[str(tid)] = team_lk

    # 8) Speichern
    save_json(out_dir, "user.json", user)
    for name in ["rors", "request_actions", "notifications"]:
        save_json(out_dir, f"{name}.json", sub_data[name] or [])
    save_json(out_dir, "groups.json", groups)
    save_json(out_dir, "procurement.json", procurement)
    save_json(out_dir, "bookings.json", bookings)
    save_json(out_dir, "manifest.json", {
        "target_userid": target,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "user": user,
        "rors": sub_data["rors"],
        "request_actions_user": sub_data["request_actions"],
        "notifications": sub_data["notifications"],
        "groups": groups,
        "procurement": procurement,
        "bookings": bookings,
        "entities": {et: [e["id"] for e in entities[et]] for et in entity_types},
        "upload_files_downloaded": files,
        "lookups": lookups,
        "cli_only_hinweise": [
            "api_keys: nur per DB (self-scoped)",
            "exports: nur per DB (self-scoped)",
            "todolist/unfinished_steps/favtags/pins: nur per DB (self-scoped)",
            "sig_keys: nur per DB (self-scoped)",
            "audit_logs: nur per DB (keine API-Route)",
            "authfail: nur per DB (keine API-Route)",
            "changelog: nur per DB oder als PDF-Export (format=pdf&changelog=1)",
            "exclusive_edit_mode/lockout_devices: nur per DB",
        ],
    })

    for et in entity_types:
        for ent in entities[et]:
            eid = ent["id"]
            d = details[(et, eid)]
            ent_dir = out_dir / et / str(eid)
            save_json(ent_dir, "entity.json", d["entity"])
            for sub in subs:
                save_json(ent_dir, f"{sub}.json", d[sub])
            if (et, eid) in upload_meta:
                save_json(ent_dir, "uploads.json", upload_meta[(et, eid)])

    # 9) Lesbare Zusammenfassung
    lines = [
        f"# eLabFTW DSGVO-Auskunft — User {target} ({user.get('fullname')})",
        "",
        f"E-Mail: {user.get('email')}  |  Erstellt: {user.get('created_at')}  |  Letzter Login: {user.get('last_login')}",
        f"Teams/Rollen: {json.dumps(teams, ensure_ascii=False)}",
        "",
        "## Mengen",
    ]
    for name, label in [("rors", "ROR-Zuordnungen"), ("request_actions", "Request-Actions"),
                        ("notifications", "Notifications")]:
        lines.append(f"- {label}: {len(sub_data[name] or [])}")
    lines.append(f"- Gruppen: {len(groups)}")
    lines.append(f"- Procurement-Requests: {len(procurement)}")
    lines.append(f"- Bookings: {len(bookings)}")
    for et in entity_types:
        n = len(entities[et])
        comments = sum(len(details[(et, e["id"])].get("comments", [])) for e in entities[et])
        revs = sum(len(details[(et, e["id"])].get("revisions", [])) for e in entities[et])
        ups = sum(len(upload_meta.get((et, e["id"]), [])) for e in entities[et])
        lines.append(f"- {et}: {n} Entries, {comments} Kommentare, {revs} Revisionen, {ups} Uploads")
    lines.append(f"- Upload-Dateien geladen: {files}")
    lines.append("")
    lines.append("## Nur per DB/CLI verfuegbar (siehe gdpr_cli.sql)")
    lines.append("- audit_logs, authfail, changelog (strukturiert), api_keys, exports,")
    lines.append("  todolist, unfinished_steps, favtags, pins, sig_keys, edit_mode, lockout_devices")
    (out_dir / "index.md").write_text("\n".join(lines))

    print(f"\nFertig. Ausgabe: {out_dir}")
    print("Entries: " + ", ".join(f"{et}={len(entities[et])}" for et in entity_types))
    print(f"Upload-Dateien: {files} | Uploads gesamt: {sum(len(v) for v in upload_meta.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
