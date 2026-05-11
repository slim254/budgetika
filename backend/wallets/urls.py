from django.urls import path
from .views import (
    WalletList, WalletDetail,
    WalletTransactionList, WalletTransactionDetail,
    UserCategoryList, UserCategoryDetail,
    UserTagList, UserTagDetail,
    TransactionDetail, TransactionCreate,
    CSVParseView, CSVExecuteView,
    WalletMetrics,
    UserRecurringTransactionList,
    WalletRecurringTransactionList, WalletRecurringTransactionDetail,
    RecurringTransactionExecutionList,
)

urlpatterns = [
    # Wallet routes
    path('', WalletList.as_view(), name='wallet-list'),
    path('<uuid:wallet_id>/', WalletDetail.as_view(), name='wallet-detail'),

    # Transaction routes (nested under wallet)
    path('<uuid:wallet_id>/transactions/', WalletTransactionList.as_view(), name='wallet-transaction-list'),
    path('<uuid:wallet_id>/transactions/<uuid:pk>/', WalletTransactionDetail.as_view(), name='wallet-transaction-detail'),

    # Per-wallet metrics
    path('<uuid:wallet_id>/metrics/', WalletMetrics.as_view(), name='wallet-metrics'),

    # Category routes (NOT nested - user-scoped)
    path('categories/', UserCategoryList.as_view(), name='category-list'),
    path('categories/<uuid:pk>/', UserCategoryDetail.as_view(), name='category-detail'),

    path('tags/', UserTagList.as_view(), name='tag-list'),
    path('tags/<uuid:pk>/', UserTagDetail.as_view(), name='tag-detail'),

    # Direct transaction routes
    path('transactions/', TransactionCreate.as_view(), name='transaction-create'),
    path('transactions/<uuid:pk>/', TransactionDetail.as_view(), name='transaction-detail'),

    # CSV import routes
    path('<uuid:wallet_id>/import/parse/', CSVParseView.as_view(), name='csv-import-parse'),
    path('<uuid:wallet_id>/import/execute/', CSVExecuteView.as_view(), name='csv-import-execute'),

    # Recurring transaction routes
    path('recurring/', UserRecurringTransactionList.as_view(), name='user-recurring-list'),
    path('<uuid:wallet_id>/recurring/', WalletRecurringTransactionList.as_view(), name='wallet-recurring-list'),
    path('<uuid:wallet_id>/recurring/<uuid:pk>/', WalletRecurringTransactionDetail.as_view(), name='wallet-recurring-detail'),
    path('<uuid:wallet_id>/recurring/<uuid:pk>/executions/', RecurringTransactionExecutionList.as_view(), name='wallet-recurring-executions'),
]