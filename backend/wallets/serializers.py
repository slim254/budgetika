from rest_framework import serializers
from .models import (
    Transaction,
    UserTransactionTag,
    Wallet,
    TransactionCategory,
    RecurringTransaction,
    RecurringTransactionExecution,
    BudgetRule,
    BudgetMonthOverride,
    SavingsGoal,
)
from django.db.models import Sum
from decimal import Decimal
from django.utils import timezone
import uuid
from django.db import transaction as db_transaction
from .services import get_rate, SavingsGoalService
from datetime import date


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for user-scoped categories.

    DRF EDUCATIONAL NOTE - ModelSerializer
    ======================================
    ModelSerializer provides:
    1. Automatic field generation from model fields
    2. Built-in create() and update() methods
    3. Validation based on model field constraints (max_length, null, etc.)
    4. Automatic handling of ForeignKey/ManyToMany relationships

    Alternative: serializers.Serializer requires manual field definition
    and explicit create/update methods. Use when you need:
    - Non-model data structures
    - Complex custom validation
    - Different read/write representations

    Read-Only Fields Pattern
    ========================
    'id' is read_only because:
    - Generated automatically (UUIDField with default)
    - Should never be set by client
    - Prevents accidental ID manipulation
    """
    transaction_count = serializers.SerializerMethodField()

    class Meta:
        model = TransactionCategory
        fields = [
            'id', 'name', 'icon', 'color',
            'is_visible', 'is_archived',
            'transaction_count'
        ]
        read_only_fields = ['id']

    def get_transaction_count(self, obj):
        """
        DRF EDUCATIONAL NOTE - SerializerMethodField
        ============================================
        SerializerMethodField allows computed/derived fields in responses.
        The method name must follow the pattern: get_<field_name>

        Performance consideration: This runs a COUNT query for each category.
        For large datasets, consider:
        - Prefetching: queryset.prefetch_related('transactions')
        - Annotation: queryset.annotate(transaction_count=Count('transactions'))
        """
        return obj.transactions.count()
    
class TagSerializer(serializers.ModelSerializer):
    """
    Serializer for user-scoped tags.

    DRF EDUCATIONAL NOTE - Serializer Context
    =========================================
    The serializer receives 'context' containing:
    - request: The HTTP request object
    - view: The view instance
    - format: The requested format (json, xml, etc.)

    Access via: self.context['request'].user

    This allows user-specific logic in serializers without
    passing user explicitly to every method.

    Tags are shared across all user's wallets.
    """
    transaction_count = serializers.SerializerMethodField()

    class Meta:
        model = UserTransactionTag
        fields = ['id', 'name', 'icon', 'color', 'is_visible', 'transaction_count']
        read_only_fields = ['id']

    def get_transaction_count(self, obj):
        """Number of transactions using this tag."""
        return obj.transactions.count()


class TransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for Transaction model.

    Read fields: category (nested), tags (nested array)
    Write fields: category_id (UUID), tag_ids (array of UUIDs)

    The validate() method ensures transaction currency matches wallet currency.

    Example request JSON:
        {
            "note": "Weekly groceries",
            "amount": "-150.50",
            "currency": "usd",
            "category_id": "uuid-here",
            "tag_ids": ["uuid-1", "uuid-2"]
        }

    Example response JSON:
        {
            "id": "uuid",
            "note": "Weekly groceries",
            "amount": "-150.50",
            "currency": "usd",
            "date": "2025-12-05T10:30:00Z",
            "category": {"id": "...", "name": "Food", ...},
            "tags": [{"id": "...", "name": "groceries", ...}]
        }
    """
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        default=[]
    )
    peer_wallet = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = ['note', 'amount', 'currency', 'id', 'date', 'category', 'category_id', 'tags', 'tag_ids', 'transfer_ref', 'peer_wallet']
        read_only_fields = ['id', 'transfer_ref', 'peer_wallet']
    def validate_category_id(self, value):
        """
        DRF EDUCATIONAL NOTE - Field-Level Validation
        =============================================
        validate_<field_name>() is called for each field during validation.
        It receives the field value and should return the validated value
        or raise serializers.ValidationError.

        Order of validation:
        1. Field-level validation (validate_<field>)
        2. Object-level validation (validate())
        3. Serializer create()/update()
        """
        if value:
            user = self.context['request'].user
            if not TransactionCategory.objects.filter(id=value, user=user).exists():
                raise serializers.ValidationError("Category not found or doesn't belong to you.")
        return value
    
    def validate_tag_ids(self, value):
        """Ensure all tags belong to the user."""
        user = self.context['request'].user
        for tag_id in value:
            if not UserTransactionTag.objects.filter(id=tag_id, user=user).exists():
                raise serializers.ValidationError(f"Tag with id {tag_id} not found or doesn't belong to you.")
        return value

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

    def create(self, validated_data):
        """
        DRF EDUCATIONAL NOTE - Custom create() Method
        =============================================
        Override create() when you need to:
        - Handle nested data (like category_id -> category object)
        - Set fields that aren't directly mapped from request
        - Handle ManyToMany relationships (must be done after save)

        ManyToMany Note: You can't set M2M fields before save() because
        the object needs a primary key first. That's why we:
        1. Pop tag_ids from validated_data
        2. Create the instance
        3. Then set the tags using instance.tags.set()
        """
        category_id = validated_data.pop('category_id', None)
        tag_ids = validated_data.pop('tag_ids', [])
        if category_id:
            validated_data['category'] = TransactionCategory.objects.get(id=category_id)
        instance = super().create(validated_data)
        if tag_ids:
            tags = UserTransactionTag.objects.filter(id__in=tag_ids, user=self.context['request'].user)
            instance.tags.set(tags)
        return instance

    def update(self, instance, validated_data):
        """Handle category_id and tag_ids when updating transaction."""
        category_id = validated_data.pop('category_id', None)
        tag_ids = validated_data.pop('tag_ids', None)
        if category_id:
            validated_data['category'] = TransactionCategory.objects.get(id=category_id)
        elif category_id is None and 'category_id' in self.initial_data:
            validated_data['category'] = None
        instance = super().update(instance, validated_data)
        if tag_ids is not None:
            tags = UserTransactionTag.objects.filter(id__in=tag_ids, user=self.context['request'].user)
            instance.tags.set(tags)
        return instance

    def validate(self, data):
        """
        Custom validation to ensure transaction currency matches wallet currency.

        Args:
            data: The transaction data being validated

        Returns:
            data: Validated data if validation passes

        Raises:
            ValidationError: If transaction currency doesn't match wallet currency
        """
        wallet = self.context.get('wallet')
        
        currency = data.get('currency')
        if wallet and currency and wallet.currency != currency:
            raise serializers.ValidationError(
                f"Transaction currency ({currency}) must match wallet currency ({wallet.currency})."
            )
        return data


