from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Transaction, Wallet
from .serializers import TransactionSerializer, WalletSerializer

class WalletDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_object(self):
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        return wallet

    def perform_update(self, serializer):
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        serializer.save(wallet=wallet)

    def perform_destroy(self, instance):
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        instance.delete()


class WalletTransactionList(generics.ListCreateAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        return Transaction.objects.filter(wallet=wallet)

    def perform_create(self, serializer):
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        serializer.save(wallet=wallet, created_by=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        context.update({"wallet": wallet})
        return context

class WalletTransactionDetail(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        return Transaction.objects.filter(wallet=wallet)
    

class WalletList(generics.ListCreateAPIView):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = [JWTAuthentication]
