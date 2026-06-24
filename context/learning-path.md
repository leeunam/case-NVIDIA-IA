# Roteiro de Aprendizado Guiado

Objetivo: permitir que o usuário aprenda o código e a lógica do projeto na prática, escrevendo partes pequenas manualmente, sem perder TDD, rastreabilidade, arquitetura modular e coerência com o domínio.

Use este roteiro quando o usuário ativar `modo aprendizado` ou pedir para implementar escrevendo o código na mão.

## Como Trabalhar Nesse Modo

1. Escolha uma issue pequena e desbloqueada.
2. Leia `AGENTS.md`, `CONTEXT.md`, o PRD/roadmap relacionado e os módulos que serão tocados.
3. Explique o fluxo antes do código: entrada, regra, saída, teste e arquivo.
4. Escreva um teste pequeno primeiro.
5. Mostre ao usuário exatamente onde inserir o teste.
6. Explique o teste linha a linha.
7. Rode ou peça para rodar a suíte local e confirme o RED.
8. Mostre a implementação mínima em um bloco pequeno.
9. Explique a implementação linha a linha ou bloco a bloco.
10. Rode a suíte local e confirme o GREEN.
11. Revise o diff antes de commit.

Prompt sugerido:

```text
Ative modo aprendizado guiado.
Use a skill $tdd.
Trabalhe somente na issue #<numero>.
Não edite arquivos diretamente sem eu pedir.
Explique o fluxo, depois me mande o primeiro teste pequeno, com caminho do arquivo e explicação linha a linha.
Depois que eu escrever, revise meu diff e me oriente para o próximo passo.
```

## Trilha 1: Scraping e Coleta de Dados

Objetivo: entender como o projeto transforma uma busca em evidências públicas estruturadas.

Ordem de leitura recomendada:

1. `src/nvidia_startup_intel/search_params.py`: transforma texto do usuário em parâmetros estruturados.
2. `src/nvidia_startup_intel/search_plan.py`: gera termos e fontes de busca sem executar busca web.
3. `src/nvidia_startup_intel/search_execution.py`: executa o plano usando `SearchClient`.
4. `src/nvidia_startup_intel/discovery.py`: transforma resultados brutos em `Startup Candidate`.
5. `src/nvidia_startup_intel/startup_deduplication.py`: junta candidatas duplicadas.
6. `src/nvidia_startup_intel/scraping_policy.py`: decide bloqueios, rate limit, login e erros.
7. `src/nvidia_startup_intel/robots.py`: consulta e respeita `robots.txt`.
8. `src/nvidia_startup_intel/page_collection.py`: coleta páginas públicas.
9. `src/nvidia_startup_intel/startup_profile.py`: extrai `Startup Profile` com campos e evidências.
10. `src/nvidia_startup_intel/evidence.py`: agrupa evidências e marca conflitos.
11. `src/nvidia_startup_intel/collection_quality.py`: mede se a coleta está pronta para assessment.
12. `src/nvidia_startup_intel/pipeline.py`: junta as etapas em uma fachada.

Stack atual:

- `urllib` e `html.parser`: coleta e parsing simples no MVP.
- `RobotsCache`: respeito a `robots.txt` quando configurado.
- Fixtures e clientes fake: validação local sem rede.

Stack futura, só quando houver necessidade medida:

- Playwright: páginas JavaScript-heavy que não aparecem com HTML estático.
- BeautifulSoup: parsing HTML mais ergonômico quando `html.parser` simples ficar frágil.
- trafilatura: extração de texto principal em blogs, notícias e páginas ruidosas.
- Scrapy: crawling estruturado em escala.
- Firecrawl: extração limpa para RAG quando a base textual justificar serviço externo.

Regra arquitetural: essas ferramentas devem entrar por adapters ou funções específicas de coleta/parsing. Elas não devem alterar regras de domínio, schemas ou evidências brutas já coletadas.

## Trilha 2: AI-Native Assessment

Objetivo: entender como evidência pública vira diagnóstico sem inventar fatos.

Arquivos principais:

- `src/nvidia_startup_intel/ai_native_assessment.py`
- `context/domain-model.md`
- `context/roadmap-pipeline-avaliação.md`

Conceitos para aprender:

- diferença entre `Startup Candidate` e `Startup Profile`;
- evidência observada versus inferência;
- classificação `ai_native`, `ai_enabled` e `non_ai`;
- wrapper/API-dependency risk;
- technical gaps;
- preliminary opportunity signal, que não é prioridade final NVIDIA.

## Trilha 3: LangGraph e Orquestração

Objetivo: entender onde entra grafo, estado e branch sem colocar regra de negócio dentro do grafo.

Arquivos principais:

- `src/nvidia_startup_intel/scraping_graph.py`
- futuro `src/nvidia_startup_intel/workflow_graph.py`
- `src/nvidia_startup_intel/pipeline.py`

O que aprender:

- estado do workflow;
- nós finos;
- branches como `ready_for_ai_native_assessment`, `ready_for_recommendation`, `ready_for_briefing` e `human_review_requested`;
- runner local sem LangGraph instalado;
- LangGraph como orquestração, não como regra de negócio.

