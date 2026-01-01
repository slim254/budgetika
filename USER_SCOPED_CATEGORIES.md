# Refactoring to User-Scoped Categories

## Goal
Change categories from wallet-specific to user-scoped, so one "Groceries" category works across all wallets.

## Current vs New Design

### Before (Wallet-Scoped)
```
User: Patryk
├── Wallet: "Personal PLN"
│   └── Categories: Groceries, Rent, Salary
├── Wallet: "Business EUR"
│   └── Categories: Groceries, Office  ← duplicate!
```

### After (User-Scoped)
```
User: Patryk
├── Categories: Groceries, Rent, Salary, Office  ← shared
├── Wallet: "Personal PLN"
│   └── Transactions → use shared categories
├── Wallet: "Business EUR"
    └── Transactions → use shared categories
```

## Benefits

- **No duplicates** - One "Groceries" for all wallets
- **Cross-wallet analysis** - "Total spent on Groceries across all wallets"
- **AI-ready** - Consistent categories = better ML training data
- **Simpler** - Create category once, use everywhere

---

## What You'll Learn

1. **Renaming models** - `WalletCategory` → `Category`
2. **Changing foreign keys** - From wallet to user
3. **Data migrations** - Merging duplicate categories
4. **Handling orphaned data** - What happens to transactions when categories merge

---

## Files to Modify

| File | Change |
|------|--------|
| `wallets/models.py` | Rename model, change FK from wallet to user |
| `wallets/serializers.py` | Update serializer for new model |
| `wallets/views.py` | Update views (categories no longer nested under wallet) |
| `wallets/urls.py` | Change URL patterns |
| `wallets/admin.py` | Update admin registration |
| `wallets/migrations/` | Data migration to merge duplicates |

---

## Step 1: Understand the Current Model

### Current `WalletCategory` (`wallets/models.py:38-66`)

```python
class WalletCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    wallet = models.ForeignKey(Wallet, related_name='categories', on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, related_name='created_categories', on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=[
        ('income', 'income'),
        ('expense', 'expense'),
        ('both', 'both'),
    ])
```

**Problems:**
- `wallet` FK means category belongs to ONE wallet
- Same user must create "Groceries" multiple times for different wallets
- `created_by` is redundant (wallet already has user)

---

## Step 2: Design the New Model

### New `Category` Model

```python
class Category(models.Model):
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='categories')
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default='#6B7280')  # Tailwind gray-500
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['name', 'user']]
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name
```

**Key Changes:**
- Renamed from `WalletCategory` to `Category`
- `wallet` FK → `user` FK
- Removed `type` field (not needed with signed amounts)
- Removed `created_by` (redundant, same as `user`)
- Added `icon`, `color` for UI
- Added `is_archived` for soft delete
- Added timestamps

---

## Step 3: Update Transaction Model

### Change the Foreign Key

```python
class Transaction(models.Model):
    # ... other fields ...

    # BEFORE:
    # category = models.ForeignKey(WalletCategory, ...)

    # AFTER:
    category = models.ForeignKey(
        'Category',  # New model name
        related_name='transactions',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
```

---

## Step 4: Create the Migration

This migration is more complex because we need to:
1. Create new `Category` model
2. Migrate data from `WalletCategory` (merging duplicates)
3. Update `Transaction.category` to point to new model
4. Delete old `WalletCategory` model

### Create Migration File

**Create:** `wallets/migrations/XXXX_user_scoped_categories.py`

