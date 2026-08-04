# eLabFTW GDPR disclosure tooling

Tooling to answer GDPR data subject access requests (Art. 15) for an
[eLabFTW](https://www.elabftw.net/) instance - **using only a sysadmin API
key**, plus a small DB/CLI part for the data the API does not expose.

Verified against a live eLabFTW instance (5.x) with a sysadmin key.

## What it produces

For a target user:

| Output | Contents |
|---|---|
| `out/` | raw JSON export (account data, teams/roles, notifications, groups, procurement, bookings, all entities with comments/revisions/steps/tags/uploads + files) |
| `report/index.html` | **HTML explorer**: overview + one page per entry with metadata, content, comments, revisions (collapsible), upload gallery with thumbnails |
| `report/Disclosure_UserX.pdf` | disclosure letter: mandatory information (categories, purposes, retention), counts, rights notice |
| `dist/gdpr_disclosure_UserX.zip` | everything combined (HTML + PDF + raw data) |

## Pipeline

```
gdpr-export  →  out/           (API export, sysadmin key)
gdpr-report  →  report/ + dist/  (HTML explorer + PDF + ZIP archive)
sql/gdpr_cli.sql  →  DB extract  (only what the API does not cover)
```

Detailed mapping of what works via API and what does not:
[docs/api-vs-cli.md](docs/api-vs-cli.md)

## Quickstart

One command - works on Linux, macOS **and Windows**:

```bash
# Linux/macOS:
./gdpr.sh
# or explicitly:
python3 gdpr.py

# Windows (cmd or double-click gdpr.bat):
gdpr.bat
```

That is it. On first run the script sets up the Python environment (venv +
`pip install`) and asks for the instance URL, sysadmin API key and user ID
once (stored in `elabftw.env`, chmod 600, gitignored). Then it exports all
data and builds the report package:

```
HTML explorer: report/index.html   <- open in your browser
PDF letter:    report/Disclosure_UserX.pdf
ZIP archive:   dist/gdpr_disclosure_UserX.zip
```

Useful variants:

```bash
./gdpr.sh --dry-run      # only fetch and count, write nothing
./gdpr.sh --no-files     # skip upload file contents (small archives)
```

The DB-only part (audit trail, failed logins, ...) is documented in
[sql/gdpr_cli.sql](sql/gdpr_cli.sql) - run it once per request if you have
database access. Everything else is automated.

## Advanced usage

The two CLI entry points behind `gdpr.sh` can also be run directly:

```bash
.venv/bin/gdpr-export --dry-run      # export (see --help for options)
.venv/bin/gdpr-report                # build report package from out/
```

The HTML explorer opens in the browser (`report/index.html`) - no server needed.

## What the export covers

- Account data + teams/roles, ROR affiliations, request actions, notifications
- Group memberships, procurement requests, bookings
- All entities owned by the user (experiments, items, templates, item types -
  owner filter, including archived and soft-deleted) with comments, revisions,
  steps, tags, request actions
- Uploads: metadata **and** file contents (original file names)

**Not covered by the API** (DB/CLI only, see `sql/gdpr_cli.sql`): audit_logs,
authfail, changelog (structured), other users' api_keys/exports/todolist/
unfinished_steps/favtags/pins/sig_keys, exclusive_edit_mode, lockout_devices.

## Before sending the disclosure

See [docs/gdpr-legal.md](docs/gdpr-legal.md) - in short:

- **Verify identity:** reply to the registered email address of the account
- **Redact:** third-party content (co-authors, reviewer comments, names in
  audit logs) before sharing (Art. 15(4))
- **Never hand out:** password hash, MFA secret, tokens, API key hashes,
  signing private keys - state categories only
- **Deadline:** 1 month (Art. 12(3)), +2 months for complex cases
- The PDF is the summary; the HTML explorer + ELN/JSON is the detailed copy

## Project layout

```
elabftw-gdpr/
├── gdpr.py                  <- cross-platform entry point (Linux/macOS/Windows)
├── gdpr.sh                  <- Unix wrapper (./gdpr.sh)
├── gdpr.bat                 <- Windows wrapper (double-click)
├── README.md                <- this file
├── LICENSE                  <- MIT
├── pyproject.toml           <- package metadata + dependencies + CLI entry points
├── elabftw.env.example      <- credentials template (never commit the real one!)
├── src/elabftw_gdpr/
│   ├── __init__.py          <- package version
│   ├── export.py            <- API export (elabapy wrapper)
│   └── report.py            <- HTML explorer + PDF letter + ZIP archive
├── sql/
│   └── gdpr_cli.sql         <- DB part for the API gaps
└── docs/
    ├── data-inventory.md    <- what eLabFTW stores about a person
    ├── api-vs-cli.md        <- API endpoints vs. DB/CLI (with code evidence)
    └── gdpr-legal.md        <- Art. 15 framing, deadlines, sources
```

`out/`, `report/`, `dist/`, `.venv/` and `elabftw.env` are local
(gitignored) - the code is fully readable/runnable without instance access.

## Notes

- Tested against eLabFTW 5.x; the API key must belong to a **sysadmin**
  account (only sysadmins see all users and scope=3).
- Known elabapy pitfall: `send_req()` sends parameters as request body
  instead of query string by default - all query calls therefore use
  `param_name="params"`.
- For very large instances/archives: use `--no-files` and provide files
  separately.
- Not legal advice - involve a DPO/lawyer in dispute cases.
