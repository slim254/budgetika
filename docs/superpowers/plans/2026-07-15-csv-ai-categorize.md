# CSV Import — AI Auto-categorization (whole-row) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (or subagent-driven-development). Backend is TDD with a **mocked LLM** — never hit the real OpenAI API in tests. Steps use checkboxes (`- [ ]`).

**Goal:** During CSV import, let the AI assign each transaction one of the user's **existing** categories, using the **entire CSV row** as context (not only the mapped fields). The user reviews one suggestion per *unique* transaction description (deduplicated) and can override any before importing.

**Why a new plan (vs. B3b):** B3b built a single-note `POST /api/wallets/categorize/` used live in `TransactionDialog`. This feature is **batched, deduplicated, whole-row, and import-scoped** with a review-and-override UX. It reuses the B3a AI layer (`ai_service`) and the `"auto_categorize"` feature key — **no new models or migrations**.

**Tech Stack:** Django/DRF, OpenAI via the B3a abstraction (`wallets/ai.py`), Next.js 15, shadcn/ui, `sonner`.

---

## Product decisions (locked)

1. **Constrain to existing categories.** The model may only return a name verbatim from the user's visible, non-archived categories, or `Uncategorized`. It never invents categories.
2. **Only uncategorized rows.** A row keeps its mapped-category value **only if that value matches an existing category** (case-insensitive). Blank or unmatched values → the AI fills them. In AI mode we **do not** auto-create categories from the mapped column (this differs from the legacy import path, which stays unchanged when AI is off).
3. **Review step.** A new optional step between *Filters* and *Review* shows one row per **unique description** with its AI category in an editable dropdown and a count of how many transactions it covers. Overrides cascade to every matching row.
4. **Whole-row context.** Each row's signature is built from **all descriptive columns** (mapped or not), **excluding the mapped date and amount columns** — including those would make every row unique and destroy deduplication. This is the mechanism that delivers "access to the whole row."

---

## Architecture

```
Frontend CSVImportDialog
  Upload → Map → Amount → Filters → [AI Categorize] → Review → Execute
                                         │                        │
                                         ▼                        ▼
        POST /api/wallets/{id}/import/categorize/   POST /api/wallets/{id}/import/execute/
        (file, mapping, amount_config, filters)     (… + ai_categories: {key: category_id})
                                         │
                                         ▼
        GenericCSVImportService.collect_signatures()  ── dedup rows needing AI → unique {key, signature, count}
                                         │
                                         ▼
        wallets.ai.categorize_signatures(user, items, category_names)  ── batches of 40, JSON reply,
                                         │                                 validated against existing names
                                         ▼
                          {key: category_name}  → response suggestions[]
```

**Dedup key:** `key = norm(signature)` where `norm` lowercases and collapses whitespace. The frontend echoes back the (possibly user-edited) `{key: category_id}` map on execute; `_import_row` recomputes each row's key with the **same** code and applies it.

**Token cost:** ~80 unique descriptions ≈ 2 `gpt-4o-mini` calls ≈ well under $0.01/import. Quota, logging, and 80/95% warnings all come free from `ai_service.complete()`.

## Global Constraints

- **DEPENDS ON B3a** (`ai_service`, `LLMResponse`, `QuotaExceededError` in `wallets/ai.py`) — already merged.
- Reuse the **`"auto_categorize"`** feature key (already in `FEATURE_CHOICES` and `AI_MODELS`). No migration.
- **Never fail an import because of AI.** If the quota is exhausted mid-batch, stop calling the AI, import everything with the remaining rows left Uncategorized, and surface `quota_exceeded: true` + a warning.
- Be defensive parsing the model's JSON: a malformed batch reply → treat that batch as all-Uncategorized, don't raise.
- Cap unique signatures per import at `AI_IMPORT_MAX_UNIQUE` (categorize the most frequent first; leave the long tail Uncategorized and report the count).
- Branch: `feat/csv-ai-categorize`.

