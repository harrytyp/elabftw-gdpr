-- ============================================================================
-- eLabFTW — DSGVO Art. 15 Auskunft: CLI/DB-Teil (ergaenzt gdpr_export.py)
-- ============================================================================
-- Ausfuehren mit User-ID des Anfragenden:
--   docker exec -it elabftw elabctl mysql -e "SET @uid = 42; SOURCE gdpr_cli.sql;"
--   oder in phpMyAdmin / MySQL-Client: @uid anpassen und Skript ausfuehren.
--
-- Deckt NUR die Daten ab, die per API NICHT erreichbar sind (self-scoped
-- oder ohne API-Route). Alles andere liefert gdpr_export.py.
--
-- ACHTUNG bei der Weitergabe (Art. 15(4) DSGVO):
--   * body/Spalten enthalten oft Daten DRITTER -> vor Versand schwärzen
--   * sig_keys.privkey, api_keys.hash, users.password_hash/mfa_secret/token
--     NIEMALS exportieren (nur Metadaten/Kategorie nennen)
-- ============================================================================

SET @uid = 42;

-- 1) Audit-Trail: Aktionen, die der User ausgelöst oder empfangen hat
SELECT created_at, category, requester_userid, target_userid, body
  FROM audit_logs
 WHERE requester_userid = @uid OR target_userid = @uid
 ORDER BY created_at;

-- 2) Fehlgeschlagene Logins (authfail)
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

-- 7) Signaturschluessel — nur Metadaten, privkey NIE exportieren!
SELECT id, created_at, last_used_at, state, type FROM sig_keys WHERE userid = @uid;

-- 8) ROR-Zuordnung + Favoriten/Pins (Praeferenzen)
SELECT ror, created_at FROM users2rors WHERE users_id = @uid;
SELECT tags_id FROM favtags2users WHERE users_id = @uid;
SELECT entity_id FROM pin_experiments2users WHERE users_id = @uid;
SELECT entity_id FROM pin_items2users WHERE users_id = @uid;
SELECT entity_id FROM pin_experiments_templates2users WHERE users_id = @uid;
SELECT entity_id FROM pin_items_types2users WHERE users_id = @uid;

-- 9) Nur als Kategorie nennen (kein Export):
--    users.password_hash, users.mfa_secret, users.token  -> "gehasht/verschluesselt gespeichert"
--    lockout_devices, exclusive_edit_mode                -> fluechtige Sperrzustaende
--    PHP-Sessions, Webserver-Logs (IPs)                  -> ausserhalb der DB
