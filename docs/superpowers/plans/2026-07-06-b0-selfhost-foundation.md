# B0 — Self-Host Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the app runnable on a personal Linux mini PC, reachable over the LAN, with configuration read from environment variables instead of hardcoded values.

**Architecture:** Introduce `django-environ` so one `settings.py` reads `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `DATABASE_URL`, and `OPENAI_API_KEY` from the environment / a `.env` file. Add an unauthenticated `GET /api/health/` endpoint. Point the frontend's axios client at an env-configurable API URL. Ship `.env.example` files and a `RUNBOOK.md`.

**Tech Stack:** Django 5.1, DRF, `django-environ`, Next.js 15, SQLite (default; swappable via `DATABASE_URL`).

## Global Constraints

- Python 3.13, Django 5.1.5. SQLite stays the default DB.
- **Do not** split settings into `dev.py`/`prod.py` — env vars provide separation. That split is a later (production) concern.
- Keep an insecure dev fallback for every setting so the app still boots with no `.env` present (needed for CI/tests).
- Single user; no auth changes. Accounts are created via `createsuperuser`.
- Branch: `feat/selfhost-foundation`.

---

### Task 1: Environment-driven Django settings

**Files:**
- Modify: `backend/config/settings.py`
- Modify: `backend/requirements.txt`
- Create: `backend/.env.example`
- Modify: `.gitignore` (repo root; create if absent)

**Interfaces:**
- Produces: settings read via a module-level `env` (`environ.Env`) object; `OPENAI_API_KEY` available in settings for later AI batches.

- [ ] **Step 1: Add `django-environ` to `backend/requirements.txt`**

Append this line:
```
django-environ==0.11.2
```

- [ ] **Step 2: Install it**

```bash
cd backend && source venv/bin/activate
pip install django-environ==0.11.2
pip freeze | grep django-environ
```
Expected: `django-environ==0.11.2`

- [ ] **Step 3: Rewrite the settings header and security block in `backend/config/settings.py`**

Replace the top of the file (from the `from pathlib import Path` line through the `ALLOWED_HOSTS = []` line) with:

```python
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# django-environ: read .env if present. Every value has a dev-safe fallback so
# the app boots with no .env (tests/CI).
env = environ.Env(
    DEBUG=(bool, True),
)
environ.Env.read_env(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key secret in production (set via .env).
SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-dev-only-CHANGE-ME-via-dotenv",
)

