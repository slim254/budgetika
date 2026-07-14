from datetime import timedelta

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


class TestFutureTransactionDate(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dateuser", password="pass")
        self.wallet = Wallet.objects.create(
            name="Main", user=self.user, initial_value=0, currency="usd"
        )
        self.client = auth_client(self.user)

    def test_future_date_only_string_is_preserved(self):
        """Frontend posts a date-only string. The stored date must match it,
        not reset to today."""
        future = timezone.now().date() + timedelta(days=40)
        payload = {
            "note": "future rent",
            "amount": "-100.00",
            "currency": "usd",
            "date": future.isoformat(),      # e.g. "2026-08-15" — date only
            "wallet": str(self.wallet.id),
        }
        response = self.client.post("/api/transactions/", payload, format="json")
        # Print the observed behaviour for the debugging log:
        print("STATUS:", response.status_code, "BODY:", response.data)
        self.assertEqual(response.status_code, 201)
        txn = Transaction.objects.get(id=response.data["id"])
        self.assertEqual(txn.date.date(), future)
