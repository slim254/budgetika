from django.contrib import admin

# Register your models here.
from .models import Transaction, Wallet

admin.site.register(Transaction)
admin.site.register(Wallet)