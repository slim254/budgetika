# Frontend

Next.js 15 (App Router), TypeScript, Tailwind CSS, shadcn/ui component library.

## Structure

```
frontend/
├── app/                    Next.js App Router pages
│   ├── dashboard/page.tsx  Wallet list
│   ├── wallet/[id]/page.tsx  Wallet detail + transaction table
│   ├── login/page.tsx
│   └── settings/page.tsx
├── components/
│   ├── ui/                 shadcn/ui primitives (don't edit these)
│   ├── TransactionDialog.tsx
│   ├── CSVImportDialog.tsx
│   ├── ColorPicker.tsx
│   ├── IconPicker.tsx
│   ├── MonthSelector.tsx
│   └── ProtectedRoute.tsx
├── contexts/
│   └── AuthProvider.tsx    JWT token management + user context
├── api/
│   └── axiosInstance.ts    Axios with JWT interceptors
└── models/
    └── wallets.ts          All TypeScript interfaces
```

## Running

```bash
npm run dev      # http://localhost:3000
npm run build
npm run lint
```

## API Client

All HTTP calls use the configured axios instance:

```typescript
import { axiosInstance } from "@/api/axiosInstance";
const response = await axiosInstance.get<Wallet[]>("wallets/");
```

- Base URL: `http://localhost:8000/api/`
- Auth: JWT injected automatically from `localStorage` (`token.access`)
- 401 handling: attempts token refresh; on failure clears token and redirects to `/login`

Do **not** use raw `fetch` — always use `axiosInstance`.

## Types

All types are in `frontend/models/wallets.ts`. Key ones:

```typescript
Wallet          — id, name, currency, initial_value, balance (computed)
Transaction     — id, note, amount, currency, date, category, tags
Category        — id, name, icon, color, is_visible, is_archived
Tag             — id, name, icon, color, is_visible
TransactionFormData  — write shape (category: string|null, tag_ids: string[])
CSVParseResponse, CSVExecuteResponse, CSVColumnMapping, AmountConfig, FilterRule
```

Amount is always signed: **positive = income, negative = expense**.

## UI Components

shadcn/ui primitives live in `components/ui/`. Install new ones with:
```bash
npx shadcn@latest add <component-name>
```

Icons come from `lucide-react`. Icon names are stored as strings (e.g., `"shopping-cart"`) in the DB and rendered via `DynamicIcon` from `IconPicker.tsx`.

Color values are hex strings (e.g., `"#F97316"`). Tinted backgrounds use `color + "20"` (20% opacity hex suffix).

## Auth

`AuthProvider` (contexts/AuthProvider.tsx) stores the JWT object in `localStorage` under the key `"token"` as `{ access: "...", refresh: "..." }`.

`ProtectedRoute` wraps pages that require auth — it redirects to `/login` if no token is present.

## Page Patterns

Pages are client components (`"use client"`). They:
1. Fetch data with `axiosInstance` in `useEffect`
2. Manage local state with `useState`
3. Pass data down to dialog/modal components as props
4. Refresh data after mutations by re-calling fetch functions

Month/year filtering on the wallet page uses URL search params (`?month=M&year=Y`) so the URL is shareable.
