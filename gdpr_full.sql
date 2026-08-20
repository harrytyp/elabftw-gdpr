-- ============================================================================
-- eLabFTW - GDPR Art. 15 disclosure - FULL DB inventory (pipeline B)
-- ============================================================================
-- Complements/extends gdpr_cli.sql: also covers content tables that the API
-- would export (so the DB pipeline needs no API key at all), plus ALL uploads
-- (state 1 = active, state 2 = archived) which the API cannot see.
--
-- Run with the data subject's user ID:
--   SET @uid = 2;  (or -e "SET @uid = 2; SOURCE gdpr_full.sql;")
--
-- Schema verified 2026-08-20 on elabimg:stable 5.6.12 / mysql:8.4.
--   * pin_experiments/pin_items/team_event_users DO NOT EXIST in this version
--   * experiments_steps/items_steps/tags2entity have NO user column -> joined
--     via the user's entity IDs
--   * todolist uses creation_time (not created_at)
--   * comments/revisions use userid (not users_id)
--
-- CAUTION before sharing (Art. 15(4) GDPR):
--   * body/columns often contain THIRD-PARTY data -> redact before sending
--   * sig_keys.privkey, api_keys.hash, users.password_hash/mfa_secret/token
--     must NEVER be exported (state category only)
-- ============================================================================

SET @uid = 42;

-- entity IDs owned by the user (used by steps/tags joins below)
SET @my_exp = (SELECT GROUP_CONCAT(id) FROM experiments WHERE userid = @uid);
SET @my_items = (SELECT GROUP_CONCAT(id) FROM items WHERE userid = @uid);

-- ---------------------------------------------------------------------------
-- A) Identity
-- ---------------------------------------------------------------------------
-- users WITHOUT sensitive columns (password_hash, mfa_secret, token, ...)
SELECT userid, email, firstname, lastname, created_at, last_login,
       validated, is_sysadmin, lang, orcid, orgid
  FROM users WHERE userid = @uid;

SELECT users_id, teams_id, is_owner, is_admin, is_archived
  FROM users2teams WHERE users_id = @uid;

-- ---------------------------------------------------------------------------
-- B) Content owned by the user (superset of API scope=3)
-- ---------------------------------------------------------------------------
SELECT id, title, category, status, state, created_at, modified_at, date,
       custom_id, elabid, rating, timestamped, locked, team
  FROM experiments WHERE userid = @uid;
SELECT id, title, category, status, state, created_at, modified_at, date,
       custom_id, elabid, rating, is_bookable, is_procurable, team
  FROM items WHERE userid = @uid;
SELECT id, title, category, state, created_at, modified_at, team
  FROM experiments_templates WHERE userid = @uid;
SELECT id, title, category, state, created_at, modified_at, team
  FROM items_types WHERE userid = @uid;

-- comments / revisions (userid column) -- steps/tags have no owner, joined by entity
SELECT 'experiments_comments' AS src, id, item_id, userid, created_at, comment
  FROM experiments_comments WHERE userid = @uid
UNION ALL
SELECT 'items_comments', id, item_id, userid, created_at, comment
  FROM items_comments WHERE userid = @uid;

SELECT 'experiments_revisions' AS src, id, item_id, userid, created_at, body
  FROM experiments_revisions WHERE userid = @uid
UNION ALL
SELECT 'items_revisions', id, item_id, userid, created_at, body
  FROM items_revisions WHERE userid = @uid;

SELECT 'experiments_steps' AS src, id, item_id, body, finished, finished_time
  FROM experiments_steps
 WHERE item_id IN (SELECT id FROM experiments WHERE userid = @uid)
UNION ALL
SELECT 'items_steps', id, item_id, body, finished, finished_time
  FROM items_steps
 WHERE item_id IN (SELECT id FROM items WHERE userid = @uid);

SELECT * FROM tags2entity
 WHERE item_id IN (SELECT id FROM experiments WHERE userid = @uid)
    OR item_id IN (SELECT id FROM items WHERE userid = @uid);

-- ---------------------------------------------------------------------------
-- C) Uploads - ALL states (1 active, 2 archived) - files from volume separately
-- ---------------------------------------------------------------------------
SELECT id, real_name, long_name, comment, item_id, type, created_at,
       hash, hash_algorithm, filesize, state, storage, immutable
  FROM uploads WHERE userid = @uid ORDER BY created_at;

-- ---------------------------------------------------------------------------
-- D) DB-only gaps (gdpr_cli.sql sections 1-8, extended)
-- ---------------------------------------------------------------------------
-- 1) audit trail
SELECT created_at, category, requester_userid, target_userid, LEFT(body, 120) AS body
  FROM audit_logs
 WHERE requester_userid = @uid OR target_userid = @uid
 ORDER BY created_at;

-- 2) failed logins
SELECT attempt_time FROM authfail WHERE users_id = @uid ORDER BY attempt_time;

-- 3) changelog (4 tables)
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

-- 4) api keys (metadata only - hash NOT selected)
SELECT id, name, created_at, last_used_at, can_write, team
  FROM api_keys WHERE userid = @uid ORDER BY created_at;

-- 5) export jobs (metadata only - no hash)
SELECT id, created_at, state, format, long_name, filesize
  FROM exports WHERE requester_userid = @uid ORDER BY created_at;

-- 6) todolist (private notes)
SELECT id, creation_time, ordering, body FROM todolist WHERE userid = @uid;

-- 7) sig keys (privkey NOT selected)
SELECT id, created_at, last_used_at, state, type, pubkey FROM sig_keys WHERE userid = @uid;

-- 8) favorite tags
SELECT tags_id FROM favtags2users WHERE users_id = @uid;

-- ---------------------------------------------------------------------------
-- E) Events / bookings (team_events.userid = owner)
-- ---------------------------------------------------------------------------
SELECT id, title, start, end, team, experiment, item, created_at, modified_at
  FROM team_events WHERE userid = @uid;