class WalletSerializer(serializers.ModelSerializer):
    """
    Serializer for Wallet model - includes a computed 'balance' field.

    The 'balance' field is not stored in the database but calculated on-the-fly
    using get_balance(). This is a common pattern in DRF when you need to provide
    calculated or derived data in API responses.

    Balance Calculation Formula:
        balance = initial_value + (sum of all income transactions) - (sum of all expense transactions)

    Example JSON Response:
        {
            "id": 1,
            "name": "Monthly Budget",
            "user": 1,
            "initial_value": "1000.00",
            "currency": "usd",
            "categories": [...],
            "transactions": [...],
            "balance": "1234.50"
        }

    Performance Note: The get_balance() method runs a new database query every
    time a wallet is serialized. For APIs with many wallets or high traffic,
    consider caching or using select_related/prefetch_related queries.
    """
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = '__all__'

    def get_balance(self, obj):
        """
        Calculate the current wallet balance based on initial value and transactions.

        Uses the `calculated_balance` annotation from the queryset when present
        (see WalletList.get_queryset) to avoid an N+1 query when listing wallets.
        Falls back to an aggregate query for detail views and other callers.
        """
        if hasattr(obj, 'calculated_balance') and obj.calculated_balance is not None:
            return obj.calculated_balance
        total = Transaction.objects.filter(wallet=obj).aggregate(Sum('amount'))['amount__sum'] or 0
        return obj.initial_value + total


