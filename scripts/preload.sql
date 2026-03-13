-- Sample preload. Adjust row counts as needed.
INSERT INTO account (id, balance)
SELECT g, 1000
FROM generate_series(1, 100000) AS g;

INSERT INTO account_log (account_id, delta)
SELECT (random() * 100000)::bigint + 1, (random() * 200)::bigint - 100
FROM generate_series(1, 200000);
