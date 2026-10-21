# Jobs domain guidance

- Follow the repository workflow in `CONTRIBUTING.md`; update relevant documentation and agent guidance in the same change.

- Keep job facts typed and attach evidence/source URLs to facts where possible.
- Fit evaluation is LLM-backed and may vary for the same inputs; deterministic safeguards in the domain layer must preserve unknowns and enforce the defense-company dealbreaker.
- Distinguish `match`, `mismatch`, and `unknown`; unknown is not automatically a failure.
- Overall fit may be provisional when no configured preference fails, but keep unresolved criteria visible.
- Never clear a defense-company dealbreaker solely because a search found no evidence.
- Keep the initial SQLite schema small. Add tables/fields only for concrete product needs and test migrations/schema behavior.
- Put shared persistence operations and input validation in `services/`; API routes and agent tools
  should call those services rather than duplicate database writes.
