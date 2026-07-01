# case-NVIDIA-IA

Desenvolvido por **Leunam Sousa de Jesus**.

## O Que É Este Projeto

Este projeto é uma ferramenta de inteligência para apoiar o gerente de Startups & VCs da NVIDIA no Brasil a descobrir, qualificar e nutrir startups brasileiras com potencial para o programa NVIDIA Inception.

A pergunta principal do sistema é:

> Esta startup brasileira merece uma abordagem da NVIDIA agora? Se sim, por qual motivo, com quais evidências e qual tecnologia ou programa NVIDIA faz sentido?

O projeto não tenta apenas encontrar startups que dizem "usamos IA". Ele tenta separar startups com IA realmente central no produto e na stack daquelas que usam IA de forma superficial, por exemplo apenas como um wrapper de API de LLM.

## Ideia Central

A arquitetura é **evidence-first**:

- toda afirmação importante precisa apontar para evidências públicas;
- inferências precisam ser marcadas como inferências;
- recomendações precisam citar fontes oficiais NVIDIA;
- dados ausentes continuam como `unknown`;
- conflitos e incertezas aparecem no briefing, não são escondidos.

Isso é importante porque uma recomendação convincente, mas sem fonte, pode atrapalhar a priorização comercial e técnica.

## Regras De Negócio Em Linguagem Simples

- Uma `Startup Candidate` é uma empresa descoberta em fonte pública.
- Um `Startup Profile` é o perfil estruturado dessa startup, com evidências.
- Uma startup é `AI-Native` quando há evidência pública de que IA é central no produto e existe profundidade técnica suficiente.
- Uma startup é `AI-Enabled` quando usa IA, mas sem prova suficiente de centralidade ou profundidade.
- `Wrapper Risk` é o risco de a startup depender principalmente de APIs externas sem dados próprios, inferência em produção ou defensibilidade técnica.
- `Technical Gap` é um gargalo técnico que tecnologia NVIDIA pode ajudar a resolver.
- `Commercial Opportunity` é uma oportunidade de programa ou relacionamento, como Inception, parceiros, créditos, comunidade ou go-to-market.
- `AI-Native Assessment` gera apenas um `Opportunity Signal`, ou seja, um sinal preliminar.
- A prioridade final da oportunidade NVIDIA é calculada no módulo de `Recommendation`, depois de cruzar gaps ou oportunidades com fontes oficiais NVIDIA.
- Se houver baixo sinal, alto risco de wrapper, conflito ou falta de fonte oficial, o sistema deve gerar um `Human Review Briefing`, não uma recomendação final.
- O `Human Review Briefing` precisa trazer startup, área de atuação, o que foi descoberto, gargalos, riscos, conflitos, evidências e perguntas para validação humana.

## Fluxo Do Sistema

O fluxo planejado é:

```text
Discovery
-> Collection
-> Profile Extraction
-> Evidence Quality
-> AI-Native Assessment
-> NVIDIA Knowledge
-> Recommendation
-> Briefing
-> Human Review
```

Em termos práticos:

1. O sistema planeja buscas sobre startups brasileiras.
2. Encontra candidatas em fontes públicas.
3. Coleta páginas públicas respeitando política de scraping e robots.txt.
4. Extrai um perfil estruturado da startup.
5. Agrupa evidências e mede a qualidade da coleta.
6. Classifica maturidade AI-native e riscos.
7. Consulta uma base versionada de fontes oficiais NVIDIA.
8. Gera recomendações técnicas ou de programa.
9. Gera briefing executivo ou briefing para revisão humana.

## Status Atual

Já existe walking skeleton implementado para o fluxo upstream e downstream local:

