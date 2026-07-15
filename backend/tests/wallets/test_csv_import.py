"""Regression tests for GenericCSVImportService against real-world
Polish bank exports (Revolut UTF-8, PKO BP-style Windows-1250).

These fixtures reproduce the exact quirks of the statements a user tried
to import: cp1250 encoding, signed amounts with a leading '+', European
decimal commas, and pending "Blokada" rows with an empty operation date.
"""

import io

from django.contrib.auth.models import User
from django.test import TestCase

from wallets.models import Transaction, Wallet
from wallets.services import GenericCSVImportService


# Revolut PL export: UTF-8, comma-delimited, signed dot-decimal amounts,
# "YYYY-MM-DD HH:MM:SS" dates. Header/values carry Polish diacritics.
REVOLUT_CSV = (
    "Rodzaj,Produkt,Data rozpoczęcia,Data zrealizowania,Opis,Kwota,Opłata,Waluta,State,Saldo\n"
    "Płatność kartą,Bieżące,2026-05-01 14:00:43,2026-05-02 15:04:35,Żabka,-13.19,0.00,PLN,ZAKOŃCZONO,121.41\n"
    "Przelew,Bieżące,2026-05-03 09:00:00,2026-05-03 09:00:00,Wypłata,1500.00,0.00,PLN,ZAKOŃCZONO,1621.41\n"
).encode("utf-8")

# PKO BP-style export: Windows-1250, comma-delimited, amounts with a
# leading '+'/'-'. First data row is a pending "Blokada" with an empty
# "Data operacji" (settles later -> would duplicate a real row).
PKO_ROWS = (
    '"Data operacji","Data waluty","Typ transakcji","Kwota","Waluta","Saldo po transakcji","Opis transakcji"\n'
    '"2026-07-14","2026-07-14","Przelew na telefon przychodz. wew.","+33.00","PLN","","PRZELEW OD PAWEŁ JAMRÓZ"\n'
    '"","2026-07-13","Blokada","-90.34","PLN","W rozliczeniu","JMP S.A. BIEDRONKA"\n'
    '"2026-07-13","2026-07-13","Płatność kartą","-90,00","PLN","","www.zalando.pl"\n'
)
PKO_CSV = PKO_ROWS.encode("cp1250")


class CSVImportParseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="imp", password="pass")
        self.wallet = Wallet.objects.create(
            name="Main", user=self.user, initial_value=0, currency="pln"
        )

    def _service(self, raw):
        return GenericCSVImportService(self.user, self.wallet, io.BytesIO(raw))

    def test_revolut_utf8_parses(self):
        result = self._service(REVOLUT_CSV).parse()
        self.assertTrue(result["success"])
        self.assertEqual(result["total_rows"], 2)
        self.assertIn("Kwota", result["columns"])
        # Diacritics survive decoding.
        self.assertIn("Data rozpoczęcia", result["columns"])

    def test_blank_headers_are_named_and_preserved(self):
        # PKO BP pads rows with blank-named columns holding extra fields.
        raw = (
            '"Data operacji","Kwota","Opis transakcji","","",""\n'
            '"2026-07-14","-230.85","Tytuł: card","Lokalizacja: ORLEN PAY","Numer karty: 4251","x"\n'
        ).encode("cp1250")
        result = self._service(raw).parse()
        self.assertEqual(
            result["columns"],
            ["Data operacji", "Kwota", "Opis transakcji", "Column 4", "Column 5", "Column 6"],
        )
        # The data under the former blank columns is retained, not dropped.
        row = result["sample_rows"][0]
        self.assertEqual(row["Column 4"], "Lokalizacja: ORLEN PAY")
        self.assertEqual(row["Column 5"], "Numer karty: 4251")

    def test_pko_cp1250_parses_without_crash(self):
        # Regression: the old parser decoded utf-8-sig only and raised on
        # the 0xa3 byte (Ł) in this statement.
        result = self._service(PKO_CSV).parse()
        self.assertTrue(result["success"])
        self.assertEqual(result["total_rows"], 3)
        self.assertIn("Typ transakcji", result["columns"])
        # cp1250 correctly decoded -> no replacement chars, real letters.
        joined = "".join(
            v for row in result["sample_rows"] for v in row.values() if v
        )
        self.assertNotIn("�", joined)
        self.assertIn("JAMRÓZ", joined)


class CSVImportExecuteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="imp2", password="pass")
        self.wallet = Wallet.objects.create(
            name="Main", user=self.user, initial_value=0, currency="pln"
        )

    def _service(self, raw):
        return GenericCSVImportService(self.user, self.wallet, io.BytesIO(raw))

    def test_revolut_signed_amounts_imported(self):
        result = self._service(REVOLUT_CSV).execute(
            column_mapping={
                "amount": "Kwota",
                "date": "Data zrealizowania",
                "note": "Opis",
            },
            amount_config={"mode": "signed"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["stats"]["imported"], 2)
        amounts = sorted(str(t.amount) for t in Transaction.objects.all())
        self.assertEqual(amounts, ["-13.19", "1500.00"])

    def test_pko_maps_data_waluty_and_parses_comma_decimal(self):
        # Mapping date -> "Data waluty" avoids the empty "Data operacji"
        # on the pending Blokada row, and "-90,00" parses as -90.00.
        result = self._service(PKO_CSV).execute(
            column_mapping={
                "amount": "Kwota",
                "date": "Data waluty",
                "note": "Opis transakcji",
            },
            amount_config={"mode": "signed"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["stats"]["imported"], 3)
        self.assertEqual(result["stats"]["errors"], 0)
        by_note = {t.note: t.amount for t in Transaction.objects.all()}
        self.assertEqual(str(by_note["www.zalando.pl"]), "-90.00")
        self.assertEqual(str(by_note["PRZELEW OD PAWEŁ JAMRÓZ"]), "33.00")

    def test_blokada_rows_can_be_filtered_out(self):
        result = self._service(PKO_CSV).execute(
            column_mapping={
                "amount": "Kwota",
                "date": "Data waluty",
                "note": "Opis transakcji",
            },
            amount_config={"mode": "signed"},
            filters=[
                {"column": "Typ transakcji", "operator": "not_equals", "value": "Blokada"}
            ],
        )
        self.assertEqual(result["stats"]["imported"], 2)
        self.assertEqual(result["stats"]["skipped_filtered"], 1)
