from rest_framework import serializers
from .models import Transaction, Wallet, UserTransactionCategory
from django.db.models import Sum


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for user-scoped categories.

    Categories are shared across all user's wallets.
    """
    transaction_count = serializers.SerializerMethodField()

    class Meta:
        model = UserTransactionCategory
        fields = ['id', 'name', 'icon', 'color', 'is_archived', 'transaction_count']
        read_only_fields = ['id']

    def get_transaction_count(self, obj):
        """Number of transactions using this category."""
        return obj.transactions.count()


class TransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for Transaction model - handles conversion between Python objects
    and JSON for API requests/responses.

    This serializer only exposes specific fields (not the 'created_by' field) to
    prevent users from seeing who created other transactions (though they could
    infer it from timestamps).

    The validate() method ensures that all transactions in a wallet use the same
    currency, preventing mixed-currency transactions which would break balance
    calculations.

    Example JSON:
        {
            "id": 1,
            "note": "Weekly groceries",
            "amount": "150.50",
            "transaction_type": "expense",
            "currency": "usd",
            "date": "2025-12-05T10:30:00Z",
            "category": 1
        }
    """
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Transaction
        fields = ['note', 'amount', 'currency', 'id', 'date', 'category', 'category_id']

    def validate_category_id(self, value):
        """Ensure category belongs to the user."""
        if value:
            user = self.context['request'].user
            if not UserTransactionCategory.objects.filter(id=value, user=user).exists():
                raise serializers.ValidationError("Category not found or doesn't belong to you.")
        return value

    def create(self, validated_data):
        """Handle category_id when creating transaction."""
        category_id = validated_data.pop('category_id', None)
        if category_id:
            validated_data['category'] = UserTransactionCategory.objects.get(id=category_id)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Handle category_id when updating transaction."""
        category_id = validated_data.pop('category_id', None)
        if category_id:
            validated_data['category'] = UserTransactionCategory.objects.get(id=category_id)
        elif category_id is None and 'category_id' in self.initial_data:
            validated_data['category'] = None
        return super().update(instance, validated_data)

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