class CSVParseSerializer(serializers.Serializer):
    """
    Serializer for CSV file upload during the parse step.

    Validates that the uploaded file:
    - Is a CSV file (by extension)
    - Does not exceed 5MB in size
    """
    file = serializers.FileField()

    def validate_file(self, value):
        """Validate file is CSV and under 5MB."""
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError("File must be a CSV file.")

        max_size = 5 * 1024 * 1024  # 5MB
        if value.size > max_size:
            raise serializers.ValidationError("File size must not exceed 5MB.")

        return value


class FilterRuleSerializer(serializers.Serializer):
    """
    Serializer for a single filter rule used during CSV import.

    Filter rules allow users to include/exclude rows based on column values.
    """
    column = serializers.CharField()
    operator = serializers.ChoiceField(choices=[
        ('equals', 'Equals'),
        ('not_equals', 'Not Equals'),
        ('contains', 'Contains'),
        ('not_contains', 'Not Contains'),
    ])
    value = serializers.CharField(allow_blank=True)


class AmountConfigSerializer(serializers.Serializer):
    """
    Serializer for amount configuration during CSV import.

    Determines how to interpret the amount column:
    - signed: Amount already has +/- sign
    - type_column: Separate column indicates income/expense
    - always_expense: All rows are expenses
    - always_income: All rows are income
    """
    mode = serializers.ChoiceField(choices=[
        ('signed', 'Signed'),
        ('type_column', 'Type Column'),
        ('always_expense', 'Always Expense'),
        ('always_income', 'Always Income'),
    ])
    income_value = serializers.CharField(required=False, allow_blank=True)
    expense_value = serializers.CharField(required=False, allow_blank=True)


class CSVExecuteSerializer(serializers.Serializer):
    """
    Serializer for executing the CSV import.

    Contains all configuration needed to import transactions:
    - file: The CSV file to import
    - column_mapping: Maps transaction fields to CSV columns
    - amount_config: How to interpret amounts
    - filters: Optional row filters
    """
    file = serializers.FileField()
    column_mapping = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        help_text="Maps transaction fields (amount, date, note, etc.) to CSV column names"
    )
    amount_config = AmountConfigSerializer()
    filters = FilterRuleSerializer(many=True, required=False, default=list)

    def validate_file(self, value):
        """Validate file is CSV and under 5MB."""
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError("File must be a CSV file.")

        max_size = 5 * 1024 * 1024  # 5MB
        if value.size > max_size:
            raise serializers.ValidationError("File size must not exceed 5MB.")

        return value

    def validate_column_mapping(self, value):
        """Validate required fields are mapped."""
        if 'amount' not in value or not value['amount']:
            raise serializers.ValidationError("'amount' mapping is required.")
        if 'date' not in value or not value['date']:
            raise serializers.ValidationError("'date' mapping is required.")
        return value


# --- Dashboard serializers -----------------------------------------------
# Plain (non-Model) Serializers shaping the aggregated dashboard responses.
# Data is produced by wallets.services.DashboardService.


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
    month = serializers.CharField()  # "YYYY-MM"
    income = serializers.DecimalField(max_digits=12, decimal_places=2)
    expenses = serializers.DecimalField(max_digits=12, decimal_places=2)
    net = serializers.DecimalField(max_digits=12, decimal_places=2)


class UserDashboardSerializer(serializers.Serializer):
    summary = DashboardSummarySerializer()
    wallets = WalletSummarySerializer(many=True)
    spending_by_category = CategorySpendingSerializer(many=True)
    monthly_trend = MonthlyTrendSerializer(many=True)


class WalletMetricsSerializer(serializers.Serializer):
    total_transactions = serializers.IntegerField()
    income_count = serializers.IntegerField()
    expense_count = serializers.IntegerField()
    income_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    expenses_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    net_this_month = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_transaction = serializers.DecimalField(max_digits=12, decimal_places=2)
    largest_expense = serializers.DecimalField(max_digits=12, decimal_places=2)
    largest_income = serializers.DecimalField(max_digits=12, decimal_places=2)


