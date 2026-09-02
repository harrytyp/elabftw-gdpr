# eLabFTW GDPR Tool _(elabftw-gdpr)_

Answer GDPR data subject access requests (Art. 15) for [eLabFTW](https://www.elabftw.net/) with one command.

Two pipelines, one goal: a complete, auditable disclosure.

- **DB pipeline** (`elab-gdpr-db`): no API key needed. Reads everything directly from MySQL (including archived uploads, the audit trail, failed logins) and copies upload files from the docker volume. Use this for the actual disclosure.
- **API pipeline** (`elab-gdpr`): needs a sysadmin API key. Fast, good for a quick check, but not complete on its own (see [Usage](#usage)).

## Sample report

What you get for every request - generated from the dedicated GDPR test
user (`gdpr-test@example.org`, seeded via `tests/seed_test_data.py`), in
English and German. Click to open the real files:

<p align="center">
  <a href="sample/SAMPLE-DISCLOSURE.pdf">
    <img src="sample/previews/preview-letter.jpg" alt="Sample disclosure letter (PDF)" width="600" style="border: 1px solid #ddd; border-radius: 4px;">
  </a>
  <br>
  <a href="sample/SAMPLE-DISCLOSURE.pdf">Open the full letter (English, PDF)</a>
  ·
  <a href="sample/SAMPLE-DISCLOSURE-DE.pdf">Zum Brief auf Deutsch (PDF)</a>
</p>

<p align="center">
  <a href="https://harrytyp.github.io/elabftw-gdpr/sample/sample-report/User1/index.html">
    <img src="sample/previews/preview-html.png" alt="Sample disclosure HTML explorer" width="600" style="border: 1px solid #ddd; border-radius: 4px;">
  </a>
  <br>
  <a href="https://harrytyp.github.io/elabftw-gdpr/sample/sample-report/User1/index.html">Open the interactive HTML explorer (English)</a>
  ·
  <a href="https://harrytyp.github.io/elabftw-gdpr/sample/sample-report/User1-de/index.html">HTML-Explorer auf Deutsch</a>
</p>

The sample letters contain interactive form fields (controller identity,
Art. 4(7) GDPR / Art. 4 Nr. 7 DSGVO) that the operator fills in while
reviewing the letter before sending.

Every request produces three files in `output/User<id>/`:

- `index.html` - the disclosure explorer you read in a browser: user profile, all entries (experiments, items, templates), comments, steps, uploads, and every appendix section (audit trail, failed logins, changelog, API keys, exports, storage, compounds, notifications, entity links, third-party comments, name mentions)
- `Disclosure_User<id>.pdf` - the official Art. 15 disclosure letter (one page, ready to send after redaction)
- `gdpr_disclosure_User<id>.zip` - everything as a package

## Install and where to run it

The tool is a Python CLI. Where you run it depends on the pipeline:

| Pipeline | Where to run | Requirements |
|---|---|---|
| **API** (`elab-gdpr`) | Any machine with Python 3.10+ (your laptop, a VM, anywhere with network access to eLabFTW) | eLabFTW URL + sysadmin API key |
| **DB** (`elab-gdpr-db`) | **On the eLabFTW server itself**, in the host shell (not inside the MySQL container, not in the web UI) | Shell access to the server + `docker` (it auto-detects the MySQL container) |

```bash
# Install (default branch = latest code):
pip install git+https://github.com/harrytyp/elabftw-gdpr
```

Then use the commands below. No installation is needed on the eLabFTW server:
clone the repo there and run `./gdpr_db_full.sh` (see [Usage](#usage)).

## Usage

Both pipelines share the same options. `--users 75,82` selects users
(comma-separated IDs; interactive pick if omitted), `--with-files` downloads
file contents (default: metadata only), `--dry-run` counts without writing,
`--out-dir <path>` sets the output location, `--lang <code>` selects the
report language (default: English).

### Report language (i18n)

The HTML explorer and the PDF disclosure letter are fully translated.
Supported languages: `en` (default) and `de`. The report UI (headings,
tables, appendix sections, the PDF letter with all GDPR article references)
is translated; the underlying data (entity titles, comments, audit-log
bodies) is user content and is deliberately never translated.

```bash
# English (default) - same as before
elab-gdpr --users 42

# German disclosure letter + HTML explorer
elab-gdpr --users 42 --lang de
elab-gdpr report --users 42 --lang de          # rebuild report from an export

# 'auto' reads the data subject's eLabFTW UI language (users.lang) and maps
# it to the closest supported report language (e.g. de_DE -> de, en_GB -> en);
# unknown/missing falls back to English
elab-gdpr --users 42 --lang auto
```

The DB pipeline does the same in one command (export + report):

```bash
# DB export + German report package in one go:
./gdpr_db_full.sh --users 42 --lang de

# or export first, then build the report from output/ at any time:
elab-gdpr-db --users 42
elab-gdpr report --out-dir output --users 42 --lang de
python3 scripts/gdpr_report.py --out-dir output --user 42 --lang de
```

The DB pipeline writes the user's `lang` into the export manifest, so
`--lang auto` works there too. Dates are formatted per language
(`de` → `DD.MM.YYYY`); the PDF letter keeps using its built-in font for
languages without special characters, and falls back to a TTF font
(DejaVu/Liberation) for scripts outside cp1252 (e.g. Polish, Czech) when one
is installed.

The generated PDF letters contain interactive form fields for the controller
identity (Art. 4(7) GDPR / Art. 4 Nr. 7 DSGVO). Fill them in while reviewing
the letter before sending - the operator data is not stored in eLabFTW.

### API pipeline - quick check, needs a sysadmin API key

```bash
elab-gdpr users                     # find the user ID
elab-gdpr --users 42                # export + report (1 click)
elab-gdpr --users 42 --with-files   # also download file contents
elab-gdpr --users 42 --lang de      # German export + report
```

First run asks for the instance URL and the API key once (stored in
`elabftw.env`, chmod 600, gitignored). The API package contains a red banner
and `LIMITATIONS.md` listing what is missing.

### DB pipeline - complete disclosure, no API key

```bash
# One-time setup on the eLabFTW server (host shell):
git clone https://github.com/harrytyp/elabftw-gdpr && cd elabftw-gdpr
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Per request (1 click - export + report package in one):
./gdpr_db_full.sh --users 42 --with-files
./gdpr_db_full.sh --users 42 --with-files --lang de    # German report
./gdpr_db_full.sh --users 42 --lang auto               # user's eLabFTW language
```

The shell wrapper exports AND builds the report package (HTML explorer +
PDF letter + ZIP) in one go. `--lang` selects the report language
(`en` default, `de`, or `auto` for the user's eLabFTW language); without
`--lang` the report is English.

It auto-detects the MySQL container, the compose `.env` and the database
name; if several candidates exist it asks (recursive). Override with
`--db-container <name>`, `--db-env-file <path>`, `--db-name <name>`.

### What each pipeline covers

| Data | API | DB |
|---|---|---|
| Account data, teams, entities (experiments, items, templates, item types) with comments, revisions, steps, tags | yes | yes |
| Upload metadata; file contents with `--with-files` | yes | yes |
| Upload binaries, incl. archived (state=2) | no | yes |
| Audit trail, failed logins, changelog, API keys, exports, todolist, sig keys, favorites, pins, team groups | no | yes |
| Storage history + assignments, compounds + links, template/type steps, signatures, request actions, procurement, notifications, entity links | no | yes |
| Third-party comments on the user's entries (data about the person from other people's content; redact before sending) | no | yes |

## Before sending the disclosure

1. **Redact third-party data (Art. 15(4)):** audit trail bodies, changelog
   content and shared documents may contain other people's names
   (co-authors, reviewers). Manually black them out.
2. **Never hand out:** password hashes, MFA secrets, reset tokens, API key
   hashes, signing private keys. These are only listed as categories in the
   PDF, by design.
3. **Deadline:** 1 month (Art. 12(3) GDPR), +2 months for complex cases.
4. **This tool is not legal proof.** It assembles data, not legal advice.
   Have a GDPR officer or DPO review the disclosure before sending it.

## Security

- The API key is stored in `elabftw.env` (chmod 600, gitignored); `config
  show` never prints it.
- Never commit or share `elabftw.env`, `output/` (contains personal data) or
  any export package.
- The DB pipeline reads the MySQL password from the compose `.env` on the
  server and never stores or logs it.
- Run log: `output/gdpr.log` (accountability, Art. 5(2)).

## Project layout

```
elabftw-gdpr/
├── gdpr.py                  <- CLI, API pipeline (installed as `elab-gdpr`)
├── gdpr_db_full.py          <- CLI, DB pipeline (installed as `elab-gdpr-db`)
├── gdpr_db_full.sh          <- 1-click server wrapper (DB pipeline)
├── gdpr.bat                 <- Windows wrapper (API pipeline)
├── scripts/                 <- internal modules (not run directly)
│   ├── gdpr_export.py       <- API export
│   ├── gdpr_report.py       <- report (HTML + PDF + ZIP)
│   ├── gdpr_detect.py       <- autodetect MySQL container / compose / DB
│   ├── gdpr_cli.sql         <- DB queries for API gaps
│   └── db-inventory.sql     <- complete DB schema reference
├── tests/                   <- test data seeding (see README-testing.md)
├── sample/                  <- sample report (builder, letter, previews)
│   └── previews/            <- embedded preview images (used in README)
├── pyproject.toml, requirements.txt, LICENSE
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
