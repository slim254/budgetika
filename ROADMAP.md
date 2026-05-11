# Roadmap

## Completed

| Feature | Notes |
|---|---|
| Signed amounts | Positive = income, negative = expense. `transaction_type` field removed. |
| User-scoped categories | Categories shared across wallets, not per-wallet. |
| Category & tag icons/colors/visibility | Lucide icons, hex colors, `is_visible` toggle, soft-delete on categories. |
| Default categories on signup | Django signal copies defaults to each new user. |
| CSV import | Two-step: parse → execute. Generic column mapper. |

---

## Build Order

| # | Feature | Priority | Complexity | Why this order |
|---|---|---|---|---|
| 1 | Dashboards | 4 | 3 | No model changes — pure reads on existing data. Immediate value. |
| 2 | Recurring Transactions | 4 | 4 | Self-contained new model. Doesn't block anything else. |
| 3 | Search & Filters + Pagination | 4 | 3 | Improves usability before data grows. |
| 4 | Budgeting Limits | 2 | 3 | Needs dashboard aggregation patterns established first. |
| 5 | CSV Export | 3 | 2 | Quick win, low risk, natural complement to CSV import. |

---

## Active Features

### 1. Dashboards — Priority 4 · Complexity 3

**What:** Aggregated financial metrics across all wallets (main dashboard) and per wallet (wallet metrics endpoint).

**Why first:** No model changes needed — pure read endpoints using existing data. Gives immediate value and teaches ORM aggregations needed for budgeting limits later.

See **`DASHBOARDS_PLAN.md`** for full spec.

---

### 2. Recurring Transactions — Priority 4 · Complexity 4

**What:** Templates that auto-generate transactions on a schedule (daily/weekly/monthly/etc). Processed by a management command run via cron.

**Why second:** New model + migration + background processing. Self-contained, doesn't depend on dashboards.

See **`RECURRING_TRANSACTIONS_PLAN.md`** for full spec.

---

### 3. Search & Filters + Pagination — Priority 4 · Complexity 3

**What:** Filter transactions by note/category/tag/date range/amount range. Paginate large lists.

**Scope:**
- Backend: Add query params to `WalletTransactionList` (`search`, `category`, `tag`, `date_from`, `date_to`, `min_amount`, `max_amount`)
- Backend: Add DRF pagination (page-based or cursor)
- Frontend: Filter bar UI on wallet page, paginator component

**Files:** `wallets/views.py`, `wallets/urls.py`, `frontend/app/wallet/[id]/page.tsx`

---

### 4. Budgeting Limits — Priority 2 · Complexity 3

**What:** Per-category monthly spending cap with a progress bar showing usage.

**Scope:**
- New model: `BudgetLimit(user, category, amount, month)` — or just `(user, category, monthly_cap)` for rolling limits
- Backend: CRUD endpoints for limits + a `GET /api/budget-status/` endpoint that returns current month's spending vs cap per category
- Frontend: Budget section on dashboard or settings page

**Files:** `wallets/models.py` (new model + migration), `wallets/serializers.py`, `wallets/views.py`, `wallets/urls.py`, frontend pages

---

### 5. CSV Export — Priority 3 · Complexity 2

**What:** Export a wallet's transactions to CSV (respects current month/year filter or all time).

**Scope:**
- Backend: `GET /api/wallets/{id}/export/?month=M&year=Y` returns a CSV file response
- Frontend: Export button on wallet page next to Import CSV

**Files:** `wallets/views.py`, `wallets/urls.py`, `frontend/app/wallet/[id]/page.tsx`

---

## Bugs

| Bug | Where | Notes |
|---|---|---|
| Future-dated transactions reset to today after saving | `TransactionDialog.tsx` + `TransactionSerializer` | Transaction `date` field uses `default=timezone.now` which may be overwritten on edit; investigate form submission flow |

---

## Backlog / Ideas

- Bank CSV presets (PKO, mBank, ING, Santander — auto-fill column mapping)
- Open Banking API integration (Plaid, SWIFT gpi for real-time sync)
- Multi-currency wallet support (exchange rates)
- Shared wallets (multiple users)
- AI-assisted auto-categorization
- Mobile-responsive improvements
