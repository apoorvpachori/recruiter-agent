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

Run quality checks with:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv.lock` is committed to pin reproducible dependency resolution. Keep any real profile, resume, and application data in the ignored local `data/` directory; never commit it.
