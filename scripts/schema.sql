-- Sample schema. Replace with your own tables.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION uuid_from_int(n BIGINT) RETURNS UUID AS $$
  SELECT (
    substr(md5(n::text), 1, 8) || '-' ||
    substr(md5(n::text), 9, 4) || '-' ||
    substr(md5(n::text), 13, 4) || '-' ||
    substr(md5(n::text), 17, 4) || '-' ||
    substr(md5(n::text), 21, 12)
  )::uuid;
$$ LANGUAGE sql IMMUTABLE;

CREATE TABLE IF NOT EXISTS account (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  balance BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS account_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id UUID NOT NULL,
  delta BIGINT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Optional index example
CREATE INDEX IF NOT EXISTS account_log_account_id_idx ON account_log (account_id);

-- Optional FK example (enable/disable as needed)
-- ALTER TABLE account_log
--   ADD CONSTRAINT account_log_account_fk
--   FOREIGN KEY (account_id) REFERENCES account (id);
