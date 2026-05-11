from django.contrib import admin

from .models import (
    Transaction,
    Wallet,
    TransactionCategory,
    UserTransactionTag,
    RecurringTransaction,
    RecurringTransactionExecution,
)

admin.site.register(Transaction)
admin.site.register(Wallet)
admin.site.register(TransactionCategory)
admin.site.register(UserTransactionTag)
admin.site.register(RecurringTransaction)
admin.site.register(RecurringTransactionExecution)