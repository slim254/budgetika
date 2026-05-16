# Wallet-to-Wallet Transfers — Design Spec

**Date:** 2026-05-16

---

## Overview

Record money moved between two of the user's own wallets as a linked pair of transactions — one debit in the source wallet, one credit in the destination wallet — so net worth is unaffected and the transfer is traceable in both transaction lists.

Supports same-currency and cross-currency transfers. Exchange rate is auto-filled from the existing Frankfurter cache; user can override the destination amount. No fee modelling — the user adjusts the received amount if needed.

---

## Data Model

Two nullable fields added to the existing `Transaction` model:

```python
transfer_ref  = models.UUIDField(null=True, blank=True, db_index=True)
transfer_peer = models.ForeignKey(
    'self', null=True, blank=True,
    on_delete=models.SET_NULL,
    related_name='transfer_peer_reverse'
)
```

A transfer is a pair of `Transaction` rows created atomically:

| Field | Debit leg (source wallet) | Credit leg (dest wallet) |
|---|---|---|
| `wallet` | source wallet | destination wallet |
| `amount` | negative (expense) | positive (income) |
| `currency` | source wallet currency | destination wallet currency |
| `date` | user-supplied | same |
| `note` | user-supplied | same |
| `category` | null | null |
| `transfer_ref` | shared UUID (new) | same UUID |
| `transfer_peer` | → credit row | → debit row |

**Edit and delete always operate on both legs atomically via `transfer_ref`.** No independent editing of individual legs.

No category or tag on transfer transactions.

---

## API

All endpoints require JWT auth.

```
POST   /api/wallets/transfers/           create a transfer
GET    /api/wallets/{id}/transfers/      list transfers for a wallet
PATCH  /api/wallets/transfers/{ref}/     edit both legs by transfer_ref
DELETE /api/wallets/transfers/{ref}/     delete both legs by transfer_ref
```

### POST payload

```json
{
  "from_wallet": "<uuid>",
  "to_wallet": "<uuid>",
  "from_amount": 500.00,
  "to_amount": 116.50,
  "date": "2026-05-16",
  "note": "Rent buffer"
}
```

- Both wallets must belong to the authenticated user (validated in serializer).
- `to_amount` is required from the frontend (user-visible and editable). If omitted, the view fills it using the cached Frankfurter rate.
- Response includes `transfer_ref` and a `peer_wallet` field on each leg so the frontend can render directional labels.

### PATCH payload

Same shape as POST. Both legs updated atomically.

### GET /api/wallets/{id}/transfers/

Returns transactions where `transfer_ref IS NOT NULL` and `wallet = id`, each annotated with `peer_wallet` name and currency.

---

## Frontend

### Entry point

"Transfer" button in the wallet page header, next to "Add transaction".

### WalletTransferDialog

Fields:
- **From wallet** — pre-filled with current wallet, read-only
- **To wallet** — dropdown of user's other wallets
- **Amount (from)** — number input, source currency label
- **Amount (to)** — auto-filled via Frankfurter with 300 ms debounce (same pattern as TransactionDialog); user can override
- **Date** — date picker, defaults to today
- **Note** — optional text

Edit mode: same dialog, pre-filled. Includes a Delete button with inline confirmation ("Delete both sides of this transfer?").

### Transaction list row

Transfer rows rendered inline in the existing transaction list with:
- `ArrowLeftRight` icon to distinguish from regular transactions
- Debit leg: `→ [Destination Wallet]  -500.00 PLN`
- Credit leg: `← [Source Wallet]  +116.50 EUR`
- No category or tag chips
- Clicking opens `WalletTransferDialog` in edit mode

---

## Files Changed

**Backend:**
- `wallets/models.py` — add `transfer_ref`, `transfer_peer` to `Transaction`
- `wallets/serializers.py` — `WalletTransferSerializer`
- `wallets/views.py` — `WalletTransferView` (create, list, edit, delete)
- `wallets/urls.py` — wire new endpoints
- `wallets/migrations/` — migration for new fields

**Frontend:**
- `frontend/components/WalletTransferDialog.tsx` — new component
- `frontend/app/wallet/[id]/page.tsx` — Transfer button in header; transfer row rendering in transaction list
- `frontend/api/transfers.ts` — API helpers (create, update, delete)
