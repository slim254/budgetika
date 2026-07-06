# Self-Host + Feature Completion Program

**Date:** 2026-07-06
**Status:** Approved (design shape)
**Owner spec.** Individual features each get their own implementation plan under `docs/superpowers/plans/`. This document is the map: gap analysis, MVP-vs-Later split, batch order, self-host approach, and the hand-off model for cheaper implementation agents (Sonnet/Haiku).

---

## 1. Goal

Get the budgeting app from "feature-rich but never deployed" to "running on a personal Linux mini PC, reached over LAN, editable over SSH/VS Code." Ship the missing user-facing features that make daily use pleasant, add one AI feature (auto-categorization), and structure everything so a later SaaS/public phase is a clean addition rather than a rewrite.

**Deployment reality (decided):**
- **Single user** (the owner, maybe family). Not public.
- Runs on a **Linux mini PC**; the owner **pulls the repo** there and runs both processes.
- Accessed over **home LAN** and edited over **SSH + VS Code Remote**.
- **SaaS-ready later**: keep boundaries clean so public hardening is additive.
- **AI provider = OpenAI.** The LLM layer is provider-agnostic; OpenAI is the first (and currently only) adapter.

---

## 2. Verified state (roadmap vs. reality, 2026-07-06)

Everything the roadmap lists as **Completed** was confirmed present in code (models, views, urls, serializers, services, frontend components). The foundation is solid. What follows is what is **missing or broken**, verified by reading the source — not the roadmap's claims.

| Area | Claim | Reality |
|---|---|---|
| AI layer | Spec + plan exist (`2026-05-17-llm-abstraction*`) | **Not implemented.** No `wallets/ai.py`. No AI models. Blocks all AI features. |
| Registration | `CLAUDE.md` + `backend/CLAUDE.md` say `POST /api/register/` exists "in `config/views.py`" | **False.** No register view, serializer, URL, or frontend page anywhere. Users are created only via `createsuperuser`. **Doc bug to fix.** |
| Email login | — | `CustomTokenObtainPairSerializer` only adds a `username` claim. **No email login.** |
| Toasts | Roadmap item "Toast Messages" (complexity 1) | **Partially done.** `<Toaster/>` already wired in `app/layout.tsx`; `toast()` used in `SavingsGoalDialog`/`SavingsGoalsPanel` only. Item = **finish the rollout**, not build. |
| CSV export | Pending | Not built. Import exists (`GenericCSVImportService`). |
| Over-budget alerts | Pending | Not built. `BudgetSummaryView` already returns `is_over_budget` per category — data is there. |
| Feature flags | Pending | Not built. |
| Health endpoint | Pending | Not built. |
| Prod settings | — | `DEBUG=True`, hardcoded `SECRET_KEY`, `ALLOWED_HOSTS=[]`, `CORS_ALLOW_ALL_ORIGINS=True`, SQLite, no env vars, no `.env`. Frontend API URL hardcoded to `http://localhost:8000/api/` in `axiosInstance.ts` (and a raw `fetch` for refresh). |
| Tests | — | Sparse: only `tests/wallets/test_savings_goals.py`. |
| Bug | "future-dated transactions reset to today" | Real. Frontend posts `date` as a date-only string to a `DateTimeField`. Needs reproduction to confirm exact cause. |

---

## 3. MVP vs Later

**MVP = "I can run it on the mini PC and use it happily every day."** Everything that blocks that, plus the cheap high-impact polish and the one AI feature chosen.

**Later = SaaS/public phase.** Anything only needed when other people (or the open internet) touch it.

### MVP batches

| Batch | Item | Why MVP | Agent | Plan file |
|---|---|---|---|---|
| **B0** | Self-host foundation | Can't run on the mini PC without it | Sonnet | `2026-07-06-b0-selfhost-foundation.md` |
| **B1a** | Fix future-date bug | Data correctness; user-visible daily | Haiku* | `2026-07-06-b1a-future-date-bug.md` |
| **B1b** | Finish toast rollout | Cheap; every mutation should confirm/err | Haiku | `2026-07-06-b1b-toast-rollout.md` |
| **B1c** | CSV export | Natural complement to import; own-your-data | Haiku | `2026-07-06-b1c-csv-export.md` |
| **B2** | Over-budget alerts (in-app) | Closes the budget loop; data already exists | Sonnet | `2026-07-06-b2-over-budget-alerts.md` |
| **B3a** | LLM abstraction (OpenAI) | Prereq for any AI | Sonnet | `2026-05-17-llm-abstraction.md` (converted to OpenAI) |
| **B3b** | AI auto-categorization | The one AI feature chosen | Sonnet | `2026-07-06-b3b-ai-auto-categorize.md` |