---

### Task 1: Settings + batch categorizer in `wallets/ai.py`

**Files:**
- Modify: `backend/config/settings.py`
- Modify: `backend/wallets/ai.py`
- Create: `backend/tests/wallets/test_ai_batch_categorize.py`

- [ ] **Step 1: Add settings** (`backend/config/settings.py`, in the AI block near `AI_MODELS`):

```python
AI_IMPORT_BATCH_SIZE = 40      # unique signatures per LLM call
AI_IMPORT_MAX_UNIQUE = 500     # cap on unique descriptions categorized per import
```

- [ ] **Step 2: Write failing tests** in `backend/tests/wallets/test_ai_batch_categorize.py`:

```python
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
```

Run — expect `ImportError` (function not built):
```bash
cd backend && source venv/bin/activate
python manage.py test tests.wallets.test_ai_batch_categorize -v 2
```

- [ ] **Step 3: Implement** in `backend/wallets/ai.py` (append after `ai_service = AIService()`):

```python
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
```

- [ ] **Step 4:** Rerun the tests — expect `OK`.

- [ ] **Step 5: Commit** `feat: batch AI categorizer for CSV import`.

---

### Task 2: Signature/dedup builder in `GenericCSVImportService`

**Files:**
- Modify: `backend/wallets/services.py`
- Create: `backend/tests/wallets/test_import_signatures.py`

**No LLM involved** — pure Python, fast unit tests.

- [ ] **Step 1: Write failing tests** in `backend/tests/wallets/test_import_signatures.py`:

```python
import io
from django.contrib.auth.models import User
from django.test import TestCase
from wallets.models import Wallet
from wallets.services import GenericCSVImportService

CSV = (
    "Date,Amount,Merchant,Title\n"
    "2024-01-01,-45.20,BIEDRONKA 1234,card payment\n"
    "2024-02-03,-12.00,BIEDRONKA 1234,card payment\n"   # same merchant, diff date+amount
    "2024-01-05,5000.00,ACME CORP,salary\n"
)


class TestSignatures(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="s", password="p")
        self.wallet = Wallet.objects.create(user=self.user, name="W", currency="pln")

    def _service(self):
        return GenericCSVImportService(self.user, self.wallet, io.BytesIO(CSV.encode()))

    def test_dedup_excludes_date_and_amount(self):
        svc = self._service()
        mapping = {"amount": "Amount", "date": "Date"}  # no category column
        uniques = svc.collect_signatures(mapping, {"mode": "signed"})
        # The two BIEDRONKA rows collapse into one unique despite different date/amount
        biedronka = [u for u in uniques if "BIEDRONKA" in u["signature"]]
        self.assertEqual(len(biedronka), 1)
        self.assertEqual(biedronka[0]["count"], 2)

    def test_signature_includes_unmapped_columns(self):
        svc = self._service()
        uniques = svc.collect_signatures({"amount": "Amount", "date": "Date"}, {"mode": "signed"})
        sig = next(u["signature"] for u in uniques if "ACME" in u["signature"])
        self.assertIn("salary", sig)      # unmapped "Title" column is present
        self.assertNotIn("5000", sig)     # amount excluded
        self.assertNotIn("2024", sig)     # date excluded
```

- [ ] **Step 2: Implement** in `backend/wallets/services.py`. Add `import re` at top if absent. Add these to `GenericCSVImportService`:

```python
    def _existing_categories(self):
        """Cache the user's real categories: {lowercased name: instance} and {id: instance}."""
        if not hasattr(self, "_cat_by_name"):
            cats = list(
                TransactionCategory.objects.filter(
                    user=self.user, is_archived=False, is_visible=True
                )
            )
            self._cat_by_name = {c.name.lower(): c for c in cats}
            self._cat_by_id = {str(c.id): c for c in cats}
        return self._cat_by_name, self._cat_by_id

    @staticmethod
    def _norm(signature):
        return re.sub(r"\s+", " ", signature).strip().lower()

    def build_signature(self, row, column_mapping):
        """Join all descriptive column values, excluding the mapped date & amount."""
        skip = {column_mapping.get("date"), column_mapping.get("amount")}
        parts = []
        for col in self.columns:
            if col in skip:
                continue
            val = (row.get(col) or "").strip()
            if val:
                parts.append(val)
        return " | ".join(parts)

    def _needs_ai_category(self, row, column_mapping):
        """A row needs AI when it has no mapped category that matches an existing one."""
        by_name, _ = self._existing_categories()
        col = column_mapping.get("category")
        if not col:
            return True
        val = row.get(col, "").strip()
        return not val or val.lower() not in by_name

    def collect_signatures(self, column_mapping, amount_config, filters=None):
        """Return unique descriptions of rows needing AI, most frequent first, capped.

        Each item: {"key", "signature", "count"}.
        """
        if self.rows is None:
            self.columns, self.rows = self._parse_csv()

        groups = {}  # key -> {"signature", "count"}
        for _, row in self.rows:
            if filters and not self._matches_filters(row, filters):
                continue
            if not self._needs_ai_category(row, column_mapping):
                continue
            signature = self.build_signature(row, column_mapping)
            if not signature:
                continue
            key = self._norm(signature)
            if key in groups:
                groups[key]["count"] += 1
            else:
                groups[key] = {"key": key, "signature": signature, "count": 1}

        ordered = sorted(groups.values(), key=lambda g: g["count"], reverse=True)
        from django.conf import settings
        return ordered[: settings.AI_IMPORT_MAX_UNIQUE]
```

- [ ] **Step 3:** Rerun tests — expect `OK`. **Commit** `feat: whole-row signature + dedup for CSV import`.

---

### Task 3: Wire `ai_categories` into `execute` / `_import_row`

**Files:**
- Modify: `backend/wallets/services.py`
- Modify: `backend/tests/wallets/test_import_signatures.py` (add execute tests) or a new file.

- [ ] **Step 1: Add tests** (append to the signatures test file):

```python
    def test_execute_applies_ai_categories(self):
        from wallets.models import TransactionCategory, Transaction
        groc = TransactionCategory.objects.create(user=self.user, name="Groceries")
        svc = self._service()
        mapping = {"amount": "Amount", "date": "Date"}
        uniques = svc.collect_signatures(mapping, {"mode": "signed"})
        key = next(u["key"] for u in uniques if "BIEDRONKA" in u["signature"])
        svc2 = self._service()
        res = svc2.execute(mapping, {"mode": "signed"}, ai_categories={key: str(groc.id)})
        self.assertTrue(res["success"])
        self.assertEqual(Transaction.objects.filter(category=groc).count(), 2)

    def test_ai_mode_does_not_autocreate_from_mapped_column(self):
        from wallets.models import TransactionCategory
        csv = "Date,Amount,Cat\n2024-01-01,-5,Made Up Cat\n"
        svc = GenericCSVImportService(self.user, self.wallet, io.BytesIO(csv.encode()))
        svc.execute({"amount": "Amount", "date": "Date", "category": "Cat"},
                    {"mode": "signed"}, ai_categories={})
        # 'Made Up Cat' does not match an existing category → NOT created in AI mode
        self.assertFalse(TransactionCategory.objects.filter(name="Made Up Cat").exists())
```

- [ ] **Step 2: Modify `execute`** signature and store the map:

```python
    def execute(self, column_mapping, amount_config, filters=None, ai_categories=None):
        # ai_categories is None -> legacy behavior (auto-create from mapped column).
        # ai_categories is a dict (possibly empty) -> AI review mode (no auto-create).
        self.ai_categories = ai_categories
        ...  # (rest unchanged)
```

