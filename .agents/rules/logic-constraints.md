# Core Logic & Behavior Rules

## General Principles
- Do not change application logic unless explicitly asked.
- **Backward Compatibility**: Ensure that any changes to shared modules, Pydantic models, or service functions use optional parameters with default values, so we don't break existing logic elsewhere.
- Do not guess or assume missing information. Only reason using the files and context that are explicitly provided or requested.
- Follow the existing project structure and coding style. Do not refactor unrelated code.
- If an issue cannot be confirmed from the provided files, state that clearly.

## Debugging
- Use Python's `logging` module for debugging. Log at `DEBUG` level for development diagnostics.
- Log level is controlled via the `LOG_LEVEL` environment variable.

## Modifications
- Tell me exactly at what line and which file to modify.
- Always search (grep) the codebase for all references of a function, class, database column, or variable before renaming or deleting it.
- **Non-Destructive Editing**: When updating files, preserve all existing comments, docstrings, and unrelated functions. Do not delete logic unless explicitly instructed.

## Dependencies
- Do not install or add new dependencies (`pip`, `uv`, etc.) without asking first.
- Always check existing dependencies in `pyproject.toml` or `requirements.txt` before writing custom utilities or adding packages.

## Secrets & Security
- Never hardcode API keys, passwords, credentials, or secrets. Always read them from environment variables via `.env` or Pydantic `BaseSettings`.
- Never read, open, or request access to the actual `.env` file or private credential files (`credentials.json`, `token.json`). If you need to verify environment configurations, use `.env.example` instead.

## Error Handling
- Ensure proper error handling: never use bare `except:` blocks. Always catch specific exceptions (`except SpecificException as e:`) and log errors appropriately or return descriptive API/UI messages.

## Quality Checks
- Ensure modified files are free of syntax errors or type mismatches (e.g., `ruff check`, `mypy`, `pytest`) before declaring a task complete.

## Git Hygiene
- Never run `git add .` or stage unrelated files. Only stage and commit files that directly implement the requested feature.
- Always review the `git diff` before committing.
