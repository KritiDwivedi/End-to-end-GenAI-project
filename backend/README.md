# Backend

FastAPI app for Document Copilot.

## Setup

```bash
cd document-copilot/backend
cp .env.example .env
uv sync
```

## Run the app

```bash
uv run uvicorn app.main:app --reload
```

API health check: `http://127.0.0.1:8000/health`

Interactive docs: `http://127.0.0.1:8000/docs`

## Manage the app

```bash
uv run pytest
uv run ruff check .
uv run alembic upgrade head
```

Use `app/main.py` as the FastAPI entry point.