- planejamento de busca;
- descoberta de candidatas;
- coleta real Playwright-first, com caminho determinístico local para testes e debug;
- extração HTML injetável com adapter opcional para trafilatura + BeautifulSoup;
- renderização Playwright como motor principal da CLI real, sem navegador real obrigatório na suíte default;
- política de scraping e robots.txt;
- extração de `StartupProfile` com schema `startup_profile.v1`;
- agrupamento de evidências;
- resumo de qualidade da coleta;
- avaliação AI-native determinística com schema `ai_native_assessment.v1`;
- gaps técnicos iniciais;
- riscos de wrapper/API-dependency;
- sinal preliminar de oportunidade;
- persistência JSON/SQL;
- runner local compatível com LangGraph;
- contrato local de `NVIDIA Knowledge` com corpus fixture oficial, taxonomia de stacks/programas, metadados obrigatórios e BM25 lexical;
- contrato de embeddings com fake determinístico, busca vetorial local e retrieval híbrido reprodutível;
- caminho opcional de persistência de embeddings em Postgres/pgvector, com schema e adapter SQL;
- contrato de adapter para retrieval framework-free e futuros retrievers como LlamaIndex;
- contrato de reranking top K, preservando chunk, citação, score original e rationale;
- adapters opcionais `LLMClient` para LiteLLM e LangChain, sem entrar no caminho padrão;
- `nvidia_recommendation.v1` para recomendação técnica citada, hipótese, bloqueio e métricas;
- recomendações de programa/Inception com gate por gap técnico ou oportunidade comercial específica;
- `executive_briefing.v1` determinístico para recommendation set suportado;
- `Human Review Briefing` versionado para baixo sinal, alto wrapper risk, conflito, unknowns ou falta de citação;
- workflow downstream local com branches auditáveis `ready_for_recommendation`, `ready_for_briefing`, `briefing_generated`, `human_review_requested` e `needs_more_collection_or_human_review`;
- workflow completo local conectando search, collection, profile extraction, evidence quality, assessment, NVIDIA retrieval, recommendation, briefing e persistence references por `run_id`;
- fundacao de frontend operacional em `frontend/`, com shell de workbench, navegacao por contexto, launcher/status de run, mock local e cliente do contrato `frontend_api_run.v1`;
- builder LangGraph opcional para o workflow completo, com checkpointer injetável para produção e smoke Postgres desligado por padrão;
- persistência downstream JSON/SQL de retrievals, recommendation sets e briefings por run e startup;
- métricas downstream para retrieval, recomendação, gaps sem recomendação, bloqueios e motivos de revisão humana;
- suíte local focada no downstream atual, sem rede, credenciais, Postgres real, LangGraph obrigatório ou provedores externos.

## Setup Local

Instalação base do projeto:

```bash
python -m pip install -e .
python -m playwright install chromium
```

Para desenvolvimento com validação local:

```bash
python -m pip install -e ".[dev]"
```

Scrapy e Firecrawl ficam em extras separados porque não são necessários para a suíte local padrão:

```bash
python -m pip install -e ".[scraping-scale]"
python -m pip install -e ".[scraping-services]"
```

Embeddings reais e Postgres/pgvector também ficam fora da instalação default:

```bash
python -m pip install -e ".[embeddings,pgvector]"
```

LangGraph e o checkpointer Postgres ficam em extra separado porque a suíte local padrão usa runners locais:

```bash
python -m pip install -e ".[workflow]"
```

## O Que Ainda Precisa De Validação Real

Sem considerar frontend, o backend já possui o fluxo completo local e os adapters de produção atrás de contratos. As pendências restantes não são ausência do core; são validação operacional e calibração com ambiente real:

1. Rodar a matriz opt-in com Playwright real, Postgres, pgvector, embedding real, reranking real, LangGraph checkpoint e Groq/LiteLLM.
2. Testar o scraping em startups brasileiras reais e revisar qualidade de evidência, taxa de `unknown`, conflitos e bloqueios por política/robots.
3. Calibrar gap-space assessment, thresholds de human review, top K, pesos híbridos e reranking com casos revisados por humano.
4. Manter o corpus oficial NVIDIA atualizado quando novas stacks, programas, fontes ou casos de uso entrarem no escopo.
5. Rodar o fluxo operacional completo com `run-intelligence` antes de demo: primeiro local determinístico, depois com integrações reais explicitamente habilitadas.

Depois dessas validações, a principal entrega restante de produto é evoluir o frontend para workflows revisados com casos reais, mantendo a fundacao atual conectada aos contratos auditaveis.

## Frameworks E Retrieval

