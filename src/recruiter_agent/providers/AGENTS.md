# Provider adapter guidance

- Follow the repository workflow in `CONTRIBUTING.md`; update relevant documentation and agent guidance in the same change.

- Keep provider-specific HTTP details and authentication here; expose normalized models/interfaces to the rest of the app.
- Read credentials from settings only. Never hardcode or log credentials.
- Set timeouts, bound result sizes, respect rate limits, and surface sanitized provider failures.
- Preserve provider source URLs and timestamps so downstream job facts can cite evidence.
- Mock HTTP responses in tests; do not require live credentials in CI.
