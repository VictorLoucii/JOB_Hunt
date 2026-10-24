# CLAUDE.md

JobHunt drafts job-application emails from LinkedIn posts. A Tampermonkey
userscript posts the selected text to a local FastAPI server; the server screens
eligibility, drafts with an LLM (OpenRouter) and saves a Gmail draft. A human
reviews and sends every draft (HITL). Single user, local only.

## Commands

Run every tool through `.venv/bin/`. `ruff` and `mypy` are not on PATH, and a
bare `pytest` is the system Python 3.14 copy, outside the venv.

| Task | Command |
|---|---|
| Install | `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"` |
| Test | `.venv/bin/pytest` |
| One test | `.venv/bin/pytest tests/test_models.py::TestEmailDraft` |
| Lint | `.venv/bin/ruff check .` |
| Typecheck | `.venv/bin/mypy server` |
| Start server | `.venv/bin/jobhunt` (same as `.venv/bin/python -m server.main`) |
| Draft stats | `.venv/bin/jobhunt stats` |

The server needs the owner's `.env`, `config.yaml` and `credentials/`. The owner
starts it; Claude hands over the command. Gmail sign-in happens at that start:
with no valid token, `GmailClient.authenticate` opens a browser window.

## How a post flows

1. `POST /webhook` (`server/routers/webhook.py`) receives the post text.
2. `services/db.py` rejects the same post text, or an author email already
   `approved` (SQLite, `data/jobhunt.db`).
3. `LLMClient.evaluate_eligibility` screens against `user.constraints` in
   `config.yaml`; the screening prompt lives inside `server/services/llm_client.py`.
4. `services/email_extractor.py` finds the address: regex first, LLM fallback.
5. A background task drafts with `prompts/email_draft.txt` and saves a Gmail draft,
   attaching the newest PDF from the resume directory (`utils/resume.py`).

Startup (`lifespan` in `server/main.py`) builds the clients once and puts them on
`app.state`; `server/dependencies.py` hands them to routes. LLM calls retry 3
times on bad JSON and walk the `llm.fallback_models` chain on 429.

## Working rules

- State assumptions; when a request reads two ways, ask. Say plainly when the
  files cannot confirm something.
- Touch only what the request needs. Keep existing comments, docstrings and
  unrelated functions; mention dead code instead of removing it.
- Name the file and line of every change you propose or make.
- Grep every reference before renaming or deleting a function, model field,
  database column or variable.
- Check `pyproject.toml` and `requirements.txt` for an existing package before
  writing a utility; ask before adding a dependency.
- Done means pytest, ruff and mypy were run, no count is above
  `.claude/check-baseline.md`, and no failing test ID is new. Report the results.
  Fixing the baseline itself is a separate task, done only when asked.
- Keep every check current: when code changes what a check guards, update the
  check in the same change. A weakened assertion that turns green proves nothing.
- Stage named files only and show `git diff --staged` before any commit.
- Server code and test code carry extra rules in `.claude/rules/`; they load
  when those files are touched.

## Secrets and personal data

Variable names live in `.env.example` and `config.example.yaml`; read those.
`.env`, `config.yaml`, `credentials/`, `AI_RESUME/` and `data/jobhunt.db` hold
keys, OAuth tokens and the owner's personal data. `.claude/settings.json` denies
them to Claude's tools and, through the sandbox, to shell commands. Keys reach
code only through `Settings`. Older copies of `config.yaml` sit in git history
(10 commits, on `origin/main`); nothing guards them. Leave them unread; removing
them is the owner's decision.

## Gotchas

- The venv runs Python 3.14.2, but mypy checks as 3.11 (`[tool.mypy]
  python_version`) and `.python-version` says 3.11.
- `LOG_LEVEL` in `.env` sets the log level; DEBUG for diagnostics.
- `implementaion_plans/` (sic) is gitignored build history, not a spec. Read one
  phase file only when a task names it.
- Shell traps on this Mac (`grep`, zsh globs, `===`): `~/.claude/playbooks/tool-traps-mac.md`.
