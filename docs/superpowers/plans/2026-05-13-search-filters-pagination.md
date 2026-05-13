# Search & Filters + Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Search all transactions" mode to the wallet page with server-side note/category/tag/date/amount filtering and infinite scroll pagination, leaving the existing month view unchanged.

**Architecture:** New `WalletTransactionSearch` view with `TransactionCursorPagination` (page size 25, ordered by `-date, -id`). Frontend wallet page gains a boolean `searchMode` state; month mode renders existing UI, search mode renders `TransactionSearch` component + an `IntersectionObserver` sentinel for infinite scroll. Filter form state lives in `TransactionSearch`; applied search params live in a `useRef` on the wallet page so `loadMoreSearchResults` can read them without stale closures.

**Tech Stack:** Django REST Framework `CursorPagination`, React `useRef` + `IntersectionObserver`, shadcn `Sheet`, `Input`, `Select`, axios.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/wallets/tests.py` | Modify | Tests for all filter params, auth, cross-user isolation, pagination |
| `backend/wallets/views.py` | Modify | Add `TransactionCursorPagination` + `WalletTransactionSearch` |
| `backend/wallets/urls.py` | Modify | Register `<uuid:wallet_id>/transactions/search/` |
| `frontend/models/wallets.ts` | Modify | Add `SearchFilters` + `TransactionSearchResponse` types |
| `frontend/components/TransactionSearch.tsx` | Create | Search input (debounced), Filters button with badge, Sheet panel |
| `frontend/app/wallet/[id]/page.tsx` | Modify | Mode toggle, search fetch, loadMore, IntersectionObserver |

---

## Task 1: Backend — tests

**Files:**
- Modify: `backend/wallets/tests.py`

- [ ] **Step 1: Replace the empty test file with the full test suite**

Open `backend/wallets/tests.py` and replace its contents with:

```python
from decimal import Decimal
from datetime import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from wallets.models import Transaction, TransactionCategory, UserTransactionTag, Wallet


def make_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
    return client


class WalletTransactionSearchTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass")
        self.client = make_client(self.user)

        self.wallet = Wallet.objects.create(
            user=self.user, name="Test Wallet", currency="usd", initial_value=Decimal("0")
        )

        self.category = TransactionCategory.objects.create(
            user=self.user, name="Food", icon="utensils", color="#F97316"
        )
        self.tag = UserTransactionTag.objects.create(
            user=self.user, name="Weekly", icon="tag", color="#3B82F6"
        )

        self.url = f"/api/wallets/{self.wallet.id}/transactions/search/"

        self.t1 = Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="Grocery shopping", amount=Decimal("-50.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 1, 15)),
            category=self.category,
        )
        self.t1.tags.add(self.tag)

        self.t2 = Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="Salary income", amount=Decimal("3000.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 2, 1)),
        )

        self.t3 = Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="Restaurant dinner", amount=Decimal("-80.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 3, 10)),
        )

    def _ids(self, response):
        return [t["id"] for t in response.data["results"]]

    # --- auth ---

    def test_requires_authentication(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_returns_404_for_other_users_wallet(self):
        other = User.objects.create_user(username="other", password="pass")
        other_wallet = Wallet.objects.create(
            user=other, name="Theirs", currency="usd", initial_value=Decimal("0")
        )
        url = f"/api/wallets/{other_wallet.id}/transactions/search/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # --- no filter ---

    def test_no_filters_returns_all_transactions(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 3)

    # --- search ---

    def test_search_filters_by_note_substring(self):
        response = self.client.get(self.url, {"search": "grocery"})
        self.assertEqual(response.status_code, 200)
        ids = self._ids(response)
        self.assertIn(str(self.t1.id), ids)
        self.assertNotIn(str(self.t2.id), ids)

    def test_search_is_case_insensitive(self):
        response = self.client.get(self.url, {"search": "GROCERY"})
        self.assertEqual(len(response.data["results"]), 1)

    # --- category ---

    def test_filter_by_category_returns_matching_transactions(self):
        response = self.client.get(self.url, {"category": str(self.category.id)})
        ids = self._ids(response)
        self.assertIn(str(self.t1.id), ids)
        self.assertNotIn(str(self.t2.id), ids)
        self.assertNotIn(str(self.t3.id), ids)

    # --- tag ---

    def test_filter_by_tag_returns_matching_transactions(self):
        response = self.client.get(self.url, {"tag": str(self.tag.id)})
        ids = self._ids(response)
        self.assertIn(str(self.t1.id), ids)
        self.assertNotIn(str(self.t2.id), ids)

    def test_filter_by_tag_no_duplicates(self):
        # Even if a transaction has the tag twice (shouldn't happen, but test distinct)
        response = self.client.get(self.url, {"tag": str(self.tag.id)})
        ids = self._ids(response)
        self.assertEqual(len(ids), len(set(ids)))

    # --- date range ---

    def test_filter_date_from_excludes_earlier_transactions(self):
        response = self.client.get(self.url, {"date_from": "2024-02-01"})
        ids = self._ids(response)
        self.assertNotIn(str(self.t1.id), ids)
        self.assertIn(str(self.t2.id), ids)
        self.assertIn(str(self.t3.id), ids)

    def test_filter_date_to_excludes_later_transactions(self):
        response = self.client.get(self.url, {"date_to": "2024-02-28"})
        ids = self._ids(response)
        self.assertIn(str(self.t1.id), ids)
        self.assertIn(str(self.t2.id), ids)
        self.assertNotIn(str(self.t3.id), ids)

    def test_filter_date_range_inclusive(self):
        response = self.client.get(self.url, {"date_from": "2024-01-15", "date_to": "2024-01-15"})
        ids = self._ids(response)
        self.assertIn(str(self.t1.id), ids)
        self.assertEqual(len(ids), 1)

    # --- amount range ---

    def test_filter_min_amount_excludes_lower(self):
        response = self.client.get(self.url, {"min_amount": "0"})
        ids = self._ids(response)
        self.assertNotIn(str(self.t1.id), ids)
        self.assertIn(str(self.t2.id), ids)
        self.assertNotIn(str(self.t3.id), ids)

    def test_filter_max_amount_excludes_higher(self):
        response = self.client.get(self.url, {"max_amount": "-60"})
        ids = self._ids(response)
        self.assertNotIn(str(self.t1.id), ids)
        self.assertNotIn(str(self.t2.id), ids)
        self.assertIn(str(self.t3.id), ids)

    # --- pagination ---

    def test_pagination_wraps_results_in_cursor_envelope(self):
        response = self.client.get(self.url)
        self.assertIn("results", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)

    def test_pagination_returns_cursor_when_more_pages_exist(self):
        # Create 23 more to exceed page_size=25 (we already have 3)
        for i in range(23):
            Transaction.objects.create(
                wallet=self.wallet, created_by=self.user,
                note=f"Filler {i}", amount=Decimal("-1.00"), currency="usd",
                date=timezone.now(),
            )
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 25)
        self.assertIsNotNone(response.data["next"])

    def test_pagination_next_is_null_on_last_page(self):
        response = self.client.get(self.url)
        self.assertIsNone(response.data["next"])
```

- [ ] **Step 2: Run the tests to confirm they all fail (view doesn't exist yet)**

```bash
cd backend && source venv/bin/activate && python manage.py test wallets.tests.WalletTransactionSearchTest -v 2
```

Expected: errors like `404` or `AttributeError` — the endpoint doesn't exist yet.

---

## Task 2: Backend — search view + URL

**Files:**
- Modify: `backend/wallets/views.py`
- Modify: `backend/wallets/urls.py`

- [ ] **Step 1: Add the pagination class and search view to `views.py`**

Add this import at the top of `backend/wallets/views.py` (after the existing `from rest_framework import generics` line):

```python
from rest_framework.pagination import CursorPagination
```

Then add these two classes at the end of `backend/wallets/views.py`:

```python
class TransactionCursorPagination(CursorPagination):
    page_size = 25
    ordering = ('-date', '-id')


