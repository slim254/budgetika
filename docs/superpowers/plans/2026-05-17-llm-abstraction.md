# LLM Abstraction & Usage Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a provider-agnostic LLM abstraction layer with per-user monthly token quotas, cost tracking, and admin observability — starting with Anthropic as the only provider.

**Architecture:** A `LLMProvider` protocol and `AnthropicAdapter` live in `wallets/ai.py`. All AI features call `AIService.complete()`, which enforces quotas, logs every call to `AIUsageLog`, and returns a usage warning when the user crosses a configured threshold. Token pricing is stored in `ModelPricing` rows with `valid_from` dates so price changes are non-destructive. A global DRF exception handler converts `QuotaExceededError` to HTTP 429.

**Tech Stack:** Django 5.1, DRF, Anthropic Python SDK (`anthropic`), SQLite (dev).

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/config/settings.py` | Modify | AI settings block (provider, models, quotas, thresholds, API key) |
| `backend/requirements.txt` | Modify | Add `anthropic` SDK |
| `backend/wallets/models.py` | Modify | Add `AIUsageLog`, `ModelPricing`, `UserAIQuota` |
| `backend/wallets/migrations/` | Generated | New migration for 3 new models |
| `backend/wallets/ai.py` | Create | `LLMResponse`, `LLMProvider` protocol, `AnthropicAdapter`, `AIService`, `quota_exception_handler` |
| `backend/wallets/views.py` | Modify | Add `AIQuotaView` |
| `backend/wallets/admin.py` | Modify | Register 3 new models with list display and filters |
| `backend/config/urls.py` | Modify | Wire `GET /api/ai/quota/` |
| `backend/tests/wallets/test_ai.py` | Create | Tests for models, AIService, exception handler, quota endpoint |

---

## Task 1: AI Settings and Anthropic Dependency

**Files:**
- Modify: `backend/config/settings.py`
- Modify: `backend/requirements.txt`

No tests for configuration.

- [ ] **Step 1: Add AI settings block to `backend/config/settings.py`**

Add `import os` at the top of the file (after existing imports), then append at the end:

```python
# AI / LLM settings
AI_DEFAULT_PROVIDER = "anthropic"
AI_DEFAULT_MONTHLY_TOKENS = 500_000
AI_WARN_THRESHOLDS = [80, 95]  # percent

AI_MODELS = {
    "auto_categorize": "claude-haiku-4-5-20251001",
    "receipt_scan": "claude-sonnet-4-6",
    "budget_recommendations": "claude-haiku-4-5-20251001",
    "chat": "claude-sonnet-4-6",
}

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
```

- [ ] **Step 2: Add `anthropic` to `backend/requirements.txt`**

Append:
```
anthropic
```

- [ ] **Step 3: Install the package**

```bash
cd backend && source venv/bin/activate
pip install anthropic
pip freeze | grep anthropic
```

Expected output: a line like `anthropic==0.x.x`

Update `requirements.txt` with the pinned version from that output.

- [ ] **Step 4: Commit**

```bash
git add backend/config/settings.py backend/requirements.txt
git commit -m "chore: add AI settings and anthropic dependency"
```

---

## Task 2: Django Models

**Files:**
- Modify: `backend/wallets/models.py`
- Create: `backend/tests/wallets/test_ai.py`
- Generated: `backend/wallets/migrations/`

- [ ] **Step 1: Create `backend/tests/wallets/test_ai.py` with failing model tests**

```python
from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from wallets.models import AIUsageLog, ModelPricing, UserAIQuota


class TestModelPricing(TestCase):
    def test_get_current_returns_most_recent_valid_row(self):
        ModelPricing.objects.create(
            provider="anthropic", model="claude-haiku-4-5-20251001",
            input_cost=Decimal("0.25"), output_cost=Decimal("1.25"),
            valid_from=date(2025, 1, 1),
        )
        ModelPricing.objects.create(
            provider="anthropic", model="claude-haiku-4-5-20251001",
            input_cost=Decimal("0.20"), output_cost=Decimal("1.00"),
            valid_from=date(2026, 1, 1),
        )
        pricing = ModelPricing.get_current("anthropic", "claude-haiku-4-5-20251001")
        self.assertEqual(pricing.input_cost, Decimal("0.20"))

    def test_get_current_returns_none_when_no_matching_pricing(self):
        result = ModelPricing.get_current("anthropic", "unknown-model")
        self.assertIsNone(result)


