from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from wallets.models import Transaction, Wallet


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class TestCSVExport(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="exp", password="pass")
        self.wallet = Wallet.objects.create(
            name="Main", user=self.user, initial_value=0, currency="usd"
        )
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user, note="salary",
            amount="1000.00", currency="usd",
            date=timezone.make_aware(datetime(2026, 6, 1, 9, 0)),
        )
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user, note="rent",
            amount="-500.00", currency="usd",
            date=timezone.make_aware(datetime(2026, 5, 1, 9, 0)),
        )
        self.client = auth_client(self.user)

    def test_export_all_returns_csv(self):
        response = self.client.get(f"/api/wallets/{self.wallet.id}/export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])
        body = response.content.decode()
        self.assertIn("date,amount,currency,note,category,tags", body)
        self.assertIn("salary", body)
        self.assertIn("rent", body)

    def test_export_month_filter(self):
        response = self.client.get(
            f"/api/wallets/{self.wallet.id}/export/?month=6&year=2026"
        )
        body = response.content.decode()
        self.assertIn("salary", body)      # June
        self.assertNotIn("rent", body)     # May excluded

    def test_export_rejects_other_users_wallet(self):
        other = User.objects.create_user(username="other", password="pass")
        response = auth_client(other).get(f"/api/wallets/{self.wallet.id}/export/")
        self.assertEqual(response.status_code, 404)
