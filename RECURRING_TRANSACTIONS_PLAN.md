# Recurring Transactions Implementation Plan

## Overview
Implement recurring (scheduled) transactions that automatically create regular transactions based on a defined pattern (daily, weekly, monthly, etc.).

Priority: 4/5 | Complexity: 4/5

---

## DRF Learning Goals

This feature will teach you:
- **Custom model design** with scheduling logic
- **Django signals** for post-save hooks
- **Management commands** for background processing
- **Date/time handling** with dateutil
- **Validation patterns** for complex business rules
- **Nested serializers** for related data

---

## Architecture Overview

```
RecurringTransaction (template)
        │
        ▼ (generates)
    Transaction (actual record)
        │
        ▼ (tracked by)
RecurringTransactionExecution (audit log)
```

**Flow:**
1. User creates RecurringTransaction (template with schedule)
2. Management command runs daily (via cron/celery)
3. Command finds due recurring transactions
4. Creates actual Transaction records
5. Logs execution in RecurringTransactionExecution
6. Updates next_occurrence date

---

## Phase 1: Models

### File: `wallets/models.py`

```python
from dateutil.relativedelta import relativedelta
import calendar


class RecurringTransaction(models.Model):
    """
    Template for automatically recurring transactions.

    DRF EDUCATIONAL NOTE - Model Design Patterns
    ============================================
    When designing models for scheduling/recurring tasks, consider:

    1. **Template vs Instance**: This model is a TEMPLATE that GENERATES
       actual Transaction instances. Don't confuse the two.

    2. **State Machine**: Use fields like is_active, next_occurrence to
       track the recurring transaction's lifecycle.

    3. **Audit Trail**: Keep RecurringTransactionExecution records to
       know what was created and when (for debugging/support).

    4. **Idempotency**: Design so running the processor twice doesn't
       create duplicate transactions.

    Scheduling Patterns
    ===================
    Common approaches for "day of month" with months of varying length:
    - day_of_month=31: On months with fewer days, use last day
    - day_of_month=29: Feb in non-leap years → use Feb 28
    - Alternative: "last day of month" as special value (-1)

    Frequency Choices
    =================
    Keep choices simple initially. You can always add more later.
    Complex patterns (e.g., "every 2nd Tuesday") require more fields
    or a cron-like expression system.
    """

    class Frequency(models.TextChoices):
        """
        DRF EDUCATIONAL NOTE - TextChoices
        ==================================
        Django 3.0+ provides TextChoices for cleaner choice fields.
        Benefits:
        - Type-safe constants (Frequency.DAILY vs 'daily')
        - Auto-generates choices tuple for model field
        - Better IDE autocomplete
        - Can add methods to the enum class
        """
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        BIWEEKLY = 'biweekly', 'Every 2 weeks'
        MONTHLY = 'monthly', 'Monthly'
        QUARTERLY = 'quarterly', 'Quarterly'
        YEARLY = 'yearly', 'Yearly'

    # Identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='recurring_transactions'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recurring_transactions'
    )

    # Transaction template data (copied to each generated transaction)
    note = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=[
        ('usd', 'USD'),
        ('eur', 'EUR'),
        ('gbp', 'GBP'),
        ('pln', 'PLN'),
    ])
    category = models.ForeignKey(
        'TransactionCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recurring_transactions'
    )
    tags = models.ManyToManyField(
        'UserTransactionTag',
        related_name='recurring_transactions',
        blank=True
    )

    # Schedule configuration
    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.MONTHLY
    )
    start_date = models.DateField(
        help_text="First occurrence date"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="Last occurrence date (null = indefinite)"
    )

    # For weekly recurrences: which day (0=Monday, 6=Sunday)
    day_of_week = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text="For weekly: 0=Mon, 1=Tue, ..., 6=Sun"
    )

    # For monthly recurrences: which day (1-31, or -1 for last day)
    day_of_month = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(-1), MaxValueValidator(31)],
        help_text="For monthly: 1-31, or -1 for last day of month"
    )

    # State tracking
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive recurring transactions won't generate new transactions"
    )
    next_occurrence = models.DateField(
        null=True,
        blank=True,
        help_text="Calculated: next date this will generate a transaction"
    )
    last_processed = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this was processed by the scheduler"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_occurrence', '-created_at']
        verbose_name = 'Recurring Transaction'
        verbose_name_plural = 'Recurring Transactions'

    def __str__(self):
        return f"{self.note} ({self.get_frequency_display()})"

    def calculate_next_occurrence(self, from_date=None):
        """
        Calculate the next occurrence date based on frequency.

        DRF EDUCATIONAL NOTE - Business Logic in Models
        ===============================================
        Where to put business logic?

        Option 1: Model methods (like this one)
        - Good for: Logic tied to single instance
        - Good for: Reusable across views/serializers
        - Example: calculate_next_occurrence(), is_due()

        Option 2: Serializer validation/methods
        - Good for: Input validation, transformation
        - Good for: Request-specific logic

        Option 3: Service layer (separate module)
        - Good for: Complex multi-model operations
        - Good for: External service calls
        - Example: process_recurring_transactions()

        Option 4: Manager methods (MyModel.objects.custom_method())
        - Good for: Queryset operations
        - Example: RecurringTransaction.objects.get_due_today()
        """
        from datetime import date, timedelta

        base_date = from_date or date.today()

        if self.frequency == self.Frequency.DAILY:
            return base_date + timedelta(days=1)

        elif self.frequency == self.Frequency.WEEKLY:
            # Next occurrence of day_of_week
            days_ahead = self.day_of_week - base_date.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return base_date + timedelta(days=days_ahead)

        elif self.frequency == self.Frequency.BIWEEKLY:
            return base_date + timedelta(weeks=2)

        elif self.frequency == self.Frequency.MONTHLY:
            next_month = base_date + relativedelta(months=1)
            if self.day_of_month == -1:
                # Last day of month
                last_day = calendar.monthrange(next_month.year, next_month.month)[1]
                return next_month.replace(day=last_day)
            else:
                # Specific day, handle months with fewer days
                last_day = calendar.monthrange(next_month.year, next_month.month)[1]
                day = min(self.day_of_month, last_day)
                return next_month.replace(day=day)

        elif self.frequency == self.Frequency.QUARTERLY:
            return base_date + relativedelta(months=3)

        elif self.frequency == self.Frequency.YEARLY:
            return base_date + relativedelta(years=1)

        return None

    def is_due(self):
        """Check if this recurring transaction should be processed today."""
        from datetime import date
        if not self.is_active:
            return False
        if self.end_date and date.today() > self.end_date:
            return False
        if self.next_occurrence and self.next_occurrence <= date.today():
            return True
        return False

    def save(self, *args, **kwargs):
        """
        DRF EDUCATIONAL NOTE - Overriding save()
        ========================================
        Override save() for:
        - Auto-calculating fields before save
        - Validation that depends on multiple fields
        - Triggering side effects (use signals instead usually)

        Always call super().save() at the end!

        For initial next_occurrence, use start_date if not set.
        """
        if not self.next_occurrence and self.start_date:
            self.next_occurrence = self.start_date
        super().save(*args, **kwargs)


class RecurringTransactionExecution(models.Model):
    """
    Audit log of transactions created from recurring templates.

    DRF EDUCATIONAL NOTE - Audit/History Tables
    ===========================================
    Audit tables are crucial for:
    1. Debugging: "Why was this transaction created?"
    2. Support: "Show me all auto-created transactions"
    3. Compliance: "Prove when/how this was generated"
    4. Idempotency: "Don't create duplicate if already processed"

    Design patterns:
    - Link to both template (RecurringTransaction) and result (Transaction)
    - Store execution timestamp
    - Consider storing snapshot of template at execution time
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recurring_transaction = models.ForeignKey(
        RecurringTransaction,
        on_delete=models.CASCADE,
        related_name='executions'
    )
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name='recurring_source'
    )
    scheduled_date = models.DateField(
        help_text="The date this was supposed to execute"
    )
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-executed_at']
        # Prevent duplicate executions for same date
        unique_together = [['recurring_transaction', 'scheduled_date']]

    def __str__(self):
        return f"{self.recurring_transaction.note} → {self.transaction.id}"
```

