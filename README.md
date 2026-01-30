# Mail Archiver (web.de -> NAS)

Small Python tool to fetch mail via IMAP, archive raw `.eml` files to a NAS, and index metadata/body for fast CLI search.

## Quick start
1) Mount your NAS on the Pi host (e.g., `/mnt/mail-archive`).
2) Copy config:
   ```bash
   cp config/.env.example config/.env
   ```
3) Edit `config/.env` with IMAP credentials and paths.
4) Build + run sync:
   ```bash
   docker compose run --rm mail-archiver sync
   ```
5) Search:
   ```bash
   docker compose run --rm mail-archiver search "invoice acme" --limit 20
   ```

## Scheduling (daily)
Use cron or systemd timer on the host:
```bash
docker compose run --rm mail-archiver sync
```

## Notes
- IMAP folders can vary by locale; update `IMAP_FOLDERS` if needed.
- SQLite DB is stored on the NAS by default; if SMB is flaky, consider keeping it local.
