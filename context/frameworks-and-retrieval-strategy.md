# Frameworks de IA, Orquestração e Retrieval

Este documento orienta humanos e agentes de IA sobre quais frameworks podem entrar no projeto, onde cada um entra e quais limites não devem ser ultrapassados.

O mapa operacional para sair do core determinístico e chegar em scraping robusto, retrieval híbrido escalável, LangGraph real, LLM via Groq/LiteLLM e Postgres/pgvector está em `context/production-retrieval-and-scraping-architecture.md`.

## Regra Principal

Frameworks não são a regra de negócio do projeto.

A regra de negócio continua em módulos pequenos de Python, schemas explícitos e documentação de domínio. Frameworks entram para orquestrar fluxo, integrar modelos, recuperar conhecimento, validar saídas ou melhorar ergonomia de implementação.

Uma IA futura deve preservar esta separação:

```text
Domínio e contratos
-> adaptadores de busca, scraping, LLM, embedding e retrieval
-> orquestração de workflow
-> persistência e briefing
```

## Onde Cada Framework Entra

| Framework | Papel no projeto | Onde entra | Onde não entra |
| --- | --- | --- | --- |
| LangGraph | Orquestração principal de workflow com estado, branches, retries, checkpoints e human-in-the-loop. | `scraping_graph.py`, futuro `workflow_graph.py`, nós como `retrieve_nvidia_knowledge_node`, `recommend_nvidia_node` e `generate_briefing_node`. | Parsing crítico, classificação AI-native, deduplicação, recomendação ou decisão de negócio escondida em nó grande. |
| LangChain | Integração com LLMs, prompts, tools, structured output, retrievers e adapters. | Dentro de nós ou adaptadores testáveis, por exemplo `llm_clients.py`, `retrievers.py`, `briefing_generation.py`. | Orquestração global do fluxo, storage da regra de negócio ou substituto dos schemas do projeto. |
| LiteLLM | Gateway/adaptador unificado para trocar Grok, Groq, OpenRouter, Ollama ou outros modelos sem mudar domínio. | `llm_clients.py` ou adapter chamado por LangChain. | Não define regra de negócio, prompts finais ou ranking de recomendação. |
| LlamaIndex | Candidato forte para RAG quando ingestão, indexação, chunking, retrievers e citações ficarem complexos. | `nvidia_knowledge.py` ou adaptadores de índice/retrieval sobre fontes oficiais NVIDIA. | Não deve virar um agente genérico que recomenda sem passar por `nvidia_recommendation.py`. |
| Pydantic | Validação e serialização de contratos estruturados. | Novos schemas externos como `nvidia_knowledge.v1`, `nvidia_recommendation.v1`, `executive_briefing.v1` quando trouxer clareza. | Migração obrigatória de todos os dataclasses existentes sem necessidade concreta. |

Decisão prática: usar LangGraph como grafo principal, LangChain como harness/adaptador de LLM e tools, LiteLLM como camada de troca de provedores e LlamaIndex como adapter de RAG quando a complexidade de `NVIDIA Knowledge` justificar. Como o alvo de `NVIDIA Knowledge` agora inclui busca lexical e vetorial, LlamaIndex é uma opção válida para essa camada, mas ainda deve ficar atrás de contratos próprios do projeto.

## Como a Orquestração Deve Ficar

O fluxo completo deve continuar nesta ordem:

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

LangGraph deve coordenar:

- estado compartilhado e artefatos por run;
- branches como `needs_more_collection_or_human_review`, `ready_for_recommendation`, `ready_for_briefing` e `human_review_requested`;
- retries de adaptadores externos;
- checkpoints para reprocessar recommendation ou briefing sem repetir scraping;
- intervenção humana quando houver baixo sinal, conflito, alto wrapper risk ou falta de fonte oficial.

LangGraph não deve calcular regra de negócio diretamente. Um nó chama funções ou serviços pequenos e devolve estado explícito.

## Como LangChain Entra

LangChain pode ser usado quando o projeto precisar plugar um LLM, tool ou retriever sem amarrar a regra de negócio a um provedor específico.

Casos válidos:

- adaptar Grok, outro LLM gratuito ou modelo local atrás de uma interface `LLMClient`;
- gerar structured output validado por schema;
- montar prompts versionados para briefing narrativo;
- chamar tools controladas dentro de um nó;
- conectar retrievers quando a implementação escolhida for LangChain.

