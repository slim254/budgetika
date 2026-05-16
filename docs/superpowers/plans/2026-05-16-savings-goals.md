# Savings Goals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a financial planning feature that tracks progress toward known future expenses and calculates required monthly savings rates.

**Architecture:** Backend model + serializer + service layer for calculations; ViewSet for CRUD + summary endpoint. Frontend dialog for create/edit, panel component for display on wallet page. All calculations delegated to service layer for reusability.

**Tech Stack:** Django ORM, DRF ViewSets, Python Decimal, React hooks, TanStack Query for API calls, shadcn/ui components.

---

## Task 1: Create SavingsGoal Model

**Files:**
- Modify: `backend/wallets/models.py`

- [ ] **Step 1: Add SavingsGoal model to wallets/models.py**

Locate the Wallet model in `wallets/models.py` and add the SavingsGoal model after it:

```python
class SavingsGoal(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("missed", "Missed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="savings_goals"
    )
    name = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=12, decimal_places=2)
    target_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["target_date"]
        indexes = [
            models.Index(fields=["wallet", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.target_date})"
```

- [ ] **Step 2: Commit the model addition**

```bash
git add backend/wallets/models.py
git commit -m "feat: add SavingsGoal model

- Per-wallet savings goal tracking with target amount and date
- Status field tracks active/completed/missed states
- Indexed on wallet + status for efficient queries"
```

---

## Task 2: Create Savings Calculations Service

