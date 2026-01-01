# CSV Transaction Import Implementation Plan

## Overview
Implement functionality to import transactions from CSV export files into the Django budgeting app. The CSV format includes: Date, Wallet, Type, Category name, Amount, Currency, Note, Labels, and Author fields.

## Missing Features Analysis

### 1. **Labels/Tags System** ⚠️ CRITICAL
**Current State:** No label/tag support exists in the Transaction model
**CSV Has:** Labels column with comma-separated values (e.g., "iCloud", "ZUS", "rower")
**Required:**
- New `TransactionLabel` model with many-to-many relationship to Transaction
- User-scoped labels (each user has their own label namespace)
- Support for parsing comma-separated labels from CSV

### 2. **Editable Transaction Dates** ⚠️ CRITICAL
**Current State:** `Transaction.date` uses `auto_now_add=True` (read-only, auto-set on creation)
**CSV Has:** Historical dates (e.g., "2024-11-12T19:27:47+00:00")
**Required:**
- Change field from `auto_now_add=True` to `default=timezone.now`
- Allows importing transactions with their original historical dates

### 3. **File Upload Infrastructure** ⚠️ CRITICAL
**Current State:** No file upload capability exists
**Required:**
- CSV upload API endpoint: `POST /api/wallets/{wallet_id}/import-transactions/`
- File validation (size, extension, headers)
- Multipart form data handling
- MEDIA_ROOT/MEDIA_URL configuration in settings

### 4. **Bulk Import Operations** ⚠️ CRITICAL
**Current State:** Only single transaction creation supported
**Required:**
- CSV parsing logic (handle encoding, validate structure)
- Bulk insert using `Transaction.objects.bulk_create()`
- Atomic transactions (all-or-nothing imports)
- Error collection and reporting

### 5. **Category Auto-Creation**
**Current State:** Categories must be created manually before use
**Required:**
- Logic to detect missing categories during import
- Auto-create `WalletCategory` entries as needed
- Infer category type (income/expense) from transaction type
- Track which categories were created during import

### 6. **Duplicate Detection**
**Current State:** No duplicate checking mechanism
**Required:**
- Detect duplicates by matching: date + amount + note
- Skip duplicates option (user-configurable)
- Report how many duplicates were skipped

### 7. **Import Validation & Error Reporting**
**Current State:** No validation framework for batch operations
**Required:**
- Row-by-row validation with error collection
- Currency validation (must match wallet currency)
- Amount parsing (handle negative values, convert to positive + type)
- Date parsing (ISO 8601 format with timezone)
- Transaction type normalization (Income/Expense → income/expense)
- Comprehensive error response with row numbers and field details

### 8. **Security Features**
**Current State:** Basic JWT authentication exists, but no file upload security
**Required:**
- File size limits (max 5MB)
- File type validation (only .csv)
- CSV header validation
- Max row limit (e.g., 10,000 transactions)
- User wallet ownership verification

## Implementation Approach

### Data Model Changes

#### 1. New TransactionLabel Model
```python
class TransactionLabel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_labels')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['name', 'created_by']]  # User-scoped labels
        ordering = ['name']
```

#### 2. Modified Transaction Model
- Change `date` field: `auto_now_add=True` → `default=timezone.now`
- Add `labels` field: `ManyToManyField(TransactionLabel, blank=True)`
- Add database index for duplicate detection: `Index(fields=['wallet', 'date', 'amount', 'note'])`

### API Endpoint Design

**Endpoint:** `POST /api/wallets/{wallet_id}/import-transactions/`
**Authentication:** JWT (IsAuthenticated)
**Content-Type:** multipart/form-data

**Request:**
```
file: <CSV file>
skip_duplicates: true/false (default: true)
dry_run: true/false (default: false)
```

**Response (Success):**
```json
{
  "status": "success",
  "summary": {
    "total_rows": 150,
    "imported": 145,
    "skipped_duplicates": 5,
    "categories_created": 3,
    "labels_created": 8,
    "failed": 0
  },
  "created_categories": ["Groceries", "Transport", "Utilities"],
  "created_labels": ["urgent", "recurring", "tax-deductible"],
  "skipped_transactions": [],
  "errors": []
}
```

**Response (Error):**
```json
{
  "status": "error",
  "summary": {
    "total_rows": 150,
    "valid": 140,
    "failed": 10
  },
  "errors": [
    {
      "row": 5,
      "field": "amount",
      "message": "Invalid decimal format",
      "data": {"amount": "invalid"}
    }
  ]
}
```

### CSV Import Logic Flow

1. **File Validation**
   - Check file size (< 5MB)
   - Validate extension (.csv only)
   - Verify CSV headers match expected format
   - Check row count (< 10,000 rows)

2. **CSV Parsing**
   - Use `csv.DictReader` for row-by-row processing
   - Handle encoding issues (UTF-8, UTF-8-BOM)
   - Parse all rows into structured data

