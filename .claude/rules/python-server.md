---
paths:
  - "server/**/*.py"
---

# Server code rules

Carried over from the Gemini rules (`.agents/rules/code-quality.md`, deleted;
see git history). Ruff and mypy already enforce type hints, line length,
import order and bare `except`.

- Start every module with a module docstring, then `from __future__ import annotations`.
- Give every service function a docstring: purpose, parameters, return value.
- Pydantic models guard every external boundary: request/response, LLM output, config.
- Route handlers are `async def`. Wrap blocking work (file I/O, SQLite, Gmail API)
  in `asyncio.to_thread()`. Outbound HTTP goes through `httpx.AsyncClient`.
- Read configuration from `Settings` (`.env`) or `UserProfile` (`config.yaml`) in
  `server/config.py`; reach them through `server/dependencies.py`, never `os.getenv`.
- SQLite: open connections in `with` blocks; pass values as `?` parameters.
- Paths: `pathlib.Path`; call `.expanduser()` on any user-configured path.
- Routers hold endpoints only; logic lives in `services/`, shared helpers in `utils/`.
  Keep a service module under 300 lines (`llm_client.py` already exceeds it: split
  only when asked).
- Log with `logging`: DEBUG diagnostics, INFO flow events, WARNING fallbacks,
  ERROR failures. Catch the specific exception and log it.
- Changes to shared models or service functions are backward compatible: new
  parameters and fields are optional with defaults.
