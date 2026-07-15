from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from wallets.ai import LLMResponse, categorize_signatures


def mock_provider(content):
    provider = MagicMock()
    provider.complete.return_value = LLMResponse(content=content, input_tokens=50, output_tokens=10)
    return provider


@override_settings(
    AI_DEFAULT_PROVIDER="openai",
    AI_DEFAULT_MONTHLY_TOKENS=1_000_000,
    AI_WARN_THRESHOLDS=[80, 95],
    AI_MODELS={"auto_categorize": "gpt-4o-mini"},
    AI_IMPORT_BATCH_SIZE=40,
    OPENAI_API_KEY="test-key",
)
class TestCategorizeSignatures(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="imp", password="pass")
        self.names = ["Groceries", "Transport", "Income"]

    def test_maps_valid_categories_and_drops_invalid(self):
        reply = '{"0": "Groceries", "1": "Nonsense", "2": "Uncategorized"}'
        items = [("k0", "BIEDRONKA"), ("k1", "MYSTERY"), ("k2", "ATM WITHDRAWAL")]
        with patch("wallets.ai.get_provider", return_value=mock_provider(reply)):
            mapping, warning, quota = categorize_signatures(self.user, items, self.names)
        self.assertEqual(mapping, {"k0": "Groceries"})  # invalid + Uncategorized excluded
        self.assertFalse(quota)

    def test_batches_multiple_calls(self):
        items = [(f"k{i}", f"sig{i}") for i in range(45)]  # > batch size 40
        provider = mock_provider('{"0": "Income"}')
        with patch("wallets.ai.get_provider", return_value=provider):
            categorize_signatures(self.user, items, self.names)
        self.assertEqual(provider.complete.call_count, 2)

    def test_quota_exceeded_returns_partial(self):
        from wallets.ai import QuotaExceededError
        items = [(f"k{i}", f"sig{i}") for i in range(80)]
        provider = MagicMock()
        provider.complete.side_effect = [
            LLMResponse(content='{"0": "Groceries"}', input_tokens=50, output_tokens=10),
            QuotaExceededError("over"),
        ]
        with patch("wallets.ai.get_provider", return_value=provider):
            mapping, warning, quota = categorize_signatures(self.user, items, self.names)
        self.assertTrue(quota)
        self.assertIn("k0", mapping)

    def test_malformed_json_is_safe(self):
        with patch("wallets.ai.get_provider", return_value=mock_provider("sorry, no JSON here")):
            mapping, _, _ = categorize_signatures(self.user, [("k0", "x")], self.names)
        self.assertEqual(mapping, {})

    def test_empty_items_makes_no_calls(self):
        provider = mock_provider("{}")
        with patch("wallets.ai.get_provider", return_value=provider):
            mapping, warning, quota = categorize_signatures(self.user, [], self.names)
        self.assertEqual(mapping, {})
        self.assertFalse(quota)
        self.assertEqual(provider.complete.call_count, 0)
