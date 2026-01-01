# Budgeting App - Codebase Analysis & Learning Guide

**Last Updated**: December 2025
**Stack**: Django REST Framework + Next.js + TypeScript + Tailwind CSS
**Purpose**: Full-stack budgeting application for tracking income and expenses

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Backend Deep Dive](#backend-deep-dive)
   - Django Models
   - Django REST Framework
   - **Class-Based Views vs Function-Based Views** ⭐ NEW
   - **Django ORM & QuerySets** ⭐ NEW
4. [Frontend Deep Dive](#frontend-deep-dive)
5. [Authentication Flow](#authentication-flow)
6. [Database Schema](#database-schema)
7. [API Endpoints](#api-endpoints)
8. [Known Issues & TODOs](#known-issues--todos)
9. [Learning Resources](#learning-resources)

---

## Project Overview

### What This App Does
The Budgeting App is a personal finance tracker that allows users to:
- Create and manage a wallet/budget account
- Track income and expense transactions
- Categorize transactions for better organization
- View monthly summaries (income, expenses, balance)
- Filter transactions by month and year

### Key Technologies

| Layer | Technology | Version |
|-------|-----------|---------|
| **Backend API** | Django REST Framework | 3.14.0 |
| **Authentication** | JWT (simple-jwt) | 5.3.2 |
| **Frontend Framework** | Next.js | 15.1.6 |
| **UI Library** | React | 19 |
| **Language (Frontend)** | TypeScript | 5 |
| **Styling** | Tailwind CSS | 3.4.1 |
| **UI Components** | shadcn/ui (Radix UI) | - |
| **HTTP Client** | Axios | 1.7.7 |
| **Database** | SQLite | (development) |

---

## Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser / Client                         │
├─────────────────────────────────────────────────────────────┤
│  Next.js Frontend                                           │
│  - React Components with TypeScript                         │
│  - Context API for state (AuthProvider)                     │
│  - Axios HTTP client with JWT interceptors                  │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTP/JSON
        ┌────────────▼────────────┐
        │   HTTP/HTTPS Layer      │
        │   (REST API Calls)      │
        └────────────┬────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Django REST Framework Backend                  │
├─────────────────────────────────────────────────────────────┤
│  API Views (generics.RetrieveUpdateDestroyAPIView, etc.)   │
│  - Authentication: JWT Token Validation                     │
│  - Authorization: IsAuthenticated permission class          │
│  - Serializers: JSON ↔ Python object conversion             │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────▼────────────┐
        │   Django ORM            │
        │   (Object-Relational    │
        │    Mapping)             │
        └────────────┬────────────┘
                     │
        ┌────────────▼────────────┐
        │   SQLite Database       │
        │   (Development only)    │
        └────────────────────────┘
```

### Design Pattern: REST API

The app follows RESTful API design principles:
- **Resource-based URLs** (`/wallets/`, `/wallets/{id}/transactions/`)
- **HTTP Methods** (GET=read, POST=create, PUT/PATCH=update, DELETE=delete)
- **Standard Status Codes** (200=OK, 201=created, 400=bad request, 401=unauthorized, 404=not found)
- **JSON Data Format** for request/response bodies

### Authentication Model

The app uses **JWT (JSON Web Token)** authentication:

1. **Login**: User sends username/password → Backend returns access token + refresh token
2. **Authenticated Requests**: Client sends access token in Authorization header
3. **Token Refresh**: When access token expires, client uses refresh token to get new access token
4. **Logout**: Client deletes tokens from localStorage (server-side no action needed)

---

## Backend Deep Dive

### Project Structure

```
backend/
├── config/                    # Django project settings
│   ├── settings.py           # All Django configuration
│   ├── urls.py               # Root URL routing
│   ├── views.py              # Custom JWT token view
│   ├── serializers.py        # Custom JWT serializer
│   ├── asgi.py
│   └── wsgi.py
├── wallets/                  # Main app (handles budgets)
│   ├── models.py             # Database models (Wallet, Transaction, WalletCategory)
│   ├── views.py              # API views (CRUD endpoints)
│   ├── serializers.py        # Request/response data transformation
│   ├── admin.py              # Django admin registration
│   ├── urls.py               # Wallet app URLs
│   └── apps.py
├── db.sqlite3                # SQLite database file
└── manage.py                 # Django management script
```

### Django Models: The Data Layer

#### 1. **Wallet Model** - User's Budget Account

```python
class Wallet(models.Model):
    name = models.CharField(max_length=100)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    initial_value = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=['usd', 'eur', 'gbp', 'pln'])
```

**Key Concepts**:
- **OneToOneField**: Each Django User has exactly ONE wallet
  - Why? This design assumes one wallet per user
  - To support multiple wallets per user, change to `ForeignKey`
- **DecimalField**: Stores precise monetary values (not float!)
  - `max_digits=10`: Total digits allowed (e.g., 12345678.90)
  - `decimal_places=2`: Digits after decimal point
- **Currency choices**: Restricts to specific currencies
- **on_delete=CASCADE**: If user is deleted, wallet is deleted too

**Real-World Example**:
```
User: john_doe
  └─ Wallet: "Monthly Budget"
       ├─ initial_value: 3000.00
       ├─ currency: "usd"
       └─ [transactions...]
```

#### 2. **WalletCategory Model** - Transaction Categories

```python
class WalletCategory(models.Model):
    name = models.CharField(max_length=100)
    wallet = models.ForeignKey(Wallet, related_name='categories')
    created_by = models.ForeignKey(User, related_name='created_categories')
    type = models.CharField(choices=['income', 'expense', 'both'])
```

**Key Concepts**:
- **ForeignKey**: Many categories per wallet (creates relationship)
- **related_name='categories'**: Allows `wallet.categories.all()` access
- **created_by**: Audit trail - who created this category
- **type field**: Controls whether category is for income, expenses, or both
  - Example: "Groceries" could only be expense, but "Transfers" could be both

**Real-World Example**:
```
Wallet: "Monthly Budget"
  ├─ Category: "Salary" (type: income)
  ├─ Category: "Groceries" (type: expense)
  ├─ Category: "Rent" (type: expense)
  └─ Category: "Transfers" (type: both)
```

#### 3. **Transaction Model** - Individual Money Flows

```python
class Transaction(models.Model):
    note = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(choices=['income', 'expense'])
    currency = models.CharField(choices=['usd', 'eur', 'gbp', 'pln'])
    date = models.DateTimeField(auto_now_add=True)  # Auto-set on creation
    wallet = models.ForeignKey(Wallet, related_name='transactions')
    created_by = models.ForeignKey(User, related_name='created_transactions')
    category = models.ForeignKey(WalletCategory, default=1)
```

**Key Concepts**:
- **auto_now_add=True**: Automatically sets timestamp to current time on creation
  - Cannot be changed after creation
  - Allows filtering transactions by month/year
- **transaction_type**: "income" (money in) or "expense" (money out)
- **amount**: Always stored as positive value
  - Interpretation depends on transaction_type
- **default=1**: Currently hardcoded to category id=1
  - **BUG**: Will fail if no category with id=1 exists
  - Should be handled in serializer or view instead

**Real-World Example**:
```
Transaction:
  - note: "Weekly groceries at Whole Foods"
  - amount: 150.50
  - transaction_type: "expense"
  - currency: "usd"
  - date: 2025-12-05T10:30:00Z
  - wallet: 1
  - category: "Groceries"
```

### Django REST Framework: The API Layer

#### Serializers - Data Transformation

Serializers convert between Python objects and JSON:

```python
# Python Object (from database)
wallet = Wallet.objects.get(id=1)
print(wallet.name)  # "Monthly Budget"

# After serializer
serializer = WalletSerializer(wallet)
print(serializer.data)  # {"id": 1, "name": "Monthly Budget", ...}
print(json.dumps(serializer.data))  # JSON string sent to client
```

**WalletSerializer** - Special Feature: Calculated Field

```python
class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    def get_balance(self, obj):
        # Calculate: initial_value + income - expenses
        transactions = Transaction.objects.filter(wallet=obj)
        income = transactions.filter(transaction_type='income').aggregate(Sum('amount'))['amount__sum'] or 0
        expense = transactions.filter(transaction_type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
        return obj.initial_value + income - expense
```

**Key Concept - SerializerMethodField**:
- Computed/derived field not stored in database
- Calculated on-the-fly when serializing
- Perfect for balance, total, count fields
- Performance: Runs extra database query each time (consider caching for high traffic)

**Example Output**:
```json
{
  "id": 1,
  "name": "Monthly Budget",
  "initial_value": "3000.00",
  "currency": "usd",
  "balance": "3245.50",
  "categories": [
    {"id": 1, "name": "Salary", "type": "income"},
    {"id": 2, "name": "Groceries", "type": "expense"}
  ],
  "transactions": [...]
}
```

**TransactionSerializer** - Custom Validation

```python
def validate(self, data):
    wallet = self.context.get('wallet')
    currency = data.get('currency')
    if wallet and currency and wallet.currency != currency:
        raise serializers.ValidationError(
            f"Currency mismatch: {currency} != {wallet.currency}"
        )
    return data
```

This ensures all transactions in a wallet use the same currency, preventing calculation errors.

#### Views - API Endpoints

Views are the HTTP request handlers. Django REST Framework provides base classes:

```python
# Base classes used in this project:
generics.ListCreateAPIView      # GET (list) + POST (create)
generics.RetrieveUpdateDestroyAPIView  # GET (detail) + PUT/PATCH + DELETE
```

**WalletList View** - List all wallets

```python
class WalletList(generics.ListCreateAPIView):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
```

**SECURITY ISSUE** ⚠️:
- Does NOT filter wallets by authenticated user
- Users can see ALL wallets in system, not just their own
- Fix: Override `get_queryset()` to filter by user

**Correct Implementation**:
```python
def get_queryset(self):
    return Wallet.objects.filter(user=self.request.user)

def perform_create(self, serializer):
    serializer.save(user=self.request.user)  # Auto-set owner
```

**WalletTransactionList View** - List transactions in a wallet

```python
def get_queryset(self):
    wallet_id = self.kwargs['wallet_id']
    wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
    queryset = Transaction.objects.filter(wallet=wallet)

    # Filter by month and year from query parameters
    month = self.request.query_params.get('month') or datetime.now().month
    year = self.request.query_params.get('year') or datetime.now().year
    queryset = queryset.filter(date__month=month, date__year=year)
    return queryset
```

**Key Security Pattern**:
1. Get wallet ID from URL
2. Verify wallet belongs to authenticated user: `user=self.request.user`
3. If not found, return 404 (user can't discover other users' data)
4. Filter transactions by that wallet

### Django URL Routing

```python
# config/urls.py
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', CustomTokenObtainPairView.as_view()),
    path('api/token/refresh/', TokenRefreshView.as_view()),
    path('api/wallets/', include('wallets.urls')),
]

# wallets/urls.py
urlpatterns = [
    path('', WalletList.as_view()),
    path('<int:wallet_id>/', WalletDetail.as_view()),
    path('<int:wallet_id>/transactions/', WalletTransactionList.as_view()),
    path('<int:wallet_id>/transactions/<int:pk>/', WalletTransactionDetail.as_view()),
]
```

### Class-Based Views vs Function-Based Views

This is a critical Django concept that you likely forgot. Your project uses **Class-Based Views (CBVs)**, which are the modern Django approach. Let me explain both approaches and why CBVs are preferred.

#### Function-Based Views (FBV) - The Old Way

Function-based views are simple Python functions that receive an HTTP request and return a response.

**Example**:
```python
# Old approach (function-based)
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

@require_http_methods(["GET", "POST"])
@login_required
def wallet_list(request):
    if request.method == "GET":
        # List all wallets
        wallets = Wallet.objects.filter(user=request.user)
        serializer = WalletSerializer(wallets, many=True)
        return JsonResponse(serializer.data, safe=False)

    elif request.method == "POST":
        # Create wallet
        data = json.loads(request.body)
        serializer = WalletSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return JsonResponse(serializer.data, status=201)
        else:
            return JsonResponse(serializer.errors, status=400)

@require_http_methods(["GET", "PUT", "DELETE"])
@login_required
def wallet_detail(request, wallet_id):
    wallet = get_object_or_404(Wallet, id=wallet_id, user=request.user)

    if request.method == "GET":
        serializer = WalletSerializer(wallet)
        return JsonResponse(serializer.data)

    elif request.method == "PUT":
        data = json.loads(request.body)
        serializer = WalletSerializer(wallet, data=data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data)
        else:
            return JsonResponse(serializer.errors, status=400)

    elif request.method == "DELETE":
        wallet.delete()
        return JsonResponse({"status": "deleted"}, status=204)
```

**Problems with FBV**:
- ❌ Lots of boilerplate code (checking methods, handling errors)
- ❌ Hard to reuse logic (duplicated auth checks, serializer validation)
- ❌ Manual error handling
- ❌ Decorators are hard to test and stack

---

#### Class-Based Views (CBV) - The Modern Way (WHAT YOUR PROJECT USES)

Class-based views are Python classes that inherit from Django base classes. They provide HTTP method handlers (get, post, put, delete) as class methods.

**Same example, CBV style**:
```python
# Modern approach (class-based) - LIKE YOUR PROJECT
from rest_framework import generics

class WalletList(generics.ListCreateAPIView):
    """
    GET - List all wallets
    POST - Create new wallet
    """
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

class WalletDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    GET - Retrieve wallet details
    PUT/PATCH - Update wallet
    DELETE - Delete wallet
    """
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_object(self):
        wallet_id = self.kwargs['wallet_id']
        return get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
```

**Benefits of CBV**:
- ✅ Less code - inheritance handles common patterns
- ✅ Reusable - mix and match mixins
- ✅ Testable - class structure easier to mock/test
- ✅ Automatic error handling
- ✅ Built-in permissions and authentication

---

#### Understanding Class-Based View Inheritance Chain

Your project uses Django REST Framework's generic CBVs. Here's how they work:

```
APIView (base class)
    ├── GenericAPIView (adds queryset/serializer support)
    │   ├── ListModelMixin (adds list() method for GET)
    │   ├── CreateModelMixin (adds create() method for POST)
    │   ├── RetrieveModelMixin (adds retrieve() method for GET detail)
    │   ├── UpdateModelMixin (adds update() method for PUT/PATCH)
    │   └── DestroyModelMixin (adds destroy() method for DELETE)
    │
    └── Concrete Classes (combine mixins):
        ├── ListCreateAPIView = ListModelMixin + CreateModelMixin + GenericAPIView
        │   └── Handles: GET (list) + POST (create)
        │
        ├── RetrieveUpdateDestroyAPIView = RetrieveModelMixin + UpdateModelMixin + DestroyModelMixin + GenericAPIView
        │   └── Handles: GET (detail) + PUT/PATCH (update) + DELETE
        │
        ├── ListAPIView = ListModelMixin + GenericAPIView
        │   └── Handles: GET (list only)
        │
        └── ... many more combinations
```

**YOUR PROJECT'S USAGE**:

```python
# Combines two mixins - list and create
class WalletList(generics.ListCreateAPIView):
    # ListModelMixin provides: list() method
    # CreateModelMixin provides: create() method
    # GenericAPIView provides: queryset, serializer_class, permission_classes, etc.

    queryset = Wallet.objects.all()  # Used by list() and create()
    serializer_class = WalletSerializer

# Combines three mixins - retrieve, update, destroy
class WalletDetail(generics.RetrieveUpdateDestroyAPIView):
    # RetrieveModelMixin provides: retrieve() method (GET)
    # UpdateModelMixin provides: update() method (PUT/PATCH)
    # DestroyModelMixin provides: destroy() method (DELETE)

    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer

    # Override get_object to add custom filtering logic
    def get_object(self):
        wallet_id = self.kwargs['wallet_id']
        return get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
```

---

#### Key CBV Methods You Can Override

Each mixin provides a default implementation, but you can customize them:

```python
class WalletList(generics.ListCreateAPIView):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer

    # Override get_queryset() - customize the query
    def get_queryset(self):
        # Filter wallets by authenticated user
        return Wallet.objects.filter(user=self.request.user)

    # Override perform_create() - runs AFTER validation but BEFORE saving
    def perform_create(self, serializer):
        # Auto-set the user when creating wallet
        serializer.save(user=self.request.user)

    # Override list() - entire GET handler
    def list(self, request, *args, **kwargs):
        # Custom logic before getting list
        response = super().list(request, *args, **kwargs)
        # Custom logic after getting list
        return response


class WalletDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer

    # Override get_object() - fetch the single object
    def get_object(self):
        wallet_id = self.kwargs['wallet_id']
        return get_object_or_404(Wallet, id=wallet_id, user=self.request.user)

    # Override perform_update() - runs after validation but before saving
    def perform_update(self, serializer):
        # Custom logic during update
        serializer.save()

    # Override perform_destroy() - runs before deleting
    def perform_destroy(self, instance):
        # Custom cleanup logic
        instance.delete()
```

---

#### Your Project's View Pattern Explained

Looking at your `WalletTransactionList` view:

```python
class WalletTransactionList(generics.ListCreateAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        # Called by ListModelMixin.list() to get transactions to display
        wallet_id = self.kwargs['wallet_id']  # From URL: /wallets/<wallet_id>/transactions/
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        queryset = Transaction.objects.filter(wallet=wallet)

        # Add month/year filtering
        month = self.request.query_params.get('month') or datetime.now().month
        year = self.request.query_params.get('year') or datetime.now().year
        queryset = queryset.filter(date__month=month, date__year=year)
        return queryset

    def perform_create(self, serializer):
        # Called by CreateModelMixin.create() after validation
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        # Auto-set wallet and user when creating
        serializer.save(wallet=wallet, created_by=self.request.user)

    def get_serializer_context(self):
        # Called to add extra data to serializer
        # TransactionSerializer.validate() uses this context
        context = super().get_serializer_context()
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        context.update({"wallet": wallet})  # Passed to serializer.context
        return context
```

**What happens when a GET request comes in?**

```
GET /api/wallets/1/transactions/?month=12&year=2025
    ↓
1. Django routes to WalletTransactionList.as_view()
    ↓
2. ListCreateAPIView dispatches to list() method
    ↓
3. list() calls self.get_queryset() to get data
    ↓
4. Your get_queryset() returns filtered transactions
    ↓
5. list() calls self.get_serializer() to serialize data
    ↓
6. Your get_serializer_context() adds wallet to context
    ↓
7. TransactionSerializer validates currency using context
    ↓
8. list() returns JsonResponse with serialized data
```

---

#### CBV Pattern: Method Resolution Order (MRO)

When Django dispatches a request, it calls methods in this order:

```python
dispatch()  # Entry point
    ↓
authentication()  # Verify JWT token
    ↓
permission_check()  # Verify IsAuthenticated
    ↓
GET/POST/PUT/DELETE()  # Route based on HTTP method
    ↓
list()/create()/retrieve()/update()/destroy()  # Mixin methods
    ↓
get_queryset()  # Get data from DB
get_serializer()  # Create serializer instance
perform_create/update/destroy()  # Custom hooks
    ↓
Response returned
```

---

#### When to Override vs Create Custom Views

**Use Generic CBVs** (what your project does):
- Simple CRUD operations
- Standard REST patterns
- Quick development

**Create Custom CBVs**:
```python
from rest_framework.views import APIView

class CustomWalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, wallet_id):
        # Complete custom logic
        wallet = get_object_or_404(Wallet, id=wallet_id)
        # Do something unique
        return Response({"custom": "data"})
```

**Use FBVs** (rarely, only for simple endpoints):
```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def custom_endpoint(request):
    # Simple logic that doesn't fit patterns
    return Response({"status": "ok"})
```

---

#### Summary Table

| Aspect | FBV | CBV | DRF Generic CBV |
|--------|-----|-----|-----------------|
| Code Length | 📈 Long | 📊 Medium | 🟢 Short |
| Reusability | ❌ Low | ✅ High | ✅✅ Very High |
| Customization | 🟢 Easy | 📊 Medium | 📊 Medium |
| Testing | 📊 Medium | ✅ Easy | ✅ Easy |
| Learning Curve | 🟢 Easy | 📊 Medium | 📊 Medium |
| DRF Integration | ❌ Manual | ✅ Built-in | ✅✅ Automatic |
| Modern Django | ❌ Old | ✅ Current | ✅✅ Best Practice |

---

### Django ORM & QuerySets - Database Queries Made Easy

The Django ORM (Object-Relational Mapping) lets you query databases using Python instead of SQL. A QuerySet is a lazy collection of database records that you can filter and transform.

#### Basic QuerySet Operations

Your project uses these patterns extensively:

```python
# GET - Returns single object or None
wallet = Wallet.objects.get(id=1)
wallet = Wallet.objects.get(user=request.user)  # OneToOne, only one per user

# FILTER - Returns QuerySet of matching objects
transactions = Transaction.objects.filter(wallet=wallet)
transactions = Transaction.objects.filter(transaction_type='income')
transactions = Transaction.objects.filter(wallet=wallet, transaction_type='income')  # AND

# GET_OBJECT_OR_404 - Returns object or raises 404
wallet = get_object_or_404(Wallet, id=wallet_id, user=request.user)

# ALL - Returns all objects
all_transactions = Transaction.objects.all()

# AGGREGATE - Compute statistics
from django.db.models import Sum
income_sum = Transaction.objects.filter(wallet=wallet, transaction_type='income').aggregate(Sum('amount'))
# Returns: {'amount__sum': 1500.00}
income_sum_value = income_sum['amount__sum'] or 0  # Handle None (no transactions)
```

**Key Concept - QuerySets are Lazy**:
```python
# This does NOT hit the database yet:
queryset = Transaction.objects.filter(wallet=wallet)

# Database query happens when you iterate/evaluate:
for tx in queryset:  # Hits DB here
    print(tx.amount)

# Or convert to list:
list(queryset)  # Hits DB here

# Or check existence:
if queryset.exists():  # Hits DB here
    pass
```

#### Date/DateTime Filtering - Used in Your Project

Your project filters transactions by month and year:

```python
month = 12
year = 2025

queryset = Transaction.objects.filter(
    date__month=month,  # __ means "lookup"
    date__year=year
)
```

**Common DateTime Lookups**:
```python
# Exact match
Transaction.objects.filter(date='2025-12-05')

# Range
Transaction.objects.filter(date__gte='2025-12-01')  # Greater than or equal
Transaction.objects.filter(date__lte='2025-12-31')  # Less than or equal
Transaction.objects.filter(date__range=['2025-12-01', '2025-12-31'])

# Extract parts
Transaction.objects.filter(date__year=2025)
Transaction.objects.filter(date__month=12)
Transaction.objects.filter(date__day=5)

# Relations
Transaction.objects.filter(wallet__user=request.user)  # Follow ForeignKey
Transaction.objects.filter(wallet__currency='usd')
```

#### Filtering by User - Your Security Pattern

Your project uses this pattern to prevent data leaks:

```python
# Always filter by authenticated user
wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
queryset = Transaction.objects.filter(wallet=wallet)

# Equivalent to:
queryset = Transaction.objects.filter(wallet__user=request.user, wallet__id=wallet_id)
```

**Why this is secure**:
- User can only see transactions from their own wallet
- If user tries to access another user's wallet ID, get_object_or_404 returns 404
- User can't enumerate other users' data

#### Aggregation - Used in Balance Calculation

Your WalletSerializer calculates balance by aggregating transactions:

```python
def get_balance(self, wallet):
    transactions = Transaction.objects.filter(wallet=wallet)

    # Sum all income
    income = transactions.filter(
        transaction_type='income'
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    # Sum all expenses
    expense = transactions.filter(
        transaction_type='expense'
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    # Calculate balance
    balance = wallet.initial_value + income - expense
    return balance
```

**How aggregate works**:
```python
result = MyModel.objects.aggregate(Sum('amount'))
# Returns: {'amount__sum': 1500.00}

# Multiple aggregations:
result = MyModel.objects.aggregate(
    total=Sum('amount'),
    count=Count('id'),
    average=Avg('amount')
)
# Returns: {'total': 1500.00, 'count': 5, 'average': 300.00}
```

#### Query Optimization - Performance Matters

One issue with your WalletSerializer is that `get_balance()` runs a NEW database query every time:

```python
# SLOW - Runs query for each wallet serialized
class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    def get_balance(self, obj):
        # This query runs every time!
        transactions = Transaction.objects.filter(wallet=obj)
        income = transactions.filter(...).aggregate(Sum('amount'))
        ...
```

**Better approach using select_related/prefetch_related**:

```python
# In view:
wallets = Wallet.objects.prefetch_related('transactions').all()
serializer = WalletSerializer(wallets, many=True)

# prefetch_related does ONE extra query instead of N queries
# Query 1: SELECT * FROM wallets
# Query 2: SELECT * FROM transactions WHERE wallet_id IN (1,2,3,...)
```

Or use database-level aggregation:

```python
from django.db.models import DecimalField, Case, When, Sum, F

class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.DecimalField(max_digits=10, decimal_places=2)

    def get_balance(self, obj):
        # Calculate using database
        result = Transaction.objects.filter(wallet=obj).aggregate(
            total_income=Sum(Case(
                When(transaction_type='income', then=F('amount')),
                output_field=DecimalField()
            )),
            total_expense=Sum(Case(
                When(transaction_type='expense', then=F('amount')),
                output_field=DecimalField()
            ))
        )
        income = result['total_income'] or 0
        expense = result['total_expense'] or 0
        return obj.initial_value + income - expense
```

#### Queryset Chaining - Building Complex Queries

Querysets support method chaining:

```python
# Start with all transactions
queryset = Transaction.objects.all()

# Filter step by step
queryset = queryset.filter(wallet=wallet)
queryset = queryset.filter(date__year=2025)
queryset = queryset.filter(transaction_type='expense')

# Order by
queryset = queryset.order_by('-date')  # Newest first

# Limit results
queryset = queryset[:10]  # Get first 10

# Execute query
transactions = queryset  # Still lazy until you iterate

# This is exactly what your get_queryset does:
def get_queryset(self):
    queryset = Transaction.objects.filter(wallet=self.wallet)
    if month:
        queryset = queryset.filter(date__month=month)
    if year:
        queryset = queryset.filter(date__year=year)
    return queryset
```

#### Common QuerySet Methods

```python
# COUNT - Number of results
count = Transaction.objects.filter(wallet=wallet).count()

# EXISTS - Faster than count for checking if any exist
if Transaction.objects.filter(wallet=wallet).exists():
    pass

# FIRST/LAST - Get single object
first_tx = Transaction.objects.filter(wallet=wallet).first()
last_tx = Transaction.objects.filter(wallet=wallet).last()

# VALUES - Return dictionaries instead of objects
tx_dicts = Transaction.objects.values('id', 'amount', 'date')
# [{'id': 1, 'amount': '150.50', 'date': '2025-12-05'}, ...]

# DISTINCT - Remove duplicates
unique_wallets = Transaction.objects.values('wallet').distinct()

# ORDER_BY - Sort results
txs = Transaction.objects.order_by('-date')  # Newest first
txs = Transaction.objects.order_by('amount')  # Oldest first

# DELETE - Delete all matching
Transaction.objects.filter(wallet=wallet).delete()
```

#### Bulk Operations - For Performance

Instead of updating one-by-one:

```python
# SLOW - Runs N queries
for transaction in transactions:
    transaction.amount = 100
    transaction.save()

# FAST - Runs 1 query
Transaction.objects.bulk_update(transactions, ['amount'])

# SLOW - Runs N queries
for data in new_data:
    Transaction.objects.create(**data)

# FAST - Runs 1 query
Transaction.objects.bulk_create([
    Transaction(**data) for data in new_data
])
```

---

## Frontend Deep Dive

### Project Structure

```
frontend/
├── app/                      # Next.js App Router (file-based routing)
│   ├── layout.tsx           # Root layout (wraps all pages)
│   ├── page.tsx             # Home page (/)
│   ├── login/
│   │   └── page.tsx         # /login
│   ├── dashboard/
│   │   ├── page.tsx         # /dashboard
│   │   └── walletTest.tsx   # Wallets component
│   └── wallet/
│       └── [id]/
│           ├── page.tsx     # /wallet/:id (wallet detail)
│           └── transactions/
│               └── page.tsx # /wallet/:id/transactions
├── components/              # Reusable React components
│   ├── ui/                  # shadcn/ui components
│   ├── TransactionList.tsx
│   ├── StickyTransactionBar.tsx
│   ├── MonthSelector.tsx
│   └── ProtectedRoute.tsx
├── contexts/                # React Context (state management)
│   └── AuthProvider.tsx     # Authentication state
├── hooks/                   # Custom React hooks
│   └── useAxiosInterceptor.ts
├── api/                     # HTTP client setup
│   └── axiosInstance.ts
├── models/                  # TypeScript interfaces
│   └── wallets.ts
├── lib/                     # Utility functions
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── next.config.ts
```

### React Context API - AuthProvider

**What is Context?**
Context API is React's built-in solution for state management and avoiding "prop drilling". It provides a way to pass data through the component tree without passing props at every level.

**Three Components**:

1. **Context Object** - Holds the data
   ```typescript
   const AuthContext = createContext<AuthContextValue | null>(null);
   ```

2. **Provider Component** - Wraps your app and provides data
   ```typescript
   <AuthProvider>
     <App />  {/* All children can access context */}
   </AuthProvider>
   ```

3. **Hook** - Consumes context in components
   ```typescript
   const { session, login } = useAuthContext();
   ```

**AuthProvider Implementation**:

```typescript
export function AuthProvider(props: AuthProviderProps) {
    const [session, setSession] = useState<Session | null>(null);

    // Restore session on app load
    useEffect(() => {
        const maybeToken = localStorage.getItem("token");
        if (maybeToken) {
            setSession(sessionFactory(JSON.parse(maybeToken)));
        }
    }, []);

    // Login and refresh functions...

    return (
        <AuthContext.Provider value={{ session, login, refreshToken }}>
            {props.children}
        </AuthContext.Provider>
    );
}
```

**Session Data Structure**:
```typescript
interface Session {
    user: {
        id: number;        // User's Django ID
        username: string;  // User's username
    };
    token: {
        access: string;    // JWT access token (used for API calls)
        refresh: string;   // JWT refresh token (used to get new access token)
        exp: number;       // Token expiration timestamp (in seconds)
    };
}
```

### JWT Authentication Flow

```
┌──────────┐                                      ┌──────────┐
│  Client  │                                      │ Backend  │
└─────┬────┘                                      └────┬─────┘
      │                                                │
      │ 1. POST /api/token/ {username, password}      │
      ├───────────────────────────────────────────────>
      │                                                │
      │                                 2. Verify username/password
      │                                    Verify or create JWT
      │                                                │
      │ 3. {access, refresh}                          │
      │ <───────────────────────────────────────────────┤
      │                                                │
      │ 4. Save to localStorage & state               │
      │                                                │
      │ 5. GET /api/wallets/                          │
      │    Header: Authorization: Bearer {access}     │
      ├───────────────────────────────────────────────>
      │                                                │
      │                              6. Verify JWT signature
      │                                 Decode to get user_id
      │                                 Filter by that user
      │                                                │
      │ 7. [{wallet1}, {wallet2}...]                  │
      │ <───────────────────────────────────────────────┤
      │                                                │
```

**JWT Token Structure**:

A JWT is three Base64-encoded strings separated by dots:

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.
eyJ1c2VyX2lkIjogMSwgInVzZXJuYW1lIjogImpvaG4ifQ.
SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
```

Breaking it down:
- **Header**: `{"alg": "HS256", "typ": "JWT"}`
- **Payload**: `{"user_id": 1, "username": "john", "exp": 1234567890}`
- **Signature**: HMAC-SHA256(header.payload, SECRET_KEY)

The `exp` field is the expiration time (Unix timestamp in seconds).

To check if expired:
```javascript
const expiresInMs = token.exp * 1000;
const isExpired = expiresInMs < Date.now();
```

### Axios HTTP Client & Interceptors

**axiosInstance.ts**:
```typescript
const axiosInstance = axios.create({
    baseURL: 'http://localhost:8000/api/',
});
```

This sets the base URL for all requests, so you can call:
```typescript
axiosInstance.get('/wallets/')  // → GET http://localhost:8000/api/wallets/
```

**useAxiosInterceptor Hook**:

Interceptors intercept every request/response:

```typescript
// Request Interceptor - Add token before sending
axiosInstance.interceptors.request.use((config) => {
    const token = localStorage.getItem("token");
    if (token) {
        const { access } = JSON.parse(token);
        config.headers.Authorization = `Bearer ${access}`;
    }
    return config;
});

// Response Interceptor - Handle 401 (token expired)
axiosInstance.interceptors.response.use(
    response => response,  // Success - return as-is
    async (error) => {
        if (error.response?.status === 401) {
            // Access token expired, try to refresh
            await authContext.refreshToken();
            // Retry original request with new token
            return axiosInstance(error.config);
        }
        throw error;
    }
);
```

**Flow**:
1. User makes API call: `axiosInstance.get('/wallets/')`
2. Request interceptor adds Authorization header with access token
3. If request succeeds → return response
4. If request fails with 401 → refresh token and retry request

### TypeScript Interfaces

**models/wallets.ts** - Type definitions:

```typescript
interface User {
    id: number;
    username: string;
}

interface WalletCategory {
    id: number;
    name: string;
    wallet: number;  // Wallet ID (ForeignKey)
    created_by: number;
    type: 'income' | 'expense' | 'both';
    transactions: Transaction[];
}

interface Wallet {
    id: number;
    name: string;
    user: number;
    initial_value: string;  // Stored as string from JSON
    currency: 'usd' | 'eur' | 'gbp' | 'pln';
    categories: WalletCategory[];
    transactions: Transaction[];
    balance: string;  // Calculated field
}

interface Transaction {
    id: number;
    note: string;
    amount: string;
    transaction_type: 'income' | 'expense';
    currency: 'usd' | 'eur' | 'gbp' | 'pln';
    date: string;  // ISO 8601 format
    wallet: number;
    created_by: number;
    category: number;
}
```

**Why strings for numbers in JSON?**
- JSON doesn't have a number type with decimal precision
- Amounts are stored as strings to preserve exact decimal places
- Convert to number when doing calculations: `parseFloat(amount)`

### Next.js App Router & File-Based Routing

Next.js 13+ uses the "App Router" where file structure = URL routes:

```
app/
├── page.tsx           → / (home)
├── login/
│   └── page.tsx       → /login
├── dashboard/
│   └── page.tsx       → /dashboard
└── wallet/
    └── [id]/
        └── page.tsx   → /wallet/:id (dynamic route)
```

**Dynamic Routes**: `[id]` becomes a URL parameter accessible via:
```typescript
export default function WalletPage({
    params: { id }
}: {
    params: { id: string }
}) {
    // Access the wallet ID from URL
    console.log(id);  // "1" if user visits /wallet/1
}
```

### React Components

**ProtectedRoute Component** - Guards pages from unauthorized access:

```typescript
export default function ProtectedRoute({ children }) {
    const { session } = useAuthContext();
    const router = useRouter();

    if (!session) {
        // Not logged in, redirect to login page
        router.push(`/login?redirect=${pathname}`);
        return null;
    }

    return children;
}
```

Usage:
```typescript
export default function DashboardPage() {
    return (
        <ProtectedRoute>
            <Dashboard />
        </ProtectedRoute>
    );
}
```

**TransactionList Component** - Displays transactions in a table:

```typescript
export function TransactionList({ transactions }) {
    return (
        <div>
            {transactions.length === 0 && <p>No transactions</p>}

            {transactions.map(tx => (
                <div key={tx.id}>
                    <span>{tx.date}</span>
                    <span>{tx.note}</span>
                    <span style={{ color: tx.type === 'income' ? 'green' : 'red' }}>
                        {tx.amount}
                    </span>
                </div>
            ))}
        </div>
    );
}
```

**MonthSelector Component** - Navigate months:

```typescript
const [month, setMonth] = useState(new Date().getMonth() + 1);
const [year, setYear] = useState(new Date().getFullYear());

function handlePrevious() {
    if (month === 1) {
        setMonth(12);
        setYear(year - 1);
    } else {
        setMonth(month - 1);
    }
    // Update URL: ?month=MM&year=YYYY
    router.push(`?month=${month}&year=${year}`);
}
```

---

## Authentication Flow

### Complete Login Flow

```
User opens app
    ↓
App mounts, AuthProvider runs useEffect
    ↓
Check localStorage for "token"
    ↓
    ├─ Token found → Decode and restore session
    │
    └─ No token → session = null
    ↓
Page tries to render protected route
    ↓
    ├─ session exists → Render protected content
    │
    └─ session is null → Redirect to /login
    ↓
User enters username/password, clicks "Login"
    ↓
login() function runs:
    1. POST http://localhost:8000/api/token/
    2. Receive { access, refresh }
    3. Decode access token → extract user_id, username, exp
    4. Create Session object
    5. Save to localStorage
    6. Update state (setSession)
    ↓
Axios request interceptor now adds token to all requests:
    GET /wallets/
    Header: Authorization: Bearer {access_token}
    ↓
Backend verifies JWT signature (checks SECRET_KEY)
    ↓
    ├─ Valid → Decode token, get user_id → Filter by that user
    │
    └─ Invalid/Expired → Return 401 Unauthorized
    ↓
Response interceptor catches 401:
    1. Call refreshToken()
    2. POST /api/token/refresh/ with refresh token
    3. Receive new { access, refresh }
    4. Update localStorage and state
    5. Retry original request with new access token
    ↓
    ├─ Retry succeeds → Return data
    │
    └─ Refresh fails → Logout user, redirect to /login
```

---

## Database Schema

### Entity Relationship Diagram (ERD)

```
┌────────────────────┐
│   Django User      │
├────────────────────┤
│ id (PK)            │
│ username           │
│ password (hashed)  │
│ email              │
└─────────┬──────────┘
          │ 1:1
          │ (OneToOneField)
          ▼
┌────────────────────┐      1:N  ┌──────────────────┐
│     Wallet         │◄──────────┤ WalletCategory   │
├────────────────────┤           ├──────────────────┤
│ id (PK)            │           │ id (PK)          │
│ name               │           │ name             │
│ user_id (FK, U)    │           │ wallet_id (FK)   │
│ initial_value      │           │ created_by (FK)  │
│ currency           │           │ type             │
└─────────┬──────────┘           └────────┬─────────┘
          │ 1:N                           │ 1:N
          │ (ForeignKey)                  │
          ▼                               ▼
┌────────────────────┐          ┌──────────────────┐
│   Transaction      │          │  [Related via    │
├────────────────────┤          │  category field] │
│ id (PK)            │
│ note               │
│ amount             │
│ transaction_type   │
│ currency           │
│ date               │
│ wallet_id (FK)     │
│ created_by (FK)    │
│ category_id (FK)   │◄─────────┘
└────────────────────┘

Legend:
PK = Primary Key (unique identifier)
FK = Foreign Key (reference to another table)
U = Unique (only one per user)
1:1 = One-to-One relationship
1:N = One-to-Many relationship
```

### Key Database Concepts

**Primary Key (PK)**: Unique identifier for each row
- Every model in Django has an `id` field by default
- `Wallet.objects.get(id=1)` finds the wallet with id=1

**Foreign Key (FK)**: Reference to another table
- Creates relationships between tables
- `transaction.wallet_id` = which wallet this transaction belongs to
- Can query: `Transaction.objects.filter(wallet_id=1)` → get all transactions for wallet 1

**Unique Constraint**: Only one of its kind
- `user = models.OneToOneField(User)` means each user has exactly one wallet
- Trying to create a second wallet for same user would fail

**Cascade Delete**: What happens when referenced item is deleted
- `on_delete=models.CASCADE` means if a wallet is deleted, all its transactions are too
- `on_delete=models.PROTECT` would prevent deletion if child records exist

---

## API Endpoints

### Authentication Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/token/` | Login - get access + refresh tokens |
| POST | `/api/token/refresh/` | Refresh - get new access token |

**Login Example**:
```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "john_doe", "password": "password123"}'

# Response:
{
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "refresh": "eyJhbGciOiJIUzI1NiIs..."
}
```

### Wallet Endpoints

| Method | Endpoint | Purpose | Auth Required |
|--------|----------|---------|---|
| GET | `/api/wallets/` | List all user's wallets | ✓ |
| POST | `/api/wallets/` | Create new wallet | ✓ |
| GET | `/api/wallets/{id}/` | Get wallet details | ✓ |
| PUT/PATCH | `/api/wallets/{id}/` | Update wallet | ✓ |
| DELETE | `/api/wallets/{id}/` | Delete wallet | ✓ |

**Example Request**:
```bash
curl -X GET http://localhost:8000/api/wallets/ \
  -H "Authorization: Bearer {access_token}"

# Response:
[
  {
    "id": 1,
    "name": "Monthly Budget",
    "user": 1,
    "initial_value": "3000.00",
    "currency": "usd",
    "balance": "3245.50",
    "categories": [...],
    "transactions": [...]
  }
]
```

### Transaction Endpoints

| Method | Endpoint | Purpose | Auth Required |
|--------|----------|---------|---|
| GET | `/api/wallets/{wallet_id}/transactions/` | List transactions (with month/year filter) | ✓ |
| POST | `/api/wallets/{wallet_id}/transactions/` | Create transaction | ✓ |
| GET | `/api/wallets/{wallet_id}/transactions/{id}/` | Get transaction details | ✓ |
| PUT/PATCH | `/api/wallets/{wallet_id}/transactions/{id}/` | Update transaction | ✓ |
| DELETE | `/api/wallets/{wallet_id}/transactions/{id}/` | Delete transaction | ✓ |

**Example - Get December 2025 transactions**:
```bash
curl -X GET "http://localhost:8000/api/wallets/1/transactions/?month=12&year=2025" \
  -H "Authorization: Bearer {access_token}"

# Response:
[
  {
    "id": 1,
    "note": "Weekly groceries",
    "amount": "150.50",
    "transaction_type": "expense",
    "currency": "usd",
    "date": "2025-12-05T10:30:00Z",
    "category": 1
  }
]
```

**Example - Create transaction**:
```bash
curl -X POST http://localhost:8000/api/wallets/1/transactions/ \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "note": "Monthly salary",
    "amount": "5000.00",
    "transaction_type": "income",
    "currency": "usd",
    "category": 1
  }'
```

---

## Known Issues & TODOs

### 🔴 Security Issues (High Priority)

#### 1. WalletList Doesn't Filter by User
**Location**: `backend/wallets/views.py:170-197`

**Issue**: Users can see all wallets in the system
```python
# Current (WRONG):
class WalletList(generics.ListCreateAPIView):
    queryset = Wallet.objects.all()  # ❌ Returns ALL wallets
```

**Fix**:
```python
# Correct:
def get_queryset(self):
    return Wallet.objects.filter(user=self.request.user)

def perform_create(self, serializer):
    serializer.save(user=self.request.user)
```

**Impact**: Data leak - users can enumerate other users' wallets and guess IDs

---

#### 2. Tokens Stored in localStorage
**Location**: `frontend/contexts/AuthProvider.tsx:56`

**Issue**: localStorage is vulnerable to XSS (Cross-Site Scripting)
- Any script can access localStorage and steal tokens
- JavaScript error on the page → attacker can steal tokens

**Better Solution**: Use httpOnly cookies
- Cannot be accessed by JavaScript
- Automatically included in requests
- More secure (though requires CSRF protection)

**Quick Fix**: Add Content Security Policy headers to prevent XSS in first place

---

#### 3. Secrets Exposed in Source
**Location**: `backend/config/settings.py:23`

**Issue**: SECRET_KEY committed to Git
```python
SECRET_KEY = 'django-insecure-_6la#*i5&!89l-k21ls)eo$2)t(*60#y(5ea-yz4&bcv7dp_zd'
```

**Fix**: Use environment variables
```python
import os
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-key-only')
```

Then in `.env.local`:
```
DJANGO_SECRET_KEY=your-secret-key-here
```

---

### 🟡 Backend Issues (Medium Priority)

#### 1. Hardcoded Category Default
**Location**: `backend/wallets/models.py:105`

**Issue**: `category = models.ForeignKey(..., default=1)` assumes category id=1 exists
- Will fail if no category with id=1
- Better to handle in serializer or view

**Fix**:
```python
# Remove default from model
category = models.ForeignKey(WalletCategory, related_name='transactions', on_delete=models.CASCADE)

# In serializer:
def create(self, validated_data):
    if 'category' not in validated_data:
        wallet = self.context['wallet']
        # Get first category or create default
        category = wallet.categories.first()
        validated_data['category'] = category
    return super().create(validated_data)
```

#### 2. No Input Validation
- No max length enforced for `note` field (stores any string)
- No amount range validation (prevents negative/zero amounts)
- No date validation on client side

#### 3. No Filtering for WalletList Creation
The view allows creating wallets without setting the user:
```python
# Should auto-set the user:
def perform_create(self, serializer):
    serializer.save(user=self.request.user)
```

---

### 🟡 Frontend Issues (Medium Priority)

#### 1. Transaction Form Not Wired Up
**Location**: `frontend/components/StickyTransactionBar.tsx`

**Issue**: The add transaction button doesn't actually send data to backend
```typescript
const onAddTransaction = () => {
    // TODO: Implement - currently does nothing
}
```

**Fix**: Call axios to create transaction:
```typescript
async function onAddTransaction() {
    try {
        await axiosInstance.post(`/wallets/${walletId}/transactions/`, {
            note: description,
            amount: parseFloat(amount),
            transaction_type: type,
            currency: "usd"  // Get from wallet
        });
        // Refresh transaction list
    } catch (error) {
        console.error("Failed to create transaction", error);
    }
}
```

#### 2. Missing Logout Function
**Location**: `frontend/contexts/AuthProvider.tsx:28`

**Issue**: logout is commented out but referenced in useAxiosInterceptor

**Implement**:
```typescript
function logout() {
    localStorage.removeItem("token");
    setSession(null);
    // Redirect to login
}
```

#### 3. Token Refresh Not Awaited
**Location**: `frontend/contexts/AuthProvider.tsx:165`

**Issue**: `refreshToken()` is called but not awaited in axios interceptor
- Token might not be updated before retry
- Could cause infinite loop if refresh fails

#### 4. No Error Handling
- Login failures only log to console
- API errors not shown to user
- No loading states during async operations

#### 5. No TypeScript for API Responses
```typescript
const response = await fetch(...);
const token = await response.json();  // type is 'any'
```

Should be:
```typescript
interface TokenResponse {
    access: string;
    refresh: string;
}
const token = await response.json() as TokenResponse;
```

---

### 🟢 Nice-to-Have Improvements (Low Priority)

1. **Add transaction categories endpoint**: Allow users to CRUD categories
2. **Add budget limits**: Set income/expense targets per category
3. **Add recurring transactions**: Auto-create monthly transactions
4. **Add transaction editing**: Currently can only delete, not update
5. **Add search/filter**: Filter transactions by amount, date range, category
6. **Add data export**: Export transactions to CSV/PDF
7. **Add charts**: Visualize spending patterns
8. **Add notifications**: Alert when approaching budget limits
9. **Mobile responsive**: Current UI might not work well on mobile
10. **Dark mode**: Toggle between light/dark theme

---

## Learning Resources

### Django REST Framework Concepts to Study

1. **Serializers**
   - `ModelSerializer` - Auto-create serializer from model
   - `SerializerMethodField` - Custom computed fields
   - Custom validation methods

2. **Views/Viewsets**
   - Generic views (`ListCreateAPIView`, `RetrieveUpdateDestroyAPIView`)
   - Mixins (CreateModelMixin, ListModelMixin, etc.)
   - Custom get_queryset() for filtering

3. **Permissions**
   - `IsAuthenticated` - User must be logged in
   - `IsAdminUser` - Must be staff/admin
   - Custom permissions (require specific user to own object)

4. **Authentication**
   - JWT (JSON Web Token) - Stateless, token-based
   - Session-based - Server stores session data
   - OAuth2 - Third-party login (Google, GitHub, etc.)

5. **Queries & Optimization**
   - `filter()` - Get records matching condition
   - `select_related()` - Join related tables (avoid N+1 queries)
   - `prefetch_related()` - Batch fetch related objects
   - `aggregate()` - Sum, Count, Average operations

### React/Next.js Concepts to Study

1. **Context API**
   - Creating context with `createContext()`
   - Provider component wrapping tree
   - `useContext()` hook to consume

2. **Custom Hooks**
   - `useEffect()` - Side effects (API calls, subscriptions)
   - `useState()` - Component state
   - `useCallback()` - Memoize functions
   - `useMemo()` - Memoize expensive computations

3. **Next.js App Router**
   - File-based routing (folder structure = URL)
   - Dynamic routes with `[param]`
   - Nested layouts
   - Server vs Client components

4. **TypeScript**
   - Interfaces - Define object shapes
   - Generics - Reusable types with parameters
   - Union types - `type | type`
   - Optional fields - `field?: type`

5. **HTTP & API**
   - REST principles (CRUD with HTTP verbs)
   - JWT tokens and bearer authentication
   - Axios interceptors for middleware logic
   - Error handling and retries

### Quick Learning Path

1. **Week 1**: Django models and REST serializers
   - Create simple model
   - Write serializer
   - Test in Django shell: `python manage.py shell`

2. **Week 2**: Django views and authentication
   - Write API views
   - Add JWT authentication
   - Test with curl/Postman

3. **Week 3**: React hooks and state management
   - Study Context API
   - Build login form
   - Store/retrieve from localStorage

4. **Week 4**: Full integration
   - Connect frontend to backend API
   - Add error handling
   - Improve UI with Tailwind

5. **Week 5+**: Add features and polish
   - Fix security issues
   - Add transaction creation
   - Implement filtering/search

---

## Code Comments Reference

I've added extensive comments to the following files explaining the "why" behind each design decision:

1. **backend/wallets/models.py** - Data model structure
2. **backend/wallets/serializers.py** - Request/response transformation
3. **backend/wallets/views.py** - API endpoint logic (includes security issues!)
4. **frontend/contexts/AuthProvider.tsx** - Authentication flow and state management

Each comment explains:
- What the code does
- Why it's designed that way
- Common gotchas and best practices
- How to improve it

---

## Useful Commands

### Backend Management

```bash
# Start development server
python manage.py runserver

# Run database migrations
python manage.py migrate

# Create superuser (admin account)
python manage.py createsuperuser

# Access Django admin
# Browse to http://localhost:8000/admin/

# Interactive Python shell
python manage.py shell
>>> from wallets.models import Wallet
>>> wallet = Wallet.objects.get(id=1)
>>> wallet.balance
3245.50

# Create test data
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from wallets.models import Wallet, WalletCategory
>>> user = User.objects.create_user('testuser', 'test@example.com', 'password')
>>> wallet = Wallet.objects.create(name='Test Wallet', user=user, initial_value=1000, currency='usd')
>>> category = WalletCategory.objects.create(name='Groceries', wallet=wallet, created_by=user, type='expense')
```

### Frontend Management

```bash
# Start development server
npm run dev
# Visit http://localhost:3000

# Build for production
npm run build

# Run production build
npm run start

# Run tests
npm test

# Format code
npm run format
```

---

## Next Steps for Learning

1. **Fix the security issues** - Start with the WalletList filtering
2. **Implement transaction creation** - Wire up the form to the API
3. **Add error handling** - Show users when things go wrong
4. **Write tests** - Add test coverage to prevent regressions
5. **Deploy** - Put it online and fix production issues

---

## Official Documentation & Resources

### Django & Django REST Framework

#### Core Django
- **Django Official Docs**: https://docs.djangoproject.com/en/stable/
  - **Models**: https://docs.djangoproject.com/en/stable/topics/db/models/
  - **Queries/ORM**: https://docs.djangoproject.com/en/stable/topics/db/queries/ ⭐
  - **Class-Based Views**: https://docs.djangoproject.com/en/stable/topics/class-based-views/ ⭐
  - **Migrations**: https://docs.djangoproject.com/en/stable/topics/migrations/
  - **Permissions & Auth**: https://docs.djangoproject.com/en/stable/topics/auth/

#### Django REST Framework (DRF) ⭐ Most Useful
- **DRF Official Docs**: https://www.django-rest-framework.org/
  - **Serializers**: https://www.django-rest-framework.org/api-guide/serializers/ ⭐
  - **Viewsets & Routers**: https://www.django-rest-framework.org/api-guide/viewsets/ ⭐
  - **Generic Views**: https://www.django-rest-framework.org/api-guide/generic-views/ ⭐ (Your project uses these!)
  - **Permissions**: https://www.django-rest-framework.org/api-guide/permissions/
  - **Authentication**: https://www.django-rest-framework.org/api-guide/authentication/
  - **Pagination**: https://www.django-rest-framework.org/api-guide/pagination/
  - **Filtering & Searching**: https://www.django-rest-framework.org/api-guide/filtering/

#### JWT Authentication
- **Simple JWT Docs**: https://django-rest-framework-simplejwt.readthedocs.io/
  - **Getting Started**: https://django-rest-framework-simplejwt.readthedocs.io/en/latest/getting_started.html
  - **Token Customization**: https://django-rest-framework-simplejwt.readthedocs.io/en/latest/token_types.html
- **JWT.io - JWT Explanation**: https://jwt.io/ (Great for understanding JWT format)
- **RFC 7519 - JWT Standard**: https://tools.ietf.org/html/rfc7519 (Official spec)

#### Django CORS
- **Django CORS Headers**: https://github.com/adamchainz/django-cors-headers

---

### React & Next.js

#### React
- **React Official Docs**: https://react.dev ⭐
  - **Hooks**: https://react.dev/reference/react
  - **Context API**: https://react.dev/reference/react/useContext ⭐
  - **useState**: https://react.dev/reference/react/useState
  - **useEffect**: https://react.dev/reference/react/useEffect

#### Next.js
- **Next.js Official Docs**: https://nextjs.org/docs ⭐
  - **App Router**: https://nextjs.org/docs/app ⭐
  - **Dynamic Routes**: https://nextjs.org/docs/app/building-your-application/routing/dynamic-routes
  - **Layouts**: https://nextjs.org/docs/app/building-your-application/routing/pages-and-layouts
  - **API Routes**: https://nextjs.org/docs/app/building-your-application/routing/route-handlers

#### TypeScript with React
- **TypeScript Official Docs**: https://www.typescriptlang.org/docs/ ⭐
  - **Handbook**: https://www.typescriptlang.org/docs/handbook/
  - **Interfaces**: https://www.typescriptlang.org/docs/handbook/2/objects.html
  - **Generics**: https://www.typescriptlang.org/docs/handbook/2/generics.html

#### Tailwind CSS
- **Tailwind CSS Docs**: https://tailwindcss.com/docs ⭐
  - **Customization**: https://tailwindcss.com/docs/configuration
  - **Utility Classes**: https://tailwindcss.com/docs/utility-first

#### shadcn/ui
- **shadcn/ui Docs**: https://ui.shadcn.com/
  - **Installation**: https://ui.shadcn.com/docs/installation/next
  - **Components**: https://ui.shadcn.com/docs/components/button

---

### HTTP & API Tools

#### HTTP Client Libraries
- **Axios Docs**: https://axios-http.com/docs ⭐ (Your project uses this!)
  - **Request & Response Interceptors**: https://axios-http.com/docs/interceptors
  - **Creating Instance**: https://axios-http.com/docs/instance
- **Fetch API (Built-in)**: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API

#### API Testing Tools
- **Postman**: https://www.postman.com/ - Full-featured API testing GUI
- **Thunder Client** (VS Code): https://marketplace.visualstudio.com/items?itemName=rangav.vscode-thunder-client - Lightweight alternative
- **curl**: https://curl.se/ - Command-line HTTP client (built-in on Mac/Linux)
- **HTTPie**: https://httpie.io/ - Human-friendly curl alternative

#### REST API Best Practices
- **REST API Design Guidelines**: https://restfulapi.net/
- **HTTP Status Codes**: https://httpwg.org/specs/rfc7231.html#status.codes

---

### Database

#### SQLite (Your Current DB)
- **SQLite Official**: https://www.sqlite.org/docs.html
- **SQLite Browser**: https://sqlitebrowser.org/ - GUI tool to view/edit database

#### PostgreSQL (Recommended for Production)
- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **Installation**: https://www.postgresql.org/download/
- **Django PostgreSQL Backend**: https://docs.djangoproject.com/en/stable/ref/databases/#postgresql-notes

#### Database Design
- **Database Normalization**: https://en.wikipedia.org/wiki/Database_normalization
- **Entity-Relationship Model**: https://en.wikipedia.org/wiki/Entity%E2%80%93relationship_model

---

### Security

#### Authentication & Authorization
- **OWASP - Authentication**: https://owasp.org/www-community/attacks/Authentication_attack
- **OWASP - Authorization**: https://owasp.org/www-community/Access_control
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/ - Security vulnerabilities guide

#### JWT Security
- **Auth0 - JWT Security Best Practices**: https://auth0.com/blog/critical-vulnerabilities-in-json-web-token-libraries/
- **NIST - Authentication Guidelines**: https://pages.nist.gov/800-63-3/sp800-63b.html

#### CORS Security
- **MDN - CORS**: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS ⭐
- **OWASP - CORS Security**: https://owasp.org/www-community/attacks/CORS_Origin_Validation

---

### Deployment & DevOps

#### Backend Hosting
- **Heroku**: https://www.heroku.com/ - PaaS (easy, free tier deprecated)
- **Railway**: https://railway.app/ - Modern PaaS alternative
- **Render**: https://render.com/ - Another PaaS option
- **DigitalOcean**: https://www.digitalocean.com/ - VPS hosting
- **AWS (EC2/RDS)**: https://aws.amazon.com/ - Full cloud platform
- **Azure**: https://azure.microsoft.com/ - Microsoft cloud

#### Frontend Hosting
- **Vercel**: https://vercel.com/ ⭐ Best for Next.js
- **Netlify**: https://www.netlify.com/ - Alternative
- **GitHub Pages**: https://pages.github.com/ - Free but static only

#### Environment Variables
- **Python dotenv**: https://python-decouple.readthedocs.io/ (Used in Django)
- **Node dotenv**: https://github.com/motdotla/dotenv (Available for Node)

#### Docker (Containerization)
- **Docker Official Docs**: https://docs.docker.com/ ⭐
  - **Docker Compose**: https://docs.docker.com/compose/
- **Docker Hub**: https://hub.docker.com/ - Repository for images

---

### Testing

#### Backend Testing
- **Django Testing Docs**: https://docs.djangoproject.com/en/stable/topics/testing/
- **pytest**: https://docs.pytest.org/ - Better testing framework than unittest
- **Factory Boy**: https://factoryboy.readthedocs.io/ - Create test fixtures

#### Frontend Testing
- **Vitest**: https://vitest.dev/ - Fast unit test framework
- **Jest**: https://jestjs.io/ - Popular testing library
- **React Testing Library**: https://testing-library.com/docs/react-testing-library/intro/
- **Playwright**: https://playwright.dev/ - End-to-end testing

---

### Tools & Utilities

#### Code Quality
- **Black**: https://github.com/psf/black - Python code formatter
- **Flake8**: https://flake8.pycqa.org/ - Python linter
- **ESLint**: https://eslint.org/ - JavaScript linter
- **Prettier**: https://prettier.io/ - Code formatter for JS/TS

#### Version Control
- **Git Documentation**: https://git-scm.com/doc ⭐
- **GitHub**: https://github.com/ - Repository hosting
- **Git Branching Model**: https://nvie.com/posts/a-successful-git-branching-model/

#### Package Managers
- **pip** (Python): https://pip.pypa.io/ - Included with Python
- **npm** (Node): https://docs.npmjs.com/ - Package manager for JavaScript
- **yarn**: https://yarnpkg.com/ - Alternative to npm

---

### Learning Platforms

#### Video Courses
- **Udemy** - https://www.udemy.com/ - Affordable courses (often on sale)
- **Coursera** - https://www.coursera.org/ - University-level courses
- **YouTube** - https://www.youtube.com/ - Free tutorials
  - **Corey Schafer Django Tutorial**: https://www.youtube.com/c/Coreyms
  - **freeCodeCamp**: https://www.freecodecamp.org/

#### Interactive Learning
- **Real Python Tutorials**: https://realpython.com/ ⭐ Excellent Django content
- **MDN Web Docs**: https://developer.mozilla.org/ ⭐ Best JavaScript resource
- **CSS-Tricks**: https://css-tricks.com/ - Web development tips

---

### Quick Reference Cheat Sheets

#### Django ORM
- **Django ORM Cheat Sheet**: https://www.mercurial.dev/cheatsheets/django-orm
- **QuerySet API**: https://docs.djangoproject.com/en/stable/ref/models/querysets/

#### REST API Status Codes
- **HTTP Status Codes**: https://httpwg.org/specs/rfc7231.html#status.codes
- **Quick Reference**: https://http.cat/ (with cats!)

#### Markdown
- **Markdown Guide**: https://www.markdownguide.org/ - For documentation

---

### Project-Specific Resources

#### Your Technologies Stack

| Technology | Version | Documentation |
|-----------|---------|---|
| Django | 5.1.3 | https://docs.djangoproject.com/en/5.1/ |
| Django REST Framework | 3.14.0 | https://www.django-rest-framework.org/ |
| simple-jwt | 5.3.2 | https://django-rest-framework-simplejwt.readthedocs.io/ |
| Next.js | 15.1.6 | https://nextjs.org/docs |
| React | 19 | https://react.dev |
| TypeScript | 5 | https://www.typescriptlang.org/docs/ |
| Tailwind CSS | 3.4.1 | https://tailwindcss.com/docs |
| Axios | 1.7.7 | https://axios-http.com/docs |

---

### Recommended Reading Order

**Week 1: Django Basics**
1. Django Official Docs - Models: https://docs.djangoproject.com/en/stable/topics/db/models/
2. Django Official Docs - Queries: https://docs.djangoproject.com/en/stable/topics/db/queries/
3. Real Python Django Tutorials: https://realpython.com/

**Week 2: Django REST Framework**
1. DRF Serializers: https://www.django-rest-framework.org/api-guide/serializers/
2. DRF Generic Views: https://www.django-rest-framework.org/api-guide/generic-views/
3. DRF Permissions: https://www.django-rest-framework.org/api-guide/permissions/

**Week 3: React & Frontend**
1. React Hooks: https://react.dev/reference/react
2. React Context: https://react.dev/reference/react/useContext
3. Next.js App Router: https://nextjs.org/docs/app

**Week 4: Full Stack Integration**
1. CORS: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
2. JWT.io - Understanding tokens: https://jwt.io/
3. Axios Interceptors: https://axios-http.com/docs/interceptors

**Week 5: Security & Deployment**
1. OWASP Top 10: https://owasp.org/www-project-top-ten/
2. Auth0 JWT Best Practices: https://auth0.com/
3. Deployment guide (Vercel + Railway/Render)

---

### Community & Support

#### Discussion Forums
- **Stack Overflow** - https://stackoverflow.com/ (Tag: django, django-rest-framework, reactjs)
- **Reddit** - https://www.reddit.com/r/django/, https://www.reddit.com/r/reactjs/
- **Dev.to** - https://dev.to/ - Community blog platform

#### GitHub & Open Source
- **GitHub Discussions**: Search "django rest framework" or "next.js" for examples
- **GitHub Issues**: Look at library issues for solutions
- **Awesome Lists**: https://awesome.re/ - Curated lists of resources

#### Local Communities
- **Meetups**: https://www.meetup.com/ - Find Django/Python/React groups
- **Conferences**: PyCon, DjangoCon, React Conf

---

Good luck with your learning journey! This is a solid foundation for understanding full-stack development with Django and React.