class TestAIUsageLog(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="loguser", password="pass")

    def test_create_log_entry_without_cost(self):
        log = AIUsageLog.objects.create(
            user=self.user,
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
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
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && source venv/bin/activate
python manage.py test tests.wallets.test_ai -v 2
```

Expected: `ImportError: cannot import name 'AIUsageLog' from 'wallets.models'`

- [ ] **Step 3: Add models to the end of `backend/wallets/models.py`**

```python
class ModelPricing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=50)
    model = models.CharField(max_length=100)
    input_cost = models.DecimalField(max_digits=12, decimal_places=8)
    output_cost = models.DecimalField(max_digits=12, decimal_places=8)
    valid_from = models.DateField()

    class Meta:
        ordering = ["-valid_from"]
        unique_together = [["provider", "model", "valid_from"]]

    @classmethod
    def get_current(cls, provider: str, model: str):
        from django.utils import timezone
        today = timezone.now().date()
        return (
            cls.objects.filter(provider=provider, model=model, valid_from__lte=today)
            .order_by("-valid_from")
            .first()
        )


FEATURE_CHOICES = [
    ("auto_categorize", "Auto Categorize"),
    ("receipt_scan", "Receipt Scan"),
    ("budget_recommendations", "Budget Recommendations"),
    ("chat", "Chat"),
]


class AIUsageLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_usage_logs")
    provider = models.CharField(max_length=50)
    model = models.CharField(max_length=100)
    feature = models.CharField(max_length=50, choices=FEATURE_CHOICES)
    input_tokens = models.PositiveIntegerField()
    output_tokens = models.PositiveIntegerField()
    cost_usd = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class UserAIQuota(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="ai_quota")
    monthly_token_limit = models.PositiveIntegerField(null=True, blank=True)
```

- [ ] **Step 4: Create and run migration**

```bash
cd backend && source venv/bin/activate
python manage.py makemigrations
python manage.py migrate
```

Expected: migration created and applied with no errors.

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python manage.py test tests.wallets.test_ai -v 2
```

Expected: `Ran 6 tests in Xs ... OK`

- [ ] **Step 6: Commit**

```bash
git add backend/wallets/models.py backend/wallets/migrations/ backend/tests/wallets/test_ai.py
git commit -m "feat: add AIUsageLog, ModelPricing, UserAIQuota models"
```

---

## Task 3: AI Service

**Files:**
- Create: `backend/wallets/ai.py`
- Modify: `backend/config/settings.py` (add exception handler)
- Modify: `backend/tests/wallets/test_ai.py`

- [ ] **Step 1: Add new imports to the top of `backend/tests/wallets/test_ai.py`**

Add these lines after the existing imports at the top of the file:

```python
from unittest.mock import patch, MagicMock

from django.test import override_settings

from wallets.ai import AIService, LLMResponse, QuotaExceededError, quota_exception_handler
```

- [ ] **Step 2: Append the following test classes to `backend/tests/wallets/test_ai.py`**

```python
MOCK_RESPONSE = LLMResponse(content="Food & Dining", input_tokens=100, output_tokens=20)


def mock_provider():
    provider = MagicMock()
    provider.complete.return_value = MOCK_RESPONSE
    return provider


@override_settings(
    AI_DEFAULT_PROVIDER="anthropic",
    AI_DEFAULT_MONTHLY_TOKENS=1000,
    AI_WARN_THRESHOLDS=[80, 95],
    AI_MODELS={"auto_categorize": "claude-haiku-4-5-20251001"},
    ANTHROPIC_API_KEY="test-key",
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
        self.assertEqual(log.provider, "anthropic")
        self.assertEqual(log.model, "claude-haiku-4-5-20251001")

    def test_complete_raises_when_quota_exceeded(self):
        AIUsageLog.objects.create(
            user=self.user, provider="anthropic", model="claude-haiku-4-5-20251001",
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
            user=self.user, provider="anthropic", model="claude-haiku-4-5-20251001",
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
            provider="anthropic", model="claude-haiku-4-5-20251001",
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
            user=self.user, provider="anthropic", model="claude-haiku-4-5-20251001",
            feature="auto_categorize", input_tokens=50, output_tokens=0,
        )
        with patch("wallets.ai.get_provider", return_value=mock_provider()):
            with self.assertRaises(QuotaExceededError):
                self.service.complete(
                    self.user, "auto_categorize", [{"role": "user", "content": "coffee"}]
                )

    def test_get_quota_status_returns_correct_data(self):
        AIUsageLog.objects.create(
            user=self.user, provider="anthropic", model="claude-haiku-4-5-20251001",
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && source venv/bin/activate
python manage.py test tests.wallets.test_ai.TestAIService tests.wallets.test_ai.TestQuotaExceptionHandler -v 2
```

