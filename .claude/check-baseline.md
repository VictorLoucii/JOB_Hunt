# Check baseline

Measured 2026-10-24 with `.venv/bin/` tools, sandbox on (same counts with it off).
Update this file only in the change that moves a number, and say why.

| Check | Result |
|---|---|
| `.venv/bin/pytest` | 68 passed, 5 failed, 5 errors |
| `.venv/bin/ruff check .` | 15 errors: 14 E501, 1 SIM105 |
| `.venv/bin/mypy server` | 23 errors in 4 files |

Failing test IDs (compare the set, not only the count):

- FAILED `tests/test_gmail_client.py::test_create_draft_without_attachment`
- FAILED `tests/test_gmail_client.py::test_create_draft_with_attachment`
- FAILED `tests/test_gmail_client.py::test_create_draft_returns_draft_id`
- FAILED `tests/test_gmail_client.py::test_create_draft_api_error`
- FAILED `tests/test_llm_client.py::TestLLMClient::test_draft_email_invalid_json`
- ERROR `tests/test_webhook.py::test_webhook_duplicate_post`
- ERROR `tests/test_webhook.py::test_webhook_invalid_payload_empty_text`
- ERROR `tests/test_webhook.py::test_webhook_invalid_payload_non_linkedin_url`
- ERROR `tests/test_webhook.py::test_webhook_valid_payload_pipeline_fires`
- ERROR `tests/test_webhook.py::test_webhook_ineligible_pipeline_skips`

Known causes:

- `tests/test_webhook.py` builds `TestClient(app)`, which runs the real `lifespan`.
  It needs the real `.env`; the sandbox blocks it, so `Settings` fails validation.
- `tests/test_gmail_client.py` sets `client._service`, which `create_draft` no
  longer uses.
- `test_draft_email_invalid_json`: probably the 3-attempt retry. Not verified.
