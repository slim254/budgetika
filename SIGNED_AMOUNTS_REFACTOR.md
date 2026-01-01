# Refactoring to Signed Amounts

## Goal
Remove the `transaction_type` field and use signed amounts instead:
- **Negative amount** = expense (money out)
- **Positive amount** = income (money in)

## Why This Refactoring?

### Current Design (Redundant)
```python
amount = 72.08           # Always positive
transaction_type = 'expense'  # Separate field to indicate type
```

**Problems:**
- Two fields for one concept (redundant)
- Balance calculation requires filtering by type
- More complex queries

### New Design (Simpler)
```python
amount = -72.08  # Sign tells you everything (negative = expense)
```

**Benefits:**
- One field instead of two
- Balance = `initial_value + SUM(amount)` (trivial!)
- Matches how banks and accounting systems work
- Your CSV export already uses this format

---

## What You'll Learn

1. **Django Data Migrations** - Transforming existing data
2. **RunPython migrations** - Custom Python code in migrations
3. **F() expressions** - Efficient bulk updates without loading objects into memory
4. **Reversible migrations** - Writing reverse operations for rollback safety
5. **Serializer field changes** - Updating API contracts
6. **Computed fields** - Simplifying `SerializerMethodField` calculations

---

## Files to Modify

| File | Change |
|------|--------|
| `wallets/models.py` | Remove `transaction_type` field |
| `wallets/serializers.py` | Update fields list, simplify `get_balance()` |
| `wallets/migrations/0002_*.py` | NEW: Data migration + field removal |
| Frontend (optional) | Derive type from amount sign |

---

## Step 1: Understand the Current Code

### Current Model (`wallets/models.py:69-112`)

```python
class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=[  # <- REMOVE THIS
        ('income', 'income'),
        ('expense', 'expense')
    ])
    currency = models.CharField(max_length=3, choices=[...])
    date = models.DateTimeField(auto_now_add=True)
    wallet = models.ForeignKey(Wallet, ...)
    created_by = models.ForeignKey(User, ...)
    category = models.ForeignKey(WalletCategory, ...)
```

### Current Balance Calculation (`wallets/serializers.py:89-107`)

```python
def get_balance(self, obj):
    transactions = Transaction.objects.filter(wallet=obj)
    # Complex: Must filter and sum separately
    income = transactions.filter(transaction_type='income').aggregate(Sum('amount'))['amount__sum'] or 0
    expense = transactions.filter(transaction_type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
    return obj.initial_value + income - expense
```

**Learning Point:** This requires TWO database aggregations. With signed amounts, we need only ONE.

---

## Step 2: Update the Model

### Edit `wallets/models.py`

**DELETE these lines (around line 96-99):**
```python
# DELETE THIS ENTIRE BLOCK:
transaction_type = models.CharField(max_length=10, choices=[
    ('income', 'income'),
    ('expense', 'expense')
])
```

**UPDATE the docstring to reflect the new design:**
```python
class Transaction(models.Model):
    """
    Individual transaction record.

    Amount sign determines transaction type:
    - POSITIVE amount = income (money coming in)
    - NEGATIVE amount = expense (money going out)

    Examples:
        Salary: amount = 5000.00 (positive = income)
        Groceries: amount = -150.50 (negative = expense)

    Attributes:
        note: Description of the transaction
        amount: Transaction amount (negative for expenses, positive for income)
        currency: Must match the wallet's currency
        date: When the transaction occurred
        wallet: The wallet this transaction belongs to
        created_by: User who created this transaction
        category: Optional category for organization
    """
```

### Why Not Just Add `blank=True`?

You might think: "Why not keep `transaction_type` but make it optional?"

**Answer:** That creates inconsistency. Some transactions would have the field, others wouldn't. The sign-based approach is:
- **Consistent** - Every transaction uses the same rule
- **Self-documenting** - The data itself tells you the type
- **Efficient** - No extra storage for a redundant field

---

## Step 3: Create the Migration

### Understanding Django Migrations

Migrations are Python files that describe database changes. They can:
1. **Schema changes** - Add/remove columns, tables, indexes
2. **Data changes** - Transform existing data (using `RunPython`)

Our migration needs BOTH:
1. Transform data: Convert positive expense amounts to negative
2. Schema change: Remove the `transaction_type` column

**IMPORTANT:** Data transformation must happen BEFORE removing the field!

