# Contributing to Budgetika

Thank you for your interest in contributing to Budgetika. This document outlines the guidelines and processes for contributing to the project.

---

## Getting Started

### Prerequisites

Before contributing, ensure you have the following installed:

- **Python 3.13+** for the backend
- **Node.js 18+** with **pnpm** for the frontend
- **Git** for version control

### Development Environment

Clone the repository and set up both the backend and frontend as described in `README.md`. Verify both services are running before making changes:

```bash
# Verify backend health
curl http://localhost:8100/api/health/

# Verify frontend
curl http://localhost:3100
```

---

## Development Workflow

### Branching Strategy

All work should be done on feature branches following this naming convention:

| Type | Pattern | Example |
| :--- | :--- | :--- |
| Feature | `feature/description` | `feature/csv-import-ai` |
| Bug Fix | `fix/description` | `fix/transfer-currency-race` |
| Refactor | `refactor/description` | `refactor/serializer-validation` |
| Documentation | `docs/description` | `docs/api-endpoint-update` |

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
type(scope): subject

body

footer
```

**Valid types:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`, `ci`, `perf`

**Examples:**

```
feat(wallets): add batch categorization for CSV import
fix(transactions): resolve duplicate transfer_ref on edge cases
docs(readme): update architecture diagram and deployment steps
```

---

## Code Standards

### Backend (Python / Django)

- Follow [PEP 8](https://peps.python.org/pep-0008/) for code style.
- All API endpoints must include input validation and return appropriate HTTP status codes.
- Database queries should be optimized — avoid N+1 problems using `select_related` and `prefetch_related`.
- Sensitive data (API keys, secrets) must **never** be committed. Use `.env` files and `django-environ`.
- Every new model must include migrations. Run `python manage.py makemigrations` before committing.

### Frontend (TypeScript / React)

- All components must be typed. Avoid `any` types unless absolutely necessary.
- API calls must go through the centralized axios instance (`frontend/api/axiosInstance.ts`).
- State management should use TanStack Query for server state, React state for local UI state.
- Follow the shadcn/ui component patterns already established in the project.
- New UI components must be accessible (proper ARIA attributes, keyboard navigation).

### Testing

| Layer | Requirement | Location |
| :--- | :--- | :--- |
| Backend | All new API endpoints require at least one integration test | `backend/tests/` |
| Frontend | Critical user flows require component or integration tests | `frontend/__tests__/` |
| Edge Cases | Boundary conditions (empty states, invalid input, network errors) must be tested | Both |

Run the full test suite before submitting a pull request:

```bash
# Backend tests
cd backend && python manage.py test

# Frontend type check
cd frontend && npx tsc --noEmit
```

---

## Pull Request Process

1. **Fork** the repository and create your feature branch.
2. **Develop** your changes following the code standards above.
3. **Test** all changes — backend tests must pass and frontend must type-check.
4. **Document** any new API endpoints, configuration options, or user-facing changes in the README.
5. **Submit** a pull request with a clear description of the changes, motivation, and any breaking changes.

### PR Template

Every pull request should include:

- **Summary:** What does this PR do?
- **Motivation:** Why is this change needed?
- **Testing:** How was this tested?
- **Breaking Changes:** Does this affect existing functionality?
- **Screenshots:** (for frontend changes) Before/after comparison

---

## Reporting Issues

When reporting a bug, include:

1. **Steps to reproduce** the issue
2. **Expected behavior** vs **actual behavior**
3. **Environment** (OS, browser, backend version)
4. **Relevant logs** or error messages from the browser console or Django output

---

## Architecture Overview

Budgetika follows a decoupled architecture:

- **Backend** (`/backend`): Django REST Framework API with JWT authentication. Handles all business logic, data persistence, and AI integrations.
- **Frontend** (`/frontend`): Next.js 15 application with server-side rendering. Consumes the backend API via TanStack Query.
- **Shared Models**: Type definitions in `frontend/models/` mirror the Django model layer for type safety.

For detailed architecture documentation, see `ARCHITECTURE.md`.

---


## License

By contributing to Budgetika, you agree that your contributions will be licensed under the project's MIT License.
