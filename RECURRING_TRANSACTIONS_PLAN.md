# Recurring Transactions Plan

Templates that auto-generate transactions on a schedule. Processed by a daily management command.

**Status:** Not started

---

## Architecture

```
RecurringTransaction  (template — defines schedule + amount)
        │
        ▼ generates
Transaction           (actual record created by processor)
        │
        ▼ tracked by
RecurringTransactionExecution  (audit log — prevents duplicates)
```

Processing flow:
1. User creates `RecurringTransaction` with frequency, start date, optional end date
2. `python manage.py process_recurring` runs daily (cron)
3. Command finds templates where `next_occurrence <= today` and `is_active=True`
4. Creates `Transaction`, records `RecurringTransactionExecution`, advances `next_occurrence`

---

## Phase 1: Models

Add to `wallets/models.py`:

```python
from dateutil.relativedelta import relativedelta
import calendar

class RecurringTransaction(models.Model):
    class Frequency(models.TextChoices):
        DAILY     = 'daily',     'Daily'
        WEEKLY    = 'weekly',    'Weekly'
        BIWEEKLY  = 'biweekly',  'Every 2 weeks'
        MONTHLY   = 'monthly',   'Monthly'
        QUARTERLY = 'quarterly', 'Quarterly'
        YEARLY    = 'yearly',    'Yearly'

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet     = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='recurring_transactions')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_transactions')

    # Copied to each generated Transaction
    note     = models.CharField(max_length=100)
    amount   = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=[('usd','usd'),('eur','eur'),('gbp','gbp'),('pln','pln')])
    category = models.ForeignKey('TransactionCategory', on_delete=models.SET_NULL, null=True, blank=True, related_name='recurring_transactions')
    tags     = models.ManyToManyField('UserTransactionTag', related_name='recurring_transactions', blank=True)

    # Schedule
    frequency    = models.CharField(max_length=20, choices=Frequency.choices, default=Frequency.MONTHLY)
    start_date   = models.DateField()
    end_date     = models.DateField(null=True, blank=True)
    day_of_week  = models.IntegerField(null=True, blank=True)   # 0=Mon … 6=Sun (weekly only)
    day_of_month = models.IntegerField(null=True, blank=True)   # 1-31, -1=last day (monthly only)

    # State
    is_active       = models.BooleanField(default=True)
    next_occurrence = models.DateField(null=True, blank=True)
    last_processed  = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_occurrence', '-created_at']

    def save(self, *args, **kwargs):
        if not self.next_occurrence and self.start_date:
            self.next_occurrence = self.start_date
        super().save(*args, **kwargs)

    def calculate_next_occurrence(self, from_date=None):
        from datetime import date, timedelta
        base = from_date or date.today()

        if self.frequency == self.Frequency.DAILY:
            return base + timedelta(days=1)
        elif self.frequency == self.Frequency.WEEKLY:
            days_ahead = self.day_of_week - base.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return base + timedelta(days=days_ahead)
        elif self.frequency == self.Frequency.BIWEEKLY:
            return base + timedelta(weeks=2)
        elif self.frequency == self.Frequency.MONTHLY:
            next_month = base + relativedelta(months=1)
            if self.day_of_month == -1:
                last_day = calendar.monthrange(next_month.year, next_month.month)[1]
                return next_month.replace(day=last_day)
            else:
                last_day = calendar.monthrange(next_month.year, next_month.month)[1]
                return next_month.replace(day=min(self.day_of_month, last_day))
        elif self.frequency == self.Frequency.QUARTERLY:
            return base + relativedelta(months=3)
        elif self.frequency == self.Frequency.YEARLY:
            return base + relativedelta(years=1)

    def is_due(self):
        from datetime import date
        if not self.is_active:
            return False
        if self.end_date and date.today() > self.end_date:
            return False
        return bool(self.next_occurrence and self.next_occurrence <= date.today())


class RecurringTransactionExecution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recurring_transaction = models.ForeignKey(RecurringTransaction, on_delete=models.CASCADE, related_name='executions')
    transaction           = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='recurring_source')
    scheduled_date        = models.DateField()
    executed_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-executed_at']
        unique_together = [['recurring_transaction', 'scheduled_date']]  # prevents duplicates
```

