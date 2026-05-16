# Wallet-to-Wallet Transfers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to record money moved between their own wallets as a linked pair of transactions (debit + credit), with cross-currency support via the existing Frankfurter exchange rate service.

**Architecture:** Two nullable fields (`transfer_ref`, `transfer_peer`) are added to the existing `Transaction` model. A transfer is a pair of `Transaction` rows created/edited/deleted atomically. Transfers appear inline in the regular transaction list, rendered distinctly by the frontend when `transfer_ref != null`.

**Tech Stack:** Django 5.1, DRF, `django.db.transaction.atomic`, existing `get_rate()` from `wallets/services.py`, Next.js 15, React, Tailwind, shadcn/ui, existing `getExchangeRate` API helper.

---

## File Map

| File | Change |
|---|---|
| `backend/wallets/models.py` | Add `transfer_ref`, `transfer_peer` to `Transaction` |
| `backend/wallets/migrations/XXXX_add_transfer_fields.py` | Migration (auto-generated) |
| `backend/wallets/serializers.py` | Add `transfer_ref`, `peer_wallet` to `TransactionSerializer`; new `WalletTransferSerializer` |
| `backend/wallets/views.py` | New `WalletTransferView` (POST/PATCH/DELETE by ref) |
| `backend/wallets/urls.py` | Wire new endpoints |
| `backend/wallets/tests.py` | `WalletTransferTest` class |
| `frontend/models/wallets.ts` | Update `Transaction` type; add `Transfer`, `TransferFormData` |
| `frontend/api/transfers.ts` | Create: `createTransfer`, `updateTransfer`, `deleteTransfer` |
| `frontend/components/WalletTransferDialog.tsx` | New dialog component |
| `frontend/app/wallet/[id]/page.tsx` | Transfer button in header; transfer row rendering; state |

---

## Task 1: Add transfer fields to Transaction model

**Files:**
- Modify: `backend/wallets/models.py` (Transaction class, ~line 162)

- [ ] **Step 1: Add fields to Transaction**

In `backend/wallets/models.py`, add two fields inside the `Transaction` class after the `tags` field (after line 204):

```python
    transfer_ref = models.UUIDField(null=True, blank=True, db_index=True)
    transfer_peer = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transfer_peer_reverse',
    )
```

- [ ] **Step 2: Generate and run migration**

```bash
cd backend && source venv/bin/activate
python manage.py makemigrations wallets --name add_transfer_fields_to_transaction
python manage.py migrate
```

Expected output includes: `Applying wallets.XXXX_add_transfer_fields_to_transaction... OK`

- [ ] **Step 3: Verify fields exist**

```bash
python manage.py shell -c "from wallets.models import Transaction; print([f.name for f in Transaction._meta.get_fields()])"
```

Expected: `transfer_ref` and `transfer_peer` appear in the list.

- [ ] **Step 4: Commit**

```bash
git add backend/wallets/models.py backend/wallets/migrations/
git commit -m "feat: add transfer_ref and transfer_peer fields to Transaction"
```

---

## Task 2: Extend TransactionSerializer with transfer fields

**Files:**
- Modify: `backend/wallets/serializers.py` (TransactionSerializer, ~line 95)

- [ ] **Step 1: Write failing test**

Append this class to `backend/wallets/tests.py`:

```python
class TransactionSerializerTransferFieldsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tfuser", password="pass")
        self.client = make_client(self.user)
        self.w1 = Wallet.objects.create(user=self.user, name="Checking", currency="pln", initial_value=Decimal("0"))
        self.w2 = Wallet.objects.create(user=self.user, name="Savings", currency="pln", initial_value=Decimal("0"))

    def test_transfer_ref_and_peer_wallet_in_transaction_list(self):
        import uuid
        ref = uuid.uuid4()
        debit = Transaction.objects.create(
            wallet=self.w1, created_by=self.user,
            note="Transfer", amount=Decimal("-200"), currency="pln",
            transfer_ref=ref,
        )
        credit = Transaction.objects.create(
            wallet=self.w2, created_by=self.user,
            note="Transfer", amount=Decimal("200"), currency="pln",
            transfer_ref=ref,
        )
        debit.transfer_peer = credit
        credit.transfer_peer = debit
        debit.save(update_fields=["transfer_peer"])
        credit.save(update_fields=["transfer_peer"])

        url = f"/api/wallets/{self.w1.id}/transactions/"
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        row = res.data[0]
        self.assertEqual(row["transfer_ref"], str(ref))
        self.assertIsNotNone(row["peer_wallet"])
        self.assertEqual(row["peer_wallet"]["name"], "Savings")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python manage.py test wallets.tests.TransactionSerializerTransferFieldsTest -v 2
```

