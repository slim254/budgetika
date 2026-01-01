from django.urls import path
from .views import (
    WalletList, WalletDetail,
    WalletTransactionList, WalletTransactionDetail,
    UserCategoryList, UserCategoryDetail,
    TransactionDetail, TransactionCreate,
)

urlpatterns = [
    # Wallet routes
    path('', WalletList.as_view(), name='wallet-list'),
    path('<uuid:wallet_id>/', WalletDetail.as_view(), name='wallet-detail'),

    # Transaction routes (nested under wallet)
    path('<uuid:wallet_id>/transactions/', WalletTransactionList.as_view(), name='wallet-transaction-list'),
    path('<uuid:wallet_id>/transactions/<uuid:pk>/', WalletTransactionDetail.as_view(), name='wallet-transaction-detail'),

    # Category routes (NOT nested - user-scoped)
    # BEFORE: path('<uuid:wallet_id>/categories/', ...)
    # AFTER:
    path('categories/', UserCategoryList.as_view(), name='category-list'),
    path('categories/<uuid:pk>/', UserCategoryDetail.as_view(), name='category-detail'),

    # Direct transaction routes
    path('transactions/', TransactionCreate.as_view(), name='transaction-create'),
    path('transactions/<uuid:pk>/', TransactionDetail.as_view(), name='transaction-detail'),
]