```python
"""
Migration: Convert wallet-scoped categories to user-scoped categories.

This migration:
1. Creates new Category model (user-scoped)
2. Migrates data from WalletCategory, merging duplicates per user
3. Updates Transaction.category to reference new Category
4. Removes old WalletCategory model

IMPORTANT: Handles duplicate category names across wallets by merging them.
Example: If user has "Groceries" in 3 wallets, they become ONE "Groceries" category.
"""
from django.db import migrations, models
import django.db.models.deletion
import uuid


def migrate_categories_forward(apps, schema_editor):
    """
    Migrate WalletCategory to Category, merging duplicates per user.

    LEARNING: When multiple wallets have same category name, we merge them.
    All transactions pointing to any "Groceries" WalletCategory will point
    to the single new "Groceries" Category.
    """
    WalletCategory = apps.get_model('wallets', 'WalletCategory')
    Category = apps.get_model('wallets', 'Category')
    Transaction = apps.get_model('wallets', 'Transaction')

    # Track mapping: old WalletCategory ID -> new Category ID
    category_mapping = {}

    # Track created categories per user to detect duplicates
    # Format: {user_id: {name: category_id}}
    user_categories = {}

    for old_cat in WalletCategory.objects.select_related('wallet', 'created_by').all():
        user_id = old_cat.wallet.user_id
        name = old_cat.name

        # Initialize user's category dict if needed
        if user_id not in user_categories:
            user_categories[user_id] = {}

        # Check if we already created this category for this user
        if name in user_categories[user_id]:
            # Duplicate! Map old category to existing new category
            new_cat_id = user_categories[user_id][name]
            category_mapping[old_cat.id] = new_cat_id
            print(f"    Merged duplicate '{name}' for user {user_id}")
        else:
            # Create new category
            new_cat = Category.objects.create(
                id=uuid.uuid4(),
                name=name,
                user_id=user_id,
                icon='',
                color='#6B7280',
                is_archived=False,
            )
            user_categories[user_id][name] = new_cat.id
            category_mapping[old_cat.id] = new_cat.id
            print(f"    Created category '{name}' for user {user_id}")

    # Update all transactions to point to new categories
    updated = 0
    for old_id, new_id in category_mapping.items():
        count = Transaction.objects.filter(category_id=old_id).update(category_id=new_id)
        updated += count

    print(f"    Updated {updated} transactions to new categories")


def migrate_categories_reverse(apps, schema_editor):
    """
    Reverse migration: Recreate WalletCategory from Category.

    WARNING: This is a lossy operation if categories were merged.
    We'll create one WalletCategory per wallet that has transactions
    with each category.
    """
    WalletCategory = apps.get_model('wallets', 'WalletCategory')
    Category = apps.get_model('wallets', 'Category')
    Transaction = apps.get_model('wallets', 'Transaction')
    Wallet = apps.get_model('wallets', 'Wallet')

    # For each category, find which wallets use it and create WalletCategory
    for cat in Category.objects.all():
        # Find wallets that have transactions with this category
        wallet_ids = Transaction.objects.filter(
            category_id=cat.id
        ).values_list('wallet_id', flat=True).distinct()

        for wallet_id in wallet_ids:
            wallet = Wallet.objects.get(id=wallet_id)
            old_cat = WalletCategory.objects.create(
                id=uuid.uuid4(),
                name=cat.name,
                wallet=wallet,
                created_by_id=cat.user_id,
                type='both',
            )
            # Update transactions in this wallet to point to new WalletCategory
            Transaction.objects.filter(
                wallet_id=wallet_id,
                category_id=cat.id
            ).update(category_id=old_cat.id)

    print("    Reverse migration complete (some data may be duplicated)")


class Migration(migrations.Migration):
    dependencies = [
        ('wallets', '0002_remove_transaction_type'),  # After signed amounts migration
    ]

    operations = [
        # Step 1: Create new Category model
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('icon', models.CharField(blank=True, max_length=50)),
                ('color', models.CharField(default='#6B7280', max_length=7)),
                ('is_archived', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='categories', to='auth.user')),
            ],
            options={
                'verbose_name_plural': 'categories',
                'ordering': ['name'],
            },
        ),
        migrations.AddConstraint(
            model_name='category',
            constraint=models.UniqueConstraint(fields=['name', 'user'], name='unique_category_per_user'),
        ),

        # Step 2: Migrate data
        migrations.RunPython(
            migrate_categories_forward,
            migrate_categories_reverse,
        ),

        # Step 3: Remove old foreign key from Transaction
        migrations.RemoveField(
            model_name='transaction',
            name='category',
        ),

        # Step 4: Add new foreign key to Transaction
        migrations.AddField(
            model_name='transaction',
            name='category',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='transactions',
                to='wallets.category'
            ),
        ),

        # Step 5: Delete old WalletCategory model
        migrations.DeleteModel(
            name='WalletCategory',
        ),
    ]
```

### Key Learning Points

1. **Merging duplicates** - Same category name in multiple wallets → one category
2. **Mapping IDs** - Track old → new IDs to update transactions
3. **Lossy reverse** - Reverse migration can't perfectly restore duplicates
4. **Order matters** - Create new model → migrate data → change FK → delete old model

---

## Step 5: Update Serializers

