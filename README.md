# Budgeting App - Full Stack Django + Next.js

A personal finance tracker built with Django REST Framework and Next.js. Track income and expenses, organize transactions by category, and view monthly summaries.

**Status**: Learning project with comprehensive documentation ✅

---

## 📚 Documentation Guide

This project includes extensive documentation tailored to your learning needs:

### For Getting Started (Right Now)
👉 **[QUICK_START.md](QUICK_START.md)** - 5-minute setup
- Copy-paste commands for immediate setup
- One-time vs recurring commands
- Common errors quick fixes
- Checklist to verify installation

### For Detailed Setup Instructions
👉 **[PROJECT_SETUP.md](PROJECT_SETUP.md)** - Complete setup guide
- Step-by-step backend (Django) setup with venv
- Step-by-step frontend (Next.js) setup
- Running both servers simultaneously
- Database management
- Troubleshooting for 10 common issues
- Testing the API with curl/Postman
- Development workflow
- Production deployment notes

### For Django Quick Reference
👉 **[DJANGO_REFRESHER.md](DJANGO_REFRESHER.md)** - Cheat sheet (500+ lines)

Quick lookup for Django concepts used in this project

### For Official Documentation & Learning Resources
👉 **[RESOURCES.md](RESOURCES.md)** - Complete reference guide
- Curated links to official documentation (Django, DRF, React, Next.js, etc.)
- Quick links by use case ("I need to fix a bug", "I want to understand X")
- Recommended reading order
- Learning platforms and communities
- API testing tools
- Deployment platforms

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+

### Setup (5 minutes)

```bash
# Terminal 1: Backend
cd budgeting-app/backend
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Terminal 2: Frontend (NEW WINDOW)
cd budgeting-app/frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/" > .env.local
npm run dev
```

Visit:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000/api/wallets/
- Admin: http://localhost:8000/admin

**For detailed instructions, see [QUICK_START.md](QUICK_START.md)**

---

## 📖 Start Learning

1. **Setup first**: Follow [QUICK_START.md](QUICK_START.md)
2. **Study Django concepts**: Use [DJANGO_REFRESHER.md](DJANGO_REFRESHER.md) as reference
3. **All code has comments**: Check `backend/wallets/*.py` files