class WalletTransactionSearch(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    pagination_class = TransactionCursorPagination

    def get_queryset(self):
        wallet_id = self.kwargs['wallet_id']
        wallet = get_object_or_404(Wallet, id=wallet_id, user=self.request.user)
        queryset = Transaction.objects.filter(wallet=wallet).select_related('category').prefetch_related('tags')

        p = self.request.query_params

        if search := p.get('search'):
            queryset = queryset.filter(note__icontains=search)

        if category := p.get('category'):
            queryset = queryset.filter(category__id=category)

        if tag := p.get('tag'):
            queryset = queryset.filter(tags__id=tag).distinct()

        if date_from := p.get('date_from'):
            queryset = queryset.filter(date__date__gte=date_from)

        if date_to := p.get('date_to'):
            queryset = queryset.filter(date__date__lte=date_to)

        if min_amount := p.get('min_amount'):
            queryset = queryset.filter(amount__gte=min_amount)

        if max_amount := p.get('max_amount'):
            queryset = queryset.filter(amount__lte=max_amount)

        return queryset
```

- [ ] **Step 2: Register the URL in `backend/wallets/urls.py`**

Add `WalletTransactionSearch` to the import:

```python
from .views import (
    WalletList, WalletDetail,
    WalletTransactionList, WalletTransactionDetail,
    WalletTransactionSearch,
    UserCategoryList, UserCategoryDetail,
    UserTagList, UserTagDetail,
    TransactionDetail, TransactionCreate,
    CSVParseView, CSVExecuteView,
    WalletMetrics,
    UserRecurringTransactionList,
    WalletRecurringTransactionList, WalletRecurringTransactionDetail,
    RecurringTransactionExecutionList,
)
```

Then add this route in `urlpatterns`, right after the existing `wallet-transaction-list` line:

```python
path('<uuid:wallet_id>/transactions/search/', WalletTransactionSearch.as_view(), name='wallet-transaction-search'),
```

- [ ] **Step 3: Run the tests — all should pass**

```bash
cd backend && source venv/bin/activate && python manage.py test wallets.tests.WalletTransactionSearchTest -v 2
```

Expected: all tests pass. If any fail, read the error and fix before continuing.

- [ ] **Step 4: Commit**

```bash
git add backend/wallets/tests.py backend/wallets/views.py backend/wallets/urls.py
git commit -m "feat: add WalletTransactionSearch endpoint with cursor pagination"
```

---

## Task 3: Frontend — add types

**Files:**
- Modify: `frontend/models/wallets.ts`

- [ ] **Step 1: Add `SearchFilters` and `TransactionSearchResponse` to the end of `frontend/models/wallets.ts`**

```typescript
export interface SearchFilters {
  category: string;
  tag: string;
  date_from: string;
  date_to: string;
  min_amount: string;
  max_amount: string;
}

export interface TransactionSearchResponse {
  next: string | null;
  previous: string | null;
  results: Transaction[];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/models/wallets.ts
git commit -m "feat: add SearchFilters and TransactionSearchResponse types"
```

---

## Task 4: Install shadcn Sheet

The filter panel uses a `Sheet` (slide-in drawer), which is not yet installed.

- [ ] **Step 1: Install the Sheet component**

```bash
cd frontend && npx shadcn@latest add sheet
```

Expected: creates `frontend/components/ui/sheet.tsx`.

- [ ] **Step 2: Commit**

```bash
git add frontend/components/ui/sheet.tsx
git commit -m "chore: add shadcn Sheet component"
```

---

## Task 5: Frontend — `TransactionSearch` component

**Files:**
- Create: `frontend/components/TransactionSearch.tsx`

This component owns all UI state for the search input and filter form. It calls `onSearch` with the final query + filters after debounce (search) or after Apply (filters).

- [ ] **Step 1: Create `frontend/components/TransactionSearch.tsx`**

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { Search, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Category, SearchFilters, Tag } from "@/models/wallets";

const EMPTY_FILTERS: SearchFilters = {
  category: "",
  tag: "",
  date_from: "",
  date_to: "",
  min_amount: "",
  max_amount: "",
};

interface TransactionSearchProps {
  categories: Category[];
  tags: Tag[];
  onSearch: (query: string, filters: SearchFilters) => void;
}

export function TransactionSearch({ categories, tags, onSearch }: TransactionSearchProps) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<SearchFilters>(EMPTY_FILTERS);
  const [sheetOpen, setSheetOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounce search query — fire onSearch 400ms after user stops typing
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onSearch(query, filters);
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]); // eslint-disable-line react-hooks/exhaustive-deps

  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  function handleApply() {
    setSheetOpen(false);
    onSearch(query, filters);
  }

  function handleClearAll() {
    const cleared = EMPTY_FILTERS;
    setFilters(cleared);
    setSheetOpen(false);
    onSearch(query, cleared);
  }

  function setFilter<K extends keyof SearchFilters>(key: K, value: SearchFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <div className="flex items-center gap-2 flex-1">
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
        <Input
          placeholder="Search notes..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-8"
        />
      </div>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetTrigger asChild>
          <Button variant="outline" size="sm" className="relative">
            <SlidersHorizontal className="mr-2 h-4 w-4" />
            Filters
            {activeFilterCount > 0 && (
              <span className="ml-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground">
                {activeFilterCount}
              </span>
            )}
          </Button>
        </SheetTrigger>

        <SheetContent className="w-80">
          <SheetHeader>
            <SheetTitle>Filter transactions</SheetTitle>
          </SheetHeader>

          <div className="mt-6 flex flex-col gap-5">
            {/* Category */}
            <div className="flex flex-col gap-1.5">
              <Label>Category</Label>
              <Select
                value={filters.category || "all"}
                onValueChange={(v) => setFilter("category", v === "all" ? "" : v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Any category</SelectItem>
                  {categories.filter((c) => !c.is_archived).map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Tag */}
            <div className="flex flex-col gap-1.5">
              <Label>Tag</Label>
              <Select
                value={filters.tag || "all"}
                onValueChange={(v) => setFilter("tag", v === "all" ? "" : v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Any tag" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Any tag</SelectItem>
                  {tags.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Date range */}
            <div className="flex flex-col gap-1.5">
              <Label>Date from</Label>
              <Input
                type="date"
                value={filters.date_from}
                onChange={(e) => setFilter("date_from", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Date to</Label>
              <Input
                type="date"
                value={filters.date_to}
                onChange={(e) => setFilter("date_to", e.target.value)}
              />
            </div>

            {/* Amount range */}
            <div className="flex flex-col gap-1.5">
              <Label>Min amount</Label>
              <Input
                type="number"
                placeholder="e.g. -500"
                value={filters.min_amount}
                onChange={(e) => setFilter("min_amount", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Max amount</Label>
              <Input
                type="number"
                placeholder="e.g. 0"
                value={filters.max_amount}
                onChange={(e) => setFilter("max_amount", e.target.value)}
              />
            </div>

            <div className="flex flex-col gap-2 pt-2">
              <Button onClick={handleApply}>Apply filters</Button>
              {activeFilterCount > 0 && (
                <Button variant="ghost" onClick={handleClearAll}>
                  Clear all
                </Button>
              )}
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/TransactionSearch.tsx
git commit -m "feat: add TransactionSearch component with debounced input and filter sheet"
```

---

## Task 6: Frontend — wallet page search mode

**Files:**
- Modify: `frontend/app/wallet/[id]/page.tsx`

- [ ] **Step 1: Add new imports to the top of `frontend/app/wallet/[id]/page.tsx`**

Replace the existing import block's first line (`"use client";`) through the existing imports with the following complete import section (keep all existing imports, add the new ones):

```tsx
"use client";

import { axiosInstance } from "@/api/axiosInstance";
import ProtectedRoute from "@/components/ProtectedRoute";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, Plus, Edit, Trash2, TrendingUp, TrendingDown, Upload, BarChart3, Search } from "lucide-react";
import { DynamicIcon } from "@/components/IconPicker";
import { UserMenu } from "@/components/UserMenu";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Wallet, Transaction, Category, Tag, SearchFilters, TransactionSearchResponse } from "@/models/wallets";
import { TransactionDialog } from "@/components/TransactionDialog";
import { CSVImportDialog } from "@/components/CSVImportDialog";
import MonthSelector from "@/components/MonthSelector";
import { formatCurrency } from "@/lib/currency";
import { TransactionSearch } from "@/components/TransactionSearch";
```

- [ ] **Step 2: Add search mode state and refs inside `WalletPage`, right after the existing state declarations**

After the line `const [importDialogOpen, setImportDialogOpen] = useState<boolean>(false);`, add:

```tsx
  // Search mode
  const [searchMode, setSearchMode] = useState(false);
  const [searchTransactions, setSearchTransactions] = useState<Transaction[]>([]);
  const [searchCursor, setSearchCursor] = useState<string | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const searchParamsRef = useRef<{ query: string; filters: SearchFilters }>({
    query: "",
    filters: { category: "", tag: "", date_from: "", date_to: "", min_amount: "", max_amount: "" },
  });
  const sentinelRef = useRef<HTMLDivElement>(null);
```

- [ ] **Step 3: Add the `buildSearchUrl` and `fetchSearchResults` helpers inside `WalletPage`, after the existing `fetchTags` function**

```tsx
  function buildSearchUrl(query: string, filters: SearchFilters, cursor?: string | null): string {
    const p = new URLSearchParams();
    if (query) p.set("search", query);
    if (filters.category) p.set("category", filters.category);
    if (filters.tag) p.set("tag", filters.tag);
    if (filters.date_from) p.set("date_from", filters.date_from);
    if (filters.date_to) p.set("date_to", filters.date_to);
    if (filters.min_amount) p.set("min_amount", filters.min_amount);
    if (filters.max_amount) p.set("max_amount", filters.max_amount);
    if (cursor) p.set("cursor", cursor);
    return `wallets/${params.id}/transactions/search/?${p.toString()}`;
  }

  function extractCursor(nextUrl: string | null): string | null {
    if (!nextUrl) return null;
    try {
      return new URL(nextUrl).searchParams.get("cursor");
    } catch {
      return null;
    }
  }

  async function fetchSearchResults(query: string, filters: SearchFilters) {
    searchParamsRef.current = { query, filters };
    setSearchLoading(true);
    try {
      const response = await axiosInstance.get<TransactionSearchResponse>(
        buildSearchUrl(query, filters)
      );
      setSearchTransactions(response.data.results);
      setSearchCursor(extractCursor(response.data.next));
    } catch (error) {
      console.error("Failed to fetch search results:", error);
    } finally {
      setSearchLoading(false);
    }
  }

  async function loadMoreSearchResults() {
    if (searchLoading || !searchCursor) return;
    setSearchLoading(true);
    try {
      const { query, filters } = searchParamsRef.current;
      const response = await axiosInstance.get<TransactionSearchResponse>(
        buildSearchUrl(query, filters, searchCursor)
      );
      setSearchTransactions((prev) => [...prev, ...response.data.results]);
      setSearchCursor(extractCursor(response.data.next));
    } catch (error) {
      console.error("Failed to load more search results:", error);
    } finally {
      setSearchLoading(false);
    }
  }
```

- [ ] **Step 4: Add the IntersectionObserver effect inside `WalletPage`, after the existing `useEffect` blocks**

```tsx
  useEffect(() => {
    if (!searchMode) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadMoreSearchResults();
        }
      },
      { threshold: 0.1 }
    );
    if (sentinelRef.current) observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [searchMode, searchCursor, searchLoading]); // eslint-disable-line react-hooks/exhaustive-deps
```

- [ ] **Step 5: Update `handleDeleteTransaction` and `handleTransactionSaved` to refresh correctly in both modes**

Replace the existing `handleDeleteTransaction`:

```tsx
  async function handleDeleteTransaction(transactionId: string) {
    if (!confirm("Are you sure you want to delete this transaction?")) {
      return;
    }
    try {
      await axiosInstance.delete(`transactions/${transactionId}/`);
      if (searchMode) {
        const { query, filters } = searchParamsRef.current;
        await fetchSearchResults(query, filters);
      } else {
        await loadData();
      }
    } catch (error) {
      console.error("Failed to delete transaction:", error);
      alert("Failed to delete transaction. Please try again.");
    }
  }
```

Replace the existing `handleTransactionSaved`:

```tsx
  async function handleTransactionSaved() {
    if (searchMode) {
      const { query, filters } = searchParamsRef.current;
      await fetchSearchResults(query, filters);
    } else {
      await loadData();
    }
  }
```

- [ ] **Step 6: Add a `handleEnterSearchMode` and `handleExitSearchMode` helper**

```tsx
  function handleEnterSearchMode() {
    setSearchMode(true);
    fetchSearchResults("", searchParamsRef.current.filters);
  }

  function handleExitSearchMode() {
    setSearchMode(false);
    setSearchTransactions([]);
    setSearchCursor(null);
  }
```

- [ ] **Step 7: Update the JSX — month/year controls area and the card**

Find the block that renders `<div className="mb-6"><MonthSelector /></div>` and replace it with:

```tsx
          <div className="mb-6 flex items-center gap-4">
            {searchMode ? (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleExitSearchMode}
                >
                  <ArrowLeft className="mr-2 h-4 w-4" /> Month view
                </Button>
                <TransactionSearch
                  categories={categories}
                  tags={tags}
                  onSearch={fetchSearchResults}
                />
              </>
            ) : (
              <>
                <MonthSelector />
                <Button variant="outline" size="sm" onClick={handleEnterSearchMode}>
                  <Search className="mr-2 h-4 w-4" /> Search all transactions
                </Button>
              </>
            )}
          </div>
```

`Search` is already included in the import block from Step 1 — no additional change needed here.

- [ ] **Step 8: Update the Card to handle search mode**

Find the `<CardTitle>` that reads `Transactions for {new Date(...)}` and replace the entire `<Card>` with the following (this adds the sentinel and search-mode list):

```tsx
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>
                    {searchMode
                      ? "All transactions"
                      : `Transactions for ${new Date(parseInt(year), parseInt(month) - 1).toLocaleString("default", { month: "long", year: "numeric" })}`}
                  </CardTitle>
                  <CardDescription>
                    {searchMode ? "Showing search results across all time" : "Manage your income and expenses"}
                  </CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setImportDialogOpen(true)}>
                    <Upload className="mr-2 h-4 w-4" />
                    Import CSV
                  </Button>
                  <Button onClick={handleAddTransaction}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Transaction
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {(() => {
                const displayedTransactions = searchMode ? searchTransactions : transactions;
                if (!searchMode && displayedTransactions.length === 0) {
                  return (
                    <div className="text-center py-12">
                      <p className="text-gray-500 mb-4">No transactions yet</p>
                      <Button onClick={handleAddTransaction}>
                        <Plus className="mr-2 h-4 w-4" />
                        Add Your First Transaction
                      </Button>
                    </div>
                  );
                }
                if (searchMode && displayedTransactions.length === 0 && !searchLoading) {
                  return (
                    <div className="text-center py-12">
                      <p className="text-gray-500">No transactions match your search</p>
                    </div>
                  );
                }
                return (
                  <>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Date</TableHead>
                          <TableHead>Note</TableHead>
                          <TableHead>Category</TableHead>
                          <TableHead>Tags</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead className="text-right">Amount</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {displayedTransactions.map((transaction) => {
                          const isIncome = Number(transaction.amount) > 0;
                          return (
                            <TableRow key={transaction.id}>
                              <TableCell className="font-medium">
                                {new Date(transaction.date).toLocaleDateString()}
                              </TableCell>
                              <TableCell>{transaction.note}</TableCell>
                              <TableCell>
                                {transaction.category ? (
                                  <div className="flex items-center gap-2">
                                    <div
                                      className="w-6 h-6 rounded flex items-center justify-center"
                                      style={{ backgroundColor: transaction.category.color + "20" }}
                                    >
                                      <DynamicIcon
                                        name={transaction.category.icon || "circle"}
                                        className="h-3 w-3"
                                        style={{ color: transaction.category.color }}
                                      />
                                    </div>
                                    <span>{transaction.category.name}</span>
                                  </div>
                                ) : (
                                  <span className="text-gray-400">Uncategorized</span>
                                )}
                              </TableCell>
                              <TableCell>
                                {transaction.tags && transaction.tags.length > 0 ? (
                                  <div className="flex flex-wrap gap-1">
                                    {transaction.tags.map((tag) => (
                                      <span
                                        key={tag.id}
                                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
                                        style={{
                                          backgroundColor: tag.color + "20",
                                          color: tag.color,
                                        }}
                                      >
                                        <DynamicIcon name={tag.icon || "tag"} className="h-3 w-3" />
                                        {tag.name}
                                      </span>
                                    ))}
                                  </div>
                                ) : (
                                  <span className="text-gray-400">—</span>
                                )}
                              </TableCell>
                              <TableCell>
                                <span
                                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                    isIncome ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                                  }`}
                                >
                                  {isIncome ? "income" : "expense"}
                                </span>
                              </TableCell>
                              <TableCell
                                className={`text-right font-semibold ${
                                  isIncome ? "text-green-600" : "text-red-600"
                                }`}
                              >
                                {isIncome ? "+" : ""}
                                {formatCurrency(transaction.amount, wallet.currency)}
                              </TableCell>
                              <TableCell className="text-right">
                                <div className="flex justify-end gap-2">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleEditTransaction(transaction)}
                                  >
                                    <Edit className="h-4 w-4" />
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleDeleteTransaction(transaction.id)}
                                  >
                                    <Trash2 className="h-4 w-4 text-red-600" />
                                  </Button>
                                </div>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>

                    {/* Infinite scroll sentinel (search mode only) */}
                    {searchMode && (
                      <div ref={sentinelRef} className="py-4 text-center text-sm text-gray-400">
                        {searchLoading && "Loading more..."}
                        {!searchLoading && !searchCursor && searchTransactions.length > 0 && "No more transactions"}
                      </div>
                    )}
                  </>
                );
              })()}
            </CardContent>
          </Card>