- `LangGraph` é caminho opcional de orquestração com estado, branches, checkpoints, retries e human-in-the-loop; a validação padrão usa runners locais sem LangGraph instalado.
- `LangChain` pode entrar apenas dentro de adapters para LLMs, prompts, tools, structured output ou retrievers; objetos do framework não entram em schemas de domínio.
- `LiteLLM` pode entrar como gateway/adaptador para Grok, Groq, OpenRouter, Ollama ou outros modelos gratuitos/baratos, sempre atrás de `LLMClient`.
- `LlamaIndex` é candidato opcional para `NVIDIA Knowledge` quando ingestão, índices, busca vetorial/híbrida, citações ou reranking ficarem complexos demais para o adapter local.
- `Pydantic` pode validar novos schemas versionados quando houver benefício concreto.
- A busca NVIDIA já possui BM25 lexical, busca vetorial local e ranking híbrido reprodutíveis; reranking top K existe como contrato/adaptador determinístico e pode receber provider real depois.
- O vector DB preferido continua sendo Postgres local com `pgvector`, mas a integração real é opcional e não faz parte da suíte padrão.
- LLM gerador e modelo de embedding permanecem desacoplados. Real LLM, real embedding provider, LangGraph, LangChain, LiteLLM, LlamaIndex e Postgres real são caminhos de integração explícitos, não dependências default.

O guia operacional completo está em [Arquitetura de produção para scraping, retrieval, LangGraph e LLM](context/production-retrieval-and-scraping-architecture.md).

## Documentação Principal

- [Glossário de domínio](CONTEXT.md)
- [Modelo de domínio detalhado](context/domain-model.md)
- [Status do MVP de scraping](context/scraping-mvp-status.md)
- [Roadmap de hardening de scraping](context/roadmap-scraping-hardening.md)
- [Adapters de coleta](context/collection-adapters.md)
- [Arquitetura de produção para scraping, retrieval, LangGraph e LLM](context/production-retrieval-and-scraping-architecture.md)
- [Production Smoke Matrix](context/production-smoke-matrix.md)
- [Frontend Foundation](frontend/README.md)
- [ADRs](context/adr)

## Validação

A suíte antiga ampla de scraping/assessment foi removida por estar inválida para o escopo atual. Existe uma suíte local focada no downstream atual, sem rede, credenciais, Postgres real ou LangGraph obrigatório.

Depois do ajuste de import path em `pyproject.toml`, `pytest` encontra `src` pelo próprio projeto. O comando padrão não precisa de `PYTHONPATH` manual:

```bash
python -m pytest -q
python -m ruff check .
python -m mypy src
```

Ruff e mypy usam um baseline intencionalmente permissivo nesta primeira adoção de tooling. Ruff está limitado a erros de sintaxe/estilo críticos e Pyflakes; mypy roda sobre `src` com tolerância para imports ausentes, `strict_optional = false` e checagem de corpos não tipados. A baseline também adia categorias de erro de tipos já existentes, como `arg-type`, `assignment`, `attr-defined`, `call-overload`, `return-value` e `union-attr`. Aumentos de strictness devem entrar em fatias futuras, junto com ajustes de código específicos.

Os comandos estáticos pressupõem `ruff` e `mypy` instalados no ambiente Python usado para validação.

## Atualização Do Corpus NVIDIA

O snapshot local do corpus oficial NVIDIA usado pela suíte default fica em `tests/fixtures/nvidia_knowledge_official_fixture.json`. Ele é uma fixture auditável, não um crawler: Não busque páginas NVIDIA ao vivo na suíte default. Atualizações devem entrar como edição explícita do snapshot, com fontes oficiais revisadas e testes locais.

Cada documento do corpus precisa manter `schema_version`, `corpus_version`, `document_id`, `title`, `source_url`, `source_type`, `ingested_at` e metadados de taxonomia com `stack_id`, `stack_name`, `topic`, `brief_description`, `technical_description`, `categories`, `use_cases` e `supported_gap_types`. Cada item exposto por `nvidia_stack_profiles_from_corpus` também precisa resolver `citation_chunk_ids` para chunks reais do mesmo documento.

Ao editar chunks, preserve estabilidade: `chunk_id` deve seguir `document_id:chunk_index`, os índices de cada documento devem ser consecutivos a partir de zero, e IDs duplicados tornam o corpus inválido. Mude `corpus_version` sempre que alterar fontes, metadados de taxonomia, texto de chunks, chunking, cobertura de gap types ou qualquer conteúdo que possa afetar retrieval, recommendation, embeddings ou métricas. Mudanças puramente documentais fora do snapshot não exigem nova versão de corpus.

## CLI Controlada