Expected: FAIL — `transfer_ref` not in response fields.

- [ ] **Step 3: Add fields to TransactionSerializer**

In `backend/wallets/serializers.py`, make these changes to `TransactionSerializer`:

Add `peer_wallet` as a `SerializerMethodField` alongside the existing `category` field (after line 126):

```python
    peer_wallet = serializers.SerializerMethodField()
```

Update the `Meta.fields` list (line 136) to include the new fields:

```python
        fields = ['note', 'amount', 'currency', 'id', 'date', 'category', 'category_id', 'tags', 'tag_ids', 'transfer_ref', 'peer_wallet']
```

Add `read_only_fields` to Meta to lock the new fields:

```python
        read_only_fields = ['id', 'transfer_ref', 'peer_wallet']
```

Add the method after `validate_tag_ids` (before `create`):

```python
    def get_peer_wallet(self, obj):
        if not obj.transfer_ref or not obj.transfer_peer_id:
            return None
        try:
            peer = obj.transfer_peer
            return {
                "id": str(peer.wallet_id),
                "name": peer.wallet.name,
                "currency": peer.wallet.currency,
            }
        except Exception:
            return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && python manage.py test wallets.tests.TransactionSerializerTransferFieldsTest -v 2
```

Expected: PASS

- [ ] **Step 5: Add select_related to WalletTransactionList queryset to avoid N+1**

In `backend/wallets/views.py`, find `WalletTransactionList.get_queryset()`. It currently returns a queryset of `Transaction` objects. Add `.select_related('transfer_peer__wallet')` to the return value. The exact line will look something like:

```python
        return Transaction.objects.filter(...).select_related('transfer_peer__wallet').order_by('-date')
```

Find the actual queryset return in `WalletTransactionList.get_queryset()` and append `.select_related('transfer_peer__wallet')` to it.

- [ ] **Step 6: Run full test suite to check nothing regressed**

```bash
cd backend && python manage.py test wallets -v 1
```

Expected: all existing tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/wallets/serializers.py backend/wallets/views.py backend/wallets/tests.py
git commit -m "feat: expose transfer_ref and peer_wallet in TransactionSerializer"
```

---

## Task 3: WalletTransferSerializer

**Files:**
- Modify: `backend/wallets/serializers.py`

- [ ] **Step 1: Add import at top of serializers.py**

At the top of `backend/wallets/serializers.py`, the existing imports include `from django.db.models import Sum`. Add:

```python
import uuid
from decimal import Decimal
from django.db import transaction as db_transaction
from django.utils import timezone
from .services import get_rate
```

- [ ] **Step 2: Add WalletTransferSerializer at the bottom of serializers.py**

```python
class WalletTransferSerializer(serializers.Serializer):
    from_wallet = serializers.UUIDField()
    to_wallet = serializers.UUIDField()
    from_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    to_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    date = serializers.DateTimeField(required=False, default=timezone.now)
    note = serializers.CharField(max_length=100, allow_blank=True, default="")

    def validate(self, data):
        user = self.context['request'].user
        try:
            from_wallet = Wallet.objects.get(id=data['from_wallet'], user=user)
        except Wallet.DoesNotExist:
            raise serializers.ValidationError({"from_wallet": "Wallet not found or doesn't belong to you."})
        try:
            to_wallet = Wallet.objects.get(id=data['to_wallet'], user=user)
        except Wallet.DoesNotExist:
            raise serializers.ValidationError({"to_wallet": "Wallet not found or doesn't belong to you."})
        if str(data['from_wallet']) == str(data['to_wallet']):
            raise serializers.ValidationError("from_wallet and to_wallet must be different.")
        if data['from_amount'] <= 0:
            raise serializers.ValidationError({"from_amount": "Must be positive."})
        to_amount = data.get('to_amount')
        if to_amount is not None and to_amount <= 0:
            raise serializers.ValidationError({"to_amount": "Must be positive."})
        data['from_wallet_obj'] = from_wallet
        data['to_wallet_obj'] = to_wallet
        return data

    def create(self, validated_data):
        from_wallet = validated_data['from_wallet_obj']
        to_wallet = validated_data['to_wallet_obj']
        from_amount = validated_data['from_amount']
        to_amount = validated_data.get('to_amount')
        date = validated_data.get('date') or timezone.now()
        note = validated_data.get('note', '')
        user = self.context['request'].user

        if to_amount is None:
            rate_date = date.date() if hasattr(date, 'date') else date
            rate = get_rate(from_wallet.currency, to_wallet.currency, rate_date)
            to_amount = (from_amount * rate).quantize(Decimal('0.01'))

        ref = uuid.uuid4()
        with db_transaction.atomic():
            debit = Transaction.objects.create(
                wallet=from_wallet,
                created_by=user,
                note=note,
                amount=-from_amount,
                currency=from_wallet.currency,
                date=date,
                transfer_ref=ref,
            )
            credit = Transaction.objects.create(
                wallet=to_wallet,
                created_by=user,
                note=note,
                amount=to_amount,
                currency=to_wallet.currency,
                date=date,
                transfer_ref=ref,
            )
            debit.transfer_peer = credit
            credit.transfer_peer = debit
            debit.save(update_fields=['transfer_peer'])
            credit.save(update_fields=['transfer_peer'])
        return debit, credit