```

- [ ] **Step 9: Verify TypeScript compiles with no errors**

```bash
cd frontend && npm run build 2>&1 | tail -30
```

Expected: build completes without TypeScript errors. Fix any type errors before continuing.

- [ ] **Step 10: Commit**

```bash
git add frontend/app/wallet/\[id\]/page.tsx
git commit -m "feat: add search mode with infinite scroll to wallet page"
```

---

## Task 7: Manual smoke test

- [ ] **Step 1: Start backend and frontend**

Terminal 1:
```bash
cd backend && source venv/bin/activate && python manage.py runserver
```

Terminal 2:
```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Verify month mode is unchanged**

Open `http://localhost:3000`, log in, navigate to a wallet. Confirm the month picker still works and transactions still load as before.

- [ ] **Step 3: Verify search mode activates**

Click "Search all transactions". Confirm:
- Month picker disappears
- Search bar and Filters button appear
- "← Month view" button appears
- All transactions load (across all months)

- [ ] **Step 4: Verify search**

Type part of a transaction note. Confirm after ~400ms the list filters to matching transactions only.

- [ ] **Step 5: Verify filters**

Click Filters, select a category, click Apply. Confirm:
- List filters to that category
- Badge shows "1" on the Filters button
- Clearing all resets the list

- [ ] **Step 6: Verify exit**

Click "← Month view". Confirm the month picker returns and the search state is gone.

- [ ] **Step 7: Final commit if any last-minute fixes were needed**

```bash
git add -p && git commit -m "fix: smoke test corrections"
```
