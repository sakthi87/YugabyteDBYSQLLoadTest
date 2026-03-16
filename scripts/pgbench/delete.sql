\set aid random(1, 100000)
DELETE FROM account_log
WHERE id IN (
  SELECT id FROM account_log
  WHERE account_id = uuid_from_int(:aid)
  LIMIT 1
);
