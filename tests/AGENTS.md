# Test guidance

- Follow the repository workflow in `CONTRIBUTING.md`; update relevant documentation and agent guidance in the same change.

- Use pytest and deterministic fixtures. Mock external model, Brave, and web calls by default.
- Use temporary SQLite databases for persistence/API tests; never connect tests to the real local database.
- Never load real `.env`, candidate profile, or resume data in tests.
- Cover success, validation failures, duplicates, unknown evidence, dealbreakers, and unauthorized SQL/actions.
- Run the complete suite plus Ruff lint/format checks before PR.
