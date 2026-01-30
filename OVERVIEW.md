# Mail Archiver Overview

## Current State
- Goal defined: archive web.de mail to a NAS and keep a searchable local index.
- Target environment: Raspberry Pi running Docker, scheduled daily.
- Storage: NAS mounted on host via SMB and bind-mounted into the container.
- Archive mode: append-only history (no deletes mirrored).
- Folders: INBOX, Sent, Junk.
- Interface: CLI for sync and search.
- Initial scaffold created (Dockerfile, docker-compose.yml, src/, migrations/, config/.env.example).

## Plan
1) SMB mount on the Pi host
   - Mount NAS at a stable path (e.g., /mnt/mail-archive).
   - Ensure mount is available before the daily run (systemd mount or fstab + retry).

2) Container setup
   - Use Dockerfile and docker-compose.yml for a lightweight Python image.
   - Bind-mount the NAS path into the container at /data.

3) Core app
   - Implement IMAP sync (TLS) for the selected folders.
   - Save raw .eml files to /data/<folder>/YYYY/MM/DD/.
   - Track last UID per folder in SQLite.

4) Search index
   - SQLite schema with FTS5 for subject/from/to/body.
   - Insert metadata and body text during sync.
   - Provide CLI search command (FTS query).

5) Scheduling and ops
   - Run daily via cron or systemd timer: docker compose run --rm mail-archiver sync.
   - Log to stdout and (optionally) a file on the NAS.

6) Hardening
   - UIDVALIDITY handling and message-id dedupe.
   - Retry on network failures.
   - Backup or periodic export of SQLite DB.

## Open Questions
- SMB share address and mount options on the Pi.
- Whether to keep SQLite DB on NAS or locally and mirror.
- Exact naming of IMAP folders (Sent/Junk localization).
