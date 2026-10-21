# Backend package guidance

- Follow the repository workflow in `CONTRIBUTING.md`; update relevant documentation and agent guidance in the same change.

- `api/` handles HTTP validation/status codes only; call services for business operations.
- `agent/` orchestrates tools and formats user-facing answers; it must not bypass tool/service validation.
- `jobs/` owns job records and deterministic fit evaluation.
- `providers/` wraps external APIs and normalizes them into provider-neutral types.
- `profile/` loads the single-user local profile; do not expose the entire profile in prompts unless needed.
- `tools/` contains reusable IO helpers. Enforce timeouts, size limits, URL safety, and useful typed errors.
- Keep agent tools narrow, bounded, and documented. Web-derived facts need sources and timestamps.
