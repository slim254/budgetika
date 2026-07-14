# Migrations TODO

Migrations deferred during code-only implementation (no Python venv available in this environment). Run these after pulling on a machine with the backend venv set up.

- wallets: run `python manage.py makemigrations wallets && python manage.py migrate` after pulling on Linux — adds ModelPricing, AIUsageLog, UserAIQuota (B3a).
