from datetime import datetime, date
from decimal import Decimal
from django.db.models import F, Sum, DecimalField, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.db import transaction as db_transaction
from rest_framework import generics, viewsets, status
from rest_framework.pagination import CursorPagination
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Transaction, UserTransactionTag, Wallet, TransactionCategory, RecurringTransaction, RecurringTransactionExecution, BudgetRule, BudgetMonthOverride, UserProfile, SavingsGoal
from .serializers import (
    TagSerializer, TransactionSerializer, WalletSerializer, CategorySerializer,
    CSVParseSerializer, CSVExecuteSerializer,
    UserDashboardSerializer, WalletDashboardSerializer,
    RecurringTransactionSerializer, RecurringTransactionExecutionSerializer,
    BudgetRuleSerializer, BudgetOverrideSerializer, BudgetSummarySerializer,
    UserProfileSerializer, WalletTransferSerializer, SavingsGoalSerializer,
)
from rest_framework.views import APIView
from rest_framework.response import Response
from .services import GenericCSVImportService, DashboardService, get_rate, SavingsGoalService
import json


class WalletDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a specific wallet.

    Endpoints:
        GET /wallets/{wallet_id}/ - Retrieve wallet details
        PUT /wallets/{wallet_id}/ - Replace entire wallet
        PATCH /wallets/{wallet_id}/ - Partially update wallet
        DELETE /wallets/{wallet_id}/ - Delete wallet (and all associated transactions)

    Security: Uses IsAuthenticated permission to ensure only logged-in users can access.
    Also verifies that the requested wallet belongs to the authenticated user using
    get_object() - this prevents users from accessing other users' wallets.
    """
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_object(self):
        """
        Override to filter wallet by both ID and the authenticated user.

        This ensures users can only retrieve/update/delete their own wallets.
        Returns 404 if wallet doesn't exist or doesn't belong to the user.
        """
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        return wallet

    def perform_update(self, serializer):
        """
        Called after validation but before saving during PUT/PATCH requests.

        We verify wallet ownership again here as an extra security measure.
        This ensures the wallet can't be updated to modify another user's data.
        """
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        serializer.save(wallet=wallet)

    def perform_destroy(self, instance):
        """
        Called when DELETE request is processed. Deletes the wallet and all
        associated transactions (due to ForeignKey on_delete=CASCADE).
        """
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        instance.delete()


class WalletTransactionList(generics.ListCreateAPIView):
    """
    API endpoint for listing transactions in a wallet or creating new transactions.

    Endpoints:
        GET /wallets/{wallet_id}/transactions/ - List transactions (with optional month/year filter)
        POST /wallets/{wallet_id}/transactions/ - Create new transaction

    Query Parameters (for GET):
        month: Month number (1-12), defaults to current month
        year: Year number, defaults to current year

    Example: GET /wallets/1/transactions/?month=11&year=2025

    The endpoint automatically filters transactions to:
    1. Only show transactions from the specified wallet
    2. Only show transactions where the requesting user owns the wallet (security)
    3. Only show transactions from the specified month/year
    """
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """
        Returns transactions filtered by wallet ownership and date range.

        Filters:
        1. wallet: Only transactions from the specified wallet
        2. user: Only transactions from wallets owned by the authenticated user
        3. date__month and date__year: Only transactions from specified month/year
        """
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        queryset = Transaction.objects.filter(wallet=wallet).select_related('transfer_peer__wallet')

        # Get month and year from query parameters, default to current date
        month = self.request.query_params.get('month')
        year = self.request.query_params.get('year')

        if not month:
            month = datetime.now().month
        if not year:
            year = datetime.now().year

        # Filter by month and year using Django's date lookup expressions
        queryset = queryset.filter(date__month=month, date__year=year)
        return queryset

    def perform_create(self, serializer):
        """
        Called when creating a new transaction.

        Automatically sets:
        - wallet: The wallet from the URL parameter
        - created_by: The authenticated user

        This prevents users from creating transactions in other users' wallets
        or spoofing the creator.
        """
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        serializer.save(wallet=wallet, created_by=self.request.user)

    def get_serializer_context(self):
        """
        Adds the wallet object to the serializer's context.

        The TransactionSerializer's validate() method uses this context to
        check that the transaction currency matches the wallet currency.
        """
        context = super().get_serializer_context()
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        context.update({"wallet": wallet})
        return context


class WalletTransactionDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a specific transaction.

    Endpoints:
        GET /wallets/{wallet_id}/transactions/{pk}/ - Retrieve transaction
        PUT /wallets/{wallet_id}/transactions/{pk}/ - Replace transaction
        PATCH /wallets/{wallet_id}/transactions/{pk}/ - Partially update transaction
        DELETE /wallets/{wallet_id}/transactions/{pk}/ - Delete transaction

    Security: The get_queryset() method ensures that:
    1. The wallet belongs to the authenticated user
    2. The transaction belongs to that wallet

    This prevents users from accessing transactions from other users' wallets.
    """
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """
        Returns transactions filtered to only include those from the user's wallet.

        This ensures users can only view/edit/delete their own transactions.
        """
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        return Transaction.objects.filter(wallet=wallet)


