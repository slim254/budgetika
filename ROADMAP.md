# Roadmap

> **Self-Host Program (2026-07-06):** Personal self-hosting on a Linux mini PC, split into **MVP** (run it + daily-use polish + AI auto-categorize — done) and **Later** (auth, feature flags, remaining AI, production hardening — not started). See `HANDOFF.md` for the batch order and `docs/superpowers/specs/2026-07-06-selfhost-feature-completion-design.md` for the design. **AI provider = OpenAI** (the LLM layer is provider-agnostic).
>
> **MVP batches (all done):** B0 self-host foundation · B1a future-date bug · B1b finish toast rollout · B1c CSV export · B2 over-budget alerts · B3a LLM layer (OpenAI) · B3b AI auto-categorize.
> **Corrections found while planning:** `POST /api/register/` was never implemented (docs claimed otherwise — now fixed); toasts are already wired (`<Toaster/>` in `layout.tsx`) so B1b only finishes the rollout.

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
| Wallet-to-wallet Transfers | Two `Transaction` records linked via shared `transfer_ref` UUID and bidirectional `transfer_peer` FK. Backend endpoints: `POST /api/wallets/transfers/`, `PATCH /api/wallets/transfers/{ref}/`, `DELETE /api/wallets/transfers/{ref}/`. Frontend: "Transfer" button in wallet header, `WalletTransferDialog` with exchange rate auto-fill (300ms debounce) and manual override, distinct row rendering with arrow icon and directional labels. Cross-currency support with Frankfurter integration. |
| Custom Date Range View | Third mode on wallet page alongside month view and search. `DateSelector` component toggles between month/year picker and two date range pickers (start/end). Transactions fetched via search endpoint with `date_from`/`date_to` filters. Summary totals recalculate for selected range. Budget panel hides in range mode (budgets are per-month). Date validation prevents invalid ranges. |
| Savings Goals | Per-wallet financial planning targets (e.g., "Wedding €500 by May 25"). System calculates required monthly savings rate across all active goals. Status: active, completed, missed (missed if target_date < today). No allocation mechanics — goals are forecasts, not fund reservations. |
| Self-host foundation | Django settings read from `.env` via `django-environ` (dev-safe fallbacks); unauthenticated `GET /api/health/` endpoint; configurable frontend API base URL via `NEXT_PUBLIC_API_URL`; `RUNBOOK.md` for mini-PC setup. |
| Future-date bug fix | `TransactionSerializer` now accepts date-only input so future-dated transactions persist instead of resetting to today on save. |
| Toast rollout | `sonner` toasts wired across all remaining dialogs and settings mutations (wallet, transaction, CSV import, budget). |
| CSV Export | `GET /api/wallets/{id}/export/?month=M&year=Y` returns a CSV response (omit params for all-time); Export button on wallet page next to Import CSV. |
| Over-budget Alerts | In-app highlighted row + toast when a budgeted category crosses its limit mid-month, driven by `is_over_budget` on the budget summary endpoint. |
| LLM Abstraction & Usage Tracking | `LLMProvider` protocol + `OpenAIAdapter` in `wallets/ai.py`; `AIService.complete()` enforces per-user monthly token quotas, logs every call to `AIUsageLog`, returns warnings at 80%/95% thresholds; `QuotaExceededError` → HTTP 429; pricing in `ModelPricing`; `GET /api/ai/quota/`. |
| AI Auto-categorization | `POST /api/wallets/categorize/` suggests a category from note text using the user's own categories as context; suggestion chip in `TransactionDialog`. |
| CSV Import AI Categorization | Whole-row, batched, review-step AI categorization during CSV import. `POST /api/wallets/{id}/import/categorize/` returns one suggestion per **unique** row description (deduped, excluding date/amount) constrained to the user's existing categories; execute applies the reviewed map via `ai_categories`. Builds on the LLM Abstraction + note auto-categorize. New "AI Categorize" step in `CSVImportDialog` with per-description override dropdowns. Quota exhaustion is non-fatal. |

---

## Build Order

MVP batches (LLM Abstraction, AI Auto-categorization, Toast Messages, CSV Export, Over-budget Alerts) are done — see Completed table above. Remaining, in order:

| # | Feature | Priority | Complexity | Why this order |
|---|---|---|---|---|
| 1 | AI Receipt Scan | 3 | 3 | Removes manual entry friction; pairs with auto-categorization. |
| 2 | AI Budget Recommendations | 2 | 2 | Needs spending history; easy follow-on to budget feature. |
| 3 | AI Chat & Financial Tips | 3 | 4 | Highest perceived value; more complex to do well. |
| 4 | Auth & Account Management | 3 | 3 | Login with username or email, email verification, password reset. |
| 5 | Feature Flags | 2 | 2 | Enables safe rollout of new features before production. |
| 6 | Production Readiness | 5 | 5 | Security, compliance, infra hardening before public launch. |

---

## Active Features

### AI Features

LLM Abstraction & Usage Tracking and AI Auto-categorization are done — see Completed table above.

#### 1. AI Receipt Scan — Priority 3 · Complexity 3

**What:** Upload a photo of a receipt; Claude extracts the merchant, amount, date, and category from the image and pre-fills the transaction form.

