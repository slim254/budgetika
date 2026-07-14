from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from wallets.models import AIUsageLog, ModelPricing, UserAIQuota

from unittest.mock import patch, MagicMock

from django.test import override_settings

from wallets.ai import AIService, LLMResponse, QuotaExceededError, quota_exception_handler

from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


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


MOCK_RESPONSE = LLMResponse(content="Food & Dining", input_tokens=100, output_tokens=20)


def mock_provider():
    provider = MagicMock()
    provider.complete.return_value = MOCK_RESPONSE
    return provider


@override_settings(
    AI_DEFAULT_PROVIDER="openai",
    AI_DEFAULT_MONTHLY_TOKENS=1000,
    AI_WARN_THRESHOLDS=[80, 95],
    AI_MODELS={"auto_categorize": "gpt-4o-mini"},
    OPENAI_API_KEY="test-key",
)
class TestAIService(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="aiservice_user", password="pass")
        self.service = AIService()

    def _call(self):
        with patch("wallets.ai.get_provider", return_value=mock_provider()):
            return self.service.complete(
                self.user, "auto_categorize", [{"role": "user", "content": "coffee"}]
            )

    def test_complete_creates_usage_log(self):
        self._call()
        log = AIUsageLog.objects.get(user=self.user)
        self.assertEqual(log.input_tokens, 100)
        self.assertEqual(log.output_tokens, 20)
        self.assertEqual(log.feature, "auto_categorize")
        self.assertEqual(log.provider, "openai")
        self.assertEqual(log.model, "gpt-4o-mini")

    def test_complete_raises_when_quota_exceeded(self):
        AIUsageLog.objects.create(
            user=self.user, provider="openai", model="gpt-4o-mini",
            feature="auto_categorize", input_tokens=1000, output_tokens=0,
        )
        with patch("wallets.ai.get_provider", return_value=mock_provider()):
            with self.assertRaises(QuotaExceededError):
                self.service.complete(
                    self.user, "auto_categorize", [{"role": "user", "content": "coffee"}]
                )

    def test_complete_returns_warning_when_usage_crosses_threshold(self):
        # Pre-load 750 tokens (75%); call adds 120 → 870/1000 = 87% → triggers 80% threshold
        AIUsageLog.objects.create(
            user=self.user, provider="openai", model="gpt-4o-mini",
            feature="auto_categorize", input_tokens=750, output_tokens=0,
        )
        _, warning = self._call()
        self.assertIsNotNone(warning)
        self.assertEqual(warning["threshold"], 80)
        self.assertEqual(warning["percent_used"], 87)

    def test_complete_returns_no_warning_below_threshold(self):
        _, warning = self._call()
        self.assertIsNone(warning)

    def test_complete_computes_cost_from_model_pricing(self):
        ModelPricing.objects.create(
            provider="openai", model="gpt-4o-mini",
            input_cost=Decimal("0.25"), output_cost=Decimal("1.25"),
            valid_from=date(2025, 1, 1),
        )
        self._call()
        log = AIUsageLog.objects.get(user=self.user)
        # 100 * 0.25 / 1_000_000 + 20 * 1.25 / 1_000_000 = 0.000025 + 0.000025 = 0.00005
        self.assertEqual(log.cost_usd, Decimal("0.00005000"))

    def test_complete_sets_null_cost_when_no_pricing(self):
        self._call()
        log = AIUsageLog.objects.get(user=self.user)
        self.assertIsNone(log.cost_usd)

    def test_complete_respects_per_user_quota(self):
        UserAIQuota.objects.create(user=self.user, monthly_token_limit=50)
        AIUsageLog.objects.create(
            user=self.user, provider="openai", model="gpt-4o-mini",
            feature="auto_categorize", input_tokens=50, output_tokens=0,
        )
        with patch("wallets.ai.get_provider", return_value=mock_provider()):
            with self.assertRaises(QuotaExceededError):
                self.service.complete(
                    self.user, "auto_categorize", [{"role": "user", "content": "coffee"}]
                )

    def test_get_quota_status_returns_correct_data(self):
        AIUsageLog.objects.create(
            user=self.user, provider="openai", model="gpt-4o-mini",
            feature="auto_categorize", input_tokens=300, output_tokens=100,
        )
        status = self.service.get_quota_status(self.user)
        self.assertEqual(status["used_tokens"], 400)
        self.assertEqual(status["limit_tokens"], 1000)
        self.assertEqual(status["percent_used"], 40)
        self.assertIn("month", status)


class TestQuotaExceptionHandler(TestCase):
    def test_returns_429_for_quota_exceeded_error(self):
        response = quota_exception_handler(QuotaExceededError("Quota exceeded"), {})
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data["code"], "quota_exceeded")

    def test_delegates_other_exceptions_to_drf_default_handler(self):
        from rest_framework.exceptions import NotFound
        response = quota_exception_handler(NotFound(), {})
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 404)


def make_auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


@override_settings(
    AI_DEFAULT_MONTHLY_TOKENS=1000,
    AI_WARN_THRESHOLDS=[80, 95],
    OPENAI_API_KEY="test-key",
)
class TestAIQuotaEndpoint(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="endpoint_user", password="pass")
        self.client = make_auth_client(self.user)

    def test_returns_current_usage_and_limit(self):
        AIUsageLog.objects.create(
            user=self.user, provider="openai", model="gpt-4o-mini",
            feature="auto_categorize", input_tokens=300, output_tokens=100,
        )
        response = self.client.get("/api/ai/quota/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["used_tokens"], 400)
        self.assertEqual(response.data["limit_tokens"], 1000)
        self.assertEqual(response.data["percent_used"], 40)
        self.assertIn("month", response.data)

    def test_returns_zero_when_no_logs_exist(self):
        response = self.client.get("/api/ai/quota/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["used_tokens"], 0)
        self.assertEqual(response.data["percent_used"], 0)

    def test_requires_authentication(self):
        unauthenticated = APIClient()
        response = unauthenticated.get("/api/ai/quota/")
        self.assertEqual(response.status_code, 401)
