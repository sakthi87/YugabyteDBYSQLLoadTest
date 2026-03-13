\set tid random(1, 10)
\set rid random(1, 100000)
\if :tid = 1
DELETE FROM t1 WHERE id = :rid;
\elif :tid = 2
DELETE FROM t2 WHERE id = :rid;
\elif :tid = 3
DELETE FROM t3 WHERE id = :rid;
\elif :tid = 4
DELETE FROM t4 WHERE id = :rid;
\elif :tid = 5
DELETE FROM t5 WHERE id = :rid;
\elif :tid = 6
DELETE FROM t6 WHERE id = :rid;
\elif :tid = 7
DELETE FROM t7 WHERE id = :rid;
\elif :tid = 8
DELETE FROM t8 WHERE id = :rid;
\elif :tid = 9
DELETE FROM t9 WHERE id = :rid;
\else
DELETE FROM t10 WHERE id = :rid;
\endif