### Create Migration File

**Create:** `wallets/migrations/0002_remove_transaction_type.py`

```python
"""
Migration: Remove transaction_type field, use signed amounts instead.

This migration:
1. Converts all expense transactions to negative amounts
2. Removes the transaction_type field

After this migration:
- Positive amounts = income
- Negative amounts = expense
"""
from django.db import migrations
from django.db.models import F


def convert_expenses_to_negative(apps, schema_editor):
    """
    Convert expense amounts from positive to negative.

    LEARNING: We use apps.get_model() instead of importing directly.
    This gives us the model as it existed at this point in migration history,
    not the current model (which might have different fields).
    """
    # Get the historical model (as it exists at this migration point)
    Transaction = apps.get_model('wallets', 'Transaction')

    # LEARNING: F() expressions let us reference field values in updates
    # This runs as a single SQL UPDATE, not loading objects into Python memory
    # SQL: UPDATE transaction SET amount = amount * -1 WHERE transaction_type = 'expense' AND amount > 0
    updated_count = Transaction.objects.filter(
        transaction_type='expense',
        amount__gt=0  # Only positive amounts (avoid double-negation if re-run)
    ).update(amount=F('amount') * -1)

    print(f"    Converted {updated_count} expense transactions to negative amounts")


def convert_expenses_to_positive(apps, schema_editor):
    """
    Reverse operation: Convert negative amounts back to positive.

    LEARNING: Django migrations should be reversible when possible.
    This allows you to rollback if something goes wrong:
        python manage.py migrate wallets 0001
    """
    Transaction = apps.get_model('wallets', 'Transaction')

    # All negative amounts become positive
    # Note: We lose the ability to distinguish "negative income" (rare edge case)
    updated_count = Transaction.objects.filter(
        amount__lt=0
    ).update(amount=F('amount') * -1)

    print(f"    Reverted {updated_count} transactions back to positive amounts")


class Migration(migrations.Migration):
    """
    LEARNING: Migration class structure:
    - dependencies: Which migrations must run before this one
    - operations: List of changes to apply (in order!)
    """

    dependencies = [
        ('wallets', '0001_initial'),  # Must run after initial migration
    ]

    operations = [
        # STEP 1: Transform data FIRST (while transaction_type field still exists)
        migrations.RunPython(
            convert_expenses_to_negative,  # Forward operation
            convert_expenses_to_positive,  # Reverse operation (for rollback)
        ),

        # STEP 2: Remove the field AFTER data is transformed
        migrations.RemoveField(
            model_name='transaction',
            name='transaction_type',
        ),
    ]
```

### Key Learning Points

1. **`apps.get_model()`** - Gets the model as it was at migration time, not current
2. **`F()` expressions** - Reference field values in queries without loading into Python
3. **Order matters** - Data migration BEFORE schema change
4. **Reversibility** - Always provide reverse function when possible

---

## Step 4: Update the Serializer

### Edit `wallets/serializers.py`

**A) Update `TransactionSerializer` (around line 30-32):**

```python
class TransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for Transaction model.

    Amount sign determines transaction type:
    - Positive = income
    - Negative = expense

    Example JSON:
        {
            "id": "uuid-here",
            "note": "Weekly groceries",
            "amount": "-150.50",
            "currency": "pln",
            "date": "2025-12-05T10:30:00Z",
            "category": "uuid-here"
        }
    """
    class Meta:
        model = Transaction
        fields = ['id', 'note', 'amount', 'currency', 'date', 'category']
        # REMOVED: 'transaction_type' from fields list

    def validate(self, data):
        """Validate currency matches wallet."""
        wallet = self.context.get('wallet')
        currency = data.get('currency')
        if wallet and currency and wallet.currency != currency:
            raise serializers.ValidationError(
                f"Transaction currency ({currency}) must match wallet currency ({wallet.currency})."
            )
        return data
```

**B) Simplify `get_balance()` in `WalletSerializer` (lines 89-107):**

```python
def get_balance(self, obj):
    """
    Calculate wallet balance.

    BEFORE (complex - two aggregations):
        income = filter(type='income').sum()
        expense = filter(type='expense').sum()
        balance = initial + income - expense

    AFTER (simple - one aggregation):
        total = sum(all amounts)  # Expenses are already negative!
        balance = initial + total

    LEARNING: With signed amounts, we just sum everything.
    Negative expenses naturally subtract from the total.
    """
    transactions = Transaction.objects.filter(wallet=obj)
    total = transactions.aggregate(Sum('amount'))['amount__sum'] or 0
    return obj.initial_value + total
```