3. **Row Processing (for each transaction)**
   - Parse date: ISO 8601 → datetime object
   - Normalize type: "Income"/"Expense" → "income"/"expense"
   - Parse amount: Take absolute value (CSV has negative for expenses)
   - Validate currency: Must match wallet currency
   - Get/create category: Query or auto-create WalletCategory
   - Parse labels: Split comma-separated string
   - Get/create labels: Query or auto-create TransactionLabel
   - Check duplicate: Query for existing transaction (date + amount + note)
   - Collect valid transactions or errors

4. **Bulk Import**
   - Use `transaction.atomic()` for database atomicity
   - `Transaction.objects.bulk_create()` for efficiency
   - Create M2M relationships for labels
   - Rollback on any database error

5. **Return Results**
   - Summary stats (imported, skipped, failed)
   - List of created categories and labels
   - Detailed error list with row numbers

### CSV Field Mapping

| CSV Column | Transaction Field | Notes |
|------------|------------------|-------|
| Date | date | Parse ISO 8601 format, convert to timezone-aware datetime |
| Type | transaction_type | Normalize: "Income" → "income", "Expense" → "expense" |
| Category name | category (FK) | Get or auto-create WalletCategory |
| Amount | amount | Use absolute value (ignore sign from CSV) |
| Currency | currency | Validate: must match wallet.currency |
| Note | note | Use as-is (or empty string if blank) |
| Labels | labels (M2M) | Parse comma-separated, get or create each label |
| Wallet | (ignored) | Use wallet_id from URL path |
| Author | (ignored) | Always use request.user as created_by |

### Security Considerations

1. **File Upload Security**
   - Enforce max file size (5MB) before processing
   - Validate file extension and MIME type
   - Don't persist uploaded files (process in-memory)
   - Sanitize all input fields

2. **User Isolation**
   - Verify wallet ownership: `get_object_or_404(Wallet, id=wallet_id, user=request.user)`
   - All created categories belong to user's wallet
   - All created labels scoped to user
   - All imported transactions use `request.user` as created_by

3. **Input Validation**
   - Limit max rows to prevent DoS
   - Validate currency against allowed choices
   - Check decimal precision for amounts
   - Validate date format

## Critical Files to Modify

### Backend Files

1. **`wallets/models.py`**
   - Add `TransactionLabel` model (new)
   - Modify `Transaction.date` field (remove `auto_now_add`)
   - Add `Transaction.labels` M2M field
   - Add database index for duplicate detection

2. **`wallets/migrations/0002_add_labels_and_editable_dates.py`** (NEW)
   - Create TransactionLabel table
   - Alter Transaction.date field
   - Add Transaction.labels M2M relationship
   - Add index for (wallet, date, amount, note)

3. **`wallets/services.py`** (NEW)
   - Create `CSVTransactionImporter` class
   - Implement all import logic and validation
   - ~300 lines of business logic

4. **`wallets/serializers.py`**
   - Add `TransactionLabelSerializer` (new)
   - Add `CSVImportSerializer` for request validation (new)
   - Update `TransactionSerializer` to include labels field

5. **`wallets/views.py`**
   - Add `WalletTransactionImportView` (new)
   - Handle file upload, orchestrate import process
   - Return formatted results

6. **`wallets/urls.py`**
   - Add route: `path('<uuid:wallet_id>/import-transactions/', ...)`

7. **`config/settings.py`**
   - Add `MEDIA_ROOT` and `MEDIA_URL`
   - Add CSV import configuration constants:
     - `CSV_IMPORT_MAX_FILE_SIZE = 5 * 1024 * 1024`
     - `CSV_IMPORT_MAX_ROWS = 10000`
     - `CSV_IMPORT_REQUIRED_HEADERS = [...]`

8. **`wallets/admin.py`**
   - Register `TransactionLabel` model

9. **`wallets/tests.py`**
   - Add test suite for TransactionLabel model
   - Add test suite for CSVTransactionImporter
   - Add integration tests for import API endpoint

### Frontend Files (API Integration)

10. **`frontend/api/wallets.ts`** (or similar)
    - Add `importTransactions()` API client function
    - Handle FormData upload with authentication

## Implementation Sequence

### Phase 1: Data Model Foundation
1. Create `TransactionLabel` model in `models.py`
2. Modify `Transaction.date` field (remove `auto_now_add`, add `default=timezone.now`)
3. Add `labels` M2M field to `Transaction`
4. Create and run migration: `python manage.py makemigrations && python manage.py migrate`
5. Update `admin.py` to register `TransactionLabel`
6. Test models in Django shell

### Phase 2: Core Import Logic
1. Create `wallets/services.py` with `CSVTransactionImporter` class
2. Implement file validation (size, extension, headers)
3. Implement CSV parsing with error handling
4. Implement category get-or-create logic
5. Implement label parsing and get-or-create logic
6. Implement duplicate detection
7. Implement bulk import with `transaction.atomic()`
8. Write unit tests for service layer

