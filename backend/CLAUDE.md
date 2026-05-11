# Backend

Django 5.1 + Django REST Framework. Python 3.13. SQLite (dev only).

## Structure

```
backend/
├── config/         Django project config (settings, root urls)
└── wallets/        Single app — all models, views, serializers, etc.
    ├── models.py
    ├── serializers.py
    ├── views.py
    ├── urls.py
    ├── services.py     CSV import business logic
    ├── signals.py      Post-save hook: copy default categories to new users
    ├── constants.py    Default category definitions
    └── migrations/
```

## Running

```bash
source venv/bin/activate
python manage.py runserver
```

## Key Packages

| Package | Version | Purpose |
|---|---|---|
| Django | 5.1.5 | Framework |
| djangorestframework | — | REST API |
| djangorestframework-simplejwt | — | JWT auth |
| django-cors-headers | — | CORS (currently allow-all in dev) |

Install: `pip install -r requirements.txt` (venv must be active).

After model changes: `python manage.py makemigrations && python manage.py migrate`

## Auth

JWT via simplejwt. `IsAuthenticated` + `JWTAuthentication` on every view. No session auth.

Token endpoints:
- `POST /api/token/` — obtain (login)
- `POST /api/token/refresh/` — refresh
- `POST /api/register/` — register (in `config/views.py`)

## View Pattern

All views use DRF generic class-based views. No ViewSets — explicit URL patterns are preferred for clarity.

Every view **must** filter querysets by `request.user` to prevent cross-user data access. Pattern:

```python
def get_queryset(self):
    return SomeModel.objects.filter(user=self.request.user)
```

`perform_create()` always sets `user=self.request.user` — never trust the client to send the user.

## Serializer Pattern

`TransactionSerializer` uses split read/write fields for relations:
- Read: `category` (nested `CategorySerializer`), `tags` (nested array)
- Write: `category_id` (UUID), `tag_ids` (list of UUIDs)

`validate_<field>()` ensures category/tag IDs belong to the requesting user.

`validate()` (object-level) enforces transaction currency matches wallet currency.

## Service Layer

Business logic that doesn't belong in views goes in `services.py`. Currently: `GenericCSVImportService` for CSV import.

Services are plain Python classes — no DRF dependencies — so they can be called from management commands, tests, or Celery tasks.

## Signals

`wallets/signals.py` listens to `User` post-save. On user creation, copies all default categories from `constants.py` into `TransactionCategory` rows owned by the new user.

## Models

- All PKs are `UUIDField(primary_key=True, default=uuid.uuid4)`
- `TransactionCategory` and `UserTransactionTag` use `unique_together = [['name', 'user']]`
- `TransactionCategory` soft-deletes via `is_archived = True`; `UserTransactionTag` hard-deletes
- `Wallet.balance` is **not** a model field — it is computed in `WalletSerializer.get_balance()`

## Admin

Standard Django admin registered in `wallets/admin.py`. Access at `/admin` with superuser.

Create superuser: `python manage.py createsuperuser`
