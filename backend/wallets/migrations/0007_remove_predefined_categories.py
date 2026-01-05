"""
Migration: Remove predefined categories pattern.

This migration transitions from shared predefined categories (user=NULL)
to user-owned categories that are copied on signup via Django signal.

Changes:
1. Delete all predefined categories (user=NULL) - they'll be recreated per-user
2. Remove is_predefined field from TransactionCategory
3. Make user field non-nullable (all categories must have an owner)
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def delete_predefined_categories(apps, schema_editor):
    """Delete all predefined categories (user=NULL)."""
    TransactionCategory = apps.get_model('wallets', 'TransactionCategory')
    count = TransactionCategory.objects.filter(user__isnull=True).count()
    TransactionCategory.objects.filter(user__isnull=True).delete()
    if count:
        print(f"\n  Deleted {count} predefined categories (user=NULL)")


def noop(apps, schema_editor):
    """Reverse migration is a no-op - can't recreate predefined categories."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('wallets', '0006_rename_usertransactioncategory_to_transactioncategory'),
    ]

    operations = [
        # Step 1: Delete predefined categories
        migrations.RunPython(delete_predefined_categories, noop),

        # Step 2: Remove is_predefined field
        migrations.RemoveField(
            model_name='transactioncategory',
            name='is_predefined',
        ),

        # Step 3: Make user field non-nullable
        migrations.AlterField(
            model_name='transactioncategory',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='transaction_categories',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
