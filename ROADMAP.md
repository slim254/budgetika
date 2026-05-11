# Roadmap

## Completed

| Feature | Notes |
|---|---|
| Signed amounts | Positive = income, negative = expense. `transaction_type` field removed. |
| User-scoped categories | Categories shared across wallets, not per-wallet. |
| Category & tag icons/colors/visibility | Lucide icons, hex colors, `is_visible` toggle, soft-delete on categories. |
| Default categories on signup | Django signal copies defaults to each new user. |
| CSV import | Two-step: parse → execute. Generic column mapper. |
| Dashboards | Main dashboard (`UserDashboard` + `GET /api/dashboard/`) with summary cards, monthly trend chart, category breakdown, wallet list. Per-wallet metrics page (`WalletMetrics` + `GET /api/wallets/{id}/metrics/`) with lifetime stats, monthly breakdown, recent transactions. |
| Currency symbol rendering | `formatCurrency` utility; wallet pages show correct symbol/code per currency (USD `$`, EUR `€`, GBP `£`, PLN `PLN`); dashboard aggregates show no symbol (mixed currencies). |
| Recurring Transactions | `RecurringTransaction` + `RecurringTransactionExecution` models. Six frequencies (daily/weekly/biweekly/monthly/quarterly/yearly). `process_recurring` management command with catch-up (creates all missed occurrences) and `--dry-run`/`--force-date` flags. "Make this recurring" toggle in `TransactionDialog`. Settings page refactored to tabs with new Recurring tab (list, toggle active, edit schedule, view execution history, delete). API: `GET /api/wallets/recurring/`, `GET/POST /api/wallets/{id}/recurring/`, `GET/PATCH/DELETE /api/wallets/{id}/recurring/{id}/`, `GET /api/wallets/{id}/recurring/{id}/executions/`. |

---

## Build Order

| # | Feature | Priority | Complexity | Why this order |
|---|---|---|---|---|
| ~~1~~ | ~~Dashboards~~ | — | — | ✅ Done |
| ~~1~~ | ~~Recurring Transactions~~ | — | — | ✅ Done |
| 1 | Search & Filters + Pagination | 4 | 3 | Improves usability before data grows. |
| 3 | Exchange Rates | 3 | 4 | Enables meaningful cross-currency dashboard totals and transactions in a foreign currency. |
| 4 | Budgeting Limits | 2 | 3 | Needs dashboard aggregation patterns established first. |
| 5 | CSV Export | 3 | 2 | Quick win, low risk, natural complement to CSV import. |

---

## Active Features

### 1. Recurring Transactions — Priority 4 · Complexity 4

**What:** Templates that auto-generate transactions on a schedule (daily/weekly/monthly/etc). Processed by a management command run via cron.

**Why second:** New model + migration + background processing. Self-contained, doesn't depend on dashboards.

See **`RECURRING_TRANSACTIONS_PLAN.md`** for full spec.

---

### 2. Search & Filters + Pagination — Priority 4 · Complexity 3

**What:** Filter transactions by note/category/tag/date range/amount range. Paginate large lists.

**Scope:**
- Backend: Add query params to `WalletTransactionList` (`search`, `category`, `tag`, `date_from`, `date_to`, `min_amount`, `max_amount`)
- Backend: Add DRF pagination (page-based or cursor)
- Frontend: Filter bar UI on wallet page, paginator component

**Files:** `wallets/views.py`, `wallets/urls.py`, `frontend/app/wallet/[id]/page.tsx`

---

### 3. Exchange Rates — Priority 3 · Complexity 4

**What:** Fetch and store historical exchange rates so that:
1. The dashboard's "Total Balance" card can show a single meaningful sum across all wallets (converted to a chosen base currency).
2. When a transaction is added to a PLN wallet in USD (or any cross-currency entry), its amount is auto-converted at the rate for that transaction's date.

**Use cases:**
- Cross-wallet dashboard sum: "You have PLN 5,000 + $200 → PLN 5,840 equivalent today"
- Cross-currency transaction entry: add $100 income to a PLN wallet → stored as PLN 390 at today's rate

**Scope:**

*Backend:*
- New model: `ExchangeRate(base_currency, quote_currency, date, rate)` — indexed on `(base, quote, date)`
- Management command or scheduled task: fetch rates from a free API (e.g. [Frankfurter](https://www.frankfurter.app/) — ECB data, no key needed) and populate the table daily
- New endpoint: `GET /api/exchange-rates/?base=pln&date=2024-01-15` — returns rates for a given base + date (or latest if no date)
- `TransactionSerializer`: if transaction currency ≠ wallet currency, look up rate for `transaction.date` and store the converted amount (or store both raw + converted)
- Dashboard endpoint: accept optional `?base_currency=pln` param; convert each wallet balance before summing

*Frontend:*
- Settings page: "Base currency for dashboard totals" preference (stored in user profile or `localStorage`)
- Dashboard `MetricsSummaryCards`: when all wallets share a base, show converted sum with a "~ PLN equivalent" label
- `TransactionDialog`: if selected currency ≠ wallet currency, show a live preview of the converted amount ("≈ PLN 390 at today's rate")

**Data source:** [Frankfurter API](https://www.frankfurter.app/) — free, no API key, ECB rates, covers USD/EUR/GBP/PLN.

**Files:**
- `wallets/models.py` (new `ExchangeRate` model + migration)
- `wallets/management/commands/fetch_exchange_rates.py` (new)
- `wallets/serializers.py`, `wallets/views.py`, `wallets/urls.py`
- `frontend/app/settings/page.tsx`, `frontend/components/TransactionDialog.tsx`, `frontend/app/dashboard/page.tsx`, `frontend/components/MetricsSummaryCards.tsx`

---

### 4. Budgeting Limits — Priority 2 · Complexity 3

**What:** Per-category monthly spending cap with a progress bar showing usage.

**Scope:**
- New model: `BudgetLimit(user, category, amount, month)` — or just `(user, category, monthly_cap)` for rolling limits
- Backend: CRUD endpoints for limits + a `GET /api/budget-status/` endpoint that returns current month's spending vs cap per category
- Frontend: Budget section on dashboard or settings page

**Files:** `wallets/models.py` (new model + migration), `wallets/serializers.py`, `wallets/views.py`, `wallets/urls.py`, frontend pages

---

### 6. CSV Export — Priority 3 · Complexity 2

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
- Multi-currency wallet support (beyond exchange rates — e.g. wallet holds multiple currencies natively)
- Shared wallets (multiple users)
- AI-assisted auto-categorization
- Mobile-responsive improvements
