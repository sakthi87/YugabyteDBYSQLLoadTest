-- 10 tables: secondary indexes + foreign keys
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE OR REPLACE FUNCTION uuid_from_int(n BIGINT) RETURNS UUID AS $$
  SELECT (
    substr(md5(n::text), 1, 8) || '-' ||
    substr(md5(n::text), 9, 4) || '-' ||
    substr(md5(n::text), 13, 4) || '-' ||
    substr(md5(n::text), 17, 4) || '-' ||
    substr(md5(n::text), 21, 12)
  )::uuid;
$$ LANGUAGE sql IMMUTABLE;
CREATE TABLE IF NOT EXISTS t1 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS t1_ref_id_idx ON t1 (ref_id);

CREATE TABLE IF NOT EXISTS t2 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t2_ref_fk FOREIGN KEY (ref_id) REFERENCES t1 (id)
);
CREATE INDEX IF NOT EXISTS t2_ref_id_idx ON t2 (ref_id);

CREATE TABLE IF NOT EXISTS t3 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t3_ref_fk FOREIGN KEY (ref_id) REFERENCES t2 (id)
);
CREATE INDEX IF NOT EXISTS t3_ref_id_idx ON t3 (ref_id);

CREATE TABLE IF NOT EXISTS t4 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t4_ref_fk FOREIGN KEY (ref_id) REFERENCES t3 (id)
);
CREATE INDEX IF NOT EXISTS t4_ref_id_idx ON t4 (ref_id);

CREATE TABLE IF NOT EXISTS t5 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t5_ref_fk FOREIGN KEY (ref_id) REFERENCES t4 (id)
);
CREATE INDEX IF NOT EXISTS t5_ref_id_idx ON t5 (ref_id);

CREATE TABLE IF NOT EXISTS t6 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t6_ref_fk FOREIGN KEY (ref_id) REFERENCES t5 (id)
);
CREATE INDEX IF NOT EXISTS t6_ref_id_idx ON t6 (ref_id);

CREATE TABLE IF NOT EXISTS t7 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t7_ref_fk FOREIGN KEY (ref_id) REFERENCES t6 (id)
);
CREATE INDEX IF NOT EXISTS t7_ref_id_idx ON t7 (ref_id);

CREATE TABLE IF NOT EXISTS t8 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t8_ref_fk FOREIGN KEY (ref_id) REFERENCES t7 (id)
);
CREATE INDEX IF NOT EXISTS t8_ref_id_idx ON t8 (ref_id);

CREATE TABLE IF NOT EXISTS t9 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t9_ref_fk FOREIGN KEY (ref_id) REFERENCES t8 (id)
);
CREATE INDEX IF NOT EXISTS t9_ref_id_idx ON t9 (ref_id);

CREATE TABLE IF NOT EXISTS t10 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t10_ref_fk FOREIGN KEY (ref_id) REFERENCES t9 (id)
);
CREATE INDEX IF NOT EXISTS t10_ref_id_idx ON t10 (ref_id);