### Phase 3: API Endpoint
1. Create `CSVImportSerializer` in `serializers.py`
2. Create `TransactionLabelSerializer` in `serializers.py`
3. Update `TransactionSerializer` to include labels
4. Create `WalletTransactionImportView` in `views.py`
5. Add URL pattern in `urls.py`
6. Update `settings.py` with configuration constants
7. Write integration tests for API endpoint

### Phase 4: Testing & Validation
1. Run all unit tests
2. Test with provided CSV file (`transactions_export_2025-11-12_pj(1).csv`)
3. Test error scenarios (invalid files, wrong currency, duplicates)
4. Test security (unauthorized access, wrong wallet)
5. Load test with large CSV files

### Phase 5: Frontend Integration
1. Create API client function for CSV import
2. Build file upload UI component
3. Add import button to wallet detail page
4. Implement success/error result display
5. Test end-to-end workflow

## Key Design Decisions

### ✅ Auto-create missing categories
- Categories found in CSV but not in database will be created automatically
- Category type inferred from transaction type (expense/income)
- User informed which categories were created in response

### ✅ Allow custom dates
- Modify Transaction model to support historical dates
- Essential for importing old transaction data

### ✅ Check for duplicates
- Skip transactions that match existing ones (date + amount + note)
- User can disable via `skip_duplicates=false` parameter
- Report how many were skipped

### ✅ Labels as separate feature
- Implement full label/tag system with M2M relationship
- Labels are user-scoped (each user has their own labels)
- Enables future features like filtering by label, label management UI

### ℹ️ Ignore CSV Author field
- Always use authenticated user as `created_by`
- CSV Author field is informational only

### ℹ️ Wallet selection from URL
- Import endpoint is nested: `/api/wallets/{wallet_id}/import-transactions/`
- User must be on specific wallet page to import
- Prevents confusion about which wallet receives transactions

## Potential Challenges & Mitigations

### Challenge 1: Timezone Handling
**Issue:** CSV dates have timezone info (+00:00), may differ from server timezone
**Solution:** Use `django.utils.timezone` for all datetime operations, store in UTC

### Challenge 2: Large File Performance
**Issue:** 10,000 rows may be slow to process
**Solution:** Use `bulk_create()` for efficiency, process in atomic transaction

### Challenge 3: Encoding Issues
**Issue:** CSV may use different encodings (UTF-8, UTF-8-BOM, ISO-8859-1)
**Solution:** Try UTF-8 first, use chardet library if needed, return clear error

### Challenge 4: Concurrent Imports
**Issue:** Multiple users importing simultaneously could create race conditions
**Solution:** Use database transactions for atomicity, duplicate detection handles overlaps

### Challenge 5: Category Type Ambiguity
**Issue:** Auto-created categories need a type (income/expense/both)
**Solution:** Infer from transaction type, create as specific type (not 'both')

## Learning Guide & Implementation Hints

This section provides educational guidance, code examples, and learning resources to help you implement this feature yourself.

### Phase 1: Data Models - Learning Guide

#### Concept 1: Many-to-Many Relationships in Django

**What you'll learn:** How M2M relationships work, when to use them vs ForeignKey

**Example - TransactionLabel Model:**
```python
# wallets/models.py
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class TransactionLabel(models.Model):
    """
    Labels/tags for transactions. Unlike categories (one per transaction),
    labels allow multiple tags per transaction.

    Example: A transaction could have labels: ["urgent", "tax-deductible", "business"]
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_labels'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # LEARNING: unique_together prevents duplicate label names per user
        # This means User A can have label "work" and User B can also have "work"
        # but User A cannot create "work" twice
        unique_together = [['name', 'created_by']]
        ordering = ['name']  # Always return labels alphabetically

        # OPTIONAL: Add a custom index for faster queries
        indexes = [
            models.Index(fields=['created_by', 'name']),
        ]

    def __str__(self):
        return self.name
```

**Hint:** Test your model in Django shell:
```bash
python manage.py shell
```
```python
from django.contrib.auth.models import User
from wallets.models import TransactionLabel

# Create a label
user = User.objects.first()
label = TransactionLabel.objects.create(name="urgent", created_by=user)

# Try to create duplicate (should fail with IntegrityError)
TransactionLabel.objects.create(name="urgent", created_by=user)  # Error!

# Different user can have same label name
other_user = User.objects.last()
TransactionLabel.objects.create(name="urgent", created_by=other_user)  # OK!
```

#### Concept 2: Modifying Existing Models

**What you'll learn:** How to change field attributes, migration considerations

**Example - Updating Transaction Model:**
```python
# wallets/models.py

class Transaction(models.Model):
    # ... existing fields ...

    # BEFORE: date = models.DateTimeField(auto_now_add=True)
    # AFTER: Change to allow manual date setting
    date = models.DateTimeField(default=timezone.now)
    # LEARNING: default=timezone.now allows you to override the date when creating
    # auto_now_add=True does NOT allow overriding

    # ... existing fields ...

    # NEW: Add many-to-many relationship with labels
    labels = models.ManyToManyField(
        TransactionLabel,
        related_name='transactions',  # Access from label: label.transactions.all()
        blank=True,  # Labels are optional
        help_text="Tags for categorizing this transaction"
    )

    class Meta:
        # LEARNING: Indexes speed up queries that filter/order by these fields
        # Since we'll check for duplicates using (wallet, date, amount, note),
        # an index helps the database find matching rows faster
        indexes = [
            models.Index(fields=['wallet', 'date', 'amount', 'note'], name='duplicate_check_idx'),
        ]
```

