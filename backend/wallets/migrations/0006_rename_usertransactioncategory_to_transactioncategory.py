from django.db import migrations


class Migration(migrations.Migration):
    """
    Rename UserTransactionCategory to TransactionCategory.

    With the introduction of predefined categories (user=None), the
    'User' prefix is misleading since not all categories belong to users.
    """

    dependencies = [
        ('wallets', '0005_add_category_tag_features'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='UserTransactionCategory',
            new_name='TransactionCategory',
        ),
    ]