### Custom Manager (Optional Enhancement)

```python
class RecurringTransactionManager(models.Manager):
    """
    DRF EDUCATIONAL NOTE - Custom Managers
    =====================================
    Custom managers add reusable queryset methods.
    Access via: RecurringTransaction.objects.get_due_today()

    Benefits:
    - Encapsulate common queries
    - Keep views/serializers clean
    - Single source of truth for business logic
    """

    def get_due_today(self):
        """Get all active recurring transactions due for processing."""
        from datetime import date
        return self.filter(
            is_active=True,
            next_occurrence__lte=date.today()
        ).filter(
            models.Q(end_date__isnull=True) |
            models.Q(end_date__gte=date.today())
        )

    def for_user(self, user):
        """Get all recurring transactions for a user."""
        return self.filter(created_by=user)

    def for_wallet(self, wallet):
        """Get all recurring transactions for a wallet."""
        return self.filter(wallet=wallet)


# Add to RecurringTransaction model:
# objects = RecurringTransactionManager()
```

---

## Phase 2: Serializers

### File: `wallets/serializers.py`

```python
class RecurringTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for recurring transaction CRUD.

    DRF EDUCATIONAL NOTE - Complex Validation
    =========================================
    When validation depends on multiple fields, use:

    1. Field-level: validate_<field>(self, value)
       - Single field validation
       - Return value or raise ValidationError

    2. Object-level: validate(self, data)
       - Cross-field validation
       - Access all fields via data dict
       - Return data or raise ValidationError

    3. Custom validators: validators=[my_validator]
       - Reusable validation functions
       - Can be shared across serializers
    """
    # Read-only nested serializers for GET responses
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)

    # Write-only IDs for POST/PUT
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        default=[]
    )

    # Computed fields
    execution_count = serializers.SerializerMethodField()
    is_due = serializers.SerializerMethodField()

    class Meta:
        model = RecurringTransaction
        fields = [
            'id', 'note', 'amount', 'currency',
            'category', 'category_id', 'tags', 'tag_ids',
            'frequency', 'start_date', 'end_date',
            'day_of_week', 'day_of_month',
            'is_active', 'next_occurrence', 'last_processed',
            'execution_count', 'is_due',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'next_occurrence', 'last_processed',
            'created_at', 'updated_at',
        ]

    def get_execution_count(self, obj):
        """Number of transactions created from this template."""
        return obj.executions.count()

    def get_is_due(self, obj):
        """Whether this recurring transaction is due for processing."""
        return obj.is_due()

    def validate_category_id(self, value):
        """Ensure category belongs to user."""
        if value:
            user = self.context['request'].user
            if not TransactionCategory.objects.filter(id=value, user=user).exists():
                raise serializers.ValidationError("Category not found.")
        return value

    def validate_tag_ids(self, value):
        """Ensure all tags belong to user."""
        user = self.context['request'].user
        for tag_id in value:
            if not UserTransactionTag.objects.filter(id=tag_id, user=user).exists():
                raise serializers.ValidationError(f"Tag {tag_id} not found.")
        return value

    def validate(self, data):
        """
        DRF EDUCATIONAL NOTE - Cross-Field Validation
        =============================================
        validate() receives all validated field data.
        Use it to check relationships between fields.

        Common patterns:
        - Date range validation (start < end)
        - Conditional requirements (if A then B required)
        - Business rule enforcement
        """
        # Validate date range
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date.'
            })

        # Validate day_of_week for weekly frequency
        frequency = data.get('frequency')
        if frequency == 'weekly' and data.get('day_of_week') is None:
            raise serializers.ValidationError({
                'day_of_week': 'Required for weekly frequency.'
            })

        # Validate day_of_month for monthly frequency
        if frequency == 'monthly' and data.get('day_of_month') is None:
            raise serializers.ValidationError({
                'day_of_month': 'Required for monthly frequency.'
            })

        # Validate currency matches wallet
        wallet = self.context.get('wallet')
        if wallet and data.get('currency') != wallet.currency:
            raise serializers.ValidationError({
                'currency': f'Must match wallet currency ({wallet.currency}).'
            })

        return data

    def create(self, validated_data):
        """
        DRF EDUCATIONAL NOTE - Handling ManyToMany in create()
        =====================================================
        ManyToMany fields need special handling because the
        parent object must exist (have a PK) before you can
        add related objects.

        Pattern:
        1. Pop M2M data from validated_data
        2. Create the instance
        3. Set M2M relationships using .set() or .add()
        """
        category_id = validated_data.pop('category_id', None)
        tag_ids = validated_data.pop('tag_ids', [])

        if category_id:
            validated_data['category'] = TransactionCategory.objects.get(id=category_id)

        instance = super().create(validated_data)

        if tag_ids:
            tags = UserTransactionTag.objects.filter(
                id__in=tag_ids,
                user=self.context['request'].user
            )
            instance.tags.set(tags)

        return instance

    def update(self, instance, validated_data):
        """Handle category and tags on update."""
        category_id = validated_data.pop('category_id', None)
        tag_ids = validated_data.pop('tag_ids', None)

        if category_id:
            validated_data['category'] = TransactionCategory.objects.get(id=category_id)
        elif category_id is None and 'category_id' in self.initial_data:
            validated_data['category'] = None

        instance = super().update(instance, validated_data)

        if tag_ids is not None:
            tags = UserTransactionTag.objects.filter(
                id__in=tag_ids,
                user=self.context['request'].user
            )
            instance.tags.set(tags)

        return instance


class RecurringTransactionExecutionSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for execution history.

    DRF EDUCATIONAL NOTE - Read-Only Serializers
    ============================================
    For audit/history tables, often you only need read access.
    Use read_only=True on the serializer or individual fields
    to prevent accidental writes.
    """
    transaction = TransactionSerializer(read_only=True)

    class Meta:
        model = RecurringTransactionExecution
        fields = ['id', 'scheduled_date', 'executed_at', 'transaction']
        read_only_fields = fields  # All fields read-only
```

