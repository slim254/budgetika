from django.contrib import admin

# Register your models here.
from .models import Transaction, Wallet, UserTransactionCategory, UserTransactionTag

admin.site.register(Transaction)
admin.site.register(Wallet)
admin.site.register(UserTransactionCategory)
admin.site.register(UserTransactionTag)