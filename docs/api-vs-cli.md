# API vs. CLI: Was geht mit dem Sysadmin-Key, was braucht DB-Zugriff?

Verifiziert gegen den eLabFTW-Quellcode (ApiEndpoint-Enum, Apiv2Controller,
getSubModel-Mapping, Models: ApiKeys/Exports/SigKeys/UserUploads/UserRequestActions/
Scheduler/TeamGroups) und die OpenAPI-Spec (doc.elabftw.net/api/v2/).

## ✅ Per Admin-API lösbar (Sysadmin-Key reicht)

| Datenblock | Endpoint |
|---|---|
| Stammdaten + Teams + Rollen | `GET /users/{id}` — alle Felder außer password_hash, mfa_secret, token, sig_privkey (werden im Code entfernt) |
| ROR-Zuordnung | `GET /users/{id}/rors` |
| Request-Actions auf ihn | `GET /users/{id}/request_actions` (filtert target_userid) |
| Notifications | `GET /users/{id}/notifications` |
| Gruppenmitgliedschaften | `GET /teams/{id}/teamgroups` (liefert Mitglieder mit Namen) |
| Entries + Inhalte | `GET /experiments?owner=X&scope=3&state=1,2,3` (+ items, experiments_templates, items_types), pro Entry: comments, revisions, steps, tags, uploads, request_actions |
| Bookings | `GET /events?eventOwner=X` |
| Procurement-Requests | `GET /teams/{id}/procurement_requests` (requester_userid filtern) |
| Entry als Archiv | `GET /experiments/{id}?format=eln|zip|pdf` |
| Changelog (Workaround) | keine eigene Route — aber `format=pdf&changelog=1` bettet die Änderungshistorie in den PDF-Export ein |
| Export-Jobs anstoßen | `POST /exports` |
| Instanz-/Team-Config, Reports | `GET /config`, `/teams`, `/instance`, `/reports` |

## 🔶 Self-Scoped-Falle — auch als Sysadmin nicht für fremde User

Diese Endpoints filtern hart auf `WHERE userid = requester` (den Key-Inhaber),
nicht auf das URL-Ziel — per Code verifiziert:

| Daten | Fundstelle |
|---|---|
| api_keys fremder User | `ApiKeys::readAll`: `WHERE ak.userid = :userid` (Requester) |
| exports fremder User | `Exports::readAll`: `WHERE requester_userid = requester` |
| todolist, unfinished_steps, favtags | self-scoped; **pins haben gar keine Route** |
| sig_keys fremder User | `SigKeys` wird mit Requester konstruiert (Privatkey bleibt unzugänglich — gewollt) |
| users/{id}/uploads | `UserUploads` „forces the use of the requester" |

→ Für die Auskunft über eine **andere** Person: diese 6 Punkte via `sql/gdpr_cli.sql`.

## ❌ Nur CLI/DB — keine API-Route existiert

- **audit_logs** (Audit-Trail) — Model existiert, keine Route im ApiEndpoint-Enum
- **authfail** (fehlgeschlagene Logins) — dito
- **changelog** als strukturierte Daten (nur PDF-Workaround, s.o.)
- **exclusive_edit_mode**, **lockout_devices** — keine Routen
- **PHP-Session-Dateien**, **Webserver-Logs** (IPs) — außerhalb der DB

## CLI-Teil: Die SQL-Befehle (`sql/gdpr_cli.sql`)

Die vollständigen Statements — sie zielen auf die Tabellen, die per API nicht
erreichbar sind. **Stand: gegen das Schema (`structure.sql`) geschrieben, aber
noch nicht gegen eine Live-DB getestet** (kein DB-Zugriff auf die Instanz).

Ausführen mit (User-ID vorher in der Datei anpassen, `SET @uid = X`):

```bash
docker exec -it elabftw elabctl mysql -e "SET @uid = 42; SOURCE sql/gdpr_cli.sql;"
```

```sql
-- 1) Audit-Trail: Aktionen, die der User ausgelöst oder empfangen hat
SELECT created_at, category, requester_userid, target_userid, body
  FROM audit_logs WHERE requester_userid = @uid OR target_userid = @uid
 ORDER BY created_at;

-- 2) Fehlgeschlagene Logins
SELECT attempt_time FROM authfail WHERE users_id = @uid ORDER BY attempt_time;

-- 3) Changelog (Änderungshistorie) — nur Einträge des Users
SELECT 'experiments' AS type, created_at, target, content
  FROM experiments_changelog WHERE users_id = @uid
UNION ALL
SELECT 'items', created_at, target, content
  FROM items_changelog WHERE users_id = @uid
UNION ALL
SELECT 'experiments_templates', created_at, target, content
  FROM experiments_templates_changelog WHERE users_id = @uid
UNION ALL
SELECT 'items_types', created_at, target, content
  FROM items_types_changelog WHERE users_id = @uid
ORDER BY created_at;

-- 4) API-Keys des Users (Metadaten — hash NICHT selektieren!)
SELECT id, name, created_at, last_used_at, can_write, team
  FROM api_keys WHERE userid = @uid ORDER BY created_at;

-- 5) Export-Jobs des Users
SELECT id, created_at, state, format, long_name, filesize
  FROM exports WHERE requester_userid = @uid ORDER BY created_at;

-- 6) Todolist (private Notizen)
SELECT body, creation_time FROM todolist WHERE userid = @uid ORDER BY creation_time;

-- 7) Signaturschlüssel — nur Metadaten, privkey NIE exportieren!
SELECT id, created_at, last_used_at, state, type FROM sig_keys WHERE userid = @uid;

-- 8) ROR-Zuordnung + Favoriten/Pins (Präferenzen)
SELECT ror, created_at FROM users2rors WHERE users_id = @uid;
SELECT tags_id FROM favtags2users WHERE users_id = @uid;
SELECT entity_id FROM pin_experiments2users WHERE users_id = @uid;
SELECT entity_id FROM pin_items2users WHERE users_id = @uid;
SELECT entity_id FROM pin_experiments_templates2users WHERE users_id = @uid;
SELECT entity_id FROM pin_items_types2users WHERE users_id = @uid;
```

Nicht per SQL exportieren (nur als Kategorie nennen): `users.password_hash`,
`users.mfa_secret`, `users.token`, `api_keys.hash`, `sig_keys.privkey` —
sowie `lockout_devices`/`exclusive_edit_mode` (flüchtige Sperrzustände).