---

## Phase 3: Views

### File: `wallets/views.py`

```python
class WalletRecurringTransactionList(generics.ListCreateAPIView):
    """
    List/create recurring transactions for a wallet.

    GET  /api/wallets/{wallet_id}/recurring-transactions/
    POST /api/wallets/{wallet_id}/recurring-transactions/

    DRF EDUCATIONAL NOTE - Nested Routes
    ====================================
    When resources are nested (recurring-transactions under wallets),
    you need to:
    1. Get parent (wallet) from URL kwargs
    2. Filter queryset by parent
    3. Set parent on create (in perform_create)
    4. Pass parent to serializer context for validation
    """
    serializer_class = RecurringTransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_wallet(self):
        """Get and validate wallet ownership."""
        wallet_id = self.kwargs['wallet_id']
        return get_object_or_404(Wallet, id=wallet_id, user=self.request.user)

    def get_queryset(self):
        wallet = self.get_wallet()
        return RecurringTransaction.objects.filter(wallet=wallet)

    def get_serializer_context(self):
        """
        DRF EDUCATIONAL NOTE - Serializer Context
        =========================================
        Context is a dict passed to serializers containing:
        - request: The HTTP request object
        - view: The view instance
        - format: Requested format

        You can add custom data (like wallet) for use in
        serializer validation or field computation.
        """
        context = super().get_serializer_context()
        context['wallet'] = self.get_wallet()
        return context

    def perform_create(self, serializer):
        """Set wallet and user on create."""
        wallet = self.get_wallet()
        serializer.save(
            wallet=wallet,
            created_by=self.request.user,
            currency=wallet.currency  # Enforce wallet currency
        )


class WalletRecurringTransactionDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Get/update/delete a specific recurring transaction.

    GET    /api/wallets/{wallet_id}/recurring-transactions/{pk}/
    PUT    /api/wallets/{wallet_id}/recurring-transactions/{pk}/
    PATCH  /api/wallets/{wallet_id}/recurring-transactions/{pk}/
    DELETE /api/wallets/{wallet_id}/recurring-transactions/{pk}/
    """
    serializer_class = RecurringTransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_wallet(self):
        wallet_id = self.kwargs['wallet_id']
        return get_object_or_404(Wallet, id=wallet_id, user=self.request.user)

    def get_queryset(self):
        wallet = self.get_wallet()
        return RecurringTransaction.objects.filter(wallet=wallet)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['wallet'] = self.get_wallet()
        return context


class RecurringTransactionExecutionList(generics.ListAPIView):
    """
    View execution history for a recurring transaction.

    GET /api/wallets/{wallet_id}/recurring-transactions/{pk}/executions/

    DRF EDUCATIONAL NOTE - ListAPIView
    ==================================
    Use ListAPIView when you only need to list objects (no create).
    It's a simpler alternative to ListCreateAPIView when creation
    happens through other means (like background jobs).
    """
    serializer_class = RecurringTransactionExecutionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        wallet_id = self.kwargs['wallet_id']
        recurring_id = self.kwargs['pk']

        # Validate access
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        recurring = get_object_or_404(
            RecurringTransaction,
            id=recurring_id,
            wallet=wallet
        )

        return RecurringTransactionExecution.objects.filter(
            recurring_transaction=recurring
        )
```

