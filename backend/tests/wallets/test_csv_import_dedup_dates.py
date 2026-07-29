"""Import regressions for duplicate detection, date-format handling and
case-insensitive category matching.

Duplicates are measured against a snapshot taken BEFORE the import loop, so a
statement containing the same purchase several times imports every occurrence
while a re-run of the same file still imports nothing.
"""

import io

from django.contrib.auth.models import User
from django.test import TestCase

from wallets.models import Transaction, TransactionCategory, Wallet
from wallets.services import GenericCSVImportService


class CSVImportDedupAndDateFormatTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tmp", password="p")
        self.wallet = Wallet.objects.create(
            user=self.user, name="W", currency="pln", initial_value=0
        )

    def _svc(self, csv):
        return GenericCSVImportService(self.user, self.wallet, io.BytesIO(csv.encode()))

    def test_identical_rows_within_one_csv_all_import(self):
        csv = (
            "Date,Amount,Note\n"
            "2024-01-01,-5.00,COFFEE\n"
            "2024-01-01,-5.00,COFFEE\n"
            "2024-01-01,-5.00,COFFEE\n"
        )
        res = self._svc(csv).execute(
            {"amount": "Amount", "date": "Date", "note": "Note"}, {"mode": "signed"}
        )
        self.assertEqual(res["stats"]["imported"], 3)
        self.assertEqual(res["stats"]["skipped_duplicates"], 0)

        # Re-running the same file skips all of them.
        res2 = self._svc(csv).execute(
            {"amount": "Amount", "date": "Date", "note": "Note"}, {"mode": "signed"}
        )
        self.assertEqual(res2["stats"]["imported"], 0)
        self.assertEqual(res2["stats"]["skipped_duplicates"], 3)
        self.assertEqual(Transaction.objects.count(), 3)

    def test_empty_note_rows_dedup_on_rerun(self):
        csv = "Date,Amount\n2024-01-01,-5.00\n"
        self._svc(csv).execute({"amount": "Amount", "date": "Date"}, {"mode": "signed"})
        res2 = self._svc(csv).execute({"amount": "Amount", "date": "Date"}, {"mode": "signed"})
        self.assertEqual(res2["stats"]["skipped_duplicates"], 1)

    def test_auto_defaults_to_dmy(self):
        csv = "Date,Amount\n01/02/2024,-5.00\n"
        self._svc(csv).execute({"amount": "Amount", "date": "Date"}, {"mode": "signed"})
        t = Transaction.objects.get()
        self.assertEqual((t.date.month, t.date.day), (2, 1))

    def test_auto_detects_mdy_from_day_over_12(self):
        csv = "Date,Amount\n01/02/2024,-5.00\n01/25/2024,-6.00\n"
        self._svc(csv).execute({"amount": "Amount", "date": "Date"}, {"mode": "signed"})
        first = Transaction.objects.get(amount=-5)
        self.assertEqual((first.date.month, first.date.day), (1, 2))

    def test_explicit_format_overrides_detection(self):
        csv = "Date,Amount\n01/02/2024,-5.00\n01/25/2024,-6.00\n"
        res = self._svc(csv).execute(
            {"amount": "Amount", "date": "Date"}, {"mode": "signed"}, date_format="DMY"
        )
        first = Transaction.objects.get(amount=-5)
        self.assertEqual((first.date.month, first.date.day), (2, 1))
        # Parsing is strict to the chosen order: 01/25/2024 is not a valid DMY
        # date, so it errors rather than being silently re-read as MDY.
        self.assertEqual(res["stats"]["imported"], 1)
        self.assertEqual(res["stats"]["errors"], 1)
        self.assertIn("Unrecognized date format", res["errors"][0]["error"])

    def test_two_digit_year_uses_chosen_order_not_year_first(self):
        # "15.01.24" is a valid date under YMD, DMY and MDY. Under DMY it must
        # be 15 January 2024 — never 2015-01-24.
        csv = "Date,Amount\n15.01.24,-5.00\n"
        self._svc(csv).execute(
            {"amount": "Amount", "date": "Date"}, {"mode": "signed"}, date_format="DMY"
        )
        t = Transaction.objects.get()
        self.assertEqual((t.date.year, t.date.month, t.date.day), (2024, 1, 15))

    def test_iso_dates_parse_under_any_chosen_order(self):
        csv = "Date,Amount\n2024-01-15,-5.00\n"
        self._svc(csv).execute(
            {"amount": "Amount", "date": "Date"}, {"mode": "signed"}, date_format="MDY"
        )
        t = Transaction.objects.get()
        self.assertEqual((t.date.year, t.date.month, t.date.day), (2024, 1, 15))

    def test_parse_reports_detection(self):
        csv = "Date,Amount,Note\n15/01/2024,-5.00,x\n"
        res = self._svc(csv).parse()
        self.assertEqual(res["date_format"], "DMY")
        self.assertFalse(res["date_format_ambiguous"])
        self.assertEqual(res["date_formats"]["Date"], {"format": "DMY", "ambiguous": False})

        res2 = self._svc("Date,Amount\n01/02/2024,-5.00\n").parse()
        self.assertTrue(res2["date_format_ambiguous"])

        res3 = self._svc("Date,Amount\n2024-01-15,-5.00\n").parse()
        self.assertEqual(res3["date_format"], "YMD")
        self.assertFalse(res3["date_format_ambiguous"])

    def test_category_matching_is_case_insensitive(self):
        TransactionCategory.objects.get_or_create(user=self.user, name="Groceries")
        csv = "Date,Amount,Cat\n2024-01-01,-5.00,groceries\n2024-01-02,-6.00,GROCERIES\n"
        res = self._svc(csv).execute(
            {"amount": "Amount", "date": "Date", "category": "Cat"}, {"mode": "signed"}
        )
        self.assertEqual(res["created_categories"], [])
        self.assertEqual(
            TransactionCategory.objects.filter(user=self.user, name__iexact="groceries").count(), 1
        )
        self.assertEqual(Transaction.objects.filter(category__name="Groceries").count(), 2)

    def test_various_date_shapes_still_parse(self):
        for value, expected in [
            ("2024-01-15", (1, 15)),
            ("2024-01-15 10:30:00", (1, 15)),
            ("15.01.2024", (1, 15)),
            ("15-01-2024", (1, 15)),
            ("15/01/2024", (1, 15)),
            ("2024-01-15T10:30:00Z", (1, 15)),
        ]:
            svc = self._svc("Date,Amount\nx,1\n")
            dt = svc._parse_date(value)
            self.assertEqual((dt.month, dt.day), expected, value)
