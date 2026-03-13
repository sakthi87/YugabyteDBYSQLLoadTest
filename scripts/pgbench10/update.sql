\set tid random(1, 10)
\set rid random(1, 100000)
\set delta random(-1000, 1000)
\if :tid = 1
UPDATE t1 SET payload = payload + :delta, updated_at = now() WHERE id = :rid;
\elif :tid = 2
UPDATE t2 SET payload = payload + :delta, updated_at = now() WHERE id = :rid;
\elif :tid = 3
UPDATE t3 SET payload = payload + :delta, updated_at = now() WHERE id = :rid;
\elif :tid = 4
UPDATE t4 SET payload = payload + :delta, updated_at = now() WHERE id = :rid;
\elif :tid = 5
UPDATE t5 SET payload = payload + :delta, updated_at = now() WHERE id = :rid;
\elif :tid = 6
UPDATE t6 SET payload = payload + :delta, updated_at = now() WHERE id = :rid;
\elif :tid = 7
UPDATE t7 SET payload = payload + :delta, updated_at = now() WHERE id = :rid;
\elif :tid = 8
UPDATE t8 SET payload = payload + :delta, updated_at = now() WHERE id = :rid;
\elif :tid = 9
UPDATE t9 SET payload = payload + :delta, updated_at = now() WHERE id = :rid;
\else
UPDATE t10 SET payload = payload + :delta, updated_at = now() WHERE id = :rid;
\endif
