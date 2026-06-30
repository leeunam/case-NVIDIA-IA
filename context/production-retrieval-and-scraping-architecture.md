# Arquitetura de Producao: Scraping, Retrieval, LangGraph e LLM

Este documento mapeia a passagem do core deterministico atual para uma arquitetura robusta de producao. Ele nao substitui os contratos existentes; ele define quais adapters entram quando a validacao sair do modo local/fake.

## Decisao Principal

Nao substituir o core deterministico por frameworks.

O core atual continua sendo a fonte auditavel de regra de negocio:

```text
Discovery
-> Collection
-> Profile Extraction
-> Evidence Quality
-> AI-Native Assessment
-> NVIDIA Knowledge
-> Recommendation
-> Briefing / Human Review
```

Frameworks entram nas bordas:

```text
contratos de dominio
-> adapters de scraping/retrieval/LLM/embedding/reranking
-> LangGraph para orquestracao e checkpoints
-> Postgres/pgvector para persistencia e busca vetorial
```

Essa separacao preserva a suite local sem rede, credenciais, Postgres real, navegador real ou LLM real, enquanto permite um caminho de producao funcional.

## Mapa: Atual Deterministico Para Producao

| Contexto | Atual deterministico | Limite de escala | Adapter/framework de producao | Contrato que nao deve mudar |
| --- | --- | --- | --- | --- |
| Search | `SearchClient`, Brave opcional, fakes em teste | um provedor, pouca estrategia de fallback | Brave, Firecrawl Search ou outro `SearchClient` com retry/rate limit | `RawDiscoveryResult` e erros auditaveis |
| Collection | `urllib` + `html.parser` como harness local | perde JS, texto ruidoso, pouca extracao principal | Playwright-first + `trafilatura` + `BeautifulSoup`; Firecrawl como adapter externo; Scrapy para escala | `CollectedPage` e `PageCollectionResult` |
| Profile Extraction | regras deterministicas | pode perder dados nao estruturados | manter deterministico; LLM so como proposta revisavel atras de contrato futuro | `StartupProfile` com evidencia por campo |
| Evidence Quality | metricas locais | precisa comparar estrategias de coleta | metricas por estrategia e reprocessamento sem nova coleta | `CollectionQualitySummary` |
| NVIDIA BM25 | BM25 proprio/local | manutencao e otimizacao limitadas | `rank_bm25.BM25Okapi` ou `langchain_community.retrievers.BM25Retriever` atras de adapter | `NVIDIAKnowledgeRetrieval` |
| Vetorial | fake embedding e busca local exata | nao representa embedding real, nao escala | `sentence-transformers`/FastEmbed para embeddings; pgvector para persistencia; FAISS apenas local/benchmark | `EmbeddingClient`, metadata de modelo e corpus |
| Hibrido | merge/RRF local | pouca interoperabilidade | `EnsembleRetriever` ou RRF proprio atras de adapter, pesos versionados | scores originais, ranking_strategy e citacoes |
| Reranking | reranker deterministico top K | baixa qualidade sem semantica real | cross-encoder local/free; LLM-as-reranker so opcional e medido | `NVIDIARerankResult` preservando chunk/citacao |
| Workflow | runner local completo e builder LangGraph opcional com checkpointer injetavel | smoke real de checkpoint/human-in-loop ainda opt-in | LangGraph compilado com Postgres checkpointer | estado explicito e branches auditaveis |
| LLM | `LLMClient`, LiteLLM/LangChain opcionais | sem chamada real no caminho default | LiteLLM com Groq via env; LangChain para chat model/tools quando necessario | `LLMGenerationRequest/Response` |
| Persistencia | JSON/SQL local, pgvector opcional | reprocessamento e auditabilidade maiores | Postgres Docker + `pgvector` + checkpoints LangGraph | run_id, schema_version e payloads auditaveis |

## Scraping Robusto

A coleta real deve virar uma cadeia de estrategias robusta, mantendo o caminho deterministico apenas para teste/debug:

```text
1. policy/robots antes de qualquer coleta
2. Playwright para renderizar a pagina publica em modo controlado
3. trafilatura para texto principal sobre HTML renderizado
4. BeautifulSoup para links, titulo, metadados e fallback HTML
5. detector needs_js_rendering como qualidade/diagnostico, nao como gate principal da CLI real
6. Firecrawl apenas como adapter externo opcional
7. Scrapy apenas para crawling em volume e multiplas fontes
```

Uso esperado por ferramenta:

- `trafilatura`: extrair texto principal, metadata e reduzir ruido de menu/rodape/noticias/blogs.
- `BeautifulSoup`: navegar HTML, extrair links, titulo, metatags e fallback quando `trafilatura` falhar.
- `Playwright`: renderizar paginas publicas como motor principal da coleta real.
- `Firecrawl`: servico externo opcional para markdown/JSON limpo quando coleta local falhar; nunca entra na suite default.
- `Scrapy`: crawling estruturado em escala, com politicas, filas, item pipelines e throttling; nao deve substituir os contratos de dominio.

Regras:

- Nao usar scraping autenticado, paywall, login ou bypass de protecao.
- Respeitar robots.txt, rate limit, bloqueios manuais e erros auditaveis.
- Cada estrategia deve registrar `collection_strategy`, `extraction_strategy`, tempo, erro e motivo de fallback.
- Testes default usam fixtures/fakes; Playwright real, Firecrawl e Scrapy real entram em smoke/integration tests opt-in.

## Retrieval NVIDIA Robusto

### BM25

A implementacao atual pode ser substituida por um adapter usando `rank_bm25` ou LangChain BM25.

Opcao core simples:

```python
from rank_bm25 import BM25Okapi

tokenized_chunks = [tokenize(chunk.text) for chunk in chunks]
bm25 = BM25Okapi(tokenized_chunks)
scores = bm25.get_scores(tokenize(query))
```

Opcao LangChain:

```python
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

docs = [
    Document(
        page_content=chunk.text,
        metadata={
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "corpus_version": corpus.corpus_version,
        },
    )
    for chunk in corpus.chunks
]
bm25 = BM25Retriever.from_documents(docs, k=top_k_lexical)
```

Preferencia:

- `rank_bm25` se o objetivo for controle simples, score explicito e menos acoplamento.
- `BM25Retriever` se o objetivo for compor com LangChain retrievers e `EnsembleRetriever`.

Em ambos os casos, a saida precisa voltar para `NVIDIAKnowledgeRetrieval`, nao para `Document` do LangChain.

### Busca Vetorial

O LLM de geracao e o embedding nao precisam ser do mesmo fornecedor. Groq e bom candidato para LLM gratuito/rapido, mas nao deve determinar o embedding.

Embeddings gratuitos/local-first recomendados para avaliar:

- `intfloat/multilingual-e5-base` ou familia E5 para portugues/ingles.
- `BAAI/bge-m3` quando houver necessidade multilingue e de retrieval tecnico mais forte.
- `sentence-transformers` como biblioteca inicial para rodar localmente.
- FastEmbed como alternativa leve se instalacao/performance de `sentence-transformers` pesar.

Regras de vetor:

- registrar `embedding_provider`, `embedding_model`, `embedding_version`, dimensao, idioma esperado, `corpus_version` e parametros do indice;
- registrar tambem `chunk_count` e `chunking_fingerprint` para tornar o rebuild por chunking auditavel;
- qualquer troca de modelo, chunking, corpus, dimensao ou parametros do indice exige rebuild;
- embeddings recuperam candidatos, nao criam fatos;
- citacoes oficiais continuam obrigatorias para recomendacao.

### Vector Store

Como o projeto ja usa Postgres Docker com `pgvector`, a fonte persistente preferida deve ser Postgres/pgvector.

Use FAISS apenas para:

- experimento local em memoria;
- benchmark de recall/latencia;
- fallback quando Postgres nao estiver disponivel.

Nao use FAISS como fonte auditavel principal se o objetivo e guardar runs, chunks, embeddings, recomendacoes e briefings no mesmo banco.

### Hibrido

Arquitetura equivalente ao exemplo com `EnsembleRetriever`:

```python
from langchain.retrievers import EnsembleRetriever

hybrid = EnsembleRetriever(
    retrievers=[bm25_retriever, vector_retriever],
    weights=[0.4, 0.6],
)
documents = hybrid.invoke(query)
```

