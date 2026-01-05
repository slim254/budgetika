"""
DRF EDUCATIONAL NOTE - Django Management Commands
=================================================
Management commands are custom scripts that can be run via:
    python manage.py <command_name>

They're perfect for:
- Database seeding (like this command)
- Data migrations that need complex logic
- Scheduled tasks (cron jobs)
- Administrative operations
- One-time data fixes

Structure requirements:
- Must be in: <app>/management/commands/<command_name>.py
- Must define a Command class extending BaseCommand
- Must implement handle() method

Usage:
    python manage.py seed_categories              # Seed categories for users without any
    python manage.py seed_categories --all        # Seed categories for ALL users
    python manage.py seed_categories --user bob   # Seed categories for specific user

NOTE: For new users, categories are automatically created via Django signal.
This command is primarily for:
- Development: Seeding test users
- Migration: Adding categories to existing users who don't have any
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from wallets.models import TransactionCategory
from wallets.constants import DEFAULT_CATEGORIES


class Command(BaseCommand):
    help = 'Seed default transaction categories for users'

    def add_arguments(self, parser):
        """
        DRF EDUCATIONAL NOTE - Command Arguments
        ========================================
        add_arguments() lets you define CLI flags and options.

        Types of arguments:
        - Positional: parser.add_argument('name')
        - Optional flags: parser.add_argument('--flag', action='store_true')
        - Optional with value: parser.add_argument('--count', type=int, default=1)

        Access in handle(): options['flag'], options['count']
        """
        parser.add_argument(
            '--all',
            action='store_true',
            help='Seed categories for ALL users (even those who already have categories)',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Seed categories for a specific username',
        )

    def handle(self, *args, **options):
        """
        DRF EDUCATIONAL NOTE - Idempotent Operations
        ============================================
        This command uses get_or_create() to be idempotent:
        - Running it multiple times produces the same result
        - Existing categories are not duplicated
        - Safe to run in migrations or deployment scripts

        Idempotency is crucial for:
        - CI/CD pipelines (may run multiple times)
        - Development (developers run it repeatedly)
        - Production deployments (should be safe to re-run)
        """
        # Determine which users to process
        if options['user']:
            try:
                users = [User.objects.get(username=options['user'])]
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"User '{options['user']}' not found")
                )
                return
        elif options['all']:
            users = User.objects.all()
        else:
            # Only users who have no categories
            users = User.objects.filter(transaction_categories__isnull=True).distinct()

        if not users:
            self.stdout.write(
                self.style.WARNING('No users need category seeding')
            )
            return

        total_created = 0

        for user in users:
            user_created = 0
            self.stdout.write(f"\nProcessing user: {user.username}")

            for cat_data in DEFAULT_CATEGORIES:
                # get_or_create prevents duplicates
                category, created = TransactionCategory.objects.get_or_create(
                    name=cat_data['name'],
                    user=user,
                    defaults={
                        'icon': cat_data['icon'],
                        'color': cat_data['color'],
                    }
                )

                if created:
                    user_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  Created: {cat_data["name"]}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'  Exists: {cat_data["name"]}')
                    )

            total_created += user_created
            self.stdout.write(f"  → Created {user_created} categories for {user.username}")

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Done! Created {total_created} categories for {len(users)} user(s)'
            )
        )