---

## Phase 4: URLs

### File: `wallets/urls.py`

```python
# Add to urlpatterns:
path(
    'wallets/<uuid:wallet_id>/recurring-transactions/',
    WalletRecurringTransactionList.as_view(),
    name='wallet-recurring-list'
),
path(
    'wallets/<uuid:wallet_id>/recurring-transactions/<uuid:pk>/',
    WalletRecurringTransactionDetail.as_view(),
    name='wallet-recurring-detail'
),
path(
    'wallets/<uuid:wallet_id>/recurring-transactions/<uuid:pk>/executions/',
    RecurringTransactionExecutionList.as_view(),
    name='wallet-recurring-executions'
),
```

---

## Phase 5: Processing Command

### File: `wallets/management/commands/process_recurring.py`

```python
"""
Management command to process recurring transactions.

DRF EDUCATIONAL NOTE - Background Processing Options
===================================================
For recurring/scheduled tasks, you have several options:

1. Management Command + Cron (this approach)
   - Simple, no extra dependencies
   - Run via: crontab -e → "0 6 * * * python manage.py process_recurring"
   - Good for: Simple schedules, low volume

2. Celery + Celery Beat
   - More complex, requires Redis/RabbitMQ
   - Better for: High volume, complex schedules, retries
   - Django-Celery-Beat for DB-stored schedules

3. Django-Q
   - Simpler than Celery, uses Django ORM
   - Good middle ground

4. APScheduler
   - In-process scheduling
   - Good for: Single-server deployments

For your MVP, Cron + Management Command is sufficient.
Upgrade to Celery when you need:
- Retries on failure
- Distributed processing
- Real-time task queuing
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import date
from wallets.models import (
    RecurringTransaction,
    RecurringTransactionExecution,
    Transaction
)


class Command(BaseCommand):
    help = 'Process due recurring transactions and create actual transactions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without creating transactions',
        )
        parser.add_argument(
            '--force-date',
            type=str,
            help='Process as if today is this date (YYYY-MM-DD), for testing',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force_date = options.get('force_date')

        if force_date:
            from datetime import datetime
            today = datetime.strptime(force_date, '%Y-%m-%d').date()
            self.stdout.write(f"Using forced date: {today}")
        else:
            today = date.today()

        self.stdout.write(f"\nProcessing recurring transactions for {today}")
        self.stdout.write("=" * 50)

        # Get all due recurring transactions
        due_transactions = RecurringTransaction.objects.filter(
            is_active=True,
            next_occurrence__lte=today
        ).filter(
            # Not ended
            models.Q(end_date__isnull=True) |
            models.Q(end_date__gte=today)
        ).select_related('wallet', 'category', 'created_by').prefetch_related('tags')

        if not due_transactions.exists():
            self.stdout.write(self.style.WARNING('No recurring transactions due.'))
            return

        created_count = 0
        error_count = 0

        for recurring in due_transactions:
            self.stdout.write(f"\nProcessing: {recurring.note}")
            self.stdout.write(f"  Frequency: {recurring.get_frequency_display()}")
            self.stdout.write(f"  Amount: {recurring.amount} {recurring.currency}")
            self.stdout.write(f"  Next occurrence: {recurring.next_occurrence}")

            if dry_run:
                self.stdout.write(self.style.WARNING('  [DRY RUN] Would create transaction'))
                continue

            try:
                # Use atomic transaction for data integrity
                # DRF EDUCATIONAL NOTE - Database Transactions
                # ============================================
                # transaction.atomic() ensures all DB operations
                # either succeed together or fail together.
                # If any error occurs, all changes are rolled back.
                with transaction.atomic():
                    # Check for existing execution (idempotency)
                    if RecurringTransactionExecution.objects.filter(
                        recurring_transaction=recurring,
                        scheduled_date=recurring.next_occurrence
                    ).exists():
                        self.stdout.write(
                            self.style.WARNING(f'  Already processed for {recurring.next_occurrence}')
                        )
                        continue

                    # Create the actual transaction
                    new_transaction = Transaction.objects.create(
                        wallet=recurring.wallet,
                        created_by=recurring.created_by,
                        note=recurring.note,
                        amount=recurring.amount,
                        currency=recurring.currency,
                        category=recurring.category,
                        # Note: date field is auto_now_add, so it will be today
                    )

                    # Copy tags
                    new_transaction.tags.set(recurring.tags.all())

                    # Create execution record
                    RecurringTransactionExecution.objects.create(
                        recurring_transaction=recurring,
                        transaction=new_transaction,
                        scheduled_date=recurring.next_occurrence,
                    )

                    # Update next occurrence
                    recurring.next_occurrence = recurring.calculate_next_occurrence(
                        from_date=recurring.next_occurrence
                    )
                    recurring.last_processed = timezone.now()
                    recurring.save()

                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  Created transaction: {new_transaction.id}')
                    )
                    self.stdout.write(f'  Next occurrence: {recurring.next_occurrence}')

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'  ERROR: {str(e)}')
                )

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(f'Created: {created_count} transactions')
        )
        if error_count:
            self.stdout.write(
                self.style.ERROR(f'Errors: {error_count}')
            )
```

