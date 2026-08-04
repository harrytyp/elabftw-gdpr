# Datenbestand: Was speichert eLabFTW über eine Person?

Inventur auf Basis des Datenbankschemas `src/sql/structure.sql` (Hauptbranch,
75 Tabellen) und der REST-API-Schemas. Ampel für die Art.-15-Auskunft:

- ✅ = gehört in die Auskunft (Kopie)
- 🟡 = nur als Kategorie/Metadatum ausweisen (Rohwert nicht aushändigen)
- ❌ = nicht in die Auskunft

## 1. Konto (`users`, `users2teams`, `users2rors`, `api_keys`)

| Daten | Ampel | Begründung |
|---|---|---|
| firstname, lastname, email, orcid, orgid | ✅ | Kern-Stammdaten |
| created_at, last_login, valid_until, auth_service, entrypoint, is_sysadmin | ✅ | Konto-Metadaten |
| Team-Zuordnung + Rollen (is_owner, is_admin, is_archived) | ✅ | in `users2teams` |
| ROR-Affiliation (`users2rors`) | ✅ | Org-Zuordnung |
| API-Keys: Name, created_at, last_used_at, can_write | ✅ | Metadaten; **hash ❌** |
| password_hash, password_modified_at, mfa_secret, token (Reset) | 🟡 | nur „gehasht/verschlüsselt gespeichert" nennen |
| Präferenzen (lang, theme, orderby, scopes, notif-\*, pdf_format, …) | 🟡 | als Kategorie zusammenfassen |

## 2. Vom Nutzer erzeugte Inhalte

| Tabelle | Ampel | Begründung |
|---|---|---|
| experiments, items, experiments_templates, items_types | ✅ | Titel, Body, Metadata, custom_id, category/status, created/modified, lastchangeby, lockedby, timestampedby, last_signed_by — **Dritt-Anteile schwärzen** |
| \*_comments | ✅ | eigene Kommentare + Kommentare anderer **über** die Person |
| \*_revisions | ✅ | eigene Versionen (body, userid) |
| \*_changelog | ✅ | Änderungshistorie (users_id, target, content) |
| uploads | ✅ | real_name (Originalname!), comment, created_at, userid + **Datei selbst**; hash/storage 🟡 |
| todolist | ✅ | private Notizen — wird gern vergessen |
| team_events (Bookings) | ✅ | Bucher + Zeitraum + Ressource |
| tags2entity, \*_steps, Link-Tabellen | ✅ | gehören zu den Entries |
| access_key (anonyme Share-Links) | 🟡 | Fakt „Link erzeugt" nennen — **Token ❌** |
| pin_\*2users, favtags2users | 🟡 | Präferenzen |

## 3. Nutzungs- und Interaktionsspuren

| Tabelle | Ampel | Begründung |
|---|---|---|
| notifications | ✅ | body, category, created_at, email_sent_at |
| exports | ✅ | Export-Historie (long_name, created_at, format) |
| audit_logs | ✅ | Einträge, wo die Person requester **oder** target ist; **Namen Dritter schwärzen** |
| \*_request_actions | ✅ | requester/target_userid + action |
| procurement_requests | ✅ | Bestellanfragen (requester_userid, body, qty) |
| authfail | ✅ | fehlgeschlagene Logins (Zeitpunkte); **device_token ❌** |
| sig_keys | 🟡 | „Signaturschlüssel vorhanden, zuletzt genutzt am …" — **privkey ❌** |
| lockout_devices, \*_edit_mode | 🟡 | flüchtige Sperrzustände |

## 4. Nicht personenbezogen (❌)

`config`, `teams`, `idps` + `idps_sources/certs/endpoints`, Status-/Kategorie-
Tabellen, `tags` (Team-Ebene), `compounds` + `compounds2*`, `instance2rors`,
`teams2rors`, reine Link-Tabellen (`experiments2items`, `items2items`, …).

## 5. Außerhalb der Datenbank (trotzdem relevant)

| Daten | Ampel | Hinweis |
|---|---|---|
| PHP-Session-Dateien | 🟡 | flüchtig, nur Kategorie |
| Upload-Dateien auf Disk/S3 | ✅ | über `uploads` abgedeckt |
| Webserver-Logs (nginx: IP-Adressen!) | 🟡 | **In der eLabFTW-DB gibt es keine IP-Spalten** — IPs liegen nur in Webserver-Logs; Speicherdauer klären |
| Backups (DB-Dump + Dateien) | 🟡 | Kategorie + Rotationsdauer |
| Timestamped PDFs | ✅ | liefern, als unveränderlich kennzeichnen |