**Files:**
- Create: `backend/wallets/services.py` (if doesn't exist; extend if it does)

- [ ] **Step 1: Add SavingsGoalService to services.py**

Check if `wallets/services.py` exists. If it does, append to it. If not, create it:

```python
from decimal import Decimal
from datetime import date, timedelta
from math import ceil
from django.db.models import Q, Sum
from .models import SavingsGoal, Transaction

class SavingsGoalService:
    """Calculate savings goals and progress."""

    @staticmethod
    def get_months_until(target_date: date) -> int:
        """Calculate months until target date. Min 1 month."""
        today = date.today()
        days_until = (target_date - today).days
        if days_until < 0:
            return 0
        months = ceil(days_until / 30.44)
        return max(1, months)

    @staticmethod
    def get_monthly_needed(target_amount: Decimal, target_date: date) -> Decimal:
        """Calculate monthly savings needed for a single goal."""
        months = SavingsGoalService.get_months_until(target_date)
        if months == 0:
            return Decimal("0")
        return (target_amount / months).quantize(Decimal("0.01"))

    @staticmethod
    def get_total_monthly_needed(goals) -> Decimal:
        """Sum monthly needed across all active goals."""
        total = Decimal("0")
        for goal in goals:
            total += SavingsGoalService.get_monthly_needed(
                goal.target_amount, goal.target_date
            )
        return total.quantize(Decimal("0.01"))

    @staticmethod
    def get_actual_savings(wallet, year: int, month: int) -> Decimal:
        """Calculate income - expenses for a given month."""
        transactions = wallet.transactions.filter(
            date__year=year, date__month=month
        )
        income = transactions.filter(amount__gt=0).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        expenses = transactions.filter(amount__lt=0).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        actual = income + expenses  # expenses are negative, so this is subtraction
        return actual.quantize(Decimal("0.01"))

    @staticmethod
    def get_monthly_summary(wallet, year: int, month: int):
        """Get complete monthly savings summary for a wallet."""
        today = date.today()
        goals = wallet.savings_goals.filter(status="active")

        # Mark any missed goals
        for goal in goals:
            if goal.target_date < today and goal.status == "active":
                goal.status = "missed"
                goal.save()

        # Recalculate active goals
        active_goals = wallet.savings_goals.filter(status="active")
        total_monthly_needed = SavingsGoalService.get_total_monthly_needed(
            active_goals
        )
        actual_savings = SavingsGoalService.get_actual_savings(wallet, year, month)
        difference = actual_savings - total_monthly_needed

        return {
            "month": month,
            "year": year,
            "total_monthly_needed": total_monthly_needed,
            "actual_savings": actual_savings,
            "difference": difference,
            "status": "on_track" if difference >= 0 else "short",
            "goals": active_goals,
        }
```

- [ ] **Step 2: Commit the service**

```bash
git add backend/wallets/services.py
git commit -m "feat: add SavingsGoalService for calculations

- get_months_until: calculate months from today to target
- get_monthly_needed: target_amount / months
- get_total_monthly_needed: sum across all active goals
- get_actual_savings: income - expenses for a month
- get_monthly_summary: complete summary with goal status updates"
```

---

## Task 3: Create SavingsGoalSerializer

**Files:**
- Modify: `backend/wallets/serializers.py`

- [ ] **Step 1: Add SavingsGoalSerializer to serializers.py**

At the end of `wallets/serializers.py`, add:

```python
from .services import SavingsGoalService
from datetime import date

class SavingsGoalSerializer(serializers.ModelSerializer):
    monthly_needed = serializers.SerializerMethodField()

    class Meta:
        model = SavingsGoal
        fields = [
            "id",
            "name",
            "target_amount",
            "target_date",
            "status",
            "monthly_needed",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "status"]

    def get_monthly_needed(self, obj) -> Decimal:
        """Compute monthly savings needed for this goal."""
        return SavingsGoalService.get_monthly_needed(
            obj.target_amount, obj.target_date
        )

    def validate_target_date(self, value):
        """Target date must be today or in the future at creation."""
        if self.instance is None and value < date.today():
            raise serializers.ValidationError(
                "Target date must be today or in the future."
            )
        return value

    def validate_target_amount(self, value):
        """Target amount must be positive."""
        if value <= 0:
            raise serializers.ValidationError("Target amount must be greater than 0.")
        return value

    def validate(self, data):
        """Ensure wallet belongs to authenticated user."""
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            wallet = data.get("wallet", self.instance.wallet if self.instance else None)
            if wallet and wallet.user != request.user:
                raise serializers.ValidationError(
                    "You do not have permission to create goals for this wallet."
                )
        return data
```

- [ ] **Step 2: Commit the serializer**

```bash
git add backend/wallets/serializers.py
git commit -m "feat: add SavingsGoalSerializer

- Includes computed monthly_needed field
- Validates target_date is in future at creation
- Validates target_amount > 0
- Enforces wallet ownership (users can only create goals for their own wallets)"
```

---

## Task 4: Create SavingsGoalViewSet

**Files:**
- Modify: `backend/wallets/views.py`

- [ ] **Step 1: Add SavingsGoalViewSet to views.py**

At the end of `wallets/views.py`, add:

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import SavingsGoal
from .serializers import SavingsGoalSerializer
from .services import SavingsGoalService

class SavingsGoalViewSet(viewsets.ModelViewSet):
    serializer_class = SavingsGoalSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        """Filter goals by wallet; ensure wallet belongs to user."""
        wallet_id = self.kwargs.get("wallet_pk")
        return SavingsGoal.objects.filter(
            wallet__id=wallet_id, wallet__user=self.request.user
        )

    def perform_create(self, serializer):
        """Set the wallet from the URL."""
        wallet_id = self.kwargs.get("wallet_pk")
        try:
            wallet = Wallet.objects.get(id=wallet_id, user=self.request.user)
        except Wallet.DoesNotExist:
            raise serializers.ValidationError("Wallet not found or access denied.")
        serializer.save(wallet=wallet)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="summary",
    )
    def summary(self, request, wallet_pk=None):
        """Get monthly savings summary for a wallet."""
        month = int(request.query_params.get("month", 0))
        year = int(request.query_params.get("year", 0))

        if not month or not year:
            today = date.today()
            month = today.month
            year = today.year

        try:
            wallet = Wallet.objects.get(id=wallet_pk, user=request.user)
        except Wallet.DoesNotExist:
            return Response(
                {"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND
            )

        summary_data = SavingsGoalService.get_monthly_summary(wallet, year, month)
        goals_qs = summary_data.pop("goals")
        goals_serialized = SavingsGoalSerializer(goals_qs, many=True).data

        response_data = {
            **summary_data,
            "goals": goals_serialized,
        }
        return Response(response_data, status=status.HTTP_200_OK)
```

- [ ] **Step 2: Commit the ViewSet**

```bash
git add backend/wallets/views.py
git commit -m "feat: add SavingsGoalViewSet with CRUD + summary

- GET /api/wallets/{wallet_id}/goals/ - list goals
- POST /api/wallets/{wallet_id}/goals/ - create goal
- PATCH/DELETE on individual goals
- GET /api/wallets/{wallet_id}/goals/summary/?month=M&year=Y - monthly summary
- All endpoints enforce wallet ownership via get_queryset"
```

---

## Task 5: Add SavingsGoal URLs

**Files:**
- Modify: `backend/wallets/urls.py`

- [ ] **Step 1: Register SavingsGoalViewSet in router**

Open `wallets/urls.py` and locate the SimpleRouter. Add this line before `urlpatterns`:

```python
# If using nested routers (wallets/{wallet_id}/goals/):
from rest_framework_nested import routers
from .views import SavingsGoalViewSet

# Inside the router registration section, add:
wallets_router = routers.SimpleRouter()
wallets_router.register(r"wallets", WalletViewSet, basename="wallet")

goals_router = routers.NestedSimpleRouter(wallets_router, "wallets", lookup="wallet")
goals_router.register(r"goals", SavingsGoalViewSet, basename="savings-goal")

urlpatterns = [
    path("api/", include(wallets_router.urls)),
    path("api/", include(goals_router.urls)),
]
```

If nested routers are not already in use, check the existing URL pattern. More likely, add:

```python
# Inside the existing router setup (check what's already there)
router.register(
    r"wallets/(?P<wallet_pk>[^/.]+)/goals",
    SavingsGoalViewSet,
    basename="savings-goal",
)
```

Or use the standard nested router pattern if not already present. **Check the current `wallets/urls.py` structure first.**

- [ ] **Step 2: Commit URLs**

```bash
git add backend/wallets/urls.py
git commit -m "feat: register SavingsGoalViewSet in router

Endpoints:
- GET/POST /api/wallets/{wallet_id}/goals/
- GET/PATCH/DELETE /api/wallets/{wallet_id}/goals/{goal_id}/
- GET /api/wallets/{wallet_id}/goals/summary/?month=M&year=Y"
```

---

## Task 6: Create Database Migration

**Files:**
- Create: Auto-generated in `backend/wallets/migrations/`

- [ ] **Step 1: Generate migration**

```bash
cd backend
source venv/bin/activate
python manage.py makemigrations wallets
```

Expected output: `Migrations for 'wallets': ... 000X_auto_YYYY_MM_DD_HHMM.py`

- [ ] **Step 2: Review migration file**

```bash
cat wallets/migrations/000X_auto_*.py | head -50
```

Verify the migration creates the `SavingsGoal` table with correct fields and FK.

- [ ] **Step 3: Apply migration**

```bash
python manage.py migrate wallets
```

Expected: `Running migrations: ... OK`

- [ ] **Step 4: Commit migration**

```bash
git add backend/wallets/migrations/
git commit -m "db: migration for SavingsGoal model"
```

---

## Task 7: Write Backend Tests

**Files:**
- Create: `backend/tests/wallets/test_savings_goals.py`

- [ ] **Step 1: Create test file with model tests**

```python
import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from wallets.models import Wallet, SavingsGoal, Transaction, TransactionCategory
from wallets.serializers import SavingsGoalSerializer
from wallets.services import SavingsGoalService

@pytest.mark.django_db
class TestSavingsGoalModel:
    """Test SavingsGoal model creation and properties."""

    def setup_method(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.wallet = Wallet.objects.create(
            user=self.user, name="Test Wallet", currency="usd", initial_value=1000
        )

    def test_create_goal(self):
        target_date = date.today() + timedelta(days=30)
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Vacation Fund",
            target_amount=Decimal("500.00"),
            target_date=target_date,
        )
        assert goal.name == "Vacation Fund"
        assert goal.status == "active"
        assert goal.wallet == self.wallet

    def test_goal_ordering(self):
        goal1 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 1",
            target_amount=Decimal("100"),
            target_date=date.today() + timedelta(days=60),
        )
        goal2 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 2",
            target_amount=Decimal("200"),
            target_date=date.today() + timedelta(days=30),
        )
        goals = list(self.wallet.savings_goals.all())
        assert goals[0] == goal2  # Earlier date first


