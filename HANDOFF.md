# HANDOFF — Self-Host + Feature Completion

Operator index for executing the self-host program with cheaper agents (Sonnet/Haiku) over SSH. Design rationale lives in `docs/superpowers/specs/2026-07-06-selfhost-feature-completion-design.md`. Each item below is a self-contained plan an agent executes literally.

## What this delivers

Get the budgeting app running on the Linux mini PC (personal, LAN-only, edited over SSH/VS Code), ship the missing daily-use features, and add AI auto-categorization (OpenAI). Structured so a later public/SaaS phase is additive, not a rewrite.

## Batch order & dependency graph

```
B0  Self-host foundation ──────────────► (everything assumes env settings + health exist)
      │
      ├─ B1a  Future-date bug        ┐
      ├─ B1b  Toast rollout          ├─ independent of each other; run in any order / parallel
      ├─ B1c  CSV export             ┘
      ├─ B2   Over-budget alerts     (independent; uses existing budget summary endpoint)
      └─ B3a  LLM abstraction (OpenAI) ──► B3b  AI auto-categorization
```

Do **B0 first**. After that, B1a/B1b/B1c/B2/B3a can proceed independently; B3b needs B3a merged.

## Plan register

| Batch | Plan file (`docs/superpowers/plans/`) | Agent | Depends on | Type |
|---|---|---|---|---|
| B0 | `2026-07-06-b0-selfhost-foundation.md` | Sonnet | — | env settings, health, LAN, RUNBOOK |
| B1a | `2026-07-06-b1a-future-date-bug.md` | Sonnet¹ | B0 | bugfix (reproduce-first) |
| B1b | `2026-07-06-b1b-toast-rollout.md` | Haiku | B0 | UI wiring |
| B1c | `2026-07-06-b1c-csv-export.md` | Haiku | B0 | endpoint + button (TDD) |
| B2 | `2026-07-06-b2-over-budget-alerts.md` | Sonnet | B0 | frontend alert + toast |
| B3a | `2026-05-17-llm-abstraction.md` | Sonnet | B0 | LLM layer + quotas (TDD) |
| B3b | `2026-07-06-b3b-ai-auto-categorize.md` | Sonnet | B3a | AI endpoint + chip (TDD) |

¹ B1a is Haiku-capable but reproduction-first with a decision tree — run it as Sonnet, or escalate to the main session if the observed failure mode doesn't match a branch.

**Specs (context, not executable):** `2026-07-06-selfhost-feature-completion-design.md` (master), `2026-05-17-llm-abstraction-design.md` (converted to OpenAI).

## Agent selection

- **Haiku** — bounded, single-concern, low-ambiguity: toast rollout, CSV export. Cheap and mechanical.
- **Sonnet** — multi-file features with logic/judgement: env settings, over-budget, LLM layer, auto-categorization, the bug's decision tree.
- **Escalate to the main (Opus) session** only when a plan's stated reproduction/assumption turns out false (each such plan says so at its branch points).

## Execution workflow (per plan, over SSH on the mini PC)

1. `cd budgeting-app && git checkout main && git pull`
2. Create the branch named in the plan header (e.g. `git checkout -b feat/csv-export`).
3. Work the plan **task by task, top to bottom.** Each task ends with a verification command — **run it and paste the output.** Do not check a box without the passing output. (See `superpowers:verification-before-completion`.)
4. Backend tasks: activate the venv first — `cd backend && source venv/bin/activate`.
5. Commit per task with the message given in the plan.
6. When the plan is done: run the full backend suite (`python manage.py test tests -v 1`) and, for frontend plans, `cd frontend && npm run lint && npm run build`. Then open a review / merge to `main`.

## Conventions every plan already encodes

- **TDD where there's logic** (services, serializers, endpoints, AI): failing test → expected-fail output → implement → passing output. Mechanical UI tasks skip TDD but state a manual check.
- **One plan = one branch = one feature.** Frequent commits (per task).
- **Every code block is copy-paste-ready** and cites real files/anchors verified 2026-07-06.
- **Migrations**: any model change lists `makemigrations` + `migrate` explicitly (only B3a adds models).
- **No app run needed to verify backend** — tests + `manage.py check` suffice; nothing here requires the full app running except the optional manual UI smoke checks.

## After MVP (not planned yet — second wave)

Auth & account management (register/email-login/reset/delete), feature flags, remaining AI (receipt scan, budget recommendations, chat), production hardening (Postgres, settings split, WhiteNoise, HTTPS/HSTS, rate-limit, CORS lockdown, GDPR export/delete + legal pages, Sentry, backups, dep audit, CI), and run-on-boot infra (systemd + Tailscale/Caddy). Each becomes its own spec → plan when you're ready. See the master spec §3 "Later" table.
