# Budgeting App

Personal budgeting app with a Django REST Framework backend and Next.js 15 frontend. SQLite in dev. JWT auth throughout.

## Architecture

```
budgeting-app/
├── backend/      Django 5.1 + DRF, Python 3.13, SQLite
└── frontend/     Next.js 15, TypeScript, Tailwind, shadcn/ui
```

## Dev Setup

Two terminals required — backend and frontend run independently.

**Backend** (Terminal 1):
```bash
cd backend
source venv/bin/activate
python manage.py runserver          # http://localhost:8000
```

**Frontend** (Terminal 2):
```bash
cd frontend
npm run dev                          # http://localhost:3000
```

After migrations or model changes:
```bash
cd backend && source venv/bin/activate
python manage.py makemigrations
python manage.py migrate
```

URLs:
- Frontend: http://localhost:3000
- API: http://localhost:8000/api/wallets/
- Admin: http://localhost:8000/admin

## Data Model

```
User
 ├── Wallet (many)           — balance is computed (initial_value + sum of transactions)
 │    └── Transaction (many) — positive = income, negative = expense
 ├── TransactionCategory (many) — per-user, not per-wallet
 └── UserTransactionTag (many)  — per-user, not per-wallet
```

All primary keys are UUIDs.

### Amount Convention

**Positive = income, negative = expense.** This is enforced everywhere — in models, serializers, and frontend display. Never use a separate `transaction_type` field.

### Categories & Tags

- User-scoped (shared across wallets), NOT wallet-scoped
- Default categories are auto-copied to each new user via Django signal in `wallets/signals.py`
- Category "delete" is a soft delete (`is_archived=True`); tags are hard deleted
- Both support `is_visible` toggle: hidden items are excluded from dropdowns but remain on existing transactions

### Wallet Balance

Balance is **never stored**. It is computed on every serialization:
```python
balance = initial_value + sum(transaction.amount for all transactions)
```

## API Overview

All endpoints require JWT auth (`Authorization: Bearer <token>`).

```
GET/POST   /api/wallets/
GET/PATCH/DELETE  /api/wallets/{wallet_id}/
GET/POST   /api/wallets/{wallet_id}/transactions/?month=M&year=Y
GET/PATCH/DELETE  /api/wallets/{wallet_id}/transactions/{id}/
GET/PATCH/DELETE  /api/transactions/{id}/
GET/POST   /api/wallets/categories/
GET/PATCH/DELETE  /api/wallets/categories/{id}/
GET/POST   /api/wallets/tags/
GET/PATCH/DELETE  /api/wallets/tags/{id}/
POST       /api/wallets/{wallet_id}/import/parse/
POST       /api/wallets/{wallet_id}/import/execute/
POST       /api/token/           (login)
POST       /api/token/refresh/
POST       /api/register/
```

## CSV Import

Two-step flow:
1. **Parse** (`/import/parse/`) — upload CSV, get columns + sample rows + unique values
2. **Execute** (`/import/execute/`) — supply column mapping + amount config + optional filters

Business logic lives in `backend/wallets/services.py` (`GenericCSVImportService`). Duplicate detection: same wallet + date + amount + note.

## Currencies

Supported: `usd`, `eur`, `gbp`, `pln`. A transaction's currency must match its wallet's currency (enforced in `TransactionSerializer.validate()`).

## Pending Features (TODOs.md)

- Recurring transactions
- Dashboard with metrics
- Budgeting (per-category monthly limits)
- Search & filters + pagination
- CSV export
- Bug: future-dated transactions reset to today after save
