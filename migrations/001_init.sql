PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  account TEXT NOT NULL DEFAULT '',
  folder TEXT NOT NULL,
  uid INTEGER NOT NULL,
  message_id TEXT,
  date TEXT,
  from_addr TEXT,
  from_email TEXT,
  to_addr TEXT,
  subject TEXT,
  path TEXT NOT NULL,
  size INTEGER,
  checksum TEXT,
  inserted_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_account_folder_uid
  ON messages(account, folder, uid);

CREATE TABLE IF NOT EXISTS folder_state (
  account TEXT NOT NULL,
  name TEXT NOT NULL,
  last_uid INTEGER NOT NULL,
  PRIMARY KEY(account, name)
);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
USING fts5(
  subject,
  from_addr,
  to_addr,
  body_text,
  tokenize = 'unicode61'
);
