#!/usr/bin/env bash
# gdpr_db_full.sh - 1-click wrapper for the DB full export (pipeline B).
#
# Usage (on the eLabFTW server, no API key, no env needed):
#   bash gdpr_db_full.sh --users 2,7 --dry-run --json
#   bash gdpr_db_full.sh --users 2 --with-files
#   bash gdpr_db_full.sh users
#   bash gdpr_db_full.sh                # interactive: container -> db -> user
#   bash gdpr_db_full.sh 2              # shorthand for --users 2
set -euo pipefail

# shorthand: single numeric/comma arg -> --users
if [[ $# -eq 1 && "$1" =~ ^[0-9,]+$ ]]; then
    set -- --users "$1"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$SCRIPT_DIR/gdpr_db_full.py" ]]; then
    exec python3 "$SCRIPT_DIR/gdpr_db_full.py" "$@"
else
    # installed as a package entry point
    exec elab-gdpr-db "$@"
fi
