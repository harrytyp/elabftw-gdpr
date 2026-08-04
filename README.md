# eLabFTW GDPR disclosure tooling

Tooling to answer GDPR data subject access requests (Art. 15) for an
[eLabFTW](https://www.elabftw.net/) instance - using only a sysadmin API
key, plus one small SQL file for the data the API does not expose.

Verified against a live eLabFTW instance (5.x) with a sysadmin key.

## Quickstart

One command - works on Linux, macOS and Windows:

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

## Commands

| Command | Purpose |
|---|---|
| `gdpr.py` (default: `all`) | export + report for the configured users |
| `gdpr.py export` | API export only |
| `gdpr.py report` | build report package from existing exports |
| `gdpr.py users` | list users visible to the sysadmin key |
| `gdpr.py status` | show what is in `output/` (exports + PDF/ZIP per user) |
| `gdpr.py config show` | show config (never the key) |
| `gdpr.py config set userid 75,82` | update user IDs in the env file |

Shared options: `--dry-run` (count only), `--no-files` (skip file downloads),
`--users 75,82` (override user IDs), `--json` (machine-readable output),
`--env-file PATH` (different credentials file), `--no-color`.

Examples:

```bash
./gdpr.py --dry-run                  # count only, write nothing
./gdpr.py export --no-files          # metadata only (fast, small)
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
- uploads: metadata and file contents (original file names)
- HTML explorer with thumbnails, PDF disclosure letter, ZIP archive

**Not covered by the API** (DB/CLI only, see `gdpr_cli.sql`): audit_logs,
authfail, changelog (structured), other users' api_keys/exports/todolist/
unfinished_steps/favtags/pins/sig_keys, exclusive_edit_mode, lockout_devices.
Detailed mapping: [docs/api-vs-cli.md](docs/api-vs-cli.md)

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
- For very large archives: use `--no-files` and provide files separately.
- Not legal advice - involve a DPO/lawyer in dispute cases.