Migration: `python manage.py makemigrations wallets --name add_recurring_transactions`

---

## Phase 2: Serializers

Add to `wallets/serializers.py`:

```python
class RecurringTransactionSerializer(serializers.ModelSerializer):
    category       = CategorySerializer(read_only=True)
    tags           = TagSerializer(many=True, read_only=True)
    category_id    = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    tag_ids        = serializers.ListField(child=serializers.UUIDField(), write_only=True, required=False, default=[])
    execution_count = serializers.SerializerMethodField()
    is_due         = serializers.SerializerMethodField()

    class Meta:
        model = RecurringTransaction
        fields = [
            'id', 'note', 'amount', 'currency',
            'category', 'category_id', 'tags', 'tag_ids',
            'frequency', 'start_date', 'end_date',
            'day_of_week', 'day_of_month',
            'is_active', 'next_occurrence', 'last_processed',
            'execution_count', 'is_due', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'next_occurrence', 'last_processed', 'created_at', 'updated_at']

    def get_execution_count(self, obj): return obj.executions.count()
    def get_is_due(self, obj): return obj.is_due()

    def validate(self, data):
        start_date = data.get('start_date')
        end_date   = data.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({'end_date': 'Must be after start date.'})
        frequency = data.get('frequency')
        if frequency == 'weekly' and data.get('day_of_week') is None:
            raise serializers.ValidationError({'day_of_week': 'Required for weekly frequency.'})
        if frequency == 'monthly' and data.get('day_of_month') is None:
            raise serializers.ValidationError({'day_of_month': 'Required for monthly frequency.'})
        wallet = self.context.get('wallet')
        if wallet and data.get('currency') != wallet.currency:
            raise serializers.ValidationError({'currency': f'Must match wallet currency ({wallet.currency}).'})
        return data

    def create(self, validated_data):
        category_id = validated_data.pop('category_id', None)
        tag_ids     = validated_data.pop('tag_ids', [])
        if category_id:
            validated_data['category'] = TransactionCategory.objects.get(id=category_id)
        instance = super().create(validated_data)
        if tag_ids:
            instance.tags.set(UserTransactionTag.objects.filter(id__in=tag_ids, user=self.context['request'].user))
        return instance

    def update(self, instance, validated_data):
        category_id = validated_data.pop('category_id', None)
        tag_ids     = validated_data.pop('tag_ids', None)
        if category_id:
            validated_data['category'] = TransactionCategory.objects.get(id=category_id)
        elif category_id is None and 'category_id' in self.initial_data:
            validated_data['category'] = None
        instance = super().update(instance, validated_data)
        if tag_ids is not None:
            instance.tags.set(UserTransactionTag.objects.filter(id__in=tag_ids, user=self.context['request'].user))
        return instance


class RecurringTransactionExecutionSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(read_only=True)
    class Meta:
        model = RecurringTransactionExecution
        fields = ['id', 'scheduled_date', 'executed_at', 'transaction']
        read_only_fields = fields
```

---

## Phase 3: Views

Add to `wallets/views.py`:

```python
class WalletRecurringTransactionList(generics.ListCreateAPIView):
    serializer_class = RecurringTransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_wallet(self):
        return get_object_or_404(Wallet, id=self.kwargs['wallet_id'], user=self.request.user)

    def get_queryset(self):
        return RecurringTransaction.objects.filter(wallet=self.get_wallet())

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['wallet'] = self.get_wallet()
        return ctx

    def perform_create(self, serializer):
        wallet = self.get_wallet()
        serializer.save(wallet=wallet, created_by=self.request.user, currency=wallet.currency)


class WalletRecurringTransactionDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RecurringTransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_wallet(self):
        return get_object_or_404(Wallet, id=self.kwargs['wallet_id'], user=self.request.user)

    def get_queryset(self):
        return RecurringTransaction.objects.filter(wallet=self.get_wallet())

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['wallet'] = self.get_wallet()
        return ctx


class RecurringTransactionExecutionList(generics.ListAPIView):
    serializer_class = RecurringTransactionExecutionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        wallet    = get_object_or_404(Wallet, id=self.kwargs['wallet_id'], user=self.request.user)
        recurring = get_object_or_404(RecurringTransaction, id=self.kwargs['pk'], wallet=wallet)
        return RecurringTransactionExecution.objects.filter(recurring_transaction=recurring)
```

