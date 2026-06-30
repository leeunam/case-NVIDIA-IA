# Production Smoke Matrix

Este guia e a rota unica de validacao opt-in antes de demo ou uso operacional. A suite local
continua sendo:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src
```

Esses comandos nao exigem rede, credenciais, Postgres real, pgvector, LangGraph, LLM real,
embedding real, reranker real ou navegador real.

## Comando Da Matriz

Rode a matriz sem habilitar integracoes para ver o plano e os status `skipped`:

```bash
PYTHONPATH=src python -m nvidia_startup_intel.production_smoke_matrix
```

Rode uma integracao especifica:

```bash
PYTHONPATH=src python -m nvidia_startup_intel.production_smoke_matrix --only playwright_collection
```

Grave o relatorio:

```bash
PYTHONPATH=src python -m nvidia_startup_intel.production_smoke_matrix \
  --output runs/production-smoke/matrix.json
```

Cada linha retorna `passed`, `skipped` ou `failed`, com `bottleneck` indicando collection,
postgres, pgvector, embedding, retrieval, reranking, langgraph, llm, briefing_quality ou
credential_hygiene.

## Matrix

| Integracao | Habilitar | Pre-requisitos | Comando | Expected artifacts | Cleanup |
| --- | --- | --- | --- | --- | --- |
| Playwright real collection | `NVIDIA_STARTUP_INTEL_RUN_PLAYWRIGHT_COLLECTION_SMOKE=1` | `python -m playwright install chromium` | `NVIDIA_STARTUP_INTEL_RUN_PLAYWRIGHT_COLLECTION_SMOKE=1 python -m pytest -q tests/integration/test_playwright_collection_integration_smoke.py -m playwright_collection_integration` | `playwright_collection_smoke.v1` com `PageCollectionResult` e `extraction_strategy` terminando em `+playwright` | Nenhum artefato persistido por padrao |
| Postgres persistence | `NVIDIA_STARTUP_INTEL_RUN_POSTGRES_PERSISTENCE_SMOKE=1` | `docker compose up -d postgres`; `python -m pip install -e ".[postgres]"`; `DATABASE_URL` se nao usar defaults do compose | `NVIDIA_STARTUP_INTEL_RUN_POSTGRES_PERSISTENCE_SMOKE=1 PYTHONPATH=src python -m nvidia_startup_intel.postgres_persistence_smoke` | run completo com paginas, perfil, evidencias, qualidade, assessment, retrievals, recommendation set, briefing e metricas | `docker compose down` quando o banco de smoke nao for mais necessario |
| pgvector retrieval | `NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE=1` | `docker compose up -d postgres`; `python -m pip install -e ".[pgvector]"`; `DATABASE_URL` ou `NVIDIA_STARTUP_INTEL_PGVECTOR_DATABASE_URL` | `NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE=1 python -m pytest -q tests/integration/test_pgvector_integration_smoke.py -m pgvector_integration` | documentos, chunks e embeddings do corpus fixture persistidos, `vector_semantic` retrieval com citacao oficial | `docker compose down`; reexecute o smoke quando mudar corpus, chunking, modelo ou dimensao |
| Real embedding model | `NVIDIA_STARTUP_INTEL_RUN_REAL_EMBEDDING_SMOKE=1` | `python -m pip install -e ".[embeddings,pgvector]"`; Postgres/pgvector ativo | `NVIDIA_STARTUP_INTEL_RUN_REAL_EMBEDDING_SMOKE=1 NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER=sentence-transformers PYTHONPATH=src python -m nvidia_startup_intel.pgvector_smoke` | metadata com provider, modelo, versao, dimensao, chunk count e fingerprint | Remova rows de embedding se trocar modelo/dimensao; suba novo indice antes do full smoke |
| Hybrid retrieval | `NVIDIA_STARTUP_INTEL_RUN_HYBRID_RETRIEVAL_SMOKE=1` | pgvector smoke ja persistiu o corpus; embedding client compatível configurado | `NVIDIA_STARTUP_INTEL_RUN_HYBRID_RETRIEVAL_SMOKE=1 PYTHONPATH=src python -m nvidia_startup_intel.production_smoke_matrix --only hybrid_retrieval` | `nvidia_knowledge.v1` com ranking `hybrid_bm25_vector`, scores BM25/vetoriais/hibridos e citacoes oficiais | Recrie embeddings quando corpus ou modelo mudar |
| Real reranking | `NVIDIA_STARTUP_INTEL_RUN_REAL_RERANKING_SMOKE=1` | `python -m pip install -e ".[reranking]"`; modelo local/cacheado ou baixavel pelo ambiente | `NVIDIA_STARTUP_INTEL_RUN_REAL_RERANKING_SMOKE=1 NVIDIA_STARTUP_INTEL_RERANKER_MODEL=<modelo> PYTHONPATH=src python -m nvidia_startup_intel.production_smoke_matrix --only reranking` | `nvidia_rerank.v1` preservando chunk, citacao, scores originais, rank original, score/rank/rationale de rerank | Limpe cache de modelo apenas se precisar liberar disco |
| LangGraph checkpoint | `NVIDIA_STARTUP_INTEL_RUN_LANGGRAPH_CHECKPOINT_SMOKE=1` | `python -m pip install -e ".[workflow]"`; Postgres ativo; `NVIDIA_STARTUP_INTEL_LANGGRAPH_CHECKPOINT_DATABASE_URL` ou `DATABASE_URL` | `NVIDIA_STARTUP_INTEL_RUN_LANGGRAPH_CHECKPOINT_SMOKE=1 python -m pytest -q tests/integration/test_intelligence_workflow_langgraph_checkpoint_smoke.py -m langgraph_checkpoint_integration` | checkpoints Postgres e workflow retomado sem repetir scraping | `docker compose down`; limpe tabelas de checkpoint se quiser repetir do zero |
| Groq/LiteLLM narrative | `NVIDIA_STARTUP_INTEL_RUN_LLM_ADAPTER_SMOKE=1` | `python -m pip install -e ".[llm]"`; `NVIDIA_STARTUP_INTEL_LLM_PROVIDER=litellm`; `NVIDIA_STARTUP_INTEL_LLM_MODEL`; `NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV`; chave real somente na variavel apontada | `NVIDIA_STARTUP_INTEL_RUN_LLM_ADAPTER_SMOKE=1 NVIDIA_STARTUP_INTEL_LLM_PROVIDER=litellm python -m pytest -q tests/integration/test_llm_adapter_integration_smoke.py -m llm_adapter_integration` | `LLMGenerationResponse` serializavel e `briefing_narrative.v1` derivado de briefing validado | Rotacione a chave se ela apareceu em conversa, terminal compartilhado ou arquivo |
| Full bounded operational smoke | `NVIDIA_STARTUP_INTEL_RUN_FULL_PRODUCTION_SMOKE=1` | Todos os servicos opcionais escolhidos configurados; uma URL publica ou query limitada | `NVIDIA_STARTUP_INTEL_RUN_FULL_PRODUCTION_SMOKE=1 PYTHONPATH=src python -m nvidia_startup_intel.production_smoke_matrix --only full_operational_smoke` | artefatos persistidos e briefing final ou Human Review Briefing | `rm -rf runs/production-smoke/<run_id>` para artefatos JSON locais; desligue Postgres quando terminar |

## Full Smoke Input

Configure exatamente uma entrada:

```bash
export NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_STARTUP_URL="https://startup-publica.example/"
# ou
export NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_QUERY="startups AI-native brasileiras em documentos"
```

Opcoes uteis:

```bash
export NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_STARTUP_NAME="Startup Publica"
export NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_LIMIT=1
export NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_MAX_PAGES=1
export NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_MAX_DEPTH=0
export NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_OUTPUT_DIR="runs/production-smoke"
export NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_PERSISTENCE_MODE="json-postgres"
export NVIDIA_STARTUP_INTEL_PRODUCTION_SMOKE_CORPUS_PATH="tests/fixtures/nvidia_knowledge_official_fixture.json"
```

Para query real, configure explicitamente o provedor de busca. Nao coloque a chave no comando:

```bash
export NVIDIA_STARTUP_INTEL_SEARCH_PROVIDER=brave
export BRAVE_SEARCH_API_KEY="<somente-no-ambiente-local>"
```

## Credential hygiene

A matriz nunca precisa receber valores de credenciais como argumento. Use somente variaveis de
ambiente locais. A saida da matriz sanitiza payloads e marca `credential_hygiene` como `failed`
se encontrar valores sensiveis em payloads, fixtures ou artefatos gerados, incluindo briefing.

Variaveis tratadas como sensiveis incluem nomes com `API_KEY`, `TOKEN`, `SECRET`, `PASSWORD`,
`DATABASE_URL` e a variavel apontada por `NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV`.

Nao commite:

- chaves de API;
- `DATABASE_URL` com senha real;
- artefatos em `runs/production-smoke/`;
- logs de provider;
- modelos baixados ou caches locais.

## Diagnostico De Falhas

Use o campo `bottleneck`:

- `collection`: browser, robots, politica de scraping, rede ou extracao HTML.
- `postgres`: conexao, schema, permissao ou persistencia relacional.
- `pgvector`: extensao `vector`, coluna de embedding ou consulta SQL vetorial.
- `embedding`: provider/modelo/dimensao/cache de embedding.
- `retrieval`: merge BM25 + vetor, corpus ou citacoes recuperadas.
- `reranking`: modelo cross-encoder, top K, preservacao de candidatos.
- `langgraph`: dependencia, checkpointer Postgres ou resume.
- `llm`: LiteLLM/Groq, credencial, provider, timeout ou resposta insegura.
- `briefing_quality`: falta de briefing final ou Human Review Briefing.
- `credential_hygiene`: valor sensivel apareceu em payload ou artefato.
