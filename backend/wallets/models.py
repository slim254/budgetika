from django.db import models
from django.contrib.auth.models import User

class Wallet(models.Model):
    name = models.CharField(max_length=100)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    initial_value = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, choices=[
        ('usd', 'usd'),
        ('eur', 'eur'),
        ('gbp', 'gbp'),
        ('pln', 'pln')
    ])
    

    def __str__(self):
        return f"{self.user.username}'s Wallet"
    
class WalletCategory(models.Model):
    name = models.CharField(max_length=100)
    wallet = models.ForeignKey(Wallet, related_name='categories', on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, related_name='created_categories', on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=[
        ('income', 'income'),
        ('expense', 'expense'),
        ('both', 'both'),
    ])

    def __str__(self):
        return self.name

class Transaction(models.Model):
    note = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=[
        ('income', 'income'),
        ('expense', 'expense')
    ])
    currency = models.CharField(max_length=3, choices=[
        ('usd', 'usd'),
        ('eur', 'eur'),
        ('gbp', 'gbp'),
        ('pln', 'pln')
    ])
    date = models.DateTimeField(auto_now_add=True)
    wallet = models.ForeignKey(Wallet, related_name='transactions', on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, related_name='created_transactions', on_delete=models.CASCADE)
    category = models.ForeignKey(WalletCategory, related_name='transactions', on_delete=models.CASCADE, default=1)

    def __str__(self):
        return self.note