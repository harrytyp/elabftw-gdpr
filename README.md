# eLabFTW DSGVO-Auskunfts-Tooling

Werkzeug zur Beantwortung von DSGVO-Auskunftsbegehren (Art. 15) für eine
[eLabFTW](https://www.elabftw.net/)-Instanz — **nur mit einem Sysadmin-API-Key**,
ergänzt um einen kleinen DB/CLI-Teil für die Daten, die die API nicht hergibt.

Verifiziert gegen eine echte eLabFTW-Instanz (5.x) mit Sysadmin-Key.

## Was es liefert

Für einen Ziel-User:

| Ausgabe | Inhalt |
|---|---|
| `out/` | Rohdaten als JSON (Stammdaten, Teams/Rollen, Notifications, Gruppen, Procurement, Bookings, alle Entries mit Kommentaren/Revisionen/Steps/Tags/Uploads + Dateien) |
| `report/index.html` | **HTML-Explorer**: Übersicht + eine Seite pro Entry mit Metadaten, Inhalt, Kommentaren, Revisionen (aufklappbar), Upload-Galerie mit Thumbnails |
| `report/Auskunft_UserX.pdf` | Auskunftsschreiben: Pflichtangaben (Kategorien, Zwecke, Speicherdauer), Mengenübersicht, Rechte-Hinweise |
| `gdpr_auskunft_UserX.zip` | alles zusammen (HTML + PDF + Rohdaten) |

## Ablauf

```
src/gdpr_export.py  →  out/           (API-Export, Sysadmin-Key)
src/gdpr_report.py  →  report/ + ZIP  (HTML-Explorer + PDF + Archiv)
sql/gdpr_cli.sql    →  DB-Auszug      (nur die Daten, die die API nicht liefert)
```

Detaillierte Einordnung, was per API geht und was nicht: [docs/api-vs-cli.md](docs/api-vs-cli.md)

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp elabftw.env.example elabftw.env
# Werte eintragen: Instanz-URL, Sysadmin-API-Key, User-ID des Anfragenden
chmod 600 elabftw.env
```

## Nutzung

```bash
# 1) Export (erst zählen, dann voll):
.venv/bin/python src/gdpr_export.py --dry-run
.venv/bin/python src/gdpr_export.py            # inkl. Upload-Dateien
.venv/bin/python src/gdpr_export.py --no-files # ohne Dateien (kleines Archiv)

# 2) Report bauen:
.venv/bin/python src/gdpr_report.py

# 3) DB-Teil (nur mit DB-Zugriff, z.B. elabctl mysql):
docker exec -it elabftw elabctl mysql -e "SET @uid = X; SOURCE sql/gdpr_cli.sql;"
```

Der HTML-Explorer öffnet sich im Browser (`report/index.html`) — kein Server nötig.

## Was der Export abdeckt

- Stammdaten + Teams/Rollen, RORs, Request-Actions, Notifications
- Gruppenmitgliedschaften, Procurement-Requests, Bookings
- Alle Entries (experiments, items, templates, items_types) des Users
  (Owner-Filter, inkl. archiviert und soft-gelöscht) mit Kommentaren,
  Revisionen, Steps, Tags, Request-Actions
- Uploads: Metadaten **und** Dateien (Original-Dateinamen)

**Nicht per API** (nur DB/CLI, siehe `sql/gdpr_cli.sql`): audit_logs, authfail,
changelog (strukturiert), api_keys/exports/todolist/unfinished_steps/favtags/
pins/sig_keys fremder User, exclusive_edit_mode, lockout_devices.

## Vor dem Versand an den Anfragenden

Siehe [docs/dsgvo-rechtliches.md](docs/dsgvo-rechtliches.md) — kurz:

- **Identität prüfen:** Antwort an die registrierte E-Mail-Adresse des Accounts
- **Schwärzen:** Anteile Dritter (Co-Autoren, Betreuer-Kommentare, Namen in
  Audit-Logs) vor Weitergabe entfernen (Art. 15(4))
- **Niemals aushändigen:** Passwort-Hash, MFA-Secret, Tokens, API-Key-Hashes,
  Signatur-Privatkeys — nur als Kategorie ausweisen
- **Frist:** 1 Monat (Art. 12(3)), +2 Monate bei Komplexität
- Das PDF ist die Zusammenfassung; der HTML-Explorer + ELN/JSON die Detailkopie

## Projektstruktur

```
elabftw-gdpr/
├── README.md                  ← diese Datei
├── requirements.txt           ← Python-Abhängigkeiten
├── elabftw.env.example        ← Vorlage für Zugangsdaten (nie committen!)
├── src/
│   ├── gdpr_export.py         ← API-Export (elabapy)
│   └── gdpr_report.py         ← HTML-Explorer + PDF + ZIP
├── sql/
│   └── gdpr_cli.sql           ← DB-Teil für die API-Lücken
└── docs/
    ├── datenbestand.md        ← was eLabFTW über eine Person speichert
    ├── api-vs-cli.md          ← API-Endpoints vs. DB/CLI (mit Code-Beleg)
    └── dsgvo-rechtliches.md   ← Art. 15-Einordnung, Fristen, Quellen
```

`out/`, `report/`, `*.zip`, `.venv/` und `elabftw.env` sind lokal
(gitignored) — der Code ist ohne Instanz-Zugang lauffähig/lesbar.

## Hinweise

- Getestet gegen eLabFTW 5.x; der API-Key muss zu einem **Sysadmin**-Account
  gehören (nur der sieht alle User und scope=3).
- Bekannte elabapy-Falle: `send_req()` schickt Parameter standardmäßig als
  Request-Body statt Query-String — alle Query-Aufrufe nutzen daher
  `param_name="params"`.
- Bei sehr großen Instanzen/Archiven: `--no-files` verwenden und Dateien
  separat bereitstellen.
- Keine Rechtsberatung — bei Streitfall DSB/Anwalt einbeziehen.
