from rest_framework import serializers
from .models import Transaction, Wallet
from django.db.models import Sum


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['note', 'amount', 'transaction_type', 'currency']

    def validate(self, data):
        wallet = self.context.get('wallet')
        currency = data.get('currency')
        if wallet and currency and wallet.currency != currency:
            raise serializers.ValidationError(f"Transaction currency ({currency}) must match wallet currency ({wallet.currency}).")
        return data

class WalletSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = '__all__'

    def get_balance(self, obj):
        transactions = Transaction.objects.filter(wallet=obj)
        income = transactions.filter(transaction_type='income').aggregate(Sum('amount'))['amount__sum'] or 0
        expense = transactions.filter(transaction_type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
        return obj.initial_value + income - expense