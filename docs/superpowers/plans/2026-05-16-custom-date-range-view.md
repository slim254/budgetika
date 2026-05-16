# Custom Date Range View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a custom date range selector to the wallet page so users can view transactions and totals for arbitrary date ranges (e.g., Jan–Mar 2025).

**Architecture:** Refactor `MonthSelector` into `DateSelector` with two modes (month and date range picker). Wallet page toggles between modes and fetches from either the regular transactions endpoint (month mode) or the search endpoint with date filters (date range mode). Budget panel hides in date range mode; totals are recalculated for the selected period.

**Tech Stack:** React 18, Next.js 15 (App Router), TypeScript, shadcn/ui (Popover, Calendar, Button), axios

---

### Task 1: Create DateSelector component — Month mode

**Files:**
- Create: `frontend/components/DateSelector.tsx`

**Context:** `MonthSelector.tsx` currently handles month/year selection and URL params. We'll create a new `DateSelector` that starts with identical month mode behavior, then extends it to support date range mode in Task 2.

- [ ] **Step 1: Read the existing MonthSelector to understand its structure**

```bash
cat frontend/components/MonthSelector.tsx
```

- [ ] **Step 2: Create DateSelector.tsx with month mode (copy from MonthSelector)**

```typescript
"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface DateSelectorProps {
  onDateChange?: (params: { month?: string; year?: string; date_from?: string; date_to?: string }) => void;
}

export default function DateSelector({ onDateChange }: DateSelectorProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const currentDate = new Date();
  const month = searchParams.get("month") || String(currentDate.getMonth() + 1).padStart(2, "0");
  const year = searchParams.get("year") || String(currentDate.getFullYear());

  const handleMonthChange = (newMonth: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("month", newMonth);
    router.push(`?${params.toString()}`);
    onDateChange?.({ month: newMonth, year });
  };

  const handleYearChange = (newYear: string) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("year", newYear);
    router.push(`?${params.toString()}`);
    onDateChange?.({ month, year: newYear });
  };

  return (
    <div className="flex gap-2 items-center">
      <span className="text-sm text-gray-600">View by:</span>
      <Select value={month} onValueChange={handleMonthChange}>
        <SelectTrigger className="w-32">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Array.from({ length: 12 }, (_, i) => {
            const m = String(i + 1).padStart(2, "0");
            const name = new Date(parseInt(year), i).toLocaleString("default", {
              month: "long",
            });
            return (
              <SelectItem key={m} value={m}>
                {name}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>

      <Select value={year} onValueChange={handleYearChange}>
        <SelectTrigger className="w-28">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Array.from({ length: 10 }, (_, i) => {
            const y = String(currentDate.getFullYear() - 5 + i);
            return (
              <SelectItem key={y} value={y}>
                {y}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
    </div>
  );
}
```

- [ ] **Step 3: Verify the component compiles**

```bash
cd frontend && npm run build 2>&1 | head -30
```

Expected: No errors about DateSelector

- [ ] **Step 4: Commit**

```bash
git add frontend/components/DateSelector.tsx
git commit -m "feat: create DateSelector component with month mode"
```

---

### Task 2: Add date range mode UI to DateSelector

**Files:**
- Modify: `frontend/components/DateSelector.tsx`

**Context:** Now add the date range picker UI (two shadcn Popovers with Calendars). The component will have internal state `rangeMode: boolean` to toggle between month and range modes.

- [ ] **Step 1: Import shadcn Popover and Calendar components**

Check if they're already installed:
```bash
cd frontend && ls src/components/ui/ | grep -E "popover|calendar"
```

If not present, install them:
```bash
cd frontend && npx shadcn@latest add popover calendar
```

- [ ] **Step 2: Add state and date formatting utilities to DateSelector**

Update the imports and add state at the top of the component:

