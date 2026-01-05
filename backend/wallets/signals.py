"""
Django signals for the wallets app.

DRF EDUCATIONAL NOTE - Django Signals
=====================================
Signals allow decoupled applications to get notified when certain
actions occur elsewhere in the framework. Common signals:

- post_save: Sent after a model's save() method is called
- pre_save: Sent before a model's save() method is called
- post_delete: Sent after a model's delete() method is called
- m2m_changed: Sent when a ManyToManyField is changed

Why use signals here?
- User creation can happen in many places (admin, API, shell, createsuperuser)
- Signal ensures default categories are ALWAYS created, regardless of how user was created
- Keeps user creation logic decoupled from category creation logic

Alternative approaches:
- Override User.save() - Requires custom User model
- Call in registration view - Would miss admin/shell created users
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from .constants import DEFAULT_CATEGORIES


@receiver(post_save, sender=User)
def create_default_categories_for_user(sender, instance, created, **kwargs):
    """
    Create default transaction categories when a new user is created.

    This signal fires after any User.save() where created=True, including:
    - User.objects.create_user() / create_superuser()
    - Django admin user creation
    - Registration API endpoints
    - Management commands

    Args:
        sender: The User model class
        instance: The actual User instance that was saved
        created: Boolean - True if this is a new user, False if update
        **kwargs: Additional signal arguments (raw, using, update_fields)
    """
    if not created:
        return

    # Import here to avoid circular imports
    from .models import TransactionCategory

    for cat_data in DEFAULT_CATEGORIES:
        TransactionCategory.objects.create(
            user=instance,
            name=cat_data['name'],
            icon=cat_data['icon'],
            color=cat_data['color'],
        )
