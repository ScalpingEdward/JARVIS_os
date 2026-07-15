# JARVIS OS Backend

Minimal Phase 1A backend built with FastAPI.

## Local setup

```bash
cd backend
python -m venv .venv
```

Activate the environment, then install and run:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

- API: `http://127.0.0.1:8000/`
- Health: `http://127.0.0.1:8000/health`
- Interactive API docs: `http://127.0.0.1:8000/docs`

## Tests

```bash
pytest -q
```

No API keys or paid services are required for Phase 1A.