**Migration Tips:**
```bash
# 1. Create migration file
python manage.py makemigrations wallets

# 2. Review the migration file (ALWAYS review before running!)
cat wallets/migrations/0002_*.py

# 3. Apply migration
python manage.py migrate wallets

# 4. If you need to rollback (undo migration)
python manage.py migrate wallets 0001  # Go back to migration 0001
```

**Common Migration Issues:**
- Changing `auto_now_add=True` → `default=timezone.now`: Migration will ask about default value for existing rows
- Adding M2M field: Django creates a "through" table automatically
- If migration fails, check for data integrity issues

#### Testing Your Models

Create a test file to verify model behavior:
```python
# wallets/tests.py
from django.test import TestCase
from django.contrib.auth.models import User
from wallets.models import Transaction, TransactionLabel, Wallet
from decimal import Decimal

class TransactionLabelModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='12345')

    def test_create_label(self):
        """Test creating a label"""
        label = TransactionLabel.objects.create(
            name="urgent",
            created_by=self.user
        )
        self.assertEqual(label.name, "urgent")
        self.assertEqual(label.created_by, self.user)

    def test_unique_constraint(self):
        """Test that same user cannot create duplicate label names"""
        TransactionLabel.objects.create(name="urgent", created_by=self.user)

        # This should raise an error
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            TransactionLabel.objects.create(name="urgent", created_by=self.user)

    def test_transaction_with_labels(self):
        """Test adding labels to a transaction"""
        wallet = Wallet.objects.create(
            name="Test Wallet",
            user=self.user,
            initial_value=Decimal('1000.00'),
            currency='pln'
        )

        transaction = Transaction.objects.create(
            note="Test purchase",
            amount=Decimal('50.00'),
            transaction_type='expense',
            currency='pln',
            wallet=wallet,
            created_by=self.user
        )

        # Create some labels
        label1 = TransactionLabel.objects.create(name="urgent", created_by=self.user)
        label2 = TransactionLabel.objects.create(name="business", created_by=self.user)

        # Add labels to transaction
        transaction.labels.add(label1, label2)

        # Verify
        self.assertEqual(transaction.labels.count(), 2)
        self.assertIn(label1, transaction.labels.all())

# Run tests:
# python manage.py test wallets.tests.TransactionLabelModelTest
```

### Phase 2: Core Import Logic - Learning Guide

#### Concept 3: Service Layer Pattern

**What you'll learn:** Separating business logic from views, reusable service classes

**Why use a service layer?**
- Views should be thin - they handle HTTP requests/responses
- Services contain business logic - they can be reused in views, management commands, Celery tasks
- Easier to test - you can test business logic without HTTP layer

**Example - Basic Service Structure:**
```python
# wallets/services.py
import csv
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from .models import Transaction, WalletCategory, TransactionLabel

class CSVTransactionImporter:
    """
    Service class for importing transactions from CSV files.

    Usage:
        importer = CSVTransactionImporter(wallet=my_wallet, user=request.user, csv_file=uploaded_file)
        result = importer.import_transactions()
    """

    def __init__(self, wallet, user, csv_file, skip_duplicates=True):
        self.wallet = wallet
        self.user = user
        self.csv_file = csv_file
        self.skip_duplicates = skip_duplicates

        # Track statistics
        self.stats = {
            'total_rows': 0,
            'imported': 0,
            'skipped_duplicates': 0,
            'failed': 0,
        }

        # Cache for performance (avoid duplicate DB queries)
        self.category_cache = {}  # {name: WalletCategory object}
        self.label_cache = {}     # {name: TransactionLabel object}

        # Collect errors
        self.errors = []
        self.created_categories = set()
        self.created_labels = set()
```

#### Concept 4: CSV Parsing in Python

**What you'll learn:** Reading CSV files, handling encoding, DictReader

**Example - File Validation:**
```python
    def validate_file(self):
        """
        Validate uploaded CSV file.
        Returns list of validation errors (empty if valid).
        """
        errors = []

        # Check file size
        if self.csv_file.size > settings.CSV_IMPORT_MAX_FILE_SIZE:
            max_mb = settings.CSV_IMPORT_MAX_FILE_SIZE / (1024 * 1024)
            errors.append({
                'field': 'file',
                'message': f'File too large. Maximum size is {max_mb}MB'
            })

        # Check file extension
        file_name = self.csv_file.name.lower()
        if not file_name.endswith('.csv'):
            errors.append({
                'field': 'file',
                'message': 'Invalid file type. Only .csv files are allowed'
            })

        # If basic validation passes, check CSV structure
        if not errors:
            try:
                # Read first line to check headers
                self.csv_file.seek(0)  # Reset file pointer to beginning
                first_line = self.csv_file.readline().decode('utf-8-sig')  # Handle BOM

                # Parse header
                import csv
                reader = csv.reader([first_line])
                headers = next(reader)

                # Check required headers
                required = settings.CSV_IMPORT_REQUIRED_HEADERS
                missing = set(required) - set(headers)

                if missing:
                    errors.append({
                        'field': 'file',
                        'message': f'Missing required CSV columns: {", ".join(missing)}'
                    })

                # Reset file pointer for later reading
                self.csv_file.seek(0)

            except Exception as e:
                errors.append({
                    'field': 'file',
                    'message': f'Invalid CSV format: {str(e)}'
                })

        return errors
```

