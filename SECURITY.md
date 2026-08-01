# Security Policy

Budgetika handles sensitive financial data. This document outlines the security model, responsible disclosure process, and hardening measures implemented across the platform.

---

## Supported Versions

| Version | Supported |
| :--- | :--- |
| `main` branch | Yes |
| Latest release tag | Yes |
| All previous releases | No — please upgrade immediately |

---

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability in Budgetika, please follow the responsible disclosure process below. **Do not open a public GitHub issue** for security-related matters.

### Steps

1. **Email the maintainer directly** with a detailed description of the vulnerability, including:
   - Steps to reproduce
   - Severity assessment (CVSS score if applicable)
   - Potential impact on users
   - Suggested fix (if any)

2. **Allow reasonable time** for a response (within 72 hours) and for a patch to be developed.

3. **Do not publicly disclose** the vulnerability until a fix has been released and coordinated with the maintainer.

---

## Security Architecture

### Authentication & Authorization

Budgetika uses JWT-based authentication with the following safeguards:

- **Short-lived access tokens** (60-minute expiry) minimize the window of token compromise.
- **Refresh token rotation** ensures that each refresh invalidates the previous refresh token.
- **Server-side token validation** via `djangorestframework-simplejwt` ensures all API requests are authenticated before reaching business logic.
- **User-scoped data access** — every query is filtered by the requesting user's ID. A user cannot access another user's wallets, transactions, or categories.

### Data Protection

| Concern | Mitigation |
| :--- | :--- |
| Secrets in source code | All secrets (API keys, database credentials, JWT secret) are managed via `.env` files using `django-environ`. Default values in `.env.example` are non-functional placeholders. |
| Database encryption | SQLite/PostgreSQL stores data at rest. For production, full-disk encryption (LUKS, FileVault) is recommended at the OS level. |
| CORS policy | The backend enforces an explicit CORS allowlist. Only configured frontend origins can make cross-origin requests. No `*` wildcard is used. |
| SQL injection | All database queries use Django's ORM with parameterized queries. Raw SQL is not used anywhere in the codebase. |
| XSS protection | Django's built-in template escaping protects the admin panel. The frontend uses React's automatic JSX escaping. |
| CSRF | CSRF tokens are enforced on all form submissions via Django's middleware. |

### AI & Third-Party Integrations

The AI integration layer is designed with security in mind:

- **Token isolation** — AI API keys are stored in environment variables, never in the database or frontend bundle.
- **Quota enforcement** — The `AIService` enforces per-user monthly token limits, preventing abuse of the LLM API.
- **Input sanitization** — Transaction notes and CSV data are sanitized before being sent to the LLM to prevent prompt injection attacks.
- **Audit logging** — Every AI call is logged to `AIUsageLog` with provider, model, token count, and cost, enabling anomaly detection.

### Network Security (Self-Host Deployments)

For users deploying Budgetika on a local network (mini-PC):

- The backend binds to `0.0.0.0` for LAN access but should be placed behind a reverse proxy (Caddy, Nginx) for HTTPS termination.
- **Tailscale** or **WireGuard** is recommended for secure remote access instead of exposing ports directly to the internet.
- Automated database backups are encrypted at the filesystem level when the host uses full-disk encryption.

---

## Dependency Management

Both frontend and backend dependencies should be kept up to date to patch known vulnerabilities:

```bash
# Backend
cd backend && pip list --outdated

# Frontend
cd frontend && pnpm audit
```

For critical security patches, update immediately:

```bash
# Backend
pip install -r requirements.txt --upgrade

# Frontend
pnpm update
```

---

## Compliance Notes

While Budgetika is designed for personal use, the architecture supports compliance with data protection regulations:

- **GDPR Article 17 (Right to Erasure):** The `on_delete=CASCADE` relationships on all models ensure that deleting a user removes all associated financial data.
- **GDPR Article 20 (Data Portability):** The `manage.py export_all` command provides a complete CSV export of all user data.
- **No third-party tracking:** The application contains no analytics SDKs, ad networks, or tracking pixels. All data stays within the user's infrastructure.

---

## Security Checklist for Production Deployment

Before deploying Budgetika in a production environment, verify the following:

- [ ] `DEBUG = False` in `.env`
- [ ] `SECRET_KEY` is a cryptographically random 50+ character string
- [ ] `ALLOWED_HOSTS` contains only the production domain
- [ ] `CORS_ALLOWED_ORIGINS` contains only the production frontend URL
- [ ] HTTPS is enforced (via reverse proxy or CDN)
- [ ] `HSTS` header is set
- [ ] Rate limiting is enabled on auth endpoints
- [ ] Database backups are automated and stored offsite
- [ ] `django-environ` is the only source of configuration (no hardcoded values)
