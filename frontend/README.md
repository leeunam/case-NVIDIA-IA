# Frontend Foundation

Operational workbench for the optional `frontend_api_run.v1` backend contract from issue #98.

The app is intentionally dependency-free for the first foundation slice: browser ES modules, CSS, and Node's built-in test runner. This keeps local UI development deterministic and avoids changing the Python backend validation flow.

## Commands

Run from the repository root:

```bash
npm --prefix frontend run dev
npm --prefix frontend run build
npm --prefix frontend test
```

The dev server serves the app at `http://127.0.0.1:5173`.

## API Modes

Default local mode is mock mode:

```text
http://127.0.0.1:5173
```

Real backend mode calls the optional FastAPI adapter:

```text
http://127.0.0.1:5173?api=real&baseUrl=http://127.0.0.1:8000
```

Start the backend API separately when using real mode:

```bash
python -m pip install -e ".[api]"
nvidia-startup-intel-api --host 127.0.0.1 --port 8000
```

The frontend client maps only these backend routes:

- `POST /api/runs`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/production-smoke-matrix`

## Run History Backing

In default mock mode, the Runs history is backed by deterministic fixtures in `src/mock-data.js`, including completed, human review, failed, and partial-artifact run records.

In real API mode, `GET /api/runs` currently reads the optional backend-for-frontend process store. That store is in-memory for the current environment: it exposes runs started during the API process lifetime and does not yet scan JSON artifact directories or Postgres history. Missing downstream artifacts remain explicit in the run record instead of being treated as successful stages.

## Contract Boundary

`src/api-contract.js` owns the typed JSDoc contract and runtime schema checks for:

- `frontend_api_run_create.v1`
- `frontend_api_run.v1`
- `frontend_api_run_history.v1`
- `frontend_api_production_smoke_matrix.v1`

`src/mock-data.js` implements fixture mode for local UI work without network, credentials, Postgres, LangGraph, LLM, embedding, or a real search provider.

Future agents should keep domain rules in the Python backend. The frontend may display `final_payload` details when present, but missing details must remain empty states instead of inferred data.

## Validation

Frontend validation:

```bash
npm --prefix frontend test
npm --prefix frontend run build
```

Backend validation remains unchanged:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src
```