**Hint - Encoding Issues:**
```python
# CSV files can have different encodings. Common ones:
# - UTF-8: Standard, most common
# - UTF-8-BOM: UTF-8 with Byte Order Mark (Excel exports often use this)
# - ISO-8859-1 / Latin-1: Older European encoding

# To handle UTF-8-BOM:
content = self.csv_file.read().decode('utf-8-sig')  # 'sig' removes BOM
# Or:
import codecs
self.csv_file = codecs.iterdecode(self.csv_file, 'utf-8-sig')
```

**Example - Parsing CSV:**
```python
    def parse_csv(self):
        """
        Parse CSV file and return rows as list of dictionaries.
        """
        try:
            # Decode file content
            self.csv_file.seek(0)
            content = self.csv_file.read().decode('utf-8-sig')

            # Parse CSV
            lines = content.splitlines()
            reader = csv.DictReader(lines)

            rows = []
            for row_num, row in enumerate(reader, start=1):
                rows.append((row_num, row))

                # Safety check: limit max rows
                if len(rows) > settings.CSV_IMPORT_MAX_ROWS:
                    raise ValueError(f'Too many rows. Maximum is {settings.CSV_IMPORT_MAX_ROWS}')

            return rows

        except Exception as e:
            raise ValueError(f'Failed to parse CSV: {str(e)}')
```

#### Concept 5: Get-or-Create Pattern

**What you'll learn:** Efficient database queries, avoiding duplicates

**Example - Category Management:**
```python
    def get_or_create_category(self, name, transaction_type):
        """
        Get existing category by name, or create new one.
        Uses cache to avoid repeated database queries.

        Args:
            name: Category name (e.g., "Groceries")
            transaction_type: 'income' or 'expense'

        Returns:
            WalletCategory object
        """
        # Check cache first (fast!)
        cache_key = f"{name}:{transaction_type}"
        if cache_key in self.category_cache:
            return self.category_cache[cache_key]

        # Try to find existing category in database
        try:
            category = WalletCategory.objects.get(
                wallet=self.wallet,
                name=name
            )
            # LEARNING: You could also validate that category.type matches transaction_type
            # or use type='both' categories

        except WalletCategory.DoesNotExist:
            # Create new category
            category = WalletCategory.objects.create(
                name=name,
                wallet=self.wallet,
                created_by=self.user,
                type=transaction_type  # 'income' or 'expense'
            )
            # Track for reporting
            self.created_categories.add(name)

        # Add to cache
        self.category_cache[cache_key] = category
        return category
```

**Django ORM Tip:**
```python
# Alternative: Use Django's built-in get_or_create
category, created = WalletCategory.objects.get_or_create(
    wallet=self.wallet,
    name=name,
    defaults={
        'created_by': self.user,
        'type': transaction_type
    }
)
# created is True if new object was created, False if it already existed
if created:
    self.created_categories.add(name)
```

#### Concept 6: Data Parsing and Validation

**Example - Parsing Different Data Types:**
```python
    def parse_date(self, date_str):
        """
        Parse ISO 8601 date string to datetime object.

        Example: "2024-11-12T19:27:47+00:00" → datetime object
        """
        try:
            # Python 3.7+ supports fromisoformat
            dt = datetime.fromisoformat(date_str)

            # Make timezone-aware if needed
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt)

            return dt

        except ValueError:
            # Try alternative parsing with dateutil (install: pip install python-dateutil)
            from dateutil import parser
            return parser.parse(date_str)

    def parse_amount(self, amount_str):
        """
        Parse amount string to Decimal.
        CSV has negative values for expenses, but we store positive amounts.

        Example: "-72.08000000" → Decimal("72.08")
        """
        try:
            # Convert to Decimal (better than float for money!)
            amount = Decimal(amount_str)

            # Return absolute value (we store positive amounts)
            return abs(amount)

        except (InvalidOperation, ValueError):
            raise ValueError(f'Invalid amount format: {amount_str}')

    def normalize_transaction_type(self, csv_type):
        """
        Convert CSV type to database format.

        CSV: "Income" or "Expense" (capitalized)
        DB:  "income" or "expense" (lowercase)
        """
        csv_type_lower = csv_type.lower().strip()

        if csv_type_lower not in ['income', 'expense']:
            raise ValueError(f'Invalid transaction type: {csv_type}')

        return csv_type_lower

    def parse_labels(self, labels_str):
        """
        Parse comma-separated labels string.

        Example: "iCloud,ZUS,rower" → [TransactionLabel, TransactionLabel, TransactionLabel]
        """
        if not labels_str or labels_str.strip() == '':
            return []

        # Split by comma, strip whitespace, filter empty
        label_names = [name.strip() for name in labels_str.split(',') if name.strip()]

        # Get or create each label
        labels = []
        for name in label_names:
            label = self.get_or_create_label(name)
            labels.append(label)

        return labels

    def get_or_create_label(self, name):
        """Get or create TransactionLabel"""
        if name in self.label_cache:
            return self.label_cache[name]

        label, created = TransactionLabel.objects.get_or_create(
            name=name,
            created_by=self.user
        )

        if created:
            self.created_labels.add(name)

        self.label_cache[name] = label
        return label
```

