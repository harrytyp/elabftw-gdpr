# GDPR-Anfrage beantworten — Anleitung (zwei 1-Klick-Pipelines)

> Stand: 2026-08-20, verifiziert End-to-End gegen eine Live-Instanz
> (elabftw 5.6.12, mysql:8.4). Beide Pipelines erzeugen ein fertiges
> Auskunftspaket: `output/User<id>/index.html` (HTML-Explorer),
> `Disclosure_User<id>.pdf` (Art.-15-Brief) und
> `gdpr_disclosure_User<id>.zip` (alles zusammen).

Für eine DSGVO-Auskunft (Art. 15) gibt es zwei Wege — **einer reicht**:

| | A — API-Key | B — Datenbank (Shell) |
|---|---|---|
| Was | Schneller Export über die API | **Vollständiger** Export direkt aus MySQL |
| Auth | Sysadmin-API-Key | Kein API-Key (Server-/DB-Zugriff) |
| Umfang | Metadaten + aktive Uploads | **Alles**: auch archivierte Uploads (state=2), Audit-Trail, Authfails, Changelog, API-Keys, Export-Historie, Todolist, Sig-Keys, Favoriten |
| Transparenz | Roter Banner + `LIMITATIONS.md` im Paket | Kein Banner (vollständig) |
| Empfehlung | Kurztest, schnelle Übersicht | **Für die eigentliche Auskunft** |

---

## Vorbereitung (einmalig)

### Weg A — API-Key

```bash
# Ohne Installation (uv) oder installiert:
uvx elabftw-gdpr          # oder: pip install elabftw-gdpr; elab-gdpr
```

Beim ersten Start fragt das Tool nach:
- **Instanz-URL**, z. B. `https://elabftw.researchmcp.duckdns.org`
- **Sysadmin-API-Key** (in eLabFTW: Admin → API keys → neuen Key anlegen)
- **User-ID(s)** (oder leer lassen → Liste der User wird angezeigt)

Gespeichert wird in `elabftw.env` (chmod 600, gitignored — nie committen).

### Weg B — Datenbank/Shell

Auf dem Server mit Docker laufen lassen — **keine Installation nötig**,
kein API-Key, keine `.env`-Datei:

```bash
# Skripte vom Repo auf den Server holen (einmalig):
git clone https://github.com/harrytyp/elabftw-gdpr ~/elabftw-gdpr
cd ~/elabftw-gdpr

# Python-Abhängigkeiten (einmalig):
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Autodetect findet den MySQL-Container, das Compose-`.env` und den
Datenbank-Namen automatisch. Gibt es mehrere Kandidaten, fragt das Tool
nach — oder du überschreibst mit `--db-container <name>`,
`--db-env-file <pfad>`, `--db-name <name>`.

---

## Pro GDPR-Anfrage

### Weg A — 1 Klick (API-Key)

```bash
# Vollständiger Lauf (Export + Report) für User 42:
elab-gdpr --users 42

# Oder: erst schauen, welche User es gibt, dann wählen:
elab-gdpr users
elab-gdpr                      # ohne --users → interaktive Auswahl

# Optionen:
elab-gdpr --users 42 --dry-run       # nur zählen, nichts schreiben
elab-gdpr --users 42 --with-files    # zusätzlich Datei-Inhalte laden
elab-gdpr --users 42 --json          # Zusammenfassung als JSON (für Skripte)
```

**Ergebnis:** `output/User42/` mit HTML/PDF/ZIP. Im ZIP liegt
`LIMITATIONS.md` — **lies sie vor Versand**: sie listet, welche Daten nur
über die DB kommen (Audit-Trail, archivierte Uploads usw.). Für die
vollständige Auskunft Weg B nutzen oder die fehlenden Teile aus
`gdpr_cli.sql` ergänzen (redigieren nicht vergessen, Art. 15(4)).

### Weg B — 1 Klick (Datenbank/Shell, ohne API-Key)

```bash
# Vollständiger Lauf (Export + Report) für User 42, mit allen Dateien:
cd ~/elabftw-gdpr
./gdpr_db_full.sh --users 42 --with-files

# Kurzform (nur User-ID):
./gdpr_db_full.sh 42

# Interaktiv (Container → DB → User auswählen):
./gdpr_db_full.sh

# Optionen:
./gdpr_db_full.sh --users 42 --dry-run      # zählen
./gdpr_db_full.sh --users 42 --no-archived  # archivierte Uploads auslassen
./gdpr_db_full.sh --users 42 --json
./gdpr_db_full.sh users                      # User-Liste aus der DB
```

**Ergebnis:** `output/User42/` mit **allem**:
- alle Uploads (aktiv **und** archiviert, `state=2`), Dateien im
  `files/`-Ordner (nur mit `--with-files`)
- `db_appendix.json` (Audit-Trail, Authfails, Changelog, API-Keys,
  Export-Historie, Todolist, Sig-Keys, Favoriten, Buchungen) — im ZIP,
  im HTML als „DB appendix"-Sektion, im PDF erwähnt
- HTML/PDF/ZIP wie gehabt

---

## Vor dem Versand an die betroffene Person (Pflicht)

1. **Redigieren (Art. 15(4) GDPR):** Audit-Trail-Body, Changelog-Inhalte
   und geteilte Dokumente können Daten **Dritter** enthalten
   (Co-Autoren, Reviewer, Namen). Manuell schwärzen.
2. **Nicht weitergegeben werden** (stehen nur als Kategorie im PDF):
   `password_hash`, `mfa_secret`, `token`, `api_keys.hash`,
   `sig_keys.privkey` — bewusst nie exportiert.
3. **Frist:** Auskunft binnen 1 Monats (Art. 12(3) GDPR).

---

## Beide Pipelines — Parameter-Übersicht

| Parameter | A (`elab-gdpr`) | B (`elab-gdpr-db`) |
|---|---|---|
| `--users 42,7` | ✅ (interaktiv wenn fehlt) | ✅ (interaktiv wenn fehlt) |
| `--with-files` | ✅ (Datei-Inhalte laden) | ✅ (Dateien aus Volume kopieren) |
| `--dry-run` | ✅ | ✅ |
| `--json` | ✅ | ✅ |
| `--out-dir <pfad>` | ✅ | ✅ |
| `--env-file <pfad>` | ✅ | ✅ |
| `--no-archived` | — | ✅ (nur aktive Uploads) |
| `--db-container/--db-name/--db-env-file` | — | ✅ (Autodetect-Override) |
| Subcommand `users` | ✅ | ✅ |

Logging: jeder Lauf schreibt `output/gdpr.log` (Rechenschaft, Art. 5(2)).
