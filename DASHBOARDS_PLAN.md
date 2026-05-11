# Dashboards Implementation Plan

Two endpoints:
1. `GET /api/dashboard/` — user-level summary across all wallets
2. `GET /api/wallets/{wallet_id}/metrics/` — single wallet deep-dive

**Status:** Not started

---

## Phase 1: User Main Dashboard

### Endpoint
```
GET /api/dashboard/
```

### Response
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
    { "month": "2025-01", "income": "3000.00", "expenses": "1500.00", "net": "1500.00" }
  ]
}
```

### Backend — Serializers (`wallets/serializers.py`)

```python
class DashboardSummarySerializer(serializers.Serializer):
    total_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_income_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_expenses_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)

class WalletSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    currency = serializers.CharField()
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    income_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    expenses_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)

class CategorySpendingSerializer(serializers.Serializer):
    category_id = serializers.UUIDField(allow_null=True)
    category_name = serializers.CharField()
    category_icon = serializers.CharField(allow_blank=True)
    category_color = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    transaction_count = serializers.IntegerField()
    percentage = serializers.FloatField()

class MonthlyTrendSerializer(serializers.Serializer):
    month = serializers.CharField()  # "2025-01"
    income = serializers.DecimalField(max_digits=12, decimal_places=2)
    expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    net = serializers.DecimalField(max_digits=12, decimal_places=2)

class UserDashboardSerializer(serializers.Serializer):
    summary = DashboardSummarySerializer()
    wallets = WalletSummarySerializer(many=True)
    spending_by_category = CategorySpendingSerializer(many=True)
    monthly_trend = MonthlyTrendSerializer(many=True)
```

### Backend — View (`wallets/views.py`)

```python
from django.db.models import Sum, Count, Q, DecimalField
from django.db.models.functions import Coalesce, TruncMonth
from decimal import Decimal