# SECURITY WARNING: don't run with debug turned on in production.
DEBUG = env.bool("DEBUG", default=True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
```

- [ ] **Step 4: Replace the `DATABASES` block in `backend/config/settings.py`**

Find the existing `DATABASES = { ... }` block and replace it with:

```python
# Database — SQLite by default; override with DATABASE_URL (e.g. postgres://...)
DATABASES = {
    "default": env.db_url(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}
```

- [ ] **Step 5: Replace the CORS config at the bottom of `backend/config/settings.py`**

Delete the line `CORS_ALLOW_ALL_ORIGINS = True` and add:

```python
# CORS — explicit allowlist (no more allow-all). Add the mini-PC LAN origin via .env.
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
)

# OpenAI (used by the AI batches; harmless if unset)
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
```

- [ ] **Step 6: Verify Django still boots and existing tests pass**

```bash
cd backend && source venv/bin/activate
python manage.py check
python manage.py test tests -v 1
```
Expected: `System check identified no issues` and the existing savings-goals tests pass (`OK`).

- [ ] **Step 7: Create `backend/.env.example`**

```
# Copy to backend/.env and edit. backend/.env is gitignored.
SECRET_KEY=generate-a-long-random-string
DEBUG=True
# Comma-separated. Add the mini-PC hostname/IP for LAN access.
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.50,budget.local
# Comma-separated frontend origins allowed to call the API.
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://192.168.1.50:3000
# Leave unset to use SQLite. Example Postgres: postgres://user:pass@localhost:5432/budget
# DATABASE_URL=
# Needed only for AI features (batch B3).
OPENAI_API_KEY=
```
(The `192.168.1.50` / `budget.local` values are placeholders — the owner replaces them with the mini PC's real LAN IP/hostname in `backend/.env`.)

- [ ] **Step 8: Ensure `.env` files are gitignored**

In the repo-root `.gitignore` (create the file if it does not exist), ensure these lines are present:
```
backend/.env
frontend/.env.local
```

- [ ] **Step 9: Commit**

```bash
git add backend/config/settings.py backend/requirements.txt backend/.env.example .gitignore
git commit -m "feat: read Django settings from environment via django-environ"
```

---

### Task 2: Health check endpoint

**Files:**
- Modify: `backend/wallets/views.py`
- Modify: `backend/config/urls.py`
- Create: `backend/tests/wallets/test_health.py`

**Interfaces:**
- Produces: `GET /api/health/` → `200 {"status": "ok"}`, no auth required.

- [ ] **Step 1: Write the failing test in `backend/tests/wallets/test_health.py`**

```python
from django.test import TestCase
from rest_framework.test import APIClient


class TestHealthEndpoint(TestCase):
    def test_health_returns_ok_without_auth(self):
        response = APIClient().get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
```

- [ ] **Step 2: Run it — expect failure**

```bash
cd backend && source venv/bin/activate
python manage.py test tests.wallets.test_health -v 2
```
Expected: `AssertionError: 404 != 200` (URL not wired).

- [ ] **Step 3: Add `HealthView` to the end of `backend/wallets/views.py`**

```python
from rest_framework.permissions import AllowAny


class HealthView(APIView):
    """Unauthenticated liveness probe for monitoring / systemd health checks."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "ok"})
```
(`APIView` and `Response` are already imported at the top of `views.py`.)

- [ ] **Step 4: Wire the URL in `backend/config/urls.py`**

Add `HealthView` to the existing `from wallets.views import (...)` block, then add to `urlpatterns`:
```python
path('api/health/', HealthView.as_view(), name='health'),
```

- [ ] **Step 5: Run the test — expect pass**

```bash
python manage.py test tests.wallets.test_health -v 2
```
Expected: `Ran 1 test ... OK`

- [ ] **Step 6: Commit**

```bash
git add backend/wallets/views.py backend/config/urls.py backend/tests/wallets/test_health.py
git commit -m "feat: add unauthenticated GET /api/health/ endpoint"
```

---

### Task 3: Env-configurable frontend API URL

**Files:**
- Modify: `frontend/api/axiosInstance.ts`
- Create: `frontend/.env.example`

**Interfaces:**
- Consumes: `process.env.NEXT_PUBLIC_API_URL` (build-time inlined by Next.js).

- [ ] **Step 1: Replace the top of `frontend/api/axiosInstance.ts`**

Replace:
```typescript
import axios from "axios";

export const axiosInstance = axios.create({
  baseURL: "http://localhost:8000/api/",
});
```
with:
```typescript
import axios from "axios";

// Configurable so the app works over LAN on the mini PC.
// Set NEXT_PUBLIC_API_URL in frontend/.env.local (must end with a trailing slash).
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/";

export const axiosInstance = axios.create({
  baseURL: API_URL,
});
```

- [ ] **Step 2: Replace the hardcoded refresh URL in the same file**

Find the raw `fetch(...)` call inside the response interceptor:
```typescript
            const response = await fetch("http://localhost:8000/api/token/refresh/", {
```
Replace the URL argument with the env-based one:
```typescript
            const response = await fetch(`${API_URL}token/refresh/`, {
```

- [ ] **Step 3: Create `frontend/.env.example`**

```
# Copy to frontend/.env.local. Must end with a trailing slash.
# Local dev:
NEXT_PUBLIC_API_URL=http://localhost:8000/api/
# LAN access to the mini PC (replace with its real IP):
# NEXT_PUBLIC_API_URL=http://192.168.1.50:8000/api/
```

- [ ] **Step 4: Verify the frontend still builds**

```bash
cd frontend
npm run lint
npm run build
```
Expected: lint passes, build completes with no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/api/axiosInstance.ts frontend/.env.example
git commit -m "feat: make frontend API base URL configurable via NEXT_PUBLIC_API_URL"
```

---

### Task 4: RUNBOOK

**Files:**
- Create: `RUNBOOK.md` (repo root)

No tests (documentation).

- [ ] **Step 1: Create `RUNBOOK.md` with the exact content below**

````markdown
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
````

- [ ] **Step 2: Commit**

```bash
git add RUNBOOK.md
git commit -m "docs: add RUNBOOK for mini-PC self-hosting"
```

---

## Self-Review notes

- Every setting keeps a dev fallback → `manage.py check`/tests pass with no `.env`.
- `CORS_ALLOW_ALL_ORIGINS` removed; replaced by an explicit allowlist.
- Health endpoint is `AllowAny` + no auth classes so monitoring never needs a token.
- Frontend refresh `fetch` now uses the same env URL as axios — no remaining hardcoded `localhost:8000`.
- Postgres is a one-line `DATABASE_URL` change, deferred to the production phase.
