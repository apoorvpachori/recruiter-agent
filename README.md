# recruiter-agent

A personal AI job-search copilot to help assess opportunities, prepare applications, and track a job search. See the [product spec](docs/product-spec.md) and [architecture proposal](docs/architecture.md).

## Development setup (macOS)

This project targets Python 3.14 and uses `uv` to manage dependencies and the project environment. The project environment is created automatically by `uv` in `.venv`; there is no need to activate it manually.

```sh
brew install python@3.14 uv
uv sync --python 3.14
uv run uvicorn recruiter_agent.main:app --reload
```

The API will be available at <http://127.0.0.1:8000>. Check <http://127.0.0.1:8000/healthz> or open the interactive API docs at <http://127.0.0.1:8000/docs>.

## Chat frontend

The React/Vite single-page app lives in `frontend/`. In separate terminals, start FastAPI and Vite:

```sh
# Terminal 1: backend
uv run uvicorn recruiter_agent.main:app --reload

# Terminal 2: frontend
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api/*` requests to FastAPI on port 8000, so the browser UI can call the existing agent endpoint without enabling broad CORS. Build the static frontend with `cd frontend && npm run build`; the output goes to ignored `frontend/dist/`.

Run quality checks with:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv.lock` is committed to pin reproducible dependency resolution. Keep any real profile, resume, and application data in the ignored local `data/` directory; never commit it.

## Candidate profile

The single-user profile lives in `data/profile.json`. It is validated by the Pydantic models in `src/recruiter_agent/profile/` and is intentionally ignored by Git. Edit this file directly; the agent can load it through the profile loader when a workflow needs candidate context. Unset preferences are left empty or `null` rather than inferred. You can point the loader at another local file with `RECRUITER_AGENT_PROFILE_PATH`.

## Model and tracing configuration

Set `FIREWORKS_API_KEY` and `FIREWORKS_MODEL` in `.env`. LangSmith tracing is enabled when `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` is set; the default example enables tracing. Use `LANGSMITH_PROJECT` to choose the dashboard project. `LANGSMITH_AGENT_ID` and `LANGSMITH_AGENT_ENVIRONMENT` are optional trace metadata; they do not select a project or change where a run is stored. Traces can include prompt/output content. Never commit `.env` or paste keys into chat.
