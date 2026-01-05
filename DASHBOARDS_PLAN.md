# Dashboards Implementation Plan

## Overview
Implement dashboard views showing aggregated financial metrics for:
1. **User Main Dashboard** - Overview of all wallets with combined metrics
2. **Wallet Dashboard** - Detailed metrics for a single wallet

Priority: 4/5 | Complexity: 3/5

---

## DRF Learning Goals

This feature will teach you:
- **Aggregation queries** with Django ORM (`Sum`, `Count`, `Avg`)
- **Non-model serializers** for computed/aggregated data
- **Query optimization** to avoid N+1 problems
- **Date-based filtering** with Q objects
- **Custom APIViews** vs generic views

---

## Phase 1: User Main Dashboard

### Endpoint
```
GET /api/dashboard/
```

### Response Structure
```json
{
  "summary": {
    "total_balance": "5234.50",
    "total_income_this_month": "3000.00",
    "total_expenses_this_month": "1500.00",
    "net_this_month": "1500.00"
  },
  "wallets": [
    {
      "id": "uuid",
      "name": "Monthly Budget",
      "currency": "usd",
      "balance": "2500.00",
      "income_this_month": "2000.00",
      "expenses_this_month": "800.00"
    }
  ],
  "spending_by_category": [
    {
      "category_id": "uuid",
      "category_name": "Groceries",
      "category_icon": "shopping-cart",
      "category_color": "#F97316",
      "total_amount": "-450.00",
      "transaction_count": 12,
      "percentage": 30.0
    }
  ],
  "monthly_trend": [
    {
      "month": "2025-01",
      "income": "3000.00",
      "expenses": "1500.00",
      "net": "1500.00"
    }
  ]
}
```

### Backend Implementation

#### File: `wallets/serializers.py`

```python
# DRF EDUCATIONAL NOTE - Non-Model Serializers
# ============================================
# When your data doesn't map directly to a model (like aggregated
# dashboard data), use serializers.Serializer instead of ModelSerializer.
#
# Key differences:
# - No `model` in Meta class
# - Must define all fields explicitly
# - No automatic create()/update() - you handle data yourself
# - Perfect for read-only computed data, API responses, validation

class DashboardSummarySerializer(serializers.Serializer):
    """
    Serializes aggregated summary data.

    DRF EDUCATIONAL NOTE - DecimalField vs FloatField
    ================================================
    For financial data, ALWAYS use DecimalField, not FloatField.
    FloatField has precision issues (0.1 + 0.2 != 0.3 in floats).
    DecimalField maintains exact precision for money calculations.
    """
    total_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_income_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_expenses_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)


class WalletSummarySerializer(serializers.Serializer):
    """Wallet data for dashboard (lighter than full WalletSerializer)."""
    id = serializers.UUIDField()
    name = serializers.CharField()
    currency = serializers.CharField()
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    income_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    expenses_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)


class CategorySpendingSerializer(serializers.Serializer):
    """Category spending breakdown."""
    category_id = serializers.UUIDField(allow_null=True)
    category_name = serializers.CharField()
    category_icon = serializers.CharField(allow_blank=True)
    category_color = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    transaction_count = serializers.IntegerField()
    percentage = serializers.FloatField()  # OK for percentages, not money


class MonthlyTrendSerializer(serializers.Serializer):
    """Monthly income/expense trend."""
    month = serializers.CharField()  # Format: "2025-01"
    income = serializers.DecimalField(max_digits=12, decimal_places=2)
    expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    net = serializers.DecimalField(max_digits=12, decimal_places=2)


class UserDashboardSerializer(serializers.Serializer):
    """
    Main dashboard serializer combining all sections.

    DRF EDUCATIONAL NOTE - Nested Serializers
    =========================================
    You can nest serializers to build complex response structures.
    Use `many=True` for lists/arrays of nested objects.
    """
    summary = DashboardSummarySerializer()
    wallets = WalletSummarySerializer(many=True)
    spending_by_category = CategorySpendingSerializer(many=True)
    monthly_trend = MonthlyTrendSerializer(many=True)
```

#### File: `wallets/views.py`

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, Count, Q, F, DecimalField
from django.db.models.functions import Coalesce, TruncMonth
from datetime import datetime
from decimal import Decimal


