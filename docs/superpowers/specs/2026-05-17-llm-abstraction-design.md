# LLM Abstraction & Usage Tracking

**Date:** 2026-05-17
**Status:** Approved

## Overview

A provider-agnostic LLM abstraction layer for the budgeting app's AI features, with per-user monthly token quotas, cost tracking, and admin observability. First implementation ships with Anthropic only; additional providers are added by dropping in a new adapter class.

## Data Model

### `AIUsageLog`
One row per LLM call.

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | auto |
| user | FK → User | |
| provider | str | `"anthropic"` \| `"openai"` \| `"gemini"` \| `"deepseek"` |
| model | str | e.g. `"claude-sonnet-4-6"` |
| feature | str | `"auto_categorize"` \| `"receipt_scan"` \| `"budget_recommendations"` \| `"chat"` |
| input_tokens | int | |
| output_tokens | int | |
| cost_usd | Decimal | computed at call time from `ModelPricing` |
| created_at | datetime | auto |

### `ModelPricing`
Tracks historical token prices. New row on price change — never update existing rows.

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | auto |
| provider | str | |
| model | str | |
| input_cost | Decimal | per 1M tokens |
| output_cost | Decimal | per 1M tokens |
| valid_from | date | most recent row where `valid_from <= today` wins |

### `UserAIQuota`
Per-user monthly limit override. Created on demand.

| Field | Type | Notes |
|---|---|---|
| id | UUID PK | auto |
| user | OneToOne → User | |
| monthly_token_limit | int, nullable | null = use `settings.AI_DEFAULT_MONTHLY_TOKENS` |

Monthly usage is always computed live from `AIUsageLog` — no stored rollup.

## Settings

```python
AI_DEFAULT_PROVIDER = "anthropic"
AI_DEFAULT_MONTHLY_TOKENS = 500_000
AI_WARN_THRESHOLDS = [80, 95]  # percent

AI_MODELS = {
    "auto_categorize": "claude-haiku-4-5",
    "receipt_scan": "claude-sonnet-4-6",
    "budget_recommendations": "claude-haiku-4-5",
    "chat": "claude-sonnet-4-6",
}
```

## Abstraction Layer (`wallets/ai.py`)

### Protocol & response type

```python
@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int

class LLMProvider(Protocol):
    def complete(self, messages: list[dict], model: str) -> LLMResponse: ...
```

### Adapters

One class per provider. First implementation: `AnthropicAdapter` only. Each adapter wraps the provider SDK and maps the response to `LLMResponse`.

A provider registry (`dict[str, LLMProvider]`) is populated at app startup from `settings.AI_DEFAULT_PROVIDER`.

### `AIService`

Single entry point for all AI features:

```python
ai_service.complete(user, feature, messages) -> tuple[LLMResponse, usage_warning]
```

Internally:
1. Compute current month token usage from `AIUsageLog`
2. Fetch limit from `UserAIQuota` (fallback to `settings.AI_DEFAULT_MONTHLY_TOKENS`)
3. If `used >= limit` → raise `QuotaExceededError`
4. Look up current `ModelPricing` for provider + model
5. Call adapter
6. Log to `AIUsageLog` with computed `cost_usd`
7. Re-check usage → if crossed a warn threshold, set `usage_warning`

`usage_warning` shape:
```json
{ "percent_used": 83, "threshold": 80 }
```

## API

### Existing AI feature endpoints
All AI feature views return `usage_warning` alongside their result:
```json
{ "suggestion": "...", "usage_warning": { "percent_used": 83, "threshold": 80 } }
```
`usage_warning` is `null` when no threshold has been crossed. Frontend shows a toast when it is present. `HTTP 429` is returned when quota is exceeded.

### New endpoint
```
GET /api/ai/quota/
```
Returns current month's usage for the authenticated user:
```json
{ "used_tokens": 415000, "limit_tokens": 500000, "percent_used": 83, "month": "2026-05" }
```

## Admin Observability

Three models registered in `wallets/admin.py`:

- **`AIUsageLog`** — list display: user, provider, model, feature, tokens, cost_usd, created_at; filters: provider, feature, month; search: user email
- **`ModelPricing`** — list display: provider, model, input_cost, output_cost, valid_from; ordered by provider + valid_from descending
- **`UserAIQuota`** — list display: user, monthly_token_limit (shows "default" when null)

## Files Changed

| File | Change |
|---|---|
| `wallets/models.py` | Add `AIUsageLog`, `ModelPricing`, `UserAIQuota` |
| `wallets/migrations/` | New migration |
| `wallets/ai.py` | New file: protocol, `AnthropicAdapter`, `AIService` |
| `wallets/admin.py` | Register 3 new models |
| `wallets/views.py` | Add `GET /api/ai/quota/` view |
| `wallets/urls.py` | Wire up quota endpoint |
| `config/settings.py` | Add AI settings block |
| `requirements.txt` | Add `anthropic` SDK |

## Out of Scope

- Frontend quota warning UI (toast wiring is a frontend concern handled per AI feature)
- Subscription model / tiered limits (monthly_token_limit is nullable; future subscription feature sets it)
- Additional provider adapters beyond Anthropic (stubbed by the protocol, added when needed)
- Streaming responses (not needed for any current AI feature)
