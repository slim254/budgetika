# Budgeting App - Project Setup & Running Guide

Complete instructions for setting up and running this Django + Next.js budgeting application from scratch.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Project Structure](#project-structure)
3. [Backend Setup (Django)](#backend-setup-django)
4. [Frontend Setup (Next.js)](#frontend-setup-nextjs)
5. [Running the Application](#running-the-application)
6. [Database Management](#database-management)
7. [Common Issues & Solutions](#common-issues--solutions)
8. [Testing the API](#testing-the-api)

---

## Prerequisites

### Required Software
- **Python 3.10+** (for Django backend)
- **Node.js 18+** and **npm** (for Next.js frontend)
- **Git** (for version control)

### Check if You Have Them

```bash
# Check Python version
python3 --version
# Should output: Python 3.10.x or higher

# Check Node.js and npm versions
node --version
npm --version
# Should output: v18.x or higher for Node
# Should output: 8.x or higher for npm
```

### Mac-Specific Installation (if needed)

Using Homebrew:
```bash
# Install Python 3
brew install python@3.11

# Install Node.js
brew install node

# Verify installation
python3 --version
node --version
```

### Linux/Windows
- **Python**: https://www.python.org/downloads/
- **Node.js**: https://nodejs.org/

---

## Project Structure

```
budgeting-app/
├── backend/                    # Django REST API
│   ├── config/                # Django settings
│   ├── wallets/               # Main app (models, views, serializers)
│   ├── manage.py              # Django management script
│   ├── db.sqlite3             # SQLite database (created after migration)
│   └── requirements.txt       # Python dependencies
│
├── frontend/                  # Next.js React application
│   ├── app/                   # App Router pages
│   ├── components/            # React components
│   ├── package.json           # Node.js dependencies
│   └── .env.local             # Environment variables (create this)
│
├── CODEBASE_ANALYSIS.md       # Detailed codebase explanation
├── DJANGO_REFRESHER.md        # Django cheat sheet
└── PROJECT_SETUP.md           # This file
```

---

## Backend Setup (Django)

### Step 1: Navigate to Backend Directory

```bash
cd budgeting-app/backend
```

From now on, all backend commands should be run from this directory.

### Step 2: Create Python Virtual Environment

A virtual environment isolates Python packages for this project from your system Python.

**On macOS/Linux**:
```bash
# Create virtual environment named 'venv'
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# You should see (venv) prefix in terminal:
# (venv) user@computer:~/budgeting-app/backend$
```

**On Windows (PowerShell)**:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# If you get permission error, run:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**On Windows (Command Prompt)**:
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate.bat
```

### Step 3: Verify Virtual Environment is Active

You should see `(venv)` at the beginning of your terminal prompt:

```bash
# macOS/Linux - should show:
(venv) user@computer:~/budgeting-app/backend$

# Windows PowerShell - should show:
(venv) PS C:\Users\user\budgeting-app\backend>

# Windows Command Prompt - should show:
(venv) C:\Users\user\budgeting-app\backend>
```

### Step 4: Install Python Dependencies

```bash
# Make sure virtual environment is active (see step 2)
pip install -r requirements.txt

# This installs:
# - Django 5.1.3
# - Django REST Framework 3.14.0
# - djangorestframework-simplejwt 5.3.2
# - django-cors-headers 4.3.1
# - python-decouple (for environment variables)
```

**If you get an error about pip**:
```bash
# Update pip first
python3 -m pip install --upgrade pip

# Then try again
pip install -r requirements.txt
```

### Step 5: Create Django Superuser (Admin Account)

```bash
# Run migrations first (see Step 6)
python manage.py migrate

# Create superuser account
python manage.py createsuperuser

# You'll be prompted for:
# Username: testuser
# Email: test@example.com
# Password: (enter a password)
# Password (again): (repeat password)
```

### Step 6: Run Database Migrations

Migrations create database tables from models.

```bash
# Apply all migrations
python manage.py migrate

# Expected output:
# Operations to perform:
#   Apply all migrations: admin, auth, contenttypes, sessions, wallets
# Running migrations:
#   Applying wallets.0001_initial... OK
#   ... more migrations ...
```

If you modify models and need new migrations:
```bash
# Create new migration
python manage.py makemigrations

# Apply migration
python manage.py migrate
```

### Step 7: Test Django Backend

```bash
# Start Django development server
python manage.py runserver

# Expected output:
# Watching for file changes with StatReloader
# Performing system checks...
#
# System check identified no issues (0 silenced).
# December 05, 2025 - 22:30:00
# Django version 5.1.3, using settings 'config.settings'
# Starting development server at http://127.0.0.1:8000/
# Quit the server with CONTROL-C.
```

✅ **Backend is running!** Visit these URLs to verify:
- Admin interface: http://localhost:8000/admin/
  - Login with superuser credentials from Step 5
- API endpoints: http://localhost:8000/api/wallets/
  - Returns `[]` (empty list) because no data exists yet

### Step 8: Create Test Data (Optional)

```bash
# Start Django interactive shell
python manage.py shell

# Run these Python commands:
from django.contrib.auth.models import User
from wallets.models import Wallet, WalletCategory

# Create test user
user = User.objects.create_user(
    username='testuser',
    email='test@example.com',
    password='password123'
)

# Create wallet for user
wallet = Wallet.objects.create(
    name='Monthly Budget',
    user=user,
    initial_value=3000.00,
    currency='usd'
)

# Create category
category = WalletCategory.objects.create(
    name='Groceries',
    wallet=wallet,
    created_by=user,
    type='expense'
)

# Create test transaction
from wallets.models import Transaction
tx = Transaction.objects.create(
    note='Weekly groceries at Whole Foods',
    amount=150.50,
    transaction_type='expense',
    currency='usd',
    wallet=wallet,
    created_by=user,
    category=category
)

# Exit shell
exit()
```

---

## Frontend Setup (Next.js)

### Step 1: Navigate to Frontend Directory

Open a **NEW TERMINAL WINDOW** (keep backend running in other window).

```bash
cd budgeting-app/frontend
```

### Step 2: Install Node.js Dependencies

```bash
# Install all npm packages from package.json
npm install

# This creates 'node_modules' folder and installs:
# - Next.js 15.1.6
# - React 19
# - TypeScript 5
# - Tailwind CSS 3.4.1
# - Axios 1.7.7
# - And many more...

# Takes 1-2 minutes depending on internet speed
```

### Step 3: Create Environment Variables File

Create a `.env.local` file in the frontend directory:

**File**: `budgeting-app/frontend/.env.local`
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
```

This tells the frontend where to find the Django API.

### Step 4: Test Frontend

```bash
# Start Next.js development server
npm run dev

# Expected output:
# ▲ Next.js 15.1.6
# - Local:        http://localhost:3000
# - Environments: .env.local
#
# ✓ Ready in 2.5s
```

✅ **Frontend is running!** Visit: http://localhost:3000

---

## Running the Application

### Full Setup Summary

You need **TWO terminal windows open simultaneously**:

#### Terminal 1: Backend (Django)

```bash
# Navigate to backend
cd budgeting-app/backend

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
.\venv\Scripts\activate.ps1  # Windows PowerShell
# OR
venv\Scripts\activate.bat  # Windows Command Prompt

# Start Django server
python manage.py runserver

# Should show:
# Starting development server at http://127.0.0.1:8000/
```

#### Terminal 2: Frontend (Next.js)

```bash
# Navigate to frontend (open NEW terminal window)
cd budgeting-app/frontend

# Start Next.js development server
npm run dev

# Should show:
# ✓ Ready in X.Xs
# http://localhost:3000
```

### Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/api/wallets/
- **Admin Panel**: http://localhost:8000/admin/

### Stop the Servers

```bash
# In each terminal, press:
Ctrl + C

# This stops the respective server
```

---

## Database Management

### Inspect Database

Django creates SQLite database automatically at `backend/db.sqlite3`

```bash
# View all database operations (in backend directory with venv active)
python manage.py shell

# Example commands:
from wallets.models import Wallet, Transaction
Wallet.objects.all()  # View all wallets
Transaction.objects.all()  # View all transactions
exit()
```

### Reset Database (Delete All Data)

**WARNING**: This deletes all data in the database.

```bash
# Option 1: Delete database file
rm backend/db.sqlite3  # macOS/Linux
del backend\db.sqlite3  # Windows

# Option 2: Then run migrations to recreate tables
python manage.py migrate

# Re-create superuser if needed
python manage.py createsuperuser
```

### Backup Database

```bash
# Copy database file
cp backend/db.sqlite3 backend/db.sqlite3.backup  # macOS/Linux
copy backend\db.sqlite3 backend\db.sqlite3.backup  # Windows
```

### View Database with SQLite Browser

Install SQLite Browser: https://sqlitebrowser.org/

Then open `backend/db.sqlite3` to view/edit data visually.

---

## Common Issues & Solutions

### Issue 1: "ModuleNotFoundError: No module named 'django'"

**Cause**: Virtual environment not activated

**Solution**:
```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
.\venv\Scripts\activate.ps1  # Windows PowerShell

# You should see (venv) prefix
(venv) user@computer$
```

### Issue 2: "django.db.utils.OperationalError: no such table: auth_user"

**Cause**: Migrations not run

**Solution**:
```bash
cd backend
source venv/bin/activate  # or activate.ps1 on Windows

python manage.py migrate
```

### Issue 3: "Port 8000 already in use"

**Cause**: Another process using port 8000

**Solution Option 1 - Kill the process**:
```bash
# macOS/Linux - find and kill process on port 8000
lsof -i :8000
kill -9 <PID>

# Windows - find and kill process on port 8000
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Solution Option 2 - Use different port**:
```bash
python manage.py runserver 8001
# Runs on http://localhost:8001 instead
```

### Issue 4: "Port 3000 already in use"

**Same as Issue 3**, but for frontend:

```bash
# macOS/Linux
lsof -i :3000
kill -9 <PID>

# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F
```

**Or use different port**:
```bash
npm run dev -- -p 3001
# Runs on http://localhost:3001 instead
```

### Issue 5: "CORS error" when frontend calls backend

**Cause**: CORS headers not configured correctly

**Current Configuration** (should work):
- Backend allows all origins: `CORS_ALLOW_ALL_ORIGINS = True` in `settings.py`

**If still getting CORS error**:
1. Verify backend is running: http://localhost:8000/api/wallets/
2. Check browser console for exact error message
3. Verify API URL in frontend `.env.local`: `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api`

### Issue 6: "Cannot GET /api/wallets/" returns 401 Unauthorized

**Cause**: JWT token not provided

**Expected behavior**: Returns `[]` (empty list) if not authenticated

**Solution**: Login first through frontend UI at http://localhost:3000/login

### Issue 7: "npm ERR! code EACCES" on macOS/Linux

**Cause**: Permissions issue with npm

**Solution**:
```bash
# Option 1: Use sudo
sudo npm install

# Option 2: Fix npm permissions
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
export PATH=~/.npm-global/bin:$PATH
```

### Issue 8: "venv already exists" when creating virtual environment

**Cause**: Virtual environment already exists

**Solution**:
```bash
# Option 1: Activate existing venv
source venv/bin/activate  # macOS/Linux
.\venv\Scripts\activate.ps1  # Windows PowerShell

# Option 2: Delete and recreate
rm -rf venv  # macOS/Linux
rmdir /s venv  # Windows

python3 -m venv venv
source venv/bin/activate
```

### Issue 9: "pip: command not found"

**Cause**: Python not in PATH or python3 should be used

**Solution**:
```bash
# Use python3 instead
python3 -m pip install -r requirements.txt

# Or use python -m pip on Windows
python -m pip install -r requirements.txt
```

### Issue 10: "SyntaxError: invalid syntax" when running Python

**Cause**: Using Python 2 instead of Python 3

**Solution**:
```bash
# Check Python version
python --version

# If version is 2.x, use python3 instead
python3 --version
python3 manage.py runserver
```

---

## Testing the API

### Test Without Authentication (Postman/Curl)

**Get all wallets** (should return 401 Unauthorized):
```bash
curl -X GET http://localhost:8000/api/wallets/
# Response: {"detail":"Authentication credentials were not provided."}
```

### Test With JWT Authentication

#### Step 1: Get JWT Token

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'

# Response:
# {
#   "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
#   "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
# }

# Copy the "access" token
```

#### Step 2: Use Token to Access API

```bash
curl -X GET http://localhost:8000/api/wallets/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"

# Response:
# [
#   {
#     "id": 1,
#     "name": "Monthly Budget",
#     "user": 1,
#     "initial_value": "3000.00",
#     "currency": "usd",
#     "balance": "2849.50",
#     "categories": [...],
#     "transactions": [...]
#   }
# ]
```

### Using Postman (GUI Tool)

1. Download Postman: https://www.postman.com/downloads/

2. Create Login Request:
   - Method: POST
   - URL: `http://localhost:8000/api/token/`
   - Body (JSON): `{"username": "testuser", "password": "password123"}`
   - Send
   - Copy the `access` token

3. Create Wallets Request:
   - Method: GET
   - URL: `http://localhost:8000/api/wallets/`
   - Headers:
     - Key: `Authorization`
     - Value: `Bearer YOUR_ACCESS_TOKEN_HERE`
   - Send

### Using Thunder Client (VS Code Extension)

1. Install extension in VS Code
2. Create new request
3. Same steps as Postman above

---

## Development Workflow

### Daily Development

```bash
# Terminal 1: Start backend (if virtual environment not already active)
cd budgeting-app/backend
source venv/bin/activate  # or activate.ps1 on Windows
python manage.py runserver

# Terminal 2: Start frontend (new terminal window)
cd budgeting-app/frontend
npm run dev

# Visit http://localhost:3000
# Make code changes
# Changes auto-reload (hot reload)
```

### Making Model Changes

```bash
# After modifying models.py:
python manage.py makemigrations

# Review the migration file in wallets/migrations/

python manage.py migrate

# Server restarts automatically
```

### Installing New Python Package

```bash
# Make sure virtual environment is active
source venv/bin/activate

# Install package
pip install package-name

# Update requirements.txt
pip freeze > requirements.txt

# Commit changes
```

### Installing New Node Package

```bash
# In frontend directory
npm install package-name

# Or for dev dependency
npm install --save-dev package-name

# Commit changes
```

---

## Production Notes (Future Deployment)

These settings are for **development only**. For production:

### Security Changes Needed

```python
# backend/config/settings.py

# ❌ Development (NEVER use in production):
DEBUG = True
SECRET_KEY = 'django-insecure-...'
CORS_ALLOW_ALL_ORIGINS = True

# ✅ Production:
DEBUG = False
SECRET_KEY = os.environ.get('SECRET_KEY')  # Use environment variable
ALLOWED_HOSTS = ['yourdomain.com']
CORS_ALLOWED_ORIGINS = ['https://yourdomain.com']

# Use PostgreSQL instead of SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT'),
    }
}

# Enable HTTPS
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
```

### Deployment Platforms

- **Backend**: Heroku, Railway, Render, DigitalOcean
- **Frontend**: Vercel, Netlify
- **Database**: PostgreSQL on Heroku, AWS RDS, DigitalOcean

---

## Useful Commands Quick Reference

### Backend (Django)

```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
.\venv\Scripts\activate.ps1  # Windows PowerShell

# Start server
python manage.py runserver

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Interactive shell
python manage.py shell

# Deactivate virtual environment
deactivate
```

### Frontend (Next.js)

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm run start

# Run linter (if configured)
npm run lint

# Format code (if configured)
npm run format
```

---

## Next Steps

1. ✅ Setup backend following Backend Setup section
2. ✅ Setup frontend following Frontend Setup section
3. ✅ Run both servers simultaneously
4. ✅ Test login at http://localhost:3000/login
5. 📖 Read `CODEBASE_ANALYSIS.md` to understand the code
6. 🔧 Make code changes and test
7. 📝 Create test transactions through the UI
8. 🐛 Debug using browser DevTools and Django logs

---

## Need Help?

1. Check the **Common Issues & Solutions** section above
2. Check error messages in terminal output
3. Check browser console (F12 → Console tab)
4. Check Django debug page (if DEBUG=True) at error URL
5. Read documentation files in the project

Good luck! Happy coding! 🚀
