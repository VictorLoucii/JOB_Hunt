# Code Quality & Style Rules (Python / FastAPI)

## Type Safety
- All function signatures must have **type hints** for parameters and return values.
- Use `from __future__ import annotations` at the top of every module for modern annotation syntax.
- Pydantic models must be used for **all** external data boundaries: API request/response, LLM output parsing, config loading.

## Async / FastAPI
- Use `async def` for all FastAPI route handlers.
- Blocking calls (file I/O, SQLite, subprocess) must use `asyncio.to_thread()` or `run_in_executor`.
- Use `httpx.AsyncClient` for outbound HTTP calls (OpenRouter API).

## Configuration
- All config values must flow through `pydantic-settings` `BaseSettings` (for secrets) or `config.yaml` (for user profile).
- No scattered `os.getenv()` calls — use the centralized `Settings` object from `server/config.py`.

## Database
- Database operations must use **context managers** (`with` / `async with`) to prevent connection leaks.
- All SQL queries should use parameterized queries (`?` placeholders) — never string formatting.

## Documentation
- Every service function must have a **docstring** explaining its purpose, parameters, and return value.
- Module-level docstrings are required for all `.py` files.

## File & Path Handling
- Use `pathlib.Path` over `os.path` for all file operations.
- Always use `Path.expanduser()` when handling user-configured paths (e.g., resume directory).

## Modularity
- Keep service modules under **300 lines**. If a module grows beyond this, extract sub-modules.
- Routers define endpoints only — business logic belongs in `services/`.
- Shared utilities belong in `utils/`.

## Logging
- Use Python's `logging` module — not `print()`.
- Log levels:
  - `DEBUG`: Development diagnostics, variable dumps
  - `INFO`: Application flow events (server start, draft created, email sent)
  - `WARNING`: Recoverable issues (missing optional config, fallback triggered)
  - `ERROR`: Failures (API errors, file not found, Gmail auth expired)

## Code Style
- Follow `ruff` linting rules as configured in `pyproject.toml`.
- Line length: 100 characters max.
- Import ordering: stdlib → third-party → local (enforced by `ruff` isort).
