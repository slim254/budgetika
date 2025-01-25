from django.urls import path
from .views import WalletTransactionList, WalletTransactionDetail, WalletList

from . import views

urlpatterns = [
    path("", WalletList.as_view(), name="index"),
    path('<int:wallet_id>/', views.WalletDetail.as_view(), name='wallet-detail'),
    path('<int:wallet_id>/transactions/', WalletTransactionList.as_view(), name='wallet-transaction-list'),
    path('<int:wallet_id>/transactions/<int:pk>/', WalletTransactionDetail.as_view(), name='wallet-transaction-detail'),
    
]