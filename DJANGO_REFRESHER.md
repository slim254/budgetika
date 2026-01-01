# Django Backend Refresher - Quick Reference

A quick cheat sheet for Django concepts used in this project. For detailed explanations, see `CODEBASE_ANALYSIS.md`.

---

## Models vs Views vs Serializers

```
Database Table → Django Model → Serializer → JSON Response
JSON Request → Serializer → Django Model → Database Table
```

**Model** - Defines database schema
```python
class Wallet(models.Model):
    name = models.CharField(max_length=100)
    initial_value = models.DecimalField(max_digits=10, decimal_places=2)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
```

**Serializer** - Converts between Python objects and JSON
```python
class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ['id', 'name', 'initial_value', 'balance']
```

**View** - Handles HTTP requests
```python
class WalletList(generics.ListCreateAPIView):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
```

---

## Class-Based Views (CBV) - What Your Project Uses

### Quick Cheat Sheet

```python
from rest_framework import generics

# List + Create (GET all, POST new)
class WalletList(generics.ListCreateAPIView):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer

# Detail + Update + Delete (GET one, PUT/PATCH, DELETE)
class WalletDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
```

### Inheritance Hierarchy

```
ListCreateAPIView:
  ├── ListModelMixin (adds list() method for GET)
  ├── CreateModelMixin (adds create() method for POST)
  └── GenericAPIView (base with queryset/serializer support)

RetrieveUpdateDestroyAPIView:
  ├── RetrieveModelMixin (GET detail)
  ├── UpdateModelMixin (PUT/PATCH)
  ├── DestroyModelMixin (DELETE)
  └── GenericAPIView
```

### Common Methods to Override

| Method | Purpose | Example |
|--------|---------|---------|
| `get_queryset()` | Filter what objects are returned | Filter by user: `return Wallet.objects.filter(user=self.request.user)` |
| `perform_create()` | Hook called after validation, before save | Auto-set user: `serializer.save(user=self.request.user)` |
| `perform_update()` | Hook called after validation, before save | Custom logic on update |
| `perform_destroy()` | Hook called before delete | Cleanup operations |
| `get_object()` | Fetch single object for detail view | Add security checks |
| `get_serializer_context()` | Add data to serializer | Pass wallet to TransactionSerializer for validation |

---

## QuerySets - Database Queries

### Basic Operations

```python
# Single object
wallet = Wallet.objects.get(id=1)  # Raises error if not found
wallet = Wallet.objects.filter(id=1).first()  # Returns None if not found
wallet = get_object_or_404(Wallet, id=1)  # Returns 404 if not found

# Multiple objects
wallets = Wallet.objects.all()  # All wallets
wallets = Wallet.objects.filter(currency='usd')  # Filter

# Count/Check existence
count = Wallet.objects.count()
exists = Wallet.objects.filter(currency='usd').exists()
```

### Filtering Patterns

```python
# Simple filter
Transaction.objects.filter(wallet=wallet)

# Multiple conditions (AND)
Transaction.objects.filter(wallet=wallet, transaction_type='income')

# Date filtering
Transaction.objects.filter(date__year=2025, date__month=12)

# Lookups (__, double underscore)
Transaction.objects.filter(amount__gte=100)  # Greater than or equal
Transaction.objects.filter(amount__lt=500)   # Less than
Transaction.objects.filter(date__range=['2025-12-01', '2025-12-31'])

# Follow relationships
Transaction.objects.filter(wallet__user=request.user)
```

### Common Methods

```python
queryset = Transaction.objects.filter(wallet=wallet)

# Modify queryset
queryset = queryset.filter(date__year=2025)
queryset = queryset.order_by('-date')  # Newest first
queryset = queryset[:10]  # First 10

# Get single result
first = queryset.first()
last = queryset.last()

# Statistics
total = queryset.count()
sum_amount = queryset.aggregate(Sum('amount'))['amount__sum']

# Return data as dicts instead of objects
dicts = queryset.values('id', 'amount')

# Get unique values
unique_types = queryset.values('transaction_type').distinct()
```

### Aggregate Functions

```python
from django.db.models import Sum, Count, Avg, Max, Min

result = Transaction.objects.aggregate(
    total=Sum('amount'),
    count=Count('id'),
    average=Avg('amount'),
    max_amount=Max('amount'),
    min_amount=Min('amount')
)
# Returns: {'total': 1500.00, 'count': 5, 'average': 300.00, ...}
```

### Optimization - select_related vs prefetch_related

```python
# N+1 Problem - Multiple queries
for wallet in Wallet.objects.all():
    print(wallet.user.username)  # Runs a query for each wallet!

# Solution 1: select_related (for ForeignKey/OneToOne)
for wallet in Wallet.objects.select_related('user'):
    print(wallet.user.username)  # Already loaded

# Solution 2: prefetch_related (for reverse ForeignKey/ManyToMany)
for wallet in Wallet.objects.prefetch_related('transactions'):
    for tx in wallet.transactions.all():
        print(tx.amount)  # Already loaded
```

---

## Relationships in Models

### OneToOneField - One per user

```python
class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # Each user has exactly ONE wallet
```

**Access**:
```python
wallet = Wallet.objects.get(user=user)
# OR via reverse relation:
wallet = user.wallet  # If related_name='wallet'
```

### ForeignKey - Many-to-one

```python
class Transaction(models.Model):
    wallet = models.ForeignKey(Wallet, related_name='transactions')
    # One wallet can have MANY transactions
```

**Access**:
```python
# Forward: Transaction to Wallet
txs_wallet = transaction.wallet

# Reverse: Wallet to Transactions
all_txs = wallet.transactions.all()  # Uses related_name
```

### Delete Behavior

