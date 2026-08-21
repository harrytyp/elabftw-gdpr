#!/usr/bin/env python3
"""Build a small synthetic sample report (sample/sample-report/) so users
can see what a GDPR disclosure looks like - WITHOUT any real data.

The sample uses generic entries ("Sample Experiment", "Sample Item", ...)
and one record per appendix category, matching the DB pipeline output
layout so gdpr_report.py can render it. Run:

    python3 sample/make_sample_report.py
    # then open sample/sample-report/User1/index.html
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import gdpr_report  # noqa: E402

OUT = REPO / "sample" / "sample-report"


def w(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8")


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    uid = 1
    user_dir = OUT / f"User{uid}"
    user_dir.mkdir(parents=True)

    # --- user ---
    user = {
        "userid": uid,
        "email": "sample.user@example.org",
        "firstname": "Sample",
        "lastname": "User",
        "fullname": "Sample User",
        "created_at": "2024-01-15 09:00:00",
        "last_login": "2026-08-01 10:00:00",
        "validated": "1",
        "is_sysadmin": "0",
        "lang": "en_GB",
        "teams": [{"id": 1, "name": "Sample Team", "is_admin": 0, "is_owner": 0, "is_archived": 0}],
    }
    w(user_dir / "user.json", user)

    # --- entities ---
    entities = {
        "experiments": [1, 2],
        "items": [3],
        "experiments_templates": [4],
        "items_types": [5],
    }
    ent_spec = {
        1: ("experiments", "Sample Experiment A", "1", "2"),
        2: ("experiments", "Sample Experiment B", "1", "5"),
        3: ("items", "Sample Item / Resource", "2", None),
        4: ("experiments_templates", "Sample Template", None, None),
        5: ("items_types", "Sample Item Type", None, None),
    }
    for eid, (et, title, cat, status) in ent_spec.items():
        ent = {
            "id": eid, "title": title, "category": cat, "status": status,
            "state": "1", "created_at": "2025-03-01 08:00:00",
            "modified_at": "2025-06-15 12:00:00", "team": 1,
            "last_signed_by": None, "timestampedby": None,
            "signature_count": 0, "timestamped": 0,
        }
        edir = user_dir / et / str(eid)
        w(edir / "entity.json", ent)
        w(edir / "comments.json", [])
        w(edir / "revisions.json", [])
        w(edir / "steps.json", [
            {"id": 1, "item_id": eid, "body": "Sample step: prepare and measure",
             "finished": "1", "finished_time": "2025-03-02 09:30:00"},
        ])
        w(edir / "uploads.json", [])

    # one sample comment + revision on experiment 1 to show the sections
    w(user_dir / "experiments" / "1" / "comments.json", [
        {"id": 1, "item_id": 1, "userid": 1, "created_at": "2025-03-05 10:00:00",
         "comment": "Sample comment on the experiment."},
    ])
    w(user_dir / "experiments" / "1" / "revisions.json", [
        {"id": 1, "item_id": 1, "userid": 1, "created_at": "2025-03-06 11:00:00",
         "body": "Sample revision body."},
    ])

    # --- uploads (metadata only) ---
    uploads_all = [
        {"id": 1, "real_name": "sample-data.csv", "long_name": "1-sample-data.csv",
         "comment": "", "item_id": "1", "type": "experiments",
         "created_at": "2025-03-07 14:00:00", "hash": "abc123",
         "hash_algorithm": "sha256", "filesize": 2048, "state": "1",
         "storage": "local"},
        {"id": 2, "real_name": "sample-log.xlsx", "long_name": "2-sample-log.xlsx",
         "comment": "", "item_id": "3", "type": "items",
         "created_at": "2025-04-01 09:00:00", "hash": "def456",
         "hash_algorithm": "sha256", "filesize": 4096, "state": "1",
         "storage": "local"},
    ]
    w(user_dir / "uploads.json", uploads_all)
    # per-entity uploads (matching the DB pipeline layout so the entity
    # pages show them)
    for up in uploads_all:
        edir = user_dir / up["type"] / str(up["item_id"])
        w(edir / "uploads.json",
          [u for u in uploads_all
           if u["type"] == up["type"] and u["item_id"] == up["item_id"]])

    # --- teams ---
    w(user_dir / "teams.json", user["teams"])

    # --- db appendix (one row per category) ---
    w(user_dir / "db_appendix.json", {
        "audit_logs": [["2025-03-01 08:05:00", "New account", "1", "1", "Account created"]],
        "authfail": [["2025-04-01 09:00:00"]],
        "changelog": [["experiments", "2025-03-10 10:00:00", "1", '{"old": "a", "new": "b"}']],
        "api_keys": [["1", "sample-api-key", "2025-03-02 10:00:00", "2025-06-01 00:00:00", "1", "1"]],
        "exports": [["1", "2025-05-01 12:00:00", "1", "eln", "sample-export.zip", "1024"]],
        "todolist": [["1", "2025-04-02 08:00:00", "1", "Sample todo item"]],
        "sig_keys": [["1", "2025-03-03 09:00:00", "2025-06-01 00:00:00", "1", "1", "pubkey-dummy"]],
        "favtags": [["1"]],
        "pins": [["experiments", "1"]],
        "team_groups": [["1"]],
        "storage_history": [["2025-03-09 10:00:00", "1", None, "2"]],
        "storage_assignments": [["items", "3", "1", "1", "box", "2025-03-09 10:00:00"]],
        "compounds": [["1", "Sample Compound", "sample-iupac", "77-88-9", "2025-03-04 09:00:00", "1"]],
        "compound_links": [["experiments", "1", "1", "2025-03-04 09:05:00"]],
        "template_steps": [["experiments_templates", "4", "Sample template step", "0", None]],
        "request_actions": [["experiments", "1", "2025-05-02 10:00:00", "1", "1", "1", "1"]],
        "procurement": [["1", "2025-05-03 11:00:00", "3", "2", "0", "1", "1"]],
        "notifications": [["1", "2025-05-04 09:00:00", "1", "0", '{"message": "Sample notification"}']],
        "links": [["exp-item", "1", "3"]],
        "third_party_mentions": [],
        "comments_on_other_entries": [["experiments_comments", "9", "1", "2025-06-01 10:00:00",
                                       "Sample comment on another user's entry (redacted)"]],
        "name_mentions": [],
        "bookings": [["1", "Sample booking", "2025-06-10 09:00:00", "2025-06-10 11:00:00",
                      "1", None, None, "2025-05-20 08:00:00"]],
    })

    # --- manifest (source=db so the report renders the appendix) ---
    w(user_dir / "manifest.json", {
        "target_userid": uid,
        "exported_at": "2026-08-20T12:00:00+0000",
        "source": "db",
        "user": user,
        "teams": user["teams"],
        "entities": {et: ids for et, ids in entities.items()},
        "uploads_total": 1,
        "uploads_active": 1,
        "uploads_archived": 0,
        "upload_files_downloaded": 0,
        "db_appendix_counts": {k: len(v) for k, v in
                               json.loads((user_dir / "db_appendix.json").read_text()).items()},
    })

    # --- render the report into the sample dir ---
    rc = gdpr_report.build_report_for_user(user_dir)
    if rc != 0:
        print("report build failed")
        return 1

    print(f"Sample report written to {OUT}/")
    print("Open sample/sample-report/User1/index.html in a browser.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
