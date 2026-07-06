# B1b — Finish Toast Notification Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. This is mechanical UI wiring — no TDD; verify with `npm run lint` + `npm run build` and a manual click-through. Steps use checkbox (`- [ ]`).

**Goal:** Every user-initiated mutation (create/update/delete/import/transfer) shows a success or error toast. Success toasts auto-dismiss (~3s, sonner default); error toasts stay until dismissed.

**Architecture:** `sonner` is already installed and `<Toaster />` is already mounted in `frontend/app/layout.tsx`. `toast()` is already used in `SavingsGoalDialog`/`SavingsGoalsPanel`. This plan applies the same `toast.success()` / `toast.error()` pattern to every other mutation site. Keep existing inline field-error UI (form validation) — toasts are for the outcome of the network call, not per-field validation.

**Tech Stack:** Next.js 15, `sonner`.

## Global Constraints

- Import with: `import { toast } from "sonner";`
- Success: `toast.success("<message>")`. Error: `toast.error("<message>")`.
- Do **not** remove existing `setError(...)` inline messages inside forms; **add** a `toast.error(...)` alongside them in `catch` blocks.
- Branch: `feat/toast-rollout`.

---

### Task 1: TransactionDialog (worked example — copy this pattern everywhere)

**Files:**
- Modify: `frontend/components/TransactionDialog.tsx`

- [ ] **Step 1: Add the import**

After the existing import block (near the top, after the `lucide-react` import), add:
```typescript
import { toast } from "sonner";
```

- [ ] **Step 2: Toast on transaction save success**

In `handleSubmit`, the edit branch currently reads:
```typescript
      if (transaction) {
        await axiosInstance.put(`transactions/${transaction.id}/`, payload);
        onSaved();
        onClose();
      } else {
```
Insert a success toast:
```typescript
      if (transaction) {
        await axiosInstance.put(`transactions/${transaction.id}/`, payload);
        toast.success("Transaction updated");
        onSaved();
        onClose();
      } else {
```
And in the create branch, after `await axiosInstance.post("transactions/", payload);` (and after the optional recurring POST), before `onSaved();`, add:
```typescript
        toast.success(isRecurring ? "Transaction added and made recurring" : "Transaction added");
```

- [ ] **Step 3: Toast on save failure**

In the `catch` block of `handleSubmit`, which reads:
```typescript
    } catch (err) {
      console.error("Failed to save transaction:", err);
      setError("Failed to save transaction. Please try again.");
    } finally {
```
add a toast:
```typescript
    } catch (err) {
      console.error("Failed to save transaction:", err);
      setError("Failed to save transaction. Please try again.");
      toast.error("Failed to save transaction");
    } finally {
```

- [ ] **Step 4: Toast on category/tag creation**

In `handleCreateCategory`, after `onCategoriesChanged();` add `toast.success(\`Category "${newCategoryName.trim()}" created\`);` (capture the name before you clear it, or use `response.data.name`). In its `catch`, add `toast.error("Failed to create category");`. Do the same in `handleCreateTag` (`toast.success(\`Tag "${response.data.name}" created\`)` / `toast.error("Failed to create tag")`).

- [ ] **Step 5: Verify**

```bash
cd frontend && npm run lint && npm run build
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/TransactionDialog.tsx
git commit -m "feat: add toasts to transaction dialog"
```

---

### Task 2: Wallet page mutations

**Files:**
- Modify: `frontend/app/wallet/[id]/page.tsx`

- [ ] **Step 1: Add `import { toast } from "sonner";`** (if not already present).

- [ ] **Step 2: Add toasts at each mutation site.** Open the file and apply:

| Location | Success toast | Error toast (in `catch`) |
|---|---|---|
| Transaction delete (`await axiosInstance.delete(\`transactions/${transactionId}/\`)`, ~line 226) | `toast.success("Transaction deleted")` | `toast.error("Failed to delete transaction")` |
| Import complete (`handleImportComplete`, ~line 278) | `toast.success("Import complete")` | `toast.error("Import failed")` |

(Transfer create/edit success toasts live in the transfer dialog — Task 3.)

- [ ] **Step 3: Verify + commit**

```bash
cd frontend && npm run lint && npm run build
git add frontend/app/wallet/[id]/page.tsx
git commit -m "feat: add toasts to wallet page mutations"
```

---

### Task 3: Remaining dialogs and settings

**Files (each is a mutation surface):**
- `frontend/components/WalletDialog.tsx`
- `frontend/components/DeleteWalletDialog.tsx`
- `frontend/components/WalletTransferDialog.tsx`
- `frontend/components/BudgetManagementDialog.tsx`
- `frontend/components/CSVImportDialog.tsx`
- `frontend/app/settings/page.tsx`
- `frontend/app/dashboard/page.tsx` (wallet create/delete if it mutates there)

- [ ] **Step 1: In each file, add `import { toast } from "sonner";` and apply this rule:** on the success path of every create/update/delete/save network call, add a `toast.success(...)`; in every `catch`, add a `toast.error(...)`. Use these messages:

| File | Action → message |
|---|---|
| `WalletDialog.tsx` | create → `toast.success("Wallet created")`; update → `toast.success("Wallet updated")`; error → `toast.error("Failed to save wallet")` |
| `DeleteWalletDialog.tsx` | delete → `toast.success("Wallet deleted")`; error → `toast.error("Failed to delete wallet")` |
| `WalletTransferDialog.tsx` | create → `toast.success("Transfer saved")`; update → `toast.success("Transfer updated")`; delete → `toast.success("Transfer deleted")`; error → `toast.error("Failed to save transfer")` |
| `BudgetManagementDialog.tsx` | save rule → `toast.success("Budget saved")`; delete → `toast.success("Budget removed")`; error → `toast.error("Failed to save budget")` |
| `CSVImportDialog.tsx` | error paths → `toast.error("Import failed")` (success toast already shown by the wallet page's `handleImportComplete`) |
| `settings/page.tsx` | any save (categories, tags, recurring, profile) → `toast.success("Saved")`; delete → `toast.success("Deleted")`; error → `toast.error("Something went wrong")` |
| `dashboard/page.tsx` | wallet create/delete if present → mirror `WalletDialog`/`DeleteWalletDialog` messages |

Keep existing inline error text; toasts are additive.

- [ ] **Step 2: Verify**

```bash
cd frontend && npm run lint && npm run build
```
Expected: no errors.

- [ ] **Step 3: Manual smoke check** (on the running app, later): create a transaction → green toast; disconnect backend and retry → red toast that stays until dismissed.

- [ ] **Step 4: Commit**

```bash
git add frontend/components frontend/app/settings/page.tsx frontend/app/dashboard/page.tsx
git commit -m "feat: add toasts across remaining dialogs and settings"
```