#### Concept 7: Duplicate Detection

**Example - Checking for Duplicates:**
```python
    def is_duplicate(self, date, amount, note):
        """
        Check if transaction already exists.

        Duplicate = same wallet + same date + same amount + same note
        """
        # LEARNING: Django ORM query with multiple filters
        exists = Transaction.objects.filter(
            wallet=self.wallet,
            date=date,
            amount=amount,
            note=note
        ).exists()  # exists() is faster than count() > 0

        return exists
```

**Advanced Duplicate Detection:**
```python
    def is_duplicate_fuzzy(self, date, amount, note):
        """
        More sophisticated duplicate detection:
        - Date within same day (ignore time)
        - Amount matches (rounded to 2 decimals)
        - Note matches (case-insensitive, whitespace normalized)
        """
        from django.db.models import Q
        from datetime import timedelta

        # Get date range (same day)
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)

        # Normalize note
        note_normalized = note.strip().lower()

        # Query
        duplicates = Transaction.objects.filter(
            wallet=self.wallet,
            date__gte=date_start,
            date__lt=date_end,
            amount=round(amount, 2)
        )

        # Check note similarity
        for txn in duplicates:
            if txn.note.strip().lower() == note_normalized:
                return True

        return False
```

#### Concept 8: Bulk Operations and Transactions

**What you'll learn:** Atomic transactions, bulk_create for performance

**Example - Main Import Method:**
```python
    def import_transactions(self):
        """
        Main import method. Orchestrates entire import process.
        """
        # 1. Validate file
        validation_errors = self.validate_file()
        if validation_errors:
            return {
                'status': 'error',
                'errors': validation_errors,
                'stats': self.stats
            }

        # 2. Parse CSV
        try:
            rows = self.parse_csv()
            self.stats['total_rows'] = len(rows)
        except ValueError as e:
            return {
                'status': 'error',
                'errors': [{'field': 'file', 'message': str(e)}],
                'stats': self.stats
            }

        # 3. Process each row
        transactions_to_create = []
        transactions_labels_map = {}  # Map transaction index to list of labels

        for row_num, row_data in rows:
            try:
                # Process row
                txn_data, labels = self.process_row(row_num, row_data)

                if txn_data:  # Only if not skipped as duplicate
                    transactions_to_create.append(txn_data)
                    transactions_labels_map[len(transactions_to_create) - 1] = labels

            except Exception as e:
                # Collect error and continue
                self.errors.append({
                    'row': row_num,
                    'message': str(e),
                    'data': row_data
                })
                self.stats['failed'] += 1

        # 4. Bulk create transactions (atomic!)
        if transactions_to_create:
            try:
                with transaction.atomic():  # LEARNING: All-or-nothing
                    # Create all transactions at once
                    created_transactions = Transaction.objects.bulk_create(
                        transactions_to_create
                    )

                    self.stats['imported'] = len(created_transactions)

                    # Create M2M relationships for labels
                    # LEARNING: bulk_create doesn't support M2M, must do separately
                    for idx, txn in enumerate(created_transactions):
                        if idx in transactions_labels_map:
                            labels = transactions_labels_map[idx]
                            txn.labels.set(labels)  # Set all labels at once

            except Exception as e:
                return {
                    'status': 'error',
                    'errors': [{'message': f'Database error: {str(e)}'}],
                    'stats': self.stats
                }

        # 5. Return results
        return {
            'status': 'success',
            'stats': self.stats,
            'errors': self.errors,
            'created_categories': list(self.created_categories),
            'created_labels': list(self.created_labels)
        }

    def process_row(self, row_num, row_data):
        """
        Process a single CSV row.

        Returns:
            (Transaction object, list of labels) or (None, None) if skipped

        Raises:
            ValueError: If row data is invalid
        """
        # Parse all fields
        date = self.parse_date(row_data['Date'])
        txn_type = self.normalize_transaction_type(row_data['Type'])
        amount = self.parse_amount(row_data['Amount'])
        currency = row_data['Currency'].lower()
        note = row_data['Note'].strip() if row_data['Note'] else ''
        category_name = row_data['Category name'].strip()
        labels_str = row_data.get('Labels', '')

        # Validate currency matches wallet
        if currency != self.wallet.currency:
            raise ValueError(
                f'Currency mismatch: transaction has {currency}, '
                f'wallet requires {self.wallet.currency}'
            )

        # Check for duplicates
        if self.skip_duplicates and self.is_duplicate(date, amount, note):
            self.stats['skipped_duplicates'] += 1
            return None, None

        # Get or create category
        category = self.get_or_create_category(category_name, txn_type)

        # Parse labels
        labels = self.parse_labels(labels_str)

        # Create transaction object (not saved yet!)
        txn = Transaction(
            note=note,
            amount=amount,
            transaction_type=txn_type,
            currency=currency,
            date=date,
            wallet=self.wallet,
            created_by=self.user,
            category=category
        )

        return txn, labels
```