```python
# CASCADE - Delete children when parent deleted
wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)

# PROTECT - Prevent deletion if children exist
wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT)

# SET_NULL - Set to NULL when parent deleted
wallet = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True)
```

---

## Request-Response Flow in DRF

```
1. HTTP Request arrives
   ↓
2. Django routes to View (e.g., WalletList.as_view())
   ↓
3. View.dispatch() is called
   ↓
4. Authentication - verify JWT token (authentication_classes)
   ↓
5. Permission check - verify IsAuthenticated (permission_classes)
   ↓
6. Route to method handler
   - GET → list()
   - POST → create()
   - PUT/PATCH → update()
   - DELETE → destroy()
   ↓
7. Method calls:
   - get_queryset() - fetch data
   - get_serializer() - create serializer
   - perform_* hooks - custom logic
   ↓
8. Serializer validates data
   ↓
9. Save to database
   ↓
10. Return JSON response
```

---

## Permissions & Authentication

```python
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

class WalletList(generics.ListCreateAPIView):
    authentication_classes = [JWTAuthentication]  # How to verify user
    permission_classes = [IsAuthenticated]        # What users can do
```

**Common Permissions**:
```python
IsAuthenticated           # User must be logged in
IsAdminUser             # User must be staff/admin
AllowAny                # Anyone (no auth required)
IsAuthenticatedOrReadOnly  # Logged in users write, anyone can read
```

**Custom Permission**:
```python
class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Allow only if user owns the object
        return obj.user == request.user
```

---

## Common Patterns from Your Project

### Pattern 1: Filter by Authenticated User

```python
def get_queryset(self):
    return Wallet.objects.filter(user=self.request.user)
```

### Pattern 2: Auto-set User on Create

```python
def perform_create(self, serializer):
    serializer.save(user=self.request.user)
```

### Pattern 3: Get with Security Check

```python
def get_object(self):
    wallet_id = self.kwargs['wallet_id']
    return get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
    # Returns 404 if wallet doesn't exist OR doesn't belong to user
```

### Pattern 4: Add Context to Serializer

```python
def get_serializer_context(self):
    context = super().get_serializer_context()
    wallet = self.get_object()
    context['wallet'] = wallet  # Now available in serializer.context
    return context
```

### Pattern 5: Computed Field in Serializer

```python
class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    def get_balance(self, obj):
        # Called for each wallet being serialized
        return obj.initial_value + obj.get_income() - obj.get_expense()
```

---

## Serializer Validation

```python
class TransactionSerializer(serializers.ModelSerializer):
    def validate(self, data):
        # Called for full object validation
        wallet = self.context.get('wallet')
        currency = data.get('currency')

        if wallet.currency != currency:
            raise serializers.ValidationError("Currency mismatch")

        return data

    def validate_amount(self, value):
        # Called for single field validation
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive")
        return value
```

---

## Admin Interface

Models are automatically available in Django admin:

```python
# admin.py
from django.contrib import admin
from .models import Wallet, Transaction

admin.site.register(Wallet)
admin.site.register(Transaction)

# Access at: http://localhost:8000/admin/
```

**Customize admin**:
```python
class WalletAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'balance']
    list_filter = ['currency']
    search_fields = ['name', 'user__username']

admin.site.register(Wallet, WalletAdmin)
```

---

## Useful Django Commands

```bash
# Start development server
python manage.py runserver

# Create/run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Interactive shell
python manage.py shell
>>> from wallets.models import Wallet
>>> Wallet.objects.all()

# Create test data
python manage.py shell << EOF
from django.contrib.auth.models import User
from wallets.models import Wallet

user = User.objects.create_user('testuser', password='123')
wallet = Wallet.objects.create(name='Test', user=user, initial_value=1000, currency='usd')
EOF
```

---

## Common Errors & Fixes

### Error: `Wallet matching query does not exist`
```python
# This throws error if not found
wallet = Wallet.objects.get(id=999)  # ❌ DoesNotExist exception

# Better:
wallet = get_object_or_404(Wallet, id=999)  # ✅ Returns 404
```

### Error: `Cannot assign...Wallet instance expected`
```python
# Trying to assign wrong type
transaction.wallet = 1  # ❌ AssertionError (expected Wallet object)

# Correct:
transaction.wallet = wallet  # ✅ Pass object, not ID
```

### Error: `Transaction.category` must be set
```python
# Missing required field
Transaction.objects.create(amount=100, currency='usd')  # ❌ category is required

# Provide default in model or view:
transaction = Transaction.objects.create(
    amount=100,
    category=wallet.categories.first(),  # ✅
    ...
)
```

### N+1 Query Problem (slow)
```python
# One query per wallet
for wallet in Wallet.objects.all():
    print(wallet.user.username)  # ❌ Runs query for each wallet

# Solution:
for wallet in Wallet.objects.select_related('user'):
    print(wallet.user.username)  # ✅ Only 2 queries total
```

---

## Key Takeaways

1. **Models** = Database schema (what data looks like)
2. **Serializers** = JSON conversion (how data is communicated)
3. **Views** = Request handlers (what happens when user makes request)
4. **QuerySets** = Database queries (how to fetch data)
5. **CBVs** = Reusable class patterns (DRY principle)
6. **Permissions** = Access control (who can do what)

---

## Further Reading

- Django ORM: https://docs.djangoproject.com/en/stable/topics/db/models/
- QuerySets: https://docs.djangoproject.com/en/stable/topics/db/queries/
- Class-Based Views: https://docs.djangoproject.com/en/stable/topics/class-based-views/
- Django REST Framework: https://www.django-rest-framework.org/
- JWT Authentication: https://django-rest-framework-simplejwt.readthedocs.io/
