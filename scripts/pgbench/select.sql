\set aid random(1, 100000)
SELECT balance FROM account WHERE id = uuid_from_int(:aid);