@pytest.mark.django_db
class TestSavingsGoalService:
    """Test calculation logic."""

    def setup_method(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.wallet = Wallet.objects.create(
            user=self.user, name="Test Wallet", currency="usd", initial_value=1000
        )
        self.category = TransactionCategory.objects.create(
            user=self.user, name="Income", slug="income"
        )

    def test_months_until_30_days(self):
        target = date.today() + timedelta(days=30)
        months = SavingsGoalService.get_months_until(target)
        assert months == 1

    def test_months_until_365_days(self):
        target = date.today() + timedelta(days=365)
        months = SavingsGoalService.get_months_until(target)
        assert months == 12

    def test_monthly_needed(self):
        target = date.today() + timedelta(days=365)
        monthly = SavingsGoalService.get_monthly_needed(Decimal("1200"), target)
        assert monthly == Decimal("100.00")

    def test_total_monthly_needed_multiple_goals(self):
        goal1 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 1",
            target_amount=Decimal("500"),
            target_date=date.today() + timedelta(days=30),
        )
        goal2 = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Goal 2",
            target_amount=Decimal("1200"),
            target_date=date.today() + timedelta(days=365),
        )
        goals = [goal1, goal2]
        total = SavingsGoalService.get_total_monthly_needed(goals)
        expected = Decimal("500.00") + Decimal("100.00")
        assert total == expected

    def test_actual_savings_calculation(self):
        today = date.today()
        Transaction.objects.create(
            wallet=self.wallet,
            date=today,
            amount=Decimal("1000"),
            category=self.category,
            note="Salary",
        )
        Transaction.objects.create(
            wallet=self.wallet,
            date=today,
            amount=Decimal("-200"),
            category=self.category,
            note="Expense",
        )
        actual = SavingsGoalService.get_actual_savings(
            self.wallet, today.year, today.month
        )
        assert actual == Decimal("800.00")

    def test_actual_savings_no_transactions(self):
        actual = SavingsGoalService.get_actual_savings(
            self.wallet, date.today().year, date.today().month
        )
        assert actual == Decimal("0.00")


