#!/usr/bin/env bash
# eLabFTW GDPR disclosure - one-command entry point.
#
# Runs everything: environment setup (first run), credential prompt (first
# run), API export and report generation (HTML + PDF + ZIP).
#
# Usage:
#   ./gdpr.sh             full run (export incl. files + report)
#   ./gdpr.sh --dry-run   only fetch and count, write nothing
#   ./gdpr.sh --no-files  export without upload file contents
#
# Extra arguments are passed through to the export command.
set -euo pipefail
cd "$(dirname "$0")"

# --- 1. Environment (first run: create venv + install package) ---------------
if [ ! -x .venv/bin/gdpr-export ]; then
    echo "[gdpr] First run - setting up Python environment..."
    python3 -m venv .venv
    .venv/bin/pip install --quiet -e .
fi

# --- 2. Credentials (first run: ask and store in elabftw.env) -----------------
if [ ! -f elabftw.env ]; then
    echo "[gdpr] First run - eLabFTW access credentials:"
    read -rp "  Instance URL (e.g. https://eln.example.org): " elab_url
    read -rp "  Sysadmin API key: " elab_key
    read -rp "  User ID of the data subject: " elab_userid
    printf 'ELAB_URL=%s\nELAB_KEY=%s\nELAB_USERID=%s\n' \
        "$elab_url" "$elab_key" "$elab_userid" > elabftw.env
    chmod 600 elabftw.env
    echo "[gdpr] Credentials saved to elabftw.env (600, gitignored)."
fi

# --- 3. Export -----------------------------------------------------------------
.venv/bin/gdpr-export "$@"

# --- 4. Report (skip after --dry-run, nothing to build) ------------------------
if [[ "$*" != *"--dry-run"* ]]; then
    .venv/bin/gdpr-report
fi

# --- 5. Result -----------------------------------------------------------------
echo ""
echo "[gdpr] Done."
echo "  HTML explorer: $(pwd)/report/index.html"
echo "  PDF letter:    $(pwd)/report/Disclosure_User*.pdf"
echo "  ZIP archive:   $(pwd)/dist/gdpr_disclosure_User*.zip"
