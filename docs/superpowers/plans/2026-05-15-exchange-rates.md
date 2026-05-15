# Exchange Rates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add on-demand exchange rate fetching (Frankfurter API, DB-cached) so the dashboard shows a converted total balance with a currency switcher, and TransactionDialog lets users enter amounts in a different currency that auto-converts to the wallet's currency on save.

**Architecture:** Rates are fetched on-demand from `api.frankfurter.app` and cached in a new `ExchangeRate` DB table. A new `UserProfile` model stores the user's preferred display currency. The dashboard accepts `?base_currency=X` to convert wallet balances before summing. The frontend reads profile preference (falling back to browser locale) and persists changes back via PATCH.

**Tech Stack:** Django 5.1 + DRF (backend), Next.js 15 + TypeScript + shadcn/ui (frontend), `requests` library for Frankfurter HTTP calls.

---

## File Map

**Create:**
- `frontend/api/profile.ts` — profile API (get/patch preferred_currency)
- `frontend/api/exchangeRates.ts` — exchange rate API (get rate for base/quote/date)

**Modify:**
- `backend/requirements.txt` — add `requests`
- `backend/wallets/models.py` — add `CURRENCY_CHOICES` constant, `ExchangeRate`, `UserProfile`
- `backend/wallets/services.py` — add `get_rate()`, update `DashboardService.user_summary()`
- `backend/wallets/serializers.py` — add `UserProfileSerializer`
- `backend/wallets/views.py` — add `ExchangeRateView`, `UserProfileView`; update `UserDashboard`
- `backend/wallets/signals.py` — add `UserProfile` creation signal
- `backend/wallets/tests.py` — add four new test classes
- `backend/config/urls.py` — register new views at `/api/exchange-rates/` and `/api/profile/`
- `frontend/lib/currency.ts` — add `getLocaleCurrency()`
- `frontend/components/MetricsSummaryCards.tsx` — add currency switcher
- `frontend/app/dashboard/page.tsx` — fetch profile, pass base_currency, handle currency change
- `frontend/components/TransactionDialog.tsx` — add cross-currency conversion section

---

## Task 1: Add `requests` to backend dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add requests to requirements.txt**

  In `backend/requirements.txt`, add this line (keep alphabetical order):

  ```
  requests==2.32.3
  ```

- [ ] **Step 2: Install**

  ```bash
  cd backend && source venv/bin/activate && pip install requests==2.32.3
  ```

  Expected: `Successfully installed requests-2.32.3` (certifi, charset-normalizer, idna, urllib3 may also install).

- [ ] **Step 3: Commit**

  ```bash
  git add backend/requirements.txt
  git commit -m "chore: add requests dependency for Frankfurter API"
  ```

---

## Task 2: ExchangeRate + UserProfile models

**Files:**
- Modify: `backend/wallets/models.py`

- [ ] **Step 1: Add `CURRENCY_CHOICES` constant and new models**

  In `backend/wallets/models.py`, add `CURRENCY_CHOICES` near the top (after imports, before the first class), then add the two new models at the end of the file. Also replace the three existing inline currency choice tuples with `CURRENCY_CHOICES`.

  After the imports block, add:

  ```python
  CURRENCY_CHOICES = [("usd", "usd"), ("eur", "eur"), ("gbp", "gbp"), ("pln", "pln")]
  ```

  Find the three places in `models.py` that have:
  ```python
  choices=[("usd", "usd"), ("eur", "eur"), ("gbp", "gbp"), ("pln", "pln")],
  ```
  Replace each with:
  ```python
  choices=CURRENCY_CHOICES,
  ```

  At the very end of the file, add:

  ```python
  class ExchangeRate(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
      base_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
      quote_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
      date = models.DateField()
      rate = models.DecimalField(max_digits=12, decimal_places=6)

      class Meta:
          unique_together = ("base_currency", "quote_currency", "date")
          indexes = [models.Index(fields=["base_currency", "quote_currency", "date"])]

      def __str__(self):
          return f"{self.base_currency}/{self.quote_currency} on {self.date}: {self.rate}"


  class UserProfile(models.Model):
      user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
      preferred_currency = models.CharField(
          max_length=3, choices=CURRENCY_CHOICES, null=True, blank=True
      )

      def __str__(self):
          return f"{self.user.username}'s profile"
  ```

- [ ] **Step 2: Create and run migration**

  ```bash
  cd backend && source venv/bin/activate
  python manage.py makemigrations wallets --name add_exchange_rate_user_profile
  python manage.py migrate
  ```

  Expected: migration file created, `OK` on migrate.

- [ ] **Step 3: Verify models are accessible in shell**

  ```bash
  python manage.py shell -c "from wallets.models import ExchangeRate, UserProfile; print('OK')"
  ```

  Expected: `OK`

- [ ] **Step 4: Commit**

  ```bash
  git add backend/wallets/models.py backend/wallets/migrations/
  git commit -m "feat: add ExchangeRate and UserProfile models"
  ```

