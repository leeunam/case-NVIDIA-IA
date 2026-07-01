# Frontend Foundation

Operational workbench for the optional `frontend_api_run.v1` backend contract from issue #98.

The app is intentionally dependency-free for the first foundation slice: browser ES modules, CSS, and Node's built-in test runner. This keeps local UI development deterministic and avoids changing the Python backend validation flow.

## Install

The frontend has no npm runtime dependencies. Use Node 20 or newer:

```bash
node --version
npm --version
```

Backend development dependencies are installed from the repository root when the real API is needed:

```bash
python -m pip install -e ".[dev,api]"
```

## Commands

Run from the repository root:

```bash
npm --prefix frontend run dev
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run qa
npm --prefix frontend run qa:browser
```

The dev server serves the app at `http://127.0.0.1:5173`.

`lint` is a dependency-free syntax check for frontend JavaScript modules. `qa` runs lint, tests, and build. `qa:browser` renders temporary static HTML from the same app renderer and uses Chrome headless to capture desktop and mobile screenshots for launcher, run workspace, evidence, assessment, NVIDIA match, briefing, run-history lookup, and production smokes. By default it writes screenshots to:

```text
/tmp/nvidia-startup-intel-frontend-qa
```

Set `FRONTEND_QA_OUTPUT_DIR` or `CHROME_BIN` when the defaults do not match the local machine.

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

Real mode should only receive a backend base URL. Do not put provider tokens, database URLs, API keys, or other credentials in frontend query parameters.

The frontend client maps only these backend routes:

- `POST /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/production-smoke-matrix`

## Production Smokes Screen

The `Production Smokes` tab is a maintainer/demo-readiness screen over the read-only production smoke matrix. It is not required for normal local validation.

The screen shows the default deterministic validation commands separately from opt-in real integration smokes. For each real smoke it displays status, bottleneck, enable flag, required environment variable names, prerequisites, command, expected artifacts, cleanup, and diagnostic text. It must never request, echo, store, or display credential values; only variable names and configured/missing status from the API contract may be shown.

The full operational smoke guidance is intentionally bounded: use only a public startup URL or bounded query, review generated artifacts for credential hygiene, and do not commit generated smoke artifacts.

## Mock Demo Flow

Use mock mode for deterministic local demos without network, credentials, Postgres, LangGraph, LLM, embeddings, or a search provider:

1. Start the frontend: `npm --prefix frontend run dev`.
2. Open `http://127.0.0.1:5173`.
3. Enter `https://neuralmind.ai/` as Startup URL and `NeuralMind` as Startup name.
4. Keep safe defaults: JSON persistence, BM25 local retrieval, local orchestration, no production toggles.
5. Start the run.
6. Inspect Runs, Evidence, Assessment, NVIDIA Match, Briefing, and Production Smokes.

Seeded mock runs can also be opened directly:

```text
http://127.0.0.1:5173?run_id=mock-completed-run&section=briefing
http://127.0.0.1:5173?run_id=mock-human-review-run&section=runs
http://127.0.0.1:5173?run_id=mock-failed-run&section=runs
```

The `section` parameter supports `runs`, `evidence`, `assessment`, `nvidia-match`, `briefing`, and `production-smokes`.

## Contract Boundary

`src/api-contract.js` owns the typed JSDoc contract and runtime schema checks for:

- `frontend_api_run_create.v1`
- `frontend_api_run.v1`
- `frontend_api_production_smoke_matrix.v1`

`src/mock-data.js` implements fixture mode for local UI work without network, credentials, Postgres, LangGraph, LLM, embedding, or a real search provider.

Future agents should keep domain rules in the Python backend. The frontend may display `final_payload` details when present, but missing details must remain empty states instead of inferred data.

## Validation

Frontend validation:

```bash
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run qa:browser
```

Backend validation remains unchanged:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src
```

## Final Demo Checklist

- Run `npm --prefix frontend run qa`.
- Run `npm --prefix frontend run qa:browser` and inspect the desktop/mobile screenshots in the output directory.
- Run backend validation from the repository root.
- Start the dev server and complete one mock run using the Mock Demo Flow above.
- Confirm the briefing is either an executive briefing with supported NVIDIA citations or a human-review briefing with reasons and pending validation questions.
- Confirm empty, loading, failed, and human-review states do not present unsupported claims as facts.
- Confirm production toggles remain explicit and no credentials or secret values are shown in the UI.
