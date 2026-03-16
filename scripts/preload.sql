-- Sample preload. Adjust row counts as needed.
INSERT INTO account (id, balance)
SELECT uuid_from_int(g), 1000
FROM generate_series(1, 100000) AS g;

INSERT INTO account_log (account_id, delta)
SELECT uuid_from_int(((g - 1) % 100000) + 1), ((g * 37) % 200) - 100
FROM generate_series(1, 200000) AS g;