Existe um entrypoint local para coletar páginas públicas de uma startup sem rodar busca, LLM, Postgres ou workflow completo:

```bash
PYTHONPATH=src python -m nvidia_startup_intel collect-pages https://startup.ai/ --max-pages 1 --max-depth 0
```

Por padrão, o comando respeita `robots.txt` em modo conservador, limita páginas/profundidade, usa renderização Playwright e extrai HTML com `trafilatura` + BeautifulSoup quando disponíveis, mantendo fallback local. O comando imprime JSON auditável em stdout. Para gravar arquivo:

```bash
PYTHONPATH=src python -m nvidia_startup_intel collect-pages https://startup.ai/ --max-pages 2 --output runs/startup-ai-collection.json
```

Para desativar Playwright no harness de debug/teste determinístico:

```bash
PYTHONPATH=src python -m nvidia_startup_intel collect-pages https://startup.ai/ --no-render-js --max-pages 1
```

## Coleta de Startup com Persistência Postgres

O caminho operacional para demonstrar uma coleta real de uma startup por URL, sem rodar o workflow de recomendação completo, usa o comando `collect-startup`. Ele coleta páginas públicas, extrai `StartupProfile`, estrutura evidências por campo, mede qualidade de coleta, salva artefatos JSON locais e persiste o run no Postgres local.

Suba o banco local:

```bash
docker compose up -d postgres
```

O serviço usa estas variáveis do `docker-compose.yml`, com defaults já definidos:

```bash
export POSTGRES_DB=nvidia_startup_intel
export POSTGRES_USER=nvidia_startup_intel
export POSTGRES_PASSWORD=nvidia_startup_intel
export POSTGRES_PORT=5432
```

Configure a conexão usada pela CLI. O driver `psycopg` precisa estar instalado no ambiente Python que roda o comando; no projeto, use o extra opcional `postgres`.

```bash
python -m pip install -e ".[postgres]"
export DATABASE_URL="postgresql://nvidia_startup_intel:nvidia_startup_intel@localhost:5432/nvidia_startup_intel"
```

Execute a coleta persistida:

```bash
PYTHONPATH=src python -m nvidia_startup_intel collect-startup https://startup.ai/ \
  --startup-name "Startup AI" \
  --max-pages 2 \
  --max-depth 1 \
  --output-dir runs
```

Por padrão, o comando respeita `robots.txt`, usa Playwright com extração `trafilatura` + BeautifulSoup quando disponíveis e grava um diretório `runs/<run_id>/` com `raw/collected_pages.json`, `processed/startup_profiles.json`, `processed/field_evidences.json` e `processed/collection_quality.json`. O mesmo `run_id` é salvo no Postgres com páginas coletadas, erros de coleta, perfil, evidências por campo e qualidade.

## Entrypoint Operacional Completo

O comando `run-intelligence` é a superfície operacional mínima para rodar o fluxo completo antes de existir uma UI. Ele aceita uma startup conhecida por URL ou uma query limitada, executa coleta, perfil, qualidade, assessment AI-native, retrieval NVIDIA, recomendação, briefing e persistência configurada, e imprime um payload final auditável com `run_id`, `startup_identifier`, `next_action`, referência de briefing, motivos de revisão humana, erros e locais dos artefatos.

Execução local segura por URL, sem LLM externo, embedding real, browser real ou Postgres real:

```bash
PYTHONPATH=src python -m nvidia_startup_intel run-intelligence \
  --startup-url https://startup.ai/ \
  --startup-name "Startup AI" \
  --max-pages 1 \
  --max-depth 0 \
  --output-dir runs \
  --persistence-mode json \
  --nvidia-corpus-path tests/fixtures/nvidia_knowledge_official_fixture.json
```

Execução por query limitada exige um `SearchClient` real configurado explicitamente:

```bash
export BRAVE_SEARCH_API_KEY="<sua-chave-local>"
PYTHONPATH=src python -m nvidia_startup_intel run-intelligence \
  --query "startups AI-native brasileiras em documentos" \
  --limit 1 \
  --max-pages 1 \
  --enable-search-provider \
  --nvidia-corpus-path tests/fixtures/nvidia_knowledge_official_fixture.json
```

Defaults seguros:

- `--persistence-mode json` grava artefatos locais em `runs/<run_id>/`.
- Playwright real fica desligado até usar `--enable-playwright`.
- Postgres real fica desligado até usar `--persistence-mode postgres` ou `json-postgres`.
- pgvector fica desligado até usar `--retrieval-mode pgvector` com `DATABASE_URL` ou `NVIDIA_STARTUP_INTEL_PGVECTOR_DATABASE_URL` e embedding real configurado por `NVIDIA_STARTUP_INTEL_EMBEDDING_*`.
- LangGraph fica desligado até usar `--orchestration langgraph`.
- Reranking real fica desligado até usar `--retrieval-mode pgvector --enable-reranking --reranker-model <modelo>`.
- Groq/LiteLLM fica desligado até usar `--enable-groq-narrative` com `NVIDIA_STARTUP_INTEL_LLM_*` e a chave somente em variável de ambiente.

O payload final representa erros como dados estruturados. Quando uma etapa falha depois de criar o run, os artefatos parciais já gravados continuam no diretório de execução ou no Postgres configurado para auditoria e reprocessamento.

## Frontend API Opcional

A API de frontend é um backend-for-frontend fino sobre o mesmo contrato usado por `run-intelligence`. Ela não contém regras de domínio novas: parsing, coleta, assessment, retrieval, recomendação, briefing, human review e persistência continuam nos módulos existentes. A API apenas recebe JSON, chama `run_operational_intelligence` e devolve payloads versionados para a futura UI.

FastAPI e Uvicorn ficam fora da instalação padrão. Para habilitar a API:

```bash
python -m pip install -e ".[api]"
```

Execute o servidor local:

```bash
nvidia-startup-intel-api --host 127.0.0.1 --port 8000
```

Também é possível usar o factory ASGI diretamente:

```bash
uvicorn "nvidia_startup_intel.frontend_api:create_app" --factory --host 127.0.0.1 --port 8000
```

Endpoints expostos:

- `POST /api/runs`: inicia uma execução operacional determinística local por `startup_url` ou `query` limitada. Aceita opções equivalentes ao `run-intelligence` quando aplicáveis, como `startup_name`, `limit`, `max_pages`, `max_depth`, `output_dir`, `persistence_mode`, `nvidia_corpus_path`, `render_js`, `robots_policy`, `retrieval_mode`, `orchestration`, `enable_search_provider`, `enable_reranking`, `reranker_model` e `llm_narrative`.
- `GET /api/runs/{run_id}`: retorna o status do run, payload final, referências de artefatos, erros, `next_action`, referência de briefing e motivos de revisão humana.
- `GET /api/production-smoke-matrix`: retorna uma visão read-only da matriz opt-in de smokes de produção para a UI exibir prontidão de integrações. Use `?only=postgres_persistence,pgvector_retrieval` para limitar integrações.
- `GET /health`: healthcheck simples do transporte.

Exemplo seguro por URL, sem browser real, Postgres real, rede externa, LLM real ou embedding real:

```bash
curl -s http://127.0.0.1:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "startup_url": "https://startup.ai/",
    "startup_name": "Startup AI",
    "max_pages": 1,
    "max_depth": 0,
    "output_dir": "runs",
    "persistence_mode": "json",
    "nvidia_corpus_path": "tests/fixtures/nvidia_knowledge_official_fixture.json"
  }'
```

O response usa `frontend_api_run.v1` e inclui `status`, `workflow_outcome`, `run_id`, `startup_identifier`, `next_action`, `briefing_reference`, `human_review_reasons`, `artifact_references`, `errors`, `options` e o `final_payload` operacional original. Erros auditáveis do workflow são retornados como dados estruturados, não como objetos de framework ou SDK de provider.

## Frontend App

A fundacao de UI fica em `frontend/` e carrega um workbench operacional, nao uma landing page. A primeira tela traz navegacao para `Runs`, `Evidence`, `Assessment`, `NVIDIA Match`, `Briefing` e `Production Smokes`, com launcher/status de run e estados vazios baseados no contrato da API.

Comandos principais:

```bash
npm --prefix frontend run dev
npm --prefix frontend run build
npm --prefix frontend test
```

Por padrao, a UI usa mock mode local sem rede. Para conectar no backend opcional, suba `nvidia-startup-intel-api --host 127.0.0.1 --port 8000` e abra:

```text
http://127.0.0.1:5173?api=real&baseUrl=http://127.0.0.1:8000
```

