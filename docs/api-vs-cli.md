# API vs. CLI: What works with the sysadmin key, what needs DB access?

Verified against the eLabFTW source code (ApiEndpoint enum, Apiv2Controller,
getSubModel mapping, Models: ApiKeys/Exports/SigKeys/UserUploads/
UserRequestActions/Scheduler/TeamGroups) and the OpenAPI spec
(doc.elabftw.net/api/v2/).

> **TL;DR:** Pipeline A (`elab-gdpr`, API key) covers the table below. For the
> 🔶 and ❌ rows use Pipeline B (`elab-gdpr-db`, no API key) - it reads all of
> them directly from MySQL, including archived uploads (state=2) and the audit
> trail. Since v1.0 both pipelines share the same CLI shape.

## ✅ Solvable via the admin API (sysadmin key is enough)

| Data | Endpoint |
|---|---|
| account data + teams + roles | `GET /users/{id}` - all fields except password_hash, mfa_secret, token, sig_privkey (removed in code) |
| ROR affiliation | `GET /users/{id}/rors` |
| request actions targeting the user | `GET /users/{id}/request_actions` (filters target_userid) |
| notifications | `GET /users/{id}/notifications` |
| group memberships | `GET /teams/{id}/teamgroups` (returns members with names) |
| entities + content | `GET /experiments?owner=X&scope=3&state=1,2,3` (+ items, experiments_templates, items_types); per entry: comments, revisions, steps, tags, uploads, request_actions |
| bookings | `GET /events?eventOwner=X` |
| procurement requests | `GET /teams/{id}/procurement_requests` (filter requester_userid) |
| entity as archive | `GET /experiments/{id}?format=eln\|zip\|pdf` |
| changelog (workaround) | no own route - but `format=pdf&changelog=1` embeds the change history into the PDF export |
| trigger export jobs | `POST /exports` |
| instance/team config, reports | `GET /config`, `/teams`, `/instance`, `/reports` |

## 🔶 Self-scoped trap - not readable for other users, even as sysadmin

These endpoints hard-filter on `WHERE userid = requester` (the key owner),
not on the URL target - verified in code:

| Data | Evidence |
|---|---|
| api_keys of other users | `ApiKeys::readAll`: `WHERE ak.userid = :userid` (requester) |
| exports of other users | `Exports::readAll`: `WHERE requester_userid = requester` |
| todolist, unfinished_steps, favtags | self-scoped; **pins have no route at all** |
| sig_keys of other users | `SigKeys` is constructed with the requester (private key stays inaccessible - intended) |
| users/{id}/uploads | `UserUploads` "forces the use of the requester" |

→ For a disclosure about a **different** person: these 6 items via `gdpr_cli.sql`.

## ❌ DB/CLI only - no API route exists

- **audit_logs** (audit trail) - model exists, no route in the ApiEndpoint enum
- **authfail** (failed logins) - same
- **changelog** as structured data (only the PDF workaround, see above)
- **exclusive_edit_mode**, **lockout_devices** - no routes
- **PHP session files**, **webserver logs** (IPs) - outside the database

## CLI part: the SQL statements (`gdpr_cli.sql`)

The full statements - they target the tables that are unreachable via the API.
**Status: tested 2026-08-20 against live elabftw/elabimg:stable + mysql:8.4 (user 2, 290 uploads, 1557 changelog rows) — all 16 tables/columns verified.**

Run with (adjust the user ID first, `SET @uid = X`):

```bash
docker exec -i elab-mysql mysql -uelabftw -p"$ELABFTW_DB_PASSWORD" elabftw < gdpr_cli.sql  # with: SET @uid = 42; on first line, or pass UID via shell
```

```sql
-- 1) Audit trail: actions requested by or targeting the user
SELECT created_at, category, requester_userid, target_userid, body
  FROM audit_logs WHERE requester_userid = @uid OR target_userid = @uid
 ORDER BY created_at;

-- 2) Failed login attempts
SELECT attempt_time FROM authfail WHERE users_id = @uid ORDER BY attempt_time;

-- 3) Changelog (change history) - entries by the user only
SELECT 'experiments' AS type, created_at, target, content
  FROM experiments_changelog WHERE users_id = @uid
UNION ALL
SELECT 'items', created_at, target, content
  FROM items_changelog WHERE users_id = @uid
UNION ALL
SELECT 'experiments_templates', created_at, target, content
  FROM experiments_templates_changelog WHERE users_id = @uid
UNION ALL
SELECT 'items_types', created_at, target, content
  FROM items_types_changelog WHERE users_id = @uid
ORDER BY created_at;

-- 4) API keys of the user (metadata only - hash is NOT selected!)
SELECT id, name, created_at, last_used_at, can_write, team
  FROM api_keys WHERE userid = @uid ORDER BY created_at;

-- 5) Export jobs of the user
SELECT id, created_at, state, format, long_name, filesize
  FROM exports WHERE requester_userid = @uid ORDER BY created_at;

-- 6) Todolist (private notes)
SELECT body, creation_time FROM todolist WHERE userid = @uid ORDER BY creation_time;

-- 7) Signing keys - metadata only, privkey NEVER exported!
SELECT id, created_at, last_used_at, state, type FROM sig_keys WHERE userid = @uid;

-- 8) ROR affiliation + favourites/pins (preferences)
SELECT ror, created_at FROM users2rors WHERE users_id = @uid;
SELECT tags_id FROM favtags2users WHERE users_id = @uid;
SELECT entity_id FROM pin_experiments2users WHERE users_id = @uid;
SELECT entity_id FROM pin_items2users WHERE users_id = @uid;
SELECT entity_id FROM pin_experiments_templates2users WHERE users_id = @uid;
SELECT entity_id FROM pin_items_types2users WHERE users_id = @uid;
```

Do not export via SQL (category only): `users.password_hash`,
`users.mfa_secret`, `users.token`, `api_keys.hash`, `sig_keys.privkey` -
as well as `lockout_devices`/`exclusive_edit_mode` (transient lock states).
