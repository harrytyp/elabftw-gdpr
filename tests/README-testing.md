# Testing the GDPR export with real data

`seed_test_data.py` creates **real** eLabFTW records (via the instance's own
API) for a dedicated GDPR test user, so the export pipeline can be verified
end-to-end with genuine data — nothing is faked, no direct DB inserts for
content, no mock JSON.

## Requirements

- A running eLabFTW instance (test instance recommended)
- `ELAB_URL` — instance base URL
- `ELAB_KEY` — **sysadmin** key (only used to create the team if missing)
- `ELAB_USER_KEY` — API key of the **test user** (create it in the UI:
  User menu → API keys → new key; or ask the instance admin)

## Run

```bash
ELAB_URL=https://eln.example.org \
ELAB_KEY=<sysadmin-key> \
ELAB_USER_KEY=<test-user-key> \
    python3 tests/seed_test_data.py
```

The script is idempotent: it first deletes any previous `GDPR *` entities of
the test user, then creates fresh ones. It prints every API call's status.

Then export the test user and check every category:

```bash
elab-gdpr-db --users <test-user-id> --dry-run
# expected: experiments 2, items 1, templates 1, item types 1, uploads 1,
#           todolist 1, audit_logs >0, changelog >0, api_keys 1
elab-gdpr-db --users <test-user-id> --with-files
# full package with the real upload file
```

## What is seeded (per category, via the real API)

| Category | How | API call |
|---|---|---|
| experiments | real experiment A+B | `POST /experiments` |
| items | real resource item | `POST /items` |
| templates | real experiment template | `POST /experiments_templates` |
| item types | real item type | `POST /items_types` |
| comments | 2 real comments | `POST /experiments/{id}/comments` |
| steps | 1 real step | `POST /experiments/{id}/steps` |
| tags | 1 real tag | `POST /experiments/{id}/tags` |
| uploads | 1 real file (multipart) | `POST /experiments/{id}/uploads` |
| status/category | set via PATCH | `PATCH /experiments/{id}` |
| todolist | 1 real todo | `POST /todolist` |
| team groups | 1 group (admin) | `POST /teams/{id}/teamgroups` |
| audit_logs | arise from real actions | automatic |
| changelog | arises from real edits | automatic |
| api_keys | the test user's own key | automatic |

## What is NOT seeded (and why — honestly)

These categories have **no working API route** in eLabFTW 5.6 and/or only
arise from real usage. They are deliberately not faked:

| Category | Why not seeded |
|---|---|
| links (experiments_links) | `POST .../experiments_links` → 500; `PATCH {"experiments_links": [...]}` → 400 "Invalid update target" (API bug in 5.6) |
| containers / storage assignment | `POST .../containers` → 500 "Column action cannot be null" |
| compounds_links | same 500 |
| request_actions | same 500 (action column null) |
| favorites / pins | no API route (UI only) |
| notifications | only arise from real events (e.g. another user commenting) |
| authfail | only from real failed logins |
| bookings / events | need a bookable item + real scheduler flow |
| procurement requests | admin/UI flow only |

If you need those categories for a demo, create them **in the UI** (as the
test user) — the export will pick them up, since it reads the real database.
The point of this script is that everything it *can* create via the API is
created via the API, and the rest is not pretended.