### Cron Setup

```bash
# Run daily at 6 AM
# Edit crontab: crontab -e

0 6 * * * cd /path/to/backend && /path/to/venv/bin/python manage.py process_recurring >> /var/log/recurring.log 2>&1
```

---

## Phase 6: Frontend Integration Points

### Settings Page - Manage Recurring Transactions

```
/settings → Recurring Transactions tab
- List all recurring transactions
- Toggle active/inactive
- Edit schedule
- View execution history
- Delete (with confirmation)
```

### Transaction Dialog - Mark as Recurring

```
When creating transaction:
[ ] Make this recurring
    Frequency: [Monthly ▼]
    Day: [15]
    End date: [Optional]
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `wallets/models.py` | ADD RecurringTransaction, RecurringTransactionExecution |
| `wallets/serializers.py` | ADD RecurringTransaction serializers |
| `wallets/views.py` | ADD recurring transaction views |
| `wallets/urls.py` | ADD recurring transaction routes |
| `wallets/management/commands/process_recurring.py` | CREATE processing command |
| `wallets/migrations/0008_recurring_transactions.py` | CREATE migration |

---

## Testing Checklist

- [ ] Create recurring transaction with all frequencies
- [ ] Validate day_of_week required for weekly
- [ ] Validate day_of_month required for monthly
- [ ] End date validation (must be after start)
- [ ] Currency must match wallet
- [ ] Processing creates correct transactions
- [ ] Idempotency: running twice doesn't duplicate
- [ ] Next occurrence calculates correctly
- [ ] End date stops processing
- [ ] is_active=False stops processing
- [ ] Execution history tracks all created transactions

---

## DRF Concepts Learned

1. **TextChoices** - Clean enum-like choices
2. **Custom Managers** - Reusable queryset methods
3. **Cross-field validation** - validate() method
4. **ManyToMany handling** - In create()/update()
5. **Serializer context** - Passing extra data
6. **Nested routes** - Parent resource in URL
7. **ListAPIView** - Read-only list endpoints
8. **Management commands** - Background processing
9. **transaction.atomic()** - Database integrity
10. **Idempotent operations** - Safe to retry
