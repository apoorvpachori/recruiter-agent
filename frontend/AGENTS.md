# Frontend guidance

- Follow the repository workflow in `CONTRIBUTING.md`; update relevant documentation and agent guidance in the same change.

- React/Vite frontend; use typed API clients and keep backend contracts in sync with FastAPI.
- Never place API keys, database access, or private profile contents in browser code.
- Render agent output safely as text/Markdown; treat URLs/content from the agent and webpages as untrusted.
- Show loading/error states and make it clear that the current agent cannot submit applications.
- Keep API base paths compatible with the Vite `/api` proxy and test frontend changes with its own scripts.