*B1a is Haiku-*capable* but reproduction-first — see its plan. If reproduction is inconclusive, escalate to Sonnet.

### Later (own specs/plans in a second wave)

| Item | Bucket | Notes |
|---|---|---|
| Auth & account mgmt (register, email login, password reset, delete) | Auth | MVP uses `createsuperuser`. Register needed only when others sign up. |
| Feature flags | Rollout | Low value for a single user; useful to gate SaaS rollout. |
| AI receipt scan | AI | OpenAI vision; needs image storage. Builds on B3a. |
| AI budget recommendations | AI | Needs 2–3 months history; builds on B3a + budgets. |
| AI chat & tips | AI | Highest complexity; tool use + context assembly. |
| CSV export email digest / over-budget **email** | Notifications | In-app alert ships in B2; email is Later (needs SMTP). |
| Production hardening | Prod | Postgres, `settings/{dev,prod}.py` split, WhiteNoise, HTTPS/HSTS, rate-limit, CORS lockdown, GDPR pages + data export/delete, Sentry, structured logging, backups, dep audit, CI. |
| Infra: reverse proxy + systemd + Tailscale HTTPS | Infra | Optional even for MVP; documented in B0 as an appendix, not required to run. |
| Backlog: bank CSV presets, Open Banking, multi-currency wallets, shared wallets, mobile/PWA | Backlog | Unchanged; out of scope for this program. |

---

## 4. Self-host approach (B0 design)

Single machine, single user → **keep it boring**. Decisions:

1. **SQLite stays.** One user, one box. Postgres is Later. But read the DB config from an env var so switching is a one-line `.env` change, not a code edit.
2. **One `settings.py`, env-driven.** Add `django-environ`. Read `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `DATABASE_URL`, and `OPENAI_API_KEY` from environment / `.env`. Ship `.env.example`. Do **not** split into `settings/dev.py` + `settings/prod.py` yet (that's Later, and env vars already give the separation).
3. **LAN access.**
   - Backend: run bound to `0.0.0.0:8000`; `ALLOWED_HOSTS` includes the mini PC's LAN IP/hostname (from env).
   - Frontend: replace the hardcoded `http://localhost:8000/api/` in `axiosInstance.ts` with `process.env.NEXT_PUBLIC_API_URL` (fallback to localhost). Same for the raw refresh `fetch`. Set `NEXT_PUBLIC_API_URL=http://<mini-pc-ip>:8000/api/` in `frontend/.env.local`.
   - `CORS_ALLOWED_ORIGINS` includes `http://<mini-pc-ip>:3000`. Drop `CORS_ALLOW_ALL_ORIGINS`.
4. **Run mode.** `python manage.py runserver 0.0.0.0:8000` + `npm run dev` is acceptable for personal MVP. Production build (`gunicorn` + `next build && next start`) and systemd/Caddy/Tailscale are documented as an **optional appendix** in the B0 plan for when the owner wants auto-start-on-boot and HTTPS. **No Docker** (SSD budget).
5. **Health endpoint.** `GET /api/health/` → `{"status": "ok"}`, no auth. Cheap, and the appendix's systemd/monitoring hooks use it.
6. **`RUNBOOK.md`** at repo root: clone → venv → `pip install -r requirements.txt` → migrate → `createsuperuser` → seed categories → set `.env` files → run both processes → open `http://<mini-pc-ip>:3000`. Written so it can be followed over SSH with zero prior context.

**No secret rotation drama:** the current hardcoded `SECRET_KEY` is dev-only. B0 generates a fresh one into `.env` (gitignored) and leaves an insecure fallback for local dev so nothing breaks if `.env` is absent.

---

## 5. AI approach (B3, OpenAI)

The existing spec/plan (`2026-05-17-llm-abstraction*`) are **excellent and detailed** but written for Anthropic. B3a converts them:

- `AnthropicAdapter` → `OpenAIAdapter` using the `openai` SDK: `client.chat.completions.create(model=..., messages=...)`; read `resp.choices[0].message.content`, `resp.usage.prompt_tokens`, `resp.usage.completion_tokens`.
- `requirements.txt`: `openai` instead of `anthropic`.
- Settings: `AI_DEFAULT_PROVIDER = "openai"`; `OPENAI_API_KEY = env("OPENAI_API_KEY", default="")`; `AI_MODELS` default to a cheap model (`gpt-4o-mini`) for `auto_categorize`. **Model is env/settings-configurable** so the owner can swap without code changes.
- The protocol, `AIService`, quota/threshold logic, `AIUsageLog`/`ModelPricing`/`UserAIQuota` models, `GET /api/ai/quota/`, admin registration, and the `quota_exception_handler` → HTTP 429 all stay exactly as specified. Provider-agnosticism is the whole point.
- **Quota is a cost seatbelt**, not a business rule — for a single user, set `AI_DEFAULT_MONTHLY_TOKENS` generously; it exists so a runaway loop can't silently rack up spend.

**B3b (auto-categorization)** on top of B3a:
- `POST /api/wallets/categorize/` — body `{ "note": "...", "wallet_id": "..." }`; passes the user's own visible categories as context; returns `{ "suggestions": ["Food & Dining", ...], "usage_warning": ... }`.
- Prompt returns a category **name** constrained to the user's category list (plus "Uncategorized"); backend maps name→id before returning, so the frontend gets real category ids.
- Frontend: suggestion chip(s) under the category picker in `TransactionDialog` (debounced on the note field, create mode). Clicking a chip sets `formData.category`. Plus a "Categorize uncategorized" bulk button on the wallet page (Later-optional; the plan marks it as a stretch task).

---

## 6. Hand-off model (how cheaper agents execute this)

The whole point of this program is that **Sonnet and Haiku execute the plans, not the author**. Each plan is written to be executed literally, with no cross-referencing required.

**Conventions every plan follows:**
- **One plan = one branch = one feature.** Branch name in the plan header (e.g. `feat/csv-export`).
- **TDD where there's logic** (backend services, serializers, AI): write the failing test, show expected failure output, implement, show passing output. Mechanical/UI-only tasks (toast wiring, a button) skip TDD but state a manual verification step.
- **Every code block is copy-paste-ready** and references real files/line-anchors from this repo (verified 2026-07-06).
- **Verification is baked in**: exact commands + expected output after each task. The agent must not claim done without pasting the passing output. (See `superpowers:verification-before-completion`.)
- **Commit per task** with a given message. Conventional Commits.
- **Migrations**: any model change lists `makemigrations` + `migrate` as explicit steps.
- **No app run required to verify backend** — tests + `manage.py check` suffice. Frontend UI tasks list a `npm run lint` + `npm run build` gate and a one-line manual check.

**Model split rationale:**
- **Haiku**: bounded, single-concern, low-ambiguity edits — the future-date fix, toast rollout, CSV export button + endpoint. Cheap and mechanical.
- **Sonnet**: multi-file features with logic and judgement — env settings refactor, over-budget alerts, the LLM layer, auto-categorization.
- **Escalate** to the main (Opus) session only if a plan's reproduction/assumptions turn out false.

**Ordering / dependencies:**
```
B0 (foundation) ──► everything else can assume env settings + health exist
B1a, B1b, B1c ── independent of each other; run in parallel after B0
B2 ── independent (uses existing budget summary endpoint)
B3a (LLM layer) ──► B3b (auto-categorize)
```
`HANDOFF.md` at repo root is the operator's index: batch order, which agent, which plan file, and the SSH workflow.

---

## 7. Files this program creates or changes (high level)

**New docs:** this spec; `HANDOFF.md`; `RUNBOOK.md`; one plan file per MVP batch (§3); updated `ROADMAP.md`; converted LLM spec/plan.

**New code (across batches):**
- Backend: `wallets/ai.py`, AI models + migration, `HealthView`, `CSVExportView`, over-budget nothing-new (frontend-only), env settings, `.env.example`.
- Frontend: `.env.local` usage, `axiosInstance.ts` env URL, toast calls across dialogs/pages, CSV export button, over-budget row styling + toast, category suggestion chip + `api/ai.ts`.

**Doc bug fixes (immediate, this session):** remove/annotate the false `/api/register/` claims in `CLAUDE.md` and `backend/CLAUDE.md`.

---

## 8. Out of scope

- Anything in the "Later" table above (auth, flags, remaining AI, full prod hardening, infra automation, backlog).
- Multi-user data model changes.
- Payment/subscription/tiered quotas (`UserAIQuota.monthly_token_limit` nullability already leaves room).
- Rewriting the DRF "educational note" docstrings (leave the codebase's teaching style intact).