---

## Phase 4: URLs

Add to `wallets/urls.py`:

```python
path('<uuid:wallet_id>/recurring/', WalletRecurringTransactionList.as_view(), name='wallet-recurring-list'),
path('<uuid:wallet_id>/recurring/<uuid:pk>/', WalletRecurringTransactionDetail.as_view(), name='wallet-recurring-detail'),
path('<uuid:wallet_id>/recurring/<uuid:pk>/executions/', RecurringTransactionExecutionList.as_view(), name='wallet-recurring-executions'),
```

---

## Phase 5: Management Command

Create `wallets/management/commands/process_recurring.py`:

```python
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone
from datetime import date
from wallets.models import RecurringTransaction, RecurringTransactionExecution, Transaction

class Command(BaseCommand):
    help = 'Process due recurring transactions'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--force-date', type=str, help='YYYY-MM-DD')

    def handle(self, *args, **options):
        dry_run   = options['dry_run']
        force_date = options.get('force_date')
        today = date.fromisoformat(force_date) if force_date else date.today()

        due = RecurringTransaction.objects.filter(
            is_active=True, next_occurrence__lte=today
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        ).select_related('wallet', 'category', 'created_by').prefetch_related('tags')

        created = errors = 0
        for recurring in due:
            if dry_run:
                self.stdout.write(f'[DRY RUN] Would process: {recurring.note}')
                continue
            try:
                with db_transaction.atomic():
                    if RecurringTransactionExecution.objects.filter(
                        recurring_transaction=recurring, scheduled_date=recurring.next_occurrence
                    ).exists():
                        continue  # Already processed (idempotency)

                    txn = Transaction.objects.create(
                        wallet=recurring.wallet, created_by=recurring.created_by,
                        note=recurring.note, amount=recurring.amount,
                        currency=recurring.currency, category=recurring.category,
                        date=timezone.make_aware(
                            datetime.combine(recurring.next_occurrence, datetime.min.time())
                        ),
                    )
                    txn.tags.set(recurring.tags.all())

                    RecurringTransactionExecution.objects.create(
                        recurring_transaction=recurring,
                        transaction=txn,
                        scheduled_date=recurring.next_occurrence,
                    )
                    recurring.next_occurrence = recurring.calculate_next_occurrence(recurring.next_occurrence)
                    recurring.last_processed  = timezone.now()
                    recurring.save()
                    created += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f'Error on {recurring.note}: {e}')

        self.stdout.write(f'Created: {created}  Errors: {errors}')
```

Cron setup (daily at 6am):
```
0 6 * * * cd /path/to/backend && /path/to/venv/bin/python manage.py process_recurring
```

---

## Phase 6: Frontend

- **Settings page** — Recurring Transactions tab: list all, toggle active, edit, view execution history, delete
- **TransactionDialog** — "Make recurring" checkbox that expands schedule options (frequency, day, end date)

---

## Files to Change

| File | Action |
|---|---|
| `wallets/models.py` | Add `RecurringTransaction`, `RecurringTransactionExecution` |
| `wallets/serializers.py` | Add `RecurringTransactionSerializer`, `RecurringTransactionExecutionSerializer` |
| `wallets/views.py` | Add 3 views |
| `wallets/urls.py` | Add 3 routes |
| `wallets/management/commands/process_recurring.py` | Create |
| `wallets/migrations/` | New migration |
| `frontend/app/settings/page.tsx` | Add Recurring tab |
| `frontend/components/TransactionDialog.tsx` | Add "Make recurring" toggle |

---

## Testing Checklist

- [ ] All 6 frequencies create correct `next_occurrence`
- [ ] `day_of_week` required for weekly, `day_of_month` for monthly
- [ ] End date stops processing
- [ ] `is_active=False` skips processing
- [ ] Running command twice doesn't create duplicates (idempotency via `unique_together`)
- [ ] Tags copied correctly to generated transactions
- [ ] Execution history visible in API
