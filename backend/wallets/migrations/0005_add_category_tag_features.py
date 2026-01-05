# Generated manually for category and tag features

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    """
    DRF EDUCATIONAL NOTE - Django Migrations
    ========================================
    Migrations are Django's way of propagating model changes to the database.

    Key concepts:
    - dependencies: List of migrations that must run before this one
    - operations: List of changes to apply to the database

    Common operations:
    - AddField: Add a new column to a table
    - AlterField: Modify an existing column
    - RemoveField: Remove a column
    - RunPython: Run custom Python code during migration

    This migration adds:
    1. is_predefined and is_visible to UserTransactionCategory
    2. icon, color, is_visible, created_at, updated_at to UserTransactionTag
    3. Makes UserTransactionCategory.user nullable (for predefined categories)
    """

    dependencies = [
        ('wallets', '0004_alter_usertransactiontag_options_alter_wallet_user'),
    ]

    operations = [
        # Make user nullable on UserTransactionCategory (for predefined categories)
        migrations.AlterField(
            model_name='usertransactioncategory',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.CASCADE,
                related_name='transaction_categories',
                to='auth.user',
            ),
        ),

        # Add is_predefined to UserTransactionCategory
        migrations.AddField(
            model_name='usertransactioncategory',
            name='is_predefined',
            field=models.BooleanField(
                default=False,
                help_text='Predefined categories are templates available to all users',
            ),
        ),

        # Add is_visible to UserTransactionCategory
        migrations.AddField(
            model_name='usertransactioncategory',
            name='is_visible',
            field=models.BooleanField(
                default=True,
                help_text="Hidden categories won't appear in dropdowns but remain on transactions",
            ),
        ),

        # Add icon to UserTransactionTag
        migrations.AddField(
            model_name='usertransactiontag',
            name='icon',
            field=models.CharField(blank=True, max_length=50),
        ),

        # Add color to UserTransactionTag
        migrations.AddField(
            model_name='usertransactiontag',
            name='color',
            field=models.CharField(default='#3B82F6', max_length=7),
        ),

        # Add is_visible to UserTransactionTag
        migrations.AddField(
            model_name='usertransactiontag',
            name='is_visible',
            field=models.BooleanField(
                default=True,
                help_text="Hidden tags won't appear in dropdowns but remain on transactions",
            ),
        ),

        # Add created_at to UserTransactionTag (with default for existing rows)
        migrations.AddField(
            model_name='usertransactiontag',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),

        # Add updated_at to UserTransactionTag
        migrations.AddField(
            model_name='usertransactiontag',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
