# Production Readiness Checklist

## 🚨 Critical (Fix ASAP)

1. **Secret Key Management**
   - Your SECRET_KEY is hardcoded and public in settings.py
   - Use environment variables: `SECRET_KEY = os.getenv('SECRET_KEY')`
   - Generate a new key and never commit it to git

2. **CORS Security**
   - Currently allowing all origins (`CORS_ALLOW_ALL_ORIGINS = True`)
   - Set to specific frontend domain: `CORS_ALLOWED_ORIGINS = ["https://yourdomain.com"]`

3. **Token Storage (XSS Risk)**
   - Tokens stored in localStorage are vulnerable to XSS attacks
   - For production: use **httpOnly + secure cookies** instead
   - This requires changes to both frontend and backend (set-cookie headers)

4. **Database**
   - SQLite is not safe for production (single-writer, data loss on crashes)
   - Migrate to PostgreSQL (recommended for Django + financial data)
   - Add automated backups

5. **HTTPS Only**
   - All endpoints must use HTTPS
   - Set `SECURE_SSL_REDIRECT = True`, `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`
   - Use HSTS headers to enforce HTTPS

## ⚠️ Important (Before Launch)

6. **Debug Mode**
   - Set `DEBUG = False` in production
   - Configure `ALLOWED_HOSTS` with your actual domain

7. **Frontend Config**
   - Hardcoded `localhost:8000` URLs won't work in prod
   - Use environment variables for API base URL

8. **Rate Limiting**
   - Add Django Ratelimit to `/api/token/` to prevent brute force
   - Limit login attempts per IP

9. **Audit Logging** (optional for personal app)
   - Log significant user actions (creation/deletion of transactions)
   - Useful for debugging bugs and investigating suspicious patterns
   - Not required for regulatory compliance unless handling real money transfers

10. **Input Validation**
    - Add constraints on amounts (max/min reasonable values)
    - Validate currency matches wallet currency everywhere

## 📋 Before Going Live

11. **Security Checklist**
    - Enable Django security middleware (already there ✓)
    - Add Content Security Policy headers
    - Test for SQL injection, XSS, CSRF vulnerabilities
    - Run `python manage.py check --deploy`

12. **Data Protection**
    - Hash passwords (Django does this by default ✓)
    - Encrypt sensitive data at rest if needed
    - Set up user data deletion/export for GDPR compliance (if handling EU users)

13. **Monitoring**
    - Set up error tracking (Sentry)
    - Monitor API response times
    - Alert on failed login attempts

14. **Testing**
    - Write tests for permission checks (users can't access other users' wallets)
    - Test transaction currency validation
    - Test import/export functionality

15. **Deployment Setup**
    - Use proper WSGI server (Gunicorn)
    - Reverse proxy (Nginx)
    - Don't serve static files directly from Django

---

## Quick Wins (Do These First)

- Move all hardcoded strings to `.env` file
- Run `python manage.py check --deploy`
- Switch to PostgreSQL
- Switch tokens from localStorage to httpOnly cookies

## Most Urgent

Security issues #1–5 must be fixed before launch.
