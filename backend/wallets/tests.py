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


from datetime import date as date_type
from wallets.models import BudgetRule, BudgetMonthOverride


class BudgetRuleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="budget_user", password="pass")
        self.client = make_client(self.user)
        self.wallet = Wallet.objects.create(
            user=self.user, name="Budget Wallet", currency="usd", initial_value=Decimal("0")
        )
        self.category = TransactionCategory.objects.create(
            user=self.user, name="Food", icon="utensils", color="#F97316"
        )
        self.url = f"/api/wallets/{self.wallet.id}/budgets/"

    def test_create_rule(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "300.00",
            "start_date": "2024-01-15",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(BudgetRule.objects.count(), 1)
        rule = BudgetRule.objects.first()
        self.assertEqual(rule.start_date, date_type(2024, 1, 1))  # coerced to first of month

    def test_create_rule_with_end_date(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "200.00",
            "start_date": "2024-01-01",
            "end_date": "2024-06-15",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        rule = BudgetRule.objects.first()
        self.assertEqual(rule.end_date, date_type(2024, 6, 1))  # coerced to first of month

    def test_amount_must_be_positive(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "-50.00",
            "start_date": "2024-01-01",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_amount_zero_rejected(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "0.00",
            "start_date": "2024-01-01",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_end_date_before_start_date_rejected(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "300.00",
            "start_date": "2024-03-01",
            "end_date": "2024-01-01",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_overlapping_open_ended_rule_rejected(self):
        BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"), start_date=date_type(2024, 1, 1)
        )
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "200.00",
            "start_date": "2024-06-01",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_non_overlapping_rule_after_end_date_allowed(self):
        BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"),
            start_date=date_type(2024, 1, 1),
            end_date=date_type(2024, 3, 1),
        )
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "amount": "200.00",
            "start_date": "2024-04-01",
        }, format="json")
        self.assertEqual(response.status_code, 201)

    def test_list_rules(self):
        BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"), start_date=date_type(2024, 1, 1)
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_delete_rule(self):
        rule = BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"), start_date=date_type(2024, 1, 1)
        )
        response = self.client.delete(f"{self.url}{rule.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(BudgetRule.objects.count(), 0)

    def test_requires_auth(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_cross_wallet_isolation(self):
        other_user = User.objects.create_user(username="other_budget", password="pass")
        other_client = make_client(other_user)
        response = other_client.get(self.url)
        self.assertEqual(response.status_code, 404)


class BudgetOverrideTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="override_user", password="pass")
        self.client = make_client(self.user)
        self.wallet = Wallet.objects.create(
            user=self.user, name="Override Wallet", currency="usd", initial_value=Decimal("0")
        )
        self.category = TransactionCategory.objects.create(
            user=self.user, name="Groceries", icon="shopping-cart", color="#10B981"
        )
        self.rule = BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"), start_date=date_type(2024, 1, 1)
        )
        self.url = f"/api/wallets/{self.wallet.id}/budgets/overrides/"

    def test_create_override(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "year": 2024,
            "month": 3,
            "amount": "500.00",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(BudgetMonthOverride.objects.count(), 1)

    def test_upsert_updates_existing(self):
        BudgetMonthOverride.objects.create(
            wallet=self.wallet, category=self.category,
            year=2024, month=3, amount=Decimal("500.00")
        )
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "year": 2024,
            "month": 3,
            "amount": "600.00",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BudgetMonthOverride.objects.count(), 1)
        self.assertEqual(BudgetMonthOverride.objects.first().amount, Decimal("600.00"))

    def test_override_without_rule_rejected(self):
        other_category = TransactionCategory.objects.create(
            user=self.user, name="Travel", icon="plane", color="#6366F1"
        )
        response = self.client.post(self.url, {
            "category_id": str(other_category.id),
            "year": 2024,
            "month": 3,
            "amount": "500.00",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_delete_override(self):
        override = BudgetMonthOverride.objects.create(
            wallet=self.wallet, category=self.category,
            year=2024, month=3, amount=Decimal("500.00")
        )
        response = self.client.delete(f"{self.url}{override.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(BudgetMonthOverride.objects.count(), 0)

    def test_amount_must_be_positive(self):
        response = self.client.post(self.url, {
            "category_id": str(self.category.id),
            "year": 2024,
            "month": 3,
            "amount": "-100.00",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_requires_auth(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_cross_wallet_isolation(self):
        other_user = User.objects.create_user(username="other_override", password="pass")
        other_client = make_client(other_user)
        response = other_client.get(self.url)
        self.assertEqual(response.status_code, 404)


class BudgetSummaryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="summary_user", password="pass")
        self.client = make_client(self.user)
        self.wallet = Wallet.objects.create(
            user=self.user, name="Summary Wallet", currency="usd", initial_value=Decimal("0")
        )
        self.category = TransactionCategory.objects.create(
            user=self.user, name="Food", icon="utensils", color="#F97316"
        )
        self.rule = BudgetRule.objects.create(
            wallet=self.wallet, category=self.category,
            amount=Decimal("300.00"), start_date=date_type(2024, 1, 1)
        )
        self.url = f"/api/wallets/{self.wallet.id}/budgets/summary/"

    def _get(self, month=3, year=2024):
        return self.client.get(f"{self.url}?month={month}&year={year}")

    def test_active_rule_appears_in_summary(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["category"]["id"], str(self.category.id))

    def test_rule_ended_before_month_excluded(self):
        self.rule.end_date = date_type(2024, 2, 1)
        self.rule.save()
        response = self._get(month=3, year=2024)
        self.assertEqual(len(response.data), 0)

    def test_rule_starting_after_month_excluded(self):
        self.rule.start_date = date_type(2024, 4, 1)
        self.rule.save()
        response = self._get(month=3, year=2024)
        self.assertEqual(len(response.data), 0)

    def test_override_takes_precedence_over_rule(self):
        BudgetMonthOverride.objects.create(
            wallet=self.wallet, category=self.category,
            year=2024, month=3, amount=Decimal("500.00")
        )
        response = self._get()
        self.assertEqual(response.data[0]["limit"], "500.00")
        self.assertTrue(response.data[0]["is_override"])
        self.assertIsNotNone(response.data[0]["override_id"])

    def test_rule_without_override_not_flagged(self):
        response = self._get()
        self.assertFalse(response.data[0]["is_override"])
        self.assertIsNone(response.data[0]["override_id"])

    def test_spending_computed_from_negative_transactions(self):
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="Groceries", amount=Decimal("-80.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 3, 10)),
            category=self.category,
        )
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="More groceries", amount=Decimal("-40.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 3, 20)),
            category=self.category,
        )
        response = self._get()
        self.assertEqual(response.data[0]["spent"], "120.00")
        self.assertEqual(response.data[0]["remaining"], "180.00")
        self.assertFalse(response.data[0]["is_over_budget"])

    def test_income_excluded_from_spending(self):
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="Refund", amount=Decimal("50.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 3, 5)),
            category=self.category,
        )
        response = self._get()
        self.assertEqual(response.data[0]["spent"], "0.00")

    def test_zero_spending_when_no_transactions(self):
        response = self._get()
        self.assertEqual(response.data[0]["spent"], "0.00")
        self.assertEqual(response.data[0]["remaining"], "300.00")

    def test_over_budget_flag(self):
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="Overspend", amount=Decimal("-350.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 3, 1)),
            category=self.category,
        )
        response = self._get()
        self.assertTrue(response.data[0]["is_over_budget"])
        self.assertEqual(response.data[0]["remaining"], "-50.00")

    def test_archived_category_rule_still_returned(self):
        self.category.is_archived = True
        self.category.save()
        response = self._get()
        self.assertEqual(len(response.data), 1)

    def test_transactions_outside_month_excluded_from_spending(self):
        Transaction.objects.create(
            wallet=self.wallet, created_by=self.user,
            note="Wrong month", amount=Decimal("-100.00"), currency="usd",
            date=timezone.make_aware(datetime(2024, 2, 28)),
            category=self.category,
        )
        response = self._get(month=3, year=2024)
        self.assertEqual(response.data[0]["spent"], "0.00")

    def test_requires_auth(self):
        self.client.credentials()
        response = self._get()
        self.assertEqual(response.status_code, 401)

    def test_cross_wallet_isolation(self):
        other_user = User.objects.create_user(username="other_summary", password="pass")
        other_client = make_client(other_user)
        response = other_client.get(f"/api/wallets/{self.wallet.id}/budgets/summary/?month=3&year=2024")
        self.assertEqual(response.status_code, 404)