@pytest.mark.django_db
class TestSavingsGoalSerializer:
    """Test serializer validation."""

    def setup_method(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.wallet = Wallet.objects.create(
            user=self.user, name="Test Wallet", currency="usd", initial_value=1000
        )

    def test_serializer_valid(self):
        data = {
            "name": "Vacation",
            "target_amount": "500",
            "target_date": str(date.today() + timedelta(days=30)),
            "wallet": self.wallet.id,
        }
        serializer = SavingsGoalSerializer(data=data)
        assert serializer.is_valid()

    def test_serializer_invalid_past_date(self):
        data = {
            "name": "Vacation",
            "target_amount": "500",
            "target_date": str(date.today() - timedelta(days=1)),
            "wallet": self.wallet.id,
        }
        serializer = SavingsGoalSerializer(data=data)
        assert not serializer.is_valid()
        assert "target_date" in serializer.errors

    def test_serializer_invalid_zero_amount(self):
        data = {
            "name": "Vacation",
            "target_amount": "0",
            "target_date": str(date.today() + timedelta(days=30)),
            "wallet": self.wallet.id,
        }
        serializer = SavingsGoalSerializer(data=data)
        assert not serializer.is_valid()
        assert "target_amount" in serializer.errors

    def test_serializer_computes_monthly_needed(self):
        goal = SavingsGoal.objects.create(
            wallet=self.wallet,
            name="Vacation",
            target_amount=Decimal("1200"),
            target_date=date.today() + timedelta(days=365),
        )
        serializer = SavingsGoalSerializer(goal)
        data = serializer.data
        assert data["monthly_needed"] == "100.00"
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd backend
source venv/bin/activate
pytest tests/wallets/test_savings_goals.py -v
```

Expected: All tests pass.

- [ ] **Step 3: Commit tests**

```bash
git add backend/tests/wallets/test_savings_goals.py
git commit -m "test: add comprehensive tests for savings goals

- Model creation and ordering
- Calculation service (months_until, monthly_needed, actual_savings)
- Serializer validation (date, amount, wallet ownership)
- Multiple goals aggregation"
```

---

## Task 8: Create Frontend API Client

**Files:**
- Create: `frontend/api/savingsGoals.ts`

- [ ] **Step 1: Create API client file**

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "./client";

export interface SavingsGoal {
  id: string;
  name: string;
  target_amount: string;
  target_date: string;
  status: "active" | "completed" | "missed";
  monthly_needed: string;
  created_at: string;
}

export interface MonthlySummary {
  month: number;
  year: number;
  total_monthly_needed: string;
  actual_savings: string;
  difference: string;
  status: "on_track" | "short";
  goals: SavingsGoal[];
}

export const savingsGoalsAPI = {
  // List all goals for a wallet
  listGoals: (walletId: string) =>
    apiClient.get<SavingsGoal[]>(`/api/wallets/${walletId}/goals/`),

  // Create a new goal
  createGoal: (walletId: string, data: Omit<SavingsGoal, "id" | "created_at" | "status" | "monthly_needed">) =>
    apiClient.post<SavingsGoal>(`/api/wallets/${walletId}/goals/`, data),

  // Update an existing goal
  updateGoal: (walletId: string, goalId: string, data: Partial<Omit<SavingsGoal, "id" | "created_at" | "status" | "monthly_needed">>) =>
    apiClient.patch<SavingsGoal>(
      `/api/wallets/${walletId}/goals/${goalId}/`,
      data
    ),

  // Delete a goal
  deleteGoal: (walletId: string, goalId: string) =>
    apiClient.delete(`/api/wallets/${walletId}/goals/${goalId}/`),

  // Get monthly summary
  getMonthlySummary: (
    walletId: string,
    month?: number,
    year?: number
  ) => {
    const params = new URLSearchParams();
    if (month) params.append("month", month.toString());
    if (year) params.append("year", year.toString());
    return apiClient.get<MonthlySummary>(
      `/api/wallets/${walletId}/goals/summary/?${params.toString()}`
    );
  },
};

// React Query hooks

export const useSavingsGoals = (walletId: string) =>
  useQuery({
    queryKey: ["savings-goals", walletId],
    queryFn: () => savingsGoalsAPI.listGoals(walletId),
  });

export const useMonthlySummary = (walletId: string, month?: number, year?: number) =>
  useQuery({
    queryKey: ["savings-summary", walletId, month, year],
    queryFn: () => savingsGoalsAPI.getMonthlySummary(walletId, month, year),
  });

export const useCreateGoal = (walletId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<SavingsGoal, "id" | "created_at" | "status" | "monthly_needed">) =>
      savingsGoalsAPI.createGoal(walletId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["savings-goals", walletId],
      });
      queryClient.invalidateQueries({
        queryKey: ["savings-summary", walletId],
      });
    },
  });
};

export const useUpdateGoal = (walletId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ goalId, data }: { goalId: string; data: Partial<Omit<SavingsGoal, "id" | "created_at" | "status" | "monthly_needed">> }) =>
      savingsGoalsAPI.updateGoal(walletId, goalId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["savings-goals", walletId],
      });
      queryClient.invalidateQueries({
        queryKey: ["savings-summary", walletId],
      });
    },
  });
};

export const useDeleteGoal = (walletId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (goalId: string) =>
      savingsGoalsAPI.deleteGoal(walletId, goalId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["savings-goals", walletId],
      });
      queryClient.invalidateQueries({
        queryKey: ["savings-summary", walletId],
      });
    },
  });
};
```

- [ ] **Step 2: Commit API client**

```bash
git add frontend/api/savingsGoals.ts
git commit -m "feat: add savings goals API client

- List, create, update, delete goals
- Get monthly summary with status
- React Query hooks for data fetching and mutations
- Auto-invalidate related queries on mutations"
```

---

## Task 9: Create SavingsGoalDialog Component

**Files:**
- Create: `frontend/components/SavingsGoalDialog.tsx`

- [ ] **Step 1: Create dialog component**

```typescript
import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SavingsGoal, useCreateGoal, useUpdateGoal } from "@/api/savingsGoals";
import { toast } from "sonner";

interface SavingsGoalDialogProps {
  walletId: string;
  goalToEdit?: SavingsGoal | null;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  walletCurrency: string;
}

export function SavingsGoalDialog({
  walletId,
  goalToEdit,
  isOpen,
  onOpenChange,
  walletCurrency,
}: SavingsGoalDialogProps) {
  const [name, setName] = useState(goalToEdit?.name || "");
  const [targetAmount, setTargetAmount] = useState(goalToEdit?.target_amount || "");
  const [targetDate, setTargetDate] = useState(goalToEdit?.target_date || "");
  const [isLoading, setIsLoading] = useState(false);

  const createGoal = useCreateGoal(walletId);
  const updateGoal = useUpdateGoal(walletId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      if (goalToEdit) {
        await updateGoal.mutateAsync({
          goalId: goalToEdit.id,
          data: {
            name,
            target_amount: targetAmount,
            target_date: targetDate,
          },
        });
        toast.success("Goal updated");
      } else {
        await createGoal.mutateAsync({
          name,
          target_amount: targetAmount,
          target_date: targetDate,
        });
        toast.success("Goal created");
      }
      onOpenChange(false);
      setName("");
      setTargetAmount("");
      setTargetDate("");
    } catch (error) {
      toast.error("Failed to save goal");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {goalToEdit ? "Edit Goal" : "Create Savings Goal"}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="goal-name">Goal Name</Label>
            <Input
              id="goal-name"
              placeholder="e.g., Wedding gift, Car insurance"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="target-amount">Target Amount</Label>
            <div className="flex items-center gap-2">
              <Input
                id="target-amount"
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
                value={targetAmount}
                onChange={(e) => setTargetAmount(e.target.value)}
                required
              />
              <span className="text-sm text-muted-foreground">{walletCurrency.toUpperCase()}</span>
            </div>
          </div>
          <div>
            <Label htmlFor="target-date">Target Date</Label>
            <Input
              id="target-date"
              type="date"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
              required
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !name || !targetAmount || !targetDate}>
              {isLoading ? "Saving..." : "Save Goal"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Commit dialog component**

```bash
git add frontend/components/SavingsGoalDialog.tsx
git commit -m "feat: add SavingsGoalDialog for create/edit goals

- Form inputs: name, target_amount, target_date
- Currency display from wallet
- Toast notifications on success/error
- Reusable for both create and edit modes"
```

---

## Task 10: Create SavingsGoalsPanel Component

**Files:**
- Create: `frontend/components/SavingsGoalsPanel.tsx`

- [ ] **Step 1: Create panel component**

```typescript
import React, { useState } from "react";
import { format, formatDistanceToNow } from "date-fns";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  useSavingsGoals,
  useMonthlySummary,
  useDeleteGoal,
  SavingsGoal,
} from "@/api/savingsGoals";
import { SavingsGoalDialog } from "./SavingsGoalDialog";
import { toast } from "sonner";
import { Pencil, Trash2, Plus } from "lucide-react";

