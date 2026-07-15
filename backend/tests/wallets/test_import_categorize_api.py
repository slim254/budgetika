import io
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from wallets.ai import LLMResponse
from wallets.models import Transaction, TransactionCategory, Wallet

CSV = (
    "Date,Amount,Merchant,Title\n"
    "2024-01-01,-45.20,BIEDRONKA 1234,card payment\n"
    "2024-02-03,-12.00,BIEDRONKA 1234,card payment\n"   # duplicate merchant
    "2024-01-05,5000.00,ACME CORP,salary\n"
)


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def mock_provider(content):
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(content=content, input_tokens=30, output_tokens=6)
    return provider


def csv_upload(content=CSV, name="import.csv"):
    f = io.BytesIO(content.encode())
    f.name = name
    return f


@override_settings(
    AI_DEFAULT_PROVIDER="openai",
    AI_DEFAULT_MONTHLY_TOKENS=1_000_000,
    AI_WARN_THRESHOLDS=[80, 95],
    AI_MODELS={"auto_categorize": "gpt-4o-mini"},
    AI_IMPORT_BATCH_SIZE=40,
    AI_IMPORT_MAX_UNIQUE=500,
    OPENAI_API_KEY="test-key",
)
class TestImportCategorizeAPI(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="imp", password="pass")
        self.wallet = Wallet.objects.create(
            user=self.user, name="W", currency="pln", initial_value=0
        )
        self.groc, _ = TransactionCategory.objects.get_or_create(user=self.user, name="Groceries")
        self.client = auth_client(self.user)
        self.url = f"/api/wallets/{self.wallet.id}/import/categorize/"

    def _payload(self, csv=CSV):
        return {
            "file": csv_upload(csv),
            "column_mapping": '{"amount": "Amount", "date": "Date"}',
            "amount_config": '{"mode": "signed"}',
            "filters": "[]",
        }

    def test_returns_grouped_suggestions(self):
        # Model maps index 0 -> Groceries (BIEDRONKA), index 1 -> Uncategorized (ACME)
        reply = '{"0": "Groceries", "1": "Uncategorized"}'
        with patch("wallets.ai.get_provider", return_value=mock_provider(reply)):
            res = self.client.post(self.url, self._payload(), format="multipart")
        self.assertEqual(res.status_code, 200)
        suggestions = res.data["suggestions"]
        # Two unique descriptions (BIEDRONKA collapsed from 2 rows, ACME)
        self.assertEqual(len(suggestions), 2)
        biedronka = next(s for s in suggestions if "BIEDRONKA" in s["signature"])
        self.assertEqual(biedronka["count"], 2)
        self.assertEqual(biedronka["category_name"], "Groceries")
        acme = next(s for s in suggestions if "ACME" in s["signature"])
        self.assertIsNone(acme["category_id"])

    def test_invalid_category_reply_yields_null(self):
        with patch("wallets.ai.get_provider", return_value=mock_provider('{"0": "Nonsense", "1": "Nonsense"}')):
            res = self.client.post(self.url, self._payload(), format="multipart")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(all(s["category_id"] is None for s in res.data["suggestions"]))

    def test_requires_auth(self):
        res = APIClient().post(self.url, self._payload(), format="multipart")
        self.assertEqual(res.status_code, 401)

    def test_other_users_wallet_is_404(self):
        other = User.objects.create_user(username="other", password="pass")
        wallet = Wallet.objects.create(user=other, name="X", currency="pln", initial_value=0)
        url = f"/api/wallets/{wallet.id}/import/categorize/"
        with patch("wallets.ai.get_provider", return_value=mock_provider("{}")):
            res = self.client.post(url, self._payload(), format="multipart")
        self.assertEqual(res.status_code, 404)

    def test_execute_applies_ai_categories(self):
        # First get suggestions to obtain the stable key for BIEDRONKA.
        with patch("wallets.ai.get_provider", return_value=mock_provider('{"0": "Groceries", "1": "Uncategorized"}')):
            res = self.client.post(self.url, self._payload(), format="multipart")
        biedronka = next(s for s in res.data["suggestions"] if "BIEDRONKA" in s["signature"])

        execute_url = f"/api/wallets/{self.wallet.id}/import/execute/"
        payload = {
            "file": csv_upload(),
            "column_mapping": '{"amount": "Amount", "date": "Date"}',
            "amount_config": '{"mode": "signed"}',
            "filters": "[]",
            "ai_categories": '{"%s": "%s"}' % (biedronka["key"], self.groc.id),
        }
        res2 = self.client.post(execute_url, payload, format="multipart")
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.data["success"])
        self.assertEqual(Transaction.objects.filter(category=self.groc).count(), 2)
