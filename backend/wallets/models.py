from django.utils import timezone
import uuid
import calendar
from datetime import date, timedelta, datetime
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from dateutil.relativedelta import relativedelta

CURRENCY_CHOICES = [("usd", "usd"), ("eur", "eur"), ("gbp", "gbp"), ("pln", "pln")]


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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wallets")
    initial_value = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
    )

    def __str__(self):
        return f"{self.user.username}'s Wallet"


class SavingsGoal(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("missed", "Missed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
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


class TransactionCategory(models.Model):
    """
    Transaction categories for organizing transactions.

    DRF EDUCATIONAL NOTE - ForeignKey Relationships
    ================================================
    We use ForeignKey for the user relationship because:
    1. One user can have MANY categories (one-to-many relationship)
    2. Each category belongs to exactly ONE user
    3. ForeignKey creates a database index for efficient queries
    4. related_name='transaction_categories' allows reverse lookup:
       user.transaction_categories.all()

    Default Categories
    ==================
    When a user is created, a set of default categories is automatically
    copied to their account via a Django signal (see signals.py).
    Users own all their categories and can freely edit, delete, or hide them.

    Attributes:
        name: Category name (unique per user)
        user: Owner of this category
        icon: Lucide icon name for UI (e.g., 'shopping-cart')
        color: Hex color for UI display
        is_visible: Toggle to hide from dropdowns (but still shows on existing transactions)
        is_archived: Soft delete - hide without losing historical data
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)

    # DRF EDUCATIONAL NOTE - Required ForeignKey
    # Every category belongs to a user. Default categories are copied
    # to each user on signup, so they own their categories fully.
    # on_delete=CASCADE means: when user is deleted, delete their categories too
    user = models.ForeignKey(
        User,
        related_name="transaction_categories",
        on_delete=models.CASCADE,
    )

    icon = models.CharField(
        max_length=50, blank=True
    )  # Lucide icon name, e.g., 'shopping-cart'
    color = models.CharField(max_length=7, default="#6B7280")  # Hex color

    # Visibility toggle - hidden categories still show on existing transactions
    # but won't appear in dropdowns when creating/editing transactions
    is_visible = models.BooleanField(
        default=True,
        help_text="Hidden categories won't appear in dropdowns but remain on transactions",
    )

    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # DRF EDUCATIONAL NOTE - unique_together constraint
        # This ensures a user can't have duplicate category names.
        unique_together = [["name", "user"]]
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserTransactionTag(models.Model):
    """
    Tags for transactions to allow flexible labeling.

    DRF EDUCATIONAL NOTE - ManyToMany vs ForeignKey
    ===============================================
    Tags use a ManyToMany relationship in Transaction because:
    - One transaction can have MANY tags
    - One tag can be used on MANY transactions

    Compare to Category which uses ForeignKey because:
    - One transaction has exactly ONE category (or none)

    The ManyToMany relationship creates a junction table automatically:
    wallets_transaction_tags containing (transaction_id, tag_id) pairs.
    Django handles this table creation and querying transparently.

    Attributes:
        name: Tag name (unique per user)
        user: Owner of this tag
        icon: Lucide icon name for UI (e.g., 'tag')
        color: Hex color for UI display
        is_visible: Toggle to hide from dropdowns
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    user = models.ForeignKey(
        User, related_name="transaction_tags", on_delete=models.CASCADE
    )

    # Icon and color for visual consistency with categories
    icon = models.CharField(max_length=50, blank=True)  # Lucide icon name, e.g., 'tag'
    color = models.CharField(max_length=7, default="#3B82F6")  # Default blue

    # Visibility toggle - hidden tags still show on existing transactions
    is_visible = models.BooleanField(
        default=True,
        help_text="Hidden tags won't appear in dropdowns but remain on transactions",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["name", "user"]]
        verbose_name_plural = "tags"
        ordering = ["name"]

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
        category: Optional ForeignKey to TransactionCategory
        tags: ManyToMany relationship to UserTransactionTag
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
    )
    date = models.DateTimeField(default=timezone.now)
    wallet = models.ForeignKey(
        Wallet, related_name="transactions", on_delete=models.CASCADE
    )
    created_by = models.ForeignKey(
        User, related_name="created_transactions", on_delete=models.CASCADE
    )
    category = models.ForeignKey(
        "TransactionCategory",
        related_name="transactions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    tags = models.ManyToManyField(
        UserTransactionTag, related_name="transactions", blank=True
    )
    transfer_ref = models.UUIDField(null=True, blank=True, db_index=True)
    transfer_peer = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='transfer_peer_reverse',
    )

    def __str__(self):
        return self.note


