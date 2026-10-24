---
paths:
  - "tests/**/*.py"
---

# Test rules

Earned 2026-10-24: `pytest` reached the real `.env`, `config.yaml` and Gmail
token, and called Google, because `TestClient(app)` runs the real `lifespan`.

- Fake every system edge: OpenRouter (`LLMClient`), Gmail (`GmailClient`,
  `googleapiclient.discovery.build`), the clock. Keep our own modules real.
- SQLite in tests is `Database(db_path=Path(":memory:"))` or a `tmp_path` file,
  never `data/jobhunt.db`.
- Settings and profile come from the `mock_settings` / `mock_user_profile`
  fixtures in `tests/conftest.py`; a test that needs a key uses a fake value.
- A test that builds `TestClient(app)` also replaces the startup clients
  (`GmailClient.authenticate`, `Settings`, `UserProfile`), not only the
  `dependency_overrides`.