class UserDashboard(APIView):
    """
    Main user dashboard with aggregated metrics.

    DRF EDUCATIONAL NOTE - APIView vs GenericAPIView
    ================================================
    Use APIView when:
    - You're not doing standard CRUD on a model
    - You need full control over the response
    - You're aggregating data from multiple sources

    Use GenericAPIView (ListAPIView, etc.) when:
    - You're doing standard CRUD operations
    - You want built-in pagination, filtering
    - You're working with a single model queryset

    APIView gives you raw get(), post(), put(), delete() methods.
    You build the response yourself with Response({...}).
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        """
        DRF EDUCATIONAL NOTE - Aggregation Queries
        ==========================================
        Django ORM aggregation functions (from django.db.models):

        - Sum('field'): Total of all values
        - Count('field'): Number of records
        - Avg('field'): Average value
        - Max('field'), Min('field'): Extremes

        Use with:
        - .aggregate(): Returns dict, ends queryset chain
        - .annotate(): Adds field to each object, preserves queryset

        Example:
            Transaction.objects.aggregate(total=Sum('amount'))
            # Returns: {'total': Decimal('1234.56')}

            Wallet.objects.annotate(tx_count=Count('transactions'))
            # Each wallet now has .tx_count attribute
        """
        user = request.user
        now = datetime.now()
        current_month = now.month
        current_year = now.year

        # Get all user's wallets with annotated balances
        # DRF EDUCATIONAL NOTE - Avoiding N+1 Queries
        # ==========================================
        # Instead of: for wallet in wallets: wallet.transactions.sum()
        # Use: annotate() to calculate in single query
        wallets = Wallet.objects.filter(user=user).annotate(
            total_transactions=Coalesce(
                Sum('transactions__amount'),
                Decimal('0'),
                output_field=DecimalField()
            ),
            income_this_month=Coalesce(
                Sum(
                    'transactions__amount',
                    filter=Q(
                        transactions__amount__gt=0,
                        transactions__date__month=current_month,
                        transactions__date__year=current_year
                    )
                ),
                Decimal('0'),
                output_field=DecimalField()
            ),
            expenses_this_month=Coalesce(
                Sum(
                    'transactions__amount',
                    filter=Q(
                        transactions__amount__lt=0,
                        transactions__date__month=current_month,
                        transactions__date__year=current_year
                    )
                ),
                Decimal('0'),
                output_field=DecimalField()
            )
        )

        # Build wallet summaries
        wallet_data = []
        total_balance = Decimal('0')
        total_income = Decimal('0')
        total_expenses = Decimal('0')

        for wallet in wallets:
            balance = wallet.initial_value + wallet.total_transactions
            total_balance += balance
            total_income += wallet.income_this_month
            total_expenses += abs(wallet.expenses_this_month)

            wallet_data.append({
                'id': wallet.id,
                'name': wallet.name,
                'currency': wallet.currency,
                'balance': balance,
                'income_this_month': wallet.income_this_month,
                'expenses_this_month': abs(wallet.expenses_this_month),
            })

        # Spending by category (this month, expenses only)
        # DRF EDUCATIONAL NOTE - values() + annotate()
        # ============================================
        # .values('field') groups by that field (like SQL GROUP BY)
        # Then .annotate() aggregates within each group
        category_spending = Transaction.objects.filter(
            wallet__user=user,
            amount__lt=0,  # Expenses only
            date__month=current_month,
            date__year=current_year
        ).values(
            'category__id',
            'category__name',
            'category__icon',
            'category__color'
        ).annotate(
            total_amount=Sum('amount'),
            transaction_count=Count('id')
        ).order_by('total_amount')  # Most negative (highest spending) first

        # Calculate percentages
        total_spent = abs(total_expenses) if total_expenses else Decimal('1')
        spending_data = []
        for cat in category_spending:
            spending_data.append({
                'category_id': cat['category__id'],
                'category_name': cat['category__name'] or 'Uncategorized',
                'category_icon': cat['category__icon'] or 'circle',
                'category_color': cat['category__color'] or '#6B7280',
                'total_amount': cat['total_amount'],
                'transaction_count': cat['transaction_count'],
                'percentage': float(abs(cat['total_amount']) / total_spent * 100),
            })

        # Monthly trend (last 6 months)
        # DRF EDUCATIONAL NOTE - TruncMonth
        # =================================
        # TruncMonth truncates datetime to first of month
        # Useful for grouping by month in reports
        six_months_ago = datetime(
            current_year if current_month > 6 else current_year - 1,
            current_month - 6 if current_month > 6 else current_month + 6,
            1
        )

        monthly_data = Transaction.objects.filter(
            wallet__user=user,
            date__gte=six_months_ago
        ).annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            income=Coalesce(
                Sum('amount', filter=Q(amount__gt=0)),
                Decimal('0')
            ),
            expenses=Coalesce(
                Sum('amount', filter=Q(amount__lt=0)),
                Decimal('0')
            )
        ).order_by('month')

        trend_data = []
        for item in monthly_data:
            trend_data.append({
                'month': item['month'].strftime('%Y-%m'),
                'income': item['income'],
                'expenses': abs(item['expenses']),
                'net': item['income'] + item['expenses'],
            })

        # Build response
        data = {
            'summary': {
                'total_balance': total_balance,
                'total_income_this_month': total_income,
                'total_expenses_this_month': total_expenses,
                'net_this_month': total_income - total_expenses,
            },
            'wallets': wallet_data,
            'spending_by_category': spending_data,
            'monthly_trend': trend_data,
        }

        serializer = UserDashboardSerializer(data)
        return Response(serializer.data)
```

#### File: `wallets/urls.py`

```python
# Add to urlpatterns:
path('dashboard/', UserDashboard.as_view(), name='user-dashboard'),
```

---

## Phase 2: Wallet Dashboard (Enhanced Detail)

### Option A: Enhance existing wallet detail endpoint
### Option B: Create separate metrics endpoint (recommended)

### Endpoint
```
GET /api/wallets/{wallet_id}/metrics/
```

### Response Structure
```json
{
  "wallet_id": "uuid",
  "wallet_name": "Monthly Budget",
  "currency": "usd",
  "balance": "2500.00",
  "metrics": {
    "total_transactions": 45,
    "income_count": 5,
    "expense_count": 40,
    "income_this_month": "2000.00",
    "expenses_this_month": "800.00",
    "net_this_month": "1200.00",
    "average_transaction": "-45.50",
    "largest_expense": "-250.00",
    "largest_income": "2000.00"
  },
  "category_breakdown": [
    {
      "category_id": "uuid",
      "category_name": "Groceries",
      "category_icon": "shopping-cart",
      "category_color": "#F97316",
      "transaction_count": 15,
      "total_amount": "-450.00",
      "percentage": 35.5
    }
  ],
  "recent_transactions": [
    // Last 10 transactions (use existing TransactionSerializer)
  ]
}
```

### Backend Implementation

```python
class WalletMetricsSerializer(serializers.Serializer):
    """Aggregated metrics for a single wallet."""
    total_transactions = serializers.IntegerField()
    income_count = serializers.IntegerField()
    expense_count = serializers.IntegerField()
    income_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    expenses_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_transaction = serializers.DecimalField(max_digits=12, decimal_places=2)
    largest_expense = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    largest_income = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)


class WalletDashboardSerializer(serializers.Serializer):
    """Full wallet dashboard response."""
    wallet_id = serializers.UUIDField()
    wallet_name = serializers.CharField()
    currency = serializers.CharField()
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    metrics = WalletMetricsSerializer()
    category_breakdown = CategorySpendingSerializer(many=True)
    recent_transactions = TransactionSerializer(many=True)


class WalletMetrics(APIView):
    """
    Detailed metrics for a single wallet.

    DRF EDUCATIONAL NOTE - get_object() Pattern
    ===========================================
    When you need to fetch a specific object in an APIView,
    create a helper method similar to GenericAPIView.get_object().
    This keeps your code DRY and handles 404s consistently.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_wallet(self, wallet_id, user):
        """Fetch wallet with ownership validation."""
        return get_object_or_404(Wallet, id=wallet_id, user=user)

    def get(self, request, wallet_id):
        user = request.user
        wallet = self.get_wallet(wallet_id, user)
        now = datetime.now()

        # DRF EDUCATIONAL NOTE - Aggregate Multiple Values
        # ================================================
        # You can compute multiple aggregates in one query
        # using .aggregate() with multiple arguments.
        # This is much more efficient than multiple queries!
        metrics = Transaction.objects.filter(wallet=wallet).aggregate(
            total_transactions=Count('id'),
            income_count=Count('id', filter=Q(amount__gt=0)),
            expense_count=Count('id', filter=Q(amount__lt=0)),
            income_this_month=Coalesce(
                Sum('amount', filter=Q(
                    amount__gt=0,
                    date__month=now.month,
                    date__year=now.year
                )),
                Decimal('0')
            ),
            expenses_this_month=Coalesce(
                Sum('amount', filter=Q(
                    amount__lt=0,
                    date__month=now.month,
                    date__year=now.year
                )),
                Decimal('0')
            ),
            average_transaction=Coalesce(Avg('amount'), Decimal('0')),
            largest_expense=Min('amount'),  # Most negative
            largest_income=Max('amount'),
        )

        metrics['net_this_month'] = (
            metrics['income_this_month'] + metrics['expenses_this_month']
        )
        metrics['expenses_this_month'] = abs(metrics['expenses_this_month'])

        # Category breakdown for this wallet
        categories = Transaction.objects.filter(
            wallet=wallet,
            amount__lt=0
        ).values(
            'category__id',
            'category__name',
            'category__icon',
            'category__color'
        ).annotate(
            total_amount=Sum('amount'),
            transaction_count=Count('id')
        ).order_by('total_amount')

        total_spent = abs(metrics['expenses_this_month']) or Decimal('1')
        category_data = [{
            'category_id': c['category__id'],
            'category_name': c['category__name'] or 'Uncategorized',
            'category_icon': c['category__icon'] or 'circle',
            'category_color': c['category__color'] or '#6B7280',
            'total_amount': c['total_amount'],
            'transaction_count': c['transaction_count'],
            'percentage': float(abs(c['total_amount']) / total_spent * 100),
        } for c in categories]

        # Recent transactions (last 10)
        # DRF EDUCATIONAL NOTE - Prefetch Related
        # =======================================
        # Use prefetch_related() for reverse ForeignKey and ManyToMany
        # Use select_related() for forward ForeignKey
        # This loads related objects in bulk, avoiding N+1 queries
        recent = Transaction.objects.filter(
            wallet=wallet
        ).select_related(
            'category'
        ).prefetch_related(
            'tags'
        ).order_by('-date')[:10]

        # Calculate balance
        total = Transaction.objects.filter(wallet=wallet).aggregate(
            total=Coalesce(Sum('amount'), Decimal('0'))
        )['total']
        balance = wallet.initial_value + total

        data = {
            'wallet_id': wallet.id,
            'wallet_name': wallet.name,
            'currency': wallet.currency,
            'balance': balance,
            'metrics': metrics,
            'category_breakdown': category_data,
            'recent_transactions': TransactionSerializer(recent, many=True).data,
        }

        serializer = WalletDashboardSerializer(data)
        return Response(serializer.data)