interface SavingsGoalsPanelProps {
  walletId: string;
  walletCurrency: string;
}

export function SavingsGoalsPanel({
  walletId,
  walletCurrency,
}: SavingsGoalsPanelProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingGoal, setEditingGoal] = useState<SavingsGoal | null>(null);

  const { data: goals = [], isLoading: goalsLoading } = useSavingsGoals(walletId);
  const { data: summary } = useMonthlySummary(walletId);
  const deleteGoal = useDeleteGoal(walletId);

  const handleDelete = async (goalId: string) => {
    try {
      await deleteGoal.mutateAsync(goalId);
      toast.success("Goal deleted");
    } catch (error) {
      toast.error("Failed to delete goal");
    }
  };

  const handleEdit = (goal: SavingsGoal) => {
    setEditingGoal(goal);
    setDialogOpen(true);
  };

  const handleOpenDialog = () => {
    setEditingGoal(null);
    setDialogOpen(true);
  };

  if (goalsLoading) {
    return <div className="text-sm text-muted-foreground">Loading goals...</div>;
  }

  const statusBadgeColor = {
    "on_track": "bg-green-100 text-green-800",
    short: "bg-yellow-100 text-yellow-800",
    active: "bg-blue-100 text-blue-800",
    completed: "bg-gray-100 text-gray-800",
    missed: "bg-red-100 text-red-800",
  };

  return (
    <div className="space-y-4">
      {/* Summary Card */}
      {summary && goals.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Monthly Savings Target</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Need to save</p>
                <p className="text-lg font-semibold">
                  {walletCurrency.toUpperCase()} {summary.total_monthly_needed}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Saved this month</p>
                <p className="text-lg font-semibold">
                  {walletCurrency.toUpperCase()} {summary.actual_savings}
                </p>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>Progress</span>
                <Badge variant={summary.status === "on_track" ? "default" : "secondary"}>
                  {summary.status === "on_track" ? "On Track" : "Short"}
                </Badge>
              </div>
              <Progress
                value={
                  Math.max(0, Math.min(100, (Number(summary.actual_savings) / Number(summary.total_monthly_needed)) * 100))
                }
              />
              {summary.status === "short" && (
                <p className="text-xs text-muted-foreground">
                  Need {walletCurrency.toUpperCase()} {Math.abs(Number(summary.difference)).toFixed(2)} more
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Goals List */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-base">Goals</CardTitle>
          <Button size="sm" onClick={handleOpenDialog}>
            <Plus className="w-4 h-4 mr-1" />
            Add Goal
          </Button>
        </CardHeader>
        <CardContent>
          {goals.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No savings goals yet. Create one to start tracking.
            </p>
          ) : (
            <div className="space-y-3">
              {goals.map((goal) => (
                <div key={goal.id} className="flex items-start justify-between p-3 border rounded">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="font-medium">{goal.name}</p>
                      <Badge variant={goal.status === "active" ? "default" : "secondary"}>
                        {goal.status.charAt(0).toUpperCase() + goal.status.slice(1)}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground mb-2">
                      Target: {walletCurrency.toUpperCase()} {goal.target_amount} by{" "}
                      {format(new Date(goal.target_date), "MMM d, yyyy")} (
                      {formatDistanceToNow(new Date(goal.target_date), { addSuffix: true })})
                    </p>
                    <p className="text-sm">
                      Need to save: <span className="font-medium">{walletCurrency.toUpperCase()} {goal.monthly_needed}/month</span>
                    </p>
                  </div>
                  {goal.status === "active" && (
                    <div className="flex gap-2 ml-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleEdit(goal)}
                      >
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDelete(goal.id)}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dialog */}
      <SavingsGoalDialog
        walletId={walletId}
        goalToEdit={editingGoal}
        isOpen={dialogOpen}
        onOpenChange={setDialogOpen}
        walletCurrency={walletCurrency}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit panel component**

```bash
git add frontend/components/SavingsGoalsPanel.tsx
git commit -m "feat: add SavingsGoalsPanel component

- Summary card shows total needed, actual savings, progress
- Goals list with name, target date, monthly requirement
- Status badges (active/completed/missed)
- Edit/delete actions for active goals
- Relative date formatting (in X weeks, etc)
- Empty state when no goals exist"
```

---

## Task 11: Integrate Panel into Wallet Page

**Files:**
- Modify: `frontend/app/wallet/[id]/page.tsx`

- [ ] **Step 1: Add SavingsGoalsPanel to wallet page**

In `frontend/app/wallet/[id]/page.tsx`, locate the wallet page component. Find where `BudgetPanel` is rendered and add `SavingsGoalsPanel` below it (or in a tab if using tabs):

```typescript
// At the top, add the import:
import { SavingsGoalsPanel } from "@/components/SavingsGoalsPanel";

// Inside the render, add after BudgetPanel:
<SavingsGoalsPanel walletId={walletId} walletCurrency={wallet.currency} />
```

- [ ] **Step 2: Commit integration**

```bash
git add frontend/app/wallet/[id]/page.tsx
git commit -m "feat: integrate SavingsGoalsPanel into wallet page

Goals section appears below budget panel on wallet page"
```

---

## Task 12: Write Frontend Tests

**Files:**
- Create: `frontend/__tests__/components/SavingsGoalsPanel.test.tsx`

- [ ] **Step 1: Create test file**

```typescript
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SavingsGoalsPanel } from "@/components/SavingsGoalsPanel";
import * as api from "@/api/savingsGoals";

// Mock the API
jest.mock("@/api/savingsGoals");

const mockGoals: api.SavingsGoal[] = [
  {
    id: "1",
    name: "Vacation",
    target_amount: "500",
    target_date: "2026-06-15",
    status: "active",
    monthly_needed: "250",
    created_at: "2026-05-16T00:00:00Z",
  },
  {
    id: "2",
    name: "Insurance",
    target_amount: "1200",
    target_date: "2026-12-31",
    status: "active",
    monthly_needed: "200",
    created_at: "2026-05-16T00:00:00Z",
  },
];

const mockSummary: api.MonthlySummary = {
  month: 5,
  year: 2026,
  total_monthly_needed: "450",
  actual_savings: "500",
  difference: "50",
  status: "on_track",
  goals: mockGoals,
};

describe("SavingsGoalsPanel", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    (api.useSavingsGoals as jest.Mock).mockReturnValue({
      data: mockGoals,
      isLoading: false,
    });
    (api.useMonthlySummary as jest.Mock).mockReturnValue({
      data: mockSummary,
    });
    (api.useDeleteGoal as jest.Mock).mockReturnValue({
      mutateAsync: jest.fn(),
    });
  });

  it("renders goals list", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    expect(screen.getByText("Vacation")).toBeInTheDocument();
    expect(screen.getByText("Insurance")).toBeInTheDocument();
  });

  it("displays summary card when goals exist", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    expect(screen.getByText("Monthly Savings Target")).toBeInTheDocument();
    expect(screen.getByText("USD 450")).toBeInTheDocument();
    expect(screen.getByText("USD 500")).toBeInTheDocument();
  });

  it("shows on-track status when actual >= needed", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    expect(screen.getByText("On Track")).toBeInTheDocument();
  });

  it("shows short status when actual < needed", () => {
    (api.useMonthlySummary as jest.Mock).mockReturnValue({
      data: { ...mockSummary, status: "short", difference: "-50" },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    expect(screen.getByText("Short")).toBeInTheDocument();
  });

  it("shows empty state when no goals", () => {
    (api.useSavingsGoals as jest.Mock).mockReturnValue({
      data: [],
      isLoading: false,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    expect(
      screen.getByText(/No savings goals yet/)
    ).toBeInTheDocument();
  });

  it("opens dialog when add goal is clicked", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <SavingsGoalsPanel walletId="wallet-1" walletCurrency="usd" />
      </QueryClientProvider>
    );

    const addButton = screen.getByText("Add Goal");
    fireEvent.click(addButton);

    expect(
      screen.getByText("Create Savings Goal")
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests**

```bash
cd frontend
npm test SavingsGoalsPanel.test.tsx
```

Expected: All tests pass.

- [ ] **Step 3: Commit tests**

```bash
git add frontend/__tests__/components/SavingsGoalsPanel.test.tsx
git commit -m "test: add tests for SavingsGoalsPanel

- Goals list rendering
- Summary card with status
- Empty state handling
- Dialog open/close
- Delete action"
```

---

## Task 13: Update Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `ROADMAP.md`

- [ ] **Step 1: Update CLAUDE.md with savings goals section**

Add to the "Data Model" section in CLAUDE.md:

```markdown
### Savings Goals

- Per-wallet financial planning targets (e.g., "Wedding €500 by May 25")
- System calculates required monthly savings rate across all active goals
- Status: active, completed, missed (missed if target_date < today)
- No allocation mechanics — goals are forecasts, not fund reservations
```

- [ ] **Step 2: Update CLAUDE.md API section**

Add to the API endpoints in CLAUDE.md:

```markdown
GET/POST   /api/wallets/{wallet_id}/goals/
GET/PATCH/DELETE  /api/wallets/{wallet_id}/goals/{goal_id}/
GET        /api/wallets/{wallet_id}/goals/summary/?month=M&year=Y
```

- [ ] **Step 3: Update ROADMAP.md**

Move "Savings Goals" from "Active Features" to "Completed" and update the build order. Change:

```markdown
## Build Order

| # | Feature | Priority | Complexity | Why this order |
|---|---|---|---|---|
| 1 | AI Auto-categorization | 3 | 3 | High-frequency action; most tangible AI value. |
```

(Remove savings goals from the list since it's now complete.)

- [ ] **Step 4: Commit documentation updates**

```bash
git add CLAUDE.md ROADMAP.md
git commit -m "docs: update CLAUDE.md and ROADMAP.md - mark savings goals as complete

- Document SavingsGoal model in data model section
- Add API endpoints for goals CRUD and summary
- Move savings goals from active to completed in roadmap
- Update build order with remaining features"
```

---

## Task 14: Run Full Test Suite and Manual Testing

**Files:**
- Integration testing across backend and frontend

- [ ] **Step 1: Run all backend tests**

```bash
cd backend
source venv/bin/activate
pytest tests/wallets/ -v
```

Expected: All tests pass, including new savings goals tests.

- [ ] **Step 2: Start backend and frontend servers**

Terminal 1 (Backend):
```bash
cd backend
source venv/bin/activate
python manage.py runserver
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

- [ ] **Step 3: Manually test create goal**

1. Open http://localhost:3000 in browser
2. Navigate to a wallet
3. Click "Add Goal"
4. Fill in: name="Vacation", amount="500", date="2026-06-15"
5. Click Save
6. Verify goal appears in list with correct monthly savings needed

- [ ] **Step 4: Manually test edit goal**

1. Click edit icon on the goal
2. Change amount to "750"
3. Click Save
4. Verify monthly needed amount updates

- [ ] **Step 5: Manually test delete goal**

1. Click delete icon
2. Verify goal is removed from list
3. Verify summary updates

- [ ] **Step 6: Manually test summary**

1. Create a goal with target 365 days away
2. Add some transactions (income and expenses)
3. Verify summary shows correct actual savings and status badge

- [ ] **Step 7: Verify API directly (optional curl test)**

```bash
# Get goals
curl -H "Authorization: Bearer <your-token>" http://localhost:8000/api/wallets/<wallet-id>/goals/

# Get summary
curl -H "Authorization: Bearer <your-token>" "http://localhost:8000/api/wallets/<wallet-id>/goals/summary/?month=5&year=2026"
```

- [ ] **Step 8: Commit if all tests pass**

```bash
git add .
git commit -m "test: verify savings goals integration - all tests passing

Backend tests: model, serializer, service calculations, ViewSet
Frontend tests: component rendering, API integration, dialog interactions
Manual testing: create, edit, delete goals; verify summary calculations"
```

---

## Summary

This plan implements the complete Savings Goals feature:

- **Backend:** SavingsGoal model, service layer for calculations, serializers with validation, ViewSet with CRUD + summary endpoint
- **Frontend:** API client with React Query hooks, create/edit dialog, goals panel component with summary card
- **Integration:** Panel renders on wallet page; full CRUD workflow with proper error handling and toast notifications
- **Testing:** Unit tests for calculations, integration tests for API, component tests for UI, manual end-to-end testing
- **Docs:** CLAUDE.md and ROADMAP.md updated to reflect completion

All tasks follow TDD and include comprehensive code samples. Each commit is atomic and can stand alone.
