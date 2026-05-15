from collections import defaultdict
from decimal import Decimal
import csv
import datetime
from datetime import date as _date
import requests
from django.db import transaction
from django.db.models import Sum, Count, Q, Avg, Min, Max, DecimalField, F
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone


from .models import ExchangeRate, Transaction, TransactionCategory, UserTransactionTag, Wallet


def get_rate(base: str, quote: str, rate_date: _date) -> Decimal:
    if base == quote:
        return Decimal("1")

    try:
        return ExchangeRate.objects.get(
            base_currency=base, quote_currency=quote, date=rate_date
        ).rate
    except ExchangeRate.DoesNotExist:
        pass

    response = requests.get(
        f"https://api.frankfurter.app/{rate_date}",
        params={"from": base.upper(), "to": quote.upper()},
        timeout=5,
    )
    response.raise_for_status()
    data = response.json()
    returned_date = _date.fromisoformat(data["date"])
    rate = Decimal(str(data["rates"][quote.upper()]))

    ExchangeRate.objects.get_or_create(
        base_currency=base, quote_currency=quote, date=returned_date,
        defaults={"rate": rate},
    )
    if returned_date != rate_date:
        ExchangeRate.objects.get_or_create(
            base_currency=base, quote_currency=quote, date=rate_date,
            defaults={"rate": rate},
        )

    return rate


