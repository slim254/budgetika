from collections import defaultdict
from decimal import Decimal
from datetime import timedelta
from math import ceil
import csv
import datetime
import re
from datetime import date as _date
import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, Count, Q, Avg, Min, Max, DecimalField, F
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone


from .models import ExchangeRate, ImportCategoryRule, SavingsGoal, Transaction, TransactionCategory, UserTransactionTag, Wallet


def suggest_keyword(signature: str) -> str:
    """Guess a merchant keyword from a transaction signature.

    Takes the leading run of purely-alphabetic tokens (merchant names usually
    lead), stopping at the first token with a digit/symbol. Falls back to the
    longest alphabetic token. The result is editable by the user, so an
    imperfect guess is fine. Unicode-aware (handles Polish characters).
    """
    tokens = [t for t in re.split(r"[\s|]+", signature) if t]
    leading = []
    for t in tokens:
        if t.isalpha() and len(t) >= 2:
            leading.append(t)
        else:
            break
    if leading:
        return " ".join(leading)[:100]
    alpha = [re.sub(r"[\W\d_]+", "", t) for t in tokens]  # keep letters only
    alpha = [a for a in alpha if len(a) >= 3]
    if alpha:
        return max(alpha, key=len)[:100]
    return tokens[0][:100] if tokens else ""


# A date written as three numeric components, optionally followed by a time.
# Used to guess whether a file is day-first (EU) or month-first (US).
_DATE_TRIPLE_RE = re.compile(r"^\s*(\d{1,4})[-/.](\d{1,2})[-/.](\d{1,4})")

# Component order for each supported date format.
_DATE_ORDER_PARTS = {
    "DMY": ("%d", "%m", "%Y"),
    "MDY": ("%m", "%d", "%Y"),
    "YMD": ("%Y", "%m", "%d"),
}

DATE_FORMAT_CHOICES = ("auto", "DMY", "MDY", "YMD")

# EU user: when nothing in the file disambiguates 01/02/2024, assume 1 February.
DEFAULT_DATE_ORDER = "DMY"


def _candidate_date_formats(order, two_digit_year=True):
    """strptime patterns for a component order, across separators and time suffixes.

    two_digit_year=False keeps only four-digit-year patterns. A two-digit year
    makes a date ambiguous again ("15.01.24" is a valid YMD, DMY and MDY date),
    so those variants must never be tried ahead of the order the user chose.
    """
    a, b, c = _DATE_ORDER_PARTS[order]
    formats = []
    for sep in ("-", "/", "."):
        base = sep.join((a, b, c))
        for suffix in ("", " %H:%M:%S", " %H:%M", "T%H:%M:%S", "T%H:%M"):
            formats.append(base + suffix)
        if not two_digit_year:
            continue
        # Two-digit year variant (15/01/24). %Y matches exactly four digits and
        # %y exactly two, so these can never shadow each other.
        short = base.replace("%Y", "%y")
        for suffix in ("", " %H:%M:%S", " %H:%M"):
            formats.append(short + suffix)
    return formats


_CANDIDATE_FORMATS = {o: _candidate_date_formats(o) for o in _DATE_ORDER_PARTS}

