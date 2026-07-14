from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from wallets.models import AIUsageLog, ModelPricing, UserAIQuota


class TestModelPricing(TestCase):
    def test_get_current_returns_most_recent_valid_row(self):
        ModelPricing.objects.create(
            provider="openai", model="gpt-4o-mini",
            input_cost=Decimal("0.25"), output_cost=Decimal("1.25"),
            valid_from=date(2025, 1, 1),
        )
        ModelPricing.objects.create(
            provider="openai", model="gpt-4o-mini",
            input_cost=Decimal("0.20"), output_cost=Decimal("1.00"),
            valid_from=date(2026, 1, 1),
        )
        pricing = ModelPricing.get_current("openai", "gpt-4o-mini")
        self.assertEqual(pricing.input_cost, Decimal("0.20"))

    def test_get_current_returns_none_when_no_matching_pricing(self):
        result = ModelPricing.get_current("openai", "unknown-model")
        self.assertIsNone(result)


class TestAIUsageLog(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="loguser", password="pass")

    def test_create_log_entry_without_cost(self):
        log = AIUsageLog.objects.create(
            user=self.user,
            provider="openai",
            model="gpt-4o-mini",
            feature="auto_categorize",
            input_tokens=100,
            output_tokens=50,
        )
        self.assertEqual(log.input_tokens, 100)
        self.assertEqual(log.output_tokens, 50)
        self.assertIsNone(log.cost_usd)
        self.assertIsNotNone(log.created_at)
        self.assertEqual(len(str(log.id)), 36)

    def test_create_log_entry_with_cost(self):
        log = AIUsageLog.objects.create(
            user=self.user,
            provider="openai",
            model="gpt-4o-mini",
            feature="auto_categorize",
            input_tokens=100,
            output_tokens=50,
            cost_usd=Decimal("0.00005000"),
        )
        self.assertEqual(log.cost_usd, Decimal("0.00005000"))


class TestUserAIQuota(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="quotauser2", password="pass")

    def test_monthly_token_limit_defaults_to_null(self):
        quota = UserAIQuota.objects.create(user=self.user)
        self.assertIsNone(quota.monthly_token_limit)

    def test_can_set_custom_limit(self):
        quota = UserAIQuota.objects.create(user=self.user, monthly_token_limit=100_000)
        self.assertEqual(quota.monthly_token_limit, 100_000)
