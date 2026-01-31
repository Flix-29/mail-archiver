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

## Metrics + Grafana (optional)
This job can push Prometheus metrics to a Pushgateway or write a textfile for node_exporter.

### Option A: Pushgateway + Prometheus (recommended)
1) Start monitoring stack (can run on NAS):
```bash
cd monitoring
docker compose up -d
```
2) Set env in `config/.env`:
```
METRICS_PUSHGATEWAY_URL=http://<NAS_IP>:9091
METRICS_JOB=mail_archiver
METRICS_INSTANCE=<pi-hostname>
```
3) In Grafana, add Prometheus datasource:
```
http://<NAS_IP>:9090
```

Suggested panels:
- `mail_archiver_messages_archived`
- `mail_archiver_run_duration_seconds`
- `mail_archiver_errors`
- `mail_archiver_last_run_timestamp`

### Option B: Textfile metrics (node_exporter)
Set:
```
METRICS_TEXTFILE=/state/metrics.prom
```
and configure node_exporter to scrape that file.

## Notes
- IMAP folders can vary by locale; update `IMAP_FOLDERS` if needed.
- SQLite DB is stored locally in `./state` by default to avoid SMB locking issues.
