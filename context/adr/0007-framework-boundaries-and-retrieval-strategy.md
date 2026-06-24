# ADR 0007: Limites de Frameworks de IA e Estratégia de Retrieval

Status: aceito

## Contexto

O projeto vai combinar workflow multi-etapa, RAG sobre documentação oficial NVIDIA, possível geração por LLM e briefing para decisão humana. Há risco de introduzir LangGraph, LangChain, LlamaIndex, embeddings, vector DB e rerankers de forma sobreposta, espalhando regra de negócio entre prompts, agentes e bibliotecas.

Também existe a dúvida sobre usar Grok ou outro LLM gratuito e escolher um modelo de embedding que "case" com esse LLM.

## Decisão

LangGraph é o orquestrador principal do workflow. Ele coordena estado, branches, checkpoints, retries e human-in-the-loop.

LangChain pode ser usado dentro de adaptadores para LLMs, prompts, tools, structured output e retrievers, sem substituir contratos de domínio ou o grafo.

LiteLLM será usado como gateway/adaptador preferencial para trocar provedores de LLM, como Grok, Groq, OpenRouter, Ollama ou outros modelos gratuitos/baratos, sem espalhar detalhes de provider pela regra de negócio.

LlamaIndex é candidato para a camada de `NVIDIA Knowledge` quando a complexidade de RAG justificar ingestão, índices, retrievers, citações e reranking mais robustos. Como o alvo de `NVIDIA Knowledge` inclui busca lexical e vetorial, LlamaIndex pode entrar nessa camada como adapter, desde que `Recommendation` continue dependendo dos contratos próprios do projeto.

Pydantic pode ser considerado para novos schemas versionados externos.

Retrieval de `NVIDIA Knowledge` deve evoluir em fases:

1. busca lexical BM25 determinística com corpus oficial NVIDIA local;
2. busca vetorial com bi-encoder embeddings versionados;
3. Postgres local com `pgvector` como vector DB preferido quando embeddings precisarem ser persistidos e consultados por SQL;
4. busca híbrida combinando lexical e vetorial com merge/ranking reprodutível;
5. adapter LlamaIndex quando índice, retrieval, metadados, persistência ou citações justificarem;
6. reranking pós-busca sobre o top K, preferencialmente com cross-encoder ou alternativa auditável.

Busca vetorial só será considerada determinística quando corpus, chunking, embedding model, versão, índice, parâmetros e critérios de desempate estiverem fixados.

O LLM gerador e o modelo de embedding devem ficar desacoplados. A escolha do embedding deve ser validada por qualidade de recuperação, idioma, custo e estabilidade, não por pertencer ao mesmo fornecedor do LLM.

## Consequências

Benefícios:

- agentes futuros sabem onde cada framework entra;
- regra de negócio permanece testável e auditável;
- RAG evolui para lexical + vetorial sem abrir mão de rastreabilidade;
- Postgres/pgvector evita sincronizar um banco relacional com um vector DB externo no MVP;
- Grok ou outro LLM gratuito pode ser trocado sem reconstruir todo o domínio;
- embeddings e reranking ficam versionados e mensuráveis.

Custos:

- mais interfaces explícitas, como `LLMClient`, `EmbeddingClient` e retrievers;
- necessidade de migration e imagem Docker com pgvector quando o índice vetorial sair do modo local/in-memory;
- necessidade de medir retrieval antes de trocar modelos;
- disciplina para não deixar LangChain e LlamaIndex vazarem para Recommendation como contratos de domínio.

## Impacto no Código

Criar ou evoluir módulos como:

- `nvidia_knowledge.py` para documentos, chunks, citações e retrieval;
- `nvidia_recommendation.py` para recomendação por gap ou oportunidade;
- `briefing.py` para briefing versionado;
- `workflow_graph.py` para orquestração downstream;
- adaptadores futuros como `llm_clients.py`, `embedding_clients.py` e `nvidia_retrievers.py`.
- migrations futuras para `CREATE EXTENSION IF NOT EXISTS vector`, tabela de chunks, tabela de embeddings e índices HNSW/IVFFlat quando necessário.

Todo output de retrieval vetorial ou híbrido deve registrar modelo, versão, corpus, índice e estratégia de ranking.
