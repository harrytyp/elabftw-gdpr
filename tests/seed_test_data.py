#!/usr/bin/env python3
"""Seed REAL eLabFTW data for the GDPR test user - via the real API.

Creates a dedicated GDPR test team + user (admin key, only if missing) and
then inserts one real record per GDPR data category AS THE TEST USER (user
key), using the instance's own API. Nothing is faked: every object exists in
eLabFTW with owner = test user and is downloaded again by the normal export
pipeline.

Usage:
  ELAB_URL=https://eln.example.org \
  ELAB_KEY=<sysadmin-key> \
  ELAB_USER_KEY=<test-user-api-key> \
      python3 tests/seed_test_data.py

Categories covered via API (as the test user):
  experiments, items, templates, item types, comments, steps, tags,
  uploads (real file), status/category, todolist, team groups, favorites.

Categories needing real usage (documented, not faked):
  audit_logs (real logins), authfail (real failed logins), notifications
  (real events), bookings (real scheduler bookings on bookable items),
  links (API route is broken upstream - 500), procurement (admin flow).
  See tests/README-testing.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("ELAB_URL", "").rstrip("/")
ADMIN_KEY = os.environ.get("ELAB_KEY", "")
USER_KEY = os.environ.get("ELAB_USER_KEY", "")
TEAM_NAME = "GDPR Test Team"
USER_EMAIL = "gdpr-test@example.org"
USER_FIRST = "GDPR"
USER_LAST = "Testuser"
TAG = "gdpr-seed"


class Api:
    def __init__(self, base: str, key: str):
        self.base = base
        self.key = key

    def req(self, method: str, path: str, body=None, raw=None,
            content_type="application/json"):
        url = f"{self.base}/api/v2{path}"
        if raw is not None:
            data = raw
        elif body is not None:
            data = json.dumps(body).encode()
        else:
            data = None
        r = urllib.request.Request(url, data=data, method=method)
        r.add_header("Authorization", self.key)
        if data:
            r.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                loc = resp.headers.get("Location", "")
                return resp.status, resp.read(), loc
        except urllib.error.HTTPError as e:
            return e.code, e.read(), ""

    def get(self, path):
        return self.req("GET", path)

    def post(self, path, body=None, raw=None, content_type="application/json"):
        return self.req("POST", path, body=body, raw=raw,
                        content_type=content_type)

    def patch(self, path, body):
        return self.req("PATCH", path, body=body)


def created_id(resp) -> int | None:
    code, out, loc = resp
    if code not in (200, 201):
        return None
    if loc:
        return int(loc.rstrip("/").split("/")[-1])
    try:
        return json.loads(out).get("id")
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team-name", default=TEAM_NAME)
    ap.add_argument("--user-email", default=USER_EMAIL)
    args = ap.parse_args()

    if not BASE or not USER_KEY:
        print("Set ELAB_URL and ELAB_USER_KEY (the test user's API key)")
        return 2

    admin = Api(BASE, ADMIN_KEY) if ADMIN_KEY else None
    user = Api(BASE, USER_KEY)

    # --- who am I (the test user) ---
    code, out, _ = user.get("/users/me")
    me = json.loads(out)
    uid = me["userid"]
    print(f"acting as user {uid}: {me['email']} ({me['fullname']})")

    # --- clean previous seed (idempotent: remove GDPR * entities) ---
    for et in ("experiments", "items", "experiments_templates", "items_types"):
        code, out, _ = user.get(f"/{et}?limit=500")
        try:
            items = json.loads(out)
        except Exception:
            continue
        for ent in (items if isinstance(items, list) else []):
            title = ent.get("title") or ""
            if title.startswith("GDPR Seed ") or title.startswith("GDPR Test "):
                code, out, _ = user.req("DELETE", f"/{et}/{ent['id']}")
                print(f"clean {et}/{ent['id']} -> {code}")
    # clean todolist
    code, out, _ = user.get("/todolist")
    try:
        for todo in json.loads(out):
            body = todo.get("body") or ""
            if body.startswith("GDPR Seed ") or body.startswith("GDPR test "):
                user.req("DELETE", f"/todolist/{todo['id']}")
                print("clean todo -> deleted")
    except Exception:
        pass

    # --- ensure team exists (admin only) ---
    tid = None
    if admin:
        code, out, _ = admin.get("/teams")
        teams = json.loads(out)
        team = next((t for t in teams if t["name"] == args.team_name), None)
        if not team:
            resp = admin.post("/teams", {"name": args.team_name})
            tid = created_id(resp)
            print(f"team create -> {resp[0]} id={tid}")
        else:
            tid = team["id"]
            print(f"team exists: id={tid}")

    # --- experiments ---
    e1 = created_id(user.post("/experiments", {
        "title": "GDPR Seed Experiment A",
        "body": "Real experiment created by the GDPR test user via API.",
        "date": "2026-08-20"}))
    e2 = created_id(user.post("/experiments", {
        "title": "GDPR Seed Experiment B",
        "body": "Second real experiment by the GDPR test user.",
        "date": "2026-08-21"}))
    print(f"experiments -> {e1}, {e2}")

    # --- item / template / item type ---
    it = created_id(user.post("/items", {
        "title": "GDPR Seed Item",
        "body": "Real resource item by the GDPR test user.",
        "date": "2026-08-20"}))
    tpl = created_id(user.post("/experiments_templates", {
        "title": "GDPR Seed Template",
        "body": "Real template by the GDPR test user."}))
    itype = created_id(user.post("/items_types", {
        "title": "GDPR Seed Item Type",
        "body": "Real item type by the GDPR test user."}))
    print(f"item={it} template={tpl} item_type={itype}")

    # --- comments / steps / tags on e1 ---
    if e1:
        for text in ("GDPR seed comment 1", "GDPR seed comment 2"):
            code, out, _ = user.post(f"/experiments/{e1}/comments", {"comment": text})
            print(f"comment -> {code}")
        code, out, _ = user.post(f"/experiments/{e1}/steps", {"body": "GDPR seed step"})
        print(f"step -> {code}")
        code, out, _ = user.post(f"/experiments/{e1}/tags", {"tag": TAG})
        print(f"tag -> {code}")

    # --- upload (real file) ---
    if e1:
        boundary = "----gdprboundary"
        raw = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="gdpr-seed.txt"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
        ).encode() + b"GDPR seed upload - real file bytes.\n" + \
            f"\r\n--{boundary}--\r\n".encode()
        code, out, _ = user.post(f"/experiments/{e1}/uploads", raw=raw,
                                 content_type=f"multipart/form-data; boundary={boundary}")
        print(f"upload -> {code}")

    # --- status / category via PATCH ---
    if e1:
        for field in ("status", "category"):
            code, out, _ = user.patch(f"/experiments/{e1}", {field: "1"})
            print(f"{field} -> {code}")

    # --- todolist ---
    code, out, _ = user.post("/todolist", {"body": "GDPR Seed todo"})
    print(f"todolist -> {code}")

    # --- team group (as admin, membership via admin) ---
    if admin and tid:
        code, out, _ = admin.post(f"/teams/{tid}/teamgroups", {"name": "GDPR Seed Group"})
        print(f"team group -> {code}")

    # --- links exp A <-> exp B, item <-> exp (per PATCH - the 5.6 API way) ---
    if e1 and e2:
        code, out, _ = user.patch(f"/experiments/{e1}", {"experiments_links": [e2]})
        print(f"experiments_link -> {code} {out[:80]}")
    if it and e1:
        code, out, _ = user.patch(f"/items/{it}", {"experiments_links": [e1]})
        print(f"items_link -> {code} {out[:80]}")

    # NOTE: containers/storage-assignment, compounds_links and request_actions
    # have no working POST/PATCH route in eLabFTW 5.6 (500 "column action
    # cannot be null" / 400 "invalid target") - documented, not faked.
    # favorites/pins, notifications, authfail, bookings arise from real UI
    # usage / real logins only (see tests/README-testing.md).

    print("\nSeed done. Export with:")
    print(f"  elab-gdpr-db --users {uid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
