import uuid
from django.db import models
from django.contrib.auth.models import User


class Wallet(models.Model):
    """
    Represents a user's wallet/budget account.

    Each user can have multiple wallets (e.g., "Monthly Budget", "Savings").
    The balance is calculated dynamically based on the initial value and
    all associated transactions (not stored in DB).

    Attributes:
        name: Display name for the wallet
        user: Owner of this wallet (ForeignKey - users can have multiple wallets)
        initial_value: Starting balance/amount in the wallet
        currency: Currency code (usd, eur, gbp, pln) - all transactions must use the same currency
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallets')
    initial_value = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=[
        ('usd', 'usd'),
        ('eur', 'eur'),
        ('gbp', 'gbp'),
        ('pln', 'pln')
    ])

    def __str__(self):
        return f"{self.user.username}'s Wallet"


class UserTransactionCategory(models.Model):
    """
    User's transaction categories, shared across all their wallets.

    Examples:
        - "Groceries" can be used in both PLN and EUR wallets
        - "Salary" income category works for any wallet

    Attributes:
        name: Category name (unique per user)
        user: Owner of this category
        icon: Optional icon identifier for UI
        color: Hex color for UI display
        is_archived: Soft delete - hide without losing historical data
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, related_name='transaction_categories', on_delete=models.CASCADE)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default='#6B7280') 
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['name', 'user']]
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name
    
class UserTransactionTag(models.Model):
    """
    Tags for transactions to allow flexible labeling.

    Attributes:
        name: Tag name (unique per user)
        user: Owner of this tag
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    user = models.ForeignKey(User, related_name='transaction_tags', on_delete=models.CASCADE)

    class Meta:
        unique_together = [['name', 'user']]
        verbose_name_plural = 'tags'
        ordering = ['name']

    def __str__(self):
        return self.name


class Transaction(models.Model):
    """
    Individual transaction record.

    Each transaction represents a money flow associated with a wallet.
    Positive amounts = income, negative amounts = expenses.
    Transactions can be categorized, tagged, and are tied to the user who created them.

    Attributes:
        note: Description of the transaction (e.g., "Weekly groceries")
        amount: Transaction amount (positive for income, negative for expense)
        currency: Must match the wallet's currency (validated in serializer)
        date: Auto-set to creation time. Supports filtering by month/year for reporting
        wallet: ForeignKey to the associated wallet
        created_by: User who created this transaction
        category: Optional ForeignKey to UserTransactionCategory
        tags: ManyToMany relationship to UserTransactionTag
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=[
        ('usd', 'usd'),
        ('eur', 'eur'),
        ('gbp', 'gbp'),
        ('pln', 'pln')
    ])
    date = models.DateTimeField(auto_now_add=True)
    wallet = models.ForeignKey(Wallet, related_name='transactions', on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, related_name='created_transactions', on_delete=models.CASCADE)
    category = models.ForeignKey(
        'UserTransactionCategory', 
        related_name='transactions',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    tags = models.ManyToManyField(UserTransactionTag, related_name='transactions', blank=True)

    def __str__(self):
        return self.note