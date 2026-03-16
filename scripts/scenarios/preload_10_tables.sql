-- Preload 100k rows per table.
-- Use deterministic values to reduce preload overhead vs random().
INSERT INTO t1 (id, ref_id, payload)
SELECT uuid_from_int(g), NULL, (g * 13) % 1000000
FROM generate_series(1, 100000) AS g;

INSERT INTO t2 (id, ref_id, payload)
SELECT uuid_from_int(g), uuid_from_int(((g - 1) % 100000) + 1), (g * 17) % 1000000
FROM generate_series(1, 100000) AS g;

INSERT INTO t3 (id, ref_id, payload)
SELECT uuid_from_int(g), uuid_from_int(((g - 1) % 100000) + 1), (g * 19) % 1000000
FROM generate_series(1, 100000) AS g;

INSERT INTO t4 (id, ref_id, payload)
SELECT uuid_from_int(g), uuid_from_int(((g - 1) % 100000) + 1), (g * 23) % 1000000
FROM generate_series(1, 100000) AS g;

INSERT INTO t5 (id, ref_id, payload)
SELECT uuid_from_int(g), uuid_from_int(((g - 1) % 100000) + 1), (g * 29) % 1000000
FROM generate_series(1, 100000) AS g;

INSERT INTO t6 (id, ref_id, payload)
SELECT uuid_from_int(g), uuid_from_int(((g - 1) % 100000) + 1), (g * 31) % 1000000
FROM generate_series(1, 100000) AS g;

INSERT INTO t7 (id, ref_id, payload)
SELECT uuid_from_int(g), uuid_from_int(((g - 1) % 100000) + 1), (g * 37) % 1000000
FROM generate_series(1, 100000) AS g;

INSERT INTO t8 (id, ref_id, payload)
SELECT uuid_from_int(g), uuid_from_int(((g - 1) % 100000) + 1), (g * 41) % 1000000
FROM generate_series(1, 100000) AS g;

INSERT INTO t9 (id, ref_id, payload)
SELECT uuid_from_int(g), uuid_from_int(((g - 1) % 100000) + 1), (g * 43) % 1000000
FROM generate_series(1, 100000) AS g;

INSERT INTO t10 (id, ref_id, payload)
SELECT uuid_from_int(g), uuid_from_int(((g - 1) % 100000) + 1), (g * 47) % 1000000
FROM generate_series(1, 100000) AS g;
