# eLabFTW GDPR Tool

Answer GDPR data subject access requests (Art. 15) for [eLabFTW](https://www.elabftw.net/) with one command. Two pipelines:

- **API** (`elab-gdpr`) — needs a sysadmin API key. Fast. Shows what's missing.
- **DB** (`elab-gdpr-db`) — no API key needed. Reads everything directly from MySQL (including archived uploads and the audit trail) and copies upload files from the docker volume.

**Use the DB pipeline for the actual disclosure.** The API pipeline is fine for a quick check, but it is not complete on its own.

Verified against eLabFTW 5.6.12 / MySQL 8.4.

---

## 1. Install

```bash
# Run without installing (uv):
uvx elabftw-gdpr --users 2          # API pipeline
uvx elabftw-gdpr-db --users 2       # DB pipeline (no API key)

# Or install once:
pip install elabftw-gdpr
elab-gdpr --users 2
elab-gdpr-db --users 2 --with-files
```

Classic repo mode also works (Linux/macOS `./gdpr.py`, Windows `gdpr.bat`).

---

## 2. Answer a GDPR request

### Option A — API pipeline (needs API key)

```bash
elab-gdpr users                     # find the user ID
elab-gdpr --users 42                # export + report (1 click)
elab-gdpr --users 42 --with-files   # also download file contents
```

First run asks for the instance URL and the sysadmin API key once (stored in `elabftw.env`, chmod 600, gitignored). If you omit `--users`, it shows the user list to pick from.

Result in `output/User42/`: `index.html` (explorer), `Disclosure_User42.pdf` (letter), `gdpr_disclosure_User42.zip` (everything).

**Important:** the API package contains a red banner + `LIMITATIONS.md` listing what is missing (audit trail, archived uploads, ...). For a complete disclosure use Option B.

### Option B — DB pipeline (no API key, on the server)

```bash
# One-time setup on the eLabFTW server:
git clone https://github.com/harrytyp/elabftw-gdpr && cd elabftw-gdpr
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Per request (1 click):
./gdpr_db_full.sh --users 42 --with-files
# or: ./gdpr_db_full.sh 42
```

That's it — no API key, no env file. It auto-detects the MySQL container, the compose `.env` and the database name. If several candidates exist, it asks (recursive). Override with `--db-container <name>`, `--db-env-file <path>`, `--db-name <name>`.

Result in `output/User42/`: **everything** — all uploads (active + archived, state=2), the audit trail, failed logins, changelog, API keys, export history, todolist, sig keys, favorites, bookings. The HTML report has a "DB appendix" section, `db_appendix.json` is in the ZIP.

---

## 3. Before sending the disclosure (mandatory)

1. **Redact third-party data (Art. 15(4)):** audit trail bodies, changelog content and shared documents may contain other people's names (co-authors, reviewers). Manually black them out.
2. **Never hand out:** password hashes, MFA secrets, reset tokens, API key hashes, signing private keys. These are only listed as categories in the PDF — by design.
3. **Deadline:** 1 month (Art. 12(3) GDPR), +2 months for complex cases.

---

## 4. Commands

| Command | What it does |
|---|---|
| `gdpr.py` / `elab-gdpr` (default: `all`) | API export + report |
| `gdpr.py export` / `elab-gdpr export` | API export only |
| `gdpr.py report` / `elab-gdpr report` | build report from existing export |
| `gdpr.py users` / `elab-gdpr users` | list users visible to the key |
| `gdpr.py status` | show what is in `output/` |
| `gdpr.py config show/set` | show/update credentials (never shows the key) |
| `gdpr_db_full.py` / `elab-gdpr-db` | DB full export (no API key, same flags) |
| `gdpr_db_full.py users` / `elab-gdpr-db users` | list users from the database |
| `gdpr_db_full.sh 42` | 1-click shell wrapper (server) — shorthand for `--users 42` |

### Shared options (both pipelines)

`--users 75,82` (comma-separated IDs; interactive pick if omitted), `--with-files` (download file contents; default: metadata only), `--dry-run` (count only, write nothing), `--json` (summary as JSON for scripts), `--out-dir <path>`, `--env-file <path>`, `--no-color`.

### DB pipeline extras

`--no-archived` (skip archived uploads, state=2), `--db-container <name>`, `--db-name <name>`, `--db-env-file <path>` (autodetect overrides).

---

## 5. What the export covers

Per user in `output/User<id>/`:

- account data, teams/roles, ROR affiliations, request actions, notifications
- group memberships, procurement requests, bookings
- all entities owned by the user (experiments, items, templates, item types — incl. archived and soft-deleted) with comments, revisions, steps, tags, request actions
- uploads: metadata (always), file contents with `--with-files`
- HTML explorer with thumbnails, PDF disclosure letter, ZIP archive
- **DB pipeline only:** audit_logs, authfail, changelog, api_keys, exports, todolist, sig_keys, favtags, pins, team groups, storage history + assignments, compounds + links, template/type steps, signatures (who signed/timestamped), request actions, procurement, notifications, entity links, archived uploads (state=2), and **third-party comments on the user's entries** (data about the person from other people's content — redact before sending!) — everything the API cannot see

The run log is `output/gdpr.log` (accountability, Art. 5(2)).

---

## 6. Notes

- The API key must belong to a **sysadmin** account (only sysadmins see all users and scope=3).
- Default is metadata only — `--with-files` includes file contents. Keeps the package small on large instances.
- `--json` is a summary for scripts, not an archive — the data package lives in `output/User<id>/`.
- Colored output auto-disables for pipes/cron and honors `NO_COLOR`.
- Windows without admin rights: the venv lives under `%LOCALAPPDATA%`, no elevation needed; UNC shares work via `pushd`; `PYTHONUTF8=1` handles umlauts.
- Not legal advice — involve a DPO/lawyer in dispute cases.

### Verifying every data category (test data)

`test_seed.sql` inserts one `GDPR-*` test record per data category (ROR,
team groups, tags/pins/favtags, storage, compounds, request actions,
procurement, notifications, todolist, exports, API keys, sig keys,
templates/types + steps, foreign-entry comments, name mentions, signatures)
so a dry-run or full export shows every appendix section with a non-zero
count. `test_cleanup.sql` removes exactly those records again:

```bash
# after a full export, verify: dry-run shows every category > 0
python3 gdpr_db_full.py --users 2 --dry-run

# cleanup (seed again afterwards if you want to re-verify)
docker exec -i -e MYSQL_PWD="$PW" elab-mysql mysql -uelabftw elabftw < test_cleanup.sql
```

Only `GDPR-*`-prefixed records (and the exact dummy key values) are touched —
imported production data is never modified.

## Project layout

```
elabftw-gdpr/
├── gdpr.py                  <- CLI entry point (API pipeline)
├── gdpr.bat                 <- Windows wrapper
├── gdpr_export.py           <- API export module
├── gdpr_report.py           <- report module (HTML + PDF + ZIP)
├── gdpr_db_full.py          <- DB full export (pipeline B)
├── gdpr_db_full.sh          <- 1-click server wrapper
├── gdpr_detect.py           <- recursive autodetect (container/db/env)
├── gdpr_full.sql            <- complete DB inventory (reference)
├── gdpr_cli.sql             <- DB queries for the API gaps (manual fallback)
├── requirements.txt
├── elabftw.env.example      <- credentials template (never commit the real one)
├── pyproject.toml           <- pip/uv packaging (elab-gdpr, elab-gdpr-db)
├── README.md
└── LICENSE                  <- MIT
```

`output/`, `.venv/` and `elabftw.env` are local (gitignored).
