# B1c — CSV Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Backend gets TDD; the frontend button gets a lint/build + manual check. Steps use checkbox (`- [ ]`).

**Goal:** Download a wallet's transactions as a CSV file — all-time, or filtered to a month/year.

**Architecture:** A DRF `GET /api/wallets/{wallet_id}/export/?month=M&year=Y` view streams a `text/csv` response with a `Content-Disposition: attachment` header. The frontend adds an "Export" button next to "Import CSV" that fetches the file as a blob and triggers a browser download.

**Tech Stack:** Django 5.1, DRF, Python `csv`, Next.js 15, axios.

## Global Constraints

- Columns: `date, amount, currency, note, category, tags`. Amount keeps its sign (negative = expense). Tags are `;`-joined names. Empty category → empty cell.
- Reuse the existing per-wallet ownership check pattern (`get_object_or_404(Wallet, id=..., user=request.user)`).
- Branch: `feat/csv-export`.

---

### Task 1: Export endpoint

**Files:**
- Modify: `backend/wallets/views.py`
- Modify: `backend/wallets/urls.py`
- Create: `backend/tests/wallets/test_csv_export.py`

**Interfaces:**
- Produces: `GET /api/wallets/{wallet_id}/export/` → `200`, `Content-Type: text/csv`, attachment.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime

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


class TestCSVExport(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="exp", password="pass")
        self.wallet = Wallet.objects.create(
            name="Main", user=self.user, initial_value=0, currency="usd"
        )
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user, note="salary",
            amount="1000.00", currency="usd",
            date=timezone.make_aware(datetime(2026, 6, 1, 9, 0)),
        )
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user, note="rent",
            amount="-500.00", currency="usd",
            date=timezone.make_aware(datetime(2026, 5, 1, 9, 0)),
        )
        self.client = auth_client(self.user)

    def test_export_all_returns_csv(self):
        response = self.client.get(f"/api/wallets/{self.wallet.id}/export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])
        body = response.content.decode()
        self.assertIn("date,amount,currency,note,category,tags", body)
        self.assertIn("salary", body)
        self.assertIn("rent", body)

    def test_export_month_filter(self):
        response = self.client.get(
            f"/api/wallets/{self.wallet.id}/export/?month=6&year=2026"
        )
        body = response.content.decode()
        self.assertIn("salary", body)      # June
        self.assertNotIn("rent", body)     # May excluded

    def test_export_rejects_other_users_wallet(self):
        other = User.objects.create_user(username="other", password="pass")
        response = auth_client(other).get(f"/api/wallets/{self.wallet.id}/export/")
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run it — expect failure**

```bash
cd backend && source venv/bin/activate
python manage.py test tests.wallets.test_csv_export -v 2
```
Expected: `404 != 200` (URL not wired).

- [ ] **Step 3: Add `CSVExportView` to `backend/wallets/views.py`**

At the top of the file, ensure these imports exist (add what's missing):
```python
import csv
from django.http import HttpResponse
```
Then add the view (near the other CSV views):
```python
class CSVExportView(APIView):
    """GET /api/wallets/{wallet_id}/export/?month=M&year=Y — download transactions as CSV."""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, wallet_id):
        wallet = get_object_or_404(Wallet, id=wallet_id, user=request.user)
        qs = (
            Transaction.objects.filter(wallet=wallet)
            .select_related("category")
            .prefetch_related("tags")
            .order_by("-date")
        )
        month = request.query_params.get("month")
        year = request.query_params.get("year")
        if month and year:
            qs = qs.filter(date__month=month, date__year=year)

        response = HttpResponse(content_type="text/csv")
        safe_name = "".join(c for c in wallet.name if c.isalnum() or c in ("-", "_")) or "wallet"
        response["Content-Disposition"] = f'attachment; filename="{safe_name}_transactions.csv"'

        writer = csv.writer(response)
        writer.writerow(["date", "amount", "currency", "note", "category", "tags"])
        for t in qs:
            writer.writerow([
                t.date.isoformat(),
                t.amount,
                t.currency,
                t.note,
                t.category.name if t.category else "",
                ";".join(tag.name for tag in t.tags.all()),
            ])
        return response
```

- [ ] **Step 4: Wire the URL in `backend/wallets/urls.py`**

Add `CSVExportView` to the `from .views import (...)` block, then add near the CSV import routes:
```python
    path('<uuid:wallet_id>/export/', CSVExportView.as_view(), name='csv-export'),
```

- [ ] **Step 5: Run the tests — expect pass**

```bash
python manage.py test tests.wallets.test_csv_export -v 2
```
Expected: `Ran 3 tests ... OK`

- [ ] **Step 6: Commit**

```bash
git add backend/wallets/views.py backend/wallets/urls.py backend/tests/wallets/test_csv_export.py
git commit -m "feat: add CSV export endpoint for wallet transactions"
```

---

### Task 2: Export button on the wallet page

**Files:**
- Create: `frontend/api/exports.ts`
- Modify: `frontend/app/wallet/[id]/page.tsx`

**Interfaces:**
- Consumes: `GET /api/wallets/{id}/export/` (Task 1).

- [ ] **Step 1: Create `frontend/api/exports.ts`**

```typescript
import { axiosInstance } from "@/api/axiosInstance";

export async function exportWalletCsv(
  walletId: string,
  params?: { month: number; year: number },
): Promise<void> {
  const response = await axiosInstance.get(`wallets/${walletId}/export/`, {
    params,
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data as Blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `wallet_${walletId}_transactions.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 2: Add the Export button next to "Import CSV"**

In `frontend/app/wallet/[id]/page.tsx`, find the action button group (around line 486) containing the `Import CSV` button:
```tsx
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setImportDialogOpen(true)}>
```
Add an Export button as the first child of that `div`:
```tsx
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={async () => {
                      try {
                        await exportWalletCsv(params.id as string);
                        toast.success("Export downloaded");
                      } catch {
                        toast.error("Export failed");
                      }
                    }}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export CSV
                  </Button>
                  <Button variant="outline" onClick={() => setImportDialogOpen(true)}>
```

- [ ] **Step 3: Add the imports at the top of the wallet page**

```typescript
import { Download } from "lucide-react";
import { exportWalletCsv } from "@/api/exports";
import { toast } from "sonner";
```
(If `toast` is already imported from B1b, don't duplicate it. `params.id` — match how the page already reads the wallet id; if it uses `params.id` elsewhere, reuse that.)

- [ ] **Step 4: Verify**

```bash
cd frontend && npm run lint && npm run build
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/api/exports.ts frontend/app/wallet/[id]/page.tsx
git commit -m "feat: add CSV export button to wallet page"
```
