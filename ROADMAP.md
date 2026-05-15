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
| Recurring Transactions | `RecurringTransaction` + `RecurringTransactionExecution` models. Six frequencies (daily/weekly/biweekly/monthly/quarterly/yearly). `process_recurring` management command with catch-up (creates all missed occurrences) and `--dry-run`/`--force-date` flags. "Make this recurring" toggle in `TransactionDialog`. Settings page refactored to tabs with new Recurring tab (list, toggle active, edit schedule, view execution history, delete). |
| Search & Filters + Pagination | Full-text note search, filter by category/tag/date range/amount range, cursor-based infinite scroll. New `WalletTransactionSearch` view + `TransactionSearch` component. |
| Budgeting Limits | Per-category monthly spending caps with optional end date and per-month overrides. `BudgetRule` + `BudgetMonthOverride` models. Collapsible `BudgetPanel` on wallet page, two-tab `BudgetManagementDialog`. Summary endpoint computes effective limit + spending per category for a given month. |
| Exchange Rates | On-demand Frankfurter API fetch with DB cache (`ExchangeRate` model). `UserProfile` stores preferred display currency. Dashboard currency switcher converts total balance, income, and expenses. `TransactionDialog` "Enter in a different currency" toggle with 300ms debounced live preview. |

---

## Build Order

| # | Feature | Priority | Complexity | Why this order |
|---|---|---|---|---|
| 1 | Wallet-to-wallet Transfers | 4 | 3 | High-frequency use case; currently requires two manual transactions. |
| 2 | Custom Date Range View | 3 | 2 | Quick win; fills gap between month view and search-all. |
| 3 | Savings Goals | 3 | 3 | Complements budgets; natural next engagement hook. |
| 4 | AI Auto-categorization | 3 | 3 | High-frequency action; most tangible AI value. |
| 5 | AI Receipt Scan | 3 | 3 | Removes manual entry friction; pairs with auto-categorization. |
| 6 | AI Budget Recommendations | 2 | 2 | Needs spending history; easy follow-on to budget feature. |
| 7 | AI Chat & Financial Tips | 3 | 4 | Highest perceived value; more complex to do well. |
| 8 | Toast Messages | 4 | 1 | Cross-cutting UX polish; cheap and high-impact. |
| 9 | CSV Export | 3 | 1 | Natural complement to CSV import. |
| 10 | Over-budget Alerts | 3 | 2 | Closes the loop on the budget feature. |
| 11 | Auth & Account Management | 3 | 3 | Login with username or email, email verification, password reset. |
| 12 | Feature Flags | 2 | 2 | Enables safe rollout of new features before production. |
| 13 | Production Readiness | 5 | 5 | Security, compliance, infra hardening before public launch. |

---

## Active Features

### 1. Wallet-to-wallet Transfers — Priority 4 · Complexity 3

**What:** Record money moved between two of your own wallets as a linked pair — one debit in the source wallet, one credit in the destination wallet — so net worth is unaffected and the transfer is traceable.

**Scope:**
- New model: `WalletTransfer(from_wallet, to_wallet, amount, date, note)` — creates two `Transaction` records atomically, linked via a shared `transfer_ref` UUID
- Backend: `POST /api/wallets/transfers/`, `GET /api/wallets/{id}/transfers/`
- Frontend: "Transfer" action in the wallet page header; simplified dialog (from/to wallet, amount, date, note)
- Transfers shown as a distinct row type in the transaction list (e.g. "→ Savings" label)

**Files:** `wallets/models.py`, `wallets/serializers.py`, `wallets/views.py`, `wallets/urls.py`, `frontend/app/wallet/[id]/page.tsx`, new `frontend/components/WalletTransferDialog.tsx`

---

### 2. Custom Date Range View — Priority 3 · Complexity 2

**What:** A third mode on the wallet page alongside month view and search: pick an arbitrary start and end date (e.g. Jan–Mar 2025) and see the full transaction list + totals for that period.

**Scope:**
- Frontend: date range picker in the wallet page header; reuses existing transaction list; totals recalculated for the range
- Backend: extend the search endpoint with `date_from` / `date_to` (already supported) — no backend changes needed

**Files:** `frontend/app/wallet/[id]/page.tsx`

---

### 3. Savings Goals — Priority 3 · Complexity 3

**What:** Set a named savings target (e.g. "Vacation fund — €5,000 by Dec 2026") linked to a wallet. Track progress as the wallet balance grows toward the target.