class WalletDashboardSerializer(serializers.Serializer):
    wallet_id = serializers.UUIDField()
    wallet_name = serializers.CharField()
    currency = serializers.CharField()
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    metrics = WalletMetricsSerializer()
    category_breakdown = CategorySpendingSerializer(many=True)
    recent_transactions = TransactionSerializer(many=True)


class RecurringTransactionSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False, default=list
    )
    execution_count = serializers.SerializerMethodField()
    is_due = serializers.SerializerMethodField()
    wallet = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = RecurringTransaction
        fields = [
            "id", "wallet", "note", "amount", "currency",
            "category", "category_id", "tags", "tag_ids",
            "frequency", "start_date", "end_date",
            "day_of_week", "day_of_month",
            "is_active", "next_occurrence", "last_processed",
            "execution_count", "is_due", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "wallet", "next_occurrence", "last_processed",
            "created_at", "updated_at",
        ]

    def get_execution_count(self, obj):
        return obj.executions.count()

    def get_is_due(self, obj):
        return obj.is_due()

    def validate_category_id(self, value):
        if value:
            user = self.context["request"].user
            if not TransactionCategory.objects.filter(id=value, user=user).exists():
                raise serializers.ValidationError("Category not found or doesn't belong to you.")
        return value

    def validate(self, data):
        start_date = data.get("start_date") or getattr(self.instance, "start_date", None)
        end_date = data.get("end_date") if "end_date" in data else getattr(self.instance, "end_date", None)
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "Must be after start date."})

        frequency = data.get("frequency") or getattr(self.instance, "frequency", None)
        if frequency == RecurringTransaction.Frequency.WEEKLY:
            day_of_week = data.get("day_of_week") if "day_of_week" in data else getattr(self.instance, "day_of_week", None)
            if day_of_week is None:
                raise serializers.ValidationError({"day_of_week": "Required for weekly frequency."})
        if frequency == RecurringTransaction.Frequency.MONTHLY:
            day_of_month = data.get("day_of_month") if "day_of_month" in data else getattr(self.instance, "day_of_month", None)
            if day_of_month is None:
                raise serializers.ValidationError({"day_of_month": "Required for monthly frequency."})

        wallet = self.context.get("wallet")
        currency = data.get("currency")
        if wallet and currency and currency != wallet.currency:
            raise serializers.ValidationError(
                {"currency": f"Must match wallet currency ({wallet.currency})."}
            )
        return data

    def create(self, validated_data):
        category_id = validated_data.pop("category_id", None)
        tag_ids = validated_data.pop("tag_ids", [])
        if category_id:
            validated_data["category"] = TransactionCategory.objects.get(id=category_id)
        instance = super().create(validated_data)
        if tag_ids:
            tags = UserTransactionTag.objects.filter(
                id__in=tag_ids, user=self.context["request"].user
            )
            instance.tags.set(tags)
        return instance

    def update(self, instance, validated_data):
        category_id = validated_data.pop("category_id", None)
        tag_ids = validated_data.pop("tag_ids", None)
        if category_id:
            validated_data["category"] = TransactionCategory.objects.get(id=category_id)
        elif category_id is None and "category_id" in self.initial_data:
            validated_data["category"] = None
        instance = super().update(instance, validated_data)
        if tag_ids is not None:
            tags = UserTransactionTag.objects.filter(
                id__in=tag_ids, user=self.context["request"].user
            )
            instance.tags.set(tags)
        return instance


class RecurringTransactionExecutionSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(read_only=True)

    class Meta:
        model = RecurringTransactionExecution
        fields = ["id", "scheduled_date", "executed_at", "transaction"]
        read_only_fields = fields


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
        wallet = self.context["wallet"]
        validated_data["category"] = TransactionCategory.objects.get(id=category_id, user=wallet.user)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "category_id" in validated_data:
            category_id = validated_data.pop("category_id")
            wallet = self.context["wallet"]
            validated_data["category"] = TransactionCategory.objects.get(id=category_id, user=wallet.user)
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


class UserProfileSerializer(serializers.Serializer):
    preferred_currency = serializers.ChoiceField(
        choices=["usd", "eur", "gbp", "pln"],
        allow_null=True,
        required=False,
    )


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