Expected: `ImportError: cannot import name 'AIService' from 'wallets.ai'` (file doesn't exist yet)

- [ ] **Step 3: Create `backend/wallets/ai.py`**

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .models import AIUsageLog, ModelPricing, UserAIQuota


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int


class QuotaExceededError(Exception):
    pass


@runtime_checkable
class LLMProvider(Protocol):
    def complete(self, messages: list[dict], model: str) -> LLMResponse: ...


class AnthropicAdapter:
    def complete(self, messages: list[dict], model: str) -> LLMResponse:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=messages,
        )
        return LLMResponse(
            content=response.content[0].text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


_PROVIDERS: dict[str, LLMProvider] = {
    "anthropic": AnthropicAdapter(),
}


def get_provider(name: str) -> LLMProvider:
    if name not in _PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {name}")
    return _PROVIDERS[name]


def register_provider(name: str, provider: LLMProvider) -> None:
    _PROVIDERS[name] = provider


def quota_exception_handler(exc, context):
    if isinstance(exc, QuotaExceededError):
        return Response(
            {"detail": str(exc), "code": "quota_exceeded"},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    return drf_exception_handler(exc, context)


class AIService:
    def _get_monthly_usage(self, user) -> int:
        now = timezone.now()
        result = AIUsageLog.objects.filter(
            user=user,
            created_at__year=now.year,
            created_at__month=now.month,
        ).aggregate(
            input_sum=Sum("input_tokens"),
            output_sum=Sum("output_tokens"),
        )
        return (result["input_sum"] or 0) + (result["output_sum"] or 0)

    def _get_limit(self, user) -> int:
        try:
            quota = user.ai_quota
            if quota.monthly_token_limit is not None:
                return quota.monthly_token_limit
        except UserAIQuota.DoesNotExist:
            pass
        return settings.AI_DEFAULT_MONTHLY_TOKENS

    def _compute_cost(
        self, provider: str, model: str, input_tokens: int, output_tokens: int
    ) -> Decimal | None:
        pricing = ModelPricing.get_current(provider, model)
        if pricing is None:
            return None
        cost = (
            Decimal(input_tokens) * pricing.input_cost / Decimal("1000000")
            + Decimal(output_tokens) * pricing.output_cost / Decimal("1000000")
        )
        return cost.quantize(Decimal("0.00000001"))

    def _check_warning(self, used: int, limit: int) -> dict | None:
        if limit == 0:
            return None
        percent_used = int(used * 100 / limit)
        for threshold in sorted(settings.AI_WARN_THRESHOLDS, reverse=True):
            if percent_used >= threshold:
                return {"percent_used": percent_used, "threshold": threshold}
        return None

    def get_quota_status(self, user) -> dict:
        now = timezone.now()
        used = self._get_monthly_usage(user)
        limit = self._get_limit(user)
        percent_used = int(used * 100 / limit) if limit > 0 else 0
        return {
            "used_tokens": used,
            "limit_tokens": limit,
            "percent_used": percent_used,
            "month": now.strftime("%Y-%m"),
        }

    def complete(
        self,
        user,
        feature: str,
        messages: list[dict],
        model: str | None = None,
        provider: str | None = None,
    ) -> tuple[LLMResponse, dict | None]:
        provider = provider or settings.AI_DEFAULT_PROVIDER
        model = model or settings.AI_MODELS.get(feature, "claude-haiku-4-5-20251001")

        used = self._get_monthly_usage(user)
        limit = self._get_limit(user)

        if used >= limit:
            raise QuotaExceededError(f"Monthly token quota of {limit:,} exceeded.")

        llm = get_provider(provider)
        response = llm.complete(messages, model)

        cost = self._compute_cost(provider, model, response.input_tokens, response.output_tokens)

        AIUsageLog.objects.create(
            user=user,
            provider=provider,
            model=model,
            feature=feature,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=cost,
        )

        new_used = used + response.input_tokens + response.output_tokens
        warning = self._check_warning(new_used, limit)

        return response, warning


ai_service = AIService()
```

- [ ] **Step 4: Add `EXCEPTION_HANDLER` to `REST_FRAMEWORK` in `backend/config/settings.py`**

Find the existing `REST_FRAMEWORK` dict and add the exception handler key:

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'EXCEPTION_HANDLER': 'wallets.ai.quota_exception_handler',
}
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python manage.py test tests.wallets.test_ai.TestAIService tests.wallets.test_ai.TestQuotaExceptionHandler -v 2
```

Expected: `Ran 10 tests in Xs ... OK`

- [ ] **Step 6: Commit**

```bash
git add backend/wallets/ai.py backend/config/settings.py backend/tests/wallets/test_ai.py
git commit -m "feat: add AIService, AnthropicAdapter, and quota exception handler"
```

---

## Task 4: AI Quota Endpoint

**Files:**
- Modify: `backend/wallets/views.py`
- Modify: `backend/config/urls.py`
- Modify: `backend/tests/wallets/test_ai.py`

- [ ] **Step 1: Add new imports to the top of `backend/tests/wallets/test_ai.py`**

Add after the existing imports at the top of the file:

```python
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
```

- [ ] **Step 2: Append quota endpoint tests to `backend/tests/wallets/test_ai.py`**

```python
def make_auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


@override_settings(
    AI_DEFAULT_MONTHLY_TOKENS=1000,
    AI_WARN_THRESHOLDS=[80, 95],
    ANTHROPIC_API_KEY="test-key",
)
class TestAIQuotaEndpoint(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="endpoint_user", password="pass")
        self.client = make_auth_client(self.user)

    def test_returns_current_usage_and_limit(self):
        AIUsageLog.objects.create(
            user=self.user, provider="anthropic", model="claude-haiku-4-5-20251001",
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
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
python manage.py test tests.wallets.test_ai.TestAIQuotaEndpoint -v 2
```

Expected: `AssertionError: 404 != 200` (URL not wired yet)

- [ ] **Step 4: Add `AIQuotaView` to `backend/wallets/views.py`**

Add the import near the top with the existing service imports:
```python
from .ai import ai_service
```

Add the view class at the end of the file:
```python
class AIQuotaView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        return Response(ai_service.get_quota_status(request.user))
```

- [ ] **Step 5: Wire the URL in `backend/config/urls.py`**

Add `AIQuotaView` to the existing import from `wallets.views`:
```python
from wallets.views import (
    TransactionCreate, TransactionDetail, UserDashboard,
    ExchangeRateView, UserProfileView, AIQuotaView,
)
```

Add to `urlpatterns`:
```python
path('api/ai/quota/', AIQuotaView.as_view(), name='ai-quota'),
```

- [ ] **Step 6: Run the full test suite to confirm all tests pass**

```bash
python manage.py test tests.wallets.test_ai -v 2
```

Expected: `Ran 19 tests in Xs ... OK`

- [ ] **Step 7: Commit**

```bash
git add backend/wallets/views.py backend/config/urls.py backend/tests/wallets/test_ai.py
git commit -m "feat: add GET /api/ai/quota/ endpoint"
```

---

## Task 5: Admin Registration

**Files:**
- Modify: `backend/wallets/admin.py`

No TDD needed — Django admin correctness is verified by `manage.py check`.

- [ ] **Step 1: Replace `backend/wallets/admin.py` with**

```python
from django.contrib import admin

from .models import (
    Transaction,
    Wallet,
    TransactionCategory,
    UserTransactionTag,
    RecurringTransaction,
    RecurringTransactionExecution,
    AIUsageLog,
    ModelPricing,
    UserAIQuota,
)

admin.site.register(Transaction)
admin.site.register(Wallet)
admin.site.register(TransactionCategory)
admin.site.register(UserTransactionTag)
admin.site.register(RecurringTransaction)
admin.site.register(RecurringTransactionExecution)


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "model", "feature", "input_tokens", "output_tokens", "cost_usd", "created_at")
    list_filter = ("provider", "feature")
    search_fields = ("user__username", "user__email")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(ModelPricing)
class ModelPricingAdmin(admin.ModelAdmin):
    list_display = ("provider", "model", "input_cost", "output_cost", "valid_from")
    ordering = ("provider", "-valid_from")


@admin.register(UserAIQuota)
class UserAIQuotaAdmin(admin.ModelAdmin):
    list_display = ("user", "monthly_token_limit_display")

    def monthly_token_limit_display(self, obj):
        return obj.monthly_token_limit if obj.monthly_token_limit is not None else "default"
    monthly_token_limit_display.short_description = "Monthly Token Limit"
```

- [ ] **Step 2: Verify with system check**

```bash
cd backend && source venv/bin/activate
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add backend/wallets/admin.py
git commit -m "feat: register AI models in Django admin"
```

---

## Usage After Implementation

**Adding initial token prices via Django admin** (`/admin`):

Create a `ModelPricing` row for each model before first use. Example (Claude Haiku as of 2025):
- Provider: `anthropic`, Model: `claude-haiku-4-5-20251001`
- Input cost: `0.80` (per 1M tokens), Output cost: `4.00` (per 1M tokens)
- Valid from: today's date

**Calling `AIService` from a new AI feature view:**

```python
from .ai import ai_service, QuotaExceededError

# In a view's post() method:
response, warning = ai_service.complete(
    user=request.user,
    feature="auto_categorize",
    messages=[{"role": "user", "content": note_text}],
)
# QuotaExceededError is handled globally → HTTP 429
# warning is None or {"percent_used": 83, "threshold": 80}
return Response({"suggestion": response.content, "usage_warning": warning})
```