**Learning Points:**
- `transaction.atomic()`: Database transaction - if any error occurs, ALL changes are rolled back
- `bulk_create()`: Creates multiple objects in single SQL query (much faster than loop)
- M2M relationships: Cannot be set during bulk_create, must do after objects are saved

### Phase 3: API Endpoint - Learning Guide

#### Concept 9: DRF APIView for File Uploads

**What you'll learn:** Handling file uploads in DRF, multipart/form-data, custom responses

**Example - View Implementation:**
```python
# wallets/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404

from .models import Wallet
from .serializers import CSVImportSerializer
from .services import CSVTransactionImporter

class WalletTransactionImportView(APIView):
    """
    API endpoint for importing transactions from CSV file.

    POST /api/wallets/{wallet_id}/import-transactions/

    Request body (multipart/form-data):
    - file: CSV file
    - skip_duplicates: boolean (default: true)
    - dry_run: boolean (default: false)
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, wallet_id):
        # 1. Validate wallet ownership
        # LEARNING: get_object_or_404 raises 404 if not found OR if user doesn't match
        wallet = get_object_or_404(
            Wallet,
            id=wallet_id,
            user=request.user  # Security: user can only import to their own wallet
        )

        # 2. Validate request data
        serializer = CSVImportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        # 3. Extract validated data
        csv_file = serializer.validated_data['file']
        skip_duplicates = serializer.validated_data.get('skip_duplicates', True)
        dry_run = serializer.validated_data.get('dry_run', False)

        # 4. Create importer and run
        importer = CSVTransactionImporter(
            wallet=wallet,
            user=request.user,
            csv_file=csv_file,
            skip_duplicates=skip_duplicates
        )

        # 5. Import transactions
        result = importer.import_transactions()

        # 6. Return appropriate response
        if result['status'] == 'error':
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        if result['errors']:
            # Partial success - some rows failed
            return Response(
                {
                    'status': 'partial_success',
                    'summary': result['stats'],
                    'created_categories': result['created_categories'],
                    'created_labels': result['created_labels'],
                    'errors': result['errors']
                },
                status=status.HTTP_200_OK
            )

        # Complete success
        return Response(
            {
                'status': 'success',
                'summary': result['stats'],
                'created_categories': result['created_categories'],
                'created_labels': result['created_labels']
            },
            status=status.HTTP_200_OK
        )
```

#### Concept 10: Custom Serializers for File Upload

**Example - Serializer:**
```python
# wallets/serializers.py
from rest_framework import serializers

class CSVImportSerializer(serializers.Serializer):
    """
    Serializer for CSV import request validation.

    LEARNING: This is NOT a ModelSerializer because we're not working with a Django model.
    We use Serializer for custom validation of arbitrary data.
    """
    file = serializers.FileField(
        help_text="CSV file to import",
        required=True
    )
    skip_duplicates = serializers.BooleanField(
        default=True,
        required=False,
        help_text="Skip transactions that already exist"
    )
    dry_run = serializers.BooleanField(
        default=False,
        required=False,
        help_text="Validate CSV without importing"
    )

    def validate_file(self, value):
        """
        Custom validation for file field.

        LEARNING: validate_<field_name> methods are called automatically
        """
        # Check file extension
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError('Only CSV files are allowed')

        # Check file size (5MB limit)
        max_size = 5 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(f'File too large. Maximum size is 5MB')

        return value


class TransactionLabelSerializer(serializers.ModelSerializer):
    """Serializer for TransactionLabel model"""

    class Meta:
        model = TransactionLabel
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']


# Update existing TransactionSerializer to include labels
class TransactionSerializer(serializers.ModelSerializer):
    labels = TransactionLabelSerializer(many=True, read_only=True)
    # LEARNING: many=True means this is a list of labels
    # read_only=True means labels are not required when creating/updating

    class Meta:
        model = Transaction
        fields = ['id', 'note', 'amount', 'transaction_type',
                  'currency', 'date', 'category', 'labels']
```

#### Concept 11: URL Routing

