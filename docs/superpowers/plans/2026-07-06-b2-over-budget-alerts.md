# B2 — Over-budget Alerts (in-app) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. One light backend regression test; the frontend is a badge + toast with a manual check. Steps use checkbox (`- [ ]`).

**Goal:** The user is warned that a category is over budget **without having to expand the collapsed Budget panel** — via a count badge on the panel header and a toast when over-budget categories exist for the viewed month.

**Architecture:** No new backend logic — `BudgetSummaryView` (`GET /api/wallets/{id}/budgets/summary/`) already returns `is_over_budget` per category (see `BudgetSummarySerializer`). Today `BudgetPanel` only fetches that summary when expanded, and shows a red bar/text **inside** the (possibly collapsed) panel. This plan makes the panel fetch on mount so it can surface an over-budget **badge** in the header and fire a **toast** on load. The email digest variant stays out of scope (Later — needs SMTP).

**Tech Stack:** Next.js 15, `sonner`; Django/DRF (test only).

## Global Constraints

- Reuse the existing `getBudgetSummary(walletId, month, year)` API helper and `BudgetSummaryItem` type.
- Budgets are per-month; keep the existing behaviour that the panel is hidden in custom date-range mode.
- Branch: `feat/over-budget-alerts`.

---

### Task 1: Backend regression test for `is_over_budget`

**Files:**
- Create: `backend/tests/wallets/test_budget_over.py`

This anchors the data contract the frontend depends on. (No production code changes — the endpoint already computes it.)

- [ ] **Step 1: Write the test**

```python
from datetime import date, datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from wallets.models import BudgetRule, Transaction, TransactionCategory, Wallet


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class TestOverBudgetSummary(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bud", password="pass")
        self.wallet = Wallet.objects.create(
            name="Main", user=self.user, initial_value=0, currency="usd"
        )
        self.cat = TransactionCategory.objects.create(user=self.user, name="Dining")
        BudgetRule.objects.create(
            wallet=self.wallet, category=self.cat,
            amount="100.00", start_date=date(2026, 6, 1),
        )
        # Spend 150 in June 2026 → over the 100 limit
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user, category=self.cat,
            note="dinner", amount="-150.00", currency="usd",
            date=timezone.make_aware(datetime(2026, 6, 10, 20, 0)),
        )
        self.client = auth_client(self.user)

    def test_summary_flags_over_budget(self):
        response = self.client.get(
            f"/api/wallets/{self.wallet.id}/budgets/summary/?month=6&year=2026"
        )
        self.assertEqual(response.status_code, 200)
        dining = next(i for i in response.data if i["category"]["name"] == "Dining")
        self.assertTrue(dining["is_over_budget"])
```

- [ ] **Step 2: Run — expect pass immediately** (documents existing behaviour)

```bash
cd backend && source venv/bin/activate
python manage.py test tests.wallets.test_budget_over -v 2
```
Expected: `OK`. If it fails, STOP — the summary contract differs from this plan's assumption; escalate.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/wallets/test_budget_over.py
git commit -m "test: assert budget summary flags over-budget categories"
```

---

### Task 2: Over-budget badge + toast in BudgetPanel

**Files:**
- Modify: `frontend/components/BudgetPanel.tsx`

- [ ] **Step 1: Fetch the summary on mount, not only when expanded**

Replace:
```typescript
  useEffect(() => {
    if (expanded) fetchSummary();
  }, [expanded, fetchSummary]);
```
with:
```typescript
  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);
```
(The detailed list is still gated behind `expanded` in the JSX; only the fetch moves.)

- [ ] **Step 2: Add imports and derive the over-budget set**

Add to the imports at the top:
```typescript
import { useRef } from "react";
import { toast } from "sonner";
```
Inside the component, after the `summary` state is declared, add:
```typescript
  const overBudget = summary.filter((i) => i.is_over_budget);
  const toastedKey = useRef<string>("");
```

- [ ] **Step 3: Toast once per month when over budget**

Add this effect after the existing effects:
```typescript
  useEffect(() => {
    const key = `${walletId}-${year}-${month}`;
    if (overBudget.length > 0 && toastedKey.current !== key) {
      toastedKey.current = key;
      toast.error(
        overBudget.length === 1
          ? `Over budget: ${overBudget[0].category.name}`
          : `${overBudget.length} categories over budget`
      );
    }
  }, [overBudget, walletId, year, month]);
```

- [ ] **Step 4: Show a count badge on the collapsed header**

In the header, replace the toggle button's label line:
```tsx
            Budget
          </button>
```
with:
```tsx
            Budget
            {overBudget.length > 0 && (
              <span className="ml-1 inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                {overBudget.length} over
              </span>
            )}
          </button>
```
(The badge must sit inside the toggle `button`; the button already uses `flex items-center gap-2`, so it aligns.)

- [ ] **Step 5: Verify**

```bash
cd frontend && npm run lint && npm run build
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/BudgetPanel.tsx
git commit -m "feat: over-budget badge and toast on budget panel"
```

---

### Task 3 (stretch): Refresh alerts after a transaction changes

Optional. Without it, the badge/toast refresh on month/wallet change and page load — good enough for MVP. To refresh immediately after adding/deleting a transaction:

**Files:**
- Modify: `frontend/components/BudgetPanel.tsx` (add a `refreshKey?: number` prop, include it in the `fetchSummary` effect deps)
- Modify: `frontend/app/wallet/[id]/page.tsx` (hold a `budgetRefresh` counter in state, bump it in the transaction save/delete handlers, pass it as `refreshKey` to `<BudgetPanel>`)

- [ ] **Step 1: Add the prop and dep**

In `BudgetPanel` props add `refreshKey?: number;`. Change the mount effect to:
```typescript
  useEffect(() => {
    fetchSummary();
  }, [fetchSummary, refreshKey]);
```

- [ ] **Step 2: Bump on mutation in the wallet page**

Add `const [budgetRefresh, setBudgetRefresh] = useState(0);`, call `setBudgetRefresh((n) => n + 1);` after successful transaction create/delete, and pass `refreshKey={budgetRefresh}` to `<BudgetPanel ... />`.

- [ ] **Step 3: Verify + commit**

```bash
cd frontend && npm run lint && npm run build
git add frontend/components/BudgetPanel.tsx frontend/app/wallet/[id]/page.tsx
git commit -m "feat: refresh over-budget alerts after transaction changes"
```
