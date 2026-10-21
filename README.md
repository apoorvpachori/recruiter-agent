# Recruiter Agent

A single-user, local-first recruiting assistant for reviewing job postings, researching companies, comparing roles with saved preferences, and keeping an application tracker. The agent can read public pages and organize evidence. **It does not fill out or submit applications.**

## Current capabilities

- React/Vite chat UI backed by a FastAPI API.
- LangChain v1 agent orchestration with Fireworks-hosted model inference.
- Read-only webpage retrieval using HTTPX and Beautiful Soup, with public-network URL validation and response limits.
- Brave LLM Context search returning extracted snippets, source URLs, and source dates.
- Job fact extraction and an LLM-backed fit assessment against the local profile, including unknowns and a defense-company dealbreaker.
- Local SQLite job tracking using SQLModel.
- Read-only, jobs-table-scoped SQL queries plus explicit save/update tools for the agent.
- Structured JSON service logs with redaction and optional LangSmith tracing.

## Important limits and safety behavior

- This is a **personal, local-only, single-user** app. It is not authenticated for exposure to a LAN or public internet.
- Fit facts should have source evidence. Search results are leads; relevant sources should be opened and checked.
- Unknown, ambiguous, conflicting, or stale facts should remain unknown. The agent should not invent profile preferences or job facts.
- The defense-company exclusion is a dealbreaker. **No defense evidence found does not mean clearance.**
- The agent can read and research, but it cannot fill forms or submit applications. Any future application interaction must be visible, reviewed, and separately confirmed by the user.
- The agent's SQL tool is read-only, restricted to the `jobs` table, limited to 100 result rows, and rejects writes/multiple statements. Job edits use dedicated validated tools and require explicit user intent.
- Web pages and search results are untrusted data, not instructions for the agent.

## Repository map

```text
.
├── AGENTS.md                          # Root contributor/agent safety rules
├── docs/architecture/                 # Architecture source of truth and decision records
├── .github/                           # CI and PR template
├── frontend/                          # React + Vite UI (own AGENTS.md)
├── src/
│   └── recruiter_agent/
│       ├── api/                       # FastAPI routes, contracts, HTTP middleware
│       ├── agent/                     # Agent graph, prompt, and tools
│       ├── jobs/                      # Job models, fit evaluation, SQL access and services
│       ├── profile/                   # Pydantic schema and local JSON profile loader
│       ├── providers/                 # Fireworks model and Brave search adapters
│       ├── tools/                     # Web page retrieval/parsing
│       ├── database.py                # SQLModel engine, session dependency, table setup
│       ├── logging_config.py          # JSON formatter and redaction
│       ├── settings.py                # Environment and .env configuration
│       └── main.py                    # FastAPI app composition and request logging
├── tests/                             # Mocked provider tests and temporary SQLite tests
├── pyproject.toml                     # Python dependencies and tool configuration
└── uv.lock                            # Locked/resolved Python dependency graph
```

Scoped `AGENTS.md` files live at the repository root and in source/test/frontend areas. Read the nearest relevant one before changing that area.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development validation, privacy expectations, and the pull request workflow.

See the [architecture guide](docs/architecture/README.md) before changing system boundaries, data flow, persistence, or agent capabilities.

## Prerequisites

- Python **3.14**
- [`uv`](https://docs.astral.sh/uv/) for Python environments/dependencies
- Node.js/npm for frontend development
- Fireworks API key and model ID for live agent responses
- Brave Search API key for live company research
- LangSmith API key is optional, for trace observability

On macOS with Homebrew:

```sh
brew install python@3.14 uv
```

`uv` follows `.python-version` and manages `.venv` for the project. There is no need to activate the virtual environment manually.

## Configure credentials and profile

Copy the example environment file and fill keys locally:

```sh
cp .env.example .env
```

Configure at minimum:

```dotenv
FIREWORKS_API_KEY=...
FIREWORKS_MODEL=accounts/fireworks/models/<model-id>
BRAVE_SEARCH_API_KEY=...
BRAVE_SEARCH_ENDPOINT=https://api.search.brave.com/res/v1/llm/context
```

To enable LangSmith tracing, set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and optionally `LANGSMITH_PROJECT`. Traces can include prompts, tool inputs, retrieved web content, and model outputs; enable tracing only if you are comfortable sending that data to LangSmith.

Never put provider credentials in frontend/Vite variables: browser-exposed frontend configuration is public. Never commit `.env`.

The single-user candidate profile lives in the ignored local file `data/profile.json`. It is validated by `src/recruiter_agent/profile/models.py`. Edit it directly; absent preferences should remain empty/null rather than guessed. Override its location with `RECRUITER_AGENT_PROFILE_PATH` if needed. Never commit the real profile or resume.

## Run locally

### Backend

```sh
uv sync --locked --python 3.14
uv run uvicorn recruiter_agent.main:app --reload --host 127.0.0.1 --port 8000
```

- Health check: <http://127.0.0.1:8000/healthz>
- API docs: <http://127.0.0.1:8000/docs>

### Frontend

Run the frontend separately in a second terminal:

```sh
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>. Vite proxies `/api/*` requests to FastAPI at `127.0.0.1:8000`. Build with `npm run build`; output is ignored under `frontend/dist/`.

## API examples

Send a natural-language request to the agent:

```sh
curl -X POST http://127.0.0.1:8000/v1/agent/input \
  -H 'Content-Type: application/json' \
  -d '{"text":"Assess this role: https://jobs.example.com/jobs/123"}'
```

Track a job manually:

```sh
curl -X POST http://127.0.0.1:8000/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://jobs.example.com/jobs/123","company":"Example AI","title":"Applied AI Engineer"}'

curl 'http://127.0.0.1:8000/v1/jobs?status=saved'

curl -X PATCH http://127.0.0.1:8000/v1/jobs/1 \
  -H 'Content-Type: application/json' \
  -d '{"status":"applied"}'
```

Current status values are `saved`, `researching`, `interested`, `draft_ready`, `applied`, `interviewing`, `offer`, `rejected`, `withdrawn`, and `on_hold`. Duplicate job URLs return HTTP 409.

## SQLite data

The backend uses SQLModel with SQLite underneath. By default it creates `data/recruiter-agent.sqlite3` and the single `jobs` table on application startup. Override the connection with `DATABASE_URL`, for example:

```dotenv
DATABASE_URL=sqlite:////absolute/path/to/recruiter-agent.sqlite3
```

Each job row contains `id`, unique `url`, optional `company`, `title`, current `status`, optional `notes`, and timestamps. The schema is deliberately kept to one table; status history and other entities can be added later if product requirements call for them. The local DB and SQLite journal files are Git-ignored.

The agent can call `get_database_schema` and `query_jobs_database` for read-only inspection. Database SQL is opened in read-only mode, only `SELECT` statements referencing `jobs` are allowed, queries are capped at 100 rows, and write operations are rejected. When the user explicitly asks to save or update a job, the agent can use `save_tracked_job` or `update_tracked_job`. The API and agent tools share the validated operations in `jobs/services/`; neither writes generated SQL.

## Tests and quality checks

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests mock Fireworks/Brave/web requests and use temporary SQLite DBs. CI does not require live credentials. If Python dependencies change, regenerate and commit `uv.lock`.

## Git and PR workflow

- Work on a feature branch; direct push to `main` is blocked.
- Open a pull request against `main`; GitHub Actions runs the checks above.
- Squash merge is the repository’s only enabled merge method; merged PR branches are deleted.
- Before PR, inspect the diff and verify no `.env`, `data/profile.json`, resume, SQLite DB, or other personal data is staged.
