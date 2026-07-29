"""Export the whole database as human-readable, per-entity CSV files.

Usage:
    python manage.py export_all

Writes one CSV per entity into a timestamped directory under
~/.budgeting-app/exports/export-YYYYMMDD-HHMMSS/: wallets, transactions,
categories, tags, savings_goals, recurring_transactions, budget_rules,
import_rules. This is a full, all-users export (the app is single-user in
practice, but nothing here filters by user) intended as a human-readable
companion to backup_db's binary snapshot — e.g. to open in a spreadsheet.
"""
import csv
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand

from wallets.models import (
    BudgetRule,
    ImportCategoryRule,
    RecurringTransaction,
    SavingsGoal,
    Transaction,
    TransactionCategory,
    UserTransactionTag,
    Wallet,
)
from wallets.views import _csv_safe

EXPORT_ROOT = Path.home() / ".budgeting-app" / "exports"


class Command(BaseCommand):
    help = "Export all wallets/transactions/categories/etc. to timestamped CSV files."

    def handle(self, *args, **options):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        export_dir = EXPORT_ROOT / f"export-{timestamp}"
        export_dir.mkdir(parents=True, exist_ok=True)

        exporters = [
            ("wallets.csv", self._export_wallets),
            ("transactions.csv", self._export_transactions),
            ("categories.csv", self._export_categories),
            ("tags.csv", self._export_tags),
            ("savings_goals.csv", self._export_savings_goals),
            ("recurring_transactions.csv", self._export_recurring_transactions),
            ("budget_rules.csv", self._export_budget_rules),
            ("import_rules.csv", self._export_import_rules),
        ]

        for filename, exporter in exporters:
            count = exporter(export_dir / filename)
            self.stdout.write(f"{filename}: {count} row(s)")

        self.stdout.write(self.style.SUCCESS(f"Exported to {export_dir}"))

    # -- per-entity exporters -------------------------------------------------

    def _export_wallets(self, path):
        header = [
            "id", "name", "user", "initial_value", "currency",
            "is_archived", "created_at", "updated_at",
        ]
        rows = (
            [
                w.id, _csv_safe(w.name), w.user.username, w.initial_value, w.currency,
                w.is_archived, w.created_at.isoformat(), w.updated_at.isoformat(),
            ]
            for w in Wallet.objects.select_related("user").order_by("user__username", "name")
        )
        return self._write_csv(path, header, rows)

    def _export_transactions(self, path):
        header = [
            "id", "wallet", "date", "note", "amount", "currency",
            "category", "tags", "created_by", "created_at", "updated_at",
        ]
        qs = (
            Transaction.objects.select_related("wallet", "category", "created_by")
            .prefetch_related("tags")
            .order_by("wallet__name", "date")
        )
        rows = (
            [
                t.id,
                _csv_safe(t.wallet.name),
                t.date.isoformat(),
                _csv_safe(t.note),
                t.amount,
                t.currency,
                _csv_safe(t.category.name if t.category else ""),
                _csv_safe(";".join(tag.name for tag in t.tags.all())),
                t.created_by.username,
                t.created_at.isoformat(),
                t.updated_at.isoformat(),
            ]
            for t in qs
        )
        return self._write_csv(path, header, rows)

    def _export_categories(self, path):
        header = [
            "id", "name", "user", "icon", "color",
            "is_archived", "is_visible", "created_at", "updated_at",
        ]
        rows = (
            [
                c.id, _csv_safe(c.name), c.user.username, c.icon, c.color,
                c.is_archived, c.is_visible, c.created_at.isoformat(), c.updated_at.isoformat(),
            ]
            for c in TransactionCategory.objects.select_related("user").order_by("user__username", "name")
        )
        return self._write_csv(path, header, rows)

    def _export_tags(self, path):
        header = ["id", "name", "user", "icon", "color", "is_visible", "created_at", "updated_at"]
        rows = (
            [
                t.id, _csv_safe(t.name), t.user.username, t.icon, t.color,
                t.is_visible, t.created_at.isoformat(), t.updated_at.isoformat(),
            ]
            for t in UserTransactionTag.objects.select_related("user").order_by("user__username", "name")
        )
        return self._write_csv(path, header, rows)

    def _export_savings_goals(self, path):
        header = ["id", "wallet", "name", "target_amount", "target_date", "status", "created_at", "updated_at"]
        rows = (
            [
                g.id, _csv_safe(g.wallet.name), _csv_safe(g.name), g.target_amount,
                g.target_date.isoformat(), g.status, g.created_at.isoformat(), g.updated_at.isoformat(),
            ]
            for g in SavingsGoal.objects.select_related("wallet").order_by("wallet__name", "target_date")
        )
        return self._write_csv(path, header, rows)

    def _export_recurring_transactions(self, path):
        header = [
            "id", "wallet", "created_by", "note", "amount", "currency", "category", "tags",
            "frequency", "start_date", "end_date", "day_of_week", "day_of_month",
            "is_active", "next_occurrence", "last_processed", "created_at", "updated_at",
        ]
        qs = (
            RecurringTransaction.objects.select_related("wallet", "created_by", "category")
            .prefetch_related("tags")
            .order_by("wallet__name", "note")
        )
        rows = (
            [
                r.id,
                _csv_safe(r.wallet.name),
                r.created_by.username,
                _csv_safe(r.note),
                r.amount,
                r.currency,
                _csv_safe(r.category.name if r.category else ""),
                _csv_safe(";".join(tag.name for tag in r.tags.all())),
                r.frequency,
                r.start_date.isoformat(),
                r.end_date.isoformat() if r.end_date else "",
                r.day_of_week if r.day_of_week is not None else "",
                r.day_of_month if r.day_of_month is not None else "",
                r.is_active,
                r.next_occurrence.isoformat() if r.next_occurrence else "",
                r.last_processed.isoformat() if r.last_processed else "",
                r.created_at.isoformat(),
                r.updated_at.isoformat(),
            ]
            for r in qs
        )
        return self._write_csv(path, header, rows)

    def _export_budget_rules(self, path):
        header = ["id", "wallet", "category", "amount", "start_date", "end_date"]
        qs = BudgetRule.objects.select_related("wallet", "category").order_by("wallet__name", "start_date")
        rows = (
            [
                b.id, _csv_safe(b.wallet.name), _csv_safe(b.category.name if b.category else ""),
                b.amount, b.start_date.isoformat(), b.end_date.isoformat() if b.end_date else "",
            ]
            for b in qs
        )
        return self._write_csv(path, header, rows)

    def _export_import_rules(self, path):
        header = ["id", "user", "keyword", "category", "created_at", "updated_at"]
        qs = ImportCategoryRule.objects.select_related("user", "category").order_by("user__username", "keyword")
        rows = (
            [
                i.id, i.user.username, _csv_safe(i.keyword), _csv_safe(i.category.name),
                i.created_at.isoformat(), i.updated_at.isoformat(),
            ]
            for i in qs
        )
        return self._write_csv(path, header, rows)

    # -- helpers ---------------------------------------------------------------

    def _write_csv(self, path, header, rows):
        count = 0
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for row in rows:
                writer.writerow(row)
                count += 1
        return count
