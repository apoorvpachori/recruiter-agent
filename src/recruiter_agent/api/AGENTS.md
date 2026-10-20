# FastAPI route guidance

- Validate request/response payloads with Pydantic or SQLModel.
- Keep endpoints thin; delegate persistence and domain rules to dedicated modules.
- Return clear 4xx responses for user-correctable errors and avoid leaking stack traces or secrets.
- Never log request bodies or prompt text. Keep request IDs and safe timing/status metadata.
- Add endpoint tests with dependency overrides and temporary databases.
