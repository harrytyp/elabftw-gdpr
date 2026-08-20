-- ============================================================================
-- eLabFTW GDPR tool - test data cleanup (reverse of test_seed.sql)
-- ============================================================================
-- Removes every GDPR-* test record and resets the signature on entry 1.
-- Run after verification:
--
--   docker exec -i -e MYSQL_PWD="$PW" elab-mysql mysql -uelabftw elabftw < test_cleanup.sql
--
-- Only records with the GDPR prefix (or the exact dummy values) are removed -
-- imported production test data stays untouched.
-- ============================================================================

-- foreign entry + its comments (owned by user 1)
DELETE FROM experiments_comments WHERE comment LIKE 'GDPR%';
DELETE FROM experiments WHERE title = 'GDPR-Foreign-Exp';

-- template + type + their steps/comments
DELETE FROM experiments_templates_comments WHERE comment LIKE 'GDPR%';
DELETE FROM experiments_templates_steps WHERE body LIKE 'GDPR%';
DELETE FROM experiments_templates WHERE title LIKE 'GDPR%';
DELETE FROM items_types_steps WHERE body LIKE 'GDPR%';
DELETE FROM items_types WHERE title LIKE 'GDPR%';

-- keys (dummy values - the tool never exports the hashes/private keys anyway)
DELETE FROM api_keys WHERE name = 'GDPR-test-key';
DELETE FROM sig_keys WHERE pubkey = 'PUBKEY-DUMMY';

-- account-level records
DELETE FROM exports WHERE long_name = 'GDPR-export.zip';
DELETE FROM todolist WHERE body = 'GDPR-todo-item';
DELETE FROM notifications WHERE body LIKE '%GDPR%';
DELETE FROM procurement_requests WHERE body = 'GDPR-procurement-test';
DELETE FROM experiments_request_actions WHERE action = 1 AND target_userid = 2 AND entity_id = 1;

-- compounds + links
DELETE FROM compounds2experiments WHERE entity_id = 1;
DELETE FROM compounds WHERE name LIKE 'GDPR%';

-- storage + history + assignment
DELETE FROM containers2items WHERE item_id = 1 AND qty_unit = 'box';
DELETE FROM storage_units_history WHERE users_id = 2;
DELETE FROM storage_units WHERE name LIKE 'GDPR%';

-- pins / favtags / tags / groups / ror
DELETE FROM pin_experiments2users WHERE users_id = 2 AND entity_id = 1;
DELETE FROM pin_items2users WHERE users_id = 2 AND entity_id = 1;
DELETE FROM favtags2users WHERE users_id = 2;
DELETE FROM tags WHERE tag = 'GDPR-tag';
DELETE FROM users2team_groups WHERE userid = 2;
DELETE FROM team_groups WHERE name = 'GDPR-TestGroup';
DELETE FROM users2rors WHERE users_id = 2 AND ror = '02nv7yv05';

-- reset signature on entry 1
UPDATE experiments SET last_signed_by = NULL, timestampedby = NULL,
       signature_count = 0, timestamped = 0 WHERE id = 1;