---

## Task 3: UserProfile registration signal

**Files:**
- Modify: `backend/wallets/signals.py`
- Modify: `backend/wallets/tests.py`

- [ ] **Step 1: Write the failing test**

  Append to `backend/wallets/tests.py`:

  ```python
  class UserProfileSignalTest(TestCase):
      def test_profile_created_on_user_registration(self):
          from wallets.models import UserProfile
          user = User.objects.create_user(username="newuser", password="pass")
          self.assertTrue(UserProfile.objects.filter(user=user).exists())

      def test_profile_preferred_currency_is_null_by_default(self):
          from wallets.models import UserProfile
          user = User.objects.create_user(username="newuser2", password="pass")
          profile = UserProfile.objects.get(user=user)
          self.assertIsNone(profile.preferred_currency)
  ```

- [ ] **Step 2: Run test to verify it fails**

  ```bash
  cd backend && source venv/bin/activate
  python manage.py test wallets.tests.UserProfileSignalTest -v 2
  ```

  Expected: FAIL — `AssertionError: False is not true` (profile doesn't exist yet).

- [ ] **Step 3: Add signal to signals.py**

  In `backend/wallets/signals.py`, add a second receiver after the existing `create_default_categories_for_user`:

  ```python
  @receiver(post_save, sender=User)
  def create_user_profile(sender, instance, created, **kwargs):
      if not created:
          return
      from .models import UserProfile
      UserProfile.objects.get_or_create(user=instance)
  ```

- [ ] **Step 4: Run test to verify it passes**

  ```bash
  python manage.py test wallets.tests.UserProfileSignalTest -v 2
  ```

  Expected: OK (2 tests pass).

- [ ] **Step 5: Commit**

  ```bash
  git add backend/wallets/signals.py backend/wallets/tests.py
  git commit -m "feat: auto-create UserProfile on user registration"
  ```

---

## Task 4: `get_rate()` service function

**Files:**
- Modify: `backend/wallets/services.py`
- Modify: `backend/wallets/tests.py`

- [ ] **Step 1: Write the failing tests**

  Append to `backend/wallets/tests.py`:

  ```python
  class GetRateTest(TestCase):
      def test_same_currency_returns_one(self):
          from wallets.services import get_rate
          import datetime
          result = get_rate("pln", "pln", datetime.date(2024, 1, 15))
          self.assertEqual(result, Decimal("1"))

      def test_returns_cached_rate_without_network_call(self):
          from wallets.services import get_rate
          from wallets.models import ExchangeRate
          import datetime
          ExchangeRate.objects.create(
              base_currency="pln", quote_currency="eur",
              date=datetime.date(2024, 1, 15), rate=Decimal("0.230000"),
          )
          result = get_rate("pln", "eur", datetime.date(2024, 1, 15))
          self.assertEqual(result, Decimal("0.230000"))

      @patch("wallets.services.requests.get")
      def test_fetches_from_frankfurter_and_caches(self, mock_get):
          from wallets.services import get_rate
          from wallets.models import ExchangeRate
          import datetime
          mock_get.return_value.json.return_value = {
              "date": "2024-01-15",
              "rates": {"EUR": 0.23},
          }
          result = get_rate("pln", "eur", datetime.date(2024, 1, 15))
          self.assertEqual(result, Decimal("0.23"))
          self.assertTrue(
              ExchangeRate.objects.filter(
                  base_currency="pln", quote_currency="eur",
                  date=datetime.date(2024, 1, 15),
              ).exists()
          )

      @patch("wallets.services.requests.get")
      def test_weekend_stores_both_requested_and_returned_dates(self, mock_get):
          from wallets.services import get_rate
          from wallets.models import ExchangeRate
          import datetime
          # Frankfurter returns Friday 2024-01-12 for Saturday 2024-01-13
          mock_get.return_value.json.return_value = {
              "date": "2024-01-12",
              "rates": {"EUR": 0.23},
          }
          get_rate("pln", "eur", datetime.date(2024, 1, 13))
          self.assertTrue(
              ExchangeRate.objects.filter(
                  base_currency="pln", quote_currency="eur",
                  date=datetime.date(2024, 1, 12),
              ).exists()
          )
          self.assertTrue(
              ExchangeRate.objects.filter(
                  base_currency="pln", quote_currency="eur",
                  date=datetime.date(2024, 1, 13),
              ).exists()
          )
  ```

  Also add this import at the top of `tests.py` (after existing imports):

  ```python
  from unittest.mock import patch, MagicMock
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  python manage.py test wallets.tests.GetRateTest -v 2
  ```

  Expected: ERROR — `ImportError: cannot import name 'get_rate' from 'wallets.services'`.

- [ ] **Step 3: Implement `get_rate()` in services.py**

  In `backend/wallets/services.py`, add `import requests` and `from datetime import date as _date` to the imports block at the top:

  ```python
  import requests
  from datetime import date as _date
  ```

  Also add `ExchangeRate` to the existing model import line:

  ```python
  from .models import ExchangeRate, Transaction, TransactionCategory, UserTransactionTag, Wallet
  ```

  Then add the `get_rate` function before the `GenericCSVImportService` class (i.e., near the top of the file, after imports):

  ```python
  def get_rate(base: str, quote: str, rate_date: _date) -> Decimal:
      if base == quote:
          return Decimal("1")

      try:
          return ExchangeRate.objects.get(
              base_currency=base, quote_currency=quote, date=rate_date
          ).rate
      except ExchangeRate.DoesNotExist:
          pass

      response = requests.get(
          f"https://api.frankfurter.app/{rate_date}",
          params={"from": base.upper(), "to": quote.upper()},
          timeout=5,
      )
      response.raise_for_status()
      data = response.json()
      returned_date = _date.fromisoformat(data["date"])
      rate = Decimal(str(data["rates"][quote.upper()]))

      ExchangeRate.objects.get_or_create(
          base_currency=base, quote_currency=quote, date=returned_date,
          defaults={"rate": rate},
      )
      if returned_date != rate_date:
          ExchangeRate.objects.get_or_create(
              base_currency=base, quote_currency=quote, date=rate_date,
              defaults={"rate": rate},
          )

      return rate
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  python manage.py test wallets.tests.GetRateTest -v 2
  ```

  Expected: OK (4 tests pass).

- [ ] **Step 5: Commit**

  ```bash
  git add backend/wallets/services.py backend/wallets/tests.py
  git commit -m "feat: add get_rate() service with on-demand Frankfurter fetch and DB caching"
  ```

---

## Task 5: ExchangeRate API endpoint

**Files:**
- Modify: `backend/wallets/views.py`
- Modify: `backend/config/urls.py`
- Modify: `backend/wallets/tests.py`

- [ ] **Step 1: Write the failing tests**

  Append to `backend/wallets/tests.py`:

  ```python
  class ExchangeRateEndpointTest(TestCase):
      def setUp(self):
          self.user = User.objects.create_user(username="tester_er", password="pass")
          self.client = make_client(self.user)

      def test_requires_authentication(self):
          from rest_framework.test import APIClient
          response = APIClient().get("/api/exchange-rates/?base=pln&quote=eur&date=2024-01-15")
          self.assertEqual(response.status_code, 401)

      def test_returns_400_for_invalid_base_currency(self):
          response = self.client.get("/api/exchange-rates/?base=xyz&quote=eur&date=2024-01-15")
          self.assertEqual(response.status_code, 400)

      def test_returns_400_for_invalid_quote_currency(self):
          response = self.client.get("/api/exchange-rates/?base=pln&quote=xyz&date=2024-01-15")
          self.assertEqual(response.status_code, 400)

      def test_returns_400_for_invalid_date(self):
          response = self.client.get("/api/exchange-rates/?base=pln&quote=eur&date=not-a-date")
          self.assertEqual(response.status_code, 400)

      @patch("wallets.views.get_rate")
      def test_returns_rate_for_valid_params(self, mock_get_rate):
          mock_get_rate.return_value = Decimal("0.230000")
          response = self.client.get("/api/exchange-rates/?base=pln&quote=eur&date=2024-01-15")
          self.assertEqual(response.status_code, 200)
          self.assertIn("rate", response.data)
          self.assertIn("date", response.data)
          self.assertEqual(response.data["date"], "2024-01-15")

      @patch("wallets.views.get_rate")
      def test_date_defaults_to_today(self, mock_get_rate):
          import datetime
          mock_get_rate.return_value = Decimal("0.23")
          response = self.client.get("/api/exchange-rates/?base=pln&quote=eur")
          self.assertEqual(response.status_code, 200)
          self.assertEqual(response.data["date"], str(datetime.date.today()))
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  python manage.py test wallets.tests.ExchangeRateEndpointTest -v 2
  ```

  Expected: ERROR — 404 responses (URL not registered yet).

- [ ] **Step 3: Add ExchangeRateView to views.py**

  In `backend/wallets/views.py`, add this import near the top with the existing service imports:

  ```python
  from wallets.services import get_rate
  ```

  Also add `from datetime import date` to the imports if not already present.

  Then add the view class (anywhere in the file, e.g., after `UserDashboard`):

  ```python
  class ExchangeRateView(APIView):
      permission_classes = [IsAuthenticated]
      authentication_classes = [JWTAuthentication]

      def get(self, request):
          base = request.query_params.get("base", "").lower()
          quote = request.query_params.get("quote", "").lower()
          date_str = request.query_params.get("date", str(date.today()))

          valid = {"usd", "eur", "gbp", "pln"}
          if base not in valid or quote not in valid:
              return Response(
                  {"error": "Invalid currency. Must be one of: usd, eur, gbp, pln"},
                  status=400,
              )

          try:
              rate_date = date.fromisoformat(date_str)
          except ValueError:
              return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

          try:
              rate = get_rate(base, quote, rate_date)
          except Exception:
              return Response({"error": "Failed to fetch exchange rate."}, status=503)

          return Response({"rate": str(rate), "date": str(rate_date)})
  ```

- [ ] **Step 4: Register the URL in config/urls.py**

  In `backend/config/urls.py`, add `ExchangeRateView` to the existing import from `wallets.views`:

  ```python
  from wallets.views import TransactionCreate, TransactionDetail, UserDashboard, ExchangeRateView
  ```

  Add the URL to `urlpatterns`:

  ```python
  path('api/exchange-rates/', ExchangeRateView.as_view(), name='exchange-rates'),
  ```

- [ ] **Step 5: Run tests to verify they pass**

  ```bash
  python manage.py test wallets.tests.ExchangeRateEndpointTest -v 2
  ```

  Expected: OK (6 tests pass).

- [ ] **Step 6: Commit**

  ```bash
  git add backend/wallets/views.py backend/config/urls.py backend/wallets/tests.py
  git commit -m "feat: add GET /api/exchange-rates/ endpoint"
  ```

---

## Task 6: UserProfile API endpoint

**Files:**
- Modify: `backend/wallets/serializers.py`
- Modify: `backend/wallets/views.py`
- Modify: `backend/config/urls.py`
- Modify: `backend/wallets/tests.py`

- [ ] **Step 1: Write the failing tests**

  Append to `backend/wallets/tests.py`:

  ```python
  class UserProfileEndpointTest(TestCase):
      def setUp(self):
          self.user = User.objects.create_user(username="tester_profile", password="pass")
          self.client = make_client(self.user)

      def test_get_returns_null_preferred_currency_when_no_profile(self):
          from wallets.models import UserProfile
          UserProfile.objects.filter(user=self.user).delete()
          response = self.client.get("/api/profile/")
          self.assertEqual(response.status_code, 200)
          self.assertIsNone(response.data["preferred_currency"])

      def test_get_returns_saved_currency(self):
          from wallets.models import UserProfile
          UserProfile.objects.get_or_create(user=self.user, defaults={"preferred_currency": "eur"})
          UserProfile.objects.filter(user=self.user).update(preferred_currency="eur")
          response = self.client.get("/api/profile/")
          self.assertEqual(response.status_code, 200)
          self.assertEqual(response.data["preferred_currency"], "eur")

      def test_patch_creates_profile_and_sets_currency(self):
          from wallets.models import UserProfile
          UserProfile.objects.filter(user=self.user).delete()
          response = self.client.patch("/api/profile/", {"preferred_currency": "gbp"}, format="json")
          self.assertEqual(response.status_code, 200)
          self.assertEqual(response.data["preferred_currency"], "gbp")

      def test_patch_updates_existing_profile(self):
          from wallets.models import UserProfile
          profile, _ = UserProfile.objects.get_or_create(user=self.user)
          profile.preferred_currency = "usd"
          profile.save()
          response = self.client.patch("/api/profile/", {"preferred_currency": "pln"}, format="json")
          self.assertEqual(response.status_code, 200)
          self.assertEqual(response.data["preferred_currency"], "pln")

      def test_patch_returns_400_for_invalid_currency(self):
          response = self.client.patch("/api/profile/", {"preferred_currency": "xyz"}, format="json")
          self.assertEqual(response.status_code, 400)

      def test_requires_authentication(self):
          from rest_framework.test import APIClient
          response = APIClient().get("/api/profile/")
          self.assertEqual(response.status_code, 401)
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  python manage.py test wallets.tests.UserProfileEndpointTest -v 2
  ```

  Expected: ERROR — 404s (URL not registered).

- [ ] **Step 3: Add UserProfileSerializer to serializers.py**

  In `backend/wallets/serializers.py`, append:

  ```python
  class UserProfileSerializer(serializers.Serializer):
      preferred_currency = serializers.ChoiceField(
          choices=["usd", "eur", "gbp", "pln"],
          allow_null=True,
          required=False,
      )
  ```

- [ ] **Step 4: Add UserProfileView to views.py**

  In `backend/wallets/views.py`, add `UserProfile` and `UserProfileSerializer` to the existing imports:

  ```python
  from wallets.models import ..., UserProfile
  from wallets.serializers import ..., UserProfileSerializer
  ```

  Then add the view:

  ```python
  class UserProfileView(APIView):
      permission_classes = [IsAuthenticated]
      authentication_classes = [JWTAuthentication]

      def get(self, request):
          try:
              profile = UserProfile.objects.get(user=request.user)
              return Response({"preferred_currency": profile.preferred_currency})
          except UserProfile.DoesNotExist:
              return Response({"preferred_currency": None})

      def patch(self, request):
          serializer = UserProfileSerializer(data=request.data)
          serializer.is_valid(raise_exception=True)
          profile, _ = UserProfile.objects.get_or_create(user=request.user)
          profile.preferred_currency = serializer.validated_data.get("preferred_currency")
          profile.save()
          return Response({"preferred_currency": profile.preferred_currency})
  ```

- [ ] **Step 5: Register the URL in config/urls.py**

  Update the import in `backend/config/urls.py`:

  ```python
  from wallets.views import (
      TransactionCreate, TransactionDetail, UserDashboard,
      ExchangeRateView, UserProfileView,
  )
  ```

  Add to `urlpatterns`:

  ```python
  path('api/profile/', UserProfileView.as_view(), name='user-profile'),
  ```

- [ ] **Step 6: Run tests to verify they pass**

  ```bash
  python manage.py test wallets.tests.UserProfileEndpointTest -v 2
  ```

  Expected: OK (6 tests pass).

- [ ] **Step 7: Commit**

  ```bash
  git add backend/wallets/serializers.py backend/wallets/views.py backend/config/urls.py backend/wallets/tests.py
  git commit -m "feat: add GET/PATCH /api/profile/ endpoint for preferred currency"
  ```

---

## Task 7: Dashboard `base_currency` support

**Files:**
- Modify: `backend/wallets/services.py`
- Modify: `backend/wallets/views.py`
- Modify: `backend/wallets/tests.py`

- [ ] **Step 1: Write the failing tests**

  Append to `backend/wallets/tests.py`:

  ```python
  class DashboardBaseCurrencyTest(TestCase):
      def setUp(self):
          self.user = User.objects.create_user(username="tester_dash", password="pass")
          self.client = make_client(self.user)
          self.wallet = Wallet.objects.create(
              user=self.user, name="PLN Wallet",
              currency="pln", initial_value=Decimal("100"),
          )

      @patch("wallets.services.get_rate")
      def test_dashboard_converts_balance_with_base_currency(self, mock_get_rate):
          mock_get_rate.return_value = Decimal("0.25")
          response = self.client.get("/api/dashboard/?base_currency=usd")
          self.assertEqual(response.status_code, 200)
          # 100 PLN * 0.25 = 25 USD
          self.assertEqual(
              Decimal(str(response.data["summary"]["total_balance"])),
              Decimal("25.00"),
          )

      def test_dashboard_without_base_currency_sums_raw(self):
          response = self.client.get("/api/dashboard/")
          self.assertEqual(response.status_code, 200)
          self.assertEqual(
              Decimal(str(response.data["summary"]["total_balance"])),
              Decimal("100.00"),
          )

      @patch("wallets.services.get_rate")
      def test_dashboard_ignores_invalid_base_currency(self, mock_get_rate):
          response = self.client.get("/api/dashboard/?base_currency=xyz")
          self.assertEqual(response.status_code, 200)
          # Invalid currency falls through to raw sum
          mock_get_rate.assert_not_called()
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  python manage.py test wallets.tests.DashboardBaseCurrencyTest -v 2
  ```

  Expected: FAIL — `test_dashboard_converts_balance_with_base_currency` fails (balance not converted yet).

- [ ] **Step 3: Update DashboardService.user_summary() in services.py**

  Find `def user_summary(self):` in `backend/wallets/services.py` and replace its signature and the `total_balance` accumulation loop with:

  ```python
  def user_summary(self, base_currency=None):
      wallets_qs = self._wallets_with_monthly_aggregates()

      wallet_data = []
      total_balance = Decimal("0")
      total_income = Decimal("0")
      total_expenses = Decimal("0")

      for wallet in wallets_qs:
          balance = wallet.initial_value + wallet.total_transactions
          income = wallet.income_this_month
          expenses = abs(wallet.expenses_this_month)

          if base_currency:
              rate = get_rate(wallet.currency, base_currency, datetime.date.today())
              total_balance += balance * rate
          else:
              total_balance += balance

          total_income += income
          total_expenses += expenses
          wallet_data.append({
              "id": wallet.id,
              "name": wallet.name,
              "currency": wallet.currency,
              "balance": balance,
              "income_this_month": income,
              "expenses_this_month": expenses,
          })
  ```

  Leave the rest of `user_summary()` (category spending, monthly trend, return dict) unchanged.

- [ ] **Step 4: Update UserDashboard.get() in views.py**

  Find `class UserDashboard(APIView)` in `backend/wallets/views.py`. Replace its `get` method:

  ```python
  def get(self, request):
      base_currency = request.query_params.get("base_currency", "").lower() or None
      if base_currency and base_currency not in {"usd", "eur", "gbp", "pln"}:
          base_currency = None
      data = DashboardService(request.user).user_summary(base_currency=base_currency)
      return Response(UserDashboardSerializer(data).data)
  ```

- [ ] **Step 5: Run tests to verify they pass**

  ```bash
  python manage.py test wallets.tests.DashboardBaseCurrencyTest -v 2
  ```

  Expected: OK (3 tests pass).

- [ ] **Step 6: Run the full test suite to check for regressions**

  ```bash
  python manage.py test wallets -v 1
  ```

  Expected: All tests pass.

- [ ] **Step 7: Commit**

  ```bash
  git add backend/wallets/services.py backend/wallets/views.py backend/wallets/tests.py
  git commit -m "feat: dashboard accepts ?base_currency param to convert total balance"
  ```

---

## Task 8: Frontend API modules

**Files:**
- Create: `frontend/api/profile.ts`
- Create: `frontend/api/exchangeRates.ts`

- [ ] **Step 1: Create profile.ts**

  Create `frontend/api/profile.ts`:

  ```typescript
  import { axiosInstance } from "./axiosInstance";
  import { Currency } from "@/models/wallets";

  export interface UserProfile {
    preferred_currency: Currency | null;
  }

  export async function getProfile(): Promise<UserProfile> {
    const response = await axiosInstance.get<UserProfile>("profile/");
    return response.data;
  }

  export async function patchProfile(preferred_currency: Currency): Promise<UserProfile> {
    const response = await axiosInstance.patch<UserProfile>("profile/", { preferred_currency });
    return response.data;
  }
  ```

- [ ] **Step 2: Create exchangeRates.ts**

  Create `frontend/api/exchangeRates.ts`:

  ```typescript
  import { axiosInstance } from "./axiosInstance";
  import { Currency } from "@/models/wallets";

  export interface ExchangeRateResponse {
    rate: string;
    date: string;
  }

  export async function getExchangeRate(
    base: Currency,
    quote: Currency,
    date?: string,
  ): Promise<ExchangeRateResponse> {
    const params: Record<string, string> = { base, quote };
    if (date) params.date = date;
    const response = await axiosInstance.get<ExchangeRateResponse>("exchange-rates/", { params });
    return response.data;
  }
  ```

- [ ] **Step 3: Verify TypeScript compiles**

  ```bash
  cd frontend && npx tsc --noEmit
  ```

  Expected: no errors.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/api/profile.ts frontend/api/exchangeRates.ts
  git commit -m "feat: add frontend API modules for profile and exchange rates"
  ```

---

## Task 9: Frontend Dashboard currency switcher

**Files:**
- Modify: `frontend/lib/currency.ts`
- Modify: `frontend/components/MetricsSummaryCards.tsx`
- Modify: `frontend/app/dashboard/page.tsx`

- [ ] **Step 1: Add getLocaleCurrency() to currency.ts**

  In `frontend/lib/currency.ts`, append after the existing `formatCurrency` function:

  ```typescript
  export function getLocaleCurrency(): Currency {
    const lang = navigator.language.toLowerCase();
    if (lang.startsWith("pl")) return "pln";
    if (lang === "en-gb") return "gbp";
    if (
      lang.startsWith("de") ||
      lang.startsWith("fr") ||
      lang.startsWith("es") ||
      lang.startsWith("it") ||
      lang.startsWith("pt")
    )
      return "eur";
    return "usd";
  }
  ```

- [ ] **Step 2: Update MetricsSummaryCards.tsx**

  Replace the entire contents of `frontend/components/MetricsSummaryCards.tsx` with:

  ```typescript
  "use client";

  import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
  import { Wallet as WalletIcon, TrendingUp, TrendingDown, Scale } from "lucide-react";
  import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
  } from "@/components/ui/select";
  import { DashboardSummary, Currency } from "@/models/wallets";
  import { formatCurrency } from "@/lib/currency";

  interface MetricsSummaryCardsProps {
    summary: DashboardSummary;
    walletCount: number;
    baseCurrency: Currency;
    onCurrencyChange: (currency: Currency) => void;
  }

  export function MetricsSummaryCards({
    summary,
    walletCount,
    baseCurrency,
    onCurrencyChange,
  }: MetricsSummaryCardsProps) {
    const totalBalance = Number(summary.total_balance);
    const income = Number(summary.total_income_this_month);
    const expenses = Number(summary.total_expenses_this_month);
    const net = Number(summary.net_this_month);

    return (
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Balance</CardTitle>
            <Select
              value={baseCurrency}
              onValueChange={(v) => onCurrencyChange(v as Currency)}
            >
              <SelectTrigger className="h-7 w-20 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="usd">USD</SelectItem>
                <SelectItem value="eur">EUR</SelectItem>
                <SelectItem value="gbp">GBP</SelectItem>
                <SelectItem value="pln">PLN</SelectItem>
              </SelectContent>
            </Select>
          </CardHeader>
          <CardContent>
            <div
              className={`text-2xl font-bold ${
                totalBalance >= 0 ? "text-green-600" : "text-red-600"
              }`}
            >
              {formatCurrency(totalBalance, baseCurrency)}
            </div>
            <p className="text-xs text-muted-foreground">
              Across {walletCount} wallet{walletCount !== 1 ? "s" : ""}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Income (this month)</CardTitle>
            <TrendingUp className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{formatCurrency(income)}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Expenses (this month)</CardTitle>
            <TrendingDown className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{formatCurrency(expenses)}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Net (this month)</CardTitle>
            <Scale className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div
              className={`text-2xl font-bold ${net >= 0 ? "text-green-600" : "text-red-600"}`}
            >
              {net >= 0 ? "+" : ""}
              {formatCurrency(net)}
            </div>
            <p className="text-xs text-muted-foreground">Income − Expenses</p>
          </CardContent>
        </Card>
      </div>
    );
  }
  ```

  Note: `Currency` must be exported from `frontend/models/wallets.ts`. Verify with:
  ```bash
  grep "export type Currency" frontend/models/wallets.ts
  ```
  It should already be there. If it only has `export type Currency = ...` without `export`, add `export`.

- [ ] **Step 3: Update dashboard/page.tsx**

  In `frontend/app/dashboard/page.tsx`, make the following changes:

  **Add imports** at the top:
  ```typescript
  import { getProfile, patchProfile } from "@/api/profile";
  import { getLocaleCurrency } from "@/lib/currency";
  import { Currency } from "@/models/wallets";
  ```

  **Add state** inside `DashboardPage`:
  ```typescript
  const [baseCurrency, setBaseCurrency] = useState<Currency>("usd");
  ```

  **Replace `fetchDashboard`** with a version that accepts the currency:
  ```typescript
  async function fetchDashboard(currency: Currency) {
    try {
      const response = await axiosInstance.get<UserDashboardResponse>("dashboard/", {
        params: { base_currency: currency },
      });
      setDashboard(response.data);
    } catch (error) {
      console.error("Failed to fetch dashboard:", error);
    }
  }
  ```

  **Replace `loadAll`** with a version that resolves base currency first:
  ```typescript
  async function loadAll() {
    setIsLoading(true);
    try {
      const [walletsRes, profile] = await Promise.all([
        axiosInstance.get<Wallet[]>("wallets/"),
        getProfile().catch(() => ({ preferred_currency: null })),
      ]);
      setWallets(walletsRes.data);
      const currency = profile.preferred_currency ?? getLocaleCurrency();
      setBaseCurrency(currency);
      await fetchDashboard(currency);
    } catch (error) {
      console.error("Failed to load dashboard:", error);
    } finally {
      setIsLoading(false);
    }
  }
  ```

  **Add a currency change handler** after `loadAll`:
  ```typescript
  async function handleCurrencyChange(currency: Currency) {
    setBaseCurrency(currency);
    await Promise.all([
      patchProfile(currency).catch(() => {}),
      fetchDashboard(currency),
    ]);
  }
  ```

  **Update the `<MetricsSummaryCards>` usage** in JSX to pass the new props:
  ```tsx
  <MetricsSummaryCards
    summary={dashboard.summary}
    walletCount={wallets.length}
    baseCurrency={baseCurrency}
    onCurrencyChange={handleCurrencyChange}
  />
  ```

- [ ] **Step 4: Verify TypeScript compiles**

  ```bash
  cd frontend && npx tsc --noEmit
  ```

  Expected: no errors.

- [ ] **Step 5: Commit**

  ```bash
  git add frontend/lib/currency.ts frontend/components/MetricsSummaryCards.tsx frontend/app/dashboard/page.tsx
  git commit -m "feat: dashboard currency switcher with profile persistence and locale fallback"
  ```

---

## Task 10: TransactionDialog cross-currency entry

**Files:**
- Modify: `frontend/components/TransactionDialog.tsx`

- [ ] **Step 1: Add state and debounced rate fetch**

  In `frontend/components/TransactionDialog.tsx`, add `useRef` to the React import:

  ```typescript
  import { useState, useEffect, FormEvent, useMemo, useRef } from "react";
  ```

  Add `getExchangeRate` import:

  ```typescript
  import { getExchangeRate } from "@/api/exchangeRates";
  ```

  Inside the `TransactionDialog` function, after the existing state declarations, add:

  ```typescript
  const conversionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [conversionOpen, setConversionOpen] = useState(false);
  const [conversionCurrency, setConversionCurrency] = useState<Currency | null>(null);
  const [conversionInput, setConversionInput] = useState<string>("");
  const [conversionPreview, setConversionPreview] = useState<string | null>(null);
  const [conversionError, setConversionError] = useState<string | null>(null);
  const [isFetchingRate, setIsFetchingRate] = useState(false);
  ```

  Add a `useEffect` for debounced rate fetching (after the existing `useEffect` blocks):

  ```typescript
  useEffect(() => {
    if (!conversionOpen || !conversionCurrency || !conversionInput || !formData.date) {
      setConversionPreview(null);
      return;
    }
    const amount = parseFloat(conversionInput);
    if (isNaN(amount) || amount <= 0) {
      setConversionPreview(null);
      return;
    }

    if (conversionTimerRef.current) clearTimeout(conversionTimerRef.current);
    conversionTimerRef.current = setTimeout(async () => {
      setIsFetchingRate(true);
      setConversionError(null);
      try {
        const data = await getExchangeRate(conversionCurrency, currency, formData.date);
        const rate = parseFloat(data.rate);
        const converted = parseFloat((amount * rate).toFixed(2));
        setConversionPreview(`≈ ${converted.toFixed(2)} ${currency.toUpperCase()}`);
        setFormData((prev) => ({ ...prev, amount: converted }));
      } catch {
        setConversionError("Failed to fetch exchange rate. Check your connection and try again.");
        setConversionPreview(null);
      } finally {
        setIsFetchingRate(false);
      }
    }, 300);

    return () => {
      if (conversionTimerRef.current) clearTimeout(conversionTimerRef.current);
    };
  }, [conversionCurrency, conversionInput, formData.date, conversionOpen, currency]);
  ```

  In the existing `useEffect` that resets the form when `open` changes (the one with `[transaction, currency, open]` dependencies), add reset lines for the conversion state at the end of the reset block:

  ```typescript
  setConversionOpen(false);
  setConversionCurrency(null);
  setConversionInput("");
  setConversionPreview(null);
  setConversionError(null);
  ```

- [ ] **Step 2: Add the conversion section to the form JSX**

  In the JSX form, find the amount `<div className="space-y-2">` block (the one with `id="amount"`). After its closing `</div>`, add:

  ```tsx
  <div className="space-y-2">
    <div className="flex items-center gap-2">
      <Switch
        id="conversion-toggle"
        checked={conversionOpen}
        onCheckedChange={(checked) => {
          setConversionOpen(checked);
          if (!checked) {
            setConversionCurrency(null);
            setConversionInput("");
            setConversionPreview(null);
            setConversionError(null);
          }
        }}
        disabled={isLoading}
      />
      <Label htmlFor="conversion-toggle" className="text-sm cursor-pointer">
        Enter in a different currency
      </Label>
    </div>

    {conversionOpen && (
      <div className="space-y-2 pl-2 border-l-2 border-muted">
        <div className="flex gap-2">
          <Select
            value={conversionCurrency ?? ""}
            onValueChange={(v) => setConversionCurrency(v as Currency)}
          >
            <SelectTrigger className="w-28">
              <SelectValue placeholder="Currency" />
            </SelectTrigger>
            <SelectContent>
              {(["usd", "eur", "gbp", "pln"] as Currency[])
                .filter((c) => c !== currency)
                .map((c) => (
                  <SelectItem key={c} value={c}>
                    {c.toUpperCase()}
                  </SelectItem>
                ))}
            </SelectContent>
          </Select>
          <Input
            type="number"
            step="0.01"
            min="0"
            placeholder="0.00"
            value={conversionInput}
            onChange={(e) => setConversionInput(e.target.value)}
            disabled={isLoading || !conversionCurrency}
            className="flex-1"
          />
        </div>
        {isFetchingRate && (
          <p className="text-xs text-muted-foreground">Fetching rate…</p>
        )}
        {conversionPreview && !isFetchingRate && (
          <p className="text-xs text-muted-foreground">{conversionPreview}</p>
        )}
        {conversionError && (
          <p className="text-xs text-red-600">{conversionError}</p>
        )}
      </div>
    )}
  </div>
  ```

  Also update the `handleSubmit` function to block submission when conversion is open but has an error or is still fetching:

  Find the beginning of `handleSubmit` (after `if (!validateForm()) return;`) and add:

  ```typescript
  if (conversionOpen && (isFetchingRate || conversionError)) {
    setError(
      conversionError ?? "Exchange rate is still loading. Please wait."
    );
    return;
  }
  ```

- [ ] **Step 3: Verify TypeScript compiles**

  ```bash
  cd frontend && npx tsc --noEmit
  ```

  Expected: no errors.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/components/TransactionDialog.tsx
  git commit -m "feat: TransactionDialog cross-currency entry with live conversion preview"
  ```

---

## Done

At this point:
- Backend: `ExchangeRate` + `UserProfile` models, `get_rate()` service, three new API endpoints, dashboard base_currency conversion — all tested.
- Frontend: profile API, exchange rate API, locale currency detection, dashboard currency switcher, TransactionDialog conversion section.

Manual smoke test:
1. Open dashboard → Total Balance shows with currency symbol and a currency switcher
2. Change currency → total updates, preference persists on reload
3. Open TransactionDialog → toggle "Enter in a different currency" → pick a currency + amount → see conversion preview → save → transaction amount is in wallet currency
