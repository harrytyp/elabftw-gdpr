#!/usr/bin/env bash
# eLabFTW GDPR disclosure - Unix wrapper around the cross-platform gdpr.py.
# Usage: ./gdpr.sh [--dry-run|--no-files]
exec python3 "$(dirname "$0")/gdpr.py" "$@"