class UserDashboard(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        user = request.user
        now = datetime.now()

        wallets = Wallet.objects.filter(user=user).annotate(
            total_transactions=Coalesce(
                Sum('transactions__amount'), Decimal('0'), output_field=DecimalField()
            ),
            income_this_month=Coalesce(
                Sum('transactions__amount', filter=Q(
                    transactions__amount__gt=0,
                    transactions__date__month=now.month,
                    transactions__date__year=now.year
                )), Decimal('0'), output_field=DecimalField()
            ),
            expenses_this_month=Coalesce(
                Sum('transactions__amount', filter=Q(
                    transactions__amount__lt=0,
                    transactions__date__month=now.month,
                    transactions__date__year=now.year
                )), Decimal('0'), output_field=DecimalField()
            )
        )

        wallet_data = []
        total_balance = total_income = total_expenses = Decimal('0')

        for wallet in wallets:
            balance = wallet.initial_value + wallet.total_transactions
            total_balance += balance
            total_income += wallet.income_this_month
            total_expenses += abs(wallet.expenses_this_month)
            wallet_data.append({
                'id': wallet.id, 'name': wallet.name, 'currency': wallet.currency,
                'balance': balance,
                'income_this_month': wallet.income_this_month,
                'expenses_this_month': abs(wallet.expenses_this_month),
            })

        # Category spending (expenses this month, grouped)
        category_spending = Transaction.objects.filter(
            wallet__user=user, amount__lt=0,
            date__month=now.month, date__year=now.year
        ).values(
            'category__id', 'category__name', 'category__icon', 'category__color'
        ).annotate(
            total_amount=Sum('amount'), transaction_count=Count('id')
        ).order_by('total_amount')

        total_spent = abs(total_expenses) or Decimal('1')
        spending_data = [{
            'category_id': c['category__id'],
            'category_name': c['category__name'] or 'Uncategorized',
            'category_icon': c['category__icon'] or 'circle',
            'category_color': c['category__color'] or '#6B7280',
            'total_amount': c['total_amount'],
            'transaction_count': c['transaction_count'],
            'percentage': float(abs(c['total_amount']) / total_spent * 100),
        } for c in category_spending]

        # Monthly trend (last 6 months)
        six_months_ago = datetime(
            now.year if now.month > 6 else now.year - 1,
            now.month - 6 if now.month > 6 else now.month + 6, 1
        )
        monthly_data = Transaction.objects.filter(
            wallet__user=user, date__gte=six_months_ago
        ).annotate(month=TruncMonth('date')).values('month').annotate(
            income=Coalesce(Sum('amount', filter=Q(amount__gt=0)), Decimal('0')),
            expenses=Coalesce(Sum('amount', filter=Q(amount__lt=0)), Decimal('0'))
        ).order_by('month')

        trend_data = [{
            'month': item['month'].strftime('%Y-%m'),
            'income': item['income'],
            'expenses': abs(item['expenses']),
            'net': item['income'] + item['expenses'],
        } for item in monthly_data]

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
        return Response(UserDashboardSerializer(data).data)
```

---

## Phase 2: Wallet Metrics

### Endpoint
```
GET /api/wallets/{wallet_id}/metrics/
```

### Response
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
  "category_breakdown": [...],
  "recent_transactions": [...]
}
```

### Backend — View (`wallets/views.py`)

```python
from django.db.models import Avg, Min, Max

class WalletMetrics(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, wallet_id):
        wallet = get_object_or_404(Wallet, id=wallet_id, user=request.user)
        now = datetime.now()

        metrics = Transaction.objects.filter(wallet=wallet).aggregate(
            total_transactions=Count('id'),
            income_count=Count('id', filter=Q(amount__gt=0)),
            expense_count=Count('id', filter=Q(amount__lt=0)),
            income_this_month=Coalesce(Sum('amount', filter=Q(
                amount__gt=0, date__month=now.month, date__year=now.year
            )), Decimal('0')),
            expenses_this_month=Coalesce(Sum('amount', filter=Q(
                amount__lt=0, date__month=now.month, date__year=now.year
            )), Decimal('0')),
            average_transaction=Coalesce(Avg('amount'), Decimal('0')),
            largest_expense=Min('amount'),
            largest_income=Max('amount'),
        )
        metrics['net_this_month'] = metrics['income_this_month'] + metrics['expenses_this_month']
        metrics['expenses_this_month'] = abs(metrics['expenses_this_month'])

        categories = Transaction.objects.filter(wallet=wallet, amount__lt=0).values(
            'category__id', 'category__name', 'category__icon', 'category__color'
        ).annotate(
            total_amount=Sum('amount'), transaction_count=Count('id')
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

        recent = Transaction.objects.filter(wallet=wallet).select_related(
            'category'
        ).prefetch_related('tags').order_by('-date')[:10]

        total = Transaction.objects.filter(wallet=wallet).aggregate(
            total=Coalesce(Sum('amount'), Decimal('0'))
        )['total']

        data = {
            'wallet_id': wallet.id, 'wallet_name': wallet.name,
            'currency': wallet.currency,
            'balance': wallet.initial_value + total,
            'metrics': metrics,
            'category_breakdown': category_data,
            'recent_transactions': TransactionSerializer(recent, many=True, context={'request': request}).data,
        }
        return Response(WalletDashboardSerializer(data).data)
```

---

## Phase 3: Balance Query Optimization

The current `WalletSerializer.get_balance()` runs one query per wallet when listing. Fix by annotating in the queryset:

```python
# WalletList.get_queryset():
def get_queryset(self):
    return Wallet.objects.filter(user=self.request.user).annotate(
        calculated_balance=F('initial_value') + Coalesce(
            Sum('transactions__amount'), Decimal('0'), output_field=DecimalField()
        )
    )

# WalletSerializer.get_balance():
def get_balance(self, obj):
    if hasattr(obj, 'calculated_balance'):
        return obj.calculated_balance
    total = Transaction.objects.filter(wallet=obj).aggregate(Sum('amount'))['amount__sum'] or 0
    return obj.initial_value + total
```

---

## Files to Change

| File | Action |
|---|---|
| `wallets/serializers.py` | Add `DashboardSummarySerializer`, `WalletSummarySerializer`, `CategorySpendingSerializer`, `MonthlyTrendSerializer`, `UserDashboardSerializer`, `WalletMetricsSerializer`, `WalletDashboardSerializer` |
| `wallets/views.py` | Add `UserDashboard`, `WalletMetrics` views |
| `wallets/urls.py` | Add `dashboard/` and `<wallet_id>/metrics/` routes |
| `frontend/app/dashboard/page.tsx` | Build dashboard UI using new endpoints |

---

## Testing Checklist

- [ ] Totals correct across multiple wallets
- [ ] Category percentages sum to ~100%
- [ ] Monthly trend months appear in order
- [ ] Empty wallet (no transactions) returns zeros, no division-by-zero
- [ ] `recent_transactions` respects ownership
