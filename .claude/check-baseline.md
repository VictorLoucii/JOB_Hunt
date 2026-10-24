# Check baseline

Measured 2026-10-24 with `.venv/bin/` tools, sandbox on; not re-measured with it off.
Update this file only in the change that moves a number, and say why.

| Check | Result |
|---|---|
| `.venv/bin/pytest` | 79 passed |
| `.venv/bin/ruff check .` | 0 errors |
| `.venv/bin/mypy server` | 0 errors |

Failing test IDs (compare the set, not only the count):

- none

Known causes:

- Fixed: the `client` fixture in `tests/test_webhook.py` fakes the startup clients.
- Fixed: the Gmail fixture fakes `build()`, which `create_draft` calls each time.
- Fixed: `test_draft_email_invalid_json` now expects the current `LLMError` message and checks 3 attempts.
- Fixed: ruff E501/SIM105. `credentials/` is excluded, so ruff no longer warns
  'Operation not permitted'.
- Fixed: 23 mypy errors (casts, annotations, Google overrides in `pyproject.toml`,
  `types-PyYAML` in the `dev` extras).
- Added: `test_create_draft_build_error`; `build()` in `create_draft` now sits inside
  the `try`, so its failure raises `GmailError`.