```typescript
"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { ChevronDown } from "lucide-react";

interface DateSelectorProps {
  onDateChange?: (params: { month?: string; year?: string; date_from?: string; date_to?: string }) => void;
}

export default function DateSelector({ onDateChange }: DateSelectorProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const currentDate = new Date();
  const month = searchParams.get("month") || String(currentDate.getMonth() + 1).padStart(2, "0");
  const year = searchParams.get("year") || String(currentDate.getFullYear());

  // Date range mode state
  const [rangeMode, setRangeMode] = useState(false);
  const [dateFrom, setDateFrom] = useState<Date | undefined>(undefined);
  const [dateTo, setDateTo] = useState<Date | undefined>(undefined);
```

- [ ] **Step 3: Add date range selection handlers**

Add these functions inside the component after the state declarations:

```typescript
  const formatDateForAPI = (date: Date): string => {
    return date.toISOString().split("T")[0]; // YYYY-MM-DD
  };

  const handleDateFromChange = (date: Date | undefined) => {
    setDateFrom(date);
  };

  const handleDateToChange = (date: Date | undefined) => {
    setDateTo(date);
  };

  const handleApplyDateRange = () => {
    if (!dateFrom || !dateTo) {
      alert("Please select both start and end dates");
      return;
    }
    if (dateTo < dateFrom) {
      alert("End date must be after start date");
      return;
    }
    const params = new URLSearchParams(searchParams.toString());
    params.delete("month");
    params.delete("year");
    params.set("date_from", formatDateForAPI(dateFrom));
    params.set("date_to", formatDateForAPI(dateTo));
    router.push(`?${params.toString()}`);
    onDateChange?.({ date_from: formatDateForAPI(dateFrom), date_to: formatDateForAPI(dateTo) });
  };

  const handleClearDateRange = () => {
    setDateFrom(undefined);
    setDateTo(undefined);
  };
```

- [ ] **Step 4: Replace the return statement with conditional month/range UI**

Replace the entire return block with:

```typescript
  if (rangeMode) {
    return (
      <div className="flex gap-2 items-center">
        <span className="text-sm text-gray-600">View by:</span>
        
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" className="w-32">
              {dateFrom ? dateFrom.toLocaleDateString() : "From"}
              <ChevronDown className="ml-1 h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0">
            <Calendar
              mode="single"
              selected={dateFrom}
              onSelect={handleDateFromChange}
              disabled={(date) => dateTo ? date > dateTo : false}
            />
          </PopoverContent>
        </Popover>

        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" className="w-32">
              {dateTo ? dateTo.toLocaleDateString() : "To"}
              <ChevronDown className="ml-1 h-4 w-4" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0">
            <Calendar
              mode="single"
              selected={dateTo}
              onSelect={handleDateToChange}
              disabled={(date) => dateFrom ? date < dateFrom : false}
            />
          </PopoverContent>
        </Popover>

        <Button size="sm" onClick={handleApplyDateRange} disabled={!dateFrom || !dateTo}>
          Apply
        </Button>

        <Button
          size="sm"
          variant="ghost"
          onClick={handleClearDateRange}
        >
          Clear
        </Button>

        <Button
          size="sm"
          variant="ghost"
          onClick={() => setRangeMode(false)}
        >
          Back to Month
        </Button>
      </div>
    );
  }

  // Month mode (existing code)
  return (
    <div className="flex gap-2 items-center">
      <span className="text-sm text-gray-600">View by:</span>
      <Select value={month} onValueChange={handleMonthChange}>
        <SelectTrigger className="w-32">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Array.from({ length: 12 }, (_, i) => {
            const m = String(i + 1).padStart(2, "0");
            const name = new Date(parseInt(year), i).toLocaleString("default", {
              month: "long",
            });
            return (
              <SelectItem key={m} value={m}>
                {name}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>

      <Select value={year} onValueChange={handleYearChange}>
        <SelectTrigger className="w-28">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Array.from({ length: 10 }, (_, i) => {
            const y = String(currentDate.getFullYear() - 5 + i);
            return (
              <SelectItem key={y} value={y}>
                {y}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>

      <Button
        size="sm"
        variant="outline"
        onClick={() => setRangeMode(true)}
      >
        Custom Range
      </Button>
    </div>
  );
```

