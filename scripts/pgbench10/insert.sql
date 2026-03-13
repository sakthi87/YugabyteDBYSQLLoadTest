\set tid random(1, 10)
\set ref random(1, 100000)
\set payload random(1, 1000000)
\if :tid = 1
INSERT INTO t1 (ref_id, payload) VALUES (NULL, :payload);
\elif :tid = 2
INSERT INTO t2 (ref_id, payload) VALUES (:ref, :payload);
\elif :tid = 3
INSERT INTO t3 (ref_id, payload) VALUES (:ref, :payload);
\elif :tid = 4
INSERT INTO t4 (ref_id, payload) VALUES (:ref, :payload);
\elif :tid = 5
INSERT INTO t5 (ref_id, payload) VALUES (:ref, :payload);
\elif :tid = 6
INSERT INTO t6 (ref_id, payload) VALUES (:ref, :payload);
\elif :tid = 7
INSERT INTO t7 (ref_id, payload) VALUES (:ref, :payload);
\elif :tid = 8
INSERT INTO t8 (ref_id, payload) VALUES (:ref, :payload);
\elif :tid = 9
INSERT INTO t9 (ref_id, payload) VALUES (:ref, :payload);
\else
INSERT INTO t10 (ref_id, payload) VALUES (:ref, :payload);
\endif