No projeto, isso deve ficar atras de um adapter:

```text
NVIDIAHybridRetrieverAdapter
-> monta Document com metadata auditavel
-> chama BM25 + vector retriever
-> aplica pesos versionados
-> converte Document de volta para RetrievedNVIDIAKnowledge
```

Pesos iniciais sugeridos:

- `0.5 BM25 / 0.5 vector` como baseline;
- `0.6 BM25 / 0.4 vector` se nomes de tecnologias NVIDIA e siglas forem decisivos;
- `0.4 BM25 / 0.6 vector` se queries em portugues nao casarem bem com docs oficiais em ingles.

Os pesos so devem mudar com metricas.

### Reranking

Reranking deve acontecer depois do merge hibrido:

```text
top_k_lexical=20
+ top_k_vector=20
-> merge/dedupe
-> candidate_top_k=30
-> reranker
-> final_top_k=5
```

Opcoes:

- cross-encoder local via `sentence-transformers`, preferencial para auditabilidade/custo;
- reranker BGE ou mMARCO se a qualidade multilingue for melhor nos fixtures;
- LLM-as-reranker via Groq apenas como experimento opt-in, com custo, latencia e estabilidade medidos.

O reranker so pode reordenar ou descartar chunks. Ele nao pode gerar novas afirmacoes.

O reranking real permanece opt-in ate que fixtures ou casos reais revisados mostrem melhoria
mensuravel sobre o retrieval hibrido sem regressao de suporte. O limiar minimo para promover o
caminho real e `top_1_expected_delta >= 1`, com `f1_delta >= 0.0`, `recall_delta >= 0.0`,
`precision_delta >= 0.0` e `coverage_delta >= 0.0` em `compare_rerank_retrieval_quality`.
Se a melhoria aparecer apenas em uma expectation estreita, mantenha o reranker como experimento
e amplie os casos antes de alterar o caminho padrao.

## Metricas Obrigatorias

O projeto ja mede recall, precision e F1 em fixtures locais. O proximo passo e ampliar expectations por etapa, casos reais revisados e comparacao entre estrategias.

Metricas minimas:

- `recall@k`: quantos chunks/citacoes esperados apareceram no top K;
- `precision@k`: quantos itens recuperados no top K eram esperados/uteis;
- `f1@k`: media harmonica entre precision@k e recall@k;
- `coverage`: quantos casos de expectativa foram cobertos;
- `mrr` opcional: posicao do primeiro chunk correto;
- `ndcg@k` opcional: qualidade de ordenacao quando houver relevancia graduada;
- `official_citation_rate`: recomendacoes com citacao oficial NVIDIA;
- `unsupported_recommendation_rate`: recomendacoes bloqueadas ou hipoteticas;
- `human_review_rate`: taxa de briefing enviado para revisao humana;
- `latency_ms` e `cost_estimate` em adapters externos.

Avaliar separadamente:

```text
BM25 only
Vector only
Hybrid BM25+Vector
Hybrid + Reranker
```

Uma troca de framework so deve ser aceita se melhorar recall/precision/F1 ou reduzir latencia/custo sem quebrar rastreabilidade.

## LangGraph Real Funcional

O grafo de producao deve conectar o fluxo completo, mantendo regra de negocio fora dos nos:

```text
plan_search
-> execute_search
-> discover_candidates
-> collect_pages
-> extract_profiles
-> structure_evidence
-> measure_quality
-> assess_ai_native
-> retrieve_nvidia_knowledge
-> rerank_retrieval
-> build_recommendations
-> generate_briefing
-> persist_artifacts
-> human_review_or_done
```

LangGraph deve cuidar de:

- estado por `run_id`;
- branches;
- retries de adapters externos;
- checkpoints;
- human-in-the-loop;
- streaming/observabilidade quando necessario.

Postgres deve cuidar de:

- runs e artefatos;
- chunks e embeddings;
- retrievals/recommendations/briefings;
- checkpoints LangGraph em producao, usando `langgraph-checkpoint-postgres` quando a dependencia entrar.

## LLM Real Com Groq

A chave nunca deve ser commitada. Use apenas variaveis de ambiente:

```bash
export NVIDIA_STARTUP_INTEL_LLM_PROVIDER=litellm
export NVIDIA_STARTUP_INTEL_LLM_MODEL=groq/<modelo-disponivel-na-sua-conta>
export NVIDIA_STARTUP_INTEL_LLM_MODEL_VERSION=<versao-ou-data>
export NVIDIA_STARTUP_INTEL_LLM_API_KEY_ENV=GROQ_API_KEY
export GROQ_API_KEY=<sua-chave-local>
```

O adapter atual ja registra o nome da variavel da credencial, nao o valor. O valor da chave nao deve aparecer em:

- codigo;
- fixtures;
- payload persistido;
- logs;
- commit;
- PR;
- briefing.

Como a chave foi compartilhada em texto, trate-a como exposta e rotacione no provedor antes de uso continuo.

## Dependencias Por Grupo

Dependencias declaradas ou previstas por grupo:

```text
[base scraping]
beautifulsoup4
trafilatura
playwright

[scraping-scale]
scrapy

[scraping-services]
firecrawl-py

[retrieval]
rank-bm25
langchain
langchain-community
sentence-transformers
faiss-cpu
pgvector
psycopg[binary,pool]

[workflow]
langgraph
langgraph-checkpoint-postgres

[llm]
litellm
langchain
langchain-groq ou LiteLLM via Groq

[evaluation]
scikit-learn
```

Nem todas devem ir para a instalacao default. A instalacao default deve continuar leve e deterministica.

## Ordem Recomendada De Implementacao

1. Ampliar expectations em `downstream_metrics.py` para mais gaps, programas e casos reais revisados.
2. Criar adapter BM25 com `rank_bm25`, mantendo fixture local e contrato atual.
3. Criar adapter LangChain BM25/EnsembleRetriever em paralelo, atras do mesmo contrato.
4. Criar embedding client real local com `sentence-transformers`.
5. Persistir embeddings reais em Postgres/pgvector e validar smoke opt-in.
6. Comparar BM25, vector e hybrid em precision/recall/F1.
7. Adicionar reranker cross-encoder opt-in e medir ganho no top K.
8. Validar smoke real da CLI Playwright-first com browser instalado.
9. Medir ganho de `trafilatura` + `BeautifulSoup` em páginas reais brasileiras.
10. Executar e calibrar smoke operacional do LangGraph completo com checkpoint Postgres.
11. Conectar LiteLLM/Groq somente para narrativa ou etapas explicitamente LLM-safe.
12. Avaliar Firecrawl/Scrapy apenas quando houver volume/falha medida que justifique.

## Pontos Que Eu Contestaria

- Nao use Firecrawl como default se o requisito e validacao sem servico externo. Ele e bom adapter de producao, mas deve ser opt-in.
- Nao troque Postgres/pgvector por FAISS como armazenamento principal. FAISS e util para benchmark local; Postgres e melhor para auditoria neste projeto.
- Nao deixe LangChain ou LlamaIndex virarem contrato de dominio. Eles podem compor retrievers, mas a saida precisa voltar aos schemas do projeto.
- Nao use Groq para classificar fatos de startup ou tecnologia NVIDIA sem evidencia. Groq pode gerar narrativa, resumir briefing e talvez reranquear, mas nao deve inventar dados.
- Nao deixe Scrapy ou Firecrawl virarem caminho obrigatorio da suite local. Eles devem provar ganho em escala ou extração externa antes de entrarem no fluxo padrão.

## Referencias Externas

- rank-bm25: https://pypi.org/project/rank-bm25/
- LangChain BM25Retriever: https://docs.langchain.com/oss/python/integrations/retrievers/bm25
- LangChain FAISS: https://docs.langchain.com/oss/python/integrations/vectorstores/faiss
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph Postgres checkpoint: https://docs.langchain.com/oss/python/langgraph/add-memory
- LiteLLM Groq provider: https://docs.litellm.ai/docs/providers/groq
- Playwright Python: https://playwright.dev/python/docs/intro
- Beautiful Soup: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- Scrapy: https://docs.scrapy.org/en/latest/intro/overview.html
- trafilatura: https://trafilatura.readthedocs.io/en/latest/
- Firecrawl: https://docs.firecrawl.dev/introduction
