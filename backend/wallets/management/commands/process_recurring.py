from datetime import date, datetime
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.db.models import Q
from django.utils import timezone

from wallets.models import (
    RecurringTransaction,
    RecurringTransactionExecution,
    Transaction,
)


class Command(BaseCommand):
    help = "Process all due recurring transactions, including missed past occurrences (catch-up)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force-date", type=str, help="YYYY-MM-DD — pretend today is this date")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force_date = options.get("force_date")
        today = date.fromisoformat(force_date) if force_date else date.today()

        due = (
            RecurringTransaction.objects.filter(is_active=True, next_occurrence__lte=today)
            .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
            .select_related("wallet", "category", "created_by")
            .prefetch_related("tags")
        )

        created = skipped = errors = 0
        for recurring in due:
            try:
                while recurring.is_due(today=today):
                    scheduled = recurring.next_occurrence
                    if dry_run:
                        self.stdout.write(f"[DRY RUN] Would create: {recurring.note} on {scheduled}")
                        recurring.next_occurrence = recurring.calculate_next_occurrence(scheduled)
                        continue

                    with db_transaction.atomic():
                        if RecurringTransactionExecution.objects.filter(
                            recurring_transaction=recurring, scheduled_date=scheduled
                        ).exists():
                            recurring.next_occurrence = recurring.calculate_next_occurrence(scheduled)
                            recurring.save(update_fields=["next_occurrence"])
                            skipped += 1
                            continue

                        txn = Transaction.objects.create(
                            wallet=recurring.wallet,
                            created_by=recurring.created_by,
                            note=recurring.note,
                            amount=recurring.amount,
                            currency=recurring.currency,
                            category=recurring.category,
                            date=timezone.make_aware(
                                datetime.combine(scheduled, datetime.min.time())
                            ),
                        )
                        txn.tags.set(recurring.tags.all())

                        RecurringTransactionExecution.objects.create(
                            recurring_transaction=recurring,
                            transaction=txn,
                            scheduled_date=scheduled,
                        )

                        recurring.next_occurrence = recurring.calculate_next_occurrence(scheduled)
                        recurring.last_processed = timezone.now()
                        recurring.save(update_fields=["next_occurrence", "last_processed"])
                        created += 1
            except Exception as e:
                errors += 1
                self.stderr.write(self.style.ERROR(f"Error on {recurring.note}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"Created: {created}  Skipped: {skipped}  Errors: {errors}"))
