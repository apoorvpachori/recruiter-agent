# Source package guidance

- Keep `recruiter_agent` modules small and organized by responsibility.
- Do not place personal profile data or credentials under `src/`.
- Avoid side effects at import time; initialize runtime resources at application startup or through explicit factories.
- Use typed Pydantic/SQLModel contracts at external boundaries.