Regras:

- toda chamada de LLM deve ter entrada e saída versionadas;
- testes locais usam fake clients ou fixtures, não chamadas reais;
- prompts não podem inventar clientes, funding, tecnologias ou recomendações;
- se o modelo falhar, a saída deve virar `unknown`, hipótese ou `human_review_requested`.

## Como LiteLLM Entra

LiteLLM deve ser tratado como gateway ou adapter para chamadas de modelo. Ele ajuda a trocar entre Grok, Groq, OpenRouter, Ollama, Hugging Face ou outros modelos gratuitos/baratos sem espalhar detalhes de provider pelo domínio.

Casos válidos:

- implementar `LLMClient` com fallback e retry;
- testar modelos diferentes para geração de briefing;
- centralizar configuração de chave, endpoint, timeout e custo;
- manter LangChain independente do provedor real.

Regras:

- credenciais e endpoints ficam fora do código de domínio;
- testes locais usam fake client, não LiteLLM real;
- saída de modelo continua passando por schema e quality gates;
- LiteLLM não escolhe tecnologia NVIDIA nem decide prioridade.

## Como LlamaIndex Entra

LlamaIndex faz sentido principalmente se `NVIDIA Knowledge` evoluir para uma camada RAG híbrida com:

- ingestão de documentos oficiais NVIDIA;
- chunking com metadados;
- índices lexical, vetorial ou híbrido;
- retrievers;
- citações por chunk;
- reranking;
- cache de embeddings.

Ele deve ficar atrás de adaptadores. O domínio deve enxergar apenas contratos como:

- `NVIDIADocument`;
- `NVIDIAChunk`;
- `NVIDIACitation`;
- `NVIDIAKnowledgeRetrieval`;
- `RetrievedChunk`.

Se LlamaIndex for adotado para RAG, mantenha LangChain fora do contrato interno de retrieval desse mesmo slice. LangChain ainda pode ficar restrito ao LLM client, prompts ou tools.

## Estratégia de Busca NVIDIA

A recuperação de conhecimento NVIDIA deve ter como alvo busca híbrida reprodutível: lexical + vetorial + merge/ranking determinístico. "Determinístico", aqui, significa que a mesma versão do corpus, mesmo chunking, mesmo modelo de embedding, mesmo índice e mesmos parâmetros retornam a mesma ordenação.

### Fase 1: Busca Lexical

Primeira fatia implementável:

- corpus local versionado de fontes oficiais NVIDIA;
- chunking determinístico;
- busca lexical BM25 por termos de gap, tecnologia, programa e sinais da startup;
- ranking simples e auditável;
- zero LLM, zero embedding, zero rede nos testes.

Essa fase valida contratos e cria baseline de recuperação.

### Fase 2: Busca Vetorial

Adicionar embeddings para recuperar trechos por similaridade semântica.

Regras:

- embeddings devem ser versionados junto com `corpus_version`;
- mudança de modelo exige rebuild do índice;
- o output deve registrar `embedding_model`, `embedding_version`, dimensão, índice e estratégia de ranking;
- embeddings não substituem citações oficiais;
- busca vetorial só recupera candidatos, não cria fatos;
- quando possível, preferir índice local/reprodutível antes de vector DB externo;
- empates devem ter critério estável, como `document_id`, `chunk_index` e score lexical.

### Fase 2.5: Vector DB Local Com Postgres/pgvector

O vector DB preferido para o projeto é Postgres local com `pgvector`, não um serviço externo separado.

Como entraria:

- o `docker-compose.yml` deixa de usar Postgres puro e passa a usar uma imagem com `pgvector`, ou instala a extensão no Postgres atual;
- uma migration executa `CREATE EXTENSION IF NOT EXISTS vector`;
- chunks oficiais NVIDIA ficam em tabelas relacionais com metadados auditáveis;
- embeddings ficam em coluna `vector(<dimensao>)`;
- busca vetorial usa distância coseno, inner product ou L2, conforme o embedding escolhido;
- índices HNSW ou IVFFlat entram quando o corpus crescer e a busca exata ficar lenta.

Por que é positivo:

- mantém documentos, metadados, embeddings, execuções e recomendações no mesmo banco;
- permite filtros SQL por `corpus_version`, documento, tecnologia, tipo de fonte e data;
- reduz sincronização entre Postgres e um vector DB externo;
- facilita auditoria, backup local e reprocessamento;
- combina bem com Docker local e com o plano futuro de histórico auditável em Postgres.