O contrato tipado fica em `frontend/src/api-contract.js`; dados ausentes no payload continuam como estados vazios na UI.

Para validar o caminho operacional completo de persistência Postgres com fixture local, rode o smoke opt-in. Ele aplica o schema via repositório, persiste coleta, perfil, evidências, qualidade, AI-Native Assessment, retrievals NVIDIA, Recommendation Set, briefing e métricas downstream, e valida que os artifacts podem ser recarregados para reprocessamento quando o `corpus_version` bate.

```bash
docker compose up -d postgres
NVIDIA_STARTUP_INTEL_RUN_POSTGRES_PERSISTENCE_SMOKE=1 \
PYTHONPATH=src python -m nvidia_startup_intel.postgres_persistence_smoke
```

Esse smoke exige `psycopg` apenas no ambiente usado para validação opcional. A suíte default continua usando SQLite/fakes e não depende de Postgres real, rede, credenciais, LangGraph, LLM ou embedding real.

## Validação Opcional LLM Adapters

LiteLLM e LangChain não fazem parte da suíte local padrão. A validação default continua usando fakes e contract tests, sem rede, credenciais, chamadas reais de LLM, LiteLLM ou LangChain instalados.

Os adapters opcionais ficam atrás do contrato `LLMClient` em `llm_adapters.py`. Para validar uma integração real com LiteLLM, instale a dependência no ambiente local e configure explicitamente o provider por variáveis de ambiente:

```bash
python -m pip install -e ".[llm]"
```

```bash
export NVIDIA_STARTUP_INTEL_LLM_PROVIDER=litellm
export NVIDIA_STARTUP_INTEL_LLM_MODEL=groq/<modelo-disponivel-na-sua-conta>
export NVIDIA_STARTUP_INTEL_LLM_MODEL_VERSION=<model-version>
export NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV=GROQ_API_KEY
export GROQ_API_KEY=<secret>
```

`NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV` guarda apenas o nome da variável que contém a credencial; a credencial não deve entrar em código, fixtures, logs, prompts ou payloads persistidos. Se uma chave tiver sido exposta em conversa, issue, terminal compartilhado ou arquivo versionado, rotacione a chave no provedor antes de reutilizá-la. O workflow downstream pode usar esse adapter para gerar `briefing_narrative.v1` com narrativas separadas de gap técnico e abordagem comercial, sempre derivadas dos artefatos validados e com fallback determinístico quando a resposta do LLM não for segura. Configurações opcionais aceitas pelo adapter incluem `NVIDIA_STARTUP_INTEL_LLM_API_BASE`, `NVIDIA_STARTUP_INTEL_LLM_TIMEOUT_SECONDS`, `NVIDIA_STARTUP_INTEL_LLM_TEMPERATURE` e `NVIDIA_STARTUP_INTEL_LLM_MAX_TOKENS`.

Para LangChain, configure `NVIDIA_STARTUP_INTEL_LLM_PROVIDER=langchain` e passe um chat model já instanciado para `LangChainLLMClient`. Objetos LiteLLM ou LangChain devem ser convertidos para `LLMGenerationResponse` antes de qualquer Recommendation, Briefing, workflow state ou payload de persistência.

Também existe um smoke test opcional isolado para validar essas fronteiras fora da suíte default:

```bash
NVIDIA_STARTUP_INTEL_RUN_LLM_ADAPTER_SMOKE=1 \
python -m pytest -q tests/integration/test_llm_adapter_integration_smoke.py -m llm_adapter_integration
```

Com `NVIDIA_STARTUP_INTEL_LLM_PROVIDER=litellm`, o smoke usa a configuração real do LiteLLM e exige que a dependência e a credencial apontada por `NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV` estejam disponíveis no ambiente. Com `NVIDIA_STARTUP_INTEL_LLM_PROVIDER=langchain`, o smoke valida um chat model localmente fornecido pelo próprio teste, sem credencial externa. Em ambos os casos, o teste afirma que a saída cruza a fronteira como `LLMGenerationResponse` serializável, não como objeto de provider.

## Validação Opcional Playwright Collection

Playwright real não faz parte da suíte local padrão. A coleta de produção é Playwright-first com extração `trafilatura` + BeautifulSoup quando disponíveis, mas a validação default continua usando fakes, fixtures e o harness determinístico de teste/debug.

