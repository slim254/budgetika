# Budgeting App

Django REST Framework backend + Next.js frontend. See [CLAUDE.md](CLAUDE.md) for architecture, [RUNBOOK.md](RUNBOOK.md) for LAN self-host deploy. This file = command cheat sheet.

## First-time setup

```bash
# Backend
cd backend
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # edit: SECRET_KEY, ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS
python manage.py migrate
python manage.py createsuperuser   # this is your login, no /register/ endpoint
python manage.py seed_categories   # optional: default categories

# Frontend
cd ../frontend
pnpm install
cp .env.example .env.local         # edit: NEXT_PUBLIC_API_URL
```

Generate a `SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Day-to-day (two terminals)

```bash
# Terminal 1 — backend
cd backend && source venv/bin/activate
python manage.py runserver 8100          # http://localhost:8100

# Terminal 2 — frontend
cd frontend
pnpm dev                                  # http://localhost:3100
```

## Backend commands

```bash
source venv/bin/activate                  # always first, from backend/

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_categories                              # default categories for a user
python manage.py process_recurring [--dry-run] [--force-date YYYY-MM-DD]
python manage.py test                                          # or: python manage.py test wallets
python manage.py check
python manage.py shell
```

## Frontend commands

```bash
pnpm install
pnpm dev                # http://localhost:3100
pnpm build
pnpm start               # serve production build
pnpm lint
npx tsc --noEmit         # typecheck
```

## Docker

Not set up — no Dockerfile/compose in this repo. Dev runs via venv + `pnpm dev`; self-host runs the same way on the mini PC (see [RUNBOOK.md](RUNBOOK.md)).

## Misc

```bash
# Find LAN IP (for self-host / testing from another device)
ip addr show | grep 'inet ' | grep -v 127.0.0.1        # Linux
ipconfig getifaddr en0                                   # macOS

# Health check
curl http://localhost:8100/api/health/
```