- [ ] **Step 3: Rework category resolution in `_import_row`.** Replace the current block:

```python
            category_name = None
            if column_mapping.get("category"):
                category_name = row.get(column_mapping["category"], "").strip() or None
            ...
            category = None
            if category_name:
                category = self._get_or_create_category(category_name)
```

with:

```python
            category = self._resolve_category(row, column_mapping)
```

and add the helper:

```python
    def _resolve_category(self, row, column_mapping):
        col = column_mapping.get("category")
        mapped_val = row.get(col, "").strip() if col else ""

        if getattr(self, "ai_categories", None) is None:
            # Legacy flow: auto-create from the mapped column (unchanged behavior).
            return self._get_or_create_category(mapped_val) if mapped_val else None

        # AI review flow.
        by_name, by_id = self._existing_categories()
        if mapped_val and mapped_val.lower() in by_name:
            return by_name[mapped_val.lower()]          # keep matching mapped value
        key = self._norm(self.build_signature(row, column_mapping))
        cat_id = self.ai_categories.get(key)
        return by_id.get(cat_id) if cat_id else None    # AI suggestion, else Uncategorized
```

> Note: `execute` must set `self.ai_categories` **before** the row loop. For the legacy `CSVExecuteView` path that never passes it, default it in `__init__` (`self.ai_categories = None`) so `getattr` is unnecessary — either is fine; keep `__init__` tidy by adding `self.ai_categories = None` there.

- [ ] **Step 4:** Run the full wallets suite — expect `OK`:
```bash
python manage.py test tests.wallets -v 2
```

- [ ] **Step 5: Commit** `feat: apply AI category suggestions during CSV import`.

---

### Task 4: Endpoints — suggest + execute passthrough

**Files:**
- Modify: `backend/wallets/views.py`
- Modify: `backend/wallets/urls.py`
- Create: `backend/tests/wallets/test_import_categorize_api.py`

- [ ] **Step 1: Tests** (mock the provider, assert grouped suggestions + execute passthrough):

```python
# key cases:
# - POST /import/categorize/ returns suggestions[] with {key, signature, count, category_id, category_name}
# - identical descriptions collapse to one suggestion with count == 2
# - a model reply naming a non-existent category yields category_id == None for that row
# - POST /import/execute/ with ai_categories JSON applies the map (Transaction.category set)
# - requires auth (401 without token); wallet must belong to the user (404 otherwise)
```
(Model the auth + mock helpers on `tests/wallets/test_categorize.py`; patch `wallets.ai.get_provider`.)

- [ ] **Step 2: Add `CSVCategorizeView`** to `backend/wallets/views.py`. Import at top: `from .ai import ai_service, categorize_signatures`. Reuse the JSON-field parsing pattern from `CSVExecuteView`:

```python
class CSVCategorizeView(APIView):
    """POST /api/wallets/{wallet_id}/import/categorize/ — AI category suggestions per unique row."""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, wallet_id):
        wallet = get_object_or_404(Wallet, id=wallet_id, user=request.user)

        data = {"file": request.data.get("file")}
        try:
            for field in ("column_mapping", "amount_config", "filters"):
                if field in request.data:
                    data[field] = json.loads(request.data[field])
        except json.JSONDecodeError as e:
            return Response({"error": f"Invalid JSON: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CSVExecuteSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        service = GenericCSVImportService(
            request.user, wallet, serializer.validated_data["file"]
        )
        uniques = service.collect_signatures(
            serializer.validated_data["column_mapping"],
            serializer.validated_data["amount_config"],
            serializer.validated_data.get("filters", []),
        )

        categories = TransactionCategory.objects.filter(
            user=request.user, is_archived=False, is_visible=True
        )
        by_name = {c.name.lower(): c for c in categories}
        names = [c.name for c in categories]

        items = [(u["key"], u["signature"]) for u in uniques]
        mapping, warning, quota_exceeded = categorize_signatures(request.user, items, names)

        suggestions = []
        for u in uniques:
            cat = by_name.get(mapping.get(u["key"], "").lower())
            suggestions.append({
                "key": u["key"],
                "signature": u["signature"],
                "count": u["count"],
                "category_id": str(cat.id) if cat else None,
                "category_name": cat.name if cat else None,
            })

        return Response({
            "suggestions": suggestions,
            "usage_warning": warning,
            "quota_exceeded": quota_exceeded,
        })
```