```

---

## Phase 3: Balance Consistency

### Current Issue
Balance is calculated in `WalletSerializer.get_balance()` which runs a new query per wallet. This can cause:
- N+1 queries when listing wallets
- Potential inconsistency if transactions change mid-request

### Solution: Use annotations consistently

```python
# In WalletList view's get_queryset():
def get_queryset(self):
    return Wallet.objects.filter(user=self.request.user).annotate(
        calculated_balance=F('initial_value') + Coalesce(
            Sum('transactions__amount'),
            Decimal('0'),
            output_field=DecimalField()
        )
    )

# Then in WalletSerializer, use the annotated field:
class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    def get_balance(self, obj):
        # Use annotated value if available, otherwise calculate
        if hasattr(obj, 'calculated_balance'):
            return obj.calculated_balance
        # Fallback for single wallet queries
        total = Transaction.objects.filter(wallet=obj).aggregate(
            Sum('amount')
        )['amount__sum'] or 0
        return obj.initial_value + total
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `wallets/serializers.py` | ADD dashboard serializers |
| `wallets/views.py` | ADD UserDashboard, WalletMetrics views |
| `wallets/urls.py` | ADD `/dashboard/` and `/wallets/{id}/metrics/` routes |

---

## Testing Checklist

- [ ] Dashboard returns correct totals across multiple wallets
- [ ] Category percentages sum to 100%
- [ ] Monthly trend shows correct months in order
- [ ] Empty wallets handled gracefully (no division by zero)
- [ ] Currency mixing handled (or documented as limitation)
- [ ] Performance acceptable with 1000+ transactions

---

## DRF Concepts Learned

1. **Non-model serializers** - For aggregated/computed data
2. **Aggregation** - Sum, Count, Avg, Min, Max
3. **annotate() vs aggregate()** - Per-object vs total
4. **Q objects** - Complex filtering conditions
5. **Coalesce** - Handle NULL in aggregations
6. **TruncMonth** - Date truncation for grouping
7. **select_related/prefetch_related** - Query optimization
8. **APIView** - Full control over response building
