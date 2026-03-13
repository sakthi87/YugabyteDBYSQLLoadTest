-- Preload 100k rows per table.
INSERT INTO t1 (ref_id, payload)
SELECT NULL, (random() * 1000000)::bigint
FROM generate_series(1, 100000);

INSERT INTO t2 (ref_id, payload)
SELECT (random() * 100000)::bigint + 1, (random() * 1000000)::bigint
FROM generate_series(1, 100000);

INSERT INTO t3 (ref_id, payload)
SELECT (random() * 100000)::bigint + 1, (random() * 1000000)::bigint
FROM generate_series(1, 100000);

INSERT INTO t4 (ref_id, payload)
SELECT (random() * 100000)::bigint + 1, (random() * 1000000)::bigint
FROM generate_series(1, 100000);

INSERT INTO t5 (ref_id, payload)
SELECT (random() * 100000)::bigint + 1, (random() * 1000000)::bigint
FROM generate_series(1, 100000);

INSERT INTO t6 (ref_id, payload)
SELECT (random() * 100000)::bigint + 1, (random() * 1000000)::bigint
FROM generate_series(1, 100000);

INSERT INTO t7 (ref_id, payload)
SELECT (random() * 100000)::bigint + 1, (random() * 1000000)::bigint
FROM generate_series(1, 100000);

INSERT INTO t8 (ref_id, payload)
SELECT (random() * 100000)::bigint + 1, (random() * 1000000)::bigint
FROM generate_series(1, 100000);

INSERT INTO t9 (ref_id, payload)
SELECT (random() * 100000)::bigint + 1, (random() * 1000000)::bigint
FROM generate_series(1, 100000);

INSERT INTO t10 (ref_id, payload)
SELECT (random() * 100000)::bigint + 1, (random() * 1000000)::bigint
FROM generate_series(1, 100000);
