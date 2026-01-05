from django.contrib import admin

# Register your models here.
from .models import Transaction, Wallet, TransactionCategory, UserTransactionTag

admin.site.register(Transaction)
admin.site.register(Wallet)
admin.site.register(TransactionCategory)
admin.site.register(UserTransactionTag)