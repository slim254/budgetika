# B1a — Fix "Future-dated transactions reset to today" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use **superpowers:systematic-debugging** first (this is a bug of not-yet-confirmed cause), then superpowers:executing-plans for the fix. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A transaction saved with a future (or any non-today) date keeps that date after saving.

**Architecture:** The cause is not confirmable offline, so this plan **reproduces first**, then branches to the matching fix. Leading hypothesis: the frontend posts `date` as a **date-only** string (`"YYYY-MM-DD"`, from `new Date().toISOString().split("T")[0]`) to a model `DateTimeField`, and DRF's default `DateTimeField` only accepts full ISO-8601 datetimes — so the value is rejected or dropped and the model's `default=timezone.now` fills in today.

**Tech Stack:** Django 5.1, DRF, Next.js 15.

## Global Constraints

- Amount convention unchanged (negative = expense).
- Do not change the `Transaction.date` model field type (`DateTimeField`) — other code (dashboards, search, month filters) depends on it.
- Branch: `fix/future-date-reset`.
- **If Task 1's observed failure mode does not match any branch below, STOP and escalate to the main session** — do not invent a fix.

---

### Task 1: Reproduce the bug with a failing backend test

**Files:**
- Create: `backend/tests/wallets/test_transaction_date.py`

- [ ] **Step 1: Write the reproduction test**

```python
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from wallets.models import Transaction, Wallet


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class TestFutureTransactionDate(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dateuser", password="pass")
        self.wallet = Wallet.objects.create(
            name="Main", user=self.user, initial_value=0, currency="usd"
        )
        self.client = auth_client(self.user)

    def test_future_date_only_string_is_preserved(self):
        """Frontend posts a date-only string. The stored date must match it,
        not reset to today."""
        future = timezone.now().date() + timedelta(days=40)
        payload = {
            "note": "future rent",
            "amount": "-100.00",
            "currency": "usd",
            "date": future.isoformat(),      # e.g. "2026-08-15" — date only
            "wallet": str(self.wallet.id),
        }
        response = self.client.post("/api/transactions/", payload, format="json")
        # Print the observed behaviour for the debugging log:
        print("STATUS:", response.status_code, "BODY:", response.data)
        self.assertEqual(response.status_code, 201)
        txn = Transaction.objects.get(id=response.data["id"])
        self.assertEqual(txn.date.date(), future)
```

- [ ] **Step 2: Run it and record the exact failure**

```bash
cd backend && source venv/bin/activate
python manage.py test tests.wallets.test_transaction_date -v 2
```

Read the printed `STATUS`/`BODY` and pick the branch:

| Observation | Root cause | Go to |
|---|---|---|
| `STATUS: 400` with a `date` error like "Datetime has wrong format" | DRF rejects date-only input | **Task 2A** |
| `STATUS: 201` but `txn.date.date()` == today (assertion fails on the date) | Date accepted but overwritten by the model default | **Task 2B** |
| `STATUS: 201` and the test **passes** | Backend is correct; the "reset" is a frontend display/refetch artifact | **Task 2C (escalate)** |

---

### Task 2A: Accept date-only input on the serializer (most likely)

**Files:**
- Modify: `backend/wallets/serializers.py` (`TransactionSerializer`)

- [ ] **Step 1: Add an explicit `date` field to `TransactionSerializer`**

In `TransactionSerializer` (after the `peer_wallet = serializers.SerializerMethodField()` line, before `class Meta`), add:

```python
    # Accept both full ISO-8601 datetimes and date-only strings ("YYYY-MM-DD"),
    # which is what the frontend date picker sends. Without "%Y-%m-%d" here,
    # DRF's default DateTimeField rejects date-only input.
    date = serializers.DateTimeField(
        required=False,
        input_formats=["iso-8601", "%Y-%m-%d"],
    )
```

`date` is already listed in `Meta.fields`, so no other change is needed.

- [ ] **Step 2: Run the reproduction test — expect pass**

```bash
python manage.py test tests.wallets.test_transaction_date -v 2
```
Expected: `Ran 1 test ... OK` (201 and the future date preserved).

- [ ] **Step 3: Guard against regressions — run the full suite**

```bash
python manage.py test tests -v 1
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add backend/wallets/serializers.py backend/tests/wallets/test_transaction_date.py
git commit -m "fix: accept date-only input so future transaction dates persist"
```

**Done.** (Optional hardening: also send a full ISO datetime from the frontend — see Task 2A-note below — but the serializer fix alone resolves the bug for all clients.)

> **Task 2A-note (optional):** In `frontend/components/TransactionDialog.tsx` `handleSubmit`, the payload uses `date: formData.date`. If you also want the frontend to send a timezone-safe datetime, add near the top of the file:
> ```typescript
> const toIsoDateTime = (d: string) => new Date(`${d}T12:00:00`).toISOString();
> ```
> and use `date: toIsoDateTime(formData.date)` in the transaction `payload` (leave the recurring `start_date` as `formData.date` — that field is a `DateField`). Anchoring to local noon prevents a midnight-UTC date from shifting a day. This is optional given the backend fix.

---

### Task 2B: Stop the model default from overwriting a provided date

**Files:**
- Modify: `backend/wallets/serializers.py` and/or `backend/wallets/views.py` (`TransactionCreate.perform_create`)

- [ ] **Step 1: Diagnose where the date is lost**

Add a temporary print in `TransactionSerializer.create` (in `backend/wallets/serializers.py`) right after `category_id = validated_data.pop('category_id', None)`:
```python
        print("VALIDATED DATE:", validated_data.get("date"))
```
Re-run the test from Task 1. If `VALIDATED DATE` is `None`, the date never reached the serializer → the field parsing dropped it → apply **Task 2A** instead (remove this print). If `VALIDATED DATE` shows the correct future date but the saved row is today, something in `perform_create`/signals overrides it — inspect `TransactionCreate.perform_create` (`backend/wallets/views.py:271`) and remove any `date=` override there.

- [ ] **Step 2: Remove the print, apply the identified fix, re-run**

```bash
python manage.py test tests.wallets.test_transaction_date -v 2
python manage.py test tests -v 1
```
Expected: both `OK`.

- [ ] **Step 3: Commit**

```bash
git add backend/wallets/ backend/tests/wallets/test_transaction_date.py
git commit -m "fix: preserve explicitly provided transaction date on create"
```

---

### Task 2C: Backend correct — escalate the frontend display artifact

If Task 1's test passed, the stored date is correct and the "reset" the user sees is the wallet page re-fetching only the **currently selected month** after save (`fetchTransactions` in `frontend/app/wallet/[id]/page.tsx` filters by month/year), so a future-month transaction simply disappears from the current view.

- [ ] **Step 1: Do not guess a UX fix. Escalate.** Report to the main session: "Backend preserves the date; the bug is that saving a transaction dated outside the viewed month hides it from the current list. Need a product decision: (a) toast 'Saved to <Month YYYY>', (b) jump the view to the saved transaction's month, or (c) leave as-is." Keep the passing test from Task 1 committed as a regression guard:

```bash
git add backend/tests/wallets/test_transaction_date.py
git commit -m "test: guard that future transaction dates are stored correctly"
```
