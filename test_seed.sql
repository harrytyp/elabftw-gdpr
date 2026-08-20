-- ============================================================================
-- eLabFTW GDPR tool - test data seed (all categories verifiable)
-- ============================================================================
-- Inserts one GDPR-* test record per data category so a dry-run / full export
-- shows every appendix section with a non-zero count. Run against the live DB:
--
--   docker exec -i -e MYSQL_PWD="$PW" elab-mysql mysql -uelabftw elabftw < test_seed.sql
--
-- Remove everything again with test_cleanup.sql. The GDPR- prefix marks all
-- records as test data. Real (imported) test content stays untouched.
--
-- NOTE: some columns are JSON or int enums - values match the 5.6.x schema.
-- ============================================================================

SET @uid = 2;  -- the test subject (max.mustermann@tum.de)

-- 1) ROR affiliation
INSERT INTO users2rors (users_id, ror, created_at)
VALUES (@uid, '02nv7yv05', NOW());

-- 2) team group + membership
INSERT INTO team_groups (name, team) VALUES ('GDPR-TestGroup', 1);
SET @grp = LAST_INSERT_ID();
INSERT INTO users2team_groups (groupid, userid) VALUES (@grp, @uid);

-- 3) tag + favorite tag + pins
INSERT INTO tags (tag, team) VALUES ('GDPR-tag', 1);
SET @tag = LAST_INSERT_ID();
INSERT INTO favtags2users (tags_id, users_id) VALUES (@tag, @uid);
INSERT INTO pin_experiments2users (entity_id, users_id) VALUES (1, @uid);
INSERT INTO pin_items2users (entity_id, users_id) VALUES (1, @uid);

-- 4) storage unit + assignment + movement history
INSERT INTO storage_units (name, parent_id) VALUES ('GDPR-Shelf-A', NULL);
SET @shelf = LAST_INSERT_ID();
INSERT INTO containers2items (item_id, storage_id, qty_stored, qty_unit, created_at, modified_at)
VALUES (1, @shelf, 3, 'box', NOW(), NOW());
INSERT INTO storage_units_history (storage_unit_id, users_id, old_parent_id, new_parent_id, created_at)
VALUES (@shelf, @uid, NULL, NULL, NOW());

-- 5) compound + link to own entry
INSERT INTO compounds (name, iupac_name, cas_number, userid, team, created_by, modified_by, created_at, modified_at, state)
VALUES ('GDPR-Compound-X', 'x-iupac', '77-88-9', @uid, 1, @uid, @uid, NOW(), NOW(), 1);
SET @comp = LAST_INSERT_ID();
INSERT INTO compounds2experiments (compound_id, entity_id, created_at, modified_at)
VALUES (@comp, 1, NOW(), NOW());

-- 6) request action targeting the user (action is int enum)
INSERT INTO experiments_request_actions (action, entity_id, requester_userid, target_userid, state, created_at)
VALUES (1, 1, 1, @uid, 1, NOW());

-- 7) procurement request by the user
INSERT INTO procurement_requests (body, entity_id, requester_userid, qty_ordered, qty_received, state, team, created_at)
VALUES ('GDPR-procurement-test', 1, @uid, 5, 0, 1, 1, NOW());

-- 8) notification (body is JSON, category is int)
INSERT INTO notifications (body, category, userid, is_ack, created_at, send_email)
VALUES ('{"message": "GDPR-notification-test"}', 1, @uid, 0, NOW(), 0);

-- 9) todolist item
INSERT INTO todolist (body, userid, ordering, creation_time)
VALUES ('GDPR-todo-item', @uid, 1, NOW());

-- 10) export job (all flags tinyint)
INSERT INTO exports (requester_userid, team, state, format, long_name, real_name, created_at, modified_at, hash, hash_algo, changelog, experiments, items, json, pdfa)
VALUES (@uid, 1, 1, 'eln', 'GDPR-export.zip', 'GDPR-export.zip', NOW(), NOW(), '', '', 0, 0, 0, 0, 0);

