from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from wallets.ai import LLMResponse
from wallets.models import TransactionCategory


def auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def mock_provider(content):
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(content=content, input_tokens=20, output_tokens=3)
    return provider


@override_settings(
    AI_DEFAULT_PROVIDER="openai",
    AI_DEFAULT_MONTHLY_TOKENS=1_000_000,
    AI_WARN_THRESHOLDS=[80, 95],
    AI_MODELS={"auto_categorize": "gpt-4o-mini"},
    OPENAI_API_KEY="test-key",
)
class TestCategorize(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cat", password="pass")
        self.dining = TransactionCategory.objects.create(user=self.user, name="Dining")
        self.client = auth_client(self.user)

    def test_returns_matching_category(self):
        with patch("wallets.ai.get_provider", return_value=mock_provider("Dining")):
            res = self.client.post("/api/wallets/categorize/", {"note": "dinner out"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["suggestion"]["name"], "Dining")
        self.assertEqual(res.data["suggestion"]["id"], str(self.dining.id))

    def test_unknown_category_returns_null_suggestion(self):
        # "Zzyzx Widgets" is not a default category (see wallets/constants.py) and
        # was never created in setUp, so it can't match the user's category list.
        with patch("wallets.ai.get_provider", return_value=mock_provider("Zzyzx Widgets")):
            res = self.client.post("/api/wallets/categorize/", {"note": "milk"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data["suggestion"])

    def test_blank_note_is_rejected(self):
        res = self.client.post("/api/wallets/categorize/", {"note": "  "}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_requires_auth(self):
        res = APIClient().post("/api/wallets/categorize/", {"note": "x"}, format="json")
        self.assertEqual(res.status_code, 401)
