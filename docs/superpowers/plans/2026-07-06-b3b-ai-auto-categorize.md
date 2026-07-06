# B3b — AI Auto-categorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans. Backend is TDD (mocked LLM). Steps use checkbox (`- [ ]`).

**Goal:** When adding a transaction, suggest a category from the user's own categories based on the note text, shown as a one-click chip under the category picker.

**Architecture:** `POST /api/wallets/categorize/` takes a `note`, passes the user's visible category names to the LLM via `AIService.complete()` (from B3a), constrains the model to answer with exactly one existing category name (or `Uncategorized`), maps that name back to a real category id, and returns it plus any quota `usage_warning`. The frontend debounces the note field in create mode and renders the suggestion as a chip.

**Tech Stack:** Django/DRF, OpenAI via the B3a abstraction, Next.js 15, `sonner`.

## Global Constraints

- **DEPENDS ON B3a** (`2026-05-17-llm-abstraction.md`) being merged: this plan imports `ai_service` and `LLMResponse` from `wallets/ai.py`. Do not start B3b until B3a's tests pass.
- Categories are user-scoped. Only suggest from the user's **visible, non-archived** categories.
- `QuotaExceededError` is already converted to HTTP 429 by B3a's global exception handler — no extra handling here.
- Branch: `feat/ai-auto-categorize`.

---

### Task 1: Categorize endpoint

**Files:**
- Modify: `backend/wallets/views.py`
- Modify: `backend/wallets/urls.py`
- Create: `backend/tests/wallets/test_categorize.py`

**Interfaces:**
- Consumes: `from .ai import ai_service` (B3a); `LLMResponse` (B3a) in tests.
- Produces: `POST /api/wallets/categorize/` body `{"note": "..."}` → `{"suggestion": {"id","name"} | null, "usage_warning": {...} | null}`.

- [ ] **Step 1: Write the failing tests in `backend/tests/wallets/test_categorize.py`**

```python
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
        with patch("wallets.ai.get_provider", return_value=mock_provider("Groceries")):
            res = self.client.post("/api/wallets/categorize/", {"note": "milk"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data["suggestion"])

    def test_blank_note_is_rejected(self):
        res = self.client.post("/api/wallets/categorize/", {"note": "  "}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_requires_auth(self):
        res = APIClient().post("/api/wallets/categorize/", {"note": "x"}, format="json")
        self.assertEqual(res.status_code, 401)
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && source venv/bin/activate
python manage.py test tests.wallets.test_categorize -v 2
```
Expected: `404`/import errors (endpoint not built).

- [ ] **Step 3: Add `CategorizeView` to `backend/wallets/views.py`**

Add the import near the other service imports at the top:
```python
from .ai import ai_service
```
Add the view at the end of the file:
```python
class CategorizeView(APIView):
    """POST /api/wallets/categorize/  {"note": "..."} -> best-matching user category."""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        note = (request.data.get("note") or "").strip()
        if not note:
            return Response({"detail": "note is required"}, status=400)

        categories = list(
            TransactionCategory.objects.filter(
                user=request.user, is_archived=False, is_visible=True
            )
        )
        names = [c.name for c in categories]
        system = (
            "You categorize personal-finance transactions. Given a short note, "
            "reply with EXACTLY ONE category name chosen verbatim from this list, "
            "or 'Uncategorized' if none fit. Reply with only the category name.\n"
            f"Categories: {', '.join(names) if names else '(none)'}"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": note},
        ]
        # QuotaExceededError -> HTTP 429 via the global handler from B3a.
        response, warning = ai_service.complete(request.user, "auto_categorize", messages)

        guess = (response.content or "").strip().strip('".')
        match = next((c for c in categories if c.name.lower() == guess.lower()), None)
        suggestion = {"id": str(match.id), "name": match.name} if match else None
        return Response({"suggestion": suggestion, "usage_warning": warning})
```

- [ ] **Step 4: Wire the URL in `backend/wallets/urls.py`**

