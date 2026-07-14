from datetime import date, datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from wallets.models import BudgetRule, Transaction, TransactionCategory, Wallet


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class TestOverBudgetSummary(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bud", password="pass")
        self.wallet = Wallet.objects.create(
            name="Main", user=self.user, initial_value=0, currency="usd"
        )
        self.cat = TransactionCategory.objects.create(user=self.user, name="Dining")
        BudgetRule.objects.create(
            wallet=self.wallet, category=self.cat,
            amount="100.00", start_date=date(2026, 6, 1),
        )
        # Spend 150 in June 2026 → over the 100 limit
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user, category=self.cat,
            note="dinner", amount="-150.00", currency="usd",
            date=timezone.make_aware(datetime(2026, 6, 10, 20, 0)),
        )
        self.client = auth_client(self.user)

    def test_summary_flags_over_budget(self):
        response = self.client.get(
            f"/api/wallets/{self.wallet.id}/budgets/summary/?month=6&year=2026"
        )
        self.assertEqual(response.status_code, 200)
        dining = next(i for i in response.data if i["category"]["name"] == "Dining")
        self.assertTrue(dining["is_over_budget"])