```

- [ ] **Step 3: Write tests for the serializer (via the API — done in Task 4 after the view is wired)**

Proceed to Task 4 to build the view before testing end-to-end.

- [ ] **Step 4: Commit**

```bash
git add backend/wallets/serializers.py
git commit -m "feat: add WalletTransferSerializer with atomic create and exchange rate fallback"
```

---

## Task 4: WalletTransferView (create, edit, delete)

**Files:**
- Modify: `backend/wallets/views.py`

- [ ] **Step 1: Add import**

In `backend/wallets/views.py`, the first line imports start with `from datetime import datetime, date`. Add to the imports block:

```python
from django.db import transaction as db_transaction
```

Also add to the `.models` import line: `ExchangeRate` is already imported. Make sure `Transaction` is imported (it is). No changes needed to model imports.

Add to the `.serializers` import: `WalletTransferSerializer`.

- [ ] **Step 2: Add WalletTransferView at the bottom of views.py**

```python
class WalletTransferView(APIView):
    """
    POST   /api/wallets/transfers/            — create a transfer
    PATCH  /api/wallets/transfers/{ref}/      — edit both legs
    DELETE /api/wallets/transfers/{ref}/      — delete both legs
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        serializer = WalletTransferSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        debit, credit = serializer.save()
        debit_data = TransactionSerializer(
            Transaction.objects.select_related('transfer_peer__wallet').get(pk=debit.pk),
            context={'request': request},
        ).data
        credit_data = TransactionSerializer(
            Transaction.objects.select_related('transfer_peer__wallet').get(pk=credit.pk),
            context={'request': request},
        ).data
        return Response(
            {'transfer_ref': str(debit.transfer_ref), 'debit': debit_data, 'credit': credit_data},
            status=status.HTTP_201_CREATED,
        )

    def _get_pair(self, transfer_ref, user):
        legs = list(
            Transaction.objects.filter(
                transfer_ref=transfer_ref,
                wallet__user=user,
            ).select_related('wallet', 'transfer_peer__wallet')
        )
        if len(legs) != 2:
            return None, None
        debit = next((t for t in legs if t.amount < 0), None)
        credit = next((t for t in legs if t.amount > 0), None)
        return debit, credit

    def patch(self, request, transfer_ref):
        debit, credit = self._get_pair(transfer_ref, request.user)
        if debit is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        note = request.data.get('note', debit.note)
        date = request.data.get('date', debit.date)
        from_amount = request.data.get('from_amount')
        to_amount = request.data.get('to_amount')

        with db_transaction.atomic():
            debit.note = note
            debit.date = date
            if from_amount is not None:
                debit.amount = -Decimal(str(from_amount))
            debit.save()
            credit.note = note
            credit.date = date
            if to_amount is not None:
                credit.amount = Decimal(str(to_amount))
            credit.save()

        debit_data = TransactionSerializer(
            Transaction.objects.select_related('transfer_peer__wallet').get(pk=debit.pk),
            context={'request': request},
        ).data
        credit_data = TransactionSerializer(
            Transaction.objects.select_related('transfer_peer__wallet').get(pk=credit.pk),
            context={'request': request},
        ).data
        return Response({'transfer_ref': str(transfer_ref), 'debit': debit_data, 'credit': credit_data})

    def delete(self, request, transfer_ref):
        count, _ = Transaction.objects.filter(
            transfer_ref=transfer_ref,
            wallet__user=request.user,
        ).delete()
        if count == 0:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 3: Wire URLs**

In `backend/wallets/urls.py`:

Add to the import block:
```python
from .views import (
    ...
    WalletTransferView,
)
```

Add to `urlpatterns`:
```python
    path('transfers/', WalletTransferView.as_view(), name='transfer-create'),
    path('transfers/<uuid:transfer_ref>/', WalletTransferView.as_view(), name='transfer-detail'),
```

- [ ] **Step 4: Write failing tests**

Append to `backend/wallets/tests.py`:

```python
class WalletTransferTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="truser", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")
        self.client = make_client(self.user)
        self.w1 = Wallet.objects.create(user=self.user, name="Checking", currency="pln", initial_value=Decimal("1000"))
        self.w2 = Wallet.objects.create(user=self.user, name="Savings", currency="pln", initial_value=Decimal("0"))
        self.w_other = Wallet.objects.create(user=self.other, name="Other", currency="pln", initial_value=Decimal("0"))
        self.create_url = "/api/wallets/transfers/"

    def _create_transfer(self, from_wallet=None, to_wallet=None, from_amount="200.00", to_amount="200.00", note="Test"):
        return self.client.post(self.create_url, {
            "from_wallet": str(from_wallet or self.w1.id),
            "to_wallet": str(to_wallet or self.w2.id),
            "from_amount": from_amount,
            "to_amount": to_amount,
            "date": "2026-05-16T10:00:00Z",
            "note": note,
        }, format="json")

    def test_create_same_currency_transfer(self):
        res = self._create_transfer()
        self.assertEqual(res.status_code, 201)
        self.assertIn("transfer_ref", res.data)
        self.assertEqual(res.data["debit"]["amount"], "-200.00")
        self.assertEqual(res.data["credit"]["amount"], "200.00")
        self.assertEqual(res.data["debit"]["currency"], "pln")
        self.assertEqual(res.data["credit"]["currency"], "pln")
        # both transactions created
        self.assertEqual(Transaction.objects.filter(transfer_ref=res.data["transfer_ref"]).count(), 2)

    def test_debit_peer_wallet_points_to_savings(self):
        res = self._create_transfer()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["debit"]["peer_wallet"]["name"], "Savings")
        self.assertEqual(res.data["credit"]["peer_wallet"]["name"], "Checking")

    def test_cannot_transfer_to_own_same_wallet(self):
        res = self._create_transfer(from_wallet=self.w1.id, to_wallet=self.w1.id)
        self.assertEqual(res.status_code, 400)

    def test_cannot_transfer_to_other_users_wallet(self):
        res = self._create_transfer(to_wallet=self.w_other.id)
        self.assertEqual(res.status_code, 400)

    def test_from_amount_must_be_positive(self):
        res = self._create_transfer(from_amount="-100")
        self.assertEqual(res.status_code, 400)

    def test_delete_removes_both_legs(self):
        res = self._create_transfer()
        ref = res.data["transfer_ref"]
        del_res = self.client.delete(f"/api/wallets/transfers/{ref}/")
        self.assertEqual(del_res.status_code, 204)
        self.assertEqual(Transaction.objects.filter(transfer_ref=ref).count(), 0)

    def test_patch_updates_both_legs(self):
        res = self._create_transfer(note="Original")
        ref = res.data["transfer_ref"]
        patch_res = self.client.patch(
            f"/api/wallets/transfers/{ref}/",
            {"note": "Updated", "from_amount": "300.00", "to_amount": "300.00"},
            format="json",
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data["debit"]["note"], "Updated")
        self.assertEqual(patch_res.data["debit"]["amount"], "-300.00")
        self.assertEqual(patch_res.data["credit"]["amount"], "300.00")

    def test_delete_nonexistent_returns_404(self):
        import uuid
        res = self.client.delete(f"/api/wallets/transfers/{uuid.uuid4()}/")
        self.assertEqual(res.status_code, 404)

    def test_transfers_appear_in_transaction_list(self):
        self._create_transfer()
        res = self.client.get(f"/api/wallets/{self.w1.id}/transactions/?month=5&year=2026")
        self.assertEqual(res.status_code, 200)
        transfer_rows = [t for t in res.data if t["transfer_ref"] is not None]
        self.assertEqual(len(transfer_rows), 1)
        self.assertEqual(transfer_rows[0]["peer_wallet"]["name"], "Savings")
```

- [ ] **Step 5: Run tests to verify they fail**

```bash
cd backend && python manage.py test wallets.tests.WalletTransferTest -v 2
```

Expected: multiple FAIL (URLs not wired yet if you haven't done Step 3; otherwise logic errors).

- [ ] **Step 6: Run tests after wiring**

Make sure Steps 1–3 are complete, then:

```bash
cd backend && python manage.py test wallets.tests.WalletTransferTest -v 2
```

Expected: all 9 tests PASS.

- [ ] **Step 7: Run full test suite**

```bash
cd backend && python manage.py test wallets -v 1
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/wallets/views.py backend/wallets/urls.py backend/wallets/tests.py backend/wallets/serializers.py
git commit -m "feat: add WalletTransferView for create/edit/delete of transfer pairs"
```

---

## Task 5: Frontend types

**Files:**
- Modify: `frontend/models/wallets.ts`

- [ ] **Step 1: Update Transaction interface**

In `frontend/models/wallets.ts`, find the `Transaction` interface (~line 36) and add two fields:

```typescript
export interface Transaction {
    id: string;
    note: string;
    amount: number;
    currency: Currency;
    date: string;
    category: Category | null;
    tags: Tag[];
    transfer_ref: string | null;
    peer_wallet: { id: string; name: string; currency: Currency } | null;
}
```

- [ ] **Step 2: Add Transfer and TransferFormData types**

At the bottom of `frontend/models/wallets.ts`, append:

```typescript
export interface Transfer {
    transfer_ref: string;
    debit: Transaction;
    credit: Transaction;
}

export interface TransferFormData {
    from_wallet: string;
    to_wallet: string;
    from_amount: number;
    to_amount: number;
    date: string;
    note: string;
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors (or same errors as before — don't introduce new ones).

- [ ] **Step 4: Commit**

```bash
git add frontend/models/wallets.ts
git commit -m "feat: add transfer types to wallets model"
```

---

## Task 6: Frontend API helper

**Files:**
- Create: `frontend/api/transfers.ts`

- [ ] **Step 1: Create the file**

```typescript
import { axiosInstance } from "./axiosInstance";
import { Transfer, TransferFormData } from "@/models/wallets";

export async function createTransfer(data: TransferFormData): Promise<Transfer> {
    const response = await axiosInstance.post<Transfer>("wallets/transfers/", data);
    return response.data;
}

export async function updateTransfer(
    transferRef: string,
    data: { note?: string; date?: string; from_amount?: number; to_amount?: number },
): Promise<Transfer> {
    const response = await axiosInstance.patch<Transfer>(`wallets/transfers/${transferRef}/`, data);
    return response.data;
}

export async function deleteTransfer(transferRef: string): Promise<void> {
    await axiosInstance.delete(`wallets/transfers/${transferRef}/`);
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/api/transfers.ts
git commit -m "feat: add transfers API helper"
```

---

## Task 7: WalletTransferDialog component

**Files:**
- Create: `frontend/components/WalletTransferDialog.tsx`

- [ ] **Step 1: Create the component**

```typescript
"use client";

import { useState, useEffect, useRef } from "react";
import { Wallet, Transfer, TransferFormData, Currency } from "@/models/wallets";
import { createTransfer, updateTransfer, deleteTransfer } from "@/api/transfers";
import { getExchangeRate } from "@/api/exchangeRates";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

interface WalletTransferDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSaved: () => void;
    onDeleted: () => void;
    wallets: Wallet[];
    currentWalletId: string;
    // For edit mode: pass the transfer_ref and pre-filled values
    editTransferRef?: string | null;
    editValues?: {
        to_wallet_id: string;
        from_amount: number;
        to_amount: number;
        date: string;
        note: string;
    } | null;
}

export function WalletTransferDialog({
    open,
    onOpenChange,
    onSaved,
    onDeleted,
    wallets,
    currentWalletId,
    editTransferRef,
    editValues,
}: WalletTransferDialogProps) {
    const isEdit = !!editTransferRef;
    const today = new Date().toISOString().slice(0, 10);

    const [toWalletId, setToWalletId] = useState("");
    const [fromAmount, setFromAmount] = useState("");
    const [toAmount, setToAmount] = useState("");
    const [date, setDate] = useState(today);
    const [note, setNote] = useState("");
    const [isFetchingRate, setIsFetchingRate] = useState(false);
    const [rateError, setRateError] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const rateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const currentWallet = wallets.find((w) => w.id === currentWalletId);
    const otherWallets = wallets.filter((w) => w.id !== currentWalletId);
    const toWallet = wallets.find((w) => w.id === toWalletId);
    const isCrossCurrency = !!toWallet && toWallet.currency !== currentWallet?.currency;

    // Populate form when opening in edit mode
    useEffect(() => {
        if (!open) {
            setConfirmDelete(false);
            setError(null);
            return;
        }
        if (isEdit && editValues) {
            setToWalletId(editValues.to_wallet_id);
            setFromAmount(String(editValues.from_amount));
            setToAmount(String(editValues.to_amount));
            setDate(editValues.date.slice(0, 10));
            setNote(editValues.note);
        } else {
            setToWalletId(otherWallets[0]?.id ?? "");
            setFromAmount("");
            setToAmount("");
            setDate(today);
            setNote("");
        }
    }, [open, isEdit]);

    // Auto-fill to_amount via exchange rate with 300ms debounce
    useEffect(() => {
        if (!open || !isCrossCurrency || !fromAmount || !date || !toWallet || !currentWallet) return;
        const amount = parseFloat(fromAmount);
        if (isNaN(amount) || amount <= 0) return;

        if (rateTimerRef.current) clearTimeout(rateTimerRef.current);
        rateTimerRef.current = setTimeout(async () => {
            setIsFetchingRate(true);
            setRateError(null);
            try {
                const data = await getExchangeRate(currentWallet.currency as Currency, toWallet.currency as Currency, date);
                const converted = (amount * parseFloat(data.rate)).toFixed(2);
                setToAmount(converted);
            } catch {
                setRateError("Could not fetch exchange rate.");
            } finally {
                setIsFetchingRate(false);
            }
        }, 300);

        return () => {
            if (rateTimerRef.current) clearTimeout(rateTimerRef.current);
        };
    }, [fromAmount, date, toWalletId, open]);

    async function handleSave() {
        if (!toWalletId || !fromAmount || !date) {
            setError("To wallet, amount, and date are required.");
            return;
        }
        const fa = parseFloat(fromAmount);
        const ta = parseFloat(toAmount || fromAmount);
        if (fa <= 0 || ta <= 0) {
            setError("Amounts must be positive.");
            return;
        }
        setSaving(true);
        setError(null);
        try {
            if (isEdit && editTransferRef) {
                await updateTransfer(editTransferRef, {
                    note,
                    date: new Date(date).toISOString(),
                    from_amount: fa,
                    to_amount: ta,
                });
            } else {
                const payload: TransferFormData = {
                    from_wallet: currentWalletId,
                    to_wallet: toWalletId,
                    from_amount: fa,
                    to_amount: ta,
                    date: new Date(date).toISOString(),
                    note,
                };
                await createTransfer(payload);
            }
            onOpenChange(false);
            onSaved();
        } catch {
            setError("Failed to save transfer. Please try again.");
        } finally {
            setSaving(false);
        }
    }

    async function handleDelete() {
        if (!editTransferRef) return;
        setDeleting(true);
        try {
            await deleteTransfer(editTransferRef);
            onOpenChange(false);
            onDeleted();
        } catch {
            setError("Failed to delete transfer.");
        } finally {
            setDeleting(false);
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>{isEdit ? "Edit Transfer" : "New Transfer"}</DialogTitle>
                </DialogHeader>

                <div className="grid gap-4 py-2">
                    <div className="grid gap-1">
                        <Label>From</Label>
                        <Input value={currentWallet?.name ?? ""} disabled />
                    </div>

                    <div className="grid gap-1">
                        <Label>To wallet</Label>
                        <Select value={toWalletId} onValueChange={setToWalletId} disabled={isEdit}>
                            <SelectTrigger>
                                <SelectValue placeholder="Select wallet" />
                            </SelectTrigger>
                            <SelectContent>
                                {otherWallets.map((w) => (
                                    <SelectItem key={w.id} value={w.id}>
                                        {w.name} ({w.currency.toUpperCase()})
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="grid gap-1">
                        <Label>Amount ({currentWallet?.currency.toUpperCase()})</Label>
                        <Input
                            type="number"
                            min="0"
                            step="0.01"
                            value={fromAmount}
                            onChange={(e) => setFromAmount(e.target.value)}
                            placeholder="0.00"
                        />
                    </div>

                    {isCrossCurrency && (
                        <div className="grid gap-1">
                            <Label>
                                Received amount ({toWallet?.currency.toUpperCase()})
                                {isFetchingRate && <span className="ml-2 text-xs text-gray-400">fetching rate…</span>}
                            </Label>
                            <Input
                                type="number"
                                min="0"
                                step="0.01"
                                value={toAmount}
                                onChange={(e) => setToAmount(e.target.value)}
                                placeholder="0.00"
                            />
                            {rateError && <p className="text-xs text-red-500">{rateError}</p>}
                        </div>
                    )}

                    <div className="grid gap-1">
                        <Label>Date</Label>
                        <Input
                            type="date"
                            value={date}
                            onChange={(e) => setDate(e.target.value)}
                        />
                    </div>

                    <div className="grid gap-1">
                        <Label>Note (optional)</Label>
                        <Input
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                            placeholder="e.g. Rent buffer"
                        />
                    </div>

                    {error && <p className="text-sm text-red-500">{error}</p>}
                </div>

                <div className="flex justify-between">
                    {isEdit && !confirmDelete && (
                        <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setConfirmDelete(true)}
                        >
                            Delete
                        </Button>
                    )}
                    {isEdit && confirmDelete && (
                        <div className="flex items-center gap-2">
                            <span className="text-sm text-red-600">Delete both sides?</span>
                            <Button
                                variant="destructive"
                                size="sm"
                                onClick={handleDelete}
                                disabled={deleting}
                            >
                                {deleting ? "Deleting…" : "Confirm"}
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(false)}>
                                Cancel
                            </Button>
                        </div>
                    )}
                    {!confirmDelete && (
                        <div className="flex gap-2 ml-auto">
                            <Button variant="outline" onClick={() => onOpenChange(false)}>
                                Cancel
                            </Button>
                            <Button onClick={handleSave} disabled={saving}>
                                {saving ? "Saving…" : isEdit ? "Save changes" : "Transfer"}
                            </Button>
                        </div>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/WalletTransferDialog.tsx
git commit -m "feat: add WalletTransferDialog component"
```

---

## Task 8: Wire transfers into the wallet page

**Files:**
- Modify: `frontend/app/wallet/[id]/page.tsx`

- [ ] **Step 1: Add imports at top of wallet page**

In the existing imports block, add:

```typescript
import { WalletTransferDialog } from "@/components/WalletTransferDialog";
import { ArrowLeftRight } from "lucide-react";
```

Also add `Transfer` to the existing models import:
```typescript
import { Wallet, Transaction, Category, Tag, SearchFilters, TransactionSearchResponse, Transfer } from "@/models/wallets";
```

- [ ] **Step 2: Add wallets list state and fetch**

In the component, add alongside the existing state declarations:

```typescript
const [wallets, setWallets] = useState<Wallet[]>([]);
const [transferDialogOpen, setTransferDialogOpen] = useState(false);
const [editingTransfer, setEditingTransfer] = useState<Transaction | null>(null);
```

Add a fetch function after `fetchTags`:

```typescript
async function fetchWallets() {
    try {
        const response = await axiosInstance.get<Wallet[]>("wallets/");
        setWallets(response.data);
    } catch (error) {
        console.error("Failed to fetch wallets:", error);
    }
}
```

Add `fetchWallets()` to the `loadData` function's `Promise.all` call alongside the existing fetches, and call it in the `useEffect` that triggers on mount/month/year changes.

- [ ] **Step 3: Add handler functions**

After the existing `handleDeleteTransaction` function, add:

```typescript
function handleAddTransfer() {
    setEditingTransfer(null);
    setTransferDialogOpen(true);
}

function handleEditTransfer(transaction: Transaction) {
    setEditingTransfer(transaction);
    setTransferDialogOpen(true);
}
```

- [ ] **Step 4: Add Transfer button to the card header**

Find the card header with the "Add Transaction" and "Import CSV" buttons (around line 415). Add a Transfer button:

```tsx
<Button variant="outline" onClick={handleAddTransfer}>
    <ArrowLeftRight className="mr-2 h-4 w-4" />
    Transfer
</Button>
```

Place it between the Import CSV button and the Add Transaction button.

- [ ] **Step 5: Render transfer rows distinctly in the transaction list**

In the `displayedTransactions.map((transaction) => { ... })` block (around line 458), at the very top of the map callback, add a branch for transfer rows before the existing `const isIncome = ...` line:

```tsx
if (transaction.transfer_ref) {
    const isOutgoing = Number(transaction.amount) < 0;
    const peerName = transaction.peer_wallet?.name ?? "another wallet";
    return (
        <TableRow key={transaction.id} className="bg-blue-50/30">
            <TableCell className="font-medium">
                {new Date(transaction.date).toLocaleDateString()}
            </TableCell>
            <TableCell>
                <div className="flex items-center gap-2">
                    <ArrowLeftRight className="h-4 w-4 text-blue-500" />
                    <span className="text-blue-700">
                        {isOutgoing ? `→ ${peerName}` : `← ${peerName}`}
                    </span>
                </div>
            </TableCell>
            <TableCell><span className="text-gray-400">—</span></TableCell>
            <TableCell><span className="text-gray-400">—</span></TableCell>
            <TableCell>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                    transfer
                </span>
            </TableCell>
            <TableCell
                className={`text-right font-semibold ${isOutgoing ? "text-red-600" : "text-green-600"}`}
            >
                {isOutgoing ? "" : "+"}
                {formatCurrency(transaction.amount, wallet.currency)}
            </TableCell>
            <TableCell className="text-right">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleEditTransfer(transaction)}
                >
                    <Edit className="h-4 w-4" />
                </Button>
            </TableCell>
        </TableRow>
    );
}
```

- [ ] **Step 6: Add WalletTransferDialog to the JSX**

Near the bottom of the return statement, alongside the existing `<TransactionDialog ...>` and `<CSVImportDialog ...>`, add:

```tsx
{wallet && (
    <WalletTransferDialog
        open={transferDialogOpen}
        onOpenChange={setTransferDialogOpen}
        onSaved={loadData}
        onDeleted={loadData}
        wallets={wallets}
        currentWalletId={params.id}
        editTransferRef={editingTransfer?.transfer_ref ?? null}
        editValues={editingTransfer ? {
            to_wallet_id: editingTransfer.peer_wallet?.id ?? "",
            from_amount: Math.abs(Number(editingTransfer.amount)),
            to_amount: Math.abs(Number(editingTransfer.amount)),
            date: editingTransfer.date,
            note: editingTransfer.note,
        } : null}
    />
)}
```

- [ ] **Step 7: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 new errors.

- [ ] **Step 8: Start dev servers and smoke test manually**

Terminal 1:
```bash
cd backend && source venv/bin/activate && python manage.py runserver
```

Terminal 2:
```bash
cd frontend && npm run dev
```

Manual checks:
1. Open http://localhost:3000, log in, open a wallet that has at least one other wallet.
2. Click "Transfer" — dialog opens with current wallet pre-filled as From.
3. Select destination wallet, enter an amount, click Transfer.
4. Transaction list refreshes; transfer row appears with `ArrowLeftRight` icon and "→ Savings" label.
5. Click the edit icon on a transfer row — dialog opens pre-filled.
6. Change the note, save — row updates.
7. Open edit dialog, click Delete, confirm — both rows disappear.
8. Test cross-currency: create a PLN→EUR transfer; verify the "Received amount (EUR)" field appears and auto-fills after 300ms.

- [ ] **Step 9: Commit**

```bash
git add frontend/app/wallet/\[id\]/page.tsx
git commit -m "feat: wire WalletTransferDialog into wallet page with transfer row rendering"
```

---

## Task 9: Final integration check

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && python manage.py test wallets -v 1
```

Expected: all tests pass.

- [ ] **Step 2: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete wallet-to-wallet transfers"
```