**Example - URLs:**
```python
# wallets/urls.py
from django.urls import path
from .views import (
    WalletList, WalletDetail, WalletTransactionList,
    WalletTransactionDetail, WalletTransactionImportView,
    # ... other views
)

urlpatterns = [
    # Existing routes
    path('', WalletList.as_view(), name='wallet-list'),
    path('<uuid:wallet_id>/', WalletDetail.as_view(), name='wallet-detail'),
    path('<uuid:wallet_id>/transactions/', WalletTransactionList.as_view(), name='wallet-transaction-list'),

    # NEW: Import endpoint
    path(
        '<uuid:wallet_id>/import-transactions/',
        WalletTransactionImportView.as_view(),
        name='wallet-transaction-import'
    ),
    # LEARNING: URL parameters like <uuid:wallet_id> are passed to view as kwargs
]
```

### Testing Your Implementation

**Run tests:**
```bash
# All tests
python manage.py test

# Specific test file
python manage.py test wallets.tests

# Specific test class
python manage.py test wallets.tests.CSVTransactionImporterTest

# Specific test method
python manage.py test wallets.tests.CSVTransactionImporterTest.test_parse_csv_basic

# With verbose output
python manage.py test --verbosity=2
```

**Manual testing with curl:**
```bash
# 1. Get JWT token
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "youruser", "password": "yourpass"}'

# Response: {"access": "eyJ...", "refresh": "eyJ..."}

# 2. Import CSV
curl -X POST http://localhost:8000/api/wallets/<WALLET_ID>/import-transactions/ \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -F "file=@/path/to/your/file.csv" \
  -F "skip_duplicates=true"
```

### Common Pitfalls & How to Avoid Them

1. **Forgetting to add imports**
   ```python
   from django.utils import timezone  # For timezone.now
   from django.db import transaction  # For transaction.atomic()
   from decimal import Decimal  # For money calculations
   ```

2. **Not handling file encoding**
   - Always use `decode('utf-8-sig')` to handle UTF-8-BOM
   - Remember to `seek(0)` if reading file multiple times

3. **Forgetting to reset file pointer**
   ```python
   csv_file.seek(0)  # Reset to beginning after validation
   ```

4. **Using float for money**
   - DON'T: `amount = float(amount_str)`  # Floating point errors!
   - DO: `amount = Decimal(amount_str)`   # Exact decimal representation

5. **Not using atomic transactions**
   - If bulk_create fails halfway, you could have partial imports
   - ALWAYS wrap in `with transaction.atomic():`

6. **Forgetting timezone awareness**
   ```python
   # BAD: naive datetime (no timezone)
   dt = datetime(2024, 11, 12, 19, 27, 47)

   # GOOD: timezone-aware
   from django.utils import timezone
   dt = timezone.now()  # Current time with timezone
   dt = timezone.make_aware(naive_dt)  # Convert naive to aware
   ```

### Learning Resources

**Django Documentation:**
- Models: https://docs.djangoproject.com/en/stable/topics/db/models/
- Migrations: https://docs.djangoproject.com/en/stable/topics/migrations/
- Query API: https://docs.djangoproject.com/en/stable/topics/db/queries/

**DRF Documentation:**
- Views: https://www.django-rest-framework.org/api-guide/views/
- Serializers: https://www.django-rest-framework.org/api-guide/serializers/
- File upload: https://www.django-rest-framework.org/api-guide/parsers/#fileuploadparser

**Python CSV:**
- csv module: https://docs.python.org/3/library/csv.html
- Encoding: https://docs.python.org/3/library/codecs.html

### Pro Tips

1. **Use Django Debug Toolbar** for development
   ```bash
   pip install django-debug-toolbar
   ```
   Shows SQL queries, helps optimize performance

2. **Use Django shell for quick testing**
   ```bash
   python manage.py shell
   ```
   Test your functions interactively

3. **Create sample data with factories**
   ```bash
   pip install factory-boy
   ```
   Generate test data easily

4. **Use pytest for better testing**
   ```bash
   pip install pytest pytest-django
   pytest wallets/tests.py -v
   ```

5. **Profile slow imports**
   ```python
   import time
   start = time.time()
   # ... your import code ...
   print(f"Import took {time.time() - start:.2f} seconds")
   ```

## Next Steps - Your Implementation Journey

1. ✅ **Start with Phase 1** - Get comfortable with Django models
2. ✅ **Test each phase** - Don't move forward until tests pass
3. ✅ **Read the docs** - When stuck, check Django/DRF documentation
4. ✅ **Ask questions** - Comment your code with questions, look up answers
5. ✅ **Iterate** - First make it work, then make it better

## Expected Deliverables

1. ✅ Working CSV import endpoint
2. ✅ Labels/tags feature for transactions
3. ✅ Historical date support for imported transactions
4. ✅ Automatic category creation during import
5. ✅ Duplicate detection and reporting
6. ✅ Comprehensive error handling and validation
7. ✅ Security hardening for file uploads
8. ✅ Test coverage for all new functionality
9. ✅ Understanding of DRF patterns and best practices
10. ✅ Hands-on experience with Django ORM and migrations

Good luck with your implementation! Remember: learning comes from struggling a bit, so don't worry if it takes time. Each error message teaches you something new!
