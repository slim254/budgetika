# Quick Start - 5 Minutes Setup

Fast setup guide if you've done this before. For detailed instructions, see `PROJECT_SETUP.md`.

---

## TL;DR - Copy & Paste Commands

### Backend Setup (Terminal 1)

```bash
# Navigate to backend
cd budgeting-app/backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# OR on Windows PowerShell:
# .\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Start backend
python manage.py runserver
```

### Frontend Setup (Terminal 2 - NEW WINDOW)

```bash
# Navigate to frontend
cd budgeting-app/frontend

# Install dependencies
npm install

# Create environment file
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api" > .env.local

# Start frontend
npm run dev
```

### Access Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/api/wallets/
- **Admin**: http://localhost:8000/admin

---

## Checklist

- [ ] Python 3.10+ installed: `python3 --version`
- [ ] Node.js 18+ installed: `node --version`
- [ ] Backend virtual environment created and activated (see `(venv)` prefix)
- [ ] Backend dependencies installed: `pip install -r requirements.txt` succeeded
- [ ] Database migrated: `python manage.py migrate` succeeded
- [ ] Backend running: `python manage.py runserver` shows "Quit the server with CONTROL-C"
- [ ] Frontend dependencies installed: `npm install` succeeded
- [ ] Frontend `.env.local` created with `NEXT_PUBLIC_API_BASE_URL`
- [ ] Frontend running: `npm run dev` shows "✓ Ready in Xs"
- [ ] Can visit http://localhost:3000 (frontend loads)
- [ ] Can visit http://localhost:8000/admin (Django admin loads)

---

## One-Time Commands

These only need to be run once:

```bash
# Create virtual environment (first time only)
cd budgeting-app/backend
python3 -m venv venv

# Install Python dependencies (first time only)
source venv/bin/activate
pip install -r requirements.txt

# Install Node dependencies (first time only)
cd budgeting-app/frontend
npm install

# Create .env.local file (first time only)
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api" > .env.local

# Create superuser (first time only)
cd budgeting-app/backend
python manage.py createsuperuser

# Run migrations (first time only)
python manage.py migrate
```

---

## Recurring Commands

These are run every time you work on the project:

```bash
# Activate virtual environment (every time you open terminal)
cd budgeting-app/backend
source venv/bin/activate

# Start backend (every work session)
python manage.py runserver

# Start frontend (every work session, in NEW terminal)
cd budgeting-app/frontend
npm run dev
```

---

## Windows Users

### PowerShell Version

```powershell
# Navigate to backend
cd budgeting-app\backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# If you get permission error, run this once:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install dependencies
pip install -r requirements.txt

# Migrations
python manage.py migrate

# Start backend
python manage.py runserver
```

### Command Prompt Version

```cmd
REM Navigate to backend
cd budgeting-app\backend

REM Create virtual environment
python -m venv venv

REM Activate virtual environment
venv\Scripts\activate.bat

REM Install dependencies
pip install -r requirements.txt

REM Migrations
python manage.py migrate

REM Start backend
python manage.py runserver
```

---

## Verify Installation

```bash
# Check backend is running (visit in browser)
http://localhost:8000/api/wallets/

# Should see either:
# [] (empty list if not authenticated)
# OR
# {"detail":"Authentication credentials were not provided."}

# Check frontend is running (visit in browser)
http://localhost:3000

# Should see login page or home page

# Check admin (visit in browser)
http://localhost:8000/admin

# Should see Django admin interface
```

---

## Deactivate Virtual Environment

When done working:

```bash
deactivate
```

You should see `(venv)` prefix disappear from terminal.

---

## Reset Everything

If something breaks:

```bash
# Remove and recreate backend environment
cd budgeting-app/backend
rm -rf venv  # macOS/Linux
rmdir /s venv  # Windows

python3 -m venv venv
source venv/bin/activate  # or Activate.ps1 on Windows
pip install -r requirements.txt

# Reset frontend
cd budgeting-app/frontend
rm -rf node_modules package-lock.json
npm install

# Reset database
cd budgeting-app/backend
rm db.sqlite3
python manage.py migrate
```

---

## Common Errors - Quick Fixes

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: No module named 'django'` | Activate venv: `source venv/bin/activate` |
| `Port 8000 already in use` | Use different port: `python manage.py runserver 8001` |
| `Port 3000 already in use` | Use different port: `npm run dev -- -p 3001` |
| `CORS error` | Backend must be running at `http://localhost:8000` |
| `Cannot GET /api/wallets/` returns 401 | Normal - login first at `/login` |
| `no such table: auth_user` | Run migrations: `python manage.py migrate` |
| `Python 2 instead of 3` | Use `python3` instead of `python` |

---

## Environment Files

### `.env.local` (Frontend)

Location: `budgeting-app/frontend/.env.local`

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
```

**Create it once, then ignore**

### `.gitignore` (Don't Commit These)

Already in `.gitignore`:
- `venv/` - Python virtual environment
- `node_modules/` - Node packages
- `db.sqlite3` - SQLite database
- `.env.local` - Environment variables
- `__pycache__/` - Python cache

**Never commit these to Git**

---

## Documentation Files

Read these for more info:

1. **QUICK_START.md** (this file) - 5 minute setup
2. **PROJECT_SETUP.md** - Detailed setup with troubleshooting
3. **CODEBASE_ANALYSIS.md** - Deep dive into code structure
4. **DJANGO_REFRESHER.md** - Django concepts cheat sheet

---

## Keyboard Shortcuts

### Stop Servers

```bash
Ctrl + C  # Works on macOS, Linux, Windows
```

### Reload Servers (After Code Changes)

- **Backend**: Automatically reloads when you save files
- **Frontend**: Automatically reloads when you save files (hot reload)

### Django Shell

```bash
python manage.py shell

# Inside shell:
from wallets.models import Wallet
Wallet.objects.all()

# Exit:
exit()
```

---

## Need Help?

1. See `PROJECT_SETUP.md` for detailed instructions
2. See `CODEBASE_ANALYSIS.md` to understand code
3. See `DJANGO_REFRESHER.md` for Django concepts

---

## Ready to Code? 🚀

1. Open two terminals side by side
2. Run backend in Terminal 1
3. Run frontend in Terminal 2
4. Visit http://localhost:3000
5. Start coding!

Good luck! 💪