### Why Is This Better?

**Before:** 2 database queries (income sum + expense sum)
```sql
SELECT SUM(amount) FROM transaction WHERE wallet_id = ? AND transaction_type = 'income';
SELECT SUM(amount) FROM transaction WHERE wallet_id = ? AND transaction_type = 'expense';
```

**After:** 1 database query
```sql
SELECT SUM(amount) FROM transaction WHERE wallet_id = ?;
```

---

## Step 5: Run the Migration

```bash
# 1. Make sure you've saved all file changes

# 2. Check migration status
python manage.py showmigrations wallets

# 3. Run the migration
python manage.py migrate wallets

# Expected output:
# Operations to perform:
#   Apply all migrations: wallets
# Running migrations:
#   Applying wallets.0002_remove_transaction_type...
#     Converted X expense transactions to negative amounts
#   OK
```

### If Something Goes Wrong

```bash
# Rollback to previous migration
python manage.py migrate wallets 0001

# This will:
# 1. Re-add the transaction_type field
# 2. Convert negative amounts back to positive
```

---

## Step 6: Verify the Changes

### Test in Django Shell

```bash
python manage.py shell
```

```python
from wallets.models import Transaction, Wallet
from django.db.models import Sum
from decimal import Decimal

# Check that expenses are now negative
expenses = Transaction.objects.filter(amount__lt=0)
print(f"Expense count: {expenses.count()}")
print("Sample expenses:")
for t in expenses[:5]:
    print(f"  {t.note}: {t.amount}")

# Check that income is still positive
income = Transaction.objects.filter(amount__gt=0)
print(f"\nIncome count: {income.count()}")
print("Sample income:")
for t in income[:5]:
    print(f"  {t.note}: {t.amount}")

# Test balance calculation
wallet = Wallet.objects.first()
if wallet:
    transactions = Transaction.objects.filter(wallet=wallet)
    total = transactions.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    balance = wallet.initial_value + total
    print(f"\nWallet: {wallet.name}")
    print(f"Initial value: {wallet.initial_value}")
    print(f"Transaction total: {total}")
    print(f"Calculated balance: {balance}")
```

### Test the API

```bash
# Get a JWT token first
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "youruser", "password": "yourpass"}'

# Get wallet (should include balance)
curl http://localhost:8000/api/wallets/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Create an expense (note: negative amount)
curl -X POST http://localhost:8000/api/wallets/WALLET_UUID/transactions/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "Test expense",
    "amount": "-25.00",
    "currency": "pln"
  }'

# Create income (positive amount)
curl -X POST http://localhost:8000/api/wallets/WALLET_UUID/transactions/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "Test income",
    "amount": "100.00",
    "currency": "pln"
  }'
```

---

## Step 7: Update Frontend (If Needed)

### Derive Type from Amount Sign

```typescript
// utils/transaction.ts

export type TransactionType = 'income' | 'expense';

/**
 * Derive transaction type from amount sign.
 * Positive = income, Negative = expense, Zero = income (arbitrary choice)
 */
export const getTransactionType = (amount: number): TransactionType => {
  return amount < 0 ? 'expense' : 'income';
};

/**
 * Format amount for display with sign indicator.
 */
export const formatAmount = (amount: number, currency: string = 'PLN') => {
  const type = getTransactionType(amount);
  const absAmount = Math.abs(amount).toFixed(2);

  return {
    value: absAmount,
    display: type === 'expense' ? `-${absAmount}` : `+${absAmount}`,
    type,
    className: type === 'expense' ? 'text-red-500' : 'text-green-500',
    currency,
  };
};

// Usage in component:
// const { display, className } = formatAmount(transaction.amount);
// <span className={className}>{display} {currency}</span>
```

### Update Forms

If you have a form with a "Type" dropdown, you have two options:

**Option A: Keep UI Dropdown, Convert on Submit**
```typescript
const handleSubmit = (data: FormData) => {
  let amount = parseFloat(data.amount);

  // Convert to negative if expense
  if (data.type === 'expense' && amount > 0) {
    amount = -amount;
  }

  // Send to API (no transaction_type field)
  api.createTransaction({
    note: data.note,
    amount: amount,
    currency: data.currency,
  });
};
```