Limites:

- para corpus pequeno, busca vetorial local em memória ou SQL exato pode bastar antes de índice aproximado;
- HNSW/IVFFlat podem trocar recall por velocidade, então parâmetros precisam ser versionados;
- vector DB não substitui BM25, citações oficiais nem quality gate de recomendação.

### Fase 3: Busca Híbrida

Combinar lexical e vetorial para reduzir perda de recall.

Uma estratégia aceitável:

```text
top_k_lexical
+ top_k_vector
-> merge e deduplicação
-> score combinado ou reciprocal rank fusion
-> candidate_top_k
```

Busca lexical ajuda em nomes de tecnologias, siglas e programas. Busca vetorial ajuda quando o gap usa vocabulário diferente do documento oficial. O merge deve ser reprodutível e auditar quanto cada fonte contribuiu para o score final.

### Fase 4: Adapter LlamaIndex Quando Necessário

Como o alvo inclui mais que lexical, LlamaIndex pode entrar como adapter para:

- ingestão e parsing de documentos oficiais NVIDIA;
- índices vetoriais ou híbridos;
- retrievers com metadados;
- persistência/carregamento de índices;
- reranking ou node postprocessors;
- citações por chunk.

Mesmo usando LlamaIndex, o domínio do projeto continua falando em `NVIDIADocument`, `NVIDIAChunk`, `NVIDIACitation`, `NVIDIAKnowledgeRetrieval` e `RetrievedChunk`. A Recommendation não deve depender diretamente de objetos internos do LlamaIndex.

### Fase 5: Reranking Pós-Busca

Reranking deve acontecer sobre o `candidate_top_k`, não sobre o corpus inteiro.

Opções:

- cross-encoder reranker local ou barato;
- reranker de biblioteca quando houver justificativa;
- LLM-as-reranker apenas se custo, estabilidade e rastreabilidade forem aceitáveis.

O reranker só pode reordenar ou descartar chunks. Ele não pode gerar novas afirmações. O output precisa preservar score, rationale curto, chunk original e citação oficial.

## Embedding, Bi-Encoder e LLM

O LLM gerador e o modelo de embedding não precisam ser do mesmo fornecedor. A combinação precisa funcionar na tarefa de recuperação.

Para este projeto, o embedding deve ser escolhido por:

- capacidade de recuperar documentação técnica NVIDIA;
- suporte a português e inglês, ou estratégia explícita de tradução/expansão de consulta;
- qualidade em testes locais de retrieval;
- custo e possibilidade de uso offline ou gratuito;
- estabilidade de versão.

Se a IA principal for Grok ou outro LLM gratuito, use um adaptador `LLMClient` separado de `EmbeddingClient`. Não acople a escolha do embedding ao LLM por intuição.

Termos práticos:

- `bi-encoder`: modelo usado para embedar query e documento separadamente, bom para busca vetorial em escala;
- `cross-encoder`: modelo que lê query e documento juntos, melhor para reranking de poucos candidatos;
- `embedding`: vetor usado pela busca vetorial;
- `reranking`: reordenação do top K recuperado.

Sequência recomendada:

```text
lexical primeiro
-> busca vetorial com bi-encoder
-> busca híbrida
-> adapter LlamaIndex se índice/retrieval ficar complexo
-> cross-encoder ou LLM reranker se o top K ainda vier ruidoso
```

## Métricas Mínimas

Antes de trocar modelo, embedding ou framework de retrieval, medir:

- recall@k de chunks relevantes;
- precision@k de citações úteis;
- taxa de recomendação sem fonte oficial;
- taxa de briefing enviado para human review por falta de fonte;
- casos em que lexical encontra e vetorial perde;
- casos em que vetorial encontra e lexical perde;
- impacto do reranking no top 1 por gap.

## Antipadrões

Evite:

- colocar recomendação NVIDIA diretamente em prompt;
- deixar LLM escolher tecnologia NVIDIA sem citação oficial;
- misturar LangChain e LlamaIndex no mesmo retrieval sem adapter claro;
- usar vector DB externo antes de validar corpus, chunks, busca lexical e busca vetorial local;
- apresentar saída de reranker como fato novo;
- depender de rede, credenciais ou modelo externo na suíte local.
