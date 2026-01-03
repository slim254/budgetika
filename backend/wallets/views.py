from datetime import datetime
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Transaction, UserTransactionTag, Wallet, UserTransactionCategory
from .serializers import TagSerializer, TransactionSerializer, WalletSerializer, CategorySerializer


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
        queryset = Transaction.objects.filter(wallet=wallet)

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
        Returns only wallets owned by the authenticated user.
        """
        return Wallet.objects.filter(user=self.request.user)

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

    GET /api/categories/ - List all categories
    POST /api/categories/ - Create new category

    Categories are user-scoped (shared across all wallets).
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """Return categories for authenticated user only."""
        return UserTransactionCategory.objects.filter(
            user=self.request.user,
            is_archived=False  # Don't show archived by default
        )

    def perform_create(self, serializer):
        """Set user automatically."""
        serializer.save(user=self.request.user)


class UserTagList(generics.ListCreateAPIView):
    """
    List all user's tags or create a new one.

    GET /api/tags/ - List all tags
    POST /api/tags/ - Create new tag

    Tags are user-scoped (shared across all wallets).
    """
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """Return tags for authenticated user only."""
        return UserTransactionTag.objects.filter(
            user=self.request.user,
        )

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

    GET /api/categories/{id}/ - Get category details
    PUT /api/categories/{id}/ - Update category
    DELETE /api/categories/{id}/ - Archive category (soft delete)
    """
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        """Return only user's categories."""
        return UserTransactionCategory.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        """
        Soft delete: Archive instead of deleting.

        This preserves historical data - transactions keep their category
        reference, but category won't appear in dropdown for new transactions.
        """
        instance.is_archived = True
        instance.save()