# Data inventory: What does eLabFTW store about a person?

Inventory based on the eLabFTW database schema (`structure.sql` in the eLabFTW
repository, main branch, 75 tables) and the REST API schemas. Traffic-light
rating for the Art. 15 disclosure:

- ✅ = include in the disclosure (copy)
- 🟡 = state as category/metadata only (do not hand out the raw value)
- ❌ = not part of the disclosure

## 1. Account (`users`, `users2teams`, `users2rors`, `api_keys`)

| Data | Rating | Rationale |
|---|---|---|
| firstname, lastname, email, orcid, orgid | ✅ | core identity data |
| created_at, last_login, valid_until, auth_service, entrypoint, is_sysadmin | ✅ | account metadata |
| team memberships + roles (is_owner, is_admin, is_archived) | ✅ | in `users2teams` |
| ROR affiliation (`users2rors`) | ✅ | organisation mapping |
| API keys: name, created_at, last_used_at, can_write | ✅ | metadata; **hash ❌** |
| password_hash, password_modified_at, mfa_secret, token (reset) | 🟡 | state "stored hashed/encrypted" only |
| preferences (lang, theme, orderby, scopes, notif-\*, pdf_format, …) | 🟡 | summarise as category |

## 2. User-created content

| Table | Rating | Rationale |
|---|---|---|
| experiments, items, experiments_templates, items_types | ✅ | title, body, metadata, custom_id, category/status, created/modified, lastchangeby, lockedby, timestampedby, last_signed_by - **redact third-party parts** |
| \*_comments | ✅ | own comments + comments by others **about** the person |
| \*_revisions | ✅ | own versions (body, userid) |
| \*_changelog | ✅ | change history (users_id, target, content) |
| uploads | ✅ | real_name (original file name!), comment, created_at, userid + **the file itself**; hash/storage 🟡 |
| todolist | ✅ | private notes - often forgotten |
| team_events (bookings) | ✅ | booker + time range + resource |
| tags2entity, \*_steps, link tables | ✅ | part of the entities |
| access_key (anonymous share links) | 🟡 | state "link created" - **token ❌** |
| pin_\*2users, favtags2users | 🟡 | preferences |

## 3. Usage and interaction traces

| Table | Rating | Rationale |
|---|---|---|
| notifications | ✅ | body, category, created_at, email_sent_at |
| exports | ✅ | export history (long_name, created_at, format) |
| audit_logs | ✅ | entries where the person is requester **or** target; **redact names of others** |
| \*_request_actions | ✅ | requester/target_userid + action |
| procurement_requests | ✅ | purchase requests (requester_userid, body, qty) |
| authfail | ✅ | failed logins (timestamps); **device_token ❌** |
| sig_keys | 🟡 | "signing key exists, last used at …" - **privkey ❌** |
| lockout_devices, \*_edit_mode | 🟡 | transient lock states |

## 4. Not personal data (❌)

`config`, `teams`, `idps` + `idps_sources/certs/endpoints`, status/category
tables, `tags` (team level), `compounds` + `compounds2*`, `instance2rors`,
`teams2rors`, pure link tables (`experiments2items`, `items2items`, …).

## 5. Outside the database (still relevant)

| Data | Rating | Note |
|---|---|---|
| PHP session files | 🟡 | transient, category only |
| upload files on disk/S3 | ✅ | covered via `uploads` |
| webserver logs (nginx: IP addresses!) | 🟡 | **the eLabFTW DB has no IP columns** - IPs only live in webserver logs; clarify retention |
| backups (DB dump + files) | 🟡 | category + rotation period |
| timestamped PDFs | ✅ | provide, mark as immutable |
