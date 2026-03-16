-- 10 tables: foreign keys chain, no secondary indexes
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

CREATE TABLE IF NOT EXISTS t2 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t2_ref_fk FOREIGN KEY (ref_id) REFERENCES t1 (id)
);

CREATE TABLE IF NOT EXISTS t3 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t3_ref_fk FOREIGN KEY (ref_id) REFERENCES t2 (id)
);

CREATE TABLE IF NOT EXISTS t4 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t4_ref_fk FOREIGN KEY (ref_id) REFERENCES t3 (id)
);

CREATE TABLE IF NOT EXISTS t5 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t5_ref_fk FOREIGN KEY (ref_id) REFERENCES t4 (id)
);

CREATE TABLE IF NOT EXISTS t6 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t6_ref_fk FOREIGN KEY (ref_id) REFERENCES t5 (id)
);

CREATE TABLE IF NOT EXISTS t7 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t7_ref_fk FOREIGN KEY (ref_id) REFERENCES t6 (id)
);

CREATE TABLE IF NOT EXISTS t8 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t8_ref_fk FOREIGN KEY (ref_id) REFERENCES t7 (id)
);

CREATE TABLE IF NOT EXISTS t9 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t9_ref_fk FOREIGN KEY (ref_id) REFERENCES t8 (id)
);

CREATE TABLE IF NOT EXISTS t10 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT t10_ref_fk FOREIGN KEY (ref_id) REFERENCES t9 (id)
);
