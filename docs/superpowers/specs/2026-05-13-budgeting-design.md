# Budgeting — Per-Category Monthly Limits Design Spec

**Date:** 2026-05-13
**Status:** Approved

---

## Overview

Add per-category monthly budget limits to the wallet page. Users set a default monthly spending cap per category (repeating until an optional end date), with the ability to override the limit for any specific month. A collapsible panel on the wallet page shows progress against the budget for the selected month.

---

## Architecture

Two new backend models (`BudgetRule`, `BudgetMonthOverride`) plus a read-only summary endpoint that computes effective limits and spending per category for a given month. The frontend gains a collapsible panel on the wallet page and a budget management dialog.

```
BudgetRule          — the repeating default limit per category per wallet
BudgetMonthOverride — a one-off override for a specific month

Summary endpoint    — joins rules + overrides + transaction spending into one response
```

The wallet page already has a month selector; the budget panel respects it (shows limits and spending for the selected month, not just the current month).

**Amount convention:** limits are stored as positive decimals (e.g., `300.00`), representing a spending cap. Spending is computed as `abs(sum of negative transactions)` for that category in that month. Income transactions (positive amounts) in a budgeted category are ignored for budget calculations.

---

## Data Model

### `BudgetRule`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `wallet` | FK → Wallet | |
| `category` | FK → TransactionCategory | |
| `amount` | Decimal | Positive — the monthly spending limit |
| `start_date` | Date | First day of first applicable month |
| `end_date` | Date (nullable) | First day of last applicable month; null = no end |

**Constraint:** no two rules for the same wallet + category may have overlapping date ranges.

A rule is "active" for a given month if `start_date <= month_start AND (end_date IS NULL OR end_date >= month_start)`.

### `BudgetMonthOverride`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `wallet` | FK → Wallet | |
| `category` | FK → TransactionCategory | |
| `year` | Integer | |
| `month` | Integer | 1–12 |
| `amount` | Decimal | Positive |

**Unique together:** `(wallet, category, year, month)`

### On category deletion

Categories are soft-deleted (`is_archived=True`). Budget rules referencing an archived category remain in the DB and still display — the category name remains accessible. No cascade delete.

### `BudgetSummaryItem` (response shape, not a model)

```json
{
  "category": { "id": "", "name": "", "icon": "", "color": "" },
  "limit": "300.00",
  "spent": "180.50",
  "remaining": "119.50",
  "is_over_budget": false,
  "is_override": false,
  "rule_id": "<uuid>"
}
```

`remaining` is always `limit - spent`. When `spent > limit`, `remaining` is negative and `is_over_budget` is `true`. The frontend uses `is_over_budget` to switch the progress bar and label to red.

---

## API

All endpoints require JWT auth and are scoped to the authenticated user's wallets (same ownership check as existing wallet endpoints).

```
GET/POST         /api/wallets/{wallet_id}/budgets/
GET/PATCH/DELETE /api/wallets/{wallet_id}/budgets/{rule_id}/

GET/POST         /api/wallets/{wallet_id}/budgets/overrides/
DELETE           /api/wallets/{wallet_id}/budgets/overrides/{override_id}/

GET              /api/wallets/{wallet_id}/budgets/summary/?month=M&year=Y
```

### Rules (`/budgets/`)

Standard CRUD. `POST` body: `{ category, amount, start_date, end_date? }`. `start_date` and `end_date` are coerced to the first day of their respective month. Serializer validates no overlapping rules for the same wallet + category.

### Overrides (`/budgets/overrides/`)

`POST` body: `{ category, year, month, amount }`. Upsert-style — if an override already exists for that wallet + category + month + year, update it rather than return an error. Serializer validates that an active `BudgetRule` exists for that category + wallet before creating an override. `DELETE` removes it, reverting that month to the rule's amount.

### Summary (`/budgets/summary/`)

Read-only. Requires `?month=M&year=Y`. Returns a list of `BudgetSummaryItem` — one per active rule for that month, with spending computed from transactions. Only categories with an active rule (or override without a rule, which is not a valid state) appear.

---

## Frontend

### Wallet page — collapsible budget panel

Sits between the month selector and the transaction list. Collapsed by default; open/closed state persisted in `localStorage` per wallet. When expanded, fetches `/budgets/summary/?month=M&year=Y` for the currently selected month.

Each row shows:
- Category icon + name
- Progress bar (spent / limit), turns red when `spent > limit`
- `£180.50 / £300.00` label
- `£119.50 remaining` (or `£X over budget` in red)

"Manage budgets" button in the panel header opens the management dialog.

### Budget management dialog

Two tabs:

**Monthly limits tab** — lists all `BudgetRule`s for this wallet. Each row: category, amount, date range. Actions: edit (amount + dates), delete. "Add limit" button opens an inline form (category picker, amount, start month, optional end month).

**This month tab** — shows the same summary rows with an "Override" button per category. Clicking reveals an inline amount input pre-filled with the rule's amount. Saving creates/updates a `BudgetMonthOverride`. If an override already exists, the row is visually marked and has a "Remove override" link.

### New files

| File | Purpose |
|---|---|
| `frontend/components/BudgetPanel.tsx` | Collapsible panel |
| `frontend/components/BudgetManagementDialog.tsx` | Two-tab management dialog |
| `frontend/api/budgets.ts` | Typed fetch functions for all budget endpoints |

### Modified files

| File | Change |
|---|---|
| `frontend/app/wallet/[id]/page.tsx` | Add `BudgetPanel` between month selector and transaction list |
| `frontend/models/wallets.ts` | Add `BudgetRule`, `BudgetMonthOverride`, `BudgetSummaryItem` types |

---

## Error Handling

### Backend validation

- Overlapping rule date ranges for the same wallet + category → 400 with descriptive message
- `amount` must be positive → 400
- `end_date` before `start_date` → 400
- Cross-wallet ownership check → 404

### Frontend

- Summary fetch failure → panel shows error state with retry button
- Save/delete failures in dialog → inline toast (same pattern as existing transaction errors)
- Empty state: no budget rules exist → "No budgets set — click Manage budgets to add one"

---

## Testing

### Backend

New test class in `tests.py` covering:
- Summary computation (correct spending aggregation, correct limit resolution)
- Override takes precedence over rule for the same month
- Overlap validation rejects conflicting rules
- Auth and cross-user wallet isolation
- Edge cases: no transactions in a budgeted category (spent = 0), archived category rule still returns in summary

### Frontend

No unit tests — consistent with the rest of the project (no frontend test files exist).