class WalletList(generics.ListCreateAPIView):
    """
    API endpoint for listing all wallets or creating a new wallet.

    Endpoints:
        GET /wallets/ - List user's wallets
        POST /wallets/ - Create new wallet

    Security: Filters wallets to only show those owned by the authenticated user.
    When creating a wallet, automatically sets the owner to the authenticated user.
    """
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """
        Returns only wallets owned by the authenticated user, annotated with
        `calculated_balance` so WalletSerializer.get_balance can read it
        without issuing one aggregate query per wallet.
        """
        return Wallet.objects.filter(user=self.request.user).annotate(
            calculated_balance=F('initial_value') + Coalesce(
                Sum('transactions__amount'),
                Decimal('0'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )

    def perform_create(self, serializer):
        """
        Creates wallet with the authenticated user as the owner.
        """
        serializer.save(user=self.request.user)


class TransactionDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a transaction by ID.

    Endpoints:
        GET /transactions/{id}/ - Retrieve transaction
        PUT /transactions/{id}/ - Replace transaction
        PATCH /transactions/{id}/ - Partially update transaction
        DELETE /transactions/{id}/ - Delete transaction

    Security: Filters transactions to only those from wallets owned by the
    authenticated user.
    """
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """
        Returns transactions from wallets owned by the authenticated user.
        """
        user_wallets = Wallet.objects.filter(user=self.request.user)
        return Transaction.objects.filter(wallet__in=user_wallets)

    def get_serializer_context(self):
        """
        Adds the wallet object to the serializer's context for validation.
        """
        context = super().get_serializer_context()
        transaction = self.get_object()
        context.update({"wallet": transaction.wallet})
        return context


class TransactionCreate(generics.CreateAPIView):
    """
    API endpoint for creating a new transaction.

    Endpoint:
        POST /transactions/ - Create new transaction

    The request must include the wallet ID to associate the transaction with.
    Security: Verifies that the wallet belongs to the authenticated user.
    """
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def perform_create(self, serializer):
        """
        Creates transaction and verifies wallet ownership.
        """
        wallet_id = self.request.data.get('wallet')
        if not wallet_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"wallet": "This field is required."})

        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        serializer.save(wallet=wallet, created_by=self.request.user)

    def get_serializer_context(self):
        """
        Adds the wallet object to the serializer's context for validation.
        """
        context = super().get_serializer_context()
        wallet_id = self.request.data.get('wallet')
        if wallet_id:
            try:
                wallet = Wallet.objects.get(id=wallet_id, user=self.request.user)
                context.update({"wallet": wallet})
            except Wallet.DoesNotExist:
                pass
        return context

class UserCategoryList(generics.ListCreateAPIView):
    """
    List all user's categories or create a new one.

    GET /api/wallets/categories/ - List all categories
    POST /api/wallets/categories/ - Create new category

    DRF EDUCATIONAL NOTE - generics.ListCreateAPIView
    =================================================
    This class combines:
    - ListModelMixin: Provides list() method for GET requests
    - CreateModelMixin: Provides create() method for POST requests
    - GenericAPIView: Base class with queryset/serializer handling

    Why not ViewSet?
    ================
    ViewSet combines all CRUD operations into one class with automatic routing.
    We use separate APIViews because:
    1. More explicit URL patterns in urls.py
    2. Easier to understand for learning DRF
    3. Fine-grained control over each endpoint
    4. Better for simple CRUD without complex routing

    Use ViewSet when:
    - You need all CRUD operations with consistent patterns
    - Using routers for automatic URL generation
    - Building larger APIs with many resources

    Query Parameters:
    - include_hidden=true: Also return is_visible=False categories
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """
        DRF EDUCATIONAL NOTE - Permission Classes vs Queryset Filtering
        ===============================================================
        Permission classes (IsAuthenticated) control ACCESS to the endpoint.
        Queryset filtering controls WHAT DATA the user can see.

        Both are needed for proper security:
        1. IsAuthenticated: Reject unauthenticated requests (401)
        2. Queryset filter: Only return user's own data (data isolation)

        Without queryset filtering, an authenticated user could see
        everyone's data - a major security flaw!
        """
        include_hidden = self.request.query_params.get('include_hidden', 'false').lower() == 'true'

        queryset = TransactionCategory.objects.filter(
            user=self.request.user,
            is_archived=False
        )

        if not include_hidden:
            queryset = queryset.filter(is_visible=True)

        return queryset

    def perform_create(self, serializer):
        """
        DRF EDUCATIONAL NOTE - perform_create() Hook
        ============================================
        This method is called after validation but before saving.
        It's the ideal place to:
        - Set the user from the request (avoiding client manipulation)
        - Add computed fields
        - Perform side effects (logging, notifications)

        The serializer.save() call triggers the serializer's create() method
        and passes any kwargs as additional data.
        """
        serializer.save(user=self.request.user)


class UserTagList(generics.ListCreateAPIView):
    """
    List all user's tags or create a new one.

    GET /api/wallets/tags/ - List all tags
    POST /api/wallets/tags/ - Create new tag

    DRF EDUCATIONAL NOTE - Authentication Classes
    =============================================
    authentication_classes = [JWTAuthentication] specifies HOW we
    authenticate users. Options include:

    - SessionAuthentication: Uses Django sessions (cookies)
    - BasicAuthentication: HTTP Basic Auth (username:password in header)
    - TokenAuthentication: DRF's built-in token auth
    - JWTAuthentication: JSON Web Tokens (stateless, scalable)

    We use JWT because:
    1. Stateless: No server-side session storage needed
    2. Scalable: Works across multiple servers without session sync
    3. Mobile-friendly: No cookies required
    4. Contains user info in the token itself (after verification)

    Query Parameters:
    - include_hidden=true: Also return is_visible=False tags
    """
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """Return tags for authenticated user only."""
        include_hidden = self.request.query_params.get('include_hidden', 'false').lower() == 'true'

        queryset = UserTransactionTag.objects.filter(user=self.request.user)

        if not include_hidden:
            queryset = queryset.filter(is_visible=True)

        return queryset

    def perform_create(self, serializer):
        """Set user automatically."""
        serializer.save(user=self.request.user)



class UserTagDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a tag.

    GET /api/tags/{id}/ - Get tag details
    PUT /api/tags/{id}/ - Update tag
    DELETE /api/tags/{id}/ - Delete tag
    """
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """Return only user's tags."""
        return UserTransactionTag.objects.filter(user=self.request.user)


class UserCategoryDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a category.

    GET /api/wallets/categories/{id}/ - Get category details
    PUT /api/wallets/categories/{id}/ - Update category (full replace)
    PATCH /api/wallets/categories/{id}/ - Partial update
    DELETE /api/wallets/categories/{id}/ - Archive category (soft delete)
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """Return only user's own categories."""
        return TransactionCategory.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        """
        DRF EDUCATIONAL NOTE - Soft Delete Pattern
        ==========================================
        Instead of actually deleting, we set is_archived=True.

        Benefits:
        - Preserves historical data for reporting
        - Transactions keep their category reference
        - Can be "undeleted" if needed
        - Audit trail maintained
        """
        instance.is_archived = True
        instance.save()


class CSVParseView(APIView):
    """
    Parse a CSV file and return column information for mapping.

    POST /api/wallets/{wallet_id}/import/parse/

    This is Step 1 of CSV import - analyzes the CSV and returns:
    - Column names
    - Sample rows
    - Unique values per column (for filter dropdowns)
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, wallet_id):
        wallet = get_object_or_404(Wallet, id=wallet_id, user=request.user)

        serializer = CSVParseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        csv_file = serializer.validated_data['file']
        service = GenericCSVImportService(request.user, wallet, csv_file)

        try:
            result = service.parse()
            return Response(result)
        except Exception as e:
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class CSVExecuteView(APIView):
    """
    Execute CSV import with the provided column mapping and configuration.

    POST /api/wallets/{wallet_id}/import/execute/

    This is Step 2 of CSV import - imports transactions using the mapping
    provided by the user after reviewing the parse results.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, wallet_id):
        wallet = get_object_or_404(Wallet, id=wallet_id, user=request.user)

        # Parse JSON fields from FormData (they come as strings)
        # Create a regular dict from request.data
        data = {
            'file': request.data.get('file')
        }

        try:
            # Parse JSON strings to Python objects
            if 'column_mapping' in request.data:
                data['column_mapping'] = json.loads(request.data['column_mapping'])
            if 'amount_config' in request.data:
                data['amount_config'] = json.loads(request.data['amount_config'])
            if 'filters' in request.data:
                data['filters'] = json.loads(request.data['filters'])
        except json.JSONDecodeError as e:
            return Response(
                {"error": f"Invalid JSON in request: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CSVExecuteSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        csv_file = serializer.validated_data['file']
        column_mapping = serializer.validated_data['column_mapping']
        amount_config = serializer.validated_data['amount_config']
        filters = serializer.validated_data.get('filters', [])

        service = GenericCSVImportService(request.user, wallet, csv_file)
        result = service.execute(column_mapping, amount_config, filters)

        if result.get('success'):
            return Response(result)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)


class UserDashboard(APIView):
    """
    Aggregated financial snapshot across all of the user's wallets.

    GET /api/dashboard/

    Returns: summary totals, per-wallet summaries, spending by category
    (this month), and a 6-month income/expense trend.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        base_currency = request.query_params.get("base_currency", "").lower() or None
        if base_currency and base_currency not in {"usd", "eur", "gbp", "pln"}:
            base_currency = None
        data = DashboardService(request.user).user_summary(base_currency=base_currency)
        return Response(UserDashboardSerializer(data).data)


class WalletMetrics(APIView):
    """
    Deep-dive metrics for a single wallet.

    GET /api/wallets/{wallet_id}/metrics/

    Returns: lifetime stats, this-month income/expense/net, category
    breakdown over all transactions, and the 10 most recent transactions.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, wallet_id):
        wallet = get_object_or_404(Wallet, id=wallet_id, user=request.user)
        data = DashboardService(request.user).wallet_summary(wallet)
        return Response(
            WalletDashboardSerializer(data, context={'request': request}).data
        )


class UserRecurringTransactionList(generics.ListAPIView):
    serializer_class = RecurringTransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        return RecurringTransaction.objects.filter(
            wallet__user=self.request.user
        ).select_related("wallet", "category", "created_by").prefetch_related("tags")


class WalletRecurringTransactionList(generics.ListCreateAPIView):
    serializer_class = RecurringTransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _get_wallet(self):
        return get_object_or_404(
            Wallet, id=self.kwargs["wallet_id"], user=self.request.user
        )

    def get_queryset(self):
        return RecurringTransaction.objects.filter(wallet=self._get_wallet())

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["wallet"] = self._get_wallet()
        return ctx

    def perform_create(self, serializer):
        wallet = self._get_wallet()
        serializer.save(
            wallet=wallet,
            created_by=self.request.user,
            currency=wallet.currency,
        )


class WalletRecurringTransactionDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RecurringTransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _get_wallet(self):
        return get_object_or_404(
            Wallet, id=self.kwargs["wallet_id"], user=self.request.user
        )

    def get_queryset(self):
        return RecurringTransaction.objects.filter(wallet=self._get_wallet())

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["wallet"] = self._get_wallet()
        return ctx


class RecurringTransactionExecutionList(generics.ListAPIView):
    serializer_class = RecurringTransactionExecutionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        wallet = get_object_or_404(
            Wallet, id=self.kwargs["wallet_id"], user=self.request.user
        )
        recurring = get_object_or_404(
            RecurringTransaction, id=self.kwargs["pk"], wallet=wallet
        )
        return RecurringTransactionExecution.objects.filter(
            recurring_transaction=recurring
        )

class TransactionCursorPagination(CursorPagination):
    page_size = 25
    ordering = ('-date', '-id')


class WalletTransactionSearch(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    pagination_class = TransactionCursorPagination

    def get_queryset(self):
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        queryset = Transaction.objects.filter(wallet=wallet).select_related('category').prefetch_related('tags')

        p = self.request.query_params

        if search := p.get('search'):
            queryset = queryset.filter(note__icontains=search)

        if category := p.get('category'):
            queryset = queryset.filter(category__id=category)

        if tag := p.get('tag'):
            queryset = queryset.filter(tags__id=tag).distinct()

        if date_from := p.get('date_from'):
            queryset = queryset.filter(date__date__gte=date_from)

        if date_to := p.get('date_to'):
            queryset = queryset.filter(date__date__lte=date_to)

        if min_amount := p.get('min_amount'):
            queryset = queryset.filter(amount__gte=min_amount)

        if max_amount := p.get('max_amount'):
            queryset = queryset.filter(amount__lte=max_amount)

        return queryset


class BudgetRuleList(generics.ListCreateAPIView):
    serializer_class = BudgetRuleSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _get_wallet(self):
        return get_object_or_404(Wallet, id=self.kwargs["wallet_id"], user=self.request.user)

    def get_queryset(self):
        return BudgetRule.objects.filter(wallet=self._get_wallet()).select_related("category")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["wallet"] = self._get_wallet()
        return ctx

    def perform_create(self, serializer):
        serializer.save(wallet=self._get_wallet())


class BudgetRuleDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BudgetRuleSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _get_wallet(self):
        return get_object_or_404(Wallet, id=self.kwargs["wallet_id"], user=self.request.user)

    def get_queryset(self):
        return BudgetRule.objects.filter(wallet=self._get_wallet()).select_related("category")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["wallet"] = self._get_wallet()
        return ctx


class BudgetOverrideList(generics.ListCreateAPIView):
    serializer_class = BudgetOverrideSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _get_wallet(self):
        return get_object_or_404(Wallet, id=self.kwargs["wallet_id"], user=self.request.user)

    def get_queryset(self):
        return BudgetMonthOverride.objects.filter(wallet=self._get_wallet()).select_related("category")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["wallet"] = self._get_wallet()
        return ctx

    def create(self, request, *args, **kwargs):
        wallet = self._get_wallet()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        vd = serializer.validated_data
        category_id = vd["category_id"]
        category = TransactionCategory.objects.get(id=category_id, user=wallet.user)

        obj, created = BudgetMonthOverride.objects.update_or_create(
            wallet=wallet,
            category=category,
            year=vd["year"],
            month=vd["month"],
            defaults={"amount": vd["amount"]},
        )
        out = BudgetOverrideSerializer(obj, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class BudgetOverrideDetail(generics.DestroyAPIView):
    serializer_class = BudgetOverrideSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _get_wallet(self):
        return get_object_or_404(Wallet, id=self.kwargs["wallet_id"], user=self.request.user)

    def get_queryset(self):
        return BudgetMonthOverride.objects.filter(wallet=self._get_wallet())


class BudgetSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, wallet_id):
        wallet = get_object_or_404(Wallet, id=wallet_id, user=request.user)

        try:
            month = int(request.query_params.get("month", datetime.now().month))
            year = int(request.query_params.get("year", datetime.now().year))
            month_start = date(year, month, 1)
        except ValueError:
            return Response(
                {"error": "Invalid month or year."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rules = BudgetRule.objects.filter(
            wallet=wallet,
            start_date__lte=month_start,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=month_start)
        ).select_related("category")

        overrides = {
            o.category_id: o
            for o in BudgetMonthOverride.objects.filter(wallet=wallet, year=year, month=month)
        }

        spending = {
            row["category_id"]: abs(row["total"])
            for row in Transaction.objects.filter(
                wallet=wallet,
                date__month=month,
                date__year=year,
                amount__lt=0,
            ).values("category_id").annotate(total=Sum("amount"))
        }

        items = []
        for rule in rules:
            if rule.category_id is None:
                continue
            override = overrides.get(rule.category_id)
            limit = override.amount if override else rule.amount
            spent = spending.get(rule.category_id, Decimal("0"))
            remaining = limit - spent
            items.append({
                "category": rule.category,
                "limit": limit,
                "spent": spent,
                "remaining": remaining,
                "is_over_budget": remaining < 0,
                "is_override": override is not None,
                "rule_id": rule.id,
                "override_id": override.id if override else None,
            })

        serializer = BudgetSummarySerializer(items, many=True)
        return Response(serializer.data)


class ExchangeRateView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        base = request.query_params.get("base", "").lower()
        quote = request.query_params.get("quote", "").lower()
        date_str = request.query_params.get("date", str(date.today()))

        valid = {"usd", "eur", "gbp", "pln"}
        if base not in valid or quote not in valid:
            return Response(
                {"error": "Invalid currency. Must be one of: usd, eur, gbp, pln"},
                status=400,
            )

        try:
            rate_date = date.fromisoformat(date_str)
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        try:
            rate = get_rate(base, quote, rate_date)
        except Exception:
            return Response({"error": "Failed to fetch exchange rate."}, status=503)

        return Response({"rate": str(rate), "date": str(rate_date)})


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        try:
            profile = UserProfile.objects.get(user=request.user)
            return Response({"preferred_currency": profile.preferred_currency})
        except UserProfile.DoesNotExist:
            return Response({"preferred_currency": None})

    def patch(self, request):
        serializer = UserProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if "preferred_currency" in serializer.validated_data:
            profile.preferred_currency = serializer.validated_data["preferred_currency"]
        profile.save()
        return Response({"preferred_currency": profile.preferred_currency})


class WalletTransferView(APIView):
    """
    POST   /api/wallets/transfers/            — create a transfer
    PATCH  /api/wallets/transfers/{ref}/      — edit both legs
    DELETE /api/wallets/transfers/{ref}/      — delete both legs
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        serializer = WalletTransferSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        debit, credit = serializer.save()
        debit_data = TransactionSerializer(
            Transaction.objects.select_related('transfer_peer__wallet').get(pk=debit.pk),
            context={'request': request},
        ).data
        credit_data = TransactionSerializer(
            Transaction.objects.select_related('transfer_peer__wallet').get(pk=credit.pk),
            context={'request': request},
        ).data
        return Response(
            {'transfer_ref': str(debit.transfer_ref), 'debit': debit_data, 'credit': credit_data},
            status=status.HTTP_201_CREATED,
        )

    def _get_pair(self, transfer_ref, user):
        legs = list(
            Transaction.objects.filter(
                transfer_ref=transfer_ref,
                wallet__user=user,
            ).select_related('wallet', 'transfer_peer__wallet')
        )
        if len(legs) != 2:
            return None, None
        debit = next((t for t in legs if t.amount < 0), None)
        credit = next((t for t in legs if t.amount > 0), None)
        return debit, credit

    def patch(self, request, transfer_ref):
        debit, credit = self._get_pair(transfer_ref, request.user)
        if debit is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        note = request.data.get('note', debit.note)
        date = request.data.get('date', debit.date)
        from_amount = request.data.get('from_amount')
        to_amount = request.data.get('to_amount')

        with db_transaction.atomic():
            debit.note = note
            debit.date = date
            if from_amount is not None:
                debit.amount = -Decimal(str(from_amount))
            debit.save()
            credit.note = note
            credit.date = date
            if to_amount is not None:
                credit.amount = Decimal(str(to_amount))
            credit.save()

        debit_data = TransactionSerializer(
            Transaction.objects.select_related('transfer_peer__wallet').get(pk=debit.pk),
            context={'request': request},
        ).data
        credit_data = TransactionSerializer(
            Transaction.objects.select_related('transfer_peer__wallet').get(pk=credit.pk),
            context={'request': request},
        ).data
        return Response({'transfer_ref': str(transfer_ref), 'debit': debit_data, 'credit': credit_data})

    def delete(self, request, transfer_ref):
        count, _ = Transaction.objects.filter(
            transfer_ref=transfer_ref,
            wallet__user=request.user,
        ).delete()
        if count == 0:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SavingsGoalViewSet(viewsets.ModelViewSet):
    serializer_class = SavingsGoalSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        """Filter goals by wallet; ensure wallet belongs to user."""
        wallet_id = self.kwargs.get("wallet_pk")
        return SavingsGoal.objects.filter(
            wallet__id=wallet_id, wallet__user=self.request.user
        )

    def perform_create(self, serializer):
        """Set the wallet from the URL."""
        wallet_id = self.kwargs.get("wallet_pk")
        try:
            wallet = Wallet.objects.get(id=wallet_id, user=self.request.user)
        except Wallet.DoesNotExist:
            from rest_framework import serializers
            raise serializers.ValidationError("Wallet not found or access denied.")
        serializer.save(wallet=wallet)

    def get_serializer_context(self):
        """Pass wallet to serializer context."""
        context = super().get_serializer_context()
        wallet_id = self.kwargs.get("wallet_pk")
        try:
            context["wallet"] = Wallet.objects.get(
                id=wallet_id, user=self.request.user
            )
        except Wallet.DoesNotExist:
            pass
        return context

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="summary",
    )
    def summary(self, request, wallet_pk=None):
        """Get monthly savings summary for a wallet."""
        from datetime import date

        month = int(request.query_params.get("month", 0))
        year = int(request.query_params.get("year", 0))

        if not month or not year:
            today = date.today()
            month = today.month
            year = today.year

        try:
            wallet = Wallet.objects.get(id=wallet_pk, user=request.user)
        except Wallet.DoesNotExist:
            return Response(
                {"error": "Wallet not found"}, status=status.HTTP_404_NOT_FOUND
            )

        summary_data = SavingsGoalService.get_monthly_summary(wallet, year, month)
        goals_qs = summary_data.pop("goals")
        goals_serialized = SavingsGoalSerializer(
            goals_qs, many=True, context=self.get_serializer_context()
        ).data

        response_data = {
            **summary_data,
            "goals": goals_serialized,
        }
        return Response(response_data, status=status.HTTP_200_OK)