# Always accepted, whatever order was chosen: a four-digit leading year cannot
# be a day or a month, so these are unambiguous.
_ISO_YEAR_FIRST_FORMATS = _candidate_date_formats("YMD", two_digit_year=False)


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

        self.category_cache = {}  # {lowercased name: Category instance}
        self.tag_cache = {}  # {name: Tag instance}

        # Snapshot of (date, amount, note) for transactions that already existed
        # when the import started. Taken once, before the row loop.
        self._existing_keys = None

        # Component order used to read ambiguous numeric dates (see _parse_date).
        self._date_order = DEFAULT_DATE_ORDER

        # AI review mode: {normalized_signature: category_id}. None => legacy behavior.
        self.ai_categories = None

        # Track what we created (for response)
        self.created_categories = set()
        self.created_tags = set()

    def parse(self):

        try:
            self.columns, self.rows = self._parse_csv()
        except Exception as e:
            raise ValueError(f"Error parsing CSV: {str(e)}")

        # Collect unique values per column (for filter dropdowns)
        unique_values = defaultdict(set)

        for row_num, row in self.rows[:100]:
            for col in self.columns:
                val = row.get(col, "").strip()
                if val:
                    unique_values[col].add(val)

        sample_rows = [row for _, row in self.rows[:5]]

        # Date format detection, per column plus an overall guess. The user has
        # not mapped a date column yet at this point, so every column that looks
        # date-like is reported and the frontend can pre-select the right guess
        # (and show a manual selector when it is ambiguous).
        date_formats = {}
        best_col, best_hits = None, 0
        for col in self.columns:
            order, ambiguous, hits = self._detect_date_order(
                row.get(col, "") for _, row in self.rows
            )
            if order is None:
                continue
            date_formats[col] = {"format": order, "ambiguous": ambiguous}
            if hits > best_hits:
                best_col, best_hits = col, hits

        overall = date_formats.get(best_col) or {
            # No date-like column found: fall back to the EU default and flag it
            # as ambiguous so the frontend still shows a usable selector.
            "format": DEFAULT_DATE_ORDER,
            "ambiguous": True,
        }

        return {
            "success": True,
            "columns": self.columns,
            "sample_rows": sample_rows,
            "total_rows": len(self.rows),
            "unique_values": {k: sorted(list(v)) for k, v in unique_values.items()},
            "date_format": overall["format"],
            "date_format_ambiguous": overall["ambiguous"],
            "date_formats": date_formats,
        }

    def execute(self, column_mapping, amount_config, filters=None, ai_categories=None,
                rules=None, date_format="auto"):
        """
        Import transactions using user's column mapping.

        This is Step 2 - user provides mapping, we import.

        ai_categories: None => legacy behavior (auto-create categories from the
            mapped column). A dict (possibly empty) {normalized_signature:
            category_id} => AI review mode: keep mapped values that match an
            existing category, fill the rest from the AI suggestion map, and
            never auto-create categories.

        rules: optional list of {"keyword", "category_id"} to upsert as durable
            ImportCategoryRule rows before importing. In AI mode, ALL of the
            user's saved rules (plus these) are applied by keyword substring, so
            teaching a merchant once cascades to every similar row now and on
            future imports.

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

            date_format: 'auto' (default), 'DMY', 'MDY' or 'YMD'. Controls how
                ambiguous numeric dates like 01/02/2024 are read. 'auto'
                pre-scans the whole date column (see _resolve_date_order).

        Returns:
            dict: {
                'success': bool,
                'stats': {'imported': 10, 'skipped_filtered': 5, ...},
                'created_categories': ['New Category'],
                'created_tags': ['new-tag'],
                'errors': [{'row': 5, 'error': 'Invalid date'}]
            }
        """
        self.ai_categories = ai_categories

        # In AI mode, persist any newly-taught rules and load the full rule set.
        if ai_categories is not None:
            self._upsert_rules(rules or [])
            self._load_rules()

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

        self._date_order = self._resolve_date_order(column_mapping, date_format)

        # Snapshot what is already in the wallet BEFORE importing anything.
        # Duplicate detection compares against this snapshot only, so a CSV that
        # legitimately contains N identical rows (same day, same amount, same
        # merchant — e.g. three coffees) imports all N instead of collapsing
        # them into one.
        self._snapshot_existing_keys()

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
            content = self._decode_bytes(content)

        lines = content.splitlines()
        if not lines:
            raise ValueError("CSV is empty or has no headers")

        delimiter = self._sniff_delimiter(lines[0])
        reader = csv.reader(lines, delimiter=delimiter)
        row_iter = iter(reader)

        try:
            header = next(row_iter)
        except StopIteration:
            raise ValueError("CSV is empty or has no headers")

        # Bank exports (e.g. PKO BP) pad rows with several blank-named
        # columns that hold extra description fields. csv.DictReader would
        # collapse those duplicate "" keys and drop the data, so we name
        # them ourselves before building row dicts.
        columns = self._uniquify_headers(header)

        rows = []
        for row_num, values in enumerate(row_iter, start=2):
            # Skip blank lines (csv.reader yields [] / all-empty rows,
            # unlike DictReader which drops them silently).
            if not any(v.strip() for v in values):
                continue
            row = dict(zip(columns, values))
            rows.append((row_num, row))
            if len(rows) > 10000:
                raise ValueError("CSV exceeds 10000 row limit")

        return columns, rows

    @staticmethod
    def _uniquify_headers(header):
        """Give every column a unique, non-empty name.

        Blank headers become "Column N" (1-based position); duplicate
        names get a " (2)", " (3)" suffix. This keeps otherwise-lost
        columns mappable in the import UI, which shows sample rows so the
        user can tell what each generic name contains.
        """
        seen = {}
        result = []
        for index, name in enumerate(header, start=1):
            name = (name or "").strip()
            if not name:
                name = f"Column {index}"
            if name in seen:
                seen[name] += 1
                name = f"{name} ({seen[name]})"
            else:
                seen[name] = 1
            result.append(name)
        return result

    @staticmethod
    def _decode_bytes(raw):
        """Decode raw CSV bytes, trying encodings in order of specificity.

        Revolut/Wise export UTF-8; Polish banks (PKO BP, mBank) commonly
        export Windows-1250. iso-8859-2 (Latin-2) is a related fallback,
        and latin-1 decodes any byte so it is the final catch-all.
        utf-8-sig strips the BOM that Excel prepends.
        """
        for encoding in ("utf-8-sig", "cp1250", "iso-8859-2", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def _sniff_delimiter(header_line):
        """Pick the delimiter that appears most in the header row.

        Handles comma (Revolut, mBank), semicolon (many Polish/German
        banks) and tab. Defaults to comma when nothing else is present.
        """
        counts = {d: header_line.count(d) for d in (",", ";", "\t")}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","

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

            note_cols = column_mapping.get("note") or []
            if isinstance(note_cols, str):
                note_cols = [note_cols] if note_cols else []
            note = " - ".join(
                v for v in (row.get(col, "").strip() for col in note_cols) if v
            ) or "Imported transaction"

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

            category = self._resolve_category(row, column_mapping)

            tags = self._get_or_create_tags(tags_str)

            with transaction.atomic():
                txn = Transaction.objects.create(
                    note=note,
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

    @staticmethod
    def _detect_date_order(values):
        """Guess the component order of a column of date strings.

        Returns (order, ambiguous, hits):
            order:     'DMY' | 'MDY' | 'YMD', or None when nothing looked like a date
            ambiguous: True when the values alone cannot prove the order
            hits:      how many values parsed as a numeric date triple

        A value whose day-position exceeds 12 (e.g. 15/01/2024) proves the
        order. A four-digit leading component proves year-first. When neither
        appears — or when the file contradicts itself — we report the EU
        default and flag it ambiguous so the user can override.
        """
        ymd = dmy = mdy = unproven = 0
        for value in values:
            match = _DATE_TRIPLE_RE.match(value or "")
            if not match:
                continue
            first, second, _ = match.groups()
            if len(first) == 4:
                ymd += 1
                continue
            a, b = int(first), int(second)
            if a > 12 and b <= 12:
                dmy += 1
            elif b > 12 and a <= 12:
                mdy += 1
            else:
                unproven += 1

        hits = ymd + dmy + mdy + unproven
        if hits == 0:
            return None, False, 0
        if dmy and not mdy:
            return "DMY", False, hits
        if mdy and not dmy:
            return "MDY", False, hits
        if not dmy and not mdy and ymd and not unproven:
            return "YMD", False, hits
        # Either the column contradicts itself, or nothing disambiguates it.
        return DEFAULT_DATE_ORDER, True, hits

    def _resolve_date_order(self, column_mapping, date_format):
        """Pick the component order to parse this import's date column with.

        An explicit DMY/MDY/YMD wins. 'auto' (or anything unrecognized)
        pre-scans EVERY row of the mapped date column, so one 15/01/2024
        anywhere in the file settles the format for all rows — rather than the
        old behavior where each row was guessed in isolation and US order
        happened to be tried first.
        """
        explicit = (date_format or "").strip().upper()
        if explicit in _DATE_ORDER_PARTS:
            return explicit

        col = column_mapping.get("date")
        if not col or not self.rows:
            return DEFAULT_DATE_ORDER
        order, _ambiguous, _hits = self._detect_date_order(
            row.get(col, "") for _, row in self.rows
        )
        return order or DEFAULT_DATE_ORDER

    def _parse_date(self, date_str, order=None):
        """
        Parse various date formats to timezone-aware datetime.

        Parsing is STRICT to the resolved order for this import, so a file read
        as day-first never silently reinterprets a row as month-first. Order of
        attempts:
        1. ISO 8601 (unambiguous, most precise)
        2. Four-digit year-first patterns — a leading 4-digit year cannot be a
           day or a month, so these are safe under any chosen order
        3. The resolved order for this import (self._date_order), including its
           two-digit-year variants

        Anything else raises, surfacing as a normal per-row import error.

        DRF LEARNING NOTE: Timezone Handling
        ====================================
        Django with USE_TZ=True requires timezone-aware datetimes.
        Naive datetime (no timezone) will cause warnings/errors.

        timezone.make_aware() converts naive → aware using default TZ.
        timezone.now() always returns aware datetime.

        📚 Docs: https://docs.djangoproject.com/en/stable/topics/i18n/timezones/

        Args:
            date_str: Date string in various formats
            order: 'DMY' | 'MDY' | 'YMD'; defaults to the import's resolved order

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

        order = (order or self._date_order or DEFAULT_DATE_ORDER).upper()
        if order not in _DATE_ORDER_PARTS:
            order = DEFAULT_DATE_ORDER

        for fmt in _ISO_YEAR_FIRST_FORMATS + _CANDIDATE_FORMATS[order]:
            try:
                dt = datetime.datetime.strptime(date_str, fmt)
            except ValueError:
                continue
            return timezone.make_aware(dt)

        raise ValueError(f"Unrecognized date format: {date_str}")

    @staticmethod
    def _clean_amount(amount_str):
        """Normalise a raw amount string into a Decimal-parseable form.

        Strips currency symbols/codes and thousands whitespace (Polish
        banks use spaces or non-breaking spaces as thousands separators),
        then normalises the decimal separator to a dot. Handles both US
        (1,234.56) and European (1.234,56 or 1,59) conventions. A leading
        +/- sign is preserved.
        """
        import re

        s = amount_str.strip()
        for token in ("$", "€", "£", "zł", "PLN", "USD", "EUR", "GBP",
                      " ", "\xa0", " "):
            s = s.replace(token, "")

        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                # European: 1.234,56 -> 1234.56
                s = s.replace(".", "").replace(",", ".")
            else:
                # US: 1,234.56 -> 1234.56
                s = s.replace(",", "")
        elif "," in s:
            # Comma only: decimal separator when it precedes 1-2 trailing
            # digits (1,59 -> 1.59); otherwise a thousands separator.
            if re.search(r",\d{1,2}$", s):
                s = s.replace(",", ".")
            else:
                s = s.replace(",", "")

        return s

    def _convert_amount(self, amount_str, row, column_mapping, amount_config):
        """
        Convert amount string to signed decimal based on configuration.

        Returns:
            Decimal: Positive for income, negative for expense
        """
        from decimal import Decimal, InvalidOperation

        cleaned = self._clean_amount(amount_str)

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

    def _snapshot_existing_keys(self):
        """Record (date, amount, note) of everything already in the wallet.

        Taken once before the import loop. Rows created during THIS import are
        deliberately not added: a statement legitimately containing the same
        purchase several times on the same day must import every occurrence.
        Re-running the same file still skips them, because by then those rows
        are part of the snapshot.
        """
        self._existing_keys = set(
            Transaction.objects.filter(wallet=self.wallet).values_list(
                "date", "amount", "note"
            )
        )

    def _is_duplicate(self, date, amount, note):
        """
        Check whether this row already existed in the wallet before the import.

        Compared against the pre-import snapshot only — see
        _snapshot_existing_keys.
        """
        if self._existing_keys is None:
            self._snapshot_existing_keys()

        return (date, Decimal(str(amount)), note) in self._existing_keys

    def _existing_categories(self):
        """Cache the user's real categories.

        Returns (by_name, by_id) where by_name maps lowercased name -> instance
        and by_id maps str(id) -> instance. Only visible, non-archived
        categories are considered (mirrors the dropdown the user sees).
        """
        if not hasattr(self, "_cat_by_name"):
            cats = list(
                TransactionCategory.objects.filter(
                    user=self.user, is_archived=False, is_visible=True
                )
            )
            self._cat_by_name = {c.name.lower(): c for c in cats}
            self._cat_by_id = {str(c.id): c for c in cats}
        return self._cat_by_name, self._cat_by_id

    @staticmethod
    def _norm(signature):
        """Normalize a signature into a stable dedup key."""
        return re.sub(r"\s+", " ", signature).strip().lower()

    def _upsert_rules(self, rules):
        """Persist newly-taught {keyword, category_id} rules (idempotent)."""
        _, by_id = self._existing_categories()
        for rule in rules:
            keyword = (rule.get("keyword") or "").strip().lower()
            category = by_id.get(rule.get("category_id"))
            if not keyword or category is None:
                continue
            ImportCategoryRule.objects.update_or_create(
                user=self.user, keyword=keyword, defaults={"category": category}
            )

    def _load_rules(self):
        """Load the user's rules as (keyword, category) sorted longest-first.

        Longest keyword first so the most specific rule wins on overlap.
        """
        self._rules = [
            (r.keyword, r.category)
            for r in ImportCategoryRule.objects.filter(user=self.user).select_related("category")
        ]
        self._rules.sort(key=lambda kc: len(kc[0]), reverse=True)

    def _match_rule(self, signature):
        """Return the category for the most specific rule whose keyword is in signature."""
        if not getattr(self, "_rules", None):
            return None
        haystack = signature.lower()
        for keyword, category in self._rules:
            if keyword in haystack:
                return category
        return None

    def build_signature(self, row, column_mapping):
        """Join all descriptive column values, excluding the mapped date & amount.

        Excluding date and amount is essential: they are high-cardinality, so
        including them would make almost every row unique and defeat dedup. The
        remaining columns (mapped or not) provide the "whole row" context.
        """
        skip = {column_mapping.get("date"), column_mapping.get("amount")}
        parts = []
        for col in self.columns:
            if col in skip:
                continue
            val = (row.get(col) or "").strip()
            if val:
                parts.append(val)
        return " | ".join(parts)

    def _needs_ai_category(self, row, column_mapping):
        """A row needs AI when it has no mapped category matching an existing one."""
        by_name, _ = self._existing_categories()
        col = column_mapping.get("category")
        if not col:
            return True
        val = row.get(col, "").strip()
        return not val or val.lower() not in by_name

    def collect_signatures(self, column_mapping, amount_config, filters=None):
        """Unique descriptions of rows needing AI, most frequent first, capped.

        Each item: {"key", "signature", "count"}. Used by the suggest endpoint
        to ask the LLM once per unique description rather than once per row.
        """
        if self.rows is None:
            self.columns, self.rows = self._parse_csv()

        groups = {}  # key -> {"key", "signature", "count"}
        for _, row in self.rows:
            if filters and not self._matches_filters(row, filters):
                continue
            if not self._needs_ai_category(row, column_mapping):
                continue
            signature = self.build_signature(row, column_mapping)
            if not signature:
                continue
            key = self._norm(signature)
            if key in groups:
                groups[key]["count"] += 1
            else:
                groups[key] = {"key": key, "signature": signature, "count": 1}

        ordered = sorted(groups.values(), key=lambda g: g["count"], reverse=True)
        return ordered[: settings.AI_IMPORT_MAX_UNIQUE]

    def _resolve_category(self, row, column_mapping):
        """Determine the category for a row, honoring legacy vs. AI-review mode."""
        col = column_mapping.get("category")
        mapped_val = row.get(col, "").strip() if col else ""

        if self.ai_categories is None:
            # Legacy flow: auto-create from the mapped column (unchanged behavior).
            return self._get_or_create_category(mapped_val) if mapped_val else None

        # AI review flow: never auto-create.
        by_name, by_id = self._existing_categories()
        if mapped_val and mapped_val.lower() in by_name:
            return by_name[mapped_val.lower()]          # keep matching mapped value
        signature = self.build_signature(row, column_mapping)
        cat_id = self.ai_categories.get(self._norm(signature))
        if cat_id:
            return by_id.get(cat_id)                     # one-off exact override wins
        return self._match_rule(signature)              # learned rule, else Uncategorized

    def _get_or_create_category(self, category_name):
        """
        Get existing category by name (case-insensitively) or create a new one.

        Categories are user-scoped (not wallet-scoped). Matching ignores case so
        a CSV saying "groceries" reuses the existing "Groceries" instead of
        creating a near-duplicate. Archived/hidden categories are matched too —
        they still occupy the (name, user) unique constraint.
        """
        key = category_name.lower()
        if key in self.category_cache:
            return self.category_cache[key]

        category = TransactionCategory.objects.filter(
            user=self.user, name__iexact=category_name
        ).first()

        if category is None:
            category = TransactionCategory.objects.create(
                user=self.user,
                name=category_name,
                icon="circle",
                color="#6B7280",
            )
            self.created_categories.add(category_name)

        self.category_cache[key] = category

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


class SavingsGoalService:
    """Calculate savings goals and progress."""

    @staticmethod
    def mark_missed_goals(wallet):
        """Mark goals as missed if target date has passed."""
        today = _date.today()
        missed_goals = wallet.savings_goals.filter(
            status="active", target_date__lt=today
        )
        missed_goals.update(status="missed")

    @staticmethod
    def get_months_until(target_date: _date) -> int:
        """Calculate months until target date. Min 1 month."""
        today = _date.today()
        days_until = (target_date - today).days
        if days_until < 0:
            return 0
        months = ceil(days_until / 30.44)
        return max(1, months)

    @staticmethod
    def get_monthly_needed(target_amount: Decimal, target_date: _date) -> Decimal:
        """Calculate monthly savings needed for a single goal."""
        months = SavingsGoalService.get_months_until(target_date)
        if months == 0:
            return Decimal("0")
        return (target_amount / months).quantize(Decimal("0.01"))

    @staticmethod
    def get_total_monthly_needed(goals: list) -> Decimal:
        """Sum monthly needed across all active goals."""
        total = Decimal("0")
        for goal in goals:
            total += SavingsGoalService.get_monthly_needed(
                goal.target_amount, goal.target_date
            )
        return total.quantize(Decimal("0.01"))

    @staticmethod
    def get_actual_savings(wallet, year: int, month: int) -> Decimal:
        """Calculate income - expenses for a given month."""
        transactions = wallet.transactions.filter(
            date__year=year, date__month=month
        )
        income = transactions.filter(amount__gt=0).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        expenses = transactions.filter(amount__lt=0).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        actual = income + expenses  # expenses are negative, so this is subtraction
        return actual.quantize(Decimal("0.01"))

    @staticmethod
    def get_monthly_summary(wallet: Wallet, year: int, month: int) -> dict:
        """Get complete monthly savings summary for a wallet.

        Note: Call mark_missed_goals() separately to update statuses.
        """
        active_goals = wallet.savings_goals.filter(status="active")
        total_monthly_needed = SavingsGoalService.get_total_monthly_needed(
            list(active_goals)
        )
        actual_savings = SavingsGoalService.get_actual_savings(wallet, year, month)
        difference = actual_savings - total_monthly_needed

        return {
            "month": month,
            "year": year,
            "total_monthly_needed": total_monthly_needed,
            "actual_savings": actual_savings,
            "difference": difference,
            "status": "on_track" if difference >= 0 else "short",
            "goals": list(active_goals),
        }