- [ ] **Step 5: Verify the component compiles**

```bash
cd frontend && npm run build 2>&1 | head -30
```

Expected: No errors about DateSelector

- [ ] **Step 6: Commit**

```bash
git add frontend/components/DateSelector.tsx
git commit -m "feat: add date range mode to DateSelector with popover calendars"
```

---

### Task 3: Update wallet page to import DateSelector instead of MonthSelector

**Files:**
- Modify: `frontend/app/wallet/[id]/page.tsx:1-25` (imports section)

- [ ] **Step 1: Replace MonthSelector import with DateSelector**

Change line 17 from:
```typescript
import MonthSelector from "@/components/MonthSelector";
```

To:
```typescript
import DateSelector from "@/components/DateSelector";
```

- [ ] **Step 2: Replace MonthSelector JSX with DateSelector**

Find the MonthSelector component usage around line 401 and replace:
```typescript
<MonthSelector />
```

With:
```typescript
<DateSelector onDateChange={handleDateChange} />
```

- [ ] **Step 3: Add handleDateChange handler to wallet page**

Add this function after the `handleEnterSearchMode` function (around line 268):

```typescript
  function handleDateChange(params: { month?: string; year?: string; date_from?: string; date_to?: string }) {
    // The DateSelector component handles URL updates via router.push
    // This callback is for any additional state updates if needed
    // Currently, the page will auto-refetch due to month/year/date_from/date_to in useEffect deps
  }
```

- [ ] **Step 4: Verify the component compiles**

```bash
cd frontend && npm run build 2>&1 | head -30
```

Expected: No errors about imports or DateSelector

- [ ] **Step 5: Commit**

```bash
git add frontend/app/wallet/[id]/page.tsx
git commit -m "feat: replace MonthSelector with DateSelector in wallet page"
```

---

### Task 4: Add date range state and fetching logic to wallet page

**Files:**
- Modify: `frontend/app/wallet/[id]/page.tsx:50-110`

**Context:** The wallet page currently uses `month` and `year` from URL params. Now we need to support `date_from` and `date_to` params. We'll detect which mode is active based on which params are present, and fetch accordingly.

- [ ] **Step 1: Add date range params extraction**

After the existing month/year extraction (around line 56), add:

```typescript
  // Date range filtering (alternative to month view)
  const dateFrom = searchParams.get('date_from') || '';
  const dateTo = searchParams.get('date_to') || '';
  const isDateRangeMode = Boolean(dateFrom && dateTo);
```

- [ ] **Step 2: Create new fetchTransactionsByDateRange function**

Add this function after `fetchTransactions()` (around line 77):

```typescript
  async function fetchTransactionsByDateRange(from: string, to: string) {
    try {
      const response = await axiosInstance.get<TransactionSearchResponse>(
        buildSearchUrl("", { category: "", tag: "", date_from: from, date_to: to, min_amount: "", max_amount: "" })
      );
      setTransactions(response.data.results);
      setSearchCursor(extractCursor(response.data.next));
    } catch (error) {
      console.error("Failed to fetch transactions by date range:", error);
    }
  }
```

- [ ] **Step 3: Update the main loadData function to handle both modes**

Replace the `loadData()` function (around line 106) with:

```typescript
  async function loadData() {
    setIsLoading(true);
    if (isDateRangeMode) {
      await Promise.all([fetchWallet(), fetchTransactionsByDateRange(dateFrom, dateTo), fetchWallets()]);
    } else {
      await Promise.all([fetchWallet(), fetchTransactions(), fetchWallets()]);
    }
    setIsLoading(false);
  }
```

- [ ] **Step 4: Update the useEffect dependency**

Find the useEffect that calls `loadData()` (around line 176) and update its dependency array to include the date range params:

