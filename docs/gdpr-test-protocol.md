# GDPR test protocol — 2026-08-20

Live instance: `https://elabftw.researchmcp.duckdns.org` (elabftw/elabimg:stable, mysql:8.4)
Test subject: `max.mustermann@tum.de` (userid 2, team 1), 18 experiments + 75 items imported
API key: sysadmin key (admin@researchmcp.duckdns.org, userid 1) — **only** the API key, no session login

## Backend commands — what works / what does not (with evidence)

All DB checks run as (see `gdpr_cli.sql`):
```bash
PW=$(grep ELABFTW_DB_PASSWORD ~/unified-researchdata-mcp/.env | cut -d= -f2 | tr -d '\r\n')
docker exec -i elab-mysql mysql -uelabftw -p"$PW" elabftw < gdpr_cli.sql
```
⚠️ The old instruction `docker exec -it elabftw elabctl mysql …` is wrong: the `elabftw` image has no `elabctl`/`mysql` — fixed 2026-08-20.

| # | gdpr_cli.sql query | Table exists? | Works? | Rows for uid=2 | Notes |
|---|---|---|---|---|---|
| 1 | `audit_logs WHERE requester_userid=@uid OR target_userid=@uid` | ✅ | ✅ | 10 | categories 10/11/20/30/40/50/80. Art. 15(4): redact third-party names in `body`. |
| 2 | `authfail WHERE users_id=@uid` | ✅ (`users_id`, `attempt_time`, `device_token`) | ✅ | 2 | `device_token` must NOT be disclosed (spec correctly selects only `attempt_time`). |
| 3 | `*_changelog WHERE users_id=@uid` (exp+items+tmpl+itype) | ✅ | ✅ | 704+853+0+0=1557 | All rows have `users_id=2` (the importer). Content is `{old,new}` diffs; import rows keep original owner attribution via `experiments.userid=1` vs `users_id=2` — fine. |
| 4 | `api_keys WHERE userid=@uid` (no hash) | ✅ | ✅ | 1 | `hash` column exists but is **not** selected — correct. API `GET /users/2/api_keys` is self-scoped (returns only requester's own). |
| 5 | `exports WHERE requester_userid=@uid` | ✅ | ✅ | 0 | `format`/`long_name`/`filesize` verified. Self-scoped via API as well — DB is the only source. |
| 6 | `todolist WHERE userid=@uid` | ✅ | ✅ | 0 | `body`/`creation_time` correct. No API route for other users. |
| 7 | `sig_keys WHERE userid=@uid` | ✅ (`pubkey`,`privkey`,`created_at`,`last_used_at`,`state`,`type`,`userid`) | ✅ | 0 | SQL correctly omits `privkey`. Not reachable via API for other users. |
| 8a | `users2rors WHERE users_id=@uid` | ✅ | ✅ | 0 | ROR API `GET /users/{id}/rors` **does** work for other users, so this is a duplicate path — harmless. |
| 8b | `favtags2users WHERE users_id=@uid` | ✅ | ✅ | 0 | Self-scoped / no cross-user API — DB only. |
| 8c | `pin_*2users` (4 tables) | ✅ | ✅ | 0/0/0/0 | All four `pin_*` tables exist; pins have **no API route at all** — DB only. |
| — | Category-only: `users.password_hash`, `mfa_secret`, `token`, `api_keys.hash`, `sig_keys.privkey`, `lockout_devices`, `experiments_edit_mode` | ✅ | N/A | — | Correctly listed as “do not export” (rating 🟡 in `data-inventory.md`). Verified: `password_hash` set, `mfa_secret` empty for uid=2. |

**Result: all 16 tables referenced in `gdpr_cli.sql` exist and all SELECTs executed without error on mysql:8.4.** The only functional gap is the `uploads` archival layer (see below).

## API vs DB — remaining gaps

| Data | API (sysadmin key) | DB | In report? | What to do |
|---|---|---|---|---|
| audit_logs, authfail, changelog (structured), exports, todolist, sig_keys, pins/favtags, lockout/edit_mode | ❌ / self-scoped | ✅ | ⚠️ Mention only (report § “DB/CLI only”) — no raw rows | Operator must append `gdpr_cli.sql` output (redacted) before sending; `gdpr_report.py` does not embed it automatically. |
| uploads — 290 rows in DB, 119 active (`state=1`), 171 archived (`state=2`) | ✅ `GET /experiments/{id}/uploads` returns **only 119 active** (verified) | ✅ full | ⚠️ Partial — 171 archived uploads (state=2) are **not** in the API export. They remain in DB as soft-deleted; for a complete Art.15 package they should be listed (at least by name/timestamp) or noted as “171 archived uploads not included”. |
| notifications | ✅ `GET /users/{id}/notifications` | ✅ | ✅ | Works; 0 for test user. |
| bookings (`team_events`) | ✅ `GET /events?eventOwner=2` | — | ✅ | 0 for test user; DB not needed. |
| files on disk | ✅ binary via `GET …/uploads/{id}?format=binary` (state=1 only) | — | ⚠️ Default is **metadata-only** since `042ff42` (`--with-files` opt-in). This matches the “list + metadata” requirement; full binaries on request. |
| webserver logs / IPs | outside DB | outside DB | ❌ | `data-inventory.md` §5: “IPs only in webserver logs” — operator must clarify retention per DPO. |

## What is still missing in the disclosure package

1. **`gdpr_cli.sql` output is not merged into the ZIP/PDF.** The HTML report flags it but does not contain it. For a one-click Art.15 package either (a) keep the two-step workflow (API ZIP + separate DB appendix) and **document it as mandatory**, or (b) add a `--db-appendix` hook that ingests a pre-run CSV.
2. **Archived uploads (state=2).** 171 rows for the test user are invisible in the export. Decision: list them (even without binaries) or explicitly declare exclusion in the PDF cover letter.
3. **Third-party redaction is manual.** `audit_logs.body` and changelog `content` leak other users’ names/IDs — no automated scrub. Keep warning prominent.
4. **Tmp / transient tables** (`lockout_devices`, `*_edit_mode`) are category-only — fine; no personal data lost.

## Recommendation

* Keep `--with-files` opt-in (current default is correct — “list + PII” without binaries).
* Fix the `gdpr_cli.sql` instruction (done) and mark status “tested 2026-08-20” (done).
* Decide on (2) above; if “include archived”, extend the export or document the exclusion.
* For a future `gdpr_report.py` iteration: add a placeholder section that is filled when a `gdpr_cli_*.csv` is dropped into `output/UserX/`.