Add `CategorizeView` to the `from .views import (...)` block, then add this line **above** the `<uuid:wallet_id>/...` patterns' block (any position works — `categorize` is not a UUID so it won't collide):
```python
    path('categorize/', CategorizeView.as_view(), name='categorize'),
```

- [ ] **Step 5: Run the tests — expect pass**

```bash
python manage.py test tests.wallets.test_categorize -v 2
```
Expected: `Ran 4 tests ... OK`

- [ ] **Step 6: Commit**

```bash
git add backend/wallets/views.py backend/wallets/urls.py backend/tests/wallets/test_categorize.py
git commit -m "feat: add AI auto-categorization endpoint"
```

---

### Task 2: Suggestion chip in TransactionDialog

**Files:**
- Create: `frontend/api/ai.ts`
- Modify: `frontend/components/TransactionDialog.tsx`

**Interfaces:**
- Consumes: `POST /api/wallets/categorize/` (Task 1).

- [ ] **Step 1: Create `frontend/api/ai.ts`**

```typescript
import { axiosInstance } from "@/api/axiosInstance";

export interface CategorySuggestion {
  id: string;
  name: string;
}

export interface CategorizeResponse {
  suggestion: CategorySuggestion | null;
  usage_warning: { percent_used: number; threshold: number } | null;
}

export const categorizeNote = (note: string) =>
  axiosInstance.post<CategorizeResponse>("wallets/categorize/", { note });
```

- [ ] **Step 2: Add imports to `frontend/components/TransactionDialog.tsx`**

```typescript
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { categorizeNote, CategorySuggestion } from "@/api/ai";
```
(If `toast` is already imported from B1b, don't duplicate.)

- [ ] **Step 3: Add suggestion state** (near the other `useState` declarations):

```typescript
  const [suggestion, setSuggestion] = useState<CategorySuggestion | null>(null);
```

- [ ] **Step 4: Debounced fetch on the note field (create mode only)**

Add this effect after the existing effects:
```typescript
  useEffect(() => {
    if (transaction) return;               // suggestions only when creating
    const note = formData.note.trim();
    if (note.length < 3) {
      setSuggestion(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await categorizeNote(note);
        setSuggestion(res.data.suggestion);
        if (res.data.usage_warning) {
          toast.warning(`AI usage at ${res.data.usage_warning.percent_used}%`);
        }
      } catch {
        // categorization is best-effort; ignore failures silently
      }
    }, 600);
    return () => clearTimeout(timer);
  }, [formData.note, transaction]);
```

- [ ] **Step 5: Render the chip under the category picker**

Find the end of the category `<Popover>...</Popover>` block (it closes just before the Tags `<div className="space-y-2">`). Immediately after the category `</Popover>`, still inside the category field's `<div className="space-y-2">`, add:
```tsx
            {suggestion && formData.category !== suggestion.id && (
              <button
                type="button"
                onClick={() => setFormData({ ...formData, category: suggestion.id })}
                className="mt-1 inline-flex items-center gap-1 rounded-full border border-primary/40 px-2 py-0.5 text-xs text-primary hover:bg-primary/10"
              >
                <Sparkles className="h-3 w-3" />
                Suggested: {suggestion.name}
              </button>
            )}
```

- [ ] **Step 6: Verify**

```bash
cd frontend && npm run lint && npm run build
```
Expected: no errors.

- [ ] **Step 7: Manual check** (later, on the running app with `OPENAI_API_KEY` set and a `ModelPricing` row optional): open Add Transaction, type "coffee at starbucks", wait ~0.6s → a "Suggested: <category>" chip appears; clicking it selects that category.

- [ ] **Step 8: Commit**

```bash
git add frontend/api/ai.ts frontend/components/TransactionDialog.tsx
git commit -m "feat: AI category suggestion chip in transaction dialog"
```

---

### Stretch (defer to a later batch): bulk "Categorize uncategorized"

A wallet-page button that loops uncategorized transactions through `/categorize/` and applies confident matches. Deferred: it multiplies token cost and needs a confirm/undo UX. Capture as a follow-up; not part of MVP.
