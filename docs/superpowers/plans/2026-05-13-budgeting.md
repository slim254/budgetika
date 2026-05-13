# Budgeting — Per-Category Monthly Limits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-category monthly budget limits to the wallet page — repeating rules with optional end dates and per-month overrides, displayed as a collapsible progress-bar panel.

**Architecture:** Two new Django models (`BudgetRule`, `BudgetMonthOverride`) + five API endpoints. Frontend: `BudgetPanel` (collapsible summary) + `BudgetManagementDialog` (two-tab CRUD dialog) wired into the existing wallet page.

**Tech Stack:** Django REST Framework `APIView` + `generics`, `update_or_create` for override upsert, React `useState`/`useEffect`, shadcn `Dialog`/`Tabs`/`Select`/`Input`, `localStorage` for panel state.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/wallets/models.py` | Modify | Add `BudgetRule` and `BudgetMonthOverride` models |
| `backend/wallets/migrations/` | Create | Auto-generated migration for new models |
| `backend/wallets/tests.py` | Modify | Budget rule, override, and summary test classes |
| `backend/wallets/serializers.py` | Modify | `BudgetRuleSerializer`, `BudgetOverrideSerializer`, `BudgetSummarySerializer` |
| `backend/wallets/views.py` | Modify | `BudgetRuleList`, `BudgetRuleDetail`, `BudgetOverrideList`, `BudgetOverrideDetail`, `BudgetSummaryView` |
| `backend/wallets/urls.py` | Modify | Register five budget URL patterns |
| `frontend/models/wallets.ts` | Modify | Add `BudgetRule`, `BudgetMonthOverride`, `BudgetSummaryItem`, form-data types |
| `frontend/api/budgets.ts` | Create | Typed axios calls for all budget endpoints |
| `frontend/components/BudgetPanel.tsx` | Create | Collapsible panel with per-category progress bars |
| `frontend/components/BudgetManagementDialog.tsx` | Create | Two-tab dialog: manage rules + this-month overrides |
| `frontend/app/wallet/[id]/page.tsx` | Modify | Import and render `BudgetPanel` + `BudgetManagementDialog` |

---

## Task 1: Backend — tests (write first, run red, then implement)

**Files:**
- Modify: `backend/wallets/tests.py`

- [ ] **Step 1: Add budget imports and three test classes to tests.py**

Open `backend/wallets/tests.py`. After the existing `WalletTransactionSearchTest` class, append the following (do NOT replace existing tests):

```python
from datetime import date as date_type
from wallets.models import BudgetRule, BudgetMonthOverride


class BudgetRuleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="budget_user", password="pass")
        self.client = make_client(self.user)
        self.wallet = Wallet.objects.create(
            user=self.user, name="Budget Wallet", currency="usd", initial_value=Decimal("0")
        )
        self.category = TransactionCategory.objects.create(
            user=self.user, name="Food", icon="utensils", color="#F97316"
        )
        self.url = f"/api/wallets/{self.wallet.id}/budgets/"

    def test_create_rule(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "300.00",
            "start_date": "2024-01-15",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(BudgetRule.objects.count(), 1)
        rule = BudgetRule.objects.first()
        self.assertEqual(rule.start_date, date_type(2024, 1, 1))  # coerced to first of month

    def test_create_rule_with_end_date(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "200.00",
            "start_date": "2024-01-01",
            "end_date": "2024-06-15",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        rule = BudgetRule.objects.first()
        self.assertEqual(rule.end_date, date_type(2024, 6, 1))  # coerced to first of month

    def test_amount_must_be_positive(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "-50.00",
            "start_date": "2024-01-01",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_amount_zero_rejected(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "0.00",
            "start_date": "2024-01-01",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_end_date_before_start_date_rejected(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "300.00",
            "start_date": "2024-03-01",
            "end_date": "2024-01-01",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_overlapping_open_ended_rule_rejected(self):
        BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"), start_date=date_type(2024, 1, 1)
        )
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "200.00",
            "start_date": "2024-06-01",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_non_overlapping_rule_after_end_date_allowed(self):
        BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"),
            start_date=date_type(2024, 1, 1),
            end_date=date_type(2024, 3, 1),
        )
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "200.00",
            "start_date": "2024-04-01",
        }, format="json")
        self.assertEqual(response.status_code, 201)

    def test_list_rules(self):
        BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"), start_date=date_type(2024, 1, 1)
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_delete_rule(self):
        rule = BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"), start_date=date_type(2024, 1, 1)
        )
        response = self.client.delete(f"{self.url}{rule.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(BudgetRule.objects.count(), 0)

    def test_requires_auth(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_cross_wallet_isolation(self):
        other_user = User.objects.create_user(username="other_budget", password="pass")
        other_client = make_client(other_user)
        response = other_client.get(self.url)
        self.assertEqual(response.status_code, 404)


class BudgetOverrideTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="override_user", password="pass")
        self.client = make_client(self.user)
        self.wallet = Wallet.objects.create(
            user=self.user, name="Override Wallet", currency="usd", initial_value=Decimal("0")
        )
        self.category = TransactionCategory.objects.create(
            user=self.user, name="Groceries", icon="shopping-cart", color="#10B981"
        )
        self.rule = BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"), start_date=date_type(2024, 1, 1)
        )
        self.url = f"/api/wallets/{self.wallet.id}/budgets/overrides/"

    def test_create_override(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "year": 2024,
            "month": 3,
            "amount": "500.00",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(BudgetMonthOverride.objects.count(), 1)

    def test_upsert_updates_existing(self):
        BudgetMonthOverride.objects.create(
            wallet=self.wallet, category=self.category,
            year=2024, month=3, amount=Decimal("500.00")
        )
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "year": 2024,
            "month": 3,
            "amount": "600.00",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BudgetMonthOverride.objects.count(), 1)
        self.assertEqual(BudgetMonthOverride.objects.first().amount, Decimal("600.00"))

    def test_override_without_rule_rejected(self):
        other_category = TransactionCategory.objects.create(
            user=self.user, name="Travel", icon="plane", color="#6366F1"
        )
        response = self.client.post(self.url, {
            "category_id": str(other_category.id),
            "year": 2024,
            "month": 3,
            "amount": "500.00",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_delete_override(self):
        override = BudgetMonthOverride.objects.create(
            wallet=self.wallet, category=self.category,
            year=2024, month=3, amount=Decimal("500.00")
        )
        response = self.client.delete(f"{self.url}{override.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(BudgetMonthOverride.objects.count(), 0)

    def test_amount_must_be_positive(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "year": 2024,
            "month": 3,
            "amount": "-100.00",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_requires_auth(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_cross_wallet_isolation(self):
        other_user = User.objects.create_user(username="other_override", password="pass")
        other_client = make_client(other_user)
        response = other_client.get(self.url)
        self.assertEqual(response.status_code, 404)


class BudgetSummaryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="summary_user", password="pass")
        self.client = make_client(self.user)
        self.wallet = Wallet.objects.create(
            user=self.user, name="Summary Wallet", currency="usd", initial_value=Decimal("0")
        )
        self.category = TransactionCategory.objects.create(
            user=self.user, name="Food", icon="utensils", color="#F97316"
        )
        self.rule = BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"), start_date=date_type(2024, 1, 1)
        )
        self.url = f"/api/wallets/{self.wallet.id}/budgets/summary/"

    def _get(self, month=3, year=2024):
        return self.client.get(f"{self.url}?month={month}&year={year}")

    def test_active_rule_appears_in_summary(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["category"]["id"], str(self.category.id))

    def test_rule_ended_before_month_excluded(self):
        self.rule.end_date = date_type(2024, 2, 1)
        self.rule.save()
        response = self._get(month=3, year=2024)
        self.assertEqual(len(response.data), 0)

    def test_rule_starting_after_month_excluded(self):
        self.rule.start_date = date_type(2024, 4, 1)
        self.rule.save()
        response = self._get(month=3, year=2024)
        self.assertEqual(len(response.data), 0)

    def test_override_takes_precedence_over_rule(self):
        BudgetMonthOverride.objects.create(
            wallet=self.wallet, category=self.category,
            year=2024, month=3, amount=Decimal("500.00")
        )
        response = self._get()
        self.assertEqual(response.data[0]["limit"], "500.00")
        self.assertTrue(response.data[0]["is_override"])
        self.assertIsNotNone(response.data[0]["override_id"])

    def test_rule_without_override_not_flagged(self):
        response = self._get()
        self.assertFalse(response.data[0]["is_override"])
        self.assertIsNone(response.data[0]["override_id"])

    def test_spending_computed_from_negative_transactions(self):
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="Groceries", amount=Decimal("-80.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 3, 10)),
            category=self.category,
        )
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="More groceries", amount=Decimal("-40.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 3, 20)),
            category=self.category,
        )
        response = self._get()
        self.assertEqual(response.data[0]["spent"], "120.00")
        self.assertEqual(response.data[0]["remaining"], "180.00")
        self.assertFalse(response.data[0]["is_over_budget"])

    def test_income_excluded_from_spending(self):
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="Refund", amount=Decimal("50.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 3, 5)),
            category=self.category,
        )
        response = self._get()
        self.assertEqual(response.data[0]["spent"], "0.00")

    def test_zero_spending_when_no_transactions(self):
        response = self._get()
        self.assertEqual(response.data[0]["spent"], "0.00")
        self.assertEqual(response.data[0]["remaining"], "300.00")

    def test_over_budget_flag(self):
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="Overspend", amount=Decimal("-350.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 3, 1)),
            category=self.category,
        )
        response = self._get()
        self.assertTrue(response.data[0]["is_over_budget"])
        self.assertEqual(response.data[0]["remaining"], "-50.00")

    def test_archived_category_rule_still_returned(self):
        self.category.is_archived = True
        self.category.save()
        response = self._get()
        self.assertEqual(len(response.data), 1)

    def test_transactions_outside_month_excluded_from_spending(self):
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="Wrong month", amount=Decimal("-100.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 2, 28)),
            category=self.category,
        )
        response = self._get(month=3, year=2024)
        self.assertEqual(response.data[0]["spent"], "0.00")

    def test_requires_auth(self):
        self.client.credentials()
        response = self._get()
        self.assertEqual(response.status_code, 401)

    def test_cross_wallet_isolation(self):
        other_user = User.objects.create_user(username="other_summary", password="pass")
        other_client = make_client(other_user)
        response = other_client.get(f"/api/wallets/{self.wallet.id}/budgets/summary/?month=3&year=2024")
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run tests to confirm they all fail (models not yet defined)**

```bash
cd backend && source venv/bin/activate && python manage.py test wallets.tests.BudgetRuleTest wallets.tests.BudgetOverrideTest wallets.tests.BudgetSummaryTest 2>&1 | tail -20
```

Expected: ImportError or similar — `BudgetRule` and `BudgetMonthOverride` do not exist yet.

---

## Task 2: Backend — models and migration

**Files:**
- Modify: `backend/wallets/models.py`
- Create: `backend/wallets/migrations/` (auto-generated)

- [ ] **Step 1: Add BudgetRule and BudgetMonthOverride to models.py**

Open `backend/wallets/models.py`. At the end of the file, after `RecurringTransactionExecution`, add:

```python
class BudgetRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, related_name="budget_rules", on_delete=models.CASCADE
    )
    category = models.ForeignKey(
        TransactionCategory, related_name="budget_rules", on_delete=models.CASCADE
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["start_date"]

    def __str__(self):
        return f"{self.category.name} budget for {self.wallet.name}"


class BudgetMonthOverride(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, related_name="budget_overrides", on_delete=models.CASCADE
    )
    category = models.ForeignKey(
        TransactionCategory, related_name="budget_overrides", on_delete=models.CASCADE
    )
    year = models.IntegerField()
    month = models.IntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = [["wallet", "category", "year", "month"]]

    def __str__(self):
        return f"{self.category.name} override {self.year}-{self.month:02d}"
```

- [ ] **Step 2: Make and apply migrations**

```bash
cd backend && source venv/bin/activate && python manage.py makemigrations && python manage.py migrate
```

Expected output contains: `Creating model BudgetRule` and `Creating model BudgetMonthOverride`, then `Running migrations`.

- [ ] **Step 3: Commit**

```bash
cd backend && git add wallets/models.py wallets/migrations/ && git commit -m "feat: add BudgetRule and BudgetMonthOverride models"
```

---

## Task 3: Backend — serializers

**Files:**
- Modify: `backend/wallets/serializers.py`

- [ ] **Step 1: Add budget serializers to serializers.py**

Open `backend/wallets/serializers.py`. Add this import at the top alongside the existing model imports:

```python
from .models import (
    Transaction,
    UserTransactionTag,
    Wallet,
    TransactionCategory,
    RecurringTransaction,
    RecurringTransactionExecution,
    BudgetRule,
    BudgetMonthOverride,
)
```

Then at the end of the file, append:

```python
class BudgetRuleSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True)
    wallet = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = BudgetRule
        fields = ["id", "wallet", "category", "category_id", "amount", "start_date", "end_date"]
        read_only_fields = ["id", "wallet"]

    def validate_category_id(self, value):
        wallet = self.context["wallet"]
        if not TransactionCategory.objects.filter(id=value, user=wallet.user).exists():
            raise serializers.ValidationError("Category not found or doesn't belong to you.")
        return value

    def validate(self, data):
        amount = data.get("amount")
        if amount is not None and amount <= 0:
            raise serializers.ValidationError({"amount": "Must be greater than zero."})

        start = data.get("start_date") or getattr(self.instance, "start_date", None)
        end = data.get("end_date") if "end_date" in data else getattr(self.instance, "end_date", None)

        if start:
            data["start_date"] = start.replace(day=1)
            start = data["start_date"]
        if end:
            data["end_date"] = end.replace(day=1)
            end = data["end_date"]

        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "Must be on or after start date."})

        wallet = self.context["wallet"]
        category_id = data.get("category_id") or getattr(self.instance, "category_id", None)

        if category_id and start:
            qs = BudgetRule.objects.filter(wallet=wallet, category_id=category_id)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            for rule in qs:
                # [start, end] overlaps [rule.start_date, rule.end_date] if:
                # NOT (end < rule.start_date OR rule.end_date < start)
                end_before_rule_start = end is not None and end < rule.start_date
                rule_end_before_start = rule.end_date is not None and rule.end_date < start
                if not (end_before_rule_start or rule_end_before_start):
                    raise serializers.ValidationError(
                        "A budget rule for this category already overlaps with the given date range."
                    )

        return data

    def create(self, validated_data):
        category_id = validated_data.pop("category_id")
        validated_data["category"] = TransactionCategory.objects.get(id=category_id)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "category_id" in validated_data:
            category_id = validated_data.pop("category_id")
            validated_data["category"] = TransactionCategory.objects.get(id=category_id)
        return super().update(instance, validated_data)


class BudgetOverrideSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True)
    wallet = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = BudgetMonthOverride
        fields = ["id", "wallet", "category", "category_id", "year", "month", "amount"]
        read_only_fields = ["id", "wallet"]

    def validate_category_id(self, value):
        wallet = self.context["wallet"]
        if not TransactionCategory.objects.filter(id=value, user=wallet.user).exists():
            raise serializers.ValidationError("Category not found or doesn't belong to you.")
        return value

    def validate(self, data):
        amount = data.get("amount")
        if amount is not None and amount <= 0:
            raise serializers.ValidationError({"amount": "Must be greater than zero."})

        wallet = self.context["wallet"]
        category_id = data.get("category_id")
        if category_id:
            if not BudgetRule.objects.filter(wallet=wallet, category_id=category_id).exists():
                raise serializers.ValidationError(
                    "No budget rule exists for this category in this wallet."
                )

        return data


class BudgetSummarySerializer(serializers.Serializer):
    category = CategorySerializer(read_only=True)
    limit = serializers.DecimalField(max_digits=10, decimal_places=2)
    spent = serializers.DecimalField(max_digits=10, decimal_places=2)
    remaining = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_over_budget = serializers.BooleanField()
    is_override = serializers.BooleanField()
    rule_id = serializers.UUIDField()
    override_id = serializers.UUIDField(allow_null=True)
```

- [ ] **Step 2: Commit**

```bash
cd backend && git add wallets/serializers.py && git commit -m "feat: add BudgetRule, BudgetOverride, BudgetSummary serializers"
```

---

## Task 4: Backend — views and URLs

**Files:**
- Modify: `backend/wallets/views.py`
- Modify: `backend/wallets/urls.py`

- [ ] **Step 1: Add budget imports to views.py**

At the top of `backend/wallets/views.py`, extend the models import:

```python
from .models import (
    Transaction, UserTransactionTag, Wallet, TransactionCategory,
    RecurringTransaction, RecurringTransactionExecution,
    BudgetRule, BudgetMonthOverride,
)
```

And extend the serializers import:

```python
from .serializers import (
    TagSerializer, TransactionSerializer, WalletSerializer, CategorySerializer,
    CSVParseSerializer, CSVExecuteSerializer,
    UserDashboardSerializer, WalletDashboardSerializer,
    RecurringTransactionSerializer, RecurringTransactionExecutionSerializer,
    BudgetRuleSerializer, BudgetOverrideSerializer, BudgetSummarySerializer,
)
```

Replace the existing `datetime` import line:

```python
# Before:
from datetime import datetime
# After:
from datetime import datetime, date
```

Replace the existing `django.db.models` import line:

```python
# Before:
from django.db.models import F, Sum, DecimalField
# After:
from django.db.models import F, Sum, DecimalField, Q
```

- [ ] **Step 2: Add budget views to views.py**

At the end of `backend/wallets/views.py`, append:

```python
class BudgetRuleList(generics.ListCreateAPIView):
    serializer_class = BudgetRuleSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _get_wallet(self):
        return get_object_or_404(Wallet, id=self.kwargs["wallet_id"], user=self.request.user)

    def get_queryset(self):
        return BudgetRule.objects.filter(wallet=self._get_wallet()).select_related("category")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["wallet"] = self._get_wallet()
        return ctx

    def perform_create(self, serializer):
        serializer.save(wallet=self._get_wallet())


class BudgetRuleDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BudgetRuleSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _get_wallet(self):
        return get_object_or_404(Wallet, id=self.kwargs["wallet_id"], user=self.request.user)

    def get_queryset(self):
        return BudgetRule.objects.filter(wallet=self._get_wallet()).select_related("category")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["wallet"] = self._get_wallet()
        return ctx


class BudgetOverrideList(generics.ListCreateAPIView):
    serializer_class = BudgetOverrideSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _get_wallet(self):
        return get_object_or_404(Wallet, id=self.kwargs["wallet_id"], user=self.request.user)

    def get_queryset(self):
        return BudgetMonthOverride.objects.filter(wallet=self._get_wallet()).select_related("category")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["wallet"] = self._get_wallet()
        return ctx

    def create(self, request, *args, **kwargs):
        wallet = self._get_wallet()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        vd = serializer.validated_data
        category_id = vd["category_id"]
        category = TransactionCategory.objects.get(id=category_id)

        obj, created = BudgetMonthOverride.objects.update_or_create(
            wallet=wallet,
            category=category,
            year=vd["year"],
            month=vd["month"],
            defaults={"amount": vd["amount"]},
        )
        out = BudgetOverrideSerializer(obj, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class BudgetOverrideDetail(generics.DestroyAPIView):
    serializer_class = BudgetOverrideSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _get_wallet(self):
        return get_object_or_404(Wallet, id=self.kwargs["wallet_id"], user=self.request.user)

    def get_queryset(self):
        return BudgetMonthOverride.objects.filter(wallet=self._get_wallet())


class BudgetSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, wallet_id):
        wallet = get_object_or_404(Wallet, id=wallet_id, user=request.user)

        try:
            month = int(request.query_params.get("month", datetime.now().month))
            year = int(request.query_params.get("year", datetime.now().year))
        except ValueError:
            return Response(
                {"error": "month and year must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        month_start = date(year, month, 1)

        rules = BudgetRule.objects.filter(
            wallet=wallet,
            start_date__lte=month_start,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=month_start)
        ).select_related("category")

        overrides = {
            o.category_id: o
            for o in BudgetMonthOverride.objects.filter(wallet=wallet, year=year, month=month)
        }

        spending = {
            row["category_id"]: abs(row["total"])
            for row in Transaction.objects.filter(
                wallet=wallet,
                date__month=month,
                date__year=year,
                amount__lt=0,
            ).values("category_id").annotate(total=Sum("amount"))
        }

        items = []
        for rule in rules:
            override = overrides.get(rule.category_id)
            limit = override.amount if override else rule.amount
            spent = spending.get(rule.category_id, Decimal("0"))
            remaining = limit - spent
            items.append({
                "category": rule.category,
                "limit": limit,
                "spent": spent,
                "remaining": remaining,
                "is_over_budget": remaining < 0,
                "is_override": override is not None,
                "rule_id": rule.id,
                "override_id": override.id if override else None,
            })

        serializer = BudgetSummarySerializer(items, many=True)
        return Response(serializer.data)
```

- [ ] **Step 3: Register budget URLs in urls.py**

Open `backend/wallets/urls.py`. Add to the import:

```python
from .views import (
    WalletList, WalletDetail,
    WalletTransactionList, WalletTransactionDetail,
    WalletTransactionSearch,
    UserCategoryList, UserCategoryDetail,
    UserTagList, UserTagDetail,
    TransactionDetail, TransactionCreate,
    CSVParseView, CSVExecuteView,
    WalletMetrics,
    UserRecurringTransactionList,
    WalletRecurringTransactionList, WalletRecurringTransactionDetail,
    RecurringTransactionExecutionList,
    BudgetRuleList, BudgetRuleDetail,
    BudgetOverrideList, BudgetOverrideDetail,
    BudgetSummaryView,
)
```

Add to `urlpatterns` (after the recurring transaction routes):

```python
    # Budget routes
    path('<uuid:wallet_id>/budgets/', BudgetRuleList.as_view(), name='budget-rule-list'),
    path('<uuid:wallet_id>/budgets/summary/', BudgetSummaryView.as_view(), name='budget-summary'),
    path('<uuid:wallet_id>/budgets/overrides/', BudgetOverrideList.as_view(), name='budget-override-list'),
    path('<uuid:wallet_id>/budgets/overrides/<uuid:pk>/', BudgetOverrideDetail.as_view(), name='budget-override-detail'),
    path('<uuid:wallet_id>/budgets/<uuid:pk>/', BudgetRuleDetail.as_view(), name='budget-rule-detail'),
```

- [ ] **Step 4: Run all budget tests**

```bash
cd backend && source venv/bin/activate && python manage.py test wallets.tests.BudgetRuleTest wallets.tests.BudgetOverrideTest wallets.tests.BudgetSummaryTest -v 2 2>&1 | tail -30
```

Expected: all tests pass. Fix any failures before proceeding.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd backend && source venv/bin/activate && python manage.py test wallets 2>&1 | tail -10
```

Expected: `OK` with no failures.

- [ ] **Step 6: Commit**

```bash
cd backend && git add wallets/views.py wallets/urls.py && git commit -m "feat: add budget views and URL routes"
```

---

## Task 5: Frontend — types and API client

**Files:**
- Modify: `frontend/models/wallets.ts`
- Create: `frontend/api/budgets.ts`

- [ ] **Step 1: Add budget types to models/wallets.ts**

Open `frontend/models/wallets.ts`. At the end of the file, append:

```typescript
// Budget types
export interface BudgetRule {
  id: string;
  wallet: string;
  category: Category;
  amount: string;        // DRF DecimalField → JSON string
  start_date: string;    // ISO date "YYYY-MM-DD"
  end_date: string | null;
}

export interface BudgetRuleFormData {
  category_id: string;
  amount: string;
  start_date: string;    // "YYYY-MM-DD"
  end_date: string | null;
}

export interface BudgetMonthOverride {
  id: string;
  wallet: string;
  category: Category;
  year: number;
  month: number;
  amount: string;
}

export interface BudgetOverrideFormData {
  category_id: string;
  year: number;
  month: number;
  amount: string;
}

export interface BudgetSummaryItem {
  category: Category;
  limit: string;
  spent: string;
  remaining: string;
  is_over_budget: boolean;
  is_override: boolean;
  rule_id: string;
  override_id: string | null;
}
```

- [ ] **Step 2: Create frontend/api/budgets.ts**

```typescript
import { axiosInstance } from "@/api/axiosInstance";
import {
  BudgetRule,
  BudgetRuleFormData,
  BudgetMonthOverride,
  BudgetOverrideFormData,
  BudgetSummaryItem,
} from "@/models/wallets";

export const getBudgetSummary = (walletId: string, month: number, year: number) =>
  axiosInstance.get<BudgetSummaryItem[]>(
    `wallets/${walletId}/budgets/summary/?month=${month}&year=${year}`
  );

export const getBudgetRules = (walletId: string) =>
  axiosInstance.get<BudgetRule[]>(`wallets/${walletId}/budgets/`);

export const createBudgetRule = (walletId: string, data: BudgetRuleFormData) =>
  axiosInstance.post<BudgetRule>(`wallets/${walletId}/budgets/`, data);

export const updateBudgetRule = (
  walletId: string,
  ruleId: string,
  data: Partial<BudgetRuleFormData>
) => axiosInstance.patch<BudgetRule>(`wallets/${walletId}/budgets/${ruleId}/`, data);

export const deleteBudgetRule = (walletId: string, ruleId: string) =>
  axiosInstance.delete(`wallets/${walletId}/budgets/${ruleId}/`);

export const upsertBudgetOverride = (walletId: string, data: BudgetOverrideFormData) =>
  axiosInstance.post<BudgetMonthOverride>(`wallets/${walletId}/budgets/overrides/`, data);

export const deleteBudgetOverride = (walletId: string, overrideId: string) =>
  axiosInstance.delete(`wallets/${walletId}/budgets/overrides/${overrideId}/`);
```

- [ ] **Step 3: Commit**

```bash
cd frontend && git add models/wallets.ts api/budgets.ts && git commit -m "feat: add budget types and API client"
```

---

## Task 6: Frontend — BudgetPanel component

**Files:**
- Create: `frontend/components/BudgetPanel.tsx`

- [ ] **Step 1: Create BudgetPanel.tsx**

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { BudgetSummaryItem, Currency } from "@/models/wallets";
import { getBudgetSummary } from "@/api/budgets";
import { DynamicIcon } from "@/components/IconPicker";
import { formatCurrency } from "@/lib/currency";

interface BudgetPanelProps {
  walletId: string;
  month: number;
  year: number;
  currency: Currency;
  onManageClick: () => void;
}

export function BudgetPanel({ walletId, month, year, currency, onManageClick }: BudgetPanelProps) {
  const storageKey = `budget-panel-${walletId}`;

  const [expanded, setExpanded] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(storageKey) === "true";
  });
  const [summary, setSummary] = useState<BudgetSummaryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(() => {
    setLoading(true);
    setError(null);
    getBudgetSummary(walletId, month, year)
      .then((res) => setSummary(res.data))
      .catch(() => setError("Failed to load budget summary."))
      .finally(() => setLoading(false));
  }, [walletId, month, year]);

  useEffect(() => {
    localStorage.setItem(storageKey, String(expanded));
  }, [expanded, storageKey]);

  useEffect(() => {
    if (expanded) fetchSummary();
  }, [expanded, fetchSummary]);

  const toggle = () => setExpanded((e) => !e);

  return (
    <Card className="mb-6">
      <CardHeader className="py-3 px-4">
        <div className="flex items-center justify-between">
          <button
            onClick={toggle}
            className="flex items-center gap-2 text-sm font-medium hover:text-gray-700"
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
            Budget
          </button>
          <Button variant="ghost" size="sm" onClick={onManageClick}>
            <Settings className="h-4 w-4 mr-1" />
            Manage budgets
          </Button>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="pt-0">
          {loading && <p className="text-sm text-gray-500 py-2">Loading...</p>}

          {error && (
            <div className="flex items-center gap-2 py-2">
              <p className="text-sm text-red-600">{error}</p>
              <Button variant="ghost" size="sm" onClick={fetchSummary}>
                Retry
              </Button>
            </div>
          )}

          {!loading && !error && summary.length === 0 && (
            <p className="text-sm text-gray-500 py-2">
              No budgets set — click Manage budgets to add one.
            </p>
          )}

          {!loading && !error && summary.length > 0 && (
            <div className="space-y-4">
              {summary.map((item) => {
                const pct = Math.min(
                  100,
                  (Number(item.spent) / Number(item.limit)) * 100
                );
                return (
                  <div key={item.category.id}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2 text-sm">
                        <div
                          className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0"
                          style={{ backgroundColor: item.category.color + "20" }}
                        >
                          <DynamicIcon
                            name={item.category.icon || "circle"}
                            className="h-3 w-3"
                            style={{ color: item.category.color }}
                          />
                        </div>
                        <span>{item.category.name}</span>
                        {item.is_override && (
                          <span className="text-xs text-gray-400">(override)</span>
                        )}
                      </div>
                      <span className="text-sm text-gray-600 ml-2 whitespace-nowrap">
                        {formatCurrency(item.spent, currency)} /{" "}
                        {formatCurrency(item.limit, currency)}
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all ${
                          item.is_over_budget ? "bg-red-500" : "bg-blue-500"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <p
                      className={`text-xs mt-1 ${
                        item.is_over_budget ? "text-red-600 font-medium" : "text-gray-500"
                      }`}
                    >
                      {item.is_over_budget
                        ? `${formatCurrency(
                            Math.abs(Number(item.remaining)),
                            currency
                          )} over budget`
                        : `${formatCurrency(item.remaining, currency)} remaining`}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add components/BudgetPanel.tsx && git commit -m "feat: add BudgetPanel collapsible component"
```

---

## Task 7: Frontend — BudgetManagementDialog component

**Files:**
- Create: `frontend/components/BudgetManagementDialog.tsx`

- [ ] **Step 1: Create BudgetManagementDialog.tsx**

```tsx
"use client";

import { useEffect, useState } from "react";
import { Trash2, Plus, ChevronDown, ChevronUp } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import {
  BudgetRule,
  BudgetSummaryItem,
  Category,
  Currency,
} from "@/models/wallets";
import {
  getBudgetRules,
  getBudgetSummary,
  createBudgetRule,
  updateBudgetRule,
  deleteBudgetRule,
  upsertBudgetOverride,
  deleteBudgetOverride,
} from "@/api/budgets";
import { DynamicIcon } from "@/components/IconPicker";
import { formatCurrency } from "@/lib/currency";

interface BudgetManagementDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  walletId: string;
  month: number;
  year: number;
  categories: Category[];
  currency: Currency;
  onChanged: () => void;
}

interface RuleFormState {
  category_id: string;
  amount: string;
  start_date: string;
  end_date: string;
}

const EMPTY_RULE_FORM: RuleFormState = {
  category_id: "",
  amount: "",
  start_date: "",
  end_date: "",
};

export function BudgetManagementDialog({
  open,
  onOpenChange,
  walletId,
  month,
  year,
  categories,
  currency,
  onChanged,
}: BudgetManagementDialogProps) {
  const [rules, setRules] = useState<BudgetRule[]>([]);
  const [summary, setSummary] = useState<BudgetSummaryItem[]>([]);
  const [loading, setLoading] = useState(false);

  // Rule form
  const [ruleForm, setRuleForm] = useState<RuleFormState>(EMPTY_RULE_FORM);
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [ruleError, setRuleError] = useState<string | null>(null);
  const [ruleSaving, setRuleSaving] = useState(false);

  // Override state: category_id → input value (null = not editing)
  const [overrideEditing, setOverrideEditing] = useState<Record<string, string>>({});
  const [overrideSaving, setOverrideSaving] = useState<Record<string, boolean>>({});

  function loadData() {
    setLoading(true);
    Promise.all([
      getBudgetRules(walletId),
      getBudgetSummary(walletId, month, year),
    ])
      .then(([rulesRes, summaryRes]) => {
        setRules(rulesRes.data);
        setSummary(summaryRes.data);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) loadData();
  }, [open, walletId, month, year]); // eslint-disable-line react-hooks/exhaustive-deps

  function startAddRule() {
    setEditingRuleId(null);
    setRuleForm(EMPTY_RULE_FORM);
    setRuleError(null);
    setShowRuleForm(true);
  }

  function startEditRule(rule: BudgetRule) {
    setEditingRuleId(rule.id);
    setRuleForm({
      category_id: rule.category.id,
      amount: rule.amount,
      start_date: rule.start_date.slice(0, 7), // "YYYY-MM"
      end_date: rule.end_date ? rule.end_date.slice(0, 7) : "",
    });
    setRuleError(null);
    setShowRuleForm(true);
  }

  async function saveRule() {
    if (!ruleForm.category_id || !ruleForm.amount || !ruleForm.start_date) {
      setRuleError("Category, amount, and start month are required.");
      return;
    }
    setRuleSaving(true);
    setRuleError(null);
    const payload = {
      category_id: ruleForm.category_id,
      amount: ruleForm.amount,
      start_date: `${ruleForm.start_date}-01`,
      end_date: ruleForm.end_date ? `${ruleForm.end_date}-01` : null,
    };
    try {
      if (editingRuleId) {
        await updateBudgetRule(walletId, editingRuleId, payload);
      } else {
        await createBudgetRule(walletId, payload);
      }
      setShowRuleForm(false);
      setRuleForm(EMPTY_RULE_FORM);
      setEditingRuleId(null);
      loadData();
      onChanged();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: unknown } })?.response?.data;
      setRuleError(
        typeof msg === "string" ? msg : "Failed to save rule. Check for overlapping date ranges."
      );
    } finally {
      setRuleSaving(false);
    }
  }

  async function handleDeleteRule(ruleId: string) {
    if (!confirm("Delete this budget rule?")) return;
    await deleteBudgetRule(walletId, ruleId);
    loadData();
    onChanged();
  }

  function startOverrideEdit(item: BudgetSummaryItem) {
    setOverrideEditing((prev) => ({ ...prev, [item.category.id]: item.limit }));
  }

  function cancelOverrideEdit(categoryId: string) {
    setOverrideEditing((prev) => {
      const next = { ...prev };
      delete next[categoryId];
      return next;
    });
  }

  async function saveOverride(item: BudgetSummaryItem) {
    const amount = overrideEditing[item.category.id];
    if (!amount) return;
    setOverrideSaving((prev) => ({ ...prev, [item.category.id]: true }));
    try {
      await upsertBudgetOverride(walletId, {
        category_id: item.category.id,
        year,
        month,
        amount,
      });
      cancelOverrideEdit(item.category.id);
      loadData();
      onChanged();
    } finally {
      setOverrideSaving((prev) => ({ ...prev, [item.category.id]: false }));
    }
  }

  async function removeOverride(item: BudgetSummaryItem) {
    if (!item.override_id) return;
    await deleteBudgetOverride(walletId, item.override_id);
    loadData();
    onChanged();
  }

  const monthLabel = new Date(year, month - 1).toLocaleString("default", {
    month: "long",
    year: "numeric",
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Manage Budgets</DialogTitle>
        </DialogHeader>

        {loading ? (
          <p className="text-sm text-gray-500 py-4">Loading...</p>
        ) : (
          <Tabs defaultValue="rules">
            <TabsList className="w-full">
              <TabsTrigger value="rules" className="flex-1">
                Monthly limits
              </TabsTrigger>
              <TabsTrigger value="month" className="flex-1">
                {monthLabel}
              </TabsTrigger>
            </TabsList>

            {/* --- Monthly limits tab --- */}
            <TabsContent value="rules" className="mt-4 space-y-3">
              {rules.length === 0 && !showRuleForm && (
                <p className="text-sm text-gray-500">No budget rules yet.</p>
              )}

              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className="flex items-center justify-between py-2 border-b last:border-0"
                >
                  <div className="flex items-center gap-2">
                    <div
                      className="w-6 h-6 rounded flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: rule.category.color + "20" }}
                    >
                      <DynamicIcon
                        name={rule.category.icon || "circle"}
                        className="h-3 w-3"
                        style={{ color: rule.category.color }}
                      />
                    </div>
                    <div>
                      <p className="text-sm font-medium">{rule.category.name}</p>
                      <p className="text-xs text-gray-500">
                        {formatCurrency(rule.amount, currency)}/month ·{" "}
                        {rule.start_date.slice(0, 7)}
                        {rule.end_date ? ` → ${rule.end_date.slice(0, 7)}` : " → no end"}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => startEditRule(rule)}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteRule(rule.id)}
                    >
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </div>
                </div>
              ))}

              {showRuleForm && (
                <div className="border rounded p-3 space-y-3 bg-gray-50">
                  <div className="space-y-1">
                    <Label className="text-xs">Category</Label>
                    <Select
                      value={ruleForm.category_id}
                      onValueChange={(v) =>
                        setRuleForm((f) => ({ ...f, category_id: v }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select category" />
                      </SelectTrigger>
                      <SelectContent>
                        {categories
                          .filter((c) => !c.is_archived)
                          .map((c) => (
                            <SelectItem key={c.id} value={c.id}>
                              {c.name}
                            </SelectItem>
                          ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-1">
                    <Label className="text-xs">Monthly limit</Label>
                    <Input
                      type="number"
                      min="0.01"
                      step="0.01"
                      placeholder="300.00"
                      value={ruleForm.amount}
                      onChange={(e) =>
                        setRuleForm((f) => ({ ...f, amount: e.target.value }))
                      }
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label className="text-xs">Start month</Label>
                      <Input
                        type="month"
                        value={ruleForm.start_date}
                        onChange={(e) =>
                          setRuleForm((f) => ({ ...f, start_date: e.target.value }))
                        }
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">End month (optional)</Label>
                      <Input
                        type="month"
                        value={ruleForm.end_date}
                        onChange={(e) =>
                          setRuleForm((f) => ({ ...f, end_date: e.target.value }))
                        }
                      />
                    </div>
                  </div>

                  {ruleError && (
                    <p className="text-xs text-red-600">{ruleError}</p>
                  )}

                  <div className="flex gap-2 justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setShowRuleForm(false);
                        setEditingRuleId(null);
                        setRuleError(null);
                      }}
                    >
                      Cancel
                    </Button>
                    <Button size="sm" onClick={saveRule} disabled={ruleSaving}>
                      {ruleSaving ? "Saving..." : "Save"}
                    </Button>
                  </div>
                </div>
              )}

              {!showRuleForm && (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={startAddRule}
                >
                  <Plus className="h-4 w-4 mr-1" /> Add limit
                </Button>
              )}
            </TabsContent>

            {/* --- This month tab --- */}
            <TabsContent value="month" className="mt-4 space-y-3">
              {summary.length === 0 && (
                <p className="text-sm text-gray-500">
                  No active budget rules for this month.
                </p>
              )}

              {summary.map((item) => {
                const isEditing = item.category.id in overrideEditing;
                return (
                  <div key={item.category.id} className="border-b last:border-0 pb-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-5 h-5 rounded flex items-center justify-center flex-shrink-0"
                          style={{ backgroundColor: item.category.color + "20" }}
                        >
                          <DynamicIcon
                            name={item.category.icon || "circle"}
                            className="h-3 w-3"
                            style={{ color: item.category.color }}
                          />
                        </div>
                        <span className="text-sm font-medium">{item.category.name}</span>
                        {item.is_override && (
                          <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">
                            override
                          </span>
                        )}
                      </div>
                      <span className="text-sm text-gray-600">
                        {formatCurrency(item.limit, currency)}/mo
                      </span>
                    </div>

                    {isEditing ? (
                      <div className="mt-2 flex items-center gap-2">
                        <Input
                          type="number"
                          min="0.01"
                          step="0.01"
                          className="h-8 text-sm"
                          value={overrideEditing[item.category.id]}
                          onChange={(e) =>
                            setOverrideEditing((prev) => ({
                              ...prev,
                              [item.category.id]: e.target.value,
                            }))
                          }
                        />
                        <Button
                          size="sm"
                          className="h-8"
                          onClick={() => saveOverride(item)}
                          disabled={overrideSaving[item.category.id]}
                        >
                          Save
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8"
                          onClick={() => cancelOverrideEdit(item.category.id)}
                        >
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <div className="mt-1.5 flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() => startOverrideEdit(item)}
                        >
                          Override this month
                        </Button>
                        {item.is_override && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs text-gray-500"
                            onClick={() => removeOverride(item)}
                          >
                            Remove override
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add components/BudgetManagementDialog.tsx && git commit -m "feat: add BudgetManagementDialog two-tab component"
```

---

## Task 8: Frontend — wire up wallet page

**Files:**
- Modify: `frontend/app/wallet/[id]/page.tsx`

- [ ] **Step 1: Add imports to page.tsx**

Open `frontend/app/wallet/[id]/page.tsx`. Add to the existing import block:

```typescript
import { BudgetPanel } from "@/components/BudgetPanel";
import { BudgetManagementDialog } from "@/components/BudgetManagementDialog";
```

- [ ] **Step 2: Add budget dialog state**

Inside `WalletPage`, after the existing `importDialogOpen` state declaration, add:

```typescript
const [budgetDialogOpen, setBudgetDialogOpen] = useState(false);
const [budgetPanelKey, setBudgetPanelKey] = useState(0);
```

- [ ] **Step 3: Add refresh handler**

After `handleImportComplete`, add:

```typescript
function handleBudgetChanged() {
  setBudgetPanelKey((k) => k + 1);
}
```

- [ ] **Step 4: Insert BudgetPanel between month selector and transaction card**

Find this block in the JSX (the `mb-6 flex items-center gap-4` div):

```tsx
          <div className="mb-6 flex items-center gap-4">
```

Replace the entire block (the div containing `searchMode ? ... : ...`) with:

```tsx
          <div className="mb-6 flex items-center gap-4">
            {searchMode ? (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleExitSearchMode}
                >
                  <ArrowLeft className="mr-2 h-4 w-4" /> Month view
                </Button>
                <TransactionSearch
                  categories={categories}
                  tags={tags}
                  onSearch={fetchSearchResults}
                />
              </>
            ) : (
              <>
                <MonthSelector />
                <Button variant="outline" size="sm" onClick={handleEnterSearchMode}>
                  <Search className="mr-2 h-4 w-4" /> Search all transactions
                </Button>
              </>
            )}
          </div>

          {!searchMode && (
            <BudgetPanel
              key={budgetPanelKey}
              walletId={params.id}
              month={parseInt(month)}
              year={parseInt(year)}
              currency={wallet.currency}
              onManageClick={() => setBudgetDialogOpen(true)}
            />
          )}
```

- [ ] **Step 5: Add BudgetManagementDialog to the JSX**

After the closing `</CSVImportDialog>` tag (before `</ProtectedRoute>`), add:

```tsx
      <BudgetManagementDialog
        open={budgetDialogOpen}
        onOpenChange={setBudgetDialogOpen}
        walletId={params.id}
        month={parseInt(month)}
        year={parseInt(year)}
        categories={categories}
        currency={wallet.currency}
        onChanged={handleBudgetChanged}
      />
```

- [ ] **Step 6: Start the dev servers and verify manually**

Terminal 1 (backend):
```bash
cd backend && source venv/bin/activate && python manage.py runserver
```

Terminal 2 (frontend):
```bash
cd frontend && npm run dev
```

Open http://localhost:3000, navigate to a wallet page, and verify:
1. Budget panel appears between month selector and transaction card (collapsed by default)
2. Expanding the panel shows "No budgets set — click Manage budgets to add one"
3. Clicking "Manage budgets" opens the dialog
4. "Monthly limits" tab shows "No budget rules yet" and an "Add limit" button
5. Adding a rule with a category, amount, and start month saves and shows up in the list
6. "This month" tab shows the rule with an "Override this month" button
7. Setting an override updates the limit and shows the override badge
8. Closing the dialog and expanding the panel shows the category with a progress bar
9. The progress bar turns red when spending exceeds the limit
10. Changing months via the month selector updates the panel

- [ ] **Step 7: Commit**

```bash
cd frontend && git add app/wallet/\[id\]/page.tsx && git commit -m "feat: wire BudgetPanel and BudgetManagementDialog into wallet page"
```
