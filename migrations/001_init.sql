PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_folder_uid
  ON messages(folder, uid);

CREATE TABLE IF NOT EXISTS folders (
  name TEXT PRIMARY KEY,
  last_uid INTEGER NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts
USING fts5(
  subject,
  from_addr,
  to_addr,
  body_text,
  tokenize = 'unicode61'
);
