#!/usr/bin/env python3
"""Seed GDPR sample categories DIRECTLY in the eLabFTW database.

The API seed (tests/seed_test_data.py) cannot create categories that have no
working API route in eLabFTW (favorites/pins, team-group membership, failed
logins, export history, storage history, procurement, third-party comments).
This script inserts those records straight into MySQL for the GDPR test
user, so a sample disclosure shows *every* appendix section populated.

Only touches records that belong to the GDPR test setup (team "GDPR Test
Team", users gdpr-test@example.org) and is idempotent: it deletes its own
previous seed rows first.

Usage:
    python3 seed_db_categories.py --dry-run     # show what would be created
    python3 seed_db_categories.py               # actually insert
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from scripts.gdpr_detect import resolve_db_target  # noqa: E402

TEST_USER_EMAIL = "gdpr-test@example.org"
OTHER_USER_EMAIL = "marvin@example.org"   # third party in the same team
TEAM_NAME = "GDPR Test Team"


class A:
    db_container = None
    db_name = None
    db_env_file = None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="only print what would be inserted, write nothing")
    args = ap.parse_args()

    t = resolve_db_target({}, A())
    c, db, u, pw = t["container"], t["db_name"], t["db_user"], t["db_password"]

    def q(sql: str) -> list[list[str]]:
        r = subprocess.run(
            ["docker", "exec", c, "mysql", "-u", u, "-p" + pw, db, "-N",
             "--default-character-set=utf8mb4", "-e", sql],
            capture_output=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.decode("utf-8", "replace"))
        return [row.split("\t") for row in
                r.stdout.decode("utf-8", "replace").splitlines() if row]

    def esc(v) -> str:
        return str(v).replace("\\", "\\\\").replace("'", "''")

    # --- resolve ids -----------------------------------------------------
    rows = q(f"SELECT userid FROM users WHERE email='{TEST_USER_EMAIL}'")
    if not rows:
        print(f"Test user {TEST_USER_EMAIL} not found"); return 2
    uid = rows[0][0]
    rows = q(f"SELECT userid FROM users WHERE email='{OTHER_USER_EMAIL}'")
    other_uid = rows[0][0] if rows else None
    rows = q(f"SELECT id FROM teams WHERE name='{TEAM_NAME}'")
    tid = rows[0][0] if rows else None
    exp_rows = q(f"SELECT id FROM experiments WHERE userid={uid} ORDER BY id")
    exp_ids = [r[0] for r in exp_rows]
    item_rows = q(f"SELECT id FROM items WHERE userid={uid} ORDER BY id")
    item_ids = [r[0] for r in item_rows]
    # a foreign experiment (not owned by uid) for the "comment on other entry"
    foreign_exp = q(f"SELECT id FROM experiments WHERE userid<>'{uid}' "
                    f"AND userid IS NOT NULL LIMIT 1")

    print(f"Dry-run: {'JA (nichts geschrieben)' if args.dry_run else 'NEIN'}")
    print(f"Test user id={uid}, team={tid}, experiments={exp_ids}, items={item_ids}")
    print(f"Other user (3rd party) id={other_uid}, foreign exp={foreign_exp}")

    if args.dry_run:
        print("\n=== DRY-RUN: geplante Inserts (nichts geschrieben) ===")
        plan_sql = [
            ("authfail", f"INSERT INTO authfail (users_id, attempt_time, device_token) VALUES ({uid}, NOW() - INTERVAL 3 DAY, 'gdpr-sample-device'), ({uid}, NOW() - INTERVAL 2 DAY, 'gdpr-sample-device')"),
            ("exports", f"INSERT INTO exports (requester_userid, state, real_name, long_name, format, team, experiments, items) VALUES ({uid}, 1, 'gdpr-sample-export.eln', 'gdpr-sample-export.eln', 'eln', {tid}, 1, 1)"),
            ("tags", f"INSERT INTO tags (team, tag) VALUES ({tid}, 'GDPR Seed') -- falls nicht vorhanden"),
            ("favtags2users", f"INSERT IGNORE INTO favtags2users (users_id, tags_id) VALUES ({uid}, <tag_id>)"),
            ("pin_experiments2users", f"INSERT IGNORE INTO pin_experiments2users (users_id, entity_id) VALUES ({uid}, {exp_ids[0] if exp_ids else '?'})"),
            ("pin_items2users", f"INSERT IGNORE INTO pin_items2users (users_id, entity_id) VALUES ({uid}, {item_ids[0] if item_ids else '?'})"),
            ("team_groups", f"INSERT INTO team_groups (name, team) VALUES ('GDPR Sample Group', {tid}) -> id via LAST_INSERT_ID()"),
            ("users2team_groups", f"INSERT IGNORE INTO users2team_groups (userid, groupid) VALUES ({uid}, <neue gruppen-id>)"),
            ("storage_units", f"INSERT INTO storage_units (name, team) VALUES ('GDPR Sample Shelf', {tid}) -> id via LAST_INSERT_ID()"),
            ("storage_units_history", f"INSERT INTO storage_units_history (storage_unit_id, old_parent_id, new_parent_id, users_id) VALUES (<neue unit-id>, NULL, NULL, {uid})"),
            ("procurement_requests", f"INSERT INTO procurement_requests (team, requester_userid, entity_id, qty_ordered, body) VALUES ({tid}, {uid}, {exp_ids[0] if exp_ids else '?'}, 3, 'GDPR sample procurement')"),
            ("experiments_comments (fremd)", f"INSERT INTO experiments_comments (item_id, comment, userid) VALUES ({exp_ids[0] if exp_ids else '?'}, 'GDPR sample: comment by a colleague on your entry', {other_uid or '?'})"),
            ("experiments_comments (eigen, fremder eintrag)", f"INSERT INTO experiments_comments (item_id, comment, userid) VALUES ({foreign_exp[0][0] if foreign_exp else '?'}, 'GDPR sample: my comment on a shared entry', {uid})"),
        ]
        for table, sql in plan_sql:
            print(f"\n[{table}]\n  {sql}")
        print("\n(ohne --dry-run werden diese Inserts ausgefuehrt)")
        return 0

    # --- execute ----------------------------------------------------------
    print("\n=== FUEHRE INSERTS AUS ===")

    def insert(sql: str, desc: str) -> None:
        try:
            q(sql)
            print(f"  [ok] {desc}")
        except RuntimeError as e:
            print(f"  [FEHLER] {desc}: {e}")

    # --- cleanup previous GDPR-sample rows (idempotent) --------------------
    print("-- cleanup vorheriger GDPR-Sample-Eintraege --")
    q(f"DELETE FROM authfail WHERE users_id={uid} AND device_token='gdpr-sample-device'")
    q(f"DELETE FROM exports WHERE requester_userid={uid} AND real_name='gdpr-sample-export.eln'")
    q(f"DELETE FROM favtags2users WHERE users_id={uid}")
    q(f"DELETE FROM pin_experiments2users WHERE users_id={uid}")
    q(f"DELETE FROM pin_items2users WHERE users_id={uid}")
    # team group + membership (by name)
    grp_rows = q(f"SELECT id FROM team_groups WHERE name='GDPR Sample Group' AND team={tid}")
    if grp_rows:
        q(f"DELETE FROM users2team_groups WHERE groupid={grp_rows[0][0]}")
        q(f"DELETE FROM team_groups WHERE id={grp_rows[0][0]}")
    # storage unit + history (by name)
    unit_rows = q(f"SELECT id FROM storage_units WHERE name='GDPR Sample Shelf'")
    if unit_rows:
        q(f"DELETE FROM storage_units_history WHERE storage_unit_id={unit_rows[0][0]}")
        q(f"DELETE FROM storage_units WHERE id={unit_rows[0][0]}")
    q(f"DELETE FROM procurement_requests WHERE requester_userid={uid} AND body='GDPR sample procurement'")
    comp_rows = q(f"SELECT id FROM compounds WHERE userid={uid} LIMIT 1")
    if comp_rows:
        q(f"DELETE FROM compounds2experiments WHERE compound_id={comp_rows[0][0]}")
    q(f"DELETE FROM experiments_comments WHERE comment LIKE 'GDPR sample:%'")
    print("  cleanup fertig")

    # 1. authfail - failed logins for the test user
    insert(
        f"INSERT INTO authfail (users_id, attempt_time, device_token) VALUES "
        f"({uid}, NOW() - INTERVAL 3 DAY, 'gdpr-sample-device'), "
        f"({uid}, NOW() - INTERVAL 2 DAY, 'gdpr-sample-device')",
        "authfail (2 fehlgeschlagene Logins)")

    # 2. exports - one finished export row
    insert(
        f"INSERT INTO exports (requester_userid, state, real_name, long_name, "
        f"format, team, experiments, items) VALUES "
        f"({uid}, 1, 'gdpr-sample-export.eln', 'gdpr-sample-export.eln', "
        f"'eln', {tid}, 1, 1)",
        "exports (1 ELN-Export)")

    # 3. favtags - create a tag in the team first, then favourite it
    tag_rows = q(f"SELECT id FROM tags WHERE team={tid} AND tag='GDPR Seed'")
    if tag_rows:
        tag_id = tag_rows[0][0]
    else:
        q(f"INSERT INTO tags (team, tag) VALUES ({tid}, 'GDPR Seed')")
        # docker exec mysql is a NEW session per call -> LAST_INSERT_ID() is
        # useless; read back the highest id instead.
        tag_id = q(f"SELECT MAX(id) FROM tags WHERE team={tid} AND tag='GDPR Seed'")[0][0]
    insert(
        f"INSERT IGNORE INTO favtags2users (users_id, tags_id) VALUES "
        f"({uid}, {tag_id})",
        f"favtags2users (Tag 'GDPR Seed' id={tag_id})")

    # 4. pins - one experiment + one item
    if exp_ids:
        insert(
            f"INSERT IGNORE INTO pin_experiments2users (users_id, entity_id) "
            f"VALUES ({uid}, {exp_ids[0]})",
            f"pin_experiments2users (Exp {exp_ids[0]})")
    if item_ids:
        insert(
            f"INSERT IGNORE INTO pin_items2users (users_id, entity_id) "
            f"VALUES ({uid}, {item_ids[0]})",
            f"pin_items2users (Item {item_ids[0]})")

    # 5. team group + membership
    q(f"INSERT INTO team_groups (name, team) VALUES ('GDPR Sample Group', {tid})")
    grp_id = q(f"SELECT MAX(id) FROM team_groups WHERE name='GDPR Sample Group' AND team={tid}")[0][0]
    insert(
        f"INSERT IGNORE INTO users2team_groups (userid, groupid) "
        f"VALUES ({uid}, {grp_id})",
        f"users2team_groups (Gruppe id={grp_id})")

    # 6. storage unit + history (storage_units has NO team column)
    q(f"INSERT INTO storage_units (name) VALUES ('GDPR Sample Shelf')")
    unit_id = q(f"SELECT MAX(id) FROM storage_units WHERE name='GDPR Sample Shelf'")[0][0]
    insert(
        f"INSERT INTO storage_units_history (storage_unit_id, old_parent_id, "
        f"new_parent_id, users_id) VALUES ({unit_id}, NULL, NULL, {uid})",
        f"storage_units_history (Unit id={unit_id})")

    # 7. procurement - one request by the user
    if exp_ids:
        insert(
            f"INSERT INTO procurement_requests (team, requester_userid, "
            f"entity_id, qty_ordered, body) VALUES "
            f"({tid}, {uid}, {exp_ids[0]}, 3, 'GDPR sample procurement')",
            f"procurement_requests (Exp {exp_ids[0]})")

    # 7b. compound link - link the user's compound to one of their experiments
    comp_rows = q(f"SELECT id FROM compounds WHERE userid={uid} LIMIT 1")
    if comp_rows and exp_ids:
        insert(
            f"INSERT IGNORE INTO compounds2experiments (compound_id, entity_id) "
            f"VALUES ({comp_rows[0][0]}, {exp_ids[0]})",
            f"compounds2experiments (Compound {comp_rows[0][0]} -> Exp {exp_ids[0]})")
    else:
        print("  (kein Compound/Exp von User 3 - compound_link uebersprungen)")

    # 8. third-party comment: OTHER user comments on the test user's entry
    if other_uid and exp_ids:
        insert(
            f"INSERT INTO experiments_comments (item_id, comment, userid) "
            f"VALUES ({exp_ids[0]}, 'GDPR sample: comment by a colleague on "
            f"your entry', {other_uid})",
            f"Fremd-Kommentar von User {other_uid} auf Exp {exp_ids[0]}")

    # 9. comment on other entry: test user comments on a foreign experiment
    if foreign_exp:
        insert(
            f"INSERT INTO experiments_comments (item_id, comment, userid) "
            f"VALUES ({foreign_exp[0][0]}, 'GDPR sample: my comment on a "
            f"shared entry', {uid})",
            f"Eigener Kommentar auf fremdem Exp {foreign_exp[0][0]}")

    print("\nSeed abgeschlossen. Jetzt Export neu fahren:")
    print(f"  elab-gdpr-db --users {uid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
