\set aid random(1, 100000)
\set delta random(-50, 50)
UPDATE account
SET balance = balance + :delta,
    updated_at = now()
WHERE id = :aid;
