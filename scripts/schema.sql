-- Sample schema. Replace with your own tables.
CREATE TABLE IF NOT EXISTS account (
  id BIGINT PRIMARY KEY,
  balance BIGINT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS account_log (
  id BIGSERIAL PRIMARY KEY,
  account_id BIGINT NOT NULL,
  delta BIGINT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);

-- Optional index example
CREATE INDEX IF NOT EXISTS account_log_account_id_idx ON account_log (account_id);

-- Optional FK example (enable/disable as needed)
-- ALTER TABLE account_log
--   ADD CONSTRAINT account_log_account_fk
--   FOREIGN KEY (account_id) REFERENCES account (id);