class GenericCSVImportService:
    def __init__(self, user, wallet, csv_file):
        self.user = user
        self.wallet = wallet
        self.csv_file = csv_file
        self.rows = None
        self.columns = None

        self.category_cache = {}  # {name: Category instance}
        self.tag_cache = {}  # {name: Tag instance}

        # Track what we created (for response)
        self.created_categories = set()
        self.created_tags = set()

    def parse(self):

        try:
            self.columns, self.rows = self._parse_csv()
        except Exception as e:
            raise {"success": False, "error": f"Error parsing CSV: {str(e)}"}

        # Collect unique values per column (for filter dropdowns)
        unique_values = defaultdict(set)

        for row_num, row in self.rows[:100]:
            for col in self.columns:
                val = row.get(col, "").strip()
                if val:
                    unique_values[col].add(val)

        sample_rows = [row for _, row in self.rows[:5]]

        return {
            "success": True,
            "columns": self.columns,
            "sample_rows": sample_rows,
            "total_rows": len(self.rows),
            "unique_values": {k: sorted(list(v)) for k, v in unique_values.items()},
        }

    def execute(self, column_mapping, amount_config, filters=None):
        """
        Import transactions using user's column mapping.

        This is Step 2 - user provides mapping, we import.

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
                return {"success": False, "error": str(e)}

        # Validate required mappings
        if "amount" not in column_mapping or "date" not in column_mapping:
            return {
                "success": False,
                "error": "'amount' and 'date' mappings are required",
            }

        # Initialize stats
        stats = {
            "total_rows": len(self.rows),
            "imported": 0,
            "skipped_filtered": 0,
            "skipped_duplicates": 0,
            "errors": 0,
        }
        errors = []

        # Process each row
        for row_num, row in self.rows:
            # Apply filters first
            if filters and not self._matches_filters(row, filters):
                stats["skipped_filtered"] += 1
                continue

            # Try to import this row
            result = self._import_row(row_num, row, column_mapping, amount_config)

            if result == "created":
                stats["imported"] += 1
            elif result == "duplicate":
                stats["skipped_duplicates"] += 1
            elif result.startswith("error:"):
                stats["errors"] += 1
                errors.append({"row": row_num, "error": result[6:]})

        return {
            "success": True,
            "stats": stats,
            "created_categories": sorted(list(self.created_categories)),
            "created_tags": sorted(list(self.created_tags)),
            "errors": errors[:20],  # Limit to first 20 errors
        }

    def _parse_csv(self):
        self.csv_file.seek(0)
        content = self.csv_file.read()

        if isinstance(content, bytes):
            # utf-8-sig handles BOM (Byte Order Mark) that Excel adds
            content = content.decode("utf-8-sig")

        lines = content.splitlines()
        reader = csv.DictReader(lines)

        if not reader.fieldnames:
            raise ValueError("CSV is empty or has no headers")

        columns = list(reader.fieldnames)
        rows = []
        for row_num, row in enumerate(reader, start=2):
            rows.append((row_num, row))
            if len(rows) > 10000:
                raise ValueError("CSV exceeds 10000 row limit")

        return columns, rows

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
            amount_str = row.get(column_mapping["amount"], "").strip()
            date_str = row.get(column_mapping["date"], "").strip()

            note = ""
            if column_mapping.get("note"):
                note = row.get(column_mapping["note"], "").strip()

            category_name = None
            if column_mapping.get("category"):
                category_name = row.get(column_mapping["category"], "").strip() or None

            tags_str = ""
            if column_mapping.get("tags"):
                tags_str = row.get(column_mapping["tags"], "").strip()

            currency = self.wallet.currency
            if column_mapping.get("currency"):
                currency = (
                    row.get(column_mapping["currency"], "").strip().lower()
                    or self.wallet.currency
                )

            date = self._parse_date(date_str)
            amount = self._convert_amount(
                amount_str, row, column_mapping, amount_config
            )

            if currency != self.wallet.currency:
                return f"error:Currency '{currency}' doesn't match wallet '{self.wallet.currency}'"

            if self._is_duplicate(date, amount, note):
                return "duplicate"

            category = None
            if category_name:
                category = self._get_or_create_category(category_name)

            tags = self._get_or_create_tags(tags_str)

            with transaction.atomic():
                txn = Transaction.objects.create(
                    note=note or "Imported transaction",
                    amount=amount,
                    currency=self.wallet.currency,
                    date=date,
                    wallet=self.wallet,
                    created_by=self.user,
                    category=category,
                )
                if tags:
                    txn.tags.set(tags)

            return "created"

        except Exception as e:
            return f"error:{str(e)}"

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
            dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt)
            return dt
        except ValueError:
            pass

        # Try common formats
        formats = [
            "%Y-%m-%d",  # 2024-01-15
            "%d-%m-%Y",  # 15-01-2024
            "%m/%d/%Y",  # 01/15/2024 (US)
            "%d/%m/%Y",  # 15/01/2024 (EU)
            "%Y-%m-%d %H:%M:%S",  # 2024-01-15 10:30:00
            "%d-%m-%Y %H:%M:%S",  # 15-01-2024 10:30:00
            "%d.%m.%Y",  # 15.01.2024 (German)
        ]
        for fmt in formats:
            try:
                dt = datetime.datetime.strptime(date_str, fmt)
                return timezone.make_aware(dt)
            except ValueError:
                continue

        raise ValueError(f"Unrecognized date format: {date_str}")

    def _convert_amount(self, amount_str, row, column_mapping, amount_config):
        """
        Convert amount string to signed decimal based on configuration.

        Returns:
            Decimal: Positive for income, negative for expense
        """
        from decimal import Decimal, InvalidOperation

        # Parse the amount string (remove currency symbols, commas, etc.)
        cleaned = amount_str.replace(",", "").replace("$", "").replace("€", "").replace("£", "").strip()

        try:
            amount = Decimal(cleaned)
        except InvalidOperation:
            raise ValueError(f"Invalid amount: {amount_str}")

        # Apply sign based on mode
        mode = amount_config.get("mode", "signed")

        if mode == "signed":
            # Amount already has the correct sign
            return amount
        elif mode == "always_expense":
            # All transactions are expenses (negative)
            return -abs(amount)
        elif mode == "always_income":
            # All transactions are income (positive)
            return abs(amount)
        elif mode == "type_column":
            # Check type column to determine sign
            type_col = column_mapping.get("type")
            if not type_col:
                raise ValueError("Type column not specified for type_column mode")

            type_value = row.get(type_col, "").strip()
            income_value = amount_config.get("income_value", "")
            expense_value = amount_config.get("expense_value", "")

            if type_value == income_value:
                return abs(amount)
            elif type_value == expense_value:
                return -abs(amount)
            else:
                raise ValueError(f"Unknown transaction type: {type_value}")
        else:
            raise ValueError(f"Unknown amount mode: {mode}")

    def _is_duplicate(self, date, amount, note):
        """
        Check if a transaction with same date, amount, and note already exists.

        This is a simple duplicate detection to avoid importing the same
        transaction multiple times.
        """
        from decimal import Decimal

        return Transaction.objects.filter(
            wallet=self.wallet,
            date=date,
            amount=Decimal(str(amount)),
            note=note,
        ).exists()

    def _get_or_create_category(self, category_name):
        """
        Get existing category by name or create a new one.

        Categories are user-scoped (not wallet-scoped).
        """
        if category_name in self.category_cache:
            return self.category_cache[category_name]

        category, created = TransactionCategory.objects.get_or_create(
            user=self.user,
            name=category_name,
            defaults={"icon": "circle", "color": "#6B7280"},
        )

        self.category_cache[category_name] = category

        if created:
            self.created_categories.add(category_name)

        return category

    def _get_or_create_tags(self, tags_str):
        """
        Parse tags string and get or create tag objects.

        Tags are comma-separated or semicolon-separated.
        Returns list of Tag objects.
        """
        if not tags_str:
            return []

        # Split by comma or semicolon
        tag_names = [t.strip() for t in tags_str.replace(";", ",").split(",") if t.strip()]

        tags = []
        for tag_name in tag_names:
            if tag_name in self.tag_cache:
                tags.append(self.tag_cache[tag_name])
            else:
                tag, created = UserTransactionTag.objects.get_or_create(
                    user=self.user,
                    name=tag_name,
                    defaults={"icon": "tag", "color": "#6B7280"},
                )
                self.tag_cache[tag_name] = tag
                tags.append(tag)

                if created:
                    self.created_tags.add(tag_name)

        return tags

    def _matches_filters(self, row, filters):
        """
        Check if row matches all filter rules.

        Returns True if row should be included (all filters match).
        """
        for filter_rule in filters:
            column = filter_rule.get("column", "")
            operator = filter_rule.get("operator", "equals")
            value = filter_rule.get("value", "")

            row_value = row.get(column, "").strip()

            if operator == "equals":
                if row_value != value:
                    return False
            elif operator == "not_equals":
                if row_value == value:
                    return False
            elif operator == "contains":
                if value.lower() not in row_value.lower():
                    return False
            elif operator == "not_contains":
                if value.lower() in row_value.lower():
                    return False

        return True


class DashboardService:
    """
    Aggregation logic for user and per-wallet dashboards.

    Plain Python service (no DRF deps) so it can also be called from
    management commands or tests. Mirrors the pattern used by
    GenericCSVImportService above.
    """

    UNCATEGORIZED_NAME = "Uncategorized"
    UNCATEGORIZED_ICON = "circle"
    UNCATEGORIZED_COLOR = "#6B7280"

    def __init__(self, user):
        self.user = user
        self.now = timezone.now()

    def user_summary(self, base_currency=None):
        wallets_qs = self._wallets_with_monthly_aggregates()

        wallet_data = []
        total_balance = Decimal("0")
        total_income = Decimal("0")
        total_expenses = Decimal("0")

        for wallet in wallets_qs:
            balance = wallet.initial_value + wallet.total_transactions
            income = wallet.income_this_month
            expenses = abs(wallet.expenses_this_month)

            if base_currency:
                try:
                    rate = get_rate(wallet.currency, base_currency, datetime.date.today())
                except Exception:
                    rate = None
                if rate is not None:
                    total_balance += balance * rate
                    total_income += income * rate
                    total_expenses += expenses * rate
                else:
                    total_balance += balance
                    total_income += income
                    total_expenses += expenses
            else:
                total_balance += balance
                total_income += income
                total_expenses += expenses
            wallet_data.append({
                "id": wallet.id,
                "name": wallet.name,
                "currency": wallet.currency,
                "balance": balance,
                "income_this_month": income,
                "expenses_this_month": expenses,
            })

        category_qs = Transaction.objects.filter(
            wallet__user=self.user,
            amount__lt=0,
            date__month=self.now.month,
            date__year=self.now.year,
        )
        spending_by_category = self._category_spending(category_qs, total_expenses)

        return {
            "summary": {
                "total_balance": total_balance,
                "total_income_this_month": total_income,
                "total_expenses_this_month": total_expenses,
                "net_this_month": total_income - total_expenses,
            },
            "wallets": wallet_data,
            "spending_by_category": spending_by_category,
            "monthly_trend": self._monthly_trend(),
        }

    def wallet_summary(self, wallet):
        aggregates = Transaction.objects.filter(wallet=wallet).aggregate(
            total_transactions=Count("id"),
            income_count=Count("id", filter=Q(amount__gt=0)),
            expense_count=Count("id", filter=Q(amount__lt=0)),
            income_this_month=Coalesce(
                Sum("amount", filter=Q(
                    amount__gt=0,
                    date__month=self.now.month,
                    date__year=self.now.year,
                )),
                Decimal("0"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            expenses_this_month_raw=Coalesce(
                Sum("amount", filter=Q(
                    amount__lt=0,
                    date__month=self.now.month,
                    date__year=self.now.year,
                )),
                Decimal("0"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            average_transaction=Coalesce(
                Avg("amount"),
                Decimal("0"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            largest_expense=Coalesce(
                Min("amount"),
                Decimal("0"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            largest_income=Coalesce(
                Max("amount"),
                Decimal("0"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            total_amount=Coalesce(
                Sum("amount"),
                Decimal("0"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )

        income_this_month = aggregates["income_this_month"]
        expenses_this_month = abs(aggregates["expenses_this_month_raw"])

        metrics = {
            "total_transactions": aggregates["total_transactions"],
            "income_count": aggregates["income_count"],
            "expense_count": aggregates["expense_count"],
            "income_this_month": income_this_month,
            "expenses_this_month": expenses_this_month,
            "net_this_month": income_this_month - expenses_this_month,
            "average_transaction": aggregates["average_transaction"],
            "largest_expense": aggregates["largest_expense"],
            "largest_income": aggregates["largest_income"],
        }

        category_qs = Transaction.objects.filter(wallet=wallet, amount__lt=0)
        category_breakdown = self._category_spending(category_qs)

        recent_transactions = (
            Transaction.objects.filter(wallet=wallet)
            .select_related("category")
            .prefetch_related("tags")
            .order_by("-date")[:10]
        )

        return {
            "wallet_id": wallet.id,
            "wallet_name": wallet.name,
            "currency": wallet.currency,
            "balance": wallet.initial_value + aggregates["total_amount"],
            "metrics": metrics,
            "category_breakdown": category_breakdown,
            "recent_transactions": recent_transactions,
        }

    def _wallets_with_monthly_aggregates(self):
        zero = Decimal("0")
        decimal_field = DecimalField(max_digits=12, decimal_places=2)
        return Wallet.objects.filter(user=self.user).annotate(
            total_transactions=Coalesce(
                Sum("transactions__amount"),
                zero,
                output_field=decimal_field,
            ),
            income_this_month=Coalesce(
                Sum(
                    "transactions__amount",
                    filter=Q(
                        transactions__amount__gt=0,
                        transactions__date__month=self.now.month,
                        transactions__date__year=self.now.year,
                    ),
                ),
                zero,
                output_field=decimal_field,
            ),
            expenses_this_month=Coalesce(
                Sum(
                    "transactions__amount",
                    filter=Q(
                        transactions__amount__lt=0,
                        transactions__date__month=self.now.month,
                        transactions__date__year=self.now.year,
                    ),
                ),
                zero,
                output_field=decimal_field,
            ),
        )

    def _category_spending(self, queryset, total_expenses=None):
        """
        Aggregate by category. Returns rows sorted by largest spend first.

        total_expenses: optional precomputed total (absolute value) used for
        percentage. If not given, derived from the queryset itself.
        """
        rows = list(
            queryset.values(
                "category__id",
                "category__name",
                "category__icon",
                "category__color",
            ).annotate(
                total_amount=Sum("amount"),
                transaction_count=Count("id"),
            )
        )

        if total_expenses is None:
            total_expenses = sum((abs(r["total_amount"]) for r in rows), Decimal("0"))

        denominator = total_expenses if total_expenses else Decimal("1")
        spending = []
        for r in rows:
            amount = r["total_amount"]
            spending.append({
                "category_id": r["category__id"],
                "category_name": r["category__name"] or self.UNCATEGORIZED_NAME,
                "category_icon": r["category__icon"] or self.UNCATEGORIZED_ICON,
                "category_color": r["category__color"] or self.UNCATEGORIZED_COLOR,
                "total_amount": amount,
                "transaction_count": r["transaction_count"],
                "percentage": float(abs(amount) / denominator * 100),
            })
        # Largest spend (most negative) first
        spending.sort(key=lambda x: x["total_amount"])
        return spending

    def _monthly_trend(self, months_back=6):
        # First day of the month, months_back months ago. Avoids the
        # spec's inline arithmetic edge case at month==6.
        cutoff = self._month_floor(self._shift_months(self.now, -(months_back - 1)))
        zero = Decimal("0")
        decimal_field = DecimalField(max_digits=12, decimal_places=2)

        rows = (
            Transaction.objects.filter(wallet__user=self.user, date__gte=cutoff)
            .annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(
                income=Coalesce(
                    Sum("amount", filter=Q(amount__gt=0)),
                    zero,
                    output_field=decimal_field,
                ),
                expenses=Coalesce(
                    Sum("amount", filter=Q(amount__lt=0)),
                    zero,
                    output_field=decimal_field,
                ),
            )
            .order_by("month")
        )

        return [
            {
                "month": r["month"].strftime("%Y-%m"),
                "income": r["income"],
                "expenses": abs(r["expenses"]),
                "net": r["income"] + r["expenses"],
            }
            for r in rows
        ]

    @staticmethod
    def _month_floor(dt):
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _shift_months(dt, delta):
        # Adjust month/year without dateutil.
        month_index = dt.month - 1 + delta
        year = dt.year + month_index // 12
        month = month_index % 12 + 1
        return dt.replace(year=year, month=month, day=1)
