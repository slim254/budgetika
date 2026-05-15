# Exchange Rates — Design Spec

**Date:** 2026-05-14

## Overview

Add exchange rate support to enable two things:

1. **Dashboard total in a single currency** — the "Total Balance" card converts all wallet balances to a user-chosen base currency before summing, with a quick currency switcher.
2. **Cross-currency transaction entry** — when adding/editing a transaction, the user can enter an amount in a different currency and have it auto-converted to the wallet's currency on save. No original amount is stored.

Rates are fetched on-demand from [Frankfurter](https://www.frankfurter.app/) (ECB data, no API key) and cached in the DB.

---

## Backend

### New model: `ExchangeRate`

File: `wallets/models.py`

```
ExchangeRate
  base_currency   CharField(max_length=3)   — e.g. "pln"
  quote_currency  CharField(max_length=3)   — e.g. "eur"
  date            DateField
  rate            DecimalField(12, 6)
```

- Unique constraint on `(base_currency, quote_currency, date)`
- DB index on same triple for fast lookup
- Currency values use the same 4-choice set as the rest of the app: `usd`, `eur`, `gbp`, `pln`

### New model: `UserProfile`

File: `wallets/models.py`

```
UserProfile
  user                OneToOneField(User, on_delete=CASCADE)
  preferred_currency  CharField(max_length=3, choices=CURRENCY_CHOICES, null=True, blank=True)
```

- Created automatically via Django signal on user registration (same pattern as default categories in `wallets/signals.py`)

### Rate service

File: `wallets/services.py` — new function `get_rate(base: str, quote: str, date: date) -> Decimal`

Logic:
1. If `base == quote`, return `Decimal("1")`
2. Look up `ExchangeRate` for `(base, quote, date)`
3. If found, return `rate`
4. Fetch from `https://api.frankfurter.app/{date}?from={base}&to={quote}`
5. Store result in `ExchangeRate`, return rate

Frankfurter returns the closest available rate for weekends/holidays. After a fetch, store the rate for **both** the returned date and the requested date (if they differ) using `get_or_create` for each — this prevents repeated Frankfurter calls when the same weekend date is requested multiple times.

### New endpoint: `GET /api/exchange-rates/`

File: `wallets/views.py` + `wallets/urls.py`

Query params: `base`, `quote`, `date` (ISO format, defaults to today)

Response:
```json
{ "rate": "0.230000", "date": "2024-01-15" }
```

Auth required. Returns 400 on invalid/unsupported currency.

### New endpoints: `GET /PATCH /api/profile/`

File: `wallets/views.py` + `wallets/urls.py`

- `GET` returns `{ "preferred_currency": "pln" }` (or `null`). If no `UserProfile` row exists for the user (existing users pre-migration), return `{"preferred_currency": null}` — do not 404.
- `PATCH` accepts `{ "preferred_currency": "eur" }`, validates against allowed choices. Uses `get_or_create` on `UserProfile` so existing users without a profile row are handled gracefully.

Auth required.

### Dashboard endpoint update

File: `wallets/views.py` — `UserDashboard.get()`

- Accepts optional `?base_currency=pln` query param
- If provided, passes it to `DashboardService.user_summary(base_currency=...)`
- `DashboardService` converts each wallet's balance to `base_currency` using today's rate (via `get_rate`) before summing into `total_balance`
- Without the param, behaviour is unchanged (raw sum, no currency symbol)

### Migrations

One migration for `ExchangeRate` and `UserProfile` models.

---

## Frontend

### Dashboard currency switcher

File: `frontend/components/MetricsSummaryCards.tsx` + `frontend/app/dashboard/page.tsx`

- On dashboard load, `GET /api/profile/`
  - If `preferred_currency` is set → use it as `base_currency`
  - Otherwise → detect from `navigator.language`:
    - `pl*` → `pln`
    - `en-GB` → `gbp`
    - `de*`, `fr*`, `es*`, `it*`, `pt*` → `eur`
    - everything else → `usd`
- Pass `base_currency` as query param to `GET /api/dashboard/?base_currency=X`
- Show a small currency selector (4 options) next to the Total Balance card
- On change → `PATCH /api/profile/ { preferred_currency: X }` → refetch dashboard with new param
- Total Balance card shows the proper currency symbol/code once a base currency is active

### TransactionDialog — cross-currency entry

File: `frontend/components/TransactionDialog.tsx`

- Add a collapsible "Enter in a different currency" section below the amount field
- When expanded: currency selector (excludes wallet's currency) + amount input
- On amount or currency change: debounced (300ms) call to `/api/exchange-rates/?base={source}&quote={wallet_currency}&date={transaction_date}`
- Show live preview: `≈ 123.45 PLN` beneath the input
- On submit: send the **converted amount** in the wallet's currency — no original amount stored
- If the exchange rate fetch fails, show an inline error and block submit until resolved

---

## What does NOT change

- The currency constraint on `Transaction` (must match wallet currency) stays in place
- No stored `original_amount` or `rate_used` on transactions
- `TransactionSerializer.validate()` is unchanged

---

## Scope boundaries

- No bulk backfill of historical rates
- No rate history chart
- No multi-currency wallet (wallet currency is immutable)
- Dashboard currency switcher only affects the "Total Balance" card, not per-wallet balances