class RecurringTransaction(models.Model):
    class Frequency(models.TextChoices):
        DAILY     = "daily",     "Daily"
        WEEKLY    = "weekly",    "Weekly"
        BIWEEKLY  = "biweekly",  "Every 2 weeks"
        MONTHLY   = "monthly",   "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        YEARLY    = "yearly",    "Yearly"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, related_name="recurring_transactions", on_delete=models.CASCADE
    )
    created_by = models.ForeignKey(
        User, related_name="recurring_transactions", on_delete=models.CASCADE
    )

    note = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
    )
    category = models.ForeignKey(
        "TransactionCategory",
        related_name="recurring_transactions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    tags = models.ManyToManyField(
        UserTransactionTag, related_name="recurring_transactions", blank=True
    )

    frequency = models.CharField(
        max_length=20, choices=Frequency.choices, default=Frequency.MONTHLY
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    day_of_week = models.IntegerField(null=True, blank=True)
    day_of_month = models.IntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    next_occurrence = models.DateField(null=True, blank=True)
    last_processed = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_occurrence", "-created_at"]

    def __str__(self):
        return f"{self.note} ({self.frequency})"

    def save(self, *args, **kwargs):
        if not self.next_occurrence and self.start_date:
            self.next_occurrence = self.start_date
        super().save(*args, **kwargs)

    def calculate_next_occurrence(self, from_date=None):
        base = from_date or date.today()

        if self.frequency == self.Frequency.DAILY:
            return base + timedelta(days=1)
        if self.frequency == self.Frequency.WEEKLY:
            days_ahead = (self.day_of_week - base.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return base + timedelta(days=days_ahead)
        if self.frequency == self.Frequency.BIWEEKLY:
            return base + timedelta(weeks=2)
        if self.frequency == self.Frequency.MONTHLY:
            next_month = base + relativedelta(months=1)
            last_day = calendar.monthrange(next_month.year, next_month.month)[1]
            target_day = last_day if self.day_of_month == -1 else min(self.day_of_month, last_day)
            return next_month.replace(day=target_day)
        if self.frequency == self.Frequency.QUARTERLY:
            return base + relativedelta(months=3)
        if self.frequency == self.Frequency.YEARLY:
            return base + relativedelta(years=1)
        return None

    def is_due(self, today=None):
        today = today or date.today()
        if not self.is_active:
            return False
        if self.end_date and today > self.end_date:
            return False
        return bool(self.next_occurrence and self.next_occurrence <= today)


class RecurringTransactionExecution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recurring_transaction = models.ForeignKey(
        RecurringTransaction,
        related_name="executions",
        on_delete=models.CASCADE,
    )
    transaction = models.ForeignKey(
        Transaction, related_name="recurring_source", on_delete=models.CASCADE
    )
    scheduled_date = models.DateField()
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-executed_at"]
        unique_together = [["recurring_transaction", "scheduled_date"]]


class BudgetRule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, related_name="budget_rules", on_delete=models.CASCADE
    )
    category = models.ForeignKey(
        TransactionCategory, related_name="budget_rules",
        on_delete=models.SET_NULL, null=True, blank=True
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["start_date"]

    def __str__(self):
        cat = self.category.name if self.category else "deleted category"
        return f"{cat} budget for {self.wallet.name}"


class BudgetMonthOverride(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, related_name="budget_overrides", on_delete=models.CASCADE
    )
    category = models.ForeignKey(
        TransactionCategory, related_name="budget_overrides",
        on_delete=models.SET_NULL, null=True, blank=True
    )
    year = models.IntegerField()
    month = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = [["wallet", "category", "year", "month"]]
        ordering = ["year", "month"]

    def __str__(self):
        cat = self.category.name if self.category else "deleted category"
        return f"{cat} override {self.year}-{self.month:02d}"


class ExchangeRate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    base_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    quote_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    date = models.DateField()
    rate = models.DecimalField(max_digits=12, decimal_places=6)

    class Meta:
        unique_together = ("base_currency", "quote_currency", "date")
        indexes = [models.Index(fields=["base_currency", "quote_currency", "date"])]

    def __str__(self):
        return f"{self.base_currency}/{self.quote_currency} on {self.date}: {self.rate}"


class UserProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    preferred_currency = models.CharField(
        max_length=3, choices=CURRENCY_CHOICES, null=True, blank=True
    )

    def __str__(self):
        return f"{self.user.username}'s profile"
