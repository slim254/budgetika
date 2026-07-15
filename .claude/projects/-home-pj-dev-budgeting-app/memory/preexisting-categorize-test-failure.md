---
name: preexisting-categorize-test-failure
description: A backend categorize test fails on main and is unrelated to new work
metadata:
  type: project
---

`tests/wallets/test_categorize.py::TestCategorize.test_unknown_category_returns_null_suggestion` fails on `main` (and every branch off it), independent of any CSV-AI-categorize work.

**Why:** The test creates a user with only a "Dining" category and mocks the LLM to reply "Groceries", expecting `suggestion == None`. But the signup signal (`wallets/signals.py`) auto-copies the default categories from `constants.py` — which include "Groceries" — so the reply legitimately matches an existing category and the suggestion is non-null. The test's premise (user has no "Groceries") is wrong given the signal.

**How to apply:** When running `python manage.py test tests.wallets`, expect exactly this 1 failure as baseline noise. Don't attribute it to your changes. A real fix would either patch out the signal in the test or assert against a category name that isn't a default.