Exercício prático: primeiro entender o runner local; depois comparar com `build_langgraph`.

## Trilha 4: NVIDIA Knowledge e Retrieval

Objetivo: entender como buscar trechos citáveis oficiais NVIDIA antes de recomendar qualquer tecnologia.

Arquivos principais:

- `src/nvidia_startup_intel/nvidia_knowledge.py`
- `tests/test_nvidia_knowledge.py`
- `tests/fixtures/nvidia_knowledge_official_fixture.json`
- `context/roadmap-nvidia-knowledge-recommendation-briefing.md`

Ordem de aprendizado:

1. schema de documento, chunk, citação e resultado recuperado;
2. corpus local oficial;
3. chunking determinístico;
4. BM25 lexical;
5. qualidade de citação;
6. contrato de embedding;
7. busca vetorial;
8. merge híbrido;
9. reranking do top K;
10. métricas de retrieval.

## Trilha 5: BM25, Embeddings, Transformer e Reranking

BM25:

- Busca lexical.
- Usa frequência de termos no documento e raridade do termo no corpus.
- É bom baseline porque é explicável, barato e determinístico.
- No projeto, deve ser usado antes de embeddings para criar uma linha auditável.

Embedding:

- Transforma texto em vetor numérico.
- Permite busca semântica por similaridade.
- Deve ser acessado via `EmbeddingClient`, nunca espalhado pelo domínio.
- A suíte default deve usar embedding fake determinístico.

Transformer:

- Arquitetura de rede neural usada em LLMs, modelos de embedding e rerankers.
- No retrieval, costuma aparecer como encoder de embeddings ou como cross-encoder de reranking.
- O projeto deve tratar transformer como detalhe de adapter/modelo, não como regra de negócio.

Bi-encoder:

- Gera embedding separado para consulta e documentos.
- É rápido para vector search.
- Entra na busca vetorial.

Cross-encoder:

- Recebe consulta e documento juntos e calcula relevância.
- É mais caro, mas melhor para reranking.
- Deve reranquear apenas o top K já recuperado, preservando scores e citações originais.

Reranking:

- Não busca fatos novos.
- Reordena candidatos já recuperados.
- Deve preservar chunk, citação, score original, score de reranking e rationale.

## Trilha 6: Métricas de Retrieval

Objetivo: medir se o retrieval está melhorando em vez de trocar framework por preferência.

Precision@K:

```text
precision@k = documentos relevantes recuperados no top K / K
```

Recall@K:

```text
recall@k = documentos relevantes recuperados no top K / total de documentos relevantes esperados
```

Exemplo:

```text
Consulta: "model serving low latency inference"
Esperado: chunk nvidia-nim-developers:0
Top 3 retornado: nvidia-nim-developers:0, nvidia-inception:0, nvidia-deepstream-sdk:0

precision@3 = 1 / 3
recall@3 = 1 / 1
```

No projeto, métricas devem usar fixture com expectativas explícitas. Não use julgamento manual solto nem chamada externa na suíte default.

## Trilha 7: Recommendation, Briefing e Human Review

Objetivo: entender como retrieval vira decisão de abordagem sem misturar fato, inferência e recomendação.

Módulos principais:

- `src/nvidia_startup_intel/nvidia_recommendation.py`
- `src/nvidia_startup_intel/briefing.py`
- futuro `src/nvidia_startup_intel/workflow_graph.py`

Regras principais:

- Recommendation consome assessment e retrieval; não repete scraping.
- Recomendação técnica exige gap técnico, evidência da startup e citação oficial NVIDIA.
- Inception só entra com gap ou oportunidade comercial específica.
- Falta de fonte oficial vira hipótese ou bloqueio.
- Human Review Briefing deve conter startup, área, descobertas, gargalos, riscos, conflitos, unknowns e perguntas pendentes.

## Trilha 8: Frameworks

LangGraph:

- Orquestra fluxo, estado, branch, retry, checkpoint e intervenção humana.
- Não deve guardar regra de negócio.

LangChain:

- Útil para prompts, tools, retrievers e structured output dentro de adapters.
- Não substitui schemas do projeto.

LiteLLM:

- Gateway para trocar Grok, Groq, OpenRouter, Ollama ou outro provedor.
- Deve ficar atrás de `LLMClient`.

LlamaIndex:

- Opcional para RAG quando ingestão, índice, metadados, citações, vector/hybrid search ou reranking ficarem complexos.
- Deve ficar atrás de adapter de `NVIDIA Knowledge`.

Postgres/pgvector:

- Caminho local preferido para persistir embeddings.
- Permite juntar metadados, runs, chunks e vetores no mesmo banco.
- Não deve ser obrigatório na suíte default.

## Critérios de Qualidade Durante Aprendizado

- O aprendizado não justifica quebrar arquitetura.
- Toda mudança deve ter teste ou revisão clara.
- Toda recomendação deve preservar evidência e citação.
- Todo campo desconhecido continua `unknown`.
- Todo framework entra por necessidade concreta e adapter testável.
- O usuário pode escrever código manualmente, mas o agent deve revisar diff, testes, escopo e aderência ao domínio antes de commit.