- [ ] **Step 3: Thread `ai_categories` through `CSVExecuteView`.** In the JSON-parsing block add `ai_categories`, then pass it to `execute`:

```python
        if 'ai_categories' in request.data:
            data['ai_categories'] = json.loads(request.data['ai_categories'])
        ...
        service = GenericCSVImportService(request.user, wallet, csv_file)
        result = service.execute(
            column_mapping, amount_config, filters,
            ai_categories=data.get('ai_categories'),   # None when absent → legacy behavior
        )
```
> `ai_categories` is not part of `CSVExecuteSerializer` (it validates on the strings). Pull it straight from the parsed `data` dict as above. Guard: `isinstance(dict)` before passing; ignore otherwise.

- [ ] **Step 4: URLs** — add `CSVCategorizeView` to the `from .views import (...)` block and register beside the other import routes in `backend/wallets/urls.py`:

```python
    path('<uuid:wallet_id>/import/categorize/', CSVCategorizeView.as_view(), name='csv-categorize'),
```

- [ ] **Step 5:** Run `python manage.py test tests.wallets -v 2` — expect `OK`. **Commit** `feat: CSV import AI-categorize endpoint + execute passthrough`.

---

### Task 5: Frontend — API client + types

**Files:**
- Modify: `frontend/api/ai.ts`
- Modify: `frontend/models/wallets.ts`

- [ ] **Step 1: Types** in `frontend/models/wallets.ts`:

```typescript
export interface ImportCategorySuggestion {
  key: string;
  signature: string;
  count: number;
  category_id: string | null;
  category_name: string | null;
}

export interface ImportCategorizeResponse {
  suggestions: ImportCategorySuggestion[];
  usage_warning: { percent_used: number; threshold: number } | null;
  quota_exceeded: boolean;
}
```

- [ ] **Step 2: Client** in `frontend/api/ai.ts`:

```typescript
import { ImportCategorizeResponse } from "@/models/wallets";

export const suggestImportCategories = (walletId: string, formData: FormData) =>
  axiosInstance.post<ImportCategorizeResponse>(
    `wallets/${walletId}/import/categorize/`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
```
(`formData` carries `file`, `column_mapping`, `amount_config`, `filters` — same shape the execute step already builds.)

---

### Task 6: Frontend — AI Categorize step in `CSVImportDialog`

**Files:** Modify `frontend/components/CSVImportDialog.tsx`.

- [ ] **Step 1: Add the step** to the `Step` type and `STEPS` array, between `filters` and `review`:

```typescript
type Step = "upload" | "mapping" | "amount" | "filters" | "categorize" | "review";
// STEPS: ...{ key: "filters", label: "Filters" }, { key: "categorize", label: "AI Categorize" }, { key: "review", ... }
```

- [ ] **Step 2: State**:

```typescript
const [aiEnabled, setAiEnabled] = useState(true);
const [suggestions, setSuggestions] = useState<ImportCategorySuggestion[]>([]);
const [aiOverrides, setAiOverrides] = useState<Record<string, string>>({}); // key -> category_id ("" = Uncategorized)
const [categories, setCategories] = useState<Category[]>([]);
const [aiLoading, setAiLoading] = useState(false);
const [aiQuotaExceeded, setAiQuotaExceeded] = useState(false);
```
Reset all of these in `resetState()`.