**Scope:**
- Backend: `POST /api/wallets/{id}/receipts/scan/` — accepts an image file, calls Claude vision API, returns extracted fields (amount, date, note/merchant, suggested category)
- Frontend: camera/upload button in `TransactionDialog` (create mode); scanned fields are injected into the form with visual confirmation step before saving; image stored on server and linked to the transaction

**Files:** new `wallets/ai.py` (shared with auto-categorization), `wallets/views.py`, `wallets/urls.py`, `wallets/models.py` (optional `receipt_image` field on `Transaction`), `frontend/components/TransactionDialog.tsx`

---

#### 2. AI Budget Recommendations — Priority 2 · Complexity 2

**What:** After 2–3 months of spending history, surface suggestions for budget limits: "You typically spend ~€280/mo on dining — want to set that as your budget?" Shown as dismissible cards inside `BudgetPanel` when no budget exists for a category.

**Scope:**
- Backend: `GET /api/wallets/{id}/budgets/recommendations/` — computes 3-month average spend per category, calls Claude to generate a one-line rationale per suggestion
- Frontend: suggestion cards at the bottom of `BudgetPanel`; one-click "Set this limit" action

**Files:** `wallets/views.py`, `wallets/urls.py`, `wallets/ai.py`, `frontend/components/BudgetPanel.tsx`, `frontend/api/budgets.ts`

---

#### 3. AI Chat & Financial Tips — Priority 3 · Complexity 4

**What:** A persistent chat panel where users can ask natural-language questions about their finances ("How does this month compare to last?" / "What's my biggest expense this year?") and receive proactive tips ("You're spending 40% more on dining than usual — here are three ways to cut back").

**Scope:**
- Backend: `POST /api/chat/` — accepts a user message, retrieves relevant financial context (balance, category totals, budget status, recent transactions) and passes it to Claude with tool use; streaming response
- Frontend: collapsible chat widget accessible from the dashboard and wallet pages; chat history persisted in `localStorage`; proactive tips surface as dismissible cards on the dashboard

**Files:** new `wallets/ai.py` (shared), `wallets/views.py`, `wallets/urls.py`, new `frontend/components/AIChat.tsx`, `frontend/app/dashboard/page.tsx`

---

Toast Messages, CSV Export, and Over-budget Alerts are done — see Completed table above. (Over-budget's optional weekly email digest was not built.)

### 4. Auth & Account Management — Priority 3 · Complexity 3

**What:** Allow login with either email or username. Add email verification on registration, password reset via email, and an account deletion flow.

**Scope:**
- Backend: custom `AuthenticationBackend` that accepts either username or email in the token endpoint; email verification token sent on `POST /api/register/`; `POST /api/password-reset/` and `POST /api/password-reset/confirm/`; `DELETE /api/account/` for GDPR-compliant account + data deletion
- Frontend: registration page (if not yet present); "Forgot password" flow; account deletion option in settings

**Files:** `backend/auth_backends.py` (new), `wallets/views.py`, `wallets/urls.py`, `frontend/app/login/page.tsx`, new `frontend/app/register/page.tsx`, `frontend/app/settings/page.tsx`

---

### 5. Feature Flags — Priority 2 · Complexity 2

**What:** A simple on/off system to enable or disable features globally (or per user for gradual rollouts), without a code deploy.

**Scope:**
- New model: `FeatureFlag(name, is_enabled, description)` — managed via Django admin
- Backend: `GET /api/feature-flags/` returns the flag map for the current user; middleware reads flags on each request
- Frontend: `useFeatureFlag('ai-chat')` hook gates UI rendering; flags fetched once on app load and cached

**Files:** `wallets/models.py`, `wallets/views.py`, `wallets/urls.py`, new `frontend/hooks/useFeatureFlag.ts`, `frontend/app/layout.tsx`

---

### 6. Production Readiness — Priority 5 · Complexity 5

📋 **Quick Reference:** See [PRODUCTION_CHECKLIST.md](./PRODUCTION_CHECKLIST.md) for a prioritized action list.

**What:** All the work needed to safely deploy the app publicly: infrastructure hardening, data security, legal compliance, and observability.

**Scope:**

*Infrastructure:*
- Switch SQLite → PostgreSQL for production
- Separate `settings/dev.py` and `settings/prod.py`; secrets via environment variables only
- Static file serving via WhiteNoise or a CDN
- HTTPS enforced; HSTS header set
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
- Account + data deletion (see Auth & Account Management #4)
- Cookie consent banner if any third-party analytics are added

*Observability:*
- Sentry integration (backend + frontend) for error tracking
- Structured logging on the backend
- Basic uptime monitoring

**Files:** `backend/settings/prod.py`, `backend/settings/dev.py`, `backend/wallets/views.py`, new `frontend/app/privacy/page.tsx`, new `frontend/app/terms/page.tsx`, `frontend/app/layout.tsx`

---

## Backlog / Ideas

- Bank CSV presets (PKO, mBank, ING, Santander — auto-fill column mapping on import)
- Open Banking API integration (Plaid / real-time sync)
- Multi-currency wallet support (wallet holds multiple currencies natively, beyond exchange rates)
- Shared wallets (multiple users with access to the same wallet)
- Mobile-responsive improvements
- Native mobile app (React Native or PWA)