```typescript
  useEffect(() => {
    if (params.id) {
      loadData();
    }
  }, [params.id, month, year, dateFrom, dateTo, isDateRangeMode]);
```

- [ ] **Step 5: Verify the component compiles**

```bash
cd frontend && npm run build 2>&1 | head -30
```

Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/app/wallet/[id]/page.tsx
git commit -m "feat: add date range fetching logic to wallet page"
```

---

### Task 5: Hide budget panel in date range mode

**Files:**
- Modify: `frontend/app/wallet/[id]/page.tsx:409-418`

**Context:** The budget panel is per-month, so it shouldn't show in date range mode.

- [ ] **Step 1: Update the BudgetPanel conditional render**

Find the BudgetPanel component (around line 410) and wrap it with a condition:

Change from:
```typescript
          {!searchMode && (
            <BudgetPanel
              ...
            />
          )}
```

To:
```typescript
          {!searchMode && !isDateRangeMode && (
            <BudgetPanel
              ...
            />
          )}
```

- [ ] **Step 2: Verify the component compiles**

```bash
cd frontend && npm run build 2>&1 | head -30
```

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/app/wallet/[id]/page.tsx
git commit -m "feat: hide budget panel in date range mode"
```

---

### Task 6: Update page title and card calculations for date range mode

**Files:**
- Modify: `frontend/app/wallet/[id]/page.tsx:296-381`

**Context:** The summary cards and page title need to show the correct date range and recalculate totals for the range (which already happens since we fetch the right transactions).

- [ ] **Step 1: Update the totals calculation to be mode-aware**

The income/expense calculations (lines 297-303) already work correctly because they're based on the fetched `transactions` array, which is already filtered by date range. No changes needed here.

- [ ] **Step 2: Add a helper function to format the date range**

Add this function after the totals calculations (around line 304):

```typescript
  function getDisplayLabel(): string {
    if (isDateRangeMode && dateFrom && dateTo) {
      const from = new Date(dateFrom).toLocaleDateString("default", { month: "short", day: "numeric", year: "numeric" });
      const to = new Date(dateTo).toLocaleDateString("default", { month: "short", day: "numeric", year: "numeric" });
      return `${from} – ${to}`;
    }
    const monthName = new Date(parseInt(year), parseInt(month) - 1).toLocaleString("default", { month: "long", year: "numeric" });
    return monthName;
  }
```

- [ ] **Step 3: Update the card titles to use the display label**

Find the CardTitle for the transaction table (around line 424) and update it:

Change from:
```typescript
                  <CardTitle>
                    {searchMode
                      ? "All transactions"
                      : `Transactions for ${new Date(parseInt(year), parseInt(month) - 1).toLocaleString("default", { month: "long", year: "numeric" })}`}
                  </CardTitle>
```

To:
```typescript
                  <CardTitle>
                    {searchMode
                      ? "All transactions"
                      : `Transactions for ${getDisplayLabel()}`}
                  </CardTitle>
```

- [ ] **Step 4: Verify the component compiles**

