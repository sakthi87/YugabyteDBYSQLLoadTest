\set aid random(1, 100000)
\set delta random(-100, 100)
INSERT INTO account_log (account_id, delta)
VALUES (uuid_from_int(:aid), :delta);
