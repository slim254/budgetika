# RUNBOOK — Self-hosting on the Linux mini PC

Single-user personal deployment. Runs over the home LAN; edit over SSH + VS Code Remote.

## First-time setup

```bash
# 1. Clone
git clone <repo-url> budgeting-app && cd budgeting-app

# 2. Backend
cd backend
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure backend env
cp .env.example .env
#   Edit .env: set SECRET_KEY (run the generator below), add the mini PC's
#   LAN IP to ALLOWED_HOSTS and CORS_ALLOWED_ORIGINS.
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 4. DB + first user
python manage.py migrate
python manage.py createsuperuser        # this is your login
python manage.py seed_categories        # optional: default categories

# 5. Frontend
cd ../frontend
pnpm install
cp .env.example .env.local
#   Edit .env.local: set NEXT_PUBLIC_API_URL=http://<mini-pc-ip>:8100/api/
```

## Run (two terminals / two tmux panes)

```bash
# Terminal 1 — backend, bound to all interfaces for LAN access
cd backend && source venv/bin/activate
python manage.py runserver 0.0.0.0:8100

# Terminal 2 — frontend
cd frontend
pnpm dev -- -H 0.0.0.0
```

Open `http://<mini-pc-ip>:3100` from any device on the LAN. Health check: `curl http://<mini-pc-ip>:8100/api/health/` → `{"status": "ok"}`.

## Find the mini PC's LAN IP

```bash
ip addr show | grep 'inet ' | grep -v 127.0.0.1
```

## Updating after a git pull

```bash
cd backend && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
cd ../frontend && pnpm install
```

## Backups & restore

The SQLite database lives outside the repo, at the path in `DATABASE_URL`
(`backend/.env`) — by default `~/.budgeting-app/db.sqlite3`. Nothing under
`backend/` needs to be backed up to preserve your data.

> The DB was moved out of `backend/db.sqlite3` and into `~/.budgeting-app/`
> as part of setting this up, starting from a fresh, empty, migrated
> database. If you're picking this up after that move: **your old superuser
> login no longer exists — run `python manage.py createsuperuser` again**
> before logging in.

### Automated daily backup (macOS)

```bash
./scripts/install-backup-agent.sh
```

Installs `scripts/com.pj.budgeting-backup.plist` as a `launchd` user agent
that runs `manage.py backup_db` every day at 09:00, using the repo's venv.
Not installed automatically — run the script yourself when ready. Uninstall
with `launchctl unload ~/Library/LaunchAgents/com.pj.budgeting-backup.plist
&& rm ~/Library/LaunchAgents/com.pj.budgeting-backup.plist`.

### Manual backup

```bash
cd backend && source venv/bin/activate
python manage.py backup_db
```

Uses SQLite's online backup API (`sqlite3.Connection.backup`), so it's safe
to run while the server is up — no torn/corrupt snapshots. Writes to
`~/.budgeting-app/backups/db-YYYYMMDD-HHMMSS.sqlite3`, then prunes backups
older than 30 days (always keeping at least the 5 most recent, regardless of
age). Fails with a clear error if `DATABASE_URL` points at a non-SQLite
database — there's no `.backup`-equivalent generic path for that case; use
your database's own backup tool instead.

### Full CSV export

```bash
cd backend && source venv/bin/activate
python manage.py export_all
```

Writes one CSV per entity (wallets, transactions, categories, tags, savings
goals, recurring transactions, budget rules, import rules) to a timestamped
directory under `~/.budgeting-app/exports/`. Human-readable, spreadsheet-
friendly companion to `backup_db`'s binary snapshot — not itself a restore
format (restore always goes through the `.sqlite3` backup file below).

### Restore

Stop the backend, then copy a backup file over the live database (path from
`DATABASE_URL`):

```bash
cp ~/.budgeting-app/backups/db-20260415-090000.sqlite3 ~/.budgeting-app/db.sqlite3
```

Restart the backend. Alternatively, for a JSON fixture produced by
`manage.py dumpdata`, `loaddata` now works end-to-end (the `raw=True` guard
added to the category/profile signals stops them from firing during
`loaddata`'s deserialization, which previously caused duplicate-category
errors on restore).

## Appendix — run-on-boot + HTTPS (optional, not required for MVP)

For always-on with auto-restart, use two `systemd` user services (backend `gunicorn config.wsgi`, frontend `next start` after `next build`). For HTTPS on the LAN without certificate hassle, put both behind **Tailscale** (`tailscale serve`) or a **Caddy** reverse proxy with a local CA. These are documented as a later production step — the `runserver`/`pnpm dev` setup above is sufficient for personal daily use.