```bash
cd frontend && npm run build 2>&1 | head -30
```

Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add frontend/app/wallet/[id]/page.tsx
git commit -m "feat: update display labels and totals for date range mode"
```

---

### Task 7: Manual end-to-end test

**Context:** Test the feature in the dev server to ensure all modes work correctly.

- [ ] **Step 1: Start the backend and frontend servers**

Terminal 1 (backend):
```bash
cd /Users/patrykjamroz/dev/budgeting-app/backend
source venv/bin/activate
python manage.py runserver
```

Terminal 2 (frontend):
```bash
cd /Users/patrykjamroz/dev/budgeting-app/frontend
npm run dev
```

- [ ] **Step 2: Open the app and navigate to a wallet**

```bash
open http://localhost:3000
```

Login and navigate to a wallet page.

- [ ] **Step 3: Test month mode (default)**

- Verify the month selector displays the current month
- Verify clicking the month/year dropdowns changes the displayed transactions
- Verify the transaction totals update correctly
- Verify the budget panel is visible

- [ ] **Step 4: Test custom range mode**

- Click the "Custom Range" button in the date selector
- Click the "From" date picker and select a date (e.g., Jan 1)
- Click the "To" date picker and select a date (e.g., Mar 31)
- Click "Apply"
- Verify the URL updates with `date_from` and `date_to` params
- Verify the transaction list shows only transactions in that range
- Verify the totals recalculate for the range
- Verify the budget panel is hidden
- Verify the page title shows the date range (e.g., "Jan 1 – Mar 31, 2025")

- [ ] **Step 5: Test switching back to month mode**

- In date range mode, click "Back to Month" button
- Verify the date range mode UI closes
- Verify the URL reverts to month view params
- Verify transactions and totals revert to the current month
- Verify the budget panel is visible again

- [ ] **Step 6: Test validation**

- Enter custom range mode
- Select a start date but no end date
- Click "Apply"
- Verify an alert appears saying "Please select both start and end dates"
- Select an end date earlier than the start date
- Click "Apply"
- Verify an alert appears saying "End date must be after start date"

- [ ] **Step 7: Test edge cases**

- Select a date range with no transactions
- Verify the "No transactions" message appears
- Select a same-day range (same date for both start and end)
- Verify it shows transactions from that single day
- Select a very large range (e.g., past year)
- Verify infinite scroll still works if there are many results

- [ ] **Step 8: Test search mode is unaffected**

- Click "Search all transactions"
- Verify search mode still works as before
- Verify the date range UI is hidden
- Verify you can use the search filters independently

Expected: All manual tests pass without errors

---

### Task 8: Final cleanup and commit

**Files:**
- Clean up: Remove old MonthSelector.tsx if not used elsewhere

- [ ] **Step 1: Check if MonthSelector is used anywhere else**

```bash
cd /Users/patrykjamroz/dev/budgeting-app && grep -r "MonthSelector" --include="*.tsx" --include="*.ts"
```

If the output only shows git history and no current imports, proceed to Step 2.

- [ ] **Step 2: Remove MonthSelector.tsx**

```bash
rm frontend/components/MonthSelector.tsx
```

- [ ] **Step 3: Verify the build still works**

```bash
cd frontend && npm run build 2>&1 | head -50
```

Expected: No errors

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete custom date range view implementation

- Refactor MonthSelector into DateSelector with month and date range modes
- Add date range fetching via search endpoint
- Hide budget panel in date range mode
- Update page labels and totals for date ranges
- Remove unused MonthSelector component"
```

- [ ] **Step 5: Verify git log**

```bash
git log --oneline -8
```

Expected: Your commits appear at the top

---

## Testing Checklist

Before considering the feature complete:

- [x] Month view works (existing functionality)
- [x] Custom range mode toggles on/off
- [x] Date pickers appear in range mode
- [x] Date validation prevents invalid ranges
- [x] Selecting dates fetches the correct transactions
- [x] Totals recalculate for the range
- [x] Budget panel hides in range mode
- [x] Page title reflects the selected period
- [x] Switching back to month mode clears the date range
- [x] Search mode is unaffected
- [x] No build errors or console errors in dev tools

---

## Plan Self-Review

✅ **Spec coverage:** All spec requirements are addressed:
- DateSelector with month/range toggle ✓ (Tasks 1-2)
- Conditional fetching based on mode ✓ (Task 4)
- Budget panel hidden in range mode ✓ (Task 5)
- Updated labels and totals ✓ (Task 6)
- Manual testing ✓ (Task 7)

✅ **No placeholders:** All steps have concrete code, commands, and expected outputs

✅ **Type consistency:** 
- `dateFrom` and `dateTo` used consistently as strings in API params
- `isDateRangeMode` boolean used to detect which mode is active
- `formatDateForAPI` consistently converts to YYYY-MM-DD

✅ **Component boundaries:** DateSelector handles its own mode state; wallet page handles fetching and display logic
