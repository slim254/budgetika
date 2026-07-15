import io

from django.contrib.auth.models import User
from django.test import TestCase

from wallets.models import Transaction, TransactionCategory, Wallet
from wallets.services import GenericCSVImportService

CSV = (
    "Date,Amount,Merchant,Title\n"
    "2024-01-01,-45.20,BIEDRONKA 1234,card payment\n"
    "2024-02-03,-12.00,BIEDRONKA 1234,card payment\n"   # same merchant, diff date+amount
    "2024-01-05,5000.00,ACME CORP,salary\n"
)


class TestSignatures(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="s", password="p")
        self.wallet = Wallet.objects.create(
            user=self.user, name="W", currency="pln", initial_value=0
        )

    def _service(self, csv=CSV):
        return GenericCSVImportService(self.user, self.wallet, io.BytesIO(csv.encode()))

    def test_dedup_excludes_date_and_amount(self):
        svc = self._service()
        mapping = {"amount": "Amount", "date": "Date"}  # no category column
        uniques = svc.collect_signatures(mapping, {"mode": "signed"})
        # The two BIEDRONKA rows collapse into one unique despite different date/amount
        biedronka = [u for u in uniques if "BIEDRONKA" in u["signature"]]
        self.assertEqual(len(biedronka), 1)
        self.assertEqual(biedronka[0]["count"], 2)

    def test_signature_includes_unmapped_columns(self):
        svc = self._service()
        uniques = svc.collect_signatures({"amount": "Amount", "date": "Date"}, {"mode": "signed"})
        sig = next(u["signature"] for u in uniques if "ACME" in u["signature"])
        self.assertIn("salary", sig)      # unmapped "Title" column is present
        self.assertNotIn("5000", sig)     # amount excluded
        self.assertNotIn("2024", sig)     # date excluded

    def test_rows_with_matching_mapped_category_are_skipped(self):
        TransactionCategory.objects.get_or_create(user=self.user, name="Groceries")
        csv = (
            "Date,Amount,Merchant,Cat\n"
            "2024-01-01,-5,BIEDRONKA,Groceries\n"   # matches existing -> skip
            "2024-01-02,-9,LIDL,\n"                 # blank -> needs AI
        )
        svc = self._service(csv)
        mapping = {"amount": "Amount", "date": "Date", "category": "Cat"}
        uniques = svc.collect_signatures(mapping, {"mode": "signed"})
        sigs = [u["signature"] for u in uniques]
        self.assertTrue(any("LIDL" in s for s in sigs))
        self.assertFalse(any("BIEDRONKA" in s for s in sigs))

    def test_execute_applies_ai_categories(self):
        groc = TransactionCategory.objects.get_or_create(user=self.user, name="Groceries")[0]
        svc = self._service()
        mapping = {"amount": "Amount", "date": "Date"}
        uniques = svc.collect_signatures(mapping, {"mode": "signed"})
        key = next(u["key"] for u in uniques if "BIEDRONKA" in u["signature"])
        svc2 = self._service()
        res = svc2.execute(mapping, {"mode": "signed"}, ai_categories={key: str(groc.id)})
        self.assertTrue(res["success"])
        self.assertEqual(Transaction.objects.filter(category=groc).count(), 2)

    def test_ai_mode_does_not_autocreate_from_mapped_column(self):
        csv = "Date,Amount,Cat\n2024-01-01,-5,Made Up Cat\n"
        svc = self._service(csv)
        svc.execute(
            {"amount": "Amount", "date": "Date", "category": "Cat"},
            {"mode": "signed"},
            ai_categories={},
        )
        # 'Made Up Cat' does not match an existing category -> NOT created in AI mode
        self.assertFalse(TransactionCategory.objects.filter(name="Made Up Cat").exists())

    def test_legacy_mode_still_autocreates(self):
        csv = "Date,Amount,Cat\n2024-01-01,-5,Made Up Cat\n"
        svc = self._service(csv)
        svc.execute(
            {"amount": "Amount", "date": "Date", "category": "Cat"},
            {"mode": "signed"},
        )  # no ai_categories -> legacy behavior
        self.assertTrue(TransactionCategory.objects.filter(name="Made Up Cat").exists())

    def test_ai_mode_keeps_matching_mapped_category(self):
        groc = TransactionCategory.objects.get_or_create(user=self.user, name="Groceries")[0]
        csv = "Date,Amount,Merchant,Cat\n2024-01-01,-5,BIEDRONKA,Groceries\n"
        svc = self._service(csv)
        svc.execute(
            {"amount": "Amount", "date": "Date", "category": "Cat"},
            {"mode": "signed"},
            ai_categories={},
        )
        self.assertEqual(Transaction.objects.filter(category=groc).count(), 1)
