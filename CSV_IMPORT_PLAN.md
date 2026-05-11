# CSV Transaction Import - Learning Guide

> Learn Django REST Framework by building a generic CSV importer

This guide teaches DRF concepts through building a real feature. Each step explains **what**, **why**, and links to official docs.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Step 1: Service Layer](#step-1-service-layer---business-logic)
3. [Step 2: Serializers](#step-2-serializers---validation--transformation)
4. [Step 3: Views](#step-3-views---http-handling)
5. [Step 4: URL Routing](#step-4-url-routing)
6. [Step 5: Testing](#step-5-testing)

---

## Architecture Overview

### The Feature We're Building

A generic CSV importer where users:
1. Select target wallet
2. Upload any CSV
3. Map CSV columns → app fields (amount, date, note, etc.)
4. Optionally filter rows (e.g., "only where Wallet = 'Main'")
5. Import transactions

### Why Generic Instead of Hardcoded?

**Bad approach** - Hardcoded Spendee parser:
```python
# ❌ Fragile - breaks if Spendee changes format
REQUIRED_COLUMNS = ['Date', 'Wallet', 'Type', 'Category name', 'Amount']
```

**Good approach** - User maps columns:
```python
# ✅ Flexible - works with any CSV
column_mapping = {'amount': 'Amount', 'date': 'Date', ...}  # User provides this
```

### DRF Architecture Pattern

```
HTTP Request
     ↓
┌─────────────┐
│   URLs      │  Route request to view
└─────────────┘
     ↓
┌─────────────┐
│   View      │  Handle HTTP, call serializer & service
└─────────────┘
     ↓
┌─────────────┐
│ Serializer  │  Validate input, transform data
└─────────────┘
     ↓
┌─────────────┐
│  Service    │  Business logic (not DRF, but good practice)
└─────────────┘
     ↓
┌─────────────┐
│   Models    │  Database operations
└─────────────┘
```

**Why this separation?**
- **Views** handle HTTP concerns (status codes, request/response)
- **Serializers** handle data validation and transformation
- **Services** handle business logic (reusable from CLI, tests, Celery tasks)
- **Models** handle database

📚 **Read**: [DRF Tutorial](https://www.django-rest-framework.org/tutorial/1-serialization/)

---

## Step 1: Service Layer - Business Logic

### Why a Service Layer?

DRF doesn't require services, but they're valuable:

```python
# ❌ Fat View - hard to test, hard to reuse
class CSVImportView(APIView):
    def post(self, request):
        # 200 lines of CSV parsing, validation, database operations...
        pass

# ✅ Thin View + Service - testable, reusable
class CSVImportView(APIView):
    def post(self, request):
        service = CSVImportService(user, wallet, file)
        return Response(service.execute(mapping))
```

**Benefits:**
- Unit test business logic without HTTP
- Reuse from management commands, Celery tasks
- Easier to read and maintain

📚 **Read**: [Service Layer Pattern](https://www.cosmicpython.com/book/chapter_04_service_layer.html)

### Create the Service

**File**: `backend/wallets/services.py` (NEW FILE)

```python
"""
Generic CSV Import Service

DRF LEARNING NOTE: Services vs Views
====================================
This is NOT a DRF concept - it's a software design pattern.
DRF views should be thin (handle HTTP only).
Business logic goes in services or model methods.

Why?
1. Testability - test CSV parsing without HTTP
2. Reusability - use from management commands, Celery, etc.
3. Clarity - views handle HTTP, services handle logic
"""

import csv
from decimal import Decimal, InvalidOperation
from datetime import datetime
from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from .models import Transaction, TransactionCategory, UserTransactionTag, Wallet


class GenericCSVImportService:
    """
    Generic CSV importer with user-defined column mapping.

    DRF LEARNING NOTE: Why not a ViewSet?
    =====================================
    ViewSets are great for CRUD operations on a single model.
    CSV import is a custom action that doesn't fit CRUD:
    - No model to list/retrieve/update/delete
    - Complex multi-step process
    - Multiple models involved (Transaction, Category, Tag)

    For custom actions, use APIView or @action decorator.

    Usage:
        service = GenericCSVImportService(user, wallet, csv_file)

        # Step 1: Parse and preview
        preview = service.parse()
        # Returns: columns, sample_rows, unique_values

        # Step 2: Import with user's mapping
        result = service.execute(
            column_mapping={'amount': 'Amount', 'date': 'Date', ...},
            amount_config={'mode': 'type_column', ...},
            filters=[{'column': 'Wallet', 'operator': 'equals', 'value': 'Main'}]
        )
    """

    def __init__(self, user, wallet, csv_file):
        """
        Initialize the service.

        DRF LEARNING NOTE: Dependency Injection
        =======================================
        We pass user, wallet, file as constructor args instead of
        accessing request.user inside the service. Why?

        1. Testability - easy to pass mock user/wallet in tests
        2. Decoupling - service doesn't know about HTTP/requests
        3. Explicit - clear what the service needs to work

        Args:
            user: Django User instance (from request.user)
            wallet: Wallet instance to import into
            csv_file: Uploaded file object (InMemoryUploadedFile)
        """
        self.user = user
        self.wallet = wallet
        self.csv_file = csv_file
        self.rows = None
        self.columns = None

        # Performance: Cache database lookups
        # Why? Avoid N+1 queries - without cache, each row does:
        #   Category.objects.get_or_create(name=name)  # DB query!
        # With 1000 rows and 10 categories, that's 1000 queries
        # instead of 10.
        self.category_cache = {}  # {name: Category instance}
        self.tag_cache = {}       # {name: Tag instance}

        # Track what we created (for response)
        self.created_categories = set()
        self.created_tags = set()

    def parse(self):
        """
        Parse CSV and return metadata for UI.

        This is Step 1 - user uploads CSV, we analyze it.
        Returns column names and sample data so UI can show
        mapping dropdowns.

        Returns:
            dict: {
                'success': bool,
                'columns': ['Date', 'Amount', ...],
                'sample_rows': [{...}, {...}],  # First 5 rows
                'total_rows': int,
                'unique_values': {
                    'Wallet': ['Main', 'Savings'],
                    'Type': ['Income', 'Expense']
                }
            }
        """
        try:
            self.columns, self.rows = self._parse_csv()
        except Exception as e:
            return {'success': False, 'error': str(e)}

        # Collect unique values per column (for filter dropdowns)
        # DRF LEARNING NOTE: defaultdict
        # ==============================
        # defaultdict(set) creates empty set for missing keys
        # Without it: unique_values[col].add(val) → KeyError
        # With it: automatically creates set, then adds
        unique_values = defaultdict(set)

        for row_num, row in self.rows[:100]:  # Check first 100 rows only
            for col in self.columns:
                val = row.get(col, '').strip()
                # Limit to 20 unique values per column (UI dropdown limit)
                if val and len(unique_values[col]) < 20:
                    unique_values[col].add(val)

        # Sample rows for preview table
        sample_rows = [row for _, row in self.rows[:5]]

        return {
            'success': True,
            'columns': self.columns,
            'sample_rows': sample_rows,
            'total_rows': len(self.rows),
            'unique_values': {k: sorted(list(v)) for k, v in unique_values.items()}
        }

    def execute(self, column_mapping, amount_config, filters=None):
        """
        Import transactions using user's column mapping.

        This is Step 2 - user provides mapping, we import.

        DRF LEARNING NOTE: Error Handling Strategy
        ==========================================
        We don't raise exceptions for row-level errors.
        Instead, we collect them and return in response.
        Why?
        - One bad row shouldn't abort entire import
        - User sees which rows failed and why
        - Partial success is better than total failure

        Args:
            column_mapping: {'amount': 'CSV Column Name', 'date': 'CSV Column', ...}
                Required: 'amount', 'date'
                Optional: 'note', 'category', 'tags', 'type', 'currency'

            amount_config: How to determine income vs expense
                {'mode': 'signed'} - amount already has sign
                {'mode': 'type_column', 'income_value': 'Income', 'expense_value': 'Expense'}
                {'mode': 'always_expense'} - all rows are expenses
                {'mode': 'always_income'} - all rows are income

            filters: Optional row filters
                [{'column': 'Wallet', 'operator': 'equals', 'value': 'Main'}]

        Returns:
            dict: {
                'success': bool,
                'stats': {'imported': 10, 'skipped_filtered': 5, ...},
                'created_categories': ['New Category'],
                'created_tags': ['new-tag'],
                'errors': [{'row': 5, 'error': 'Invalid date'}]
            }
        """
        # Parse if not already done (user might call execute directly)
        if self.rows is None:
            try:
                self.columns, self.rows = self._parse_csv()
            except Exception as e:
                return {'success': False, 'error': str(e)}

        # Validate required mappings
        if 'amount' not in column_mapping or 'date' not in column_mapping:
            return {'success': False, 'error': "'amount' and 'date' mappings are required"}

        # Initialize stats
        stats = {
            'total_rows': len(self.rows),
            'imported': 0,
            'skipped_filtered': 0,
            'skipped_duplicates': 0,
            'errors': 0
        }
        errors = []

        # Process each row
        for row_num, row in self.rows:
            # Apply filters first
            if filters and not self._matches_filters(row, filters):
                stats['skipped_filtered'] += 1
                continue

            # Try to import this row
            result = self._import_row(row_num, row, column_mapping, amount_config)

            if result == 'created':
                stats['imported'] += 1
            elif result == 'duplicate':
                stats['skipped_duplicates'] += 1
            elif result.startswith('error:'):
                stats['errors'] += 1
                errors.append({'row': row_num, 'error': result[6:]})

        return {
            'success': True,
            'stats': stats,
            'created_categories': sorted(list(self.created_categories)),
            'created_tags': sorted(list(self.created_tags)),
            'errors': errors[:20]  # Limit to first 20 errors
        }

    # ==================== PRIVATE METHODS ====================

    def _parse_csv(self):
        """
        Parse CSV file into list of rows.

        DRF LEARNING NOTE: File Handling
        ================================
        Uploaded files in Django are either:
        - InMemoryUploadedFile (small files, <2.5MB default)
        - TemporaryUploadedFile (large files)

        Both support .read() and .seek().
        We .seek(0) to reset position in case file was read before.

        📚 Docs: https://docs.djangoproject.com/en/stable/ref/files/uploads/

        Returns:
            tuple: (columns list, rows list of (row_num, dict) tuples)
        """
        # Reset file pointer to beginning
        self.csv_file.seek(0)
        content = self.csv_file.read()

        # Handle bytes vs string
        # Uploaded files are bytes, but csv.DictReader needs string
        if isinstance(content, bytes):
            # utf-8-sig handles BOM (Byte Order Mark) that Excel adds
            content = content.decode('utf-8-sig')

        # Parse CSV
        # DRF LEARNING NOTE: csv.DictReader
        # ==================================
        # DictReader gives us rows as dicts with header keys:
        #   {'Date': '2024-01-01', 'Amount': '100', ...}
        # Instead of plain lists:
        #   ['2024-01-01', '100', ...]
        #
        # 📚 Docs: https://docs.python.org/3/library/csv.html#csv.DictReader
        lines = content.splitlines()
        reader = csv.DictReader(lines)

        if not reader.fieldnames:
            raise ValueError("CSV is empty or has no headers")

        columns = list(reader.fieldnames)

        # Collect rows with line numbers (for error reporting)
        rows = []
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (1 is header)
            rows.append((row_num, row))
            if len(rows) > 10000:
                raise ValueError("CSV exceeds 10,000 row limit")

        return columns, rows

    def _matches_filters(self, row, filters):
        """
        Check if row matches all filter rules.

        DRF LEARNING NOTE: Filter Design
        =================================
        We support simple filters for MVP:
        - equals, not_equals, contains, not_empty
        - Multiple filters use AND logic

        For complex filtering, consider:
        - django-filter library
        - Custom FilterSet classes

        📚 Docs: https://django-filter.readthedocs.io/

        Args:
            row: Dict of CSV row data
            filters: List of filter rules

        Returns:
            bool: True if row matches all filters
        """
        for f in filters:
            col = f['column']
            op = f['operator']
            expected = f.get('value', '').lower()
            actual = row.get(col, '').strip().lower()

            if op == 'equals' and actual != expected:
                return False
            elif op == 'not_equals' and actual == expected:
                return False
            elif op == 'contains' and expected not in actual:
                return False
            elif op == 'not_empty' and not actual:
                return False

        return True

    def _import_row(self, row_num, row, column_mapping, amount_config):
        """
        Import a single CSV row as a Transaction.

        DRF LEARNING NOTE: Atomic Transactions
        ======================================
        We use transaction.atomic() to ensure:
        - Either transaction + tags are saved, or nothing is
        - No partial state if error occurs

        📚 Docs: https://docs.djangoproject.com/en/stable/topics/db/transactions/

        Returns:
            str: 'created', 'duplicate', or 'error:message'
        """
        try:
            # Extract values using column mapping
            amount_str = row.get(column_mapping['amount'], '').strip()
            date_str = row.get(column_mapping['date'], '').strip()

            # Optional fields - use .get() with empty string default
            note = ''
            if column_mapping.get('note'):
                note = row.get(column_mapping['note'], '').strip()

            category_name = None
            if column_mapping.get('category'):
                category_name = row.get(column_mapping['category'], '').strip() or None

            tags_str = ''
            if column_mapping.get('tags'):
                tags_str = row.get(column_mapping['tags'], '').strip()

            currency = self.wallet.currency
            if column_mapping.get('currency'):
                currency = row.get(column_mapping['currency'], '').strip().lower() or self.wallet.currency

            # Parse date
            date = self._parse_date(date_str)

            # Convert amount (apply sign based on amount_config)
            amount = self._convert_amount(amount_str, row, column_mapping, amount_config)

            # Validate currency matches wallet
            if currency != self.wallet.currency:
                return f"error:Currency '{currency}' doesn't match wallet '{self.wallet.currency}'"

            # Check for duplicates
            if self._is_duplicate(date, amount, note):
                return 'duplicate'

            # Get or create category
            category = None
            if category_name:
                category = self._get_or_create_category(category_name)

            # Get or create tags
            tags = self._get_or_create_tags(tags_str)

            # Create transaction atomically
            with transaction.atomic():
                txn = Transaction.objects.create(
                    note=note or 'Imported transaction',
                    amount=amount,
                    currency=self.wallet.currency,
                    date=date,
                    wallet=self.wallet,
                    created_by=self.user,
                    category=category
                )
                # Set M2M relationship
                # DRF LEARNING NOTE: M2M Assignment
                # ==================================
                # For ManyToMany fields, you can't set in create().
                # Must save object first, then use .set() or .add()
                #
                # 📚 Docs: https://docs.djangoproject.com/en/stable/topics/db/examples/many_to_many/
                if tags:
                    txn.tags.set(tags)

            return 'created'

        except Exception as e:
            return f'error:{str(e)}'

    def _parse_date(self, date_str):
        """
        Parse various date formats to timezone-aware datetime.

        DRF LEARNING NOTE: Timezone Handling
        ====================================
        Django with USE_TZ=True requires timezone-aware datetimes.
        Naive datetime (no timezone) will cause warnings/errors.

        timezone.make_aware() converts naive → aware using default TZ.
        timezone.now() always returns aware datetime.

        📚 Docs: https://docs.djangoproject.com/en/stable/topics/i18n/timezones/

        Args:
            date_str: Date string in various formats

        Returns:
            datetime: Timezone-aware datetime
        """
        if not date_str:
            raise ValueError("Date is empty")

        # Try ISO 8601 format first (most precise)
        # Handles: 2024-01-15, 2024-01-15T10:30:00, 2024-01-15T10:30:00Z
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt)
            return dt
        except ValueError:
            pass

        # Try common formats
        formats = [
            '%Y-%m-%d',           # 2024-01-15
            '%d-%m-%Y',           # 15-01-2024
            '%m/%d/%Y',           # 01/15/2024 (US)
            '%d/%m/%Y',           # 15/01/2024 (EU)
            '%Y-%m-%d %H:%M:%S',  # 2024-01-15 10:30:00
            '%d-%m-%Y %H:%M:%S',  # 15-01-2024 10:30:00
            '%d.%m.%Y',           # 15.01.2024 (German)
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return timezone.make_aware(dt)
            except ValueError:
                continue

        # Fallback: python-dateutil (handles almost anything)
        # pip install python-dateutil
        from dateutil import parser
        dt = parser.parse(date_str)
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt)
        return dt

    def _convert_amount(self, amount_str, row, column_mapping, amount_config):
        """
        Convert amount string to signed Decimal.

        DRF LEARNING NOTE: Decimal vs Float
        ===================================
        Always use Decimal for money! Float has precision issues:
            >>> 0.1 + 0.2
            0.30000000000000004

        Decimal is exact:
            >>> Decimal('0.1') + Decimal('0.2')
            Decimal('0.3')

        📚 Docs: https://docs.python.org/3/library/decimal.html

        Args:
            amount_str: Amount from CSV (e.g., "100.50", "1,234.56")
            row: Full CSV row (for type_column mode)
            column_mapping: User's column mapping
            amount_config: Amount sign handling config

        Returns:
            Decimal: Signed amount (positive=income, negative=expense)
        """
        # Clean amount string
        # Handle European format: "1.234,56" → "1234.56"
        # Handle spaces: "1 234.56" → "1234.56"
        amount_str = amount_str.replace(' ', '').replace(',', '.')

        # Handle double dots from European thousands separator
        # "1.234.56" should become "1234.56"
        parts = amount_str.rsplit('.', 1)
        if len(parts) == 2:
            amount_str = parts[0].replace('.', '') + '.' + parts[1]

        try:
            amount = Decimal(amount_str)
        except InvalidOperation:
            raise ValueError(f"Invalid amount: '{amount_str}'")

        # Apply sign based on mode
        mode = amount_config.get('mode', 'signed')

        if mode == 'signed':
            # Amount already has sign (positive=income, negative=expense)
            return amount

        elif mode == 'always_expense':
            # All amounts are expenses (e.g., credit card statement)
            return -abs(amount)

        elif mode == 'always_income':
            # All amounts are income
            return abs(amount)

        elif mode == 'type_column':
            # Use separate column to determine sign
            type_col = column_mapping.get('type')
            if not type_col:
                raise ValueError("'type_column' mode requires 'type' in column_mapping")

            type_val = row.get(type_col, '').strip().lower()
            income_val = amount_config.get('income_value', 'income').lower()
            expense_val = amount_config.get('expense_value', 'expense').lower()

            if type_val == income_val:
                return abs(amount)
            elif type_val == expense_val:
                return -abs(amount)
            else:
                raise ValueError(f"Unknown type value: '{type_val}' (expected '{income_val}' or '{expense_val}')")

        raise ValueError(f"Unknown amount mode: '{mode}'")

    def _is_duplicate(self, date, amount, note):
        """
        Check if transaction already exists.

        DRF LEARNING NOTE: QuerySet Methods
        ===================================
        .filter() returns QuerySet (lazy, chainable)
        .exists() returns bool (efficient, stops at first match)
        .count() returns int (counts all matches)

        For "does it exist?" checks, always use .exists()
        It's faster than .count() > 0 or bool(.filter())

        📚 Docs: https://docs.djangoproject.com/en/stable/ref/models/querysets/#exists

        Why date__date?
        ===============
        date__date extracts just the date part from datetime.
        This ignores time differences (timezone issues, etc.)

        📚 Docs: https://docs.djangoproject.com/en/stable/ref/models/querysets/#date
        """
        return Transaction.objects.filter(
            wallet=self.wallet,
            date__date=date.date(),  # Compare date only, ignore time
            amount=amount,
            note=note
        ).exists()

    def _get_or_create_category(self, name):
        """
        Get existing category or create new one.

        DRF LEARNING NOTE: get_or_create()
        ==================================
        Atomic operation that either:
        - Gets existing object matching criteria
        - Creates new object with defaults

        Returns tuple: (object, created_bool)

        Why use it?
        - Thread-safe (uses database locking)
        - Avoids race conditions
        - Single database round-trip

        📚 Docs: https://docs.djangoproject.com/en/stable/ref/models/querysets/#get-or-create

        DRF LEARNING NOTE: Caching
        ==========================
        We cache results to avoid N+1 queries.
        Without cache: 1000 rows with same category = 1000 queries
        With cache: 1000 rows with same category = 1 query + 999 cache hits
        """
        # Check cache first
        if name in self.category_cache:
            return self.category_cache[name]

        # Get or create (user-scoped categories)
        category, created = TransactionCategory.objects.get_or_create(
            user=self.user,
            name=name,
            defaults={
                'icon': 'tag',       # Default icon
                'color': '#6B7280'   # Default gray
            }
        )

        if created:
            self.created_categories.add(name)

        # Cache for future lookups
        self.category_cache[name] = category
        return category

    def _get_or_create_tags(self, tags_str):
        """
        Parse comma-separated tags and get/create each.

        DRF LEARNING NOTE: String Parsing
        =================================
        CSV tags might be: "food, urgent, recurring"
        We split by comma and strip whitespace from each.

        List comprehension with filter:
            [x.strip() for x in tags_str.split(',') if x.strip()]

        The 'if x.strip()' filters out empty strings from
        inputs like "food,,urgent" or "food, , urgent"
        """
        if not tags_str:
            return []

        tags = []
        for name in [t.strip() for t in tags_str.split(',') if t.strip()]:
            # Check cache
            if name in self.tag_cache:
                tags.append(self.tag_cache[name])
                continue

            # Get or create
            tag, created = UserTransactionTag.objects.get_or_create(
                user=self.user,
                name=name,
                defaults={
                    'icon': 'tag',
                    'color': '#3B82F6'  # Blue
                }
            )

            if created:
                self.created_tags.add(name)

            self.tag_cache[name] = tag
            tags.append(tag)

        return tags
```

---

## Step 2: Serializers - Validation & Transformation

### What Are Serializers?

Serializers are DRF's core concept. They handle:

1. **Deserialization**: JSON/form data → Python objects (input)
2. **Validation**: Check data is valid
3. **Serialization**: Python objects → JSON (output)

Think of them as Django Forms for APIs.

📚 **Read**: [DRF Serializers](https://www.django-rest-framework.org/api-guide/serializers/)

### Serializer vs ModelSerializer

```python
# ModelSerializer - auto-generates fields from model
# Use when: CRUD operations on a model
class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'date', 'note']

# Serializer - define fields manually
# Use when: Custom input that doesn't map to a model
class CSVImportSerializer(serializers.Serializer):
    file = serializers.FileField()
    column_mapping = serializers.DictField()
```

**Our case**: CSV import input doesn't map to any model, so we use `Serializer`.

📚 **Read**: [ModelSerializer](https://www.django-rest-framework.org/api-guide/serializers/#modelserializer)

### Create the Serializers

**File**: `backend/wallets/serializers.py` (add at end)

```python
# ============================================================
# CSV IMPORT SERIALIZERS
# ============================================================
#
# DRF LEARNING NOTE: Nested Serializers
# =====================================
# Serializers can be nested. Our structure:
#
# CSVExecuteSerializer
#   ├── file (FileField)
#   ├── column_mapping (DictField)
#   ├── amount_config (AmountConfigSerializer)  ← nested
#   └── filters (FilterRuleSerializer, many=True)  ← nested list
#
# 📚 Docs: https://www.django-rest-framework.org/api-guide/serializers/#dealing-with-nested-objects


class CSVParseSerializer(serializers.Serializer):
    """
    Validate file upload for CSV parsing (Step 1).

    DRF LEARNING NOTE: FileField
    ============================
    FileField handles uploaded files. The validated value is
    an UploadedFile object with:
    - .name - filename
    - .size - file size in bytes
    - .read() - get file contents
    - .seek(0) - reset read position

    📚 Docs: https://www.django-rest-framework.org/api-guide/fields/#filefield
    """
    file = serializers.FileField(
        required=True,
        help_text="CSV file to parse"
    )

    def validate_file(self, value):
        """
        Custom field validation.

        DRF LEARNING NOTE: validate_<field_name>
        ========================================
        DRF calls validate_<field_name> for each field.
        Raise ValidationError to reject, or return value to accept.

        Validation order:
        1. Field-level: validate_<field_name>()
        2. Object-level: validate() (access all fields)

        📚 Docs: https://www.django-rest-framework.org/api-guide/serializers/#field-level-validation
        """
        # Check extension
        if not value.name.lower().endswith('.csv'):
            raise serializers.ValidationError(
                "File must be a CSV (.csv extension)"
            )

        # Check size (5MB limit)
        max_size = 5 * 1024 * 1024  # 5MB in bytes
        if value.size > max_size:
            raise serializers.ValidationError(
                f"File too large. Maximum size is 5MB, got {value.size / 1024 / 1024:.1f}MB"
            )

        return value


class FilterRuleSerializer(serializers.Serializer):
    """
    Single filter rule for row filtering.

    DRF LEARNING NOTE: ChoiceField
    ==============================
    ChoiceField restricts input to specific values.
    Invalid values get clear error message:
    "operator: \"invalid\" is not a valid choice."

    📚 Docs: https://www.django-rest-framework.org/api-guide/fields/#choicefield

    Example filter:
        {"column": "Wallet", "operator": "equals", "value": "Main"}
    """
    column = serializers.CharField(
        help_text="CSV column name to filter on"
    )
    operator = serializers.ChoiceField(
        choices=['equals', 'not_equals', 'contains', 'not_empty'],
        help_text="Filter operator"
    )
    value = serializers.CharField(
        allow_blank=True,
        required=False,
        default='',
        help_text="Value to compare (not needed for 'not_empty')"
    )


class AmountConfigSerializer(serializers.Serializer):
    """
    Configuration for amount sign handling.

    DRF LEARNING NOTE: Default Values
    =================================
    - required=False + default='x' → field optional, defaults to 'x'
    - required=False (no default) → field optional, defaults to None
    - required=True (default) → field must be provided

    📚 Docs: https://www.django-rest-framework.org/api-guide/fields/#core-arguments
    """
    mode = serializers.ChoiceField(
        choices=['signed', 'type_column', 'always_expense', 'always_income'],
        help_text=(
            "How to determine transaction sign:\n"
            "- signed: Amount already has sign (+/-)\n"
            "- type_column: Use separate column (requires 'type' in mapping)\n"
            "- always_expense: All transactions are expenses\n"
            "- always_income: All transactions are income"
        )
    )
    income_value = serializers.CharField(
        required=False,
        default='income',
        help_text="Value in type column that indicates income (for type_column mode)"
    )
    expense_value = serializers.CharField(
        required=False,
        default='expense',
        help_text="Value in type column that indicates expense (for type_column mode)"
    )


class CSVExecuteSerializer(serializers.Serializer):
    """
    Validate import execution request (Step 2).

    DRF LEARNING NOTE: DictField and Nested Serializers
    ===================================================
    - DictField: arbitrary key-value pairs
    - Nested serializer: structured object with known fields

    column_mapping is DictField because keys are dynamic (CSV columns).
    amount_config is nested serializer because structure is fixed.

    📚 Docs:
    - DictField: https://www.django-rest-framework.org/api-guide/fields/#dictfield
    - Nested: https://www.django-rest-framework.org/api-guide/serializers/#dealing-with-nested-objects
    """
    file = serializers.FileField(required=True)

    column_mapping = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        help_text=(
            "Map app fields to CSV columns:\n"
            "Required: 'amount', 'date'\n"
            "Optional: 'note', 'category', 'tags', 'type', 'currency'\n"
            "Example: {'amount': 'Amount', 'date': 'Date', 'note': 'Description'}"
        )
    )

    amount_config = AmountConfigSerializer(
        help_text="How to determine income vs expense"
    )

    filters = FilterRuleSerializer(
        many=True,  # Accept list of filters
        required=False,
        default=list,
        help_text="Optional row filters. Multiple filters use AND logic."
    )

    def validate_file(self, value):
        """Same validation as CSVParseSerializer."""
        if not value.name.lower().endswith('.csv'):
            raise serializers.ValidationError("File must be a CSV")
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("File too large (max 5MB)")
        return value

    def validate_column_mapping(self, value):
        """
        Validate required fields are mapped.

        DRF LEARNING NOTE: Field vs Object Validation
        =============================================
        - validate_<field>: validate single field
        - validate(): validate across multiple fields

        Here we check column_mapping has required keys.
        We could also use validate() if we needed to check
        column_mapping against amount_config.

        📚 Docs: https://www.django-rest-framework.org/api-guide/serializers/#object-level-validation
        """
        required = ['amount', 'date']
        missing = [f for f in required if f not in value or not value[f]]

        if missing:
            raise serializers.ValidationError(
                f"Required mappings missing: {', '.join(missing)}"
            )

        return value

    def validate(self, data):
        """
        Object-level validation (cross-field).

        DRF LEARNING NOTE: validate() Method
        ====================================
        Called after all field validations pass.
        Has access to all fields via 'data' dict.
        Use for validation that depends on multiple fields.

        📚 Docs: https://www.django-rest-framework.org/api-guide/serializers/#object-level-validation
        """
        # If mode is type_column, 'type' must be in column_mapping
        amount_config = data.get('amount_config', {})
        column_mapping = data.get('column_mapping', {})

        if amount_config.get('mode') == 'type_column':
            if 'type' not in column_mapping or not column_mapping['type']:
                raise serializers.ValidationError({
                    'column_mapping': "'type' mapping required when using 'type_column' mode"
                })

        return data
```

---

## Step 3: Views - HTTP Handling

### APIView vs ViewSet

| Feature | APIView | ViewSet |
|---------|---------|---------|
| **Use case** | Custom actions | CRUD on model |
| **URL routing** | Manual | Automatic via Router |
| **Methods** | get(), post(), etc. | list(), create(), retrieve(), etc. |
| **Flexibility** | High | Medium |

**Our case**: CSV import doesn't fit CRUD pattern, so we use `APIView`.

📚 **Read**:
- [APIView](https://www.django-rest-framework.org/api-guide/views/)
- [ViewSets](https://www.django-rest-framework.org/api-guide/viewsets/)

### Create the Views

**File**: `backend/wallets/views.py` (add at end)

```python
# ============================================================
# CSV IMPORT VIEWS
# ============================================================
#
# DRF LEARNING NOTE: View Responsibilities
# ========================================
# Views should be thin! They handle HTTP concerns:
# 1. Parse request data
# 2. Call serializer for validation
# 3. Call service for business logic
# 4. Return response with appropriate status
#
# Business logic goes in services, NOT views.

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Wallet
from .services import GenericCSVImportService
from .serializers import CSVParseSerializer, CSVExecuteSerializer


class CSVParseView(APIView):
    """
    Step 1: Parse CSV and return column info.

    POST /api/wallets/<wallet_id>/import/parse/

    DRF LEARNING NOTE: APIView Class Attributes
    ===========================================
    - permission_classes: Who can access? [IsAuthenticated] = logged in users
    - authentication_classes: How to identify user? [JWTAuthentication] = JWT token
    - parser_classes: How to parse request body? (default includes JSON, form, multipart)
    - renderer_classes: How to render response? (default includes JSON)

    📚 Docs: https://www.django-rest-framework.org/api-guide/views/#api-policy-attributes

    DRF LEARNING NOTE: Why Not @api_view?
    =====================================
    DRF has two styles:
    1. Function-based: @api_view(['POST'])
    2. Class-based: APIView

    Class-based is better for:
    - Organizing related methods (get, post, put, delete)
    - Sharing code via inheritance
    - Class attributes (permission_classes, etc.)

    📚 Docs: https://www.django-rest-framework.org/api-guide/views/#function-based-views
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, wallet_id):
        """
        Handle POST request.

        DRF LEARNING NOTE: Request Object
        =================================
        DRF's Request extends Django's HttpRequest:
        - request.data: Parsed body (JSON, form, multipart)
        - request.query_params: URL query params (?key=value)
        - request.user: Authenticated user (or AnonymousUser)
        - request.FILES: Uploaded files (also in request.data for multipart)

        📚 Docs: https://www.django-rest-framework.org/api-guide/requests/
        """
        # Get wallet (security: only user's wallets)
        try:
            wallet = Wallet.objects.get(id=wallet_id, user=request.user)
        except Wallet.DoesNotExist:
            return Response(
                {'error': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate input
        # DRF LEARNING NOTE: Serializer Usage Pattern
        # ===========================================
        # 1. Create serializer with data=request.data
        # 2. Call .is_valid() to run validation
        # 3. Access .validated_data for clean data
        # 4. Access .errors for validation errors
        #
        # Alternative: is_valid(raise_exception=True) raises ValidationError
        #
        # 📚 Docs: https://www.django-rest-framework.org/api-guide/serializers/#validation
        serializer = CSVParseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        # Call service (business logic)
        service = GenericCSVImportService(
            user=request.user,
            wallet=wallet,
            csv_file=serializer.validated_data['file']
        )
        result = service.parse()

        # Return response
        # DRF LEARNING NOTE: Response Object
        # ==================================
        # Response(data, status, headers)
        # - data: Will be serialized to JSON (or other format)
        # - status: HTTP status code (use status.HTTP_xxx constants)
        #
        # 📚 Docs: https://www.django-rest-framework.org/api-guide/responses/
        if not result.get('success'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


class CSVExecuteView(APIView):
    """
    Step 2: Execute import with user's column mapping.

    POST /api/wallets/<wallet_id>/import/execute/

    DRF LEARNING NOTE: Idempotency
    ==============================
    This endpoint is NOT idempotent (calling twice creates duplicates).
    We have duplicate detection to mitigate, but consider:
    - Adding idempotency key header
    - Tracking import jobs in database
    - Returning 409 Conflict if same file imported recently

    📚 Read: https://stripe.com/docs/api/idempotent_requests
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, wallet_id):
        """Execute CSV import with mapping."""
        # Get wallet
        try:
            wallet = Wallet.objects.get(id=wallet_id, user=request.user)
        except Wallet.DoesNotExist:
            return Response(
                {'error': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate input
        serializer = CSVExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            # DRF LEARNING NOTE: Error Response Format
            # ========================================
            # serializer.errors returns dict of field → errors:
            # {
            #     'column_mapping': ['Required mappings missing: amount, date'],
            #     'file': ['File too large']
            # }
            #
            # For non-field errors, key is 'non_field_errors'
            #
            # 📚 Docs: https://www.django-rest-framework.org/api-guide/serializers/#validation
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract validated data
        data = serializer.validated_data

        # Execute import
        service = GenericCSVImportService(
            user=request.user,
            wallet=wallet,
            csv_file=data['file']
        )
        result = service.execute(
            column_mapping=data['column_mapping'],
            amount_config=data['amount_config'],
            filters=data.get('filters', [])
        )

        if not result.get('success'):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        # DRF LEARNING NOTE: Status Codes
        # ===============================
        # 200 OK: Request succeeded, returning data
        # 201 CREATED: Resource created (for POST creating new item)
        # 204 NO CONTENT: Success, no body (for DELETE)
        # 400 BAD REQUEST: Invalid input
        # 401 UNAUTHORIZED: Not authenticated
        # 403 FORBIDDEN: Authenticated but not allowed
        # 404 NOT FOUND: Resource doesn't exist
        #
        # We use 200 (not 201) because we're returning stats,
        # not the created resources.
        #
        # 📚 Docs: https://www.django-rest-framework.org/api-guide/status-codes/
        return Response(result, status=status.HTTP_200_OK)
```

---

## Step 4: URL Routing

### DRF URL Patterns

Two approaches:
1. **Manual**: `path()` with `.as_view()`
2. **Router**: Auto-generates URLs for ViewSets

We use manual because APIView doesn't work with Router.

📚 **Read**: [DRF Routers](https://www.django-rest-framework.org/api-guide/routers/)

### Add URL Routes

**File**: `backend/wallets/urls.py`

```python
"""
URL Configuration for wallets app.

DRF LEARNING NOTE: URL Design
=============================
RESTful URL patterns:
- /wallets/              → list all wallets
- /wallets/<id>/         → single wallet
- /wallets/<id>/import/  → wallet sub-resource

Our import endpoints are nested under wallet:
- POST /wallets/<id>/import/parse/   → parse CSV
- POST /wallets/<id>/import/execute/ → execute import

Why nested? Import is an action ON a wallet, not a separate resource.

📚 Read: https://restfulapi.net/resource-naming/
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    WalletViewSet,
    TransactionViewSet,
    TransactionCategoryViewSet,
    UserTransactionTagViewSet,
    # Import views
    CSVParseView,
    CSVExecuteView,
)

# DRF LEARNING NOTE: DefaultRouter
# ================================
# Router auto-generates URLs for ViewSets:
# - GET /wallets/ → list()
# - POST /wallets/ → create()
# - GET /wallets/<pk>/ → retrieve()
# - PUT /wallets/<pk>/ → update()
# - DELETE /wallets/<pk>/ → destroy()
#
# 📚 Docs: https://www.django-rest-framework.org/api-guide/routers/

router = DefaultRouter()
router.register('wallets', WalletViewSet, basename='wallet')
router.register('transactions', TransactionViewSet, basename='transaction')
router.register('categories', TransactionCategoryViewSet, basename='category')
router.register('tags', UserTransactionTagViewSet, basename='tag')

urlpatterns = [
    # Router URLs (ViewSets)
    path('', include(router.urls)),

    # Manual URLs (APIViews)
    # DRF LEARNING NOTE: URL Parameters
    # =================================
    # <uuid:wallet_id> captures UUID and passes to view as wallet_id
    # Django URL converters: str, int, slug, uuid, path
    #
    # 📚 Docs: https://docs.djangoproject.com/en/stable/topics/http/urls/#path-converters
    path(
        'wallets/<uuid:wallet_id>/import/parse/',
        CSVParseView.as_view(),
        name='csv-import-parse'
    ),
    path(
        'wallets/<uuid:wallet_id>/import/execute/',
        CSVExecuteView.as_view(),
        name='csv-import-execute'
    ),
]
```

---

## Step 5: Testing

### Test with cURL

```bash
# 1. Get JWT token
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "your_user", "password": "your_pass"}'

# Save the access token
TOKEN="eyJ..."

# 2. List your wallets (get wallet ID)
curl -X GET http://localhost:8000/api/wallets/ \
  -H "Authorization: Bearer $TOKEN"

# Save wallet ID
WALLET_ID="uuid-of-your-wallet"

# 3. Create test CSV
cat > test.csv << 'EOF'
Date,Wallet,Type,Category name,Amount,Currency,Note,Labels
2024-11-12,Main,Expense,Groceries,72.08,pln,Weekly shopping,"food,recurring"
2024-11-11,Main,Income,Salary,3000.00,pln,Monthly salary,
2024-11-10,Savings,Expense,Transport,15.50,pln,Bus ticket,
EOF

# 4. Step 1: Parse CSV
curl -X POST "http://localhost:8000/api/wallets/$WALLET_ID/import/parse/" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.csv"

# 5. Step 2: Execute import
curl -X POST "http://localhost:8000/api/wallets/$WALLET_ID/import/execute/" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.csv" \
  -F 'column_mapping={"amount":"Amount","date":"Date","note":"Note","category":"Category name","tags":"Labels","type":"Type"}' \
  -F 'amount_config={"mode":"type_column","income_value":"Income","expense_value":"Expense"}' \
  -F 'filters=[{"column":"Wallet","operator":"equals","value":"Main"}]'
```

### Write Python Tests

**File**: `backend/wallets/tests/test_csv_import.py`

```python
"""
Tests for CSV import functionality.

DRF LEARNING NOTE: Testing
==========================
DRF provides APITestCase with useful methods:
- self.client.post(url, data, format='multipart')
- self.client.credentials(HTTP_AUTHORIZATION='Bearer ...')

📚 Docs: https://www.django-rest-framework.org/api-guide/testing/
"""
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status

from wallets.models import Wallet, Transaction


class CSVImportTests(APITestCase):
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
        self.wallet = Wallet.objects.create(
            name='Test Wallet',
            user=self.user,
            initial_value=Decimal('1000.00'),
            currency='pln'
        )
        # Authenticate
        self.client.force_authenticate(user=self.user)

    def test_parse_csv_returns_columns(self):
        """Test that parse endpoint returns CSV columns."""
        csv_content = b"Date,Amount,Note\n2024-01-01,100,Test"
        csv_file = BytesIO(csv_content)
        csv_file.name = 'test.csv'

        response = self.client.post(
            f'/api/wallets/{self.wallet.id}/import/parse/',
            {'file': csv_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['columns'], ['Date', 'Amount', 'Note'])
        self.assertEqual(response.data['total_rows'], 1)

    def test_execute_creates_transactions(self):
        """Test that execute endpoint creates transactions."""
        csv_content = b"Date,Amount,Note\n2024-01-01,100.50,Test transaction"
        csv_file = BytesIO(csv_content)
        csv_file.name = 'test.csv'

        response = self.client.post(
            f'/api/wallets/{self.wallet.id}/import/execute/',
            {
                'file': csv_file,
                'column_mapping': '{"amount": "Amount", "date": "Date", "note": "Note"}',
                'amount_config': '{"mode": "always_expense"}',
                'filters': '[]'
            },
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stats']['imported'], 1)

        # Verify transaction created
        txn = Transaction.objects.get(wallet=self.wallet)
        self.assertEqual(txn.amount, Decimal('-100.50'))  # Negative (expense)
        self.assertEqual(txn.note, 'Test transaction')
```

---

## Checklist

### Backend
- [x] Transaction.date uses `default=timezone.now` (already done)
- [ ] Create `backend/wallets/services.py`
- [ ] Add serializers to `backend/wallets/serializers.py`
- [ ] Add views to `backend/wallets/views.py`
- [ ] Add URLs to `backend/wallets/urls.py`
- [ ] Test with cURL
- [ ] Write unit tests

### UI (Future)
- [ ] Import modal/page
- [ ] File upload component
- [ ] Column mapping dropdowns
- [ ] Amount mode selection
- [ ] Filter builder
- [ ] Results display

---

## Further Reading

### DRF Documentation
- [Tutorial](https://www.django-rest-framework.org/tutorial/1-serialization/) - Start here
- [Serializers](https://www.django-rest-framework.org/api-guide/serializers/)
- [Views](https://www.django-rest-framework.org/api-guide/views/)
- [Requests](https://www.django-rest-framework.org/api-guide/requests/)
- [Responses](https://www.django-rest-framework.org/api-guide/responses/)
- [Validation](https://www.django-rest-framework.org/api-guide/serializers/#validation)
- [Status Codes](https://www.django-rest-framework.org/api-guide/status-codes/)
- [Testing](https://www.django-rest-framework.org/api-guide/testing/)

### Django Documentation
- [File Uploads](https://docs.djangoproject.com/en/stable/ref/files/uploads/)
- [QuerySets](https://docs.djangoproject.com/en/stable/ref/models/querysets/)
- [Transactions](https://docs.djangoproject.com/en/stable/topics/db/transactions/)
- [Timezones](https://docs.djangoproject.com/en/stable/topics/i18n/timezones/)

### Python Documentation
- [csv module](https://docs.python.org/3/library/csv.html)
- [decimal module](https://docs.python.org/3/library/decimal.html)
- [datetime](https://docs.python.org/3/library/datetime.html)
