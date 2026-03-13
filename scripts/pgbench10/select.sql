\set tid random(1, 10)
\set rid random(1, 100000)
\if :tid = 1
SELECT payload FROM t1 WHERE id = :rid;
\elif :tid = 2
SELECT payload FROM t2 WHERE id = :rid;
\elif :tid = 3
SELECT payload FROM t3 WHERE id = :rid;
\elif :tid = 4
SELECT payload FROM t4 WHERE id = :rid;
\elif :tid = 5
SELECT payload FROM t5 WHERE id = :rid;
\elif :tid = 6
SELECT payload FROM t6 WHERE id = :rid;
\elif :tid = 7
SELECT payload FROM t7 WHERE id = :rid;
\elif :tid = 8
SELECT payload FROM t8 WHERE id = :rid;
\elif :tid = 9
SELECT payload FROM t9 WHERE id = :rid;
\else
SELECT payload FROM t10 WHERE id = :rid;
\endif
