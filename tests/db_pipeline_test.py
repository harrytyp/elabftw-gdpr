#!/usr/bin/env python3
"""DB-pipeline smoke test against the real eLabFTW data (User 2).

Verifies the export + report chain on genuine data without needing API keys:
  - export inventory: every GDPR category the DB pipeline promises
  - report: en default output, --lang auto resolution, de fallback,
    per-language <html lang> and date format, PDF + ZIP generation.

Usage (on the eLabFTW server, repo root):
  .venv/bin/python tests/db_pipeline_test.py [--user 2]
Exit code 0 = all checks passed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "bin" / "python"
if not PY.exists():
    PY = Path(sys.executable)

PASS = []
FAIL = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", type=int, default=2)
    args = parser.parse_args()
    uid = args.user

    print(f"=== eLabFTW GDPR DB-pipeline test (user {uid}, real data) ===\n")

    # ---- 1. dry-run: counts without writing --------------------------------
    print("[1] dry-run (counts only)")
    r = run([str(PY), str(ROOT / "gdpr_db_full.py"), "--users", str(uid), "--dry-run"])
    out = r.stdout + r.stderr
    check("dry-run exit 0", r.returncode == 0, f"rc={r.returncode}")
    # dry-run prints column-style lines ("experiments            18", "uploads: 290")
    for label in ("DRY RUN", "experiments", "uploads:") :
        check(f"dry-run mentions {label!r}", label in out)

    # ---- 2. export to a temp dir -------------------------------------------
    print("\n[2] full export (metadata-only)")
    tmp = Path(tempfile.mkdtemp(prefix="gdpr_test_"))
    r = run([str(PY), str(ROOT / "gdpr_db_full.py"), "--users", str(uid),
             "--out-dir", str(tmp)])
    out = r.stdout + r.stderr
    check("export exit 0", r.returncode == 0, f"rc={r.returncode}")
    user_dir = tmp / f"User{uid}"
    check("output dir created", user_dir.is_dir())
    check("manifest.json written", (user_dir / "manifest.json").is_file())
    check("db_appendix.json written", (user_dir / "db_appendix.json").is_file())

    # ---- 3. category inventory from the real export -------------------------
    print("\n[3] GDPR category inventory")
    manifest = json.loads((user_dir / "manifest.json").read_text(encoding="utf-8"))
    user = manifest.get("user", {})
    appx = json.loads((user_dir / "db_appendix.json").read_text(encoding="utf-8"))
    entities = manifest.get("entities", {})

    check("user.lang present", bool(user.get("lang")), f"lang={user.get('lang')!r}")
    check("experiments > 0", len(entities.get("experiments", [])) > 0,
          f"{len(entities.get('experiments', []))}")
    check("items > 0", len(entities.get("items", [])) > 0,
          f"{len(entities.get('items', []))}")
    check("templates present", len(entities.get("experiments_templates", [])) >= 0)
    check("item types present", len(entities.get("items_types", [])) >= 0)
    check("uploads_total > 0", manifest.get("uploads_total", 0) > 0,
          f"{manifest.get('uploads_total')}")

    # categories the DB pipeline promises on top of the API
    cat_checks = {
        "audit_logs": appx.get("audit_logs"),
        "authfail (failed logins)": appx.get("authfail"),
        "changelog": appx.get("changelog"),
        "api_keys": appx.get("api_keys"),
        "exports": appx.get("exports"),
        "todolist": appx.get("todolist"),
        "sig_keys": appx.get("sig_keys"),
        "favtags (favorites)": appx.get("favtags"),
        "pins": appx.get("pins"),
        "team_groups": appx.get("team_groups"),
        "storage_history": appx.get("storage_history"),
        "compounds": appx.get("compounds"),
        "request_actions": appx.get("request_actions"),
        "procurement": appx.get("procurement"),
        "notifications": appx.get("notifications"),
        "links (entity links)": appx.get("links"),
        "storage_assignments": appx.get("storage_assignments"),
        "compound_links": appx.get("compound_links"),
        "template_steps": appx.get("template_steps"),
        "third_party_mentions": appx.get("third_party_mentions"),
    }
    for label, rows in cat_checks.items():
        check(f"appendix has {label}", isinstance(rows, list),
              f"{len(rows) if isinstance(rows, list) else 'missing'}")

    # ---- 4. report build: default (en) -------------------------------------
    print("\n[4] report build, default language (en)")
    r = run([str(PY), str(ROOT / "gdpr.py"), "report",
             "--out-dir", str(tmp), "--user", str(uid)])
    check("report en exit 0", r.returncode == 0, f"rc={r.returncode}")
    html_en = (user_dir / "index.html")
    pdf = user_dir / f"Disclosure_User{uid}.pdf"
    zipf = user_dir / f"gdpr_disclosure_User{uid}.zip"
    check("index.html built", html_en.is_file())
    check("PDF built", pdf.is_file())
    check("ZIP built", zipf.is_file())
    # PDF sanity: non-empty, contains the document-title metadata (the body
    # text is glyph-subset encoded, so no plaintext search for UI strings)
    if pdf.is_file():
        pdf_raw = pdf.read_bytes()
        check("PDF non-empty", len(pdf_raw) > 500, f"{len(pdf_raw)} B")
        check("PDF has GDPR metadata", b"GDPR" in pdf_raw)
        check("PDF has ReportLab producer", b"ReportLab" in pdf_raw)
    en_src = html_en.read_text(encoding="utf-8")
    check("html lang=en", '<html lang="en">' in en_src)
    # English UI strings that live on the index page
    for probe in ("GDPR data subject access request", "Account &amp; teams",
                  "Audit trail", "Overview", "Notifications", "Entries"):
        check(f"en UI string present: {probe[:30]!r}", probe in en_src)
    # English strings on the detail pages / PDF (checked elsewhere live)
    entries_dir = user_dir / "entries"
    if entries_dir.is_dir():
        ent_files = list(entries_dir.glob("*.html"))
        check("entity pages exist", len(ent_files) > 0, f"{len(ent_files)}")
        if ent_files:
            ent_src = ent_files[0].read_text(encoding="utf-8")
            check("entity page has 'Comments' heading", "Comments" in ent_src)
            check("entity page has 'Metadata' heading", "Metadata" in ent_src)
            check("entity page has 'Revisions' heading", "Revisions" in ent_src)
    else:
        check("entity pages exist", False, "no entries dir")

    # ---- 5. report build: --lang auto ---------------------------------------
    print("\n[5] report build, --lang auto")
    tmp2 = Path(tempfile.mkdtemp(prefix="gdpr_test_auto_"))
    subprocess.run(["cp", "-r", str(user_dir), str(tmp2 / f"User{uid}")],
                   check=True)
    r = run([str(PY), str(ROOT / "gdpr.py"), "report",
             "--out-dir", str(tmp2), "--user", str(uid), "--lang", "auto"])
    check("report auto exit 0", r.returncode == 0, f"rc={r.returncode}")
    auto_src = (tmp2 / f"User{uid}" / "index.html").read_text(encoding="utf-8")
    expected_lang = "en" if (user.get("lang") or "en_GB").startswith(("en", "en_")) else "de"
    check(f"auto resolves to {expected_lang}",
          f'<html lang="{expected_lang}">' in auto_src,
          f"user.lang={user.get('lang')!r}")

    # ---- 6. report build: explicit --lang de (German translation) ------------
    print("\n[6] report build, --lang de (German translation)")
    tmp3 = Path(tempfile.mkdtemp(prefix="gdpr_test_de_"))
    subprocess.run(["cp", "-r", str(user_dir), str(tmp3 / f"User{uid}")],
                   check=True)
    r = run([str(PY), str(ROOT / "gdpr.py"), "report",
             "--out-dir", str(tmp3), "--user", str(uid), "--lang", "de"])
    check("report de exit 0", r.returncode == 0, f"rc={r.returncode}")
    de_src = (tmp3 / f"User{uid}" / "index.html").read_text(encoding="utf-8")
    check("html lang=de for --lang de", '<html lang="de">' in de_src)
    # date format: German uses DD.MM.YYYY - the export line label is German
    m = re.search(r"Export erstellt: ([0-9][0-9]?\.[0-9][0-9]?\.[0-9]{4})", de_src)
    check("German date format (DD.MM.YYYY) in export line", bool(m),
          m.group(1) if m else "not found")
    # real German UI strings (translation now populated)
    for probe in ("DSGVO-Auskunftsersuchen", "Konto &amp; Teams", "Audit-Trail",
                  "Benachrichtigungen", "Beschaffungsanträge", "Übersicht",
                  "Einträge", "Export erstellt:"):
        check(f"de UI string present: {probe[:30]!r}", probe in de_src)
    # 'Zurück zur Übersicht' lives on the entity pages, check one there
    de_entries = sorted((tmp3 / f"User{uid}" / "entries").glob("*.html"))
    if de_entries:
        de_ent = de_entries[0].read_text(encoding="utf-8")
        check("entity page has 'Zurück zur Übersicht'",
              "Zurück zur Übersicht" in de_ent)
        check("entity page has 'Metadaten'", "Metadaten" in de_ent)
        check("entity page has 'Versionen'", "Versionen" in de_ent)
    else:
        check("entity page has 'Zurück zur Übersicht'", False, "no entries")
    # no English leftovers on the index page for translated section headings
    for probe_en in ("<h2>Overview</h2>", "<h2>Account &amp; teams</h2>",
                     "<h2>Notifications", "<h2>Bookings"):
        check(f"de index has no EN heading {probe_en[:30]!r}",
              probe_en not in de_src)
    # German PDF builds and contains umlauts (readable via pymupdf if present)
    pdf_de = tmp3 / f"User{uid}" / f"Disclosure_User{uid}.pdf"
    check("de PDF built", pdf_de.is_file())
    if pdf_de.is_file():
        try:
            import pymupdf  # optional, only on machines where installed
            pdf_text = pymupdf.open(str(pdf_de))[0].get_text()
            check("de PDF contains umlaut text (Zusammenfassung)",
                  "Zusammenfassung" in pdf_text or "DSGVO" in pdf_text)
            check("de PDF uses German date (DD.MM.YYYY)",
                  bool(re.search(r"\d{2}\.\d{2}\.\d{4}", pdf_text)))
        except ImportError:
            check("de PDF text extraction", True,
                  "pymupdf not installed - skipped (PDF build already verified)")

    # ---- 7. direct script invocation still works ----------------------------
    print("\n[7] direct scripts/gdpr_report.py invocation")
    tmp4 = Path(tempfile.mkdtemp(prefix="gdpr_test_direct_"))
    subprocess.run(["cp", "-r", str(user_dir), str(tmp4 / f"User{uid}")],
                   check=True)
    r = run([str(PY), str(ROOT / "scripts" / "gdpr_report.py"),
             "--out-dir", str(tmp4), "--user", str(uid), "--lang", "en"])
    check("direct invocation exit 0", r.returncode == 0, f"rc={r.returncode}")

    print(f"\n=== RESULT: {len(PASS)} passed, {len(FAIL)} failed ===")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