**Scope:**
- New model: `SavingsGoal(wallet, name, target_amount, target_date, created_at)`
- Backend: CRUD endpoints under `/api/wallets/{id}/goals/`
- Frontend: goals section on the wallet page or dashboard; progress bar showing current balance vs target; days remaining label

**Files:** `wallets/models.py`, `wallets/serializers.py`, `wallets/views.py`, `wallets/urls.py`, new `frontend/components/SavingsGoals.tsx`, `frontend/app/wallet/[id]/page.tsx`

---

### AI Features

#### 4. AI Auto-categorization — Priority 3 · Complexity 3

**What:** When adding a transaction (or importing via CSV), use Claude to suggest a category based on the note text. Also expose a "Categorize all uncategorized" bulk action.

**Scope:**
- Backend: `POST /api/wallets/categorize/` — accepts a note, returns ranked category suggestions; the user's own categories are passed as context so suggestions are personalized
- Frontend: suggestion chip(s) below the category picker in `TransactionDialog`; bulk-categorize button on wallet page

**Files:** new `wallets/ai.py`, `wallets/views.py`, `wallets/urls.py`, `frontend/components/TransactionDialog.tsx`, `frontend/app/wallet/[id]/page.tsx`

---

#### 5. AI Receipt Scan — Priority 3 · Complexity 3

**What:** Upload a photo of a receipt; Claude extracts the merchant, amount, date, and category from the image and pre-fills the transaction form.

**Scope:**
- Backend: `POST /api/wallets/{id}/receipts/scan/` — accepts an image file, calls Claude vision API, returns extracted fields (amount, date, note/merchant, suggested category)
- Frontend: camera/upload button in `TransactionDialog` (create mode); scanned fields are injected into the form with visual confirmation step before saving; image stored on server and linked to the transaction

**Files:** new `wallets/ai.py` (shared with auto-categorization), `wallets/views.py`, `wallets/urls.py`, `wallets/models.py` (optional `receipt_image` field on `Transaction`), `frontend/components/TransactionDialog.tsx`

---

#### 6. AI Budget Recommendations — Priority 2 · Complexity 2

**What:** After 2–3 months of spending history, surface suggestions for budget limits: "You typically spend ~€280/mo on dining — want to set that as your budget?" Shown as dismissible cards inside `BudgetPanel` when no budget exists for a category.

**Scope:**
- Backend: `GET /api/wallets/{id}/budgets/recommendations/` — computes 3-month average spend per category, calls Claude to generate a one-line rationale per suggestion
- Frontend: suggestion cards at the bottom of `BudgetPanel`; one-click "Set this limit" action

**Files:** `wallets/views.py`, `wallets/urls.py`, `wallets/ai.py`, `frontend/components/BudgetPanel.tsx`, `frontend/api/budgets.ts`

---

#### 7. AI Chat & Financial Tips — Priority 3 · Complexity 4

**What:** A persistent chat panel where users can ask natural-language questions about their finances ("How does this month compare to last?" / "What's my biggest expense this year?") and receive proactive tips ("You're spending 40% more on dining than usual — here are three ways to cut back").

**Scope:**
- Backend: `POST /api/chat/` — accepts a user message, retrieves relevant financial context (balance, category totals, budget status, recent transactions) and passes it to Claude with tool use; streaming response
- Frontend: collapsible chat widget accessible from the dashboard and wallet pages; chat history persisted in `localStorage`; proactive tips surface as dismissible cards on the dashboard

**Files:** new `wallets/ai.py` (shared), `wallets/views.py`, `wallets/urls.py`, new `frontend/components/AIChat.tsx`, `frontend/app/dashboard/page.tsx`

---

### 8. Toast Messages — Priority 4 · Complexity 1

**What:** Consistent, dismissible toast notifications for all user-initiated actions (save, delete, error, import complete, etc.) using the shadcn/ui `Toaster`.

**Scope:**
- Add `<Toaster />` to the root layout
- Replace inline error states and silent successes across all pages and dialogs with `toast()` calls
- Error toasts stay until dismissed; success toasts auto-dismiss after 3s

**Files:** `frontend/app/layout.tsx`, `frontend/components/TransactionDialog.tsx`, `frontend/app/wallet/[id]/page.tsx`, `frontend/app/settings/page.tsx`, and any other page with user-initiated mutations

---

### 9. CSV Export — Priority 3 · Complexity 1

**What:** Download a wallet's transactions as a CSV file.

**Scope:**
- Backend: `GET /api/wallets/{id}/export/?month=M&year=Y` — returns a CSV response; omit params for all-time export
- Frontend: Export button on wallet page next to Import CSV

