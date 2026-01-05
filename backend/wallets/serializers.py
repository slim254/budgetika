from rest_framework import serializers
from .models import Transaction, UserTransactionTag, Wallet, TransactionCategory
from django.db.models import Sum


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

    class Meta:
        model = Transaction
        fields = ['note', 'amount', 'currency', 'id', 'date', 'category', 'category_id', 'tags', 'tag_ids']
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

        This method is called when serializing a Wallet object to include the
        'balance' field in the JSON response.

        Args:
            obj: The Wallet instance being serialized

        Returns:
            Decimal: The calculated balance (initial_value + income - expense)
        """
        transactions = Transaction.objects.filter(wallet=obj)
        total = transactions.aggregate(Sum('amount'))['amount__sum'] or 0
        
        return obj.initial_value + total