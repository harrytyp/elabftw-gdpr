# eLabFTW GDPR disclosure tooling

Tooling to answer GDPR data subject access requests (Art. 15) for an
[eLabFTW](https://www.elabftw.net/) instance - two 1-click pipelines:

- **Pipeline A (API)** - `elab-gdpr`: sysadmin API key, fast, with a clearly
  marked limitation banner for the data only the database knows.
- **Pipeline B (DB)** - `elab-gdpr-db`: no API key needed, reads everything
  directly from MySQL (including archived uploads and the audit trail) and
  copies the upload files from the docker volume.

Verified against a live eLabFTW instance (5.6.x, mysql:8.4).

## Quickstart

One command - no git clone needed, install via pip/uv:

```bash
# Run without installing (uv):
uvx elabftw-gdpr --users 2          # API pipeline
uvx elabftw-gdpr-db --users 2       # DB pipeline (no API key)

# Or install once:
pip install elabftw-gdpr
elab-gdpr --users 2                 # API
elab-gdpr-db --users 2 --with-files # DB, with all upload files
```

Classic repo mode still works on Linux, macOS and Windows:

```bash
# Linux/macOS:
./gdpr.py
# Windows (cmd or double-click gdpr.bat):
gdpr.bat
```

On first run the script sets up the Python environment (venv + `pip install`)
and asks for the instance URL, sysadmin API key and user ID(s) once
(stored in `elabftw.env`, chmod 600, gitignored). If no user ID is entered,
it shows the user list from the instance for selection. Then it exports all
data and builds the report package:

```
output/User75/index.html            <- HTML explorer (open in browser)
output/User75/Disclosure_User75.pdf
output/User75/gdpr_disclosure_User75.zip
output/gdpr.log                     <- run log (Art. 5(2) GDPR accountability)
```

### Two pipelines at a glance

| Pipeline | Command (1 click) | Auth | What you get |
|---|---|---|---|
| A - API | `elab-gdpr --users 2` | sysadmin API key | export + report, metadata + active uploads; red LIMITATIONS banner + `LIMITATIONS.md` for DB-only data |
| B - DB | `elab-gdpr-db --users 2` | **none** (server/DB access) | EVERYTHING: all uploads incl. archived (state=2), audit trail, authfail, changelog, api_keys, exports, todolist, sig_keys, favtags, bookings |

Pipeline B auto-detects the MySQL container, the compose/`.env` file and the
database name. If several candidates exist it asks you (recursive) - override
with `--db-container <name>`, `--db-env-file <path>`, `--db-name <name>`.
On the eLabFTW server itself no env file is needed at all: the credentials
are read from the stack's `.env`.

> **How-to für eine konkrete GDPR-Anfrage:** [docs/gdpr-request-howto.md](docs/gdpr-request-howto.md)
> — Schritt für Schritt für beide Pipelines, inkl. Redaktions-Pflicht.

## Commands

| Command | Purpose |
|---|---|
| `gdpr.py` (default: `all`) | export + report for the configured users (API) |
| `gdpr.py export` | API export only |
| `gdpr.py report` | build report package from existing exports |
| `gdpr.py users` | list users visible to the sysadmin key |
| `gdpr.py status` | show what is in `output/` (exports + PDF/ZIP per user) |
| `gdpr.py config show` | show config (never the key) |
| `gdpr.py config set userid 75,82` | update user IDs in the env file |
| `gdpr_db_full.py` / `elab-gdpr-db` | DB full export (no API key; same flags) |
| `gdpr_db_full.py users` / `elab-gdpr-db users` | list users from the database |
| `gdpr_db_full.sh 2` | 1-click shell wrapper (server) - shorthand for `--users 2` |

Shared options: `--dry-run` (count only), `--with-files` (also download file contents; default: metadata only),
`--users 75,82` (override user IDs), `--json` (machine-readable output),
`--env-file PATH` (different credentials file), `--no-color`.
DB pipeline adds: `--no-archived` (skip state=2 uploads), `--db-container`,
`--db-name`, `--db-env-file` (autodetect overrides).

Color output works in Windows CMD and PowerShell through `colorama`. It is
automatically disabled when stdout is redirected or piped, and can always be
disabled explicitly with `--no-color` or the `NO_COLOR` environment variable.
The Windows launcher uses `pushd`, so the repository also works directly from
an UNC path such as `\\server\\share\\elabftw-gdpr`. Its Python virtual
environment is kept locally under `%LOCALAPPDATA%` in that case.

### Windows without admin rights, on network shares

- **No admin rights needed:** the venv is created under `%LOCALAPPDATA%`
  (per-user, never on the share), so `pip install` works without elevation.
- **Python installation:** if the launcher `py` or `python` is missing,
  `gdpr.bat` shows instructions. Install Python from python.org and choose
  "Install Now" - this installs for the current user only, no admin rights.
  The `--version` probe skips the Microsoft Store app aliases that would
  otherwise open the Store instead of running Python.
- **Unicode:** `gdpr.bat` sets `PYTHONUTF8=1`, so umlauts and other non-ASCII
  characters work on German/cp1252 consoles without `UnicodeEncodeError`.
- **Network shares:** `pushd` maps the share to a temporary drive letter, so
  the tool runs directly from `\\server\\share\\...`. The share must be
  writable for `output/` and `elabftw.env`. If it is read-only, the log falls
  back to `%LOCALAPPDATA%` and you can export to a local folder instead:
  `gdpr.py all --out-dir C:\path\to\output`.
- **Colors:** on Windows 10+ consoles ANSI colors are enabled via colorama;
  on older Windows they stay disabled automatically.

After an API export, the tool prints the remaining DB/CLI steps and writes
`LIMITATIONS.md` into the package. The API export is not the complete
disclosure: audit logs, failed login attempts and some self-scoped metadata
require the separate `gdpr_cli.sql` workflow - or simply use Pipeline B
(`elab-gdpr-db`), which includes all of it in one go. See
[docs/api-vs-cli.md](docs/api-vs-cli.md) before sending the package. Review
and redact third-party data before disclosure.

The run log is `output/gdpr.log`. It documents the processing run for
accountability, but it is not the complete disclosure and may need to be
retrieved or supplemented through the relevant administrator or database
tooling.

> Do not use `--json` as an export archive. It is a summary intended for
> scripts and automation; the actual data package is written below
> `output/User<id>/`.


Examples:

```bash
./gdpr.py --dry-run                  # count only, write nothing
./gdpr.py --with-files               # also download file contents (slower, larger)
./gdpr.py export --users 75,82 --json
./gdpr.py report --user 75           # rebuild report for one user
./gdpr.py users                      # find user IDs
./gdpr.py status --json
```

Multiple users: put several IDs in `elabftw.env`
(`ELAB_USERID=75,82,130`) or pass `--users` - each user gets their own
folder under `output/`.

## What the export covers

Per user (in `output/User<id>/`):

- account data + teams/roles, ROR affiliations, request actions, notifications
- group memberships, procurement requests, bookings
- all entities owned by the user (experiments, items, templates, item types -
  owner filter, including archived and soft-deleted) with comments, revisions,
  steps, tags, request actions
- uploads: metadata (always) and file contents on request (`--with-files`, original file names)
- HTML explorer with thumbnails, PDF disclosure letter, ZIP archive

**Not covered by the API** (DB/CLI only, see `gdpr_cli.sql`): audit_logs,
authfail, changelog (structured), other users' api_keys/exports/todolist/
unfinished_steps/favtags/pins/sig_keys, exclusive_edit_mode, lockout_devices.
**All of these ARE covered by Pipeline B** (`elab-gdpr-db`).
Detailed mapping: [docs/api-vs-cli.md](docs/api-vs-cli.md)

The API export is not the complete disclosure by itself. The DB-only part
(audit trail, failed logins, self-scoped exports/todolists and related data)
is documented in [gdpr_cli.sql](gdpr_cli.sql) and
[docs/api-vs-cli.md](docs/api-vs-cli.md). Run that separate step once per
request if you have database access, then review and redact third-party data
before sending the disclosure. Or skip the extra step entirely: Pipeline B
(`elab-gdpr-db --users <id> --with-files`) produces the complete package in
one command, including archived uploads.

The run log is written to `output/gdpr.log`. It records the processing run for
accountability, but it is not itself the complete disclosure. If logs or the
DB-only data must be retrieved from another system, use the documented SQL/CLI
step and the relevant administrator tooling.

Everything else is automated.


## Tab completion (Linux/macOS, optional)

```bash
.venv/bin/pip install argcomplete
echo 'eval "$(register-python-argcomplete gdpr.py)"' >> ~/.bashrc
```

## Before sending the disclosure

See [docs/gdpr-legal.md](docs/gdpr-legal.md) - in short:

- **Verify identity:** reply to the registered email address of the account
- **Redact:** third-party content (co-authors, reviewer comments, names in
  audit logs) before sharing (Art. 15(4))
- **Never hand out:** password hash, MFA secret, tokens, API key hashes,
  signing private keys - state categories only
- **Deadline:** 1 month (Art. 12(3)), +2 months for complex cases
- The PDF is the summary; the HTML explorer + JSON is the detailed copy

## Project layout

```
elabftw-gdpr/
├── gdpr.py                  <- CLI entry point (cross-platform, subcommands)
├── gdpr.bat                 <- Windows wrapper (double-click)
├── gdpr_export.py           <- API export module
├── gdpr_report.py           <- report module (HTML explorer + PDF + ZIP)
├── gdpr_cli.sql             <- DB part for the API gaps
├── requirements.txt         <- Python dependencies
├── elabftw.env.example      <- credentials template (never commit the real one!)
├── README.md                <- this file
├── LICENSE                  <- MIT
├── .gitignore
└── docs/
    ├── data-inventory.md    <- what eLabFTW stores about a person
    ├── api-vs-cli.md        <- API endpoints vs. DB/CLI (with code evidence)
    └── gdpr-legal.md        <- Art. 15 framing, deadlines, sources
```

`output/`, `.venv/` and `elabftw.env` are local (gitignored) - the code is
fully readable/runnable without instance access.

## Notes

- Tested against eLabFTW 5.x; the API key must belong to a **sysadmin**
  account (only sysadmins see all users and scope=3).
- Known elabapy pitfall: `send_req()` sends parameters as request body
  instead of query string by default - all query calls therefore use
  `param_name="params"`.
- Colored output is auto-disabled for pipes/cron and honors `NO_COLOR`.
- Default is metadata only (upload file contents excluded); use `--with-files`
  to include them. For very large instances this keeps the package small.
- Not legal advice - involve a DPO/lawyer in dispute cases.