**Files:** `wallets/views.py`, `wallets/urls.py`, `frontend/app/wallet/[id]/page.tsx`

---

### 10. Over-budget Alerts — Priority 3 · Complexity 2

**What:** Notify the user when spending in a budgeted category crosses the limit mid-month.

**Scope:**
- In-app: highlighted row + toast when a category tips over budget (leverages `is_over_budget` from the summary endpoint)
- Optional email: weekly digest of over-budget categories via Django email + a management command

**Files:** `frontend/components/BudgetPanel.tsx`, `frontend/app/wallet/[id]/page.tsx`; email requires new Django task/signal

---

### 11. Auth & Account Management — Priority 3 · Complexity 3

**What:** Allow login with either email or username. Add email verification on registration, password reset via email, and an account deletion flow.

**Scope:**
- Backend: custom `AuthenticationBackend` that accepts either username or email in the token endpoint; email verification token sent on `POST /api/register/`; `POST /api/password-reset/` and `POST /api/password-reset/confirm/`; `DELETE /api/account/` for GDPR-compliant account + data deletion
- Frontend: registration page (if not yet present); "Forgot password" flow; account deletion option in settings

**Files:** `backend/auth_backends.py` (new), `wallets/views.py`, `wallets/urls.py`, `frontend/app/login/page.tsx`, new `frontend/app/register/page.tsx`, `frontend/app/settings/page.tsx`

---

### 12. Feature Flags — Priority 2 · Complexity 2

**What:** A simple on/off system to enable or disable features globally (or per user for gradual rollouts), without a code deploy.

**Scope:**
- New model: `FeatureFlag(name, is_enabled, description)` — managed via Django admin
- Backend: `GET /api/feature-flags/` returns the flag map for the current user; middleware reads flags on each request
- Frontend: `useFeatureFlag('ai-chat')` hook gates UI rendering; flags fetched once on app load and cached

**Files:** `wallets/models.py`, `wallets/views.py`, `wallets/urls.py`, new `frontend/hooks/useFeatureFlag.ts`, `frontend/app/layout.tsx`

---

### 13. Production Readiness — Priority 5 · Complexity 5

📋 **Quick Reference:** See [PRODUCTION_CHECKLIST.md](./PRODUCTION_CHECKLIST.md) for a prioritized action list.

**What:** All the work needed to safely deploy the app publicly: infrastructure hardening, data security, legal compliance, and observability.

**Scope:**

*Infrastructure:*
- Switch SQLite → PostgreSQL for production
- Separate `settings/dev.py` and `settings/prod.py`; secrets via environment variables only
- Static file serving via WhiteNoise or a CDN
- HTTPS enforced; HSTS header set
- Health check endpoint (`GET /api/health/`)
- Database backups (automated daily, offsite)

*Security:*
- Rate limiting on auth endpoints (`/api/token/`, `/api/register/`)
- CORS locked to the production frontend origin
- All secret keys, DB credentials, and API keys read from env vars
- Input sanitisation and SQL injection review
- Dependency audit (`pip-audit`, `npm audit`)

*Legal & compliance (GDPR):*
- Privacy policy page
- Terms of service page
- User data export endpoint (GDPR Article 20) — `GET /api/account/export/` returns all user data as JSON/CSV
- Account + data deletion (see Auth & Account Management #12)
- Cookie consent banner if any third-party analytics are added

*Observability:*
- Sentry integration (backend + frontend) for error tracking
- Structured logging on the backend
- Basic uptime monitoring

**Files:** `backend/settings/prod.py`, `backend/settings/dev.py`, `backend/wallets/views.py`, new `frontend/app/privacy/page.tsx`, new `frontend/app/terms/page.tsx`, `frontend/app/layout.tsx`

---

## Bugs

| Bug | Where | Notes |
|---|---|---|
| Future-dated transactions reset to today after saving | `TransactionDialog.tsx` + `TransactionSerializer` | Transaction `date` field uses `default=timezone.now` which may be overwritten on edit; investigate form submission flow |

---

## Backlog / Ideas

- Bank CSV presets (PKO, mBank, ING, Santander — auto-fill column mapping on import)
- Open Banking API integration (Plaid / real-time sync)
- Multi-currency wallet support (wallet holds multiple currencies natively, beyond exchange rates)
- Shared wallets (multiple users with access to the same wallet)
- Mobile-responsive improvements
- Native mobile app (React Native or PWA)
