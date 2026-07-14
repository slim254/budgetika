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
npm install
cp .env.example .env.local
#   Edit .env.local: set NEXT_PUBLIC_API_URL=http://<mini-pc-ip>:8000/api/
```

## Run (two terminals / two tmux panes)

```bash
# Terminal 1 — backend, bound to all interfaces for LAN access
cd backend && source venv/bin/activate
python manage.py runserver 0.0.0.0:8000

# Terminal 2 — frontend
cd frontend
npm run dev -- -H 0.0.0.0
```

Open `http://<mini-pc-ip>:3000` from any device on the LAN. Health check: `curl http://<mini-pc-ip>:8000/api/health/` → `{"status": "ok"}`.

## Find the mini PC's LAN IP

```bash
ip addr show | grep 'inet ' | grep -v 127.0.0.1
```

## Updating after a git pull

```bash
cd backend && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
cd ../frontend && npm install
```

## Appendix — run-on-boot + HTTPS (optional, not required for MVP)

For always-on with auto-restart, use two `systemd` user services (backend `gunicorn config.wsgi`, frontend `next start` after `next build`). For HTTPS on the LAN without certificate hassle, put both behind **Tailscale** (`tailscale serve`) or a **Caddy** reverse proxy with a local CA. These are documented as a later production step — the `runserver`/`npm run dev` setup above is sufficient for personal daily use.
