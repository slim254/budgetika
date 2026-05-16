# Custom Date Range View — Design Spec

**Date:** 2026-05-16  
**Feature:** Custom Date Range View  
**Priority:** 3 · **Complexity:** 2

## Overview

Add a custom date range selector to the wallet page as an alternative to month view. Users can pick arbitrary start and end dates (e.g., Jan–Mar 2025) to view transactions and financial totals for that period.

## User Problem

Currently, users can view transactions by:
1. **Month view** — Pick a single month
2. **Search view** — Full-text search with filters across all time

But they can't easily answer questions like "How much did I spend Jan–Mar?" or "Show me Q1 activity." Custom date range fills that gap.

## Design

### State & Modes

The wallet page will have two mutually exclusive time-period viewing modes:
- **Month mode** — Pick a specific month/year; fetch from `GET /api/wallets/{id}/transactions/?month=M&year=Y`
- **Date Range mode** — Pick start/end dates; fetch from `GET /api/wallets/{id}/transactions/search/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`

(Search mode remains separate and unchanged.)

A toggle button in the header allows switching between Month and Date Range modes.

### Components

#### `DateSelector` (refactored `MonthSelector`)

Replaces `MonthSelector.tsx`. Provides two UIs:

**Month mode:**
- Dropdown or popover showing month/year pickers (existing UI)
- Current behavior: clicking month/year updates URL params and refetches

**Date Range mode:**
- Two shadcn `Popover` + `Calendar` components for start/end dates
- Start date picker opens when user clicks the start date field
- End date picker opens when user clicks the end date field
- Validation: if end < start, disable the apply/confirm action
- On date selection, refetch transactions immediately

**Toggle:**
- Small button or chip inside the selector (e.g., "Month" / "Custom Range") to switch modes
- State: `rangeMode: boolean` (or enum for future extensibility)

#### Wallet Page Integration

**State additions:**
- `rangeMode: boolean` — whether date range or month view is active
- `dateRange: { from: Date | null, to: Date | null }` — selected date range

**Conditional rendering:**
- If `rangeMode`: show `DateSelector` in range mode; fetch with date filters
- If not `rangeMode`: show `DateSelector` in month mode; fetch with month/year params
- Budget panel hidden when `rangeMode` is true (budgets are per-month)
- Totals cards always shown; recalculated for the active period

**Data fetching:**
- Month mode: `fetchTransactions()` uses existing endpoint
- Date Range mode: new `fetchTransactionsByDateRange(from, to)` uses search endpoint with no query string, only date filters

### Display & UX

**Header area (below wallet title):**
- Same summary cards as month view: Initial Value, Total Income, Total Expenses
- Values recalculated for the selected date range
- Optional breadcrumb/label: "Showing Jan 1–Mar 31, 2025" for clarity

**Transaction table:**
- Identical to month/search view
- Lists all transactions in the date range
- Edit/delete actions unchanged

**Budget panel:**
- Hidden in date range mode (no change to budget logic, just visibility)

**Search mode button:**
- Still available as a separate third option; unchanged

### Edge Cases & Validation

1. **Invalid range** — If end date < start date, show validation error and disable/grey out the confirm button
2. **Same-day range** — Allowed (shows transactions from that single day)
3. **Very large range** — No pagination changes; search endpoint handles cursor-based pagination (already implemented)
4. **No transactions in range** — Show the same empty state message as month view
5. **Switching modes** — Toggling between month and date range clears the opposite mode's state to avoid stale data

### Files to Modify

- `frontend/components/MonthSelector.tsx` → refactor to `DateSelector.tsx` (or rename in place)
- `frontend/app/wallet/[id]/page.tsx` — integrate new component, add date range state, new fetch function
- No backend changes (search endpoint already supports `date_from`/`date_to`)

### Success Criteria

- [x] User can toggle between Month and Date Range modes in the wallet header
- [x] Date range picker shows two calendars (start/end) with validation
- [x] Selecting a date range fetches and displays transactions for that range
- [x] Summary totals (income/expenses) recalculate for the selected range
- [x] Budget panel is hidden in date range mode
- [x] Switching back to month mode clears date range state
- [x] Works with existing search/filter flow (no backend changes needed)

### Non-Goals

- Custom range view does not affect search mode (which remains a full-featured filter view)
- No preset ranges (e.g., "This quarter," "Last 30 days") in the initial implementation
- Date range is not persisted in URL (toggling to month view resets the range)