### Edit `wallets/serializers.py`

**Remove `WalletCategorySerializer`, add `CategorySerializer`:**

```python
from .models import Transaction, Wallet, Category  # Changed import


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for user-scoped categories.

    Categories are shared across all user's wallets.
    """
    transaction_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'icon', 'color', 'is_archived', 'transaction_count']
        read_only_fields = ['id']

    def get_transaction_count(self, obj):
        """Number of transactions using this category."""
        return obj.transactions.count()


class TransactionSerializer(serializers.ModelSerializer):
    """Update to use new Category."""
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Transaction
        fields = ['id', 'note', 'amount', 'currency', 'date', 'category', 'category_id']

    def validate_category_id(self, value):
        """Ensure category belongs to the user."""
        if value:
            user = self.context['request'].user
            if not Category.objects.filter(id=value, user=user).exists():
                raise serializers.ValidationError("Category not found or doesn't belong to you.")
        return value
```

---

## Step 6: Update Views

### Edit `wallets/views.py`

**Remove wallet-scoped category views, add user-scoped:**

```python
from .models import Transaction, Wallet, Category  # Changed import
from .serializers import TransactionSerializer, WalletSerializer, CategorySerializer


class CategoryList(generics.ListCreateAPIView):
    """
    List all user's categories or create a new one.

    GET /api/categories/ - List all categories
    POST /api/categories/ - Create new category

    Categories are user-scoped (shared across all wallets).
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """Return categories for authenticated user only."""
        return Category.objects.filter(
            user=self.request.user,
            is_archived=False  # Don't show archived by default
        )

    def perform_create(self, serializer):
        """Set user automatically."""
        serializer.save(user=self.request.user)


class CategoryDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a category.

    GET /api/categories/{id}/ - Get category details
    PUT /api/categories/{id}/ - Update category
    DELETE /api/categories/{id}/ - Archive category (soft delete)
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """Return only user's categories."""
        return Category.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        """
        Soft delete: Archive instead of deleting.

        This preserves historical data - transactions keep their category
        reference, but category won't appear in dropdown for new transactions.
        """
        instance.is_archived = True
        instance.save()
```

---

## Step 7: Update URLs

### Edit `wallets/urls.py`

```python
from django.urls import path
from .views import (
    WalletList, WalletDetail,
    WalletTransactionList, WalletTransactionDetail,
    CategoryList, CategoryDetail,  # New views
    TransactionDetail, TransactionCreate,
)

urlpatterns = [
    # Wallet routes
    path('', WalletList.as_view(), name='wallet-list'),
    path('<uuid:wallet_id>/', WalletDetail.as_view(), name='wallet-detail'),

    # Transaction routes (nested under wallet)
    path('<uuid:wallet_id>/transactions/', WalletTransactionList.as_view(), name='wallet-transaction-list'),
    path('<uuid:wallet_id>/transactions/<uuid:pk>/', WalletTransactionDetail.as_view(), name='wallet-transaction-detail'),

    # Category routes (NOT nested - user-scoped)
    # BEFORE: path('<uuid:wallet_id>/categories/', ...)
    # AFTER:
    path('categories/', CategoryList.as_view(), name='category-list'),
    path('categories/<uuid:pk>/', CategoryDetail.as_view(), name='category-detail'),

    # Direct transaction routes
    path('transactions/', TransactionCreate.as_view(), name='transaction-create'),
    path('transactions/<uuid:pk>/', TransactionDetail.as_view(), name='transaction-detail'),
]
```

**Note:** Categories are now at `/api/wallets/categories/` not `/api/wallets/{wallet_id}/categories/`

Or you could move them to a separate URL namespace:
```python
# In config/urls.py
path('api/categories/', include('wallets.category_urls')),
```

---

## Step 8: Update Admin

### Edit `wallets/admin.py`

```python
from django.contrib import admin
from .models import Wallet, Category, Transaction


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'icon', 'color', 'is_archived', 'created_at']
    list_filter = ['user', 'is_archived', 'created_at']
    search_fields = ['name', 'user__username']
    ordering = ['user', 'name']


# Remove or comment out:
# @admin.register(WalletCategory)
# class WalletCategoryAdmin(admin.ModelAdmin):
#     ...
```

---

## Step 9: Run Migration