Para validar o browser instalado sem depender de rede, rode o smoke direto. Sem URL, ele cria uma página HTML temporária local, renderiza com Chromium via Playwright e retorna o `PageCollectionResult` versionado:

```bash
PYTHONPATH=src python -m nvidia_startup_intel.playwright_collection_smoke
```

Para validar uma URL pública real de forma opt-in:

```bash
PYTHONPATH=src python -m nvidia_startup_intel.playwright_collection_smoke https://startup.ai/
```

Também existe um teste de integração isolado, fora da suíte default:

```bash
NVIDIA_STARTUP_INTEL_RUN_PLAYWRIGHT_COLLECTION_SMOKE=1 \
python -m pytest -q tests/integration/test_playwright_collection_integration_smoke.py -m playwright_collection_integration
```

Esse caminho exige `playwright` e os browser binaries instalados com `python -m playwright install chromium`. Falhas são reportadas como `OPTIONAL PLAYWRIGHT COLLECTION SMOKE FAILED` para separar problema de ambiente real da suíte determinística local.

## Validação Opcional Production Scraping

A issue de scraping de produção usa um smoke opt-in para medir se o caminho Playwright-first atual encontra evidência pública suficiente em uma lista pequena de startups brasileiras antes de adicionar Firecrawl, Scrapy ou outros serviços externos.

Execute contra URLs públicas controladas e grave o JSON em `runs/production-scraping/`, que fica fora das fixtures versionadas:

```bash
mkdir -p runs/production-scraping
PYTHONPATH=src python -m nvidia_startup_intel.production_scraping_smoke \
  https://startup-brasileira.example/ \
  https://outra-startup.example/ \
  --max-pages 2 \
  --max-depth 1 \
  --output runs/production-scraping/smoke-$(date -u +%Y%m%dT%H%M%SZ).json
```

O payload retorna `production_scraping_validation.v1` com `run_id`, estratégia de coleta, decisão de política, decisão de `robots.txt`, limites de crawl, erros auditáveis, tempo decorrido, tamanho de texto por página, páginas vazias ou com pouco texto, completude do `startup_profile.v1`, taxa de `unknown`, conflitos e prontidão para AI-Native Assessment.

Também existe um teste de integração isolado, desabilitado por padrão:

```bash
NVIDIA_STARTUP_INTEL_RUN_PRODUCTION_SCRAPING_SMOKE=1 \
NVIDIA_STARTUP_INTEL_PRODUCTION_SCRAPING_URLS="https://startup-brasileira.example/,https://outra-startup.example/" \
python -m pytest -q tests/integration/test_production_scraping_integration_smoke.py -m production_scraping_integration
```

Esse caminho pode usar rede e navegador real apenas quando explicitamente habilitado. Não use URLs privadas, autenticadas, paywalled ou protegidas por login; bloqueios de política, `robots.txt`, browser, rede e extração devem aparecer como dados auditáveis no relatório, não como fixtures commitadas.

## Validação Opcional LangGraph Checkpoint

LangGraph e `langgraph-checkpoint-postgres` não fazem parte da suíte local padrão. O workflow completo possui runner local determinístico e builder LangGraph opcional; o checkpointer é injetado apenas em produção ou smoke opt-in.

Instale o extra opcional e suba o Postgres local antes do smoke:

```bash
python -m pip install -e ".[workflow]"
docker compose up -d postgres
```

Configure a conexão do checkpointer sem commitar credenciais:

```bash
export NVIDIA_STARTUP_INTEL_LANGGRAPH_CHECKPOINT_DATABASE_URL="$DATABASE_URL"
```

Rode o smoke explicitamente:

```bash
NVIDIA_STARTUP_INTEL_RUN_LANGGRAPH_CHECKPOINT_SMOKE=1 \
python -m pytest -q tests/integration/test_intelligence_workflow_langgraph_checkpoint_smoke.py -m langgraph_checkpoint_integration
```

O smoke compila `build_intelligence_langgraph` com checkpointer Postgres e valida o caminho de resume downstream a partir de artefatos upstream já carregados, sem repetir scraping. Sem a variável `NVIDIA_STARTUP_INTEL_RUN_LANGGRAPH_CHECKPOINT_SMOKE=1`, o teste fica pulado.

## Validação Opcional Pgvector

