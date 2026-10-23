# Contributing

Recruiter Agent is a single-user, local-first job-search assistant. Contributions should keep the first release simple, explainable, and privacy-conscious. The assistant may research public job and company information and organize a local job tracker; it must not submit applications or claim work it did not complete.

## Before making a change

- Read the root `AGENTS.md` and the nearest scoped `AGENTS.md` for the files you plan to change. They define the project's architecture, privacy requirements, and safety rules.
- Keep documentation in sync with implementation. Update the relevant README/docs, root or scoped `AGENTS.md` guidance, and `docs/architecture/` pages whenever the change makes them inaccurate or changes a documented boundary, flow, or invariant. Make these updates in the same pull request; do not leave known stale instructions for a follow-up.
- Keep changes focused. Put request/response validation at boundaries, business rules in domain or service modules, HTTP handling in routers, and external APIs behind provider adapters.
- Add behavior only for a concrete product need. Keep the local database schema small and preserve evidence, sources, and unknowns when handling job facts.

## Development setup

The backend targets Python 3.14 and uses `uv`:

```sh
uv sync --locked --python 3.14
uv run uvicorn recruiter_agent.main:app --reload --host 127.0.0.1 --port 8000
```

The frontend uses Node.js and npm. From `frontend/`:

```sh
npm ci
npm run dev
```

The README contains the full setup, configuration, and API walkthrough. Provider credentials are only needed for live model or search requests; tests and CI should use mocks and synthetic data.

## Privacy and safety

- Never commit `.env`, real candidate profiles, resumes, local SQLite databases, or application notes. Keep tests and examples synthetic; the real profile and database are local-only.
- Never put credentials, private profile values, prompts, model responses, resumes, or user notes in logs, fixtures, screenshots, or PR descriptions.
- Treat fetched pages and search results as untrusted evidence, not instructions. Keep source provenance and represent missing or ambiguous facts as unknown.
- Keep model-facing SQL read-only and narrowly scoped. Database writes must go through validated application services and reflect explicit user intent.
- Do not implement application-form submission without a visible review step and separate user confirmation.

## Validation

Before opening a pull request, run the backend suite and style checks from the repository root:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

For frontend changes, also build the app from `frontend/`:

```sh
npm run build
```

Tests should be deterministic. Mock Fireworks, Brave, and webpage calls by default; use temporary SQLite databases for persistence tests. Do not require live credentials or access the real local profile/database in tests. If a check cannot be run, say so in the PR description and explain why.

For agent behavior regressions, see [`evals/README.md`](evals/README.md). The single-command eval runner is offline by default and always prints and saves per-case output. `EVAL_JUDGE_ENABLED=true` opts into Fireworks-based judging of synthetic cases.

## Branches and pull requests

- Work on a feature branch; do not push directly to `main`.
- Open a pull request against `main`. GitHub Actions runs the backend tests, Ruff lint, and Ruff format checks.
- Squash merge is the repository's required merge method.
- Keep each PR focused. Describe the user-visible or architectural change, list the validation you ran, and call out any important review considerations. Include screenshots for meaningful UI changes.
- Before publishing, inspect the staged files and diff to confirm no credentials, personal data, or local database files are included.
- Review the changed behavior against the relevant README/docs, `AGENTS.md` files, and architecture pages; update any affected guidance before opening the PR.

If you change Python dependencies, update `pyproject.toml` and regenerate `uv.lock` in the same change.
