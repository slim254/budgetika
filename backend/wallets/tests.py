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