```bash
# 1. Save all file changes

# 2. Check current migration status
python manage.py showmigrations wallets

# 3. Run migration
python manage.py migrate wallets

# Expected output:
# Running migrations:
#   Applying wallets.0003_user_scoped_categories...
#     Created category 'Groceries' for user 1
#     Created category 'Rent' for user 1
#     Merged duplicate 'Groceries' for user 1  ← if duplicates existed
#     Updated 150 transactions to new categories
#   OK
```

---

## Step 10: Verify

### Test in Django Shell

```bash
python manage.py shell
```

```python
from wallets.models import Category, Transaction, Wallet
from django.contrib.auth.models import User

# Check categories are user-scoped
user = User.objects.first()
categories = Category.objects.filter(user=user)
print(f"User {user.username} has {categories.count()} categories:")
for cat in categories:
    txn_count = cat.transactions.count()
    print(f"  - {cat.name}: {txn_count} transactions")

# Verify no duplicates
from django.db.models import Count
duplicates = Category.objects.values('user', 'name').annotate(
    count=Count('id')
).filter(count__gt=1)
print(f"\nDuplicate categories: {list(duplicates)}")  # Should be empty

# Test cross-wallet query
groceries = Category.objects.filter(user=user, name='Groceries').first()
if groceries:
    # Total spent on groceries across ALL wallets
    from django.db.models import Sum
    total = groceries.transactions.aggregate(Sum('amount'))['amount__sum']
    print(f"\nTotal Groceries spending: {total}")
```

### Test API

```bash
# List all categories (user-scoped, not wallet-scoped)
curl http://localhost:8000/api/wallets/categories/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Create category (no wallet_id needed!)
curl -X POST http://localhost:8000/api/wallets/categories/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "New Category", "color": "#10B981"}'

# Create transaction with category
curl -X POST http://localhost:8000/api/wallets/WALLET_ID/transactions/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "Weekly shopping",
    "amount": "-150.00",
    "currency": "pln",
    "category_id": "CATEGORY_UUID"
  }'
```

---

## Step 11: Update Frontend

### API Changes

```typescript
// BEFORE (wallet-scoped):
// GET /api/wallets/{walletId}/categories/
// POST /api/wallets/{walletId}/categories/

// AFTER (user-scoped):
// GET /api/wallets/categories/
// POST /api/wallets/categories/

// Categories are now global - fetch once, use in any wallet
const fetchCategories = async () => {
  const response = await fetch('/api/wallets/categories/', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return response.json();
};

// When creating transaction, pass category_id
const createTransaction = async (walletId: string, data: TransactionData) => {
  await fetch(`/api/wallets/${walletId}/transactions/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      note: data.note,
      amount: data.amount,
      currency: data.currency,
      category_id: data.categoryId  // UUID of user's category
    })
  });
};
```

---

## Common Issues

### Issue 1: "Category matching query does not exist"

**Cause:** Transaction references old WalletCategory ID that doesn't exist in new Category table.

**Fix:** The migration should handle this, but if you have issues:
```python
# Find orphaned transactions
Transaction.objects.filter(category__isnull=False).exclude(
    category_id__in=Category.objects.values_list('id', flat=True)
)
```

### Issue 2: Duplicate Key Error on Migration

**Cause:** Two WalletCategories with same name for same user (via different wallets).

**Fix:** The migration handles this by merging. If it fails, manually check:
```python
from collections import defaultdict
dupes = defaultdict(list)
for wc in WalletCategory.objects.select_related('wallet'):
    key = (wc.wallet.user_id, wc.name)
    dupes[key].append(wc.id)
# Find keys with more than one ID
{k: v for k, v in dupes.items() if len(v) > 1}
```

### Issue 3: API Returns 404 for Categories

**Cause:** Using old URL pattern `/api/wallets/{wallet_id}/categories/`

**Fix:** Update to new pattern `/api/wallets/categories/`

---

## Summary

### What Changed
| Before | After |
|--------|-------|
| `WalletCategory` model | `Category` model |
| `wallet` FK | `user` FK |
| `/api/wallets/{id}/categories/` | `/api/wallets/categories/` |
| Duplicates across wallets | One category per name per user |

### Benefits
- Cross-wallet spending analysis works
- No duplicate categories to manage
- Better for future AI categorization
- Simpler mental model

### Migration Order
1. Signed amounts refactoring (do first)
2. CSV import (can do before or after categories)
3. User-scoped categories (this guide)