- [ ] **Step 3: Fetch categories** once when the dialog opens (needed to populate override dropdowns):
```typescript
// on open: axiosInstance.get<Category[]>("wallets/categories/") → setCategories(res.data.filter(c => c.is_visible && !c.is_archived))
```

- [ ] **Step 4: Build the shared FormData helper.** Extract the `column_mapping`/`amount_config`/`filters` FormData assembly (currently inline in `handleExecute`) into `buildImportFormData()` so both the suggest call and execute reuse it. `handleExecute` additionally appends `ai_categories`.

- [ ] **Step 5: Fetch suggestions when entering the step** (only if `aiEnabled` and not yet fetched). On success: `setSuggestions`, seed `aiOverrides` from each suggestion's `category_id ?? ""`, set `aiQuotaExceeded`, and `toast.warning` on `usage_warning`. On failure: toast, but allow proceeding (import still works, everything Uncategorized).

- [ ] **Step 6: Render the step**:
  - A toggle at top: "Use AI to categorize uncategorized transactions". When off, skip fetch and send no `ai_categories`.
  - Loading spinner while fetching.
  - If `aiQuotaExceeded`, an amber notice: "AI quota reached — some rows left uncategorized."
  - A table: **Description** (`signature`, truncated) · **# Transactions** (`count`) · **Category** (a `Select` bound to `aiOverrides[key]`, options = all `categories` + an "Uncategorized" option with value `""`).
  - Empty state when `suggestions.length === 0`: "No uncategorized transactions to suggest."

- [ ] **Step 7: Pass overrides to execute.** In `handleExecute`, when `aiEnabled`, append the non-empty overrides:
```typescript
const aiCategories = Object.fromEntries(
  Object.entries(aiOverrides).filter(([, id]) => id) // drop "" (Uncategorized)
);
formData.append("ai_categories", JSON.stringify(aiCategories));
```

- [ ] **Step 8: Navigation.** Add a `Continue` button for the `categorize` step (→ `review`), mirroring the others. The step is skippable (Continue works even with the toggle off / no suggestions).

- [ ] **Step 9: Verify**:
```bash
cd frontend && npm run lint && npm run build
```
Expect no errors.

---

### Task 7: Manual verification + docs

- [ ] **Step 1: Manual check** (backend running with `OPENAI_API_KEY` set; a wallet with a few categories like Groceries/Transport/Income):
  1. Export or craft a bank-style CSV with a merchant column and **no** category column.
  2. Import → map Amount/Date only → Filters → **AI Categorize**: after ~1s a table of unique merchants appears with suggested categories.
  3. Change one dropdown; confirm the **# Transactions** count and that on import every matching row gets the overridden category.
  4. Re-run the same import → duplicate detection skips them (no double categories).
  5. Toggle AI off → import proceeds, all rows Uncategorized. ✔

- [ ] **Step 2: Update `ROADMAP.md`** — add a "CSV AI Auto-categorization (whole-row, batched, review step)" row to the Completed table; note it builds on the LLM Abstraction + B3b auto-categorize.

- [ ] **Step 3: Update `CLAUDE.md` CSV Import section** — mention the optional AI categorize step and the new `POST /api/wallets/{id}/import/categorize/` endpoint (+ the `ai_categories` field on execute).

- [ ] **Step 4: Final commit** `docs: record CSV AI auto-categorization`.

---

## Out of scope (capture as follow-ups)

- **AI proposing new categories** on import (decided against — existing only).
- **Amount/sign as a model hint** (income vs. expense). Could append `(income)`/`(expense)` to signatures later; adds a small dedup split. Not in MVP.
- **OpenAI JSON mode** (`response_format`) — the adapter doesn't expose extra params yet; the defensive regex parser is sufficient. Revisit if malformed replies show up in `AIUsageLog`.
- **Persisting merchant→category mappings** so repeat imports skip the LLM entirely (a local cache would cut cost to ~0 on subsequent months).