A persistência de embeddings em Postgres/pgvector é um caminho de integração, não uma dependência da suíte local padrão. Para validar quando Docker e Postgres estiverem disponíveis:

```bash
docker compose up -d postgres
PYTHONPATH=src python -m nvidia_startup_intel.pgvector_smoke
```

Esse comando usa o `DeterministicFakeEmbeddingClient` por padrão para validar pgvector sem download de modelo. Para validar o caminho real com `sentence-transformers`, instale os extras opcionais e configure explicitamente o provider e o modelo:

```bash
python -m pip install -e ".[embeddings,pgvector]"
export NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER=sentence-transformers
export NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL=intfloat/multilingual-e5-base
export NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL_VERSION=local-or-pinned-snapshot
docker compose up -d postgres
PYTHONPATH=src python -m nvidia_startup_intel.pgvector_smoke
```

`NVIDIA_STARTUP_INTEL_EMBEDDING_MODEL` pode apontar para um modelo gratuito baixável pelo `sentence-transformers` ou para um caminho local já cacheado. O smoke aplica o schema do projeto em `db/schema.sql`, valida `CREATE EXTENSION IF NOT EXISTS vector`, persiste o corpus oficial fixture com embeddings e metadados, e recupera NVIDIA Knowledge por similaridade vetorial SQL usando `PgvectorNVIDIAEmbeddingStore`.

O índice de embeddings registra `corpus_version`, `chunk_count`, `chunking_fingerprint`, provider, modelo, versão do embedding, dimensão e parâmetros do índice. Rebuild é obrigatório quando corpus, chunking, modelo, versão, dimensão ou parâmetros mudarem; a fingerprint existe para deixar essa decisão auditável mesmo antes de consultar o pgvector.

Também existe um teste de integração isolado, fora da suíte default:

```bash
docker compose up -d postgres
NVIDIA_STARTUP_INTEL_RUN_PGVECTOR_SMOKE=1 python -m pytest -q tests/integration/test_pgvector_integration_smoke.py -m pgvector_integration
```

O smoke requer `psycopg` apenas no ambiente usado para essa validação opcional; o embedding real requer `sentence-transformers` apenas quando `NVIDIA_STARTUP_INTEL_EMBEDDING_PROVIDER` estiver configurado. Por padrão, `DATABASE_URL` ou `NVIDIA_STARTUP_INTEL_PGVECTOR_DATABASE_URL` podem apontar para outro Postgres/pgvector. Sem configuração explícita, o smoke usa as credenciais do `docker-compose.yml`. Falhas desse caminho são reportadas como `OPTIONAL PGVECTOR SMOKE FAILED` para não parecerem falhas da suíte local padrão.

O schema em `db/schema.sql` cria `CREATE EXTENSION IF NOT EXISTS vector`, persiste documentos, chunks e embeddings auditáveis, e usa busca exata por similaridade SQL. Índices HNSW/IVFFlat continuam fora até haver volume ou latência medidos que justifiquem a troca.

## Validação Opcional Reranking

Reranking real não faz parte da suíte local padrão. A suíte default valida o contrato `NVIDIAReranker` com fake determinístico ou cross-encoder injetado em memória, sem download de modelo, rede, credenciais ou provider externo.

Para validar um cross-encoder local real, instale o extra opcional e use `SentenceTransformersCrossEncoderReranker` somente depois que o retrieval híbrido BM25 + vetorial produzir o `candidate_top_k`:

```bash
python -m pip install -e ".[reranking]"
```

O reranker pode apenas reordenar ou descartar os chunks recebidos. Ele não pode criar novos chunks, citações, scores originais, claims sobre startup ou fatos NVIDIA. O payload `nvidia_rerank.v1` preserva rank original, scores BM25/vetorial/híbrido, citação oficial, score/rank/rationale de reranking, nome do modelo, versão do modelo e parâmetros usados.

O reranking real só deve ser habilitado para produção quando `compare_rerank_retrieval_quality` demonstrar ganho no top 1 sem regressão nas métricas de suporte: `top_1_expected_delta >= 1`, `f1_delta >= 0.0`, `recall_delta >= 0.0`, `precision_delta >= 0.0` e `coverage_delta >= 0.0` nos fixtures ou casos reais revisados. Se o ganho vier apenas de uma fixture frágil, mantenha o reranker como experimento opt-in e amplie as expectations antes de mudar o caminho padrão.