-- 11) API key (hash is a dummy - NEVER exported by the tool)
INSERT INTO api_keys (userid, name, hash, created_at, can_write, team)
VALUES (@uid, 'GDPR-test-key', 'dummy-hash-never-exported', NOW(), 1, 1);

-- 12) signing key (privkey dummy - NEVER exported by the tool; type is int)
INSERT INTO sig_keys (userid, type, privkey, pubkey, state, created_at)
VALUES (@uid, 1, 'PRIVATE-KEY-DUMMY', 'PUBKEY-DUMMY', 1, NOW());

-- 13) template + step + comment (can* are JSON objects)
INSERT INTO experiments_templates (userid, team, title, body, canread, canread_target, canwrite, canwrite_target, state, created_at, modified_at)
VALUES (@uid, 1, 'GDPR-Template-1', 'template body',
        '{"teams": [], "users": [], "teamgroups": []}',
        '{"teams": [], "users": [], "teamgroups": []}',
        '{"teams": [], "users": [], "teamgroups": []}',
        '{"teams": [], "users": [], "teamgroups": []}', 1, NOW(), NOW());
SET @tmpl = LAST_INSERT_ID();
INSERT INTO experiments_templates_steps (item_id, body, ordering) VALUES (@tmpl, 'GDPR template step', 1);
INSERT INTO experiments_templates_comments (item_id, userid, comment, created_at, modified_at, immutable)
VALUES (@tmpl, @uid, 'GDPR template comment', NOW(), NOW(), 0);

-- 14) item type + step (canbook is JSON)
INSERT INTO items_types (userid, team, title, body, canread, canread_target, canwrite, canwrite_target, canbook, state, created_at, modified_at)
VALUES (@uid, 1, 'GDPR-ItemType-1', 'itype body',
        '{"teams": [], "users": [], "teamgroups": []}',
        '{"teams": [], "users": [], "teamgroups": []}',
        '{"teams": [], "users": [], "teamgroups": []}',
        '{"teams": [], "users": [], "teamgroups": []}',
        '{"teams": [], "users": [], "teamgroups": []}', 1, NOW(), NOW());
SET @itype = LAST_INSERT_ID();
INSERT INTO items_types_steps (item_id, body, ordering) VALUES (@itype, 'GDPR itype step', 1);

-- 15) foreign entry (owned by user 1) + comments:
--     a) comment BY the user on a foreign entry -> comments_on_other_entries
--     b) comment by ANOTHER user mentioning the subject -> name_mentions
INSERT INTO experiments (userid, team, title, body, date, elabid, canread, canwrite, state, created_at, modified_at)
VALUES (1, 1, 'GDPR-Foreign-Exp', 'foreign body', '2026-08-20', 'gdpr-foreign-test',
        '{"teams": [], "users": [], "teamgroups": []}',
        '{"teams": [], "users": [], "teamgroups": []}', 1, NOW(), NOW());
SET @fexp = LAST_INSERT_ID();
INSERT INTO experiments_comments (item_id, userid, comment, created_at, modified_at, immutable)
VALUES (@fexp, @uid, 'GDPR user2 comment on foreign entry', NOW(), NOW(), 0);
INSERT INTO experiments_comments (item_id, userid, comment, created_at, modified_at, immutable)
VALUES (@fexp, 1, 'GDPR mention max mustermann on foreign entry', NOW(), NOW(), 0);

-- 16) third-party comment on the user's OWN entry (by another user)
INSERT INTO experiments_comments (item_id, userid, comment, created_at, modified_at, immutable)
VALUES (1, 1, 'GDPR comment by admin on user2 entry', NOW(), NOW(), 0);

-- 17) signature on own entry
UPDATE experiments SET last_signed_by=1, timestampedby=1, signature_count=1, timestamped=1 WHERE id=1;
