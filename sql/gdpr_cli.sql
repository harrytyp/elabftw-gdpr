-- ============================================================================
-- eLabFTW — GDPR Art. 15 disclosure: DB/CLI part (complements the API export)
-- ============================================================================
-- Run with the data subject's user ID:
--   docker exec -it elabftw elabctl mysql -e "SET @uid = 42; SOURCE gdpr_cli.sql;"
--   or in phpMyAdmin / a MySQL client (adjust @uid first).
--
-- Covers ONLY the data that is NOT reachable via the API (self-scoped or no
-- route). Everything else is delivered by the API export (gdpr-export).
--
-- CAUTION before sharing (Art. 15(4) GDPR):
--   * body/columns often contain THIRD-PARTY data -> redact before sending
--   * sig_keys.privkey, api_keys.hash, users.password_hash/mfa_secret/token
--     must NEVER be exported (state category only)
-- ============================================================================

SET @uid = 42;

-- 1) Audit trail: actions requested by or targeting the user
SELECT created_at, category, requester_userid, target_userid, body
  FROM audit_logs
 WHERE requester_userid = @uid OR target_userid = @uid
 ORDER BY created_at;

-- 2) Failed login attempts (authfail)
SELECT attempt_time FROM authfail WHERE users_id = @uid ORDER BY attempt_time;

-- 3) Changelog (change history) — entries by the user only
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

-- 4) API keys of the user (metadata only — hash is NOT selected!)
SELECT id, name, created_at, last_used_at, can_write, team
  FROM api_keys WHERE userid = @uid ORDER BY created_at;

-- 5) Export jobs of the user
SELECT id, created_at, state, format, long_name, filesize
  FROM exports WHERE requester_userid = @uid ORDER BY created_at;

-- 6) Todolist (private notes)
SELECT body, creation_time FROM todolist WHERE userid = @uid ORDER BY creation_time;

-- 7) Signing keys — metadata only, privkey NEVER exported!
SELECT id, created_at, last_used_at, state, type FROM sig_keys WHERE userid = @uid;

-- 8) ROR affiliation + favourites/pins (preferences)
SELECT ror, created_at FROM users2rors WHERE users_id = @uid;
SELECT tags_id FROM favtags2users WHERE users_id = @uid;
SELECT entity_id FROM pin_experiments2users WHERE users_id = @uid;
SELECT entity_id FROM pin_items2users WHERE users_id = @uid;
SELECT entity_id FROM pin_experiments_templates2users WHERE users_id = @uid;
SELECT entity_id FROM pin_items_types2users WHERE users_id = @uid;

-- 9) Category-only (no export):
--    users.password_hash, users.mfa_secret, users.token  -> "stored hashed/encrypted"
--    lockout_devices, exclusive_edit_mode                -> transient lock states
--    PHP sessions, webserver logs (IPs)                  -> outside the database
