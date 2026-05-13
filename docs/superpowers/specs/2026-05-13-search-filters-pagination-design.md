# Search & Filters + Pagination — Design Spec

**Date:** 2026-05-13
**Status:** Approved

---

## Overview

Add search, filtering, and infinite-scroll pagination to the wallet transaction view. The existing month/year view is preserved unchanged. A new "Search all transactions" mode gives users a way to query across all time with multiple filter criteria.

---

## Architecture

Dual-mode wallet page backed by a new dedicated search endpoint. The month view and search view are cleanly separated — no shared conditional logic.

```
Month mode  →  existing WalletTransactionList (?month=M&year=Y)
Search mode →  new WalletTransactionSearch     (?search=&category=&tag=&date_from=&date_to=&min_amount=&max_amount=&cursor=)
```

---

## Backend

### New endpoint

`GET /api/wallets/{wallet_id}/transactions/search/`

**Query parameters** (all optional):

| Param | Type | Description |
|---|---|---|
| `search` | string | Case-insensitive substring match on `note` |
| `category` | UUID | Exact match on `category_id` |
| `tag` | UUID | Filters transactions that have this tag (M2M) |
| `date_from` | ISO date | Inclusive lower bound on `date` |
| `date_to` | ISO date | Inclusive upper bound on `date` |
| `min_amount` | decimal | Inclusive lower bound on `amount` |
| `max_amount` | decimal | Inclusive upper bound on `amount` |
| `cursor` | string | Opaque cursor for pagination (managed by DRF) |

**Pagination:** DRF `CursorPagination`, page size 25, ordering `('-date', '-id')` for stable sort.

**Response shape:**
```json
{
  "next": "<cursor URL or null>",
  "previous": "<cursor URL or null>",
  "results": [ ...transactions ]
}
```

**Implementation:**

- New `WalletTransactionSearch` view extending `generics.ListAPIView`
- Custom `TransactionCursorPagination(CursorPagination)` with `page_size = 25` and `ordering = ('-date', '-id')`
- `get_queryset` chains `.filter()` calls for each present param
- Scoped to the authenticated user's wallet (same ownership check as existing views)
- No new model or migration required

**Files changed:**
- `backend/wallets/views.py` — add `TransactionCursorPagination`, `WalletTransactionSearch`
- `backend/wallets/urls.py` — add route `<uuid:wallet_id>/transactions/search/`

---

## Frontend

### Two modes on the wallet page

Mode is stored in local component state (not the URL).

**Month mode (default)**
- Existing month/year picker + transaction table, unchanged
- New "Search all transactions" button in the header area, next to the month picker
- Clicking it activates search mode

**Search mode**
- Month picker replaced by a search bar + "Filters" button
- "← Back to month view" link returns to month mode and clears all filters

```
[← Month view]   [Search notes...________] [Filters ②]
──────────────────────────────────────────────────────
Transaction rows
Transaction rows
[spinner — visible when fetching next page near bottom]
```

The badge on the Filters button shows the count of active filters.

### Filter panel

A shadcn `Sheet` component (slides in from the right) containing:

| Control | Filter param |
|---|---|
| Category dropdown (single select) | `category` |
| Tag dropdown (single select) | `tag` |
| Date from / Date to (date inputs) | `date_from` / `date_to` |
| Min amount / Max amount (number inputs) | `min_amount` / `max_amount` |

- "Apply filters" button sends the current form state to the API
- "Clear all" link resets all filter fields and re-fetches
- Filters are applied on "Apply" click, not on every keystroke
- Search input debounces at 400ms (triggers a new fetch, resets cursor)

### Infinite scroll

An `IntersectionObserver` watches a sentinel `<div>` at the bottom of the transaction list. When it enters the viewport:
1. The next page is fetched using the `next` cursor URL from the last response
2. Results are appended to the existing list
3. A spinner is shown during the fetch
4. When `next` is null and at least one page has loaded, show "No more transactions"

### New components

- `TransactionSearch` (`frontend/components/TransactionSearch.tsx`) — search input + Filters button + Sheet panel with filter form

### Files changed

- `frontend/app/wallet/[id]/page.tsx` — mode toggle state, conditional rendering, fetch logic for both modes, `IntersectionObserver` sentinel
- `frontend/components/TransactionSearch.tsx` — new component

**No changes to:** `TransactionDialog`, categories page, tags page, settings page.

---

## Scope boundaries

- Search covers `note` text only (not category name, tag name)
- Single category filter (not multi-select)
- Single tag filter (not multi-select)
- No sorting controls (always newest first)
- No URL-based deep linking to search state
- Existing month view filters (month/year) are not extended
