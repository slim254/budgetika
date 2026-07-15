import io
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from wallets.models import ImportCategoryRule, Transaction, TransactionCategory, Wallet
from wallets.services import GenericCSVImportService, suggest_keyword

# Two BIEDRONKA rows with DIFFERENT signatures (store #, city, ref) — only a
# keyword rule can group them; exact-signature dedup cannot.
CSV = (
    "Date,Amount,Merchant\n"
    "2024-01-01,-45.20,BIEDRONKA 1234 WARSZAWA ref558\n"
    "2024-02-03,-12.00,BIEDRONKA 9987 KRAKOW ref210\n"
    "2024-01-05,-8.00,ORLEN STACJA 55\n"
)


class TestSuggestKeyword(TestCase):
    def test_leading_alpha_tokens(self):
        self.assertEqual(suggest_keyword("BIEDRONKA 1234 WARSZAWA ref558"), "BIEDRONKA")
        self.assertEqual(suggest_keyword("UBER *TRIP"), "UBER")

    def test_fallback_longest_alpha(self):
        # No leading alpha token -> longest alpha token
        self.assertEqual(suggest_keyword("1234 BIEDRONKA 55"), "BIEDRONKA")


class TestRuleEngine(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="r", password="p")
        self.wallet = Wallet.objects.create(
            user=self.user, name="W", currency="pln", initial_value=0
        )
        self.groc, _ = TransactionCategory.objects.get_or_create(user=self.user, name="Groceries")

    def _service(self, csv=CSV):
        return GenericCSVImportService(self.user, self.wallet, io.BytesIO(csv.encode()))

    def test_execute_creates_and_applies_rule_across_similar(self):
        svc = self._service()
        res = svc.execute(
            {"amount": "Amount", "date": "Date"},
            {"mode": "signed"},
            ai_categories={},
            rules=[{"keyword": "BIEDRONKA", "category_id": str(self.groc.id)}],
        )
        self.assertTrue(res["success"])
        # Rule persisted (lowercased)
        self.assertTrue(
            ImportCategoryRule.objects.filter(user=self.user, keyword="biedronka").exists()
        )
        # Both differing BIEDRONKA rows got Groceries
        self.assertEqual(Transaction.objects.filter(category=self.groc).count(), 2)

    def test_saved_rule_applies_on_next_import_without_being_passed(self):
        ImportCategoryRule.objects.create(
            user=self.user, keyword="biedronka", category=self.groc
        )
        svc = self._service()
        svc.execute({"amount": "Amount", "date": "Date"}, {"mode": "signed"}, ai_categories={})
        self.assertEqual(Transaction.objects.filter(category=self.groc).count(), 2)

    def test_longest_keyword_wins(self):
        dining, _ = TransactionCategory.objects.get_or_create(user=self.user, name="Dining Out")
        ImportCategoryRule.objects.create(user=self.user, keyword="orlen", category=self.groc)
        ImportCategoryRule.objects.create(user=self.user, keyword="orlen stacja", category=dining)
        svc = self._service()
        svc.execute({"amount": "Amount", "date": "Date"}, {"mode": "signed"}, ai_categories={})
        # ORLEN STACJA 55 matches both; the longer, more specific keyword wins
        orlen_txn = Transaction.objects.get(amount=Decimal("-8.00"))
        self.assertEqual(orlen_txn.category, dining)

    def test_upsert_updates_existing_rule_category(self):
        dining, _ = TransactionCategory.objects.get_or_create(user=self.user, name="Dining Out")
        ImportCategoryRule.objects.create(user=self.user, keyword="biedronka", category=dining)
        svc = self._service()
        svc.execute(
            {"amount": "Amount", "date": "Date"},
            {"mode": "signed"},
            ai_categories={},
            rules=[{"keyword": "BIEDRONKA", "category_id": str(self.groc.id)}],
        )
        rule = ImportCategoryRule.objects.get(user=self.user, keyword="biedronka")
        self.assertEqual(rule.category, self.groc)  # updated, not duplicated
        self.assertEqual(
            ImportCategoryRule.objects.filter(user=self.user, keyword="biedronka").count(), 1
        )

    def test_exact_override_beats_rule(self):
        dining, _ = TransactionCategory.objects.get_or_create(user=self.user, name="Dining Out")
        ImportCategoryRule.objects.create(user=self.user, keyword="biedronka", category=self.groc)
        svc = self._service()
        uniques = svc.collect_signatures({"amount": "Amount", "date": "Date"}, {"mode": "signed"})
        warsaw_key = next(u["key"] for u in uniques if "WARSZAWA" in u["signature"])
        svc2 = self._service()
        svc2.execute(
            {"amount": "Amount", "date": "Date"},
            {"mode": "signed"},
            ai_categories={warsaw_key: str(dining.id)},  # one-off exact override
        )
        warsaw = Transaction.objects.get(amount=Decimal("-45.20"))
        krakow = Transaction.objects.get(amount=Decimal("-12.00"))
        self.assertEqual(warsaw.category, dining)   # exact override wins for this row
        self.assertEqual(krakow.category, self.groc)  # rule still applies to the other
