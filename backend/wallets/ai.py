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


class OpenAIAdapter:
    def complete(self, messages: list[dict], model: str) -> LLMResponse:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        # NOTE: gpt-4o / gpt-4o-mini accept `max_tokens`. If you later switch a
        # feature to an o-series reasoning model, rename this to
        # `max_completion_tokens` (those models reject `max_tokens`).
        response = client.chat.completions.create(
            model=model,
            max_tokens=1024,
            messages=messages,
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )


_PROVIDERS: dict[str, LLMProvider] = {
    "openai": OpenAIAdapter(),
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
        model = model or settings.AI_MODELS.get(feature, "gpt-4o-mini")

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


import json
import re


def _parse_json_map(content: str) -> dict:
    """Extract the first {...} block and parse it; return {} on any failure."""
    if not content:
        return {}
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def categorize_signatures(user, items, category_names, feature="auto_categorize", batch_size=None):
    """Batch-categorize unique transaction signatures against the user's existing categories.

    Args:
        items: list of (key, signature) tuples — one per UNIQUE description.
        category_names: allowed category names (existing, visible).

    Returns:
        (mapping, warning, quota_exceeded)
        mapping: {key: canonical_category_name} — only keys the model mapped to a
                 real existing category are present (Uncategorized/invalid omitted).
        warning: last usage_warning dict from ai_service, or None.
        quota_exceeded: True if the monthly quota ran out mid-batch (partial result).
    """
    batch_size = batch_size or settings.AI_IMPORT_BATCH_SIZE
    valid = {n.lower(): n for n in category_names}
    result: dict[str, str] = {}
    warning = None
    quota_exceeded = False

    for start in range(0, len(items), batch_size):
        batch = items[start:start + batch_size]
        listing = "\n".join(f"{i}. {sig}" for i, (_, sig) in enumerate(batch))
        system = (
            "You categorize personal-finance transactions. For each numbered "
            "transaction below, choose EXACTLY ONE category name verbatim from this "
            "list, or 'Uncategorized' if none clearly fit.\n"
            f"Categories: {', '.join(category_names) if category_names else '(none)'}\n"
            'Reply ONLY with a JSON object mapping each number (as a string) to a '
            'category name, e.g. {"0": "Groceries", "1": "Uncategorized"}.'
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": listing},
        ]
        try:
            response, warning = ai_service.complete(user, feature, messages)
        except QuotaExceededError:
            quota_exceeded = True
            break

        for idx_str, name in _parse_json_map(response.content).items():
            try:
                idx = int(idx_str)
            except (ValueError, TypeError):
                continue
            if 0 <= idx < len(batch):
                canonical = valid.get(str(name).strip().lower())
                if canonical:
                    result[batch[idx][0]] = canonical

    return result, warning, quota_exceeded
