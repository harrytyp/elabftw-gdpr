# eLabFTW GDPR Tool _(elabftw-gdpr)_

Answer GDPR data subject access requests (Art. 15) for [eLabFTW](https://www.elabftw.net/) with one command.

Two pipelines, one goal: a complete, auditable disclosure.

- **DB pipeline** (`elab-gdpr-db`): no API key needed. Reads everything directly from MySQL (including archived uploads, the audit trail, failed logins) and copies upload files from the docker volume. **Use this for the actual disclosure.**
- **API pipeline** (`elab-gdpr`): needs a sysadmin API key. Fast, good for a quick check, but not complete on its own (see [What the export covers](#what-the-export-covers)).

Verified against eLabFTW 5.6.12 / MySQL 8.4.

**See what you get before running anything:**
[**Sample disclosure report**](https://harrytyp.github.io/elabftw-gdpr/sample-report/User1/index.html)
(a rendered web page, fully synthetic data).

## Table of Contents

- [Install](#install)
- [Usage](#usage)
- [Before sending the disclosure](#before-sending-the-disclosure-mandatory)
- [What the export covers](#what-the-export-covers)
- [Commands](#commands)
- [Sample report](#sample-report)
- [Security](#security)
- [Verifying every data category](#verifying-every-data-category)
- [Project layout](#project-layout)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Install

Latest release: [github.com/harrytyp/elabftw-gdpr/releases/latest](https://github.com/harrytyp/elabftw-gdpr/releases/latest)

```bash
# Install from the repo (default branch = always the latest code):
pip install git+https://github.com/harrytyp/elabftw-gdpr
elab-gdpr --users 2          # API pipeline
elab-gdpr-db --users 2 --with-files   # DB pipeline (no API key)

# Or run without installing (uv):
uvx --from git+https://github.com/harrytyp/elabftw-gdpr elab-gdpr --users 2

# Prefer a pinned version in production:
pip install git+https://github.com/harrytyp/elabftw-gdpr@v1.0.0
```

Pre-built wheels are attached to each [release](https://github.com/harrytyp/elabftw-gdpr/releases/latest)
(install URL: `.../releases/latest/download/elabftw_gdpr-<version>-py3-none-any.whl`).

Classic repo mode also works (Linux/macOS `./gdpr.py`, Windows `gdpr.bat`).

**Dependencies:** Python ≥ 3.10. On the eLabFTW server, the DB pipeline needs
`docker` access (it auto-detects the MySQL container). See
[requirements.txt](requirements.txt).

## Usage

### Option A: API pipeline (needs API key)

```bash
elab-gdpr users                     # find the user ID
elab-gdpr --users 42                # export + report (1 click)
elab-gdpr --users 42 --with-files   # also download file contents
```

First run asks for the instance URL and the sysadmin API key once (stored in
`elabftw.env`, chmod 600, gitignored). If you omit `--users`, it shows the
user list to pick from.

Result in `output/User42/`: `index.html` (explorer),
`Disclosure_User42.pdf` (letter), `gdpr_disclosure_User42.zip` (everything).

**Important:** the API package contains a red banner + `LIMITATIONS.md`
listing what is missing (audit trail, archived uploads, ...). For a complete
disclosure use Option B.

### Option B: DB pipeline (no API key, on the server)

```bash
# One-time setup on the eLabFTW server:
git clone https://github.com/harrytyp/elabftw-gdpr && cd elabftw-gdpr
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Per request (1 click):
./gdpr_db_full.sh --users 42 --with-files
# or: ./gdpr_db_full.sh 42
```

That's it: no API key, no env file. It auto-detects the MySQL container, the
compose `.env` and the database name. If several candidates exist, it asks
(recursive). Override with `--db-container <name>`, `--db-env-file <path>`,
`--db-name <name>`.

Result in `output/User42/`: **everything**, including all uploads (active + archived,
state=2), the audit trail, failed logins, changelog, API keys, export
history, todolist, sig keys, favorites, bookings. The HTML report has a "DB
appendix" section, `db_appendix.json` is in the ZIP.

## Before sending the disclosure (mandatory)

1. **Redact third-party data (Art. 15(4)):** audit trail bodies, changelog
   content and shared documents may contain other people's names
   (co-authors, reviewers). Manually black them out.
2. **Never hand out:** password hashes, MFA secrets, reset tokens, API key
   hashes, signing private keys. These are only listed as categories in the
   PDF, by design.
3. **Deadline:** 1 month (Art. 12(3) GDPR), +2 months for complex cases.

## What the export covers

Per user in `output/User<id>/`:

- account data, teams/roles, ROR affiliations, request actions, notifications
- group memberships, procurement requests, bookings
- all entities owned by the user (experiments, items, templates, item types,
  incl. archived and soft-deleted) with comments, revisions, steps, tags,
  request actions
- uploads: metadata (always), file contents with `--with-files`
- HTML explorer with thumbnails, PDF disclosure letter, ZIP archive
- **DB pipeline only:** audit_logs, authfail, changelog, api_keys, exports,
  todolist, sig_keys, favtags, pins, team groups, storage history +
  assignments, compounds + links, template/type steps, signatures (who
  signed/timestamped), request actions, procurement, notifications, entity
  links, archived uploads (state=2), and **third-party comments on the
  user's entries** (data about the person from other people's content;
  redact before sending!). Everything the API cannot see

The run log is `output/gdpr.log` (accountability, Art. 5(2)).

## Commands

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
| `gdpr_db_full.sh 42` | 1-click shell wrapper (server), shorthand for `--users 42` |

### Shared options (both pipelines)

`--users 75,82` (comma-separated IDs; interactive pick if omitted),
`--with-files` (download file contents; default: metadata only), `--dry-run`
(count only, write nothing), `--json` (summary as JSON for scripts),
`--out-dir <path>`, `--env-file <path>`, `--no-color`.

### DB pipeline extras

`--no-archived` (skip archived uploads, state=2), `--db-container <name>`,
`--db-name <name>`, `--db-env-file <path>` (autodetect overrides).

## Sample report

See exactly what a disclosure looks like before running anything:

**➡️ [Open the sample disclosure report](https://harrytyp.github.io/elabftw-gdpr/sample-report/User1/index.html)**
(rendered web page, fully synthetic "Sample User" data, no real data anywhere)

It shows the complete package you get for every request:

- **`index.html`** - the disclosure explorer you read in a browser: user
  profile, all their entries (experiments, items, templates), comments,
  steps, uploads, and every appendix section (audit trail, failed logins,
  changelog, API keys, exports, storage, compounds, notifications, entity
  links, third-party comments, name mentions, ...)
- **`Disclosure_User<id>.pdf`** - the official Art. 15 disclosure letter
  (one page, ready to send after redaction)
- **`gdpr_disclosure_User<id>.zip`** - everything as a package

Rebuild the sample locally:

```bash
python3 docs/make_sample_report.py
# then open docs/sample-report/User1/index.html
```

## Security

- **Credentials:** the API key is stored in `elabftw.env` (chmod 600,
  gitignored). `config show` never prints the key.
- **Never commit or share:** `elabftw.env`, `output/` (contains personal
  data!), any export package.
- **Never hand out (Art. 32):** password hashes, MFA secrets, tokens, API
  key hashes, signing private keys; see [Before sending](#before-sending-the-disclosure-mandatory).
- The DB pipeline reads the MySQL password from the compose `.env` on the
  server and never stores or logs it.

## Verifying every data category

`tests/seed_test_data.py` creates **real** eLabFTW records via the instance's
own API (dedicated test user): experiments, items, templates, item types,
comments, steps, tags, uploads (real file), status/category, todolist, team
groups, so a dry-run or full export shows these categories with real data,
nothing faked:

```bash
ELAB_URL=https://eln.example.org \
ELAB_KEY=<sysadmin-key> ELAB_USER_KEY=<test-user-key> \
    python3 tests/seed_test_data.py
python3 gdpr_db_full.py --users <test-user-id> --dry-run
```

Categories with no working API route in eLabFTW 5.6 (links, containers,
request actions, favorites/pins, notifications, authfail, bookings) are
**documented, not faked**; see `tests/README-testing.md`. The script is
idempotent (cleans previous `GDPR *` entities first) and only touches the
test user's data.

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
├── tests/
│   ├── seed_test_data.py    <- create real test data via the API (no fakes)
│   └── README-testing.md    <- what is seeded / what needs real usage
├── docs/
│   ├── make_sample_report.py  <- build the synthetic sample disclosure
│   └── sample-report/         <- sample (rendered via GitHub Pages)
├── README.md
└── LICENSE                  <- MIT
```

`output/`, `.venv/`, `dist/` and `elabftw.env` are local (gitignored).

## Maintainers

- [@harrytyp](https://github.com/harrytyp), maintainer

## Contributing

Questions, bugs and ideas: [GitHub issues](https://github.com/harrytyp/elabftw-gdpr/issues).

Pull requests are welcome. For anything touching the export format or the
GDPR text, please open an issue first to discuss. This tool produces legal
documents and changes to the disclosure content should be deliberate.

## License

[MIT](LICENSE) © harrytyp
