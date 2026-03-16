-- 10 tables: no secondary indexes, no foreign keys
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
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t3 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t4 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t5 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t6 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t7 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t8 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t9 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS t10 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ref_id UUID,
  payload BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);