**Option B: Let User Enter Signed Amount**
```tsx
<input
  type="number"
  name="amount"
  placeholder="Enter amount (negative for expense)"
  step="0.01"
/>
<p className="text-sm text-gray-500">
  Use negative for expenses (e.g., -50.00), positive for income
</p>
```

---

## Common Issues & Troubleshooting

### Issue 1: Migration Fails with "column does not exist"

**Cause:** You removed the field from `models.py` before running the migration.

**Fix:**
1. Temporarily add the field back to `models.py`
2. Run the migration
3. Remove the field again (migration already handled it)

### Issue 2: Balance is Wrong After Migration

**Cause:** Some expenses might have already been negative (double-negation).

**Check:**
```python
# Look for unexpected positive amounts that should be expenses
Transaction.objects.filter(amount__gt=0).values('note', 'amount')
```

**Fix:** The migration filters `amount__gt=0` to avoid this, but if you ran it multiple times, you might need to manually fix data.

### Issue 3: API Returns `transaction_type` Required Error

**Cause:** Old frontend or client still sending `transaction_type`.

**Fix:** Update the client code to stop sending `transaction_type`. The field no longer exists.

### Issue 4: "No such column: transaction_type" During Migration

**Cause:** Migration order issue - trying to access field after removal.

**Fix:** Ensure `RunPython` comes BEFORE `RemoveField` in the migration operations list.

---

## Learning Exercises

After completing this refactoring, try these exercises to deepen your understanding:

### Exercise 1: Add a Computed Property
Add a `transaction_type` property to the model that derives type from sign:

```python
@property
def transaction_type(self) -> str:
    """Derive transaction type from amount sign."""
    return 'expense' if self.amount < 0 else 'income'
```

### Exercise 2: Add a Manager Method
Create a custom manager to query by type:

```python
class TransactionManager(models.Manager):
    def expenses(self):
        return self.filter(amount__lt=0)

    def income(self):
        return self.filter(amount__gt=0)

# Usage: Transaction.objects.expenses()
```

### Exercise 3: Write a Test
Write a test that verifies balance calculation:

```python
def test_balance_with_signed_amounts(self):
    wallet = Wallet.objects.create(initial_value=1000, ...)

    # Add income
    Transaction.objects.create(amount=500, wallet=wallet, ...)

    # Add expense (negative!)
    Transaction.objects.create(amount=-200, wallet=wallet, ...)

    # Calculate balance
    total = Transaction.objects.filter(wallet=wallet).aggregate(Sum('amount'))['amount__sum']
    balance = wallet.initial_value + total

    self.assertEqual(balance, 1300)  # 1000 + 500 - 200
```

---

## Summary

### What We Did
1. Removed redundant `transaction_type` field
2. Converted expense amounts to negative values
3. Simplified balance calculation to single aggregation
4. Updated serializer to reflect new API contract

### Key Learnings
- **Data migrations** transform existing data during schema changes
- **F() expressions** enable efficient bulk updates
- **Migration order matters** - data changes before schema changes
- **Signed amounts** are simpler and match accounting conventions

### Next Steps
After completing this refactoring, you can proceed with the CSV import feature. The import will be simpler because:
- CSV amounts can be used as-is (already signed)
- No need to map CSV "Type" column to `transaction_type` field
- Balance calculations work automatically

---

## Quick Reference

### Querying Transactions After Refactoring

```python
# All expenses
Transaction.objects.filter(amount__lt=0)

# All income
Transaction.objects.filter(amount__gt=0)

# Total balance change for a wallet
Transaction.objects.filter(wallet=wallet).aggregate(Sum('amount'))

# Expenses total (as positive number)
from django.db.models import Sum
from django.db.models.functions import Abs
expenses_total = Transaction.objects.filter(
    wallet=wallet, amount__lt=0
).aggregate(total=Sum(Abs('amount')))['total']
```

### Creating Transactions After Refactoring

```python
# Income (positive)
Transaction.objects.create(
    note="Salary",
    amount=Decimal('5000.00'),  # Positive!
    wallet=wallet,
    ...
)

# Expense (negative)
Transaction.objects.create(
    note="Groceries",
    amount=Decimal('-150.50'),  # Negative!
    wallet=wallet,
    ...
)
```
